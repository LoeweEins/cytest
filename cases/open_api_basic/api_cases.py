import json
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional, Tuple

from cytest import STEP, INFO, CHECK_POINT, GSTORE


def _require_base_url():
    base = getattr(GSTORE, "open_api_base_url", "") or ""
    if base == "":
        raise RuntimeError("BLOCKED: 未配置 OPEN_API_BASE_URL 且 suite_setup 未执行")
    return base


def _timeout_s() -> int:
    return int(getattr(GSTORE, "open_api_timeout_s", 20))


def _http_get_json(url: str, *, timeout_s: int) -> Tuple[int, Any, str]:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "cytest-open-api-basic",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            status = int(getattr(resp, "status", 200))
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        status = int(getattr(e, "code", 0) or 0)
        body = e.read().decode("utf-8", errors="replace")
        return status, None, body
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error calling {url}: {e}")

    try:
        return status, json.loads(body), body
    except Exception:
        return status, None, body


def _assert_object_has_keys(obj: Any, *, keys: List[str], title: str):
    CHECK_POINT(f"{title} 为 dict", isinstance(obj, dict))
    if not isinstance(obj, dict):
        return
    for k in keys:
        CHECK_POINT(f"{title}.{k} 字段存在", k in obj, failStop=False)


def _make_get_by_id_case(
    *,
    case_id: str,
    name: str,
    tags: List[str],
    path: str,
    expected_keys: List[str],
):
    class_name = f"cOPENAPI{case_id}"

    def teststeps(self):
        base = _require_base_url()
        url = f"{base}{path}"
        timeout = _timeout_s()

        STEP(1, f"GET {path}")
        status, data, raw = _http_get_json(url, timeout_s=timeout)

        CHECK_POINT("HTTP 状态码应为 200", status == 200)
        if status != 200:
            INFO(f"响应体(截断)={raw[:500]}")
            return

        CHECK_POINT("响应应为合法 JSON", data is not None)
        if data is None:
            INFO(f"响应体(截断)={raw[:500]}")
            return

        _assert_object_has_keys(data, keys=expected_keys, title="body")

    return type(
        class_name,
        (),
        {
            "name": name,
            "tags": tags,
            "teststeps": teststeps,
            "__module__": __name__,
        },
    )


def _register_cases():
    # JSONPlaceholder 字段契约（相对稳定）
    POST_KEYS = ["userId", "id", "title", "body"]
    COMMENT_KEYS = ["postId", "id", "name", "email", "body"]
    ALBUM_KEYS = ["userId", "id", "title"]
    PHOTO_KEYS = ["albumId", "id", "title", "url", "thumbnailUrl"]
    TODO_KEYS = ["userId", "id", "title", "completed"]
    USER_KEYS = ["id", "name", "username", "email"]

    cases: List[type] = []

    # 1-20: posts
    for i in range(1, 21):
        cases.append(
            _make_get_by_id_case(
                case_id=f"{i:04d}",
                name=f"OPENAPI-{i:04d}-GET /posts/{i} 返回字段契约",
                tags=["API", "JSONPlaceholder", "posts"],
                path=f"/posts/{i}",
                expected_keys=POST_KEYS,
            )
        )

    # 21-40: comments
    for idx, i in enumerate(range(1, 21), start=21):
        cases.append(
            _make_get_by_id_case(
                case_id=f"{idx:04d}",
                name=f"OPENAPI-{idx:04d}-GET /comments/{i} 返回字段契约",
                tags=["API", "JSONPlaceholder", "comments"],
                path=f"/comments/{i}",
                expected_keys=COMMENT_KEYS,
            )
        )

    # 41-60: albums
    for idx, i in enumerate(range(1, 21), start=41):
        cases.append(
            _make_get_by_id_case(
                case_id=f"{idx:04d}",
                name=f"OPENAPI-{idx:04d}-GET /albums/{i} 返回字段契约",
                tags=["API", "JSONPlaceholder", "albums"],
                path=f"/albums/{i}",
                expected_keys=ALBUM_KEYS,
            )
        )

    # 61-80: photos
    for idx, i in enumerate(range(1, 21), start=61):
        cases.append(
            _make_get_by_id_case(
                case_id=f"{idx:04d}",
                name=f"OPENAPI-{idx:04d}-GET /photos/{i} 返回字段契约",
                tags=["API", "JSONPlaceholder", "photos"],
                path=f"/photos/{i}",
                expected_keys=PHOTO_KEYS,
            )
        )

    # 81-90: users
    for idx, i in enumerate(range(1, 11), start=81):
        cases.append(
            _make_get_by_id_case(
                case_id=f"{idx:04d}",
                name=f"OPENAPI-{idx:04d}-GET /users/{i} 返回字段契约",
                tags=["API", "JSONPlaceholder", "users"],
                path=f"/users/{i}",
                expected_keys=USER_KEYS,
            )
        )

    # 91-100: todos
    for idx, i in enumerate(range(1, 11), start=91):
        cases.append(
            _make_get_by_id_case(
                case_id=f"{idx:04d}",
                name=f"OPENAPI-{idx:04d}-GET /todos/{i} 返回字段契约",
                tags=["API", "JSONPlaceholder", "todos"],
                path=f"/todos/{i}",
                expected_keys=TODO_KEYS,
            )
        )

    # 注册到模块全局命名空间，供 Collector 扫描
    g = globals()
    for cls in cases:
        g[cls.__name__] = cls


_register_cases()

