"""Cognito HTTP API group and username helpers."""
import re
from typing import Any

from .responses import error


def _claims(event: dict[str, Any]) -> dict[str, Any]:
    context = event.get("requestContext") or {}
    authorizer = context.get("authorizer") or {}
    jwt = authorizer.get("jwt") or {}
    return jwt.get("claims") or {}


def require_group(event: dict[str, Any], group: str) -> dict[str, Any] | None:
    """Return a 403 proxy response unless the JWT contains the requested group."""
    if not group or not re.fullmatch(r"[a-zA-Z0-9_-]+", group):
        raise ValueError("group must be a simple Cognito group name")
    groups = _claims(event).get("cognito:groups", "")
    if isinstance(groups, (list, tuple, set)):
        allowed = group in groups
    else:
        allowed = re.search(rf"\b{re.escape(group)}\b", str(groups)) is not None
    if not allowed:
        return error(403, "forbidden", "You are not authorized to access this resource.")
    return None


def get_username(event: dict[str, Any]) -> str:
    """Return the Cognito username, falling back to the stable subject claim."""
    claims = _claims(event)
    return str(claims.get("cognito:username") or claims.get("username") or claims.get("sub") or "unknown")
