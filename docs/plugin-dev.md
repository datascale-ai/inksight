# 插件开发（JSON 模式扩展）

InkSight 当前推荐通过 JSON 模式扩展内容能力，而不是新增 Python 模式渲染代码。

## 1. 设计原则

- 内容生成与布局渲染解耦
- 配置驱动，减少硬编码
- 新增模式优先复用现有 block 与 content type

## 2. 基本结构

一个模式定义通常包含：

- `mode_id` / `display_name` / `icon`
- `content`（生成逻辑）
- `layout`（渲染结构）
- `cacheable` / `description`

## 3. 常见 content.type

- `llm`：文本输出
- `llm_json`：结构化 JSON 输出
- `computed`：基于本地上下文计算
- `external_data`：外部数据源聚合
- `image_gen`：图像生成
- `composite`：组合多个子内容

## 4. 开发流程建议

1. 在 `backend/core/modes/builtin` 或 `custom` 下新增 json
2. 按 schema 校验字段合法性
3. 在预览接口验证渲染效果
4. 补齐测试（内容生成、渲染、路由）
5. 更新 README 与 docs

## 5. 调试建议

- 先验证内容层是否返回预期字段
- 再验证渲染层 block 是否按顺序落位
- 对图像模式优先检查外部 API key 与下载链路
