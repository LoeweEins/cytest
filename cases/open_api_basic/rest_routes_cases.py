import json
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Tuple

from cytest import STEP, INFO, CHECK_POINT, GSTORE


def _base_url() -> str:
    base = getattr(GSTORE, "open_api_base_url", "") or ""
    if base == "":
        raise RuntimeError("BLOCKED: 未配置 OPEN_API_BASE_URL 且 suite_setup 未执行")
    return base


def _timeout_s() -> int:
    return int(getattr(GSTORE, "open_api_timeout_s", 20))


def _request_json(method: str, path: str, *, payload: Optional[Dict[str, Any]] = None) -> Tuple[int, Any, str]:
    url = f"{_base_url()}{path}"
    headers = {
        "Accept": "application/json",
        "User-Agent": "cytest-open-api-basic",
    }
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json; charset=utf-8"
        data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=_timeout_s()) as resp:
            status = int(getattr(resp, "status", 200))
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        status = int(getattr(e, "code", 0) or 0)
        raw = e.read().decode("utf-8", errors="replace")
        try:
            return status, json.loads(raw), raw
        except Exception:
            return status, None, raw
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error calling {url}: {e}")

    try:
        return status, json.loads(raw), raw
    except Exception:
        return status, None, raw


def _assert_is_list(data: Any, title: str):
    CHECK_POINT(f"{title} 为 list", isinstance(data, list))


def _assert_is_dict(data: Any, title: str):
    CHECK_POINT(f"{title} 为 dict", isinstance(data, dict))


class cOPENAPI0101:
    name = "OPENAPI-0101-GET /posts（列表）"
    tags = ["API", "JSONPlaceholder", "routes"]

    def teststeps(self):
        STEP(1, "请求 posts 列表")
        status, data, raw = _request_json("GET", "/posts")
        CHECK_POINT("HTTP 状态码应为 200", status == 200)
        if status != 200:
            INFO(f"响应体(截断)={raw[:500]}")
            return
        _assert_is_list(data, "body")
        if isinstance(data, list) and len(data) > 0:
            first = data[0] if isinstance(data[0], dict) else None
            CHECK_POINT("posts[0] 为 dict", isinstance(first, dict))
            if isinstance(first, dict):
                CHECK_POINT("posts[0].id 字段存在", "id" in first, failStop=False)
                CHECK_POINT("posts[0].title 字段存在", "title" in first, failStop=False)


class cOPENAPI0102:
    name = "OPENAPI-0102-GET /posts/1/comments（嵌套资源）"
    tags = ["API", "JSONPlaceholder", "routes"]

    def teststeps(self):
        STEP(1, "请求 posts/1/comments")
        status, data, raw = _request_json("GET", "/posts/1/comments")
        CHECK_POINT("HTTP 状态码应为 200", status == 200)
        if status != 200:
            INFO(f"响应体(截断)={raw[:500]}")
            return
        _assert_is_list(data, "body")
        if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
            CHECK_POINT("comments[0].postId 字段存在", "postId" in data[0], failStop=False)
            CHECK_POINT("comments[0].email 字段存在", "email" in data[0], failStop=False)


class cOPENAPI0103:
    name = "OPENAPI-0103-GET /comments?postId=1（查询参数）"
    tags = ["API", "JSONPlaceholder", "routes"]

    def teststeps(self):
        STEP(1, "请求 comments?postId=1")
        status, data, raw = _request_json("GET", "/comments?postId=1")
        CHECK_POINT("HTTP 状态码应为 200", status == 200)
        if status != 200:
            INFO(f"响应体(截断)={raw[:500]}")
            return
        _assert_is_list(data, "body")
        if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
            CHECK_POINT("comments[0].postId == 1（建议）", data[0].get("postId") == 1, failStop=False)


class cOPENAPI0104:
    name = "OPENAPI-0104-POST /posts（创建资源）"
    tags = ["API", "JSONPlaceholder", "routes", "高风险"]

    def teststeps(self):
        STEP(1, "创建 post")
        payload = {"title": "foo", "body": "bar", "userId": 1}
        status, data, raw = _request_json("POST", "/posts", payload=payload)
        CHECK_POINT("HTTP 状态码应为 201", status == 201)
        if status != 201:
            INFO(f"响应体(截断)={raw[:500]}")
            return
        _assert_is_dict(data, "body")
        if isinstance(data, dict):
            CHECK_POINT("返回 id 字段存在", "id" in data, failStop=False)
            CHECK_POINT("返回 title 字段存在", "title" in data, failStop=False)
            CHECK_POINT("返回 body 字段存在", "body" in data, failStop=False)
            CHECK_POINT("返回 userId 字段存在", "userId" in data, failStop=False)


class cOPENAPI0105:
    name = "OPENAPI-0105-PUT /posts/1（整体更新）"
    tags = ["API", "JSONPlaceholder", "routes", "高风险"]

    def teststeps(self):
        STEP(1, "PUT 更新 post 1")
        payload = {"id": 1, "title": "foo", "body": "bar", "userId": 1}
        status, data, raw = _request_json("PUT", "/posts/1", payload=payload)
        CHECK_POINT("HTTP 状态码应为 200", status == 200)
        if status != 200:
            INFO(f"响应体(截断)={raw[:500]}")
            return
        _assert_is_dict(data, "body")
        if isinstance(data, dict):
            CHECK_POINT("返回 id==1（建议）", data.get("id") == 1, failStop=False)
            CHECK_POINT("返回 title 字段存在", "title" in data, failStop=False)


class cOPENAPI0106:
    name = "OPENAPI-0106-PATCH /posts/1（部分更新）"
    tags = ["API", "JSONPlaceholder", "routes", "高风险"]

    def teststeps(self):
        STEP(1, "PATCH 更新 post 1 title")
        payload = {"title": "patched-title"}
        status, data, raw = _request_json("PATCH", "/posts/1", payload=payload)
        CHECK_POINT("HTTP 状态码应为 200", status == 200)
        if status != 200:
            INFO(f"响应体(截断)={raw[:500]}")
            return
        _assert_is_dict(data, "body")
        if isinstance(data, dict):
            CHECK_POINT("返回 title 字段存在", "title" in data, failStop=False)


class cOPENAPI0107:
    name = "OPENAPI-0107-DELETE /posts/1（删除）"
    tags = ["API", "JSONPlaceholder", "routes", "高风险"]

    def teststeps(self):
        STEP(1, "DELETE 删除 post 1")
        status, data, raw = _request_json("DELETE", "/posts/1")
        CHECK_POINT("HTTP 状态码应为 200", status == 200)
        if status != 200:
            INFO(f"响应体(截断)={raw[:500]}")
            return
        # 文档示例里返回 {}（实现可能不同，但一般是空对象）
        CHECK_POINT("响应为 dict 或空", isinstance(data, dict) or raw.strip() in ("", "{}"), failStop=False)

