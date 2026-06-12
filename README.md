# weather-agent

> 从零手写的 AI Agent，理解 Agent 核心循环的最佳实践项目。

用户说"查北京天气" → Agent 自动串联 geocode + 天气 API → 返回天气结果。

---

## 项目结构

```
weather-agent/
├── .python-version           # pyenv 虚拟环境（Python 3.14）
├── .env.example              # API Key 配置模板
├── requirements.txt          # openai + httpx + python-dotenv
├── docs/
│   └── agent-tool-design.md  # Agent Tool 设计指南（教学文档）
├── src/
│   ├── tools.py              # 工具定义 + 注册 + 执行
│   ├── agent.py              # Agent 核心循环
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
| `geocode` | 城市名 | Open-Meteo（免费） | 城市名 → 经纬度 |
| `get_weather` | lat, lon | GFS 全球预报 | 气温/体感/湿度/风速/云量/气压/天气现象 |

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
- **依赖**: openai（LLM 调用）、httpx（HTTP 请求）、python-dotenv（环境变量）
- **LLM**: 兼容 OpenAI 接口的任意模型（DeepSeek / 通义千问 / 豆包 / OpenAI）

## 学习路径

1. 阅读 `docs/agent-tool-design.md` → 理解 Agent Tool 的设计思想
2. 阅读 `src/tools.py` → 理解工具如何定义和注册
3. 阅读 `src/agent.py` → 理解 Agent 核心循环
4. 阅读 `src/main.py` → 理解如何串联
5. 动手加一个新工具 → 巩固理解

---

> 这个项目的核心代码不到 150 行。Agent 不是魔法，就是一个 while 循环里调 LLM + 执行函数。
