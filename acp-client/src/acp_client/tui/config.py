"""Конфигурация TUI-клиента и ее локальное хранение."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

type TUITheme = Literal["light", "dark"]


@dataclass(slots=True)
class TUIConfig:
    """Пользовательская конфигурация запуска TUI."""

    host: str = "127.0.0.1"
    port: int = 8765
    theme: TUITheme = "light"


class TUIConfigStore:
    """Загружает и сохраняет конфигурацию TUI в JSON-файл."""

    def __init__(self, file_path: Path | None = None) -> None:
        """Настраивает путь хранения конфигурации в домашней директории."""

        self._file_path = file_path or (Path.home() / ".acp-client" / "tui_config.json")

    def load(self) -> TUIConfig:
        """Загружает конфигурацию из файла или возвращает значения по умолчанию."""

        if not self._file_path.exists():
            return TUIConfig()

        try:
            payload = json.loads(self._file_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return TUIConfig()

        return self._from_payload(payload)

    def save(self, config: TUIConfig) -> None:
        """Сохраняет конфигурацию в файл, не прерывая выполнение при ошибках IO."""

        try:
            self._file_path.parent.mkdir(parents=True, exist_ok=True)
            self._file_path.write_text(
                json.dumps(
                    {
                        "host": config.host,
                        "port": config.port,
                        "theme": config.theme,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
        except OSError:
            # Локальная конфигурация не должна ломать runtime поведение TUI.
            return

    @staticmethod
    def _from_payload(payload: Any) -> TUIConfig:
        """Преобразует произвольный JSON-payload в валидный объект TUIConfig."""

        if not isinstance(payload, dict):
            return TUIConfig()

        host = payload.get("host")
        port = payload.get("port")
        theme = payload.get("theme")

        normalized_host = host if isinstance(host, str) and host else "127.0.0.1"
        normalized_port = port if isinstance(port, int) and port > 0 else 8765
        normalized_theme: TUITheme = "dark" if theme == "dark" else "light"

        return TUIConfig(
            host=normalized_host,
            port=normalized_port,
            theme=normalized_theme,
        )


def resolve_tui_connection(*, host: str | None, port: int | None) -> tuple[str, int]:
    """Возвращает host/port запуска TUI с fallback на сохраненный конфиг."""

    config = TUIConfigStore().load()
    resolved_host = host if isinstance(host, str) and host else config.host
    resolved_port = port if isinstance(port, int) and port > 0 else config.port
    return resolved_host, resolved_port
