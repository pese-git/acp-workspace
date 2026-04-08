# План интеграции LLM-агента в ACP Server

## 1. Обзор подхода к интеграции

### 1.1 Стратегия интеграции

LLM-агент интегрируется в acp-server как модульный компонент, встраивающийся в существующий prompt-turn pipeline. Подход базируется на:

1. **Минимальная инвазивность**: Изменения в core ACP протокола максимально ограничены
2. **Расширяемость**: Новые LLM провайдеры и агентные фреймворки добавляются без переделки основного кода
3. **Совместимость**: Существующие клиенты продолжают работать без изменений
4. **Гибкость**: Поддержка как встроенного агента, так и интеграции с популярными фреймворками
5. **Мульти-агентность**: Возможность использования нескольких агентов одновременно

### 1.2 Фазы реализации

```
Фаза 0: Фундамент (недели 1-2)
├─ Проектирование интерфейсов
├─ Создание абстракций
└─ Базовая инфраструктура

Фаза 1: Основной агент (недели 3-4)
├─ Базовый LLM-агент
├─ Провайдер OpenAI
└─ Интеграция с prompt-turn

Фаза 2: Интеграция инструментов (недели 5-6)
├─ Реестр инструментов
├─ Обработка разрешений
└─ Pipeline выполнения

Фаза 3: Поддержка фреймворков (недели 7-8)
├─ Интеграция Langchain
├─ Поддержка Langgraph
└─ Точки расширяемости

Фаза 4: Мульти-агентная система (недели 9-10)
├─ Оркестратор мульти-агентов
├─ Координация между агентами
└─ Распределение задач

Фаза 5: Финализация (недели 11-12)
├─ Полное тестирование
├─ Документация
└─ Production readiness
```

## 2. Архитектура решения

### 2.1 Слоистая архитектура

```
┌──────────────────────────────────────────────────────────────┐
│                  Транспортный слой (HTTP/WS)                  │
│         acp-server/http_server.py, server.py                 │
└────────────────────────────┬─────────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────────┐
│                    Слой протокола ACP                         │
│         acp-server/protocol/core.py - ACPProtocol            │
│              ↓ маршрутизирует session/prompt                 │
└────────────────────────────┬─────────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────────┐
│           Слой оркестрации LLM-агентов                        │
│    agents/orchestrator.py - AgentOrchestrator                │
│    ├─ Управление жизненным циклом prompt-turn              │
│    ├─ Координация выполнения инструментов                    │
│    └─ Обработка потоков разрешений                           │
└────────────────────────────┬─────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
   ┌────▼────┐        ┌──────▼──────┐       ┌────▼────┐
   │Фреймворк│        │Реестр       │       │Провайдер│
   │агента   │        │инструментов │       │LLM      │
   │         │        │             │       │         │
   └────┬────┘        └──────┬──────┘       └────┬────┘
        │                    │                    │
   ┌────▼──┬────┬────┐       │               ┌────▼────┐
   │Native │Lang│Lang│       │               │OpenAI   │
   │Agent  │chai│grap│       │   InMemory   │Claude   │
   │       │n   │h   │       │   Registry   │Llama2   │
   └───────┴────┴────┘       │               │Gemini   │
                              │               │Custom   │
                         ┌────▼──────────┐    └────┬────┘
                         │Выполнитель    │         │
                         │инструментов   │◄────────┘
                         │(fs/*, term)   │
                         └────────────────┘
```

### 2.2 Ядро архитектуры: Оркестратор агентов

```python
# Оркестратор управления prompt-turn с LLM-агентом
class AgentOrchestrator:
    """Оркестратор управления prompt-turn с LLM-агентом."""
    
    def __init__(
        self,
        agent: LLMAgent,
        tool_registry: ToolRegistry,
        session_storage: SessionStorage,
        permissions_handler: PermissionsHandler,
    ):
        self.agent = agent
        self.tools = tool_registry
        self.storage = session_storage
        self.permissions = permissions_handler
    
    async def execute_prompt_turn(
        self,
        session_id: str,
        prompt: list[ContentBlock],
        config: SessionConfig,
    ) -> PromptTurnResult:
        """Основной вход для выполнения prompt-turn."""
        
        # Этап 1: Подготовка
        session = await self.storage.load_session(session_id)
        tools = self.tools.get_tools_for_session(session_id)
        
        # Этап 2: Инициализация turn
        turn_state = self._initialize_turn(session_id)
        
        # Этап 3: Отправка в LLM
        agent_response = await self.agent.process_prompt(
            session_id=session_id,
            prompt=prompt,
            tools=tools,
            config=config,
        )
        
        # Этап 4: Обработка tool calls
        while agent_response.stop_reason == "tool_call":
            results = await self._execute_tool_calls(
                session_id=session_id,
                tool_calls=agent_response.tool_calls,
            )
            agent_response = await self.agent.continue_with_results(
                session_id=session_id,
                tool_results=results,
            )
        
        # Этап 5: Финализация
        final_result = self._finalize_turn(session_id, agent_response)
        await self.storage.update_session(session)
        
        return final_result
```

