from cytest import STEP, INFO, CHECK_POINT, GSTORE

from lib.saleor_api import SaleorGraphQLError, gql_request
from lib.gql_diagnose import summarize_gql_failure


def _require_saleor_api_ready():
    url = getattr(GSTORE, "saleor_graphql_url", "") or ""
    if url == "":
        raise RuntimeError("BLOCKED: 未配置 SALEOR_GRAPHQL_URL（需要可 POST 的 /graphql/ endpoint）")

    api_callable = getattr(GSTORE, "saleor_api_callable", True)
    if api_callable is False:
        raise RuntimeError("BLOCKED: SALEOR_GRAPHQL_URL 不支持 POST GraphQL（请换成真正的 API endpoint）")


def _pick_channel_slug_or_block():
    """
    Product 相关查询在多 channel 环境下通常需要 channel 参数。
    优先级：
    1) GSTORE.saleor_channel_slug（或环境变量 SALEOR_CHANNEL_SLUG）
    2) 若存在 staff token，则通过 channels 查询自动取第一个 slug
    """
    slug = getattr(GSTORE, "saleor_channel_slug", "") or ""
    if slug:
        return slug

    token = getattr(GSTORE, "saleor_access_token", None)
    if not token:
        raise RuntimeError("BLOCKED: 未配置 SALEOR_CHANNEL_SLUG 且无 staff token，无法自动确定 channel")

    url = GSTORE.saleor_graphql_url
    q_channels = "query { channels { slug } }"
    data, errors, raw = gql_request(url, q_channels, token=token, timeout_s=GSTORE.http_timeout_s)
    if errors:
        INFO(summarize_gql_failure(title="PRODUCT 自动查询 channels 失败", errors=errors, raw=raw))
        raise RuntimeError("BLOCKED: 查询 channels 失败（需要 staff/app 权限）")

    channels = (data or {}).get("channels")
    if not isinstance(channels, list) or len(channels) == 0:
        raise RuntimeError("BLOCKED: channels 为空，无法确定 channel")
    first = channels[0] if isinstance(channels[0], dict) else None
    slug = first.get("slug") if isinstance(first, dict) else None
    if not slug:
        raise RuntimeError("BLOCKED: channel.slug 为空")
    GSTORE.saleor_channel_slug = slug
    return slug


def _pick_one_product_or_soft_fail(*, url: str, channel: str, page_size: int):
    query = """
    query ProductsPickOne($first: Int!, $channel: String!) {
      products(first: $first, channel: $channel) {
        edges {
          node { id slug name }
        }
      }
    }
    """
    variables = {"first": int(page_size), "channel": str(channel)}
    try:
        data, errors, raw = gql_request(url, query, variables=variables, timeout_s=GSTORE.http_timeout_s)
    except SaleorGraphQLError as e:
        INFO(summarize_gql_failure(title="PRODUCT 拉取 products 列表失败", exc=e, variables=variables))
        CHECK_POINT("products 列表请求应成功返回", False)
        return None

    CHECK_POINT("GraphQL errors 为空（pick one product）", errors == [], failStop=False)
    if errors:
        INFO(summarize_gql_failure(title="PRODUCT products 列表 errors 非空", errors=errors, raw=raw, variables=variables))

    conn = (data or {}).get("products") if isinstance(data, dict) else None
    edges = conn.get("edges") if isinstance(conn, dict) else None
    CHECK_POINT("products.edges 为 list", isinstance(edges, list))
    if not isinstance(edges, list) or len(edges) == 0:
        INFO("环境无商品数据：无法进行 product 详情字段断言（不判定为框架失败）")
        CHECK_POINT("建议：环境至少存在 1 个商品（populatedb 后应成立）", False, failStop=False)
        return None

    first_edge = edges[0] if isinstance(edges[0], dict) else None
    node = first_edge.get("node") if isinstance(first_edge, dict) else None
    CHECK_POINT("首个 product node 为 dict", isinstance(node, dict))
    if not isinstance(node, dict):
        return None
    return node


