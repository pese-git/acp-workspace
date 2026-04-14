# Конфигурация ACP сервера

Сервер поддерживает гибкую систему конфигурации через переменные окружения, .env файл и CLI аргументы.

## 📋 Переменные окружения

### LLM Провайдер

| Переменная | Значение | По умолчанию | Описание |
|-----------|----------|--------------|---------|
| `ACP_LLM_PROVIDER` | `openai` \| `mock` | `mock` | Тип LLM провайдера |
| `ACP_LLM_API_KEY` | `string` | - | API ключ для OpenAI/совместимого сервиса |
| `ACP_LLM_BASE_URL` | `string` | - | Base URL для LLM (опционально, для совместимых сервисов) |
| `ACP_LLM_MODEL` | `string` | `gpt-4o` | Модель LLM |
| `ACP_LLM_TEMPERATURE` | `0.0-1.0` | `0.7` | Temperature для генерации |
| `ACP_LLM_MAX_TOKENS` | `integer` | `8192` | Максимум токенов в ответе |

### Агент

| Переменная | Значение | Описание |
|-----------|----------|---------|
| `ACP_SYSTEM_PROMPT` | `string` | Системный промпт для агента |

## 🎯 Приоритеты конфигурации

Система использует следующие приоритеты (от высшего к низшему):

1. **CLI аргументы** - самый высокий приоритет
2. **Переменные окружения** - переопределяют .env
3. **.env файл** - базовая конфигурация
4. **Значения по умолчанию** - самый низкий приоритет

```
CLI arg --llm-model gpt-4-turbo
    ↓
Переопределяет Environment: ACP_LLM_MODEL=gpt-4o
    ↓
Переопределяет .env: ACP_LLM_MODEL=gpt-3.5-turbo
    ↓
Используется дефолт: gpt-4o
```

## 🚀 Примеры использования

### Вариант 1: Только .env файл (Development)

```bash
# .env файл
ACP_LLM_PROVIDER=openai
ACP_LLM_API_KEY=sk-...
ACP_LLM_MODEL=gpt-4o
ACP_LLM_TEMPERATURE=0.7

# Запуск сервера
acp-server --port 8765
```

### Вариант 2: Только переменные окружения (Production)

```bash
export ACP_LLM_PROVIDER=openai
export ACP_LLM_API_KEY=sk-...
export ACP_LLM_MODEL=gpt-4o

acp-server --port 8765
```

### Вариант 3: Смешанный вариант (Development с переопределениями)

```bash
# .env содержит базовую конфигурацию
# ACP_LLM_PROVIDER=mock
# ACP_LLM_MODEL=gpt-4o

# Переменная окружения переопределяет одно значение
export ACP_LLM_TEMPERATURE=0.95

# CLI аргумент переопределяет еще одно
acp-server \
  --port 8765 \
  --llm-provider openai \
  --llm-api-key sk-... \
  --llm-model gpt-4-turbo
```

Результат:
- `provider`: `openai` (из CLI)
- `model`: `gpt-4-turbo` (из CLI)
- `api_key`: `sk-...` (из CLI)
- `temperature`: `0.95` (из Environment)
- `max_tokens`: `8192` (дефолт)

### Вариант 4: Только CLI (для тестирования)

```bash
acp-server \
  --host 127.0.0.1 \
  --port 8765 \
  --llm-provider openai \
  --llm-model gpt-4-turbo \
  --llm-api-key sk-... \
  --llm-temperature 0.9 \
  --system-prompt "Your custom prompt"
```

### Вариант 5: Программно

```python
from acp_server.config import AppConfig
from acp_server.http_server import ACPHttpServer
from dotenv import load_dotenv

# Загружаем переменные из .env
load_dotenv()

# Создаем конфиг из переменных окружения
config = AppConfig()

# Переопределяем отдельные значения если нужно
config.llm.temperature = 0.95
config.llm.model = "gpt-4-turbo"

# Используем конфиг при создании сервера
server = ACPHttpServer(
    host="127.0.0.1",
    port=8765,
    config=config
)

import asyncio
asyncio.run(server.run())
```

## 🔧 Docker и контейнеризация

### Docker с .env файлом

```dockerfile
FROM python:3.12
WORKDIR /app
COPY . .
RUN pip install -e .

# Копируем .env в контейнер
COPY .env .env

CMD ["acp-server", "--host", "0.0.0.0", "--port", "8765"]
```

### Docker с переменными окружения

```dockerfile
FROM python:3.12
WORKDIR /app
COPY . .
RUN pip install -e .

CMD ["acp-server", "--host", "0.0.0.0", "--port", "8765"]
```

```bash
# Запуск с переменными окружения
docker run \
  -e ACP_LLM_PROVIDER=openai \
  -e ACP_LLM_API_KEY=sk-... \
  -e ACP_LLM_MODEL=gpt-4-turbo \
  -p 8765:8765 \
  acp-server
```

## 🔐 Безопасность

- **Никогда не коммитьте .env файл в git** - используйте `.env.example` как шаблон
- **API ключи должны быть в .env или переменных окружения**, не в CLI аргументах
- **Для production используйте переменные окружения**, не .env файлы
- **Используйте `.gitignore`** для исключения .env файла

## 📝 CLI аргументы

```bash
acp-server --help

positional arguments:
  (none)

optional arguments:
  --host HOST                   IP адрес для прослушивания (127.0.0.1)
  --port PORT                   Порт для прослушивания (8765)
  --require-auth               Требовать authenticate перед session/new
  --auth-api-key KEY           API ключ для аутентификации
  --log-level {DEBUG,INFO,WARNING,ERROR}
  --log-json                   Использовать JSON формат логов
  --storage {memory|json:/path}
                              Storage backend (memory или json:/path)
  
  # LLM конфигурация
  --llm-provider {openai|mock} Тип LLM провайдера
  --llm-model MODEL            Модель LLM
  --llm-api-key KEY            API ключ для LLM
  --llm-base-url URL           Base URL для LLM
  --llm-temperature TEMP       Temperature (0.0-1.0)
  --llm-max-tokens TOKENS      Максимум токенов
  
  # Агент
  --system-prompt PROMPT       Системный промпт
```

## ⚙️ Файл конфигурации (.env.example)

```bash
# === LLM Провайдер ===
ACP_LLM_PROVIDER=openai
ACP_LLM_API_KEY=sk-your-api-key-here
ACP_LLM_BASE_URL=https://api.openai.com/v1
ACP_LLM_MODEL=gpt-4o
ACP_LLM_TEMPERATURE=0.7
ACP_LLM_MAX_TOKENS=8192

# === Агент ===
ACP_SYSTEM_PROMPT=Ты помощник, который помогает пользователю выполнять различные задачи.
```

## 🔍 Проверка конфигурации

Проверить текущую конфигурацию можно программно:

```python
from acp_server.config import AppConfig
from dotenv import load_dotenv

load_dotenv()
config = AppConfig()

print(f"Provider: {config.llm.provider}")
print(f"Model: {config.llm.model}")
print(f"Temperature: {config.llm.temperature}")
print(f"System Prompt: {config.agent.system_prompt}")
```

## 📚 Дополнительно

- Все параметры типизированы через Pydantic
- Автоматическая валидация типов и значений
- Поддержка множественных способов конфигурации
- Гибкие приоритеты для гибридных подходов
