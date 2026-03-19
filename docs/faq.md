# 常见问题（FAQ）

如果你已经开始使用，遇到“为什么不对”“为什么找不到”“为什么和预期不一样”这类问题，先从这里查起最快。

## 1. 文档入口在哪里？

当前建议直接看这些文档：

- `README.md`
- `docs/hardware.md`
- `docs/assembly.md`
- `docs/flash.md`
- `docs/config.md`
- `docs/deploy.md`
- `docs/api-key.md`
- `docs/faq.md`

## 2. 配置页里为什么找不到 AI 模型设置？

因为当前代码中：

- **设备配置页**负责设备配置
- **个人信息页**负责模型、API Key、额度与访问模式

也就是说，AI 模型和 API Key 已经从设备配置页拆到了**个人信息页**。

## 3. ARTWALL 没有图片

优先检查：

- 是否配置了 `DASHSCOPE_API_KEY`
- 是否已在**个人信息页**中完成图像模型配置
- 后端是否已重启并加载最新环境变量
- 后端日志中是否出现图片下载失败或超时

## 4. 本地 `next build` 失败

当前 WebApp 使用 `next/font` 拉取在线字体。
如果本地或 CI 环境无法访问 Google Fonts，`npm run build` 可能失败。

这通常不是业务代码错误，而是构建环境网络问题。

## 5. 端口冲突导致服务无法启动

默认端口：

- WebApp：`3000`
- Backend：`8080`

如果端口被占用，可以改端口启动，并同步更新前端环境变量：

```bash
python -m uvicorn api.index:app --host 0.0.0.0 --port 18080
```

## 6. WebApp 能打开，但刷机失败

优先检查：

- `INKSIGHT_BACKEND_API_BASE` 是否可达
- 后端 `/api/firmware/*` 是否正常
- 浏览器是否支持 WebSerial
- USB 线是否真的是数据线

## 7. 设备预览和设备真实显示不一致

优先检查：

- 当前预览是否使用了模式级覆盖参数
- 设备是否已经点击“保存到设备”
- 设备是否在线、是否已立即拉取最新配置
- 当前是否命中缓存

## 8. 提交 PR 时无法自动合并

如果你维护的是自己的 fork，且上游做过 squash / rewrite，建议：

- 先同步 `upstream/main`
- 基于最新主干新开干净分支
- 使用 `cherry-pick` 只带有效提交

这样通常比在旧分支上反复 merge 更稳妥。
