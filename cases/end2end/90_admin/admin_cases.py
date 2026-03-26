from cytest import STEP, INFO, CHECK_POINT, GSTORE

from lib.saleor_api import SaleorGraphQLError, gql_request, me
from lib.gql_diagnose import summarize_gql_failure


def _require_saleor_api_ready():
    url = getattr(GSTORE, "saleor_graphql_url", "")
    if url is None:
        url = ""
    if url == "":
        raise RuntimeError("BLOCKED: 未配置 SALEOR_GRAPHQL_URL")
    if getattr(GSTORE, "saleor_api_callable", True) is False:
        raise RuntimeError("BLOCKED: SALEOR_GRAPHQL_URL 不支持 POST GraphQL")


class cADMIN0001:
    name = "ADMIN-0001-me 查询必须返回 staff 用户（鉴权验证）"
    tags = ["API", "冒烟"]

    def teststeps(self):
        _require_saleor_api_ready()
        url = GSTORE.saleor_graphql_url
        token = getattr(GSTORE, "saleor_access_token", None)
        if not token:
            raise RuntimeError("BLOCKED: 未获取到 staff token")

        STEP(1, "me 查询，验证 isStaff")
        user, errors, raw = me(url, token, timeout_s=GSTORE.http_timeout_s)
        CHECK_POINT("GraphQL errors 为空", errors == [], failStop=False)
        if errors:
            INFO(summarize_gql_failure(title="ADMIN-0001 me errors", errors=errors, raw=raw))
        CHECK_POINT("me 返回 dict", isinstance(user, dict))
        if isinstance(user, dict):
            CHECK_POINT("isStaff == True", user.get("isStaff") is True, failStop=False)


class cADMIN0002:
    name = "ADMIN-0002-channels 列表（需要 staff 权限）"
    tags = ["API", "回归"]

    def teststeps(self):
        _require_saleor_api_ready()
        url = GSTORE.saleor_graphql_url
        token = getattr(GSTORE, "saleor_access_token", None)
        if not token:
            raise RuntimeError("BLOCKED: 未获取到 staff token")

        STEP(1, "查询 channels { id slug name }")
        query = "query { channels { id slug name } }"
        try:
            data, errors, raw = gql_request(url, query, token=token, timeout_s=GSTORE.http_timeout_s)
        except SaleorGraphQLError as e:
            INFO(summarize_gql_failure(title="ADMIN-0002 channels 失败", exc=e))
            CHECK_POINT("channels 请求应成功返回", False)
            return

        CHECK_POINT("GraphQL errors 为空", errors == [], failStop=False)
        if errors:
            INFO(summarize_gql_failure(title="ADMIN-0002 channels errors", errors=errors, raw=raw))

        channels = data.get("channels") if isinstance(data, dict) else None
        CHECK_POINT("channels 为 list", isinstance(channels, list))
        if isinstance(channels, list) and len(channels) > 0 and isinstance(channels[0], dict):
            CHECK_POINT("channel.slug 非空", bool(channels[0].get("slug")), failStop=False)

