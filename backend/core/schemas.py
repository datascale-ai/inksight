"""
Pydantic 输入验证模型
为 API 端点提供请求体的类型和范围校验
"""
from __future__ import annotations

import re
from typing import Optional
from pydantic import BaseModel, Field, field_validator

from .config import SUPPORTED_MODES

# MAC 地址格式：AA:BB:CC:DD:EE:FF
_MAC_RE = re.compile(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")

# 允许的 LLM 提供商
_VALID_PROVIDERS = {"deepseek", "aliyun", "moonshot"}

# 允许的语言选项
_VALID_LANGUAGES = {"zh", "en", "mixed"}

# 允许的内容调性
_VALID_TONES = {"positive", "neutral", "deep", "humor"}

# 允许的刷新策略
_VALID_STRATEGIES = {"random", "cycle"}


class ConfigRequest(BaseModel):
    """设备配置请求体"""

    mac: str = Field(..., description="设备 MAC 地址 (AA:BB:CC:DD:EE:FF)")
    nickname: str = Field(default="", max_length=32, description="设备昵称")
    modes: list[str] = Field(
        default=["STOIC"],
        min_length=1,
        max_length=8,
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

    @field_validator("mac")
    @classmethod
    def validate_mac(cls, v: str) -> str:
        if not _MAC_RE.match(v):
            raise ValueError("MAC 地址格式无效，应为 AA:BB:CC:DD:EE:FF")
        return v

    @field_validator("modes")
    @classmethod
    def validate_modes(cls, v: list[str]) -> list[str]:
        cleaned = []
        for mode in v:
            m = mode.upper().strip()
            if m not in SUPPORTED_MODES:
                raise ValueError(f"不支持的模式: {mode}，可选: {SUPPORTED_MODES}")
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

    @field_validator("characterTones")
    @classmethod
    def validate_character_tones(cls, v: list[str]) -> list[str]:
        return [t.strip()[:20] for t in v if t.strip()]
