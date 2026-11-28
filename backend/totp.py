"""RFC 6238 TOTP (stdlib only) for SumaiBoard G1-01.

Secrets are base32. Verification returns the matched time step so callers can
atomically consume it (spec section 4.2: strictly-greater step consumption).
"""
import base64
import hashlib
import hmac
import secrets as _secrets
import struct
import time


def generate_secret() -> str:
    return base64.b32encode(_secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _decode_secret(secret_b32: str) -> bytes:
    s = "".join(secret_b32.split()).upper()
    pad = "=" * ((8 - len(s) % 8) % 8)
    return base64.b32decode(s + pad)


def hotp(secret_b32: str, counter: int, digits: int = 6) -> str:
    key = _decode_secret(secret_b32)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % (10 ** digits)
    return str(code).zfill(digits)


def totp_at(secret_b32: str, timestamp: float, step: int = 30, digits: int = 6) -> str:
    return hotp(secret_b32, int(timestamp // step), digits)


def verify(secret_b32: str, code: str, timestamp: float = None, window: int = 1,
           step: int = 30, digits: int = 6):
    """Return the matched step counter, or None. Window is +/- `window` steps."""
    if timestamp is None:
        timestamp = time.time()
    code = "".join(str(code).split())
    if not code.isdigit() or len(code) != digits:
        return None
    current = int(timestamp // step)
    for delta in range(-window, window + 1):
        candidate = current + delta
        if hmac.compare_digest(hotp(secret_b32, candidate, digits), code):
            return candidate
    return None


def otpauth_uri(secret_b32: str, account: str, issuer: str) -> str:
    from urllib.parse import quote
    label = quote(f"{issuer}:{account}", safe="")
    return (f"otpauth://totp/{label}?secret={secret_b32}"
            f"&issuer={quote(issuer, safe='')}&algorithm=SHA1&digits=6&period=30")
