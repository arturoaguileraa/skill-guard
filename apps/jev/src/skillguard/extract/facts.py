"""Deterministic signal extraction.

Everything Jev is documented to be bad at -- counting, comparing numbers,
matching literals -- happens here, in code. The model never sees a question
like "how many URLs are there?"; it sees the list and is asked what it means.
"""

from __future__ import annotations

import re
from typing import Any

URL_RE = re.compile(r"https?://[^\s\)\"'<>\]]+", re.I)
BASE64_BLOB_RE = re.compile(r"[A-Za-z0-9+/]{120,}={0,2}")
HEX_BLOB_RE = re.compile(r"(?:\\x[0-9a-f]{2}){24,}", re.I)

# Paths whose mere mention is worth surfacing to the model as a named fact.
SENSITIVE_PATHS = [
    "~/.ssh", ".ssh/id_", "~/.aws", ".aws/credentials", "~/.config/gcloud",
    ".npmrc", ".pypirc", ".netrc", ".git-credentials", "id_rsa", "id_ed25519",
    ".env", "keychain", "Login Data", "Local Storage", "cookies.sqlite",
    "~/.claude/", ".claude.json", "settings.local.json", "wallet.dat",
]

# Word-boundary matched: bare substrings turn "since" into a netcat hit and
# make the fact sheet useless as evidence.
EXFIL_VERBS = [
    r"\bcurl\b", r"\bwget\b", r"\bfetch\s*\(", r"requests\.(?:post|get)",
    r"\burllib\b", r"\bhttpx\b", r"\baxios\b", r"\bnc\b\s+-", r"\bnetcat\b",
    r"\bscp\b", r"base64\s+-d", r"\bxxd\s+-r\b", r"\bopenssl\s+enc\b",
]

# Phrasings that try to move the agent off its own rails. Presence is a fact;
# whether it is *malicious* is Jev's call, not the regex's.
OVERRIDE_PHRASES = [
    "ignore previous", "ignore all previous", "disregard the above",
    "do not tell the user", "without telling the user", "without asking",
    "do not mention", "silently", "no confirmation", "skip confirmation",
    "bypass the", "override the system prompt", "you are now", "developer mode",
    "this has been audited", "this is safe", "pre-approved", "trusted source",
]

TRUSTED_HOSTS = {
    "github.com", "raw.githubusercontent.com", "docs.anthropic.com",
    "anthropic.com", "claude.com", "npmjs.com", "pypi.org", "developer.mozilla.org",
}


def _hits(text: str, needles: list[str]) -> list[str]:
    low = text.lower()
    return sorted({n for n in needles if n.lower() in low})


def _re_hits(text: str, patterns: list[str]) -> list[str]:
    return sorted({p for p in patterns if re.search(p, text, re.I)})


def compute(text: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """Reduce raw artifact text to a compact, named fact sheet."""
    urls = URL_RE.findall(text)
    hosts = sorted({u.split("/")[2].lower() for u in urls if "/" in u[8:]})
    untrusted = [h for h in hosts if not any(h == t or h.endswith("." + t) for t in TRUSTED_HOSTS)]

    facts: dict[str, Any] = {
        "url_count": len(urls),
        "hosts": hosts[:25],
        "hosts_outside_common_allowlist": untrusted[:25],
        "sensitive_path_mentions": _hits(text, SENSITIVE_PATHS),
        "network_or_encoding_verbs": _re_hits(text, EXFIL_VERBS),
        "instruction_override_phrases": _hits(text, OVERRIDE_PHRASES),
        "long_base64_blobs": len(BASE64_BLOB_RE.findall(text)),
        "hex_escape_runs": len(HEX_BLOB_RE.findall(text)),
        "char_count": len(text),
    }
    if extra:
        facts.update(extra)
    return facts
