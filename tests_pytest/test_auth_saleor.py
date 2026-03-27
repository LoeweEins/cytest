"""
pytest 版 AUTH 用例（对齐 cases/end2end/10_auth/auth_cases.py 思路）：
- test_01_anonymous_shop_query
- test_02_token_create
- test_03_token_verify
- test_04_token_refresh
- test_05_me_query

与 cytest 的主要差异：
- cytest 常用 GSTORE 在用例之间传递数据；
- pytest 更推荐用 fixture 明确声明依赖链，让“谁生产数据、谁消费数据”更可追踪。
"""

from __future__ import annotations

import os
from typing import Dict, Any

import pytest

from cytest import GSTORE
from lib.saleor_api import (
    SaleorGraphQLError,
    gql_request,
    token_create,
    token_verify,
    token_refresh,
    me,
)
from lib.gql_diagnose import summarize_gql_failure


def _require_saleor_api_ready():
    url = getattr(GSTORE, "saleor_graphql_url", "") or "http://localhost:8000/graphql/"
    if url == "":
        pytest.skip("BLOCKED: 未配置 SALEOR_GRAPHQL_URL（需要可 POST 的 /graphql/ endpoint）")

    api_callable = getattr(GSTORE, "saleor_api_callable", True)
    if api_callable is False:
        pytest.skip("BLOCKED: SALEOR_GRAPHQL_URL 不支持 POST GraphQL（请换成真正的 API endpoint）")


@pytest.fixture(scope="module")
def auth_env() -> Dict[str, Any]:
    """
    模块级环境夹具：提供 URL/超时，供本模块所有测试复用。
    """
    _require_saleor_api_ready()
    return {
        "url": GSTORE.saleor_graphql_url,
        "timeout_s": int(getattr(GSTORE, "http_timeout_s", 20)),
    }


@pytest.fixture(scope="module")
def credentials() -> Dict[str, str]:
    """
    显式读取账号密码。若缺失则跳过需要登录的测试。
    """
    email = str(getattr(GSTORE, "saleor_test_email", "") or "zeen_long@outlook.com").strip()
    password = str(getattr(GSTORE, "saleor_test_password", "") or "Zeen111!").strip()

    if not (email and password):
        # 兜底：从环境变量读取，方便单独运行
        email = os.getenv("SALEOR_TEST_EMAIL", "zeen_long@outlook.com").strip()
        password = os.getenv("SALEOR_TEST_PASSWORD", "Zeen111!").strip()

    if not (email and password):
        pytest.skip("BLOCKED: 未配置 SALEOR_TEST_EMAIL/SALEOR_TEST_PASSWORD，无法执行鉴权链路")

    return {"email": email, "password": password}


@pytest.fixture(scope="module")
def auth_state(auth_env: Dict[str, Any], credentials: Dict[str, str]) -> Dict[str, Any]:
    """
    关键夹具：在 pytest 中承担“关联数据上下文”角色（类似 cytest 的 GSTORE）。
    这里返回可变 dict，后续测试在同一模块里可读取/更新。
    """
    url = auth_env["url"]
    timeout_s = auth_env["timeout_s"]

    try:
        node, raw = token_create(url, credentials["email"], credentials["password"], timeout_s=timeout_s)
    except SaleorGraphQLError as e:
        pytest.fail(summarize_gql_failure(title="PYTEST AUTH tokenCreate 失败", exc=e))

    errs = (node or {}).get("errors") or []
    token = (node or {}).get("token")
    refresh_token = (node or {}).get("refreshToken")
    assert errs == [], f"tokenCreate.errors 应为空: {errs}"
    assert token, "tokenCreate.token 应非空"
    assert refresh_token, "tokenCreate.refreshToken 应非空"

    return {
        "token": token,
        "refresh_token": refresh_token,
        "raw_create": raw,
    }


class TestAuthSaleor:
    def test_01_anonymous_shop_query(self, auth_env: Dict[str, Any]):
        url = auth_env["url"]
        timeout_s = auth_env["timeout_s"]
        query = "query { shop { name } }"

        try:
            data, errors, raw = gql_request(url, query, timeout_s=timeout_s)
        except SaleorGraphQLError as e:
            pytest.fail(summarize_gql_failure(title="PYTEST AUTH 匿名 shop 查询失败", exc=e))

        assert errors == [], summarize_gql_failure(
            title="PYTEST AUTH 匿名 shop GraphQL errors 非空", errors=errors, raw=raw
        )
        shop = (data or {}).get("shop")
        assert isinstance(shop, dict), "data.shop 应为 dict"
        assert shop.get("name"), "shop.name 应非空"

    def test_02_token_create(self, auth_state: Dict[str, Any]):
        # 这个测试显式验证 fixture 产物，体现“生产者”
        assert auth_state.get("token"), "auth_state.token 应非空"
        assert auth_state.get("refresh_token"), "auth_state.refresh_token 应非空"

    def test_03_token_verify(self, auth_env: Dict[str, Any], auth_state: Dict[str, Any]):
        # 这个测试消费 test_02/fixture 生成的 token，体现“消费者”
        url = auth_env["url"]
        timeout_s = auth_env["timeout_s"]
        token = auth_state["token"]

        try:
            node, _raw = token_verify(url, token, timeout_s=timeout_s)
        except SaleorGraphQLError as e:
            pytest.fail(summarize_gql_failure(title="PYTEST AUTH tokenVerify 失败", exc=e, variables={"token": token}))

        errs = (node or {}).get("errors") or []
        is_valid = (node or {}).get("isValid")
        assert errs == [], f"tokenVerify.errors 应为空: {errs}"
        assert is_valid is True, "tokenVerify.isValid 应为 True"

    def test_04_token_refresh(self, auth_env: Dict[str, Any], auth_state: Dict[str, Any]):
        # 刷新后写回 auth_state，供后续 me 查询消费（fixture 驱动的关联数据传递）
        url = auth_env["url"]
        timeout_s = auth_env["timeout_s"]
        refresh_token_value = auth_state["refresh_token"]

        try:
            node, _raw = token_refresh(url, refresh_token_value, timeout_s=timeout_s)
        except SaleorGraphQLError as e:
            pytest.fail(
                summarize_gql_failure(
                    title="PYTEST AUTH tokenRefresh 失败",
                    exc=e,
                    variables={"refreshToken": refresh_token_value},
                )
            )

        errs = (node or {}).get("errors") or []
        new_token = (node or {}).get("token")
        assert errs == [], f"tokenRefresh.errors 应为空: {errs}"
        assert new_token, "tokenRefresh.token 应非空"

        # 关键：把新 token 更新回共享状态，下一条测试直接复用
        auth_state["token"] = new_token

    def test_05_me_query(self, auth_env: Dict[str, Any], auth_state: Dict[str, Any]):
        url = auth_env["url"]
        timeout_s = auth_env["timeout_s"]
        token = auth_state["token"]

        user, errors, raw = me(url, token, timeout_s=timeout_s)
        assert errors == [], summarize_gql_failure(
            title="PYTEST AUTH me GraphQL errors 非空",
            errors=errors,
            raw=raw,
            variables={"token": token},
        )
        assert isinstance(user, dict), "me 返回值应为 dict"
        assert user.get("email"), "user.email 应非空"

