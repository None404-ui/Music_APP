#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen


def _load_payload(raw: str) -> dict:
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("JSON must be an object")
    return data


def _read_input(value: str | None) -> str:
    if value:
        p = Path(value)
        if p.exists():
            return p.read_text(encoding="utf-8")
        return value
    return sys.stdin.read()


def _check_json(url: str, timeout: float = 5.0) -> tuple[bool, str]:
    try:
        req = Request(url, headers={"Accept": "application/json"})
        with urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8").strip()
            return True, body[:240]
    except URLError as e:
        return False, str(e)
    except Exception as e:
        return False, str(e)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Принимает JSON от server-info и печатает команды подключения клиента."
    )
    parser.add_argument(
        "payload",
        nargs="?",
        help="JSON строка или путь к файлу с JSON. Если не задано, читается stdin.",
    )
    parser.add_argument("--check", action="store_true", help="Проверить доступность hub/backend")
    parser.add_argument("--run-app", action="store_true", help="Показать итоговую команду запуска app")
    args = parser.parse_args()

    raw = _read_input(args.payload).strip()
    if not raw:
        raise SystemExit("Нет входных данных. Передайте JSON строкой, файлом или через stdin.")
    payload = _load_payload(raw)

    backend_url = str(payload.get("backend_url") or "").strip().rstrip("/")
    hub_url = str(payload.get("hub_url") or "").strip().rstrip("/")
    workspace = str(payload.get("workspace") or ".").strip()

    if not backend_url or not hub_url:
        raise SystemExit("В JSON должны быть backend_url и hub_url.")

    print("=== CLIENT EXPORTS ===")
    print(f'export CRATES_BACKEND_URL="{backend_url}"')
    print(f'export CRATES_LAN_HUB_URL="{hub_url}"')
    print()
    if args.run_app:
        print("=== APP START ===")
        print(f'cd "{workspace}" && python main.py')
        print()

    if args.check:
        print("=== CONNECTIVITY CHECK ===")
        ok_hub, hub_msg = _check_json(f"{hub_url}/health")
        print(f"Hub:     {'OK' if ok_hub else 'FAIL'} {hub_msg}")
        ok_backend, backend_msg = _check_json(f"{backend_url}/api/music-items/")
        print(f"Backend: {'OK' if ok_backend else 'FAIL'} {backend_msg}")
        print()

    print("=== WHAT CLIENT SHOULD DO ===")
    print("1. Export CRATES_BACKEND_URL and CRATES_LAN_HUB_URL.")
    print("2. Start the app.")
    print("3. Upload a track from the UI.")
    print("4. After successful upload, the local source file is no longer needed.")


if __name__ == "__main__":
    main()
