import os
from cytest import INFO, GSTORE

force_tags = ["E2E", "API", "Saleor"]
default_tags = ["回归"]


def suite_setup():
    # 远程 Saleor GraphQL API endpoint（由 Auth 套件进一步细化）
    # 优先读环境变量；若没有，再读本地私有配置（不提交仓库）
    GSTORE.saleor_graphql_url = os.getenv("SALEOR_GRAPHQL_URL", "").strip()
    if not GSTORE.saleor_graphql_url:
        try:
            from lib.local_secrets import SALEOR_GRAPHQL_URL as _URL  # type: ignore
        except Exception:
            _URL = ""
        GSTORE.saleor_graphql_url = str(_URL or "").strip()

    GSTORE.http_timeout_s = int(os.getenv("E2E_HTTP_TIMEOUT_S", "20"))
    INFO(f"[end2end] saleor_graphql_url={GSTORE.saleor_graphql_url or '<EMPTY>'}")


def suite_teardown():
    INFO("[end2end] suite_teardown")

