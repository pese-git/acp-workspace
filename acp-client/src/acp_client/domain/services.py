"""Domain Services интерфейсы - абстракции для бизнес-операций.

Содержит:
- TransportService - низкоуровневая коммуникация с сервером
- SessionService - управление жизненным циклом сессии
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any


class TransportService(ABC):
    """Service для низкоуровневой коммуникации с ACP сервером.
    
    Инкапсулирует детали транспорта (WebSocket, TCP и т.д.)
    и предоставляет единый интерфейс для отправки и получения сообщений.
    """
    
    @abstractmethod
    async def connect(self) -> None:
        """Устанавливает соединение с сервером.
        
        Raises:
            TransportError: При ошибке подключения
        """
        ...
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Разрывает соединение с сервером."""
        ...
    
    @abstractmethod
    async def send(self, message: dict[str, Any]) -> None:
        """Отправляет сообщение на сервер.
        
        Аргументы:
            message: JSON-RPC сообщение
        
        Raises:
            TransportError: При ошибке отправки
        """
        ...
    
    @abstractmethod
    async def receive(self) -> dict[str, Any]:
        """Получает одно сообщение с сервера.
        
        Это блокирующая операция, ожидающая сообщение.
        
        Возвращает:
            JSON-RPC сообщение из сервера
        
        Raises:
            TransportError: При ошибке получения
        """
        ...
    
    @abstractmethod
    async def listen(self) -> AsyncIterator[dict[str, Any]]:
        """Слушает входящие сообщения с сервера.
        
        Возвращает асинхронный итератор, который выдает
        сообщения по мере их поступления с сервера.
        
        Yields:
            JSON-RPC сообщения из сервера
        """
        ...
    
    @abstractmethod
    def is_connected(self) -> bool:
        """Проверяет наличие активного соединения.
        
        Возвращает:
            True если соединение активно
        """
        ...


class SessionService(ABC):
    """Service для управления жизненным циклом сессии.
    
    Предоставляет высокоуровневые операции для работы с сессиями,
    включая создание, загрузку, и отправку запросов.
    """
    
    @abstractmethod
    async def initialize(self) -> dict[str, Any]:
        """Инициализирует соединение с сервером.
        
        Отправляет метод 'initialize' и получает capabilities сервера.
        
        Возвращает:
            Ответ с capabilities сервера
        
        Raises:
            SessionError: При ошибке инициализации
        """
        ...
    
    @abstractmethod
    async def authenticate(
        self,
        auth_method: str,
        credentials: dict[str, Any],
    ) -> dict[str, Any]:
        """Аутентифицирует клиент на сервере.
        
        Аргументы:
            auth_method: Метод аутентификации
            credentials: Учетные данные
        
        Возвращает:
            Результат аутентификации
        
        Raises:
            SessionError: При ошибке аутентификации
        """
        ...
    
    @abstractmethod
    async def create_session(
        self,
        client_capabilities: dict[str, Any],
    ) -> dict[str, Any]:
        """Создает новую сессию на сервере.
        
        Аргументы:
            client_capabilities: Возможности клиента
        
        Возвращает:
            Объект сессии с ID и конфигурацией
        
        Raises:
            SessionError: При ошибке создания
        """
        ...
    
    @abstractmethod
    async def load_session(self, session_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Загружает существующую сессию.
        
        Аргументы:
            session_id: ID сессии для загрузки
        
        Возвращает:
            Кортеж (setup_result, replay_updates)
            - setup_result: Объект сессии
            - replay_updates: История обновлений для воспроизведения
        
        Raises:
            SessionError: При ошибке загрузки
        """
        ...
    
    @abstractmethod
    async def list_sessions(self) -> list[dict[str, Any]]:
        """Получает список всех доступных сессий.
        
        Возвращает:
            Список сессий с метаданными
        
        Raises:
            SessionError: При ошибке получения списка
        """
        ...
    
    @abstractmethod
    async def send_prompt(
        self,
        session_id: str,
        prompt: str,
        on_update: Any = None,
    ) -> dict[str, Any]:
        """Отправляет prompt в активную сессию.
        
        Аргументы:
            session_id: ID сессии
            prompt: Текст запроса
            on_update: Callback для обновлений (опционально)
        
        Возвращает:
            Результат выполнения prompt
        
        Raises:
            SessionError: При ошибке отправки
        """
        ...
    
    @abstractmethod
    async def cancel_prompt(self, session_id: str) -> None:
        """Отменяет текущий выполняемый prompt.
        
        Аргументы:
            session_id: ID сессии
        
        Raises:
            SessionError: При ошибке отмены
        """
        ...
