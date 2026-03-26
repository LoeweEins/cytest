from cytest import STEP, INFO, CHECK_POINT, GSTORE

from lib.saleor_api import SaleorGraphQLError, gql_request
from lib.gql_diagnose import summarize_gql_failure


def _require_saleor_api_ready():
    url = getattr(GSTORE, "saleor_graphql_url", "")
    if url is None:
        url = ""
    if url == "":
        raise RuntimeError("BLOCKED: 未配置 SALEOR_GRAPHQL_URL")
    if getattr(GSTORE, "saleor_api_callable", True) is False:
        raise RuntimeError("BLOCKED: SALEOR_GRAPHQL_URL 不支持 POST GraphQL")


def _pick_channel_slug_or_block():
    slug = getattr(GSTORE, "saleor_channel_slug", "")
    if slug is None:
        slug = ""
    if slug != "":
        return slug

    token = getattr(GSTORE, "saleor_access_token", None)
    if not token:
        raise RuntimeError("BLOCKED: 未配置 SALEOR_CHANNEL_SLUG 且无 staff token，无法自动确定 channel")

    url = GSTORE.saleor_graphql_url
    data, errors, raw = gql_request(url, "query { channels { slug } }", token=token, timeout_s=GSTORE.http_timeout_s)
    if errors:
        INFO(summarize_gql_failure(title="PAY 自动查询 channels 失败", errors=errors, raw=raw))
        raise RuntimeError("BLOCKED: 查询 channels 失败（权限不足）")
    channels = data.get("channels") if data else None
    if not isinstance(channels, list) or len(channels) == 0:
        raise RuntimeError("BLOCKED: channels 为空")
    first = channels[0]
    if not isinstance(first, dict):
        raise RuntimeError("BLOCKED: channels[0] 结构异常")
    slug = first.get("slug")
    if not slug:
        raise RuntimeError("BLOCKED: channel.slug 为空")
    GSTORE.saleor_channel_slug = slug
    return slug


class cPAY0001:
    name = "PAY-0001-匿名调用 payments 列表应被拒绝（权限校验）"
    tags = ["API", "回归"]

    def teststeps(self):
        _require_saleor_api_ready()
        url = GSTORE.saleor_graphql_url

        STEP(1, "匿名查询 payments(first=1)")
        query = "query { payments(first: 1) { totalCount } }"
        variables = {}

        try:
            data, errors, raw = gql_request(url, query, variables=variables, timeout_s=GSTORE.http_timeout_s)
        except SaleorGraphQLError as e:
            INFO(summarize_gql_failure(title="PAY-0001 payments 匿名调用异常", exc=e, variables=variables))
            CHECK_POINT("GraphQL 应返回 JSON（即使有 errors）", False)
            return

        CHECK_POINT("GraphQL errors 非空（匿名不可访问 payments）", isinstance(errors, list) and len(errors) > 0)
        if errors:
            INFO(summarize_gql_failure(title="PAY-0001 预期权限错误", errors=errors, raw=raw, variables=variables))


class cPAY0002:
    name = "PAY-0002-staff 查询 payments 列表字段契约"
    tags = ["API", "冒烟"]

    def teststeps(self):
        _require_saleor_api_ready()
        url = GSTORE.saleor_graphql_url
        token = getattr(GSTORE, "saleor_access_token", None)
        if not token:
            raise RuntimeError("BLOCKED: 未获取到 staff token（无法访问 payments 列表）")

        STEP(1, "staff token 查询 payments(first=3)")
        query = """
        query {
          payments(first: 3) {
            totalCount
            edges {
              node {
                id
                gateway
                chargeStatus
              }
            }
          }
        }
        """
        variables = {}

        try:
            data, errors, raw = gql_request(url, query, variables=variables, token=token, timeout_s=GSTORE.http_timeout_s)
        except SaleorGraphQLError as e:
            INFO(summarize_gql_failure(title="PAY-0002 payments staff 调用失败", exc=e))
            CHECK_POINT("payments staff 请求应成功返回", False)
            return

        CHECK_POINT("GraphQL errors 为空", errors == [], failStop=False)
        if errors:
            INFO(summarize_gql_failure(title="PAY-0002 GraphQL errors 非空", errors=errors, raw=raw))

        conn = data.get("payments") if isinstance(data, dict) else None
        CHECK_POINT("data.payments 存在", isinstance(conn, dict))
        if not isinstance(conn, dict):
            return
        CHECK_POINT("totalCount 为 int 且 >=0", isinstance(conn.get("totalCount"), int) and conn.get("totalCount") >= 0, failStop=False)
        edges = conn.get("edges")
        CHECK_POINT("edges 为 list", isinstance(edges, list))

