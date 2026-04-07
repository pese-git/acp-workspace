import pytest

from acp_client.messages import ACPMessage, parse_json_params


def test_parse_json_params_object() -> None:
    params = parse_json_params('{"x":1,"y":"ok"}')
    assert params == {"x": 1, "y": "ok"}


def test_parse_json_params_requires_object() -> None:
    with pytest.raises(ValueError):
        parse_json_params("[1, 2]")


def test_message_to_from_dict() -> None:
    request = ACPMessage.request(method="ping", params={})
    restored = ACPMessage.from_dict(request.to_dict())
    assert restored.method == "ping"
