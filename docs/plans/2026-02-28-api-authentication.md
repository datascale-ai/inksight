# API 鉴权实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**目标：** 为 API 添加两层鉴权 —— 设备 Token 校验（保护设备端点）+ 管理员 Token（保护管理端点），复用已有但未启用的 Token 基础设施。

**架构：** 新建 `backend/core/auth.py` 模块，使用 FastAPI `Depends()` 依赖注入实现设备 Token 和管理员 Token 校验。设备 Token 复用已有的 `X-Device-Token` 请求头 + `validate_device_token()` 函数。管理员 Token 通过 `ADMIN_TOKEN` 环境变量配置，使用 `Authorization: Bearer <token>` 请求头校验。未认证请求返回 401/403。`ADMIN_TOKEN` 未设置时跳过管理员鉴权，方便本地开发。

**技术栈：** Python FastAPI (Depends, Header, HTTPException)、已有的 `config_store.py` Token 函数、已有的固件 `X-Device-Token` 请求头。

---

## 现状梳理

**已实现但未启用：**
- `generate_device_token()` — `backend/core/config_store.py:323-338`
- `validate_device_token()` — `backend/core/config_store.py:341-352`
- 固件发送 `X-Device-Token` 请求头 — `firmware/src/network.cpp:91-93`
- MAC 地址校验正则 `_MAC_RE` — `backend/core/schemas.py:14`
- 数据库字段 `device_state.auth_token` 已存在

**缺失部分：**
- 没有任何端点调用 `validate_device_token()`
- 没有管理员鉴权机制
- 路径参数中的 MAC 地址未校验（仅在 `ConfigRequest` 请求体中校验）
- 没有 Token 分发端点（设备获取 Token 并存储）

---

### Task 1：创建 `backend/core/auth.py` — 鉴权依赖

**文件：**
- 新建：`backend/core/auth.py`
- 新建：`backend/tests/test_auth.py`

**Step 1：编写失败的测试**

创建 `backend/tests/test_auth.py`：

```python
"""API 鉴权依赖的单元测试。"""
import os
import pytest

from core.auth import validate_mac_param, require_device_token, require_admin


class TestValidateMacParam:
    def test_valid_mac(self):
        result = validate_mac_param("AA:BB:CC:DD:EE:FF")
        assert result == "AA:BB:CC:DD:EE:FF"

    def test_valid_mac_lowercase(self):
        result = validate_mac_param("aa:bb:cc:dd:ee:ff")
        assert result == "AA:BB:CC:DD:EE:FF"

    def test_invalid_mac(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            validate_mac_param("not-a-mac")
        assert exc_info.value.status_code == 400

    def test_empty_mac(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            validate_mac_param("")
        assert exc_info.value.status_code == 400


class TestRequireAdmin:
    def test_no_admin_token_configured_allows_access(self, monkeypatch):
        monkeypatch.delenv("ADMIN_TOKEN", raising=False)
        # 未配置 ADMIN_TOKEN 时应放行
        require_admin(authorization=None)

    def test_valid_admin_token(self, monkeypatch):
        monkeypatch.setenv("ADMIN_TOKEN", "secret123")
        require_admin(authorization="Bearer secret123")

    def test_invalid_admin_token(self, monkeypatch):
        monkeypatch.setenv("ADMIN_TOKEN", "secret123")
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            require_admin(authorization="Bearer wrong")
        assert exc_info.value.status_code == 403

    def test_missing_admin_token_when_required(self, monkeypatch):
        monkeypatch.setenv("ADMIN_TOKEN", "secret123")
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            require_admin(authorization=None)
        assert exc_info.value.status_code == 403

    def test_malformed_auth_header(self, monkeypatch):
        monkeypatch.setenv("ADMIN_TOKEN", "secret123")
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            require_admin(authorization="Basic secret123")
        assert exc_info.value.status_code == 403


class TestRequireDeviceToken:
    @pytest.mark.asyncio
    async def test_no_token_stored_allows_access(self, monkeypatch):
        """新设备无 Token 时应放行（宽限期）。"""
        from core import config_store
        async def _fake_validate(mac, token):
            return False
        async def _fake_get_state(mac):
            return None  # 无设备状态 = 新设备
        monkeypatch.setattr(config_store, "validate_device_token", _fake_validate)
        monkeypatch.setattr(config_store, "get_device_state", _fake_get_state)

        result = await require_device_token(mac="AA:BB:CC:DD:EE:FF", x_device_token=None)
        assert result is True

    @pytest.mark.asyncio
    async def test_valid_token(self, monkeypatch):
        from core import config_store
        async def _fake_validate(mac, token):
            return True
        monkeypatch.setattr(config_store, "validate_device_token", _fake_validate)

        result = await require_device_token(mac="AA:BB:CC:DD:EE:FF", x_device_token="valid-token")
        assert result is True

    @pytest.mark.asyncio
    async def test_invalid_token_when_device_has_token(self, monkeypatch):
        from core import config_store
        async def _fake_validate(mac, token):
            return False
        async def _fake_get_state(mac):
            return {"auth_token": "real-token"}  # 设备已有 Token
        monkeypatch.setattr(config_store, "validate_device_token", _fake_validate)
        monkeypatch.setattr(config_store, "get_device_state", _fake_get_state)

        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await require_device_token(mac="AA:BB:CC:DD:EE:FF", x_device_token="wrong-token")
        assert exc_info.value.status_code == 401
```

