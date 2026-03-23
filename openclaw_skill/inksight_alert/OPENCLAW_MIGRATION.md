# Inksight Alert 迁移说明（OpenClaw）

本文档把本次改造整理为“可迁移、低耦合”的交付方案，方便用户在自己的 OpenClaw 项目中落地。

目标：优先使用 `external_skills/inksight_alert` 自包含能力完成部署。

---

## 1. 交付内容（建议直接拷贝）

将以下文件整体拷贝到目标项目的 `external_skills/inksight_alert/`：

- `skill.py`
- `SKILL.md`
- `README.md`
- `OPENCLAW_MIGRATION.md`（本文件）

---

## 2. 已实现能力（在 `skill.py` 内）

当前 `InksightAlertSkill` 已具备以下能力：

- 工具名：`send_to_inksight_focus_mode`
- 入参 schema：
  - `mac_address`
  - `sender`
  - `message_summary`
  - `raw_message`
  - `mentioned_users`
- 执行前清洗：`message_summary` 强制截断到 20 字符
- 动态鉴权：
  - 优先 `INKSIGHT_ALERT_TOKEN_MAP`
  - 回退 `INKSIGHT_ALERT_TOKEN`
- 请求协议：
  - `POST {INKSIGHT_BASE_URL}/api/device/{mac}/alert`
  - Header: `X-Agent-Token`
  - Body: `{"sender": ..., "message": ..., "level": "critical"}`
- 异常保护：永不抛异常阻断主流程，返回 `SUCCESS/FAILED/ERROR`
- 完整调试日志：
  - `start` / `blocked` / `sending` / `success|upstream failed` / `done`

---

## 3. 当前门控规则（严格）

只有同时满足以下 3 个条件才触发下发：

1. `sender_id` 命中 `FOCUS_VIP_USER_IDS`
2. `raw_message + message_summary` 命中 `FOCUS_URGENT_KEYWORDS`
3. `@target` 命中 `FOCUS_MENTION_TARGETS`（任意位置匹配，不要求在开头）

并且：

- `FOCUS_VIP_USER_IDS` 未配置时：`fail-closed`（不触发）
- `FOCUS_MENTION_TARGETS` 未配置时：`fail-closed`（不触发）
- `mac_address` 非法或为空时：
  - 自动回退 `FOCUS_DEFAULT_MAC_ADDRESS`
  - 回退值也非法则不触发
- 为保证鉴权稳定，VIP 判定依赖稳定 `sender_id`，不依赖昵称；展示名可由 `FOCUS_VIP_USER_NAME_MAP` 映射。

---

## 4. 目标项目配置要求

确保目标项目配置了 external skills 扫描目录，例如：

```yaml
skills:
  external_dirs:
    - "./external_skills"
```

环境变量建议最小集：

```env
INKSIGHT_BASE_URL=https://your-inksight-host
INKSIGHT_ALERT_TOKEN_MAP={"AA:BB:CC:DD:EE:FF":"token_xxx"}
INKSIGHT_ALERT_TOKEN=

FOCUS_VIP_USER_IDS=QQ_OPENID_1,QQ_OPENID_2
FOCUS_URGENT_KEYWORDS=宕机,速来,线上事故,P0,全站不可用
FOCUS_MENTION_TARGETS=测试员,值班SRE
FOCUS_VIP_USER_NAME_MAP={"QQ_OPENID_1":"老板","QQ_OPENID_2":"运维负责人"}
FOCUS_DEFAULT_MAC_ADDRESS=88:56:A6:7B:C7:0C
```

---

## 5. 为什么推荐按 `sender_id` 而不是昵称

QQ 场景中“显示名/群昵称”会随场景与账号设置变化，不适合作为强鉴权依据。  
`sender_id`（openid/member_openid）稳定，适合作为 VIP 白名单主键。

---

## 6. 与 Core 的关系（解耦边界）

### 必需改动（可零 core 改动）

- 仅拷贝 `external_skills/inksight_alert` 目录
- 配置 `external_dirs` + 环境变量

该模式即可运行，但 `sender_id/sender` 的质量取决于目标项目通道层是否有透传。

### 可选增强（建议，但不强制）

如果目标 OpenClaw 的 QQ 适配层支持 `extra/metadata`，建议将以下字段注入到会话上下文：

- `sender_id`
- `sender_name`
- `raw_message`
- `mentioned_users`

本技能会优先使用这些通道事实字段，避免 LLM 改写参数导致误判。  
注意：虽然工具入参不要求显式传 `sender_id`，但门控本身依赖 `sender_id`，因此建议在通道层稳定透传。

---

## 7. 迁移后自检清单

1. `/api/skills` 能看到 `send_to_inksight_focus_mode`
2. 触发样例日志出现 `InksightAlert start` 与 `sending`
3. 若失败，`InksightAlert done` 能看到具体 `status/detail/error`
4. Inksight 后端能收到：
   - `POST /api/device/{mac}/alert`
   - `X-Agent-Token`
   - `sender/message/level`

---

## 8. 常见问题

- **Q: 工具被调用但没下发？**  
  A: 看 `InksightAlert done` 的 `status/detail/error`，优先排查门控与网络。

- **Q: sender 名字不稳定？**  
  A: 正常现象。白名单用 `FOCUS_VIP_USER_IDS`，名字仅用于展示。

- **Q: 为何 URL 里出现中文 MAC 占位文本？**  
  A: 旧逻辑把 LLM 占位词当有效 MAC。当前版本已加 MAC 合法性校验与回退。

