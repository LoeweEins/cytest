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
    """
    在多 channel 环境下，collections/products 等查询需要指定 channel。
    优先级：
    1) GSTORE.saleor_channel_slug（或环境变量 SALEOR_CHANNEL_SLUG）
    2) 若存在 staff token，则通过 channels 查询自动取第一个 slug
    """
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
    data, errors, _raw = gql_request(url, q_channels, token=token, timeout_s=GSTORE.http_timeout_s)
    if errors:
        raise RuntimeError(f"BLOCKED: 查询 channels 失败（需要 staff/app 权限）：{errors[0].get('message') if isinstance(errors, list) and errors else errors}")

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


class cCATALOG0001:
    name = "CATALOG-0001-匿名查询 Shop（基础可用性）"
    tags = ["API", "冒烟"]

    def teststeps(self):
        _require_saleor_api_ready()

        STEP(1, "查询 shop { name, description }")
        url = GSTORE.saleor_graphql_url
        query = "query { shop { name description } }"

        try:
            data, errors, _raw = gql_request(url, query, timeout_s=GSTORE.http_timeout_s)
        except SaleorGraphQLError as e:
            INFO(
                summarize_gql_failure(
                    title="CATALOG-0001 shop 查询失败",
                    exc=e,
                )
            )
            CHECK_POINT("GraphQL 请求应成功返回", False)
            return

        CHECK_POINT("GraphQL errors 为空", errors == [], failStop=False)
        if errors:
            INFO(
                summarize_gql_failure(
                    title="CATALOG-0001 GraphQL errors 非空",
                    errors=errors,
                    raw=_raw,
                )
            )

        shop = None
        if data is not None:
            shop = data.get("shop")
        CHECK_POINT("data.shop 存在", isinstance(shop, dict))
        if isinstance(shop, dict):
            shop_name = shop.get("name")
        else:
            shop_name = None
        CHECK_POINT("shop.name 非空", bool(shop_name))


class cCATALOG0002:
    name = "CATALOG-0002-查询一级类目 categories(level=0)"
    tags = ["API", "回归"]

    def teststeps(self):
        _require_saleor_api_ready()

        STEP(1, "查询 categories(level=0, first=N) 的 edges/node")
        url = GSTORE.saleor_graphql_url
        page_size = getattr(GSTORE, "catalog_page_size", 5)

        query = """
        query Categories($first: Int!, $level: Int!) {
          categories(first: $first, level: $level) {
            totalCount
            edges {
              node { id name slug level }
            }
          }
        }
        """

        try:
            data, errors, _raw = gql_request(
                url,
                query,
                variables={"first": int(page_size), "level": 0},
                timeout_s=GSTORE.http_timeout_s,
            )
        except SaleorGraphQLError as e:
            INFO(
                summarize_gql_failure(
                    title="CATALOG-0002 categories 查询失败",
                    exc=e,
                    variables={"first": int(page_size), "level": 0},
                )
            )
            CHECK_POINT("categories 查询应成功返回", False)
            return

        CHECK_POINT("GraphQL errors 为空", errors == [], failStop=False)
        if errors:
            INFO(
                summarize_gql_failure(
                    title="CATALOG-0002 GraphQL errors 非空",
                    errors=errors,
                    raw=_raw,
                    variables={"first": int(page_size), "level": 0},
                )
            )

        conn = None
        if data is not None:
            conn = data.get("categories")
        CHECK_POINT("data.categories 存在", isinstance(conn, dict))
        if not isinstance(conn, dict):
            return

        total = conn.get("totalCount")
        edges = conn.get("edges")
        CHECK_POINT("totalCount 为 int 且 >= 0", isinstance(total, int) and total >= 0, failStop=False)
        CHECK_POINT("edges 为 list", isinstance(edges, list))
        if not isinstance(edges, list) or len(edges) == 0:
            INFO("一级类目为空：该环境可能未初始化样例数据（可接受，但会影响后续目录用例）")
            CHECK_POINT("至少存在 1 个一级类目（建议 populatedb 后应成立）", False, failStop=False)
            return

        first_node = edges[0].get("node") if isinstance(edges[0], dict) else None
        CHECK_POINT("首个 node 为 dict", isinstance(first_node, dict))
        if isinstance(first_node, dict):
            CHECK_POINT("node.id 非空", bool(first_node.get("id")), failStop=False)
            CHECK_POINT("node.name 非空", bool(first_node.get("name")), failStop=False)
            CHECK_POINT("node.slug 非空", bool(first_node.get("slug")), failStop=False)
            CHECK_POINT("node.level == 0", first_node.get("level") == 0, failStop=False)