### 2.3 Поток данных через систему

```
Клиент → WebSocket → ACPProtocol → AgentOrchestrator → LLMAgent
                                          ↓
                                    ToolRegistry
                                          ↓
                                    (fs/*, terminal)
                                          ↓
                          session/update (tool_call)
                                          ↓
                              session/request_permission
                                          ↓
                                    Пользователь
```

### 2.4 Компоненты системы

```
acp-server/src/acp_server/
├── protocol/
│   ├── handlers/
│   │   └── agent.py                 # Новый handler для agent/prompt
│   ├── integrations/                # НОВАЯ ПАПКА
│   │   ├── __init__.py
│   │   ├── agent.py                 # Интерфейсы LLMAgent
│   │   ├── orchestrator.py          # AgentOrchestrator
│   │   ├── tool_registry.py         # ToolRegistry
│   │   ├── multi_agent.py           # Мульти-агентная система
│   │   └── state.py                 # AgentState dataclass
│   └── providers/                   # НОВАЯ ПАПКА
│       ├── __init__.py
│       ├── base.py                  # LLMProvider ABC
│       ├── openai.py                # OpenAI реализация
│       ├── custom.py                # Шаблон кастомного провайдера
│       └── mock.py                  # Mock для тестирования
├── agents/                           # НОВАЯ ПАПКА
│   ├── __init__.py
│   ├── native.py                    # NativeAgent (встроенный)
│   ├── langchain_adapter.py         # Интеграция Langchain
│   ├── langgraph_adapter.py         # Интеграция Langgraph
│   └── custom_agent.py              # Шаблон кастомного агента
├── tools/                            # НОВАЯ ПАПКА
│   ├── __init__.py
│   ├── executor.py                  # ToolExecutor
│   ├── builders.py                  # Вспомогательные функции
│   └── acp_tools.py                 # Встроенные ACP инструменты
└── messages_agent.py                # НОВЫЙ: Agent-specific сообщения
```

## 3. Компоненты системы

### 3.1 Провайдер LLM (LLMProvider)

**Расположение**: `acp-server/src/acp_server/protocol/providers/base.py`

```python
class LLMProvider(ABC):
    """Абстрактный интерфейс провайдера LLM."""
    
    @abstractmethod
    async def create_completion(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs,
    ) -> CompletionResponse:
        """Синхронный вызов LLM для получения одного ответа."""
    
    @abstractmethod
    async def stream_completion(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        **kwargs,
    ) -> AsyncIterator[CompletionChunk]:
        """Потоковая обработка ответа от LLM."""
```

**Провайдер OpenAI** (`openai.py`):
- Поддержка GPT-4, GPT-3.5-turbo и других моделей
- Парсинг tool call из OpenAI формата
- Retry логика с экспоненциальной задержкой
- Кэширование embedding токенов

### 3.2 Базовый интерфейс агента (LLMAgent)

**Расположение**: `acp-server/src/acp_server/protocol/integrations/agent.py`

```python
class LLMAgent(ABC):
    """Базовый интерфейс для LLM-агентов."""
    
    @abstractmethod
    async def initialize(self, config: AgentConfig) -> None:
        """Инициализация агента."""
    
    @abstractmethod
    async def process_prompt(
        self,
        session_id: str,
        prompt: list[ContentBlock],
        tools: list[ToolDefinition],
        config: SessionConfig,
    ) -> PromptResponse:
        """Обработка пользовательского запроса через LLM."""
    
    @abstractmethod
    async def continue_with_results(
        self,
        session_id: str,
        tool_results: list[ToolResult],
    ) -> PromptResponse:
        """Продолжение обработки с результатами tool calls."""
    
    @abstractmethod
    async def cancel(self, session_id: str) -> None:
        """Отмена текущей обработки."""
```

**NativeAgent** (`agents/native.py`):
- Встроенная реализация базовой функциональности
- Прямая работа с OpenAI API
- Управление историей сообщений
- Маршрутизация tool call

### 3.3 Оркестратор агентов (AgentOrchestrator)

**Расположение**: `acp-server/src/acp_server/protocol/integrations/orchestrator.py`

Ответственность:
- Управление жизненным циклом prompt-turn
- Координация между Agent и Tool Registry
- Обработка потоков разрешений
- Отправка session/update событий
- Управление состоянием ActiveTurnState

### 3.4 Реестр инструментов (ToolRegistry)

