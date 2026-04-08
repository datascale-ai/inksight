from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable


class LayoutDslError(ValueError):
    pass


FragmentBuilder = Callable[[dict[str, Any]], dict[str, Any]]
PresetBuilder = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class PrimitiveSpec:
    props: tuple[str, ...]
    field_props: tuple[str, ...] = ()


@dataclass(frozen=True)
class FragmentSpec:
    builder: FragmentBuilder
    props: tuple[str, ...]
    required_props: tuple[str, ...] = ()
    field_props: tuple[str, ...] = ()
    defaults: dict[str, Any] | None = None


@dataclass(frozen=True)
class PresetSpec:
    builder: PresetBuilder
    props: tuple[str, ...]
    required_props: tuple[str, ...] = ()
    defaults: dict[str, Any] | None = None


def _compact(data: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in data.items() if value is not None}


def _merge_defaults(props: dict[str, Any], defaults: dict[str, Any] | None = None) -> dict[str, Any]:
    merged = deepcopy(defaults or {})
    merged.update(props)
    return merged


def _require_props(label: str, props: dict[str, Any], required_props: tuple[str, ...]) -> None:
    missing = [name for name in required_props if props.get(name) in (None, "")]
    if missing:
        raise LayoutDslError(f"{label} missing required props: {', '.join(missing)}")


def _normalize_props(raw_props: Any, label: str, defaults: dict[str, Any] | None = None) -> dict[str, Any]:
    if raw_props is None:
        return deepcopy(defaults or {})
    if not isinstance(raw_props, dict):
        raise LayoutDslError(f"{label} props must be an object")
    return _merge_defaults(raw_props, defaults)


def _text_node(
    *,
    field: str | None = None,
    template: str | None = None,
    font: str | None = None,
    font_name: str | None = None,
    font_size: int | None = None,
    align: str | None = None,
    align_y: str | None = None,
    max_lines: int | None = None,
    ellipsis: bool | None = None,
    line_height: int | None = None,
    grow: int | None = None,
) -> dict[str, Any]:
    return _compact(
        {
            "type": "text",
            "field": field,
            "template": template,
            "font": font,
            "font_name": font_name,
            "font_size": font_size,
            "align": align,
            "align_y": align_y,
            "max_lines": max_lines,
            "ellipsis": ellipsis,
            "line_height": line_height,
            "grow": grow,
        }
    )


def _separator_node(*, style: str = "short", width: int | None = None, margin_x: int | None = None) -> dict[str, Any]:
    return _compact(
        {
            "type": "separator",
            "style": style,
            "width": width,
            "margin_x": margin_x,
        }
    )


def _fragment_title_with_rule(props: dict[str, Any]) -> dict[str, Any]:
    children: list[dict[str, Any]] = []
    meta_field = props.get("meta_field")
    if isinstance(meta_field, str) and meta_field:
        children.append(
            _text_node(
                field=meta_field,
                font=props.get("meta_font"),
                font_name=props.get("meta_font_name"),
                font_size=props.get("meta_font_size"),
                align=props.get("meta_align", "center"),
                align_y=props.get("meta_align_y"),
                max_lines=props.get("meta_max_lines", 1),
            )
        )
    children.append(
        _text_node(
            field=str(props.get("title_field", "")),
            font=props.get("title_font"),
            font_name=props.get("title_font_name"),
            font_size=props.get("title_font_size"),
            align=props.get("title_align", "center"),
            align_y=props.get("title_align_y"),
            max_lines=props.get("title_max_lines", 2),
        )
    )
    children.append(
        _separator_node(
            style=props.get("separator_style", "short"),
            width=props.get("separator_width"),
        )
    )
    return {
        "type": "column",
        "gap": props.get("header_gap", 3),
        "children": children,
    }


def _fragment_inset_body_text(props: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "box",
        "padding_x": props.get("inset_x", 28),
        "children": [
            _text_node(
                field=str(props.get("field", "")),
                font=props.get("font"),
                font_name=props.get("font_name"),
                font_size=props.get("font_size"),
                align=props.get("align", "left"),
                align_y=props.get("align_y"),
                max_lines=props.get("max_lines", 3),
                line_height=props.get("line_height"),
                ellipsis=props.get("ellipsis"),
            )
        ],
    }


def _fragment_footer_note(props: dict[str, Any]) -> dict[str, Any]:
    children: list[dict[str, Any]] = []
    if props.get("show_divider", True):
        children.append(
            {
                "type": "box",
                "padding_x": props.get("divider_inset_x", 40),
                "children": [
                    _separator_node(style=props.get("divider_style", "dashed"))
                ],
            }
        )
    if props.get("field"):
        children.append(
            _text_node(
                field=str(props.get("field", "")),
                font=props.get("font"),
                font_name=props.get("font_name"),
                font_size=props.get("font_size"),
                align=props.get("align", "center"),
                align_y=props.get("align_y"),
                max_lines=props.get("max_lines", 2),
            )
        )
    return {
        "type": "column",
        "gap": props.get("gap", 6),
        "children": children,
    }


def _fragment_metric_hero(props: dict[str, Any]) -> dict[str, Any]:
    children: list[dict[str, Any]] = []
    meta_field = props.get("meta_field")
    if isinstance(meta_field, str) and meta_field:
        children.append(
            _text_node(
                field=meta_field,
                font=props.get("meta_font"),
                font_name=props.get("meta_font_name"),
                font_size=props.get("meta_font_size", 11),
                align=props.get("meta_align", "center"),
                align_y=props.get("meta_align_y"),
                max_lines=props.get("meta_max_lines", 1),
            )
        )
    children.append(
        {
            "type": "big_number",
            "field": str(props.get("hero_field", "")),
            "font_size": props.get("hero_font_size", 38),
            "align": props.get("hero_align", "center"),
            "align_y": props.get("hero_align_y"),
        }
    )
    children.append(
        _separator_node(
            style=props.get("separator_style", "short"),
            width=props.get("separator_width", 70),
        )
    )
    return {
        "type": "column",
        "gap": props.get("gap", 4),
        "children": children,
    }


def _fragment_briefing_repeat_row(props: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "repeat",
        "field": str(props.get("field", "")),
        "limit": props.get("limit", 2),
        "gap": props.get("gap", 6),
        "item": {
            "type": "row",
            "gap": props.get("row_gap", 8),
            "align": props.get("row_align", "end"),
            "children": [
                _text_node(
                    field=str(props.get("left_field", "title")),
                    font=props.get("left_font"),
                    font_name=props.get("left_font_name"),
                    font_size=props.get("left_font_size"),
                    align=props.get("left_align", "left"),
                    align_y=props.get("left_align_y"),
                    max_lines=props.get("left_max_lines", 2),
                    grow=props.get("left_grow", 1),
                ),
                _text_node(
                    field=str(props.get("right_field", "score")),
                    font=props.get("right_font"),
                    font_name=props.get("right_font_name"),
                    font_size=props.get("right_font_size"),
                    align=props.get("right_align", "right"),
                    align_y=props.get("right_align_y"),
                    max_lines=props.get("right_max_lines", 1),
                ),
            ],
        },
    }


def _fragment_briefing_repeat_text(props: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "repeat",
        "field": str(props.get("field", "")),
        "limit": props.get("limit", 2),
        "gap": props.get("gap", 6),
        "item": _text_node(
            field=str(props.get("text_field", "title")),
            font=props.get("text_font"),
            font_name=props.get("text_font_name"),
            font_size=props.get("text_font_size"),
            align=props.get("text_align", "left"),
            align_y=props.get("text_align_y"),
            max_lines=props.get("text_max_lines", 2),
            line_height=props.get("text_line_height"),
            ellipsis=props.get("text_ellipsis"),
        ),
    }


def _fragment_stacked_text(props: dict[str, Any]) -> dict[str, Any]:
    children: list[dict[str, Any]] = []
    for item in props.get("items", []):
        if not isinstance(item, dict):
            continue
        children.append(
            _text_node(
                field=str(item.get("field", "")),
                template=item.get("template"),
                font=item.get("font"),
                font_name=item.get("font_name"),
                font_size=item.get("font_size"),
                align=item.get("align", "left"),
                align_y=item.get("align_y"),
                max_lines=item.get("max_lines"),
                line_height=item.get("line_height"),
                ellipsis=item.get("ellipsis"),
                grow=item.get("grow"),
            )
        )
    return {
        "type": "column",
        "gap": props.get("gap", 4),
        "children": children,
    }


def _fragment_daily_date_panel(props: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "box",
        "width": props.get("width", 116),
        "children": [
            {
                "type": "column",
                "padding_x": props.get("padding_x", 8),
                "gap": props.get("gap", 4),
                "children": [
                    _text_node(
                        field=str(props.get("year_field", "year")),
                        font_size=props.get("year_font_size", 12),
                        align="center",
                        max_lines=1,
                    ),
                    {
                        "type": "big_number",
                        "field": str(props.get("day_field", "day")),
                        "font_size": props.get("day_font_size", 52),
                        "align": "center",
                        "align_y": props.get("day_align_y"),
                    },
                    {
                        "type": "column",
                        "gap": props.get("gap", 4),
                        "children": [
                            _text_node(
                                field=str(props.get("month_field", "month_cn")),
                                font_size=props.get("month_font_size", 14),
                                align="center",
                                max_lines=1,
                            ),
                            _text_node(
                                field=str(props.get("weekday_field", "weekday_cn")),
                                font_size=props.get("weekday_font_size", 12),
                                align="center",
                                max_lines=1,
                            ),
                            {
                                "type": "progress_bar",
                                "field": str(props.get("progress_field", "day_of_year")),
                                "max_field": str(props.get("progress_max_field", "days_in_year")),
                                "width": props.get("progress_width", 80),
                                "align": "center",
                            },
                            {
                                "type": "box",
                                "padding_x": props.get("season_inset_x"),
                                "children": [
                                    _text_node(
                                        field=str(props.get("season_field", "season_text")),
                                        font=props.get("season_font"),
                                        font_name=props.get("season_font_name"),
                                        font_size=props.get("season_font_size", 10),
                                        align="center",
                                align_y=props.get("season_align_y"),
                                        max_lines=props.get("season_max_lines", 2),
                                    )
                                ],
                            },
                        ],
                    },
                ],
            }
        ],
    }


def _fragment_quote_block(props: dict[str, Any]) -> dict[str, Any]:
    children: list[dict[str, Any]] = [
        _text_node(
            field=str(props.get("quote_field", "quote")),
            font=props.get("quote_font"),
            font_name=props.get("quote_font_name"),
            font_size=props.get("quote_font_size", 14),
            align=props.get("quote_align", "left"),
            align_y=props.get("quote_align_y"),
            max_lines=props.get("quote_max_lines", 4),
        ),
        _text_node(
            template=str(props.get("author_template", "— {author}")),
            font=props.get("author_font"),
            font_name=props.get("author_font_name"),
            font_size=props.get("author_font_size", 11),
            align=props.get("author_align", "right"),
            align_y=props.get("author_align_y"),
            max_lines=props.get("author_max_lines", 1),
        ),
    ]
    if props.get("show_divider", True):
        children.append(
            _separator_node(style=props.get("divider_style", "dashed"), margin_x=props.get("divider_margin_x", 6))
        )
    return {
        "type": "box",
        "children": [
            {
                "type": "column",
                "gap": props.get("gap", 2),
                "children": children,
            }
        ],
    }


