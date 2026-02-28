"""
模式注册中心
统一管理内置 Python 模式和 JSON 自定义模式的注册、查询、加载
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Awaitable, Callable

from PIL import Image

logger = logging.getLogger(__name__)

@dataclass
class ContentContext:
    """统一的 Python 内置模式内容生成上下文。"""
    config: dict
    date_ctx: dict
    weather_str: str
    date_str: str
    festival: str = ""
    daily_word: str = ""
    upcoming_holiday: str = ""
    days_until_holiday: int = 0
    llm_provider: str = "deepseek"
    llm_model: str = "deepseek-chat"
    language: str = "zh"
    content_tone: str = "neutral"
    character_tones: list[str] = field(default_factory=list)


ContentFn = Callable[[ContentContext], Awaitable[dict]]
RenderFn = Callable[..., Image.Image]

MODES_DIR = os.path.join(os.path.dirname(__file__), "modes")
BUILTIN_JSON_DIR = os.path.join(MODES_DIR, "builtin")
CUSTOM_JSON_DIR = os.path.join(MODES_DIR, "custom")
SCHEMA_PATH = os.path.join(MODES_DIR, "schema", "mode_schema.json")


@dataclass
class ModeInfo:
    mode_id: str
    display_name: str
    icon: str = "star"
    cacheable: bool = True
    description: str = ""
    source: str = "builtin"  # "builtin" | "builtin_json" | "custom"


@dataclass
class BuiltinMode:
    info: ModeInfo
    content_fn: ContentFn
    render_fn: RenderFn


@dataclass
class JsonMode:
    info: ModeInfo
    definition: dict = field(default_factory=dict)
    file_path: str = ""


class ModeRegistry:
    """Central registry for all display modes (builtin Python + JSON-defined)."""

    def __init__(self) -> None:
        self._builtin: dict[str, BuiltinMode] = {}
        self._json_modes: dict[str, JsonMode] = {}

    # ── Registration ─────────────────────────────────────────

    def register_builtin(
        self,
        mode_id: str,
        content_fn: ContentFn,
        render_fn: RenderFn,
        *,
        display_name: str = "",
        icon: str = "star",
        cacheable: bool = True,
        description: str = "",
    ) -> None:
        mode_id = mode_id.upper()
        info = ModeInfo(
            mode_id=mode_id,
            display_name=display_name or mode_id,
            icon=icon,
            cacheable=cacheable,
            description=description,
            source="builtin",
        )
        self._builtin[mode_id] = BuiltinMode(
            info=info, content_fn=content_fn, render_fn=render_fn
        )
        logger.debug(f"[Registry] Registered builtin mode: {mode_id}")

    def load_json_mode(self, path: str, *, source: str = "custom") -> str | None:
        """Load and validate a single JSON mode definition. Returns mode_id or None on error."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                definition = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"[Registry] Failed to load {path}: {e}")
            return None

        mode_id = definition.get("mode_id", "").upper()
        if not mode_id:
            logger.error(f"[Registry] Missing mode_id in {path}")
            return None

        if not _validate_mode_def(definition):
            logger.error(f"[Registry] Validation failed for {path}")
            return None

        if mode_id in self._builtin:
            logger.warning(
                f"[Registry] JSON mode {mode_id} shadows builtin — skipped"
            )
            return None

        info = ModeInfo(
            mode_id=mode_id,
            display_name=definition.get("display_name", mode_id),
            icon=definition.get("icon", "star"),
            cacheable=definition.get("cacheable", True),
            description=definition.get("description", ""),
            source=source,
        )
        self._json_modes[mode_id] = JsonMode(
            info=info, definition=definition, file_path=path
        )
        logger.info(f"[Registry] Loaded JSON mode: {mode_id} from {path}")
        return mode_id

    def load_directory(self, dir_path: str, *, source: str = "custom") -> list[str]:
        """Load all .json files from a directory. Returns list of loaded mode_ids."""
        loaded = []
        if not os.path.isdir(dir_path):
            return loaded
        for fname in sorted(os.listdir(dir_path)):
            if not fname.endswith(".json"):
                continue
            path = os.path.join(dir_path, fname)
            mid = self.load_json_mode(path, source=source)
            if mid:
                loaded.append(mid)
        return loaded

    def unregister_custom(self, mode_id: str) -> bool:
        mode_id = mode_id.upper()
        jm = self._json_modes.get(mode_id)
        if jm and jm.info.source == "custom":
            del self._json_modes[mode_id]
            return True
        return False

    # ── Queries ──────────────────────────────────────────────

    def is_supported(self, mode_id: str) -> bool:
        mode_id = mode_id.upper()
        return mode_id in self._builtin or mode_id in self._json_modes

    def get_supported_ids(self) -> set[str]:
        return set(self._builtin.keys()) | set(self._json_modes.keys())

    def get_cacheable_ids(self) -> set[str]:
        ids: set[str] = set()
        for mid, bm in self._builtin.items():
            if bm.info.cacheable:
                ids.add(mid)
        for mid, jm in self._json_modes.items():
            if jm.info.cacheable:
                ids.add(mid)
        return ids

    def get_mode_info(self, mode_id: str) -> ModeInfo | None:
        mode_id = mode_id.upper()
        if mode_id in self._builtin:
            return self._builtin[mode_id].info
        jm = self._json_modes.get(mode_id)
        return jm.info if jm else None

    def get_builtin(self, mode_id: str) -> BuiltinMode | None:
        return self._builtin.get(mode_id.upper())

    def get_json_mode(self, mode_id: str) -> JsonMode | None:
        return self._json_modes.get(mode_id.upper())

    def is_json_mode(self, mode_id: str) -> bool:
        return mode_id.upper() in self._json_modes

    def is_builtin(self, mode_id: str) -> bool:
        return mode_id.upper() in self._builtin

    def list_modes(self) -> list[ModeInfo]:
        infos: list[ModeInfo] = []
        for bm in self._builtin.values():
            infos.append(bm.info)
        for jm in self._json_modes.values():
            infos.append(jm.info)
        return sorted(infos, key=lambda m: m.mode_id)

    def get_mode_icon_map(self) -> dict[str, str]:
        result: dict[str, str] = {}
        for mid, bm in self._builtin.items():
            result[mid] = bm.info.icon
        for mid, jm in self._json_modes.items():
            result[mid] = jm.info.icon
        return result


