import os
from cytest import INFO, GSTORE

from lib.saleor_api import SaleorGraphQLError, gql_request, token_create

force_tags = ["Edge", "Boundary", "幂等性"]
default_tags = ["回归"]


def suite_setup():
    """
    边界条件套件：
    - 复用 Saleor 连接/探测/预登录（用于查询 order/payments，验证是否重复扣费/重复订单）。
    - 需要可写 Saleor（公开 demo 多数无法执行完整支付/下单）。
    """
    GSTORE.checkout_page_size = int(os.getenv("CHECKOUT_PAGE_SIZE", "3"))
    GSTORE.checkout_email = os.getenv("CHECKOUT_EMAIL", "buyer@example.com").strip() or "buyer@example.com"

    # URL 兜底
    if not getattr(GSTORE, "saleor_graphql_url", ""):
        try:
            from lib.local_secrets import SALEOR_GRAPHQL_URL as _URL  # type: ignore
        except Exception:
            _URL = ""
        GSTORE.saleor_graphql_url = str(_URL or "").strip()

    # 超时兜底
    if not getattr(GSTORE, "http_timeout_s", None):
        GSTORE.http_timeout_s = int(os.getenv("E2E_HTTP_TIMEOUT_S", "30"))

    # 探测 endpoint 是否可 POST
    GSTORE.saleor_api_callable = bool(getattr(GSTORE, "saleor_graphql_url", ""))
    if GSTORE.saleor_api_callable:
        try:
            gql_request(
                GSTORE.saleor_graphql_url,
                "query { shop { name } }",
                timeout_s=GSTORE.http_timeout_s,
            )
        except SaleorGraphQLError as e:
            INFO(f"[35_edge_conditions] GraphQL endpoint 不可 POST：{e}")
            GSTORE.saleor_api_callable = False

    # channel slug（可手动配置，也可自动发现）
    GSTORE.saleor_channel_slug = os.getenv("SALEOR_CHANNEL_SLUG", "").strip()

    # staff token（用于查询 order/payments）
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
                INFO(f"[35_edge_conditions] tokenCreate 失败：{e}")
            else:
                token = None
                if node is not None:
                    token = node.get("token")
                GSTORE.saleor_access_token = token

    INFO(
        f"[35_edge_conditions] suite_setup url={GSTORE.saleor_graphql_url or '<EMPTY>'}, "
        f"callable={GSTORE.saleor_api_callable}, channel={GSTORE.saleor_channel_slug or '<AUTO>'}, "
        f"staff_token={'Y' if GSTORE.saleor_access_token else 'N'}"
    )


def suite_teardown():
    INFO("[35_edge_conditions] suite_teardown")

