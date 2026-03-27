"""
主流程：串联 product → inventory → checkout/pricing → shipping → payment → order → payments。

环境要求（缺一不可时会 BLOCKED 或失败并打印 GraphQL 错误）：
- 可写的 Saleor GraphQL（公开 demo 往往无法完成支付或禁用 Dummy 网关）。
- Channel 上启用测试支付网关（默认 mirumee.payments.dummy），可用环境变量 SALEOR_PAYMENT_GATEWAY 覆盖。
- 实体商品需有可用的 shippingMethods；数字商品可走 isShippingRequired=false 分支。

参考：checkoutComplete / checkoutPaymentCreate 官方文档。
"""

import os
from cytest import STEP, INFO, CHECK_POINT, GSTORE

from lib.saleor_api import SaleorGraphQLError, gql_request
from lib.gql_diagnose import summarize_gql_failure
from lib.saleor_flow_helpers import (
    require_saleor_api_ready,
    pick_channel_slug_or_block,
    pick_variant_id_or_block,
    fetch_variant_inventory,
)

# Saleor 文档常用示例地址（波兰）
_DEFAULT_ADDRESS = {
    "firstName": "E2E",
    "lastName": "Buyer",
    "streetAddress1": "Teczowa 7",
    "city": "Wroclaw",
    "postalCode": "53-601",
    "country": "PL",
}


def _payment_gateway_id():
    return os.getenv("SALEOR_PAYMENT_GATEWAY", "mirumee.payments.dummy").strip() or "mirumee.payments.dummy"


def _dummy_card_token():
    # Dummy 网关：多数卡号会模拟成功扣款（见 Saleor Dummy Credit Card 文档）
    return os.getenv("SALEOR_DUMMY_PAYMENT_TOKEN", "4242424242424242").strip() or "4242424242424242"


def _query_checkout_for_flow(url: str, checkout_token):
    q = """
    query CheckoutFlow($token: UUID!) {
      checkout(token: $token) {
        id
        token
        isShippingRequired
        shippingMethods { id name }
        availablePaymentGateways { id name }
        subtotalPrice { gross { amount currency } }
        totalPrice { gross { amount currency } }
      }
    }
    """
    data, errors, raw = gql_request(url, q, variables={"token": checkout_token}, timeout_s=GSTORE.http_timeout_s)
    return data, errors, raw


