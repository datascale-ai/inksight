# InkSight Web

InkSight 的官网与 Web 在线刷机前端（Next.js App Router）。

## 本地开发

```bash
npm install
npm run dev
```

默认访问：`http://localhost:3000`

## 在线刷机配置

在线刷机页会请求固件元数据接口：

- `GET /api/firmware/releases`
- `GET /api/firmware/releases/latest`

推荐配置服务端代理目标（Next.js API Route -> InkSight Backend）：

```bash
INKSIGHT_BACKEND_API_BASE=http://127.0.0.1:8080
```

浏览器端跨域直连时，再配置：

```bash
NEXT_PUBLIC_FIRMWARE_API_BASE=https://your-backend.example.com
```

未配置 `NEXT_PUBLIC_FIRMWARE_API_BASE` 时，前端默认请求当前域名下的 `/api/firmware/releases`，由本项目内置代理转发到 `INKSIGHT_BACKEND_API_BASE`。

## 构建与部署

```bash
npm run build
npm run start
```
