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

# 中国主要城市名（地级市/直辖市级）—— 用于模糊匹配
_CITY_NAMES = [
    # 直辖市
    "北京", "上海", "天津", "重庆",
    # 省会城市
    "石家庄", "太原", "呼和浩特", "沈阳", "长春", "哈尔滨",
    "南京", "杭州", "合肥", "福州", "南昌", "济南", "郑州",
    "武汉", "长沙", "广州", "南宁", "海口", "成都", "贵阳",
    "昆明", "拉萨", "西安", "兰州", "西宁", "银川", "乌鲁木齐",
    # 副省级城市 & 重要地级市
    "大连", "青岛", "宁波", "厦门", "深圳",
    "苏州", "无锡", "常州", "徐州", "南通", "扬州", "镇江", "泰州", "盐城", "淮安", "连云港", "宿迁",
    "温州", "嘉兴", "湖州", "绍兴", "金华", "衢州", "舟山", "台州", "丽水",
    "珠海", "汕头", "佛山", "韶关", "湛江", "肇庆", "江门", "茂名", "惠州", "梅州", "汕尾", "河源", "阳江", "清远", "东莞", "中山", "潮州", "揭阳", "云浮",
    "桂林", "柳州", "北海", "梧州", "钦州", "贵港", "玉林", "百色", "贺州", "河池", "来宾", "崇左", "防城港",
    "三亚", "三沙", "儋州",
    "唐山", "保定", "邯郸", "秦皇岛", "张家口", "承德", "沧州", "廊坊", "衡水", "邢台",
    "大同", "阳泉", "长治", "晋城", "朔州", "晋中", "运城", "忻州", "临汾", "吕梁",
    "包头", "乌海", "赤峰", "通辽", "鄂尔多斯", "呼伦贝尔", "巴彦淖尔", "乌兰察布",
    "鞍山", "抚顺", "本溪", "丹东", "锦州", "营口", "阜新", "辽阳", "盘锦", "铁岭", "朝阳", "葫芦岛",
    "吉林", "四平", "辽源", "通化", "白山", "松原", "白城", "延边",
    "齐齐哈尔", "鸡西", "鹤岗", "双鸭山", "大庆", "伊春", "佳木斯", "七台河", "牡丹江", "黑河", "绥化",
    "芜湖", "蚌埠", "淮南", "马鞍山", "淮北", "铜陵", "安庆", "黄山", "滁州", "阜阳", "宿州", "六安", "亳州", "池州", "宣城",
    "泉州", "漳州", "南平", "龙岩", "宁德", "莆田", "三明",
    "景德镇", "萍乡", "九江", "新余", "鹰潭", "赣州", "吉安", "宜春", "抚州", "上饶",
    "淄博", "枣庄", "东营", "烟台", "潍坊", "济宁", "泰安", "威海", "日照", "临沂", "德州", "聊城", "滨州", "菏泽",
    "洛阳", "开封", "平顶山", "安阳", "鹤壁", "新乡", "焦作", "濮阳", "许昌", "漯河", "三门峡", "南阳", "商丘", "信阳", "周口", "驻马店",
    "黄石", "十堰", "宜昌", "襄阳", "鄂州", "荆门", "孝感", "荆州", "黄冈", "咸宁", "随州", "恩施",
    "株洲", "湘潭", "衡阳", "邵阳", "岳阳", "常德", "张家界", "益阳", "郴州", "永州", "怀化", "娄底", "湘西",
    "自贡", "攀枝花", "泸州", "德阳", "绵阳", "广元", "遂宁", "内江", "乐山", "南充", "眉山", "宜宾", "广安", "达州", "雅安", "巴中", "资阳",
    "遵义", "六盘水", "安顺", "毕节", "铜仁",
    "曲靖", "玉溪", "保山", "昭通", "丽江", "普洱", "临沧",
    "宝鸡", "咸阳", "渭南", "延安", "汉中", "榆林", "安康", "商洛",
    "嘉峪关", "金昌", "白银", "天水", "武威", "张掖", "平凉", "酒泉", "庆阳", "定西", "陇南",
    "海东",
    "石嘴山", "吴忠", "固原", "中卫",
    "克拉玛依", "吐鲁番", "哈密",
    # 港澳台
    "香港", "澳门", "台北", "高雄", "台中", "台南", "基隆", "新竹", "嘉义",
]


