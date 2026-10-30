import base64
import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

SECRET = "test-secret"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("LINE_CHANNEL_SECRET", SECRET)
    monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "test-token")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    from app.main import app

    with TestClient(app) as c:
        yield c


def sign(body: str) -> str:
    digest = hmac.new(SECRET.encode(), body.encode(), hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def follow_body(event_type: str) -> str:
    return json.dumps({
        "destination": "Ubot",
        "events": [{
            "type": event_type,
            "mode": "active",
            "timestamp": 1700000000000,
            "source": {"type": "user", "userId": "Uabc"},
            "webhookEventId": "01H000",
            "deliveryContext": {"isRedelivery": False},
            **({"replyToken": "rt", "follow": {"isUnblocked": False}} if event_type == "follow" else {}),
        }],
    })


def test_bad_signature_is_rejected(client):
    r = client.post("/callback", content='{"events": []}', headers={"X-Line-Signature": "wrong"})
    assert r.status_code == 400


def test_good_signature_is_accepted(client):
    body = '{"destination": "Ubot", "events": []}'
    r = client.post("/callback", content=body, headers={"X-Line-Signature": sign(body)})
    assert r.status_code == 200


def test_follow_and_unfollow(client, monkeypatch):
    bot = client.app.state.bot
    replies = []
    monkeypatch.setattr(bot, "reply", lambda token, text: replies.append(text))

    body = follow_body("follow")
    assert client.post("/callback", content=body, headers={"X-Line-Signature": sign(body)}).status_code == 200
    assert bot.store.subscribers() == ["Uabc"]
    assert len(replies) == 1

    body = follow_body("unfollow")
    assert client.post("/callback", content=body, headers={"X-Line-Signature": sign(body)}).status_code == 200
    assert bot.store.subscribers() == []


def test_text_message_gets_reply(client, monkeypatch):
    bot = client.app.state.bot
    replies = []
    monkeypatch.setattr(bot, "reply", lambda token, text: replies.append((token, text)))

    body = json.dumps({
        "destination": "Ubot",
        "events": [{
            "type": "message",
            "mode": "active",
            "timestamp": 1700000000000,
            "source": {"type": "user", "userId": "Uabc"},
            "webhookEventId": "01H001",
            "deliveryContext": {"isRedelivery": False},
            "replyToken": "rt-123",
            "message": {"type": "text", "id": "1", "text": "明日", "quoteToken": "q"},
        }],
    })
    assert client.post("/callback", content=body, headers={"X-Line-Signature": sign(body)}).status_code == 200
    assert len(replies) == 1
    token, text = replies[0]
    assert token == "rt-123"
    assert text.startswith("明日")
