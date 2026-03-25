from __future__ import annotations

import asyncio
import base64
import io
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from api.shared import logger
from core.auth import require_user
from core.config import SCREEN_HEIGHT, SCREEN_WIDTH
from core.config_store import get_main_db
from core.context import get_date_context, get_weather
from core.mode_registry import CUSTOM_JSON_DIR, _validate_mode_def, get_registry
from core.config_store import save_custom_mode, get_custom_mode as get_user_custom_mode_from_db

router = APIRouter(tags=["discover"])


@router.get("/discover/modes")
async def list_shared_modes(
    category: Optional[str] = Query(None, description="分类过滤"),
    page: int = Query(1, ge=1, description="页码"),
    limit: int = Query(20, ge=1, le=100, description="每页数量"),
):
    """获取广场模式列表（公开接口，无需认证）"""
    db = await get_main_db()
    offset = (page - 1) * limit

    # 构建查询
    query = """
        SELECT 
            sm.id,
            sm.mode_id,
            sm.name,
            sm.description,
            sm.category,
            sm.thumbnail_url,
            sm.created_at,
            u.username as author_username
        FROM shared_modes sm
        INNER JOIN users u ON sm.author_id = u.id
        WHERE sm.is_active = 1
    """
    params = []

    if category:
        query += " AND sm.category = ?"
        params.append(category)

    query += " ORDER BY sm.created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()

    # 获取总数
    count_query = "SELECT COUNT(*) FROM shared_modes sm WHERE sm.is_active = 1"
    count_params = []
    if category:
        count_query += " AND sm.category = ?"
        count_params.append(category)

    cursor = await db.execute(count_query, count_params)
    total_row = await cursor.fetchone()
    total = total_row[0] if total_row else 0

    modes = [
        {
            "id": row[0],
            "mode_id": row[1],
            "name": row[2],
            "description": row[3],
            "category": row[4],
            "thumbnail_url": row[5],
            "created_at": row[6],
            "author": f"@{row[7]}" if row[7] else "@unknown",
        }
        for row in rows
    ]

    return {
        "modes": modes,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": (total + limit - 1) // limit if total > 0 else 0,
        },
    }


