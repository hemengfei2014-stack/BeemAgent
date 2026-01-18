#!/bin/bash
set -e

# 设置模型缓存目录
export HF_HOME=/mnt/data/huggingface_cache
mkdir -p $HF_HOME

# 设置可见设备
export CUDA_VISIBLE_DEVICES=0,1,2,3

# gpt-oss context window 128,000


# 启动 vLLM OpenAI API Server
# 注意：
# --cpu-offload-gb 80: 解决显存不足问题
# --tensor-parallel-size 4: 使用 4 卡并行
python -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen3-30B-A3B-Thinking-2507 \
    --trust-remote-code \
    --tensor-parallel-size 4 \
    --gpu-memory-utilization 0.85 \
    --host 0.0.0.0 \
    --port 8000 \
    --served-model-name Qwen/Qwen3-30B-A3B-Thinking-2507 \
    --enable-auto-tool-choice \
    --tool-call-parser hermes \
    --reasoning-parser deepseek_r1
