[English](README.md) | 中文

# InkSight | inco (墨鱼)

> 一款 LLM 驱动的智能电子墨水屏桌面伴侣，为你递送有温度的"慢信息"——纸墨之间，皆是智慧。

官网主页：[https://www.inksight.site](https://www.inksight.site)

![Version](https://img.shields.io/badge/version-v0.1-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-ESP32--C3-orange)
![Python](https://img.shields.io/badge/python-3.10+-blue)

![inco](images/intro.jpg)

---

## 项目简介

**墨鱼**（inco）是基于 InkSight 构建的智能墨水屏桌面伴侣。通过后端 大语言模型（DeepSeek / 通义千问 / Kimi）生成基于当前环境（天气、时间、日期、节气）的个性化内容，在 4.2 英寸电子墨水屏上展示。内置 **22 个内置模式**（6 个核心模式 + 16 个扩展模式），并支持自定义AI模式，为你的桌面带来有温度的智能陪伴。模式系统支持 JSON 配置驱动扩展——无需编写 Python 即可创建自定义内容模式。

**核心特点：**

- **22 个内置模式 + 自定义模式** — 核心模式：每日推荐、天气、诗词、AI 画廊、老黄历、AI 简报；扩展模式：斯多葛、禅意、食谱、倒计时、便签、习惯打卡、慢信、历史上的今天、每日一谜、每日一问、认知偏差、微故事、人生进度条、微挑战、毒舌、健身
- **模式可扩展** — 通过 JSON 配置定义新模式（提示词、布局、样式），无需编写代码
- **AI 模式生成器** — 用自然语言生成自定义模式定义
- **内置模式编辑器** — 配置页支持模板化创建/编辑自定义 JSON 模式并实时预览
- **4 种刷新策略** — 随机轮换、循环轮换、时段绑定、智能模式
- **运行模式切换** — 短按 BOOT 在 `active`（在线轮询）/`interval`（间歇刷新）间切换；支持 Web/API 远程触发刷新、切模式、下发预览图
- **用户系统** — 用户注册登录、设备绑定、多设备管理
- **设备鉴权** — 基于 Device Token 的设备 API 认证
- **统计仪表板** — 设备状态监控、电池电压趋势、模式使用统计、缓存命中率
- **WiFi 配网** — Captive Portal 自动弹出配置页面，零门槛
- **在线配置** — Web 界面管理所有设置，支持配置导入/导出、预览效果、历史配置
- **智能缓存** — 批量预生成内容，响应时间 < 1 秒
- **多 LLM 支持** — DeepSeek、阿里百炼、月之暗面
- **超低功耗** — Deep Sleep 模式，单次充电续航 3-6 个月
- **低成本硬件** — BOM 成本约 ¥220，开源硬件可复现

---

## 内容模式

![内容模式](images/mode.png)

| 模式 | 说明 |
|------|------|
| **STOIC** - 斯多葛哲学 | 庄重、内省的哲学语录，适合工作日的清晨 |
| **ROAST** - 毒舌吐槽 | 犀利的中文吐槽，用黑色幽默缓解压力 |
| **ZEN** - 禅意 | 极简的汉字（如"静"、"空"），营造宁静氛围 |
| **DAILY** - 每日推荐 | 语录、书籍推荐、冷知识、节气信息的丰富排版 |
| **BRIEFING** - AI 简报 | Hacker News Top 3 + Product Hunt #1，AI 行业洞察 |
| **ARTWALL** - AI 画廊 | 根据天气/节气生成黑白版画风格的艺术作品 |
| **RECIPE** - 每日食谱 | 时令食材推荐早中晚三餐方案，荤素搭配 |
| **FITNESS** - 健身计划 | 简单的居家健身训练计划，动作列表 + 健康提示 |
| **POETRY** - 每日诗词 | 精选古典诗词，感受文字之美 |
| **COUNTDOWN** - 倒计时 | 重要日期倒计时/正计日，纪念日提醒 |
| **WEATHER** - 天气看板 | 实时天气与趋势摘要，辅助当日安排 |
| **MEMO** - 便签 | 在墨水屏显示自定义短便签 |
| **HABIT** - 习惯打卡 | 展示每日习惯完成状态和进度 |
| **ALMANAC** - 老黄历 | 农历日期、宜忌、节气、养生提示 |
| **LETTER** - 慢信 | 来自不同时空的一封温暖短信，有角色感和画面感 |
| **THISDAY** - 历史上的今天 | 同一天发生过的重大历史事件 |
| **RIDDLE** - 每日一谜 | 谜语、脑筋急转弯、趣味知识题 |
| **QUESTION** - 每日一问 | 一个值得花3分钟思考的开放式问题 |
| **BIAS** - 认知偏差 | 每天认识一个认知偏差或心理学效应 |
| **STORY** - 微故事 | 一个完整的三段式微型小说，有反转有余韵 |
| **LIFEBAR** - 人生进度条 | 年/月/周/人生的进度可视化 |
| **CHALLENGE** - 微挑战 | 每天一个5分钟可完成的小挑战 |

---

## 刷新策略

| 策略 | 说明 |
|------|------|
| **随机轮换** | 从已启用的模式中随机选取 |
| **循环轮换** | 按顺序循环切换已启用的模式（重启后不丢失进度） |
| **时段绑定** | 根据时间段显示不同内容模式（如早上食谱、上午简报、晚上禅意） |
| **智能模式** | 根据时间段自动匹配最佳模式（早餐建议 / 科技简报 / 运动计划等） |

### 智能模式默认时段

| 时间段 | 推荐模式 |
|--------|----------|
| 06:00 - 09:00 | 食谱、每日推荐 |
| 09:00 - 12:00 | AI 简报、斯多葛 |
| 12:00 - 14:00 | 禅意、诗词 |
| 14:00 - 18:00 | 斯多葛、毒舌 |
| 18:00 - 21:00 | 健身、食谱 |
| 21:00 - 06:00 | 禅意、诗词 |

---

## 技术架构

![技术架构图](structure.png)


| 层 | 技术栈 |
|----|--------|
| 硬件 | ESP32-C3 + 4.2" E-Paper (400x300, 1-bit) + LiFePO4 电池 |
| 固件 | PlatformIO / Arduino, GxEPD2, WiFiManager |
| 后端 | Python FastAPI, Pillow, OpenAI SDK, httpx, SQLite |
| 前端 | 静态页面（`webconfig/`）+ Next.js 应用（`webapp/`，官网与在线刷机） |

详细架构设计请参考 [系统架构文档](docs/architecture.md)。

---

## 你需要准备

### 硬件清单

- ESP32-C3 开发板（推荐 SuperMini）
- 4.2 英寸电子墨水屏（SPI 接口，400x300）
- 杜邦线 / 焊接工具（按你的装配方式选择）
- 供电方案：USB 供电，或 LiFePO4 电池 + TP5000 充电模块（可选）

### 配置设备清单

- 一台电脑（Windows/macOS/Linux，建议使用 Chrome/Edge）
- 一根支持数据传输的 USB 线（用于刷机）
- 2.4GHz WiFi 网络（设备联网获取天气与 LLM 内容）
- LLM API Key（使用自部署后端时需要）
- 可选：一部手机（仅在你希望通过移动端 Captive Portal 配网时使用）

---

## 快速开始

### 1. 硬件准备

- ESP32-C3 开发板 (推荐 SuperMini)
- 4.2 英寸电子墨水屏 (SPI 接口, 400x300)
- LiFePO4 电池 + TP5000 充电模块 (可选)

硬件接线详见 [硬件指南](docs/hardware.md)。

### 2. 后端部署

```bash
# 克隆项目
git clone https://github.com/datascale-ai/inksight.git
cd inksight/backend

# 安装依赖
pip install -r requirements.txt

# 下载字体文件 (Noto Serif SC, Lora, Inter — 约 70MB)
python scripts/setup_fonts.py

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入你的 API Key

# 启动服务
python -m uvicorn api.index:app --host 0.0.0.0 --port 8080
```

你可以按以下两种方式使用：

- **公网托管方式（推荐给小白）**：直接使用公网站点完成刷机与配置，开箱即用。
- **本地自部署方式**：本地启动后端（`http://127.0.0.1:8080`）和前端（`http://localhost:3000`）进行配置与开发。

同一套运行配置下，建议只选择一种目标地址即可。

入口访问：

| 入口 | URL | 说明 |
|------|-----|------|
| 在线体验 / 官网 | `https://www.inksight.site` | 公网托管站点（开箱即用） |

| 本地后端页面 | URL | 说明 |
|------|-----|------|
| 预览控制台 | `http://localhost:8080` | 测试各模式渲染效果 |
| 配置管理 | `http://localhost:8080/config` | 管理设备配置 |
| 统计仪表板 | `http://localhost:8080/dashboard` | 设备状态与使用统计 |
| 模式编辑器 | `http://localhost:8080/editor` | 创建与编辑自定义 JSON 模式 |

### 2.5 Web 应用（官网 + 在线刷机）

```bash
cd webapp

# 配置环境变量
cp .env.example .env

npm install
npm run dev
```

默认访问：`http://localhost:3000`

环境变量说明（按你选择的方式配置）：

- `INKSIGHT_BACKEND_API_BASE`（后端目标：本地自部署通常为 `http://127.0.0.1:8080`；公网部署使用你的后端域名）
- `NEXT_PUBLIC_FIRMWARE_API_BASE`（可选；若配置，请与上面的后端目标保持一致）

`webapp` 的 `/config` 页面包含登录与设备绑定流程。

### 3. 固件烧录

**方式 A：Web 在线刷机（推荐）**

- 使用 Chrome/Edge 打开 InkSight Web Flasher 页面。
- 从 GitHub Releases 选择固件版本。
- 通过 USB 连接 ESP32-C3，点击刷写即可。

固件发布产物命名为 `inksight-firmware-<semver>.bin`，统一上传到 GitHub Releases。

**方式 B：PlatformIO 本地烧录**

```bash
cd firmware

# 使用 PlatformIO 编译并上传
pio run --target upload

# 查看串口日志
pio device monitor
```

或使用 Arduino IDE 打开 `firmware/src/main.cpp` 进行编译上传。

如果 `webapp` 与后端 API 分开部署，请将
`NEXT_PUBLIC_FIRMWARE_API_BASE` 指向你当前选择的同一后端目标。若不配置，
`webapp` 会使用内置 Next.js API 路由，将 `/api/firmware/*` 代理到
`INKSIGHT_BACKEND_API_BASE`。

### 4. 配网

大多数情况下，可在网页前端一站式完成配置；Captive Portal 作为补充方案使用。

1. 首次启动（或无 WiFi 配置）会自动进入 Captive Portal
2. 设备已配置时，长按 BOOT（>= 2 秒）重启；重启过程中继续按住可强制进入配网模式
3. 用电脑（或手机）连接设备热点 `InkSight-XXXXXX`
4. 自动弹出配置页面，选择 WiFi，然后按你的部署方式选择“官方服务”（开箱即用）或“自定义后端地址”（自部署）

### 5. 按钮操作

| 操作 | 效果 |
|------|------|
| RESET | 硬件重启 |
| 短按 BOOT (>= 50ms 且 < 2 秒) | 切换运行状态：`active`（在线轮询）/ `interval`（间歇刷新） |
| 长按 BOOT (>= 2 秒) | 重启设备 |
| 重启过程中持续按住 BOOT | 进入 Captive Portal 配网模式 |

设备首次完成配置后，会默认进入一次 `active` 运行状态。

---

## 配置说明

![配置管理](images/configuration.png)

访问 `http://your-server:8080/config?mac=XX:XX:XX:XX:XX:XX` 进行在线配置：

| 配置项 | 说明 |
|--------|------|
| 昵称 | 设备名称 |
| 内容模式 | 选择要显示的模式（可多选） |
| 刷新策略 | 随机轮换 / 循环轮换 / 时段绑定 / 智能模式 |
| 时段规则 | 时段绑定模式下配置不同时段对应的模式（最多 24 条） |
| 刷新间隔 | 10 分钟 ~ 24 小时 |
| 语言偏好 | 中文 / 英文 / 中英混合 |
| 内容调性 | 积极 / 中性 / 深沉 / 幽默 |
| 角色语气 | 鲁迅、王小波、JARVIS、苏格拉底、村上春树等预设 + 自定义 |
| 地理位置 | 用于获取天气信息 |
| LLM 提供商 | DeepSeek / 阿里百炼 / 月之暗面 |
| LLM 模型 | 根据提供商选择具体模型 |
| 倒计时事件 | COUNTDOWN 模式使用的日期事件（最多 10 个） |
| 模式级覆盖 | 按模式覆盖城市、LLM 提供商、模型及扩展字段 |
| API Key | 设备级文本/图像 API Key（加密存储） |

### 配置管理功能

- **配置导入/导出** — JSON 格式备份和迁移设备配置
- **配置预览** — 保存前可预览各模式的渲染效果
- **立即刷新** — 远程触发设备在下次唤醒时刷新内容
- **历史配置** — 查看、回滚历史配置版本
- **自定义模式编辑器** — 模板化创建/编辑 JSON 模式
- **AI 模式生成器** — 通过自然语言生成模式定义

### 更多能力

- **习惯打卡** — 记录每日习惯完成状态
- **收藏** — 收藏模式或内容快照
- **内容历史** — 按设备分页查看历史渲染内容
- **分享与二维码** — 生成分享图与设备绑定二维码
- **Widget 嵌入** — 通过只读接口输出可嵌入图片
- **账户体系** — 注册/登录/绑定设备
- **设备鉴权** — 设备接口支持 `X-Device-Token` 认证

API 接口详见 [API 文档](docs/api.md)。

---

## 统计仪表板

![统计仪表板](images/dashboard.png)

访问 `http://your-server:8080/dashboard?mac=XX:XX:XX:XX:XX:XX` 查看设备统计：

- **设备状态** — 最后刷新时间、电池电压、WiFi 信号强度
- **电压趋势** — 电池电压历史曲线（最近 30 条记录）
- **模式统计** — 各模式使用频率分布
- **每日渲染** — 每日渲染次数柱状图
- **缓存命中率** — 缓存使用效率
- **渲染记录** — 最近渲染详情（模式、耗时、状态）

---

## API 端点

### 核心接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| GET | `/api/render` | 生成 BMP 图像（设备端调用） |
| GET | `/api/preview` | 生成 PNG 预览图 |
| GET | `/api/widget/{mac}` | 只读 Widget 图片接口（可嵌入） |

### 配置接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/config` | 保存设备配置 |
| GET | `/api/config/{mac}` | 获取当前配置 |
| GET | `/api/config/{mac}/history` | 获取配置历史 |
| PUT | `/api/config/{mac}/activate/{config_id}` | 激活指定历史配置 |

### 模式管理接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/modes` | 获取模式列表（内置 + 自定义） |
| POST | `/api/modes/custom/preview` | 预览自定义模式定义 |
| POST | `/api/modes/custom` | 创建/更新自定义 JSON 模式 |
| GET | `/api/modes/custom/{mode_id}` | 获取自定义模式定义 |
| DELETE | `/api/modes/custom/{mode_id}` | 删除自定义模式 |
| POST | `/api/modes/generate` | 通过自然语言生成模式定义（AI） |

### 设备控制接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/device/{mac}/refresh` | 触发设备下次唤醒时刷新 |
| GET | `/api/device/{mac}/state` | 获取设备运行状态 |
| POST | `/api/device/{mac}/runtime` | 设置运行模式（`active` / `interval`） |
| POST | `/api/device/{mac}/apply-preview` | 下发预览图到设备 |
| POST | `/api/device/{mac}/switch` | 触发切换到指定模式 |
| POST | `/api/device/{mac}/favorite` | 收藏当前内容或指定模式 |
| GET | `/api/device/{mac}/favorites` | 获取收藏列表 |
| GET | `/api/device/{mac}/history` | 获取内容历史（分页） |
| POST | `/api/device/{mac}/token` | 生成设备认证 Token |
| GET | `/api/device/{mac}/qr` | 生成设备二维码 |
| GET | `/api/device/{mac}/share` | 生成分享图 |
| GET | `/api/devices/recent` | 获取最近上线设备（用于发现） |

### 习惯打卡接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/device/{mac}/habit/check` | 提交习惯打卡 |
| GET | `/api/device/{mac}/habit/status` | 获取当周习惯状态 |
| DELETE | `/api/device/{mac}/habit/{habit_name}` | 删除习惯及其记录 |

### 统计接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/stats/overview` | 全局统计概览（管理端） |
| GET | `/api/stats/{mac}` | 设备统计详情 |
| GET | `/api/stats/{mac}/renders` | 渲染历史（分页） |

### 固件接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/firmware/releases` | 获取固件版本列表 |
| GET | `/api/firmware/releases/latest` | 获取最新固件版本 |
| GET | `/api/firmware/validate-url` | 校验固件下载 URL |

### 用户认证接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/register` | 注册 |
| POST | `/api/auth/login` | 登录 |
| POST | `/api/auth/logout` | 登出 |
| GET | `/api/auth/me` | 获取当前用户信息 |

### 用户设备管理接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/user/devices` | 获取当前用户绑定设备 |
| POST | `/api/user/devices` | 绑定设备 |
| DELETE | `/api/user/devices/{mac}` | 解绑设备 |

**说明：**
- 设备接口在设备已发放 Token 后，需携带 `X-Device-Token`
- 管理接口在配置 `ADMIN_TOKEN` 后，需携带 `Authorization: Bearer <token>`
- `/api/widget/{mac}` 为只读接口，不会更新设备状态或触发刷新

---

## 项目结构

```
inksight/
├── backend/                # Python 后端服务
│   ├── api/index.py        # FastAPI 入口 + 所有 API 端点
│   ├── core/               # 核心模块
│   │   ├── config.py       # 配置常量
│   │   ├── config_store.py # 配置存储 + 设备状态 (SQLite)
│   │   ├── stats_store.py  # 统计数据采集与查询
│   │   ├── context.py      # 环境上下文 (天气/日期)
│   │   ├── content.py      # LLM 内容生成
│   │   ├── json_content.py # JSON 模式内容生成
│   │   ├── pipeline.py     # 统一生成管线
│   │   ├── renderer.py     # 内置模式图像渲染
│   │   ├── json_renderer.py# JSON 模式图像渲染
│   │   ├── mode_registry.py# 模式注册（内置 + JSON）
│   │   ├── mode_generator.py # AI 模式定义生成
│   │   ├── cache.py        # 缓存系统
│   │   ├── schemas.py      # Pydantic 请求校验
│   │   ├── auth.py         # 鉴权（JWT + 设备 Token）
│   │   ├── crypto.py       # 密钥加解密工具
│   │   ├── db.py           # 数据库连接管理
│   │   ├── errors.py       # 错误处理
│   │   └── modes/          # JSON 模式定义
│   │       ├── schema/     # 模式验证 JSON Schema
│   │       ├── builtin/    # 内置 JSON 模式 (22 种)
│   │       └── custom/     # 用户自定义 JSON 模式
│   ├── scripts/            # 工具脚本
│   │   └── setup_fonts.py  # 字体下载脚本
│   ├── fonts/              # 字体文件 (需通过脚本下载)
│   │   └── icons/          # PNG 图标
│   ├── tests/              # 测试文件
│   ├── requirements.txt    # Python 依赖
│   └── vercel.json         # Vercel 部署配置
├── firmware/               # ESP32-C3 固件
│   ├── src/
│   │   ├── main.cpp        # 固件主程序（按钮控制 + 刷新逻辑）
│   │   ├── config.h        # 引脚定义 + 常量配置
│   │   ├── network.cpp     # WiFi / HTTP / NTP（含 RSSI 上报）
│   │   ├── display.cpp     # 墨水屏显示逻辑
│   │   ├── storage.cpp     # NVS 存储
│   │   └── portal.cpp      # Captive Portal 配网
│   ├── data/portal_html.h  # 配网页面 HTML
│   └── platformio.ini      # PlatformIO 配置
├── webconfig/              # Web 配置前端
│   ├── config.html         # 配置管理页面
│   ├── preview.html        # 预览控制台
│   └── dashboard.html      # 统计仪表板
├── webapp/                 # Next.js 官网 + 在线刷机前端
│   ├── app/                # App Router 页面与 API 路由
│   ├── components/         # UI 组件
│   ├── public/             # 静态资源
│   └── package.json        # Node.js 依赖与脚本
└── docs/                   # 项目文档
    ├── architecture.md     # 系统架构
    ├── api.md              # API 接口文档
    └── hardware.md         # 硬件指南
```

---

## 开发路线

- [x] WiFi 配网系统 (Captive Portal)
- [x] 在线配置管理 + 历史配置
- [x] 循环/随机刷新策略
- [x] 时段绑定 + 智能模式刷新策略
- [x] 智能缓存系统（重启后 cycle_index 不丢失）
- [x] 22 种内容模式（含天气、便签、习惯打卡、老黄历、慢信、历史上的今天、每日一谜、每日一问、认知偏差、微故事、人生进度条、微挑战）
- [x] 多 LLM 提供商支持
- [x] Web/API 按需刷新、切模式、预览下发
- [x] 配置导入/导出 + 预览效果
- [x] Toast 通知替代 confirm/alert
- [x] Preview 控制台增强（请求取消、历史记录、限速、分辨率模拟）
- [x] 统计仪表板（设备监控 + 使用统计 + 图表可视化）
- [x] RSSI 信号强度上报
- [x] 模式可扩展化系统（JSON 配置驱动自定义模式）
- [x] 用户系统（注册、登录、设备绑定）
- [x] 设备 Token 鉴权
- [x] 自定义模式管理（创建、预览、删除）
- [x] AI 模式生成（自然语言生成模式定义）
- [x] 习惯打卡、收藏、内容历史
- [x] 分享图、二维码、Widget 接口
- [x] 多分辨率渲染支持（`w` / `h` 请求参数 + 固件编译分辨率）
- [x] 用户自定义 API Key（设备级文本/图像 Key，加密存储）
- [ ] Vercel 一键部署
- [ ] 硬件产品化 (PCB 设计)

---

## 贡献

欢迎提交 Issue 和 Pull Request！请查看 [贡献指南](CONTRIBUTING.md) 了解详情。

---

## 许可证

[MIT License](LICENSE)

---

## 致谢

- [Open-Meteo](https://open-meteo.com/) — 免费天气数据 API
- [Hacker News](https://news.ycombinator.com/) — 科技资讯
- [Product Hunt](https://www.producthunt.com/) — 产品发现
- [DeepSeek](https://www.deepseek.com/) — LLM 服务
- [阿里百炼](https://bailian.console.aliyun.com/) — LLM 服务
- [月之暗面](https://www.moonshot.cn/) — LLM 服务
- [GxEPD2](https://github.com/ZinggJM/GxEPD2) — E-Paper 显示驱动库