def _fragment_book_block(props: dict[str, Any]) -> dict[str, Any]:
    children: list[dict[str, Any]] = [
        _text_node(
            field=str(props.get("title_field", "book_title")),
            font=props.get("title_font"),
            font_name=props.get("title_font_name"),
            font_size=props.get("title_font_size", 13),
            align=props.get("title_align", "left"),
            align_y=props.get("title_align_y"),
            max_lines=props.get("title_max_lines", 2),
        ),
        _text_node(
            template=str(props.get("author_template", "{book_author}")),
            font=props.get("author_font"),
            font_name=props.get("author_font_name"),
            font_size=props.get("author_font_size", 11),
            align=props.get("author_align", "left"),
            align_y=props.get("author_align_y"),
            max_lines=props.get("author_max_lines", 1),
        ),
        _text_node(
            field=str(props.get("desc_field", "book_desc")),
            font=props.get("desc_font"),
            font_name=props.get("desc_font_name"),
            font_size=props.get("desc_font_size", 11),
            align=props.get("desc_align", "left"),
            align_y=props.get("desc_align_y"),
            max_lines=props.get("desc_max_lines", 2),
        ),
    ]
    if props.get("show_divider", True):
        children.append(
            _separator_node(style=props.get("divider_style", "dashed"), margin_x=props.get("divider_margin_x", 6))
        )
    return {
        "type": "box",
        "children": [
            {
                "type": "column",
                "gap": props.get("gap", 2),
                "children": children,
            }
        ],
    }


def _fragment_plain_text(props: dict[str, Any]) -> dict[str, Any]:
    return _text_node(
        field=str(props.get("field", "")) if props.get("field") else None,
        template=props.get("template"),
        font=props.get("font"),
        font_name=props.get("font_name"),
        font_size=props.get("font_size"),
        align=props.get("align", "left"),
        align_y=props.get("align_y"),
        max_lines=props.get("max_lines"),
        line_height=props.get("line_height"),
        ellipsis=props.get("ellipsis"),
        grow=props.get("grow"),
    )


PRIMITIVE_REGISTRY: dict[str, PrimitiveSpec] = {
    "text": PrimitiveSpec(
        props=("field", "template", "font", "font_name", "font_size", "align", "align_y", "max_lines", "ellipsis", "line_height", "grow"),
        field_props=("field", "template"),
    ),
    "separator": PrimitiveSpec(props=("style", "width", "margin_x")),
    "big_number": PrimitiveSpec(props=("field", "font_size", "align", "align_y"), field_props=("field",)),
    "progress_bar": PrimitiveSpec(props=("field", "max_field", "width", "align"), field_props=("field", "max_field")),
    "box": PrimitiveSpec(props=("width", "padding_x", "children")),
    "row": PrimitiveSpec(props=("gap", "align", "grow", "children")),
    "column": PrimitiveSpec(props=("padding_x", "padding_y", "justify", "gap", "children")),
    "repeat": PrimitiveSpec(props=("field", "limit", "gap", "item"), field_props=("field",)),
    "section_box": PrimitiveSpec(props=("title", "icon", "children")),
}


FRAGMENT_REGISTRY: dict[str, FragmentSpec] = {
    "title_with_rule": FragmentSpec(
        builder=_fragment_title_with_rule,
        props=("meta_field", "meta_font", "meta_font_name", "meta_font_size", "meta_align", "meta_align_y", "meta_max_lines", "title_field", "title_font", "title_font_name", "title_font_size", "title_align", "title_align_y", "title_max_lines", "separator_style", "separator_width", "header_gap"),
        required_props=("title_field",),
        field_props=("meta_field", "title_field"),
    ),
    "inset_body_text": FragmentSpec(
        builder=_fragment_inset_body_text,
        props=("field", "font", "font_name", "font_size", "align", "align_y", "max_lines", "line_height", "ellipsis", "inset_x"),
        required_props=("field",),
        field_props=("field",),
    ),
    "footer_note": FragmentSpec(
        builder=_fragment_footer_note,
        props=("field", "font", "font_name", "font_size", "align", "align_y", "max_lines", "gap", "show_divider", "divider_inset_x", "divider_style"),
        field_props=("field",),
    ),
    "metric_hero": FragmentSpec(
        builder=_fragment_metric_hero,
        props=("meta_field", "meta_font", "meta_font_name", "meta_font_size", "meta_align", "meta_align_y", "meta_max_lines", "hero_field", "hero_font_size", "hero_align", "hero_align_y", "separator_style", "separator_width", "gap"),
        required_props=("hero_field",),
        field_props=("meta_field", "hero_field"),
    ),
    "briefing_repeat_row": FragmentSpec(
        builder=_fragment_briefing_repeat_row,
        props=("field", "limit", "gap", "row_gap", "row_align", "left_field", "left_font", "left_font_name", "left_font_size", "left_align", "left_align_y", "left_max_lines", "left_grow", "right_field", "right_font", "right_font_name", "right_font_size", "right_align", "right_align_y", "right_max_lines"),
        required_props=("field",),
        field_props=("field", "left_field", "right_field"),
    ),
    "briefing_repeat_text": FragmentSpec(
        builder=_fragment_briefing_repeat_text,
        props=("field", "limit", "gap", "text_field", "text_font", "text_font_name", "text_font_size", "text_align", "text_align_y", "text_max_lines", "text_line_height", "text_ellipsis"),
        required_props=("field",),
        field_props=("field", "text_field"),
    ),
    "stacked_text": FragmentSpec(
        builder=_fragment_stacked_text,
        props=("gap", "items"),
    ),
    "daily_date_panel": FragmentSpec(
        builder=_fragment_daily_date_panel,
        props=("width", "padding_x", "gap", "year_field", "year_font_size", "day_field", "day_font_size", "day_align_y", "month_field", "month_font_size", "weekday_field", "weekday_font_size", "progress_field", "progress_max_field", "progress_width", "season_field", "season_font", "season_font_name", "season_font_size", "season_align_y", "season_max_lines", "season_inset_x"),
        defaults={"year_field": "year", "day_field": "day", "month_field": "month_cn", "weekday_field": "weekday_cn", "progress_field": "day_of_year", "progress_max_field": "days_in_year", "season_field": "season_text"},
        field_props=("year_field", "day_field", "month_field", "weekday_field", "progress_field", "progress_max_field", "season_field"),
    ),
    "quote_block": FragmentSpec(
        builder=_fragment_quote_block,
        props=("quote_field", "quote_font", "quote_font_name", "quote_font_size", "quote_align", "quote_align_y", "quote_max_lines", "author_template", "author_font", "author_font_name", "author_font_size", "author_align", "author_align_y", "author_max_lines", "show_divider", "divider_style", "divider_margin_x", "gap"),
        defaults={"quote_field": "quote", "author_template": "— {author}"},
        field_props=("quote_field", "author_template"),
    ),
    "book_block": FragmentSpec(
        builder=_fragment_book_block,
        props=("title_field", "title_font", "title_font_name", "title_font_size", "title_align", "title_align_y", "title_max_lines", "author_template", "author_font", "author_font_name", "author_font_size", "author_align", "author_align_y", "author_max_lines", "desc_field", "desc_font", "desc_font_name", "desc_font_size", "desc_align", "desc_align_y", "desc_max_lines", "show_divider", "divider_style", "divider_margin_x", "gap"),
        defaults={"title_field": "book_title", "author_template": "{book_author}", "desc_field": "book_desc"},
        field_props=("title_field", "author_template", "desc_field"),
    ),
    "plain_text": FragmentSpec(
        builder=_fragment_plain_text,
        props=("field", "template", "font", "font_name", "font_size", "align", "align_y", "max_lines", "line_height", "ellipsis", "grow"),
        field_props=("field", "template"),
    ),
}


def _build_fragment_instance(fragment_name: str, raw_props: Any) -> dict[str, Any]:
    spec = FRAGMENT_REGISTRY.get(fragment_name)
    if spec is None:
        raise LayoutDslError(f"Unknown fragment: {fragment_name}")
    props = _normalize_props(raw_props, f"fragment '{fragment_name}'", spec.defaults)
    _require_props(f"fragment '{fragment_name}'", props, spec.required_props)
    return spec.builder(props)


def _story_card(props: dict[str, Any]) -> dict[str, Any]:
    sections = [
        _build_fragment_instance("inset_body_text", section)
        for section in props.get("sections", [])
        if isinstance(section, dict)
    ]
    return _compact(
        {
            "type": "column",
            "padding_x": props.get("padding_x", 18),
            "padding_y": props.get("padding_y", 6),
            "justify": props.get("justify", "center"),
            "gap": props.get("gap", 6),
            "children": [
                _build_fragment_instance(
                    "title_with_rule",
                    {
                        "meta_field": props.get("meta_field"),
                        "meta_font": props.get("meta_font"),
                        "meta_font_name": props.get("meta_font_name"),
                        "meta_font_size": props.get("meta_font_size"),
                        "title_field": props.get("title_field", "title"),
                        "title_font": props.get("title_font"),
                        "title_font_name": props.get("title_font_name"),
                        "title_font_size": props.get("title_font_size"),
                        "title_max_lines": props.get("title_max_lines", 2),
                        "separator_width": props.get("separator_width", 50),
                        "header_gap": props.get("header_gap", 3),
                    },
                ),
                {
                    "type": "column",
                    "gap": props.get("section_gap", 6),
                    "children": sections,
                },
            ],
        }
    )


def _thisday_card(props: dict[str, Any]) -> dict[str, Any]:
    return _compact(
        {
            "type": "column",
            "padding_x": props.get("padding_x", 18),
            "padding_y": props.get("padding_y", 8),
            "justify": props.get("justify", "center"),
            "gap": props.get("gap", 8),
            "children": [
                _build_fragment_instance(
                    "metric_hero",
                    {
                        "meta_field": props.get("meta_field", "years_ago"),
                        "meta_font_size": props.get("meta_font_size", 11),
                        "hero_field": props.get("hero_field", "year"),
                        "hero_font_size": props.get("hero_font_size", 38),
                        "separator_width": props.get("separator_width", 70),
                        "gap": props.get("header_gap", 4),
                    },
                ),
                {
                    "type": "column",
                    "gap": props.get("body_gap", 8),
                    "children": [
                        _text_node(
                            field=str(props.get("title_field", "event_title")),
                            font=props.get("title_font"),
                            font_name=props.get("title_font_name"),
                            font_size=props.get("title_font_size", 16),
                            align="center",
                            max_lines=props.get("title_max_lines", 2),
                        ),
                        _build_fragment_instance(
                            "inset_body_text",
                            {
                                "field": props.get("body_field", "event_desc"),
                                "font": props.get("body_font"),
                                "font_name": props.get("body_font_name"),
                                "font_size": props.get("body_font_size", 13),
                                "align": "left",
                                "max_lines": props.get("body_max_lines", 4),
                                "inset_x": props.get("body_inset_x", 28),
                            },
                        ),
                    ],
                },
                _build_fragment_instance(
                    "footer_note",
                    {
                        "field": props.get("footer_field", "significance"),
                        "font": props.get("footer_font"),
                        "font_name": props.get("footer_font_name"),
                        "font_size": props.get("footer_font_size", 11),
                        "align": "center",
                        "max_lines": props.get("footer_max_lines", 2),
                        "gap": props.get("footer_gap", 6),
                        "divider_inset_x": props.get("divider_inset_x", 40),
                    },
                ),
            ],
        }
    )


def _build_briefing_section(section: dict[str, Any]) -> dict[str, Any]:
    kind = section.get("kind")
    fragment_name = {
        "repeat_row": "briefing_repeat_row",
        "repeat_text": "briefing_repeat_text",
        "stack_text": "stacked_text",
    }.get(str(kind))
    if fragment_name is None:
        raise LayoutDslError(f"Unknown briefing section kind: {kind}")
    return {
        "type": "section_box",
        "title": str(section.get("title", "")),
        "icon": section.get("icon"),
        "children": [_build_fragment_instance(fragment_name, section)],
    }


