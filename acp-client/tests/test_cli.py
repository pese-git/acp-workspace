from __future__ import annotations

import json
from typing import Any

from acp_client.cli import run_client
from acp_client.messages import ACPMessage, SessionUpdateNotification


def test_run_client_show_updates_for_session_load(monkeypatch, capsys) -> None:
    async def fake_load_session_parsed(
        self,
        *,
        session_id: str,
        cwd: str,
        mcp_servers: list[dict[str, Any]] | None = None,
    ) -> tuple[ACPMessage, list[SessionUpdateNotification]]:
        # Возвращаем минимальный валидный ответ и одно типизированное replay-событие.
        response = ACPMessage(id="req_1", result=None)
        updates = [
            SessionUpdateNotification.model_validate(
                {
                    "jsonrpc": "2.0",
                    "method": "session/update",
                    "params": {
                        "sessionId": session_id,
                        "update": {"sessionUpdate": "agent_message_chunk"},
                    },
                }
            )
        ]
        return response, updates

    monkeypatch.setattr("acp_client.cli.ACPClient.load_session_parsed", fake_load_session_parsed)
    monkeypatch.setattr(
        "sys.argv",
        [
            "acp-client",
            "--method",
            "session/load",
            "--params",
            '{"sessionId":"sess_1","cwd":"/tmp","mcpServers":[]}',
            "--show-updates",
        ],
    )

    run_client()

    output = capsys.readouterr().out
    payload = json.loads(output)
    assert payload["response"]["id"] == "req_1"
    assert payload["response"]["result"] is None
    assert payload["updates"][0]["method"] == "session/update"


def test_run_client_starts_tui_mode(monkeypatch) -> None:
    recorded: dict[str, object] = {}

    def fake_run_tui_app(*, host: str, port: int) -> None:
        recorded["host"] = host
        recorded["port"] = port

    monkeypatch.setattr("acp_client.cli.run_tui_app", fake_run_tui_app)
    monkeypatch.setattr(
        "sys.argv",
        [
            "acp-client",
            "--tui",
            "--host",
            "127.0.0.9",
            "--port",
            "9900",
        ],
    )

    run_client()

    assert recorded == {"host": "127.0.0.9", "port": 9900}