**Расположение**: `acp-server/src/acp_server/protocol/integrations/tool_registry.py`

```python
class ToolRegistry:
    """Реестр инструментов, доступных агенту."""
    
    def register_tool(self, tool: ToolDefinition) -> None:
        """Регистрация инструмента."""
    
    def get_tools_for_session(self, session_id: str) -> list[ToolDefinition]:
        """Получить инструменты с учетом прав."""
    
    async def execute_tool(
        self,
        session_id: str,
        tool_call: ToolCall,
    ) -> ToolExecutionResult:
        """Выполнить инструмент."""
    
    async def request_permission(
        self,
        session_id: str,
        tool_call: ToolCall,
        options: list[PermissionOption],
    ) -> PermissionResponse:
        """Запрос разрешения для tool call."""
```

### 3.5 Встроенные инструменты (Built-in Tools)

**Расположение**: `acp-server/src/acp_server/tools/acp_tools.py`

Встроенные инструменты:
- `fs:read_text_file` — Чтение файла (вид: "read")
- `fs:write_text_file` — Запись файла (вид: "edit")
- `fs:delete_file` — Удаление файла (вид: "delete")
- `terminal:execute` — Выполнение команды (вид: "execute")
- `search:grep` — Поиск в коде (вид: "search")

## 4. Мульти-агентная система

### 4.1 Архитектура мульти-агентной системы

Мульти-агентная система позволяет использовать несколько агентов в одной сессии для разделения ответственности и повышения эффективности.

```
┌────────────────────────────────────────────────────┐
│         Multi-Agent Orchestrator                    │
│  (agents/multi_agent.py - MultiAgentOrchestrator)  │
└────────────────────────────┬───────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
   ┌────▼─────┐        ┌────▼─────┐        ┌────▼─────┐
   │ Мастер-  │        │ Специали-│        │ Верифи-  │
   │ агент    │        │ зирован- │        │ кационный│
   │(routing) │        │ные агенты│        │ агент    │
   │          │        │          │        │          │
   └──────────┘        └──────────┘        └──────────┘
        │                   │                   │
        ├───────────────────┼───────────────────┤
        │                   │                   │
   Инструменты A        Инструменты B       Инструменты C
   (файловая           (код/поиск)         (проверка)
    система)
```

### 4.2 Компоненты мульти-агентной системы

**Расположение**: `acp-server/src/acp_server/protocol/integrations/multi_agent.py`

```python
class MultiAgentOrchestrator:
    """Оркестратор для управления несколькими агентами."""
    
    def __init__(
        self,
        agents: dict[str, LLMAgent],  # agent_name -> LLMAgent
        master_agent: LLMAgent,       # Маршрутизирует задачи
        tool_registry: ToolRegistry,
    ):
        self.agents = agents
        self.master_agent = master_agent
        self.tools = tool_registry
    
    async def execute_prompt_turn(
        self,
        session_id: str,
        prompt: list[ContentBlock],
        config: SessionConfig,
    ) -> PromptTurnResult:
        """Выполнить prompt-turn с несколькими агентами."""
        
        # 1. Мастер-агент анализирует задачу
        task_plan = await self.master_agent.analyze_task(prompt)
        
        # 2. Распределение подзадач между специализированными агентами
        subtask_results = await self._execute_subtasks(
            task_plan.subtasks,
            session_id,
            config,
        )
        
        # 3. Собрать и синтезировать результаты
        final_result = await self.master_agent.synthesize_results(
            subtask_results
        )
        
        return final_result
    
    async def _execute_subtasks(
        self,
        subtasks: list[SubTask],
        session_id: str,
        config: SessionConfig,
    ) -> list[SubTaskResult]:
        """Параллельное выполнение подзадач."""
        tasks = []
        for subtask in subtasks:
            agent = self.agents.get(subtask.agent_name)
            tasks.append(
                agent.process_prompt(
                    session_id=session_id,
                    prompt=subtask.prompt,
                    tools=subtask.available_tools,
                    config=config,
                )
            )
        
        results = await asyncio.gather(*tasks)
        return results
```

### 4.3 Типы агентов в мульти-агентной системе

1. **Мастер-агент (Master Agent)**
   - Анализирует входящий запрос
   - Разбивает сложные задачи на подзадачи
   - Маршрутизирует к специализированным агентам
   - Синтезирует окончательный результат
   - Модель: GPT-4 (высокая интеллектуальность)

2. **Специализированные агенты (Specialist Agents)**
   - Выполняют конкретные типы задач
   - Примеры: CodeAgent, FileSystemAgent, SearchAgent
   - Оптимизированы для своей области
   - Модель: GPT-3.5-turbo или специализированная

3. **Верификационный агент (Verification Agent)**
   - Проверяет качество результатов
   - Выявляет ошибки и противоречия
   - Предлагает исправления
   - Гарантирует согласованность результатов

