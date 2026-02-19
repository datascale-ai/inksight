# InkSight API 接口文档

**版本:** v1.0.0

**Base URL:** `https://your-deployment-url.vercel.app`

## 1. 概述

本接口服务用于 InkSight 墨水屏设备的云端渲染。API 遵循 **Server-Side Rendering** 原则——服务端负责所有数据聚合、排版布局和图像处理，直接返回设备可读取的图像二进制流。

### 通用请求头

| Key | Value | 说明 |
|-----|-------|------|
| `User-Agent` | `ESP32-HTTP-Client` | 标识设备类型 (可选) |

---

## 2. 核心接口

### 2.1 获取墨水屏渲染图

设备唤醒后调用的核心接口。

- **URL:** `GET /api/render`

#### 请求参数

| 参数名 | 类型 | 必填 | 示例 | 描述 |
|--------|------|------|------|------|
| `v` | `float` | 是 | `3.25` | 电池当前电压 |
| `mac` | `string` | 否 | `A1:B2:C3:D4` | 设备 MAC 地址 |
| `persona` | `string` | 否 | `鲁迅` | 强制指定角色语气 |
| `rssi` | `int` | 否 | `-65` | WiFi 信号强度 (dBm) |
| `w` | `int` | 否 | `400` | 屏幕宽度 (100-1600)，默认 400 |
| `h` | `int` | 否 | `300` | 屏幕高度 (100-1200)，默认 300 |

#### 响应

- **Status:** `200 OK`
- **Content-Type:** `image/bmp`
- **Body:** 1-bit Monochrome BMP 图片数据

#### 错误处理

即使服务端发生错误，也会返回一张错误提示图片（而非 JSON），避免设备解析失败。

#### 示例

```bash
# 默认分辨率 (400x300)
curl -X GET "https://your-url.vercel.app/api/render?v=3.20&mac=test_device" --output screen.bmp

# 自定义分辨率 (800x480)
curl -X GET "https://your-url.vercel.app/api/render?v=3.20&mac=test_device&w=800&h=480" --output screen.bmp
```

---

### 2.2 浏览器预览

用于在浏览器中调试查看生成效果。

- **URL:** `GET /api/preview`

逻辑与 `/api/render` 一致，但返回 `image/png` 格式，方便在浏览器中查看。

请求参数同 `/api/render`。

---

### 2.3 设备配置

- **URL:** `GET /api/config/{mac}`

#### 路径参数

| 参数名 | 类型 | 描述 |
|--------|------|------|
| `mac` | `string` | 设备 MAC 地址 |

返回该设备的当前配置。

- **URL:** `POST /api/config`

#### 请求体 (JSON)

```json
{
  "mac": "XX:XX:XX:XX:XX:XX",
  "nickname": "我的桌面",
  "modes": ["STOIC", "DAILY", "RECIPE"],
  "strategy": "cycle",
  "refresh_interval": 60,
  "language": "zh",
  "tone": "positive",
  "lat": 31.23,
  "lon": 121.47,
  "llm_provider": "deepseek",
  "llm_model": "deepseek-chat"
}
```

---

### 2.4 配置历史

- **URL:** `GET /api/config/{mac}/history`

返回该设备最近 5 次配置记录。

---

### 2.5 激活历史配置

- **URL:** `PUT /api/config/{mac}/activate/{config_id}`

将指定的历史配置设为当前活跃配置。

---

### 2.6 健康检查

- **URL:** `GET /api/health`
- **响应:**

```json
{
  "status": "ok",
  "timestamp": "2026-02-16T10:00:00Z",
  "version": "1.0.0"
}
```

---

## 3. 电量映射算法

后端根据传入的 `v` 参数计算电池百分比并绘制对应图标：

| 电压范围 | 电量 | 图标 |
|----------|------|------|
| v >= 3.40V | 100% | 满电 |
| 3.30V <= v < 3.40V | 70% | 高电量 |
| 3.20V <= v < 3.30V | 40% | 中电量 |
| v < 3.20V | 10% | 低电量警告 |

## 4. ESP32 客户端处理规范

由于 ESP32 内存有限，需采用流式处理 (Stream Processing)：

```cpp
// 发起请求
http.begin("http://server/api/render?v=3.2");
int httpCode = http.GET();

if (httpCode == 200) {
    int len = http.getSize();
    WiFiClient *stream = http.getStreamPtr();

    // 流式写入屏幕缓冲区
    uint8_t buffer[128];
    while (http.connected() && (len > 0 || len == -1)) {
        size_t size = stream->available();
        if (size) {
            int c = stream->readBytes(buffer,
                ((size > sizeof(buffer)) ? sizeof(buffer) : size));
            // 将 buffer 写入屏幕驱动的显存
        }
    }
}
```
