import os

import pytest


@pytest.fixture(scope="session")
def open_api_base_url() -> str:
    return os.getenv("OPEN_API_BASE_URL", "https://jsonplaceholder.typicode.com").strip().rstrip("/")


@pytest.fixture(scope="session")
def open_api_timeout_s() -> int:
    return int(os.getenv("OPEN_API_TIMEOUT_S", "20"))

