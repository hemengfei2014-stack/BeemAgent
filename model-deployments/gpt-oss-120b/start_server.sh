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
# --max-model-len 8192: 限制 context length 节省显存
# --tensor-parallel-size 4: 使用 4 卡并行
python -m vllm.entrypoints.openai.api_server \
    --model /mnt/data/huggingface_cache/gpt-oss-120b \
    --trust-remote-code \
    --tensor-parallel-size 4 \
    --gpu-memory-utilization 0.9 \
    --host 0.0.0.0 \
    --port 8000 \
    --served-model-name gpt-oss-120b \
    --enable-auto-tool-choice \
    --tool-call-parser openai
