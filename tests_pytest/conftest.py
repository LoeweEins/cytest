"""
pytest 会话级初始化：对齐 cases/end2end/30_checkout/__st__.py 的 suite_setup，
向 cytest.GSTORE 写入 URL/超时/探测结果/token，供 lib.saleor_flow_helpers 复用。
"""

import os

import pytest

from cytest import INFO, GSTORE
from lib.saleor_api import SaleorGraphQLError, gql_request, token_create


def _bootstrap_saleor_gstore():
    GSTORE.checkout_page_size = int(os.getenv("CHECKOUT_PAGE_SIZE", "3"))
    GSTORE.checkout_email = os.getenv("CHECKOUT_EMAIL", "buyer@example.com").strip() or "buyer@example.com"

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
            gql_request(
                GSTORE.saleor_graphql_url,
                "query { shop { name } }",
                timeout_s=GSTORE.http_timeout_s,
            )
        except SaleorGraphQLError as e:
            INFO(f"[tests_pytest] GraphQL endpoint 不可 POST：{e}")
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
                INFO(f"[tests_pytest] tokenCreate 失败：{e}")
            else:
                token = None
                if node is not None:
                    token = node.get("token")
                GSTORE.saleor_access_token = token

    INFO(
        f"[tests_pytest] conftest bootstrap url={GSTORE.saleor_graphql_url or '<EMPTY>'}, "
        f"callable={GSTORE.saleor_api_callable}, channel={GSTORE.saleor_channel_slug or '<AUTO>'}, "
        f"token={'Y' if GSTORE.saleor_access_token else 'N'}"
    )


@pytest.fixture(scope="session", autouse=True)
def saleor_session_bootstrap():
    _bootstrap_saleor_gstore()
    yield


@pytest.fixture
def gstore():
    return GSTORE
