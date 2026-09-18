"""Turn MCP server declarations into Artifacts.

Reads the `mcpServers` map out of a Claude config. The server's *command* and
*args* are the interesting surface: an MCP server is arbitrary code the agent
is told to trust, and its tool descriptions are instructions the model obeys.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from skillguard.artifact import Artifact
from skillguard.extract.facts import compute


def _walk_servers(blob: Any, path: str = "") -> list[tuple[str, dict[str, Any]]]:
    found: list[tuple[str, dict[str, Any]]] = []
    if isinstance(blob, dict):
        servers = blob.get("mcpServers")
        if isinstance(servers, dict):
            for name, cfg in servers.items():
                if isinstance(cfg, dict):
                    found.append((f"{path}:{name}" if path else name, cfg))
        for key, value in blob.items():
            if key != "mcpServers":
                found.extend(_walk_servers(value, f"{path}/{key}" if path else str(key)))
    return found


def extract_mcp_servers(config_path: Path) -> list[Artifact]:
    try:
        blob = json.loads(config_path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return []

    artifacts: list[Artifact] = []
    for name, cfg in _walk_servers(blob):
        rendered = json.dumps(cfg, indent=2, sort_keys=True)
        env_keys = sorted((cfg.get("env") or {}).keys()) if isinstance(cfg.get("env"), dict) else []
        artifacts.append(Artifact(
            kind="mcp_server",
            identity=name,
            source=str(config_path),
            declared={k: v for k, v in cfg.items() if k != "env"},
            instructions=rendered,
            facts=compute(rendered, extra={
                "transport": cfg.get("type") or ("stdio" if cfg.get("command") else "unknown"),
                "command": cfg.get("command"),
                "arg_count": len(cfg.get("args") or []),
                "env_var_names": env_keys,
                "env_var_count": len(env_keys),
            }),
        ))
    return artifacts
