from __future__ import annotations

from acp_client.tui.components.prompt_input import PromptInput


def test_prompt_input_history_navigation_restores_draft() -> None:
    prompt_input = PromptInput()
    prompt_input.set_active_session("sess_1")
    prompt_input.remember_prompt("first")
    prompt_input.remember_prompt("second")

    prompt_input.text = "draft"
    prompt_input.action_history_previous()
    assert prompt_input.text == "second"

    prompt_input.action_history_previous()
    assert prompt_input.text == "first"

    prompt_input.action_history_next()
    assert prompt_input.text == "second"

    prompt_input.action_history_next()
    assert prompt_input.text == "draft"


def test_prompt_input_history_is_isolated_by_session() -> None:
    prompt_input = PromptInput()
    prompt_input.set_active_session("sess_1")
    prompt_input.remember_prompt("one")

    prompt_input.set_active_session("sess_2")
    prompt_input.remember_prompt("two")
    prompt_input.action_history_previous()
    assert prompt_input.text == "two"

    prompt_input.set_active_session("sess_1")
    prompt_input.action_history_previous()
    assert prompt_input.text == "one"


def test_prompt_input_skips_consecutive_duplicates() -> None:
    prompt_input = PromptInput()
    prompt_input.set_active_session("sess_1")
    prompt_input.remember_prompt("same")
    prompt_input.remember_prompt("same")

    prompt_input.action_history_previous()
    assert prompt_input.text == "same"

    prompt_input.action_history_previous()
    assert prompt_input.text == "same"
