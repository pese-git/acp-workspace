.PHONY: sync check check-client check-server check-tui lint typecheck test \
	serve connect

HOST ?= 127.0.0.1
PORT ?= 8765

# === Основные команды ===

sync:
	uv sync --directory codelab --extra dev

check: lint typecheck test

lint:
	uv run --directory codelab ruff check .

typecheck:
	uv run --directory codelab ty check

test:
	uv run --directory codelab python -m pytest

# === Частичные проверки ===

check-client:
	uv run --directory codelab python -m pytest tests/client/

check-server:
	uv run --directory codelab python -m pytest tests/server/

check-tui:
	uv run --directory codelab ruff check src/codelab/client/tui tests/client/test_tui_*.py
	uv run --directory codelab python -m pytest tests/client/test_tui_*.py

# === Запуск ===

serve:
	uv run --directory codelab codelab serve --host $(HOST) --port $(PORT)

connect:
	uv run --directory codelab codelab connect --host $(HOST) --port $(PORT)

# === Deprecated (для обратной совместимости, будут удалены) ===

server-sync:
	@echo "DEPRECATED: use 'make sync' instead"
	uv sync --directory codelab --extra dev

server-check:
	@echo "DEPRECATED: use 'make check-server' instead"
	uv run --directory codelab python -m pytest tests/server/

client-sync:
	@echo "DEPRECATED: use 'make sync' instead"
	uv sync --directory codelab --extra dev

client-check:
	@echo "DEPRECATED: use 'make check-client' instead"
	uv run --directory codelab python -m pytest tests/client/

run-server-ws:
	@echo "DEPRECATED: use 'make serve' instead"
	uv run --directory codelab codelab serve --host $(HOST) --port $(PORT)
