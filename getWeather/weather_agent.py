"""
天气播报 Agent
使用 DeepSeek API + Function Calling 自动查天气和 AQI，综合回答用户问题。
"""

import json
import os
import requests
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# ── DeepSeek 客户端 ──────────────────────────────────────────────────────────
client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY", "your-deepseek-api-key"),
    base_url="https://api.deepseek.com",
)
MODEL = "deepseek-chat"

# ── 工具定义（JSON Schema） ──────────────────────────────────────────────────
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": (
                "获取指定城市的实时天气，包括温度、体感温度、天气描述、"
                "湿度、风速、能见度、紫外线指数。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名称，支持中文或英文，例如：北京、Shanghai",
                    }
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_aqi",
            "description": (
                "获取指定城市的空气质量指数（AQI），包括 PM2.5、PM10 等污染物数据"
                "及健康建议，判断是否适合户外运动。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名称，支持中文或英文，例如：北京、Shanghai",
                    }
                },
                "required": ["city"],
            },
        },
    },
]


# ── 工具实现 ─────────────────────────────────────────────────────────────────

def get_weather(city: str) -> dict:
    """调用 wttr.in 获取天气（免费，无需 API Key）"""
    try:
        url = f"https://wttr.in/{city}?format=j1"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        cur = data["current_condition"][0]
        # 优先取中文描述，fallback 英文
        lang_zh = cur.get("lang_zh")
        description = lang_zh[0]["value"] if lang_zh else cur["weatherDesc"][0]["value"]

        return {
            "city": city,
            "temperature_c": int(cur["temp_C"]),
            "feels_like_c": int(cur["FeelsLikeC"]),
            "description": description,
            "humidity_pct": int(cur["humidity"]),
            "wind_speed_kmph": int(cur["windspeedKmph"]),
            "wind_direction": cur["winddir16Point"],
            "visibility_km": int(cur["visibility"]),
            "uv_index": int(cur["uvIndex"]),
        }
    except Exception as e:
        return {"error": f"天气查询失败: {e}"}


def get_aqi(city: str) -> dict:
    """调用 WAQI API 获取 AQI（demo token 有速率限制，生产环境请替换）"""
    try:
        url = f"https://api.waqi.info/feed/{city}/?token=demo"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if data["status"] != "ok":
            return {"error": f"AQI 查询失败: {data.get('data', 'unknown error')}"}

        aqi_data = data["data"]
        aqi_value = aqi_data["aqi"]
        iaqi = aqi_data.get("iaqi", {})

        # AQI 等级映射
        if aqi_value <= 50:
            level, advice, outdoor_ok = "优", "空气清新，非常适合户外运动", True
        elif aqi_value <= 100:
            level, advice, outdoor_ok = "良", "空气尚可，适合一般户外活动", True
        elif aqi_value <= 150:
            level, advice, outdoor_ok = "轻度污染", "敏感人群减少户外活动，普通人可短时间运动", False
        elif aqi_value <= 200:
            level, advice, outdoor_ok = "中度污染", "建议减少户外运动，戴口罩外出", False
        elif aqi_value <= 300:
            level, advice, outdoor_ok = "重度污染", "避免户外运动，尽量留在室内", False
        else:
            level, advice, outdoor_ok = "严重污染", "严禁户外剧烈运动，关闭门窗", False

        result = {
            "city": city,
            "aqi": aqi_value,
            "level": level,
            "dominant_pollutant": aqi_data.get("dominentpol", "未知"),
            "outdoor_exercise_ok": outdoor_ok,
            "health_advice": advice,
        }
        if "pm25" in iaqi:
            result["pm25"] = iaqi["pm25"]["v"]
        if "pm10" in iaqi:
            result["pm10"] = iaqi["pm10"]["v"]

        return result
    except Exception as e:
        return {"error": f"AQI 查询失败: {e}"}


# ── 工具分发 ─────────────────────────────────────────────────────────────────

TOOL_HANDLERS = {
    "get_weather": get_weather,
    "get_aqi": get_aqi,
}


def execute_tool(name: str, arguments: str) -> str:
    handler = TOOL_HANDLERS.get(name)
    if not handler:
        return json.dumps({"error": f"未知工具: {name}"}, ensure_ascii=False)
    args = json.loads(arguments)
    result = handler(**args)
    return json.dumps(result, ensure_ascii=False)


# ── Agent 主循环 ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = (
    "你是一位专业的天气播报员兼健身顾问。"
    "当用户询问天气或户外运动建议时，你必须先调用工具获取实时数据，"
    "再基于数据给出具体、实用的建议。"
    "回答要简洁友好，包含关键数据，并给出明确的行动建议。"
)


def run_agent(user_query: str) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_query},
    ]

    print(f"\n{'='*50}")
    print(f"用户: {user_query}")
    print(f"{'='*50}")

    # agentic loop：持续执行直到模型不再调用工具
    while True:
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
        )

        msg = response.choices[0].message
        finish_reason = response.choices[0].finish_reason

        # 将助手消息追加到历史
        messages.append(msg)

        if finish_reason == "tool_calls":
            # 执行所有工具调用
            for tool_call in msg.tool_calls:
                tool_name = tool_call.function.name
                tool_args = tool_call.function.arguments
                print(f"\n[工具调用] {tool_name}({tool_args})")

                result = execute_tool(tool_name, tool_args)
                print(f"[工具结果] {result}")

                # 将工具结果追加到历史
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                })

        elif finish_reason == "stop":
            # 模型已完成最终回答
            final_answer = msg.content
            print(f"\n{'='*50}")
            print(f"Agent 回答:\n{final_answer}")
            print(f"{'='*50}\n")
            return final_answer

        else:
            # 其他停止原因（length、content_filter 等）
            return f"[未完成，停止原因: {finish_reason}]"


# ── 入口 ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # 示例查询
    queries = [
        "北京今天天气怎么样，适合出门跑步吗？",
        "上海明天适合去公园散步吗？",
    ]

    for q in queries:
        run_agent(q)
