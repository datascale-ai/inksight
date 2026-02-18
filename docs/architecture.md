# InkSight 系统架构文档

## 系统概览

```
graph TD
    User[用户环境] -->|WiFi| ESP32[ESP32-C3 终端]
    ESP32 -->|HTTP GET / 电量 & Mac地址| Cloud[Vercel Serverless]
    
    subgraph Cloud Backend
        Cloud -->|API Call| Weather[Open-Meteo API]
        Cloud -->|API Call| LLM[DeepSeek / 阿里百炼 / 月之暗面]
        Cloud -->|Image Processing| Renderer[Python Pillow]
    end
    
    Renderer -->|生成 BMP| Cloud
    Cloud -->|返回二进制流| ESP32
    ESP32 -->|SPI 驱动| Screen[4.2寸 E-Ink 屏幕]
```

## 固件端 (Firmware)

- **开发框架:** PlatformIO (C++ / Arduino Framework)
- **核心库:** `GxEPD2` (显示驱动), `WiFiManager` (配网), `HTTPClient` (网络)

### 工作流状态机

1. **BOOT:** 初始化 SPI，读取电池电压。
2. **CONNECT:** 尝试连接 WiFi。若失败则开启 AP 模式等待配置。
3. **REQUEST:** 向后端发送 GET 请求（携带电压参数）。
4. **STREAM:** 逐字节读取 Response Body，直接写入屏幕缓冲区。
5. **DISPLAY:** 触发全屏/局部刷新更新。
6. **SLEEP:** 开启 Deep Sleep 定时器，切断所有外设电源，系统休眠。

### 配网流程 (Captive Portal)

1. 首次启动或长按 BOOT 按钮 2 秒，进入配网模式。
2. ESP32 开启 AP 热点 `InkSight-XXXXXX`。
3. 用户连接后自动弹出配置页面。
4. 选择 WiFi 并输入密码，配置完成后设备自动连接。

## 后端服务 (Backend)

- **部署平台:** Vercel (Python Runtime)
- **框架:** FastAPI
- **核心依赖:** Pillow (图像渲染), httpx (HTTP 客户端), openai (LLM SDK)

### 图像渲染管线 (Rendering Pipeline)

1. **Input:** 接收 HTTP 请求，解析参数（电压、MAC 地址）。
2. **Context:** 并行获取外部数据（时间、天气、电池电量）。
3. **Intelligence:** 根据内容模式构造 Prompt，调用 LLM API 获取文本。
4. **Rasterization (核心):**
   - 创建 400x300 画布 (Mode '1', 1-bit 黑白)。
   - 加载字体文件（Noto Serif）。
   - 执行 Text Wrap 算法计算多行布局。
   - 绘制 UI 元素（线条、图标、电量指示）。
5. **Output:** 将 Image 对象转换为 BMP 字节流返回。

### 内容模式 (10 种)

| 模式 ID | 名称 | 说明 |
|---------|------|------|
| STOIC | 斯多葛哲学 | 庄重、内省的哲学语录 |
| ROAST | 毒舌吐槽 | 犀利的中文吐槽，黑色幽默 |
| ZEN | 禅意 | 极简的汉字，营造宁静氛围 |
| DAILY | 每日推荐 | 语录、书籍推荐、冷知识、节气 |
| BRIEFING | AI 简报 | HN/PH 热榜 + AI 行业洞察 |
| ARTWALL | AI 画廊 | 黑白版画风格的 AI 艺术作品 |
| RECIPE | 每日食谱 | 时令三餐方案，荤素搭配 |
| FITNESS | 健身计划 | 居家健身训练计划 |
| POETRY | 每日诗词 | 精选古典诗词，感受文字之美 |
| COUNTDOWN | 倒计时 | 重要日期倒计时/正计日，纪念日提醒 |

### 智能缓存系统

- **批量预生成:** 首次请求时并行生成所有用户选择的模式。
- **智能 TTL:** Cache 过期时间 = 刷新间隔 x 模式数量 x 1.1。
- **Cache Hit 优化:** 缓存命中时响应时间 < 1 秒。

### 配置管理

- 基于 SQLite 数据库，按 MAC 地址存储用户配置。
- 自动保存最近 5 次配置历史，支持查看、编辑、激活。
- 配置项包括：昵称、内容模式、刷新策略、语言偏好、内容调性、地理位置、LLM 提供商/模型。

## 数据交互协议

设备与后端之间通过 HTTP 通信，详见 [API 文档](api.md)。

## 性能指标

| 指标 | 数值 |
|------|------|
| Cache Hit 响应时间 | < 1 秒 |
| Cache Miss 响应时间 | 15-20 秒 (多模式并行生成) |
| Cache Hit 率 | > 95% |
| 设备唤醒到显示完成 | < 15 秒 (取决于网络) |