class cFULL0001:
    name = "FULL-0001-主流程：选品→库存→结账/定价→配送与账单→Dummy 支付→下单→订单/支付校验"
    tags = ["API", "主流程", "E2E", "高风险"]

    def teststeps(self):
        require_saleor_api_ready()
        url = GSTORE.saleor_graphql_url
        buyer_email = str(getattr(GSTORE, "checkout_email", "buyer@example.com") or "buyer@example.com")

        STEP(1, "[Product] 确定 channel 并选取可售 variant")
        channel_slug = pick_channel_slug_or_block()
        variant_id = pick_variant_id_or_block(channel_slug)
        CHECK_POINT("channel 与 variant 已确定", bool(channel_slug) and bool(variant_id))

        STEP(2, "[Inventory] 读取 variant 库存字段（若 schema 支持）")
        inv = fetch_variant_inventory(url, channel_slug, variant_id)
        if isinstance(inv, dict):
            CHECK_POINT("trackInventory 为 bool", isinstance(inv.get("trackInventory"), bool), failStop=False)
            qa = inv.get("quantityAvailable")
            CHECK_POINT("quantityAvailable 为 int 且 >=0", isinstance(qa, int) and qa >= 0, failStop=False)
            if inv.get("trackInventory") is True and isinstance(qa, int) and qa < 1:
                raise RuntimeError("BLOCKED: quantityAvailable<1，无法保证可下单（请换有库存商品或环境）")
        else:
            INFO("当前环境未返回 productVariant 库存字段，跳过库存硬断言")

        STEP(3, "[Checkout+Pricing] checkoutCreate 并校验价格结构")
        m_create = """
        mutation CheckoutCreate($channel: String!, $email: String!, $lines: [CheckoutLineInput!]!) {
          checkoutCreate(input: { channel: $channel, email: $email, lines: $lines }) {
            errors { field message code }
            checkout {
              id
              token
              quantity
              subtotalPrice { gross { amount currency } }
              totalPrice { gross { amount currency } }
              lines { quantity variant { id } }
            }
          }
        }
        """
        v_create = {
            "channel": str(channel_slug),
            "email": buyer_email,
            "lines": [{"variantId": str(variant_id), "quantity": 1}],
        }
        try:
            data, errors, raw = gql_request(url, m_create, variables=v_create, timeout_s=GSTORE.http_timeout_s)
        except SaleorGraphQLError as e:
            INFO(summarize_gql_failure(title="FULL-0001 checkoutCreate", exc=e, variables=v_create))
            CHECK_POINT("checkoutCreate 应成功", False)
            return

        if errors:
            INFO(summarize_gql_failure(title="FULL-0001 checkoutCreate GraphQL errors", errors=errors, raw=raw))
            CHECK_POINT("GraphQL errors 应为空", False)
            return

        node = (data or {}).get("checkoutCreate")
        if not isinstance(node, dict) or node.get("errors"):
            INFO(f"checkoutCreate 业务错误: {node}")
            CHECK_POINT("checkoutCreate.errors 为空", False)
            return

        checkout = node.get("checkout")
        if not isinstance(checkout, dict):
            CHECK_POINT("checkout 对象存在", False)
            return

        checkout_id = checkout.get("id")
        checkout_token = checkout.get("token")
        CHECK_POINT("checkout.id/token 非空", bool(checkout_id) and bool(checkout_token))

        sub = checkout.get("subtotalPrice")
        tot = checkout.get("totalPrice")
        CHECK_POINT("subtotalPrice/totalPrice 结构存在", isinstance(sub, dict) and isinstance(tot, dict))
        if isinstance(sub, dict) and sub.get("gross"):
            g = sub["gross"]
            CHECK_POINT("subtotal gross.amount 非负", isinstance(g, dict) and float(g.get("amount", -1)) >= 0, failStop=False)
        if isinstance(tot, dict) and tot.get("gross"):
            g2 = tot["gross"]
            CHECK_POINT("total gross.amount 非负", isinstance(g2, dict) and float(g2.get("amount", -1)) >= 0, failStop=False)

        STEP(4, "[Shipping/Billing] 写入地址；按需选择配送方式")
        addr = dict(_DEFAULT_ADDRESS)

        m_ship_addr = """
        mutation ShipAddr($id: ID!, $addr: AddressInput!) {
          checkoutShippingAddressUpdate(id: $id, shippingAddress: $addr) {
            errors { field message code }
            checkout { id isShippingRequired }
          }
        }
        """
        m_bill_addr = """
        mutation BillAddr($id: ID!, $addr: AddressInput!) {
          checkoutBillingAddressUpdate(id: $id, billingAddress: $addr) {
            errors { field message code }
            checkout { id }
          }
        }
        """

        data2, err2, raw2 = _query_checkout_for_flow(url, checkout_token)
        if err2:
            INFO(summarize_gql_failure(title="FULL-0001 查询 checkout 状态", errors=err2, raw=raw2))
            CHECK_POINT("查询 checkout 成功", False)
            return

        ck = (data2 or {}).get("checkout")
        shipping_required = bool(isinstance(ck, dict) and ck.get("isShippingRequired"))

        if shipping_required:
            try:
                d_sa, e_sa, r_sa = gql_request(
                    url,
                    m_ship_addr,
                    variables={"id": checkout_id, "addr": addr},
                    timeout_s=GSTORE.http_timeout_s,
                )
            except SaleorGraphQLError as e:
                INFO(summarize_gql_failure(title="checkoutShippingAddressUpdate", exc=e))
                CHECK_POINT("配送地址更新应成功", False)
                return
            if e_sa:
                INFO(summarize_gql_failure(title="shipping address GraphQL errors", errors=e_sa, raw=r_sa))
                CHECK_POINT("配送地址 GraphQL 无错", False)
                return
            n_sa = (d_sa or {}).get("checkoutShippingAddressUpdate")
            if isinstance(n_sa, dict) and n_sa.get("errors"):
                INFO(f"checkoutShippingAddressUpdate 错误: {n_sa.get('errors')}")
                CHECK_POINT("配送地址业务无错", False)
                return

        try:
            d_ba, e_ba, r_ba = gql_request(
                url,
                m_bill_addr,
                variables={"id": checkout_id, "addr": addr},
                timeout_s=GSTORE.http_timeout_s,
            )
        except SaleorGraphQLError as e:
            INFO(summarize_gql_failure(title="checkoutBillingAddressUpdate", exc=e))
            CHECK_POINT("账单地址更新应成功", False)
            return
        if e_ba:
            INFO(summarize_gql_failure(title="billing address GraphQL errors", errors=e_ba, raw=r_ba))
            CHECK_POINT("账单地址 GraphQL 无错", False)
            return
        n_ba = (d_ba or {}).get("checkoutBillingAddressUpdate")
        if isinstance(n_ba, dict) and n_ba.get("errors"):
            INFO(f"checkoutBillingAddressUpdate 错误: {n_ba.get('errors')}")
            CHECK_POINT("账单地址业务无错", False)
            return

        data3, err3, raw3 = _query_checkout_for_flow(url, checkout_token)
        if err3:
            INFO(summarize_gql_failure(title="FULL-0001 二次查询 checkout", errors=err3, raw=raw3))
            CHECK_POINT("二次查询 checkout 成功", False)
            return

        ck3 = (data3 or {}).get("checkout")
        if not isinstance(ck3, dict):
            CHECK_POINT("checkout 查询非空", False)
            return

        if shipping_required:
            methods = ck3.get("shippingMethods")
            if not isinstance(methods, list) or len(methods) == 0:
                raise RuntimeError("BLOCKED: isShippingRequired=true 但 shippingMethods 为空（请配置运费/仓库）")

            delivery_method_id = None
            for m in methods:
                if isinstance(m, dict) and m.get("id"):
                    delivery_method_id = m["id"]
                    break
            if not delivery_method_id:
                raise RuntimeError("BLOCKED: 无法解析 shippingMethods[].id")

            m_dm = """
            mutation DM($id: ID!, $deliveryMethodId: ID!) {
              checkoutDeliveryMethodUpdate(id: $id, deliveryMethodId: $deliveryMethodId) {
                errors { field message code }
                checkout { id }
              }
            }
            """
            try:
                d_dm, e_dm, r_dm = gql_request(
                    url,
                    m_dm,
                    variables={"id": checkout_id, "deliveryMethodId": delivery_method_id},
                    timeout_s=GSTORE.http_timeout_s,
                )
            except SaleorGraphQLError as e:
                INFO(summarize_gql_failure(title="checkoutDeliveryMethodUpdate", exc=e))
                CHECK_POINT("选择配送方式应成功", False)
                return
            if e_dm:
                INFO(summarize_gql_failure(title="delivery method GraphQL errors", errors=e_dm, raw=r_dm))
                CHECK_POINT("配送方式 GraphQL 无错", False)
                return
            n_dm = (d_dm or {}).get("checkoutDeliveryMethodUpdate")
            if isinstance(n_dm, dict) and n_dm.get("errors"):
                INFO(f"checkoutDeliveryMethodUpdate 错误: {n_dm.get('errors')}")
                CHECK_POINT("配送方式业务无错", False)
                return

        STEP(5, "[Payments] checkoutPaymentCreate（Dummy 网关）")
        data4, err4, raw4 = _query_checkout_for_flow(url, checkout_token)
        if err4:
            INFO(summarize_gql_failure(title="FULL-0001 支付前查询 checkout", errors=err4, raw=raw4))
            CHECK_POINT("支付前查询成功", False)
            return

        ck4 = (data4 or {}).get("checkout")
        if not isinstance(ck4, dict):
            CHECK_POINT("支付前 checkout 存在", False)
            return

        gateways = ck4.get("availablePaymentGateways")
        gateway_id = _payment_gateway_id()
        if isinstance(gateways, list) and len(gateways) > 0:
            ids = [g.get("id") for g in gateways if isinstance(g, dict) and g.get("id")]
            if gateway_id not in ids:
                INFO(f"环境可用网关: {ids}，当前配置 SALEOR_PAYMENT_GATEWAY={gateway_id!r}")
                if ids:
                    gateway_id = ids[0]
                    INFO(f"自动改用第一个可用网关: {gateway_id!r}")
                else:
                    raise RuntimeError("BLOCKED: availablePaymentGateways 无可用 id（请启用 Dummy 网关）")
        else:
            raise RuntimeError(
                "BLOCKED: checkout 上无 availablePaymentGateways（需在 Channel 启用 mirumee.payments.dummy 等）"
            )

        total = ck4.get("totalPrice")
        if not isinstance(total, dict) or not isinstance(total.get("gross"), dict):
            CHECK_POINT("totalPrice.gross 存在", False)
            return
        amount_str = total["gross"].get("amount")
        if amount_str is None:
            CHECK_POINT("total amount 存在", False)
            return
        amount_str = str(amount_str)

        m_pay = """
        mutation Pay($id: ID!, $input: PaymentInput!) {
          checkoutPaymentCreate(id: $id, input: $input) {
            errors { field message code }
            payment { id gateway chargeStatus }
          }
        }
        """
        pay_input = {
            "amount": amount_str,
            "gateway": gateway_id,
            "token": _dummy_card_token(),
        }
        try:
            d_pay, e_pay, r_pay = gql_request(
                url,
                m_pay,
                variables={"id": checkout_id, "input": pay_input},
                timeout_s=GSTORE.http_timeout_s,
            )
        except SaleorGraphQLError as e:
            INFO(summarize_gql_failure(title="checkoutPaymentCreate", exc=e, variables={"input": pay_input}))
            CHECK_POINT("创建支付应成功", False)
            return
        if e_pay:
            INFO(summarize_gql_failure(title="checkoutPaymentCreate GraphQL errors", errors=e_pay, raw=r_pay))
            CHECK_POINT("支付 GraphQL 无错", False)
            return
        n_pay = (d_pay or {}).get("checkoutPaymentCreate")
        if isinstance(n_pay, dict) and n_pay.get("errors"):
            INFO(f"checkoutPaymentCreate 业务错误: {n_pay.get('errors')}")
            CHECK_POINT("支付业务无错", False)
            return

        STEP(6, "[Orders] checkoutComplete 生成订单")
        m_complete = """
        mutation CC($token: UUID!) {
          checkoutComplete(token: $token) {
            confirmationNeeded
            errors { field message code }
            order {
              id
              number
              status
              paymentStatus
              payments { id gateway chargeStatus }
            }
          }
        }
        """
        try:
            d_cc, e_cc, r_cc = gql_request(
                url,
                m_complete,
                variables={"token": checkout_token},
                timeout_s=GSTORE.http_timeout_s,
            )
        except SaleorGraphQLError as e:
            INFO(summarize_gql_failure(title="checkoutComplete", exc=e))
            CHECK_POINT("checkoutComplete 应成功", False)
            return
        if e_cc:
            INFO(summarize_gql_failure(title="checkoutComplete GraphQL errors", errors=e_cc, raw=r_cc))
            CHECK_POINT("完成结账 GraphQL 无错", False)
            return

        n_cc = (d_cc or {}).get("checkoutComplete")
        if not isinstance(n_cc, dict):
            CHECK_POINT("checkoutComplete 返回存在", False)
            return

        if n_cc.get("confirmationNeeded") is True:
            raise RuntimeError("BLOCKED: checkoutComplete.confirmationNeeded=true（需二次确认/3DS，自动化未配置）")

        if n_cc.get("errors"):
            INFO(f"checkoutComplete 错误: {n_cc.get('errors')}")
            CHECK_POINT("checkoutComplete.errors 为空", False)
            return

        order = n_cc.get("order")
        CHECK_POINT("已创建 order", isinstance(order, dict) and bool(order.get("id")))

        if isinstance(order, dict):
            ps = order.get("paymentStatus")
            CHECK_POINT("order.paymentStatus 非空", bool(ps), failStop=False)
            # 不同版本枚举名可能为 FULLY_PAID / FULLY_CHARGED 等
            if isinstance(ps, str):
                ok_pay = ps.upper() in ("FULLY_PAID", "FULLY_CHARGED", "PAID")
                CHECK_POINT(f"paymentStatus 表示已支付: {ps}", ok_pay, failStop=False)

            pays = order.get("payments")
            if isinstance(pays, list) and len(pays) > 0:
                p0 = pays[0]
                if isinstance(p0, dict):
                    cs = p0.get("chargeStatus")
                    CHECK_POINT("首笔 payment.chargeStatus 存在", bool(cs), failStop=False)
                    if isinstance(cs, str):
                        CHECK_POINT(
                            "chargeStatus 为已扣款状态",
                            cs.upper() in ("FULLY_CHARGED", "CHARGED", "FULLY_PAID"),
                            failStop=False,
                        )

        STEP(7, "[Orders+Payments] staff 侧按 id 复查订单（联动 40/50 类校验）")
        staff = getattr(GSTORE, "saleor_access_token", None)
        if not staff:
            INFO("无 staff token，跳过 staff order 复查")
            return

        if not isinstance(order, dict) or not order.get("id"):
            return

        q_ord = """
        query StaffOrder($id: ID!) {
          order(id: $id) {
            id
            number
            paymentStatus
            payments { id chargeStatus gateway }
          }
        }
        """
        try:
            d_o, e_o, r_o = gql_request(
                url,
                q_ord,
                variables={"id": order["id"]},
                token=staff,
                timeout_s=GSTORE.http_timeout_s,
            )
        except SaleorGraphQLError as e:
            INFO(summarize_gql_failure(title="staff order 查询", exc=e))
            CHECK_POINT("staff 能查到订单", False)
            return

        if e_o:
            INFO(summarize_gql_failure(title="staff order GraphQL errors", errors=e_o, raw=r_o))
            CHECK_POINT("staff order 查询无 GraphQL 错", False)
            return

        o2 = (d_o or {}).get("order")
        CHECK_POINT("staff order 与下单 id 一致", isinstance(o2, dict) and o2.get("id") == order.get("id"))