**Step 2：运行测试确认失败**

运行：`cd backend && python -m pytest tests/test_auth.py -v`
预期：FAIL — `ModuleNotFoundError: No module named 'core.auth'`

**Step 3：实现 `backend/core/auth.py`**

```python
"""
FastAPI 鉴权依赖模块。

两层鉴权：
1. Device Token — 校验 X-Device-Token 请求头，保护设备相关端点
2. Admin Token — 校验 Authorization Bearer token，保护管理端点
"""
from __future__ import annotations

import hmac
import logging
import os
import re
from typing import Optional

from fastapi import Header, HTTPException

from .config_store import validate_device_token, get_device_state

logger = logging.getLogger(__name__)

_MAC_RE = re.compile(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")


def validate_mac_param(mac: str) -> str:
    """校验并规范化 MAC 地址路径参数。

    返回大写 MAC，格式无效时抛出 400。
    """
    if not mac or not _MAC_RE.match(mac):
        raise HTTPException(status_code=400, detail="MAC 地址格式无效，应为 AA:BB:CC:DD:EE:FF")
    return mac.upper()


def require_admin(
    authorization: Optional[str] = Header(default=None),
) -> None:
    """FastAPI 依赖：管理端点鉴权。

    未设置 ADMIN_TOKEN 环境变量时跳过鉴权（本地开发模式）。
    """
    admin_token = os.environ.get("ADMIN_TOKEN")
    if not admin_token:
        return  # 未配置管理 Token — 开放访问

    if not authorization:
        raise HTTPException(status_code=403, detail="需要管理员认证")

    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0] != "Bearer":
        raise HTTPException(status_code=403, detail="认证格式无效，应为: Bearer <token>")

    if not hmac.compare_digest(parts[1], admin_token):
        raise HTTPException(status_code=403, detail="管理员 Token 无效")


async def require_device_token(
    mac: str,
    x_device_token: Optional[str] = Header(default=None),
) -> bool:
    """FastAPI 依赖：校验设备 Token。

    宽限期逻辑：
    - 设备尚未存储 Token（新设备）→ 放行
    - 设备已有 Token → 请求必须携带匹配的 Token
    """
    if x_device_token:
        valid = await validate_device_token(mac, x_device_token)
        if valid:
            return True

    # 检查设备是否已有 Token
    state = await get_device_state(mac)
    if state and state.get("auth_token"):
        # 设备有 Token 但请求未提供有效 Token
        logger.warning(f"[AUTH] 设备 Token 校验失败: {mac}")
        raise HTTPException(status_code=401, detail="设备 Token 无效或缺失")

    # 新设备无 Token — 放行（宽限期）
    return True
```

**Step 4：运行测试确认通过**

运行：`cd backend && python -m pytest tests/test_auth.py -v`
预期：全部 10 个测试 PASS

**Step 5：提交**

```bash
git add backend/core/auth.py backend/tests/test_auth.py
git commit -m "feat(auth): 添加设备 Token 和管理员 Token 的 FastAPI 鉴权依赖"
```

---

### Task 2：添加 Token 分发端点

**文件：**
- 修改：`backend/api/index.py` — 新增 `POST /api/device/{mac}/token` 端点
- 修改：`backend/tests/test_auth.py` — 新增分发测试

