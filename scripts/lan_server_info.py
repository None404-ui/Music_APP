#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
from pathlib import Path


def _detect_ip(interface: str) -> str:
    try:
        out = subprocess.check_output(
            ["ipconfig", "getifaddr", interface],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        if out:
            return out
    except Exception:
        pass
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        return ip
    except Exception:
        return "127.0.0.1"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Печатает данные для подключения клиента к LAN серверу."
    )
    parser.add_argument("--interface", default="en0", help="Сетевой интерфейс для определения IP")
    parser.add_argument("--hub-port", type=int, default=8765, help="Порт LAN Audio Hub")
    parser.add_argument("--backend-port", type=int, default=8000, help="Порт Django backend")
    parser.add_argument(
        "--workspace",
        default=str(Path(__file__).resolve().parents[1]),
        help="Корень проекта musicAPP",
    )
    args = parser.parse_args()

    ip = _detect_ip(args.interface)
    workspace = Path(args.workspace).resolve()
    payload = {
        "server_ip": ip,
        "hub_url": f"http://{ip}:{args.hub_port}",
        "backend_url": f"http://{ip}:{args.backend_port}",
        "django_allowed_hosts": f"{ip},127.0.0.1,localhost",
        "workspace": str(workspace),
        "server_commands": {
            "hub": [
                f'cd "{workspace}"',
                "pip install -r lan_audio_hub/requirements-lan.txt",
                "python -m lan_audio_hub",
            ],
            "backend": [
                f'cd "{workspace / "backend"}"',
                f'export CRATES_LAN_HUB_URL=http://{ip}:{args.hub_port}',
                f'export DJANGO_ALLOWED_HOSTS={ip},127.0.0.1,localhost',
                "python manage.py runserver 0.0.0.0:8000",
            ],
        },
        "client_exports": {
            "CRATES_BACKEND_URL": f"http://{ip}:{args.backend_port}",
            "CRATES_LAN_HUB_URL": f"http://{ip}:{args.hub_port}",
        },
    }

    print("=== SHARE THIS JSON WITH CLIENT ===")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print()
    print("=== QUICK SERVER CHECKLIST ===")
    print(f"Hub URL:     {payload['hub_url']}")
    print(f"Backend URL: {payload['backend_url']}")
    print("Run in terminal #1:")
    for cmd in payload["server_commands"]["hub"]:
        print(cmd)
    print()
    print("Run in terminal #2:")
    for cmd in payload["server_commands"]["backend"]:
        print(cmd)


if __name__ == "__main__":
    main()
