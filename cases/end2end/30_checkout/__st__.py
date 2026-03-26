import os
from cytest import INFO, GSTORE

from lib.saleor_api import SaleorGraphQLError, gql_request, token_create

force_tags = ["Checkout", "结算"]
default_tags = ["回归"]

def suite_setup():
    GSTORE.checkout_page_size = int(os.getenv("CHECKOUT_PAGE_SIZE", "3"))
    GSTORE.checkout_email = os.getenv("CHECKOUT_EMAIL", "buyer@example.com").strip() or "buyer@example.com"

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
            INFO(f"[30_checkout] GraphQL endpoint 不可 POST：{e}")
            GSTORE.saleor_api_callable = False

    # channel slug：可手动配置，也可用 staff token 自动发现
    GSTORE.saleor_channel_slug = os.getenv("SALEOR_CHANNEL_SLUG", "").strip()

    # 预先拿 staff token（checkout 并非必须，但自动发现 channel/读取某些字段时可能需要）
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
                INFO(f"[30_checkout] tokenCreate 失败（将要求显式 SALEOR_CHANNEL_SLUG）：{e}")
            else:
                token = None
                if node is not None:
                    token = node.get("token")
                GSTORE.saleor_access_token = token

    INFO(
        f"[30_checkout] suite_setup, email={GSTORE.checkout_email!r}, page_size={GSTORE.checkout_page_size}, "
        f"url={GSTORE.saleor_graphql_url or '<EMPTY>'}, callable={GSTORE.saleor_api_callable}, "
        f"channel_slug={GSTORE.saleor_channel_slug or '<AUTO>'}, token={'Y' if GSTORE.saleor_access_token else 'N'}"
    )

def suite_teardown():
    INFO("[30_checkout] suite_teardown")
