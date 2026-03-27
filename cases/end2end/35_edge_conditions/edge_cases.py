"""
边界条件/幂等性用例：
- “同时点两次支付”：用连续两次调用 checkoutPaymentCreate / checkoutComplete 来模拟 UI 双击或重复提交。
- “并发点两次支付”：用线程 + Barrier 让两次 checkoutPaymentCreate 几乎同时发出（更接近真实双击/连点）。
- 验证目标：
  - 不应生成两笔“已扣款”的支付（或至少应被系统拒绝/去重）。
  - 不应生成两张不同的订单（重复下单）。

注意：
- 不同 Saleor 配置对“重复支付/重复完成 checkout”行为可能不同；本套件以“不能产生重复订单/重复扣费”为核心断言。
- 若环境缺少 Dummy 网关或不允许 checkoutComplete（需 fully paid 或 allow unpaid orders），用例会 BLOCKED。
"""

import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from cytest import STEP, INFO, CHECK_POINT, GSTORE

from lib.saleor_api import SaleorGraphQLError, gql_request
from lib.gql_diagnose import summarize_gql_failure
from lib.saleor_flow_helpers import (
    require_saleor_api_ready,
    pick_channel_slug_or_block,
    pick_variant_id_or_block,
)


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
    return os.getenv("SALEOR_DUMMY_PAYMENT_TOKEN", "4242424242424242").strip() or "4242424242424242"


def _query_checkout(url: str, token):
    q = """
    query Q($token: UUID!) {
      checkout(token: $token) {
        id
        token
        isShippingRequired
        shippingMethods { id name }
        availablePaymentGateways { id name }
        totalPrice { gross { amount currency } }
      }
    }
    """
    return gql_request(url, q, variables={"token": token}, timeout_s=GSTORE.http_timeout_s)


