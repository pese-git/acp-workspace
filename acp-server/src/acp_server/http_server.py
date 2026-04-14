"""WebSocket транспорт ACP-сервера.

Модуль поднимает endpoint `GET /acp/ws` для двустороннего потока с
`session/update` и server->client RPC.

Пример использования:
    server = ACPHttpServer(host="127.0.0.1", port=8080)
    await server.run()
"""

from __future__ import annotations

import asyncio
import time
import uuid

import structlog
from aiohttp import WSMsgType, web

from .agent.orchestrator import AgentOrchestrator
from .agent.state import OrchestratorConfig
from .config import AppConfig
from .llm import LLMProvider, MockLLMProvider, OpenAIProvider
from .messages import ACPMessage
from .protocol import ACPProtocol, ProtocolOutcome
from .storage import SessionStorage
from .tools.registry import SimpleToolRegistry

# Получаем структурированный logger
logger = structlog.get_logger()

# Константа: максимальное время ожидания для deferred prompt tasks (в секундах)
# Если prompt не завершится за это время, его нужно отменить
DEFERRED_PROMPT_TIMEOUT = 30.0


def _truncate_payload(payload: str, max_length: int = 500) -> str:
    """Обрезает payload для логирования, сохраняя значимую часть.
    
    Args:
        payload: Строка payload для обрезки
        max_length: Максимальная длина результата
        
    Returns:
        Обрезанный payload или полный, если он короче max_length
    """
    if len(payload) > max_length:
        return payload[:max_length]
    return payload


