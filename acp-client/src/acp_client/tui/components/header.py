"""Верхняя информационная панель приложения с интеграцией MVVM.

Отвечает за отображение:
- Статуса соединения с сервером
- Индикатора загрузки
- Базовой информации о приложении
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.widgets import Static

if TYPE_CHECKING:
    from acp_client.presentation.ui_view_model import UIViewModel


class HeaderBar(Static):
    """Header с MVVM интеграцией для отображения статуса приложения.
    
    Обязательно требует UIViewModel для работы. Подписывается на Observable свойства:
    - connection_status: текущий статус соединения
    - is_loading: флаг глобальной загрузки
    
    Примеры использования:
        >>> from acp_client.presentation.ui_view_model import UIViewModel, ConnectionStatus
        >>> ui_vm = UIViewModel()
        >>> header = HeaderBar(ui_vm)
        >>> 
        >>> # Когда UIViewModel обновляется, header обновляется автоматически
        >>> ui_vm.connection_status.value = ConnectionStatus.CONNECTED
    """

    def __init__(self, ui_vm: UIViewModel) -> None:
        """Инициализирует HeaderBar с обязательным UIViewModel.
        
        Args:
            ui_vm: UIViewModel для управления состоянием header'a
        """
        super().__init__("", id="header")
        self.ui_vm = ui_vm
        
        # Подписываемся на изменения в UIViewModel
        self.ui_vm.connection_status.subscribe(self._on_connection_status_changed)
        self.ui_vm.is_loading.subscribe(self._on_loading_changed)
        
        # Инициализируем UI с текущим состоянием
        self._update_display()

    def _on_connection_status_changed(self, status: object) -> None:
        """Обновить header при изменении статуса соединения.
        
        Args:
            status: Новый статус соединения (ConnectionStatus enum)
        """
        self._update_display()

    def _on_loading_changed(self, is_loading: bool) -> None:
        """Обновить header при изменении статуса загрузки.
        
        Args:
            is_loading: True если идет загрузка, False иначе
        """
        self._update_display()

    def _update_display(self) -> None:
        """Обновить отображение header'a на основе текущего состояния UIViewModel."""
        if self.ui_vm is None:
            return
        
        status_text = self.ui_vm.connection_status.value.value
        loading_indicator = "⟳ " if self.ui_vm.is_loading.value else ""
        
        display_text = f"{loading_indicator}ACP-Client TUI | {status_text}"
        self.update(display_text)
    
    def set_status(self, status_text: str) -> None:
        """Fallback метод для backward compatibility с app.py.
        
        Args:
            status_text: Статус для отображения
        """
        if self.ui_vm is not None:
            # Если есть UIViewModel, обновляем через него
            self._update_display()
        else:
            # Иначе обновляем напрямую
            display_text = f"ACP-Client TUI | {status_text}"
            self.update(display_text)
