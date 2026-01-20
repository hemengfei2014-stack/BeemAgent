import logging
import os
import json
import time
import uuid
import asyncio
import hashlib
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from logging.handlers import RotatingFileHandler

from .db import Paths, connect_sqlite, init_app_db, init_enterprise_db_if_needed
from .enterprise import (
    build_dictionaries,
    classify_internal,
    enterprise_tool_schemas,
    execute_enterprise_tool,
)
from .model_client import ModelClient, sse_json_lines_from_bytes
from .security import AuthContext, create_access_token, decode_access_token


ROOT_DIR = Path(__file__).resolve().parents[1]
PATHS = Paths(root_dir=ROOT_DIR)

LOG_DIR = ROOT_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_PATH = LOG_DIR / "qa_gateway.log"

logger = logging.getLogger("qa_gateway")
logger.setLevel(logging.INFO)
if not any(isinstance(h, RotatingFileHandler) for h in logger.handlers):
    handler = RotatingFileHandler(str(LOG_PATH), maxBytes=20 * 1024 * 1024, backupCount=10, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s\t%(levelname)s\t%(message)s"))
    logger.addHandler(handler)

if os.getenv("QA_LOG_STDOUT", "0") == "1":
    sh = logging.StreamHandler()
    sh.setFormatter(logging.Formatter("%(asctime)s\t%(levelname)s\t%(message)s"))
    logger.addHandler(sh)

enterprise_conn = connect_sqlite(PATHS.enterprise_db_path)
init_enterprise_db_if_needed(enterprise_conn, PATHS.synthetic_data_dir)
enterprise_dict = build_dictionaries(enterprise_conn)
enterprise_tools = enterprise_tool_schemas()

app_conn = connect_sqlite(PATHS.app_db_path)
init_app_db(app_conn)

model_client = ModelClient(base_url="http://localhost:8000/v1")

inflight: dict[tuple[str, str, str], str] = {}

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://localhost:8085", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def request_log_middleware(request: Request, call_next):
    start = time.time()
    token = request.cookies.get("fakebeem_token")
    ctx = decode_access_token(token) if token else None
    try:
        response = await call_next(request)
    except Exception as e:
        elapsed_ms = int((time.time() - start) * 1000)
        logger.info(
            json.dumps(
                {
                    "type": "http_request",
                    "method": request.method,
                    "path": request.url.path,
                    "status": 500,
                    "elapsed_ms": elapsed_ms,
                    "org_id": getattr(ctx, "org_id", None),
                    "user_id": getattr(ctx, "user_id", None),
                    "error": str(e),
                },
                ensure_ascii=False,
            )
        )
        raise
    elapsed_ms = int((time.time() - start) * 1000)
    logger.info(
        json.dumps(
            {
                "type": "http_request",
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "elapsed_ms": elapsed_ms,
                "org_id": getattr(ctx, "org_id", None),
                "user_id": getattr(ctx, "user_id", None),
            },
            ensure_ascii=False,
        )
    )
    return response


@app.middleware("http")
async def disable_cache_for_static(request: Request, call_next):
    response = await call_next(request)
    if request.method == "GET" and (request.url.path == "/" or request.url.path.startswith("/assets/")):
        response.headers["Cache-Control"] = "no-store"
    return response


def now_ms() -> int:
    return int(time.time() * 1000)


def _log_verbose_enabled() -> bool:
    return os.getenv("QA_LOG_VERBOSE", "0") == "1"


def _log_include_user_text() -> bool:
    return os.getenv("QA_LOG_INCLUDE_USER_TEXT", "0") == "1"


def _text_preview(text: Any, limit: int = 400) -> str:
    if not isinstance(text, str):
        return ""
    s = text.strip().replace("\n", " ")
    if len(s) <= limit:
        return s
    return s[:limit] + "…"


def _load_term_aliases() -> dict[str, str]:
    raw = (os.getenv("QA_TERM_ALIASES_JSON") or "").strip()
    if raw:
        try:
            obj = json.loads(raw)
            if isinstance(obj, dict):
                out: dict[str, str] = {}
                for k, v in obj.items():
                    if isinstance(k, str) and k.strip() and isinstance(v, str) and v.strip():
                        out[k.strip()] = v.strip()
                if out:
                    return out
        except Exception:
            pass
    return {
        "用增": "用户增长",
        "增长": "用户增长",
        "人力": "人力资源",
        "人力资源": "人力资源",
        "hr": "人力资源",
        "HR": "人力资源",
        "产研": "产品+研发",
    }


def _format_term_aliases_for_prompt() -> str:
    if os.getenv("QA_PROMPT_INCLUDE_TERM_ALIASES", "1") == "0":
        return ""
    aliases = _load_term_aliases()
    if not aliases:
        return ""
    items = sorted(aliases.items(), key=lambda kv: (kv[1], kv[0]))
    pairs = []
    seen: set[str] = set()
    for alias, canonical in items:
        key = f"{alias}={canonical}"
        if key in seen:
            continue
        seen.add(key)
        pairs.append(key)
    if not pairs:
        return ""
    return "术语与同义词约定（用于消歧/改写查询词）：\n" + "；".join(pairs)


def _build_user_profile_hint(ctx: AuthContext) -> str:
    if os.getenv("QA_PROMPT_INCLUDE_USER_PROFILE", "0") != "1":
        return ""
    try:
        user = enterprise_conn.execute(
            "SELECT id, name, manager_id, role, email, mobile FROM user WHERE org_id=? AND id=? LIMIT 1",
            (ctx.org_id, ctx.user_id),
        ).fetchone()
        if not user:
            return ""
        manager_name = None
        if user["manager_id"]:
            m = enterprise_conn.execute(
                "SELECT name FROM user WHERE org_id=? AND id=? LIMIT 1",
                (ctx.org_id, user["manager_id"]),
            ).fetchone()
            if m:
                manager_name = m["name"]
        dept_rows = enterprise_conn.execute(
            """
            SELECT d.name AS dept_name
            FROM dept_user du
            JOIN dept d ON d.org_id=du.org_id AND d.id=du.dept_id
            WHERE du.org_id=? AND du.user_id=?
            ORDER BY CAST(d.level AS INTEGER) ASC, d.name ASC
            """,
            (ctx.org_id, ctx.user_id),
        ).fetchall()
        dept_names = [r["dept_name"] for r in dept_rows if r and r["dept_name"]]
        parts: list[str] = []
        parts.append("用户画像提示")
        if not (ctx.user_name or "").strip():
            parts.append(f"name={user['name']}")
        if dept_names:
            parts.append("departments=" + ",".join(dept_names[:6]))
        if user["role"] is not None and str(user["role"]).strip():
            parts.append(f"role_id={str(user['role']).strip()}")
        if user["manager_id"] and manager_name:
            parts.append(f"manager={user['manager_id']}({manager_name})")
        return "\n" + "；".join(parts)
    except Exception:
        return ""


def require_auth(request: Request) -> AuthContext:
    token = request.cookies.get("fakebeem_token")
    if not token:
        raise HTTPException(status_code=401, detail="not_logged_in")
    ctx = decode_access_token(token)
    if not ctx:
        raise HTTPException(status_code=401, detail="invalid_token")
    return ctx


@app.get("/api/auth/me")
def me(ctx: AuthContext = Depends(require_auth)) -> dict[str, Any]:
    return {
        "ok": True,
        "user": {
            "org_id": ctx.org_id,
            "org_name": ctx.org_name,
            "user_id": ctx.user_id,
            "user_name": ctx.user_name,
        },
    }


@app.post("/api/auth/login")
def login(payload: dict[str, Any], response: Response) -> dict[str, Any]:
    org_name = str(payload.get("org_name", "")).strip()
    user_id = str(payload.get("user_id", "")).strip()
    if not org_name or not user_id:
        raise HTTPException(status_code=400, detail="missing_org_or_user")

    org = enterprise_conn.execute("SELECT * FROM org WHERE name=? LIMIT 1", (org_name,)).fetchone()
    if not org:
        raise HTTPException(status_code=401, detail="invalid_org_or_user")
    user = enterprise_conn.execute(
        "SELECT * FROM user WHERE org_id=? AND id=? LIMIT 1",
        (org["id"], user_id),
    ).fetchone()
    if not user:
        raise HTTPException(status_code=401, detail="invalid_org_or_user")

    ctx = AuthContext(
        org_id=str(org["id"]),
        org_name=str(org["name"]),
        user_id=str(user["id"]),
        user_name=str(user["name"]),
    )
    token = create_access_token(ctx)
    response.set_cookie(
        "fakebeem_token",
        token,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
        max_age=60 * 60 * 24 * 7,
    )
    return {"ok": True, "user": {"org_id": ctx.org_id, "org_name": ctx.org_name, "user_id": ctx.user_id, "user_name": ctx.user_name}}


@app.post("/api/auth/logout")
def logout(response: Response) -> dict[str, Any]:
    response.delete_cookie("fakebeem_token", path="/")
    return {"ok": True}


@app.get("/api/conversations")
def list_conversations(ctx: AuthContext = Depends(require_auth)) -> dict[str, Any]:
    rows = app_conn.execute(
        """
        SELECT id, title, created_at_ms, updated_at_ms
        FROM conversations
        WHERE org_id=? AND user_id=?
        ORDER BY updated_at_ms DESC
        LIMIT 200
        """,
        (ctx.org_id, ctx.user_id),
    ).fetchall()
    return {"ok": True, "conversations": [dict(r) for r in rows]}


@app.post("/api/conversations")
def create_conversation(ctx: AuthContext = Depends(require_auth)) -> dict[str, Any]:
    conv_id = str(uuid.uuid4())
    ts = now_ms()
    title = "新会话"
    app_conn.execute(
        """
        INSERT INTO conversations(id,org_id,user_id,title,created_at_ms,updated_at_ms)
        VALUES (?,?,?,?,?,?)
        """,
        (conv_id, ctx.org_id, ctx.user_id, title, ts, ts),
    )
    app_conn.commit()
    return {"ok": True, "conversation": {"id": conv_id, "title": title, "created_at_ms": ts, "updated_at_ms": ts}}


@app.get("/api/conversations/{conversation_id}")
def get_conversation(conversation_id: str, ctx: AuthContext = Depends(require_auth)) -> dict[str, Any]:
    conv = app_conn.execute(
        "SELECT * FROM conversations WHERE id=? AND org_id=? AND user_id=?",
        (conversation_id, ctx.org_id, ctx.user_id),
    ).fetchone()
    if not conv:
        raise HTTPException(status_code=404, detail="not_found")
    rows = app_conn.execute(
        """
        SELECT id, role, content, reasoning_content, created_at_ms
        FROM conversation_messages
        WHERE conversation_id=?
        ORDER BY created_at_ms ASC
        """,
        (conversation_id,),
    ).fetchall()
    return {"ok": True, "conversation": dict(conv), "messages": [dict(r) for r in rows]}


def _title_from_first_message(text: str) -> str:
    t = (text or "").strip().replace("\n", " ")
    return t[:10] if len(t) > 10 else t or "新会话"


def _save_message(conversation_id: str, role: str, content: str, reasoning_content: str | None = None) -> None:
    app_conn.execute(
        """
        INSERT INTO conversation_messages(id,conversation_id,role,content,reasoning_content,created_at_ms)
        VALUES (?,?,?,?,?,?)
        """,
        (str(uuid.uuid4()), conversation_id, role, content, reasoning_content, now_ms()),
    )


def _update_conversation_updated(conversation_id: str) -> None:
    app_conn.execute(
        "UPDATE conversations SET updated_at_ms=? WHERE id=?",
        (now_ms(), conversation_id),
    )


def _ensure_conversation_owner(conversation_id: str, ctx: AuthContext) -> dict[str, Any]:
    conv = app_conn.execute(
        "SELECT * FROM conversations WHERE id=? AND org_id=? AND user_id=?",
        (conversation_id, ctx.org_id, ctx.user_id),
    ).fetchone()
    if not conv:
        raise HTTPException(status_code=404, detail="conversation_not_found")
    return dict(conv)

def _extract_tool_calls_from_message(message: Any) -> list[dict[str, Any]]:
    if not isinstance(message, dict):
        return []
    tool_calls = message.get("tool_calls")
    if not isinstance(tool_calls, list):
        return []
    out: list[dict[str, Any]] = []
    for tc in tool_calls:
        if isinstance(tc, dict):
            out.append(tc)
    return out

def _safe_parse_tool_arguments(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        return {}
    s = raw.strip()
    if not s:
        return {}
    try:
        val = json.loads(s)
    except Exception:
        return {}
    return val if isinstance(val, dict) else {}

def _extract_first_json_object(text: str) -> dict[str, Any] | None:
    s = (text or "").strip()
    if not s:
        return None
    l = s.find("{")
    r = s.rfind("}")
    if l == -1 or r == -1 or r <= l:
        return None
    blob = s[l : r + 1].strip()
    try:
        obj = json.loads(blob)
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None

def _build_router_business_context() -> str:
    term_aliases = _format_term_aliases_for_prompt()
    extra = ("\n\n" + term_aliases) if term_aliases else ""
    return (
        "你在一个企业内部问答系统（FakeBeem）里做“路由判定”。系统包含以下业务域：\n"
        "1) org（组织架构）：组织/部门/员工信息、上下级/leader/manager、联系方式、部门成员等。\n"
        "2) message（IM）：会话列表、会话消息、群聊/私聊；严格权限：只能访问当前登录用户参与的会话。\n"
        "3) doc（文档）：文档列表、搜索、详情；严格权限：只能访问当前登录用户可访问的文档。\n"
        "4) calendar（日历/日程）：会议/日程查询；组织内公开但只能在当前组织内。\n"
        "\n"
        "路由目标：判断当前用户问题是否需要访问企业内部数据（internal）。\n"
        "- 如果问题需要上述域的数据才能回答（例如“我的leader是谁/我能访问哪些文档/我和某人聊过什么/我下周有啥会”），则 is_internal=true，并给出 domains。\n"
        "- 如果问题是纯闲聊/写作/通用知识且不依赖企业内部数据，则 is_internal=false。\n"
        "必须结合对话上下文判断指代（例如“他/那个文档/上一条消息里的人”）。\n"
    ) + extra

async def _route_with_model(
    ctx: AuthContext,
    conversation_id: str,
    user_question: str,
    history: list[dict[str, Any]],
    model: str,
) -> dict[str, Any]:
    router_model = str(os.getenv("QA_ROUTER_MODEL") or model)
    biz = _build_router_business_context()
    ctx_lines: list[str] = []
    for m in history[-12:]:
        role = m.get("role")
        content = m.get("content")
        if role in {"user", "assistant"} and isinstance(content, str) and content.strip():
            compact = content.strip().replace("\n", " ")
            if len(compact) > 240:
                compact = compact[:240] + "…"
            ctx_lines.append(f"{role}: {compact}")
    context_block = "\n".join(ctx_lines) if ctx_lines else "(无历史上下文)"

    system = (
        "你是路由分类器，不是聊天机器人。"
        "只输出 JSON，不要输出任何解释性文本，不要使用 markdown。"
        "JSON schema:\n"
        '{ "is_internal": true|false, "domains": ["org"|"message"|"doc"|"calendar"], "confidence": 0.0-1.0, "reason": "一句话原因" }'
    )
    identity = f"当前登录用户：org_id={ctx.org_id}, org_name={ctx.org_name}, user_id={ctx.user_id}, user_name={ctx.user_name}。"
    user = (
        biz
        + "\n"
        + identity
        + "\n\n对话上下文（最近若干条）：\n"
        + context_block
        + "\n\n当前问题：\n"
        + user_question.strip()
    )

    req: dict[str, Any] = {
        "model": router_model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": 0.0,
        "max_tokens": 200,
        "stream": False,
    }
    started = now_ms()
    if _log_verbose_enabled():
        logger.info(
            json.dumps(
                {
                    "type": "route_model_payload",
                    "conversation_id": conversation_id,
                    "org_id": ctx.org_id,
                    "user_id": ctx.user_id,
                    "router_model": router_model,
                    "temperature": 0.0,
                    "max_tokens": 200,
                    "stream": False,
                    "history_used": len(ctx_lines),
                    "system_len": len(system),
                    "user_len": len(user),
                    "question": user_question if _log_include_user_text() else _text_preview(user_question, 240),
                },
                ensure_ascii=False,
            )
        )
    logger.info(
        json.dumps(
            {
                "type": "route_model_request",
                "conversation_id": conversation_id,
                "org_id": ctx.org_id,
                "user_id": ctx.user_id,
                "router_model": router_model,
                "history_used": len(ctx_lines),
                "question_len": len(user_question),
            },
            ensure_ascii=False,
        )
    )
    resp = await model_client.chat_completions(req)
    elapsed = now_ms() - started
    msg = ((resp.get("choices") or [{}])[0]).get("message") or {}
    content = msg.get("content") if isinstance(msg, dict) else None
    raw_text = content if isinstance(content, str) else ""
    parsed = _extract_first_json_object(raw_text)
    logger.info(
        json.dumps(
            {
                "type": "route_model_response",
                "conversation_id": conversation_id,
                "org_id": ctx.org_id,
                "user_id": ctx.user_id,
                "router_model": router_model,
                "elapsed_ms": elapsed,
                "raw_len": len(raw_text),
                "raw_head": raw_text[:300],
                "parsed_ok": bool(parsed),
            },
            ensure_ascii=False,
        )
    )
    if not parsed:
        raise ValueError("route_model_parse_failed")

    is_internal = bool(parsed.get("is_internal"))
    domains_in = parsed.get("domains")
    domains: list[str] = []
    if isinstance(domains_in, list):
        for d in domains_in:
            if isinstance(d, str) and d in {"org", "message", "doc", "calendar"}:
                domains.append(d)
    domains = sorted(set(domains))
    if is_internal and not domains:
        domains = ["org", "doc", "message", "calendar"]

    confidence = parsed.get("confidence")
    conf = float(confidence) if isinstance(confidence, (int, float)) else None
    reason = parsed.get("reason")
    reason_s = str(reason) if isinstance(reason, str) else ""

    return {"is_internal": is_internal, "domains": domains, "confidence": conf, "reason": reason_s}

def _try_parse_single_tool_request_from_text(text: str) -> tuple[str, dict[str, Any]] | None:
    s = (text or "").strip()
    if not s:
        return None
    l = s.find("{")
    r = s.rfind("}")
    if l == -1 or r == -1 or r <= l:
        return None
    blob = s[l : r + 1].strip()
    try:
        obj = json.loads(blob)
    except Exception:
        return None
    if not isinstance(obj, dict):
        return None
    tool = obj.get("tool") or obj.get("tool_name") or obj.get("name")
    params = obj.get("parameters") or obj.get("args") or obj.get("arguments") or {}
    if not isinstance(tool, str) or not tool.strip():
        return None
    if not isinstance(params, dict):
        params = {}
    return tool.strip(), params

def _infer_tool_call_from_bare_parameters(text: str, user_question: str) -> tuple[str, dict[str, Any]] | None:
    obj = _extract_first_json_object(text or "")
    if not obj:
        return None
    keys = set(obj.keys())
    q = (user_question or "").strip()
    if ({"start_time", "end_time"} <= keys) or ({"start_ms", "end_ms"} <= keys):
        if any(k in q for k in ["会议", "日历", "日程", "邀约", "参会", "安排"]):
            start = obj.get("start_ms", obj.get("start_time"))
            end = obj.get("end_ms", obj.get("end_time"))
            try:
                start_i = int(start)
                end_i = int(end)
            except Exception:
                return None
            if start_i < 10**12:
                start_i *= 1000
            if end_i < 10**12:
                end_i *= 1000
            uid = obj.get("user_id")
            limit = obj.get("limit", 20)
            args: dict[str, Any] = {"start_ms": start_i, "end_ms": end_i, "limit": int(limit)}
            if uid is not None:
                args["user_id"] = str(uid)
            return "cal_get_events_in_range", args
    return None

def _normalize_tool_name(raw: str) -> str:
    name = (raw or "").strip()
    if not name:
        return ""
    aliases = {
        "session_list": "im_list_my_sessions",
        "session_messages": "im_get_session_messages",
        "schedule_get_events": "cal_get_events_in_range",
        "calendar_get_events": "cal_get_events_in_range",
        "cal_get_events": "cal_get_events_in_range",
        "doc_list": "doc_list_accessible",
        "doc_recent": "doc_list_recently_updated",
        "doc_recently_updated": "doc_list_recently_updated",
        "recent_docs": "doc_list_recently_updated",
    }
    return aliases.get(name, name)


def _compose_messages_for_chat(ctx: AuthContext, user_question: str, history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    system = (
        "你是企业内部问答助手 FakeBeem。"
        "你必须严格遵守数据权限与组织隔离："
        "组织系统/日程系统为组织内公开，但只能在当前组织内查询；消息系统/文档系统为严格权限控制，只能访问当前登录用户可见的数据。"
        "当需要企业内部数据时，必须通过工具获取，禁止编造。"
        "当工具返回的数据不足以回答时，直接说明无法从可访问数据得出结论。"
        "最终回答尽量简洁，并给出依据引用（doc_id/message_id/event_id/session_id）。"
        "每轮你可以调用 1~N 个工具（受服务端并行上限约束），优先少而精，避免无谓调用。"
        "如果需要调用工具，必须通过 tool_calls 触发，不要在 content 里输出工具调用 JSON。"
    )
    identity = f"当前登录用户：org_id={ctx.org_id}, org_name={ctx.org_name}, user_id={ctx.user_id}, user_name={ctx.user_name}。"
    term_aliases = _format_term_aliases_for_prompt()
    profile_hint = _build_user_profile_hint(ctx)
    extra_blocks = []
    if term_aliases:
        extra_blocks.append(term_aliases)
    if profile_hint:
        extra_blocks.append(profile_hint.strip("\n"))
    extra = ("\n\n" + "\n\n".join(extra_blocks)) if extra_blocks else ""
    messages: list[dict[str, Any]] = [{"role": "system", "content": system + "\n" + identity + extra}]
    for m in history[-20:]:
        role = m.get("role")
        content = m.get("content")
        if role in {"user", "assistant"} and isinstance(content, str):
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_question})
    return messages


def _compose_messages_for_non_internal(ctx: AuthContext, user_question: str, history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    system = (
        "你是企业内部问答助手 FakeBeem。"
        "你必须遵守组织隔离与权限：如果需要企业内部数据但未提供证据，则说明无法确定，禁止编造。"
        "回答尽量简洁。"
    )
    identity = f"当前登录用户：org_id={ctx.org_id}, org_name={ctx.org_name}, user_id={ctx.user_id}, user_name={ctx.user_name}。"
    term_aliases = _format_term_aliases_for_prompt()
    extra = ("\n\n" + term_aliases) if term_aliases else ""
    messages: list[dict[str, Any]] = [{"role": "system", "content": system + "\n" + identity + extra}]
    for m in history[-20:]:
        role = m.get("role")
        content = m.get("content")
        if role in {"user", "assistant"} and isinstance(content, str):
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_question})
    return messages