def _briefing_sections(props: dict[str, Any]) -> dict[str, Any]:
    sections = [
        _build_briefing_section(section)
        for section in props.get("sections", [])
        if isinstance(section, dict)
    ]
    return _compact(
        {
            "type": "column",
            "padding_x": props.get("padding_x", 18),
            "padding_y": props.get("padding_y", 6),
            "gap": props.get("gap", 4),
            "justify": props.get("justify", "space_between"),
            "children": sections,
        }
    )


def _daily_card(props: dict[str, Any]) -> dict[str, Any]:
    variant = str(props.get("variant", "full"))
    if variant == "compact":
        return _compact(
            {
                "type": "column",
                "padding_x": props.get("padding_x", 8),
                "justify": props.get("justify", "center"),
                "gap": props.get("gap", 5),
                "children": [
                    {
                        "type": "big_number",
                        "field": str(props.get("day_field", "day")),
                        "font_size": props.get("day_font_size", 40),
                        "align": props.get("day_align", "left"),
                    },
                    _build_fragment_instance(
                        "plain_text",
                        {
                            "template": props.get("meta_template", "{month_cn} {weekday_cn}"),
                            "font_size": props.get("meta_font_size", 10),
                            "align": props.get("meta_align", "left"),
                            "max_lines": 1,
                        },
                    ),
                    _separator_node(style="short", width=props.get("separator_width", 40)),
                    _build_fragment_instance(
                        "plain_text",
                        {
                            "field": props.get("quote_field", "quote"),
                            "font": props.get("quote_font"),
                            "font_name": props.get("quote_font_name"),
                            "font_size": props.get("quote_font_size", 11),
                            "align": "left",
                            "max_lines": props.get("quote_max_lines", 2),
                        },
                    ),
                    _build_fragment_instance(
                        "plain_text",
                        {
                            "template": props.get("author_template", "— {author}"),
                            "font_size": props.get("author_font_size", 9),
                            "align": "right",
                            "max_lines": 1,
                        },
                    ),
                ],
            }
        )
    return _compact(
        {
            "type": "column",
            "padding_x": props.get("padding_x", 18),
            "justify": props.get("justify", "center"),
            "children": [
                {
                    "type": "row",
                    "min_height": props.get("min_height"),
                    "gap": props.get("row_gap", 10),
                    "align": "stretch",
                    "children": [
                        _build_fragment_instance(
                            "daily_date_panel",
                            {
                                "width": props.get("panel_width", 116),
                                "padding_x": props.get("panel_padding_x", 8),
                                "gap": props.get("panel_gap", 4),
                                "year_field": props.get("year_field", "year"),
                                "year_font_size": props.get("year_font_size", 12),
                                "day_field": props.get("day_field", "day"),
                                "day_font_size": props.get("day_font_size", 52),
                                "day_align_y": props.get("day_align_y"),
                                "month_field": props.get("month_field", "month_cn"),
                                "month_font_size": props.get("month_font_size", 14),
                                "weekday_field": props.get("weekday_field", "weekday_cn"),
                                "weekday_font_size": props.get("weekday_font_size", 12),
                                "progress_field": props.get("progress_field", "day_of_year"),
                                "progress_max_field": props.get("progress_max_field", "days_in_year"),
                                "progress_width": props.get("progress_width", 80),
                                "season_field": props.get("season_field", "season_text"),
                                "season_font": props.get("season_font"),
                                "season_font_name": props.get("season_font_name"),
                                "season_font_size": props.get("season_font_size", 10),
                                "season_align_y": props.get("season_align_y"),
                                "season_max_lines": props.get("season_max_lines", 2),
                                "season_inset_x": props.get("season_inset_x"),
                            },
                        ),
                        {
                            "type": "column",
                            "grow": 1,
                            "padding_x": props.get("content_padding_x", 6),
                            "justify": props.get("content_justify", "space_between"),
                            "children": [
                                _build_fragment_instance(
                                    "quote_block",
                                    {
                                        "quote_field": props.get("quote_field", "quote"),
                                        "quote_font": props.get("quote_font"),
                                        "quote_font_name": props.get("quote_font_name"),
                                        "quote_font_size": props.get("quote_font_size", 14),
                                        "quote_align": "left",
                                        "quote_align_y": props.get("quote_align_y"),
                                        "quote_max_lines": props.get("quote_max_lines", 4),
                                        "author_template": props.get("author_template", "— {author}"),
                                        "author_font": props.get("author_font"),
                                        "author_font_name": props.get("author_font_name"),
                                        "author_font_size": props.get("author_font_size", 11),
                                        "author_align": "right",
                                        "author_align_y": props.get("author_align_y"),
                                        "author_max_lines": props.get("author_max_lines", 1),
                                        "divider_margin_x": props.get("divider_margin_x", 6),
                                        "gap": props.get("quote_gap", 2),
                                    },
                                ),
                                _build_fragment_instance(
                                    "book_block",
                                    {
                                        "title_field": props.get("book_title_field", "book_title"),
                                        "title_font": props.get("book_title_font"),
                                        "title_font_name": props.get("book_title_font_name"),
                                        "title_font_size": props.get("book_title_font_size", 13),
                                        "title_align": "left",
                                        "title_align_y": props.get("book_title_align_y"),
                                        "title_max_lines": props.get("book_title_max_lines", 2),
                                        "author_template": props.get("book_author_template", "{book_author}"),
                                        "author_font": props.get("book_author_font"),
                                        "author_font_name": props.get("book_author_font_name"),
                                        "author_font_size": props.get("book_author_font_size", 11),
                                        "author_align": "left",
                                        "author_align_y": props.get("book_author_align_y"),
                                        "author_max_lines": props.get("book_author_max_lines", 1),
                                        "desc_field": props.get("book_desc_field", "book_desc"),
                                        "desc_font": props.get("book_desc_font"),
                                        "desc_font_name": props.get("book_desc_font_name"),
                                        "desc_font_size": props.get("book_desc_font_size", 11),
                                        "desc_align": "left",
                                        "desc_align_y": props.get("book_desc_align_y"),
                                        "desc_max_lines": props.get("book_desc_max_lines", 2),
                                        "divider_margin_x": props.get("divider_margin_x", 6),
                                        "gap": props.get("book_gap", 2),
                                    },
                                ),
                                _build_fragment_instance(
                                    "plain_text",
                                    {
                                        "field": props.get("tip_field", "tip"),
                                        "font": props.get("tip_font"),
                                        "font_name": props.get("tip_font_name"),
                                        "font_size": props.get("tip_font_size", 11),
                                        "align": "left",
                                        "align_y": props.get("tip_align_y"),
                                        "max_lines": props.get("tip_max_lines", 2),
                                    },
                                ),
                            ],
                        },
                    ],
                }
            ],
        }
    )


def _quote_focus_card(props: dict[str, Any]) -> dict[str, Any]:
    return _compact(
        {
            "type": "column",
            "padding_x": props.get("padding_x", 18),
            "padding_y": props.get("padding_y"),
            "justify": props.get("justify", "center"),
            "gap": props.get("gap", 6),
            "children": [
                {
                    "type": "box",
                    "padding_x": props.get("quote_inset_x", 24),
                    "children": [
                        _text_node(
                            field=str(props.get("quote_field", "quote")),
                            font=props.get("quote_font"),
                            font_name=props.get("quote_font_name"),
                            font_size=props.get("quote_font_size", 18),
                            align="center",
                            align_y=props.get("quote_align_y"),
                            max_lines=props.get("quote_max_lines", 4),
                        )
                    ],
                }
            ],
        }
    )


def _zen_focus_card(props: dict[str, Any]) -> dict[str, Any]:
    children: list[dict[str, Any]] = [
        {
            "type": "box",
            "padding_x": props.get("word_inset_x", 60),
            "children": [
                _text_node(
                    field=str(props.get("word_field", "word")),
                    font=props.get("word_font"),
                    font_name=props.get("word_font_name"),
                    font_size=props.get("word_font_size", 96),
                    align="center",
                    align_y=props.get("word_align_y"),
                    max_lines=1,
                )
            ],
        }
    ]
    source_field = props.get("source_field")
    if source_field:
        children.append(
            _build_fragment_instance(
                "plain_text",
                {
                    "field": source_field,
                    "font": props.get("source_font"),
                    "font_name": props.get("source_font_name"),
                    "font_size": props.get("source_font_size", 9),
                    "align": "center",
                    "align_y": props.get("source_align_y"),
                    "max_lines": 1,
                },
            )
        )
    return _compact(
        {
            "type": "column",
            "padding_x": props.get("padding_x", 18),
            "justify": props.get("justify", "center"),
            "gap": props.get("gap", 10),
            "children": children,
        }
    )


def _prompt_card(props: dict[str, Any]) -> dict[str, Any]:
    children: list[dict[str, Any]] = []
    title_template = props.get("title_template")
    if title_template:
        children.append(
            _build_fragment_instance(
                "plain_text",
                {
                    "template": title_template,
                    "font": props.get("title_font"),
                    "font_name": props.get("title_font_name"),
                    "font_size": props.get("title_font_size", 14),
                    "align": "center",
                    "max_lines": 1,
                },
            )
        )
    meta_template = props.get("meta_template")
    if meta_template:
        children.append(
            _build_fragment_instance(
                "plain_text",
                {
                    "template": meta_template,
                    "font": props.get("meta_font"),
                    "font_name": props.get("meta_font_name"),
                    "font_size": props.get("meta_font_size", 11),
                    "align": "center",
                    "max_lines": 1,
                },
            )
        )
    if title_template or meta_template:
        children.append(_separator_node(style="short", width=props.get("separator_width", 60)))
    children.append(
        {
            "type": "box",
            "padding_x": props.get("hero_inset_x", 32),
            "children": [
                _text_node(
                    field=str(props.get("hero_field", "question")),
                    font=props.get("hero_font"),
                    font_name=props.get("hero_font_name"),
                    font_size=props.get("hero_font_size", 18),
                    align="center",
                    align_y=props.get("hero_align_y"),
                    max_lines=props.get("hero_max_lines", 3),
                )
            ],
        }
    )
    note_field = props.get("note_field")
    if note_field:
        if props.get("show_note_divider", True):
            children.append(
                _separator_node(style=props.get("note_divider_style", "dashed"), margin_x=props.get("note_divider_margin_x", 50))
            )
        children.append(
            _build_fragment_instance(
                "plain_text",
                {
                    "field": note_field,
                    "font": props.get("note_font"),
                    "font_name": props.get("note_font_name"),
                    "font_size": props.get("note_font_size", 11),
                    "align": "center",
                    "align_y": props.get("note_align_y"),
                    "max_lines": props.get("note_max_lines", 2),
                },
            )
        )
    return _compact(
        {
            "type": "column",
            "padding_x": props.get("padding_x", 18),
            "padding_y": props.get("padding_y"),
            "justify": props.get("justify", "center"),
            "gap": props.get("gap", 8),
            "children": children,
        }
    )


def _word_card(props: dict[str, Any]) -> dict[str, Any]:
    children: list[dict[str, Any]] = [
        {
            "type": "box",
            "padding_x": props.get("word_inset_x", 20),
            "children": [
                _text_node(
                    field=str(props.get("word_field", "word")),
                    font=props.get("word_font"),
                    font_name=props.get("word_font_name"),
                    font_size=props.get("word_font_size", 48),
                    align="center",
                    align_y=props.get("word_align_y"),
                    max_lines=props.get("word_max_lines", 2),
                )
            ],
        }
    ]
    phonetic_field = props.get("phonetic_field")
    if phonetic_field:
        children.append(
            _build_fragment_instance(
                "plain_text",
                {
                    "field": phonetic_field,
                    "font": props.get("phonetic_font"),
                    "font_name": props.get("phonetic_font_name"),
                    "font_size": props.get("phonetic_font_size", 11),
                    "align": "center",
                    "max_lines": 1,
                },
            )
        )
    children.append(_separator_node(style="short", width=props.get("separator_width", 40)))
    children.append(
        _build_fragment_instance(
            "plain_text",
            {
                "field": props.get("definition_field", "definition"),
                "font": props.get("definition_font"),
                "font_name": props.get("definition_font_name"),
                "font_size": props.get("definition_font_size", 16),
                "align": "center",
                "max_lines": props.get("definition_max_lines", 2),
            },
        )
    )
    example_field = props.get("example_field")
    if example_field:
        children.append(
            _build_fragment_instance(
                "plain_text",
                {
                    "field": example_field,
                    "font": props.get("example_font"),
                    "font_name": props.get("example_font_name"),
                    "font_size": props.get("example_font_size", 12),
                    "align": "center",
                    "max_lines": props.get("example_max_lines", 2),
                },
            )
        )
    return _compact(
        {
            "type": "column",
            "padding_x": props.get("padding_x", 18),
            "justify": props.get("justify", "center"),
            "gap": props.get("gap", 8),
            "children": children,
        }
    )


