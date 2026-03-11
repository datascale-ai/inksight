"""
Pydantic 输入验证模型
为 API 端点提供请求体的类型和范围校验
"""
from __future__ import annotations

import re
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .config import get_supported_modes

# MAC 地址格式：AA:BB:CC:DD:EE:FF
_MAC_RE = re.compile(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")

# 允许的 LLM 提供商
_VALID_PROVIDERS = {"deepseek", "aliyun", "moonshot"}
_VALID_IMAGE_PROVIDERS = {"aliyun"}

# 允许的语言选项
_VALID_LANGUAGES = {"zh", "en", "mixed"}

# 允许的内容调性
_VALID_TONES = {"positive", "neutral", "deep", "humor"}

# 允许的刷新策略
_VALID_STRATEGIES = {"random", "cycle", "time_slot", "smart"}

# 角色调性白名单：只允许中英文、数字、空格和基本标点
_SAFE_TONE_RE = re.compile(
    r"^[\u4e00-\u9fff\u3400-\u4dbf"   # CJK Unified Ideographs
    r"a-zA-Z0-9"
    r"\s·\-\.\u3001\u3002"             # space, middot, dash, period, CN punctuation
    r"]{1,20}$"
)


class ConfigRequest(BaseModel):
    """设备配置请求体"""

    mac: str = Field(..., description="设备 MAC 地址 (AA:BB:CC:DD:EE:FF)")
    nickname: str = Field(default="", max_length=32, description="设备昵称")
    modes: list[str] = Field(
        default=["STOIC"],
        min_length=1,
        max_length=10,
        description="启用的内容模式列表",
    )
    refreshStrategy: str = Field(
        default="random", description="刷新策略: random / cycle"
    )
    refreshInterval: int = Field(
        default=60, ge=10, le=1440, description="刷新间隔(分钟), 10~1440"
    )
    language: str = Field(default="zh", description="语言: zh / en / mixed")
    contentTone: str = Field(default="neutral", description="调性: positive / neutral / deep / humor")
    city: str = Field(default="杭州", max_length=20, description="城市名称")
    characterTones: list[str] = Field(
        default_factory=list, max_length=5, description="角色调性列表"
    )
    llmProvider: str = Field(default="deepseek", description="LLM 提供商")
    llmModel: str = Field(default="deepseek-chat", max_length=50, description="LLM 模型名")
    imageProvider: str = Field(default="aliyun", description="图像模型提供商")
    imageModel: str = Field(default="qwen-image-max", max_length=50, description="图像模型名")
    countdownEvents: list[dict] = Field(
        default_factory=list,
        max_length=10,
        description="倒计时事件列表 [{name, date, type}]",
    )
    timeSlotRules: list[dict] = Field(
        default_factory=list,
        max_length=24,
        description="时段绑定规则 [{startHour, endHour, modes}]",
    )
    memoText: str = Field(default="", description="MEMO 模式下的备忘录文本")
    llmApiKey: str = Field(default="", max_length=200, description="LLM API Key (encrypted at rest)")
    imageApiKey: str = Field(default="", max_length=200, description="Image API Key (encrypted at rest)")
    screenSize: str = Field(default="400x300", description="屏幕尺寸: 400x300 / 296x128 / 800x480")
    modeOverrides: dict[str, dict] = Field(
        default_factory=dict,
        description="按模式覆盖配置，key 为 mode_id，value 可包含 city/llm_provider/llm_model 及其他模式设置项",
    )

    @field_validator("mac")
    @classmethod
    def validate_mac(cls, v: str) -> str:
        if not _MAC_RE.match(v):
            raise ValueError("MAC 地址格式无效，应为 AA:BB:CC:DD:EE:FF")
        return v

    @field_validator("modes")
    @classmethod
    def validate_modes(cls, v: list[str]) -> list[str]:
        supported = get_supported_modes()
        cleaned = []
        for mode in v:
            m = mode.upper().strip()
            if m not in supported:
                raise ValueError(f"不支持的模式: {mode}，可选: {supported}")
            cleaned.append(m)
        return cleaned

    @field_validator("refreshStrategy")
    @classmethod
    def validate_strategy(cls, v: str) -> str:
        if v not in _VALID_STRATEGIES:
            raise ValueError(f"无效刷新策略: {v}，可选: {_VALID_STRATEGIES}")
        return v

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        if v not in _VALID_LANGUAGES:
            raise ValueError(f"无效语言: {v}，可选: {_VALID_LANGUAGES}")
        return v

    @field_validator("contentTone")
    @classmethod
    def validate_tone(cls, v: str) -> str:
        if v not in _VALID_TONES:
            raise ValueError(f"无效调性: {v}，可选: {_VALID_TONES}")
        return v

    @field_validator("llmProvider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        if v not in _VALID_PROVIDERS:
            raise ValueError(f"无效 LLM 提供商: {v}，可选: {_VALID_PROVIDERS}")
        return v

    @field_validator("imageProvider")
    @classmethod
    def validate_image_provider(cls, v: str) -> str:
        if v not in _VALID_IMAGE_PROVIDERS:
            raise ValueError(f"无效图像提供商: {v}，可选: {_VALID_IMAGE_PROVIDERS}")
        return v

    @field_validator("characterTones")
    @classmethod
    def validate_character_tones(cls, v: list[str]) -> list[str]:
        cleaned = []
        for t in v:
            t = t.strip()[:20]
            if not t:
                continue
            if not _SAFE_TONE_RE.match(t):
                raise ValueError(
                    f"角色调性包含非法字符: {t!r}，只允许中英文、数字和基本标点"
                )
            cleaned.append(t)
        return cleaned

    @field_validator("modeOverrides")
    @classmethod
    def validate_mode_overrides(cls, v: dict[str, dict]) -> dict[str, dict]:
        cleaned: dict[str, dict] = {}
        for mode_id, raw in v.items():
            if not isinstance(mode_id, str):
                continue
            key = mode_id.strip().upper()
            if not key:
                continue
            if not isinstance(raw, dict):
                continue

            item: dict[str, object] = {}
            city = raw.get("city")
            if isinstance(city, str) and city.strip():
                item["city"] = city.strip()[:20]

            provider = raw.get("llm_provider", raw.get("llmProvider"))
            if isinstance(provider, str) and provider.strip():
                if provider not in _VALID_PROVIDERS:
                    raise ValueError(f"无效 LLM 提供商: {provider}，可选: {_VALID_PROVIDERS}")
                item["llm_provider"] = provider

            model = raw.get("llm_model", raw.get("llmModel"))
            if isinstance(model, str) and model.strip():
                item["llm_model"] = model.strip()[:50]

            for k, val in raw.items():
                if k in {"city", "llm_provider", "llmProvider", "llm_model", "llmModel"}:
                    continue
                if isinstance(val, (str, int, float, bool, list, dict)) or val is None:
                    item[k] = val

            if item:
                cleaned[key] = item
        return cleaned


class RenderQuery(BaseModel):
    """渲染端点 Query 参数模型。"""

    model_config = ConfigDict(populate_by_name=True)

    v: float = Field(default=3.3, description="Battery voltage")
    mac: Optional[str] = Field(default=None, description="Device MAC address")
    persona: Optional[str] = Field(default=None, description="Force persona")
    rssi: Optional[int] = Field(default=None, description="WiFi RSSI (dBm)")
    refresh_min: Optional[int] = Field(default=None, ge=1, le=1440, description="Device effective refresh interval in minutes")
    w: int = Field(default=400, ge=100, le=1600, description="Screen width in pixels")
    h: int = Field(default=300, ge=100, le=1200, description="Screen height in pixels")
    next_mode: Optional[int] = Field(default=None, alias="next", description="1 = advance to next mode")

    @field_validator("mac")
    @classmethod
    def validate_optional_mac(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return ConfigRequest.validate_mac(v)


class DeviceHeartbeatRequest(BaseModel):
    """设备心跳请求体。"""

    battery_voltage: Optional[float] = Field(default=3.3, ge=0.0, le=10.0)
    wifi_rssi: Optional[int] = Field(default=None, ge=-150, le=0)


class OkResponse(BaseModel):
    ok: bool = True


class ConfigSaveResponse(OkResponse):
    config_id: int