@router.post("/discover/modes/publish")
async def publish_mode(
    body: dict,
    user_id: int = Depends(require_user),
):
    """发布模式到广场（需要认证）"""
    source_custom_mode_id = body.get("source_custom_mode_id", "").strip().upper()
    name = body.get("name", "").strip()
    description = body.get("description", "").strip()
    category = body.get("category", "").strip()
    mac = body.get("mac", "").strip().upper()
    thumbnail_base64 = body.get("thumbnail_base64")
    colors = int(body.get("colors", 2))

    # 参数验证
    if not source_custom_mode_id:
        return JSONResponse({"error": "source_custom_mode_id 不能为空"}, status_code=400)
    if not name:
        return JSONResponse({"error": "name 不能为空"}, status_code=400)
    if not category:
        return JSONResponse({"error": "category 不能为空"}, status_code=400)
    if not mac:
        return JSONResponse({"error": "mac 不能为空"}, status_code=400)

    # 检查重名
    db = await get_main_db()
    cursor = await db.execute(
        "SELECT id FROM shared_modes WHERE name = ? AND is_active = 1",
        (name,),
    )
    existing = await cursor.fetchone()
    if existing:
        return JSONResponse(
            {"error": f"模式名称 '{name}' 已存在，请使用其他名称"},
            status_code=409  # Conflict
        )

    # 验证设备是否属于该用户
    from core.config_store import has_active_membership
    if not await has_active_membership(mac, user_id):
        return JSONResponse(
            {"error": "设备不存在或无权访问"},
            status_code=403
        )

    # 查找模式定义（优先从数据库，回退到注册表）
    mode_def = None
    
    # 首先尝试从数据库获取用户的自定义模式（按设备）
    user_mode_data = await get_user_custom_mode_from_db(user_id, source_custom_mode_id, mac)
    if user_mode_data:
        mode_def = user_mode_data["definition"]
    else:
        # 回退到注册表（可能是文件系统或已加载的模式）
        registry = get_registry()
        mode = registry.get_json_mode(source_custom_mode_id, mac)
        if not mode:
            return JSONResponse(
                {"error": f"自定义模式 {source_custom_mode_id} 不存在"},
                status_code=404,
            )
        if mode.info.source != "custom":
            return JSONResponse(
                {"error": f"模式 {source_custom_mode_id} 不是自定义模式"},
                status_code=400,
            )
        mode_def = mode.definition

    # 获取完整的模式定义 JSON
    config_json = json.dumps(mode_def, ensure_ascii=False)

    # 生成预览缩略图（必须成功）
    try:
        from core.json_content import generate_json_mode_content
        from core.json_renderer import render_json_mode
        from core.config_store import get_user_llm_config

        # 获取用户的 LLM 配置（用于生成缩略图）
        user_llm_cfg = await get_user_llm_config(user_id)
        llm_provider = ""
        llm_model = ""
        api_key = ""
        llm_base_url = ""
        image_provider = ""
        image_model = ""
        image_api_key = ""
        
        if user_llm_cfg:
            llm_access_mode = (user_llm_cfg.get("llm_access_mode") or "preset").strip().lower()
            llm_provider = (user_llm_cfg.get("provider") or "").strip()
            llm_model = (user_llm_cfg.get("model") or "").strip()
            api_key_plain = (user_llm_cfg.get("api_key") or "").strip()
            if api_key_plain:
                api_key = api_key_plain
            if llm_access_mode == "custom_openai":
                llm_base_url = (user_llm_cfg.get("base_url") or "").strip()
            image_provider = (user_llm_cfg.get("image_provider") or "").strip()
            image_model = (user_llm_cfg.get("image_model") or "").strip()
            image_api_key_plain = (user_llm_cfg.get("image_api_key") or "").strip()
            if image_api_key_plain:
                image_api_key = image_api_key_plain

        # 获取上下文数据
        date_ctx = await get_date_context()
        weather = await get_weather()

        # 生成内容（对于 image_gen 类型，需要等待图片生成完成）
        content_type = mode_def.get("content", {}).get("type", "static")
        max_retries = 10  # 最多重试 10 次
        retry_interval = 2  # 每次重试间隔 2 秒
        
        content = None
        if content_type == "image_gen":
            # 对于图片生成类型，需要轮询直到生成完成
            for attempt in range(max_retries):
                content = await generate_json_mode_content(
                    mode_def,
                    date_ctx=date_ctx,
                    date_str=date_ctx["date_str"],
                    weather_str=weather["weather_str"],
                    screen_w=SCREEN_WIDTH,
                    screen_h=SCREEN_HEIGHT,
                    llm_provider=llm_provider,
                    llm_model=llm_model,
                    llm_base_url=(llm_base_url or None),
                    api_key=api_key,
                    image_provider=image_provider,
                    image_model=image_model,
                    image_api_key=image_api_key,
                )
                
                image_url = content.get("image_url", "")
                description = content.get("description", "")
                
                # 检查是否还在生成中
                is_generating = (
                    description == "图像生成中" or 
                    description == "Image generating..." or
                    not image_url or 
                    not image_url.strip() or
                    not (image_url.startswith("http://") or image_url.startswith("https://"))
                )
                
                if not is_generating:
                    # 图片已生成完成
                    logger.info(f"[DISCOVER] Image generated successfully after {attempt + 1} attempt(s)")
                    break
                
                # 如果还在生成中，等待后重试
                if attempt < max_retries - 1:
                    logger.info(f"[DISCOVER] Image still generating, retrying in {retry_interval}s (attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(retry_interval)
                else:
                    # 最后一次重试失败
                    return JSONResponse(
                        {"error": "图片生成超时，无法发布。请检查图片生成 API 配置是否正确，或稍后重试。"},
                        status_code=408  # Request Timeout
                    )
        else:
            # 非图片生成类型，直接生成内容
            content = await generate_json_mode_content(
                mode_def,
                date_ctx=date_ctx,
                date_str=date_ctx["date_str"],
                weather_str=weather["weather_str"],
                screen_w=SCREEN_WIDTH,
                screen_h=SCREEN_HEIGHT,
                llm_provider=llm_provider,
                llm_model=llm_model,
                llm_base_url=(llm_base_url or None),
                api_key=api_key,
                image_provider=image_provider,
                image_model=image_model,
                image_api_key=image_api_key,
            )

        # 渲染图片
        img = render_json_mode(
            mode_def,
            content,
            date_str=date_ctx["date_str"],
            weather_str=weather["weather_str"],
            battery_pct=100.0,
            screen_w=SCREEN_WIDTH,
            screen_h=SCREEN_HEIGHT,
            colors=colors,
        )

        # 转换为 base64
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        png_bytes = buf.getvalue()
        thumbnail_base64_str = base64.b64encode(png_bytes).decode("ascii")
        thumbnail_url = f"data:image/png;base64,{thumbnail_base64_str}"

        logger.info(f"[DISCOVER] Generated thumbnail for mode {source_custom_mode_id}")
    except Exception as e:
        logger.error(f"[DISCOVER] Failed to generate thumbnail for {source_custom_mode_id}: {e}", exc_info=True)
        return JSONResponse(
            {"error": f"预览图片生成失败: {str(e)}"},
            status_code=500
        )

    # 插入到数据库（再次检查重名，防止并发问题）
    db = await get_main_db()
    now = datetime.now().isoformat()
    try:
        cursor = await db.execute(
            """
            INSERT INTO shared_modes 
            (mode_id, name, description, category, author_id, config_json, thumbnail_url, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (source_custom_mode_id, name, description, category, user_id, config_json, thumbnail_url, 1, now),
        )
        await db.commit()
    except Exception as e:
        await db.rollback()
        error_msg = str(e).lower()
        if "unique" in error_msg or "constraint" in error_msg:
            return JSONResponse(
                {"error": f"模式名称 '{name}' 已存在，请使用其他名称"},
                status_code=409  # Conflict
            )
        logger.error(f"[DISCOVER] Failed to insert shared mode: {e}", exc_info=True)
        return JSONResponse(
            {"error": "发布失败，请稍后重试"},
            status_code=500
        )
    shared_mode_id = cursor.lastrowid

    logger.info(f"[DISCOVER] User {user_id} published mode {source_custom_mode_id} as shared mode {shared_mode_id}")
    return {"ok": True, "id": shared_mode_id}


@router.post("/discover/modes/{mode_id}/install")
async def install_shared_mode(
    mode_id: int,
    body: dict,
    user_id: int = Depends(require_user),
):
    """安装共享模式到用户本地设备（需要认证）"""
    mac = body.get("mac", "").strip().upper()
    if not mac:
        return JSONResponse({"error": "mac 不能为空"}, status_code=400)

    # 验证设备是否属于该用户
    from core.config_store import has_active_membership
    if not await has_active_membership(mac, user_id):
        return JSONResponse(
            {"error": "设备不存在或无权访问"},
            status_code=403
        )

    db = await get_main_db()

    # 查询共享模式
    cursor = await db.execute(
        """
        SELECT config_json, mode_id, name
        FROM shared_modes
        WHERE id = ? AND is_active = 1
        """,
        (mode_id,),
    )
    row = await cursor.fetchone()
    if not row:
        return JSONResponse({"error": "共享模式不存在或已下架"}, status_code=404)

    config_json_str, original_mode_id, original_name = row

    # 解析配置 JSON
    try:
        mode_def = json.loads(config_json_str)
    except json.JSONDecodeError:
        return JSONResponse({"error": "模式配置格式错误"}, status_code=500)

    # 生成新的模式 ID（避免冲突）
    new_mode_id = f"CUSTOM_{uuid.uuid4().hex[:8].upper()}"
    mode_def["mode_id"] = new_mode_id

    # 可选：更新显示名称，添加来源标识
    if "display_name" in mode_def:
        mode_def["display_name"] = f"{original_name} (来自广场)"

    # 验证模式定义
    if not _validate_mode_def(mode_def):
        return JSONResponse({"error": "模式定义验证失败"}, status_code=400)

    # 检查是否与内置模式冲突
    registry = get_registry()
    if registry.is_builtin(new_mode_id):
        return JSONResponse({"error": "模式 ID 冲突"}, status_code=409)

    # 保存到数据库（用户专属，指定设备）
    success = await save_custom_mode(user_id, new_mode_id, mode_def, mac)
    if not success:
        return JSONResponse({"error": "保存模式失败"}, status_code=500)

    # 加载到注册表以便立即使用
    registry.unregister_custom(new_mode_id, mac)
    loaded = registry.load_custom_mode_from_dict(new_mode_id, mode_def, source="custom", mac=mac)
    if not loaded:
        # Rollback database entry
        from core.config_store import delete_custom_mode
        await delete_custom_mode(user_id, new_mode_id, mac)
        return JSONResponse({"error": "模式加载失败"}, status_code=500)

    logger.info(f"[DISCOVER] User {user_id} installed shared mode {mode_id} as {new_mode_id} on device {mac}")
    return {"ok": True, "custom_mode_id": new_mode_id}
