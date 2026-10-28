"""Hides credentials in logs and request dumps before they leave for Jira."""

from __future__ import annotations

import re

MASK = "***"
SENSITIVE_KEYS = (
    "password",
    "passwd",
    "pwd",
    "secret",
    "client_secret",
    "token",
    "access_token",
    "refresh_token",
    "id_token",
    "api_key",
    "apikey",
    "x-api-key",
    "authorization",
    "cookie",
    "set-cookie",
)

# `Authorization: Bearer x` header lines: the whole value goes, scheme included
HEADER_RE = re.compile(
    r"^(\s*(?:[\w-]*authorization|cookie|set-cookie|x-api-key|x-auth-token)\s*:\s*)\S.*$",
    re.IGNORECASE | re.MULTILINE,
)
BEARER_RE = re.compile(r"\b(Bearer|Basic|Token)\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE)
JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}")


class SecretMasker:
    def __init__(self, extra_keys: tuple[str, ...] = ()):
        keys = sorted({key.lower() for key in SENSITIVE_KEYS + extra_keys}, key=len, reverse=True)
        names = "|".join(re.escape(key) for key in keys)
        # `"password": "x"`, `'token': 'x'`, `password=x`, `Authorization: x` (header line)
        self._pair_re = re.compile(
            rf"""(?<![\w-])(["']?)({names})\1(\s*[:=]\s*)("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|[^\s,;&}}\]]+)""",
            re.IGNORECASE,
        )

    def _mask_pair(self, match: re.Match) -> str:
        quote, key, separator, value = match.groups()
        if value[:1] in {'"', "'"}:
            masked = f"{value[0]}{MASK}{value[0]}"
        else:
            masked = MASK
        return f"{quote}{key}{quote}{separator}{masked}"

    def mask(self, text: str) -> str:
        text = HEADER_RE.sub(lambda m: m.group(1) + MASK, text)
        text = BEARER_RE.sub(lambda m: f"{m.group(1)} {MASK}", text)
        text = JWT_RE.sub(MASK, text)
        return self._pair_re.sub(self._mask_pair, text)
