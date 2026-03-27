import json
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Tuple

import pytest


def _request_json(
    base_url: str,
    method: str,
    path: str,
    *,
    timeout_s: int,
    payload: Optional[Dict[str, Any]] = None,
) -> Tuple[int, Any, str]:
    url = f"{base_url}{path}"
    headers = {
        "Accept": "application/json",
        "User-Agent": "pytest-open-api-basic",
    }
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json; charset=utf-8"
        data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            status = int(getattr(resp, "status", 200))
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        status = int(getattr(e, "code", 0) or 0)
        raw = e.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as e:
        pytest.fail(f"Network error calling {url}: {e}")

    try:
        return status, json.loads(raw), raw
    except Exception:
        return status, None, raw


def _assert_has_keys(obj: Any, keys):
    assert isinstance(obj, dict), f"body 应为 dict，实际={type(obj)}"
    for k in keys:
        assert k in obj, f"缺少字段 {k}"


# === 对应 cases/open_api_basic/api_cases.py：100 条 GET by id 字段契约 ===
POST_KEYS = ("userId", "id", "title", "body")
COMMENT_KEYS = ("postId", "id", "name", "email", "body")
ALBUM_KEYS = ("userId", "id", "title")
PHOTO_KEYS = ("albumId", "id", "title", "url", "thumbnailUrl")
TODO_KEYS = ("userId", "id", "title", "completed")
USER_KEYS = ("id", "name", "username", "email")


_GET_BY_ID_CASES = []
_GET_BY_ID_CASES += [(f"/posts/{i}", POST_KEYS) for i in range(1, 21)]
_GET_BY_ID_CASES += [(f"/comments/{i}", COMMENT_KEYS) for i in range(1, 21)]
_GET_BY_ID_CASES += [(f"/albums/{i}", ALBUM_KEYS) for i in range(1, 21)]
_GET_BY_ID_CASES += [(f"/photos/{i}", PHOTO_KEYS) for i in range(1, 21)]
_GET_BY_ID_CASES += [(f"/users/{i}", USER_KEYS) for i in range(1, 11)]
_GET_BY_ID_CASES += [(f"/todos/{i}", TODO_KEYS) for i in range(1, 11)]


@pytest.mark.parametrize("path,keys", _GET_BY_ID_CASES, ids=[p for p, _ in _GET_BY_ID_CASES])
def test_get_by_id_contract(open_api_base_url, open_api_timeout_s, path, keys):
    status, data, raw = _request_json(open_api_base_url, "GET", path, timeout_s=open_api_timeout_s)
    assert status == 200, f"HTTP {status}, body={raw[:200]}"
    assert data is not None, f"响应非 JSON: {raw[:200]}"
    _assert_has_keys(data, keys)


# === 对应 cases/open_api_basic/rest_routes_cases.py：Routes 用例 ===


def test_get_posts_list(open_api_base_url, open_api_timeout_s):
    status, data, raw = _request_json(open_api_base_url, "GET", "/posts", timeout_s=open_api_timeout_s)
    assert status == 200, f"HTTP {status}, body={raw[:200]}"
    assert isinstance(data, list), f"body 应为 list，实际={type(data)}"
    if data:
        assert isinstance(data[0], dict), "posts[0] 应为 dict"
        assert "id" in data[0]
        assert "title" in data[0]


def test_get_post_comments_nested(open_api_base_url, open_api_timeout_s):
    status, data, raw = _request_json(open_api_base_url, "GET", "/posts/1/comments", timeout_s=open_api_timeout_s)
    assert status == 200, f"HTTP {status}, body={raw[:200]}"
    assert isinstance(data, list), f"body 应为 list，实际={type(data)}"
    if data and isinstance(data[0], dict):
        assert "postId" in data[0]
        assert "email" in data[0]


def test_get_comments_filter_by_postid(open_api_base_url, open_api_timeout_s):
    status, data, raw = _request_json(open_api_base_url, "GET", "/comments?postId=1", timeout_s=open_api_timeout_s)
    assert status == 200, f"HTTP {status}, body={raw[:200]}"
    assert isinstance(data, list), f"body 应为 list，实际={type(data)}"
    if data and isinstance(data[0], dict):
        assert data[0].get("postId") == 1


def test_post_posts_create(open_api_base_url, open_api_timeout_s):
    payload = {"title": "foo", "body": "bar", "userId": 1}
    status, data, raw = _request_json(open_api_base_url, "POST", "/posts", timeout_s=open_api_timeout_s, payload=payload)
    assert status == 201, f"HTTP {status}, body={raw[:200]}"
    assert isinstance(data, dict), f"body 应为 dict，实际={type(data)}"
    # JSONPlaceholder 通常会回显字段并给出 id
    for k in ("title", "body", "userId"):
        assert k in data
    assert "id" in data


def test_put_posts_update(open_api_base_url, open_api_timeout_s):
    payload = {"id": 1, "title": "foo", "body": "bar", "userId": 1}
    status, data, raw = _request_json(open_api_base_url, "PUT", "/posts/1", timeout_s=open_api_timeout_s, payload=payload)
    assert status == 200, f"HTTP {status}, body={raw[:200]}"
    assert isinstance(data, dict), f"body 应为 dict，实际={type(data)}"
    assert data.get("id") == 1
    assert "title" in data


def test_patch_posts_partial_update(open_api_base_url, open_api_timeout_s):
    payload = {"title": "patched-title"}
    status, data, raw = _request_json(open_api_base_url, "PATCH", "/posts/1", timeout_s=open_api_timeout_s, payload=payload)
    assert status == 200, f"HTTP {status}, body={raw[:200]}"
    assert isinstance(data, dict), f"body 应为 dict，实际={type(data)}"
    assert "title" in data


def test_delete_posts(open_api_base_url, open_api_timeout_s):
    status, data, raw = _request_json(open_api_base_url, "DELETE", "/posts/1", timeout_s=open_api_timeout_s)
    assert status == 200, f"HTTP {status}, body={raw[:200]}"
    # 文档示例返回 {}，但做宽松兼容
    assert isinstance(data, dict) or raw.strip() in ("", "{}")