def _letter_card(props: dict[str, Any]) -> dict[str, Any]:
    children: list[dict[str, Any]] = []
    if props.get("top_gap"):
        children.append({"type": "spacer", "height": props.get("top_gap")})
    children.append(
        _build_fragment_instance(
            "plain_text",
            {
                "field": props.get("greeting_field", "greeting"),
                "font": props.get("greeting_font"),
                "font_name": props.get("greeting_font_name"),
                "font_size": props.get("greeting_font_size", 12),
                "align": "left",
                "max_lines": props.get("greeting_max_lines", 1),
            },
        )
    )
    children.append(
        _build_fragment_instance(
            "plain_text",
            {
                "field": props.get("body_field", "body"),
                "font": props.get("body_font"),
                "font_name": props.get("body_font_name"),
                "font_size": props.get("body_font_size", 13),
                "align": "left",
                "max_lines": props.get("body_max_lines", 6),
            },
        )
    )
    children.append(
        _build_fragment_instance(
            "plain_text",
            {
                "field": props.get("closing_field", "closing"),
                "font": props.get("closing_font"),
                "font_name": props.get("closing_font_name"),
                "font_size": props.get("closing_font_size", 12),
                "align": "right",
                "max_lines": props.get("closing_max_lines", 1),
            },
        )
    )
    postscript_field = props.get("postscript_field")
    if postscript_field:
        children.append(
            _build_fragment_instance(
                "plain_text",
                {
                    "field": postscript_field,
                    "font": props.get("postscript_font"),
                    "font_name": props.get("postscript_font_name"),
                    "font_size": props.get("postscript_font_size", 10),
                    "align": "left",
                    "max_lines": props.get("postscript_max_lines", 1),
                },
            )
        )
    return _compact(
        {
            "type": "column",
            "padding_x": props.get("padding_x", 18),
            "padding_y": props.get("padding_y"),
            "justify": props.get("justify", "center"),
            "gap": props.get("gap", 8),
            "children": children,
        }
    )


def _bias_card(props: dict[str, Any]) -> dict[str, Any]:
    children: list[dict[str, Any]] = []
    if props.get("top_gap"):
        children.append({"type": "spacer", "height": props.get("top_gap")})
    children.append(
        _build_fragment_instance(
            "plain_text",
            {
                "field": props.get("title_field", "name"),
                "font": props.get("title_font"),
                "font_name": props.get("title_font_name"),
                "font_size": props.get("title_font_size", 18),
                "align": "center",
                "max_lines": props.get("title_max_lines", 2),
            },
        )
    )
    subtitle_field = props.get("subtitle_field")
    if subtitle_field:
        children.append(
            _build_fragment_instance(
                "plain_text",
                {
                    "field": subtitle_field,
                    "font": props.get("subtitle_font"),
                    "font_name": props.get("subtitle_font_name"),
                    "font_size": props.get("subtitle_font_size", 11),
                    "align": "center",
                    "max_lines": props.get("subtitle_max_lines", 1),
                },
            )
        )
    children.append(_separator_node(style="short", width=props.get("separator_width", 70)))
    children.append(
        _build_fragment_instance(
            "plain_text",
            {
                "field": props.get("definition_field", "definition"),
                "font": props.get("definition_font"),
                "font_name": props.get("definition_font_name"),
                "font_size": props.get("definition_font_size", 14),
                "align": props.get("definition_align", "center"),
                "max_lines": props.get("definition_max_lines", 2),
            },
        )
    )
    example_field = props.get("example_field")
    if example_field:
        children.append(
            {
                "type": "section_box",
                "title": str(props.get("example_title", "Example")),
                "children": [
                    _build_fragment_instance(
                        "inset_body_text",
                        {
                            "field": example_field,
                            "font": props.get("example_font"),
                            "font_name": props.get("example_font_name"),
                            "font_size": props.get("example_font_size", 12),
                            "align": "left",
                            "max_lines": props.get("example_max_lines", 3),
                            "inset_x": props.get("example_inset_x", 36),
                        },
                    )
                ],
            }
        )
    antidote_field = props.get("antidote_field")
    if antidote_field:
        if props.get("show_antidote_divider", True):
            children.append(_separator_node(style="dashed", margin_x=props.get("antidote_divider_margin_x", 40)))
        antidote_label = props.get("antidote_label")
        if antidote_label:
            children.append(
                {
                    "type": "icon_text",
                    "icon": props.get("antidote_icon", "tips"),
                    "text": str(antidote_label),
                    "font_size": props.get("antidote_label_font_size", 12),
                    "margin_x": props.get("antidote_label_margin_x", 24),
                }
            )
        children.append(
            _build_fragment_instance(
                "inset_body_text",
                {
                    "field": antidote_field,
                    "font": props.get("antidote_font"),
                    "font_name": props.get("antidote_font_name"),
                    "font_size": props.get("antidote_font_size", 12),
                    "align": props.get("antidote_align", "left"),
                    "max_lines": props.get("antidote_max_lines", 2),
                    "inset_x": props.get("antidote_inset_x", 40),
                },
            )
        )
    return _compact(
        {
            "type": "column",
            "padding_x": props.get("padding_x", 18),
            "padding_y": props.get("padding_y"),
            "justify": props.get("justify", "center"),
            "gap": props.get("gap", 8),
            "children": children,
        }
    )


def _riddle_card(props: dict[str, Any]) -> dict[str, Any]:
    children: list[dict[str, Any]] = []
    if props.get("top_gap"):
        children.append({"type": "spacer", "height": props.get("top_gap")})
    meta_field = props.get("meta_field")
    if meta_field:
        children.append(
            _build_fragment_instance(
                "plain_text",
                {
                    "field": meta_field,
                    "font": props.get("meta_font"),
                    "font_name": props.get("meta_font_name"),
                    "font_size": props.get("meta_font_size", 11),
                    "align": "center",
                    "max_lines": props.get("meta_max_lines", 1),
                },
            )
        )
    if meta_field:
        children.append(_separator_node(style="short", width=props.get("separator_width", 60)))
    children.append(
        {
            "type": "box",
            "padding_x": props.get("question_inset_x", 24),
            "children": [
                _text_node(
                    field=str(props.get("question_field", "question")),
                    font=props.get("question_font"),
                    font_name=props.get("question_font_name"),
                    font_size=props.get("question_font_size", 18),
                    align="center",
                    align_y=props.get("question_align_y"),
                    max_lines=props.get("question_max_lines", 4),
                )
            ],
        }
    )
    hint_field = props.get("hint_field")
    if hint_field:
        hint_template = props.get("hint_template")
        children.append(
            _build_fragment_instance(
                "plain_text",
                {
                    "template": hint_template,
                    "field": None if hint_template else hint_field,
                    "font": props.get("hint_font"),
                    "font_name": props.get("hint_font_name"),
                    "font_size": props.get("hint_font_size", 11),
                    "align": "center",
                    "max_lines": props.get("hint_max_lines", 2),
                },
            )
        )
    answer_field = props.get("answer_field")
    if answer_field:
        if props.get("show_answer_divider", True):
            children.append(
                _separator_node(
                    style=props.get("answer_divider_style", "dashed"),
                    margin_x=props.get("answer_divider_margin_x", 60),
                )
            )
        children.append(
            _build_fragment_instance(
                "plain_text",
                {
                    "field": answer_field,
                    "font": props.get("answer_font"),
                    "font_name": props.get("answer_font_name"),
                    "font_size": props.get("answer_font_size", 12),
                    "align": "center",
                    "max_lines": props.get("answer_max_lines", 2),
                },
            )
        )
    return _compact(
        {
            "type": "column",
            "padding_x": props.get("padding_x", 18),
            "padding_y": props.get("padding_y"),
            "justify": props.get("justify", "center"),
            "gap": props.get("gap", 10),
            "children": children,
        }
    )


def _recipe_card(props: dict[str, Any]) -> dict[str, Any]:
    variant = str(props.get("variant", "full"))
    children: list[dict[str, Any]] = []
    title_align = "left" if variant == "compact" else "center"
    children.append(
        _build_fragment_instance(
            "plain_text",
            {
                "field": props.get("season_field", "season"),
                "font": props.get("season_font"),
                "font_name": props.get("season_font_name"),
                "font_size": props.get("season_font_size", 16),
                "align": title_align,
                "max_lines": 1,
            },
        )
    )
    children.append(_separator_node(style="short", width=props.get("separator_width", 70)))
    if variant == "compact":
        delimiter = str(props.get("compact_delimiter", ":"))
        for field_name, label_key in (
            ("breakfast", "breakfast_label"),
            ("lunch", "lunch_label"),
            ("dinner", "dinner_label"),
        ):
            label = str(props.get(label_key, field_name.title()))
            children.append(
                _build_fragment_instance(
                    "plain_text",
                    {
                        "template": f"{label}{delimiter} {{{field_name}}}",
                        "font": props.get("compact_font"),
                        "font_name": props.get("compact_font_name"),
                        "font_size": props.get("compact_font_size", 10),
                        "align": props.get("compact_align", "left"),
                        "max_lines": props.get("compact_max_lines", 1),
                    },
                )
            )
        compact_tip_field = props.get("compact_tip_field")
        if compact_tip_field:
            children.append(
                _build_fragment_instance(
                    "plain_text",
                    {
                        "field": compact_tip_field,
                        "font": props.get("compact_tip_font"),
                        "font_name": props.get("compact_tip_font_name"),
                        "font_size": props.get("compact_tip_font_size", 9),
                        "align": props.get("compact_tip_align", "left"),
                        "max_lines": props.get("compact_tip_max_lines", 1),
                    },
                )
            )
    else:
        section_font_size = props.get("section_font_size", 13)
        meal_font_size = props.get("meal_font_size", 13)
        meal_max_lines = props.get("meal_max_lines", 2)
        meal_inset_x = props.get("meal_inset_x", 36)
        for field_name, label_key in (
            ("breakfast", "breakfast_title"),
            ("lunch", "lunch_title"),
            ("dinner", "dinner_title"),
        ):
            children.append(
                {
                    "type": "section_box",
                    "title": str(props.get(label_key, field_name.title())),
                    "title_font_size": section_font_size,
                    "children": [
                        _build_fragment_instance(
                            "inset_body_text",
                            {
                                "field": field_name,
                                "font": props.get("meal_font"),
                                "font_name": props.get("meal_font_name"),
                                "font_size": meal_font_size,
                                "align": "left",
                                "max_lines": meal_max_lines,
                                "inset_x": meal_inset_x,
                            },
                        )
                    ],
                }
            )
        tip_field = props.get("tip_field")
        if tip_field:
            if props.get("show_tip_divider", True):
                children.append(
                    _separator_node(style=props.get("tip_divider_style", "dashed"), margin_x=props.get("tip_divider_margin_x", 30))
                )
            children.append(
                _build_fragment_instance(
                    "plain_text",
                    {
                        "field": tip_field,
                        "font": props.get("tip_font"),
                        "font_name": props.get("tip_font_name"),
                        "font_size": props.get("tip_font_size", 12),
                        "align": "center",
                        "max_lines": props.get("tip_max_lines", 2),
                    },
                )
            )
    return _compact(
        {
            "type": "column",
            "padding_x": props.get("padding_x", 18),
            "padding_y": props.get("padding_y"),
            "justify": props.get("justify", "center"),
            "gap": props.get("gap", 6),
            "children": children,
        }
    )


