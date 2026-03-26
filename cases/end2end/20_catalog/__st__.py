import os
from cytest import INFO, GSTORE

from lib.saleor_api import SaleorGraphQLError, gql_request, token_create

force_tags = ["Catalog", "类目"]
default_tags = ["回归"]


def suite_setup():
    """
    说明：
    - 依赖 end2end/__st__.py 写入的 GSTORE.saleor_graphql_url
    - 允许用环境变量覆盖默认分页大小，避免一次取太多导致 demo/本地环境变慢
    """
    GSTORE.catalog_page_size = int(os.getenv("CATALOG_PAGE_SIZE", "5"))

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
            INFO(f"[20_catalog] GraphQL endpoint 不可 POST：{e}")
            GSTORE.saleor_api_callable = False

    # Catalog 用例里有些查询在“多 channel 环境”需要指定 channel，
    # 且 `channels` 查询需要 staff/app 权限。这里尽量复用本地测试账号获取 token。
    GSTORE.saleor_access_token = getattr(GSTORE, "saleor_access_token", None)
    GSTORE.saleor_channel_slug = os.getenv("SALEOR_CHANNEL_SLUG", "").strip()

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
                INFO(f"[20_catalog] tokenCreate 失败（将以匿名能力运行）：{e}")
            else:
                token = None
                if node is not None:
                    token = node.get("token")
                GSTORE.saleor_access_token = token

    INFO(
        f"[20_catalog] suite_setup, page_size={GSTORE.catalog_page_size}, "
        f"url={GSTORE.saleor_graphql_url or '<EMPTY>'}, callable={GSTORE.saleor_api_callable}, "
        f"channel_slug={GSTORE.saleor_channel_slug or '<AUTO>'}, "
        f"token={'Y' if GSTORE.saleor_access_token else 'N'}"
    )


def suite_teardown():
    INFO("[20_catalog] suite_teardown")
