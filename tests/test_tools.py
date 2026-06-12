"""
tests/test_tools.py — geocode 工具测试（pytest 风格）

测试覆盖：
  - _extract_city_name: 城市名提取逻辑
  - geocode: 三级降级查询流程
  - _format_geocode_result: 结果格式化
"""

import json

import pytest

from src.tools import _extract_city_name, _format_geocode_result, geocode


# ============================================================
# _extract_city_name 测试
# ============================================================

class TestExtractCityName:
    """从中国地址字符串中提取城市名"""

    @pytest.mark.parametrize(
        "addr, expected",
        [
            ("河南郑州金水区", "郑州"),
            ("广东省广州市天河区", "广州"),
            ("江苏省南京市鼓楼区", "南京"),
            ("广西南宁青秀区", "南宁"),
            ("浙江省杭州市西湖区", "杭州"),
            ("湖北省武汉市江夏区", "武汉"),
            ("河南省洛阳市涧西区", "洛阳"),
            ("广东省深圳市南山区", "深圳"),
            ("福建省厦门市思明区", "厦门"),
        ],
    )
    def test_province_city_district(self, addr, expected):
        """省+市+区 格式"""
        assert _extract_city_name(addr) == expected

    @pytest.mark.parametrize(
        "addr, expected",
        [
            ("北京市朝阳区", "北京"),
            ("上海浦东新区", "上海"),
            ("重庆渝中区", "重庆"),
            ("天津河西区", "天津"),
        ],
    )
    def test_direct_municipality_with_district(self, addr, expected):
        """直辖市+区 格式（不能误匹配区名）"""
        assert _extract_city_name(addr) == expected

    @pytest.mark.parametrize(
        "addr, expected",
        [
            ("山东青岛", "青岛"),
            ("广东深圳", "深圳"),
            ("江苏南京", "南京"),
            ("浙江杭州", "杭州"),
            ("河南洛阳", "洛阳"),
        ],
    )
    def test_province_abbreviation(self, addr, expected):
        """省份简称（不带"省"字）"""
        assert _extract_city_name(addr) == expected

    @pytest.mark.parametrize(
        "addr, expected",
        [
            ("陕西省西安市", "西安"),
            ("吉林省长春市", "长春"),
            ("湖南省长沙市", "长沙"),
        ],
    )
    def test_province_full_city_full(self, addr, expected):
        """省全称+市全称（带"市"字）"""
        assert _extract_city_name(addr) == expected

    @pytest.mark.parametrize(
        "addr, expected",
        [
            ("深圳", "深圳"),
            ("成都", "成都"),
            ("杭州", "杭州"),
            ("西安", "西安"),
        ],
    )
    def test_city_only(self, addr, expected):
        """纯城市名"""
        assert _extract_city_name(addr) == expected

    @pytest.mark.parametrize(
        "addr, expected",
        [
            ("黑龙江省哈尔滨市道里区", "哈尔滨"),
            ("内蒙古呼和浩特新城区", "呼和浩特"),
            ("新疆乌鲁木齐天山", "乌鲁木齐"),
        ],
    )
    def test_long_city_names(self, addr, expected):
        """长城市名（3 字及以上）"""
        assert _extract_city_name(addr) == expected

    def test_ambiguous_district_name(self):
        """辽宁朝阳市 vs 北京朝阳区 歧义"""
        assert _extract_city_name("辽宁省朝阳市") == "朝阳"
        assert _extract_city_name("北京市朝阳区") == "北京"

    @pytest.mark.parametrize(
        "addr",
        ["随便写的东西", ""],
    )
    def test_unrecognized_returns_none(self, addr):
        """无法识别的地址返回 None"""
        assert _extract_city_name(addr) is None


# ============================================================
# _format_geocode_result 测试
# ============================================================

class TestFormatGeocodeResult:
    """地理信息格式化为 JSON 字符串"""

    def test_basic_format(self):
        result = _format_geocode_result({
            "latitude": 34.75778,
            "longitude": 113.64861,
            "name": "郑州",
            "country": "中国",
        })
        parsed = json.loads(result)
        assert parsed["lat"] == 34.75778
        assert parsed["lon"] == 113.64861
        assert parsed["name"] == "郑州"
        assert parsed["country"] == "中国"

    def test_missing_country(self):
        result = _format_geocode_result({
            "latitude": 35.0,
            "longitude": 139.0,
            "name": "Tokyo",
        })
        parsed = json.loads(result)
        assert parsed["country"] == "未知"


