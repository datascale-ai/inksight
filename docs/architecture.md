# InkSight 系统架构

本文档以当前仓库代码为准，说明 InkSight 的三层结构、核心渲染链路、模式系统与配置存储方式。

## 1. 总体结构

InkSight 当前由三部分组成：

- **Firmware**：ESP32 固件，负责联网、拉取内容、驱动墨水屏、深度休眠
- **Backend**：FastAPI 服务，负责配置、天气、模式内容生成、图像渲染、缓存与统计
- **WebApp**：Next.js 应用，负责官网、文档、在线刷机、登录、设备配置与预览

## 2. 核心数据流

典型链路如下：

1. 设备联网后向后端请求渲染内容
2. 后端读取设备配置、地点、时间等上下文
3. 后端按模式决定使用静态内容、外部数据、规则计算或大模型生成
4. 渲染器把结果绘制为适合电子墨水屏的黑白位图
5. 设备接收图像并刷新显示

除了设备请求，WebApp 也会通过 API 完成：

- 设备配置保存
- 模式预览
- 固件版本查询
- 设备状态与统计展示

## 3. 后端架构

后端入口位于：

- `backend/api/index.py`

它同时负责：

- FastAPI API
- 兼容静态页面
- 生命周期初始化

### 核心渲染流程

设备调用 `/api/render` 或 Web 端调用 `/api/preview` 时，主要流程是：

1. `api/index.py` 接收请求
2. `core/cache.py` 检查缓存
3. 若未命中，则进入 `core/pipeline.py:generate_and_render()`
4. `core/mode_registry.py` 判断当前模式属于内置模式还是 JSON 模式
5. 内容生成完成后，由 `core/renderer.py` 或 `core/json_renderer.py` 输出图像

### 模式系统

当前内置模式已经统一迁移到 JSON 模式系统，内置定义位于：

- `backend/core/modes/builtin/`

同时也支持：

- `backend/core/modes/custom/` 中的自定义 JSON 模式

当前仓库中内置 **24 个 JSON 模式**。

### 内容来源

模式内容可以来自多种来源：

- 静态内容
- 规则计算内容
- 外部数据（如天气）
- 文本大模型
- 图像模型
- 组合型内容

天气相关上下文主要由：

- `backend/core/context.py`

负责获取与整理。

### 配置与缓存

当前后端使用两个 SQLite 数据库：

- `inksight.db`：设备配置、配置历史、设备状态
- `cache.db`：渲染缓存

缓存 TTL 采用与刷新频率、模式数量相关的计算方式，用来减少重复生成带来的延迟和成本。

## 4. WebApp 架构

当前主前端位于：

- `webapp/`

主要职责：

- 官网展示
- 文档中心
- Web 在线刷机
- 登录与个人信息
- 设备配置页
- 个人信息页
- 在线预览

当前产品结构中：

- 设备配置页管理设备行为与模式配置
- 个人信息页管理模型、API Key、额度与访问模式

如果单看配置流，这是一个很重要的职责划分。

## 5. 固件架构

固件位于：

- `firmware/`

主要模块包括：

- `src/main.cpp`：主循环、按键逻辑、睡眠与唤醒
- `src/network.cpp`：Wi-Fi、HTTP 请求、时间同步
- `src/display.cpp`：墨水屏显示封装
- `src/portal.cpp`：配网 Portal
- `src/storage.cpp`：设备本地状态持久化

当前仓库内置多个屏幕尺寸与板型 profile，默认环境是：

- `epd_42_c3`

## 6. 外部依赖

当前常见外部依赖包括：

- 天气接口
- 文本大模型接口
- 图像模型接口

LLM 调用由 OpenAI 兼容方式统一封装，图像模式则根据配置使用对应服务。

## 7. 为什么会有缓存与预生成

InkSight 的内容生成不总是即时且廉价的，尤其在以下场景：

- 需要访问外部天气数据
- 需要调用大模型
- 需要渲染多个模式预览

因此系统使用缓存与批量预生成来降低：

- 设备等待时间
- API 调用次数
- 重复渲染成本

## 8. 相关文档

- 硬件：[`hardware.md`](hardware.md)
- 刷机：[`flash.md`](flash.md)
- 配置：[`config.md`](config.md)
- API：[`api.md`](api.md)
