# Диаграммы взаимодействия ACP Client ↔ Server

## Архитектура взаимодействия

```mermaid
graph TB
    subgraph Client["ACP Client"]
        CLI["CLI<br/>acp-client"]
        ACPClient["ACPClient<br/>654 строк"]
        Transport["Transport Layer<br/>WebSocket"]
        Handlers["Handlers<br/>RPC Обработчики"]
        Helpers["Helpers<br/>Утилиты"]
    end
    
    subgraph Network["WebSocket JSON-RPC"]
        WS["Двусторонний<br/>обмен сообщениями"]
    end
    
    subgraph Server["ACP Server"]
        HTTPServer["ACPHttpServer<br/>WebSocket Endpoint"]
        Protocol["ACPProtocol<br/>Диспетчер методов"]
        ServerHandlers["Handlers<br/>auth/session/prompt"]
        Storage["SessionStorage<br/>Хранилище сессий"]
    end
    
    CLI -->|запросы| ACPClient
    ACPClient -->|использует| Transport
    ACPClient -->|использует| Handlers
    ACPClient -->|использует| Helpers
    Transport -->|отправляет| WS
    Handlers -->|обрабатывает| WS
    WS -->|получает| HTTPServer
    HTTPServer -->|парсит| Protocol
    Protocol -->|диспетчеризует| ServerHandlers
    ServerHandlers -->|работает| Storage
    Storage -->|возвращает| ServerHandlers
    ServerHandlers -->|ответ| HTTPServer
    HTTPServer -->|отправляет| WS
    WS -->|получает| Transport
    Transport -->|передает| ACPClient
    ACPClient -->|результат| CLI
```

## Жизненный цикл Client→Server запроса

```mermaid
sequenceDiagram
    participant Client as ACPClient
    participant Transport as Transport<br/>WebSocket
    participant Server as ACPHttpServer
    participant Protocol as ACPProtocol
    participant Handler as Handler<br/>auth/session/etc
    participant Storage as SessionStorage
    
    Client->>Transport: await_ws_response(request)
    Transport->>Server: WebSocket JSON-RPC
    Server->>Protocol: handle(method, params)
    Protocol->>Handler: dispatch to handler
    Handler->>Storage: get/update session
    Storage-->>Handler: return session
    Handler->>Handler: process request
    Handler-->>Protocol: response
    Protocol-->>Server: result
    Server-->>Transport: JSON-RPC response
    Transport-->>Client: parsed result
```

## Обработка Server→Client RPC (обратные запросы)

```mermaid
sequenceDiagram
    participant Server as ACPServer<br/>in session/prompt
    participant Transport as HTTPServer<br/>Update Loop
    participant Client as ACPClient<br/>WebSocket Session
    participant Handlers as Handlers<br/>RPC обработчики
    
    Server->>Transport: yield fs/readTextFile RPC
    Transport->>Client: отправить RPC запрос
    Client->>Handlers: dispatch RPC type
    Handlers->>Handlers: обработать запрос<br/>fs/terminal/permissions
    Handlers-->>Client: return result
    Client-->>Transport: отправить response
    Transport->>Server: receive response
    Server->>Server: continue processing
```

## Полный цикл Session/Prompt с updates

```mermaid
graph LR
    subgraph ClientSide["Client"]
        CP["ACPClient<br/>prompt()"]
    end
    
    subgraph WSConnection["WebSocket"]
        RPC["JSON-RPC<br/>Запрос"]
        Updates["session/update<br/>События"]
        RPC2["RPC Ответ<br/>на запрос"]
    end
    
    subgraph ServerSide["Server"]
        Prompt["session/prompt<br/>handler"]
        Processing["обработка<br/>LLM логика"]
        UpdateStream["update-поток<br/>события"]
    end
    
    CP -->|отправляет| RPC
    RPC -->|передает| Prompt
    Prompt -->|инициирует| Processing
    Processing -->|генерирует| Updates
    Updates -->|отправляет| CP
    Processing -->|финальный результат| RPC2
    RPC2 -->|передает| CP
```

## Типы взаимодействия

### 1. Синхронные запросы (Client→Server)

```mermaid
graph LR
    Client["Client<br/>await request"] -->|1. send JSON-RPC| Server["Server<br/>handle method"]
    Server -->|2. process| Handler["Handler"]
    Handler -->|3. return response| Server
    Server -->|4. send JSON-RPC result| Client["Client<br/>get result"]
```

### 2. Асинхронные события (Server→Client)

```mermaid
graph LR
    Server["Server<br/>session/prompt"] -->|1. yield RPC| Stream["Update Stream<br/>session/update"]
    Stream -->|2. send event| Client["Client<br/>WebSocket Session"]
    Client -->|3. handle event| Handler["Handler"]
    Handler -->|4. process| Response["RPC Response"]
    Response -->|5. send back| Server["Server<br/>continue processing"]
```

## Поток данных в session/prompt