4. **Координационный агент (Coordinator Agent)**
   - Управляет зависимостями между агентами
   - Обеспечивает обмен данными
   - Разрешает конфликты
   - Оптимизирует очередность выполнения

### 4.4 Конфигурация мульти-агентной системы

```python
# Конфигурация в session/new
multi_agent_config = {
    "agent": "multi",
    "master_agent": {
        "type": "native",
        "model": "gpt-4",
        "system_prompt": "You are a task decomposition expert...",
    },
    "specialist_agents": {
        "code_agent": {
            "type": "native",
            "model": "gpt-4",
            "tools": ["fs:read_file", "fs:write_file", "terminal:execute"],
        },
        "file_agent": {
            "type": "native",
            "model": "gpt-3.5-turbo",
            "tools": ["fs:*"],
        },
        "search_agent": {
            "type": "langchain",
            "model": "gpt-3.5-turbo",
            "tools": ["search:*"],
        },
    },
    "verification_agent": {
        "type": "native",
        "model": "gpt-4",
        "system_prompt": "You are a quality assurance expert...",
    },
}
```

### 4.5 Модели взаимодействия в мульти-агентной системе

#### Модель 1: Последовательное выполнение (Sequential)

```
Задача → Мастер → Подзадача 1 → Агент 1 → Результат 1
                        ↓
                   Подзадача 2 → Агент 2 → Результат 2
                        ↓
                   Подзадача 3 → Агент 3 → Результат 3
                        ↓
                   Синтез результатов → Финальный ответ
```

#### Модель 2: Параллельное выполнение (Parallel)

```
Задача → Мастер → Подзадача 1 ─┐
                  Подзадача 2 ─┼→ Параллельное выполнение
                  Подзадача 3 ─┘
                        ↓
                   Синтез результатов → Финальный ответ
```

#### Модель 3: Иерархическое выполнение (Hierarchical)

```
Главная задача
      ↓
  Мастер-агент
      ↓
  ├─ Подзадача A → Агент A
  │                   ├─ Под-подзадача A1 → Микро-агент A1
  │                   └─ Под-подзадача A2 → Микро-агент A2
  │
  └─ Подзадача B → Агент B
                       └─ Под-подзадача B1 → Микро-агент B1
```

### 4.6 Обмен данными между агентами

```python
class InterAgentCommunication:
    """Канал для обмена данными между агентами."""
    
    async def share_context(
        self,
        from_agent: str,
        to_agent: str,
        data: dict,
        context_type: str = "general",  # general, file_list, search_results
    ) -> None:
        """Поделиться контекстом между агентами."""
        pass
    
    async def get_shared_context(
        self,
        agent: str,
        context_type: str | None = None,
    ) -> dict:
        """Получить общий контекст."""
        pass
    
    async def notify_agent(
        self,
        agent: str,
        event: str,
        payload: dict,
    ) -> None:
        """Отправить уведомление агенту."""
        pass
```

### 4.7 Управление ресурсами в мульти-агентной системе

```python
class ResourceManager:
    """Управление ресурсами для мульти-агентной системы."""
    
    def __init__(
        self,
        max_concurrent_agents: int = 5,
        max_tokens_per_session: int = 100000,
        rate_limit_per_agent: int = 10,  # RPM
    ):
        self.max_concurrent = max_concurrent_agents
        self.max_tokens = max_tokens_per_session
        self.rate_limit = rate_limit_per_agent
    
    async def allocate_resources(
        self,
        session_id: str,
        agents: list[str],
    ) -> dict:
        """Распределить ресурсы между агентами."""
        pass
    
    async def track_token_usage(
        self,
        session_id: str,
        agent: str,
        tokens_used: int,
    ) -> None:
        """Отследить использование токенов."""
        pass
    
    async def enforce_limits(
        self,
        session_id: str,
    ) -> bool:
        """Проверить соблюдение лимитов."""
        pass
```

## 5. Этапы реализации

### Фаза 0: Фундамент и дизайн

**Deliverables:**
- ✓ Техническое задание (LLM_AGENT_INTEGRATION_SPEC.md)
- ✓ План интеграции (LLM_AGENT_INTEGRATION_PLAN.md)
- [ ] Интерфейсы и абстракции (ABC классы)
- [ ] Структуры данных (Dataclasses)

**PR/Commits:**
```
commit: Добавить интерфейсы интеграции LLM-агента
- Добавить LLMProvider ABC
- Добавить LLMAgent ABC
- Добавить Agent-specific state классы
- Добавить Agent message типы
```

### Фаза 1: Основной агент

**Deliverables:**
- [ ] NativeAgent реализация
- [ ] OpenAI LLMProvider реализация
- [ ] Базовая интеграция с session/prompt

