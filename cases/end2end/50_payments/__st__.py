import os
from cytest import INFO, GSTORE

from lib.saleor_api import SaleorGraphQLError, gql_request, token_create

force_tags = ["Payments", "支付"]
default_tags = ["回归"]

def suite_setup():
    if not getattr(GSTORE, "saleor_graphql_url", ""):
        try:
            from lib.local_secrets import SALEOR_GRAPHQL_URL as _URL  # type: ignore
        except Exception:
            _URL = ""
        GSTORE.saleor_graphql_url = str(_URL or "").strip()

    if not getattr(GSTORE, "http_timeout_s", None):
        GSTORE.http_timeout_s = int(os.getenv("E2E_HTTP_TIMEOUT_S", "20"))

    GSTORE.saleor_api_callable = bool(getattr(GSTORE, "saleor_graphql_url", ""))
    if GSTORE.saleor_api_callable:
        try:
            gql_request(GSTORE.saleor_graphql_url, "query { shop { name } }", timeout_s=GSTORE.http_timeout_s)
        except SaleorGraphQLError as e:
            INFO(f"[50_payments] GraphQL endpoint 不可 POST：{e}")
            GSTORE.saleor_api_callable = False

    GSTORE.saleor_channel_slug = os.getenv("SALEOR_CHANNEL_SLUG", "").strip()
    GSTORE.saleor_access_token = getattr(GSTORE, "saleor_access_token", None)
    if not GSTORE.saleor_access_token:
        try:
            from lib.local_secrets import SALEOR_TEST_EMAIL as _EMAIL, SALEOR_TEST_PASSWORD as _PWD  # type: ignore
        except Exception:
            _EMAIL, _PWD = "", ""
        email = str((_EMAIL or "")).strip()
        pwd = str((_PWD or "")).strip()
        if email and pwd and GSTORE.saleor_api_callable:
            try:
                node, _raw = token_create(GSTORE.saleor_graphql_url, email, pwd, timeout_s=GSTORE.http_timeout_s)
            except SaleorGraphQLError as e:
                INFO(f"[50_payments] tokenCreate 失败：{e}")
            else:
                token = node.get("token") if isinstance(node, dict) else None
                GSTORE.saleor_access_token = token

    INFO(
        f"[50_payments] suite_setup, url={GSTORE.saleor_graphql_url or '<EMPTY>'}, callable={GSTORE.saleor_api_callable}, "
        f"channel_slug={GSTORE.saleor_channel_slug or '<AUTO>'}, token={'Y' if GSTORE.saleor_access_token else 'N'}"
    )

def suite_teardown():
    INFO("[50_payments] suite_teardown")