```mermaid
graph TB
    subgraph Init["1. Инициализация"]
        A["Client: session/prompt<br/>request"]
    end
    
    subgraph Processing["2. Обработка на сервере"]
        B["Server: prompt handler"]
        C["LLM обработка"]
        D["Tool call"]
    end
    
    subgraph Updates["3. Updates для клиента"]
        E["session/update<br/>MessageUpdate"]
        F["session/update<br/>ToolCallUpdate"]
        G["session/update<br/>PlanUpdate"]
    end
    
    subgraph RPC["4. Server→Client RPC"]
        H["fs/readTextFile"]
        I["terminal/execute"]
        J["session/request_permission"]
    end
    
    subgraph Response["5. Client обработка"]
        K["Handlers: fs/terminal/permissions"]
        L["Возврат результата"]
    end
    
    subgraph Final["6. Финальный результат"]
        M["Client: получает session/prompt<br/>response"]
    end
    
    A -->|отправляет| B
    B -->|запускает| C
    C -->|создает| D
    D -->|генерирует| E
    E -->|отправляет| H
    F -->|отправляет| I
    G -->|отправляет| J
    H -->|обрабатывает| K
    I -->|обрабатывает| K
    J -->|обрабатывает| K
    K -->|возвращает| L
    L -->|передает серверу| M
```

## Состояния WebSocket сессии

```mermaid
graph TD
    A["CLOSED"] -->|open_ws_session| B["OPENED"]
    B -->|perform_ws_initialize| C["INITIALIZED"]
    C -->|perform_ws_authenticate| D["AUTHENTICATED"]
    D -->|request| E["WAITING"]
    E -->|response received| D
    D -->|handle RPC| F["PROCESSING_RPC"]
    F -->|response sent| D
    D -->|close| A
```

## Взаимодействие модулей Client

```mermaid
graph TB
    subgraph Transport["transport/websocket.py"]
        A["ACPClientWSSession"]
        B["await_ws_response"]
        C["perform_ws_initialize"]
        D["perform_ws_authenticate"]
    end
    
    subgraph Handlers["handlers/"]
        E["permissions.py<br/>build_permission_result"]
        F["filesystem.py<br/>handle_server_fs_request"]
        G["terminal.py<br/>handle_server_terminal_request"]
    end
    
    subgraph Helpers["helpers/"]
        H["auth.py<br/>pick_auth_method_id"]
        I["session.py<br/>extract_tool_call_updates"]
        J["session.py<br/>extract_plan_updates"]
    end
    
    subgraph Core["client.py"]
        K["ACPClient"]
        L["_request_ws"]
        M["initialize"]
        N["authenticate"]
        O["prompt"]
    end
    
    K -->|использует| A
    K -->|использует| B
    K -->|использует| C
    K -->|использует| D
    L -->|вызывает| B
    L -->|обрабатывает RPC через| E
    L -->|обрабатывает RPC через| F
    L -->|обрабатывает RPC через| G
    M -->|использует| H
    M -->|использует| C
    N -->|использует| D
    O -->|использует| L
    O -->|парсит обновления через| I
    O -->|парсит обновления через| J
```

## Протокол обмена сообщениями

### Инициализация (Initialize)

```mermaid
sequenceDiagram
    participant Client
    participant Server
    
    Client->>Server: initialize (clientCapabilities)
    activate Server
    Server->>Server: create session
    Server-->>Client: initialize response
    deactivate Server
    Note over Client,Server: Теперь можно вызывать session/* методы
```

### Аутентификация (Authenticate)

```mermaid
sequenceDiagram
    participant Client
    participant Server
    
    Client->>Server: authenticate (authMethodId, params)
    activate Server
    Server->>Server: validate credentials
    Server-->>Client: authenticate response (status)
    deactivate Server
    Note over Client,Server: Если успешно, можно использовать все методы
```

### Создание сессии (Session/New)

```mermaid
sequenceDiagram
    participant Client
    participant Server
    
    Client->>Server: session/new (model, tools, config)
    activate Server
    Server->>Server: create new session
    Server-->>Client: session/new response (sessionId)
    deactivate Server
```

### Prompt Turn (Session/Prompt)

```mermaid
sequenceDiagram
    participant Client
    participant Server
    participant Update Stream
    
    Client->>Server: session/prompt (messages, tools)
    activate Server
    Server->>Server: LLM processing
    loop Асинхронные RPC запросы
        Server->>Update Stream: session/update
        Update Stream->>Client: RPC (fs/terminal/permissions)
        activate Client
        Client->>Client: handle RPC
        Client-->>Update Stream: RPC response
        deactivate Client
        Update Stream->>Server: RPC response
        Server->>Server: continue processing
    end
    Server-->>Client: session/prompt response (finalResult)
    deactivate Server
```

## Обработка ошибок и исключений

```mermaid
graph TB
    A["Client отправляет<br/>запрос"] -->|сетевая ошибка| B["Transport Error"]
    A -->|парсинг ошибка| C["Parse Error"]
    A -->|валидация ошибка| D["Validation Error"]
    A -->|сервер ошибка| E["Server Error"]
    
    B -->|retry| A
    C -->|логирование| F["Error Logged"]
    D -->|логирование| F
    E -->|обработка| G["Error Handler"]
    
    G -->|возвращает ошибку| A
    F -->|fail| H["Exception"]
```

## Performance: Асинхронность и параллелизм

```mermaid
graph LR
    subgraph Async["Асинхронные операции"]
        A["WebSocket отправка"]
        B["WebSocket получение"]
        C["LLM обработка"]
        D["File I/O"]
        E["Terminal I/O"]
    end
    
    subgraph NonBlocking["Non-blocking"]
        F["Client ждет<br/>не блокируя"]
        G["Server обрабатывает<br/>LLM запросы"]
        H["Update stream<br/>асинхронный"]
    end
    
    A -->|async| F
    B -->|async| F
    C -->|async| G
    D -->|async| G
    E -->|async| G
    G -->|async| H
```
