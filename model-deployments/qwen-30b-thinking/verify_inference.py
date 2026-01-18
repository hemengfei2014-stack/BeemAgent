import argparse
import json
import sys

import openai


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000/v1")
    parser.add_argument("--api-key", default="EMPTY")
    parser.add_argument(
        "--model", default="Qwen/Qwen3-30B-A3B-Thinking-2507"
    )
    parser.add_argument(
        "--prompt",
        default="写一段实现斐波拉契数列的python代码",
    )
    parser.add_argument(
        "--reasoning-effort",
        choices=["low", "medium", "high"],
        default="high",
    )
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--max-tokens", type=int, default=10240)
    parser.add_argument("--include-reasoning", action="store_true")
    parser.add_argument("--timeout", type=float, default=600)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    client = openai.Client(
        base_url=args.base_url,
        api_key=args.api_key,
        timeout=args.timeout,
    )

    print(f"正在请求模型: {args.model}")

    extra_body = {"include_reasoning": True} if args.include_reasoning else None

    completion = client.chat.completions.create(
        model=args.model,
        messages=[{"role": "user", "content": args.prompt}],
        temperature=args.temperature,
        reasoning_effort=args.reasoning_effort,
        max_tokens=args.max_tokens,
        extra_body=extra_body,
    )

    payload = completion.model_dump()
    choice = payload["choices"][0]
    message = choice.get("message") or {}
    content = message.get("content")
    reasoning = message.get("reasoning")

    print("\n=== Response ===")
    if content:
        print(content)
    elif reasoning and args.include_reasoning:
        print("[content为空；仅返回了reasoning，可能是max_tokens不足或输出被截断]")
    else:
        print("[content为空]")
    print("=== End ===\n")

    if args.include_reasoning:
        print("=== Reasoning ===")
        print(reasoning or "[reasoning为空]")
        print("=== End ===\n")

    finish_reason = choice.get("finish_reason")
    usage = payload.get("usage")
    if finish_reason:
        print(f"finish_reason: {finish_reason}")
    if usage:
        print("usage:", json.dumps(usage, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"Error: {e}")
        raise SystemExit(1)
