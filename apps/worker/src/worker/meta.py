"""Cheap, deterministic metadata for an artifact: what the skill calls itself
(SKILL.md frontmatter) and where it lives (GitHub blob URL). Pure text parsing —
nothing here is fed to Jev, and nothing here trusts the content."""

from __future__ import annotations

import re

_FRONTMATTER = re.compile(r"\A﻿?---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.S)
_GITHUB_BLOB = re.compile(r"^https://github\.com/([^/]+/[^/]+)/blob/[^/]+/(.+)$")


def _clean(value: str, limit: int) -> str | None:
    value = value.strip().strip("\"'").strip()
    return value[:limit] or None


# Paths that hold a repo's own tests/fixtures, not skills a user would install
# (e.g. a malware scanner's samples). Ingesting them would present test malware
# as a real publisher's skill.
_TEST_PATH = re.compile(r"(^|/)(tests?|__tests__|fixtures?|testdata|test_data)/", re.I)


def is_test_path(path: str | None) -> bool:
    return bool(path and _TEST_PATH.search(path))


def parse_frontmatter(content: str) -> tuple[str | None, str | None]:
    """Return (name, description) from a leading `---` YAML block, if any."""
    m = _FRONTMATTER.match(content)
    if not m:
        return None, None
    fields: dict[str, str] = {}
    lines = m.group(1).splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        key, sep, rest = line.partition(":")
        i += 1
        if not sep or line[:1] in (" ", "\t", "#") or not key.strip():
            continue
        rest = rest.strip()
        if rest in (">", "|", ">-", "|-"):  # block scalar: gather indented lines
            block = []
            while i < len(lines) and (lines[i][:1] in (" ", "\t") or not lines[i].strip()):
                block.append(lines[i].strip())
                i += 1
            rest = " ".join(b for b in block if b)
        fields[key.strip().lower()] = rest
    return _clean(fields.get("name", ""), 256), _clean(fields.get("description", ""), 500)


def parse_github_url(url: str | None) -> tuple[str | None, str | None]:
    """Return (owner/repo, path) from a github.com blob URL."""
    m = _GITHUB_BLOB.match(url or "")
    return (m.group(1), m.group(2)) if m else (None, None)
