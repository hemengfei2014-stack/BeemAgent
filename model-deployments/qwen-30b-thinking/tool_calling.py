import openai
import sys
import json

# ----------------------------
# 1) 定义自定义工具
# ----------------------------
def get_weather(city: str) -> str:
    """
    自定义工具函数：返回城市的天气信息（这里模拟返回）。
    实际场景可以改成真实 API 请求天气服务。
    """
    return f"The weather in {city} is 22°C, sunny."

# ----------------------------
# 2) 配置 OpenAI 客户端
# ----------------------------
client = openai.Client(
    base_url="http://localhost:8000/v1",
    api_key="EMPTY",
)

# 模型名称
model_name = "Qwen/Qwen3-30B-A3B-Thinking-2507"

# 定义工具描述
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather information for a given city",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "The name of the city"
                    }
                },
                "required": ["city"]
            }
        }
    }
]

print(f"请求模型: {model_name} 进行工具调用示例")

try:
    # ----------------------------
    # 3) 请求模型可能的工具调用
    # ----------------------------
    messages = [
        {
            "role": "system",
            "content": "You are a helpful assistant. You have access to the following tools: get_weather. Use them when necessary."
        },
        {
            "role": "user",
            "content": "请帮我查一下北京、上海、天津、广州、南昌现在的天气并回复天气结果"
        }
    ]

    completion = client.chat.completions.create(
        model=model_name,
        messages=messages,
        tools=tools,
        tool_choice="auto",
    )

    msg = completion.choices[0].message

    
    # 支持多轮工具调用循环
    while msg.tool_calls:
        print(f"模型请求调用工具，数量: {len(msg.tool_calls)}")
        
        # 1. 将助手的工具调用消息添加到历史（只添加一次）
        messages.append(msg)

        # 2. 处理所有工具调用
        for tool_call in msg.tool_calls:
            func_name = tool_call.function.name
            func_args = json.loads(tool_call.function.arguments)

            print(f"执行工具: {func_name}, 参数: {func_args}")

            # 运行对应的工具函数
            if func_name == "get_weather":
                output = get_weather(**func_args)
                
                # 3. 将工具的结果作为新消息添加到历史
                messages.append({
                    "role": "tool", 
                    "tool_call_id": tool_call.id, 
                    "content": output
                })


        # 4. 再次请求模型，带上工具执行结果
        completion = client.chat.completions.create(
            model=model_name,
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )
        msg = completion.choices[0].message

    # 最终结果
    print("\n=== 最终生成输出 ===")
    print(msg.content)
    print("=== End ===\n")

except Exception as e:
    print("Error:", e)
    sys.exit(1)
