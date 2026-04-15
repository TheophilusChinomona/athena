"""Tests for WhatsApp media delivery via send_message_tool.

Covers the speccon-reliability-fork fix: _send_whatsapp now accepts
media_files and routes them through the bridge /send-media endpoint
instead of silently dropping them.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.config import Platform
from tools.send_message_tool import _send_whatsapp, _send_to_platform


class _AsyncCM:
    def __init__(self, value):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, *exc):
        return False


def _mock_session_factory(responses):
    """Build a fake aiohttp.ClientSession that returns queued responses.

    responses: list of (status, json_body) tuples — one per POST.
    """
    calls = []

    def _make_cm(status, body):
        resp = MagicMock()
        resp.status = status
        resp.json = AsyncMock(return_value=body)
        resp.text = AsyncMock(return_value=str(body))
        return _AsyncCM(resp)

    queue = list(responses)

    def _post(url, json=None, timeout=None):
        status, body = queue.pop(0)
        calls.append({"url": url, "json": json})
        return _make_cm(status, body)

    session = MagicMock()
    session.post = _post
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    return session, calls


class TestSendWhatsAppMedia:
    def test_audio_file_sent_as_audio(self, tmp_path, monkeypatch):
        audio = tmp_path / "voice.ogg"
        audio.write_bytes(b"OggS")

        session, calls = _mock_session_factory([(200, {"messageId": "m1"})])
        monkeypatch.setattr(
            "aiohttp.ClientSession", lambda *a, **kw: session
        )

        result = asyncio.run(_send_whatsapp(
            {"bridge_port": 3000},
            "chat@1",
            "Here it is",
            media_files=[str(audio)],
        ))

        assert result == {
            "success": True,
            "platform": "whatsapp",
            "chat_id": "chat@1",
            "message_id": "m1",
            "media_count": 1,
        }
        assert calls[0]["url"].endswith("/send-media")
        assert calls[0]["json"]["mediaType"] == "audio"
        assert calls[0]["json"]["filePath"] == str(audio)
        assert calls[0]["json"]["caption"] == "Here it is"

    def test_video_classified_as_video(self, tmp_path, monkeypatch):
        vid = tmp_path / "clip.mp4"
        vid.write_bytes(b"\x00")
        session, calls = _mock_session_factory([(200, {"messageId": "m2"})])
        monkeypatch.setattr("aiohttp.ClientSession", lambda *a, **kw: session)

        asyncio.run(_send_whatsapp({"bridge_port": 3000}, "c", "", media_files=[str(vid)]))
        assert calls[0]["json"]["mediaType"] == "video"

    def test_image_classified_as_image(self, tmp_path, monkeypatch):
        img = tmp_path / "pic.png"
        img.write_bytes(b"\x89PNG")
        session, calls = _mock_session_factory([(200, {"messageId": "m3"})])
        monkeypatch.setattr("aiohttp.ClientSession", lambda *a, **kw: session)

        asyncio.run(_send_whatsapp({"bridge_port": 3000}, "c", "", media_files=[str(img)]))
        assert calls[0]["json"]["mediaType"] == "image"

    def test_unknown_ext_classified_as_document(self, tmp_path, monkeypatch):
        doc = tmp_path / "report.pdf"
        doc.write_bytes(b"%PDF-")
        session, calls = _mock_session_factory([(200, {"messageId": "m4"})])
        monkeypatch.setattr("aiohttp.ClientSession", lambda *a, **kw: session)

        asyncio.run(_send_whatsapp({"bridge_port": 3000}, "c", "", media_files=[str(doc)]))
        assert calls[0]["json"]["mediaType"] == "document"

    def test_caption_only_on_first_attachment(self, tmp_path, monkeypatch):
        a = tmp_path / "a.mp3"; a.write_bytes(b"x")
        b = tmp_path / "b.mp3"; b.write_bytes(b"x")
        session, calls = _mock_session_factory([
            (200, {"messageId": "m1"}),
            (200, {"messageId": "m2"}),
        ])
        monkeypatch.setattr("aiohttp.ClientSession", lambda *a, **kw: session)

        asyncio.run(_send_whatsapp(
            {"bridge_port": 3000},
            "c",
            "hello",
            media_files=[str(a), str(b)],
        ))
        assert calls[0]["json"].get("caption") == "hello"
        assert "caption" not in calls[1]["json"]

    def test_missing_file_returns_error(self, tmp_path):
        ghost = tmp_path / "nope.mp3"
        result = asyncio.run(_send_whatsapp(
            {"bridge_port": 3000},
            "c",
            "hi",
            media_files=[str(ghost)],
        ))
        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_text_only_still_works(self, monkeypatch):
        session, calls = _mock_session_factory([(200, {"messageId": "t1"})])
        monkeypatch.setattr("aiohttp.ClientSession", lambda *a, **kw: session)

        result = asyncio.run(_send_whatsapp(
            {"bridge_port": 3000}, "c", "plain text"
        ))
        assert result["success"] is True
        assert calls[0]["url"].endswith("/send")
        assert calls[0]["json"] == {"chatId": "c", "message": "plain text"}


class TestDispatcherWhatsAppMedia:
    """_send_to_platform must not drop WhatsApp media any more."""

    def test_whatsapp_media_only_no_longer_rejected(self, tmp_path, monkeypatch):
        """Previously returned an error for WhatsApp + media-only. Now routes."""
        audio = tmp_path / "v.mp3"
        audio.write_bytes(b"x")

        session, calls = _mock_session_factory([(200, {"messageId": "m1"})])
        monkeypatch.setattr("aiohttp.ClientSession", lambda *a, **kw: session)

        from types import SimpleNamespace
        pconfig = SimpleNamespace(extra={"bridge_port": 3000}, token=None)

        result = asyncio.run(_send_to_platform(
            Platform.WHATSAPP,
            pconfig,
            "chat@1",
            "",  # empty message, media only
            media_files=[str(audio)],
        ))
        assert result.get("success") is True
        assert calls[0]["url"].endswith("/send-media")
