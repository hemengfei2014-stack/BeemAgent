# QA Gateway（FakeBeem 企业内部问答网关）

本目录是 “QA Gateway API + Enterprise Data Access + Web 前端（静态页）” 的落地实现。目标是在不让模型直接接触原始企业数据文件的前提下，实现：

- 登录后多轮会话（类似 ChatGPT）
- 流式输出（SSE），支持中断
- 企业内部问题强制走“工具查询/计算 → 可追溯证据 → 模型组织语言”的路径
- 严格组织隔离与判权（消息/文档按用户权限过滤）

## 架构与数据流

整体数据流与技术方案一致：

1. 浏览器访问 `/` 得到静态页面（`qa_gateway/web`）。
2. 用户通过 `/api/auth/login` 登录，服务端校验组织与用户，签发 JWT 到 HttpOnly Cookie（`fakebeem_token`）。
3. 前端创建/选择会话（`/api/conversations`），并通过 OpenAI 风格接口 `/v1/chat/completions` 发起聊天请求（支持 `stream=true`）。
4. 网关根据问题做内部路由：
   - internal：在模型工具调用循环中查询 SQLite（`enterprise_data.db`）得到结构化证据（tool output JSON），再由模型基于证据生成答案。
   - 非 internal：直接把“对话历史 + 身份”转发到模型服务生成答案。
5. 网关将 SSE 原样透传回前端；同时把 user/assistant 消息（含 reasoning_content）与工具执行记录落库到 `qa_gateway.db`。

## 运行方式

### 前置：模型服务

本项目默认假设本机已经有 OpenAI 兼容的模型服务运行在：

- `http://localhost:8000/v1`（vLLM OpenAI API Server）
- 模型名默认 `gpt-oss-120b`

本仓库内置了该模型的本地部署脚本与验证/压测脚本，目录在：

- [../model-deployments/gpt-oss-120b](../model-deployments/gpt-oss-120b)

其中：

- 启动服务：[../model-deployments/gpt-oss-120b/start_server.sh](../model-deployments/gpt-oss-120b/start_server.sh)
  - 默认启动 `vllm.entrypoints.openai.api_server` 监听 `0.0.0.0:8000`
  - `--served-model-name gpt-oss-120b`：客户端请求里的 `model` 必须填该名字
  - 默认使用 4 卡 TP（`CUDA_VISIBLE_DEVICES=0,1,2,3`，`--tensor-parallel-size 4`）
- 停止服务：[../model-deployments/gpt-oss-120b/stop_server.sh](../model-deployments/gpt-oss-120b/stop_server.sh)（按 `--served-model-name` + `--port` 精确匹配进程）
- 推理验证：[../model-deployments/gpt-oss-120b/verify_inference.py](../model-deployments/gpt-oss-120b/verify_inference.py)（包含 `reasoning_effort` 用法）
- 压测脚本：[../model-deployments/gpt-oss-120b/benchmark.py](../model-deployments/gpt-oss-120b/benchmark.py)

QA Gateway 当前使用该模型的方式：

