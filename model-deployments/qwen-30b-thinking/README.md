# qwen-30b-thinking

这个目录提供一套围绕 `Qwen/Qwen3-30B-A3B-Thinking-2507` 的本地 OpenAI 兼容服务启动脚本与验证/压测脚本，默认使用 vLLM 的 OpenAI API Server（`vllm.entrypoints.openai.api_server`），并开启推理解析与自动工具选择（tool calling）。

## 目录内容

- `start_server.sh`：启动 vLLM OpenAI 兼容服务（默认监听 `0.0.0.0:8000`）。
- `stop_server.sh`：停止上述服务（按 `--served-model-name` + `--port` 精确匹配进程）。
- `verify_inference.py`：推理验证（支持命令行参数、可选打印 reasoning）。
- `tool_calling.py`：工具调用示例（function calling + 本地执行工具函数 + 多轮循环）。
- `benchmark.py`：多进程 + 异步并发的吞吐/延迟压测（请求 `/v1/chat/completions`）。
- `benchmark_summary.txt`：一次基准测试的汇总结果（由 `benchmark.py` 生成）。

## 快速开始

### 1) 启动服务

脚本默认做了三件事：

- 设置模型缓存目录：`HF_HOME=/mnt/data/huggingface_cache`
- 固定使用 4 张卡：`CUDA_VISIBLE_DEVICES=0,1,2,3`
- 以 TP=4 启动 vLLM，并将 OpenAI 侧的模型名设置为 `Qwen/Qwen3-30B-A3B-Thinking-2507`

启动：

```bash
bash start_server.sh
```

关键参数（见 `start_server.sh`）：

- `--model Qwen/Qwen3-30B-A3B-Thinking-2507`：直接使用 Hugging Face repo id（如需本地权重可改为本地目录）。
- `--tensor-parallel-size 4`：4 卡张量并行（与 `CUDA_VISIBLE_DEVICES` 保持一致）。
- `--gpu-memory-utilization 0.85`：显存利用率上限（相对保守）。
- `--served-model-name Qwen/Qwen3-30B-A3B-Thinking-2507`：客户端请求时要填写的 `model` 名称。
- `--enable-auto-tool-choice` + `--tool-call-parser hermes`：启用自动工具选择，并按 Hermes 风格解析工具调用。
- `--reasoning-parser deepseek_r1`：启用推理内容解析（用于 thinking/reasoning 输出结构化拆分）。

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

常用参数：

```bash
python verify_inference.py \
  --base-url http://localhost:8000/v1 \
  --model Qwen/Qwen3-30B-A3B-Thinking-2507 \
  --reasoning-effort high \
  --include-reasoning
```

说明：

- `--include-reasoning` 会在请求中追加 `extra_body={"include_reasoning": True}`，并在返回里打印 `message.reasoning`（如果服务端返回该字段）。
- 如果出现 `content` 为空但 `reasoning` 有值，脚本会给出提示，通常与输出被截断或 token 上限有关。

## 工具调用示例

运行：

```bash
python tool_calling.py
```

该脚本的流程与 `gpt-oss-120b/tool_calling.py` 类似：

- 声明 `get_weather` 工具（function schema）。
- 模型自动决定是否发起工具调用。
- 本地执行工具并把结果回传，直到模型输出最终答复。

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
- 每请求 `max_tokens=128`

输出：

- 控制台打印每组进程数的报告
- 写入 `benchmark_result_p{N}.txt`
- 汇总写入 `benchmark_summary.txt`

## 常见调整点

- 端口：修改 `start_server.sh` 的 `--port`，并同步修改 `stop_server.sh` 与各 Python 脚本中的 base url。
- 模型来源：保持 Hugging Face repo id 不变即可自动下载到 `HF_HOME`；如要离线/本地权重，改 `--model` 为本地目录。
- 工具与推理解析：如你切换了 `--tool-call-parser` 或 `--reasoning-parser`，验证脚本的输出字段可能不同，需要相应调整查看字段。

