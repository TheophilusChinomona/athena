"""Tests for WhatsApp message formatting and chunking.

Covers:
- format_message(): markdown → WhatsApp syntax conversion
- send(): message chunking for long responses
- MAX_MESSAGE_LENGTH: practical UX limit
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gateway.config import Platform, PlatformConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_adapter():
    """Create a WhatsAppAdapter with test attributes (bypass __init__)."""
    from gateway.platforms.whatsapp import WhatsAppAdapter

    adapter = WhatsAppAdapter.__new__(WhatsAppAdapter)
    adapter.platform = Platform.WHATSAPP
    adapter.config = MagicMock()
    adapter.config.extra = {}
    adapter._bridge_port = 3000
    adapter._bridge_script = "/tmp/test-bridge.js"
    adapter._session_path = MagicMock()
    adapter._bridge_log_fh = None
    adapter._bridge_log = None
    adapter._bridge_process = None
    adapter._reply_prefix = None
    adapter._running = True
    adapter._message_handler = None
    adapter._fatal_error_code = None
    adapter._fatal_error_message = None
    adapter._fatal_error_retryable = True
    adapter._fatal_error_handler = None
    adapter._active_sessions = {}
    adapter._pending_messages = {}
    adapter._background_tasks = set()
    adapter._auto_tts_disabled_chats = set()
    adapter._message_queue = asyncio.Queue()
    adapter._http_session = MagicMock()
    adapter._mention_patterns = []
    return adapter


class _AsyncCM:
    """Minimal async context manager returning a fixed value."""

    def __init__(self, value):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, *exc):
        return False


# ---------------------------------------------------------------------------
# format_message tests
# ---------------------------------------------------------------------------

class TestFormatMessage:
    """WhatsApp markdown conversion."""

    def test_bold_double_asterisk(self):
        adapter = _make_adapter()
        assert adapter.format_message("**hello**") == "*hello*"

    def test_bold_double_underscore(self):
        adapter = _make_adapter()
        assert adapter.format_message("__hello__") == "*hello*"

    def test_strikethrough(self):
        adapter = _make_adapter()
        assert adapter.format_message("~~deleted~~") == "~deleted~"

    def test_headers_converted_to_bold(self):
        adapter = _make_adapter()
        assert adapter.format_message("# Title") == "*Title*"
        assert adapter.format_message("## Subtitle") == "*Subtitle*"
        assert adapter.format_message("### Deep") == "*Deep*"

    def test_links_converted(self):
        adapter = _make_adapter()
        result = adapter.format_message("[click here](https://example.com)")
        assert result == "click here (https://example.com)"

    def test_code_blocks_protected(self):
        """Code blocks should not have their content reformatted."""
        adapter = _make_adapter()
        content = "before **bold** ```python\n**not bold**\n``` after **bold**"
        result = adapter.format_message(content)
        assert "```python\n**not bold**\n```" in result
        assert result.startswith("before *bold*")
        assert result.endswith("after *bold*")

    def test_inline_code_protected(self):
        """Inline code should not have its content reformatted."""
        adapter = _make_adapter()
        content = "use `**raw**` here"
        result = adapter.format_message(content)
        assert "`**raw**`" in result
        assert result.startswith("use ")

    def test_empty_content(self):
        adapter = _make_adapter()
        assert adapter.format_message("") == ""
        assert adapter.format_message(None) is None

    def test_plain_text_unchanged(self):
        adapter = _make_adapter()
        assert adapter.format_message("hello world") == "hello world"

    def test_already_whatsapp_italic(self):
        """Single *italic* should pass through unchanged."""
        adapter = _make_adapter()
        # After bold conversion, *text* is WhatsApp italic
        assert adapter.format_message("*italic*") == "*italic*"

    def test_multiline_mixed(self):
        adapter = _make_adapter()
        content = "# Header\n\n**Bold text** and ~~strike~~\n\n```\ncode\n```"
        result = adapter.format_message(content)
        assert "*Header*" in result
        assert "*Bold text*" in result
        assert "~strike~" in result
        assert "```\ncode\n```" in result


# ---------------------------------------------------------------------------
# MAX_MESSAGE_LENGTH tests
# ---------------------------------------------------------------------------

class TestMessageLimits:
    """WhatsApp message length limits."""

    def test_max_message_length_is_practical(self):
        from gateway.platforms.whatsapp import WhatsAppAdapter
        assert WhatsAppAdapter.MAX_MESSAGE_LENGTH == 4096


# ---------------------------------------------------------------------------
# send() chunking tests
# ---------------------------------------------------------------------------

class TestSendChunking:
    """WhatsApp send() splits long messages into chunks."""

    @pytest.mark.asyncio
    async def test_short_message_single_send(self):
        adapter = _make_adapter()
        resp = MagicMock(status=200)
        resp.json = AsyncMock(return_value={"messageId": "msg1"})
        adapter._http_session.post = MagicMock(return_value=_AsyncCM(resp))

        result = await adapter.send("chat1", "short message")
        assert result.success
        # Only one call to bridge /send
        assert adapter._http_session.post.call_count == 1

    @pytest.mark.asyncio
    async def test_long_message_chunked(self):
        adapter = _make_adapter()
        resp = MagicMock(status=200)
        resp.json = AsyncMock(return_value={"messageId": "msg1"})
        adapter._http_session.post = MagicMock(return_value=_AsyncCM(resp))

        # Create a message longer than MAX_MESSAGE_LENGTH (4096)
        long_msg = "a " * 3000  # ~6000 chars

        result = await adapter.send("chat1", long_msg)
        assert result.success
        # Should have made multiple calls
        assert adapter._http_session.post.call_count > 1

    @pytest.mark.asyncio
    async def test_empty_message_no_send(self):
        adapter = _make_adapter()
        result = await adapter.send("chat1", "")
        assert result.success
        assert adapter._http_session.post.call_count == 0

    @pytest.mark.asyncio
    async def test_whitespace_only_no_send(self):
        adapter = _make_adapter()
        result = await adapter.send("chat1", "   \n  ")
        assert result.success
        assert adapter._http_session.post.call_count == 0

    @pytest.mark.asyncio
    async def test_format_applied_before_send(self):
        """Markdown should be converted to WhatsApp format before sending."""
        adapter = _make_adapter()
        resp = MagicMock(status=200)
        resp.json = AsyncMock(return_value={"messageId": "msg1"})
        adapter._http_session.post = MagicMock(return_value=_AsyncCM(resp))

        await adapter.send("chat1", "**bold text**")

        # Check the payload sent to the bridge
        call_args = adapter._http_session.post.call_args
        payload = call_args.kwargs.get("json") or call_args[1].get("json")
        assert payload["message"] == "*bold text*"

    @pytest.mark.asyncio
    async def test_reply_to_only_on_first_chunk(self):
        """reply_to should only be set on the first chunk."""
        adapter = _make_adapter()
        resp = MagicMock(status=200)
        resp.json = AsyncMock(return_value={"messageId": "msg1"})
        adapter._http_session.post = MagicMock(return_value=_AsyncCM(resp))

        long_msg = "word " * 2000  # ~10000 chars, multiple chunks

        await adapter.send("chat1", long_msg, reply_to="orig123")

        calls = adapter._http_session.post.call_args_list
        assert len(calls) > 1

        # First chunk should have replyTo
        first_payload = calls[0].kwargs.get("json") or calls[0][1].get("json")
        assert first_payload.get("replyTo") == "orig123"

        # Subsequent chunks should NOT have replyTo
        for call in calls[1:]:
            payload = call.kwargs.get("json") or call[1].get("json")
            assert "replyTo" not in payload

    @pytest.mark.asyncio
    async def test_bridge_error_returns_failure(self):
        adapter = _make_adapter()
        resp = MagicMock(status=500)
        resp.text = AsyncMock(return_value="Internal Server Error")
        adapter._http_session.post = MagicMock(return_value=_AsyncCM(resp))

        result = await adapter.send("chat1", "hello")
        assert not result.success
        assert "Internal Server Error" in result.error

    @pytest.mark.asyncio
    async def test_not_connected_returns_failure(self):
        adapter = _make_adapter()
        adapter._running = False

        result = await adapter.send("chat1", "hello")
        assert not result.success
        assert "Not connected" in result.error


# ---------------------------------------------------------------------------
# display_config tier classification
# ---------------------------------------------------------------------------

class TestWhatsAppTier:
    """WhatsApp should be classified as TIER_MEDIUM."""

    def test_whatsapp_streaming_follows_global(self):
        from gateway.display_config import resolve_display_setting
        # TIER_MEDIUM has streaming: None (follow global), not False
        assert resolve_display_setting({}, "whatsapp", "streaming") is None

    def test_whatsapp_tool_progress_is_new(self):
        from gateway.display_config import resolve_display_setting
        assert resolve_display_setting({}, "whatsapp", "tool_progress") == "new"


# ---------------------------------------------------------------------------
# Whitespace tightening (post speccon-reliability-fork fix)
# ---------------------------------------------------------------------------

class TestWhitespaceCollapse:
    """format_message should tighten chat-hostile whitespace."""

    def test_collapses_triple_newlines_to_double(self):
        adapter = _make_adapter()
        out = adapter.format_message("line1\n\n\n\nline2")
        assert out == "line1\n\nline2"

    def test_preserves_single_blank_line(self):
        adapter = _make_adapter()
        out = adapter.format_message("a\n\nb")
        assert out == "a\n\nb"

    def test_strips_trailing_spaces_per_line(self):
        adapter = _make_adapter()
        out = adapter.format_message("hello   \nworld\t\t")
        assert out == "hello\nworld"

    def test_trims_leading_trailing_blank_lines(self):
        adapter = _make_adapter()
        out = adapter.format_message("\n\nhello\n\n")
        assert out == "hello"


# ---------------------------------------------------------------------------
# Inline media extraction (belt-and-braces path-detection)
# ---------------------------------------------------------------------------

class TestInlineMediaExtraction:
    """_extract_inline_media_paths should detect real media paths."""

    def test_extracts_audio_path(self, tmp_path):
        adapter = _make_adapter()
        audio = tmp_path / "hello.mp3"
        audio.write_bytes(b"id3")
        cleaned, refs = adapter._extract_inline_media_paths(
            f"Here's the audio: {audio}"
        )
        assert refs == [(str(audio), "audio")]
        assert str(audio) not in cleaned

    def test_video_maps_to_video_type(self, tmp_path):
        adapter = _make_adapter()
        vid = tmp_path / "clip.mp4"
        vid.write_bytes(b"\x00\x00")
        _, refs = adapter._extract_inline_media_paths(f"see {vid}")
        assert refs[0][1] == "video"

    def test_image_and_document_types(self, tmp_path):
        adapter = _make_adapter()
        img = tmp_path / "a.png"; img.write_bytes(b"x")
        doc = tmp_path / "b.pdf"; doc.write_bytes(b"%PDF")
        _, refs = adapter._extract_inline_media_paths(f"{img} and {doc}")
        types = {t for _, t in refs}
        assert types == {"image", "document"}

    def test_ignores_unknown_extension(self, tmp_path):
        adapter = _make_adapter()
        weird = tmp_path / "thing.xyz"
        weird.write_bytes(b"x")
        cleaned, refs = adapter._extract_inline_media_paths(str(weird))
        assert refs == []
        assert cleaned == str(weird)

    def test_ignores_nonexistent_path(self):
        adapter = _make_adapter()
        cleaned, refs = adapter._extract_inline_media_paths(
            "/home/nope/ghost.mp3"
        )
        assert refs == []

    def test_dedupes_repeated_path(self, tmp_path):
        adapter = _make_adapter()
        audio = tmp_path / "same.ogg"
        audio.write_bytes(b"x")
        _, refs = adapter._extract_inline_media_paths(
            f"{audio} and again {audio}"
        )
        assert len(refs) == 1

    def test_plain_text_untouched(self):
        adapter = _make_adapter()
        cleaned, refs = adapter._extract_inline_media_paths("Just a normal reply.")
        assert refs == []
        assert cleaned == "Just a normal reply."


class TestSendRoutesMediaPaths:
    """send() must route inline media paths through _send_media_to_bridge."""

    def test_send_strips_path_and_calls_media_bridge(self, tmp_path):
        adapter = _make_adapter()
        audio = tmp_path / "voice.ogg"
        audio.write_bytes(b"id3")

        adapter._check_managed_bridge_exit = AsyncMock(return_value=None)
        adapter._send_media_to_bridge = AsyncMock()
        from gateway.platforms.base import SendResult
        adapter._send_media_to_bridge.return_value = SendResult(
            success=True, message_id="mid-1"
        )

        result = asyncio.run(adapter.send(
            chat_id="chat@x",
            content=f"Here's your audio: {audio}",
        ))

        assert result.success is True
        assert result.message_id == "mid-1"
        adapter._send_media_to_bridge.assert_awaited_once()
        call_kwargs = adapter._send_media_to_bridge.await_args.kwargs
        assert call_kwargs["file_path"] == str(audio)
        assert call_kwargs["media_type"] == "audio"
        assert str(audio) not in (call_kwargs.get("caption") or "")

    def test_send_no_media_goes_through_text_send(self):
        adapter = _make_adapter()
        adapter._check_managed_bridge_exit = AsyncMock(return_value=None)
        adapter._send_media_to_bridge = AsyncMock()

        # Mock HTTP session post to succeed
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={"messageId": "text-1"})
        adapter._http_session.post = MagicMock(return_value=_AsyncCM(mock_resp))

        result = asyncio.run(adapter.send(
            chat_id="chat@x",
            content="plain text reply",
        ))
        assert result.success is True
        adapter._send_media_to_bridge.assert_not_awaited()
