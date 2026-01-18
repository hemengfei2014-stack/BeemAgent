import openai
import sys

# 设置 API 客户端
client = openai.Client(
    base_url="http://localhost:8000/v1",
    api_key="EMPTY",
)

model_name = "gpt-oss-120b"

# low、medium、high
reasoning_mode = "high"

print(f"正在请求模型: {model_name}")

try:
    completion = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "user", "content": "写一段实现斐波拉契数列的python代码"}
        ],
        temperature=0.7,
        reasoning_effort=reasoning_mode,  # 推理强度模式
        max_tokens=10240,
    )

    print("\n=== Response ===")
    print(completion.choices[0].message.content)
    print("=== End ===\n")

except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
