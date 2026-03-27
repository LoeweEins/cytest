"""
Saleor 端到端流程共享步骤：channel / variant 选择、API 就绪检查。

供 checkout、full_purchase 等套件复用，避免在多个 *_cases.py 里复制粘贴。
"""

from cytest import INFO, GSTORE

from lib.saleor_api import SaleorGraphQLError, gql_request
from lib.gql_diagnose import summarize_gql_failure


def require_saleor_api_ready():
    url = getattr(GSTORE, "saleor_graphql_url", "")
    if url is None:
        url = ""
    if url == "":
        raise RuntimeError("BLOCKED: 未配置 SALEOR_GRAPHQL_URL（需要可 POST 的 /graphql/ endpoint）")

    api_callable = getattr(GSTORE, "saleor_api_callable", True)
    if api_callable is False:
        raise RuntimeError("BLOCKED: SALEOR_GRAPHQL_URL 不支持 POST GraphQL（请换成真正的 API endpoint）")


def pick_channel_slug_or_block():
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
        INFO(summarize_gql_failure(title="自动查询 channels 失败", errors=errors, raw=raw))
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


def pick_variant_id_or_block(channel_slug: str):
    """
    从 products 列表中取一个 variantId（用于 checkoutCreate.lines.variantId）。
    """
    url = GSTORE.saleor_graphql_url
    page_size = int(getattr(GSTORE, "checkout_page_size", 3))

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
        INFO(summarize_gql_failure(title="取 variantId 失败", exc=e, variables=variables))
        raise RuntimeError("BLOCKED: 无法获取 variantId（products 查询失败）")

    if errors:
        INFO(summarize_gql_failure(title="取 variantId GraphQL errors", errors=errors, raw=raw, variables=variables))
        raise RuntimeError("BLOCKED: 无法获取 variantId（GraphQL errors）")

    products = data.get("products") if isinstance(data, dict) else None
    edges = products.get("edges") if isinstance(products, dict) else None
    if not isinstance(edges, list) or len(edges) == 0:
        raise RuntimeError("BLOCKED: products 为空，环境没有可用商品（请 populatedb 或创建商品）")

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


def fetch_variant_inventory(url: str, channel_slug: str, variant_id: str):
    """
    读取 variant 的库存字段（pricing/inventory 联动断言用）。
    若 schema 不支持 productVariant 查询则返回 None。
    """
    query = """
    query VInv($id: ID!, $channel: String!) {
      productVariant(id: $id, channel: $channel) {
        id
        quantityAvailable
        trackInventory
      }
    }
    """
    variables = {"id": str(variant_id), "channel": str(channel_slug)}
    try:
        data, errors, _raw = gql_request(url, query, variables=variables, timeout_s=GSTORE.http_timeout_s)
    except SaleorGraphQLError:
        return None
    if errors:
        return None
    if not isinstance(data, dict):
        return None
    return data.get("productVariant")