# 省级前缀 → 完整省名映射（支持简称）
_PROVINCE_PREFIX_MAP: dict[str, str] = {
    "北京": "北京", "北京市": "北京",
    "天津": "天津", "天津市": "天津",
    "上海": "上海", "上海市": "上海",
    "重庆": "重庆", "重庆市": "重庆",
    "河北": "河北", "河北省": "河北",
    "山西": "山西", "山西省": "山西",
    "辽宁": "辽宁", "辽宁省": "辽宁",
    "吉林": "吉林", "吉林省": "吉林",
    "黑龙江": "黑龙江", "黑龙江省": "黑龙江",
    "江苏": "江苏", "江苏省": "江苏",
    "浙江": "浙江", "浙江省": "浙江",
    "安徽": "安徽", "安徽省": "安徽",
    "福建": "福建", "福建省": "福建",
    "江西": "江西", "江西省": "江西",
    "山东": "山东", "山东省": "山东",
    "河南": "河南", "河南省": "河南",
    "湖北": "湖北", "湖北省": "湖北",
    "湖南": "湖南", "湖南省": "湖南",
    "广东": "广东", "广东省": "广东",
    "海南": "海南", "海南省": "海南",
    "四川": "四川", "四川省": "四川",
    "贵州": "贵州", "贵州省": "贵州",
    "云南": "云南", "云南省": "云南",
    "陕西": "陕西", "陕西省": "陕西",
    "甘肃": "甘肃", "甘肃省": "甘肃",
    "青海": "青海", "青海省": "青海",
    "台湾": "台湾", "台湾省": "台湾",
    "内蒙古": "内蒙古", "内蒙古自治区": "内蒙古",
    "广西": "广西", "广西壮族自治区": "广西",
    "西藏": "西藏", "西藏自治区": "西藏",
    "宁夏": "宁夏", "宁夏回族自治区": "宁夏",
    "新疆": "新疆", "新疆维吾尔自治区": "新疆",
    "香港": "香港", "香港特别行政区": "香港",
    "澳门": "澳门", "澳门特别行政区": "澳门",
}

# 直辖市集合（这些省份名本身就是城市名）
_DIRECT_MUNICIPALITIES = {"北京", "天津", "上海", "重庆"}


def _extract_city_name(address: str) -> str | None:
    """
    从中国地址字符串中提取城市名。
    例如："河南郑州金水区" → "郑州"、"北京市朝阳区" → "北京"、"广东省广州市天河区" → "广州"
    """
    s = address
    city_from_prefix: str | None = None

    # 第 1 步：剥离省级前缀（支持简称和全称）
    for prefix in sorted(_PROVINCE_PREFIX_MAP, key=len, reverse=True):
        if s.startswith(prefix):
            province = _PROVINCE_PREFIX_MAP[prefix]
            s = s[len(prefix):]
            # 如果是直辖市，省份名就是城市名
            if province in _DIRECT_MUNICIPALITIES:
                city_from_prefix = province
            break

    # 第 2 步：在剩余字符串中按长度降序匹配城市名
    for city in sorted(_CITY_NAMES, key=len, reverse=True):
        if s.startswith(city):
            # 检查匹配到的城市名后面是否跟着区县级后缀
            # 如 "朝阳区" 中的 "朝阳" — 如果已剥离了直辖市前缀，则不应匹配
            after = s[len(city):]
            if after.startswith(("区", "县", "镇", "乡", "街道", "路", "村", "新区", "开发区")):
                # 如果是从直辖市剥离出来的，说明这是区名不是城市名，用直辖市名
                if city_from_prefix:
                    return city_from_prefix
                continue
            return city

    # 第 3 步：如果剥离了直辖市前缀但剩余部分没匹配到城市，用直辖市名
    if city_from_prefix:
        return city_from_prefix

    return None


async def _query_geocode(name: str) -> dict | None:
    """调用 Open-Meteo Geocoding API，返回第一条结果或 None"""
    url = "https://geocoding-api.open-meteo.com/v1/search"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            url,
            params={"name": name, "count": 1, "language": "zh", "format": "json"},
        )
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results")
        return results[0] if results else None


def _format_geocode_result(r: dict) -> str:
    """将 API 返回的地理信息格式化为 JSON 字符串"""
    return (
        f'{{"lat": {r["latitude"]}, "lon": {r["longitude"]}, '
        f'"name": "{r["name"]}", "country": "{r.get("country", "未知")}"}}'
    )


async def geocode(city: str) -> str:
    """
    城市名/地址 → 经纬度（Open-Meteo Geocoding API，免费无需 Key）

    支持城市名、含省市区前缀的完整地址（如"河南郑州金水区"），
    会自动提取城市名进行查询。

    返回格式：JSON 字符串 {"lat": 39.9, "lon": 116.4, "name": "北京", "country": "中国"}
    """

    # 第 1 步：原样查询
    result = await _query_geocode(city)
    if result:
        return _format_geocode_result(result)

    # 第 2 步：去掉区县级后缀后重试（如 "河南郑州金水区" → "河南郑州金水"）
    for suffix in ["新区", "开发区", "高新区", "区", "县", "镇", "乡", "街道"]:
        if city.endswith(suffix):
            stripped = city[: -len(suffix)]
            result = await _query_geocode(stripped)
            if result:
                return _format_geocode_result(result)

    # 第 3 步：提取纯城市名重试（如 "河南郑州金水区" → "郑州"）
    city_name = _extract_city_name(city)
    if city_name and city_name != city:
        result = await _query_geocode(city_name)
        if result:
            return _format_geocode_result(result)

    return f'{{"error": "未找到城市 {city}，请确认城市名称"}}'


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
            "description": "将城市名称或地址转换为经纬度坐标，返回 lat（纬度）、lon（经度）、城市名、国家。支持完整地址（如：河南郑州金水区、北京市朝阳区）",
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