**Step 1：编写失败的测试**

追加到 `backend/tests/test_auth.py`：

```python
class TestTokenProvisioning:
    @pytest.mark.asyncio
    async def test_provision_new_device(self, monkeypatch):
        """新设备首次请求时获得 Token。"""
        from api import index
        from core import config_store

        generated_token = "test-token-abc"
        async def _fake_get_state(mac):
            return None
        async def _fake_generate(mac):
            return generated_token
        monkeypatch.setattr(config_store, "get_device_state", _fake_get_state)
        monkeypatch.setattr(config_store, "generate_device_token", _fake_generate)

        resp = await index.provision_device_token("AA:BB:CC:DD:EE:FF")
        assert resp["token"] == generated_token

    @pytest.mark.asyncio
    async def test_provision_existing_device_returns_existing(self, monkeypatch):
        """已有 Token 的设备返回已有 Token。"""
        from api import index
        from core import config_store

        async def _fake_get_state(mac):
            return {"auth_token": "existing-token"}
        monkeypatch.setattr(config_store, "get_device_state", _fake_get_state)

        resp = await index.provision_device_token("AA:BB:CC:DD:EE:FF")
        assert resp["token"] == "existing-token"
```

**Step 2：运行测试确认失败**

运行：`cd backend && python -m pytest tests/test_auth.py::TestTokenProvisioning -v`
预期：FAIL — `AttributeError: module 'api.index' has no attribute 'provision_device_token'`

**Step 3：在 `index.py` 中添加分发端点**

在已有的 `/api/device/{mac}/habit/status` 端点之后（约第 1001 行附近）添加：

```python
@app.post("/api/device/{mac}/token")
async def provision_device_token(mac: str):
    """分发或获取设备 Token。

    - 新设备（无状态）：生成并返回新 Token
    - 已有设备：返回已有 Token
    """
    state = await get_device_state(mac)
    if state and state.get("auth_token"):
        return {"token": state["auth_token"], "new": False}

    token = await generate_device_token(mac)
    logger.info(f"[AUTH] 为设备 {mac} 分发了新 Token")
    return {"token": token, "new": True}
```

**Step 4：运行测试确认通过**

运行：`cd backend && python -m pytest tests/test_auth.py::TestTokenProvisioning -v`
预期：PASS

**Step 5：提交**

```bash
git add backend/api/index.py backend/tests/test_auth.py
git commit -m "feat(auth): 添加设备 Token 分发端点"
```

---

### Task 3：为设备端点接入 Token 校验

**文件：**
- 修改：`backend/api/index.py` — 在设备端点中调用 `require_device_token`

**Step 1：编写集成测试**

追加到 `backend/tests/test_auth.py`：

```python
class TestEndpointProtection:
    """验证设备已有 Token 时拒绝无效请求。"""

    @pytest.mark.asyncio
    async def test_device_state_rejects_bad_token(self, monkeypatch):
        from core import config_store
        from fastapi import HTTPException

        async def _fake_validate(mac, token):
            return False
        async def _fake_get_state(mac):
            return {"auth_token": "real-token", "last_persona": "STOIC"}
        monkeypatch.setattr(config_store, "validate_device_token", _fake_validate)
        monkeypatch.setattr(config_store, "get_device_state", _fake_get_state)

        with pytest.raises(HTTPException) as exc_info:
            from core.auth import require_device_token
            await require_device_token(mac="AA:BB:CC:DD:EE:FF", x_device_token="wrong")
        assert exc_info.value.status_code == 401
```

**Step 2：运行测试确认通过（依赖逻辑已就绪）**

运行：`cd backend && python -m pytest tests/test_auth.py::TestEndpointProtection -v`
预期：PASS

**Step 3：将鉴权依赖接入端点**

修改 `backend/api/index.py` — 更新导入和端点签名。

更新顶部导入（第 15 行附近）：

```python
from fastapi import FastAPI, Query, Request, Response, Depends, Header
```

新增 auth 模块导入（第 55 行之后）：

```python
from core.auth import validate_mac_param, require_device_token, require_admin
```

然后修改端点签名，添加 `x_device_token` 参数并在函数体开头调用鉴权。

**设备端点 — 添加 Token 校验：**

