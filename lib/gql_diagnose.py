from __future__ import annotations

from typing import Any, Dict, Iterable, Optional


_SENSITIVE_KEYS = {
    "password",
    "token",
    "refreshToken",
    "refresh_token",
    "accessToken",
    "access_token",
    "authorization",
}


def _redact(value: Any, *, key_hint: Optional[str] = None) -> Any:
    if key_hint and key_hint in _SENSITIVE_KEYS:
        return "<redacted>"
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        for k, v in value.items():
            out[k] = _redact(v, key_hint=str(k))
        return out
    if isinstance(value, list):
        return [_redact(v) for v in value[:10]] + (["<...>"] if len(value) > 10 else [])
    if isinstance(value, str) and len(value) > 500:
        return value[:500] + "<...>"
    return value


def _iter_errors(errors: Any) -> Iterable[dict]:
    if not errors:
        return []
    if isinstance(errors, list):
        for e in errors:
            if isinstance(e, dict):
                yield e
        return
    if isinstance(errors, dict):
        yield errors


def summarize_gql_failure(
    *,
    title: str,
    errors: Any = None,
    raw: Any = None,
    exc: Optional[BaseException] = None,
    variables: Optional[Dict[str, Any]] = None,
) -> str:
    """
    把 GraphQL 失败信息压缩成一行可读摘要，供 INFO() 输出。
    - 不依赖外部 AI；先用规则化归因，后续可替换为真正的 LLM 生成。
    """
    parts = [f"[{title}]"]

    if exc is not None:
        msg = str(exc)
        if len(msg) > 800:
            msg = msg[:800] + "<...>"
        parts.append(f"异常={msg}")

    errs = list(_iter_errors(errors))
    if errs:
        e0 = errs[0]
        msg = e0.get("message")
        path = e0.get("path")
        ext = e0.get("extensions") if isinstance(e0.get("extensions"), dict) else {}
        code = ext.get("code") or e0.get("code")

        if msg:
            parts.append(f"错误={msg}")
        if code:
            parts.append(f"code={code}")
        if path:
            parts.append(f"path={path}")
        if len(errs) > 1:
            parts.append(f"更多错误={len(errs) - 1}条")

        msg_l = str(msg).lower() if msg is not None else ""
        reason = None
        if "permission" in msg_l or "not authorized" in msg_l or "unauthorized" in msg_l:
            reason = "可能原因=权限不足/未鉴权（token 缺失或角色不够）"
        elif "channel" in msg_l:
            reason = "可能原因=channel 参数缺失/无权限访问该 channel"
        elif "not found" in msg_l:
            reason = "可能原因=资源不存在/测试数据未初始化"
        elif "invalid" in msg_l:
            reason = "可能原因=参数非法/环境配置不匹配"
        if reason:
            parts.append(reason)

    if variables:
        parts.append(f"variables={_redact(variables)}")

    if isinstance(raw, dict):
        raw_errors = raw.get("errors")
        if raw_errors and not errs:
            parts.append("raw.errors 存在（但未传入 errors 参数）")
        if raw.get("data") is None and raw_errors:
            parts.append("raw.data=None")

    return " | ".join(parts)

