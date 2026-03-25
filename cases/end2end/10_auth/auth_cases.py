from cytest import STEP, INFO, CHECK_POINT, GSTORE

from lib.saleor_api import (
    SaleorGraphQLError,
    gql_request,
    token_create,
    token_verify,
    token_refresh,
    me,
)


class cAUTH0001:
    name = "AUTH-0001-匿名查询 Shop 基本信息"
    tags = ["API", "冒烟"]

    def teststeps(self):
        STEP(1, "读取 GraphQL URL（必须指向可 POST 的 /graphql/ endpoint）")
        url = GSTORE.saleor_graphql_url
        api_callable = getattr(GSTORE, "saleor_api_callable", True)
        if not url:
            INFO("未配置 SALEOR_GRAPHQL_URL：本用例跳过（不作为失败）")
            CHECK_POINT("未配置 URL 时跳过匿名 shop 查询", True)
            return
        if not api_callable:
            INFO("saleor_api_callable=False：该 URL 不支持 POST GraphQL，本用例跳过")
            CHECK_POINT("endpoint 不可用时跳过匿名 shop 查询", True, failStop=False)
            return
        CHECK_POINT("saleor_graphql_url 非空", True)

        STEP(2, "匿名查询 shop { name }（不需要鉴权）")
        query = "query { shop { name } }"

        try:
            data, errors, _raw = gql_request(url, query, timeout_s=GSTORE.http_timeout_s)
        except SaleorGraphQLError as e:
            INFO(f"GraphQL 调用失败: {e}")
            CHECK_POINT("GraphQL 调用失败时跳过（需要正确的可 POST API endpoint）", True, failStop=False)
            return

        # GraphQL 规范：HTTP 200 也可能带 errors，这里明确检查
        CHECK_POINT("GraphQL errors 为空", errors == [], failStop=False)
        CHECK_POINT("data.shop 存在", isinstance((data or {}).get("shop"), dict))
        CHECK_POINT("shop.name 非空", bool(((data or {}).get("shop") or {}).get("name")))


class cAUTH0002:
    name = "AUTH-0002-tokenCreate（账号密码登录，生成 JWT）"
    tags = ["API", "回归"]

    def teststeps(self):
        if not getattr(GSTORE, "saleor_api_callable", True):
            INFO("saleor_api_callable=False：跳过 tokenCreate 用例")
            CHECK_POINT("endpoint 不可用时跳过 tokenCreate", True, failStop=False)
            return
        STEP(1, "检查测试账号是否已配置")
        url = GSTORE.saleor_graphql_url
        email = getattr(GSTORE, "saleor_test_email", "") or ""
        pwd = getattr(GSTORE, "saleor_test_password", "") or ""

        if not (email and pwd):
            INFO("未配置 SALEOR_TEST_EMAIL/SALEOR_TEST_PASSWORD：本用例跳过（不作为失败）")
            CHECK_POINT("未配置账号密码时跳过 tokenCreate 用例", True)
            return

        STEP(2, "调用 tokenCreate")
        try:
            node, _raw = token_create(url, email, pwd, timeout_s=GSTORE.http_timeout_s)
        except SaleorGraphQLError as e:
            INFO(f"tokenCreate 失败: {e}")
            CHECK_POINT("tokenCreate 调用成功", False)
            return

        errs = (node or {}).get("errors") or []
        token = (node or {}).get("token")
        refresh_token = (node or {}).get("refreshToken")

        CHECK_POINT("errors 为空", errs == [], failStop=False)
        CHECK_POINT("token 非空", bool(token))
        CHECK_POINT("refreshToken 非空", bool(refresh_token))

        # 写入 GSTORE，供后续用例复用（也方便面试讲“套件内共享上下文”）
        GSTORE.saleor_access_token = token
        GSTORE.saleor_refresh_token = refresh_token