```python
# /api/render — 第 469 行
@app.get("/api/render")
async def render(
    v: float = Query(default=3.3, description="Battery voltage"),
    mac: Optional[str] = Query(default=None, description="Device MAC address"),
    persona: Optional[str] = Query(default=None, description="Force persona"),
    rssi: Optional[int] = Query(default=None, description="WiFi RSSI (dBm)"),
    w: int = Query(default=SCREEN_WIDTH, ge=100, le=1600),
    h: int = Query(default=SCREEN_HEIGHT, ge=100, le=1200),
    next_mode: Optional[int] = Query(default=None, alias="next"),
    x_device_token: Optional[str] = Header(default=None),
):
    # 仅在提供了 mac 时校验 Token
    if mac:
        await require_device_token(mac, x_device_token)
    # ... 后续逻辑不变
```

```python
# /api/device/{mac}/state — 第 928 行
@app.get("/api/device/{mac}/state")
async def device_state(mac: str, x_device_token: Optional[str] = Header(default=None)):
    await require_device_token(mac, x_device_token)
    # ... 后续逻辑不变
```

对以下所有设备端点应用相同模式：
- `POST /api/device/{mac}/refresh`（第 920 行）
- `GET /api/device/{mac}/state`（第 928 行）
- `POST /api/device/{mac}/switch`（第 937 行）
- `POST /api/device/{mac}/favorite`（第 949 行）
- `GET /api/device/{mac}/favorites`（第 964 行）
- `GET /api/device/{mac}/history`（第 974 行）
- `POST /api/device/{mac}/habit/check`（第 986 行）
- `GET /api/device/{mac}/habit/status`（第 997 行）
- `GET /api/config/{mac}`（第 606 行）
- `GET /api/config/{mac}/history`（第 614 行）
- `GET /api/stats/{mac}`（第 1013 行）
- `GET /api/stats/{mac}/renders`（第 1019 行）
- `GET /api/widget/{mac}`（第 516 行）
- `GET /api/device/{mac}/qr`（第 1033 行）
- `GET /api/device/{mac}/share`（第 1061 行）

**注意：** 以下端点不需要设备鉴权：
- `POST /api/device/{mac}/token` — Token 分发端点本身
- `GET /api/health` — 公开
- `GET /api/preview` — 预览控制台
- `GET /api/firmware/*` — 公开
- `GET /`、`/config`、`/dashboard`、`/editor` — 静态页面

**Step 4：运行全量测试确认无破坏**

运行：`cd backend && python -m pytest tests/ -v`
预期：所有已有测试仍 PASS（测试中未发送 Token 且设备无已存储 Token，宽限期放行）

**Step 5：提交**

```bash
git add backend/api/index.py
git commit -m "feat(auth): 为设备端点启用 Token 校验"
```

---

### Task 4：为管理端点接入管理员鉴权

**文件：**
- 修改：`backend/api/index.py` — 在管理端点添加 `Depends(require_admin)`

**Step 1：编写管理员鉴权测试**

追加到 `backend/tests/test_auth.py`：

```python
class TestAdminProtection:
    def test_admin_blocks_without_token(self, monkeypatch):
        monkeypatch.setenv("ADMIN_TOKEN", "admin-secret")
        from core.auth import require_admin
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            require_admin(authorization=None)
        assert exc_info.value.status_code == 403

    def test_admin_allows_with_correct_token(self, monkeypatch):
        monkeypatch.setenv("ADMIN_TOKEN", "admin-secret")
        from core.auth import require_admin
        require_admin(authorization="Bearer admin-secret")

    def test_admin_skips_when_not_configured(self, monkeypatch):
        monkeypatch.delenv("ADMIN_TOKEN", raising=False)
        from core.auth import require_admin
        require_admin(authorization=None)  # 不应抛出异常
```

**Step 2：运行测试确认通过**

运行：`cd backend && python -m pytest tests/test_auth.py::TestAdminProtection -v`
预期：PASS

**Step 3：在管理端点添加 `Depends(require_admin)`**

对以下端点添加 `admin_auth: None = Depends(require_admin)` 参数：

