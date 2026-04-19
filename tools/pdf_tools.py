"""PDF analysis tool — ``pdf_analyze``.

Sends a PDF directly to the active chat model instead of going through a
lossy text-extraction or page-rasterization step. Both OpenAI (>=gpt-4.1)
and Gemini (>=1.5) accept PDFs natively:

  * OpenAI chat/completions — ``{"type": "file", "file": {"file_data":
    "data:application/pdf;base64,...", "filename": "..."}}``
  * Gemini ``generateContent`` — ``{"inlineData": {"mimeType":
    "application/pdf", "data": "<base64>"}}``

The OpenAI-compatible Gemini shim at ``generativelanguage.googleapis.com/
v1beta/openai`` does NOT support the ``file`` content type, so we fall
back to Gemini's native API when the active provider is ``gemini``.

Usage — agent calls::

    pdf_analyze(pdf_path="/data/invoice.pdf",
                question="Extract the line items as JSON: description, qty, unit_price, total")

Returns the model's response text. Designed for repo-dump / data-extraction
workflows where the agent wants to see a PDF exactly as a human would.
"""

from __future__ import annotations

import base64
import json
import logging
import os
from pathlib import Path
from typing import Any, Awaitable, Dict, Tuple

import httpx

from tools.registry import registry, tool_error

logger = logging.getLogger(__name__)

_MAX_PDF_BYTES = 32 * 1024 * 1024  # 32 MB — API practical limit for inline uploads
_DEFAULT_TIMEOUT = 240.0            # seconds; PDFs are heavier than chat


# ---------------------------------------------------------------------------
# Provider resolution
# ---------------------------------------------------------------------------


def _resolve_active_provider() -> Tuple[str, str, str]:
    """Return ``(provider_id, api_key, base_url)`` for the active chat provider.

    Resolution order:
      1. ``active_provider`` field in auth.json (if it's an api-key provider)
      2. ``HERMES_PROVIDER`` env var
      3. ``OPENAI_API_KEY`` env presence → ``openai``
      4. ``GEMINI_API_KEY`` / ``GOOGLE_API_KEY`` env presence → ``gemini``

    Raises :class:`ValueError` if no usable provider is found.
    """
    from hermes_cli.auth import (
        PROVIDER_REGISTRY,
        get_active_provider,
        resolve_api_key_provider_credentials,
    )

    candidate = (get_active_provider() or os.getenv("HERMES_PROVIDER") or "").strip()
    if candidate and candidate in PROVIDER_REGISTRY:
        pconfig = PROVIDER_REGISTRY[candidate]
        if pconfig.auth_type == "api_key":
            try:
                creds = resolve_api_key_provider_credentials(candidate)
                if creds.get("api_key"):
                    return creds["provider"], creds["api_key"], creds["base_url"]
            except Exception as e:
                logger.debug("pdf_analyze: active provider %s unresolved: %s", candidate, e)

    # Fallback: walk known providers that this tool supports.
    for pid in ("openai", "gemini"):
        try:
            creds = resolve_api_key_provider_credentials(pid)
            if creds.get("api_key"):
                return creds["provider"], creds["api_key"], creds["base_url"]
        except Exception:
            continue

    raise ValueError(
        "pdf_analyze: no usable provider — set OPENAI_API_KEY or GEMINI_API_KEY, "
        "or configure model.provider in the active profile's config.yaml"
    )


# ---------------------------------------------------------------------------
# File handling
# ---------------------------------------------------------------------------


def _load_pdf_base64(pdf_path: str) -> Tuple[str, str]:
    p = Path(pdf_path).expanduser()
    if not p.is_file():
        raise FileNotFoundError(f"pdf_analyze: file not found: {pdf_path}")
    if p.suffix.lower() != ".pdf":
        raise ValueError(f"pdf_analyze: expected .pdf, got {p.suffix}: {pdf_path}")
    size = p.stat().st_size
    if size > _MAX_PDF_BYTES:
        raise ValueError(
            f"pdf_analyze: file too large ({size / 1_048_576:.1f} MB > 32 MB). "
            "Split the PDF or use pdf_extract_text for text-only content."
        )
    return base64.b64encode(p.read_bytes()).decode(), p.name


