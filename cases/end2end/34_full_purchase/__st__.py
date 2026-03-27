import os
from cytest import INFO, GSTORE

from lib.saleor_api import SaleorGraphQLError, gql_request, token_create

force_tags = ["FullPurchase", "E2E", "主流程"]
default_tags = ["回归"]

def suite_setup():
    """
    与 30_checkout 相同的 Saleor 连接与 staff 预登录，供 channel 自动发现。
    完整支付还要求渠道启用 Dummy 等测试网关，见用例内 BLOCKED 说明。
    """
    GSTORE.checkout_page_size = int(os.getenv("CHECKOUT_PAGE_SIZE", "3"))
    GSTORE.checkout_email = os.getenv("CHECKOUT_EMAIL", "buyer@example.com").strip() or "buyer@example.com"

    if not getattr(GSTORE, "saleor_graphql_url", ""):
        try:
            from lib.local_secrets import SALEOR_GRAPHQL_URL as _URL  # type: ignore
        except Exception:
            _URL = ""
        GSTORE.saleor_graphql_url = str(_URL or "").strip()

    if not getattr(GSTORE, "http_timeout_s", None):
        GSTORE.http_timeout_s = int(os.getenv("E2E_HTTP_TIMEOUT_S", "30"))

    GSTORE.saleor_api_callable = bool(getattr(GSTORE, "saleor_graphql_url", ""))
    if GSTORE.saleor_api_callable:
        try:
            gql_request(
                GSTORE.saleor_graphql_url,
                "query { shop { name } }",
                timeout_s=GSTORE.http_timeout_s,
            )
        except SaleorGraphQLError as e:
            INFO(f"[34_full_purchase] GraphQL endpoint 不可 POST：{e}")
            GSTORE.saleor_api_callable = False

    GSTORE.saleor_channel_slug = os.getenv("SALEOR_CHANNEL_SLUG", "").strip()

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
                INFO(f"[34_full_purchase] tokenCreate 失败：{e}")
            else:
                token = None
                if node is not None:
                    token = node.get("token")
                GSTORE.saleor_access_token = token

    INFO(
        f"[34_full_purchase] suite_setup url={GSTORE.saleor_graphql_url or '<EMPTY>'}, "
        f"callable={GSTORE.saleor_api_callable}, channel={GSTORE.saleor_channel_slug or '<AUTO>'}, "
        f"staff_token={'Y' if GSTORE.saleor_access_token else 'N'}"
    )

def suite_teardown():
    INFO("[34_full_purchase] suite_teardown")
