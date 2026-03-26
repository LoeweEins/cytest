from cytest import STEP, INFO, CHECK_POINT, GSTORE

from lib.saleor_api import (
    SaleorGraphQLError,
    gql_request,
    token_create,
    token_verify,
    token_refresh,
    me,
)
from lib.gql_diagnose import summarize_gql_failure

def _require_saleor_api_ready():
    """
    需求：当 URL 未配置 或 endpoint 不支持 POST 时，不再跳过，而是直接“阻塞/异常”。

    cytest 的结果分类里没有独立的 blocked 状态；这里用 RuntimeError 抛出，
    Runner 会把用例标记为 abort（在报告里表现为 Abort/Blocked）。
    """
    url = getattr(GSTORE, "saleor_graphql_url", "")
    if url is None:
        url = ""
    if url == "":
        raise RuntimeError("BLOCKED: 未配置 SALEOR_GRAPHQL_URL（需要可 POST 的 /graphql/ endpoint）")

    api_callable = getattr(GSTORE, "saleor_api_callable", True)
    if api_callable is False:
        raise RuntimeError("BLOCKED: SALEOR_GRAPHQL_URL 不支持 POST GraphQL（请换成真正的 API endpoint）")


class cAUTH0001:
    name = "AUTH-0001-匿名查询 Shop 基本信息"
    tags = ["API", "冒烟"]

    def teststeps(self):
        _require_saleor_api_ready()
        STEP(1, "读取 GraphQL URL（必须指向可 POST 的 /graphql/ endpoint）")
        url = GSTORE.saleor_graphql_url
        CHECK_POINT("saleor_graphql_url 非空", bool(url))

        STEP(2, "匿名查询 shop { name }（不需要鉴权）")
        query = "query { shop { name } }"

        try:
            data, errors, _raw = gql_request(url, query, timeout_s=GSTORE.http_timeout_s)
        except SaleorGraphQLError as e:
            INFO(
                summarize_gql_failure(
                    title="AUTH-0001 shop 查询失败",
                    exc=e,
                )
            )
            CHECK_POINT("GraphQL 请求应成功返回（网络/URL/服务可用）", False)
            return

        # GraphQL 规范：HTTP 200 也可能带 errors，这里明确检查
        CHECK_POINT("GraphQL errors 为空", errors == [], failStop=False)
        if errors:
            INFO(
                summarize_gql_failure(
                    title="AUTH-0001 GraphQL errors 非空",
                    errors=errors,
                    raw=_raw,
                )
            )
        if data is None:
            shop = None
        else:
            shop = data.get("shop")
        CHECK_POINT("data.shop 存在", isinstance(shop, dict))
        if isinstance(shop, dict):
            shop_name = shop.get("name")
        else:
            shop_name = None
        CHECK_POINT("shop.name 非空", bool(shop_name))


class cAUTH0002:
    name = "AUTH-0002-tokenCreate（账号密码登录，生成 JWT）"
    tags = ["API", "回归"]

    def teststeps(self):
        _require_saleor_api_ready()
        STEP(1, "检查测试账号是否已配置")
        url = GSTORE.saleor_graphql_url
        email = getattr(GSTORE, "saleor_test_email", "")
        pwd = getattr(GSTORE, "saleor_test_password", "")
        if email is None:
            email = ""
        if pwd is None:
            pwd = ""

        if not (email and pwd):
            raise RuntimeError("BLOCKED: 未配置 SALEOR_TEST_EMAIL/SALEOR_TEST_PASSWORD（无法执行 tokenCreate）")

        STEP(2, "调用 tokenCreate")
        try:
            node, _raw = token_create(url, email, pwd, timeout_s=GSTORE.http_timeout_s)
        except SaleorGraphQLError as e:
            INFO(
                summarize_gql_failure(
                    title="AUTH-0002 tokenCreate 失败",
                    exc=e,
                    variables={"email": email, "password": pwd},
                )
            )
            CHECK_POINT("tokenCreate 调用成功", False)
            return

        errs = []
        token = None
        refresh_token = None
        if node is not None:
            errs = node.get("errors") or []
            token = node.get("token")
            refresh_token = node.get("refreshToken")

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
        _require_saleor_api_ready()
        STEP(1, "从 GSTORE 获取 access token")
        url = GSTORE.saleor_graphql_url
        token = getattr(GSTORE, "saleor_access_token", None)
        if not token:
            raise RuntimeError("BLOCKED: 未获取到 access token（请先跑通 tokenCreate 或在套件初始化中获取 token）")

        STEP(2, "调用 tokenVerify")
        try:
            node, _raw = token_verify(url, token, timeout_s=GSTORE.http_timeout_s)
        except SaleorGraphQLError as e:
            INFO(
                summarize_gql_failure(
                    title="AUTH-0003 tokenVerify 失败",
                    exc=e,
                    variables={"token": token},
                )
            )
            CHECK_POINT("tokenVerify 调用成功", False)
            return

        errs = []
        is_valid = None
        if node is not None:
            errs = node.get("errors") or []
            is_valid = node.get("isValid")

        CHECK_POINT("errors 为空", errs == [], failStop=False)
        CHECK_POINT("isValid 为 True", is_valid is True)


