"""Handler для команды /mode.

Показывает или изменяет режим сессии.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from codelab.server.models import AvailableCommand, AvailableCommandInput

from ..base import CommandHandler, CommandResult

if TYPE_CHECKING:
    from codelab.server.protocol.state import SessionState

# Доступные режимы сессии
AVAILABLE_MODES = ["code", "architect", "ask", "debug"]


class ModeCommandHandler(CommandHandler):
    """Handler для команды /mode.

    Без аргументов: показывает текущий режим.
    С аргументом: устанавливает новый режим.

    Пример использования:
        handler = ModeCommandHandler()
        # Показать текущий режим
        result = handler.execute([], session)
        # Установить режим
        result = handler.execute(["architect"], session)
    """

    def execute(
        self,
        args: list[str],
        session: SessionState,
    ) -> CommandResult:
        """Выполняет команду /mode.

        Args:
            args: Пустой список для показа режима, или [mode_name] для установки
            session: Состояние сессии

        Returns:
            CommandResult с информацией о режиме или подтверждением смены
        """
        current_mode = session.config_values.get("mode", "code")

        # Если аргументов нет — показываем текущий режим
        if not args:
            lines = [
                f"🎯 **Текущий режим:** `{current_mode}`",
                "",
                "**Доступные режимы:**",
            ]
            for mode in AVAILABLE_MODES:
                marker = "→" if mode == current_mode else " "
                lines.append(f" {marker} `{mode}`")

            lines.append("")
            lines.append("Для смены режима: `/mode <имя_режима>`")

            return CommandResult(
                content=[{"type": "text", "text": "\n".join(lines)}]
            )

        # Устанавливаем новый режим
        new_mode = args[0].lower()

        if new_mode not in AVAILABLE_MODES:
            return CommandResult(
                content=[{
                    "type": "text",
                    "text": (
                        f"❌ Неизвестный режим: `{new_mode}`\n\n"
                        f"Доступные режимы: {', '.join(f'`{m}`' for m in AVAILABLE_MODES)}"
                    ),
                }]
            )

        if new_mode == current_mode:
            return CommandResult(
                content=[{
                    "type": "text",
                    "text": f"ℹ️ Режим `{current_mode}` уже активен.",
                }]
            )

        # Устанавливаем новый режим в config_values
        session.config_values["mode"] = new_mode

        # Формируем update для клиента
        mode_update = {
            "sessionUpdate": "current_mode_update",
            "mode": new_mode,
        }

        return CommandResult(
            content=[{
                "type": "text",
                "text": f"✅ Режим изменён: `{current_mode}` → `{new_mode}`",
            }],
            updates=[mode_update],
        )

    def get_definition(self) -> AvailableCommand:
        """Возвращает определение команды /mode."""
        return AvailableCommand(
            name="mode",
            description="Показать или изменить режим сессии",
            input=AvailableCommandInput(
                hint="имя режима (code, architect, ask, debug)"
            ),
        )