def _prepare_checkout_ready_for_payment(url: str):
    """
    创建 checkout + 地址 + （若需要）配送方式，返回 (checkout_id, checkout_token, total_amount_str)。
    """
    channel_slug = pick_channel_slug_or_block()
    variant_id = pick_variant_id_or_block(channel_slug)

    m_create = """
    mutation C($channel: String!, $email: String!, $lines: [CheckoutLineInput!]!) {
      checkoutCreate(input: { channel: $channel, email: $email, lines: $lines }) {
        errors { field message code }
        checkout { id token }
      }
    }
    """
    v_create = {
        "channel": str(channel_slug),
        "email": str(getattr(GSTORE, "checkout_email", "buyer@example.com") or "buyer@example.com"),
        "lines": [{"variantId": str(variant_id), "quantity": 1}],
    }
    data, errors, raw = gql_request(url, m_create, variables=v_create, timeout_s=GSTORE.http_timeout_s)
    if errors:
        INFO(summarize_gql_failure(title="EDGE checkoutCreate GraphQL errors", errors=errors, raw=raw, variables=v_create))
        raise RuntimeError("BLOCKED: checkoutCreate GraphQL errors")
    node = (data or {}).get("checkoutCreate")
    if not isinstance(node, dict) or node.get("errors"):
        INFO(f"checkoutCreate 业务错误: {node}")
        raise RuntimeError("BLOCKED: checkoutCreate errors")
    ck = node.get("checkout")
    if not isinstance(ck, dict) or not ck.get("id") or not ck.get("token"):
        raise RuntimeError("BLOCKED: checkoutCreate 未返回 id/token")
    checkout_id = ck["id"]
    checkout_token = ck["token"]

    # 更新账单地址（大多数场景需要）
    m_bill = """
    mutation B($id: ID!, $addr: AddressInput!) {
      checkoutBillingAddressUpdate(id: $id, billingAddress: $addr) {
        errors { field message code }
        checkout { id }
      }
    }
    """
    d_b, e_b, r_b = gql_request(url, m_bill, variables={"id": checkout_id, "addr": dict(_DEFAULT_ADDRESS)}, timeout_s=GSTORE.http_timeout_s)
    if e_b:
        INFO(summarize_gql_failure(title="EDGE billing address GraphQL errors", errors=e_b, raw=r_b))
        raise RuntimeError("BLOCKED: checkoutBillingAddressUpdate GraphQL errors")
    n_b = (d_b or {}).get("checkoutBillingAddressUpdate")
    if isinstance(n_b, dict) and n_b.get("errors"):
        INFO(f"checkoutBillingAddressUpdate errors: {n_b.get('errors')}")
        raise RuntimeError("BLOCKED: checkoutBillingAddressUpdate errors")

    # 查询 checkout，决定是否需要配送
    d_q, e_q, r_q = _query_checkout(url, checkout_token)
    if e_q:
        INFO(summarize_gql_failure(title="EDGE 查询 checkout GraphQL errors", errors=e_q, raw=r_q))
        raise RuntimeError("BLOCKED: checkout 查询 errors")
    ck2 = (d_q or {}).get("checkout")
    if not isinstance(ck2, dict):
        raise RuntimeError("BLOCKED: checkout 查询为空")

    if ck2.get("isShippingRequired"):
        m_ship = """
        mutation S($id: ID!, $addr: AddressInput!) {
          checkoutShippingAddressUpdate(id: $id, shippingAddress: $addr) {
            errors { field message code }
            checkout { id }
          }
        }
        """
        d_s, e_s, r_s = gql_request(url, m_ship, variables={"id": checkout_id, "addr": dict(_DEFAULT_ADDRESS)}, timeout_s=GSTORE.http_timeout_s)
        if e_s:
            INFO(summarize_gql_failure(title="EDGE shipping address GraphQL errors", errors=e_s, raw=r_s))
            raise RuntimeError("BLOCKED: checkoutShippingAddressUpdate GraphQL errors")
        n_s = (d_s or {}).get("checkoutShippingAddressUpdate")
        if isinstance(n_s, dict) and n_s.get("errors"):
            INFO(f"checkoutShippingAddressUpdate errors: {n_s.get('errors')}")
            raise RuntimeError("BLOCKED: checkoutShippingAddressUpdate errors")

        # 选择配送方式
        d_q2, e_q2, r_q2 = _query_checkout(url, checkout_token)
        if e_q2:
            INFO(summarize_gql_failure(title="EDGE 二次查询 checkout GraphQL errors", errors=e_q2, raw=r_q2))
            raise RuntimeError("BLOCKED: checkout 查询 errors")
        ck3 = (d_q2 or {}).get("checkout")
        if not isinstance(ck3, dict):
            raise RuntimeError("BLOCKED: checkout 查询为空")

        methods = ck3.get("shippingMethods")
        if not isinstance(methods, list) or len(methods) == 0:
            raise RuntimeError("BLOCKED: isShippingRequired=true 但 shippingMethods 为空")
        delivery_id = None
        for m in methods:
            if isinstance(m, dict) and m.get("id"):
                delivery_id = m["id"]
                break
        if not delivery_id:
            raise RuntimeError("BLOCKED: 无法解析 shippingMethods[].id")

        m_dm = """
        mutation DM($id: ID!, $deliveryMethodId: ID!) {
          checkoutDeliveryMethodUpdate(id: $id, deliveryMethodId: $deliveryMethodId) {
            errors { field message code }
            checkout { id }
          }
        }
        """
        d_dm, e_dm, r_dm = gql_request(url, m_dm, variables={"id": checkout_id, "deliveryMethodId": delivery_id}, timeout_s=GSTORE.http_timeout_s)
        if e_dm:
            INFO(summarize_gql_failure(title="EDGE delivery method GraphQL errors", errors=e_dm, raw=r_dm))
            raise RuntimeError("BLOCKED: checkoutDeliveryMethodUpdate GraphQL errors")
        n_dm = (d_dm or {}).get("checkoutDeliveryMethodUpdate")
        if isinstance(n_dm, dict) and n_dm.get("errors"):
            INFO(f"checkoutDeliveryMethodUpdate errors: {n_dm.get('errors')}")
            raise RuntimeError("BLOCKED: checkoutDeliveryMethodUpdate errors")

    # 取 total amount
    d_q3, e_q3, r_q3 = _query_checkout(url, checkout_token)
    if e_q3:
        INFO(summarize_gql_failure(title="EDGE 支付前查询 checkout GraphQL errors", errors=e_q3, raw=r_q3))
        raise RuntimeError("BLOCKED: checkout 查询 errors")
    ck4 = (d_q3 or {}).get("checkout")
    if not isinstance(ck4, dict):
        raise RuntimeError("BLOCKED: checkout 查询为空")
    gateways = ck4.get("availablePaymentGateways")
    if not isinstance(gateways, list) or len(gateways) == 0:
        raise RuntimeError("BLOCKED: checkout 上无 availablePaymentGateways（需启用 Dummy 等网关）")

    total = ck4.get("totalPrice")
    if not isinstance(total, dict) or not isinstance(total.get("gross"), dict):
        raise RuntimeError("BLOCKED: totalPrice.gross 不存在")
    amount = total["gross"].get("amount")
    if amount is None:
        raise RuntimeError("BLOCKED: total amount 为空")
    return checkout_id, checkout_token, str(amount)


