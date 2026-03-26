from cytest import STEP, INFO, CHECK_POINT, GSTORE

from lib.saleor_api import SaleorGraphQLError, gql_request
from lib.gql_diagnose import summarize_gql_failure


def _require_saleor_api_ready():
    url = getattr(GSTORE, "saleor_graphql_url", "")
    if url is None:
        url = ""
    if url == "":
        raise RuntimeError("BLOCKED: 未配置 SALEOR_GRAPHQL_URL（需要可 POST 的 /graphql/ endpoint）")

    api_callable = getattr(GSTORE, "saleor_api_callable", True)
    if api_callable is False:
        raise RuntimeError("BLOCKED: SALEOR_GRAPHQL_URL 不支持 POST GraphQL（请换成真正的 API endpoint）")


def _pick_channel_slug_or_block():
    slug = getattr(GSTORE, "saleor_channel_slug", "")
    if slug is None:
        slug = ""
    if slug != "":
        return slug

    token = getattr(GSTORE, "saleor_access_token", None)
    if not token:
        raise RuntimeError("BLOCKED: 未配置 SALEOR_CHANNEL_SLUG 且无 staff token，无法自动确定 channel")

    url = GSTORE.saleor_graphql_url
    q_channels = "query { channels { slug } }"
    data, errors, raw = gql_request(url, q_channels, token=token, timeout_s=GSTORE.http_timeout_s)
    if errors:
        INFO(summarize_gql_failure(title="CHECKOUT 自动查询 channels 失败", errors=errors, raw=raw))
        raise RuntimeError("BLOCKED: 查询 channels 失败（需要 staff/app 权限）")

    channels = data.get("channels") if data else None
    if not isinstance(channels, list) or len(channels) == 0:
        raise RuntimeError("BLOCKED: channels 为空，无法确定 channel")
    first = channels[0]
    if not isinstance(first, dict):
        raise RuntimeError("BLOCKED: channels[0] 结构异常")
    slug = first.get("slug")
    if not slug:
        raise RuntimeError("BLOCKED: channel.slug 为空")
    GSTORE.saleor_channel_slug = slug
    return slug


def _pick_variant_id_or_block(channel_slug: str):
    """
    从 products 列表中取一个 variantId（用于 checkoutCreate.lines.variantId）。
    只读查询即可，但需要 channel 参数。
    """
    url = GSTORE.saleor_graphql_url
    page_size = int(getattr(GSTORE, "checkout_page_size", 3))

    # 注意：不同 Saleor 版本 schema 里 `Product.variants` 可能不是 connection，
    # 不能传 first/edges。这里用更通用的方式：先取 products，再取变体列表（若为 list）。
    query = """
    query PickVariant($first: Int!, $channel: String!) {
      products(first: $first, channel: $channel) {
        edges {
          node {
            id
            name
            variants {
              id
              name
            }
          }
        }
      }
    }
    """
    variables = {"first": int(page_size), "channel": str(channel_slug)}

    try:
        data, errors, raw = gql_request(url, query, variables=variables, timeout_s=GSTORE.http_timeout_s)
    except SaleorGraphQLError as e:
        INFO(summarize_gql_failure(title="CHECKOUT 取 variantId 失败", exc=e, variables=variables))
        raise RuntimeError("BLOCKED: 无法获取 variantId（products 查询失败）")

    if errors:
        INFO(summarize_gql_failure(title="CHECKOUT 取 variantId GraphQL errors", errors=errors, raw=raw, variables=variables))
        raise RuntimeError("BLOCKED: 无法获取 variantId（GraphQL errors）")

    products = data.get("products") if isinstance(data, dict) else None
    edges = products.get("edges") if isinstance(products, dict) else None
    if not isinstance(edges, list) or len(edges) == 0:
        raise RuntimeError("BLOCKED: products 为空，环境没有可用商品（请 populatedb 或创建商品）")

    # 遍历找第一个有 variant 的商品
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        node = edge.get("node")
        if not isinstance(node, dict):
            continue
        variants = node.get("variants")
        if not isinstance(variants, list) or len(variants) == 0:
            continue
        v0 = variants[0] if isinstance(variants[0], dict) else None
        if isinstance(v0, dict) and v0.get("id"):
            return v0.get("id")

    raise RuntimeError("BLOCKED: 未找到任何 variant（商品无 variants 或数据不足）")


class cCHECKOUT0001:
    name = "CHECKOUT-0001-checkoutCreate（匿名创建 checkout，带 email + lines）"
    tags = ["API", "冒烟", "高风险"]

    def teststeps(self):
        _require_saleor_api_ready()

        url = GSTORE.saleor_graphql_url
        buyer_email = str(getattr(GSTORE, "checkout_email", "buyer@example.com") or "buyer@example.com")

        STEP(1, "确定 channel slug")
        channel_slug = _pick_channel_slug_or_block()
        CHECK_POINT("channel_slug 非空", bool(channel_slug))

        STEP(2, "选择一个 variantId（来自 products 列表）")
        variant_id = _pick_variant_id_or_block(channel_slug)
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

        # 真实断言：quantity 与 lines[0].quantity 一致（至少为 1）
        quantity = checkout.get("quantity")
        CHECK_POINT("checkout.quantity 为 int 且 >=1", isinstance(quantity, int) and quantity >= 1, failStop=False)

        lines = checkout.get("lines")
        CHECK_POINT("checkout.lines 为 list 且非空", isinstance(lines, list) and len(lines) > 0)
        if isinstance(lines, list) and len(lines) > 0 and isinstance(lines[0], dict):
            CHECK_POINT("第一条 line.quantity == 1", lines[0].get("quantity") == 1, failStop=False)

        # 保存到 GSTORE，供后续 checkout 查询/更新用
        GSTORE.checkout_id = checkout_id
        GSTORE.checkout_token = checkout_token


class cCHECKOUT0002:
    name = "CHECKOUT-0002-checkout 查询（按 token 校验字段契约）"
    tags = ["API", "回归"]

    def teststeps(self):
        _require_saleor_api_ready()

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

