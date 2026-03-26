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


class cORDER0001:
    name = "ORDER-0001-匿名查询 orders 应被拒绝（权限校验）"
    tags = ["API", "回归", "安全"]

    def teststeps(self):
        _require_saleor_api_ready()
        url = GSTORE.saleor_graphql_url

        STEP(1, "匿名调用 orders(first=1)")
        query = """
        query {
          orders(first: 1) {
            totalCount
          }
        }
        """
        try:
            data, errors, raw = gql_request(url, query, timeout_s=GSTORE.http_timeout_s)
        except SaleorGraphQLError as e:
            INFO(summarize_gql_failure(title="ORDER-0001 orders 匿名调用异常", exc=e))
            CHECK_POINT("GraphQL 请求应返回 JSON（即使有 errors）", False)
            return

        # 真实断言：应出现权限错误（errors 非空）
        CHECK_POINT("GraphQL errors 非空（匿名不可访问 orders）", isinstance(errors, list) and len(errors) > 0)
        if errors:
            INFO(summarize_gql_failure(title="ORDER-0001 预期权限错误", errors=errors, raw=raw))


class cORDER0002:
    name = "ORDER-0002-staff 查询 orders 列表字段契约"
    tags = ["API", "冒烟"]

    def teststeps(self):
        _require_saleor_api_ready()
        url = GSTORE.saleor_graphql_url
        token = getattr(GSTORE, "saleor_access_token", None)
        if not token:
            raise RuntimeError("BLOCKED: 未获取到 staff token（无法访问 orders 列表）")

        STEP(1, "staff token 调用 orders(first=3)")
        query = """
        query {
          orders(first: 3) {
            totalCount
            edges {
              node {
                id
                number
                status
              }
            }
          }
        }
        """
        try:
            data, errors, raw = gql_request(url, query, token=token, timeout_s=GSTORE.http_timeout_s)
        except SaleorGraphQLError as e:
            INFO(summarize_gql_failure(title="ORDER-0002 orders staff 调用失败", exc=e))
            CHECK_POINT("orders staff 请求应成功返回", False)
            return

        CHECK_POINT("GraphQL errors 为空", errors == [], failStop=False)
        if errors:
            INFO(summarize_gql_failure(title="ORDER-0002 GraphQL errors 非空", errors=errors, raw=raw))

        conn = data.get("orders") if isinstance(data, dict) else None
        CHECK_POINT("data.orders 存在", isinstance(conn, dict))
        if not isinstance(conn, dict):
            return

        total = conn.get("totalCount")
        CHECK_POINT("totalCount 为 int 且 >=0", isinstance(total, int) and total >= 0, failStop=False)
        edges = conn.get("edges")
        CHECK_POINT("edges 为 list", isinstance(edges, list))
        if isinstance(edges, list) and len(edges) > 0 and isinstance(edges[0], dict):
            node = edges[0].get("node")
            CHECK_POINT("首个 node 为 dict", isinstance(node, dict))
            if isinstance(node, dict):
                CHECK_POINT("order.id 非空", bool(node.get("id")), failStop=False)