- 后端通过 [ModelClient](./model_client.py#L7-L24) 调用 `POST /v1/chat/completions`
- base_url 在 [main.py](./main.py#L47-L56) 固定为 `http://localhost:8000/v1`
- 前端发起请求时固定 `model: "gpt-oss-120b"`（见 [./web/app.js](./web/app.js#L186-L195)）
- 流式返回会同时包含：
  - `choices[0].delta.reasoning_content`（thinking）
  - `choices[0].delta.content`（final answer）
  网关会解析并分别累计后落库（见 [chat_completions](./main.py#L781-L1079)）

### 启动 QA Gateway

在仓库根目录执行：

```bash
uvicorn qa_gateway.main:app --host 0.0.0.0 --port 8085
```

浏览器打开：

- `http://localhost:8085/`

登录示例：

- 组织名称：`Jaco`
- 用户 ID：`10052`

## 数据与数据库文件

本实现使用两个 SQLite 文件（均在仓库根目录）：

- `enterprise_data.db`：由合成数据（`fake_beem/simplified_schema/synthetic_data/`）初始化导入的企业数据查询库
- `qa_gateway.db`：网关自身的会话、消息与工具执行记录库

初始化逻辑：

- 启动时会调用 [init_enterprise_db_if_needed](./db.py#L107-L412)：
  - 首次创建或 schema_version 不匹配时，会 DROP/CREATE 表并从 TSV 导入数据
  - 包含 message/doc/calendar 的拆表与索引创建（含 doc FTS、calendar participant 索引等）
- 启动时会调用 [init_app_db](./db.py#L41-L98) 初始化会话库表结构：
  - `conversations`：会话元信息（title/created_at_ms/updated_at_ms）
  - `conversation_messages`：对话消息（含 `reasoning_content`）
  - `tool_runs`：每次工具调用的入参/结果摘要/耗时/是否截断等记录

关于 `enterprise_data.db` 的 schema_version：

- 当前版本为 `2`（见 [db.py](./db.py#L107-L412) 的 `_meta.schema_version` 写入）
- `doc` 表包含 `update_time` 与 `content_length` 字段，以支持“按更新时间排序”的文档查询（见 [db.py](./db.py#L207-L218) 与 [enterprise.py](./enterprise.py#L1367-L1382)）

## 对外接口（HTTP API）

### 认证

- `POST /api/auth/login`
  - body: `{ "org_name": "Jaco", "user_id": "10052" }`
  - 成功后写入 Cookie：`fakebeem_token`（HttpOnly）
- `GET /api/auth/me`
  - 返回当前登录身份（org_id/org_name/user_id/user_name）
- `POST /api/auth/logout`
  - 清理 Cookie

实现见 [main.py](./main.py#L114-L177)。

### 会话管理

- `GET /api/conversations`：会话列表（按 updated_at_ms 倒序）
- `POST /api/conversations`：新建会话
- `GET /api/conversations/{conversation_id}`：会话详情 + 消息列表

实现见 [main.py](./main.py#L179-L227)。

### 聊天生成（OpenAI 风格）

- `POST /v1/chat/completions`
  - 关键参数：
    - `model`：默认 `gpt-oss-120b`
    - `stream`：`true/false`
    - `messages`：当前前端只传最后一条 user 消息，历史从服务端会话库回放
    - `metadata.conversation_id`：必填，用于绑定会话
    - `reasoning_effort`：透传给模型服务（如 `high`）

实现见 [chat_completions](./main.py#L781-L1079)。

## 内部问题路由与“证据驱动”回答

### 路由：是否内部问题、命中哪些域

路由采用“模型判定为主，规则兜底为辅”：

1) 优先使用路由模型：把业务域说明 + 登录身份 + 近若干轮对话上下文 + 当前问题，发给模型服务做分类，得到 JSON：

```json
{
  "is_internal": true,
  "domains": ["org", "doc", "message", "calendar"],
  "confidence": 0.0,
  "reason": "一句话原因"
}
```

实现见：

- 业务域说明构建：[\_build_router_business_context](./main.py#L303-L316)
- 路由模型调用与解析：[\_route_with_model](./main.py#L317-L417)
- 在聊天入口中落日志与应用路由：[\chat_completions](./main.py#L781-L855)

2) 兜底回退到规则/词典路由：当路由模型调用失败或解析失败时（可通过环境变量控制是否开启兜底），回退到 [classify_internal](./enterprise.py#L81-L149) 的关键词/实体词典命中逻辑。

### 内部问题：工具调用循环（Tool Calling Loop）

当 `is_internal=true` 时，网关不会直接把企业数据塞进 prompt，而是让模型通过工具来取证据：

1) 网关向模型发起一次“可调用工具”的 chat completion（`tools=enterprise_tool_schemas()` + `tool_choice=auto`）。
2) 若模型返回 tool_calls，网关逐个执行工具（SQLite 查询 + 判权），把结果以 `role=tool` 的消息追加回上下文。
3) 循环多步，直到模型不再要求调用工具为止，此时该轮输出即为“基于证据的最终回答”。

实现见：[\_run_internal_tool_calling_loop](./main.py#L573-L779)。

补充：为兼容部分模型“把工具调用 JSON 写在 content 里但没有 tool_calls”的情况，网关增加了两类解析兜底：

- 解析 content 中的单个工具请求 JSON：[\_try_parse_single_tool_request_from_text](./main.py#L419-L440)
- 当 content 里只给了裸参数（例如 start_ms/end_ms）时，按当前问题意图推断工具：[\_infer_tool_call_from_bare_parameters](./main.py#L442-L467)

再补充：当以上都没有触发 tool_calls 时，网关对几类高频内部问题做了最后一道“强制工具兜底”，避免模型直接输出参数 JSON 或胡乱回答：

- “最近看了哪些文档”等文档类问题 → `doc_list_recently_updated`
- “我的 leader/上级是谁”等组织类问题 → `org_get_self_profile`
- “最近有什么会议/日程”等日历类问题 → `cal_get_events_in_range`

实现见：[\_run_internal_tool_calling_loop](./main.py#L620-L681)。

### internal + stream 的两段式调用

当 `stream=true` 且问题为 internal 时，网关采用两段式：

1) 先用非流式的工具调用循环把证据（tool outputs）补齐到 messages 中
2) 再以 `stream=true` 发起第二次模型调用，仅做“基于已有证据组织语言”的流式输出（这一步不再允许工具调用）

实现见：[\chat_completions](./main.py#L855-L945)。

## Prompt 上下文增强（术语/用户画像）

为提升“工具选择/参数更准确”（尤其是企业内部黑话、同义词、缩写），网关支持在 system prompt 中追加轻量上下文（默认只开启术语，不默认开启用户画像）。

### 术语与同义词约定（默认开启）

- 默认会在 system prompt 中追加“术语与同义词约定（用于消歧/改写查询词）”。
- 默认内置示例（可自行覆盖）：
  - `用增` → `用户增长`
  - `人力`/`HR`/`hr` → `人力资源`
  - `产研` → `产品+研发`
- 开关：
  - `QA_PROMPT_INCLUDE_TERM_ALIASES=0`：关闭术语追加（默认开启）
- 覆盖默认映射：
  - `QA_TERM_ALIASES_JSON='{"用增":"用户增长","HR":"人力资源","hr":"人力资源","产研":"产品+研发"}'`

实现见 [main.py](./main.py) 的 `*_term_aliases*` 相关函数。

### 用户画像提示（默认关闭）

- 仅用于消歧，不建议塞入可直接回答问题的“事实”（例如 CEO/人数/部门树等），避免模型绕过工具直接回答。
- 开关：
  - `QA_PROMPT_INCLUDE_USER_PROFILE=1`：在 system prompt 中追加当前登录用户的轻量画像（部门、role_id、manager 等；避免与 identity 重复）

实现见 [main.py](./main.py) 的 `_build_user_profile_hint`。

### 工具与权限（Enterprise Tools）

可用工具列表在 [enterprise_tool_schemas](./enterprise.py#L609-L835)，工具执行入口在 [execute_enterprise_tool](./enterprise.py#L837-L1529)。核心约束：

- org/calendar：组织内公开但必须组织隔离（只能在当前 org_id 内）
- message/doc：严格按当前登录用户过滤，只能访问“我可见”的会话与文档

工具返回统一结构：

```json
{
  "ok": true,
  "tool": "doc_list_recently_updated",
  "summary": "recent docs (ordered by update_time)",
  "evidence_refs": { "doc_ids": ["..."] },
  "truncated": false,
  "data": [ ... ]
}
```

### 日历：组织者会议不遗漏

日历工具 `cal_get_events_in_range` 会同时返回“我是参与者”以及“我是组织者”的会议，避免仅凭 participant 表漏掉组织者会议。

实现见：[`cal_get_events_in_range` 分支](./enterprise.py#L1398-L1424)。

## 流式输出（SSE）与中断


网关对模型服务的流式返回尽量做“字节级透传”：

- 从模型服务读取 bytes chunk
- 原样 `yield` 给前端（`text/event-stream`）

同时为了落库，会在网关侧解析 SSE 的 `data:` 行，累计：

- `delta.content` → answer
- `delta.reasoning_content` → reasoning

实现见 [chat_completions](./main.py#L891-L1056) 与 [sse_json_lines_from_bytes](./model_client.py#L27-L47)。

### 中断（Stop）

前端通过 `AbortController.abort()` 断开连接；网关侧捕获异常后标记 `cancelled=True` 并结束本轮（不会继续等待上游）。

实现：

- 前端：[./web/app.js](./web/app.js#L179-L257)
- 后端：[\_stream / \_stream_internal 异常处理](./main.py#L891-L1056)

### 单会话单请求（in-flight 限制）

为保证“上一轮没结束前不能继续提问”，网关在后端也做了兜底：

- key = (org_id, user_id, conversation_id)
- 若 key 已在 `inflight` 中，直接返回 409 `conversation_inflight`

实现见 [chat_completions](./main.py#L801-L805)。

## 日志

应用日志默认写入：

- `../logs/qa_gateway.log`

日志内容是 JSON line，包含：

- `http_request`：method/path/status/elapsed_ms/org_id/user_id/error
- `route_model_request` / `route_model_response`：路由模型请求/响应（包含 parse 是否成功、耗时等）
- （可选详细）`route_model_payload`：路由模型请求关键参数摘要
- `chat_route`：conversation_id/is_internal/domains/confidence/fallback/route_error/stream
- `tool_loop_model_request` / `tool_loop_model_response`：内部工具循环每步的模型请求/响应（是否有 tool_calls、来源等）
- `tool_execute`：单个工具执行记录（tool_name/ok/elapsed_ms/truncated 等）
- （可选详细）`tool_loop_model_payload` / `tool_loop_model_result` / `tool_execute_payload`：工具循环每步请求/结果摘要
- （可选详细）`chat_received` / `chat_model_payload` / `final_model_payload` / `final_model_result`：聊天请求与最终回答摘要
- `chat_done`：answer_len/reasoning_len/cancelled/trace_id

实现见 [main.py](./main.py#L31-L109) 与 [chat_completions](./main.py#L781-L1079)。

环境变量：

- `QA_LOG_STDOUT=1`：同时输出到 stdout（默认不输出）
- `QA_LOG_VERBOSE=1`：输出更详细的“逐步”日志（payload/result 摘要；默认关闭）
- `QA_LOG_INCLUDE_USER_TEXT=1`：详细日志里记录用户问题全文（默认关闭；开启前请确认合规）
- `QA_ROUTER_MODEL=...`：指定路由分类器使用的模型名（默认复用请求的 `model`）
- `QA_ROUTE_FALLBACK=0`：禁用路由失败时的规则兜底（默认开启）

### 查看日志（按 conversation_id / trace_id 串起来）

日志是 JSON lines，推荐用 `jq` 过滤：

```bash
tail -f logs/qa_gateway.log | jq -c 'select(.conversation_id=="<conversation_id>")'
```

internal 工具循环会生成 `trace_id`，可以按 trace 串起完整工具调用链：

```bash
tail -f logs/qa_gateway.log | jq -c 'select(.trace_id=="<trace_id>")'
```

也可以只保留关键字段便于阅读：

```bash
tail -f logs/qa_gateway.log | jq -c 'select(.conversation_id=="<conversation_id>") | {type,conversation_id,trace_id,step_idx,tool_name,ok,elapsed_ms,question,tool_args_head,assistant_content_head,answer_head,raw_head}'
```

### 从数据库回放执行链路（qa_gateway.db）

`qa_gateway.db` 会记录对话与工具调用的结构化信息：

- `conversation_messages`：user/assistant 消息（含 reasoning_content）
- `tool_runs`：每次工具调用（tool_args_json/result_summary/result_refs_json/elapsed_ms/ok/error 等）

示例：

```bash
sqlite3 qa_gateway.db "select role, substr(content,1,120) as content_head, created_at_ms from conversation_messages where conversation_id='<conversation_id>' order by created_at_ms;"
```

```bash
sqlite3 qa_gateway.db "select trace_id, step_idx, tool_name, ok, elapsed_ms, substr(tool_args_json,1,200) as tool_args_head, result_summary from tool_runs where conversation_id='<conversation_id>' order by created_at_ms;"
```

## 模块 / 文件说明

### 后端（Python）

- [main.py](./main.py)
  - FastAPI 应用入口
  - 初始化数据库与词典
  - 登录/会话 API
  - `/v1/chat/completions`：模型路由、内部工具调用循环、流式透传、落库
  - 日志与 in-flight 兜底
- [db.py](./db.py)
  - SQLite 连接参数与 PRAGMA
  - `enterprise_data.db`：从 synthetic_data TSV 导入并建表/建索引/FTS（schema_version=2）
  - `qa_gateway.db`：会话、消息、工具执行记录表结构
- [enterprise.py](./enterprise.py)
  - `build_dictionaries`：构建 org/user/dept 词典（用于路由实体召回）
  - `classify_internal`：规则/词典路由（路由模型失败时的兜底）
  - `enterprise_tool_schemas`：声明对模型开放的工具列表与参数 schema
  - `execute_enterprise_tool`：工具执行入口（SQLite 查询 + 判权 + 统一返回结构）
- [security.py](./security.py)
  - JWT 生成/校验（HS256）
  - 身份上下文 `AuthContext`
  - `QA_JWT_SECRET` 可配置；未配置时使用 dev-only 默认值（仅适用于本地演示）
- [model_client.py](./model_client.py)
  - 调用本机模型服务的 httpx 客户端
  - SSE 切块解析：从 buffer 中按 `\n\n` 分割事件并解析 `data: ...` 的 JSON

### 前端（静态）

前端不依赖 Node/Vite/React，直接由 FastAPI 静态托管：

- [web/index.html](./web/index.html)：登录页 + ChatGPT 风格布局
- [web/app.js](./web/app.js)
  - 登录态恢复（`/api/auth/me`）
  - 会话列表与消息加载
  - SSE 流式渲染（同时展示 reasoning_content 与 content）
  - AbortController 中断生成
- [web/style.css](./web/style.css)：样式

## 扩展指南（如何新增一种内部可计算问题）

1. 声明一个新工具 schema：
   - 在 [enterprise_tool_schemas](./enterprise.py#L609-L835) 增加一个 function（name/description/parameters）
2. 实现该工具的判权与查询：
   - 在 [execute_enterprise_tool](./enterprise.py#L837-L1529) 增加 `if tool_name == "..."` 分支
   - 返回结构遵循 `ok/err` 统一格式，并尽量在 `evidence_refs` 中带上可追溯主键（doc_id/message_id/event_id/session_id 等）
3. 让路由模型更稳定地识别该类问题：
   - 如果是新业务域，补充 [\_build_router_business_context](./main.py#L303-L316) 的业务域说明
   - 如果仍是现有域但容易漏判，优先通过“更清晰的业务域说明 + 上下文窗口”解决；必要时再加少量兜底触发（见 [\_run_internal_tool_calling_loop](./main.py#L620-L681)）
