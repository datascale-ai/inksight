from __future__ import annotations

from fastapi import APIRouter, Query

from core.context import LocationSearchScope, search_locations

router = APIRouter(tags=["locations"])


@router.get("/locations/search")
async def location_search(
    q: str = Query(..., min_length=1, max_length=60, description="地点关键词"),
    limit: int = Query(default=8, ge=1, le=10, description="最多返回数量"),
    scope: LocationSearchScope = Query(default="auto", description="搜索范围：auto/cn/global"),
):
    query = q.strip()
    if not query:
        return {"query": "", "items": []}
    items = await search_locations(query, limit=limit, scope=scope)
    return {"query": query, "scope": scope, "items": items}
