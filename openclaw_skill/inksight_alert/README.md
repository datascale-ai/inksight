# Inksight Alert External Skill

This package is a decoupled external skill for Co-Claw/OpenClaw deployments.
It can be copied into another project with minimal integration effort.

## Files

- `skill.py`: executable external skill implementation.
- `SKILL.md`: planner-facing usage and trigger guidance.
- `.env.example`: environment variable template.

## Deployment

1. Copy this directory to your target project's `external_skills/`.
2. Ensure project config includes this directory in `skills.external_dirs`.
3. Configure env vars (see `.env.example`).
4. Reload external skills:
   - `POST /api/skills/reload`
   - or restart backend service.

## Runtime Policy Gates

The skill performs hard policy checks internally (fail-closed):

- `FOCUS_VIP_USER_IDS`: sender_id must be in this whitelist.
- `FOCUS_URGENT_KEYWORDS`: `raw_message + message_summary` must include one urgent keyword.
- `FOCUS_MENTION_TARGETS`: message must @mention one configured target.

This allows deployment without changing core planner/channel code.

## Required Env Vars

- `INKSIGHT_BASE_URL`
- `INKSIGHT_ALERT_TOKEN_MAP` or `INKSIGHT_ALERT_TOKEN`

## Optional Env Vars

- `FOCUS_VIP_USER_IDS`
- `FOCUS_VIP_USER_NAME_MAP`
- `FOCUS_URGENT_KEYWORDS`
- `FOCUS_MENTION_TARGETS`
- `FOCUS_DEFAULT_MAC_ADDRESS`

Notes:

- VIP gate relies on stable `sender_id` (not nickname).
- Outgoing sender display can be mapped by `FOCUS_VIP_USER_NAME_MAP`.
- If `mac_address` is empty/invalid, skill falls back to `FOCUS_DEFAULT_MAC_ADDRESS`.

## Example Params

```json
{
  "mac_address": "AA:BB:CC:DD:EE:FF",
  "sender": "张总",
  "sender_id": "CD8AAB72ED26BD50FF148013996DB264",
  "message_summary": "支付服务宕机速查",
  "raw_message": "@值班SRE 支付服务宕机了，速来",
  "mentioned_users": ["值班SRE"]
}
```

