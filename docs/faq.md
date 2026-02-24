# 常见问题（FAQ）

## 1. 文档页面 404

确认访问的是已定义路由：

- `/docs`
- `/docs/hardware`
- `/docs/assembly`
- `/docs/flash`
- `/docs/api-key`
- `/docs/config`
- `/docs/plugin-dev`
- `/docs/api-reference`
- `/docs/faq`

## 2. ARTWALL 没有图片

优先检查：

- 是否配置 `DASHSCOPE_API_KEY`
- 后端服务是否重启并加载新环境变量
- 后端日志中是否有图片下载失败/超时

## 3. 预览页是随机模式，不是指定模式

`/` 是预览控制台入口，默认可能是 AUTO。  
请直接访问：`/api/preview?persona=ARTWALL` 进行模式级验证。

## 4. 端口冲突导致服务无法启动

如果 `8080` 被占用，可改用：

```bash
python -m uvicorn api.index:app --host 0.0.0.0 --port 18080 --reload
```

## 5. webapp 能打开但刷机失败

优先检查：

- `INKSIGHT_BACKEND_API_BASE` 是否可达
- 后端 `/api/firmware/*` 是否正常
- 跨域场景下是否已正确设置浏览器侧 API 基地址

## 6. 提交 PR 显示无法自动合并

通常是分支历史与上游重复提交导致。  
建议基于 `upstream/main` 新建干净分支，使用 `cherry-pick` 仅带有效提交再提 PR。
