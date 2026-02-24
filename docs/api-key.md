# 配置 API Key

InkSight 的内容生成依赖外部模型服务。请在后端环境变量中配置对应密钥。

## 1. 基础配置

```bash
cd inksight/backend
cp .env.example .env
```

编辑 `.env` 填入你实际使用的密钥。

## 2. 常见变量

- `DEEPSEEK_API_KEY`：文本内容生成（如语录/简报）
- `DASHSCOPE_API_KEY`：图像生成（如 ARTWALL）
- 其他提供商变量按你选择的模型平台补充

## 3. 生效方式

环境变量修改后必须重启后端服务：

```bash
python -m uvicorn api.index:app --host 0.0.0.0 --port 8080
```

## 4. 验证建议

- 先用 `/api/preview?persona=STOIC` 验证文本模式
- 再用 `/api/preview?persona=ARTWALL` 验证图像模式
- 若 ARTWALL 无图，优先检查 `DASHSCOPE_API_KEY` 与服务重启状态

## 5. 安全建议

- 不要把 `.env` 提交到仓库
- 生产环境建议使用平台 Secret 管理
- 定期轮换密钥并限制权限范围
