[English](README.md) | 中文

# 墨鱼 | InkSight

> 一块真正适合放在桌面的电子墨水信息屏，并配有一个能一站式完成刷机、配置、预览与发现创意模式的网站。

官网主页：[https://www.inksight.site](https://www.inksight.site)

![InkSight](images/intro.jpg)

## 它为什么特别

墨鱼AI墨水屏是一个面向桌面场景的电子墨水屏伴侣。
它不是另一块“会打扰你的屏幕”，而是把天气、习惯、便签、倒计时、简报和更有温度的内容，以纸面般克制的方式放到你的视线里。

- **抬头即见**：天气、倒计时、便签、习惯、简报一眼可读
- **电子墨水体验**：纸感显示，不刺眼，适合长时间放在桌面，超长时间待机
- **模式丰富且好看**：24 个内置模式，既有实用信息，也有更适合桌面氛围的内容
- **网站一站式完成**：小白友好一键配置，网页刷机、在线配置、无设备预览、模式广场都已打通
- **开源且可扩展**：固件、后端、Web 配置、JSON 模式系统都可扩展，之后会开源PCB板设计图纸、外壳3D打印图纸等等

## 一个网站完成整条体验

当前官网不只是展示页，而是把完整体验串在一起。
哪怕你是第一次接触电子墨水屏、ESP32 或 WebSerial，也可以跟着页面一步步完成上手；很多情况下，你几乎只需要点点屏幕，就能完成设备刷机、联网和配置。

- **在线刷机**：浏览器里直接完成 Web Flasher，不需要先装复杂工具链
- **在线配置**：在 `/config` 里完成设备模式、个性化设置与常用参数调整
- **在线预览**：保存前先看到墨水屏效果，减少“改了才知道不合适”的试错
- **无设备体验**：没有设备也能先玩模式和预览，先理解产品体验再决定要不要做
- **模式广场**：发现、分享、安装社区用户创作的模式，让灵感和玩法可以流动起来

这让墨鱼AI墨水屏不只是一个开源硬件项目，也更像一个完整产品。

## 丰富而精美的模式库

当前内置 **24 个模式**，包括：

- **每日推荐**：语录、书籍、冷知识、节气信息
- **天气看板**：实时天气与趋势摘要
- **诗词 / 禅意 / 斯多葛**：更适合桌面氛围的慢内容
- **AI 简报**：科技热点与 AI 洞察
- **AI 画廊**：黑白风格的上下文艺术图
- **便签 / 倒计时 / 习惯 / 健身**：更偏实用的桌面工具模式

同时你还可以：

- **创建自己的自定义模式**
- **把模式保存到设备**
- **把创意发布到模式广场**
- **安装别人分享的社区模式**

## 推荐硬件方案

最推荐的入门组合：

| 部件 | 推荐选型 |
|------|----------|
| 主控 | ESP32-C3 开发板 |
| 屏幕 | 4.2寸 SPI 墨水屏 |
| 供电 | 开发期 USB，长期使用可选锂电池方案（推荐 `505060-2000mAh` + TP5000） |
| 成本 | DIY BOM 通常约 **220 元** |

> **详细的硬件购买方案与淘宝链接**，请参考：[**硬件购买清单与方案推荐**](docs/bom.md)

当前对外推荐统一以 **ESP32-C3 + 4.2寸墨水屏** 为主。

如果你是第一次上手，建议从 **ESP32-C3 + 4.2寸** 开始。

## 体验我们的软件(一站式官网)

![Official_Website](images/official_web_screenshot.png)

如果你想先感受和了解产品，可以直接访问官网去体验：

- 官网：[`inksight.site`](https://www.inksight.site)
- 在线刷机：支持一键拉取我们发布的最新固件代码并部署，教程视频: [`刷机视频教程`](https://www.bilibili.com/video/BV1aWcQzQE3r/?spm_id_from=333.1387.homepage.video_card.click&vd_source=166ea338ef8c38d7904da906b88ef0b7)
- 设备配置：当刷完设备之后，可以在这里配置显示的内容
- 模式广场：可以分享自己的大作，也可以用上大神们设计的精美模式
- 无设备体验：提供给还没有设备的朋友们一个体验的机会

## 动手做一台墨鱼AI墨水屏

![动手做一台墨鱼AI墨水屏](images/build-device.png)

如果你喜欢 DIY、想亲手组一台自己的墨鱼AI墨水屏，买到了设备之后不知道如何组装的话，可以参考 [`组装视频教程`](https://www.bilibili.com/video/BV1spwKzUE6N?spm_id_from=333.788.videopod.sections&vd_source=166ea338ef8c38d7904da906b88ef0b7)

我们也准备了相应的文档：

- 硬件指南：[`docs/hardware.md`](docs/hardware.md)
- 组装指南：[`docs/assembly.md`](docs/assembly.md)
- 刷机指南：[`docs/flash.md`](docs/flash.md)
- 配置指南：[`docs/config.md`](docs/config.md)

## 社区优秀作品展示

非常感谢社区开发者们为 InkSight 创作的精美外壳和定制 PCB！以下是一些优秀的社区开源硬件和 3D 打印模型：

### 3D 打印外壳
- **[适配 InkSight 4.2寸 桌面外壳 18650电池版](https://makerworld.com.cn/zh/models/2315926-gua-pei-inksight-4-2cun-zhi-neng-dian-zi-mo-shui-p#profileId-2617500)**
  
  <img src="images/community/case1.png" width="400">

- **[InkSight 4.2寸](https://makerworld.com.cn/zh/models/2319168-fu-ke-jiao-cheng-gua-pei-inksight-4-2cun-zhi-neng#profileId-2621798)**
  
  <img src="images/community/case2.png" width="400">
  <img src="images/community/case3.png" width="400">

- **[华为Nova14彩显手机壳3.98寸四色墨水屏](https://makerworld.com.cn/zh/models/2399226-gu-jian-kai-yuan-diy-hua-wei-nova14cai-xian-shou-j#profileId-2744953)**

<img src="images/community/case4.png" width="400">

### 定制 PCB 驱动板
- **[4.2寸墨水屏驱动（InkSight 定制版）](https://oshwhub.com/kidstory/4-2)**
  
  <img src="images/community/pcb1.png" width="400">

- **[墨鱼AI墨水屏（已验证）](https://oshwhub.com/qq173972819/project_mqihrlpc)**
  
  <img src="images/community/pcb2.png" width="400">

## 本地部署服务 / 二次开发

如果你是开发者、想在本地部署一套服务，或者不仅仅满足我们提供的官网服务，准备二次开发、联调 API 和前后端流程，请从这里进入：

- 中文部署文档：[`docs/deploy.md`](docs/deploy.md)
- English deployment guide: [`docs/en/deploy.md`](docs/en/deploy.md)
- 架构设计：[`docs/architecture.md`](docs/architecture.md)
- API：[`docs/api.md`](docs/api.md)
- 插件 / 扩展开发：[`docs/plugin-dev.md`](docs/plugin-dev.md)

## 社区

- Discord: [https://discord.gg/5Ne6D4YNf](https://discord.gg/5Ne6D4YNf)
- QQ 群: [1026120682](http://qm.qq.com/cgi-bin/qm/qr?_wv=1027&k=kha7gD4FzS3ld_f9bx_TlLIj94Oyoip1&authKey=n4yACMiVaMagSs5HUH5HLw%2BhXdKRFjCDI4rAt7zdVym7yTeXwMxTkWqUjE9jzjXo&noverify=0&group_code=1026120682)
- [BiliBili](https://www.bilibili.com/video/BV1nSNcziE7q/)

![QQ 群二维码](images/QQ.jpg)