def _poetry_card(props: dict[str, Any]) -> dict[str, Any]:
    children: list[dict[str, Any]] = []
    if props.get("top_gap"):
        children.append({"type": "spacer", "height": props.get("top_gap")})
    children.append(
        _build_fragment_instance(
            "plain_text",
            {
                "field": props.get("title_field", "title"),
                "font": props.get("title_font"),
                "font_name": props.get("title_font_name"),
                "font_size": props.get("title_font_size", 14),
                "align": "center",
                "max_lines": props.get("title_max_lines", 1),
            },
        )
    )
    author_field = props.get("author_field")
    if author_field:
        children.append(
            _build_fragment_instance(
                "plain_text",
                {
                    "field": author_field,
                    "font": props.get("author_font"),
                    "font_name": props.get("author_font_name"),
                    "font_size": props.get("author_font_size", 11),
                    "align": "center",
                    "max_lines": props.get("author_max_lines", 1),
                },
            )
        )
    children.append(_separator_node(style="short", width=props.get("separator_width", 60)))
    children.append(
        {
            "type": "box",
            "padding_x": props.get("lines_inset_x", 30),
            "children": [
                {
                    "type": "repeat",
                    "field": props.get("lines_field", "lines"),
                    "limit": props.get("lines_limit", 8),
                    "gap": props.get("lines_gap", 8),
                    "item": _text_node(
                        field="_value",
                        font=props.get("lines_font"),
                        font_name=props.get("lines_font_name"),
                        font_size=props.get("lines_font_size", 16),
                        align="center",
                        max_lines=props.get("line_max_lines", 1),
                    ),
                }
            ],
        }
    )
    note_field = props.get("note_field")
    if note_field:
        children.append(
            _build_fragment_instance(
                "plain_text",
                {
                    "field": note_field,
                    "font": props.get("note_font"),
                    "font_name": props.get("note_font_name"),
                    "font_size": props.get("note_font_size", 10),
                    "align": "center",
                    "max_lines": props.get("note_max_lines", 2),
                },
            )
        )
    return _compact(
        {
            "type": "column",
            "padding_x": props.get("padding_x", 18),
            "padding_y": props.get("padding_y"),
            "justify": props.get("justify", "center"),
            "gap": props.get("gap", 8),
            "children": children,
        }
    )


def _progress_metric(metric: dict[str, Any]) -> dict[str, Any]:
    children: list[dict[str, Any]] = []
    label_field = metric.get("label_field")
    label_template = metric.get("label_template")
    if label_field or label_template:
        children.append(
            _text_node(
                field=str(label_field) if label_field else None,
                template=label_template,
                font=metric.get("label_font"),
                font_name=metric.get("label_font_name"),
                font_size=metric.get("label_font_size"),
                align=metric.get("label_align", "left"),
                max_lines=metric.get("label_max_lines", 1),
            )
        )
    children.append(
        _text_node(
            field=str(metric.get("value_field")) if metric.get("value_field") else None,
            template=metric.get("value_template"),
            font=metric.get("value_font"),
            font_name=metric.get("value_font_name"),
            font_size=metric.get("value_font_size"),
            align=metric.get("value_align", "left"),
            max_lines=metric.get("value_max_lines", 1),
        )
    )
    children.append(
        _compact(
            {
                "type": "progress_bar",
                "field": metric.get("bar_field"),
                "max_field": metric.get("bar_max_field"),
                "width": metric.get("bar_width"),
                "height": metric.get("bar_height"),
            }
        )
    )
    return {
        "type": "column",
        "gap": metric.get("gap", 4),
        "children": children,
    }


def _fitness_rows(props: dict[str, Any]) -> dict[str, Any]:
    left_template = props.get("exercise_template")
    left_field = props.get("exercise_name_field", "name")
    return {
        "type": "repeat",
        "field": str(props.get("exercises_field", "exercises")),
        "limit": props.get("exercise_limit", 8),
        "gap": props.get("exercise_gap", 6),
        "item": {
            "type": "row",
            "gap": props.get("exercise_row_gap", 8),
            "align": props.get("exercise_row_align", "end"),
            "children": [
                _text_node(
                    field=str(left_field) if not left_template else None,
                    template=left_template,
                    font=props.get("exercise_font"),
                    font_name=props.get("exercise_font_name"),
                    font_size=props.get("exercise_font_size", 13),
                    align=props.get("exercise_align", "left"),
                    max_lines=props.get("exercise_max_lines", 1),
                    grow=1,
                ),
                _text_node(
                    field=str(props.get("exercise_reps_field", "reps")),
                    font=props.get("exercise_reps_font"),
                    font_name=props.get("exercise_reps_font_name"),
                    font_size=props.get("exercise_reps_font_size", 13),
                    align=props.get("exercise_reps_align", "right"),
                    max_lines=1,
                ),
            ],
        },
    }


def _lifebar_card(props: dict[str, Any]) -> dict[str, Any]:
    primary_metric = _merge_defaults(
        props.get("primary_metric") if isinstance(props.get("primary_metric"), dict) else {},
        {
            "label_field": "year_label",
            "value_template": "{year_pct}%",
            "value_font": "noto_serif_bold",
            "label_font_size": 12,
            "value_font_size": 28,
            "bar_field": "day_of_year",
            "bar_max_field": "days_in_year",
            "bar_width": 336,
            "bar_height": 8,
            "gap": 4,
        },
    )
    left_metric = _merge_defaults(
        props.get("left_metric") if isinstance(props.get("left_metric"), dict) else {},
        {
            "label_field": "month_label",
            "value_template": "{month_pct}%",
            "value_font": "noto_serif_bold",
            "label_font_size": 11,
            "value_font_size": 20,
            "bar_field": "day",
            "bar_max_field": "days_in_month",
            "bar_width": 140,
            "bar_height": 6,
            "gap": 4,
        },
    )
    right_metric = _merge_defaults(
        props.get("right_metric") if isinstance(props.get("right_metric"), dict) else {},
        {
            "label_field": "week_label",
            "value_template": "{week_pct}%",
            "value_font": "noto_serif_bold",
            "label_font_size": 11,
            "value_font_size": 20,
            "bar_field": "weekday_num",
            "bar_max_field": "week_total",
            "bar_width": 140,
            "bar_height": 6,
            "gap": 4,
        },
    )
    bottom_metric = _merge_defaults(
        props.get("bottom_metric") if isinstance(props.get("bottom_metric"), dict) else {},
        {
            "label_field": "life_label",
            "value_template": "{life_pct}%",
            "value_font": "noto_serif_bold",
            "label_font_size": 11,
            "value_font_size": 20,
            "bar_field": "age",
            "bar_max_field": "life_expect",
            "bar_width": 336,
            "bar_height": 8,
            "gap": 4,
        },
    )
    children: list[dict[str, Any]] = []
    if props.get("top_gap"):
        children.append({"type": "spacer", "height": props.get("top_gap")})
    children.append(_progress_metric(primary_metric))
    if props.get("show_middle", True):
        children.append(
            {
                "type": "row",
                "gap": props.get("row_gap", 10),
                "children": [
                    {
                        "type": "box",
                        "width": props.get("left_panel_width", 163),
                        "children": [_progress_metric(left_metric)],
                    },
                    {
                        "type": "box",
                        "width": props.get("right_panel_width", 163),
                        "children": [_progress_metric(right_metric)],
                    },
                ],
            }
        )
    if props.get("show_divider", True):
        children.append(
            _separator_node(
                style=props.get("divider_style", "dashed"),
                margin_x=props.get("divider_margin_x"),
            )
        )
    children.append(_progress_metric(bottom_metric))
    return _compact(
        {
            "type": "column",
            "padding_x": props.get("padding_x", 32),
            "padding_y": props.get("padding_y"),
            "justify": props.get("justify", "start"),
            "gap": props.get("gap", 14),
            "children": children,
        }
    )


def _countdown_card(props: dict[str, Any]) -> dict[str, Any]:
    event_children: list[dict[str, Any]] = []
    name_field = props.get("event_name_field", "name")
    if name_field:
        event_children.append(
            _text_node(
                field=str(name_field),
                font=props.get("event_name_font"),
                font_name=props.get("event_name_font_name"),
                font_size=props.get("event_name_font_size", 14),
                align="center",
                max_lines=props.get("event_name_max_lines", 2),
            )
        )
    if props.get("show_event_date", True):
        event_children.append(
            _text_node(
                field=str(props.get("event_date_field", "date")),
                font=props.get("event_date_font"),
                font_name=props.get("event_date_font_name"),
                font_size=props.get("event_date_font_size", 11),
                align="center",
                max_lines=1,
            )
        )
    if props.get("show_divider", True):
        event_children.append(
            _separator_node(
                style=props.get("divider_style", "short"),
                width=props.get("divider_width", 70),
            )
        )
    event_children.append(
        {
            "type": "big_number",
            "field": str(props.get("days_field", "days")),
            "font": props.get("days_font"),
            "font_size": props.get("days_font_size", 52),
            "align": "center",
        }
    )
    days_label_template = props.get("days_label_template")
    if days_label_template:
        event_children.append(
            _text_node(
                template=days_label_template,
                font=props.get("days_label_font"),
                font_name=props.get("days_label_font_name"),
                font_size=props.get("days_label_font_size", 13),
                align="center",
                max_lines=1,
            )
        )
    children: list[dict[str, Any]] = []
    if props.get("top_gap"):
        children.append({"type": "spacer", "height": props.get("top_gap")})
    message_field = props.get("message_field", "message")
    if message_field:
        children.append(
            _text_node(
                field=str(message_field),
                font=props.get("message_font"),
                font_name=props.get("message_font_name"),
                font_size=props.get("message_font_size", 16),
                align="center",
                max_lines=props.get("message_max_lines", 2),
            )
        )
    children.append(
        {
            "type": "repeat",
            "field": str(props.get("events_field", "events")),
            "limit": 1,
            "item": {
                "type": "column",
                "gap": props.get("event_gap", 6),
                "children": event_children,
            },
        }
    )
    return _compact(
        {
            "type": "column",
            "padding_x": props.get("padding_x", 18),
            "padding_y": props.get("padding_y"),
            "justify": props.get("justify", "center"),
            "gap": props.get("gap", 18),
            "children": children,
        }
    )


