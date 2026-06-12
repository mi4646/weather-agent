# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 常用命令

```bash
# 运行 Agent（命令行传参）
python src/main.py 帮我查一下今天北京天气

# 运行 Agent（交互式输入）
python src/main.py

# 运行全部测试
pytest tests/ -v

# 运行单个测试文件
pytest tests/test_tools.py -v

# 运行单个测试类
pytest tests/test_tools.py::TestExtractCityName -v

# 运行单个测试用例
pytest tests/test_tools.py::TestExtractCityName::test_province_city_district -v

# 安装依赖
pip install -r requirements.txt
```

## 架构概览

这是一个从零手写的 AI Agent 学习项目，核心代码不到 150 行。架构分三层：

### 1. 工具层 (`src/tools.py`)

每个工具由两部分组成，存储在 `TOOLS` 字典中（`key=工具名`, `value={definition, execute}`）：

- **definition**：给 LLM 看的说明书（OpenAI function calling JSON 格式）
- **execute**：实际执行的 async Python 函数

注册通过 `register(name, definition, executor)` 完成。`get_definitions()` 返回所有说明书列表发给 LLM。**添加新工具只需写函数 + 注册，不改 agent.py**。

现有两个工具：
- `geocode` — 地址→经纬度（Open-Meteo 免费 API），支持中国区县级地址三级降级查询
- `get_weather` — 经纬度→当前天气（GFS 全球预报数据）

`geocode` 的三级降级流程：原样查询 → 剥离区县级后缀重试 → 提取纯城市名重试。内置 300+ 中国地级市列表和省级前缀映射，正确处理直辖市歧义。

### 2. Agent 层 (`src/agent.py`)

`Agent` 类封装核心循环，构造参数：`llm`（AsyncOpenAI 客户端）、`model`（模型名）、`tools`（工具说明书列表）、`tool_executors`（`{名称: 执行函数}` 映射）。

`Agent.run(user_input)` 的核心是一个 `while True` 循环：
1. 消息历史 + 工具说明书 → 发给 LLM
2. LLM 返回 `finish_reason="tool_calls"` → 执行对应工具 → 结果追加到消息历史 → 继续循环
3. LLM 返回 `finish_reason="stop"` → 返回最终答案

**决策权在 LLM**，agent.py 只负责执行和消息传递，不做任何业务决策。

### 3. 入口层 (`src/main.py`)

从 `.env` 读取 `LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL` 构建 AsyncOpenAI 客户端，从 `tools.py` 获取工具定义和执行器，创建 Agent 实例并运行。支持命令行传参和交互式输入两种模式。

### 日志 (`src/logger.py`)

双输出设计：文件日志（`logs/agent.log`，DEBUG 级别，记录完整执行流程）和终端输出（stderr，WARNING 级别，不干扰用户）。每次 Agent 运行都会在日志中记录工具列表、每轮消息、LLM 原始响应、工具执行参数和结果。

## 配置

通过 `.env` 文件配置（模板见 `.env.example`）：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `LLM_API_KEY` | LLM API Key（必填） | — |
| `LLM_BASE_URL` | LLM API 地址 | `https://api.openai.com/v1` |
| `LLM_MODEL` | 模型名称 | `gpt-4o` |

兼容 OpenAI 接口的任意模型（DeepSeek / 通义千问 / 豆包 / OpenAI）。

## 技术要点

- `pyproject.toml` 中 `asyncio_mode = "auto"`，pytest 自动处理 async 测试，无需 `@pytest.mark.asyncio` 装饰器也能运行（但当前测试仍保留了显式标记）
- 工具执行器统一为 `async`，避免阻塞 Agent 循环
- 测试中通过 `monkeypatch` 替换 `_query_geocode` 来模拟 API 调用，实现确定性的降级流程测试
- `.vscode/` 和 `.idea/` 已在 `.gitignore` 中排除
