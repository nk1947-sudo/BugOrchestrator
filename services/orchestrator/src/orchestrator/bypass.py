"""Access-control / WAF bypass technique builder.

These are standard broken-access-control test techniques (see OWASP's
testing guide) for checking whether a restriction is enforced only at one
layer - e.g. an IP allowlist enforced by a reverse proxy but not by the
origin app. They are not a general detection-evasion feature: every variant
this module produces is turned into a PlannedAction with
`category=waf_bypass`, which docs/ARCHITECTURE.md and orchestrator.loop both
route through the same human-approval gate as any other high-impact action.
Nothing here executes on its own.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BypassVariant:
    technique: str
    description: str
    method: str
    path: str
    extra_headers: dict[str, str] = field(default_factory=dict)


def _mutate_path(path: str) -> str:
    """Insert a double slash before the final path segment. Deliberately not
    a `./` dot-segment insertion - RFC 3986 dot-segment removal happens
    client-side in httpx (and most conforming HTTP libraries) before the
    request ever reaches the wire, so that mutation would silently collapse
    back to the original path and test nothing. A doubled slash is not a
    dot-segment, so it survives unnormalized through a standard client while
    still being a real class of WAF/rule-matching bypass (some proxies
    normalize `//`, the origin app may not, or vice versa)."""
    trimmed = path.rstrip("/")
    if "/" not in trimmed.strip("/"):
        return path
    head, _, tail = trimmed.rpartition("/")
    return f"{head}//{tail}"


def build_bypass_variants(method: str, path: str) -> list[BypassVariant]:
    """Only called when a baseline request to `path` came back 403 - see
    orchestrator.loop. Capped to three well-understood techniques rather than
    an open-ended payload list, per the "zero noise" principle."""
    return [
        BypassVariant(
            technique="origin_header_spoof",
            description=(
                "Spoof X-Forwarded-For/X-Originating-IP/Client-IP to 127.0.0.1 - tests "
                "whether an IP allowlist is enforced by a proxy/WAF in front of the origin "
                "rather than by the origin itself."
            ),
            method=method,
            path=path,
            extra_headers={
                "X-Forwarded-For": "127.0.0.1",
                "X-Originating-IP": "127.0.0.1",
                "Client-IP": "127.0.0.1",
            },
        ),
        BypassVariant(
            technique="path_segment_mutation",
            description=(
                "Insert a harmless `./` path segment before the final component - tests "
                "whether an access-control rule matches the literal path string instead of "
                "the normalized route."
            ),
            method=method,
            path=_mutate_path(path),
        ),
        BypassVariant(
            technique="method_override",
            description=(
                "Resend as POST with X-HTTP-Method-Override set to the original method - "
                "tests whether an access-control rule keys off the literal HTTP method only."
            ),
            method="POST",
            path=path,
            extra_headers={"X-HTTP-Method-Override": method},
        ),
    ]
