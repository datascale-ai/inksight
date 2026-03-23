"""Inksight Focus-mode alert external skill.

This skill is designed for high-priority QQ group emergency escalation:
- receive a minimal alert payload from the planner
- sanitize the summary to <= 20 chars
- resolve per-device token from env
- push critical alert to Inksight Focus endpoint
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Any

import httpx

# NOTE:
# External skill loader checks subclassing against `co_claw.core.skill.base.Skill`.
# Using `src.co_claw...` may create a different class identity and fail discovery.
from co_claw.core.skill.base import Skill, SkillResult

logger = logging.getLogger(__name__)


def _rule_compress_summary(text: str, limit: int = 20) -> str:
    """Level-1 summary: deterministic local compression."""
    s = (text or "").strip()
    if not s:
        return ""
    # Remove common filler words and punctuation noise.
    for token in ["请问", "麻烦", "一下", "尽快", "帮忙", "谢谢", "好的", "就是", "这个", "那个"]:
        s = s.replace(token, "")
    s = s.replace("\n", " ")
    s = " ".join(s.split())
    s = s.strip(" ，。！？、；：:,.!?")
    return s[:limit]


async def _llm_compress_summary(text: str, limit: int = 20) -> str:
    """Level-2 summary: LLM compression with strict fallback safety.

    Uses OpenAI-compatible endpoint from env:
      OPENAI_API_BASE / OPENAI_API_KEY / OPENAI_MODEL
    """
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    api_base = os.getenv("OPENAI_API_BASE", "").strip().rstrip("/")
    model = os.getenv("OPENAI_MODEL", "").strip() or "gpt-4o-mini"
    if not api_key or not api_base:
        return ""

    prompt = (
        "请把下面消息压缩成20字以内的中文陈述句或祈使句，只输出一句结果，不要解释：\n"
        f"{text}"
    )
    url = f"{api_base}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": "你是精简摘要助手。输出必须<=20字。"},
            {"role": "user", "content": prompt},
        ],
    }
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
        if not (200 <= resp.status_code < 300):
            return ""
        data = resp.json()
        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        content = str(content).strip().replace("\n", " ")
        return content[:limit]
    except Exception:
        return ""


def _parse_csv_env(name: str) -> list[str]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _contains_ci(items: list[str], value: str) -> bool:
    if not value:
        return False
    needle = value.strip().lower()
    return any(str(i).strip().lower() == needle for i in items)


def _normalize_mac(value: str) -> str:
    """Normalize common MAC formats to uppercase colon-separated form.

    Returns empty string when input does not look like a MAC address.
    """
    text = (value or "").strip().upper()
    if not text:
        return ""
    compact = text.replace("-", "").replace(":", "")
    if len(compact) != 12 or any(c not in "0123456789ABCDEF" for c in compact):
        return ""
    return ":".join(compact[i:i + 2] for i in range(0, 12, 2))


def _contains_any_keyword(text: str, keywords: list[str]) -> bool:
    if not keywords:
        return True
    lowered = text.lower()
    return any(k.lower() in lowered for k in keywords)


def _has_mention_target(raw_text: str, mentioned_users: list[str], targets: list[str]) -> bool:
    if not targets:
        return False
    mentioned_set = {u.strip().lower() for u in mentioned_users if u and u.strip()}
    raw_lower = raw_text.lower()
    for target in targets:
        t = target.strip().lower()
        if not t:
            continue
        # Position-independent matching: mention can appear anywhere in text.
        if t in mentioned_set:
            return True
        if f"@{t}" in raw_lower:
            return True
    return False


def _load_token(mac_address: str) -> tuple[str | None, str | None]:
    """Resolve token from map first, then fallback token.

    Returns:
        (token, error_message)
    """
    token_map_raw = os.getenv("INKSIGHT_ALERT_TOKEN_MAP", "").strip()
    fallback_token = os.getenv("INKSIGHT_ALERT_TOKEN", "").strip()

    if token_map_raw:
        try:
            token_map = json.loads(token_map_raw)
            if isinstance(token_map, dict):
                mapped = token_map.get(mac_address)
                if isinstance(mapped, str) and mapped.strip():
                    return mapped.strip(), None
        except Exception:
            # Keep fallback behavior even when token-map JSON is malformed.
            pass

    if fallback_token:
        return fallback_token, None

    return None, "AUTH_MISSING: no token in INKSIGHT_ALERT_TOKEN_MAP or INKSIGHT_ALERT_TOKEN"


def _load_vip_name_map() -> dict[str, str]:
    """Load VIP display-name mapping from env JSON.

    Env format:
      FOCUS_VIP_USER_NAME_MAP='{"<sender_id>":"<display_name>"}'
    """
    raw = os.getenv("FOCUS_VIP_USER_NAME_MAP", "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            return {}
        result: dict[str, str] = {}
        for k, v in data.items():
            key = str(k).strip()
            val = str(v).strip()
            if key and val:
                result[key] = val
        return result
    except Exception:
        return {}


class InksightAlertSkill(Skill):
    @property
    def name(self) -> str:
        return "send_to_inksight_focus_mode"

    @property
    def description(self) -> str:
        return (
            "When high-priority emergency QQ @mentions from executives/VIP senders are detected, "
            "push a critical local-refresh alert popup to Inksight e-ink devices to trigger Focus mode."
        )

    def get_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "mac_address": {
                    "type": "string",
                    "description": "Target Inksight device MAC address.",
                },
                "sender": {
                    "type": "string",
                    "description": "QQ sender nickname.",
                },
                "sender_id": {
                    "type": "string",
                    "description": "Stable sender ID from channel (recommended for whitelist checks).",
                },
                "channel": {
                    "type": "string",
                    "description": "Message channel source, e.g. qq_group / qq_guild.",
                },
                "message_summary": {
                    "type": "string",
                    "description": "Ultra-short command summary (max 20 chars).",
                },
                "raw_message": {
                    "type": "string",
                    "description": "Optional original QQ message text for policy checks.",
                },
                "mentioned_users": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of users that were @mentioned in the message.",
                },
            },
            "required": ["mac_address", "sender", "message_summary"],
        }

    async def execute(
        self,
        params: dict[str, Any] | None = None,
        _context: Any | None = None,
        **kwargs: Any,
    ) -> SkillResult:
        """Execute alert push with full error isolation.

        Note:
        - Supports co-claw runtime call style: execute(params, context)
        - Also supports execute(**kwargs) style requested by external integration
        """
        trace_id = uuid.uuid4().hex[:12]
        final_status = "ERROR"
        final_detail = ""
        final_error = ""
        resp_status: int | None = None
        target_url = ""
        try:
            payload_in = params if isinstance(params, dict) else {}
            if kwargs:
                payload_in = {**payload_in, **kwargs}

            context_meta = getattr(_context, "metadata", {}) if _context is not None else {}
            if not isinstance(context_meta, dict):
                context_meta = {}

            mac_address = str(payload_in.get("mac_address", "")).strip()
            sender = str(payload_in.get("sender", "")).strip()
            sender_id = str(payload_in.get("sender_id", "")).strip()
            channel = str(payload_in.get("channel", "")).strip()
            raw_summary_input = str(payload_in.get("message_summary", "")).strip()
            message_summary = _rule_compress_summary(raw_summary_input, limit=20)
            summary_strategy = "rule"
            if raw_summary_input and len(raw_summary_input) > 20:
                llm_summary = await _llm_compress_summary(raw_summary_input, limit=20)
                if llm_summary:
                    message_summary = llm_summary
                    summary_strategy = "llm"
            if not message_summary:
                message_summary = str(raw_summary_input).strip()[:20]
                summary_strategy = "trim"
            raw_message = str(payload_in.get("raw_message", "")).strip()
            mentioned_users_input = payload_in.get("mentioned_users", [])
            mentioned_users = (
                [str(u).strip() for u in mentioned_users_input if str(u).strip()]
                if isinstance(mentioned_users_input, list)
                else []
            )

            # Use channel metadata as trusted source to avoid LLM-generated sender drift.
            sender = str(context_meta.get("sender_name") or sender).strip()
            sender_id = str(context_meta.get("sender_id") or sender_id).strip()
            channel = str(context_meta.get("channel") or channel).strip()
            raw_message = str(context_meta.get("raw_message") or raw_message).strip()
            if not mentioned_users:
                from_meta = context_meta.get("mentioned_users")
                if isinstance(from_meta, list):
                    mentioned_users = [str(u).strip() for u in from_meta if str(u).strip()]

            # Sender display name for downstream device notification:
            # - identity gate uses sender_id only (stable)
            # - outgoing sender text prefers configured VIP name mapping
            vip_name_map = _load_vip_name_map()
            sender_display = (
                vip_name_map.get(sender_id)
                or sender
                or sender_id
                or "VIP用户"
            )
            logger.info(
                "InksightAlert start trace=%s sender_id=%s sender=%s channel=%s raw_len=%s summary_len=%s summary_strategy=%s",
                trace_id,
                sender_id,
                sender_display,
                channel,
                len(raw_message),
                len(message_summary),
                summary_strategy,
            )

            mac_address = _normalize_mac(mac_address)
            if not mac_address:
                fallback_mac = _normalize_mac(os.getenv("FOCUS_DEFAULT_MAC_ADDRESS", "").strip())
                if fallback_mac:
                    mac_address = fallback_mac
                else:
                    logger.info(
                        "InksightAlert blocked: trace=%s invalid or missing mac_address and no valid FOCUS_DEFAULT_MAC_ADDRESS",
                        trace_id,
                    )

            if not mac_address or not sender_display or not message_summary:
                logger.info(
                    "InksightAlert blocked: trace=%s missing required fields (mac=%s sender_display=%s summary_len=%s)",
                    trace_id,
                    bool(mac_address),
                    bool(sender_display),
                    len(message_summary),
                )
                final_status = "FAILED"
                final_detail = "missing required fields"
                final_error = "missing required fields"
                return SkillResult(
                    success=False,
                    data={
                        "status": "FAILED",
                        "detail": "FAILED: missing required fields (mac_address, sender_display, message_summary)",
                    },
                    error="missing required fields",
                )

            # Policy gate (self-contained; decoupled from planner/core):
            # Trigger only when sender, mention, and urgency constraints are satisfied.
            vip_user_ids = _parse_csv_env("FOCUS_VIP_USER_IDS")
            urgent_keywords = _parse_csv_env("FOCUS_URGENT_KEYWORDS")
            mention_targets = _parse_csv_env("FOCUS_MENTION_TARGETS")

            if not mention_targets:
                logger.info(
                    "InksightAlert blocked by mention gate: trace=%s FOCUS_MENTION_TARGETS is empty (fail-closed)",
                    trace_id,
                )
                final_status = "FAILED"
                final_detail = "FOCUS_MENTION_TARGETS is empty"
                final_error = "policy_mention_targets_not_configured"
                return SkillResult(
                    success=False,
                    data={
                        "status": "FAILED",
                        "detail": "FAILED: FOCUS_MENTION_TARGETS is not configured",
                    },
                    error="policy_mention_targets_not_configured",
                )

            if not vip_user_ids:
                logger.info(
                    "InksightAlert blocked by VIP gate: trace=%s FOCUS_VIP_USER_IDS is empty (fail-closed)",
                    trace_id,
                )
                final_status = "FAILED"
                final_detail = "FOCUS_VIP_USER_IDS is empty"
                final_error = "policy_vip_user_ids_not_configured"
                return SkillResult(
                    success=False,
                    data={
                        "status": "FAILED",
                        "detail": "FAILED: FOCUS_VIP_USER_IDS is not configured",
                    },
                    error="policy_vip_user_ids_not_configured",
                )

            sender_ok = _contains_ci(vip_user_ids, sender_id)

            if not sender_ok:
                logger.info(
                    "InksightAlert blocked by VIP gate: trace=%s sender_id=%s sender=%s allowed_ids=%s channel=%s",
                    trace_id,
                    sender_id,
                    sender,
                    vip_user_ids,
                    channel,
                )
                detail = "FAILED: sender_id not in FOCUS_VIP_USER_IDS"
                final_status = "FAILED"
                final_detail = detail
                final_error = "policy_sender_not_allowed"
                return SkillResult(
                    success=False,
                    data={"status": "FAILED", "detail": detail},
                    error="policy_sender_not_allowed",
                )

            urgency_source = f"{raw_message} {message_summary}".strip()
            if urgent_keywords and not _contains_any_keyword(urgency_source, urgent_keywords):
                logger.info(
                    "InksightAlert blocked by urgency gate: trace=%s sender=%s summary=%s keywords=%s",
                    trace_id,
                    sender,
                    message_summary,
                    urgent_keywords,
                )
                final_status = "FAILED"
                final_detail = "no urgent keyword matched"
                final_error = "policy_not_urgent"
                return SkillResult(
                    success=False,
                    data={
                        "status": "FAILED",
                        "detail": "FAILED: no urgent keyword matched",
                    },
                    error="policy_not_urgent",
                )

            if mention_targets and not _has_mention_target(raw_message, mentioned_users, mention_targets):
                logger.info(
                    "InksightAlert blocked by mention gate (position-independent): trace=%s sender=%s mention_targets=%s mentioned_users=%s raw_message=%s",
                    trace_id,
                    sender,
                    mention_targets,
                    mentioned_users,
                    raw_message[:120],
                )
                final_status = "FAILED"
                final_detail = "no mention target matched"
                final_error = "policy_mention_not_matched"
                return SkillResult(
                    success=False,
                    data={
                        "status": "FAILED",
                        "detail": "FAILED: no mention target matched",
                    },
                    error="policy_mention_not_matched",
                )

            base_url = os.getenv("INKSIGHT_BASE_URL", "").strip().rstrip("/")
            if not base_url:
                final_status = "FAILED"
                final_detail = "missing INKSIGHT_BASE_URL"
                final_error = "missing INKSIGHT_BASE_URL"
                return SkillResult(
                    success=False,
                    data={
                        "status": "FAILED",
                        "detail": "FAILED: missing INKSIGHT_BASE_URL",
                    },
                    error="missing INKSIGHT_BASE_URL",
                )

            token, token_err = _load_token(mac_address)
            if not token:
                logger.warning("InksightAlert auth missing: trace=%s mac=%s err=%s", trace_id, mac_address, token_err)
                final_status = "FAILED"
                final_detail = str(token_err)
                final_error = str(token_err)
                return SkillResult(
                    success=False,
                    data={
                        "status": "FAILED",
                        "detail": f"FAILED: {token_err}",
                    },
                    error=token_err,
                )

            url = f"{base_url}/api/device/{mac_address}/alert"
            target_url = url
            body = {
                "sender": sender_display,
                "message": message_summary,
                "level": "critical",
            }
            headers = {
                "Content-Type": "application/json",
                "X-Agent-Token": token,
            }

            logger.info(
                "InksightAlert sending: trace=%s mac=%s sender_id=%s sender=%s channel=%s summary=%s",
                trace_id,
                mac_address,
                sender_id,
                sender_display,
                channel,
                message_summary,
            )
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(url, json=body, headers=headers)
            resp_status = resp.status_code

            if 200 <= resp.status_code < 300:
                logger.info("InksightAlert success: trace=%s mac=%s status=%s", trace_id, mac_address, resp.status_code)
                final_status = "SUCCESS"
                final_detail = f"upstream {resp.status_code}"
                return SkillResult(
                    success=True,
                    data={
                        "status": "SUCCESS",
                        "detail": "SUCCESS: alert pushed to Inksight Focus mode",
                        "mac_address": mac_address,
                        "sender": sender_display,
                        "message_summary": message_summary,
                    },
                )

            logger.warning(
                "InksightAlert upstream failed: trace=%s mac=%s status=%s body=%s",
                trace_id,
                mac_address,
                resp.status_code,
                resp.text[:300],
            )
            final_status = "FAILED"
            final_detail = f"upstream returned {resp.status_code}"
            final_error = f"upstream status {resp.status_code}"
            return SkillResult(
                success=False,
                data={
                    "status": "FAILED",
                    "detail": f"FAILED: upstream returned {resp.status_code}",
                    "response_text": resp.text[:300],
                },
                error=f"upstream status {resp.status_code}",
            )
        except Exception as exc:
            # Never raise to break the main agent process.
            err_text = str(exc) or exc.__class__.__name__
            logger.exception("InksightAlert exception: trace=%s err=%s", trace_id, err_text)
            final_status = "ERROR"
            final_detail = err_text
            final_error = err_text
            return SkillResult(
                success=False,
                data={
                    "status": "ERROR",
                    "detail": f"ERROR: exception while pushing alert: {err_text}",
                },
                error=err_text,
            )
        finally:
            logger.info(
                "InksightAlert done: trace=%s status=%s detail=%s error=%s target=%s http_status=%s",
                trace_id,
                final_status,
                final_detail,
                final_error,
                target_url,
                resp_status,
            )