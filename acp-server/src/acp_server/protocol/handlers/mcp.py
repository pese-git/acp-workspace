"""Обработчики методов ACP для управления MCP серверами.

Реализует методы:
- session/mcp/add — добавление MCP сервера к сессии
- session/mcp/remove — удаление MCP сервера из сессии
- session/mcp/list — список подключённых MCP серверов
"""

from __future__ import annotations

from typing import Any

import structlog

from ...mcp.manager import (
    MCPManager,
    MCPManagerError,
    MCPServerAlreadyExistsError,
    MCPServerNotFoundError,
)
from ...mcp.models import MCPServerConfig
from ...messages import ACPMessage, JsonRpcId
from ..state import SessionState

# Используем structlog для структурированного логирования
logger = structlog.get_logger()


def _get_or_create_mcp_manager(session: SessionState) -> MCPManager:
    """Получить или создать MCPManager для сессии.
    
    MCPManager хранится в поле session.mcp_manager.
    
    Args:
        session: Состояние сессии.
    
    Returns:
        MCPManager для данной сессии.
    """
    if session.mcp_manager is None:
        session.mcp_manager = MCPManager(session.session_id)
        logger.debug(
            "Created new MCPManager for session",
            session_id=session.session_id,
        )
    
    return session.mcp_manager


async def session_mcp_add(
    request_id: JsonRpcId | None,
    params: dict[str, Any],
    session: SessionState,
) -> ACPMessage:
    """Добавить MCP сервер к сессии.
    
    Запускает MCP сервер, выполняет инициализацию и получает список
    инструментов. Инструменты становятся доступны агенту с namespace-
    префиксом mcp:{server_id}:{tool_name}.
    
    JSON-RPC метод: session/mcp/add
    
    Параметры:
        name: str — уникальный идентификатор сервера
        command: str — команда для запуска сервера
        args: list[str] — аргументы командной строки (опционально)
        env: list[dict] — переменные окружения (опционально)
    
    Результат:
        server_id: str — ID добавленного сервера
        tools_count: int — количество доступных инструментов
        tools: list[dict] — список инструментов с их описаниями
    
    Args:
        request_id: ID JSON-RPC запроса.
        params: Параметры запроса с конфигурацией MCP сервера.
        session: Состояние сессии.
    
    Returns:
        ACPMessage с результатом или ошибкой.
    """
    logger.info(
        "session/mcp/add called",
        session_id=session.session_id,
        params=params,
    )
    
    # Валидация обязательных параметров
    if "name" not in params:
        return ACPMessage.error(
            id=request_id,
            code=-32602,
            message="Missing required parameter: name",
        )
    
    if "command" not in params:
        return ACPMessage.error(
            id=request_id,
            code=-32602,
            message="Missing required parameter: command",
        )
    
    try:
        # Создаём конфигурацию
        config = MCPServerConfig(
            name=params["name"],
            command=params["command"],
            args=params.get("args", []),
            env=params.get("env", []),
        )
        
        # Получаем MCPManager
        mcp_manager = _get_or_create_mcp_manager(session)
        
        # Добавляем сервер
        tools = await mcp_manager.add_server(config)
        
        # Формируем ответ
        tools_info = [
            {
                "name": tool.name,
                "description": tool.description,
                "kind": tool.kind,
            }
            for tool in tools
        ]
        
        logger.info(
            "MCP server added successfully",
            session_id=session.session_id,
            server_id=config.name,
            tools_count=len(tools),
        )
        
        return ACPMessage.result(
            id=request_id,
            result={
                "server_id": config.name,
                "tools_count": len(tools),
                "tools": tools_info,
            },
        )
        
    except MCPServerAlreadyExistsError as e:
        logger.warning(
            "MCP server already exists",
            session_id=session.session_id,
            error=str(e),
        )
        return ACPMessage.error(
            id=request_id,
            code=-32000,
            message=str(e),
        )
        
    except MCPManagerError as e:
        logger.error(
            "Failed to add MCP server",
            session_id=session.session_id,
            error=str(e),
        )
        return ACPMessage.error(
            id=request_id,
            code=-32000,
            message=f"Failed to add MCP server: {e}",
        )
        
    except Exception as e:
        logger.exception(
            "Unexpected error adding MCP server",
            session_id=session.session_id,
        )
        return ACPMessage.error(
            id=request_id,
            code=-32603,
            message=f"Internal error: {e}",
        )