```python
# POST /api/config — 第 590 行
@app.post("/api/config")
async def post_config(body: ConfigRequest, admin_auth: None = Depends(require_admin)):
    # ... 后续逻辑不变

# PUT /api/config/{mac}/activate/{config_id} — 第 620 行
@app.put("/api/config/{mac}/activate/{config_id}")
async def put_activate(mac: str, config_id: int, admin_auth: None = Depends(require_admin)):
    # ... 后续逻辑不变

# POST /api/modes/custom — 第 683 行
@app.post("/api/modes/custom")
async def create_custom_mode(body: dict, admin_auth: None = Depends(require_admin)):
    # ... 后续逻辑不变

# DELETE /api/modes/custom/{mode_id} — 第 727 行
@app.delete("/api/modes/custom/{mode_id}")
async def delete_custom_mode(mode_id: str, admin_auth: None = Depends(require_admin)):
    # ... 后续逻辑不变

# POST /api/modes/generate — 第 747 行
@app.post("/api/modes/generate")
async def generate_mode(body: dict, admin_auth: None = Depends(require_admin)):
    # ... 后续逻辑不变

# POST /api/modes/custom/preview — 第 648 行
@app.post("/api/modes/custom/preview")
async def custom_mode_preview(body: dict, admin_auth: None = Depends(require_admin)):
    # ... 后续逻辑不变

# GET /api/stats/overview — 第 1007 行
@app.get("/api/stats/overview")
async def stats_overview(admin_auth: None = Depends(require_admin)):
    # ... 后续逻辑不变
```

**Step 4：运行全量测试**

运行：`cd backend && python -m pytest tests/ -v`
预期：全部 PASS（测试环境未设置 `ADMIN_TOKEN`，管理员鉴权自动跳过）

**Step 5：提交**

```bash
git add backend/api/index.py
git commit -m "feat(auth): 为管理端点启用管理员 Token 鉴权"
```

---

### Task 5：更新 `.env.example` 和 webconfig 前端页面

**文件：**
- 修改：`backend/.env.example` — 添加 `ADMIN_TOKEN`
- 修改：`webconfig/config.html` — 添加管理密钥输入框 + fetch 请求携带鉴权头
- 修改：`webconfig/dashboard.html` — fetch 请求携带鉴权头

**Step 1：更新 `.env.example`**

在 `backend/.env.example` 末尾追加：

```bash

# ============================================
# 鉴权配置
# ============================================

# 管理端点的访问密钥（配置管理、模式管理、统计概览等）
# 留空或不设置则跳过管理员鉴权（适用于本地开发）
ADMIN_TOKEN=
```

**Step 2：为 webconfig `config.html` 添加管理员鉴权**

在 `<script>` 部分 `const API_BASE = ...` 之后添加辅助函数：

```javascript
// ── 管理员鉴权 ──────────────────────────────────────────────
function getAdminToken() {
  return localStorage.getItem('inksight_admin_token') || '';
}
function setAdminToken(token) {
  localStorage.setItem('inksight_admin_token', token);
}
function authHeaders() {
  const token = getAdminToken();
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  return headers;
}
```

更新所有管理端点的 `fetch()` 调用，使用 `authHeaders()`：

- `saveConfig()`：将 headers 改为 `authHeaders()`
- `triggerRefresh()`：添加 `headers: authHeaders()`
- `activateConfig()`：添加 `headers: authHeaders()`
- 自定义模式的保存/删除/生成：添加 `headers: authHeaders()`

在配置页面设置区域添加管理密钥输入框：

```html
<div class="form-group">
  <label>管理密钥 (Admin Token)</label>
  <input type="password" id="adminToken" placeholder="留空表示无需认证"
         onchange="setAdminToken(this.value)">
  <small>部署时设置 ADMIN_TOKEN 环境变量后，需要在此输入对应密钥</small>
</div>
```

页面加载时从 localStorage 恢复：

```javascript
document.getElementById('adminToken').value = getAdminToken();
```

**Step 3：为 webconfig `dashboard.html` 添加管理员鉴权**

添加相同的 `getAdminToken()` / `authHeaders()` 辅助函数。
更新 `GET /api/stats/overview` 的 fetch 调用，携带鉴权头。

**Step 4：手动测试**

1. 不设置 `ADMIN_TOKEN` 启动后端 — 所有端点应正常工作
2. 在 `.env` 中设置 `ADMIN_TOKEN=test123`，重启后端
3. 不带 Token 请求 `POST /api/config` — 应返回 403
4. 携带 `Authorization: Bearer test123` — 应成功
5. 打开 webconfig，输入管理密钥，保存配置 — 应成功

**Step 5：提交**

