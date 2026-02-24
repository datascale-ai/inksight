# Web 在线刷机

InkSight 提供基于浏览器的在线刷机能力，适合绝大多数用户。

## 1. 使用条件

- 浏览器：Chrome / Edge（支持 WebSerial）
- 访问环境：`localhost` 或 HTTPS 域名
- 连接方式：USB 数据线（必须支持数据传输）

## 2. 基本流程

1. 打开 Web 刷机页面：`/flash`
2. 连接设备并授权串口
3. 选择固件版本（可刷新版本列表）
4. 点击刷写并等待完成
5. 刷写后观察串口日志确认启动正常

## 3. 版本来源与代理

WebApp 会通过以下接口获取固件版本信息：

- `GET /api/firmware/releases`
- `GET /api/firmware/releases/latest`
- `GET /api/firmware/validate-url?url=...`

当未配置 `NEXT_PUBLIC_FIRMWARE_API_BASE` 时，前端默认走同域 API Route 代理到 `INKSIGHT_BACKEND_API_BASE`。

## 4. 故障排查

### 无法识别串口设备

- 确认是数据线，不是仅充电线
- 尝试更换 USB 口或重插设备
- 在系统设备管理中确认串口是否存在

### 版本列表加载失败

- 检查后端是否可访问
- 检查后端是否触发 GitHub API 频率限制
- 在页面内点击“刷新版本”重试

### 刷写中断/失败

- 保持 USB 连接稳定
- 切换到手动 URL 模式并先做链接校验
- 重启设备后再次进入刷机流程