def _fitness_card(props: dict[str, Any]) -> dict[str, Any]:
    children: list[dict[str, Any]] = []
    if props.get("top_gap"):
        children.append({"type": "spacer", "height": props.get("top_gap")})
    children.append(
        _text_node(
            field=str(props.get("title_field", "workout_name")),
            font=props.get("title_font"),
            font_name=props.get("title_font_name"),
            font_size=props.get("title_font_size", 16),
            align=props.get("title_align", "center"),
            max_lines=props.get("title_max_lines", 2),
        )
    )
    children.append(
        _text_node(
            field=str(props.get("duration_field", "duration")),
            font=props.get("duration_font"),
            font_name=props.get("duration_font_name"),
            font_size=props.get("duration_font_size", 14),
            align=props.get("duration_align", "center"),
            max_lines=1,
        )
    )
    children.append(
        _separator_node(
            style=props.get("header_divider_style", "solid"),
            margin_x=props.get("header_divider_margin_x", 24),
            width=props.get("header_divider_width"),
        )
    )
    children.append(
        {
            "type": "section_box",
            "title": str(props.get("exercise_title", "Exercises")),
            "icon": props.get("exercise_icon", "exercise"),
            "title_font": props.get("section_title_font"),
            "title_font_size": props.get("section_title_font_size", 14),
            "content_indent": props.get("section_content_indent", 36),
            "gap": props.get("section_gap", 4),
            "children": [_fitness_rows(props)],
        }
    )
    if props.get("tip_field"):
        if props.get("show_tip_divider", True):
            children.append(
                _separator_node(
                    style=props.get("tip_divider_style", "solid"),
                    margin_x=props.get("tip_divider_margin_x", 24),
                )
            )
        children.append(
            {
                "type": "section_box",
                "title": str(props.get("tip_title", "Tip")),
                "icon": props.get("tip_icon", "tips"),
                "title_font": props.get("section_title_font"),
                "title_font_size": props.get("section_title_font_size", 14),
                "content_indent": props.get("section_content_indent", 36),
                "gap": props.get("section_gap", 4),
                "children": [
                    _text_node(
                        field=str(props.get("tip_field", "tip")),
                        font=props.get("tip_font"),
                        font_name=props.get("tip_font_name"),
                        font_size=props.get("tip_font_size", 14),
                        align="left",
                        max_lines=props.get("tip_max_lines", 3),
                    )
                ],
            }
        )
    return _compact(
        {
            "type": "column",
            "padding_x": props.get("padding_x", 18),
            "padding_y": props.get("padding_y"),
            "justify": props.get("justify", "start"),
            "gap": props.get("gap", 6),
            "children": children,
        }
    )


PRESET_REGISTRY: dict[str, PresetSpec] = {
    "story_card": PresetSpec(
        builder=_story_card,
        props=("padding_x", "padding_y", "justify", "gap", "meta_field", "meta_font", "meta_font_name", "meta_font_size", "title_field", "title_font", "title_font_name", "title_font_size", "title_max_lines", "separator_width", "header_gap", "section_gap", "sections"),
        required_props=("title_field", "sections"),
        defaults={"title_field": "title", "title_font": "noto_serif_bold", "title_font_size": 20, "title_max_lines": 2, "meta_field": "meta", "meta_font": "noto_serif_light", "meta_font_size": 12, "separator_width": 50, "header_gap": 3, "section_gap": 6, "padding_x": 18, "padding_y": 6, "justify": "center", "gap": 6, "sections": [{"field": "body", "font": "noto_serif_light", "font_size": 15, "max_lines": 10}]},
    ),
    "thisday_card": PresetSpec(
        builder=_thisday_card,
        props=("padding_x", "padding_y", "justify", "gap", "meta_field", "meta_font_size", "hero_field", "hero_font_size", "separator_width", "title_field", "title_font", "title_font_name", "title_font_size", "title_max_lines", "body_field", "body_font", "body_font_name", "body_font_size", "body_inset_x", "body_max_lines", "body_gap", "divider_inset_x", "footer_field", "footer_font", "footer_font_name", "footer_font_size", "footer_max_lines", "footer_gap"),
        required_props=("hero_field", "title_field", "body_field"),
    ),
    "briefing_sections": PresetSpec(
        builder=_briefing_sections,
        props=("padding_x", "padding_y", "gap", "justify", "sections"),
        required_props=("sections",),
    ),
    "daily_card": PresetSpec(
        builder=_daily_card,
        props=("variant", "padding_x", "justify", "gap", "row_gap", "min_height", "panel_width", "panel_padding_x", "panel_gap", "year_field", "year_font_size", "day_field", "day_font_size", "day_align", "day_align_y", "month_field", "month_font_size", "weekday_field", "weekday_font_size", "progress_field", "progress_max_field", "progress_width", "season_field", "season_font", "season_font_name", "season_font_size", "season_align_y", "season_max_lines", "season_inset_x", "content_padding_x", "content_justify", "quote_field", "quote_font", "quote_font_name", "quote_font_size", "quote_align_y", "quote_max_lines", "author_template", "author_font", "author_font_name", "author_font_size", "author_align_y", "author_max_lines", "quote_gap", "book_title_field", "book_title_font", "book_title_font_name", "book_title_font_size", "book_title_align_y", "book_title_max_lines", "book_author_template", "book_author_font", "book_author_font_name", "book_author_font_size", "book_author_align_y", "book_author_max_lines", "book_desc_field", "book_desc_font", "book_desc_font_name", "book_desc_font_size", "book_desc_align_y", "book_desc_max_lines", "book_gap", "divider_margin_x", "tip_field", "tip_font", "tip_font_name", "tip_font_size", "tip_max_lines", "meta_template", "meta_font_size", "meta_align", "separator_width"),
        defaults={"variant": "full"},
    ),
    "quote_focus_card": PresetSpec(
        builder=_quote_focus_card,
        props=("padding_x", "padding_y", "justify", "gap", "quote_inset_x", "quote_field", "quote_font", "quote_font_name", "quote_font_size", "quote_align_y", "quote_max_lines"),
        defaults={"quote_field": "quote", "quote_font": "noto_serif_light", "quote_font_size": 22, "quote_align_y": "center", "quote_max_lines": 6, "quote_inset_x": 24, "padding_x": 18, "padding_y": 10, "justify": "center", "gap": 6},
    ),
    "zen_focus_card": PresetSpec(
        builder=_zen_focus_card,
        props=("padding_x", "justify", "gap", "word_inset_x", "word_field", "word_font", "word_font_name", "word_font_size", "word_align_y", "source_field", "source_font", "source_font_name", "source_font_size", "source_align_y"),
        defaults={"word_field": "word", "word_font": "noto_serif_bold", "word_font_size": 48, "word_align_y": "center", "word_inset_x": 20, "source_field": "source", "source_font": "noto_serif_light", "source_font_size": 14, "source_align_y": "bottom", "padding_x": 18, "justify": "center", "gap": 8},
    ),
    "prompt_card": PresetSpec(
        builder=_prompt_card,
        props=("padding_x", "padding_y", "justify", "gap", "title_template", "title_font", "title_font_name", "title_font_size", "meta_template", "meta_font", "meta_font_name", "meta_font_size", "separator_width", "hero_inset_x", "hero_field", "hero_font", "hero_font_name", "hero_font_size", "hero_align_y", "hero_max_lines", "note_field", "note_font", "note_font_name", "note_font_size", "note_align_y", "note_max_lines", "show_note_divider", "note_divider_style", "note_divider_margin_x"),
        required_props=("hero_field",),
        defaults={"hero_field": "question", "hero_font": "noto_serif_light", "hero_font_size": 20, "hero_align_y": "center", "hero_max_lines": 5, "hero_inset_x": 20, "note_field": "note", "note_font": "noto_serif_light", "note_font_size": 13, "note_max_lines": 2, "separator_width": 50, "padding_x": 18, "padding_y": 10, "justify": "center", "gap": 6},
    ),
    "word_card": PresetSpec(
        builder=_word_card,
        props=("padding_x", "justify", "gap", "word_inset_x", "word_field", "word_font", "word_font_name", "word_font_size", "word_align_y", "word_max_lines", "phonetic_field", "phonetic_font", "phonetic_font_name", "phonetic_font_size", "separator_width", "definition_field", "definition_font", "definition_font_name", "definition_font_size", "definition_max_lines", "example_field", "example_font", "example_font_name", "example_font_size", "example_max_lines"),
        required_props=("word_field", "definition_field"),
        defaults={"word_field": "word", "word_font": "noto_serif_bold", "word_font_size": 32, "word_align_y": "center", "word_max_lines": 2, "word_inset_x": 20, "phonetic_field": "phonetic", "phonetic_font_size": 14, "separator_width": 50, "definition_field": "definition", "definition_font": "noto_serif_light", "definition_font_size": 16, "definition_max_lines": 3, "example_field": "example", "example_font": "noto_serif_light", "example_font_size": 13, "example_max_lines": 2, "padding_x": 18, "justify": "center", "gap": 6},
    ),
    "letter_card": PresetSpec(
        builder=_letter_card,
        props=("padding_x", "padding_y", "justify", "gap", "top_gap", "greeting_field", "greeting_font", "greeting_font_name", "greeting_font_size", "greeting_max_lines", "body_field", "body_font", "body_font_name", "body_font_size", "body_max_lines", "closing_field", "closing_font", "closing_font_name", "closing_font_size", "closing_max_lines", "postscript_field", "postscript_font", "postscript_font_name", "postscript_font_size", "postscript_max_lines"),
        defaults={"greeting_field": "greeting", "greeting_font": "noto_serif_light", "greeting_font_size": 16, "greeting_max_lines": 1, "body_field": "body", "body_font": "noto_serif_light", "body_font_size": 16, "body_max_lines": 8, "closing_field": "closing", "closing_font": "noto_serif_light", "closing_font_size": 14, "closing_max_lines": 1, "postscript_field": "postscript", "postscript_font": "noto_serif_light", "postscript_font_size": 12, "postscript_max_lines": 2, "padding_x": 24, "padding_y": 12, "justify": "center", "gap": 6, "top_gap": 8},
    ),
    "bias_card": PresetSpec(
        builder=_bias_card,
        props=("padding_x", "padding_y", "justify", "gap", "top_gap", "title_field", "title_font", "title_font_name", "title_font_size", "title_max_lines", "subtitle_field", "subtitle_font", "subtitle_font_name", "subtitle_font_size", "subtitle_max_lines", "separator_width", "definition_field", "definition_font", "definition_font_name", "definition_font_size", "definition_align", "definition_max_lines", "example_title", "example_field", "example_font", "example_font_name", "example_font_size", "example_max_lines", "example_inset_x", "show_antidote_divider", "antidote_divider_margin_x", "antidote_icon", "antidote_label", "antidote_label_font_size", "antidote_label_margin_x", "antidote_field", "antidote_font", "antidote_font_name", "antidote_font_size", "antidote_align", "antidote_max_lines", "antidote_inset_x"),
        defaults={"title_field": "name", "title_font": "noto_serif_bold", "title_font_size": 20, "title_max_lines": 1, "subtitle_field": "subtitle", "subtitle_font": "noto_serif_light", "subtitle_font_size": 13, "subtitle_max_lines": 1, "separator_width": 50, "definition_field": "definition", "definition_font": "noto_serif_light", "definition_font_size": 15, "definition_max_lines": 3, "example_title": "Example", "example_field": "example", "example_font": "noto_serif_light", "example_font_size": 13, "example_max_lines": 3, "example_inset_x": 16, "antidote_icon": "tips", "antidote_label": "Antidote", "antidote_field": "antidote", "antidote_font": "noto_serif_light", "antidote_font_size": 13, "antidote_max_lines": 3, "antidote_inset_x": 16, "show_antidote_divider": True, "padding_x": 18, "padding_y": 8, "justify": "center", "gap": 4, "top_gap": 6},
    ),
    "riddle_card": PresetSpec(
        builder=_riddle_card,
        props=("padding_x", "padding_y", "justify", "gap", "top_gap", "meta_field", "meta_font", "meta_font_name", "meta_font_size", "meta_max_lines", "separator_width", "question_inset_x", "question_field", "question_font", "question_font_name", "question_font_size", "question_align_y", "question_max_lines", "hint_field", "hint_template", "hint_font", "hint_font_name", "hint_font_size", "hint_max_lines", "show_answer_divider", "answer_divider_style", "answer_divider_margin_x", "answer_field", "answer_font", "answer_font_name", "answer_font_size", "answer_max_lines"),
        defaults={"meta_field": "category", "meta_font": "noto_serif_light", "meta_font_size": 13, "meta_max_lines": 1, "separator_width": 50, "question_field": "question", "question_font": "noto_serif_light", "question_font_size": 20, "question_align_y": "center", "question_max_lines": 4, "question_inset_x": 20, "hint_field": "hint", "hint_font": "noto_serif_light", "hint_font_size": 13, "hint_max_lines": 2, "answer_field": "answer", "answer_font": "noto_serif_light", "answer_font_size": 14, "answer_max_lines": 2, "show_answer_divider": True, "padding_x": 18, "padding_y": 10, "justify": "center", "gap": 5, "top_gap": 6},
    ),
    "recipe_card": PresetSpec(
        builder=_recipe_card,
        props=("variant", "padding_x", "padding_y", "justify", "gap", "season_field", "season_font", "season_font_name", "season_font_size", "separator_width", "section_font_size", "meal_font", "meal_font_name", "meal_font_size", "meal_max_lines", "meal_inset_x", "breakfast_title", "lunch_title", "dinner_title", "tip_field", "tip_font", "tip_font_name", "tip_font_size", "tip_max_lines", "show_tip_divider", "tip_divider_style", "tip_divider_margin_x", "compact_delimiter", "compact_font", "compact_font_name", "compact_font_size", "compact_align", "compact_max_lines", "compact_tip_field", "compact_tip_font", "compact_tip_font_name", "compact_tip_font_size", "compact_tip_align", "compact_tip_max_lines", "breakfast_label", "lunch_label", "dinner_label"),
        defaults={"variant": "full", "season_field": "season", "breakfast_title": "Breakfast", "lunch_title": "Lunch", "dinner_title": "Dinner", "tip_field": "tip", "breakfast_label": "Breakfast", "lunch_label": "Lunch", "dinner_label": "Dinner"},
    ),
    "poetry_card": PresetSpec(
        builder=_poetry_card,
        props=("padding_x", "padding_y", "justify", "gap", "top_gap", "title_field", "title_font", "title_font_name", "title_font_size", "title_max_lines", "author_field", "author_font", "author_font_name", "author_font_size", "author_max_lines", "separator_width", "lines_inset_x", "lines_field", "lines_limit", "lines_gap", "lines_font", "lines_font_name", "lines_font_size", "line_max_lines", "note_field", "note_font", "note_font_name", "note_font_size", "note_max_lines"),
        defaults={"title_field": "title", "title_font": "noto_serif_bold", "title_font_size": 20, "title_max_lines": 1, "author_field": "author", "author_font": "noto_serif_light", "author_font_size": 14, "author_max_lines": 1, "separator_width": 50, "lines_field": "lines", "lines_font": "noto_serif_light", "lines_font_size": 16, "lines_limit": 8, "lines_gap": 4, "line_max_lines": 1, "lines_inset_x": 24, "note_field": "note", "note_font": "noto_serif_light", "note_font_size": 12, "note_max_lines": 2, "padding_x": 18, "padding_y": 10, "justify": "center", "gap": 5, "top_gap": 6},
    ),
    "lifebar_card": PresetSpec(
        builder=_lifebar_card,
        props=("padding_x", "padding_y", "justify", "gap", "top_gap", "show_middle", "row_gap", "left_panel_width", "right_panel_width", "show_divider", "divider_style", "divider_margin_x", "primary_metric", "left_metric", "right_metric", "bottom_metric"),
    ),
    "countdown_card": PresetSpec(
        builder=_countdown_card,
        props=("padding_x", "padding_y", "justify", "gap", "top_gap", "message_field", "message_font", "message_font_name", "message_font_size", "message_max_lines", "events_field", "event_gap", "event_name_field", "event_name_font", "event_name_font_name", "event_name_font_size", "event_name_max_lines", "show_event_date", "event_date_field", "event_date_font", "event_date_font_name", "event_date_font_size", "show_divider", "divider_style", "divider_width", "days_field", "days_font", "days_font_size", "days_label_template", "days_label_font", "days_label_font_name", "days_label_font_size"),
        defaults={"message_field": "message", "message_font": "noto_serif_light", "message_font_size": 14, "message_max_lines": 2, "events_field": "events", "event_gap": 8, "event_name_field": "name", "event_name_font": "noto_serif_light", "event_name_font_size": 16, "event_name_max_lines": 1, "event_date_field": "date", "event_date_font_size": 12, "show_event_date": True, "days_field": "days", "days_font_size": 36, "show_divider": True, "padding_x": 18, "padding_y": 10, "justify": "center", "gap": 6, "top_gap": 6},
    ),
    "fitness_card": PresetSpec(
        builder=_fitness_card,
        props=("padding_x", "padding_y", "justify", "gap", "top_gap", "title_field", "title_font", "title_font_name", "title_font_size", "title_align", "title_max_lines", "duration_field", "duration_font", "duration_font_name", "duration_font_size", "duration_align", "header_divider_style", "header_divider_margin_x", "header_divider_width", "exercise_title", "exercise_icon", "section_title_font", "section_title_font_size", "section_content_indent", "section_gap", "exercises_field", "exercise_limit", "exercise_gap", "exercise_row_gap", "exercise_row_align", "exercise_name_field", "exercise_template", "exercise_font", "exercise_font_name", "exercise_font_size", "exercise_align", "exercise_max_lines", "exercise_reps_field", "exercise_reps_font", "exercise_reps_font_name", "exercise_reps_font_size", "exercise_reps_align", "show_tip_divider", "tip_divider_style", "tip_divider_margin_x", "tip_title", "tip_icon", "tip_field", "tip_font", "tip_font_name", "tip_font_size", "tip_max_lines"),
        defaults={"title_field": "workout_name", "duration_field": "duration", "exercises_field": "exercises", "exercise_name_field": "name", "exercise_reps_field": "reps", "tip_field": "tip"},
    ),
}


