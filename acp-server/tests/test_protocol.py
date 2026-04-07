from acp_server.messages import ACPMessage
from acp_server.protocol import process_request


def test_initialize_request() -> None:
    request = ACPMessage(id="1", type="request", method="initialize", params={})

    response = process_request(request)

    assert response.type == "response"
    assert response.error is None
    assert response.result is not None
    assert response.result["protocol"] == "ACP"


def test_unknown_method() -> None:
    request = ACPMessage(id="2", type="request", method="missing", params={})

    response = process_request(request)

    assert response.error is not None
    assert response.error["code"] == -32601
