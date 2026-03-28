---
name: send_to_inksight_focus_mode
description: 仅在高优先级 QQ 紧急升级场景下使用此技能。它会在严格策略校验通过后，将关键告警推送到 Inksight 墨水屏的专注模式。
---

# Inksight 专注告警技能

## 用途

此技能用于将紧急告警推送到 Inksight 设备的专注模式。

## 严格触发策略

仅当以下所有条件都满足时，才可调用此技能：

1. 发送者 ID 位于 VIP 白名单中（`FOCUS_VIP_USER_IDS`）。
2. 消息具有紧急性质（包含故障 / 事故等语义）。
3. 消息中明确 @ 提到了已配置的目标用户。

任一条件不满足时，都不得调用此技能。

注意：
- 准入校验依赖稳定的 `sender_id`，而不是昵称。
- 对外展示的 `sender` 名称可通过 `FOCUS_VIP_USER_NAME_MAP` 进行映射。

## 输入规则

- `mac_address`：目标设备的 MAC 地址。若未提供，运行时可使用 `FOCUS_DEFAULT_MAC_ADDRESS`。
- `sender`：QQ 发送者昵称。
- `message_summary`：必填。必须简洁，且长度小于等于 20 个字符。
- `raw_message`（可选）：用于策略校验的原始消息文本。
- `mentioned_users`（可选）：消息中被 @ 的用户名列表。

## 摘要格式要求

调用前需要：

- 去除情绪化措辞和口头填充词
- 只保留可执行的信息
- 产出一条中文、中性、指令式的句子
- 使用两级摘要策略：
  - level-1：基于规则的压缩
  - level-2：可选的 LLM 压缩（若可用）
  - 回退方案：强制截断至 <= 20 个字符

## 预期结果

- 成功：返回 `status=SUCCESS`
- 策略不匹配或上游失败：返回 `status=FAILED`
- 异常安全回退：返回 `status=ERROR`