_PUBLIC_FRAGMENT_META: dict[str, dict[str, str]] = {
    "plain_text": {
        "label": "Plain Text",
        "label_zh": "纯文本",
        "description": "A single text block with font, size, and alignment controls.",
        "description_zh": "单个文本块，可设置字体、字号和对齐。",
    },
    "title_with_rule": {
        "label": "Title With Rule",
        "label_zh": "标题加分隔线",
        "description": "A title block with optional meta text and a divider.",
        "description_zh": "带可选副标题和分隔线的标题块。",
    },
    "inset_body_text": {
        "label": "Inset Body Text",
        "label_zh": "缩进正文",
        "description": "Body text with left and right inset padding.",
        "description_zh": "带左右缩进的正文文本。",
    },
    "footer_note": {
        "label": "Footer Note",
        "label_zh": "底部说明",
        "description": "A footer text block with optional divider above it.",
        "description_zh": "底部说明文字，可选上方分隔线。",
    },
    "metric_hero": {
        "label": "Metric Hero",
        "label_zh": "数字主视觉",
        "description": "A large metric value with optional meta text.",
        "description_zh": "大数字主视觉，可附带说明文字。",
    },
    "quote_block": {
        "label": "Quote Block",
        "label_zh": "语录块",
        "description": "A quote with optional attribution and divider.",
        "description_zh": "语录加署名，可带分隔线。",
    },
    "book_block": {
        "label": "Book Block",
        "label_zh": "书籍块",
        "description": "Book title, author, and description layout.",
        "description_zh": "书名、作者和简介布局。",
    },
}

_PUBLIC_PRESET_META: dict[str, dict[str, str]] = {
    "quote_focus_card": {
        "label": "Centered Text",
        "label_zh": "居中文本",
        "description": "A centered full-page text card, great for quotes or affirmations.",
        "description_zh": "居中展示的整页文本卡片，适合语录、格言等。",
    },
    "zen_focus_card": {
        "label": "Big Word",
        "label_zh": "大字展示",
        "description": "A large word/phrase with optional source line.",
        "description_zh": "大字为主，可附来源说明。",
    },
    "prompt_card": {
        "label": "Title + Body",
        "label_zh": "标题正文",
        "description": "Title, main text block, and optional note.",
        "description_zh": "标题、主体文本和可选补充说明。",
    },
    "word_card": {
        "label": "Term Card",
        "label_zh": "词条卡片",
        "description": "A term with pronunciation, definition, and example.",
        "description_zh": "词条、注音、释义和例句。",
    },
    "letter_card": {
        "label": "Letter",
        "label_zh": "信笺",
        "description": "Greeting, body, closing, and postscript.",
        "description_zh": "称呼、正文、落款和附言。",
    },
    "poetry_card": {
        "label": "Verse",
        "label_zh": "诗文",
        "description": "Title, author, lines of text, and optional note.",
        "description_zh": "标题、作者、逐行文本和可选注释。",
    },
    "riddle_card": {
        "label": "Q & A",
        "label_zh": "问答",
        "description": "Category, question, hint, and answer.",
        "description_zh": "分类、问题、提示和答案。",
    },
    "bias_card": {
        "label": "Knowledge Card",
        "label_zh": "知识卡片",
        "description": "Name, definition, example, and tip.",
        "description_zh": "名称、定义、案例和建议。",
    },
    "story_card": {
        "label": "Article",
        "label_zh": "图文",
        "description": "Title, meta info, and body sections.",
        "description_zh": "标题、元信息和正文段落。",
    },
    "countdown_card": {
        "label": "Countdown",
        "label_zh": "倒计时",
        "description": "Message and event countdowns with days remaining.",
        "description_zh": "寄语和事件倒计时，显示剩余天数。",
    },
}

_PUBLIC_FRAGMENT_ORDER = tuple(_PUBLIC_FRAGMENT_META.keys())
_PUBLIC_PRESET_ORDER = tuple(_PUBLIC_PRESET_META.keys())
_PUBLIC_FONT_OPTIONS = (
    "noto_serif_light",
    "noto_serif_regular",
    "noto_serif_bold",
    "lora_regular",
    "lora_bold",
    "inter_medium",
)
_PUBLIC_SELECT_OPTIONS: dict[str, tuple[str, ...]] = {
    "align": ("left", "center", "right"),
    "align_y": ("top", "center", "bottom"),
    "justify": ("start", "center", "end", "space_between"),
    "style": ("short", "solid", "dashed"),
    "variant": ("full", "compact"),
}
_FRAGMENT_STACK_DEFAULTS = {
    "padding_x": 18,
    "gap": 6,
    "justify": "center",
}
_FRAGMENT_STACK_PROPS = ("padding_x", "padding_y", "gap", "justify")


def _humanize_prop_name(name: str) -> str:
    words = str(name).split("_")
    return " ".join(word.capitalize() if word else "" for word in words).strip()


_PROP_LABEL_ZH: dict[str, str] = {
    "padding_x": "水平内边距",
    "padding_y": "垂直内边距",
    "justify": "纵向对齐",
    "gap": "间距",
    "top_gap": "顶部间距",
    "row_gap": "行间距",
    "grow": "自动伸展",
    "field": "数据字段",
    "font": "字体",
    "font_size": "字号",
    "font_name": "自定义字体",
    "align": "水平对齐",
    "align_y": "垂直对齐",
    "max_lines": "最大行数",
    "ellipsis": "超出省略",
    "line_height": "行高",
    "template": "模板",
    "style": "样式",
    "width": "宽度",
    "margin_x": "水平外边距",
    "inset_x": "左右缩进",
    "separator_width": "分隔线宽度",
    "variant": "变体",
    "title": "标题文字",
    "icon": "图标",
    "limit": "数量上限",
    "show_divider": "显示分隔线",
    "show_note_divider": "显示备注分隔线",
    "show_answer_divider": "显示答案分隔线",
    "show_antidote_divider": "显示建议分隔线",
    "show_event_date": "显示事件日期",
    "show_tip_divider": "显示贴士分隔线",
    "divider_style": "分隔线样式",
    "divider_width": "分隔线宽度",
    "divider_inset_x": "分隔线缩进",
    "divider_margin_x": "分隔线外边距",
    "sections": "段落列表",
    "separator_style": "分隔线样式",
}

