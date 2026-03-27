"""
平移 cytest cases/end2end/30_checkout/checkout_cases.py：
- CHECKOUT-0001 / CHECKOUT-0002

运行（项目根目录 z_cytest-main）：
  pip install -e ".[pytest-allure]"
  pytest tests_pytest/test_checkout_saleor.py -v --alluredir=tests_pytest/allure-results

Allure HTML（需本机安装 allure commandline 或 npx）：
  allure generate tests_pytest/allure-results -o tests_pytest/allure-report --clean
"""

from __future__ import annotations

import json

import allure
import pytest

from cytest import GSTORE
from lib.saleor_api import SaleorGraphQLError, gql_request
from lib.gql_diagnose import summarize_gql_failure
from lib.saleor_flow_helpers import (
    require_saleor_api_ready,
    pick_channel_slug_or_block,
    pick_variant_id_or_block,
)


def _attach_json(name: str, obj):
    try:
        body = json.dumps(obj, ensure_ascii=False, indent=2)
    except Exception:
        body = str(obj)
    allure.attach(body, name=name, attachment_type=allure.attachment_type.JSON)


@allure.feature("Saleor Checkout")
@allure.story("GraphQL API")
class TestCheckoutSaleor:
    @allure.title("CHECKOUT-0001-checkoutCreate（匿名创建 checkout，带 email + lines）")
    @allure.tag("API", "冒烟", "高风险")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_01_checkout_create(self, gstore):
        require_saleor_api_ready()
        url = gstore.saleor_graphql_url
        buyer_email = str(getattr(gstore, "checkout_email", "buyer@example.com") or "buyer@example.com")

        with allure.step("确定 channel slug"):
            channel_slug = pick_channel_slug_or_block()
            assert channel_slug, "channel_slug 非空"

        with allure.step("选择一个 variantId（来自 products 列表）"):
            variant_id = pick_variant_id_or_block(channel_slug)
            assert variant_id, "variantId 非空"

        with allure.step("调用 checkoutCreate(channel,email,lines)"):
            mutation = """
            mutation CheckoutCreate($channel: String!, $email: String!, $lines: [CheckoutLineInput!]!) {
              checkoutCreate(input: { channel: $channel, email: $email, lines: $lines }) {
                errors { field message code }
                checkout {
                  id
                  token
                  quantity
                  subtotalPrice { gross { amount currency } }
                  totalPrice { gross { amount currency } }
                  lines {
                    quantity
                    variant { id name }
                  }
                }
              }
            }
            """
            variables = {
                "channel": str(channel_slug),
                "email": buyer_email,
                "lines": [{"variantId": str(variant_id), "quantity": 1}],
            }
            _attach_json("checkoutCreate.variables", variables)

            try:
                data, errors, raw = gql_request(url, mutation, variables=variables, timeout_s=gstore.http_timeout_s)
            except SaleorGraphQLError as e:
                _attach_json("checkoutCreate.exception", {"detail": str(e)})
                pytest.fail(summarize_gql_failure(title="CHECKOUT-0001 checkoutCreate 失败", exc=e, variables=variables))

            _attach_json("checkoutCreate.response", raw)
            assert not errors, summarize_gql_failure(
                title="CHECKOUT-0001 GraphQL errors 非空", errors=errors, raw=raw, variables=variables
            )

            node = data.get("checkoutCreate") if isinstance(data, dict) else None
            assert isinstance(node, dict), "data.checkoutCreate 存在"
            cp_errors = node.get("errors") or []
            assert cp_errors == [], f"checkoutCreate.errors 应为空: {cp_errors}"

            checkout = node.get("checkout")
            assert isinstance(checkout, dict), "checkout 非空"

            checkout_id = checkout.get("id")
            checkout_token = checkout.get("token")
            assert checkout_id, "checkout.id 非空"
            assert checkout_token, "checkout.token 非空"

            quantity = checkout.get("quantity")
            assert isinstance(quantity, int) and quantity >= 1, "checkout.quantity 为 int 且 >=1"

            lines = checkout.get("lines")
            assert isinstance(lines, list) and len(lines) > 0, "checkout.lines 为 list 且非空"
            if isinstance(lines[0], dict):
                assert lines[0].get("quantity") == 1, "第一条 line.quantity == 1"

            gstore.checkout_id = checkout_id
            gstore.checkout_token = checkout_token

    @allure.title("CHECKOUT-0002-checkout 查询（按 token 校验字段契约）")
    @allure.tag("API", "回归")
    @allure.severity(allure.severity_level.NORMAL)
    def test_02_checkout_query_by_token(self, gstore):
        require_saleor_api_ready()
        url = gstore.saleor_graphql_url
        token = getattr(gstore, "checkout_token", None)
        if not token:
            pytest.fail("BLOCKED: 未获取到 checkout_token（请先执行 test_01_checkout_create）")

        with allure.step("按 token 查询 checkout"):
            query = """
            query CheckoutByToken($token: UUID!) {
              checkout(token: $token) {
                id
                token
                quantity
                subtotalPrice { gross { amount currency } }
                totalPrice { gross { amount currency } }
                lines {
                  quantity
                  variant { id name }
                }
              }
            }
            """
            variables = {"token": token}
            _attach_json("checkout.query.variables", variables)

            try:
                data, errors, raw = gql_request(url, query, variables=variables, timeout_s=gstore.http_timeout_s)
            except SaleorGraphQLError as e:
                _attach_json("checkout.query.exception", {"detail": str(e)})
                pytest.fail(summarize_gql_failure(title="CHECKOUT-0002 checkout 查询失败", exc=e, variables=variables))

            _attach_json("checkout.query.response", raw)
            assert not errors, summarize_gql_failure(
                title="CHECKOUT-0002 GraphQL errors 非空", errors=errors, raw=raw, variables=variables
            )

            checkout = data.get("checkout") if isinstance(data, dict) else None
            assert isinstance(checkout, dict), "checkout 非空"
            assert checkout.get("token") == token, "checkout.token 与输入一致"
            q = checkout.get("quantity")
            assert isinstance(q, int) and q >= 1, "quantity 为 int 且 >=1"

            lines = checkout.get("lines")
            assert isinstance(lines, list) and len(lines) > 0, "lines 为 list 且非空"