**PR/Commits:**
```
commit: Реализовать NativeAgent и OpenAI провайдер
- NativeAgent с управлением истории сообщений
- OpenAILLMProvider с поддержкой GPT-4
- Парсинг tool call из OpenAI формата
- Интеграция с deferred prompt completion

commit: Интегрировать агента в prompt handler
- Обновить handlers/prompt.py для использования AgentOrchestrator
- Добавить конфигурацию агента в session/set_config_option
- Обработка ошибок агента gracefully
```

### Фаза 2: Интеграция инструментов

**Deliverables:**
- [ ] ToolRegistry реализация
- [ ] Tool execution engine
- [ ] Интеграция потока разрешений
- [ ] Встроенные инструменты (fs, terminal)

**PR/Commits:**
```
commit: Реализовать ToolRegistry и выполнение
- ToolRegistry с регистрацией инструментов
- ToolExecutor для fs/* и terminal/*
- Обработка session/request_permission
- Встроенные ACP инструменты

commit: Интегрировать tool calls в prompt turn
- Парсинг tool calls из ответа агента
- Запрос разрешений (если режим "ask")
- Выполнение инструментов
- Передача результатов в LLM
```

### Фаза 3: Поддержка фреймворков

**Deliverables:**
- [ ] Langchain адаптер
- [ ] Langgraph адаптер
- [ ] Шаблон кастомного агента
- [ ] Документация расширяемости

**PR/Commits:**
```
commit: Добавить поддержку Langchain
- LangchainAgent адаптер
- Преобразование инструментов Langchain <-> ACP
- Интеграция с существующими инструментами

commit: Добавить поддержку Langgraph
- LanggraphAgent адаптер
- Поддержка граф-базированых workflow
- Сохранение состояния

commit: Документировать разработку кастомных агентов
- Шаблон кастомного агента
- Рекомендации по интеграции
- Примеры реализаций
```

### Фаза 4: Мульти-агентная система

**Deliverables:**
- [ ] MultiAgentOrchestrator реализация
- [ ] Мастер-агент реализация
- [ ] Распределение задач
- [ ] Синтез результатов
- [ ] Документация мульти-агентной системы

**PR/Commits:**
```
commit: Реализовать мульти-агентный оркестратор
- MultiAgentOrchestrator основной класс
- Управление несколькими агентами
- Маршрутизация задач
- Параллельное выполнение

commit: Добавить мастер-агент и координацию
- MasterAgent для разложения задач
- Inter-agent communication
- Синтез результатов от нескольких агентов
- Конфигурация мульти-агентной системы

commit: Добавить управление ресурсами
- ResourceManager для мульти-агентной системы
- Отслеживание использования токенов
- Rate limiting per agent
- Балансирование нагрузки
```

### Фаза 5: Финализация и тестирование

**Deliverables:**
- [ ] Comprehensive unit тесты
- [ ] Integration тесты
- [ ] E2E тесты
- [ ] Обновление документации
- [ ] Примеры и tutorials

**PR/Commits:**
```
commit: Добавить comprehensive тесты
- Unit тесты для агентов
- Unit тесты для провайдеров
- Integration тесты с протоколом
- E2E тесты для tool calls

commit: Обновить документацию
- Guide по интеграции агентов
- Guide по разработке провайдеров
- Документация реестра инструментов
- Справка по конфигурации
```

## 6. Примеры использования различных агентных фреймворков

### 6.1 Встроенный Native Agent

```python
# Конфигурация в session/new
response = await client.session_new(
    session_id="sess_001",
    config={
        "agent": "native",
        "llm_model": "gpt-4",
        "llm_api_key": "sk-...",
        "temperature": 0.7,
    }
)

# Использование
prompt_response = await client.session_prompt(
    session_id="sess_001",
    prompt=[{
        "type": "text",
        "text": "Анализируй этот код на наличие ошибок"
    }],
)
```

### 6.2 Интеграция с Langchain

```python
# Кастомный Langchain агент
from acp_server.agents.langchain_adapter import LangchainAgentAdapter
from langchain.agents import create_openai_functions_agent
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-4")
agent = create_openai_functions_agent(llm, tools=[...])

# Оборачивание в ACP агента
acp_agent = LangchainAgentAdapter(agent)

# Использование в оркестраторе
orchestrator = AgentOrchestrator(
    agent=acp_agent,
    tool_registry=tool_registry,
    ...
)
```

### 6.3 Интеграция с Langgraph

```python
# Workflow на LangGraph
from langgraph.graph import StateGraph

workflow = StateGraph(AgentState)
# ... определение узлов и переходов

# Оборачивание в ACP агента
from acp_server.agents.langgraph_adapter import LanggraphAgentAdapter
acp_agent = LanggraphAgentAdapter(workflow)

# Интеграция с ACP
orchestrator = AgentOrchestrator(
    agent=acp_agent,
    tool_registry=tool_registry,
    ...
)
```

