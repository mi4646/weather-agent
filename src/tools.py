"""
tools.py — Agent 工具定义与执行

每个工具包含两部分：
1. definition: 给 LLM 看的"说明书"（OpenAI function calling 格式）
2. execute:   实际执行的 Python 函数

添加新工具只需三步：
① 写一个 async 函数
② 写一份 definition
③ 注册到 TOOLS 字典
"""

import httpx
from typing import Any, Callable, Coroutine

# ── 工具类型定义 ──────────────────────────────────────────

# 每个工具的"说明书"（符合 OpenAI tool 格式）
ToolDefinition = dict[str, Any]

# 工具执行函数签名：接收参数 → 返回结果字符串
ToolExecutor = Callable[..., Coroutine[Any, Any, str]]


# ── 工具注册表 ────────────────────────────────────────────

# 所有可用工具，key 是工具名
TOOLS: dict[str, dict[str, Any]] = {}


def register(name: str, definition: ToolDefinition, executor: ToolExecutor) -> None:
    """注册一个工具"""
    TOOLS[name] = {
        "definition": definition,
        "execute": executor,
    }


def get_definitions() -> list[ToolDefinition]:
    """获取所有工具的说明书列表（发送给 LLM）"""
    return [t["definition"] for t in TOOLS.values()]


def get_executor(name: str) -> ToolExecutor | None:
    """根据工具名获取执行函数"""
    tool = TOOLS.get(name)
    return tool["execute"] if tool else None


# ── 具体工具实现 ──────────────────────────────────────────

async def geocode(city: str) -> str:
    """
    城市名 → 经纬度（Open-Meteo Geocoding API，免费无需 Key）

    返回格式：JSON 字符串 {"lat": 39.9, "lon": 116.4, "name": "北京", "country": "中国"}
    """
    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {"name": city, "count": 1, "language": "zh", "format": "json"}

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    results = data.get("results")
    if not results:
        return f'{{"error": "未找到城市 {city}，请确认城市名称"}}'

    r = results[0]
    return (
        f'{{"lat": {r["latitude"]}, "lon": {r["longitude"]}, '
        f'"name": "{r["name"]}", "country": "{r.get("country", "未知")}"}}'
    )


async def get_weather(lat: float, lon: float) -> str:
    """
    根据经纬度查询天气（GFS 全球预报数据）

    返回格式：自然语言描述的温度、体感温度、湿度、风速、天气现象
    """
    url = "https://weather.spaceroute.cn/api/weather/current"
    params = {"lat": lat, "lon": lon}

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    current = data["current"]
    return (
        f"气温 {current['t2m']}°C，体感温度 {current['feels_like']}°C，"
        f"相对湿度 {current['rh']}%，风速 {current['wind_speed']} m/s，"
        f"降水量 {current['tp']} mm，云量 {current['tcc']}%，"
        f"海平面气压 {current['prmsl']} hPa，"
        f"天气现象：{current['phenomenon']}"
    )


# ── 注册所有工具 ──────────────────────────────────────────
register(
    name="geocode",
    definition={
        "type": "function",
        "function": {
            "name": "geocode",
            "description": "将城市名称转换为经纬度坐标，返回 lat（纬度）、lon（经度）、城市名、国家",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名称，如：北京、上海、Tokyo",
                    }
                },
                "required": ["city"],
            },
        },
    },
    executor=geocode,
)

register(
    name="get_weather",
    definition={
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "根据经纬度查询当前天气，返回气温、体感温度、湿度、风速、降水量、云量、气压、天气现象",
            "parameters": {
                "type": "object",
                "properties": {
                    "lat": {
                        "type": "number",
                        "description": "纬度，范围 -90 到 90",
                    },
                    "lon": {
                        "type": "number",
                        "description": "经度，范围 -180 到 180",
                    },
                },
                "required": ["lat", "lon"],
            },
        },
    },
    executor=get_weather,
)
