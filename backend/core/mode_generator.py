"""
AI 模式生成器
根据用户自然语言描述（和可选的参考图片）生成 InkSight 模式 JSON 定义
"""
from __future__ import annotations

import json
import logging
import re

from .content import _get_client, _clean_json_response
from .mode_registry import _validate_mode_def

logger = logging.getLogger(__name__)

# Vision-capable models per provider
VISION_MODELS = {
    "aliyun": {"qwen-vl-max", "qwen-vl-plus"},
}

AVAILABLE_ICONS = (
    "art, body, book, breakfast, cloud, cookie, dinner, electric_bolt, "
    "exercise, flag, foggy, food, global, lunch, meat, partly_cloudy, "
    "rainy, rice, snow, star, sunny, thunderstorm, tips, vegetable, vital, yes, zen"
)

# Compact examples embedded directly
_ZEN_EXAMPLE = """{
  "mode_id": "ZEN", "display_name": "禅意", "icon": "zen", "cacheable": true,
  "description": "极简汉字与意境注释",
  "content": {
    "type": "llm_json",
    "prompt_template": "你是一位禅宗大师。选择一个最适合当下环境的汉字，并说明为什么选这个字。\\n用 JSON 输出：{{\\"word\\": \\"一个汉字\\", \\"source\\": \\"出处或意境说明（10字以内）\\"}}\\n只输出一个字和一句意境说明。\\n环境：{context}",
    "output_schema": { "word": { "type": "string", "default": "静" }, "source": { "type": "string", "default": "万物归寂" } },
    "temperature": 0.8,
    "fallback": { "word": "静", "source": "万物归寂" }
  },
  "layout": {
    "status_bar": { "line_width": 1, "dashed": true },
    "body": [
      { "type": "centered_text", "field": "word", "font": "noto_serif_regular", "font_size": 96, "max_width_ratio": 0.7, "vertical_center": true },
      { "type": "spacer", "height": 10 },
      { "type": "text", "field": "source", "font": "noto_serif_light", "font_size": 9, "align": "center", "max_lines": 1 }
    ],
    "footer": { "label": "ZEN", "attribution_template": "— ..." }
  }
}"""

_STOIC_EXAMPLE = """{
  "mode_id": "STOIC", "display_name": "斯多葛哲学", "icon": "book", "cacheable": true,
  "description": "庄重、内省的哲学语录，附当代解读",
  "content": {
    "type": "llm_json",
    "prompt_template": "你是一位斯多葛哲学导师。根据当前情境选择一个斯多葛核心概念，用一句原文语录+一句当代解读呈现。\\n用 JSON 输出：{{\\"quote\\": \\"语录原文（40字以内）\\", \\"author\\": \\"作者\\", \\"interpretation\\": \\"当代解读（20字以内）\\"}}\\n只输出 JSON。\\n环境：{context}",
    "output_schema": {
      "quote": { "type": "string", "default": "The impediment to action advances action." },
      "author": { "type": "string", "default": "Marcus Aurelius" },
      "interpretation": { "type": "string", "default": "挡路的石头，本身就是路。" }
    },
    "temperature": 0.8,
    "fallback": { "quote": "The impediment to action advances action.", "author": "Marcus Aurelius", "interpretation": "挡路的石头，本身就是路。" }
  },
  "layout": {
    "status_bar": { "line_width": 1 },
    "body": [
      { "type": "centered_text", "field": "quote", "font": "noto_serif_regular", "font_size": 20, "max_width_ratio": 0.88, "vertical_center": true }
    ],
    "footer": { "label": "STOIC", "attribution_template": "— {author}" }
  }
}"""


