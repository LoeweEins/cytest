import os
from cytest import INFO, GSTORE


force_tags = ["OpenAPI", "基础API", "无需部署"]
default_tags = ["冒烟", "回归"]


def suite_setup():
    """
    公网开源 API 基础测试套件（无需本地部署）

    默认使用 JSONPlaceholder：
    - https://jsonplaceholder.typicode.com

    环境变量：
    - OPEN_API_BASE_URL: 覆盖默认 base url
    - OPEN_API_TIMEOUT_S: 覆盖请求超时（秒）
    """
    GSTORE.open_api_base_url = os.getenv("OPEN_API_BASE_URL", "https://jsonplaceholder.typicode.com").strip().rstrip("/")
    GSTORE.open_api_timeout_s = int(os.getenv("OPEN_API_TIMEOUT_S", "20"))

    INFO(f"[open_api_basic] base_url={GSTORE.open_api_base_url}, timeout_s={GSTORE.open_api_timeout_s}")


def suite_teardown():
    INFO("[open_api_basic] suite_teardown")

