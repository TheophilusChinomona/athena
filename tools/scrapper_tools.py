"""Scrapper pipeline tools — profile-scoped batch helpers for the agent.

These tools orchestrate the CAPS question validator + submodule tagger
at scale. They are *batch-first*: each call processes N questions in
parallel and returns a terse summary so the agent's context doesn't
explode. Full per-question detail is always written to Neon.

Availability
------------
Gated on ``SCRAPPER_DATABASE_URL`` (Neon) and ``OPENAI_API_KEY``.
Without both, ``check_scrapper_requirements`` reports unavailable.

Architecture
------------
* Reuses ``scrapper-pipeline`` skill code as the single source of truth.
  The pipeline repo must be checked out at ``SCRAPPER_PIPELINE_PATH``
  (default ``/opt/scrapper-tool/scrapper-pipeline``), and its
  ``src`` directory is prepended to ``sys.path`` on first import.
* Writes all results via psycopg3 directly to Neon — no abstraction
  layer in between. Keeps the agent tool simple and legible.
* Async fan-out: each batch call opens one semaphore-bounded gather
  over N tasks (``SCRAPPER_BATCH_CONCURRENCY``, default 10).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Dict, List, Optional, Tuple

from tools.registry import registry, tool_error

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lazy import of the scrapper-pipeline skill code
# ---------------------------------------------------------------------------

_DEFAULT_PIPELINE_PATH = "/opt/scrapper-tool/scrapper-pipeline"


def _pipeline_src_path() -> Path:
    root = Path(os.environ.get("SCRAPPER_PIPELINE_PATH", _DEFAULT_PIPELINE_PATH))
    return root / "src"


def _ensure_pipeline_on_path() -> None:
    src = _pipeline_src_path()
    if str(src) not in sys.path and src.is_dir():
        sys.path.insert(0, str(src))


def _import_validator():
    _ensure_pipeline_on_path()
    from scrapper.skills.caps_validator import (  # type: ignore[import-not-found]
        CapsValidator,
        CapsValidatorError,
        ValidationCallResult,
    )
    return CapsValidator, CapsValidatorError, ValidationCallResult


def _import_tagger():
    _ensure_pipeline_on_path()
    from scrapper.skills.submodule_tagger import (  # type: ignore[import-not-found]
        SubmoduleCandidate,
        SubmoduleTagger,
        SubmoduleTaggerError,
        TagCallResult,
    )
    return SubmoduleCandidate, SubmoduleTagger, SubmoduleTaggerError, TagCallResult


def _import_reinspector():
    _ensure_pipeline_on_path()
    from scrapper.skills.file_reinspector import (  # type: ignore[import-not-found]
        FileReinspector,
        FileReinspectorError,
        ReinspectionCallResult,
    )
    return FileReinspector, FileReinspectorError, ReinspectionCallResult


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------


def check_scrapper_requirements() -> bool:
    """Return True iff the scrapper pipeline is runnable from this agent."""
    have_db = bool(os.environ.get("SCRAPPER_DATABASE_URL", "").strip())
    have_key = bool(
        os.environ.get("OPENAI_API_KEY", "").strip()
        or os.environ.get("GEMINI_API_KEY", "").strip()
    )
    pipeline_ok = _pipeline_src_path().is_dir()
    return have_db and have_key and pipeline_ok


# ---------------------------------------------------------------------------
# DB helpers (psycopg3)
# ---------------------------------------------------------------------------


def _db():
    import psycopg  # type: ignore[import-not-found]

    url = os.environ.get("SCRAPPER_DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("SCRAPPER_DATABASE_URL is not set")
    return psycopg.connect(url, autocommit=True)


def _provider_and_key() -> Tuple[str, str]:
    """Return ``(provider, api_key)`` for the active model.

    Preference: OpenAI if ``OPENAI_API_KEY`` is set, else Gemini.
    Callers can force with ``SCRAPPER_PROVIDER``.
    """
    forced = (os.environ.get("SCRAPPER_PROVIDER") or "").strip().lower()
    if forced == "openai" and os.environ.get("OPENAI_API_KEY"):
        return "openai", os.environ["OPENAI_API_KEY"].strip()
    if forced == "gemini" and os.environ.get("GEMINI_API_KEY"):
        return "gemini", os.environ["GEMINI_API_KEY"].strip()
    if os.environ.get("OPENAI_API_KEY"):
        return "openai", os.environ["OPENAI_API_KEY"].strip()
    if os.environ.get("GEMINI_API_KEY"):
        return "gemini", os.environ["GEMINI_API_KEY"].strip()
    raise RuntimeError("neither OPENAI_API_KEY nor GEMINI_API_KEY is set")


def _default_model(provider: str, purpose: str) -> str:
    """Model for ``purpose`` in ('validate', 'tag'). Overridable via env."""
    env_override = os.environ.get(f"SCRAPPER_{purpose.upper()}_MODEL", "").strip()
    if env_override:
        return env_override
    if provider == "openai":
        return "gpt-4.1-mini"
    return "gemini-2.5-flash"


# ---------------------------------------------------------------------------
# scrapper_queue_next_for_validation
# ---------------------------------------------------------------------------


SCRAPPER_QUEUE_NEXT_FOR_VALIDATION_SCHEMA = {
    "name": "scrapper_queue_next_for_validation",
    "description": (
        "Pop the next N questions needing text-only CAPS validation. Reads from "
        "v_validation_queue (raw_questions with no text_only row in "
        "question_validations, from verified PDFs). Returns a list of question ids "
        "plus just enough metadata to feed scrapper_validate_batch."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "How many questions to return (default 50, max 500).",
            },
            "subject_filter": {
                "type": "string",
                "description": "Optional exact subject name to restrict the queue.",
            },
            "grade_filter": {
                "type": "integer",
                "description": "Optional grade (4-12) to restrict the queue.",
            },
        },
        "required": [],
    },
}


def _queue_next(limit: int, subject: Optional[str], grade: Optional[int]) -> List[Dict[str, Any]]:
    limit = max(1, min(int(limit or 50), 500))
    sql = "SELECT question_id, scraped_file_id, grade, subject FROM v_validation_queue"
    params: List[Any] = []
    filters: List[str] = []
    if subject:
        filters.append("subject = %s")
        params.append(subject)
    if grade is not None:
        filters.append("grade = %s")
        params.append(int(grade))
    if filters:
        sql += " WHERE " + " AND ".join(filters)
    sql += " ORDER BY created_at ASC LIMIT %s"
    params.append(limit)

    with _db() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return [
        {"question_id": str(r[0]), "scraped_file_id": r[1], "grade": r[2], "subject": r[3]}
        for r in rows
    ]


async def _handle_queue_next_for_validation(args: Dict[str, Any], **_kw: Any) -> str:
    try:
        items = _queue_next(
            args.get("limit", 50),
            args.get("subject_filter"),
            args.get("grade_filter"),
        )
    except Exception as e:
        return tool_error(f"scrapper_queue_next_for_validation: {e}")
    return json.dumps({"count": len(items), "items": items})


registry.register(
    name="scrapper_queue_next_for_validation",
    toolset="scrapper",
    schema=SCRAPPER_QUEUE_NEXT_FOR_VALIDATION_SCHEMA,
    handler=_handle_queue_next_for_validation,
    check_fn=check_scrapper_requirements,
    is_async=True,
    emoji="📋",
)


# ---------------------------------------------------------------------------
# scrapper_validate_batch
# ---------------------------------------------------------------------------


SCRAPPER_VALIDATE_BATCH_SCHEMA = {
    "name": "scrapper_validate_batch",
    "description": (
        "Run CAPS validation on a batch of questions in parallel. For each "
        "question, loads its text + answer + explanation, calls the LLM "
        "validator with the grade+subject-locked constraint block, parses the "
        "API contract JSON, and writes one row to question_validations. "
        "Returns a terse summary (processed/accepted/rejected/errors/cost). "
        "Full per-question detail is in question_validations."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "question_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "UUID strings of raw_questions to validate.",
            },
            "tier": {
                "type": "string",
                "enum": ["text_only", "with_pdf"],
                "description": "Validation tier (default text_only).",
            },
            "concurrency": {
                "type": "integer",
                "description": "Max parallel LLM calls (default 10, max 30).",
            },
        },
        "required": ["question_ids"],
    },
}


@dataclass
class _QRow:
    question_id: str
    scraped_file_id: int
    grade: int
    subject: str
    question_text: str
    answer_text: str
    explanation_text: str


def _load_question_rows(question_ids: List[str]) -> List[_QRow]:
    if not question_ids:
        return []
    # raw_questions doesn't carry answer/explanation directly — we pull
    # question_text, and join scraped_files for grade+subject. For now
    # answer/explanation come empty; a future migration can add them.
    sql = """
        SELECT rq.id::text, rq.scraped_file_id, sf.grade, sf.subject,
               rq.question_text
        FROM raw_questions rq
        JOIN scraped_files sf ON sf.id = rq.scraped_file_id
        WHERE rq.id::text = ANY(%s)
    """
    with _db() as conn, conn.cursor() as cur:
        cur.execute(sql, (list(question_ids),))
        rows = cur.fetchall()
    return [
        _QRow(
            question_id=r[0],
            scraped_file_id=r[1],
            grade=r[2] or 0,
            subject=r[3] or "",
            question_text=r[4] or "",
            answer_text="",
            explanation_text="",
        )
        for r in rows
    ]


def _write_validation(
    question_id: str,
    tier: str,
    provider: str,
    model: str,
    call_result: Any,
) -> None:
    r = call_result.result  # ValidationResult
    sql = """
        INSERT INTO question_validations (
            question_id, evaluation_status, status_reason, cognitive_level,
            cognitive_justification, ai_notes, ai_issue_codes,
            ai_suggested_question_text, ai_suggested_answer, ai_suggested_explanation,
            answer_correct, grade_fit, term_fit,
            tier, model, model_provider,
            prompt_tokens, completion_tokens, cost_usd, raw_json
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb
        )
        ON CONFLICT (question_id, tier) DO UPDATE SET
            evaluation_status = EXCLUDED.evaluation_status,
            status_reason = EXCLUDED.status_reason,
            cognitive_level = EXCLUDED.cognitive_level,
            cognitive_justification = EXCLUDED.cognitive_justification,
            ai_notes = EXCLUDED.ai_notes,
            ai_issue_codes = EXCLUDED.ai_issue_codes,
            ai_suggested_question_text = EXCLUDED.ai_suggested_question_text,
            ai_suggested_answer = EXCLUDED.ai_suggested_answer,
            ai_suggested_explanation = EXCLUDED.ai_suggested_explanation,
            answer_correct = EXCLUDED.answer_correct,
            grade_fit = EXCLUDED.grade_fit,
            term_fit = EXCLUDED.term_fit,
            model = EXCLUDED.model,
            model_provider = EXCLUDED.model_provider,
            prompt_tokens = EXCLUDED.prompt_tokens,
            completion_tokens = EXCLUDED.completion_tokens,
            cost_usd = EXCLUDED.cost_usd,
            raw_json = EXCLUDED.raw_json,
            created_at = NOW()
    """
    with _db() as conn, conn.cursor() as cur:
        cur.execute(
            sql,
            (
                question_id,
                r.evaluationStatus,
                r.statusReason,
                r.cognitiveLevel,
                r.cognitiveJustification,
                r.aiNotes,
                r.aiIssueCodes,
                r.aiSuggestedQuestionText,
                r.aiSuggestedAnswer,
                r.aiSuggestedExplanation,
                r.validation.answerCorrect,
                r.validation.gradeFit,
                r.validation.termFit,
                tier,
                model,
                provider,
                call_result.prompt_tokens,
                call_result.completion_tokens,
                float(call_result.cost_usd),
                json.dumps(call_result.raw_json),
            ),
        )


async def _validate_one(validator: Any, q: _QRow, tier: str, sem: asyncio.Semaphore) -> Dict[str, Any]:
    async with sem:
        try:
            call = await validator.validate(
                question_id=q.question_id,
                grade=q.grade,
                subject=q.subject,
                question_text=q.question_text,
                answer_text=q.answer_text,
                explanation_text=q.explanation_text,
            )
        except Exception as e:
            return {"question_id": q.question_id, "ok": False, "error": str(e)[:200]}
        try:
            _write_validation(q.question_id, tier, validator.provider, validator.model, call)
        except Exception as e:
            return {
                "question_id": q.question_id,
                "ok": False,
                "error": f"db write: {e}"[:200],
            }
        return {
            "question_id": q.question_id,
            "ok": True,
            "status": call.result.evaluationStatus,
            "cost_usd": float(call.cost_usd),
        }


async def _handle_validate_batch(args: Dict[str, Any], **_kw: Any) -> str:
    question_ids = list(args.get("question_ids") or [])
    if not question_ids:
        return tool_error("scrapper_validate_batch: question_ids is empty")
    tier = (args.get("tier") or "text_only").lower()
    if tier not in ("text_only", "with_pdf"):
        return tool_error(f"scrapper_validate_batch: invalid tier {tier!r}")
    concurrency = max(1, min(int(args.get("concurrency") or 10), 30))

    try:
        provider, api_key = _provider_and_key()
    except Exception as e:
        return tool_error(f"scrapper_validate_batch: {e}")
    model = _default_model(provider, "validate")

    CapsValidator, _CapsValidatorError, _VCR = _import_validator()
    validator = CapsValidator(api_key=api_key, provider=provider, model=model)

    rows = _load_question_rows(question_ids)
    found_ids = {r.question_id for r in rows}
    missing = [qid for qid in question_ids if qid not in found_ids]

    sem = asyncio.Semaphore(concurrency)
    t0 = time.time()
    results = await asyncio.gather(*[_validate_one(validator, q, tier, sem) for q in rows])
    elapsed = time.time() - t0

    accepted = sum(1 for r in results if r.get("ok") and r.get("status") == "ACCEPT")
    rejected = sum(1 for r in results if r.get("ok") and r.get("status") == "REJECT")
    errors = [r for r in results if not r.get("ok")]
    cost_total = sum(float(r.get("cost_usd") or 0) for r in results if r.get("ok"))

    summary = {
        "processed": len(results),
        "accepted": accepted,
        "rejected": rejected,
        "errors": len(errors),
        "missing": missing,
        "cost_usd": round(cost_total, 6),
        "elapsed_s": round(elapsed, 2),
        "model": model,
        "provider": provider,
        "tier": tier,
    }
    if errors:
        summary["error_samples"] = errors[:3]
    return json.dumps(summary)


registry.register(
    name="scrapper_validate_batch",
    toolset="scrapper",
    schema=SCRAPPER_VALIDATE_BATCH_SCHEMA,
    handler=_handle_validate_batch,
    check_fn=check_scrapper_requirements,
    is_async=True,
    emoji="✅",
)


# ---------------------------------------------------------------------------
# scrapper_queue_next_for_tagging
# ---------------------------------------------------------------------------


SCRAPPER_QUEUE_NEXT_FOR_TAGGING_SCHEMA = {
    "name": "scrapper_queue_next_for_tagging",
    "description": (
        "Pop the next N questions that have passed validation but are missing "
        "CAPS submodule tags. Ordered by creation time."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "How many questions to return (default 50, max 500).",
            },
            "subject_filter": {"type": "string"},
            "grade_filter": {"type": "integer"},
            "only_accepted": {
                "type": "boolean",
                "description": "If true (default), only pick questions with ACCEPT validation.",
            },
        },
        "required": [],
    },
}


def _queue_next_for_tagging(
    limit: int, subject: Optional[str], grade: Optional[int], only_accepted: bool
) -> List[Dict[str, Any]]:
    limit = max(1, min(int(limit or 50), 500))
    sql = [
        "SELECT rq.id::text, rq.scraped_file_id, sf.grade, sf.subject",
        "FROM raw_questions rq",
        "JOIN scraped_files sf ON sf.id = rq.scraped_file_id",
        "WHERE NOT EXISTS (",
        "  SELECT 1 FROM question_submodules qs WHERE qs.question_id = rq.id",
        ")",
        "  AND sf.status = 'verified' AND sf.grade IS NOT NULL AND sf.subject IS NOT NULL",
    ]
    params: List[Any] = []
    if only_accepted:
        sql.append(
            "  AND EXISTS (SELECT 1 FROM question_validations qv "
            "WHERE qv.question_id = rq.id AND qv.evaluation_status = 'ACCEPT')"
        )
    if subject:
        sql.append("  AND sf.subject = %s")
        params.append(subject)
    if grade is not None:
        sql.append("  AND sf.grade = %s")
        params.append(int(grade))
    sql.append("ORDER BY rq.created_at ASC LIMIT %s")
    params.append(limit)

    with _db() as conn, conn.cursor() as cur:
        cur.execute("\n".join(sql), params)
        rows = cur.fetchall()
    return [
        {"question_id": r[0], "scraped_file_id": r[1], "grade": r[2], "subject": r[3]}
        for r in rows
    ]


async def _handle_queue_next_for_tagging(args: Dict[str, Any], **_kw: Any) -> str:
    try:
        items = _queue_next_for_tagging(
            args.get("limit", 50),
            args.get("subject_filter"),
            args.get("grade_filter"),
            bool(args.get("only_accepted", True)),
        )
    except Exception as e:
        return tool_error(f"scrapper_queue_next_for_tagging: {e}")
    return json.dumps({"count": len(items), "items": items})


registry.register(
    name="scrapper_queue_next_for_tagging",
    toolset="scrapper",
    schema=SCRAPPER_QUEUE_NEXT_FOR_TAGGING_SCHEMA,
    handler=_handle_queue_next_for_tagging,
    check_fn=check_scrapper_requirements,
    is_async=True,
    emoji="🏷️",
)


# ---------------------------------------------------------------------------
# scrapper_tag_batch
# ---------------------------------------------------------------------------


SCRAPPER_TAG_BATCH_SCHEMA = {
    "name": "scrapper_tag_batch",
    "description": (
        "Assign CAPS submodule tags to a batch of questions in parallel. For each "
        "question, pulls the candidate submodules filtered by grade+subject, asks "
        "the LLM to pick the top 1-3, and writes them to question_submodules. "
        "Terse summary returned; full tags per question are in question_submodules."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "question_ids": {
                "type": "array",
                "items": {"type": "string"},
            },
            "concurrency": {"type": "integer"},
        },
        "required": ["question_ids"],
    },
}


def _load_candidates(grade: int, subject: str) -> List[Any]:
    _SubmoduleCandidate, _SubmoduleTagger, _Err, _TCR = _import_tagger()
    sql = (
        "SELECT sub_module_id, module, topic, submodule_name "
        "FROM submodules WHERE grade = %s AND subject = %s "
        "ORDER BY sub_module_id"
    )
    with _db() as conn, conn.cursor() as cur:
        cur.execute(sql, (int(grade), subject))
        rows = cur.fetchall()
    return [
        _SubmoduleCandidate(
            sub_module_id=r[0],
            module=r[1],
            topic=r[2],
            submodule_name=r[3],
        )
        for r in rows
    ]


def _write_tags(
    question_id: str,
    model: str,
    provider: str,
    call: Any,
) -> int:
    if not call.response.tags:
        return 0
    sql = """
        INSERT INTO question_submodules
            (question_id, sub_module_id, confidence, rank, model, model_provider, cost_usd)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (question_id, sub_module_id) DO UPDATE SET
            confidence = EXCLUDED.confidence,
            rank = EXCLUDED.rank,
            model = EXCLUDED.model,
            model_provider = EXCLUDED.model_provider,
            cost_usd = EXCLUDED.cost_usd,
            created_at = NOW()
    """
    written = 0
    cost_share = float(call.cost_usd) / max(1, len(call.response.tags))
    with _db() as conn, conn.cursor() as cur:
        for t in call.response.tags:
            cur.execute(
                sql,
                (
                    question_id,
                    int(t.sub_module_id),
                    float(t.confidence),
                    int(t.rank),
                    model,
                    provider,
                    cost_share,
                ),
            )
            written += 1
    return written


async def _tag_one(tagger: Any, q: _QRow, sem: asyncio.Semaphore) -> Dict[str, Any]:
    async with sem:
        try:
            candidates = _load_candidates(q.grade, q.subject)
        except Exception as e:
            return {"question_id": q.question_id, "ok": False, "error": f"load: {e}"[:200]}
        try:
            call = await tagger.tag(
                question_id=q.question_id,
                grade=q.grade,
                subject=q.subject,
                question_text=q.question_text,
                candidates=candidates,
            )
        except Exception as e:
            return {"question_id": q.question_id, "ok": False, "error": str(e)[:200]}
        try:
            written = _write_tags(q.question_id, tagger.model, tagger.provider, call)
        except Exception as e:
            return {"question_id": q.question_id, "ok": False, "error": f"db: {e}"[:200]}
        return {
            "question_id": q.question_id,
            "ok": True,
            "tags_written": written,
            "cost_usd": float(call.cost_usd),
        }


async def _handle_tag_batch(args: Dict[str, Any], **_kw: Any) -> str:
    question_ids = list(args.get("question_ids") or [])
    if not question_ids:
        return tool_error("scrapper_tag_batch: question_ids is empty")
    concurrency = max(1, min(int(args.get("concurrency") or 10), 30))

    try:
        provider, api_key = _provider_and_key()
    except Exception as e:
        return tool_error(f"scrapper_tag_batch: {e}")
    model = _default_model(provider, "tag")

    _SubmoduleCandidate, SubmoduleTagger, _Err, _TCR = _import_tagger()
    tagger = SubmoduleTagger(api_key=api_key, provider=provider, model=model)

    rows = _load_question_rows(question_ids)
    found = {r.question_id for r in rows}
    missing = [qid for qid in question_ids if qid not in found]

    sem = asyncio.Semaphore(concurrency)
    t0 = time.time()
    results = await asyncio.gather(*[_tag_one(tagger, q, sem) for q in rows])
    elapsed = time.time() - t0

    ok = sum(1 for r in results if r.get("ok"))
    errors = [r for r in results if not r.get("ok")]
    tags_total = sum(int(r.get("tags_written") or 0) for r in results)
    cost_total = sum(float(r.get("cost_usd") or 0) for r in results if r.get("ok"))

    summary = {
        "processed": len(results),
        "ok": ok,
        "errors": len(errors),
        "missing": missing,
        "tags_written": tags_total,
        "cost_usd": round(cost_total, 6),
        "elapsed_s": round(elapsed, 2),
        "model": model,
        "provider": provider,
    }
    if errors:
        summary["error_samples"] = errors[:3]
    return json.dumps(summary)


registry.register(
    name="scrapper_tag_batch",
    toolset="scrapper",
    schema=SCRAPPER_TAG_BATCH_SCHEMA,
    handler=_handle_tag_batch,
    check_fn=check_scrapper_requirements,
    is_async=True,
    emoji="🏷️",
)


# ---------------------------------------------------------------------------
# scrapper_stats
# ---------------------------------------------------------------------------


SCRAPPER_STATS_SCHEMA = {
    "name": "scrapper_stats",
    "description": (
        "High-level progress snapshot: counts by validation status, tagging "
        "coverage, total cost spent, and remaining queue sizes. Fast — runs "
        "a single SQL roundtrip of aggregates."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}


def _stats() -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    with _db() as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM raw_questions")
        out["total_questions"] = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM v_validation_queue")
        out["validation_pending"] = cur.fetchone()[0]

        cur.execute(
            "SELECT evaluation_status, COUNT(*) FROM question_validations "
            "WHERE tier = 'text_only' GROUP BY 1"
        )
        out["validation_by_status"] = {k: v for k, v in cur.fetchall()}

        cur.execute("SELECT COALESCE(SUM(cost_usd), 0) FROM question_validations")
        out["validation_cost_total_usd"] = float(cur.fetchone()[0])

        cur.execute(
            "SELECT COUNT(DISTINCT question_id), COUNT(*), "
            "COALESCE(SUM(cost_usd), 0) FROM question_submodules"
        )
        qd, tags, cost = cur.fetchone()
        out["tagged_questions"] = qd
        out["total_tag_rows"] = tags
        out["tagging_cost_total_usd"] = float(cost)

        cur.execute("SELECT COUNT(*) FROM submodules")
        out["submodules_registered"] = cur.fetchone()[0]
    return out


async def _handle_stats(_args: Dict[str, Any], **_kw: Any) -> str:
    try:
        return json.dumps(_stats())
    except Exception as e:
        return tool_error(f"scrapper_stats: {e}")


registry.register(
    name="scrapper_stats",
    toolset="scrapper",
    schema=SCRAPPER_STATS_SCHEMA,
    handler=_handle_stats,
    check_fn=check_scrapper_requirements,
    is_async=True,
    emoji="📊",
)


# ---------------------------------------------------------------------------
# scrapper_fetch_pdf
# ---------------------------------------------------------------------------


SCRAPPER_FETCH_PDF_SCHEMA = {
    "name": "scrapper_fetch_pdf",
    "description": (
        "Download the PDF for a scraped_file_id from Firebase Storage to a "
        "local temp path. Returns the local path so the agent can feed it "
        "into pdf_analyze for a with_pdf re-validation pass."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "scraped_file_id": {"type": "integer"},
        },
        "required": ["scraped_file_id"],
    },
}


def _fetch_pdf_sync(scraped_file_id: int) -> Dict[str, Any]:
    from google.cloud import storage  # type: ignore[import-not-found]
    from google.oauth2 import service_account  # type: ignore[import-not-found]

    with _db() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT filename, storage_path, storage_bucket FROM scraped_files WHERE id=%s",
            (int(scraped_file_id),),
        )
        row = cur.fetchone()
    if not row:
        raise RuntimeError(f"scraped_file_id {scraped_file_id} not found")
    filename, storage_path, bucket_name = row
    if not bucket_name or not storage_path:
        raise RuntimeError(f"missing storage_path/bucket for {scraped_file_id}")

    sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if sa_json:
        creds = service_account.Credentials.from_service_account_info(json.loads(sa_json))
        client = storage.Client(credentials=creds)
    else:
        client = storage.Client()

    bucket = client.bucket(bucket_name)
    blob = bucket.blob(storage_path)
    local = Path("/tmp") / f"scrapper_{scraped_file_id}_{uuid.uuid4().hex[:8]}.pdf"
    blob.download_to_filename(str(local))
    return {
        "scraped_file_id": scraped_file_id,
        "local_path": str(local),
        "filename": filename,
        "bytes": local.stat().st_size,
    }


async def _handle_fetch_pdf(args: Dict[str, Any], **_kw: Any) -> str:
    try:
        res = await asyncio.to_thread(_fetch_pdf_sync, int(args["scraped_file_id"]))
    except Exception as e:
        return tool_error(f"scrapper_fetch_pdf: {e}")
    return json.dumps(res)


registry.register(
    name="scrapper_fetch_pdf",
    toolset="scrapper",
    schema=SCRAPPER_FETCH_PDF_SCHEMA,
    handler=_handle_fetch_pdf,
    check_fn=check_scrapper_requirements,
    is_async=True,
    emoji="⬇️",
)


# ---------------------------------------------------------------------------
# scrapper_inspect_flags
# ---------------------------------------------------------------------------


SCRAPPER_INSPECT_FLAGS_SCHEMA = {
    "name": "scrapper_inspect_flags",
    "description": (
        "Return recent REJECT validations or common issue codes for human-grade "
        "triage. Use when stats show a spike in rejections or errors."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "description": "Max rows (default 20)."},
            "issue_code": {
                "type": "string",
                "description": "Optional exact issue code to filter by.",
            },
        },
        "required": [],
    },
}


def _inspect_flags(limit: int, issue_code: Optional[str]) -> Dict[str, Any]:
    limit = max(1, min(int(limit or 20), 200))
    with _db() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT ai_issue_codes, COUNT(*) FROM question_validations "
            "WHERE evaluation_status = 'REJECT' AND ai_issue_codes <> '' "
            "GROUP BY 1 ORDER BY 2 DESC LIMIT 20"
        )
        top = [{"codes": r[0], "count": r[1]} for r in cur.fetchall()]

        sql = (
            "SELECT qv.question_id::text, qv.status_reason, qv.ai_issue_codes, "
            "sf.grade, sf.subject, sf.filename "
            "FROM question_validations qv "
            "JOIN raw_questions rq ON rq.id = qv.question_id "
            "JOIN scraped_files sf ON sf.id = rq.scraped_file_id "
            "WHERE qv.evaluation_status = 'REJECT'"
        )
        params: List[Any] = []
        if issue_code:
            sql += " AND position(%s in qv.ai_issue_codes) > 0"
            params.append(issue_code)
        sql += " ORDER BY qv.created_at DESC LIMIT %s"
        params.append(limit)
        cur.execute(sql, params)
        recent = [
            {
                "question_id": r[0],
                "reason": (r[1] or "")[:200],
                "codes": r[2],
                "grade": r[3],
                "subject": r[4],
                "filename": r[5],
            }
            for r in cur.fetchall()
        ]
    return {"top_issue_codes": top, "recent_rejects": recent}


async def _handle_inspect_flags(args: Dict[str, Any], **_kw: Any) -> str:
    try:
        return json.dumps(_inspect_flags(args.get("limit", 20), args.get("issue_code")))
    except Exception as e:
        return tool_error(f"scrapper_inspect_flags: {e}")


registry.register(
    name="scrapper_inspect_flags",
    toolset="scrapper",
    schema=SCRAPPER_INSPECT_FLAGS_SCHEMA,
    handler=_handle_inspect_flags,
    check_fn=check_scrapper_requirements,
    is_async=True,
    emoji="🚩",
)


# ---------------------------------------------------------------------------
# scrapper_audit — read-only data-quality snapshot
# ---------------------------------------------------------------------------


SCRAPPER_AUDIT_SCHEMA = {
    "name": "scrapper_audit",
    "description": (
        "Return a structured data-quality snapshot for the whole dataset: "
        "counts by validation_status, document_type, missing-metadata tallies, "
        "exam_sets coverage, and raw_questions garbage signals. Fast — read-only."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}


def _audit() -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    with _db() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT validation_status, COUNT(*) FROM scraped_files GROUP BY 1 ORDER BY 2 DESC"
        )
        out["scraped_files_by_validation_status"] = {k or "null": v for k, v in cur.fetchall()}

        cur.execute(
            "SELECT document_type, COUNT(*) FROM scraped_files GROUP BY 1 ORDER BY 2 DESC"
        )
        out["scraped_files_by_document_type"] = {k or "null": v for k, v in cur.fetchall()}

        cur.execute(
            """
            SELECT
                COUNT(*) FILTER (WHERE subject IS NULL OR subject = '' OR subject = 'Unknown-Subject'),
                COUNT(*) FILTER (WHERE grade IS NULL),
                COUNT(*) FILTER (WHERE year IS NULL),
                COUNT(*) FILTER (WHERE paper_number IS NULL AND document_type='Question Paper'),
                COUNT(*) FILTER (WHERE document_type IS NULL OR document_type = '')
            FROM scraped_files
            """
        )
        r = cur.fetchone()
        out["scraped_files_missing"] = {
            "subject": r[0],
            "grade": r[1],
            "year": r[2],
            "paper_number_on_qp": r[3],
            "document_type": r[4],
        }

        cur.execute("SELECT status, COUNT(*) FROM exam_sets GROUP BY 1 ORDER BY 2 DESC")
        out["exam_sets_by_status"] = {k or "null": v for k, v in cur.fetchall()}

        cur.execute(
            "SELECT "
            "  COUNT(*), "
            "  COUNT(*) FILTER (WHERE LENGTH(question_text) < 20), "
            "  COUNT(*) FILTER (WHERE confidence_score < 0.7) "
            "FROM raw_questions"
        )
        r = cur.fetchone()
        out["raw_questions"] = {
            "total": r[0],
            "short_text_under_20_chars": r[1],
            "confidence_below_0_7": r[2],
        }

        cur.execute("SELECT COUNT(*) FROM dead_letter_queue")
        out["dead_letter_queue"] = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM submodules")
        out["submodules_registered"] = cur.fetchone()[0]
    return out


async def _handle_audit(_args: Dict[str, Any], **_kw: Any) -> str:
    try:
        return json.dumps(_audit())
    except Exception as e:
        return tool_error(f"scrapper_audit: {e}")


registry.register(
    name="scrapper_audit",
    toolset="scrapper",
    schema=SCRAPPER_AUDIT_SCHEMA,
    handler=_handle_audit,
    check_fn=check_scrapper_requirements,
    is_async=True,
    emoji="📊",
)


# ---------------------------------------------------------------------------
# scrapper_queue_next_for_reinspection
# ---------------------------------------------------------------------------


SCRAPPER_QUEUE_NEXT_FOR_REINSPECTION_SCHEMA = {
    "name": "scrapper_queue_next_for_reinspection",
    "description": (
        "Pop the next N scraped_files that need content-based reclassification. "
        "Targets weak classifications (classified_filename, classified_header, "
        "classified_insufficient, review_required, unvalidated) and missing-metadata "
        "rows. Files already in 'vision_confirmed' state are skipped."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "limit": {"type": "integer"},
            "min_priority": {
                "type": "string",
                "description": "Filter: 'weak' (all weak statuses), 'missing_meta' (any NULL subject/grade/year/document_type), 'all' (both). Default 'all'.",
            },
        },
        "required": [],
    },
}


def _queue_reinspection(limit: int, priority: str) -> List[Dict[str, Any]]:
    limit = max(1, min(int(limit or 50), 500))
    where_parts: List[str] = []
    if priority in ("weak", "all"):
        where_parts.append(
            "validation_status IN ('classified_filename', 'classified_header', "
            "'classified_insufficient', 'review_required', 'unvalidated')"
        )
    if priority in ("missing_meta", "all"):
        where_parts.append(
            "(subject IS NULL OR subject='' OR subject='Unknown-Subject' "
            "OR grade IS NULL OR year IS NULL OR document_type IS NULL OR document_type='')"
        )
    clause = " OR ".join(f"({w})" for w in where_parts) if where_parts else "1=1"
    sql = (
        "SELECT id, filename, storage_path, storage_bucket, subject, grade, year, "
        "paper_number, session, language, document_type, validation_status "
        "FROM scraped_files "
        f"WHERE ({clause}) AND validation_status <> 'vision_confirmed' "
        "ORDER BY id LIMIT %s"
    )
    with _db() as conn, conn.cursor() as cur:
        cur.execute(sql, (limit,))
        rows = cur.fetchall()
    cols = [
        "id", "filename", "storage_path", "storage_bucket", "subject", "grade",
        "year", "paper_number", "session", "language", "document_type",
        "validation_status",
    ]
    return [dict(zip(cols, r)) for r in rows]


async def _handle_queue_reinspection(args: Dict[str, Any], **_kw: Any) -> str:
    try:
        items = _queue_reinspection(args.get("limit", 50), args.get("min_priority", "all"))
    except Exception as e:
        return tool_error(f"scrapper_queue_next_for_reinspection: {e}")
    return json.dumps({"count": len(items), "items": items})


registry.register(
    name="scrapper_queue_next_for_reinspection",
    toolset="scrapper",
    schema=SCRAPPER_QUEUE_NEXT_FOR_REINSPECTION_SCHEMA,
    handler=_handle_queue_reinspection,
    check_fn=check_scrapper_requirements,
    is_async=True,
    emoji="🔍",
)


# ---------------------------------------------------------------------------
# scrapper_reinspect_batch
# ---------------------------------------------------------------------------


SCRAPPER_REINSPECT_BATCH_SCHEMA = {
    "name": "scrapper_reinspect_batch",
    "description": (
        "Re-classify a batch of scraped_files using full PDF content. Downloads "
        "each PDF (cached), extracts text locally when possible, falls back to "
        "PDF vision for scanned papers, then calls Gemini 2.5 Flash for structured "
        "classification. High-confidence agreements set validation_status="
        "'vision_confirmed'. High-confidence disagreements update the row and "
        "write a flags audit entry. Low-confidence results flag for review. "
        "Terse summary returned."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "scraped_file_ids": {"type": "array", "items": {"type": "integer"}},
            "concurrency": {"type": "integer"},
            "autofix_threshold": {
                "type": "number",
                "description": "Minimum per-field confidence to auto-update a field (default 0.85).",
            },
            "review_threshold": {
                "type": "number",
                "description": "Below this overall_confidence, flag for review (default 0.6).",
            },
        },
        "required": ["scraped_file_ids"],
    },
}


_PDF_CACHE_DIR = Path(os.environ.get("SCRAPPER_PDF_CACHE", "/opt/scrapper-tool/pdf-cache"))


def _cached_pdf_path(scraped_file_id: int) -> Path:
    _PDF_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return _PDF_CACHE_DIR / f"{scraped_file_id}.pdf"


def _download_pdf_bytes(scraped_file_id: int, storage_path: str, bucket: str) -> bytes:
    """Read from local cache or download from GCS."""
    cached = _cached_pdf_path(scraped_file_id)
    if cached.exists() and cached.stat().st_size > 0:
        return cached.read_bytes()
    from google.cloud import storage as gcs  # type: ignore[import-not-found]
    from google.oauth2 import service_account  # type: ignore[import-not-found]

    sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if sa_json:
        creds = service_account.Credentials.from_service_account_info(json.loads(sa_json))
        client = gcs.Client(credentials=creds)
    else:
        client = gcs.Client()
    blob = client.bucket(bucket).blob(storage_path)
    data = blob.download_as_bytes()
    cached.write_bytes(data)
    return data


def _build_current_metadata(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "subject": row.get("subject"),
        "grade": row.get("grade"),
        "year": row.get("year"),
        "paper_number": row.get("paper_number"),
        "session": row.get("session"),
        "language": row.get("language"),
        "document_type": row.get("document_type"),
        "validation_status": row.get("validation_status"),
    }


def _apply_reinspection(
    row: Dict[str, Any],
    verdict: Any,
    autofix_threshold: float,
    review_threshold: float,
    cost_usd: float,
    model: str,
) -> Dict[str, Any]:
    """Compare verdict to current row, decide action, write to DB.

    Returns a small dict describing what happened for the batch summary.
    """
    sid = int(row["id"])
    current = _build_current_metadata(row)

    # Map verdict field name -> (current value, new value, per-field confidence)
    fields = [
        ("subject", verdict.subject),
        ("grade", verdict.grade),
        ("year", verdict.year),
        ("paper_number", verdict.paper_number),
        ("session", verdict.session),
        ("language", verdict.language),
        ("document_type", verdict.document_type),
    ]

    updates: Dict[str, Any] = {}
    disagreements: List[str] = []
    for name, fv in fields:
        new_val = fv.value
        if new_val in (None, ""):
            continue
        # Coerce int-bearing fields back to int
        if name in ("grade", "year", "paper_number"):
            try:
                new_val = int(str(new_val))
            except (TypeError, ValueError):
                continue
        cur_val = current.get(name)
        if cur_val == new_val:
            continue
        if fv.confidence >= autofix_threshold:
            updates[name] = new_val
            disagreements.append(f"{name}: {cur_val!r} -> {new_val!r} ({fv.confidence:.2f})")
        else:
            disagreements.append(f"{name}?: {cur_val!r} vs {new_val!r} ({fv.confidence:.2f})")

    new_status: Optional[str]
    if verdict.overall_confidence >= autofix_threshold:
        new_status = "vision_confirmed" if not updates else "vision_corrected"
    elif verdict.overall_confidence >= review_threshold:
        new_status = "vision_partial"
    else:
        new_status = "review_required"

    # Write DB changes
    with _db() as conn, conn.cursor() as cur:
        if updates or new_status:
            set_parts = []
            params: List[Any] = []
            for k, v in updates.items():
                set_parts.append(f"{k} = %s")
                params.append(v)
            if new_status:
                set_parts.append("validation_status = %s")
                params.append(new_status)
            set_parts.append("updated_at = NOW()")
            params.append(sid)
            cur.execute(
                f"UPDATE scraped_files SET {', '.join(set_parts)} WHERE id = %s",
                params,
            )

        # Audit row in flags — only when we actually changed something
        if disagreements or new_status == "review_required":
            category = "reinspection_autofix" if updates else "reinspection_flag"
            severity = "info" if updates else ("warning" if new_status == "review_required" else "info")
            description = (
                f"model={model} overall_conf={verdict.overall_confidence:.2f} "
                f"tier={verdict.tier_used} cost=${cost_usd:.6f} "
                f"disagreements=[{'; '.join(disagreements)[:600]}] "
                f"notes={verdict.notes[:200]!r}"
            )
            # flags.created_by is UUID NOT NULL — use a sentinel zero uuid
            sentinel_uuid = "00000000-0000-0000-0000-000000000000"
            cur.execute(
                "INSERT INTO flags (target_type, target_id, category, status, severity, "
                "description, created_by) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (
                    "scraped_file",
                    str(sid),
                    category,
                    "open",
                    severity,
                    description,
                    sentinel_uuid,
                ),
            )

    return {
        "scraped_file_id": sid,
        "new_status": new_status,
        "updates": list(updates.keys()),
        "overall_confidence": round(float(verdict.overall_confidence), 3),
        "tier": verdict.tier_used,
    }


async def _reinspect_one(
    reinspector: Any,
    row: Dict[str, Any],
    autofix_threshold: float,
    review_threshold: float,
    sem: asyncio.Semaphore,
) -> Dict[str, Any]:
    sid = int(row["id"])
    async with sem:
        try:
            pdf_bytes = await asyncio.to_thread(
                _download_pdf_bytes, sid, row["storage_path"], row["storage_bucket"]
            )
        except Exception as e:
            return {"scraped_file_id": sid, "ok": False, "error": f"download: {e}"[:240]}
        try:
            call = await reinspector.reinspect(
                scraped_file_id=sid,
                filename=row.get("filename") or "",
                pdf_bytes=pdf_bytes,
                current_metadata=_build_current_metadata(row),
            )
        except Exception as e:
            return {"scraped_file_id": sid, "ok": False, "error": str(e)[:240]}
        try:
            applied = await asyncio.to_thread(
                _apply_reinspection,
                row,
                call.verdict,
                autofix_threshold,
                review_threshold,
                float(call.cost_usd),
                call.model,
            )
        except Exception as e:
            return {"scraped_file_id": sid, "ok": False, "error": f"db: {e}"[:240]}
        applied["ok"] = True
        applied["cost_usd"] = float(call.cost_usd)
        return applied


async def _handle_reinspect_batch(args: Dict[str, Any], **_kw: Any) -> str:
    ids = [int(x) for x in (args.get("scraped_file_ids") or [])]
    if not ids:
        return tool_error("scrapper_reinspect_batch: scraped_file_ids is empty")
    concurrency = max(1, min(int(args.get("concurrency") or 10), 20))
    autofix = float(args.get("autofix_threshold") or 0.85)
    review = float(args.get("review_threshold") or 0.60)

    FileReinspector, _Err, _RCR = _import_reinspector()
    gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not gemini_key:
        return tool_error("scrapper_reinspect_batch: GEMINI_API_KEY not set")
    model = os.environ.get("SCRAPPER_REINSPECT_MODEL", "gemini-2.5-flash").strip()
    reinspector = FileReinspector(api_key=gemini_key.strip(), model=model)

    # Load rows from DB
    with _db() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, filename, storage_path, storage_bucket, subject, grade, year, "
            "paper_number, session, language, document_type, validation_status "
            "FROM scraped_files WHERE id = ANY(%s)",
            (ids,),
        )
        cols = [
            "id", "filename", "storage_path", "storage_bucket", "subject", "grade",
            "year", "paper_number", "session", "language", "document_type",
            "validation_status",
        ]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]

    found = {r["id"] for r in rows}
    missing = [i for i in ids if i not in found]

    sem = asyncio.Semaphore(concurrency)
    t0 = time.time()
    results = await asyncio.gather(
        *[_reinspect_one(reinspector, r, autofix, review, sem) for r in rows]
    )
    elapsed = time.time() - t0

    ok = sum(1 for r in results if r.get("ok"))
    errors = [r for r in results if not r.get("ok")]
    status_counts: Dict[str, int] = {}
    autofix_count = 0
    for r in results:
        if r.get("ok"):
            s = r.get("new_status") or "unknown"
            status_counts[s] = status_counts.get(s, 0) + 1
            if r.get("updates"):
                autofix_count += 1
    cost_total = sum(float(r.get("cost_usd") or 0) for r in results if r.get("ok"))

    summary = {
        "processed": len(results),
        "ok": ok,
        "errors": len(errors),
        "missing": missing,
        "autofix_count": autofix_count,
        "by_new_status": status_counts,
        "cost_usd": round(cost_total, 6),
        "elapsed_s": round(elapsed, 2),
        "model": model,
        "provider": "gemini",
    }
    if errors:
        summary["error_samples"] = errors[:3]
    return json.dumps(summary)


registry.register(
    name="scrapper_reinspect_batch",
    toolset="scrapper",
    schema=SCRAPPER_REINSPECT_BATCH_SCHEMA,
    handler=_handle_reinspect_batch,
    check_fn=check_scrapper_requirements,
    is_async=True,
    emoji="🔬",
)
