from cytest import STEP, INFO, CHECK_POINT, GSTORE

from lib.saleor_api import SaleorGraphQLError, gql_request
from lib.gql_diagnose import summarize_gql_failure


def _require_saleor_api_ready():
    url = getattr(GSTORE, "saleor_graphql_url", "")
    if url is None:
        url = ""
    if url == "":
        raise RuntimeError("BLOCKED: 未配置 SALEOR_GRAPHQL_URL")
    if getattr(GSTORE, "saleor_api_callable", True) is False:
        raise RuntimeError("BLOCKED: SALEOR_GRAPHQL_URL 不支持 POST GraphQL")


def _pick_channel_slug_or_block():
    slug = getattr(GSTORE, "saleor_channel_slug", "")
    if slug is None:
        slug = ""
    if slug != "":
        return slug

    token = getattr(GSTORE, "saleor_access_token", None)
    if not token:
        raise RuntimeError("BLOCKED: 未配置 SALEOR_CHANNEL_SLUG 且无 staff token")

    url = GSTORE.saleor_graphql_url
    data, errors, raw = gql_request(url, "query { channels { slug } }", token=token, timeout_s=GSTORE.http_timeout_s)
    if errors:
        INFO(summarize_gql_failure(title="PRICING 自动查询 channels 失败", errors=errors, raw=raw))
        raise RuntimeError("BLOCKED: 查询 channels 失败（权限不足）")
    channels = data.get("channels") if data else None
    if not isinstance(channels, list) or len(channels) == 0:
        raise RuntimeError("BLOCKED: channels 为空")
    first = channels[0]
    if not isinstance(first, dict):
        raise RuntimeError("BLOCKED: channels[0] 结构异常")
    slug = first.get("slug")
    if not slug:
        raise RuntimeError("BLOCKED: channel.slug 为空")
    GSTORE.saleor_channel_slug = slug
    return slug


class cPRICING0001:
    name = "PRICING-0001-读取 checkout 价格字段契约（subtotal/total 为非负数）"
    tags = ["API", "回归"]

    def teststeps(self):
        _require_saleor_api_ready()

        url = GSTORE.saleor_graphql_url
        channel = _pick_channel_slug_or_block()

        STEP(1, "选一个 variantId（从 products 里取第一个带 variants 的商品）")
        q_pick = """
        query PickVariant($first: Int!, $channel: String!) {
          products(first: $first, channel: $channel) {
            edges {
              node {
                variants { id }
              }
            }
          }
        }
        """
        variables = {"first": 3, "channel": str(channel)}
        try:
            data, errors, raw = gql_request(url, q_pick, variables=variables, timeout_s=GSTORE.http_timeout_s)
        except SaleorGraphQLError as e:
            INFO(summarize_gql_failure(title="PRICING-0001 取 variant 失败", exc=e, variables=variables))
            CHECK_POINT("取 variantId 成功", False)
            return
        CHECK_POINT("GraphQL errors 为空（pick）", errors == [], failStop=False)
        products = data.get("products") if isinstance(data, dict) else None
        edges = products.get("edges") if isinstance(products, dict) else None
        variant_id = None
        if isinstance(edges, list):
            for edge in edges:
                node = edge.get("node") if isinstance(edge, dict) else None
                variants = node.get("variants") if isinstance(node, dict) else None
                if isinstance(variants, list) and len(variants) > 0 and isinstance(variants[0], dict):
                    variant_id = variants[0].get("id")
                    break
        CHECK_POINT("variantId 非空", bool(variant_id))
        if not variant_id:
            return

        STEP(2, "创建 checkout，并断言 subtotal/total 字段结构与非负")
        m_create = """
        mutation CheckoutCreate($channel: String!, $email: String!, $lines: [CheckoutLineInput!]!) {
          checkoutCreate(input: { channel: $channel, email: $email, lines: $lines }) {
            errors { field message code }
            checkout {
              subtotalPrice { gross { amount currency } }
              totalPrice { gross { amount currency } }
            }
          }
        }
        """
        variables2 = {
            "channel": str(channel),
            "email": "buyer@example.com",
            "lines": [{"variantId": str(variant_id), "quantity": 1}],
        }
        try:
            data2, errors2, raw2 = gql_request(url, m_create, variables=variables2, timeout_s=GSTORE.http_timeout_s)
        except SaleorGraphQLError as e:
            INFO(summarize_gql_failure(title="PRICING-0001 checkoutCreate 失败", exc=e, variables=variables2))
            CHECK_POINT("checkoutCreate 成功", False)
            return

        CHECK_POINT("GraphQL errors 为空（checkoutCreate）", errors2 == [], failStop=False)
        node = data2.get("checkoutCreate") if isinstance(data2, dict) else None
        CHECK_POINT("checkoutCreate 节点存在", isinstance(node, dict))
        if not isinstance(node, dict):
            return

        cp_errors = node.get("errors") or []
        CHECK_POINT("checkoutCreate.errors 为空", cp_errors == [], failStop=False)

        checkout = node.get("checkout")
        CHECK_POINT("checkout 存在", isinstance(checkout, dict))
        if not isinstance(checkout, dict):
            return

        subtotal = checkout.get("subtotalPrice")
        total = checkout.get("totalPrice")
        CHECK_POINT("subtotalPrice 为 dict", isinstance(subtotal, dict))
        CHECK_POINT("totalPrice 为 dict", isinstance(total, dict))

        def _amount(taxed_money):
            gross = taxed_money.get("gross") if isinstance(taxed_money, dict) else None
            amount = gross.get("amount") if isinstance(gross, dict) else None
            return amount

        sub_amt = _amount(subtotal)
        tot_amt = _amount(total)
        CHECK_POINT("subtotal.gross.amount 为 number", isinstance(sub_amt, (int, float)), failStop=False)
        CHECK_POINT("total.gross.amount 为 number", isinstance(tot_amt, (int, float)), failStop=False)
        if isinstance(sub_amt, (int, float)):
            CHECK_POINT("subtotal >= 0", sub_amt >= 0, failStop=False)
        if isinstance(tot_amt, (int, float)):
            CHECK_POINT("total >= 0", tot_amt >= 0, failStop=False)

