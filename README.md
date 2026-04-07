# ACP Protocol Workspace

Репозиторий разделен на два независимых Python-проекта:

- `acp-server` — сервер ACP (TCP + HTTP/WebSocket)
- `acp-client` — клиент ACP (TCP + HTTP/WebSocket)

Каждый проект имеет собственные:

- `pyproject.toml`
- `uv.lock`
- тесты
- команды запуска через `uv run`

## Быстрый старт

### 1) Сервер

```bash
cd acp-server
uv sync
uv run acp-server --transport tcp --host 127.0.0.1 --port 8765
```

### 2) Клиент

```bash
cd acp-client
uv sync
uv run acp-client --transport tcp --host 127.0.0.1 --port 8765 --method ping
```
