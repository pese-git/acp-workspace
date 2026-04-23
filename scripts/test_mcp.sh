#!/bin/bash
# =============================================================================
# test_mcp.sh — скрипт для ручного тестирования MCP интеграции в ACP протоколе
# =============================================================================
# Использование:
#   ./scripts/test_mcp.sh [путь_к_MCP_серверу]
#
# Переменные окружения:
#   ACP_HOST     — хост ACP сервера (по умолчанию: 127.0.0.1)
#   ACP_PORT     — порт ACP сервера (по умолчанию: 8080)
#   MCP_COMMAND  — команда запуска MCP сервера (по умолчанию: npx)
#   MCP_TEST_DIR — рабочая директория для тестов (по умолчанию: /tmp/mcp-test)
# =============================================================================

set -e

# ─────────────────────────────────────────────────────────────────────────────
# Конфигурация
# ─────────────────────────────────────────────────────────────────────────────

# Настройки ACP сервера
HOST="${ACP_HOST:-127.0.0.1}"
PORT="${ACP_PORT:-8080}"
WS_URL="ws://${HOST}:${PORT}/acp/ws"

# Настройки MCP сервера
MCP_COMMAND="${MCP_COMMAND:-npx}"
MCP_TEST_DIR="${MCP_TEST_DIR:-/tmp/mcp-test}"

# Путь к MCP серверу (может быть передан как аргумент)
MCP_SERVER_PATH="${1:-}"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ─────────────────────────────────────────────────────────────────────────────
# Вспомогательные функции
# ─────────────────────────────────────────────────────────────────────────────

# Выводит информационное сообщение
info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# Выводит сообщение об успехе
success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

# Выводит предупреждение
warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Выводит ошибку и завершает скрипт
error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
    exit 1
}

# Проверяет наличие утилиты
check_command() {
    if ! command -v "$1" &> /dev/null; then
        return 1
    fi
    return 0
}

# ─────────────────────────────────────────────────────────────────────────────
# Проверка зависимостей
# ─────────────────────────────────────────────────────────────────────────────

info "Проверка зависимостей..."

# Проверяем наличие websocat
if ! check_command websocat; then
    error "websocat не найден. Установите его:
    - macOS: brew install websocat
    - Linux: cargo install websocat
    - или скачайте с https://github.com/vi/websocat"
fi

success "websocat найден: $(which websocat)"

# Создаём тестовую директорию, если не существует
if [ ! -d "$MCP_TEST_DIR" ]; then
    info "Создание тестовой директории: $MCP_TEST_DIR"
    mkdir -p "$MCP_TEST_DIR"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Формирование JSON сообщений (согласно ACP протоколу)
# ─────────────────────────────────────────────────────────────────────────────

# Сообщение initialize (02-Initialization.md)
# Согласно протоколу, клиент должен отправить:
# - protocolVersion: версия протокола (целое число)
# - clientCapabilities: поддерживаемые возможности клиента
# - clientInfo: информация о клиенте (name, title, version)
INIT_MSG=$(cat <<EOF
{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":1,"clientCapabilities":{"fs":{"readTextFile":true,"writeTextFile":true},"terminal":true},"clientInfo":{"name":"test-mcp-client","title":"MCP Test Client","version":"1.0.0"}}}
EOF
)

# Формируем конфигурацию MCP сервера в зависимости от наличия пути
if [ -n "$MCP_SERVER_PATH" ]; then
    # Используем указанный путь к MCP серверу
    MCP_CONFIG=$(cat <<EOF
[{"name":"filesystem","command":"$MCP_SERVER_PATH","args":["$MCP_TEST_DIR"],"env":[]}]
EOF
)
else
    # Используем npx с @modelcontextprotocol/server-filesystem (стандартный MCP сервер)
    MCP_CONFIG=$(cat <<EOF
[{"name":"filesystem","command":"$MCP_COMMAND","args":["-y","@modelcontextprotocol/server-filesystem","$MCP_TEST_DIR"],"env":[]}]
EOF
)
fi

# Сообщение session/new (03-Session Setup.md)
# Согласно протоколу, параметры:
# - cwd: рабочая директория (абсолютный путь)
# - mcpServers: список MCP серверов для подключения
SESSION_MSG=$(cat <<EOF
{"jsonrpc":"2.0","id":1,"method":"session/new","params":{"cwd":"$MCP_TEST_DIR","mcpServers":$MCP_CONFIG}}
EOF
)

# Примечание: методы session/mcp/* определены в handlers/mcp.py, но пока
# не зарегистрированы в core.py. Для полного тестирования MCP используйте
# интерактивный режим или TUI клиент, где можно отправить session/prompt
# с sessionId из ответа session/new.

# ─────────────────────────────────────────────────────────────────────────────
# Вывод конфигурации
# ─────────────────────────────────────────────────────────────────────────────

echo ""
echo "════════════════════════════════════════════════════════════════════════════"
echo "  MCP Integration Test — ACP Protocol"
echo "════════════════════════════════════════════════════════════════════════════"
echo ""
info "Конфигурация:"
echo "  ACP сервер:     $WS_URL"
echo "  MCP команда:    $MCP_COMMAND"
echo "  Тестовая папка: $MCP_TEST_DIR"
if [ -n "$MCP_SERVER_PATH" ]; then
    echo "  MCP сервер:     $MCP_SERVER_PATH"
else
    echo "  MCP сервер:     @modelcontextprotocol/server-filesystem (via npx)"
fi
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# Выполнение тестов
# ─────────────────────────────────────────────────────────────────────────────

info "Отправляемые сообщения:"
echo ""
echo -e "${YELLOW}1. Initialize:${NC}"
echo "   $INIT_MSG" | head -c 200
echo "..."
echo ""
echo -e "${YELLOW}2. Session/new:${NC}"
echo "   $SESSION_MSG" | head -c 200
echo "..."
echo ""
info "Для отправки session/prompt нужен sessionId из ответа session/new"
echo ""

info "Подключение к WebSocket: $WS_URL"
echo "────────────────────────────────────────────────────────────────────────────"
echo ""

# Выполняем подключение и отправку сообщений
# - Отправляем initialize, ждём 1 сек
# - Отправляем session/new, ждём 5 сек (для инициализации MCP сервера)
# - Держим соединение открытым для получения ответов
#
# Примечание: для отправки session/prompt нужен sessionId из ответа session/new.
# Для полного теста MCP используйте интерактивный режим или TUI клиент.
(
    echo "$INIT_MSG"
    sleep 1
    echo "$SESSION_MSG"
    sleep 5  # Ожидание запуска и инициализации MCP сервера
    # Дополнительное время для просмотра ответов
    sleep 10
) | websocat "$WS_URL" 2>&1

# Проверяем код возврата
EXIT_CODE=$?
echo ""
echo "────────────────────────────────────────────────────────────────────────────"

if [ $EXIT_CODE -eq 0 ]; then
    success "Тест завершён"
else
    warn "websocat завершился с кодом: $EXIT_CODE"
fi

echo ""
echo "════════════════════════════════════════════════════════════════════════════"
