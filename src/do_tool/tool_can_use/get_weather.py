from src.do_tool.tool_can_use.base_tool import BaseTool, register_tool
import aiohttp
import json

class GetWeatherTool(BaseTool):
    name = "get_weather"
    description = "查询指定城市的当天天气情况。"
    parameters = {
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "description": "要查询天气的城市名称（如：北京、上海、广州）"
            }
        },
        "required": ["city"]
    }

    async def execute(self, function_args, message_txt=""):
        city = function_args.get("city")
        if not city:
            return {"name": self.name, "content": "请提供城市名称。"}

        # 请在此处填写您的和风天气 API KEY
        API_KEY = "YOUR_API_KEY_HERE"  # <-- 在这里填写和风天气的API KEY
        
        # 先通过城市搜索API获取城市ID
        search_url = f"https://geoapi.qweather.com/v2/city/lookup?location={city}&key={API_KEY}"
        
        try:
            async with aiohttp.ClientSession() as session:
                # 获取城市ID
                async with session.get(search_url) as resp:
                    if resp.status != 200:
                        return {"name": self.name, "content": f"无法获取{city}的城市信息（状态码: {resp.status}）"}
                    search_data = await resp.json()
                    if search_data.get("code") != "200" or not search_data.get("location"):
                        return {"name": self.name, "content": f"未找到城市：{city}"}
                    
                    location = search_data["location"][0]
                    city_id = location["id"]
                    city_name = location["name"]
                    
                # 获取实时天气
                weather_url = f"https://devapi.qweather.com/v7/weather/now?location={city_id}&key={API_KEY}"
                async with session.get(weather_url) as resp:
                    if resp.status != 200:
                        return {"name": self.name, "content": f"无法获取{city_name}的天气信息（状态码: {resp.status}）"}
                    weather_data = await resp.json()
                    
                    if weather_data.get("code") != "200":
                        return {"name": self.name, "content": f"获取天气信息失败：{weather_data.get('code')}"}
                    
                    now = weather_data["now"]
                    result = (
                        f"{city_name}当前天气：\n"
                        f"天气：{now['text']}\n"
                        f"温度：{now['temp']}°C\n"
                        f"体感温度：{now['feelsLike']}°C\n"
                        f"湿度：{now['humidity']}%\n"
                        f"风向：{now['windDir']}\n"
                        f"风力等级：{now['windScale']}级"
                    )
                    return {"name": self.name, "content": result}
                    
        except Exception as e:
            return {"name": self.name, "content": f"查询天气时发生错误: {str(e)}"}

# 注册工具
register_tool(GetWeatherTool) 