```bash
git add backend/.env.example webconfig/config.html webconfig/dashboard.html
git commit -m "feat(auth): 在环境配置和 webconfig 前端中添加管理员 Token 支持"
```

---

### Task 6：运行全量测试并验证

**文件：**
- 无新增文件

**Step 1：运行全部后端测试**

运行：`cd backend && python -m pytest tests/ -v`
预期：全部测试 PASS

**Step 2：验证向后兼容性**

运行：`cd backend && python -m uvicorn api.index:app --host 0.0.0.0 --port 8080`

在未配置任何鉴权的情况下测试（`.env` 中无 `ADMIN_TOKEN`）：

```bash
# 健康检查 — 应正常
curl http://localhost:8080/api/health

# 无 Token 渲染 — 应正常（无设备状态 = 宽限期放行）
curl "http://localhost:8080/api/render?mac=AA:BB:CC:DD:EE:FF&v=3.3"

# 保存配置 — 应正常（无 ADMIN_TOKEN = 开放访问）
curl -X POST http://localhost:8080/api/config \
  -H "Content-Type: application/json" \
  -d '{"mac":"AA:BB:CC:DD:EE:FF","modes":["STOIC"],...}'
```

**Step 3：如有修复则提交**

```bash
git add -A
git commit -m "fix(auth): 修复全量测试中发现的问题"
```

---

## 端点保护总览

| 端点 | 鉴权层 | 行为 |
|------|--------|------|
| `GET /api/health` | 无 | 公开 |
| `GET /api/render` | 设备 Token | 新设备宽限期放行 |
| `GET /api/preview` | 无 | 公开（预览控制台） |
| `GET /api/widget/{mac}` | 设备 Token | 新设备宽限期放行 |
| `GET /api/config/{mac}` | 设备 Token | 新设备宽限期放行 |
| `GET /api/config/{mac}/history` | 设备 Token | 新设备宽限期放行 |
| `POST /api/config` | 管理员 Token | 设置了 ADMIN_TOKEN 时无 Token 返回 403 |
| `PUT /api/config/{mac}/activate/{id}` | 管理员 Token | 设置了 ADMIN_TOKEN 时无 Token 返回 403 |
| `POST /api/device/{mac}/refresh` | 设备 Token | 新设备宽限期放行 |
| `GET /api/device/{mac}/state` | 设备 Token | 新设备宽限期放行 |
| `POST /api/device/{mac}/switch` | 设备 Token | 新设备宽限期放行 |
| `POST /api/device/{mac}/token` | 无 | Token 分发端点 |
| `POST /api/device/{mac}/favorite` | 设备 Token | 新设备宽限期放行 |
| `GET /api/device/{mac}/favorites` | 设备 Token | 新设备宽限期放行 |
| `GET /api/device/{mac}/history` | 设备 Token | 新设备宽限期放行 |
| `POST /api/device/{mac}/habit/check` | 设备 Token | 新设备宽限期放行 |
| `GET /api/device/{mac}/habit/status` | 设备 Token | 新设备宽限期放行 |
| `GET /api/device/{mac}/qr` | 设备 Token | 新设备宽限期放行 |
| `GET /api/device/{mac}/share` | 设备 Token | 新设备宽限期放行 |
| `GET /api/modes` | 无 | 公开 |
| `POST /api/modes/custom` | 管理员 Token | 设置了 ADMIN_TOKEN 时无 Token 返回 403 |
| `POST /api/modes/custom/preview` | 管理员 Token | 设置了 ADMIN_TOKEN 时无 Token 返回 403 |
| `GET /api/modes/custom/{id}` | 无 | 公开（只读） |
| `DELETE /api/modes/custom/{id}` | 管理员 Token | 设置了 ADMIN_TOKEN 时无 Token 返回 403 |
| `POST /api/modes/generate` | 管理员 Token | 设置了 ADMIN_TOKEN 时无 Token 返回 403 |
| `GET /api/stats/overview` | 管理员 Token | 设置了 ADMIN_TOKEN 时无 Token 返回 403 |
| `GET /api/stats/{mac}` | 设备 Token | 新设备宽限期放行 |
| `GET /api/stats/{mac}/renders` | 设备 Token | 新设备宽限期放行 |
| `GET /api/firmware/*` | 无 | 公开 |
| `GET /`、`/config`、`/dashboard`、`/editor` | 无 | 静态页面 |
