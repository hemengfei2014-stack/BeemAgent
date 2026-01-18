# BeemAgent

Scripts and tools for serving and benchmarking different OpenAI-compatible model deployments.

## Model Comparison (4× L20)

### Specs

| Feature | gpt-oss-120b | Qwen/Qwen3-30B-A3B-Thinking-2507 |
|---|---|---|
| Total parameters | 117B | 30.5B |
| Active parameters / token | 5.1B | 3.3B |
| Architecture | MoE | MoE |
| Native context length | 128,000 | 262,144 |
| Reasoning control | Configurable (low/medium/high) | Thinking-only (no non-thinking mode) |
| Tool calling | Yes (auto tool choice) | Yes (auto tool choice) |
| Multi-tool calling | No | Yes |

### Benchmark (4× L20, 24 Requests Total)

Benchmarks executed on [gpt-oss-120b/benchmark.py](./gpt-oss-120b/benchmark.py) and [qwen-30b-thinking/benchmark.py](./qwen-30b-thinking/benchmark.py) with varying process counts.

**gpt-oss-120b**

Results saved in [benchmark_summary.txt](./gpt-oss-120b/benchmark_summary.txt).

| Processes | Time (s) | Throughput (req/s) | Throughput (tok/s) | Avg Latency (s) | P95 Latency (s) |
|---|---:|---:|---:|---:|---:|
| 1 | 6.54 | 3.67 | 469.75 | 1.09 | 1.10 |
| 2 | 3.84 | 6.25 | 799.55 | 1.28 | 1.29 |
| 4 | 2.98 | 8.04 | 1029.73 | 1.55 | 1.69 |
| 8 | 2.07 | 11.61 | 1486.42 | 2.05 | 2.06 |

**Qwen/Qwen3-30B-A3B-Thinking-2507**

Results saved in [benchmark_summary.txt](./qwen-30b-thinking/benchmark_summary.txt).

| Processes | Time (s) | Throughput (req/s) | Throughput (tok/s) | Avg Latency (s) | P95 Latency (s) |
|---|---:|---:|---:|---:|---:|
| 1 | 7.71 | 3.11 | 398.60 | 1.28 | 1.31 |
| 2 | 4.34 | 5.53 | 708.24 | 1.44 | 1.46 |
| 4 | 3.24 | 7.41 | 948.68 | 1.67 | 1.78 |
| 8 | 2.07 | 11.61 | 1486.41 | 2.05 | 2.06 |

*Note: Latency increases with concurrency, but overall throughput improves significantly.*

### Serving Footprint (This Repo Defaults)

| Model | Default server instances | Default GPU usage |
|---|---:|---|
| gpt-oss-120b | 1 | 1 instance (TP=4) uses all 4 GPUs |
| Qwen/Qwen3-30B-A3B-Thinking-2507 | 1 | 1 instance (TP=4) uses all 4 GPUs |

## Directories

### gpt-oss-120b

The [gpt-oss-120b](./gpt-oss-120b) directory contains scripts and tools for running and verifying the GPT-OSS model:

- [verify_inference.py](./gpt-oss-120b/verify_inference.py): Verify model inference.
- [tool_calling.py](./gpt-oss-120b/tool_calling.py): Tool calling examples.
- [benchmark.py](./gpt-oss-120b/benchmark.py): Multi-process benchmark runner.
- [start_server.sh](./gpt-oss-120b/start_server.sh): Start the OpenAI-compatible server.

### qwen-30b-thinking

The [qwen-30b-thinking](./qwen-30b-thinking) directory contains scripts and tools for running and verifying the Qwen3-30B-A3B-Thinking model:

- [verify_inference.py](./qwen-30b-thinking/verify_inference.py): Verify model inference.
- [tool_calling.py](./qwen-30b-thinking/tool_calling.py): Tool calling examples.
- [benchmark.py](./qwen-30b-thinking/benchmark.py): Multi-process benchmark runner.
- [start_server.sh](./qwen-30b-thinking/start_server.sh): Start the OpenAI-compatible server (reasoning + tool calling flags).
