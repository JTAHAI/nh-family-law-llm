"""Loopback-only source/wheel launcher using the actual production ASGI gateway."""
from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import socket
import sys

from .version import VERSION


def serve_desktop(*, port: int = 8000, data_root: str | None = None) -> int:
    if isinstance(port, bool) or not isinstance(port, int) or not 0 <= port <= 65535:
        print(json.dumps({"error": "invalid_loopback_port"}), file=sys.stderr)
        return 2
    try:
        import uvicorn
    except ImportError:
        print(json.dumps({"error": "api_dependencies_missing", "action": "Install nh-family-law-llm[api] in this environment."}), file=sys.stderr)
        return 3
    if data_root:
        root = Path(data_root).expanduser().absolute()
        if root.is_symlink() or (root.exists() and not root.is_dir()):
            print(json.dumps({"error": "unsafe_runtime_directory"}), file=sys.stderr)
            return 2
        root.mkdir(parents=True, exist_ok=True)
        os.environ["NH_FAMILY_LAW_DATA_ROOT"] = str(root)
        os.environ["NHFL_RUNTIME_DATA_ROOT"] = str(root)
        os.environ["NHFL_IDEMPOTENCY_STATE_ROOT"] = str(root / "replay-state")
        os.environ["NHFL_AUTHORITY_DATA_ROOT"] = str(root / "authority-data")
        os.environ["NHFL_RUNTIME_LOG_DIR"] = str(root / "logs")
    instance_id = secrets.token_hex(32)
    os.environ["NHFL_LOCAL_API_INSTANCE_ID"] = instance_id
    # Keep ownership of the bound socket across startup. No free-port race and
    # no broad network bind can be requested via this CLI.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        if os.name == "nt" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            listener.bind(("127.0.0.1", port))
            listener.listen(128)
        except OSError:
            print(json.dumps({"error": "loopback_bind_failed", "port": port}), file=sys.stderr)
            return 4
        selected_port = listener.getsockname()[1]
        print(json.dumps({
            "event": "nhfl_starting", "version": VERSION,
            "url": f"http://127.0.0.1:{selected_port}/nh-review",
            "port": selected_port, "pid": os.getpid(), "instance_id": instance_id,
            "healthy": False, "review_required": True,
        }), flush=True)
        config = uvicorn.Config(
            "app.api.production:app", host="127.0.0.1", port=selected_port,
            access_log=False, log_config=None, log_level="warning",
        )
        server = uvicorn.Server(config)
        server.run(sockets=[listener])
        return 0 if server.started else 5
