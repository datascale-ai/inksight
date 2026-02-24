# InkSight WebApp

InkSight 的 Next.js 官网与在线刷机前端（App Router）。

- 公网主页: [https://www.inksight.site](https://www.inksight.site)
- 本地默认地址: `http://localhost:3000`

## 功能范围

- 官网展示与导航入口
- 文档展示页（快速开始、硬件说明等）
- 在线刷机页面（通过后端固件 API 拉取版本与下载地址）

## 页面路由

| 路由 | 说明 |
|------|------|
| `/` | 官网首页 |
| `/docs` | 文档页面 |
| `/flash` | 在线刷机页面 |
| `/store` | 插件市场页面（占位） |

## 本地开发

```bash
npm install
npm run dev
```

可选检查：

```bash
npm run lint
```

## 环境变量

WebApp 支持“浏览器直连后端”和“同域代理到后端”两种模式。

| 变量名 | 默认值 | 用途 |
|--------|--------|------|
| `INKSIGHT_BACKEND_API_BASE` | `http://127.0.0.1:8080` | Next.js API Route 的后端代理目标 |
| `NEXT_PUBLIC_FIRMWARE_API_BASE` | 空 | 浏览器侧直接请求后端固件 API 的基地址 |

推荐本地 `.env.local`：

```bash
INKSIGHT_BACKEND_API_BASE=http://127.0.0.1:8080
```

如果前端与后端分开部署，再增加：

```bash
NEXT_PUBLIC_FIRMWARE_API_BASE=https://your-backend.example.com
```

## 固件 API 代理链路

当未设置 `NEXT_PUBLIC_FIRMWARE_API_BASE` 时，前端请求当前域名下的 API Route，再由服务端代理到 `INKSIGHT_BACKEND_API_BASE`。

当前已实现的代理端点：

- `GET /api/firmware/releases`
- `GET /api/firmware/releases/latest`
- `GET /api/firmware/validate-url?url=...`

## 构建与部署

```bash
npm run build
npm run start
```

生产部署前建议确认：

- `INKSIGHT_BACKEND_API_BASE` 指向可访问的 InkSight 后端
- 后端已开放 `/api/firmware/*` 相关接口
- 若使用浏览器直连，后端 CORS 已正确配置

## 常见问题

- 刷机页提示 `upstream_unreachable`：检查 `INKSIGHT_BACKEND_API_BASE` 是否可达。
- 版本列表为空：检查后端 GitHub Releases 拉取是否受限（令牌/频率限制）。
- 前端能开但刷机失败：优先用同域代理模式排除浏览器跨域问题。