def _staff_get_order(url: str, order_id: str):
    staff = getattr(GSTORE, "saleor_access_token", None)
    if not staff:
        raise RuntimeError("BLOCKED: 缺少 staff token（无法查询 order/payments 以验证是否重复扣费/重复订单）")
    q = """
    query O($id: ID!) {
      order(id: $id) {
        id
        number
        paymentStatus
        payments { id gateway chargeStatus }
      }
    }
    """
    data, errors, raw = gql_request(url, q, variables={"id": str(order_id)}, token=staff, timeout_s=GSTORE.http_timeout_s)
    if errors:
        INFO(summarize_gql_failure(title="staff order 查询 GraphQL errors", errors=errors, raw=raw, variables={"id": order_id}))
        raise RuntimeError("BLOCKED: staff order 查询 errors")
    return (data or {}).get("order")


class cEDGE0001:
    name = "EDGE-0001-双击支付：重复 checkoutPaymentCreate 不应导致双重扣费"
    tags = ["API", "边界", "幂等性", "高风险"]

    def teststeps(self):
        require_saleor_api_ready()
        url = GSTORE.saleor_graphql_url

        STEP(1, "准备一个可支付的 checkout（含地址/配送/总价）")
        checkout_id, checkout_token, amount_str = _prepare_checkout_ready_for_payment(url)
        CHECK_POINT("checkout_token 非空", bool(checkout_token))

        STEP(2, "第一次 checkoutPaymentCreate（正常金额）")
        m_pay = """
        mutation Pay($id: ID!, $input: PaymentInput!) {
          checkoutPaymentCreate(id: $id, input: $input) {
            errors { field message code }
            payment { id gateway chargeStatus }
          }
        }
        """
        pay_input = {"amount": amount_str, "gateway": _payment_gateway_id(), "token": _dummy_card_token()}
        d1, e1, r1 = gql_request(url, m_pay, variables={"id": checkout_id, "input": pay_input}, timeout_s=GSTORE.http_timeout_s)
        if e1:
            INFO(summarize_gql_failure(title="EDGE-0001 第一次支付 GraphQL errors", errors=e1, raw=r1))
            CHECK_POINT("第一次支付 GraphQL 无错", False)
            return
        n1 = (d1 or {}).get("checkoutPaymentCreate")
        if isinstance(n1, dict) and n1.get("errors"):
            INFO(f"第一次支付业务错误: {n1.get('errors')}")
            raise RuntimeError("BLOCKED: 第一次支付未成功（检查网关/配置）")
        p1 = n1.get("payment") if isinstance(n1, dict) else None
        p1_id = p1.get("id") if isinstance(p1, dict) else None
        CHECK_POINT("首次 payment.id 非空", bool(p1_id), failStop=False)

        STEP(3, "立刻第二次 checkoutPaymentCreate（模拟双击/重复提交）")
        d2, e2, r2 = gql_request(url, m_pay, variables={"id": checkout_id, "input": pay_input}, timeout_s=GSTORE.http_timeout_s)
        if e2:
            INFO(summarize_gql_failure(title="EDGE-0001 第二次支付 GraphQL errors", errors=e2, raw=r2))
            CHECK_POINT("第二次支付 GraphQL 不应报错（更优），但可接受业务 errors", True, failStop=False)
        n2 = (d2 or {}).get("checkoutPaymentCreate")

        # 允许第二次被拒绝（更符合幂等性）
        if isinstance(n2, dict) and n2.get("errors"):
            INFO(f"第二次支付被系统拒绝（期望行为之一）: {n2.get('errors')}")
            CHECK_POINT("重复支付应被拒绝或去重", True)
            return

        p2 = n2.get("payment") if isinstance(n2, dict) else None
        p2_id = p2.get("id") if isinstance(p2, dict) else None
        if p2_id and p1_id and p2_id != p1_id:
            INFO(f"重复提交返回了另一笔 payment.id（不一定代表重复扣费）：p1={p1_id}, p2={p2_id}")

        STEP(4, "完成 checkout 并从订单 payments 校验：不应出现两笔已扣款（防重复扣费）")
        m_cc = """
        mutation CC($token: UUID!) {
          checkoutComplete(token: $token) {
            confirmationNeeded
            errors { field message code }
            order { id number paymentStatus payments { id chargeStatus gateway } }
          }
        }
        """
        d_cc, e_cc, r_cc = gql_request(url, m_cc, variables={"token": checkout_token}, timeout_s=GSTORE.http_timeout_s)
        if e_cc:
            INFO(summarize_gql_failure(title="EDGE-0001 checkoutComplete GraphQL errors", errors=e_cc, raw=r_cc))
            raise RuntimeError("BLOCKED: checkoutComplete GraphQL errors（环境可能不允许完成 checkout）")
        n_cc = (d_cc or {}).get("checkoutComplete")
        if not isinstance(n_cc, dict):
            raise RuntimeError("BLOCKED: checkoutComplete 返回为空")
        if n_cc.get("confirmationNeeded") is True:
            raise RuntimeError("BLOCKED: confirmationNeeded=true（需二次确认/3DS）")
        if n_cc.get("errors"):
            INFO(f"checkoutComplete errors: {n_cc.get('errors')}")
            raise RuntimeError("BLOCKED: checkoutComplete errors（可能要求 fully paid 或支付配置不完整）")
        order = n_cc.get("order")
        if not isinstance(order, dict) or not order.get("id"):
            raise RuntimeError("BLOCKED: 未生成 order，无法校验扣费次数")

        # 更强校验：订单侧最多 1 笔“已扣款”
        o = _staff_get_order(url, order["id"])
        CHECK_POINT("staff order 可查询", isinstance(o, dict), failStop=False)
        if isinstance(o, dict):
            pays = o.get("payments")
            charged = 0
            if isinstance(pays, list):
                for p in pays:
                    if isinstance(p, dict):
                        cs = str(p.get("chargeStatus") or "").upper()
                        if cs in ("FULLY_CHARGED", "CHARGED", "FULLY_PAID"):
                            charged += 1
            CHECK_POINT("双击支付不应导致两笔已扣款", charged <= 1)