### 6.4 Кастомная реализация агента

```python
# Кастомный агент с enhanced reasoning
from acp_server.protocol.integrations.agent import LLMAgent

class CustomReasoningAgent(LLMAgent):
    """Кастомный агент с улучшенным рассуждением."""
    
    async def process_prompt(
        self,
        session_id: str,
        prompt: list[ContentBlock],
        tools: list[ToolDefinition],
        config: SessionConfig,
    ) -> PromptResponse:
        # Кастомная логика рассуждения
        # Использование специализированного prompting
        # Улучшенный выбор инструментов
        pass

# Регистрация в оркестраторе
custom_agent = CustomReasoningAgent(
    llm_provider=openai_provider,
    reasoning_model="gpt-4",
)

orchestrator = AgentOrchestrator(
    agent=custom_agent,
    ...
)
```

### 6.5 Мульти-агентная система

```python
# Конфигурация мульти-агентной системы
multi_agent_config = {
    "agent": "multi",
    "master_agent": {
        "type": "native",
        "model": "gpt-4",
    },
    "specialist_agents": {
        "code_agent": {
            "type": "native",
            "model": "gpt-4",
            "tools": ["fs:read_file", "fs:write_file", "terminal:execute"],
        },
        "research_agent": {
            "type": "langchain",
            "model": "gpt-3.5-turbo",
            "tools": ["search:*"],
        },
    },
}

# Использование
response = await client.session_new(
    session_id="sess_multi_001",
    config=multi_agent_config
)

result = await client.session_prompt(
    session_id="sess_multi_001",
    prompt="Проанализируй архитектуру проекта и предложи улучшения",
)
```

## 7. Риски и стратегии смягчения

### 7.1 Риск: Превышение Context Window

**Проблема**: История сообщений растет и превышает context window LLM.

**Вероятность**: Высокая при долгих сессиях

**Влияние**: Высокое (ошибка LLM, невозможность обработки)

**Стратегия смягчения**:
- Автоматическое сжатие истории (summarization)
- Ограничение количества сообщений в контексте
- Sliding window с перекрытием для сохранения контекста
- Конфигурируемое поведение через session config

### 7.2 Риск: Бесконечный цикл Tool Calls

**Проблема**: Агент бесконечно запрашивает одни и те же tool calls.

**Вероятность**: Средняя (логическая ошибка в ответе LLM)

**Влияние**: Высокое (зависание, потребление ресурсов)

**Стратегия смягчения**:
- Счетчик tool calls per turn (по умолчанию 10)
- Детектирование дублирующихся tool calls
- Timeout для каждого tool call
- Отмена через session/cancel

### 7.3 Риск: Недоступность LLM провайдера

**Проблема**: OpenAI API или другой LLM провайдер недоступен.

**Вероятность**: Низкая (99.9% uptime обычно)

**Влияние**: Критическое (все сессии блокируются)

**Стратегия смягчения**:
- Retry логика с exponential backoff
- Fallback провайдер (если настроен)
- Graceful error сообщения
- Health checks
- Circuit breaker pattern

### 7.4 Риск: Нарушение прав доступа к инструментам

**Проблема**: LLM пытается выполнить операции без разрешения.

**Вероятность**: Низкая при правильном промптировании

**Влияние**: Среднее (потенциальное нарушение безопасности)

**Стратегия смягчения**:
- Валидация списка инструментов перед отправкой в LLM
- Проверки разрешений перед выполнением
- Audit logging всех операций
- Политики разрешений per session
- Подсказки о доступных инструментах в system prompt

### 7.5 Риск: Несовместимость форматов сообщений

**Проблема**: Новый LLM провайдер имеет другой формат сообщений.

**Вероятность**: Средняя (зависит от провайдера)

**Влияние**: Среднее (потребуется адаптер)

**Стратегия смягчения**:
- Абстрактный формат Message в ACP
- Адаптеры для преобразования форматов
- Документированный интерфейс для провайдеров
- Тесты совместимости

### 7.6 Риск: Несогласованность состояния SessionState

**Проблема**: SessionState становится несогласованным при ошибке.

**Вероятность**: Низкая при правильной обработке

**Влияние**: Высокое (невозможность продолжить сессию)

**Стратегия смягчения**:
- Транзакционные обновления (update all or nothing)
- Валидация состояния после каждого изменения
- Rollback на ошибку
- Механизм восстановления состояния
- Comprehensive logging для отладки

### 7.7 Риск: Взрыв затрат на API

**Проблема**: Неограниченные вызовы к платным LLM API привели к большим счетам.

