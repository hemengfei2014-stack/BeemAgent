# gpt-oss-120b

这个目录提供一套围绕 `gpt-oss-120b` 的本地 OpenAI 兼容服务启动脚本与验证/压测脚本，默认使用 vLLM 的 OpenAI API Server（`vllm.entrypoints.openai.api_server`），并开启自动工具选择（tool calling）。

## 目录内容

- `start_server.sh`：启动 vLLM OpenAI 兼容服务（默认监听 `0.0.0.0:8000`）。
- `stop_server.sh`：停止上述服务（按 `--served-model-name` + `--port` 精确匹配进程）。
- `verify_inference.py`：最小化推理验证（chat completion + `reasoning_effort`）。
- `tool_calling.py`：工具调用示例（function calling + 本地执行工具函数 + 多轮循环）。
- `benchmark.py`：多进程 + 异步并发的吞吐/延迟压测（请求 `/v1/chat/completions`）。
- `benchmark_summary.txt`：一次基准测试的汇总结果（由 `benchmark.py` 生成）。

## 快速开始

### 1) 启动服务

脚本默认做了三件事：

- 设置模型缓存目录：`HF_HOME=/mnt/data/huggingface_cache`
- 固定使用 4 张卡：`CUDA_VISIBLE_DEVICES=0,1,2,3`
- 以 TP=4 启动 vLLM，并将 OpenAI 侧的模型名设置为 `gpt-oss-120b`

启动：

```bash
bash start_server.sh
```

关键参数（见 `start_server.sh`）：

- `--model /mnt/data/huggingface_cache/gpt-oss-120b`：模型路径（如你的模型不在该位置，请改为实际路径或 Hugging Face repo id）。
- `--tensor-parallel-size 4`：4 卡张量并行（与 `CUDA_VISIBLE_DEVICES` 保持一致）。
- `--gpu-memory-utilization 0.9`：显存利用率上限。
- `--served-model-name gpt-oss-120b`：客户端请求时要填写的 `model` 名称。
- `--enable-auto-tool-choice` + `--tool-call-parser openai`：启用自动工具选择，并按 OpenAI 风格解析工具调用。

服务端点（默认）：

- Base URL: `http://localhost:8000/v1`
- Chat Completions: `http://localhost:8000/v1/chat/completions`

### 2) 停止服务

```bash
bash stop_server.sh
```

如果你修改了启动脚本的 `--served-model-name` 或 `--port`，需要同步修改 `stop_server.sh` 顶部的 `MODEL_NAME/PORT`，否则可能匹配不到进程。

## 推理验证

在服务启动后运行：

```bash
python verify_inference.py
```

要点：

- 默认请求模型名：`gpt-oss-120b`（对应服务端 `--served-model-name`）。
- 使用 `reasoning_effort` 控制推理强度：`low` / `medium` / `high`（脚本内默认 `high`）。
- `max_tokens` 默认较大（`10240`），用于避免长回答被截断。

## 工具调用示例

该示例会：

- 向模型声明一个 `get_weather` 工具（function schema）。
- 让模型自动选择是否调用工具（`tool_choice="auto"`）。
- 当模型返回 `tool_calls` 时，在本地执行工具函数，把结果以 `role="tool"` 回传，直到模型不再要求工具调用。

运行：

```bash
python tool_calling.py
```

## 压测/基准测试

运行：

```bash
python benchmark.py
```

默认行为（见 `benchmark.py` 顶部常量）：

- 目标接口：`http://localhost:8000/v1/chat/completions`
- 总请求数：24
- 进程数：`[1, 2, 4, 8]`
- 每进程并发：4（`CONCURRENT_REQUESTS_PER_PROCESS`）
- 每请求 `max_tokens=128`（用于更稳定对比吞吐与延迟）

输出：

- 控制台打印每组进程数的报告
- 写入 `benchmark_result_p{N}.txt`
- 汇总写入 `benchmark_summary.txt`

## 常见调整点

- 端口：修改 `start_server.sh` 的 `--port`，并同步修改 `stop_server.sh` 与各 Python 脚本中的 base url。
- 模型位置：如果使用本地权重，修改 `--model` 为实际目录；若走 Hugging Face repo，直接填 repo id。
- 显存压力：降低 `--gpu-memory-utilization`，或减少并发/输出 token；也可以在 vLLM 侧调整 `--max-model-len` 等参数（本仓库默认未启用这些参数）。

