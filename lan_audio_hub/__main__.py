"""
Запуск: из корня репозитория musicAPP:
  pip install -r lan_audio_hub/requirements-lan.txt
  python -m lan_audio_hub

Переменные окружения:
  LAN_HUB_HOST — по умолчанию 0.0.0.0
  LAN_HUB_PORT — по умолчанию 8765
  LAN_HUB_DATA — каталог с index.sqlite и подпапкой tracks/
"""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    host = (os.environ.get("LAN_HUB_HOST") or "0.0.0.0").strip()
    port = int((os.environ.get("LAN_HUB_PORT") or "8765").strip())
    uvicorn.run(
        "lan_audio_hub.app:app",
        host=host,
        port=port,
        factory=False,
        reload=False,
        workers=1,
    )


if __name__ == "__main__":
    main()