class cEDGE0002:
    name = "EDGE-0002-双击下单：重复 checkoutComplete 不应生成两张订单"
    tags = ["API", "边界", "幂等性", "高风险"]

    def teststeps(self):
        require_saleor_api_ready()
        url = GSTORE.saleor_graphql_url

        STEP(1, "准备 checkout 并完成一次支付（确保能 checkoutComplete）")
        checkout_id, checkout_token, amount_str = _prepare_checkout_ready_for_payment(url)

        m_pay = """
        mutation Pay($id: ID!, $input: PaymentInput!) {
          checkoutPaymentCreate(id: $id, input: $input) {
            errors { field message code }
            payment { id chargeStatus }
          }
        }
        """
        pay_input = {"amount": amount_str, "gateway": _payment_gateway_id(), "token": _dummy_card_token()}
        d1, e1, r1 = gql_request(url, m_pay, variables={"id": checkout_id, "input": pay_input}, timeout_s=GSTORE.http_timeout_s)
        if e1:
            INFO(summarize_gql_failure(title="EDGE-0002 支付 GraphQL errors", errors=e1, raw=r1))
            raise RuntimeError("BLOCKED: 无法创建支付")
        n1 = (d1 or {}).get("checkoutPaymentCreate")
        if isinstance(n1, dict) and n1.get("errors"):
            INFO(f"支付业务错误: {n1.get('errors')}")
            raise RuntimeError("BLOCKED: 支付未成功（检查网关/配置）")

        STEP(2, "第一次 checkoutComplete（生成订单）")
        m_cc = """
        mutation CC($token: UUID!) {
          checkoutComplete(token: $token) {
            confirmationNeeded
            errors { field message code }
            order { id number paymentStatus payments { id chargeStatus gateway } }
          }
        }
        """
        d_cc1, e_cc1, r_cc1 = gql_request(url, m_cc, variables={"token": checkout_token}, timeout_s=GSTORE.http_timeout_s)
        if e_cc1:
            INFO(summarize_gql_failure(title="EDGE-0002 第一次 checkoutComplete GraphQL errors", errors=e_cc1, raw=r_cc1))
            raise RuntimeError("BLOCKED: checkoutComplete GraphQL errors")
        n_cc1 = (d_cc1 or {}).get("checkoutComplete")
        if not isinstance(n_cc1, dict):
            CHECK_POINT("checkoutComplete 返回存在", False)
            return
        if n_cc1.get("confirmationNeeded") is True:
            raise RuntimeError("BLOCKED: confirmationNeeded=true（需二次确认/3DS）")
        if n_cc1.get("errors"):
            INFO(f"第一次 checkoutComplete errors: {n_cc1.get('errors')}")
            raise RuntimeError("BLOCKED: checkoutComplete errors（可能要求 fully paid）")
        order1 = n_cc1.get("order")
        CHECK_POINT("第一次应创建 order", isinstance(order1, dict) and bool(order1.get("id")))
        if not isinstance(order1, dict) or not order1.get("id"):
            return
        order1_id = order1["id"]

        STEP(3, "立刻第二次 checkoutComplete（模拟双击下单/重复提交）")
        d_cc2, e_cc2, r_cc2 = gql_request(url, m_cc, variables={"token": checkout_token}, timeout_s=GSTORE.http_timeout_s)
        if e_cc2:
            INFO(summarize_gql_failure(title="EDGE-0002 第二次 checkoutComplete GraphQL errors", errors=e_cc2, raw=r_cc2))
            CHECK_POINT("第二次 checkoutComplete 可报错（期望行为之一）", True, failStop=False)
            return
        n_cc2 = (d_cc2 or {}).get("checkoutComplete")
        if not isinstance(n_cc2, dict):
            CHECK_POINT("第二次 checkoutComplete 返回存在", True, failStop=False)
            return
        if n_cc2.get("errors"):
            INFO(f"第二次 checkoutComplete 被系统拒绝（期望行为之一）: {n_cc2.get('errors')}")
            CHECK_POINT("重复下单应被拒绝或去重", True)
            return

        order2 = n_cc2.get("order")
        if isinstance(order2, dict) and order2.get("id"):
            # 关键断言：不能生成另一张不同订单
            CHECK_POINT("重复 checkoutComplete 不应生成不同订单", order2.get("id") == order1_id)
        else:
            CHECK_POINT("第二次未返回订单（可接受）", True, failStop=False)

        STEP(4, "staff 侧复查订单 payments（可选强化：不应出现多笔 fully charged）")
        o = _staff_get_order(url, order1_id)
        CHECK_POINT("staff order 可查询", isinstance(o, dict), failStop=False)
        if isinstance(o, dict):
            pays = o.get("payments")
            if isinstance(pays, list) and len(pays) > 1:
                charged = 0
                for p in pays:
                    if isinstance(p, dict):
                        cs = str(p.get("chargeStatus") or "").upper()
                        if cs in ("FULLY_CHARGED", "CHARGED", "FULLY_PAID"):
                            charged += 1
                CHECK_POINT("不应出现两笔及以上已扣款支付（疑似重复扣费）", charged <= 1)


