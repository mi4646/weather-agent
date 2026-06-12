# weather-agent

> 从零手写的 AI Agent，理解 Agent 核心循环的最佳实践项目。

用户说"查北京天气" → Agent 自动串联 geocode + 天气 API → 返回天气结果。

---

## 项目结构

```
weather-agent/
├── .python-version           # pyenv 虚拟环境（Python 3.14）
├── .env.example              # API Key 配置模板
├── requirements.txt          # 依赖列表
├── pyproject.toml            # pytest 配置
├── docs/
│   └── agent-tool-design.md  # Agent Tool 设计指南（教学文档）
├── tests/
│   ├── __init__.py
│   └── test_tools.py         # geocode 工具单元测试（39 个用例）
├── src/
│   ├── tools.py              # 工具定义 + 注册 + 执行
│   ├── agent.py              # Agent 核心循环
│   ├── logger.py             # 日志模块（双输出）
│   └── main.py               # CLI 入口
└── README.md
```

## 架构

```
用户输入 "查北京天气"
  │
  ▼
main.py → Agent.run()
  │
  ▼
┌─────────────── Agent 循环 ───────────────┐
│                                           │
│  messages → LLM（带工具列表）              │
│     │                                     │
│     ├── finish="tool_calls"               │
│     │   → geocode("北京") → 经纬度         │
│     │   → 结果回传 → 继续循环              │
│     │                                     │
│     └── finish="stop"                     │
│         → 返回最终答案                     │
└───────────────────────────────────────────┘
```

### 核心设计原则

| 原则 | 说明 |
|------|------|
| **决策权在 LLM** | agent.py 只执行，不决策。LLM 自己判断何时调工具 |
| **工具是黑盒** | LLM 只看工具说明书（name/description/parameters），不关心实现 |
| **注册即用** | 加工具只需写函数 + 注册，不改 agent.py 一行代码 |

## 工具列表

| 工具 | 输入 | 数据源 | 说明 |
|------|------|--------|------|
| `geocode` | 城市名/地址 | Open-Meteo（免费） | 地址 → 经纬度。支持完整地址（如"河南郑州金水区"），三级降级查询 |
| `get_weather` | lat, lon | GFS 全球预报 | 气温/体感/湿度/风速/云量/气压/天气现象 |

### geocode 智能地址解析

`geocode` 对含省/市/区的完整地址（如 "河南郑州金水区"）会自动降级查询：

| 步骤 | 策略 | 示例 |
|------|------|------|
| 第 1 步 | 原样查询 | `geocode("河南郑州金水区")` |
| 第 2 步 | 剥离区县级后缀后重试 | `geocode("河南郑州金水")` → 去掉 "区" |
| 第 3 步 | 提取纯城市名重试 | `geocode("郑州")` → 通过地址解析提取 |

内置 300+ 中国地级市名称列表，支持省级简称（如 "河南" 和 "河南省" 均可），正确处理直辖市歧义（"北京市朝阳区" → "北京"，不误识别为辽宁 "朝阳"）。

## 快速开始

### 1. 环境准备

```bash
cd weather-agent

# pyenv 自动激活虚拟环境（.python-version 已配置）
python --version  # Python 3.14.5

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置 API Key

```bash
cp .env.example .env
# 编辑 .env，填入 LLM_API_KEY 和 LLM_BASE_URL
```

### 3. 运行

```bash
# 命令行传参
python src/main.py 帮我查一下今天北京天气

# 交互式输入
python src/main.py
```

## 查看执行日志

每次运行，详细的执行流程会记录到 `logs/agent.log`：

```bash
# 终端 1：运行 Agent（只看到最终答案）
python src/main.py 查北京天气

# 终端 2：实时查看完整执行流程
tail -f logs/agent.log
```

日志会记录：

| 记录内容 | 学习价值 |
|----------|----------|
| 🛠️ 已注册工具列表 | LLM 收到了哪些工具说明书 |
| 📨 每轮发给 LLM 的消息 | 消息历史如何逐轮累积 |
| ⬅️ LLM 原始响应（finish_reason + tool_calls） | LLM 返回的原始 JSON 决策 |
| 🔧 工具执行（名称 + 参数 + 返回结果） | 工具如何被调用和执行 |

**这就是 Agent 的完整数据流**——LLM 怎么知道有工具可用、怎么决策、工具怎么被执行。

## 添加新工具

三步搞定，不改 agent.py：

```python
# 1. 写执行函数
async def send_email(to: str, subject: str, body: str) -> str:
    ...
    return "邮件已发送"

# 2. 注册
register(
    name="send_email",
    definition={...},   # OpenAI function calling 格式
    executor=send_email,
)
```

详细说明见 `docs/agent-tool-design.md`。

## 技术栈

- **语言**: Python 3.14
- **环境**: pyenv virtualenv
- **依赖**: openai（LLM 调用）、httpx（HTTP 请求）、python-dotenv（环境变量）、pytest + pytest-asyncio（测试）
- **LLM**: 兼容 OpenAI 接口的任意模型（DeepSeek / 通义千问 / 豆包 / OpenAI）

## 运行测试

```bash
cd weather-agent
pytest tests/ -v
```

测试覆盖 `_extract_city_name`（地址解析）、`_format_geocode_result`（结果格式化）、`geocode`（三级降级流程），共 39 个用例。

## 学习路径

1. 阅读 `docs/agent-tool-design.md` → 理解 Agent Tool 的设计思想
2. 阅读 `src/tools.py` → 理解工具如何定义和注册
3. 阅读 `src/agent.py` → 理解 Agent 核心循环
4. 阅读 `src/logger.py` → 理解日志双输出机制
5. 阅读 `src/main.py` → 理解如何串联
6. 阅读 `tests/test_tools.py` → 理解如何用 pytest 测试工具
7. 动手加一个新工具 → 巩固理解

---

> 这个项目的核心代码不到 150 行。Agent 不是魔法，就是一个 while 循环里调 LLM + 执行函数。
