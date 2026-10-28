"""Stand of a test: the host its API calls went to.

Services of one stand share the host and differ by port
(`244.lnsk.infra.innoseti.ru:4001`, `…:18081`), so the port is dropped and the most
called host wins; a third-party service called now and then does not outvote it.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from urllib.parse import urlsplit

URL_RE = re.compile(r"https?://[A-Za-z0-9.-]+(?::\d+)?", re.IGNORECASE)


@dataclass
class Stand:
    host: str
    url: str
    name: str | None
    origins: list[dict]

    def to_dict(self) -> dict:
        return {"host": self.host, "url": self.url, "name": self.name, "origins": self.origins}


def detect_stand(urls: list[str], names: dict[str, str] | None = None) -> Stand | None:
    hosts: Counter[tuple[str, str]] = Counter()
    origins: Counter[str] = Counter()
    for url in urls:
        parts = urlsplit(url)
        if not parts.hostname:
            continue
        scheme = parts.scheme.lower() or "http"
        hosts[(scheme, parts.hostname.lower())] += 1
        origins[f"{scheme}://{parts.netloc.lower()}"] += 1
    if not hosts:
        return None
    # most_common keeps first-seen order for ties
    (scheme, host), _ = hosts.most_common(1)[0]
    return Stand(
        host=host,
        url=f"{scheme}://{host}",
        name=(names or {}).get(host),
        origins=[{"origin": origin, "count": count} for origin, count in origins.most_common()],
    )


def urls_in_text(text: str) -> list[str]:
    return URL_RE.findall(text or "")