class cFULL0002:
    name = "FULL-0002-负向：支付金额不匹配总价→支付不成功→订单应为待支付"
    tags = ["API", "主流程", "E2E", "负向", "高风险"]

    def teststeps(self):
        require_saleor_api_ready()
        url = GSTORE.saleor_graphql_url
        buyer_email = str(getattr(GSTORE, "checkout_email", "buyer@example.com") or "buyer@example.com")

        STEP(1, "[Product] 确定 channel/variant（少付场景要求环境允许 unpaid order）")
        channel_slug = pick_channel_slug_or_block()
        variant_id = pick_variant_id_or_block(channel_slug)
        CHECK_POINT("channel 与 variant 已确定", bool(channel_slug) and bool(variant_id))
        INFO("提示：少付后仍能生成“待支付订单”通常依赖 Channel.allowUnpaidOrders=true；若环境不允许，checkoutComplete 将返回错误并被本用例标记为 BLOCKED。")

        STEP(2, "[Checkout] checkoutCreate")
        m_create = """
        mutation CheckoutCreate($channel: String!, $email: String!, $lines: [CheckoutLineInput!]!) {
          checkoutCreate(input: { channel: $channel, email: $email, lines: $lines }) {
            errors { field message code }
            checkout {
              id
              token
              totalPrice { gross { amount currency } }
              isShippingRequired
            }
          }
        }
        """
        v_create = {"channel": str(channel_slug), "email": buyer_email, "lines": [{"variantId": str(variant_id), "quantity": 1}]}
        try:
            data, errors, raw = gql_request(url, m_create, variables=v_create, timeout_s=GSTORE.http_timeout_s)
        except SaleorGraphQLError as e:
            INFO(summarize_gql_failure(title="FULL-0002 checkoutCreate", exc=e, variables=v_create))
            CHECK_POINT("checkoutCreate 应成功", False)
            return
        if errors:
            INFO(summarize_gql_failure(title="FULL-0002 checkoutCreate GraphQL errors", errors=errors, raw=raw, variables=v_create))
            CHECK_POINT("GraphQL errors 应为空", False)
            return

        node = (data or {}).get("checkoutCreate")
        if not isinstance(node, dict) or node.get("errors"):
            INFO(f"checkoutCreate 业务错误: {node}")
            CHECK_POINT("checkoutCreate.errors 为空", False)
            return
        checkout = node.get("checkout")
        if not isinstance(checkout, dict):
            CHECK_POINT("checkout 对象存在", False)
            return
        checkout_id = checkout.get("id")
        checkout_token = checkout.get("token")
        CHECK_POINT("checkout.id/token 非空", bool(checkout_id) and bool(checkout_token))

        STEP(3, "[Shipping/Billing] 更新地址并选择配送方式（若需要）")
        addr = dict(_DEFAULT_ADDRESS)

        m_bill_addr = """
        mutation BillAddr($id: ID!, $addr: AddressInput!) {
          checkoutBillingAddressUpdate(id: $id, billingAddress: $addr) {
            errors { field message code }
            checkout { id }
          }
        }
        """
        try:
            d_ba, e_ba, r_ba = gql_request(
                url,
                m_bill_addr,
                variables={"id": checkout_id, "addr": addr},
                timeout_s=GSTORE.http_timeout_s,
            )
        except SaleorGraphQLError as e:
            INFO(summarize_gql_failure(title="FULL-0002 checkoutBillingAddressUpdate", exc=e))
            CHECK_POINT("账单地址更新应成功", False)
            return
        if e_ba:
            INFO(summarize_gql_failure(title="FULL-0002 billing address GraphQL errors", errors=e_ba, raw=r_ba))
            CHECK_POINT("账单地址 GraphQL 无错", False)
            return
        n_ba = (d_ba or {}).get("checkoutBillingAddressUpdate")
        if isinstance(n_ba, dict) and n_ba.get("errors"):
            INFO(f"checkoutBillingAddressUpdate 错误: {n_ba.get('errors')}")
            CHECK_POINT("账单地址业务无错", False)
            return

        data_ck, err_ck, raw_ck = _query_checkout_for_flow(url, checkout_token)
        if err_ck:
            INFO(summarize_gql_failure(title="FULL-0002 查询 checkout", errors=err_ck, raw=raw_ck))
            CHECK_POINT("查询 checkout 成功", False)
            return
        ck = (data_ck or {}).get("checkout")
        if not isinstance(ck, dict):
            CHECK_POINT("checkout 查询非空", False)
            return
        shipping_required = bool(ck.get("isShippingRequired"))

        if shipping_required:
            m_ship_addr = """
            mutation ShipAddr($id: ID!, $addr: AddressInput!) {
              checkoutShippingAddressUpdate(id: $id, shippingAddress: $addr) {
                errors { field message code }
                checkout { id }
              }
            }
            """
            try:
                d_sa, e_sa, r_sa = gql_request(
                    url,
                    m_ship_addr,
                    variables={"id": checkout_id, "addr": addr},
                    timeout_s=GSTORE.http_timeout_s,
                )
            except SaleorGraphQLError as e:
                INFO(summarize_gql_failure(title="FULL-0002 checkoutShippingAddressUpdate", exc=e))
                CHECK_POINT("配送地址更新应成功", False)
                return
            if e_sa:
                INFO(summarize_gql_failure(title="FULL-0002 shipping address GraphQL errors", errors=e_sa, raw=r_sa))
                CHECK_POINT("配送地址 GraphQL 无错", False)
                return
            n_sa = (d_sa or {}).get("checkoutShippingAddressUpdate")
            if isinstance(n_sa, dict) and n_sa.get("errors"):
                INFO(f"checkoutShippingAddressUpdate 错误: {n_sa.get('errors')}")
                CHECK_POINT("配送地址业务无错", False)
                return

            data_ck2, err_ck2, raw_ck2 = _query_checkout_for_flow(url, checkout_token)
            if err_ck2:
                INFO(summarize_gql_failure(title="FULL-0002 二次查询 checkout", errors=err_ck2, raw=raw_ck2))
                CHECK_POINT("二次查询 checkout 成功", False)
                return
            ck2 = (data_ck2 or {}).get("checkout")
            if not isinstance(ck2, dict):
                CHECK_POINT("checkout 查询非空", False)
                return

            methods = ck2.get("shippingMethods")
            if not isinstance(methods, list) or len(methods) == 0:
                raise RuntimeError("BLOCKED: isShippingRequired=true 但 shippingMethods 为空（请配置运费/仓库）")

            delivery_method_id = None
            for m in methods:
                if isinstance(m, dict) and m.get("id"):
                    delivery_method_id = m["id"]
                    break
            if not delivery_method_id:
                raise RuntimeError("BLOCKED: 无法解析 shippingMethods[].id")

            m_dm = """
            mutation DM($id: ID!, $deliveryMethodId: ID!) {
              checkoutDeliveryMethodUpdate(id: $id, deliveryMethodId: $deliveryMethodId) {
                errors { field message code }
                checkout { id }
              }
            }
            """
            try:
                d_dm, e_dm, r_dm = gql_request(
                    url,
                    m_dm,
                    variables={"id": checkout_id, "deliveryMethodId": delivery_method_id},
                    timeout_s=GSTORE.http_timeout_s,
                )
            except SaleorGraphQLError as e:
                INFO(summarize_gql_failure(title="FULL-0002 checkoutDeliveryMethodUpdate", exc=e))
                CHECK_POINT("选择配送方式应成功", False)
                return
            if e_dm:
                INFO(summarize_gql_failure(title="FULL-0002 delivery method GraphQL errors", errors=e_dm, raw=r_dm))
                CHECK_POINT("配送方式 GraphQL 无错", False)
                return
            n_dm = (d_dm or {}).get("checkoutDeliveryMethodUpdate")
            if isinstance(n_dm, dict) and n_dm.get("errors"):
                INFO(f"checkoutDeliveryMethodUpdate 错误: {n_dm.get('errors')}")
                CHECK_POINT("配送方式业务无错", False)
                return

        STEP(4, "[Payments] 用小于 total 的金额创建支付（金额不匹配）")
        data4, err4, raw4 = _query_checkout_for_flow(url, checkout_token)
        if err4:
            INFO(summarize_gql_failure(title="FULL-0002 支付前查询 checkout", errors=err4, raw=raw4))
            CHECK_POINT("支付前查询成功", False)
            return
        ck4 = (data4 or {}).get("checkout")
        if not isinstance(ck4, dict):
            CHECK_POINT("checkout 存在", False)
            return
        gateways = ck4.get("availablePaymentGateways")
        if not isinstance(gateways, list) or len(gateways) == 0:
            raise RuntimeError("BLOCKED: checkout 上无 availablePaymentGateways（需在 Channel 启用 Dummy 等网关）")

        gateway_id = _payment_gateway_id()
        ids = [g.get("id") for g in gateways if isinstance(g, dict) and g.get("id")]
        if gateway_id not in ids:
            gateway_id = ids[0] if ids else gateway_id

        total = ck4.get("totalPrice")
        if not isinstance(total, dict) or not isinstance(total.get("gross"), dict):
            CHECK_POINT("totalPrice.gross 存在", False)
            return
        amount = total["gross"].get("amount")
        if amount is None:
            CHECK_POINT("total amount 存在", False)
            return

        try:
            total_amount = float(str(amount))
        except Exception:
            CHECK_POINT("total amount 可转为数字", False)
            return
        if total_amount <= 0:
            raise RuntimeError("BLOCKED: totalAmount<=0，无法构造“少付”场景")
        underpay_amount = max(0.01, round(total_amount - 0.01, 2))
        CHECK_POINT("underpay_amount < total_amount", underpay_amount < total_amount)

        m_pay = """
        mutation Pay($id: ID!, $input: PaymentInput!) {
          checkoutPaymentCreate(id: $id, input: $input) {
            errors { field message code }
            payment { id gateway chargeStatus }
          }
        }
        """
        pay_input = {
            "amount": str(underpay_amount),
            "gateway": gateway_id,
            "token": _dummy_card_token(),
        }
        try:
            d_pay, e_pay, r_pay = gql_request(
                url,
                m_pay,
                variables={"id": checkout_id, "input": pay_input},
                timeout_s=GSTORE.http_timeout_s,
            )
        except SaleorGraphQLError as e:
            INFO(summarize_gql_failure(title="FULL-0002 checkoutPaymentCreate", exc=e, variables={"input": pay_input}))
            CHECK_POINT("创建支付应成功返回", False)
            return
        if e_pay:
            INFO(summarize_gql_failure(title="FULL-0002 checkoutPaymentCreate GraphQL errors", errors=e_pay, raw=r_pay))
            CHECK_POINT("支付 GraphQL 无错", False)
            return
        n_pay = (d_pay or {}).get("checkoutPaymentCreate")
        if isinstance(n_pay, dict) and n_pay.get("errors"):
            pay_errors = n_pay.get("errors") or []
            INFO(f"checkoutPaymentCreate 业务错误: {pay_errors}")

            # 目标场景：支付金额不匹配总价 → 支付不成功（这里允许/期望报错）
            # 常见返回：PARTIAL_PAYMENT_NOT_ALLOWED
            expect_code = False
            if isinstance(pay_errors, list):
                for e in pay_errors:
                    if isinstance(e, dict) and str(e.get("code", "")).upper() in ("PARTIAL_PAYMENT_NOT_ALLOWED",):
                        expect_code = True
                        break
            CHECK_POINT("少付应触发部分支付不允许（或等价错误）", expect_code, failStop=False)
            INFO("支付创建未成功（符合本用例的负向前置），继续尝试生成待支付订单。")

        STEP(5, "[Orders] checkoutComplete → 订单应为待支付（未完全覆盖总价）")
        m_complete = """
        mutation CC($token: UUID!) {
          checkoutComplete(token: $token) {
            confirmationNeeded
            errors { field message code }
            order {
              id
              number
              status
              paymentStatus
              payments { id gateway chargeStatus }
            }
          }
        }
        """
        try:
            d_cc, e_cc, r_cc = gql_request(
                url,
                m_complete,
                variables={"token": checkout_token},
                timeout_s=GSTORE.http_timeout_s,
            )
        except SaleorGraphQLError as e:
            INFO(summarize_gql_failure(title="FULL-0002 checkoutComplete", exc=e))
            CHECK_POINT("checkoutComplete 应成功", False)
            return
        if e_cc:
            INFO(summarize_gql_failure(title="FULL-0002 checkoutComplete GraphQL errors", errors=e_cc, raw=r_cc))
            CHECK_POINT("完成结账 GraphQL 无错", False)
            return

        n_cc = (d_cc or {}).get("checkoutComplete")
        if not isinstance(n_cc, dict):
            CHECK_POINT("checkoutComplete 返回存在", False)
            return
        if n_cc.get("confirmationNeeded") is True:
            raise RuntimeError("BLOCKED: checkoutComplete.confirmationNeeded=true（需二次确认/3DS，自动化未配置）")
        if n_cc.get("errors"):
            INFO(f"checkoutComplete 错误: {n_cc.get('errors')}")
            raise RuntimeError(
                "BLOCKED: 环境不允许“未付清仍下单”（通常需要 Channel.allowUnpaidOrders=true，"
                "或需要交易/支付完全覆盖 total 才能完成 checkout）"
            )

        order = n_cc.get("order")
        CHECK_POINT("已创建 order（允许 unpaid）", isinstance(order, dict) and bool(order.get("id")))
        if not isinstance(order, dict):
            return

        ps = order.get("paymentStatus")
        CHECK_POINT("order.paymentStatus 非空", bool(ps), failStop=False)
        if isinstance(ps, str):
            # 目标：少付情况下应处于未支付/待支付，而不是 FULLY_PAID/FULLY_CHARGED
            not_paid = ps.upper() not in ("FULLY_PAID", "FULLY_CHARGED", "PAID")
            CHECK_POINT(f"paymentStatus 应为待支付（实际={ps}）", not_paid)