# ============================================================
# geocode 三级降级流程测试
# ============================================================

class TestGeocode:
    """geocode 函数的完整流程"""

    @staticmethod
    def _mock_api_response(name: str, lat: float, lon: float) -> dict:
        """构造模拟的 API 返回"""
        return {
            "latitude": lat,
            "longitude": lon,
            "name": name,
            "country": "中国",
        }

    # ── 第 1 步：原样查询成功 ──

    @pytest.mark.asyncio
    async def test_step1_direct_match(self, monkeypatch):
        """城市名直接命中"""
        import src.tools as tools_mod

        calls = []

        async def fake_query(name):
            calls.append(name)
            return self._mock_api_response("郑州", 34.76, 113.65)

        monkeypatch.setattr(tools_mod, "_query_geocode", fake_query)

        result = await geocode("郑州")
        parsed = json.loads(result)

        assert parsed["name"] == "郑州"
        assert calls == ["郑州"]

    # ── 第 2 步：剥离区级后缀 ──

    @pytest.mark.asyncio
    async def test_step2_strip_district(self, monkeypatch):
        """"河南郑州金水区" → 去掉 "区" → 第 2 步命中"""
        import src.tools as tools_mod

        calls = []

        async def fake_query(name):
            calls.append(name)
            if name == "河南郑州金水区":
                return None
            if name == "河南郑州金水":
                return self._mock_api_response("郑州", 34.76, 113.65)
            return None

        monkeypatch.setattr(tools_mod, "_query_geocode", fake_query)

        result = await geocode("河南郑州金水区")
        parsed = json.loads(result)

        assert parsed["name"] == "郑州"
        assert len(calls) == 2

    @pytest.mark.asyncio
    async def test_step2_strip_xian(self, monkeypatch):
        """"河北省石家庄正定县" → 去掉 "县" → 第 2 步命中"""
        import src.tools as tools_mod

        calls = []

        async def fake_query(name):
            calls.append(name)
            if name == "河北省石家庄正定县":
                return None
            if name == "河北省石家庄正定":
                return self._mock_api_response("石家庄", 38.04, 114.51)
            return None

        monkeypatch.setattr(tools_mod, "_query_geocode", fake_query)

        result = await geocode("河北省石家庄正定县")
        parsed = json.loads(result)
        assert parsed["name"] == "石家庄"

    # ── 第 3 步：提取纯城市名 ──

    @pytest.mark.asyncio
    async def test_step3_extract_city_name(self, monkeypatch):
        """"广东广州天河区" → 第 1、2 步都失败 → 第 3 步提取 "广州" 命中"""
        import src.tools as tools_mod

        calls = []

        async def fake_query(name):
            calls.append(name)
            if name == "广东广州天河区":
                return None
            if name == "广东广州天河":
                return None
            if name == "广州":
                return self._mock_api_response("广州", 23.13, 113.26)
            return None

        monkeypatch.setattr(tools_mod, "_query_geocode", fake_query)

        result = await geocode("广东广州天河区")
        parsed = json.loads(result)
        assert parsed["name"] == "广州"
        assert len(calls) == 3

    @pytest.mark.asyncio
    async def test_step3_direct_municipality(self, monkeypatch):
        """"北京市朝阳区" → 第 1、2 步失败 → 第 3 步提取 "北京" 命中"""
        import src.tools as tools_mod

        calls = []

        async def fake_query(name):
            calls.append(name)
            if name == "北京市朝阳区":
                return None
            if name == "北京市朝阳":
                return None
            if name == "北京":
                return self._mock_api_response("北京", 39.9, 116.4)
            return None

        monkeypatch.setattr(tools_mod, "_query_geocode", fake_query)

        result = await geocode("北京市朝阳区")
        parsed = json.loads(result)
        assert parsed["name"] == "北京"

    # ── 全部失败 ──

    @pytest.mark.asyncio
    async def test_all_steps_fail(self, monkeypatch):
        """所有步骤都失败，返回 error"""
        import src.tools as tools_mod

        async def fake_query(name):
            return None

        monkeypatch.setattr(tools_mod, "_query_geocode", fake_query)

        result = await geocode("不存在的城市名xyz")
        parsed = json.loads(result)

        assert "error" in parsed
        assert "不存在的城市名xyz" in parsed["error"]