**Вероятность**: Средняя (без контроля использования)

**Влияние**: Финансовое (потенциально высокое)

**Стратегия смягчения**:
- Rate limiting per API ключ
- Отслеживание использования токенов
- Оценка стоимости per request
- Alerts и лимиты использования
- Конфигурируемые лимиты (max tokens)
- Детальное логирование стоимости

## 8. Мониторинг и метрики

### 8.1 Ключевые метрики

```
Специфичные для агента:
- Среднее время обработки prompt (по модели)
- Процент успешных prompt (%)
- Процент успешных tool call (%)
- Среднее количество tool call per prompt
- Процент ошибок по типам
- Latency LLM API

Специфичные для инструментов:
- Время выполнения инструмента (по инструменту)
- Процент успешного выполнения (%)
- Процент отказов в разрешениях (%)
- Наиболее используемые инструменты

Специфичные для мульти-агентной системы:
- Время задержки при координации агентов
- Эффективность распределения задач
- Overhead синтеза результатов
- Процент конфликтов между агентами

Система-wide:
- Активные сессии агентов
- Всего обработано prompt
- Всего выполнено tool call
- Стоимость API per день
- Процент ошибок по компонентам
```

### 8.2 Стратегия логирования

```
Обработка агентом:
- agent_prompt_started (session_id, prompt_length, available_tools)
- agent_response_received (session_id, stop_reason, tool_calls_count, time)
- agent_tool_call_parsed (session_id, tool_call_id, tool_name)

Выполнение инструмента:
- tool_execution_started (session_id, tool_call_id, tool_name)
- tool_execution_completed (session_id, tool_call_id, status, duration)
- tool_permission_requested (session_id, tool_call_id, options)

Мульти-агентная система:
- multi_agent_decomposition (session_id, subtask_count, agents_involved)
- multi_agent_execution_started (session_id, agent, subtask)
- multi_agent_synthesis_completed (session_id, synthesis_time)

Ошибки:
- agent_error (session_id, error_type, message, traceback)
- provider_error (provider, error_type, message)
- tool_execution_error (session_id, tool_name, error)
```

## 9. Расширение и кастомизация

### 9.1 Добавление нового LLM провайдера

```python
# 1. Создать новый провайдер
class AnthropicLLMProvider(LLMProvider):
    async def create_completion(self, messages, tools=None, **kwargs):
        # Реализация для Anthropic API
        pass

# 2. Зарегистрировать в конфигурации
AVAILABLE_PROVIDERS = {
    "openai": OpenAILLMProvider,
    "anthropic": AnthropicLLMProvider,
}

# 3. Использовать в агенте
agent = NativeAgent(llm_provider=AnthropicLLMProvider(...))
```

### 9.2 Добавление кастомного инструмента

```python
# 1. Определить tool definition
my_tool = ToolDefinition(
    id="custom:analyze_sentiment",
    name="Анализ тональности",
    kind="search",
    inputSchema={...},
)

# 2. Зарегистрировать
tool_registry.register_tool(my_tool)

# 3. Реализовать handler
class SentimentAnalysisTool(ToolImplementation):
    async def execute(self, input: dict) -> dict:
        text = input["text"]
        # Кастомная логика
        return {"sentiment": sentiment_score}

# 4. Зарегистрировать executor
tool_executor.register_tool_handler("custom:analyze_sentiment", handler)
```

### 9.3 Создание адаптера кастомного фреймворка

```python
# Создать адаптер для нового фреймворка
from acp_server.protocol.integrations.agent import LLMAgent

class MyFrameworkAgent(LLMAgent):
    def __init__(self, framework_agent, tool_registry):
        self.framework_agent = framework_agent
        self.tool_registry = tool_registry
    
    async def process_prompt(
        self,
        session_id: str,
        prompt: list[ContentBlock],
        tools: list[ToolDefinition],
        config: SessionConfig,
    ) -> PromptResponse:
        # 1. Преобразовать инструменты в формат фреймворка
        framework_tools = self._convert_tools(tools)
        
        # 2. Преобразовать prompt в формат фреймворка
        framework_prompt = self._convert_prompt(prompt)
        
        # 3. Обработать через фреймворк
        result = await self.framework_agent.process(
            framework_prompt,
            tools=framework_tools,
        )
        
        # 4. Преобразовать результат обратно в ACP формат
        return self._convert_response(result)
```

## 10. Тестирование

### 10.1 Unit тесты

