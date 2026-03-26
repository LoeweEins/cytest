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
        INFO(summarize_gql_failure(title="INVENTORY 自动查询 channels 失败", errors=errors, raw=raw))
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


class cINVENTORY0001:
    name = "INVENTORY-0001-productVariants(channel) 库存字段契约（quantityAvailable/trackInventory）"
    tags = ["API", "回归"]

    def teststeps(self):
        _require_saleor_api_ready()
        url = GSTORE.saleor_graphql_url
        channel = _pick_channel_slug_or_block()
        page_size = int(getattr(GSTORE, "inventory_page_size", 5))

        STEP(1, "调用 productVariants(first, channel) 并校验库存字段存在")
        query = """
        query Variants($first: Int!, $channel: String!) {
          productVariants(first: $first, channel: $channel) {
            totalCount
            edges {
              node {
                id
                sku
                trackInventory
                quantityAvailable
              }
            }
          }
        }
        """
        variables = {"first": page_size, "channel": str(channel)}

        try:
            data, errors, raw = gql_request(url, query, variables=variables, timeout_s=GSTORE.http_timeout_s)
        except SaleorGraphQLError as e:
            INFO(summarize_gql_failure(title="INVENTORY-0001 productVariants 失败", exc=e, variables=variables))
            CHECK_POINT("productVariants 请求应成功返回", False)
            return

        CHECK_POINT("GraphQL errors 为空", errors == [], failStop=False)
        if errors:
            INFO(summarize_gql_failure(title="INVENTORY-0001 GraphQL errors 非空", errors=errors, raw=raw, variables=variables))

        conn = data.get("productVariants") if isinstance(data, dict) else None
        CHECK_POINT("data.productVariants 存在", isinstance(conn, dict))
        if not isinstance(conn, dict):
            return

        edges = conn.get("edges")
        CHECK_POINT("edges 为 list", isinstance(edges, list))
        if not isinstance(edges, list) or len(edges) == 0:
            INFO("variant 列表为空：环境可能没有商品变体")
            CHECK_POINT("至少存在 1 个 variant（建议 populatedb）", False, failStop=False)
            return

        first_edge = edges[0] if isinstance(edges[0], dict) else None
        node = first_edge.get("node") if isinstance(first_edge, dict) else None
        CHECK_POINT("node 为 dict", isinstance(node, dict))
        if isinstance(node, dict):
            CHECK_POINT("variant.id 非空", bool(node.get("id")), failStop=False)
            CHECK_POINT("trackInventory 为 bool", isinstance(node.get("trackInventory"), bool), failStop=False)
            CHECK_POINT("quantityAvailable 为 int", isinstance(node.get("quantityAvailable"), int), failStop=False)
            if isinstance(node.get("quantityAvailable"), int):
                CHECK_POINT("quantityAvailable >= 0", node.get("quantityAvailable") >= 0, failStop=False)

