from cytest import STEP, INFO, CHECK_POINT, GSTORE

from lib.saleor_api import SaleorGraphQLError, gql_request
from lib.gql_diagnose import summarize_gql_failure
from lib.saleor_flow_helpers import (
    require_saleor_api_ready,
    pick_channel_slug_or_block,
    pick_variant_id_or_block,
)


class cCHECKOUT0001:
    name = "CHECKOUT-0001-checkoutCreate（匿名创建 checkout，带 email + lines）"
    tags = ["API", "冒烟", "高风险"]

    def teststeps(self):
        require_saleor_api_ready()

        url = GSTORE.saleor_graphql_url
        buyer_email = str(getattr(GSTORE, "checkout_email", "buyer@example.com") or "buyer@example.com")

        STEP(1, "确定 channel slug")
        channel_slug = pick_channel_slug_or_block()
        CHECK_POINT("channel_slug 非空", bool(channel_slug))

        STEP(2, "选择一个 variantId（来自 products 列表）")
        variant_id = pick_variant_id_or_block(channel_slug)
        CHECK_POINT("variantId 非空", bool(variant_id))

        STEP(3, "调用 checkoutCreate(channel,email,lines)")
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

        try:
            data, errors, raw = gql_request(url, mutation, variables=variables, timeout_s=GSTORE.http_timeout_s)
        except SaleorGraphQLError as e:
            INFO(summarize_gql_failure(title="CHECKOUT-0001 checkoutCreate 失败", exc=e, variables=variables))
            CHECK_POINT("checkoutCreate 请求应成功返回", False)
            return

        CHECK_POINT("GraphQL errors 为空", errors == [], failStop=False)
        if errors:
            INFO(summarize_gql_failure(title="CHECKOUT-0001 GraphQL errors 非空", errors=errors, raw=raw, variables=variables))

        node = data.get("checkoutCreate") if isinstance(data, dict) else None
        CHECK_POINT("data.checkoutCreate 存在", isinstance(node, dict))
        if not isinstance(node, dict):
            return

        cp_errors = node.get("errors") or []
        CHECK_POINT("checkoutCreate.errors 为空", cp_errors == [], failStop=False)

        checkout = node.get("checkout")
        CHECK_POINT("checkout 非空", isinstance(checkout, dict))
        if not isinstance(checkout, dict):
            return

        checkout_id = checkout.get("id")
        checkout_token = checkout.get("token")
        CHECK_POINT("checkout.id 非空", bool(checkout_id))
        CHECK_POINT("checkout.token 非空", bool(checkout_token))

        quantity = checkout.get("quantity")
        CHECK_POINT("checkout.quantity 为 int 且 >=1", isinstance(quantity, int) and quantity >= 1, failStop=False)

        lines = checkout.get("lines")
        CHECK_POINT("checkout.lines 为 list 且非空", isinstance(lines, list) and len(lines) > 0)
        if isinstance(lines, list) and len(lines) > 0 and isinstance(lines[0], dict):
            CHECK_POINT("第一条 line.quantity == 1", lines[0].get("quantity") == 1, failStop=False)

        GSTORE.checkout_id = checkout_id
        GSTORE.checkout_token = checkout_token


class cCHECKOUT0002:
    name = "CHECKOUT-0002-checkout 查询（按 token 校验字段契约）"
    tags = ["API", "回归"]

    def teststeps(self):
        require_saleor_api_ready()

        url = GSTORE.saleor_graphql_url
        token = getattr(GSTORE, "checkout_token", None)
        if not token:
            raise RuntimeError("BLOCKED: 未获取到 checkout_token（请先执行 CHECKOUT-0001）")

        STEP(1, "按 token 查询 checkout")
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

        try:
            data, errors, raw = gql_request(url, query, variables=variables, timeout_s=GSTORE.http_timeout_s)
        except SaleorGraphQLError as e:
            INFO(summarize_gql_failure(title="CHECKOUT-0002 checkout 查询失败", exc=e, variables=variables))
            CHECK_POINT("checkout 查询应成功返回", False)
            return

        CHECK_POINT("GraphQL errors 为空", errors == [], failStop=False)
        if errors:
            INFO(summarize_gql_failure(title="CHECKOUT-0002 GraphQL errors 非空", errors=errors, raw=raw, variables=variables))

        checkout = data.get("checkout") if isinstance(data, dict) else None
        CHECK_POINT("checkout 非空", isinstance(checkout, dict))
        if not isinstance(checkout, dict):
            return

        CHECK_POINT("checkout.token 与输入一致", checkout.get("token") == token, failStop=False)
        CHECK_POINT("quantity 为 int 且 >=1", isinstance(checkout.get("quantity"), int) and checkout.get("quantity") >= 1, failStop=False)

        lines = checkout.get("lines")
        CHECK_POINT("lines 为 list 且非空", isinstance(lines, list) and len(lines) > 0)