class cPRODUCT0001:
    name = "PRODUCT-0001-product(id, channel) 详情字段契约"
    tags = ["API", "回归"]

    def teststeps(self):
        _require_saleor_api_ready()

        url = GSTORE.saleor_graphql_url
        page_size = int(getattr(GSTORE, "product_page_size", 5))

        STEP(1, "确定 channel slug")
        channel_slug = _pick_channel_slug_or_block()
        CHECK_POINT("channel_slug 非空", bool(channel_slug))

        STEP(2, "从 products 列表挑一个 product（用于后续详情查询）")
        picked = _pick_one_product_or_soft_fail(url=url, channel=channel_slug, page_size=page_size)
        if not isinstance(picked, dict):
            return
        product_id = picked.get("id")
        product_slug = picked.get("slug")
        CHECK_POINT("picked.id 非空", bool(product_id))
        CHECK_POINT("picked.slug 非空", bool(product_slug), failStop=False)

        STEP(3, "用 product(id, channel) 查询详情并断言明确返回字段")
        query = """
        query ProductById($id: ID!, $channel: String!) {
          product(id: $id, channel: $channel) {
            id
            name
            slug
            description
            seoTitle
            seoDescription
            isAvailable
            category { id name slug }
            productType { id name hasVariants }
            media { url alt }
            attributes {
              attribute { id name slug }
              values { id name slug }
            }
            variants {
              id
              name
              sku
            }
          }
        }
        """
        variables = {"id": str(product_id), "channel": str(channel_slug)}

        try:
            data, errors, raw = gql_request(url, query, variables=variables, timeout_s=GSTORE.http_timeout_s)
        except SaleorGraphQLError as e:
            INFO(summarize_gql_failure(title="PRODUCT-0001 product(id) 查询失败", exc=e, variables=variables))
            CHECK_POINT("product(id) 查询应成功返回", False)
            return

        CHECK_POINT("GraphQL errors 为空（product）", errors == [], failStop=False)
        if errors:
            INFO(summarize_gql_failure(title="PRODUCT-0001 GraphQL errors 非空（product）", errors=errors, raw=raw, variables=variables))

        product = (data or {}).get("product") if isinstance(data, dict) else None
        CHECK_POINT("data.product 存在", isinstance(product, dict))
        if not isinstance(product, dict):
            return

        CHECK_POINT("product.id 非空", bool(product.get("id")), failStop=False)
        CHECK_POINT("product.name 非空", bool(product.get("name")), failStop=False)
        CHECK_POINT("product.slug 非空", bool(product.get("slug")), failStop=False)

        category = product.get("category")
        CHECK_POINT("product.category 为 dict", isinstance(category, dict), failStop=False)
        if isinstance(category, dict):
            CHECK_POINT("category.id 非空", bool(category.get("id")), failStop=False)
            CHECK_POINT("category.name 非空", bool(category.get("name")), failStop=False)
            CHECK_POINT("category.slug 非空", bool(category.get("slug")), failStop=False)

        ptype = product.get("productType")
        CHECK_POINT("product.productType 为 dict", isinstance(ptype, dict), failStop=False)
        if isinstance(ptype, dict):
            CHECK_POINT("productType.id 非空", bool(ptype.get("id")), failStop=False)
            CHECK_POINT("productType.name 非空", bool(ptype.get("name")), failStop=False)
            CHECK_POINT("productType.hasVariants 为 bool", isinstance(ptype.get("hasVariants"), bool), failStop=False)

        media = product.get("media")
        CHECK_POINT("product.media 为 list", isinstance(media, list), failStop=False)
        if isinstance(media, list) and len(media) > 0 and isinstance(media[0], dict):
            CHECK_POINT("media[0].url 非空", bool(media[0].get("url")), failStop=False)

        attrs = product.get("attributes")
        CHECK_POINT("product.attributes 为 list", isinstance(attrs, list), failStop=False)
        if isinstance(attrs, list) and len(attrs) > 0 and isinstance(attrs[0], dict):
            a0 = attrs[0].get("attribute")
            CHECK_POINT("attributes[0].attribute 为 dict", isinstance(a0, dict), failStop=False)

        variants = product.get("variants")
        CHECK_POINT("product.variants 为 list", isinstance(variants, list), failStop=False)
        if isinstance(variants, list) and len(variants) > 0 and isinstance(variants[0], dict):
            v0 = variants[0]
            CHECK_POINT("variant.id 非空", bool(v0.get("id")), failStop=False)
            CHECK_POINT("variant.name 非空", bool(v0.get("name")), failStop=False)
            CHECK_POINT("variant.sku 字段存在", "sku" in v0, failStop=False)


class cPRODUCT0002:
    name = "PRODUCT-0002-products 列表字段契约（edges.node.id/name/slug）"
    tags = ["API", "冒烟"]

    def teststeps(self):
        _require_saleor_api_ready()

        url = GSTORE.saleor_graphql_url
        page_size = int(getattr(GSTORE, "product_page_size", 5))

        STEP(1, "确定 channel slug")
        channel_slug = _pick_channel_slug_or_block()
        CHECK_POINT("channel_slug 非空", bool(channel_slug))

        STEP(2, "products(first, channel) 返回字段契约检查")
        query = """
        query ProductsContract($first: Int!, $channel: String!) {
          products(first: $first, channel: $channel) {
            totalCount
            edges {
              node { id name slug }
            }
          }
        }
        """
        variables = {"first": int(page_size), "channel": str(channel_slug)}

        try:
            data, errors, raw = gql_request(url, query, variables=variables, timeout_s=GSTORE.http_timeout_s)
        except SaleorGraphQLError as e:
            INFO(summarize_gql_failure(title="PRODUCT-0002 products 列表失败", exc=e, variables=variables))
            CHECK_POINT("products 列表请求应成功返回", False)
            return

        CHECK_POINT("GraphQL errors 为空", errors == [], failStop=False)
        if errors:
            INFO(summarize_gql_failure(title="PRODUCT-0002 GraphQL errors 非空", errors=errors, raw=raw, variables=variables))

        conn = (data or {}).get("products") if isinstance(data, dict) else None
        CHECK_POINT("data.products 存在", isinstance(conn, dict))
        if not isinstance(conn, dict):
            return

        CHECK_POINT("products.totalCount 为 int 且 >= 0", isinstance(conn.get("totalCount"), int) and conn.get("totalCount") >= 0, failStop=False)
        edges = conn.get("edges")
        CHECK_POINT("products.edges 为 list", isinstance(edges, list))
        if isinstance(edges, list) and len(edges) > 0:
            first_edge = edges[0] if isinstance(edges[0], dict) else None
            node = first_edge.get("node") if isinstance(first_edge, dict) else None
            CHECK_POINT("首个 product node 为 dict", isinstance(node, dict))
            if isinstance(node, dict):
                CHECK_POINT("product.id 非空", bool(node.get("id")), failStop=False)
                CHECK_POINT("product.name 非空", bool(node.get("name")), failStop=False)
                CHECK_POINT("product.slug 非空", bool(node.get("slug")), failStop=False)

