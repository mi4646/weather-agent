# Agent Tool 设计指南

> 本文档面向 AI Agent 初学者，从通用概念出发，最终落地到本项目的具体实现。

---

## 目录

1. [什么是 Agent Tool](#1-什么是-agent-tool)
2. [Tool 的两层结构](#2-tool-的两层结构)
3. [Tool 的定义格式](#3-tool-的定义格式)
4. [Tool 的实现方式](#4-tool-的实现方式)
5. [Tool 的注册与管理](#5-tool-的注册与管理)
6. [本项目实践](#6-本项目实践)
7. [常见问题](#7-常见问题)

---

## 1. 什么是 Agent Tool

### 直观理解

AI Agent 和普通聊天机器人的核心区别在于：**Agent 能"做事"，不只是"说话"。**

```
普通聊天机器人：
  用户："今天北京天气怎么样？"
  机器人："抱歉，我无法获取实时天气信息。"

AI Agent：
  用户："今天北京天气怎么样？"
  Agent：决定调用 get_weather 工具 → 拿到数据 → "北京今天晴，32°C"
```

**Tool（工具）就是 Agent 的"手"** —— LLM 是大脑（负责理解和决策），Tool 是手（负责执行具体操作）。

### Tool 的本质

Tool 是一个**黑盒函数**：

```
输入（参数） → [ 工具内部实现 ] → 输出（结果）
```

Agent 只关心"输入什么、输出什么"，不关心内部怎么实现。这意味着：

- 同一个 Tool，内部可以随时换实现方式
- 换实现不影响 Agent 的任何代码
- 你可以先用 Mock 数据跑通，再换真实 API

---

## 2. Tool 的两层结构

每个 Tool 由两层组成，缺一不可：

```
┌──────────────────────────────────────────┐
│  外层：说明书（Definition / Schema）       │  ← 给 LLM 看的
│  - 名称（name）                           │
│  - 描述（description）                    │
│  - 参数定义（parameters）                  │
├──────────────────────────────────────────┤
│  内层：执行函数（Executor）                │  ← 系统执行的
│  - 实际的 Python/JS/... 代码              │
│  - 可以是 API 调用、数据库查询、计算...    │
└──────────────────────────────────────────┘
```

### 为什么需要两层？

**LLM 不能直接调用你的代码。** LLM 只能输出文本。流程是这样的：

```
1. LLM 看到说明书 → 决定"我要调 get_weather"
2. LLM 输出 JSON → {"name": "get_weather", "arguments": {"city": "北京"}}
3. 你的系统解析这个 JSON → 找到对应的执行函数 → 调用 get_weather("北京")
4. 执行结果返回给 LLM → LLM 用自然语言总结
```

说明书是 LLM 和你的代码之间的**协议**。没有它，LLM 不知道有哪些工具、工具能干什么。

---

## 3. Tool 的定义格式

### OpenAI Function Calling 格式（行业标准）

目前主流 LLM（OpenAI、DeepSeek、通义千问、豆包等）都兼容这个格式：

```json
{
  "type": "function",
  "function": {
    "name": "get_weather",
    "description": "查询指定城市的天气，返回天气状况、温度、湿度、风力等信息",
    "parameters": {
      "type": "object",
      "properties": {
        "city": {
          "type": "string",
          "description": "城市名称，如：北京、上海、广州"
        }
      },
      "required": ["city"]
    }
  }
}
```

### 各字段详解

| 字段 | 必须 | 说明 | 注意事项 |
|------|:----:|------|----------|
| `type` | ✅ | 固定为 `"function"` | 不要改 |
| `function.name` | ✅ | 工具名称，唯一标识 | 用 snake_case，见名知意 |
| `function.description` | ✅ | 描述工具功能 | **这是最重要的字段！** LLM 靠它判断是否该用这个工具 |
| `function.parameters` | ✅ | 参数 JSON Schema | 遵循 [JSON Schema](https://json-schema.org/) 规范 |
| `parameters.type` | ✅ | 固定为 `"object"` | 参数总是以对象形式传入 |
| `parameters.properties` | ✅ | 每个参数的定义 | 包含 type、description |
| `parameters.required` | ❌ | 必填参数列表 | 没有就不填 |

### description 怎么写？（关键技巧）

`description` 是 LLM 选择工具的唯一依据。写好 description 的要点：

| ✅ 好的 description | ❌ 差的 description |
|-----|-----|
| "查询指定城市的天气，返回天气状况、温度、湿度、风力等信息" | "查天气" |
| "向指定手机号发送短信验证码，6 位数字，有效期 5 分钟" | "发短信" |
| "根据订单 ID 查询订单状态，包括：待支付、已支付、已发货、已完成" | "查订单" |

**原则：说清楚"什么时候用"和"返回什么"。**

### parameters 怎么写？

每个参数也是一个"迷你说明书"：

```json
{
  "city": {
    "type": "string",
    "description": "城市名称，如：北京、上海、广州"
  }
}
```

- `type` 支持：`"string"`, `"number"`, `"integer"`, `"boolean"`, `"array"`, `"object"`
- `description` 要包含示例值，帮助 LLM 正确提取参数
- `enum` 可以限制可选值：`"enum": ["北京", "上海", "广州"]`

---

## 4. Tool 的实现方式

Tool 的内部实现**完全自由**，LLM 不关心。以下是常见方式：

### 方式一：Mock 数据（学习/测试阶段）

```python
async def get_weather(city: str) -> str:
    data = {"北京": "晴，32°C", "上海": "多云，28°C"}
    return data.get(city, "未找到该城市")
```

### 方式二：HTTP API 调用

```python
async def get_weather(city: str) -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"https://api.weather.com/v1?city={city}")
        return resp.json()["summary"]
```

### 方式三：Shell 命令

```python
import subprocess

def get_weather(city: str) -> str:
    result = subprocess.run(
        ["curl", f"wttr.in/{city}?format=3"],
        capture_output=True, text=True
    )
    return result.stdout.strip()
```

### 方式四：数据库查询

```python
async def get_weather(city: str) -> str:
    async with db.connect() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM weather WHERE city = $1", city
        )
        return f"{row['weather']}, {row['temp']}°C"
```

### 方式五：本地文件读取

```python
import json

async def get_weather(city: str) -> str:
    with open("weather_cache.json") as f:
        cache = json.load(f)
    return cache.get(city, "无数据")
```

### 方式六：硬件设备

```python
async def get_temperature(room: str) -> str:
    sensor = SensorRegistry.get(room)
    temp = await sensor.read()
    return f"{room} 温度：{temp}°C"
```

**关键领悟**：换实现方式只需改执行函数内部，Tool 的 definition 和 Agent 的代码完全不用动。

---

## 5. Tool 的注册与管理

### 注册模式

当工具多了（5 个、10 个、50 个），需要一个统一的注册中心：

```python
# 注册表：key = 工具名，value = {definition, execute}
TOOLS: dict[str, dict] = {}

def register(name: str, definition: dict, executor: callable):
    """注册一个工具"""
    TOOLS[name] = {
        "definition": definition,
        "execute": executor,
    }

# 使用
register("get_weather", weather_definition, get_weather_func)
register("send_email", email_definition, send_email_func)
```

### 为什么用注册模式？

| 好处 | 说明 |
|------|------|
| **统一管理** | 所有工具在一个地方，一眼看清 Agent 有哪些能力 |
| **动态查询** | Agent 循环通过 `TOOLS[name]` 查找执行函数 |
| **易于扩展** | 加工具只需调 `register()`，不改其他代码 |
| **可测试** | 测试时可以注入 Mock 工具 |

### 两种暴露给 Agent 的方式

| 方式 | 操作 | 适用场景 |
|------|------|----------|
| 全部暴露 | `list(TOOLS.values())` 全部发给 LLM | 工具少（< 10 个） |
| 按需暴露 | 根据场景筛选部分工具 | 工具多，或不同场景用不同工具集 |

---

## 6. 本项目实践

### 项目结构

```
weather-agent/
└── src/
    └── tools.py    ← 工具定义 + 注册 + 执行，都在这里
```

### 代码解析

#### 6.1 注册函数

```python
TOOLS: dict[str, dict[str, Any]] = {}

def register(name: str, definition: ToolDefinition, executor: ToolExecutor) -> None:
    TOOLS[name] = {
        "definition": definition,  # 给 LLM 看的说明书
        "execute": executor,       # 实际执行的函数
    }
```

#### 6.2 获取所有说明书

```python
def get_definitions() -> list[ToolDefinition]:
    """Agent 调用此函数，拿到所有工具说明书发给 LLM"""
    return [t["definition"] for t in TOOLS.values()]
```

#### 6.3 根据名称查找执行函数

```python
def get_executor(name: str) -> ToolExecutor | None:
    """LLM 返回工具名后，Agent 调用此函数找到对应的执行函数"""
    tool = TOOLS.get(name)
    return tool["execute"] if tool else None
```

#### 6.4 添加新工具的步骤

假设你要添加一个"发邮件"工具：

```python
# 步骤 1：写执行函数
async def send_email(to: str, subject: str, body: str) -> str:
    # 实际发送逻辑
    return f"邮件已发送至 {to}"

# 步骤 2：写说明书
EMAIL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "send_email",
        "description": "发送邮件。to: 收件人邮箱, subject: 主题, body: 正文",
        "parameters": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "收件人邮箱地址"},
                "subject": {"type": "string", "description": "邮件主题"},
                "body": {"type": "string", "description": "邮件正文内容"},
            },
            "required": ["to", "subject", "body"],
        },
    },
}

# 步骤 3：注册
register("send_email", EMAIL_DEFINITION, send_email)
```

**完成！** Agent 自动具备发邮件能力，不需要改 agent.py 一行代码。

---

## 7. 常见问题

### Q1: 工具名（name）可以和函数名不同吗？

可以。`name` 是给 LLM 看的标识符，`execute` 是实际的 Python 函数。但建议保持一致，减少心智负担。

### Q2: 一个工具可以有多个参数吗？

可以。在 `parameters.properties` 里定义多个参数，`required` 里列出必填项即可。

### Q3: LLM 调用工具时参数填错了怎么办？

LLM 偶尔会"幻觉"，比如把城市名填成日期。应对方法：
- 在 `description` 里给示例值
- 在执行函数里做参数校验
- Agent 循环里加 try/except 兜底

### Q4: 工具返回结果格式有要求吗？

返回字符串即可。LLM 会自己理解字符串内容并总结给用户。如果你想返回结构化数据，序列化成 JSON 字符串，在 description 里说明格式。

### Q5: 同步函数还是异步函数？

如果你的工具涉及网络请求（API 调用），用 `async`，避免阻塞 Agent 循环。如果只是本地计算，同步也可以。本项目统一用 `async`，保持一致性。

---

## 参考资料

- [OpenAI Function Calling 文档](https://platform.openai.com/docs/guides/function-calling)
- [JSON Schema 规范](https://json-schema.org/)
- [Anthropic Tool Use 文档](https://docs.anthropic.com/en/docs/build-with-claude/tool-use)

---

> 下一步：阅读 `agent.py` 了解 Agent 如何使用这些工具。