class cCATALOG0003:
    name = "CATALOG-0003-查询集合 collections(first=N)"
    tags = ["API", "回归"]

    def teststeps(self):
        _require_saleor_api_ready()

        STEP(1, "查询 collections 的 totalCount/edges/node")
        url = GSTORE.saleor_graphql_url
        page_size = getattr(GSTORE, "catalog_page_size", 5)
        channel_slug = _pick_channel_slug_or_block()

        query = """
        query Collections($first: Int!, $channel: String!) {
          collections(first: $first, channel: $channel) {
            totalCount
            edges {
              node { id name slug }
            }
          }
        }
        """

        try:
            data, errors, _raw = gql_request(
                url,
                query,
                variables={"first": int(page_size), "channel": str(channel_slug)},
                timeout_s=GSTORE.http_timeout_s,
            )
        except SaleorGraphQLError as e:
            INFO(
                summarize_gql_failure(
                    title="CATALOG-0003 collections 查询失败",
                    exc=e,
                    variables={"first": int(page_size), "channel": str(channel_slug)},
                )
            )
            CHECK_POINT("collections 查询应成功返回", False)
            return

        CHECK_POINT("GraphQL errors 为空", errors == [], failStop=False)
        if errors:
            INFO(
                summarize_gql_failure(
                    title="CATALOG-0003 GraphQL errors 非空",
                    errors=errors,
                    raw=_raw,
                    variables={"first": int(page_size), "channel": str(channel_slug)},
                )
            )

        conn = None
        if data is not None:
            conn = data.get("collections")
        CHECK_POINT("data.collections 存在", isinstance(conn, dict))
        if not isinstance(conn, dict):
            return

        total = conn.get("totalCount")
        edges = conn.get("edges")
        CHECK_POINT("totalCount 为 int 且 >= 0", isinstance(total, int) and total >= 0, failStop=False)
        CHECK_POINT("edges 为 list", isinstance(edges, list))
        if isinstance(edges, list) and len(edges) > 0:
            node = edges[0].get("node") if isinstance(edges[0], dict) else None
            CHECK_POINT("首个 collection node 为 dict", isinstance(node, dict))
            if isinstance(node, dict):
                CHECK_POINT("collection.id 非空", bool(node.get("id")), failStop=False)
                CHECK_POINT("collection.name 非空", bool(node.get("name")), failStop=False)
                CHECK_POINT("collection.slug 非空", bool(node.get("slug")), failStop=False)


class cCATALOG0004:
    name = "CATALOG-0004-查询 channel 列表并用第一个 channel 查询 products(first=N, channel=slug)"
    tags = ["API", "回归", "高风险"]

    def teststeps(self):
        _require_saleor_api_ready()

        url = GSTORE.saleor_graphql_url
        page_size = getattr(GSTORE, "catalog_page_size", 5)

        STEP(1, "确定 channel slug（优先配置，其次通过 staff token 自动查询 channels）")
        channel_slug = _pick_channel_slug_or_block()
        CHECK_POINT("channel_slug 非空", bool(channel_slug))

        STEP(2, f"用 channel={channel_slug} 查询 products(first={page_size})")
        q_products = """
        query Products($first: Int!, $channel: String!) {
          products(first: $first, channel: $channel) {
            totalCount
            edges {
              node {
                id
                name
                slug
              }
            }
          }
        }
        """
        try:
            data2, errors2, _raw2 = gql_request(
                url,
                q_products,
                variables={"first": int(page_size), "channel": str(channel_slug)},
                timeout_s=GSTORE.http_timeout_s,
            )
        except SaleorGraphQLError as e:
            INFO(
                summarize_gql_failure(
                    title="CATALOG-0004 products 查询失败",
                    exc=e,
                    variables={"first": int(page_size), "channel": str(channel_slug)},
                )
            )
            CHECK_POINT("products 查询应成功返回", False)
            return

        CHECK_POINT("GraphQL errors 为空（products）", errors2 == [], failStop=False)
        if errors2:
            INFO(
                summarize_gql_failure(
                    title="CATALOG-0004 GraphQL errors 非空（products）",
                    errors=errors2,
                    raw=_raw2,
                    variables={"first": int(page_size), "channel": str(channel_slug)},
                )
            )

        conn = None
        if data2 is not None:
            conn = data2.get("products")
        CHECK_POINT("data.products 存在", isinstance(conn, dict))
        if not isinstance(conn, dict):
            return

        edges = conn.get("edges")
        CHECK_POINT("products.edges 为 list", isinstance(edges, list))
        if isinstance(edges, list) and len(edges) > 0:
            node = edges[0].get("node") if isinstance(edges[0], dict) else None
            CHECK_POINT("首个 product node 为 dict", isinstance(node, dict))
            if isinstance(node, dict):
                CHECK_POINT("product.id 非空", bool(node.get("id")), failStop=False)
                CHECK_POINT("product.name 非空", bool(node.get("name")), failStop=False)
                CHECK_POINT("product.slug 非空", bool(node.get("slug")), failStop=False)