```python
# tests/test_agent_orchestrator.py
async def test_simple_prompt_processing():
    """Тест простой обработки prompt."""
    orchestrator = create_test_orchestrator()
    result = await orchestrator.execute_prompt_turn(...)
    assert result.stop_reason == "end_turn"

# tests/test_tool_registry.py
async def test_tool_execution():
    """Тест выполнения инструмента."""
    registry = ToolRegistry()
    registry.register_tool(read_file_tool)
    result = await registry.execute_tool(...)
    assert result.status == "completed"

# tests/test_multi_agent.py
async def test_task_decomposition():
    """Тест разложения задачи несколькими агентами."""
    orchestrator = create_test_multi_agent_orchestrator()
    result = await orchestrator.execute_prompt_turn(...)
    assert all(subtask.status == "completed")
```

### 10.2 Integration тесты

```python
# tests/test_integration_protocol_agent.py
async def test_session_prompt_with_agent():
    """Тест полного flow: protocol -> agent -> tools."""
    protocol = ACPProtocol(orchestrator=orchestrator)
    response = await protocol.handle(
        ACPMessage.request("session/prompt", {...})
    )
    assert response.response.result.stop_reason
```

### 10.3 E2E тесты

```python
# tests/test_e2e_agent_workflow.py
async def test_agent_with_file_operations():
    """Тест агента с операциями с файлами."""
    # Setup
    client = create_test_client()
    await client.initialize()
    
    # Create session
    session = await client.session_new(agent="native")
    
    # Send prompt that requires file operations
    response = await client.session_prompt(
        session_id=session.session_id,
        prompt="Создай файл и напиши в него 'Привет, мир!'",
    )
    
    # Verify results
    assert response.stop_reason == "end_turn"
    assert file_content == "Привет, мир!"

# E2E тест мульти-агентной системы
async def test_multi_agent_task_decomposition():
    """Тест разложения сложной задачи несколькими агентами."""
    client = create_test_client()
    
    session = await client.session_new(agent="multi")
    
    response = await client.session_prompt(
        session_id=session.session_id,
        prompt="Найди все Python файлы, проанализируй их качество и создай отчет",
    )
    
    assert response.stop_reason == "end_turn"
    assert report_file_exists
```

## 11. Документация и примеры

### 11.1 Структура документации

```
doc/
├── AGENT_INTEGRATION_GUIDE.md        # Быстрый старт
├── AGENT_ARCHITECTURE.md              # Детали архитектуры
├── PROVIDER_DEVELOPMENT.md            # Разработка провайдеров
├── CUSTOM_AGENT_GUIDE.md              # Разработка кастомных агентов
├── TOOL_REGISTRY_GUIDE.md             # Управление инструментами
├── MULTI_AGENT_GUIDE.md               # Мульти-агентная система
├── FRAMEWORK_ADAPTERS.md              # Langchain, Langgraph, etc.
└── examples/
    ├── simple_agent.py                # Минимальный пример
    ├── langchain_agent.py             # Интеграция Langchain
    ├── multi_agent_system.py          # Мульти-агентная система
    ├── custom_reasoning_agent.py      # Кастомная реализация
    └── multi_tool_agent.py            # Сложное использование инструментов
```

### 11.2 Пример быстрого старта

```python
# Минимальный пример использования
import asyncio
from acp_server import ACPServer, NativeAgent, OpenAILLMProvider
from acp_server.tools import ToolRegistry, built_in_tools

async def main():
    # 1. Создать провайдер LLM
    llm_provider = OpenAILLMProvider(api_key="sk-...")
    
    # 2. Создать агента
    agent = NativeAgent(llm_provider=llm_provider)
    
    # 3. Создать реестр инструментов
    tool_registry = ToolRegistry()
    tool_registry.register_tools(built_in_tools.all_tools())
    
    # 4. Запустить сервер
    server = ACPServer(
        host="127.0.0.1",
        port=8080,
        agent=agent,
        tool_registry=tool_registry,
    )
    
    await server.start()

if __name__ == "__main__":
    asyncio.run(main())
```

## 12. Критерии успеха

1. ✅ Агент может обрабатывать простые текстовые запросы
2. ✅ Tool calls из LLM корректно маршрутизируются и выполняются
3. ✅ Permission requests отправляются и обрабатываются
4. ✅ Session/cancel корректно отменяет обработку
5. ✅ Интеграция с популярными агентными фреймворками демонстрируется
6. ✅ Мульти-агентная система функционирует корректно
7. ✅ Все проверки проходят: `make check`
8. ✅ Документация актуальна и полна
9. ✅ Performance тесты показывают приемлемые метрики
10. ✅ Production-ready код с proper error handling

## 13. Версионирование и совместимость

- **Версия API**: 1.0 (соответствует ACP Protocol v1)
- **Python**: 3.12+
- **Зависимости**: Минимальны для базовой функциональности, опциональны для фреймворков
- **Backward Compatibility**: Изменения совместимы с существующей архитектурой
- **Extensibility**: Фреймворки и провайдеры добавляются без изменения core API
