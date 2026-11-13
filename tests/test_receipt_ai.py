import base64
import json

import httpx2
import pytest

from receipt_ai import GEMINI_REQUEST_LIMIT, AIError, Claude, Gemini

REPLY = '```json\n{"store": "Lidl", "items": []}\n```'


class Recorder:
    """httpx2 transport that answers every request with one canned response."""

    def __init__(self, status=200, body=None, error=None):
        self.status, self.body, self.error = status, body, error
        self.requests = []

    def client(self):
        return httpx2.Client(transport=httpx2.MockTransport(self.handle))

    def handle(self, request):
        self.requests.append(request)
        if self.error:
            raise self.error
        # keep the SDKs from retrying canned failures
        return httpx2.Response(self.status, json=self.body, headers={"x-should-retry": "false"})

    def sent(self):
        return json.loads(self.requests[-1].content)


def claude_message(text=REPLY, stop_reason="end_turn"):
    return {"id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
            "content": [{"type": "text", "text": text}], "stop_reason": stop_reason,
            "stop_sequence": None, "usage": {"input_tokens": 10, "output_tokens": 10}}


def claude_error(kind, message):
    return {"type": "error", "error": {"type": kind, "message": message}}


def gemini_reply(text=REPLY):
    return {"candidates": [{"content": {"parts": [{"text": text}], "role": "model"}, "finishReason": "STOP"}]}


def gemini_error(code, message):
    return {"error": {"code": code, "message": message, "status": "X"}}


# ---------- Claude ----------

def test_claude_sends_images_before_the_prompt_and_returns_the_text():
    server = Recorder(body=claude_message())
    reply = Claude("key", server.client()).ask("claude-opus-5-5", "Read this", [b"one", b"two"])

    assert reply == REPLY
    request = server.requests[-1]
    assert request.headers["authorization"] == "Bearer key"
    content = server.sent()["messages"][0]["content"]
    assert [c["type"] for c in content] == ["image", "image", "text"]
    assert base64.b64decode(content[0]["source"]["data"]) == b"one"
    assert content[0]["source"]["media_type"] == "image/jpeg"
    assert content[-1]["text"] == "Read this"


def test_sonnet_falls_back_only_to_the_older_sonnet():
    server = Recorder(body=claude_message())
    Claude("key", server.client()).ask("claude-sonnet-5-5", "p", [b"x"])
    assert server.sent()["fallbacks"] == [{"model": "claude-sonnet-5"}]
    assert "server-side-fallback" in server.requests[-1].headers["anthropic-beta"]

    for model in ("claude-haiku-5-5", "claude-opus-5-5"):
        Claude("key", server.client()).ask(model, "p", [b"x"])
        assert "fallbacks" not in server.sent()


def test_sonnet_is_the_default_claude_model():
    assert Claude.models[0] == "claude-sonnet-5-5"


@pytest.mark.parametrize("status, body, expected", [
    (401, claude_error("authentication_error", "invalid x-api-key"), "didn't accept the API key"),
    (404, claude_error("not_found_error", "model: nope"), "doesn't know the model \"claude-opus-5-5\""),
    (429, claude_error("rate_limit_error", "slow down"), "busy"),
    (529, claude_error("overloaded_error", "overloaded"), "having problems"),
    (400, claude_error("invalid_request_error", "Your credit balance is too low."),
     "refused the request: Your credit balance is too low."),
])
def test_claude_errors_are_explained(status, body, expected):
    server = Recorder(status, body)
    with pytest.raises(AIError, match=expected):
        Claude("key", server.client()).ask("claude-opus-5-5", "p", [b"x"])


def test_claude_refusal_and_cut_off_reply_are_explained():
    with pytest.raises(AIError, match="declined"):
        Claude("key", Recorder(body=claude_message(stop_reason="refusal")).client()).ask("claude-opus-5-5", "p", [])
    with pytest.raises(AIError, match="cut off"):
        Claude("key", Recorder(body=claude_message(stop_reason="max_tokens")).client()).ask("claude-opus-5-5", "p", [])


def test_claude_check_looks_up_the_model():
    server = Recorder(body={"id": "claude-opus-5-5", "type": "model", "display_name": "Claude Opus 5.5",
                            "created_at": "2026-01-01T00:00:00Z"})
    Claude("key", server.client()).check("claude-opus-5-5")
    assert server.requests[-1].url.path.endswith("/models/claude-opus-5-5")


# ---------- Gemini ----------

def test_gemini_sends_images_before_the_prompt_and_returns_the_text():
    server = Recorder(body=gemini_reply())
    reply = Gemini("key", server.client()).ask("gemini-4-hydrogen", "Read this", [b"one", b"two"])

    assert reply == REPLY
    request = server.requests[-1]
    assert request.headers["x-goog-api-key"] == "key"
    assert "gemini-4-hydrogen:generateContent" in request.url.path
    sent = server.sent()
    parts = [p for content in sent["contents"] for p in content["parts"]]
    assert base64.b64decode(parts[0]["inlineData"]["data"]) == b"one"
    assert parts[-1]["text"] == "Read this"
    assert sent["generationConfig"]["mediaResolution"] == "MEDIA_RESOLUTION_HIGH"


@pytest.mark.parametrize("status, body, expected", [
    (403, gemini_error(403, "denied"), "didn't accept the API key"),
    (404, gemini_error(404, "not found"), "doesn't know the model"),
    (429, gemini_error(429, "quota"), "busy"),
    (500, gemini_error(500, "boom"), "having problems"),
    (400, gemini_error(400, "API key not valid. Please pass a valid API key."),
     "refused the request: API key not valid"),
])
def test_gemini_errors_are_explained(status, body, expected):
    server = Recorder(status, body)
    with pytest.raises(AIError, match=expected):
        Gemini("key", server.client()).ask("gemini-4-hydrogen", "p", [b"x"])


def test_gemini_offline_is_explained():
    server = Recorder(error=httpx2.ConnectError("no route"))
    with pytest.raises(AIError, match="Couldn't reach Gemini"):
        Gemini("key", server.client()).ask("gemini-4-hydrogen", "p", [b"x"])


def test_gemini_empty_answer_is_explained():
    body = {"candidates": [{"finishReason": "SAFETY"}]}
    with pytest.raises(AIError, match="no answer"):
        Gemini("key", Recorder(body=body).client()).ask("gemini-4-hydrogen", "p", [b"x"])


def test_gemini_refuses_oversized_requests_before_sending():
    server = Recorder(body=gemini_reply())
    with pytest.raises(AIError, match="too large"):
        Gemini("key", server.client()).ask("gemini-4-hydrogen", "p", [b"x" * (GEMINI_REQUEST_LIMIT // 2)] * 2)
    assert not server.requests