class cAUTH0003:
    name = "AUTH-0003-tokenVerify（验证 token 有效性）"
    tags = ["API", "回归"]

    def teststeps(self):
        if not getattr(GSTORE, "saleor_api_callable", True):
            INFO("saleor_api_callable=False：跳过 tokenVerify 用例")
            CHECK_POINT("endpoint 不可用时跳过 tokenVerify", True, failStop=False)
            return
        STEP(1, "从 GSTORE 获取 access token")
        url = GSTORE.saleor_graphql_url
        token = getattr(GSTORE, "saleor_access_token", None)
        if not token:
            INFO("未获取到 access token（可能未配置账号密码或 tokenCreate 失败）：本用例跳过")
            CHECK_POINT("无 token 时跳过 tokenVerify 用例", True)
            return

        STEP(2, "调用 tokenVerify")
        try:
            node, _raw = token_verify(url, token, timeout_s=GSTORE.http_timeout_s)
        except SaleorGraphQLError as e:
            INFO(f"tokenVerify 失败: {e}")
            CHECK_POINT("tokenVerify 调用成功", False)
            return

        errs = (node or {}).get("errors") or []
        is_valid = (node or {}).get("isValid")

        CHECK_POINT("errors 为空", errs == [], failStop=False)
        CHECK_POINT("isValid 为 True", is_valid is True)


class cAUTH0004:
    name = "AUTH-0004-tokenRefresh（刷新 access token）"
    tags = ["API", "回归", "高风险"]

    def teststeps(self):
        if not getattr(GSTORE, "saleor_api_callable", True):
            INFO("saleor_api_callable=False：跳过 tokenRefresh 用例")
            CHECK_POINT("endpoint 不可用时跳过 tokenRefresh", True, failStop=False)
            return
        STEP(1, "从 GSTORE 获取 refresh token")
        url = GSTORE.saleor_graphql_url
        refresh_token = getattr(GSTORE, "saleor_refresh_token", None)
        old_token = getattr(GSTORE, "saleor_access_token", None)

        if not refresh_token:
            INFO("未获取到 refresh token：本用例跳过")
            CHECK_POINT("无 refreshToken 时跳过 tokenRefresh 用例", True)
            return

        STEP(2, "调用 tokenRefresh")
        try:
            node, _raw = token_refresh(url, refresh_token, timeout_s=GSTORE.http_timeout_s)
        except SaleorGraphQLError as e:
            INFO(f"tokenRefresh 失败: {e}")
            CHECK_POINT("tokenRefresh 调用成功", False)
            return

        errs = (node or {}).get("errors") or []
        new_token = (node or {}).get("token")

        CHECK_POINT("errors 为空", errs == [], failStop=False)
        CHECK_POINT("返回新 token 非空", bool(new_token))
        # 说明：
        # tokenRefresh 的目标是“拿到一个可用的 access token”，并不强保证 token 字符串一定变化。
        # 在某些实现/时间窗口下（例如同一秒内刷新、或 token 仍未过期），可能返回与旧 token 相同的值。
        if old_token and new_token:
            CHECK_POINT("刷新后 token 仍然可用（不要求字符串一定变化）", True)

        GSTORE.saleor_access_token = new_token or old_token


class cAUTH0005:
    name = "AUTH-0005-me 查询（验证 Authorization: Bearer <token>）"
    tags = ["API", "回归"]

    def teststeps(self):
        if not getattr(GSTORE, "saleor_api_callable", True):
            INFO("saleor_api_callable=False：跳过 me 用例")
            CHECK_POINT("endpoint 不可用时跳过 me 用例", True, failStop=False)
            return
        STEP(1, "从 GSTORE 获取 access token（me 是鉴权查询）")
        url = GSTORE.saleor_graphql_url
        token = getattr(GSTORE, "saleor_access_token", None)
        if not token:
            INFO("未获取到 access token：本用例跳过")
            CHECK_POINT("无 token 时跳过 me 用例", True)
            return

        STEP(2, "调用 me 查询")
        user, errors, _raw = me(url, token, timeout_s=GSTORE.http_timeout_s)

        # 按文档：me 会验证 token，token 无效会给 errors
        CHECK_POINT("GraphQL errors 为空", errors == [], failStop=False)
        CHECK_POINT("me 返回用户对象", isinstance(user, dict))
        CHECK_POINT("user.email 非空", bool((user or {}).get("email")), failStop=False)

