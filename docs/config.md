# Web 配置后台

Web 配置后台用于管理设备配置、模式策略和运行参数。

## 1. 入口

- 本地后端：`http://127.0.0.1:18080/config`
- 线上部署：`https://your-domain/config`

## 2. 可配置项

- 设备昵称、城市
- 内容模式（多选）
- 刷新策略（随机 / 循环 / 时段绑定 / 智能）
- 语言偏好、内容调性、角色语气
- LLM 提供商与模型
- 倒计时事件（COUNTDOWN）

## 3. 配置管理能力

- 导入 / 导出 JSON
- 历史配置查看与激活
- 预览渲染效果
- 远程触发设备下次唤醒刷新

## 4. 推荐流程

1. 先配置基础信息（模式、城市、刷新间隔）
2. 再设置语言、调性与角色语气
3. 最后按需增加时段规则和倒计时事件
4. 保存后用预览确认显示效果

## 5. 相关接口

详情参考 API 文档：`/docs/api-reference`

常用接口：

- `POST /api/config`
- `GET /api/config/{mac}`
- `GET /api/config/{mac}/history`
- `PUT /api/config/{mac}/activate/{id}`
