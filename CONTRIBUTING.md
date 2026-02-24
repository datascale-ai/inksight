# 贡献指南

感谢你对 InkSight 项目的关注！我们欢迎各种形式的贡献。

## 如何贡献

### 报告 Bug

1. 在 [Issues](https://github.com/datascale-ai/inksight/issues) 中搜索是否已有相同问题。
2. 如果没有，创建新 Issue，请包含：
   - 问题的简要描述
   - 复现步骤
   - 期望行为 vs 实际行为
   - 环境信息（操作系统、Python 版本、ESP32 固件版本等）

### 提交功能建议

欢迎在 Issues 中提交功能建议，请说明：
- 功能的使用场景
- 期望的实现方式
- 是否愿意自己实现

### 提交代码

1. Fork 本仓库
2. 创建功能分支: `git checkout -b feature/your-feature-name`
3. 提交改动: `git commit -m "feat: add your feature description"`
4. 推送分支: `git push origin feature/your-feature-name`
5. 创建 Pull Request

## 开发环境搭建

### 后端

```bash
cd backend

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入你的 API Key

# 启动开发服务器
python -m uvicorn api.index:app --reload --host 0.0.0.0 --port 8000
```

### 固件

1. 安装 [PlatformIO](https://platformio.org/install)
2. 打开 `firmware/` 目录
3. 连接 ESP32-C3 开发板
4. 运行 `pio run --target upload`

## 代码风格

### Python (后端)

- 遵循 PEP 8
- 使用 4 空格缩进
- 函数和变量使用 snake_case
- 类名使用 PascalCase
- 添加必要的类型注解

### C++ (固件)

- 使用 4 空格缩进
- 函数名使用 camelCase
- 常量使用 UPPER_SNAKE_CASE
- 添加关键逻辑的注释

## Commit 规范

推荐使用 [Conventional Commits](https://www.conventionalcommits.org/) 格式：

- `feat:` 新功能
- `fix:` Bug 修复
- `docs:` 文档更新
- `refactor:` 代码重构
- `test:` 测试相关
- `chore:` 构建/工具链相关

示例: `feat: add weather icon for snowy days`

## 项目结构

- `backend/` — Python FastAPI 后端，包含渲染和 LLM 集成
- `backend/core/patterns/` — 各内容模式的实现，添加新模式请参考现有实现
- `firmware/` — ESP32-C3 固件代码
- `webconfig/` — Web 配置页面和预览控制台
- `docs/` — 项目文档

## 添加新的内容模式

如果你想贡献一个新的内容模式：

1. 在 `backend/core/patterns/` 下创建新的 Python 文件
2. 实现 `render_xxx()` 函数，接收上下文参数，返回 PIL Image
3. 在 `backend/core/content.py` 中注册新模式的内容生成函数
4. 在 `backend/api/index.py` 中注册新模式
5. 添加对应的测试文件到 `backend/tests/`
6. 更新文档

## 许可

提交的所有贡献将遵循项目的 [MIT 许可证](LICENSE)。
