# InkSight Widget 嵌入指南

## 概述

InkSight 提供了只读的 Widget API，可以将墨水屏内容嵌入到各种平台的小组件中。

## API 端点

```
GET /api/widget/{mac}?mode=STOIC&size=medium
```

### 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `mac` | 设备 MAC 地址 | 必填 |
| `mode` | 内容模式 | 设备配置的第一个模式 |
| `w` | 宽度 (px) | 400 |
| `h` | 高度 (px) | 300 |
| `size` | 预设尺寸: small/medium/large | medium |

### 尺寸预设

- `small`: 200x150 (适合小组件)
- `medium`: 400x300 (标准尺寸)
- `large`: 800x480 (大屏/横屏)

### 响应

- Content-Type: `image/png`
- Cache-Control: `public, max-age=300` (5分钟 CDN 缓存)
- 不触发设备状态更新

## iOS Scriptable

```javascript
let mac = "AA:BB:CC:DD:EE:FF"
let server = "https://your-inksight-server.com"
let url = `${server}/api/widget/${mac}?size=medium`

let widget = new ListWidget()
let req = new Request(url)
let img = await req.loadImage()
widget.backgroundImage = img
widget.setPadding(0, 0, 0, 0)

if (config.runsInWidget) {
  Script.setWidget(widget)
} else {
  widget.presentMedium()
}
Script.complete()
```

## Android KWGT

1. 在 KWGT 中创建一个新组件
2. 添加 Image 模块
3. 设置图片源为 URL:
   ```
   https://your-server/api/widget/YOUR_MAC?size=small
   ```
4. 设置刷新间隔为 30 分钟

## Web 嵌入

```html
<iframe
  src="https://your-server/widget?mac=YOUR_MAC&mode=STOIC&size=medium"
  width="400"
  height="300"
  frameborder="0"
  style="border-radius: 8px; border: 1px solid #e5e5e5;"
></iframe>
```

## macOS Widgetsmith / Übersicht

```coffeescript
command: "curl -s 'https://your-server/api/widget/YOUR_MAC?size=large' -o /tmp/inksight.png && echo done"
refreshFrequency: 1800000  # 30 minutes

render: (output) ->
  """
  <img src="/tmp/inksight.png" style="width:100%;height:100%;object-fit:contain">
  """
```

## Web 页面

访问 `https://your-server/widget?mac=YOUR_MAC` 查看实时 widget 预览。

支持的 URL 参数与 API 端点一致。