# ── Validation ───────────────────────────────────────────────


def _validate_mode_def(definition: dict) -> bool:
    """Lightweight validation without jsonschema dependency."""
    mode_id = definition.get("mode_id", "")
    if not isinstance(mode_id, str) or not mode_id:
        return False

    content = definition.get("content")
    if not isinstance(content, dict):
        return False
    ctype = content.get("type", "")
    if ctype not in ("llm", "llm_json", "static", "external_data", "image_gen", "computed", "composite"):
        return False
    if ctype in ("llm", "llm_json") and not content.get("prompt_template"):
        return False
    if ctype in ("llm", "llm_json") and not content.get("fallback"):
        return False

    layout = definition.get("layout")
    if not isinstance(layout, dict):
        return False
    body = layout.get("body")
    if not isinstance(body, list) or len(body) == 0:
        return False

    # Validate optional layout_overrides
    overrides = definition.get("layout_overrides")
    if overrides is not None:
        if not isinstance(overrides, dict):
            return False
        for key, val in overrides.items():
            if not isinstance(val, dict):
                return False

    return True


# ── Singleton ────────────────────────────────────────────────

_registry: ModeRegistry | None = None


def get_registry() -> ModeRegistry:
    """Get or create the global mode registry singleton."""
    global _registry
    if _registry is None:
        _registry = ModeRegistry()
        _init_registry(_registry)
    return _registry


def _init_registry(registry: ModeRegistry) -> None:
    """Initialize the registry with builtin modes and load JSON modes."""
    _register_builtin_python_modes(registry)

    builtin_loaded = registry.load_directory(BUILTIN_JSON_DIR, source="builtin_json")
    if builtin_loaded:
        logger.info(f"[Registry] Loaded {len(builtin_loaded)} builtin JSON modes")

    custom_loaded = registry.load_directory(CUSTOM_JSON_DIR, source="custom")
    if custom_loaded:
        logger.info(f"[Registry] Loaded {len(custom_loaded)} custom JSON modes")


def _register_builtin_python_modes(registry: ModeRegistry) -> None:
    """All built-in modes are now JSON-defined; keep hook for future use."""
    return None


def reset_registry() -> None:
    """Reset the singleton (useful for tests)."""
    global _registry
    _registry = None
