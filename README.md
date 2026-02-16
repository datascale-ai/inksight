# InkSight (墨见)

> A minimalist smart e-ink desktop companion powered by LLM, delivering calm and meaningful "slow information" to your desk.

> 一款极简主义的智能电子墨水屏桌面摆件，通过 LLM 生成有温度的"慢信息"。

![Version](https://img.shields.io/badge/version-v0.8-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-ESP32--C3-orange)
![Python](https://img.shields.io/badge/python-3.10+-blue)

<!-- 
TODO: 添加项目实物照片
![InkSight Demo](docs/images/demo.jpg) 
-->

---

## 项目简介

InkSight 通过后端 LLM（DeepSeek / 通义千问 / Kimi）生成基于当前环境（天气、时间、日期、节气）的个性化内容，在 4.2 英寸电子墨水屏上展示。支持 8 种不同的内容模式，从哲学语录到健身计划，从科技简报到每日食谱，为你的桌面带来有温度的智能陪伴。

**核心特点：**

- **8 种内容模式** — 斯多葛哲学、毒舌吐槽、禅意、每日推荐、AI 简报、AI 画廊、食谱、健身
- **智能刷新策略** — 支持循环轮换和随机轮换
- **WiFi 配网** — Captive Portal 自动弹出配置页面，零门槛
- **在线配置** — Web 界面管理所有设置，支持历史配置
- **智能缓存** — 批量预生成内容，响应时间 < 1 秒
- **多 LLM 支持** — DeepSeek、阿里百炼、月之暗面
- **超低功耗** — Deep Sleep 模式，单次充电续航 3-6 个月

---

## 内容模式

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

---

## 技术架构

![技术架构图](structure.png)


| 层 | 技术栈 |
|----|--------|
| 硬件 | ESP32-C3 + 4.2" E-Paper (400x300, 1-bit) + LiFePO4 电池 |
| 固件 | PlatformIO / Arduino, GxEPD2, WiFiManager |
| 后端 | Python FastAPI, Pillow, OpenAI SDK, httpx, SQLite |
| 前端 | HTML / CSS / JavaScript (配置页面 & 预览控制台) |

详细架构设计请参考 [系统架构文档](docs/architecture.md)。

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

启动后访问 `http://localhost:8080` 查看预览控制台。

### 3. 固件烧录

```bash
cd firmware

# 使用 PlatformIO 编译并上传
pio run --target upload

# 查看串口日志
pio device monitor
```

或使用 Arduino IDE 打开 `firmware/src/main.cpp` 进行编译上传。

### 4. 配网

1. 首次启动或长按 BOOT 按钮 2 秒进入配网模式
2. 手机连接设备热点 `InkSight-XXXXXX`
3. 自动弹出配置页面，选择 WiFi 并输入密码
4. 配置完成后设备自动连接并开始工作

---

## 配置说明

访问 `http://your-server:8080/config?mac=XX:XX:XX:XX:XX:XX` 进行在线配置：

| 配置项 | 说明 |
|--------|------|
| 昵称 | 设备名称 |
| 内容模式 | 选择要显示的模式（可多选） |
| 刷新策略 | 循环轮换 / 随机轮换 |
| 刷新间隔 | 10 分钟 ~ 24 小时 |
| 语言偏好 | 中文 / 英文 / 中英混合 |
| 内容调性 | 积极 / 中性 / 深沉 / 幽默 |
| 地理位置 | 用于获取天气信息 |
| LLM 提供商 | DeepSeek / 阿里百炼 / 月之暗面 |
| LLM 模型 | 根据提供商选择具体模型 |

API 接口详见 [API 文档](docs/api.md)。

---

## 项目结构

```
inksight/
├── backend/                # Python 后端服务
│   ├── api/index.py        # FastAPI 入口
│   ├── core/               # 核心模块
│   │   ├── config.py       # 配置常量
│   │   ├── context.py      # 环境上下文 (天气/日期)
│   │   ├── content.py      # LLM 内容生成
│   │   ├── renderer.py     # 图像渲染
│   ├── scripts/            # 工具脚本
│   │   └── setup_fonts.py  # 字体下载脚本
│   ├── fonts/              # 字体文件 (TTF 需通过脚本下载)
│   │   └── icons/          # PNG 图标 (已包含在仓库中)
│   │   ├── config_store.py # 配置存储 (SQLite)
│   │   ├── cache.py        # 缓存系统
│   │   └── patterns/       # 8 种内容模式实现
│   ├── tests/              # 测试文件
│   ├── requirements.txt    # Python 依赖
│   └── vercel.json         # Vercel 部署配置
├── firmware/               # ESP32-C3 固件
│   ├── src/main.cpp        # 固件主程序
│   ├── data/portal.h       # 配网页面
│   └── platformio.ini      # PlatformIO 配置
├── web/                    # Web 前端
│   ├── config.html         # 配置页面
│   └── preview.html        # 预览控制台
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
- [x] 智能缓存系统
- [x] 8 种内容模式
- [x] 多 LLM 提供商支持
- [ ] 支持不同屏幕分辨率
- [ ] 模式可扩展化系统 (JSON 配置驱动)
- [ ] 用户自定义 API Key
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
