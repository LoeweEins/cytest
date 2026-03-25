import os
from cytest import INFO, GSTORE, CHECK_POINT

from lib.saleor_api import (
    SaleorGraphQLError,
    gql_request,
    get_saleor_graphql_url,
    token_create,
)

force_tags = ["Auth", "鉴权"]
default_tags = ["冒烟", "回归"]


def suite_setup():
    """
    Auth 套件初始化目标：
    - 确定 GraphQL API URL（必须能 POST /graphql/）
    - 如果提供测试账号密码，则预先获取 access/refresh token 供用例复用

    环境变量：
    - SALEOR_GRAPHQL_URL: https://<your-saleor-domain>/graphql/
    - SALEOR_TEST_EMAIL / SALEOR_TEST_PASSWORD: （可选）用于 tokenCreate
    """
    GSTORE.saleor_graphql_url = get_saleor_graphql_url(GSTORE.saleor_graphql_url or "")
    GSTORE.saleor_test_email = os.getenv("SALEOR_TEST_EMAIL", "").strip()
    GSTORE.saleor_test_password = os.getenv("SALEOR_TEST_PASSWORD", "").strip()
    if not (GSTORE.saleor_test_email and GSTORE.saleor_test_password):
        try:
            from lib.local_secrets import (  # type: ignore
                SALEOR_TEST_EMAIL as _EMAIL,
                SALEOR_TEST_PASSWORD as _PWD,
            )
        except Exception:
            _EMAIL, _PWD = "", ""
        GSTORE.saleor_test_email = (GSTORE.saleor_test_email or str(_EMAIL or "").strip())
        GSTORE.saleor_test_password = (GSTORE.saleor_test_password or str(_PWD or "").strip())
    _default_timeout = getattr(GSTORE, "http_timeout_s", None) or 20
    GSTORE.http_timeout_s = int(os.getenv("E2E_HTTP_TIMEOUT_S", str(_default_timeout)))

    INFO(f"[auth] saleor_graphql_url={GSTORE.saleor_graphql_url or '<EMPTY>'}")

    # 没配置 URL：后续用例会失败，但这里先给出明确提示
    CHECK_POINT("必须配置 SALEOR_GRAPHQL_URL（指向可 POST 的 /graphql/ endpoint）", bool(GSTORE.saleor_graphql_url), failStop=False)

    # 先探测：这个 URL 是否真的支持 POST GraphQL（有些“playground 页面地址”看起来像 /graphql/ 但对 POST 不通）
    GSTORE.saleor_api_callable = bool(GSTORE.saleor_graphql_url)
    if GSTORE.saleor_api_callable:
        probe_query = "query { shop { name } }"
        try:
            _data, _errors, _raw = gql_request(
                GSTORE.saleor_graphql_url,
                probe_query,
                timeout_s=GSTORE.http_timeout_s,
            )
        except SaleorGraphQLError as e:
            INFO(f"[auth] GraphQL endpoint 不可 POST（探测失败）：{e}")
            GSTORE.saleor_api_callable = False
        else:
            # 即使 errors 非空，也说明 endpoint 至少可访问（后续鉴权会另行处理）
            GSTORE.saleor_api_callable = True

    if not GSTORE.saleor_api_callable:
        INFO("[auth] saleor_api_callable=False：将跳过 tokenCreate/tokenVerify/tokenRefresh/me 用例")
        GSTORE.saleor_access_token = None
        GSTORE.saleor_refresh_token = None
        return

    # 如果没提供账号密码，仍允许跑“匿名可访问”的用例；需要登录的用例会做前置检查
    if not (GSTORE.saleor_test_email and GSTORE.saleor_test_password):
        INFO("[auth] 未设置 SALEOR_TEST_EMAIL/SALEOR_TEST_PASSWORD：将跳过需要登录的用例前置 token 获取")
        GSTORE.saleor_access_token = None
        GSTORE.saleor_refresh_token = None
        return

    try:
        node, _raw = token_create(
            GSTORE.saleor_graphql_url,
            GSTORE.saleor_test_email,
            GSTORE.saleor_test_password,
            timeout_s=GSTORE.http_timeout_s,
        )
    except SaleorGraphQLError as e:
        INFO(f"[auth] tokenCreate 调用失败：{e}")
        GSTORE.saleor_access_token = None
        GSTORE.saleor_refresh_token = None
        CHECK_POINT("tokenCreate 能成功返回 token（账号密码正确、环境允许密码登录）", False, failStop=False)
        return

    errs = (node or {}).get("errors") or []
    GSTORE.saleor_access_token = (node or {}).get("token")
    GSTORE.saleor_refresh_token = (node or {}).get("refreshToken")

    CHECK_POINT("tokenCreate 返回 errors 为空", errs == [], failStop=False)
    CHECK_POINT("tokenCreate 返回 access token 非空", bool(GSTORE.saleor_access_token), failStop=False)
    CHECK_POINT("tokenCreate 返回 refresh token 非空", bool(GSTORE.saleor_refresh_token), failStop=False)


def suite_teardown():
    INFO("[auth] suite_teardown")

