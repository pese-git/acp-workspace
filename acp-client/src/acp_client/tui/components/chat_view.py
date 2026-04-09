"""Компонент для отображения истории сообщений с MVVM интеграцией.

Отвечает за:
- Отображение истории сообщений из ChatViewModel
- Отображение streaming текста в реальном времени
- Отображение tool calls
- Реактивные обновления при изменении состояния
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import structlog
from textual.app import ComposeResult
from textual.containers import Container, VerticalScroll
from textual.widgets import Static

if TYPE_CHECKING:
    from acp_client.presentation.chat_view_model import ChatViewModel


class ChatView(VerticalScroll):
    """Компонент чата с MVVM интеграцией.
    
    Обязательно требует ChatViewModel для работы. Подписывается на Observable свойства:
    - messages: история сообщений
    - tool_calls: список tool calls
    - is_streaming: флаг активного streaming
    - streaming_text: текущий streaming текст
    
    Примеры использования:
        >>> from acp_client.presentation.chat_view_model import ChatViewModel
        >>> chat_vm = ChatViewModel(coordinator, event_bus)
        >>> chat_view = ChatView(chat_vm)
        >>> 
        >>> # Когда ChatViewModel обновляется, chat_view обновляется автоматически
        >>> chat_vm.messages.value = [message1, message2]
    """

    def __init__(self, chat_vm: ChatViewModel) -> None:
        """Инициализирует ChatView с обязательным ChatViewModel.
        
        Args:
            chat_vm: ChatViewModel для управления состоянием чата
        """
        super().__init__(id="chat_view")
        self.chat_vm = chat_vm
        self._mounted = False
        self._content_container: Container | None = None
        self._logger = structlog.get_logger("chat_view")
        
        self.chat_vm.messages.subscribe(self._on_messages_changed)
        self.chat_vm.tool_calls.subscribe(self._on_tool_calls_changed)
        self.chat_vm.is_streaming.subscribe(self._on_streaming_changed)
        self.chat_vm.streaming_text.subscribe(self._on_streaming_text_changed)

    def compose(self) -> ComposeResult:
        """Создает внутренний контейнер для контента чата."""
        # Создаем контейнер для динамического добавления виджетов
        self._content_container = Container(id="chat_content")
        yield self._content_container

    def on_mount(self) -> None:
        """Вызывается когда компонент смонтирован в приложение."""
        self._mounted = True
        self._update_display()

    def _on_messages_changed(self, messages: list) -> None:
        """Обновить чат при изменении сообщений.
        
        Args:
            messages: Новый список сообщений
        """
        self._update_display()

    def _on_tool_calls_changed(self, tool_calls: list) -> None:
        """Обновить чат при изменении tool calls.
        
        Args:
            tool_calls: Новый список tool calls
        """
        self._update_display()

    def _on_streaming_changed(self, is_streaming: bool) -> None:
        """Обновить чат при изменении статуса streaming.
        
        Args:
            is_streaming: True если идет streaming, False иначе
        """
        self._update_display()

    def _on_streaming_text_changed(self, text: str) -> None:
        """Обновить чат при получении нового streaming текста.
        
        Args:
            text: Новый streaming текст
        """
        self._logger.debug("on_streaming_text_changed", text=text[:50] if text else "", 
                          text_length=len(text))
        self._update_display()

    def _update_display(self) -> None:
        """Обновить отображение чата на основе текущего состояния."""
        if self.chat_vm is None or not self._mounted or self._content_container is None:
            return
        
        # Очищаем старый контент (счетчик не сбрасываем, чтобы ID оставались уникальными)
        self._content_container.query("*").remove()
        
        # Отображаем сообщения
        messages = self.chat_vm.messages.value
        for message in messages:
            self._render_message(message)
        
        # Отображаем streaming текст если идет streaming
        if self.chat_vm.is_streaming.value and self.chat_vm.streaming_text.value:
            self._render_streaming_text(self.chat_vm.streaming_text.value)
        
        # Отображаем tool calls
        tool_calls = self.chat_vm.tool_calls.value
        for tool_call in tool_calls:
            self._render_tool_call(tool_call)
        
        # Скроллируем вниз
        self.scroll_end()

    def _render_message(self, message: object) -> None:
        """Отобразить одно сообщение.
        
        Args:
            message: Объект сообщения (dict с ключами type и content)
        """
        if self._content_container is None:
            return
            
        # Извлекаем тип и содержимое из сообщения
        if isinstance(message, dict):
            msg_type: str = message.get("type", "unknown")  # type: ignore[no-matching-overload]
            content: str = message.get("content", "")  # type: ignore[no-matching-overload]
            
            # Форматируем сообщение в зависимости от типа
            if msg_type == "user":
                formatted = f"[bold blue]Ты:[/bold blue] {content}"
            elif msg_type == "assistant":
                formatted = f"[bold green]Агент:[/bold green] {content}"
            elif msg_type == "system":
                formatted = f"[bold yellow]Система:[/bold yellow] {content}"
            else:
                formatted = content
        else:
            formatted = str(message)
        
        # Монтируем виджет с сообщением в контейнер, используя timestamp для уникальности
        message_widget = Static(formatted, id=f"msg_{time.time_ns()}", classes="message")
        self._content_container.mount(message_widget)

    def _render_streaming_text(self, text: str) -> None:
        """Отобразить streaming текст.
        
        Args:
            text: Streaming текст
        """
        if self._content_container is None:
            return

        # Используем timestamp для streaming виджета
        streaming_widget = Static(
            f"[bold green]⟳ {text}[/bold green]",
            id=f"stream_{time.time_ns()}",
            classes="message",
        )
        self._content_container.mount(streaming_widget)

    def _render_tool_call(self, tool_call: object) -> None:
        """Отобразить tool call.
        
        Args:
            tool_call: Объект tool call
        """
        if self._content_container is None:
            return

        # Используем timestamp для tool call виджета
        tool_widget = Static(
            f"[italic]Tool: {tool_call}[/italic]",
            id=f"tool_{time.time_ns()}",
            classes="message",
        )
        self._content_container.mount(tool_widget)

    def append_message(self, message: str) -> None:
        """Добавить сообщение в чат (для backward compatibility).
        
        Args:
            message: Текст сообщения
        """
        if self.chat_vm is not None:
            messages = self.chat_vm.messages.value.copy()
            messages.append({"type": "assistant", "content": message})
            self.chat_vm.messages.value = messages
        else:
            # Fallback для случаев без ViewModel
            if self._content_container is not None:
                widget = Static(message, id=f"msg_{time.time_ns()}", classes="message")
                self._content_container.mount(widget)

    def clear_messages(self) -> None:
        """Очистить все сообщения из чата.
        
        Удаляет все сообщения из ChatViewModel.
        """
        if self.chat_vm is not None:
            self.chat_vm.messages.value = []

    def add_user_message(self, message: str) -> None:
        """Добавить пользовательское сообщение в чат.
        
        Args:
            message: Текст пользовательского сообщения
        """
        if self.chat_vm is not None:
            messages = self.chat_vm.messages.value.copy()
            messages.append({"type": "user", "content": message})
            self.chat_vm.messages.value = messages

    def add_system_message(self, message: str) -> None:
        """Добавить системное сообщение в чат.
        
        Args:
            message: Текст системного сообщения
        """
        if self.chat_vm is not None:
            messages = self.chat_vm.messages.value.copy()
            messages.append({"type": "system", "content": message})
            self.chat_vm.messages.value = messages

    def append_agent_chunk(self, text: str) -> None:
        """Добавить chunk текста агента в streaming режиме.
        
        Используется для обновления streaming текста при получении данных от агента.
        
        Args:
            text: Текст chunk'а от агента
        """
        self._logger.debug("append_agent_chunk", text=text, text_length=len(text))
        if self.chat_vm is not None:
            # Активируем streaming режим и конкатенируем текст
            self.chat_vm.is_streaming.value = True
            # Конкатенируем новый текст со старым (не перезаписываем!)
            old_text = self.chat_vm.streaming_text.value
            self.chat_vm.streaming_text.value += text
            self._logger.debug("streaming_text_updated", 
                             old_length=len(old_text),
                             new_length=len(self.chat_vm.streaming_text.value))

    def finish_agent_message(self) -> None:
        """Обозначить окончание агентского сообщения.
        
        Используется для маркировки конца streaming сообщения от агента.
        """
        if self.chat_vm is not None:
            # Сохраняем streaming текст в messages перед сбросом
            streaming_text = self.chat_vm.streaming_text.value
            self._logger.debug("finish_agent_message", 
                             streaming_text_length=len(streaming_text))
            
            if streaming_text:
                # Добавляем накопленный streaming текст в историю сообщений
                messages = self.chat_vm.messages.value.copy()
                messages.append({"type": "assistant", "content": streaming_text})
                self.chat_vm.messages.value = messages
                self._logger.debug("streaming_text_saved_to_messages", 
                                 text_length=len(streaming_text))
            
            # Отключаем streaming режим и очищаем буфер
            self.chat_vm.is_streaming.value = False
            self.chat_vm.streaming_text.value = ""
