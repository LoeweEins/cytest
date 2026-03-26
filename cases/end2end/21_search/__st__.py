import os
from cytest import INFO, GSTORE

from lib.saleor_api import SaleorGraphQLError, gql_request, token_create

force_tags = ["Search", "搜索"]
default_tags = ["回归"]

def suite_setup():
    """
    Search 套件初始化：
    - 复用 end2end/__st__.py 写入的 URL；支持直接运行本套件时的本地私有配置兜底
    - 提供可配置的搜索关键字与分页大小（避免环境差异导致不稳定）
    """
    GSTORE.search_page_size = int(os.getenv("SEARCH_PAGE_SIZE", "5"))
    GSTORE.search_query = os.getenv("SEARCH_QUERY", "a").strip() or "a"

    # URL 兜底：直接跑本套件时不会经过 end2end/__st__.py
    if not getattr(GSTORE, "saleor_graphql_url", ""):
        try:
            from lib.local_secrets import SALEOR_GRAPHQL_URL as _URL  # type: ignore
        except Exception:
            _URL = ""
        GSTORE.saleor_graphql_url = str(_URL or "").strip()

    # 超时兜底
    if not getattr(GSTORE, "http_timeout_s", None):
        GSTORE.http_timeout_s = int(os.getenv("E2E_HTTP_TIMEOUT_S", "20"))

    # 探测 endpoint 是否可 POST（用于用例里的阻塞判断）
    GSTORE.saleor_api_callable = bool(getattr(GSTORE, "saleor_graphql_url", ""))
    if GSTORE.saleor_api_callable:
        try:
            gql_request(
                GSTORE.saleor_graphql_url,
                "query { shop { name } }",
                timeout_s=GSTORE.http_timeout_s,
            )
        except SaleorGraphQLError as e:
            INFO(f"[21_search] GraphQL endpoint 不可 POST：{e}")
            GSTORE.saleor_api_callable = False

    # 多 channel 环境的显式覆盖（若不设且无 staff token，将在用例里 blocked）
    GSTORE.saleor_channel_slug = os.getenv("SALEOR_CHANNEL_SLUG", "").strip()

    # Search 用例依赖 channel；而 channels 查询需要 staff/app 权限。
    # 这里尽量用本地测试账号提前获取 staff token，便于用例自动发现 channel。
    GSTORE.saleor_access_token = getattr(GSTORE, "saleor_access_token", None)
    if not GSTORE.saleor_access_token:
        try:
            from lib.local_secrets import (  # type: ignore
                SALEOR_TEST_EMAIL as _EMAIL,
                SALEOR_TEST_PASSWORD as _PWD,
            )
        except Exception:
            _EMAIL, _PWD = "", ""

        email = str((_EMAIL or "")).strip()
        pwd = str((_PWD or "")).strip()
        if email and pwd and GSTORE.saleor_api_callable:
            try:
                node, _raw = token_create(
                    GSTORE.saleor_graphql_url,
                    email,
                    pwd,
                    timeout_s=GSTORE.http_timeout_s,
                )
            except SaleorGraphQLError as e:
                INFO(f"[21_search] tokenCreate 失败（将要求显式 SALEOR_CHANNEL_SLUG）：{e}")
            else:
                token = None
                if node is not None:
                    token = node.get("token")
                GSTORE.saleor_access_token = token

    INFO(
        f"[21_search] suite_setup, page_size={GSTORE.search_page_size}, "
        f"query={GSTORE.search_query!r}, url={GSTORE.saleor_graphql_url or '<EMPTY>'}, "
        f"callable={GSTORE.saleor_api_callable}, channel_slug={GSTORE.saleor_channel_slug or '<AUTO>'}, "
        f"token={'Y' if GSTORE.saleor_access_token else 'N'}"
    )

def suite_teardown():
    INFO("[21_search] suite_teardown")