async def session_mcp_remove(
    request_id: JsonRpcId | None,
    params: dict[str, Any],
    session: SessionState,
) -> ACPMessage:
    """Удалить MCP сервер из сессии.
    
    Останавливает MCP сервер и удаляет его инструменты из доступных.
    
    JSON-RPC метод: session/mcp/remove
    
    Параметры:
        server_id: str — ID сервера для удаления
    
    Результат:
        server_id: str — ID удалённого сервера
        success: bool — True если успешно удалён
    
    Args:
        request_id: ID JSON-RPC запроса.
        params: Параметры с server_id.
        session: Состояние сессии.
    
    Returns:
        ACPMessage с результатом или ошибкой.
    """
    logger.info(
        "session/mcp/remove called",
        session_id=session.session_id,
        params=params,
    )
    
    # Валидация параметров
    server_id = params.get("server_id")
    
    if not server_id:
        return ACPMessage.error(
            id=request_id,
            code=-32602,
            message="Missing required parameter: server_id",
        )
    
    # Получаем MCPManager
    mcp_manager = session.mcp_manager
    
    if mcp_manager is None:
        return ACPMessage.error(
            id=request_id,
            code=-32000,
            message="No MCP servers connected to this session",
        )
    
    try:
        await mcp_manager.remove_server(server_id)
        
        logger.info(
            "MCP server removed successfully",
            session_id=session.session_id,
            server_id=server_id,
        )
        
        return ACPMessage.result(
            id=request_id,
            result={
                "server_id": server_id,
                "success": True,
            },
        )
        
    except MCPServerNotFoundError as e:
        logger.warning(
            "MCP server not found for removal",
            session_id=session.session_id,
            server_id=server_id,
        )
        return ACPMessage.error(
            id=request_id,
            code=-32000,
            message=str(e),
        )
        
    except MCPManagerError as e:
        logger.error(
            "Failed to remove MCP server",
            session_id=session.session_id,
            server_id=server_id,
            error=str(e),
        )
        return ACPMessage.error(
            id=request_id,
            code=-32000,
            message=f"Failed to remove MCP server: {e}",
        )
        
    except Exception as e:
        logger.exception(
            "Unexpected error removing MCP server",
            session_id=session.session_id,
        )
        return ACPMessage.error(
            id=request_id,
            code=-32603,
            message=f"Internal error: {e}",
        )


async def session_mcp_list(
    request_id: JsonRpcId | None,
    params: dict[str, Any],
    session: SessionState,
) -> ACPMessage:
    """Получить список подключённых MCP серверов.
    
    JSON-RPC метод: session/mcp/list
    
    Параметры:
        (нет параметров)
    
    Результат:
        servers: list[dict] — список серверов с информацией о каждом:
            - id: str — идентификатор сервера
            - name: str — имя сервера
            - command: str — команда запуска
            - state: str — состояние (created, ready, closed и т.д.)
            - tools_count: int — количество инструментов
            - capabilities: dict — capabilities сервера (опционально)
    
    Args:
        request_id: ID JSON-RPC запроса.
        params: Параметры запроса (игнорируются).
        session: Состояние сессии.
    
    Returns:
        ACPMessage со списком серверов.
    """
    logger.debug(
        "session/mcp/list called",
        session_id=session.session_id,
    )
    
    # Получаем MCPManager
    mcp_manager = session.mcp_manager
    
    if mcp_manager is None:
        # Нет MCPManager — нет серверов
        return ACPMessage.result(
            id=request_id,
            result={"servers": []},
        )
    
    try:
        servers_info = mcp_manager.get_servers_info()
        
        logger.debug(
            "Returning MCP servers list",
            session_id=session.session_id,
            servers_count=len(servers_info),
        )
        
        return ACPMessage.result(
            id=request_id,
            result={"servers": servers_info},
        )
        
    except Exception as e:
        logger.exception(
            "Unexpected error listing MCP servers",
            session_id=session.session_id,
        )
        return ACPMessage.error(
            id=request_id,
            code=-32603,
            message=f"Internal error: {e}",
        )


def get_mcp_manager(session: SessionState) -> MCPManager | None:
    """Получить MCPManager для сессии без создания нового.
    
    Утилитарная функция для использования в других модулях.
    
    Args:
        session: Состояние сессии.
    
    Returns:
        MCPManager или None если не создан.
    """
    return session.mcp_manager


async def shutdown_mcp_manager(session: SessionState) -> None:
    """Завершить работу MCPManager при закрытии сессии.
    
    Должен вызываться при завершении сессии для очистки ресурсов.
    
    Args:
        session: Состояние сессии.
    """
    mcp_manager = session.mcp_manager
    
    if mcp_manager is not None:
        await mcp_manager.shutdown()
        session.mcp_manager = None