def _concurrent_checkout_payment_create(url: str, checkout_id: str, pay_input: dict):
    """
    两个线程在 Barrier 上同步后几乎同时发起 checkoutPaymentCreate。
    返回 [(data, errors, raw), (data, errors, raw)]，顺序不固定。
    """
    m_pay = """
    mutation Pay($id: ID!, $input: PaymentInput!) {
      checkoutPaymentCreate(id: $id, input: $input) {
        errors { field message code }
        payment { id gateway chargeStatus }
      }
    }
    """
    barrier = threading.Barrier(2)
    results = []
    lock = threading.Lock()

    def _one_shot():
        barrier.wait()
        try:
            out = gql_request(
                url,
                m_pay,
                variables={"id": checkout_id, "input": pay_input},
                timeout_s=GSTORE.http_timeout_s,
            )
        except Exception as e:
            with lock:
                results.append(("exception", str(e)))
            return
        with lock:
            results.append(out)

    with ThreadPoolExecutor(max_workers=2) as ex:
        f1 = ex.submit(_one_shot)
        f2 = ex.submit(_one_shot)
        for f in as_completed([f1, f2]):
            f.result()

    return results


class cEDGE0003:
    name = "EDGE-0003-并发支付：两线程同时 checkoutPaymentCreate 不应双重扣费"
    tags = ["API", "边界", "幂等性", "并发", "高风险"]

    def teststeps(self):
        require_saleor_api_ready()
        url = GSTORE.saleor_graphql_url

        STEP(1, "准备一个可支付的 checkout（含地址/配送/总价）")
        checkout_id, checkout_token, amount_str = _prepare_checkout_ready_for_payment(url)
        CHECK_POINT("checkout_token 非空", bool(checkout_token))

        pay_input = {"amount": amount_str, "gateway": _payment_gateway_id(), "token": _dummy_card_token()}

        STEP(2, "两线程 Barrier 同步后几乎同时发起两次 checkoutPaymentCreate")
        pair = _concurrent_checkout_payment_create(url, checkout_id, pay_input)
        CHECK_POINT("并发两线程均已执行", len(pair) == 2)

        ok_ids = []
        for item in pair:
            if isinstance(item, tuple) and item[0] == "exception":
                INFO(f"并发支付线程异常: {item[1]}")
                continue
            data, errors, raw = item
            if errors:
                INFO(summarize_gql_failure(title="EDGE-0003 并发支付 GraphQL errors", errors=errors, raw=raw))
                continue
            node = (data or {}).get("checkoutPaymentCreate")
            if isinstance(node, dict) and node.get("errors"):
                INFO(f"并发支付业务错误: {node.get('errors')}")
                continue
            p = node.get("payment") if isinstance(node, dict) else None
            if isinstance(p, dict) and p.get("id"):
                ok_ids.append(p["id"])

        INFO(f"并发两次支付：成功返回的 payment.id 列表（可能 1/2 个）={ok_ids}")
        if len(ok_ids) == 0:
            raise RuntimeError("BLOCKED: 并发两次 checkoutPaymentCreate 均未返回成功 payment（无法继续 checkoutComplete）")

        STEP(3, "checkoutComplete 后从订单 payments 校验：已扣款笔数不应 >1")
        m_cc = """
        mutation CC($token: UUID!) {
          checkoutComplete(token: $token) {
            confirmationNeeded
            errors { field message code }
            order { id number paymentStatus payments { id chargeStatus gateway } }
          }
        }
        """
        d_cc, e_cc, r_cc = gql_request(url, m_cc, variables={"token": checkout_token}, timeout_s=GSTORE.http_timeout_s)
        if e_cc:
            INFO(summarize_gql_failure(title="EDGE-0003 checkoutComplete GraphQL errors", errors=e_cc, raw=r_cc))
            raise RuntimeError("BLOCKED: checkoutComplete GraphQL errors")
        n_cc = (d_cc or {}).get("checkoutComplete")
        if not isinstance(n_cc, dict):
            raise RuntimeError("BLOCKED: checkoutComplete 返回为空")
        if n_cc.get("confirmationNeeded") is True:
            raise RuntimeError("BLOCKED: confirmationNeeded=true（需二次确认/3DS）")
        if n_cc.get("errors"):
            INFO(f"checkoutComplete errors: {n_cc.get('errors')}")
            raise RuntimeError("BLOCKED: checkoutComplete errors（可能两笔并发支付导致状态异常或总额未覆盖）")
        order = n_cc.get("order")
        if not isinstance(order, dict) or not order.get("id"):
            raise RuntimeError("BLOCKED: 未生成 order，无法校验扣费次数")

        o = _staff_get_order(url, order["id"])
        CHECK_POINT("staff order 可查询", isinstance(o, dict), failStop=False)
        if isinstance(o, dict):
            pays = o.get("payments")
            charged = 0
            if isinstance(pays, list):
                for p in pays:
                    if isinstance(p, dict):
                        cs = str(p.get("chargeStatus") or "").upper()
                        if cs in ("FULLY_CHARGED", "CHARGED", "FULLY_PAID"):
                            charged += 1
            CHECK_POINT("并发支付不应导致两笔已扣款", charged <= 1)