_PROP_PREFIX_ZH: dict[str, str] = {
    "title": "标题",
    "subtitle": "副标题",
    "meta": "元信息",
    "body": "正文",
    "quote": "引文",
    "word": "词条",
    "source": "来源",
    "author": "作者",
    "hero": "主体",
    "note": "备注",
    "greeting": "称呼",
    "closing": "落款",
    "postscript": "附言",
    "phonetic": "注音",
    "definition": "释义",
    "example": "例句",
    "hint": "提示",
    "answer": "答案",
    "question": "问题",
    "category": "分类",
    "antidote": "建议",
    "message": "寄语",
    "event": "事件",
    "events": "事件列表",
    "days": "天数",
    "lines": "诗行",
    "line": "单行",
    "tip": "小贴士",
    "section": "段落",
    "sections": "段落列表",
    "exercise": "项目",
    "season": "时令",
    "header": "头部",
    "footer": "底部",
    "compact": "紧凑",
    "book": "书籍",
    "desc": "描述",
    "duration": "时长",
    "separator": "分隔线",
}

_PROP_SUFFIX_ZH: dict[str, str] = {
    "field": "字段",
    "font": "字体",
    "font_name": "自定义字体",
    "font_size": "字号",
    "align": "对齐",
    "align_y": "纵向对齐",
    "max_lines": "最大行数",
    "template": "模板",
    "inset_x": "缩进",
    "gap": "间距",
    "width": "宽度",
    "limit": "上限",
    "style": "样式",
    "margin_x": "外边距",
    "label": "标签",
}


def _humanize_prop_name_zh(name: str) -> str:
    if name in _PROP_LABEL_ZH:
        return _PROP_LABEL_ZH[name]
    parts = name.split("_")
    prefix = parts[0]
    prefix_zh = _PROP_PREFIX_ZH.get(prefix)
    if prefix_zh:
        rest = "_".join(parts[1:])
        if rest in _PROP_LABEL_ZH:
            return f"{prefix_zh}{_PROP_LABEL_ZH[rest]}"
        if rest in _PROP_SUFFIX_ZH:
            return f"{prefix_zh}{_PROP_SUFFIX_ZH[rest]}"
        for suf_key, suf_zh in _PROP_SUFFIX_ZH.items():
            if rest.endswith(suf_key):
                mid = rest[: -len(suf_key)].rstrip("_")
                mid_zh = _PROP_PREFIX_ZH.get(mid, "")
                return f"{prefix_zh}{mid_zh}{suf_zh}"
    for suf_key, suf_zh in sorted(_PROP_SUFFIX_ZH.items(), key=lambda x: -len(x[0])):
        if name.endswith("_" + suf_key):
            pre = name[: -(len(suf_key) + 1)]
            pre_zh = _PROP_PREFIX_ZH.get(pre, "")
            if pre_zh:
                return f"{pre_zh}{suf_zh}"
    return ""


def _prop_value_kind(name: str, field_props: tuple[str, ...] = ()) -> str:
    if name in field_props or name == "field" or name.endswith("_field"):
        return "template" if name == "template" or name.endswith("_template") else "field"
    if name == "template" or name.endswith("_template"):
        return "template"
    if name == "font" or name.endswith("_font"):
        return "font"
    if name == "font_name" or name.endswith("_font_name"):
        return "font_name"
    return "plain"


def _prop_input_type(name: str, value_kind: str) -> str:
    if name.startswith("show_") or name in {"ellipsis"}:
        return "boolean"
    if value_kind == "font":
        return "select"
    if value_kind == "template":
        return "textarea"
    if (
        name.endswith("_size")
        or name.endswith("_gap")
        or name.endswith("_width")
        or name.endswith("_height")
        or name.endswith("_limit")
        or name.endswith("_lines")
        or name.endswith("_padding")
        or name in {"gap", "grow", "inset_x", "padding_x", "padding_y", "row_gap", "divider_inset_x", "divider_margin_x", "quote_inset_x", "word_inset_x", "hero_inset_x", "top_gap"}
    ):
        return "number"
    if name == "justify" or name.endswith("_align") or name.endswith("_align_y") or name.endswith("_style") or name == "variant":
        return "select"
    return "string"


def _prop_options(name: str, value_kind: str) -> list[str] | None:
    if value_kind == "font":
        return list(_PUBLIC_FONT_OPTIONS)
    if name in _PUBLIC_SELECT_OPTIONS:
        return list(_PUBLIC_SELECT_OPTIONS[name])
    if name.endswith("_align"):
        return list(_PUBLIC_SELECT_OPTIONS["align"])
    if name.endswith("_align_y"):
        return list(_PUBLIC_SELECT_OPTIONS["align_y"])
    if name.endswith("_style"):
        return list(_PUBLIC_SELECT_OPTIONS["style"])
    return None


def _build_prop_meta(
    prop_name: str,
    *,
    required_props: tuple[str, ...] = (),
    field_props: tuple[str, ...] = (),
    defaults: dict[str, Any] | None = None,
) -> dict[str, Any]:
    value_kind = _prop_value_kind(prop_name, field_props)
    input_type = _prop_input_type(prop_name, value_kind)
    meta: dict[str, Any] = {
        "name": prop_name,
        "label": _humanize_prop_name(prop_name),
        "type": input_type,
        "value_kind": value_kind,
        "required": prop_name in required_props,
    }
    zh = _humanize_prop_name_zh(prop_name)
    if zh:
        meta["label_zh"] = zh
    if value_kind == "font_name":
        meta["hidden"] = True
    default_value = (defaults or {}).get(prop_name)
    if default_value is not None:
        meta["default"] = default_value
    options = _prop_options(prop_name, value_kind)
    if options:
        meta["options"] = options
    return meta


def _build_fragment_catalog_item(name: str) -> dict[str, Any]:
    spec = FRAGMENT_REGISTRY[name]
    meta = _PUBLIC_FRAGMENT_META[name]
    return {
        "name": name,
        "label": meta["label"],
        "label_zh": meta["label_zh"],
        "description": meta["description"],
        "description_zh": meta["description_zh"],
        "props": [
            _build_prop_meta(
                prop_name,
                required_props=spec.required_props,
                field_props=spec.field_props,
                defaults=spec.defaults,
            )
            for prop_name in spec.props
        ],
    }


def _build_preset_catalog_item(name: str) -> dict[str, Any]:
    spec = PRESET_REGISTRY[name]
    meta = _PUBLIC_PRESET_META[name]
    inferred_field_props = tuple(p for p in spec.props if p == "field" or p.endswith("_field"))
    return {
        "name": name,
        "label": meta["label"],
        "label_zh": meta["label_zh"],
        "description": meta["description"],
        "description_zh": meta["description_zh"],
        "props": [
            _build_prop_meta(
                prop_name,
                required_props=spec.required_props,
                field_props=inferred_field_props,
                defaults=spec.defaults,
            )
            for prop_name in spec.props
        ],
    }


def get_public_layout_dsl_catalog() -> dict[str, Any]:
    return {
        "version": 1,
        "fonts": list(_PUBLIC_FONT_OPTIONS),
        "fragment_stack": {
            "props": [
                _build_prop_meta(prop_name, defaults=_FRAGMENT_STACK_DEFAULTS)
                for prop_name in _FRAGMENT_STACK_PROPS
            ]
        },
        "fragments": [_build_fragment_catalog_item(name) for name in _PUBLIC_FRAGMENT_ORDER],
        "presets": [_build_preset_catalog_item(name) for name in _PUBLIC_PRESET_ORDER],
    }


def get_layout_dsl_catalog() -> dict[str, Any]:
    return {
        "primitives": {
            name: {
                "props": list(spec.props),
                "field_props": list(spec.field_props),
            }
            for name, spec in PRIMITIVE_REGISTRY.items()
        },
        "fragments": {
            name: {
                "props": list(spec.props),
                "required_props": list(spec.required_props),
                "field_props": list(spec.field_props),
            }
            for name, spec in FRAGMENT_REGISTRY.items()
        },
        "presets": {
            name: {
                "props": list(spec.props),
                "required_props": list(spec.required_props),
            }
            for name, spec in PRESET_REGISTRY.items()
        },
    }


def _build_fragment_stack(layout: dict[str, Any]) -> dict[str, Any]:
    fragments = layout.get("fragments")
    if not isinstance(fragments, list) or not fragments:
        raise LayoutDslError("fragments must be a non-empty array")
    stack_props = layout.get("fragment_stack", {})
    if stack_props is None:
        stack_props = {}
    if not isinstance(stack_props, dict):
        raise LayoutDslError("fragment_stack must be an object")
    children: list[dict[str, Any]] = []
    for entry in fragments:
        if not isinstance(entry, dict):
            raise LayoutDslError("fragment entries must be objects")
        fragment_name = str(entry.get("fragment", "")).strip()
        if not fragment_name:
            raise LayoutDslError("fragment entry missing fragment")
        if "props" in entry:
            raw_props = entry.get("props")
        else:
            raw_props = {key: value for key, value in entry.items() if key != "fragment"}
        children.append(_build_fragment_instance(fragment_name, raw_props))
    return _compact(
        {
            "type": "column",
            "padding_x": stack_props.get("padding_x", 18),
            "padding_y": stack_props.get("padding_y"),
            "justify": stack_props.get("justify", "center"),
            "gap": stack_props.get("gap", 6),
            "children": children,
        }
    )


def validate_layout_dsl(layout: dict[str, Any] | None, *, allow_raw_body: bool = True) -> None:
    if not isinstance(layout, dict):
        raise LayoutDslError("layout must be an object")
    if layout.get("layout_engine") != "component_tree":
        return
    has_raw_body = isinstance(layout.get("body"), dict) and bool(layout.get("body", {}).get("type"))
    has_preset = layout.get("body_preset") is not None
    has_fragments = layout.get("fragments") is not None
    if not any((has_raw_body, has_preset, has_fragments)):
        raise LayoutDslError("component_tree layout requires body, body_preset, or fragments")
    if sum(int(flag) for flag in (has_raw_body, has_preset, has_fragments)) > 1:
        raise LayoutDslError("component_tree layout must choose only one of body, body_preset, or fragments")
    if has_raw_body and not allow_raw_body:
        raise LayoutDslError("raw component_tree body is not allowed here")
    if has_preset:
        preset_name = str(layout.get("body_preset", "")).strip()
        if not preset_name:
            raise LayoutDslError("body_preset must be a non-empty string")
        spec = PRESET_REGISTRY.get(preset_name)
        if spec is None:
            raise LayoutDslError(f"Unknown body_preset: {preset_name}")
        props = _normalize_props(layout.get("preset_props", {}), f"preset '{preset_name}'", spec.defaults)
        _require_props(f"preset '{preset_name}'", props, spec.required_props)
    if has_fragments:
        _build_fragment_stack(layout)


def compile_layout_dsl(layout: dict[str, Any] | None, *, allow_raw_body: bool = True) -> dict[str, Any]:
    if not isinstance(layout, dict):
        return {}
    expanded = deepcopy(layout)
    if expanded.get("layout_engine") != "component_tree":
        return expanded
    validate_layout_dsl(expanded, allow_raw_body=allow_raw_body)
    preset_name = expanded.get("body_preset")
    if preset_name:
        spec = PRESET_REGISTRY[str(preset_name)]
        props = _normalize_props(expanded.get("preset_props", {}), f"preset '{preset_name}'", spec.defaults)
        expanded["body"] = spec.builder(props)
        return expanded
    if expanded.get("fragments") is not None:
        expanded["body"] = _build_fragment_stack(expanded)
        return expanded
    return expanded


def expand_layout_presets(layout: dict[str, Any] | None) -> dict[str, Any]:
    return compile_layout_dsl(layout)