def _build_generation_prompt(description: str) -> str:
    """Build the meta-prompt that teaches the LLM to produce valid mode JSON."""
    return f"""你是 InkSight 模式设计助手。InkSight 是一个墨水屏桌面伴侣，屏幕 400x300 像素，1位黑白显示。

你的任务是根据用户描述，生成一个完整有效的 InkSight 模式 JSON 定义。

## 模式 JSON 结构规范

### 顶层字段（全部必填除 icon/cacheable/description）
- mode_id: 大写字母+数字+下划线，2-32字符，以字母开头，如 "MY_VOCAB"
- display_name: 显示名称，最长32字符
- icon: 图标名，可选值: {AVAILABLE_ICONS}
- cacheable: 布尔值，是否可缓存（默认 true）
- description: 简短描述，最长200字符

### content 配置（推荐 "llm_json" 类型）
- type: "llm_json"
- prompt_template: LLM 提示词，**必须**包含 {{context}} 占位符。提示词中的 JSON 示例必须用双花括号 {{{{ }}}} 转义
- output_schema: 定义输出字段，每个字段有 type（"string"/"number"/"array"/"boolean"）和 default
- temperature: 0.0-2.0，推荐 0.7-0.9
- fallback: 兜底数据，字段必须与 output_schema 完全对应

### layout 配置
- status_bar: {{"line_width": 1}} 或 {{"line_width": 1, "dashed": true}}
- body: 布局块数组（从上到下渲染），**至少一个块**
- footer: {{"label": "MODE_ID", "attribution_template": "— {{field_name}}"}}

### 可用布局块类型
- centered_text: 居中大文本。字段: field, font, font_size, vertical_center(bool), max_width_ratio(0.3-1.0)
- text: 普通文本。字段: field 或 template, font, font_size, align(left/center/right), margin_x, max_lines
- separator: 分隔线。字段: style(solid/dashed/short), margin_x
- spacer: 间距。字段: height
- list: 列表。字段: field(数组字段名), max_items, item_template, numbered(bool), item_spacing, margin_x
- section: 带标题区块。字段: title, icon, children(子块数组)
- icon_text: 图标+文字行。字段: icon, text/field, font_size
- two_column: 双栏。字段: left(块数组), right(块数组), left_width, gap
- big_number: 大数字。字段: field, font_size, align
- key_value: 键值对。字段: field, label, font_size
- group: 分组。字段: title, children(子块数组)

### 可用字体
noto_serif_light, noto_serif_regular, noto_serif_bold, lora_regular, lora_bold

## 示例1：禅意模式（大字居中）
{_ZEN_EXAMPLE}

## 示例2：斯多葛模式（语录+归属）
{_STOIC_EXAMPLE}

## 设计要点
1. 屏幕只有 400x300 像素，内容要精简，不要塞太多内容
2. 1位黑白显示，无灰度，设计要简洁
3. font_size 推荐: 标题 14-18, 正文 12-14, 注释 9-11, 大字展示 36-96
4. fallback 数据必须完整，包含所有 output_schema 的字段
5. prompt_template 中演示 JSON 格式时必须用双花括号 {{{{}}}} 转义，但 {{context}} 保持单花括号
6. body 数组不要过长，一般 2-6 个块即可

## 用户需求
{description}

请直接输出完整有效的 JSON 模式定义，不要输出任何其他内容。"""


def _supports_vision(provider: str, model: str) -> bool:
    """Check if the given provider/model supports image input."""
    models = VISION_MODELS.get(provider, set())
    return model in models


def _build_messages(prompt: str, image_base64: str | None = None,
                    provider: str = "", model: str = "") -> list[dict]:
    """Build OpenAI-compatible messages, optionally with image."""
    if image_base64 and _supports_vision(provider, model):
        # Strip data URL prefix if present
        if "," in image_base64 and image_base64.startswith("data:"):
            image_base64 = image_base64.split(",", 1)[1]
        return [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {
                    "url": f"data:image/jpeg;base64,{image_base64}"
                }},
            ],
        }]
    return [{"role": "user", "content": prompt}]


