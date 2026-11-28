"""Immutable process-level deployment context (single source of truth)."""

from dataclasses import dataclass
import os
import re
import threading
from typing import Optional
from urllib.parse import urlsplit

ALLOWED_PROFILES = frozenset({"sample", "product"})
_TENANT_ID_RE = re.compile(r"^[1-9]\d*$")
_MAX_INT32 = 2147483647


@dataclass(frozen=True)
class DeploymentContext:
    """Immutable deployment identity resolved once per process from environment."""

    profile: str
    tenant_id: int
    deployment_id: str


_LOCK = threading.Lock()
_CONTEXT: Optional[DeploymentContext] = None


def _parse_context_from_env() -> DeploymentContext:
    profile = os.getenv("DEPLOYMENT_PROFILE", "").strip()
    if profile not in ALLOWED_PROFILES:
        raise RuntimeError(
            "DEPLOYMENT_PROFILE is required and must be 'sample' or 'product'"
        )

    deployment_id_val = os.getenv("DEPLOYMENT_ID", "").strip()
    if (
        not deployment_id_val
        or len(deployment_id_val) > 64
        or any(ch.isspace() or ord(ch) < 32 for ch in deployment_id_val)
    ):
        raise RuntimeError(
            "DEPLOYMENT_ID is required and must be a non-empty string up to 64 characters without whitespace"
        )

    raw_tenant = os.getenv("DEPLOYMENT_TENANT_ID", "").strip()
    if not _TENANT_ID_RE.fullmatch(raw_tenant):
        raise RuntimeError(
            "DEPLOYMENT_TENANT_ID is required and must be a positive integer"
        )
    tenant_id_val = int(raw_tenant)
    if tenant_id_val < 1 or tenant_id_val > _MAX_INT32:
        raise RuntimeError("DEPLOYMENT_TENANT_ID is out of range")

    if profile == "sample" and tenant_id_val != 1:
        raise RuntimeError("DEPLOYMENT_TENANT_ID must be 1 when DEPLOYMENT_PROFILE=sample")

    return DeploymentContext(
        profile=profile,
        tenant_id=tenant_id_val,
        deployment_id=deployment_id_val,
    )


def get_deployment_context() -> DeploymentContext:
    """Return the immutable process-level DeploymentContext."""
    global _CONTEXT
    if _CONTEXT is None:
        with _LOCK:
            if _CONTEXT is None:
                _CONTEXT = _parse_context_from_env()
    return _CONTEXT


def deployment_profile() -> str:
    """Return the validated deployment profile ('sample' or 'product')."""
    return get_deployment_context().profile


def deployment_tenant_id() -> int:
    """Return the validated positive integer tenant ID."""
    return get_deployment_context().tenant_id


def deployment_id() -> str:
    """Return the validated deployment identifier."""
    return get_deployment_context().deployment_id


def parse_origin(value: str, *, allow_trailing_slash: bool = False) -> tuple[str, str, int]:
    """Parse an Origin URL into normalized (scheme, host, effective_port)."""
    raw = (value or "").strip()
    if not raw:
        raise ValueError("Origin must not be empty")
    parsed = urlsplit(raw)
    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https"):
        raise ValueError("Origin scheme must be http or https")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("Origin must not contain credentials")
    host = (parsed.hostname or "").lower()
    if not host:
        raise ValueError("Origin must contain a host")
    if parsed.query or parsed.fragment:
        raise ValueError("Origin must not contain query or fragment")
    if allow_trailing_slash:
        if parsed.path not in ("", "/"):
            raise ValueError("PUBLIC_ORIGIN must not contain a path")
    elif parsed.path != "":
        raise ValueError("Origin header must not contain a path")
    port = parsed.port  # raises ValueError if out-of-range/non-numeric
    effective_port = port if port is not None else (443 if scheme == "https" else 80)
    return (scheme, host, effective_port)
