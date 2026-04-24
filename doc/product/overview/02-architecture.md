# Архитектура CodeLab

> Обзор архитектуры системы и взаимодействия компонентов.

## Общая архитектура

CodeLab реализует клиент-серверную архитектуру, определённую [Agent Client Protocol (ACP)](../../Agent%20Client%20Protocol/get-started/02-Architecture.md).

```mermaid
graph TB
    subgraph "Client Layer"
        TUI[TUI Client<br/>Textual]
        WebUI[Web UI<br/>Browser]
    end
    
    subgraph "Transport"
        WS[WebSocket<br/>JSON-RPC 2.0]
    end
    
    subgraph "Server Layer"
        Protocol[ACP Protocol<br/>Handler]
        Session[Session<br/>Manager]
        Agent[LLM Agent<br/>Orchestrator]
        Tools[Tool<br/>Registry]
    end
    
    subgraph "External"
        LLM[LLM Provider<br/>OpenAI/Anthropic]
        MCP[MCP Servers]
    end
    
    TUI --> WS
    WebUI --> WS
    WS --> Protocol
    Protocol --> Session
    Session --> Agent
    Agent --> Tools
    Agent --> LLM
    Tools --> MCP
```

## Компоненты системы

### Клиент (Client)

Клиент предоставляет пользовательский интерфейс и обрабатывает запросы сервера:

```mermaid
graph LR
    subgraph "TUI Client"
        UI[UI Components]
        VM[ViewModels<br/>MVVM]
        UC[Use Cases]
        Transport[Transport<br/>Layer]
    end
    
    UI --> VM
    VM --> UC
    UC --> Transport
```

**Слои клиента (Clean Architecture):**
- **Presentation** — UI компоненты (Textual widgets)
- **ViewModels** — логика представления (MVVM паттерн)
- **Application** — use cases, state machine
- **Infrastructure** — транспорт, DI, handlers

### Сервер (Server)

Сервер содержит AI-агента и обрабатывает протокол ACP:

```mermaid
graph TB
    subgraph "ACP Server"
        HTTP[HTTP/WebSocket<br/>Server]
        Protocol[Protocol<br/>Dispatcher]
        
        subgraph "Handlers"
            Auth[Auth]
            Session[Session]
            Prompt[Prompt]
            Perm[Permissions]
        end
        
        subgraph "Agent"
            Orch[Orchestrator]
            LLM[LLM Provider]
            ToolReg[Tool Registry]
        end
        
        Storage[(Session<br/>Storage)]
    end
    
    HTTP --> Protocol
    Protocol --> Auth
    Protocol --> Session
    Protocol --> Prompt
    Protocol --> Perm
    Session --> Storage
    Prompt --> Orch
    Orch --> LLM
    Orch --> ToolReg
```

## Протокол ACP

Взаимодействие происходит через JSON-RPC 2.0:

```mermaid
sequenceDiagram
    participant C as Client
    participant S as Server
    participant A as Agent (LLM)
    
    Note over C,S: Инициализация
    C->>S: initialize
    S-->>C: capabilities
    
    Note over C,S: Сессия
    C->>S: session/new
    S-->>C: session_id
    
    Note over C,S: Prompt Turn
    C->>S: session/prompt
    
    loop Agent работает
        S->>A: LLM запрос
        A-->>S: tool_call
        S-->>C: notification (tool_call)
        S->>C: client/request_permission
        C-->>S: permission response
        S-->>C: notification (result)
    end
    
    S-->>C: prompt/finished
```

## Потоки данных

### Prompt Turn

Цикл обработки пользовательского запроса:

```mermaid
flowchart TD
    A[User Prompt] --> B[session/prompt]
    B --> C{Agent Planning}
    C --> D[Generate Plan]
    D --> E{Execute Tools}
    
    E --> F[Tool Call]
    F --> G{Need Permission?}
    G -->|Yes| H[Request Permission]
    H --> I{User Decision}
    I -->|Allow| J[Execute]
    I -->|Deny| K[Skip]
    G -->|No| J
    
    J --> L[Tool Result]
    K --> L
    L --> M{More Tools?}
    M -->|Yes| E
    M -->|No| N[Final Response]
    N --> O[prompt/finished]
```

### Система разрешений

```mermaid
flowchart LR
    subgraph "Permission Flow"
        Tool[Tool Call] --> Check{Check Policy}
        Check -->|Auto-Allow| Execute[Execute]
        Check -->|Auto-Deny| Skip[Skip]
        Check -->|Ask| Request[Request<br/>Permission]
        Request --> User{User}
        User -->|Allow| Execute
        User -->|Allow All| Policy[Update<br/>Policy]
        Policy --> Execute
        User -->|Deny| Skip
    end
```

## Хранение данных

### Структура сессий

```mermaid
erDiagram
    SESSION ||--o{ MESSAGE : contains
    SESSION ||--o{ TOOL_CALL : has
    SESSION {
        string id PK
        string name
        datetime created_at
        json config
        json context
    }
    MESSAGE {
        string id PK
        string session_id FK
        string role
        json content
        datetime timestamp
    }
    TOOL_CALL {
        string id PK
        string session_id FK
        string tool_name
        json arguments
        json result
        string status
    }
```

## Директории проекта

```
codelab/src/codelab/
├── shared/              # Общие модули
│   ├── messages.py      # JSON-RPC сообщения
│   ├── logging.py       # Структурированное логирование
│   └── content/         # Типы контента ACP
│
├── server/              # Серверная часть
│   ├── protocol/        # ACP протокол
│   ├── agent/           # LLM агент
│   ├── tools/           # Инструменты
│   ├── storage/         # Хранилище сессий
│   └── mcp/             # MCP интеграция
│
└── client/              # Клиентская часть
    ├── domain/          # Domain Layer
    ├── application/     # Application Layer
    ├── infrastructure/  # Infrastructure Layer
    ├── presentation/    # ViewModels (MVVM)
    └── tui/             # TUI компоненты
```

## См. также

- [Введение](01-introduction.md) — общая информация о CodeLab
- [Сценарии использования](03-use-cases.md) — примеры применения
- [Спецификация ACP](../../Agent%20Client%20Protocol/protocol/01-Overview.md) — детали протокола