async def _call_llm_with_messages(
    provider: str,
    model: str,
    messages: list[dict],
    temperature: float = 0.3,
    max_tokens: int = 2048,
) -> str:
    """Call LLM with pre-built messages (supports multimodal)."""
    client, _ = _get_client(provider, model)
    response = await client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    text = response.choices[0].message.content.strip()

    finish_reason = response.choices[0].finish_reason
    usage = response.usage
    logger.info(
        f"[MODE_GEN] {provider}/{model} tokens={usage.total_tokens}, "
        f"finish={finish_reason}"
    )
    if finish_reason == "length":
        logger.warning("[MODE_GEN] Response truncated due to max_tokens limit")

    return text


def _auto_fix(definition: dict) -> dict:
    """Auto-fix common issues in LLM-generated mode definitions."""
    # Force mode_id uppercase
    mode_id = definition.get("mode_id", "")
    if isinstance(mode_id, str):
        mode_id = re.sub(r"[^A-Z0-9_]", "_", mode_id.upper())
        if not mode_id or not mode_id[0].isalpha():
            mode_id = "MY_" + mode_id
        definition["mode_id"] = mode_id[:32]

    # Ensure display_name exists
    if not definition.get("display_name"):
        definition["display_name"] = mode_id.replace("_", " ").title()

    # Ensure content section
    content = definition.get("content", {})

    # Ensure prompt_template contains {context}
    pt = content.get("prompt_template", "")
    if isinstance(pt, str) and "{context}" not in pt:
        content["prompt_template"] = pt + "\n环境：{context}"

    # Ensure fallback has all output_schema fields
    schema = content.get("output_schema", {})
    fallback = content.get("fallback", {})
    if schema and isinstance(schema, dict) and isinstance(fallback, dict):
        for key, field_def in schema.items():
            if key not in fallback:
                default = ""
                if isinstance(field_def, dict):
                    default = field_def.get("default", "")
                fallback[key] = default
        content["fallback"] = fallback

    # Ensure layout.body exists and is non-empty
    layout = definition.get("layout", {})
    body = layout.get("body", [])
    if not body:
        layout["body"] = [{"type": "centered_text", "field": "text",
                           "font_size": 16, "vertical_center": True}]
    definition["layout"] = layout

    # Ensure footer label matches mode_id
    footer = layout.get("footer", {})
    if not footer.get("label"):
        footer["label"] = definition.get("mode_id", "CUSTOM")
        layout["footer"] = footer

    return definition


async def generate_mode_definition(
    description: str,
    image_base64: str | None = None,
    provider: str = "deepseek",
    model: str = "deepseek-chat",
) -> dict:
    """Generate a mode JSON definition from natural language description.

    Returns dict with keys: ok, mode_def (on success), error (on failure),
    warning (optional).
    """
    warning = None

    # Check vision support
    if image_base64 and not _supports_vision(provider, model):
        warning = "当前模型不支持图片输入，已忽略上传的图片"
        image_base64 = None

    prompt = _build_generation_prompt(description)
    messages = _build_messages(prompt, image_base64, provider, model)

    # Call LLM
    raw_text = await _call_llm_with_messages(
        provider, model, messages,
        temperature=0.3,
        max_tokens=2048,
    )

    # Clean and parse
    cleaned = _clean_json_response(raw_text)
    try:
        definition = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.warning(f"[MODE_GEN] Invalid JSON from LLM: {e}")
        return {
            "ok": False,
            "error": f"AI 返回的内容不是有效 JSON: {e}",
            "raw_response": raw_text[:500],
        }

    if not isinstance(definition, dict):
        return {"ok": False, "error": "AI 返回的不是 JSON 对象"}

    # Auto-fix common issues
    definition = _auto_fix(definition)

    # Validate
    if not _validate_mode_def(definition):
        return {
            "ok": False,
            "error": "生成的模式定义校验失败，请尝试更详细的描述",
            "mode_def": definition,
        }

    result = {"ok": True, "mode_def": definition}
    if warning:
        result["warning"] = warning
    return result
