"""Тесты CLI entrypoint-ов acp-client и acp-client-tui."""

from __future__ import annotations


def test_tui_main_forwards_history_dir(monkeypatch, tmp_path) -> None:
    """acp-client-tui пробрасывает --history-dir в run_tui_app."""
    from acp_client.tui import __main__ as tui_main

    captured: dict[str, dict[str, object]] = {}
    history_dir = tmp_path / "history"

    monkeypatch.setattr(
        "acp_client.tui.__main__.setup_logging",
        lambda **kwargs: captured.setdefault("logging", kwargs),
    )
    monkeypatch.setattr(
        "acp_client.tui.__main__.run_tui_app",
        lambda **kwargs: captured.setdefault("run", kwargs),
    )
    monkeypatch.setattr(
        "sys.argv",
        ["acp-client-tui", "--history-dir", str(history_dir)],
    )

    tui_main.main()

    assert captured["run"]["history_dir"] == str(history_dir)


def test_cli_forwards_history_dir(monkeypatch, tmp_path) -> None:
    """acp-client пробрасывает --history-dir в lazy run_tui_app."""
    from acp_client import cli as client_cli

    captured: dict[str, dict[str, object]] = {}
    history_dir = tmp_path / "history"

    monkeypatch.setattr(
        "acp_client.cli.setup_logging",
        lambda **kwargs: captured.setdefault("logging", kwargs),
    )
    monkeypatch.setattr(
        "acp_client.cli.run_tui_app",
        lambda **kwargs: captured.setdefault("run", kwargs),
    )
    monkeypatch.setattr(
        "sys.argv",
        ["acp-client", "--history-dir", str(history_dir)],
    )

    client_cli.run_client()

    assert captured["run"]["history_dir"] == str(history_dir)