class cAUTH0004:
    name = "AUTH-0004-tokenRefresh（刷新 access token）"
    tags = ["API", "回归", "高风险"]

    def teststeps(self):
        _require_saleor_api_ready()
        STEP(1, "从 GSTORE 获取 refresh token")
        url = GSTORE.saleor_graphql_url
        refresh_token = getattr(GSTORE, "saleor_refresh_token", None)
        old_token = getattr(GSTORE, "saleor_access_token", None)

        if not refresh_token:
            raise RuntimeError("BLOCKED: 未获取到 refresh token（请先跑通 tokenCreate 或在套件初始化中获取 refreshToken）")

        STEP(2, "调用 tokenRefresh")
        try:
            node, _raw = token_refresh(url, refresh_token, timeout_s=GSTORE.http_timeout_s)
        except SaleorGraphQLError as e:
            INFO(
                summarize_gql_failure(
                    title="AUTH-0004 tokenRefresh 失败",
                    exc=e,
                    variables={"refreshToken": refresh_token},
                )
            )
            CHECK_POINT("tokenRefresh 调用成功", False)
            return

        errs = []
        new_token = None
        if node is not None:
            errs = node.get("errors") or []
            new_token = node.get("token")

        CHECK_POINT("errors 为空", errs == [], failStop=False)
        CHECK_POINT("返回新 token 非空", bool(new_token))
        # 真实断言：刷新后的 token 是否“可用”，应通过 Saleor 的 tokenVerify（或 me 查询）验证。
        # 注意：tokenRefresh 不强保证 token 字符串一定变化，因此这里不比较 new_token != old_token。
        if new_token:
            try:
                verify_node, _raw2 = token_verify(url, new_token, timeout_s=GSTORE.http_timeout_s)
            except SaleorGraphQLError as e:
                INFO(
                    summarize_gql_failure(
                        title="AUTH-0004 刷新后 tokenVerify 失败",
                        exc=e,
                        variables={"token": new_token},
                    )
                )
                CHECK_POINT("tokenVerify 调用成功（刷新后的 token）", False)
                return
            verify_errs = []
            is_valid = None
            if verify_node is not None:
                verify_errs = verify_node.get("errors") or []
                is_valid = verify_node.get("isValid")
            CHECK_POINT("tokenVerify.errors 为空（刷新后的 token）", verify_errs == [], failStop=False)
            CHECK_POINT("tokenVerify.isValid 为 True（刷新后的 token）", is_valid is True)

        if new_token:
            GSTORE.saleor_access_token = new_token
        else:
            GSTORE.saleor_access_token = old_token


class cAUTH0005:
    name = "AUTH-0005-me 查询（验证 Authorization: Bearer <token>）"
    tags = ["API", "回归"]

    def teststeps(self):
        _require_saleor_api_ready()
        STEP(1, "从 GSTORE 获取 access token（me 是鉴权查询）")
        url = GSTORE.saleor_graphql_url
        token = getattr(GSTORE, "saleor_access_token", None)
        if not token:
            raise RuntimeError("BLOCKED: 未获取到 access token（me 需要鉴权 token）")

        STEP(2, "调用 me 查询")
        user, errors, _raw = me(url, token, timeout_s=GSTORE.http_timeout_s)

        # 按文档：me 会验证 token，token 无效会给 errors
        CHECK_POINT("GraphQL errors 为空", errors == [], failStop=False)
        if errors:
            INFO(
                summarize_gql_failure(
                    title="AUTH-0005 me GraphQL errors 非空",
                    errors=errors,
                    raw=_raw,
                    variables={"token": token},
                )
            )
        CHECK_POINT("me 返回用户对象", isinstance(user, dict))
        if isinstance(user, dict):
            email = user.get("email")
        else:
            email = None
        CHECK_POINT("user.email 非空", bool(email), failStop=False)