class ACPHttpServer:
    """Транспортный слой ACP поверх aiohttp (WebSocket-only).

    Класс принимает wire-сообщения, передает их в `ACPProtocol` и отправляет
    обратно response/notifications в правильном порядке.

    Пример использования:
        server = ACPHttpServer(port=8080)
        await server.run()
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8080,
        *,
        require_auth: bool = False,
        auth_api_key: str | None = None,
        storage: SessionStorage | None = None,
        config: AppConfig | None = None,
    ) -> None:
        """Создает транспортный сервер с адресом прослушивания.

        Args:
            host: IP адрес для прослушивания (по умолчанию 127.0.0.1).
            port: Порт для прослушивания (по умолчанию 8080).
            require_auth: Требовать аутентификацию перед session/new и session/load.
            auth_api_key: API ключ для аутентификации.
            storage: Backend для хранения сессий (по умолчанию InMemoryStorage).
            config: Глобальная конфигурация приложения (LLM, агент и т.д.).

        Пример использования:
            ACPHttpServer(host="0.0.0.0", port=8080)
        """

        self.host = host
        self.port = port
        self.require_auth = require_auth
        self.auth_api_key = auth_api_key
        self.storage = storage
        self.config = config or AppConfig()
        # Оркестратор агента инициализируется в методе run()
        self._agent_orchestrator: AgentOrchestrator | None = None
        
        # Логируем инициализацию сервера
        logger.debug(
            "acp http server initialized",
            host=host,
            port=port,
            require_auth=require_auth,
            has_auth_key=bool(auth_api_key),
        )

    async def _initialize_llm_provider(self) -> LLMProvider | None:
        """Инициализирует LLM провайдера на основе конфигурации.

        Returns:
            Инициализированный LLM провайдер или None если тип провайдера неизвестен.

        Пример использования:
            provider = await server._initialize_llm_provider()
        """
        logger.debug("initializing llm provider", provider_type=self.config.llm.provider)
        llm_provider: LLMProvider | None = None

        if self.config.llm.provider == "openai":
            # Инициализируем OpenAI провайдера
            logger.debug("configuring openai provider", model=self.config.llm.model)
            openai_provider = OpenAIProvider()
            config_dict = {
                "api_key": self.config.llm.api_key,
                "model": self.config.llm.model,
                "temperature": self.config.llm.temperature,
                "max_tokens": self.config.llm.max_tokens,
            }
            if self.config.llm.base_url:
                config_dict["base_url"] = self.config.llm.base_url

            await openai_provider.initialize(config_dict)
            logger.debug("openai provider initialized", model=self.config.llm.model)
            llm_provider = openai_provider
            logger.info(
                "openai llm provider initialized",
                model=self.config.llm.model,
            )
        elif self.config.llm.provider == "mock":
            # Используем mock провайдера для разработки
            llm_provider = MockLLMProvider()
            logger.info("mock llm provider initialized")
        else:
            # Неизвестный тип провайдера, логируем ошибку
            logger.warning(
                "unknown llm provider type, using mock",
                provider=self.config.llm.provider,
            )
            llm_provider = MockLLMProvider()

        return llm_provider

    async def run(self) -> None:
        """Запускает WS endpoint и держит процесс живым.

        Инициализирует LLM провайдера и AgentOrchestrator на основе конфигурации.

        Пример использования:
            await ACPHttpServer().run()
        """
        # Инициализируем LLM провайдера на основе конфигурации
        llm_provider = await self._initialize_llm_provider()
        
        # Создаем AgentOrchestrator если есть провайдер
        agent_orchestrator: AgentOrchestrator | None = None
        if llm_provider is not None:
            # Создаем реестр инструментов (пока пустой, можно расширить в будущем)
            tool_registry = SimpleToolRegistry()
            
            # Создаем конфигурацию оркестратора на основе глобального конфига
            orchestrator_config = OrchestratorConfig(
                enabled=True,
                agent_class="naive",
                model=self.config.llm.model,
                temperature=self.config.llm.temperature,
                max_tokens=self.config.llm.max_tokens,
                llm_provider_class="openai" if self.config.llm.provider == "openai" else "mock",
            )
            
            # Инициализируем оркестратор
            agent_orchestrator = AgentOrchestrator(
                config=orchestrator_config,
                llm_provider=llm_provider,
                tool_registry=tool_registry,
            )
            
            logger.info(
                "agent orchestrator initialized",
                system_prompt_length=len(self.config.agent.system_prompt),
            )
        
        # Сохраняем оркестратор для использования в обработчике
        self._agent_orchestrator = agent_orchestrator

        app = web.Application()
        app.router.add_get("/acp/ws", self.handle_ws_request)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host=self.host, port=self.port)
        await site.start()
        
        # Логируем запуск сервера
        logger.info(
            "server started",
            host=self.host,
            port=self.port,
            endpoint="/acp/ws",
        )

        try:
            while True:
                await asyncio.sleep(3600)
        finally:
            # Логируем остановку сервера
            logger.info("server shutting down")
            await runner.cleanup()

    async def handle_ws_request(self, request: web.Request) -> web.WebSocketResponse:
        """Обрабатывает WebSocket-сессию с поддержкой update-потока.

        Пример использования:
            # вызывается aiohttp автоматически на GET /acp/ws
        """

        # Генерируем уникальный ID подключения для отслеживания
        connection_id = str(uuid.uuid4())[:8]
        remote_addr = request.remote or "unknown"
        start_time = time.time()
        
        # Логируем установку нового WebSocket подключения
        logger.info(
            "ws connection request received",
            connection_id=connection_id,
            remote_addr=remote_addr,
        )
        
        # Логируем подключение клиента
        logger.info(
            "ws connection established",
            connection_id=connection_id,
            remote_addr=remote_addr,
        )

        ws = web.WebSocketResponse()
        await ws.prepare(request)
        protocol = ACPProtocol(
            require_auth=self.require_auth,
            auth_api_key=self.auth_api_key,
            storage=self.storage,
            agent_orchestrator=self._agent_orchestrator,
        )
        # Храним отложенные завершения prompt-turn по sessionId в рамках WS-соединения.
        deferred_prompt_tasks: dict[str, asyncio.Task[None]] = {}
        # По ACP любые session-методы в WS доступны только после initialize.
        initialized = False
        
        # Создаем логгер с контекстом подключения
        conn_logger = logger.bind(connection_id=connection_id)

        try:
            async for message in ws:
                if message.type == WSMsgType.TEXT:
                    method_name: str | None = None
                    session_id: str | None = None
                    request_id: str | None = None
                    try:
                        acp_request = ACPMessage.from_json(message.data)
                        method_name = acp_request.method
                        request_id = str(acp_request.id) if acp_request.id is not None else None
                        
                        # Логируем получение данных с payload
                        conn_logger.debug(
                            "message received",
                            payload=_truncate_payload(message.data),
                        )
                        
                        if method_name is None:
                            outcome = protocol.handle_client_response(acp_request)
                        else:
                            if method_name == "initialize":
                                initialized = True
                            elif not initialized:
                                if acp_request.is_notification:
                                    outcome = ProtocolOutcome()
                                else:
                                    outcome = ProtocolOutcome(
                                        response=ACPMessage.error_response(
                                            acp_request.id,
                                            code=-32000,
                                            message="Initialize required before session methods",
                                        )
                                    )
                                method_name = None
                                session_id = None
                                for notification in outcome.notifications:
                                    await ws.send_str(notification.to_json())
                                if outcome.response is not None:
                                    await ws.send_str(outcome.response.to_json())
                                for followup_response in outcome.followup_responses:
                                    await ws.send_str(followup_response.to_json())
                                continue
                            if isinstance(acp_request.params, dict):
                                raw_session_id = acp_request.params.get("sessionId")
                                if isinstance(raw_session_id, str):
                                    session_id = raw_session_id
                            outcome = await protocol.handle(acp_request)
                        
                        # Логируем входящий запрос с методом и сессией
                        conn_logger.info(
                            "request received",
                            method=method_name,
                            request_id=request_id,
                            session_id=session_id,
                        )
                    except Exception as exc:
                        # Логируем ошибку парсинга с полным traceback
                        conn_logger.error(
                            "request parse error",
                            request_id=request_id,
                            error=str(exc),
                            exc_info=True,
                        )
                        outcome = ProtocolOutcome(
                            response=ACPMessage.error_response(
                                None,
                                code=-32700,
                                message="Parse error",
                                data=str(exc),
                            )
                        )

                    if method_name == "session/cancel" and session_id is not None:
                        task = deferred_prompt_tasks.pop(session_id, None)
                        if task is not None:
                            task.cancel()

                    if (
                        method_name == "session/prompt"
                        and session_id is not None
                        and outcome.response is None
                        and protocol.should_auto_complete_active_turn(session_id)
                    ):
                        task = deferred_prompt_tasks.pop(session_id, None)
                        if task is not None:
                            task.cancel()
                        deferred_prompt_tasks[session_id] = asyncio.create_task(
                            self._complete_deferred_prompt(
                                ws=ws,
                                protocol=protocol,
                                session_id=session_id,
                                deferred_prompt_tasks=deferred_prompt_tasks,
                                connection_id=connection_id,
                            )
                        )

                    # Отправляем уведомления
                    for notification in outcome.notifications:
                        notification_json = notification.to_json()
                        await ws.send_str(notification_json)
                        conn_logger.debug(
                            "notification sent",
                            method=notification.method,
                            payload=_truncate_payload(notification_json),
                        )

                    # Отправляем основной ответ
                    if outcome.response is not None:
                        response_json = outcome.response.to_json()
                        await ws.send_str(response_json)
                        conn_logger.debug(
                            "response sent",
                            request_id=request_id,
                            has_error=outcome.response.error is not None,
                            payload=_truncate_payload(response_json),
                        )
                    
                    # Отправляем дополнительные ответы
                    for followup_response in outcome.followup_responses:
                        followup_json = followup_response.to_json()
                        await ws.send_str(followup_json)
                        conn_logger.debug(
                            "followup response sent",
                            request_id=followup_response.id,
                            payload=_truncate_payload(followup_json),
                        )

                    if method_name == "shutdown":
                        conn_logger.info("shutdown requested")
                        await ws.close()
                        break
                elif message.type in {WSMsgType.ERROR, WSMsgType.CLOSE, WSMsgType.CLOSING}:
                    break
        finally:
            # Очищаем все оставшиеся deferred prompt tasks с подробным логированием
            if deferred_prompt_tasks:
                conn_logger.info(
                    "cleaning up deferred prompt tasks",
                    pending_tasks_count=len(deferred_prompt_tasks),
                )
                for session_id_to_cancel, task_to_cancel in list(deferred_prompt_tasks.items()):
                    if not task_to_cancel.done():
                        task_to_cancel.cancel()
                        conn_logger.debug(
                            "deferred prompt task cancelled",
                            session_id=session_id_to_cancel,
                        )
                    deferred_prompt_tasks.pop(session_id_to_cancel, None)
            
            # Логируем закрытие соединения с продолжительностью и статусом
            duration = time.time() - start_time
            conn_logger.info(
                "ws connection closed",
                duration=round(duration, 3),
                pending_deferred_tasks=len(deferred_prompt_tasks),
            )

        return ws

    async def _complete_deferred_prompt(
        self,
        *,
        ws: web.WebSocketResponse,
        protocol: ACPProtocol,
        session_id: str,
        deferred_prompt_tasks: dict[str, asyncio.Task[None]],
        connection_id: str,
    ) -> None:
        """Завершает отложенный `session/prompt` и отправляет финальный response.

        Метод нужен для demo-эмуляции in-flight turn, который можно отменить через
        `session/cancel` до отправки финального `stopReason`.

        Включает механизмы:
        - Timeout обработки (30 сек по умолчанию)
        - Graceful обработка исключений
        - Очистка состояния при любом исходе
        - Детальное логирование жизненного цикла

        Пример использования:
            task = asyncio.create_task(server._complete_deferred_prompt(...))
        """
        
        conn_logger = logger.bind(connection_id=connection_id, session_id=session_id)

        try:
            # Небольшая задержка оставляет окно для входящего `session/cancel`.
            await asyncio.sleep(0.05)
            
            # Выполняем завершение turn с timeout
            try:
                response = protocol.complete_active_turn(
                    session_id, 
                    stop_reason="end_turn"
                )
            except TimeoutError:
                conn_logger.warning(
                    "deferred prompt completion timeout",
                    timeout_sec=DEFERRED_PROMPT_TIMEOUT,
                )
                response = None
            except Exception as exc:
                conn_logger.error(
                    "deferred prompt completion error",
                    error=str(exc),
                    exc_info=True,
                )
                response = None
            
            # Отправляем response если он есть и соединение еще живо
            if response is not None and not ws.closed:
                try:
                    await ws.send_str(response.to_json())
                    conn_logger.info("deferred prompt completed successfully")
                except Exception as exc:
                    conn_logger.error(
                        "deferred prompt send error",
                        error=str(exc),
                        exc_info=True,
                    )
            elif ws.closed:
                conn_logger.debug("deferred prompt skipped (websocket closed)")
            else:
                conn_logger.debug("deferred prompt skipped (no response)")
                
        except asyncio.CancelledError:
            # Нормальная ветка: отмена задачи при `session/cancel`.
            conn_logger.info("deferred prompt cancelled by client")
            return
        except Exception as exc:
            # Неожиданное исключение - логируем, но не пробрасываем
            conn_logger.error(
                "deferred prompt unexpected error",
                error=str(exc),
                exc_info=True,
            )
        finally:
            # Гарантированная очистка из словаря
            removed = deferred_prompt_tasks.pop(session_id, None)
            if removed is not None:
                conn_logger.debug("deferred prompt task removed from tracking")
