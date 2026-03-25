import json
import os
import time
import urllib.request
import urllib.error
from typing import Optional, Tuple, Dict, Any


class SaleorGraphQLError(RuntimeError):
    pass


def _now_ms():
    return int(time.time() * 1000)


def get_saleor_graphql_url(default: str = "") -> str:
    """
    Saleor 的 GraphQL API URL，建议用环境变量覆盖。

    - SALEOR_GRAPHQL_URL: 例如 https://<your-saleor-domain>/graphql/

    注意：某些“storefront demo”地址看起来像 /graphql/，但可能并不是可 POST 的 API endpoint。
    """
    url = os.getenv("SALEOR_GRAPHQL_URL", "").strip()
    if url:
        return url
    return default


def gql_request(
    url: str,
    query: str,
    variables: Optional[Dict[str, Any]] = None,
    token: Optional[str] = None,
    timeout_s: int = 20,
    extra_headers: Optional[Dict[str, str]] = None,
):
    """
    发送一次 GraphQL 请求，返回 (data, errors, raw_response_json)。

    - errors: GraphQL errors 数组（可能 HTTP 200 也会有）
    """
    if not url:
        raise ValueError("Saleor GraphQL url is empty. Set SALEOR_GRAPHQL_URL.")

    payload = {"query": query, "variables": variables or {}}
    body = json.dumps(payload).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "cytest-saleor-client",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if extra_headers:
        headers.update(extra_headers)

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            resp_body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        resp_body = e.read().decode("utf-8", errors="replace")
        raise SaleorGraphQLError(f"HTTP {e.code} calling GraphQL. Body: {resp_body[:5000]}")
    except urllib.error.URLError as e:
        raise SaleorGraphQLError(f"Network error calling GraphQL: {e}")

    try:
        raw = json.loads(resp_body)
    except Exception as e:
        raise SaleorGraphQLError(f"Invalid JSON response: {e}. Body: {resp_body[:2000]}")

    return raw.get("data"), raw.get("errors") or [], raw


def token_create(url: str, email: str, password: str, timeout_s: int = 20):
    """
    对应 Saleor 文档：tokenCreate(email, password)。
    返回：tokenCreate 节点（包含 token/refreshToken/errors/user 等）。

    文档参考：
    - https://docs.saleor.io/api-reference/authentication/mutations/token-create
    """
    query = """
    mutation TokenCreate($email: String!, $password: String!) {
      tokenCreate(email: $email, password: $password) {
        token
        refreshToken
        errors {
          field
          message
          code
        }
        user {
          id
          email
          isStaff
        }
      }
    }
    """
    data, errors, raw = gql_request(
        url,
        query,
        variables={"email": email, "password": password},
        timeout_s=timeout_s,
    )
    if errors:
        raise SaleorGraphQLError(f"GraphQL errors: {errors}")
    return (data or {}).get("tokenCreate"), raw


def token_verify(url: str, token: str, timeout_s: int = 20):
    """
    对应 Saleor 文档：tokenVerify(token)。
    文档参考：
    - https://docs.saleor.io/api-reference/authentication/mutations/token-verify
    """
    query = """
    mutation TokenVerify($token: String!) {
      tokenVerify(token: $token) {
        isValid
        errors {
          field
          message
          code
        }
      }
    }
    """
    data, errors, raw = gql_request(url, query, variables={"token": token}, timeout_s=timeout_s)
    if errors:
        raise SaleorGraphQLError(f"GraphQL errors: {errors}")
    return (data or {}).get("tokenVerify"), raw


def token_refresh(url: str, refresh_token: str, timeout_s: int = 20):
    """
    对应 Saleor 文档：tokenRefresh(refreshToken)。
    文档参考：
    - https://docs.saleor.io/api-reference/authentication/mutations/token-refresh
    """
    query = """
    mutation TokenRefresh($refreshToken: String!) {
      tokenRefresh(refreshToken: $refreshToken) {
        token
        errors {
          field
          message
          code
        }
      }
    }
    """
    data, errors, raw = gql_request(url, query, variables={"refreshToken": refresh_token}, timeout_s=timeout_s)
    if errors:
        raise SaleorGraphQLError(f"GraphQL errors: {errors}")
    return (data or {}).get("tokenRefresh"), raw


def me(url: str, token: str, timeout_s: int = 20):
    """
    对应 Saleor 文档：me 查询（验证 token 并返回当前用户）。
    文档参考：
    - https://docs.saleor.io/api-reference/users/queries/me
    """
    query = """
    query Me {
      me {
        id
        email
        isStaff
      }
    }
    """
    data, errors, raw = gql_request(url, query, variables={}, token=token, timeout_s=timeout_s)
    return (data or {}).get("me"), errors, raw