# ---------------------------------------------------------------------------
# Provider call paths
# ---------------------------------------------------------------------------


async def _call_openai(
    api_key: str,
    base_url: str,
    model: str,
    pdf_b64: str,
    filename: str,
    question: str,
) -> str:
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "file",
                        "file": {
                            "filename": filename,
                            "file_data": f"data:application/pdf;base64,{pdf_b64}",
                        },
                    },
                    {"type": "text", "text": question},
                ],
            }
        ],
        "max_tokens": 16384,
    }
    async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
        r = await client.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
    if r.status_code != 200:
        raise RuntimeError(f"OpenAI HTTP {r.status_code}: {r.text[:400]}")
    data = r.json()
    try:
        return data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"OpenAI response missing content: {e} — {json.dumps(data)[:400]}")


async def _call_gemini_native(
    api_key: str,
    model: str,
    pdf_b64: str,
    question: str,
) -> str:
    # Gemini's openai-compat shim can't take `file` content blocks — use native
    # generateContent. Model may come in as `gemini-2.5-pro` or `models/gemini-...`.
    model_path = model if model.startswith("models/") else f"models/{model}"
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/"
        f"{model_path}:generateContent?key={api_key}"
    )
    payload = {
        "contents": [
            {
                "parts": [
                    {"inlineData": {"mimeType": "application/pdf", "data": pdf_b64}},
                    {"text": question},
                ]
            }
        ],
        "generationConfig": {"maxOutputTokens": 16384},
    }
    async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
        r = await client.post(
            url,
            headers={"Content-Type": "application/json"},
            json=payload,
        )
    if r.status_code != 200:
        raise RuntimeError(f"Gemini HTTP {r.status_code}: {r.text[:400]}")
    data = r.json()
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"] or ""
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"Gemini response missing text: {e} — {json.dumps(data)[:400]}")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def pdf_analyze_tool(pdf_path: str, question: str, model: str = "") -> str:
    """Analyze a PDF via the active chat model's native PDF-input path."""
    pdf_b64, filename = _load_pdf_base64(pdf_path)
    provider_id, api_key, base_url = _resolve_active_provider()

    model_override = (model or os.getenv("PDF_ANALYZE_MODEL", "")).strip()
    if not model_override:
        model_override = "gpt-4.1" if provider_id == "openai" else "gemini-2.5-pro"

    logger.info(
        "pdf_analyze: %s via %s/%s (%d bytes b64)",
        filename,
        provider_id,
        model_override,
        len(pdf_b64),
    )

    if provider_id == "gemini":
        return await _call_gemini_native(api_key, model_override, pdf_b64, question)
    return await _call_openai(api_key, base_url, model_override, pdf_b64, filename, question)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

PDF_ANALYZE_SCHEMA = {
    "name": "pdf_analyze",
    "description": (
        "Analyze a PDF file end-to-end with vision+text reasoning. The PDF is "
        "sent directly to the active chat model (OpenAI or Gemini), preserving "
        "layout, images, tables, and scanned content. Use for extracting "
        "structured data from invoices, reports, forms, and scanned documents — "
        "anything where text extraction alone would lose context."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "pdf_path": {
                "type": "string",
                "description": "Absolute local path to the .pdf file.",
            },
            "question": {
                "type": "string",
                "description": (
                    "What to extract, ask, or summarize. Be specific: ask for "
                    "JSON output when you want structured data."
                ),
            },
        },
        "required": ["pdf_path", "question"],
    },
}


def _handle_pdf_analyze(args: Dict[str, Any], **_kw: Any) -> Awaitable[str]:
    pdf_path = args.get("pdf_path", "")
    question = args.get("question", "")
    if not pdf_path or not question:
        async def _bad():
            return tool_error("pdf_analyze requires both pdf_path and question")
        return _bad()
    return pdf_analyze_tool(pdf_path, question)


registry.register(
    name="pdf_analyze",
    toolset="vision",
    schema=PDF_ANALYZE_SCHEMA,
    handler=_handle_pdf_analyze,
    is_async=True,
    emoji="📄",
)
