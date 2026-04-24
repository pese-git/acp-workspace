# Переменные окружения

Полный справочник переменных окружения CodeLab.

## LLM провайдер

### CODELAB_LLM_PROVIDER

Выбор LLM провайдера.

| Значение | Описание |
|----------|----------|
| `openai` | OpenAI API (GPT-4, GPT-4o) |
| `anthropic` | Anthropic API (Claude) |
| `mock` | Тестовый провайдер без реального LLM |

**По умолчанию:** `mock`

```bash
export CODELAB_LLM_PROVIDER=openai
```

### CODELAB_LLM_API_KEY

API ключ для выбранного LLM провайдера.

- Для OpenAI: ключ вида `sk-...`
- Для Anthropic: ключ вида `sk-ant-...`

**Обязателен** для `openai` и `anthropic` провайдеров.

```bash
export CODELAB_LLM_API_KEY=sk-your-key-here
```

### CODELAB_LLM_BASE_URL

Кастомный базовый URL API. Используется для:
- OpenRouter
- Azure OpenAI
- Локальных LLM серверов (vLLM, Ollama с OpenAI-совместимым API)

**По умолчанию:** стандартный URL провайдера

```bash
# OpenRouter
export CODELAB_LLM_BASE_URL=https://openrouter.ai/api/v1

# Azure OpenAI
export CODELAB_LLM_BASE_URL=https://your-resource.openai.azure.com/

# Локальный vLLM
export CODELAB_LLM_BASE_URL=http://localhost:8000/v1
```

### CODELAB_LLM_MODEL

Название модели LLM.

**По умолчанию:** `gpt-4o`

```bash
# OpenAI модели
export CODELAB_LLM_MODEL=gpt-4o
export CODELAB_LLM_MODEL=gpt-4-turbo

# Anthropic модели
export CODELAB_LLM_MODEL=claude-3-opus-20240229
export CODELAB_LLM_MODEL=claude-3-sonnet-20240229

# OpenRouter (с префиксом провайдера)
export CODELAB_LLM_MODEL=anthropic/claude-3-opus
```

### CODELAB_LLM_TEMPERATURE

Параметр "творчества" модели. Значения от 0.0 до 1.0.

- `0.0` — детерминированные ответы
- `0.7` — баланс точности и творчества
- `1.0` — максимальная вариативность

**По умолчанию:** `0.7`

```bash
export CODELAB_LLM_TEMPERATURE=0.3
```

### CODELAB_LLM_MAX_TOKENS

Максимальное количество токенов в ответе модели.

**По умолчанию:** `8192`

```bash
export CODELAB_LLM_MAX_TOKENS=16384
```

## Сервер

### CODELAB_PORT

Порт WebSocket сервера.

**По умолчанию:** `8765`

```bash
export CODELAB_PORT=4096
```

### CODELAB_HOST

Адрес привязки сервера.

| Значение | Описание |
|----------|----------|
| `127.0.0.1` | Только локальные подключения |
| `0.0.0.0` | Все сетевые интерфейсы |

**По умолчанию:** `127.0.0.1`

```bash
# Доступ из сети
export CODELAB_HOST=0.0.0.0
```

### CODELAB_HOME

Путь к домашней директории приложения.

**По умолчанию:** `~/.codelab`

```bash
export CODELAB_HOME=/opt/codelab/data
```

## Логирование

### CODELAB_LOG_LEVEL

Уровень детализации логов.

| Значение | Описание |
|----------|----------|
| `DEBUG` | Все сообщения, включая отладочные |
| `INFO` | Информационные сообщения и выше |
| `WARNING` | Предупреждения и ошибки |
| `ERROR` | Только ошибки |

**По умолчанию:** `INFO`

```bash
export CODELAB_LOG_LEVEL=DEBUG
```

## Сводная таблица

| Переменная | По умолчанию | Обязательная |
|------------|--------------|--------------|
| `CODELAB_LLM_PROVIDER` | `mock` | Нет |
| `CODELAB_LLM_API_KEY` | - | Да* |
| `CODELAB_LLM_BASE_URL` | - | Нет |
| `CODELAB_LLM_MODEL` | `gpt-4o` | Нет |
| `CODELAB_LLM_TEMPERATURE` | `0.7` | Нет |
| `CODELAB_LLM_MAX_TOKENS` | `8192` | Нет |
| `CODELAB_PORT` | `8765` | Нет |
| `CODELAB_HOST` | `127.0.0.1` | Нет |
| `CODELAB_HOME` | `~/.codelab` | Нет |
| `CODELAB_LOG_LEVEL` | `INFO` | Нет |

\* Обязательна для провайдеров `openai` и `anthropic`

## Пример .env файла

```env
# CodeLab Configuration
# =====================

# LLM провайдер
CODELAB_LLM_PROVIDER=openai
CODELAB_LLM_API_KEY=sk-your-api-key-here
CODELAB_LLM_MODEL=gpt-4o
CODELAB_LLM_TEMPERATURE=0.7
CODELAB_LLM_MAX_TOKENS=8192

# Сервер
CODELAB_PORT=8765
CODELAB_HOST=127.0.0.1

# Логирование
CODELAB_LOG_LEVEL=INFO
```

## См. также

- [Конфигурация](02-configuration.md) — общий справочник конфигурации
- [CLI команды](01-cli.md) — параметры командной строки
