.PHONY: server-sync server-check client-sync client-check check \
	run-server-http run-server-ws ping-http ping-ws

HOST ?= 127.0.0.1
HTTP_PORT ?= 8080

server-sync:
	uv sync --directory acp-server

server-check:
	uv run --directory acp-server ruff check .
	uv run --directory acp-server ty check
	uv run --directory acp-server python -m pytest

client-sync:
	uv sync --directory acp-client

client-check:
	uv run --directory acp-client ruff check .
	uv run --directory acp-client ty check
	uv run --directory acp-client python -m pytest

check: server-check client-check

run-server-http:
	uv run --directory acp-server acp-server --transport http --host $(HOST) --port $(HTTP_PORT)

run-server-ws:
	uv run --directory acp-server acp-server --transport ws --host $(HOST) --port $(HTTP_PORT)

ping-http:
	uv run --directory acp-client acp-client --transport http --host $(HOST) --port $(HTTP_PORT) --method ping

ping-ws:
	uv run --directory acp-client acp-client --transport ws --host $(HOST) --port $(HTTP_PORT) --method ping
