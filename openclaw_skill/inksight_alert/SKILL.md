---
name: send_to_inksight_focus_mode
description: Use this skill only for high-priority QQ emergency escalation. It pushes a critical alert to Inksight e-ink Focus mode after strict policy checks.
---

# Inksight Focus Alert Skill

## Purpose

This skill pushes emergency alerts to Inksight devices for Focus mode.

## Strict Trigger Policy

Call this skill only when all required conditions are satisfied:

1. Sender ID is in VIP whitelist (`FOCUS_VIP_USER_IDS`).
2. Message is urgent (contains outage/incident semantics).
3. Message explicitly @mentions configured target users.

If any condition is not met, do not call this skill.

Note:
- Gate checks rely on stable `sender_id` (not nickname).
- Outgoing `sender` display can be mapped by `FOCUS_VIP_USER_NAME_MAP`.

## Input Rules

- `mac_address`: target device MAC. If unavailable, runtime may use `FOCUS_DEFAULT_MAC_ADDRESS`.
- `sender`: QQ sender nickname.
- `message_summary`: required. Must be concise and less than or equal to 20 chars.
- `raw_message` (optional): original message text for policy checking.
- `mentioned_users` (optional): list of usernames that were @mentioned.

## Summary Formatting

Before calling:

- remove emotional words and filler words
- keep actionable content only
- produce a neutral command sentence in Chinese
- two-level summary strategy:
  - level-1: rule-based compression
  - level-2: optional LLM compression (if available)
  - fallback: hard trim to <= 20 chars

## Expected Outcome

- Success: returns `status=SUCCESS`
- Policy mismatch or upstream failure: returns `status=FAILED`
- Exception safety fallback: returns `status=ERROR`

