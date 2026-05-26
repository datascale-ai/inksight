# 背单词模式

`VOCAB_REVIEW` 是内置背词模式，使用设备 MAC 独立保存进度。第一版使用项目内置 `core_en` 基础词库，不包含语音读词或自动判答。

## 固件环境

背词专用固件环境：

```bash
platformio run -e epd_42_wroom32e_vocab_review
```

该环境面向 ESP32-WROOM32E + 4.2 寸 400x300 黑白屏，功能键沿用 `GPIO23`，接法为一端接 `GPIO23`、另一端接 `GND`。它是背词专用功能键固件，不同于 `epd_42_wroom32e_ai_chat`。

## 按键语义

- 非背词模式：长按功能键进入背单词模式。
- 正面：短按翻到释义面。
- 反面：短按在 `忘了 / 模糊 / 记住` 间切换评分。
- 反面：长按提交当前评分并进入下一词。

## 评分语义

- `忘了`：10 分钟后再次复习，并记录一次遗忘。
- `模糊`：至少 1 天后复习，熟练度略降。
- `记住`：按简化 SM-2 增加间隔，首次 1 天，第二次 6 天，之后按熟练度增长。

## 模式设置

- `deck_id`：词库 ID，默认 `core_en`。
- `daily_limit`：每日复习总上限，默认 `30`。
- `new_cards_per_day`：每日新词上限，默认 `10`。

## 设备 API

```http
POST /api/device/{mac}/vocab/event
X-Device-Token: <device-token>
Content-Type: application/json
```

请求示例：

```json
{"action":"enter"}
```

支持的 `action`：`enter`、`flip`、`next_rating`、`submit_rating`。提交评分时可传 `rating`：`forgot`、`fuzzy`、`remember`。
