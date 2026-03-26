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
    Search 相关查询在多 channel 环境下通常需要 channel 参数。
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
        INFO(
            summarize_gql_failure(
                title="SEARCH 自动查询 channels 失败",
                errors=errors,
                raw=raw,
            )
        )
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


class cSEARCH0001:
    name = "SEARCH-0001-产品搜索 products(filter.search=QUERY)"
    tags = ["API", "回归"]

    def teststeps(self):
        _require_saleor_api_ready()

        url = GSTORE.saleor_graphql_url
        page_size = int(getattr(GSTORE, "search_page_size", 5))
        query_str = str(getattr(GSTORE, "search_query", "a") or "a")

        STEP(1, "确定 channel slug")
        channel_slug = _pick_channel_slug_or_block()
        CHECK_POINT("channel_slug 非空", bool(channel_slug))

        STEP(2, f"按关键字搜索 products：query={query_str!r}, first={page_size}")
        query = """
        query ProductsSearch($first: Int!, $channel: String!, $q: String!) {
          products(first: $first, channel: $channel, filter: { search: $q }) {
            totalCount
            pageInfo { hasNextPage endCursor }
            edges {
              cursor
              node { id name slug }
            }
          }
        }
        """
        variables = {"first": int(page_size), "channel": str(channel_slug), "q": query_str}

        try:
            data, errors, raw = gql_request(url, query, variables=variables, timeout_s=GSTORE.http_timeout_s)
        except SaleorGraphQLError as e:
            INFO(summarize_gql_failure(title="SEARCH-0001 products 搜索失败", exc=e, variables=variables))
            CHECK_POINT("products 搜索请求应成功返回", False)
            return

        CHECK_POINT("GraphQL errors 为空", errors == [], failStop=False)
        if errors:
            INFO(summarize_gql_failure(title="SEARCH-0001 GraphQL errors 非空", errors=errors, raw=raw, variables=variables))

        conn = (data or {}).get("products") if isinstance(data, dict) else None
        CHECK_POINT("data.products 存在", isinstance(conn, dict))
        if not isinstance(conn, dict):
            return

        CHECK_POINT("products.totalCount 为 int 且 >= 0", isinstance(conn.get("totalCount"), int) and conn.get("totalCount") >= 0, failStop=False)
        page_info = conn.get("pageInfo")
        CHECK_POINT("products.pageInfo 为 dict", isinstance(page_info, dict), failStop=False)
        if isinstance(page_info, dict):
            CHECK_POINT("pageInfo.hasNextPage 为 bool", isinstance(page_info.get("hasNextPage"), bool), failStop=False)

        edges = conn.get("edges")
        CHECK_POINT("products.edges 为 list", isinstance(edges, list))
        if not isinstance(edges, list) or len(edges) == 0:
            INFO("搜索结果为空：可能是环境数据不足或关键字未命中（不阻塞结构断言）")
            CHECK_POINT("建议：搜索应至少命中 1 条（若环境有样例数据）", False, failStop=False)
            return

        first_edge = edges[0] if isinstance(edges[0], dict) else None
        node = first_edge.get("node") if isinstance(first_edge, dict) else None
        CHECK_POINT("首个 edge.node 为 dict", isinstance(node, dict))
        if isinstance(node, dict):
            CHECK_POINT("product.id 非空", bool(node.get("id")), failStop=False)
            CHECK_POINT("product.name 非空", bool(node.get("name")), failStop=False)
            CHECK_POINT("product.slug 非空", bool(node.get("slug")), failStop=False)


class cSEARCH0002:
    name = "SEARCH-0002-产品列表排序字段存在（products.edges.node.id/name/slug）"
    tags = ["API", "冒烟"]

    def teststeps(self):
        _require_saleor_api_ready()

        url = GSTORE.saleor_graphql_url
        page_size = int(getattr(GSTORE, "search_page_size", 5))

        STEP(1, "确定 channel slug")
        channel_slug = _pick_channel_slug_or_block()
        CHECK_POINT("channel_slug 非空", bool(channel_slug))

        STEP(2, "不带 filter，取 products 结构字段（用于字段契约检查）")
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
            INFO(summarize_gql_failure(title="SEARCH-0002 products 列表失败", exc=e, variables=variables))
            CHECK_POINT("products 列表请求应成功返回", False)
            return

        CHECK_POINT("GraphQL errors 为空", errors == [], failStop=False)
        if errors:
            INFO(summarize_gql_failure(title="SEARCH-0002 GraphQL errors 非空", errors=errors, raw=raw, variables=variables))

        conn = (data or {}).get("products") if isinstance(data, dict) else None
        CHECK_POINT("data.products 存在", isinstance(conn, dict))
        if not isinstance(conn, dict):
            return

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

