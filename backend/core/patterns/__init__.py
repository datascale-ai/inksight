"""
Patterns 包
每个模式一个文件，便于扩展和维护

所有业务模式已迁移到 JSON 定义 (core/modes/builtin/)，
由 json_renderer.py 统一渲染。此处仅保留错误页渲染器。
"""

from .error import render_error

__all__ = [
    "render_error",
]