def _save_tool_run(
    conversation_id: str,
    org_id: str,
    user_id: str,
    trace_id: str,
    step_idx: int,
    model: str,
    tool_call_id: str,
    tool_name: str,
    tool_args_json: str,
    ok_flag: bool,
    error: str | None,
    result_refs_json: str,
    result_summary: str,
    tool_output_bytes: int,
    truncated: bool,
    elapsed_ms: int,
) -> None:
    app_conn.execute(
        """
        INSERT INTO tool_runs(
          id,conversation_id,org_id,user_id,trace_id,step_idx,model,tool_call_id,tool_name,
          tool_args_json,ok,error,result_refs_json,result_summary,tool_output_bytes,truncated,elapsed_ms,created_at_ms
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            str(uuid.uuid4()),
            conversation_id,
            org_id,
            user_id,
            trace_id,
            int(step_idx),
            str(model),
            str(tool_call_id),
            str(tool_name),
            tool_args_json,
            1 if ok_flag else 0,
            error,
            result_refs_json,
            result_summary,
            int(tool_output_bytes),
            1 if truncated else 0,
            int(elapsed_ms),
            now_ms(),
        ),
    )

async def _run_internal_tool_calling_loop(
    ctx: AuthContext,
    conversation_id: str,
    user_question: str,
    history: list[dict[str, Any]],
    model: str,
    temperature: float,
    max_tokens: int,
    reasoning_effort: Any,
) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    trace_id = str(uuid.uuid4())
    messages = _compose_messages_for_chat(ctx, user_question, history)
    max_steps = 10
    max_tool_calls_per_step = 5
    max_tool_output_chars = 12000
    have_recent_contacts = False

    step_idx = 0
    last_resp: dict[str, Any] | None = None
    while step_idx < max_steps:
        req_payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "tools": enterprise_tools,
            "tool_choice": "auto",
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if reasoning_effort is not None:
            req_payload["reasoning_effort"] = reasoning_effort

        if _log_verbose_enabled():
            last_user = ""
            for m in reversed(messages):
                if m.get("role") == "user" and isinstance(m.get("content"), str):
                    last_user = m["content"]
                    break
            logger.info(
                json.dumps(
                    {
                        "type": "tool_loop_model_payload",
                        "conversation_id": conversation_id,
                        "trace_id": trace_id,
                        "step_idx": step_idx,
                        "model": model,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "reasoning_effort": reasoning_effort,
                        "message_count": len(messages),
                        "last_user": last_user if _log_include_user_text() else _text_preview(last_user, 300),
                    },
                    ensure_ascii=False,
                )
            )
        logger.info(
            json.dumps(
                {
                    "type": "tool_loop_model_request",
                    "conversation_id": conversation_id,
                    "trace_id": trace_id,
                    "step_idx": step_idx,
                    "model": model,
                    "message_count": len(messages),
                },
                ensure_ascii=False,
            )
        )
        resp = await model_client.chat_completions(req_payload)
        last_resp = resp
        msg = ((resp.get("choices") or [{}])[0]).get("message") or {}
        tool_calls = _extract_tool_calls_from_message(msg)
        if _log_verbose_enabled():
            assistant_content = msg.get("content") if isinstance(msg, dict) else ""
            tool_names: list[str] = []
            for tc in tool_calls:
                fn = (tc or {}).get("function") or {}
                name = fn.get("name")
                if isinstance(name, str) and name:
                    tool_names.append(_normalize_tool_name(name))
            logger.info(
                json.dumps(
                    {
                        "type": "tool_loop_model_result",
                        "conversation_id": conversation_id,
                        "trace_id": trace_id,
                        "step_idx": step_idx,
                        "assistant_content_head": _text_preview(assistant_content or "", 500),
                        "tool_names": tool_names,
                    },
                    ensure_ascii=False,
                )
            )
        tool_call_source = "model_tool_calls" if tool_calls else ""
        inferred_from_content = False
        if not tool_calls and isinstance(msg.get("content"), str):
            parsed = _try_parse_single_tool_request_from_text(msg.get("content") or "")
            if parsed:
                tool_name_raw, tool_args = parsed
                tool_calls = [
                    {
                        "id": f"parsed_step{step_idx}_tool0",
                        "type": "function",
                        "function": {"name": tool_name_raw, "arguments": json.dumps(tool_args, ensure_ascii=False)},
                    }
                ]
                tool_call_source = "parsed_tool_request"
                inferred_from_content = True
        if not tool_calls and isinstance(msg.get("content"), str):
            inferred = _infer_tool_call_from_bare_parameters(msg.get("content") or "", user_question=user_question)
            if inferred:
                tool_name_raw, tool_args = inferred
                tool_calls = [
                    {
                        "id": f"infer_step{step_idx}_tool0",
                        "type": "function",
                        "function": {"name": tool_name_raw, "arguments": json.dumps(tool_args, ensure_ascii=False)},
                    }
                ]
                tool_call_source = "inferred_bare_params"
                inferred_from_content = True
        if not tool_calls:
            q = user_question
            if ("文档" in q) and any(k in q for k in ["最近", "查看", "访问", "打开", "浏览", "看"]):
                tool_calls = [
                    {
                        "id": f"heur_step{step_idx}_tool0",
                        "type": "function",
                        "function": {"name": "doc_list_recently_updated", "arguments": json.dumps({"limit": 10}, ensure_ascii=False)},
                    }
                ]
                tool_call_source = "heur_doc_recent"
            elif any(k in (q or "") for k in ["leader", "Leader", "上级", "领导", "主管", "汇报对象", "汇报给", "我老板"]):
                tool_calls = [
                    {
                        "id": f"heur_step{step_idx}_tool0",
                        "type": "function",
                        "function": {"name": "org_get_self_profile", "arguments": json.dumps({}, ensure_ascii=False)},
                    }
                ]
                tool_call_source = "heur_leader"
            elif any(k in (q or "") for k in ["会议", "日历", "日程", "安排", "邀约", "参会"]):
                now = now_ms()
                start_ms = now - 30 * 24 * 3600 * 1000
                end_ms = now + 14 * 24 * 3600 * 1000
                tool_calls = [
                    {
                        "id": f"heur_step{step_idx}_tool0",
                        "type": "function",
                        "function": {"name": "cal_get_events_in_range", "arguments": json.dumps({"start_ms": start_ms, "end_ms": end_ms, "user_id": ctx.user_id, "limit": 50}, ensure_ascii=False)},
                    }
                ]
                tool_call_source = "heur_calendar_recent"
            elif any(k in (q or "") for k in ["最近联系人", "最近联系", "聊过天", "聊过", "聊天", "说过话"]) and any(
                k in (q or "") for k in ["谁", "哪些人", "联系人"]
            ) and (not have_recent_contacts):
                tool_calls = [
                    {
                        "id": f"heur_step{step_idx}_tool0",
                        "type": "function",
                        "function": {"name": "im_get_recent_contacts", "arguments": json.dumps({"limit": 10}, ensure_ascii=False)},
                    }
                ]
                tool_call_source = "heur_im_recent_contacts"

        logger.info(
            json.dumps(
                {
                    "type": "tool_loop_model_response",
                    "conversation_id": conversation_id,
                    "trace_id": trace_id,
                    "step_idx": step_idx,
                    "has_tool_calls": bool(tool_calls),
                    "tool_call_count": len(tool_calls),
                    "tool_call_source": tool_call_source,
                },
                ensure_ascii=False,
            )
        )

        if not tool_calls:
            break

        assistant_content = "" if inferred_from_content else (msg.get("content") or "")
        assistant_msg: dict[str, Any] = {"role": "assistant", "content": assistant_content, "tool_calls": tool_calls}
        messages.append(assistant_msg)

        for idx, tc in enumerate(tool_calls[:max_tool_calls_per_step]):
            tool_call_id = str(tc.get("id") or f"step{step_idx}_tool{idx}")
            fn = tc.get("function") or {}
            tool_name = _normalize_tool_name(str(fn.get("name") or ""))
            tool_args = _safe_parse_tool_arguments(fn.get("arguments"))

            started = now_ms()
            tool_ok = False
            tool_error: str | None = None
            result: dict[str, Any]
            try:
                result = execute_enterprise_tool(enterprise_conn, ctx.org_id, ctx.user_id, tool_name, tool_args)
                tool_ok = bool(result.get("ok"))
            except Exception as e:
                tool_error = str(e)
                result = {"ok": False, "tool": tool_name, "error": {"code": "tool_exec_error", "message": tool_error}, "data": None, "summary": "tool_exec_error", "evidence_refs": {}, "truncated": False}
            elapsed = now_ms() - started

            result_str = json.dumps(result, ensure_ascii=False)
            truncated = False
            if len(result_str) > max_tool_output_chars:
                result_str = result_str[:max_tool_output_chars]
                truncated = True

            result_refs_json = json.dumps(result.get("evidence_refs") or {}, ensure_ascii=False)
            result_summary = str(result.get("summary") or "")
            _save_tool_run(
                conversation_id=conversation_id,
                org_id=ctx.org_id,
                user_id=ctx.user_id,
                trace_id=trace_id,
                step_idx=step_idx,
                model=model,
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                tool_args_json=json.dumps(tool_args, ensure_ascii=False),
                ok_flag=tool_ok,
                error=tool_error or (None if tool_ok else json.dumps((result.get("error") or {}), ensure_ascii=False)),
                result_refs_json=result_refs_json,
                result_summary=result_summary,
                tool_output_bytes=len(result_str.encode("utf-8")),
                truncated=truncated or bool(result.get("truncated")),
                elapsed_ms=int(elapsed),
            )
            app_conn.commit()

            logger.info(
                json.dumps(
                    {
                        "type": "tool_execute",
                        "conversation_id": conversation_id,
                        "trace_id": trace_id,
                        "step_idx": step_idx,
                        "tool_call_id": tool_call_id,
                        "tool_name": tool_name,
                        "ok": tool_ok,
                        "elapsed_ms": int(elapsed),
                        "output_chars": len(result_str),
                        "truncated": truncated or bool(result.get("truncated")),
                    },
                    ensure_ascii=False,
                )
            )
            if _log_verbose_enabled():
                logger.info(
                    json.dumps(
                        {
                            "type": "tool_execute_payload",
                            "conversation_id": conversation_id,
                            "trace_id": trace_id,
                            "step_idx": step_idx,
                            "tool_call_id": tool_call_id,
                            "tool_name": tool_name,
                            "tool_args_head": _text_preview(json.dumps(tool_args, ensure_ascii=False), 800),
                            "tool_result_summary": result_summary,
                            "tool_refs": result.get("evidence_refs") or {},
                        },
                        ensure_ascii=False,
                    )
                )

            messages.append({"role": "tool", "tool_call_id": tool_call_id, "content": result_str})
            if tool_ok and tool_name == "im_get_recent_contacts":
                have_recent_contacts = True

        step_idx += 1

    if last_resp is None:
        last_resp = {
            "choices": [
                {"message": {"role": "assistant", "content": "当前无法获取足够的可访问证据来回答该问题。"}},
            ]
        }
    return trace_id, messages, last_resp


@app.post("/v1/chat/completions")
async def chat_completions(request: Request, ctx: AuthContext = Depends(require_auth)) -> Response:
    payload = await request.json()
    stream = bool(payload.get("stream"))
    model = payload.get("model") or "gpt-oss-120b"
    conversation_id = (payload.get("metadata") or {}).get("conversation_id")
    if not conversation_id:
        raise HTTPException(status_code=400, detail="missing_conversation_id")

    conv = _ensure_conversation_owner(conversation_id, ctx)

    messages_in = payload.get("messages") or []
    if not isinstance(messages_in, list) or not messages_in:
        raise HTTPException(status_code=400, detail="missing_messages")

    last = messages_in[-1]
    if last.get("role") != "user" or not isinstance(last.get("content"), str):
        raise HTTPException(status_code=400, detail="last_message_must_be_user")
    user_question = last["content"].strip()

    if _log_verbose_enabled():
        logger.info(
            json.dumps(
                {
                    "type": "chat_received",
                    "conversation_id": conversation_id,
                    "org_id": ctx.org_id,
                    "user_id": ctx.user_id,
                    "model": model,
                    "stream": stream,
                    "temperature": payload.get("temperature", 0.2),
                    "max_tokens": payload.get("max_tokens", 4096),
                    "reasoning_effort": payload.get("reasoning_effort") if "reasoning_effort" in payload else None,
                    "question": user_question if _log_include_user_text() else _text_preview(user_question, 400),
                    "question_len": len(user_question),
                },
                ensure_ascii=False,
            )
        )

    key = (ctx.org_id, ctx.user_id, conversation_id)
    if key in inflight:
        raise HTTPException(status_code=409, detail="conversation_inflight")
    inflight[key] = str(uuid.uuid4())

    try:
        history_rows = app_conn.execute(
            "SELECT role, content FROM conversation_messages WHERE conversation_id=? ORDER BY created_at_ms ASC",
            (conversation_id,),
        ).fetchall()
        history = [dict(r) for r in history_rows]
        routing: dict[str, Any]
        try:
            routing = await _route_with_model(
                ctx=ctx,
                conversation_id=conversation_id,
                user_question=user_question,
                history=history,
                model=model,
            )
        except Exception as e:
            fallback_enabled = os.getenv("QA_ROUTE_FALLBACK", "1") != "0"
            if fallback_enabled:
                routing = classify_internal(ctx.org_id, user_question, enterprise_dict)
                routing["fallback"] = "keyword_rules"
            else:
                routing = {"is_internal": False, "domains": [], "fallback": "disabled"}
            routing["route_error"] = str(e)
        logger.info(
            json.dumps(
                {
                    "type": "chat_route",
                    "conversation_id": conversation_id,
                    "org_id": ctx.org_id,
                    "user_id": ctx.user_id,
                    "is_internal": routing.get("is_internal"),
                    "domains": routing.get("domains"),
                    "confidence": routing.get("confidence"),
                    "fallback": routing.get("fallback"),
                    "route_error": routing.get("route_error"),
                    "question_len": len(user_question),
                    "stream": stream,
                },
                ensure_ascii=False,
            )
        )
    except Exception:
        inflight.pop(key, None)
        raise

    temperature = float(payload.get("temperature", 0.2))
    max_tokens = int(payload.get("max_tokens", 4096))
    reasoning_effort = payload.get("reasoning_effort") if "reasoning_effort" in payload else None

    if routing.get("is_internal"):
        try:
            trace_id, tool_messages, final_resp = await _run_internal_tool_calling_loop(
                ctx=ctx,
                conversation_id=conversation_id,
                user_question=user_question,
                history=history,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                reasoning_effort=reasoning_effort,
            )
        except Exception:
            inflight.pop(key, None)
            raise
        if stream:
            loop_msg_raw = ((final_resp.get("choices") or [{}])[0]).get("message")
            loop_msg = loop_msg_raw if isinstance(loop_msg_raw, dict) else {}
            loop_content = loop_msg.get("content") or ""
            loop_reasoning = loop_msg.get("reasoning_content") or ""
            loop_tool_calls = _extract_tool_calls_from_message(loop_msg)

            _save_message(conversation_id, "user", user_question)
            if conv.get("title") == "新会话":
                title = _title_from_first_message(user_question)
                app_conn.execute(
                    "UPDATE conversations SET title=? WHERE id=?",
                    (title, conversation_id),
                )
            _update_conversation_updated(conversation_id)
            app_conn.commit()

            async def _stream_internal() -> AsyncIterator[bytes]:
                buffer = ""
                answer = ""
                reasoning = ""
                cancelled = False
                try:
                    def _emit_delta(delta: dict[str, Any]) -> bytes:
                        payload = {"choices": [{"delta": delta}]}
                        return ("data: " + json.dumps(payload, ensure_ascii=False) + "\n\n").encode("utf-8")

                    def _chunks(s: str, size: int = 160) -> list[str]:
                        if not s:
                            return []
                        return [s[i : i + size] for i in range(0, len(s), size)]

                    if (not loop_tool_calls) and loop_content.strip():
                        answer = loop_content
                        reasoning = loop_reasoning

                        for part in _chunks(reasoning, 200):
                            yield _emit_delta({"reasoning_content": part})
                            await asyncio.sleep(0)
                        for part in _chunks(answer, 200):
                            yield _emit_delta({"content": part})
                            await asyncio.sleep(0)
                        yield b"data: [DONE]\n\n"
                        return

                    if (not loop_tool_calls) and (not loop_content.strip()) and loop_reasoning.strip():
                        final_max_tokens = max_tokens
                        if final_max_tokens < 4096:
                            final_max_tokens = 4096
                        finalizer_payload: dict[str, Any] = {
                            "model": model,
                            "messages": tool_messages
                            + [
                                {
                                    "role": "user",
                                    "content": "请基于以上证据给出最终答复正文。不要输出推理过程，不要输出任何工具调用。",
                                }
                            ],
                            "stream": False,
                            "max_tokens": final_max_tokens,
                            "temperature": temperature,
                        }
                        if reasoning_effort is not None:
                            finalizer_payload["reasoning_effort"] = "low" if reasoning_effort == "high" else reasoning_effort
                        finalizer_resp = await model_client.chat_completions(finalizer_payload)
                        finalizer_msg = ((finalizer_resp.get("choices") or [{}])[0]).get("message") or {}
                        answer = (finalizer_msg.get("content") or "").strip()
                        reasoning = (finalizer_msg.get("reasoning_content") or "").strip() or loop_reasoning
                        if not answer:
                            answer = "抱歉，当前模型未生成最终答复正文，请稍后重试。"

                        for part in _chunks(reasoning, 200):
                            yield _emit_delta({"reasoning_content": part})
                            await asyncio.sleep(0)
                        for part in _chunks(answer, 200):
                            yield _emit_delta({"content": part})
                            await asyncio.sleep(0)
                        yield b"data: [DONE]\n\n"
                        return

                    final_max_tokens = max_tokens
                    if final_max_tokens < 4096:
                        final_max_tokens = 4096
                    final_payload: dict[str, Any] = {
                        "model": model,
                        "messages": tool_messages,
                        "stream": True,
                        "max_tokens": final_max_tokens,
                        "temperature": temperature,
                    }
                    if reasoning_effort is not None:
                        if isinstance(reasoning_effort, str) and reasoning_effort == "high":
                            final_payload["reasoning_effort"] = "low"
                        else:
                            final_payload["reasoning_effort"] = reasoning_effort
                    if _log_verbose_enabled():
                        logger.info(
                            json.dumps(
                                {
                                    "type": "final_model_payload",
                                    "conversation_id": conversation_id,
                                    "trace_id": trace_id,
                                    "org_id": ctx.org_id,
                                    "user_id": ctx.user_id,
                                    "model": model,
                                    "stream": True,
                                    "temperature": temperature,
                                    "max_tokens": final_payload.get("max_tokens"),
                                    "reasoning_effort": final_payload.get("reasoning_effort"),
                                    "message_count": len(tool_messages),
                                },
                                ensure_ascii=False,
                            )
                        )

                    async for chunk in model_client.stream_chat_completions(final_payload):
                        try:
                            text = chunk.decode("utf-8", errors="ignore")
                        except Exception:
                            text = ""
                        buffer += text
                        events, buffer = sse_json_lines_from_bytes(buffer)
                        for ev in events:
                            if ev.get("_done"):
                                continue
                            try:
                                choice0 = (ev.get("choices") or [None])[0] or {}
                                delta = choice0.get("delta") or {}
                                if isinstance(delta.get("content"), str):
                                    answer += delta["content"]
                                if isinstance(delta.get("reasoning_content"), str):
                                    reasoning += delta["reasoning_content"]
                            except Exception:
                                pass
                        yield chunk
                    if buffer:
                        yield buffer.encode("utf-8")
                except Exception:
                    cancelled = True
                    return
                finally:
                    inflight.pop(key, None)
                    if answer.strip() or reasoning.strip():
                        _save_message(conversation_id, "assistant", (answer or "").strip(), reasoning_content=(reasoning or "").strip() or None)
                        _update_conversation_updated(conversation_id)
                        app_conn.commit()
                    logger.info(
                        json.dumps(
                            {
                                "type": "chat_done",
                                "conversation_id": conversation_id,
                                "trace_id": trace_id,
                                "org_id": ctx.org_id,
                                "user_id": ctx.user_id,
                                "stream": True,
                                "cancelled": cancelled,
                                "answer_len": len(answer),
                                "reasoning_len": len(reasoning),
                            },
                            ensure_ascii=False,
                        )
                    )

            return StreamingResponse(_stream_internal(), media_type="text/event-stream")

        inflight.pop(key, None)
        msg = ((final_resp.get("choices") or [{}])[0]).get("message") or {}
        content = msg.get("content") or ""
        reasoning_content = msg.get("reasoning_content") or ""
        if _log_verbose_enabled():
            logger.info(
                json.dumps(
                    {
                        "type": "final_model_result",
                        "conversation_id": conversation_id,
                        "trace_id": trace_id,
                        "org_id": ctx.org_id,
                        "user_id": ctx.user_id,
                        "stream": False,
                        "answer_head": _text_preview(content, 800),
                        "reasoning_head": _text_preview(reasoning_content, 800),
                    },
                    ensure_ascii=False,
                )
            )
        _save_message(conversation_id, "user", user_question)
        if conv.get("title") == "新会话":
            title = _title_from_first_message(user_question)
            app_conn.execute(
                "UPDATE conversations SET title=? WHERE id=?",
                (title, conversation_id),
            )
        if content.strip() or reasoning_content.strip():
            _save_message(conversation_id, "assistant", content.strip(), reasoning_content=reasoning_content.strip() or None)
        _update_conversation_updated(conversation_id)
        app_conn.commit()
        logger.info(
            json.dumps(
                {
                    "type": "chat_done",
                    "conversation_id": conversation_id,
                    "trace_id": trace_id,
                    "org_id": ctx.org_id,
                    "user_id": ctx.user_id,
                    "stream": False,
                    "cancelled": False,
                    "answer_len": len(content or ""),
                    "reasoning_len": len(reasoning_content or ""),
                },
                ensure_ascii=False,
            )
        )
        return Response(content=json.dumps(final_resp), media_type="application/json")

    model_messages = _compose_messages_for_non_internal(ctx, user_question, history)
    req_payload: dict[str, Any] = {
        "model": model,
        "messages": model_messages,
        "stream": stream,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if reasoning_effort is not None:
        req_payload["reasoning_effort"] = reasoning_effort
    if _log_verbose_enabled():
        logger.info(
            json.dumps(
                {
                    "type": "chat_model_payload",
                    "conversation_id": conversation_id,
                    "org_id": ctx.org_id,
                    "user_id": ctx.user_id,
                    "model": model,
                    "stream": stream,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "reasoning_effort": reasoning_effort,
                    "message_count": len(model_messages),
                },
                ensure_ascii=False,
            )
        )

    _save_message(conversation_id, "user", user_question)
    if conv.get("title") == "新会话":
        title = _title_from_first_message(user_question)
        app_conn.execute(
            "UPDATE conversations SET title=? WHERE id=?",
            (title, conversation_id),
        )
    _update_conversation_updated(conversation_id)
    app_conn.commit()

    async def _stream() -> AsyncIterator[bytes]:
        buffer = ""
        answer = ""
        reasoning = ""
        cancelled = False
        try:
            async for chunk in model_client.stream_chat_completions(req_payload):
                try:
                    text = chunk.decode("utf-8", errors="ignore")
                except Exception:
                    text = ""
                buffer += text
                events, buffer = sse_json_lines_from_bytes(buffer)
                for ev in events:
                    if ev.get("_done"):
                        continue
                    try:
                        choice0 = (ev.get("choices") or [None])[0] or {}
                        delta = choice0.get("delta") or {}
                        if isinstance(delta.get("content"), str):
                            answer += delta["content"]
                        if isinstance(delta.get("reasoning_content"), str):
                            reasoning += delta["reasoning_content"]
                    except Exception:
                        pass
                yield chunk
            if buffer:
                yield buffer.encode("utf-8")
        except Exception:
            cancelled = True
            return
        finally:
            inflight.pop(key, None)
            if answer.strip() or reasoning.strip():
                _save_message(conversation_id, "assistant", (answer or "").strip(), reasoning_content=(reasoning or "").strip() or None)
                _update_conversation_updated(conversation_id)
                app_conn.commit()
            logger.info(
                json.dumps(
                    {
                        "type": "chat_done",
                        "conversation_id": conversation_id,
                        "org_id": ctx.org_id,
                        "user_id": ctx.user_id,
                        "stream": True,
                        "cancelled": cancelled,
                        "answer_len": len(answer),
                        "reasoning_len": len(reasoning),
                    },
                    ensure_ascii=False,
                )
            )

    if stream:
        return StreamingResponse(_stream(), media_type="text/event-stream")

    try:
        resp_json = await model_client.chat_completions(req_payload)
    finally:
        inflight.pop(key, None)

    msg = (resp_json.get("choices") or [{}])[0].get("message") or {}
    content = msg.get("content") or ""
    reasoning_content = msg.get("reasoning_content") or ""
    if content.strip() or reasoning_content.strip():
        _save_message(conversation_id, "assistant", content.strip(), reasoning_content=reasoning_content.strip() or None)
        _update_conversation_updated(conversation_id)
        app_conn.commit()
    logger.info(
        json.dumps(
            {
                "type": "chat_done",
                "conversation_id": conversation_id,
                "org_id": ctx.org_id,
                "user_id": ctx.user_id,
                "stream": False,
                "cancelled": False,
                "answer_len": len(content or ""),
                "reasoning_len": len(reasoning_content or ""),
            },
            ensure_ascii=False,
        )
    )

    return Response(content=json.dumps(resp_json), media_type="application/json")


WEB_DIR = ROOT_DIR / "qa_gateway" / "web"
app.mount("/assets", StaticFiles(directory=WEB_DIR), name="assets")


@app.get("/")
def index() -> Response:
    return FileResponse(WEB_DIR / "index.html", headers={"Cache-Control": "no-store"})
