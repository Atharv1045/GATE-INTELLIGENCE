"""
Security utilities:
- Password hashing using Argon2id (via argon2-cffi when installed, with cryptographic PBKDF2-HMAC-SHA256 fallback).
- JWT token creation & verification (via PyJWT when installed, or RFC 7519 HMAC-SHA256 implementation).
- PDF file validation (MIME, %PDF- magic bytes, file size limit, active script / Launch action inspection).
- Prompt injection sanitizer for untrusted PDF text before sending to LLMs.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import time
from typing import Any, Dict, Optional, Tuple

from app.core.config import settings

try:
    from argon2 import PasswordHasher
    from argon2.exceptions import VerifyMismatchError

    _ARGON2_HASHER = PasswordHasher(
        time_cost=2, memory_cost=65536, parallelism=2, hash_len=32, salt_len=16
    )
except ImportError:
    _ARGON2_HASHER = None

try:
    import jwt as _pyjwt
except ImportError:
    _pyjwt = None


def hash_password(password: str) -> str:
    """Hash a password using Argon2id if available, or PBKDF2-HMAC-SHA256."""
    if _ARGON2_HASHER is not None:
        return _ARGON2_HASHER.hash(password)
    salt = secrets.token_hex(16)
    iterations = 260000
    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations
    )
    return f"pbkdf2_sha256${iterations}${salt}${dk.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against an Argon2id or PBKDF2 hash."""
    if hashed_password.startswith("$argon2"):
        if _ARGON2_HASHER is None:
            return False
        try:
            return _ARGON2_HASHER.verify(hashed_password, plain_password)
        except Exception:
            return False
    if hashed_password.startswith("pbkdf2_sha256$"):
        try:
            _, iter_str, salt, hex_digest = hashed_password.split("$", 3)
            dk = hashlib.pbkdf2_hmac(
                "sha256",
                plain_password.encode("utf-8"),
                salt.encode("utf-8"),
                int(iter_str),
            )
            return hmac.compare_digest(dk.hex(), hex_digest)
        except Exception:
            return False
    return False


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(segment: str) -> bytes:
    pad = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + pad)


def create_access_token(
    subject: str, extra_claims: Optional[Dict[str, Any]] = None, expires_minutes: Optional[int] = None
) -> str:
    now = int(time.time())
    exp_seconds = (expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES) * 60
    payload: Dict[str, Any] = {
        "sub": str(subject),
        "iat": now,
        "exp": now + exp_seconds,
    }
    if extra_claims:
        payload.update(extra_claims)

    if _pyjwt is not None:
        return _pyjwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

    header = {"alg": "HS256", "typ": "JWT"}
    h_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    p_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{h_b64}.{p_b64}".encode("ascii")
    sig = hmac.new(
        settings.SECRET_KEY.encode("utf-8"), signing_input, hashlib.sha256
    ).digest()
    return f"{h_b64}.{p_b64}.{_b64url_encode(sig)}"


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    if _pyjwt is not None:
        try:
            return _pyjwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        except Exception:
            return None

    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        h_b64, p_b64, s_b64 = parts
        signing_input = f"{h_b64}.{p_b64}".encode("ascii")
        expected_sig = hmac.new(
            settings.SECRET_KEY.encode("utf-8"), signing_input, hashlib.sha256
        ).digest()
        actual_sig = _b64url_decode(s_b64)
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None
        payload = json.loads(_b64url_decode(p_b64).decode("utf-8"))
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        return payload
    except Exception:
        return None


def validate_pdf_upload(
    file_bytes: bytes, filename: str, content_type: Optional[str] = None
) -> Tuple[bool, str, str]:
    """
    Validate uploaded PDF bytes:
    - Filename extension check (.pdf)
    - MIME check if provided
    - Size limit check (MAX_UPLOAD_SIZE_MB)
    - Magic bytes signature (%PDF-)
    - Malicious embedded action check (/JavaScript, /JS, /Launch)
    Returns (is_valid, message, sha256_checksum).
    """
    if not filename or not filename.lower().endswith(".pdf"):
        return False, "Uploaded file must have a .pdf extension.", ""

    if content_type and content_type not in (
        "application/pdf",
        "application/x-pdf",
        "application/octet-stream",
    ):
        return False, f"Unsupported MIME type: {content_type}. Expected application/pdf.", ""

    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(file_bytes) == 0:
        return False, "Uploaded PDF file is empty.", ""
    if len(file_bytes) > max_bytes:
        return (
            False,
            f"PDF exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB} MB.",
            "",
        )

    if not file_bytes[:1024].lstrip().startswith(b"%PDF-"):
        return False, "Invalid PDF file signature: missing %PDF- header.", ""

    # Inspect raw bytes for dangerous embedded actions
    dangerous_markers = [b"/JavaScript", b"/Launch", b"/RichMedia", b"/EmbeddedFiles"]
    for marker in dangerous_markers:
        if marker in file_bytes:
            return (
                False,
                f"Security policy violation: PDF contains disallowed active content ({marker.decode('ascii')}).",
                "",
            )

    checksum = hashlib.sha256(file_bytes).hexdigest()
    return True, "Valid PDF document.", checksum


PROMPT_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions", re.I),
    re.compile(r"system\s*prompt", re.I),
    re.compile(r"you\s+are\s+now\s+(a|an)\s+", re.I),
    re.compile(r"<\s*/?\s*system\s*>", re.I),
    re.compile(r"do\s+not\s+follow\s+the\s+rules", re.I),
    re.compile(r"reveal\s+your\s+(api\s+key|secret|instructions)", re.I),
]


def sanitize_untrusted_pdf_text(text: str) -> Tuple[str, bool]:
    """
    Neutralize prompt-injection attempts embedded inside untrusted PDFs before passing to LLM agents.
    Returns (sanitized_text, injection_detected).
    """
    if not text:
        return "", False
    detected = False
    cleaned = text
    for pattern in PROMPT_INJECTION_PATTERNS:
        if pattern.search(cleaned):
            detected = True
            cleaned = pattern.sub("[REDACTED_UNTRUSTED_INSTRUCTION]", cleaned)
    return cleaned, detected
