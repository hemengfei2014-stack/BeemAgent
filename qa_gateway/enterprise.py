import re
import sqlite3
import time
from dataclasses import dataclass
from typing import Any
from datetime import datetime, timedelta


@dataclass(frozen=True)
class EnterpriseDictionaries:
    org_names: set[str]
    user_names_by_org: dict[str, set[str]]
    dept_names_by_org: dict[str, set[str]]


def build_dictionaries(conn: sqlite3.Connection) -> EnterpriseDictionaries:
    org_names = {r["name"] for r in conn.execute("SELECT name FROM org").fetchall()}
    user_names_by_org: dict[str, set[str]] = {}
    dept_names_by_org: dict[str, set[str]] = {}
    for r in conn.execute("SELECT org_id, name FROM user").fetchall():
        user_names_by_org.setdefault(r["org_id"], set()).add(r["name"])
    for r in conn.execute("SELECT org_id, name FROM dept").fetchall():
        dept_names_by_org.setdefault(r["org_id"], set()).add(r["name"])
    return EnterpriseDictionaries(
        org_names=org_names,
        user_names_by_org=user_names_by_org,
        dept_names_by_org=dept_names_by_org,
    )


def _contains_any(text: str, candidates: set[str]) -> bool:
    for c in candidates:
        if c and c in text:
            return True
    return False


def _extract_time_range_ms(text: str) -> tuple[int, int] | None:
    now = int(time.time())
    local = time.localtime(now)
    base_day_start = int(time.mktime((local.tm_year, local.tm_mon, local.tm_mday, 0, 0, 0, 0, 0, -1))) * 1000

    day_offset = 0
    if "明天" in text:
        day_offset = 1
    if "后天" in text:
        day_offset = 2

    hhmm = re.findall(r"(\d{1,2}):(\d{2})", text)
    if len(hhmm) >= 1:
        h1, m1 = int(hhmm[0][0]), int(hhmm[0][1])
        start = base_day_start + day_offset * 86400000 + (h1 * 60 + m1) * 60000
        end = start + 3600000
        if len(hhmm) >= 2:
            h2, m2 = int(hhmm[1][0]), int(hhmm[1][1])
            end = base_day_start + day_offset * 86400000 + (h2 * 60 + m2) * 60000
        if end < start:
            end = start + 3600000
        return start, end

    if any(k in text for k in ["上午", "下午", "晚上", "今天", "明天", "后天"]):
        if "上午" in text:
            start = base_day_start + day_offset * 86400000 + 9 * 3600000
            end = base_day_start + day_offset * 86400000 + 12 * 3600000
            return start, end
        if "下午" in text:
            start = base_day_start + day_offset * 86400000 + 13 * 3600000
            end = base_day_start + day_offset * 86400000 + 18 * 3600000
            return start, end
        if "晚上" in text:
            start = base_day_start + day_offset * 86400000 + 18 * 3600000
            end = base_day_start + day_offset * 86400000 + 22 * 3600000
            return start, end
        start = base_day_start + day_offset * 86400000
        end = start + 86400000
        return start, end

    return None


def classify_internal(
    org_id: str,
    question: str,
    dictionaries: EnterpriseDictionaries,
) -> dict[str, Any]:
    text = question.strip()
    text_lower = text.lower()

    org_kw = {
        "组织",
        "公司",
        "部门",
        "领导",
        "上级",
        "leader",
        "manager",
        "邮箱",
        "手机号",
        "工号",
        "同事",
        "CEO",
        "ceo",
        "我的信息",
        "个人信息",
        "个人资料",
        "我的资料",
        "介绍我",
        "自我介绍",
        "我的部门",
        "我的岗位",
        "我的职位",
        "我的领导",
        "我的上级",
        "我的邮箱",
        "我的手机号",
    }
    msg_kw = {"聊天", "聊过天", "最近联系人", "最近联系", "消息", "会话", "群", "单聊", "session", "群聊", "我和", "我们聊"}
    doc_kw = {"文档", "doc", "pdf", "sheet", "slide", "共享", "权限", "我能访问", "搜索"}
    cal_kw = {"日历", "会议", "邀约", "空闲", "忙", "可用", "参会", "时间段"}

    hit_org = any((k in text) or (k.isascii() and k.lower() in text_lower) for k in org_kw) or _contains_any(text, dictionaries.org_names)
    hit_msg = any((k in text) or (k.isascii() and k.lower() in text_lower) for k in msg_kw)
    hit_doc = any((k in text) or (k.isascii() and k.lower() in text_lower) for k in doc_kw)
    hit_cal = any((k in text) or (k.isascii() and k.lower() in text_lower) for k in cal_kw)

    user_names = dictionaries.user_names_by_org.get(org_id, set())
    dept_names = dictionaries.dept_names_by_org.get(org_id, set())
    hit_entity = _contains_any(text, user_names) or _contains_any(text, dept_names)

    domains: list[str] = []
    if hit_org or hit_entity:
        domains.append("org")
    if hit_msg:
        domains.append("message")
    if hit_doc:
        domains.append("doc")
    if hit_cal:
        domains.append("calendar")

    is_internal = bool(domains)
    if not is_internal and hit_entity:
        is_internal = True
        domains = ["org"]

    return {
        "is_internal": is_internal,
        "domains": sorted(set(domains)),
        "time_range_ms": _extract_time_range_ms(text),
    }


def _lookup_user_by_name(conn: sqlite3.Connection, org_id: str, name: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM user WHERE org_id=? AND name=? LIMIT 1",
        (org_id, name),
    ).fetchone()


def _lookup_user_by_id(conn: sqlite3.Connection, org_id: str, user_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM user WHERE org_id=? AND id=? LIMIT 1",
        (org_id, user_id),
    ).fetchone()


def _epoch_seconds_to_date_str(epoch_seconds: str) -> str | None:
    try:
        ts = int(str(epoch_seconds).strip())
        if ts <= 0:
            return None
        return time.strftime("%Y-%m-%d", time.localtime(ts))
    except Exception:
        return None


def _mask_phone_cn(phone: str) -> str:
    p = re.sub(r"\D+", "", phone or "")
    if len(p) < 7:
        return phone
    return f"+86-{p[:3]}****{p[-4:]}"


def _gender_label(g: str) -> str:
    if str(g) == "1":
        return "Male"
    if str(g) == "2":
        return "Female"
    return "Unknown"


def _role_title(role: str) -> str:
    mapping = {
        "1": "Product Manager",
        "2": "Software Engineer",
        "3": "ML Engineer",
        "4": "HR",
        "5": "Android Engineer",
        "6": "iOS Engineer",
        "7": "QA Engineer",
        "8": "L2 Dept Leader",
        "9": "L1 Dept Leader",
    }
    return mapping.get(str(role), str(role))


def _query_user_departments(conn: sqlite3.Connection, org_id: str, user_id: str) -> list[dict[str, str]]:
    rows = conn.execute(
        """
        SELECT d.id AS dept_id, d.name AS dept_name
        FROM dept_user du
        JOIN dept d ON d.org_id=du.org_id AND d.id=du.dept_id
        WHERE du.org_id=? AND du.user_id=?
        ORDER BY d.level ASC, d.name ASC
        """,
        (org_id, user_id),
    ).fetchall()
    return [{"dept_id": r["dept_id"], "name": r["dept_name"]} for r in rows]



def query_org_answers(conn: sqlite3.Connection, org_id: str, viewer_user_id: str, question: str) -> dict[str, Any]:
    q = question.strip()
    evidence: dict[str, Any] = {"domain": "org", "items": []}
    q_lower = q.lower()

    if any(k in q for k in ["我的信息", "个人信息", "个人资料", "我的资料", "介绍我", "自我介绍"]) or any(
        k in q for k in ["我的部门", "我的岗位", "我的职位", "我的领导", "我的上级", "我的邮箱", "我的手机号"]
    ):
        user = _lookup_user_by_id(conn, org_id, viewer_user_id)
        org = conn.execute("SELECT * FROM org WHERE id=?", (org_id,)).fetchone()
        if not user or not org:
            evidence["items"].append({"type": "self_profile_not_found"})
            return evidence
        manager = _lookup_user_by_id(conn, org_id, user["manager_id"]) if user["manager_id"] else None
        depts = _query_user_departments(conn, org_id, viewer_user_id)
        evidence["items"].append(
            {
                "type": "self_profile",
                "user": {
                    "user_id": user["id"],
                    "user_name": user["name"],
                    "org_id": org_id,
                    "org_name": org["name"],
                    "department": depts,
                    "direct_manager": {"user_id": manager["id"], "user_name": manager["name"]} if manager else None,
                    "job_title": _role_title(user["role"]),
                    "phone": _mask_phone_cn(user["mobile"]),
                    "email": user["email"],
                    "join_date": _epoch_seconds_to_date_str(user["join_date"]),
                    "gender": _gender_label(user["gender"]),
                    "birthday": _epoch_seconds_to_date_str(user["birthday"]),
                },
            }
        )
        return evidence

    if ("ceo" in q_lower) or ("老板" in q) or ("负责人" in q):
        org = conn.execute("SELECT * FROM org WHERE id=?", (org_id,)).fetchone()
        if org:
            ceo = _lookup_user_by_id(conn, org_id, org["owner_user_id"])
            if ceo:
                evidence["items"].append(
                    {"type": "org_ceo", "org_id": org_id, "user_id": ceo["id"], "name": ceo["name"]}
                )

    if ("部门" in q) and any(k in q for k in ["哪些", "有哪些", "有什么", "列出", "列表", "都有哪些", "都有什么"]):
        rows = conn.execute(
            """
            SELECT
              d.id AS dept_id,
              d.name AS dept_name,
              d.parent_id AS parent_id,
              d.level AS level,
              d.leader_id AS leader_id,
              u.name AS leader_name
            FROM dept d
            LEFT JOIN user u ON u.org_id = d.org_id AND u.id = d.leader_id
            WHERE d.org_id=?
            ORDER BY CAST(d.level AS INTEGER) ASC, d.name ASC
            """,
            (org_id,),
        ).fetchall()
        evidence["items"].append(
            {
                "type": "org_departments",
                "org_id": org_id,
                "count": len(rows),
                "departments": [
                    {
                        "dept_id": r["dept_id"],
                        "name": r["dept_name"],
                        "parent_id": r["parent_id"],
                        "level": r["level"],
                        "leader": {"user_id": r["leader_id"], "user_name": r["leader_name"]}
                        if r["leader_id"] and r["leader_name"]
                        else ({"user_id": r["leader_id"]} if r["leader_id"] else None),
                    }
                    for r in rows
                ],
            }
        )
        return evidence

    m = re.search(r"(\d{5})", q)
    target_user = None
    if m:
        target_user = _lookup_user_by_id(conn, org_id, m.group(1))
    if not target_user:
        for name in conn.execute("SELECT name FROM user WHERE org_id=?", (org_id,)).fetchall():
            if name["name"] and name["name"] in q:
                target_user = _lookup_user_by_name(conn, org_id, name["name"])
                break

    if "多少人" in q or "人数" in q:
        n = conn.execute("SELECT COUNT(*) AS c FROM user WHERE org_id=?", (org_id,)).fetchone()["c"]
        evidence["items"].append({"type": "org_headcount", "org_id": org_id, "count": n})
        return evidence

    if target_user and ("领导" in q or "上级" in q):
        manager_id = target_user["manager_id"]
        manager = _lookup_user_by_id(conn, org_id, manager_id) if manager_id else None
        evidence["items"].append(
            {
                "type": "user_manager",
                "target_user": {"id": target_user["id"], "name": target_user["name"]},
                "manager": {"id": manager["id"], "name": manager["name"]} if manager else None,
            }
        )
        return evidence

    if target_user and ("邮箱" in q or "email" in q.lower()):
        evidence["items"].append(
            {
                "type": "user_email",
                "target_user": {"id": target_user["id"], "name": target_user["name"]},
                "email": target_user["email"],
            }
        )
        return evidence

    if target_user and ("手机" in q or "手机号" in q or "电话" in q):
        evidence["items"].append(
            {
                "type": "user_mobile",
                "target_user": {"id": target_user["id"], "name": target_user["name"]},
                "mobile": target_user["mobile"],
            }
        )
        return evidence

    if target_user and ("部门" in q or "团队" in q):
        rows = _query_user_departments(conn, org_id, target_user["id"])
        evidence["items"].append(
            {
                "type": "user_departments",
                "target_user": {"id": target_user["id"], "name": target_user["name"]},
                "departments": rows,
            }
        )
        return evidence

    if not evidence["items"]:
        evidence["items"].append({"type": "org_fallback", "hint": "未匹配到可计算的组织问题模式"})
    return evidence


def query_doc_answers(conn: sqlite3.Connection, org_id: str, viewer_user_id: str, question: str) -> dict[str, Any]:
    q = question.strip()
    evidence: dict[str, Any] = {"domain": "doc", "items": []}

    accessible = conn.execute(
        "SELECT doc_id FROM doc_user_access WHERE org_id=? AND user_id=?",
        (org_id, viewer_user_id),
    ).fetchall()
    allowed_doc_ids = {r["doc_id"] for r in accessible}

    if "能访问" in q or "可访问" in q:
        docs = conn.execute(
            """
            SELECT doc_id, title, ctype, owner
            FROM doc
            WHERE org_id=? AND doc_id IN (%s)
            ORDER BY create_time DESC
            LIMIT 50
            """
            % (",".join(["?"] * max(1, len(allowed_doc_ids)))),
            tuple([org_id] + list(allowed_doc_ids)) if allowed_doc_ids else (org_id, ""),
        ).fetchall()
        evidence["items"].append(
            {
                "type": "doc_access_list",
                "count": len(allowed_doc_ids),
                "docs": [{"doc_id": r["doc_id"], "title": r["title"], "ctype": r["ctype"], "owner": r["owner"]} for r in docs],
            }
        )
        return evidence

    keywords = []
    for token in re.findall(r"[\u4e00-\u9fff]{2,}|[a-zA-Z0-9_]{3,}", q):
        if token in {"文档", "搜索", "相关"}:
            continue
        keywords.append(token)
    keywords = keywords[:5]

    if not keywords:
        evidence["items"].append({"type": "doc_fallback", "hint": "未提取到可用于搜索的关键词"})
        return evidence

    query = " AND ".join(keywords)
    rows = conn.execute(
        """
        SELECT doc_id, title, ctype, owner
        FROM doc_fts
        JOIN doc ON doc.org_id = doc_fts.org_id AND doc.doc_id = doc_fts.doc_id
        WHERE doc_fts MATCH ? AND doc_fts.org_id = ?
        LIMIT 10
        """,
        (query, org_id),
    ).fetchall()
    filtered = [r for r in rows if r["doc_id"] in allowed_doc_ids]
    evidence["items"].append(
        {
            "type": "doc_search",
            "keywords": keywords,
            "results": [
                {"doc_id": r["doc_id"], "title": r["title"], "ctype": r["ctype"], "owner": r["owner"]}
                for r in filtered
            ],
        }
    )
    return evidence


def query_message_answers(conn: sqlite3.Connection, org_id: str, viewer_user_id: str, question: str) -> dict[str, Any]:
    q = question.strip()
    evidence: dict[str, Any] = {"domain": "message", "items": []}

    sessions = conn.execute(
        "SELECT session_id FROM im_user_session WHERE org_id=? AND user_id=?",
        (org_id, viewer_user_id),
    ).fetchall()
    allowed_sessions = {r["session_id"] for r in sessions}

    m = re.search(r"(\d{5})", q)
    if m and ("我和" in q or "我们" in q or "聊天" in q):
        other = m.group(1)
        a, b = sorted([viewer_user_id, other])
        session_id = f"{a}_{b}"
        if session_id not in allowed_sessions:
            evidence["items"].append({"type": "message_denied", "session_id": session_id})
            return evidence
        msgs = conn.execute(
            """
            SELECT message_id, send_time_ms, from_user_id, content
            FROM im_message
            WHERE org_id=? AND session_id=?
            ORDER BY send_time_ms DESC
            LIMIT 20
            """,
            (org_id, session_id),
        ).fetchall()
        evidence["items"].append(
            {
                "type": "message_recent",
                "session_id": session_id,
                "messages": [
                    {
                        "message_id": r["message_id"],
                        "send_time_ms": r["send_time_ms"],
                        "from_user_id": r["from_user_id"],
                        "content": r["content"][:200],
                    }
                    for r in reversed(msgs)
                ],
            }
        )
        return evidence

    kw = None
    if "关键词" in q:
        m2 = re.search(r"关键词[：: ]*([^\s，。]+)", q)
        if m2:
            kw = m2.group(1).strip()
    if not kw:
        for token in re.findall(r"[\u4e00-\u9fff]{2,}", q):
            if token not in {"聊天", "消息", "会话", "群聊", "单聊", "最近"}:
                kw = token
                break

    if kw:
        msgs = conn.execute(
            """
            SELECT message_id, send_time_ms, from_user_id, session_id, content
            FROM im_message
            WHERE org_id=? AND content LIKE ?
            ORDER BY send_time_ms DESC
            LIMIT 50
            """,
            (org_id, f"%{kw}%"),
        ).fetchall()
        filtered = [r for r in msgs if r["session_id"] in allowed_sessions]
        evidence["items"].append(
            {
                "type": "message_search",
                "keyword": kw,
                "matches": [
                    {
                        "message_id": r["message_id"],
                        "send_time_ms": r["send_time_ms"],
                        "from_user_id": r["from_user_id"],
                        "session_id": r["session_id"],
                        "content": r["content"][:200],
                    }
                    for r in filtered[:20]
                ],
            }
        )
        return evidence

    evidence["items"].append({"type": "message_fallback", "hint": "未匹配到可计算的消息问题模式"})
    return evidence


def query_calendar_answers(conn: sqlite3.Connection, org_id: str, viewer_user_id: str, question: str) -> dict[str, Any]:
    q = question.strip()
    evidence: dict[str, Any] = {"domain": "calendar", "items": []}

    time_range = _extract_time_range_ms(q)
    target_user = viewer_user_id
    m = re.search(r"(\d{5})", q)
    if m:
        target_user = m.group(1)

    if time_range:
        start_ms, end_ms = time_range
        rows = conn.execute(
            """
            SELECT e.event_id, e.subject, e.start_time, e.end_time, e.organizer_id
            FROM calendar_event e
            JOIN calendar_event_participant p ON p.event_id = e.event_id
            WHERE p.user_id = ?
              AND NOT (e.end_time <= ? OR e.start_time >= ?)
            ORDER BY e.start_time ASC
            LIMIT 20
            """,
            (target_user, start_ms, end_ms),
        ).fetchall()
        evidence["items"].append(
            {
                "type": "calendar_events_in_range",
                "user_id": target_user,
                "time_range_ms": [start_ms, end_ms],
                "events": [
                    {
                        "event_id": r["event_id"],
                        "subject": r["subject"],
                        "start_time": r["start_time"],
                        "end_time": r["end_time"],
                        "organizer_id": r["organizer_id"],
                    }
                    for r in rows
                ],
            }
        )
        if ("有空" in q or "空闲" in q or "忙" in q) and len(rows) == 0:
            evidence["items"].append({"type": "calendar_free", "user_id": target_user, "time_range_ms": [start_ms, end_ms]})
        if ("有空" in q or "空闲" in q or "忙" in q) and len(rows) > 0:
            evidence["items"].append({"type": "calendar_busy", "user_id": target_user, "time_range_ms": [start_ms, end_ms]})
        return evidence

    kw = None
    for token in re.findall(r"[\u4e00-\u9fff]{2,}", q):
        if token not in {"日历", "会议", "时间"}:
            kw = token
            break
    if kw:
        rows = conn.execute(
            """
            SELECT event_id, subject, start_time, end_time, organizer_id
            FROM calendar_event
            WHERE subject LIKE ?
            ORDER BY start_time DESC
            LIMIT 20
            """,
            (f"%{kw}%",),
        ).fetchall()
        evidence["items"].append(
            {
                "type": "calendar_search",
                "keyword": kw,
                "events": [
                    {
                        "event_id": r["event_id"],
                        "subject": r["subject"],
                        "start_time": r["start_time"],
                        "end_time": r["end_time"],
                        "organizer_id": r["organizer_id"],
                    }
                    for r in rows
                ],
            }
        )
        return evidence

    evidence["items"].append({"type": "calendar_fallback", "hint": "未匹配到可计算的日历问题模式"})
    return evidence


def enterprise_tool_schemas() -> list[dict[str, Any]]:
    def fn(name: str, description: str, parameters: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": parameters,
            },
        }

    positive_int = {"type": "integer", "minimum": 1}
    limit_param = {"type": "integer", "minimum": 1, "maximum": 200, "default": 20}

    return [
        fn(
            "org_get_self_profile",
            "Get current logged-in user's profile and departments.",
            {"type": "object", "properties": {}, "required": []},
        ),
        fn(
            "org_get_org_overview",
            "Get current org overview: org name, CEO, headcount, department count.",
            {"type": "object", "properties": {}, "required": []},
        ),
        fn(
            "org_list_departments",
            "List departments in current org.",
            {"type": "object", "properties": {"limit": limit_param}, "required": []},
        ),
        fn(
            "org_resolve_user",
            "Resolve a user within current org by user_id/name/email/mobile_suffix.",
            {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "object",
                        "properties": {
                            "user_id": {"type": "string"},
                            "name": {"type": "string"},
                            "email": {"type": "string"},
                            "mobile_suffix": {"type": "string"},
                        },
                    }
                },
                "required": ["query"],
            },
        ),
        fn(
            "org_get_user_profile",
            "Get a user's profile by user_id within current org.",
            {"type": "object", "properties": {"user_id": {"type": "string"}}, "required": ["user_id"]},
        ),
        fn(
            "org_get_user_manager",
            "Get a user's direct manager info within current org.",
            {"type": "object", "properties": {"user_id": {"type": "string"}}, "required": ["user_id"]},
        ),
        fn(
            "org_get_user_departments",
            "Get a user's departments within current org.",
            {"type": "object", "properties": {"user_id": {"type": "string"}}, "required": ["user_id"]},
        ),
        fn(
            "org_search_users",
            "Search users by keyword (name/email/mobile suffix) within current org.",
            {"type": "object", "properties": {"query": {"type": "string"}, "limit": limit_param}, "required": ["query"]},
        ),
        fn(
            "org_get_dept_detail",
            "Get department detail by dept_id within current org.",
            {"type": "object", "properties": {"dept_id": {"type": "string"}}, "required": ["dept_id"]},
        ),
        fn(
            "org_list_dept_users",
            "List users in a department by dept_id within current org.",
            {"type": "object", "properties": {"dept_id": {"type": "string"}, "limit": limit_param}, "required": ["dept_id"]},
        ),
        fn(
            "org_get_subordinates",
            "List direct subordinates of a manager_id within current org.",
            {"type": "object", "properties": {"manager_id": {"type": "string"}, "limit": limit_param}, "required": ["manager_id"]},
        ),
        fn(
            "org_get_dept_tree_path",
            "Get department tree path (root to current) by dept_id within current org.",
            {"type": "object", "properties": {"dept_id": {"type": "string"}}, "required": ["dept_id"]},
        ),
        fn(
            "im_list_my_sessions",
            "List sessions visible to current user.",
            {"type": "object", "properties": {"limit": limit_param}, "required": []},
        ),
        fn(
            "im_get_recent_contacts",
            "Get recent contacts for current user from private chats.",
            {"type": "object", "properties": {"limit": limit_param}, "required": []},
        ),
        fn(
            "im_get_chat_history",
            "Get chat history between current user and other_user_id (private chat).",
            {"type": "object", "properties": {"other_user_id": {"type": "string"}, "limit": limit_param}, "required": ["other_user_id"]},
        ),
        fn(
            "im_get_session_messages",
            "Get recent messages for a session_id visible to current user.",
            {"type": "object", "properties": {"session_id": {"type": "string"}, "limit": limit_param}, "required": ["session_id"]},
        ),
        fn(
            "im_search_my_messages",
            "Search messages by keyword within sessions visible to current user.",
            {"type": "object", "properties": {"keyword": {"type": "string"}, "limit": limit_param}, "required": ["keyword"]},
        ),
        fn(
            "im_get_message_stats",
            "Get message stats for current user in period today/week/month.",
            {
                "type": "object",
                "properties": {"period": {"type": "string", "enum": ["today", "week", "month"]}},
                "required": ["period"],
            },
        ),
        fn(
            "doc_list_accessible",
            "List documents accessible to current user.",
            {"type": "object", "properties": {"limit": limit_param}, "required": []},
        ),
        fn(
            "doc_search_accessible",
            "Search documents accessible to current user by keywords.",
            {"type": "object", "properties": {"keywords": {"type": "string"}, "limit": limit_param}, "required": ["keywords"]},
        ),
        fn(
            "doc_get_detail",
            "Get document detail by doc_id if current user has access.",
            {"type": "object", "properties": {"doc_id": {"type": "string"}}, "required": ["doc_id"]},
        ),
        fn(
            "doc_get_stats",
            "Get stats of accessible documents for current user grouped by ctype.",
            {"type": "object", "properties": {}, "required": []},
        ),
        fn(
            "doc_list_recently_updated",
            "List recently updated documents accessible to current user.",
            {"type": "object", "properties": {"limit": limit_param}, "required": []},
        ),
        fn(
            "doc_list_created_by_me",
            "List documents created by current user.",
            {"type": "object", "properties": {"limit": limit_param}, "required": []},
        ),
        fn(
            "cal_get_events_in_range",
            "Get calendar events for a user in [start_ms, end_ms) within current org.",
            {
                "type": "object",
                "properties": {
                    "start_ms": {"type": "integer"},
                    "end_ms": {"type": "integer"},
                    "user_id": {"type": "string"},
                    "limit": limit_param,
                },
                "required": ["start_ms", "end_ms"],
            },
        ),
        fn(
            "cal_get_events_on_date",
            "Get calendar events for a user on a date (YYYY-MM-DD) within current org.",
            {"type": "object", "properties": {"date": {"type": "string"}, "user_id": {"type": "string"}, "limit": limit_param}, "required": ["date"]},
        ),
        fn(
            "cal_search_events",
            "Search calendar events by keyword within current org.",
            {"type": "object", "properties": {"keyword": {"type": "string"}, "limit": limit_param}, "required": ["keyword"]},
        ),
        fn(
            "cal_check_freebusy",
            "Check if a user is busy in [start_ms, end_ms) within current org.",
            {
                "type": "object",
                "properties": {"start_ms": {"type": "integer"}, "end_ms": {"type": "integer"}, "user_id": {"type": "string"}},
                "required": ["start_ms", "end_ms", "user_id"],
            },
        ),
        fn(
            "cal_get_event_detail",
            "Get event detail by event_id within current org.",
            {"type": "object", "properties": {"event_id": {"type": "string"}}, "required": ["event_id"]},
        ),
        fn(
            "cal_get_event_stats",
            "Get calendar stats for current user in period today/week/month.",
            {"type": "object", "properties": {"period": {"type": "string", "enum": ["today", "week", "month"]}}, "required": ["period"]},
        ),
        fn(
            "cross_get_shared_docs",
            "Get docs accessible by both current user and other_user_id in current org.",
            {"type": "object", "properties": {"other_user_id": {"type": "string"}, "limit": limit_param}, "required": ["other_user_id"]},
        ),
        fn(
            "cross_get_common_meetings",
            "Get common meetings between current user and other_user_id in current org.",
            {
                "type": "object",
                "properties": {
                    "other_user_id": {"type": "string"},
                    "start_ms": {"type": "integer"},
                    "end_ms": {"type": "integer"},
                    "limit": limit_param,
                },
                "required": ["other_user_id"],
            },
        ),
        fn(
            "cross_get_user_card",
            "Get a combined user card for other_user_id: profile, departments, manager.",
            {"type": "object", "properties": {"other_user_id": {"type": "string"}}, "required": ["other_user_id"]},
        ),
        fn(
            "cross_search_user_messages_by_keyword",
            "Search current user's messages by keyword.",
            {"type": "object", "properties": {"keyword": {"type": "string"}, "limit": limit_param}, "required": ["keyword"]},
        ),
    ]


def execute_enterprise_tool(
    conn: sqlite3.Connection,
    org_id: str,
    viewer_user_id: str,
    tool_name: str,
    tool_args: dict[str, Any],
) -> dict[str, Any]:
    def clamp_limit(value: Any, default: int, maximum: int = 200) -> int:
        try:
            n = int(value)
        except Exception:
            n = default
        if n < 1:
            n = 1
        if n > maximum:
            n = maximum
        return n

    def ok(data: Any, summary: str, refs: dict[str, Any] | None = None, truncated: bool = False) -> dict[str, Any]:
        return {
            "ok": True,
            "tool": tool_name,
            "summary": summary,
            "evidence_refs": refs or {},
            "truncated": bool(truncated),
            "data": data,
        }

    def err(code: str, message: str) -> dict[str, Any]:
        return {
            "ok": False,
            "tool": tool_name,
            "error": {"code": code, "message": message},
            "evidence_refs": {},
            "truncated": False,
            "data": None,
            "summary": message,
        }

    org = conn.execute("SELECT * FROM org WHERE id=? LIMIT 1", (org_id,)).fetchone()
    if not org:
        return err("org_not_found", "org_not_found")

    def lookup_user(user_id: str) -> sqlite3.Row | None:
        return _lookup_user_by_id(conn, org_id, user_id)

    def ensure_user_in_org(user_id: str) -> sqlite3.Row | None:
        u = lookup_user(user_id)
        return u

    if tool_name == "org_get_self_profile":
        user = lookup_user(viewer_user_id)
        if not user:
            return err("user_not_found", "current_user_not_found")
        manager = lookup_user(user["manager_id"]) if user["manager_id"] else None
        depts = _query_user_departments(conn, org_id, viewer_user_id)
        payload = {
            "user_id": user["id"],
            "name": user["name"],
            "org_id": org_id,
            "org_name": org["name"],
            "departments": depts,
            "manager": {"user_id": manager["id"], "name": manager["name"]} if manager else None,
            "role": _role_title(user["role"]),
            "mobile": _mask_phone_cn(user["mobile"]),
            "email": user["email"],
            "join_date": _epoch_seconds_to_date_str(user["join_date"]),
            "gender": _gender_label(user["gender"]),
        }
        return ok(payload, "current user profile", refs={"user_ids": [viewer_user_id]})

    if tool_name == "org_get_org_overview":
        ceo = lookup_user(org["owner_user_id"])
        headcount = conn.execute("SELECT COUNT(*) AS c FROM user WHERE org_id=?", (org_id,)).fetchone()["c"]
        dept_count = conn.execute("SELECT COUNT(*) AS c FROM dept WHERE org_id=?", (org_id,)).fetchone()["c"]
        payload = {
            "org_id": org_id,
            "org_name": org["name"],
            "ceo": {"user_id": ceo["id"], "name": ceo["name"]} if ceo else None,
            "headcount": headcount,
            "dept_count": dept_count,
        }
        return ok(payload, "org overview", refs={"org_ids": [org_id]})

    if tool_name == "org_list_departments":
        limit = clamp_limit(tool_args.get("limit"), 50)
        rows = conn.execute(
            """
            SELECT d.id AS dept_id, d.name AS dept_name, d.parent_id AS parent_id, d.level AS level, d.leader_id AS leader_id,
                   u.name AS leader_name
            FROM dept d
            LEFT JOIN user u ON u.org_id=d.org_id AND u.id=d.leader_id
            WHERE d.org_id=?
            ORDER BY CAST(d.level AS INTEGER) ASC, d.name ASC
            LIMIT ?
            """,
            (org_id, limit),
        ).fetchall()
        depts = [
            {
                "dept_id": r["dept_id"],
                "name": r["dept_name"],
                "parent_id": r["parent_id"],
                "level": r["level"],
                "leader": {"user_id": r["leader_id"], "name": r["leader_name"]} if r["leader_id"] else None,
            }
            for r in rows
        ]
        return ok(depts, "departments list", refs={"dept_ids": [d["dept_id"] for d in depts]}, truncated=len(rows) >= limit)

    if tool_name == "org_resolve_user":
        q = tool_args.get("query") or {}
        if not isinstance(q, dict):
            return err("invalid_args", "query must be an object")
        user_id = str(q.get("user_id") or "").strip()
        name = str(q.get("name") or "").strip()
        email = str(q.get("email") or "").strip()
        mobile_suffix = str(q.get("mobile_suffix") or "").strip()
        if user_id:
            u = lookup_user(user_id)
            if not u:
                return ok([], "no user matched", refs={})
            return ok([{"user_id": u["id"], "name": u["name"]}], "resolved by user_id", refs={"user_ids": [u["id"]]})
        if email:
            u = conn.execute("SELECT * FROM user WHERE org_id=? AND email=? LIMIT 5", (org_id, email)).fetchall()
            out = [{"user_id": r["id"], "name": r["name"]} for r in u]
            return ok(out, "resolved by email", refs={"user_ids": [r["user_id"] for r in out]})
        if mobile_suffix:
            u = conn.execute(
                "SELECT * FROM user WHERE org_id=? AND mobile LIKE ? LIMIT 5",
                (org_id, f"%{re.sub(r'\\D+', '', mobile_suffix)}"),
            ).fetchall()
            out = [{"user_id": r["id"], "name": r["name"]} for r in u]
            return ok(out, "resolved by mobile suffix", refs={"user_ids": [r["user_id"] for r in out]})
        if name:
            u = conn.execute("SELECT * FROM user WHERE org_id=? AND name=? LIMIT 5", (org_id, name)).fetchall()
            out = [{"user_id": r["id"], "name": r["name"]} for r in u]
            return ok(out, "resolved by name", refs={"user_ids": [r["user_id"] for r in out]})
        return err("invalid_args", "at least one of user_id/name/email/mobile_suffix is required")

    if tool_name == "org_get_user_profile":
        user_id = str(tool_args.get("user_id") or "").strip()
        u = ensure_user_in_org(user_id)
        if not u:
            return err("user_not_found", "user_not_found_in_org")
        payload = {
            "user_id": u["id"],
            "name": u["name"],
            "org_id": org_id,
            "role": _role_title(u["role"]),
            "mobile": _mask_phone_cn(u["mobile"]),
            "email": u["email"],
            "join_date": _epoch_seconds_to_date_str(u["join_date"]),
            "gender": _gender_label(u["gender"]),
            "manager_id": u["manager_id"],
        }
        return ok(payload, "user profile", refs={"user_ids": [u["id"]]})

    if tool_name == "org_get_user_manager":
        user_id = str(tool_args.get("user_id") or "").strip()
        u = ensure_user_in_org(user_id)
        if not u:
            return err("user_not_found", "user_not_found_in_org")
        manager = lookup_user(u["manager_id"]) if u["manager_id"] else None
        payload = {"user_id": u["id"], "name": u["name"], "manager": {"user_id": manager["id"], "name": manager["name"]} if manager else None}
        return ok(payload, "user manager", refs={"user_ids": [u["id"], manager["id"]] if manager else [u["id"]]})

    if tool_name == "org_get_user_departments":
        user_id = str(tool_args.get("user_id") or "").strip()
        u = ensure_user_in_org(user_id)
        if not u:
            return err("user_not_found", "user_not_found_in_org")
        depts = _query_user_departments(conn, org_id, u["id"])
        return ok({"user_id": u["id"], "name": u["name"], "departments": depts}, "user departments", refs={"user_ids": [u["id"]], "dept_ids": [d["dept_id"] for d in depts]})

    if tool_name == "org_search_users":
        query = str(tool_args.get("query") or "").strip()
        if not query:
            return err("invalid_args", "query is required")
        limit = clamp_limit(tool_args.get("limit"), 20)
        qn = re.sub(r"\s+", "", query)
        rows = conn.execute(
            """
            SELECT id, name, email, mobile, role
            FROM user
            WHERE org_id=?
              AND (name LIKE ? OR email LIKE ? OR mobile LIKE ? OR id = ?)
            ORDER BY name ASC
            LIMIT ?
            """,
            (org_id, f"%{qn}%", f"%{qn}%", f"%{qn}%", qn, limit),
        ).fetchall()
        users = [{"user_id": r["id"], "name": r["name"], "email": r["email"], "mobile": _mask_phone_cn(r["mobile"]), "role": _role_title(r["role"])} for r in rows]
        return ok(users, "user search results", refs={"user_ids": [u["user_id"] for u in users]}, truncated=len(rows) >= limit)

    if tool_name == "org_get_dept_detail":
        dept_id = str(tool_args.get("dept_id") or "").strip()
        d = conn.execute("SELECT * FROM dept WHERE org_id=? AND id=? LIMIT 1", (org_id, dept_id)).fetchone()
        if not d:
            return err("dept_not_found", "dept_not_found_in_org")
        leader = lookup_user(d["leader_id"]) if d["leader_id"] else None
        payload = {
            "dept_id": d["id"],
            "name": d["name"],
            "parent_id": d["parent_id"],
            "level": d["level"],
            "leader": {"user_id": leader["id"], "name": leader["name"]} if leader else None,
        }
        return ok(payload, "department detail", refs={"dept_ids": [d["id"]], "user_ids": [leader["id"]] if leader else []})

    if tool_name == "org_list_dept_users":
        dept_id = str(tool_args.get("dept_id") or "").strip()
        limit = clamp_limit(tool_args.get("limit"), 50)
        d = conn.execute("SELECT * FROM dept WHERE org_id=? AND id=? LIMIT 1", (org_id, dept_id)).fetchone()
        if not d:
            return err("dept_not_found", "dept_not_found_in_org")
        rows = conn.execute(
            """
            SELECT u.id AS user_id, u.name AS name, u.email AS email, u.mobile AS mobile, u.role AS role
            FROM dept_user du
            JOIN user u ON u.org_id=du.org_id AND u.id=du.user_id
            WHERE du.org_id=? AND du.dept_id=?
            ORDER BY u.name ASC
            LIMIT ?
            """,
            (org_id, dept_id, limit),
        ).fetchall()
        users = [{"user_id": r["user_id"], "name": r["name"], "email": r["email"], "mobile": _mask_phone_cn(r["mobile"]), "role": _role_title(r["role"])} for r in rows]
        return ok({"dept_id": dept_id, "dept_name": d["name"], "users": users}, "department users", refs={"dept_ids": [dept_id], "user_ids": [u["user_id"] for u in users]}, truncated=len(rows) >= limit)

    if tool_name == "org_get_subordinates":
        manager_id = str(tool_args.get("manager_id") or "").strip()
        limit = clamp_limit(tool_args.get("limit"), 50)
        m = ensure_user_in_org(manager_id)
        if not m:
            return err("user_not_found", "manager_not_found_in_org")
        rows = conn.execute(
            """
            SELECT id, name, email, mobile, role
            FROM user
            WHERE org_id=? AND manager_id=?
            ORDER BY name ASC
            LIMIT ?
            """,
            (org_id, manager_id, limit),
        ).fetchall()
        users = [{"user_id": r["id"], "name": r["name"], "email": r["email"], "mobile": _mask_phone_cn(r["mobile"]), "role": _role_title(r["role"])} for r in rows]
        return ok({"manager_id": manager_id, "manager_name": m["name"], "subordinates": users}, "subordinates list", refs={"user_ids": [manager_id] + [u["user_id"] for u in users]}, truncated=len(rows) >= limit)

    if tool_name == "org_get_dept_tree_path":
        dept_id = str(tool_args.get("dept_id") or "").strip()
        max_hops = 20
        path_names: list[str] = []
        seen: set[str] = set()
        cur = dept_id
        while cur and cur not in seen and len(path_names) < max_hops:
            seen.add(cur)
            d = conn.execute("SELECT id, name, parent_id FROM dept WHERE org_id=? AND id=? LIMIT 1", (org_id, cur)).fetchone()
            if not d:
                break
            path_names.append(d["name"])
            cur = d["parent_id"]
        if not path_names:
            return err("dept_not_found", "dept_not_found_in_org")
        full = "/".join(reversed(path_names))
        return ok({"dept_id": dept_id, "path": full}, "department tree path", refs={"dept_ids": [dept_id]})

    if tool_name == "im_list_my_sessions":
        limit = clamp_limit(tool_args.get("limit"), 200)
        rows = conn.execute(
            """
            SELECT session_id, conversation_type
            FROM im_user_session
            WHERE org_id=? AND user_id=?
            ORDER BY session_id ASC
            LIMIT ?
            """,
            (org_id, viewer_user_id, limit),
        ).fetchall()
        sessions = [{"session_id": r["session_id"], "conversation_type": r["conversation_type"]} for r in rows]
        return ok(sessions, "visible sessions", refs={"session_ids": [s["session_id"] for s in sessions]}, truncated=len(rows) >= limit)

    if tool_name == "im_get_recent_contacts":
        limit = clamp_limit(tool_args.get("limit"), 10)
        rows = conn.execute(
            """
            SELECT m.send_time_ms, m.from_user_id, m.target_id, m.session_id, m.content
            FROM im_message m
            JOIN im_user_session s ON s.org_id=m.org_id AND s.session_id=m.session_id AND s.user_id=?
            WHERE m.org_id=?
              AND m.conversation_type='1'
              AND (m.from_user_id=? OR m.target_id=?)
            ORDER BY m.send_time_ms DESC
            LIMIT 500
            """,
            (viewer_user_id, org_id, viewer_user_id, viewer_user_id),
        ).fetchall()
        latest: dict[str, dict[str, Any]] = {}
        for r in rows:
            other = r["target_id"] if r["from_user_id"] == viewer_user_id else r["from_user_id"]
            if not other:
                continue
            if other not in latest:
                other_u = lookup_user(other)
                latest[other] = {
                    "other_user_id": other,
                    "other_user_name": other_u["name"] if other_u else None,
                    "last_time_ms": r["send_time_ms"],
                    "last_message_preview": (r["content"] or "")[:120],
                    "session_id": r["session_id"],
                }
        contacts = sorted(latest.values(), key=lambda x: int(x.get("last_time_ms") or 0), reverse=True)[:limit]
        return ok(contacts, "recent contacts", refs={"user_ids": [c["other_user_id"] for c in contacts], "session_ids": [c["session_id"] for c in contacts]})

    if tool_name == "im_get_chat_history":
        other_user_id = str(tool_args.get("other_user_id") or "").strip()
        if not other_user_id:
            return err("invalid_args", "other_user_id is required")
        if not ensure_user_in_org(other_user_id):
            return err("user_not_found", "other_user_not_found_in_org")
        limit = clamp_limit(tool_args.get("limit"), 20)
        a, b = sorted([viewer_user_id, other_user_id])
        session_id = f"{a}_{b}"
        allowed = conn.execute(
            "SELECT 1 FROM im_user_session WHERE org_id=? AND user_id=? AND session_id=? LIMIT 1",
            (org_id, viewer_user_id, session_id),
        ).fetchone()
        if not allowed:
            return err("permission_denied", "session_not_visible_to_current_user")
        msgs = conn.execute(
            """
            SELECT message_id, send_time_ms, from_user_id, content
            FROM im_message
            WHERE org_id=? AND session_id=?
            ORDER BY send_time_ms DESC
            LIMIT ?
            """,
            (org_id, session_id, limit),
        ).fetchall()
        messages = [
            {"message_id": r["message_id"], "send_time_ms": r["send_time_ms"], "from_user_id": r["from_user_id"], "content": (r["content"] or "")[:300]}
            for r in reversed(msgs)
        ]
        return ok({"session_id": session_id, "other_user_id": other_user_id, "messages": messages}, "chat history", refs={"session_ids": [session_id], "message_ids": [m["message_id"] for m in messages]}, truncated=len(msgs) >= limit)

    if tool_name == "im_get_session_messages":
        session_id = str(tool_args.get("session_id") or "").strip()
        if not session_id:
            return err("invalid_args", "session_id is required")
        limit = clamp_limit(tool_args.get("limit"), 20)
        allowed = conn.execute(
            "SELECT 1 FROM im_user_session WHERE org_id=? AND user_id=? AND session_id=? LIMIT 1",
            (org_id, viewer_user_id, session_id),
        ).fetchone()
        if not allowed:
            return err("permission_denied", "session_not_visible_to_current_user")
        msgs = conn.execute(
            """
            SELECT message_id, send_time_ms, from_user_id, target_id, content
            FROM im_message
            WHERE org_id=? AND session_id=?
            ORDER BY send_time_ms DESC
            LIMIT ?
            """,
            (org_id, session_id, limit),
        ).fetchall()
        messages = [
            {"message_id": r["message_id"], "send_time_ms": r["send_time_ms"], "from_user_id": r["from_user_id"], "target_id": r["target_id"], "content": (r["content"] or "")[:300]}
            for r in reversed(msgs)
        ]
        return ok({"session_id": session_id, "messages": messages}, "session messages", refs={"session_ids": [session_id], "message_ids": [m["message_id"] for m in messages]}, truncated=len(msgs) >= limit)

    if tool_name == "im_search_my_messages" or tool_name == "cross_search_user_messages_by_keyword":
        keyword = str(tool_args.get("keyword") or "").strip()
        if not keyword:
            return err("invalid_args", "keyword is required")
        limit = clamp_limit(tool_args.get("limit"), 20)
        rows = conn.execute(
            """
            SELECT m.message_id, m.send_time_ms, m.from_user_id, m.session_id, m.content
            FROM im_message m
            JOIN im_user_session s ON s.org_id=m.org_id AND s.session_id=m.session_id AND s.user_id=?
            WHERE m.org_id=? AND m.content LIKE ?
            ORDER BY m.send_time_ms DESC
            LIMIT ?
            """,
            (viewer_user_id, org_id, f"%{keyword}%", limit),
        ).fetchall()
        matches = [
            {"message_id": r["message_id"], "send_time_ms": r["send_time_ms"], "from_user_id": r["from_user_id"], "session_id": r["session_id"], "content": (r["content"] or "")[:200]}
            for r in rows
        ]
        return ok({"keyword": keyword, "matches": matches}, "message search", refs={"message_ids": [m["message_id"] for m in matches], "session_ids": list({m["session_id"] for m in matches})}, truncated=len(rows) >= limit)

    if tool_name == "im_get_message_stats":
        period = str(tool_args.get("period") or "").strip()
        if period not in {"today", "week", "month"}:
            return err("invalid_args", "period must be today/week/month")
        now = int(time.time())
        local = time.localtime(now)
        day_start = int(time.mktime((local.tm_year, local.tm_mon, local.tm_mday, 0, 0, 0, 0, 0, -1))) * 1000
        if period == "today":
            start_ms = day_start
        elif period == "week":
            weekday = local.tm_wday
            start_ms = day_start - weekday * 86400000
        else:
            month_start = int(time.mktime((local.tm_year, local.tm_mon, 1, 0, 0, 0, 0, 0, -1))) * 1000
            start_ms = month_start
        total_sent = conn.execute(
            """
            SELECT COUNT(*) AS c
            FROM im_message m
            JOIN im_user_session s ON s.org_id=m.org_id AND s.session_id=m.session_id AND s.user_id=?
            WHERE m.org_id=? AND m.send_time_ms >= ? AND m.from_user_id=?
            """,
            (viewer_user_id, org_id, start_ms, viewer_user_id),
        ).fetchone()["c"]
        total_visible = conn.execute(
            """
            SELECT COUNT(*) AS c
            FROM im_message m
            JOIN im_user_session s ON s.org_id=m.org_id AND s.session_id=m.session_id AND s.user_id=?
            WHERE m.org_id=? AND m.send_time_ms >= ?
            """,
            (viewer_user_id, org_id, start_ms),
        ).fetchone()["c"]
        return ok({"period": period, "since_ms": start_ms, "sent_count": total_sent, "visible_message_count": total_visible}, "message stats", refs={})

    if tool_name == "doc_list_accessible":
        limit = clamp_limit(tool_args.get("limit"), 50)
        rows = conn.execute(
            """
            SELECT d.doc_id, d.title, d.ctype, d.owner, d.create_time, d.update_time, d.note
            FROM doc_user_access a
            JOIN doc d ON d.org_id=a.org_id AND d.doc_id=a.doc_id
            WHERE a.org_id=? AND a.user_id=?
            ORDER BY CAST(d.update_time AS INTEGER) DESC
            LIMIT ?
            """,
            (org_id, viewer_user_id, limit),
        ).fetchall()
        docs = [
            {
                "doc_id": r["doc_id"],
                "title": r["title"],
                "ctype": r["ctype"],
                "owner": r["owner"],
                "create_time": r["create_time"],
                "update_time": r["update_time"],
                "note_preview": (r["note"] or "")[:160],
            }
            for r in rows
        ]
        return ok(docs, "accessible docs", refs={"doc_ids": [d["doc_id"] for d in docs]}, truncated=len(rows) >= limit)

    if tool_name == "doc_search_accessible":
        keywords = str(tool_args.get("keywords") or "").strip()
        if not keywords:
            return err("invalid_args", "keywords is required")
        limit = clamp_limit(tool_args.get("limit"), 10)
        tokens = [t for t in re.split(r"\s+", keywords) if t]
        tokens = tokens[:6]
        query = " AND ".join(tokens)
        rows = conn.execute(
            """
            SELECT d.doc_id, d.title, d.ctype, d.owner, d.create_time, d.update_time, d.note
            FROM doc_fts
            JOIN doc d ON d.org_id = doc_fts.org_id AND d.doc_id = doc_fts.doc_id
            JOIN doc_user_access a ON a.org_id=d.org_id AND a.doc_id=d.doc_id AND a.user_id=?
            WHERE doc_fts MATCH ? AND doc_fts.org_id = ?
            LIMIT ?
            """,
            (viewer_user_id, query, org_id, limit),
        ).fetchall()
        docs = [
            {
                "doc_id": r["doc_id"],
                "title": r["title"],
                "ctype": r["ctype"],
                "owner": r["owner"],
                "create_time": r["create_time"],
                "update_time": r["update_time"],
                "note_preview": (r["note"] or "")[:160],
            }
            for r in rows
        ]
        return ok({"keywords": tokens, "results": docs}, "doc search", refs={"doc_ids": [d["doc_id"] for d in docs]}, truncated=len(rows) >= limit)

    if tool_name == "doc_get_detail":
        doc_id = str(tool_args.get("doc_id") or "").strip()
        if not doc_id:
            return err("invalid_args", "doc_id is required")
        allowed = conn.execute(
            "SELECT 1 FROM doc_user_access WHERE org_id=? AND user_id=? AND doc_id=? LIMIT 1",
            (org_id, viewer_user_id, doc_id),
        ).fetchone()
        if not allowed:
            return err("permission_denied", "doc_not_accessible_to_current_user")
        d = conn.execute("SELECT * FROM doc WHERE org_id=? AND doc_id=? LIMIT 1", (org_id, doc_id)).fetchone()
        if not d:
            return err("doc_not_found", "doc_not_found")
        payload = {
            "doc_id": d["doc_id"],
            "title": d["title"],
            "ctype": d["ctype"],
            "owner": d["owner"],
            "create_time": d["create_time"],
            "update_time": d["update_time"],
            "content_length": d["content_length"],
            "note": (d["note"] or "")[:2000],
        }
        return ok(payload, "doc detail", refs={"doc_ids": [doc_id], "user_ids": [d["owner"]] if d["owner"] else []})

    if tool_name == "doc_get_stats":
        rows = conn.execute(
            """
            SELECT d.ctype AS ctype, COUNT(*) AS c
            FROM doc_user_access a
            JOIN doc d ON d.org_id=a.org_id AND d.doc_id=a.doc_id
            WHERE a.org_id=? AND a.user_id=?
            GROUP BY d.ctype
            ORDER BY c DESC
            """,
            (org_id, viewer_user_id),
        ).fetchall()
        stats = [{"ctype": r["ctype"], "count": r["c"]} for r in rows]
        total = sum(int(r["count"]) for r in stats)
        return ok({"total": total, "by_ctype": stats}, "doc stats", refs={})

    if tool_name == "doc_list_recently_updated":
        limit = clamp_limit(tool_args.get("limit"), 20)
        rows = conn.execute(
            """
            SELECT d.doc_id, d.title, d.ctype, d.owner, d.create_time, d.update_time
            FROM doc_user_access a
            JOIN doc d ON d.org_id=a.org_id AND d.doc_id=a.doc_id
            WHERE a.org_id=? AND a.user_id=?
            ORDER BY CAST(d.update_time AS INTEGER) DESC
            LIMIT ?
            """,
            (org_id, viewer_user_id, limit),
        ).fetchall()
        docs = [{"doc_id": r["doc_id"], "title": r["title"], "ctype": r["ctype"], "owner": r["owner"], "create_time": r["create_time"], "update_time": r["update_time"]} for r in rows]
        return ok(docs, "recent docs (ordered by update_time)", refs={"doc_ids": [d["doc_id"] for d in docs]}, truncated=len(rows) >= limit)

    if tool_name == "doc_list_created_by_me":
        limit = clamp_limit(tool_args.get("limit"), 20)
        rows = conn.execute(
            """
            SELECT doc_id, title, ctype, owner, create_time
            FROM doc
            WHERE org_id=? AND owner=?
            ORDER BY CAST(create_time AS INTEGER) DESC
            LIMIT ?
            """,
            (org_id, viewer_user_id, limit),
        ).fetchall()
        docs = [{"doc_id": r["doc_id"], "title": r["title"], "ctype": r["ctype"], "owner": r["owner"], "create_time": r["create_time"]} for r in rows]
        return ok(docs, "docs created by current user", refs={"doc_ids": [d["doc_id"] for d in docs]})

    if tool_name == "cal_get_events_in_range":
        start_ms = tool_args.get("start_ms")
        end_ms = tool_args.get("end_ms")
        try:
            start_ms_i = int(start_ms)
            end_ms_i = int(end_ms)
        except Exception:
            return err("invalid_args", "start_ms/end_ms must be integers")
        user_id = str(tool_args.get("user_id") or viewer_user_id).strip()
        if not ensure_user_in_org(user_id):
            return err("permission_denied", "target_user_not_in_current_org")
        limit = clamp_limit(tool_args.get("limit"), 50)
        rows = conn.execute(
            """
            SELECT e.event_id, e.subject, e.start_time, e.end_time, e.organizer_id
            FROM calendar_event e
            LEFT JOIN calendar_event_participant p ON p.event_id = e.event_id AND p.user_id = ?
            WHERE (p.user_id IS NOT NULL OR e.organizer_id = ?)
              AND NOT (e.end_time <= ? OR e.start_time >= ?)
            ORDER BY e.start_time ASC
            LIMIT ?
            """,
            (user_id, user_id, start_ms_i, end_ms_i, limit),
        ).fetchall()
        events = [{"event_id": r["event_id"], "subject": r["subject"], "start_time": r["start_time"], "end_time": r["end_time"], "organizer_id": r["organizer_id"]} for r in rows]
        return ok({"user_id": user_id, "time_range_ms": [start_ms_i, end_ms_i], "events": events}, "events in range", refs={"event_ids": [e["event_id"] for e in events], "user_ids": [user_id]}, truncated=len(rows) >= limit)

    if tool_name == "cal_get_events_on_date":
        date_str = str(tool_args.get("date") or "").strip()
        user_id = str(tool_args.get("user_id") or viewer_user_id).strip()
        if not ensure_user_in_org(user_id):
            return err("permission_denied", "target_user_not_in_current_org")
        limit = clamp_limit(tool_args.get("limit"), 50)
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception:
            return err("invalid_args", "date must be YYYY-MM-DD")
        start_ms_i = int(datetime(d.year, d.month, d.day).timestamp() * 1000)
        end_ms_i = int((datetime(d.year, d.month, d.day) + timedelta(days=1)).timestamp() * 1000)
        return execute_enterprise_tool(conn, org_id, viewer_user_id, "cal_get_events_in_range", {"start_ms": start_ms_i, "end_ms": end_ms_i, "user_id": user_id, "limit": limit})

    if tool_name == "cal_search_events":
        keyword = str(tool_args.get("keyword") or "").strip()
        if not keyword:
            return err("invalid_args", "keyword is required")
        limit = clamp_limit(tool_args.get("limit"), 20)
        rows = conn.execute(
            """
            SELECT DISTINCT e.event_id, e.subject, e.start_time, e.end_time, e.organizer_id
            FROM calendar_event e
            WHERE e.subject LIKE ?
              AND (
                EXISTS (
                  SELECT 1
                  FROM calendar_event_participant p
                  JOIN user u ON u.id=p.user_id AND u.org_id=?
                  WHERE p.event_id=e.event_id
                )
                OR EXISTS (
                  SELECT 1
                  FROM user u2
                  WHERE u2.org_id=? AND u2.id=e.organizer_id
                )
              )
            ORDER BY e.start_time DESC
            LIMIT ?
            """,
            (f"%{keyword}%", org_id, org_id, limit),
        ).fetchall()
        events = [{"event_id": r["event_id"], "subject": r["subject"], "start_time": r["start_time"], "end_time": r["end_time"], "organizer_id": r["organizer_id"]} for r in rows]
        return ok({"keyword": keyword, "events": events}, "calendar search", refs={"event_ids": [e["event_id"] for e in events]}, truncated=len(rows) >= limit)

    if tool_name == "cal_check_freebusy":
        try:
            start_ms_i = int(tool_args.get("start_ms"))
            end_ms_i = int(tool_args.get("end_ms"))
        except Exception:
            return err("invalid_args", "start_ms/end_ms must be integers")
        user_id = str(tool_args.get("user_id") or "").strip()
        if not ensure_user_in_org(user_id):
            return err("permission_denied", "target_user_not_in_current_org")
        res = execute_enterprise_tool(conn, org_id, viewer_user_id, "cal_get_events_in_range", {"start_ms": start_ms_i, "end_ms": end_ms_i, "user_id": user_id, "limit": 50})
        if not res.get("ok"):
            return res
        events = (res.get("data") or {}).get("events") or []
        busy = len(events) > 0
        return ok({"user_id": user_id, "time_range_ms": [start_ms_i, end_ms_i], "busy": busy, "conflicts": events}, "freebusy", refs={"event_ids": [e.get("event_id") for e in events if isinstance(e, dict) and e.get("event_id")]})

    if tool_name == "cal_get_event_detail":
        event_id = str(tool_args.get("event_id") or "").strip()
        if not event_id:
            return err("invalid_args", "event_id is required")
        e = conn.execute("SELECT * FROM calendar_event WHERE event_id=? LIMIT 1", (event_id,)).fetchone()
        if not e:
            return err("event_not_found", "event_not_found")
        participant_rows = conn.execute("SELECT user_id FROM calendar_event_participant WHERE event_id=?", (event_id,)).fetchall()
        participant_ids = [r["user_id"] for r in participant_rows]
        in_org = []
        for pid in participant_ids:
            if lookup_user(pid):
                in_org.append(pid)
        if not in_org:
            return err("permission_denied", "event_not_in_current_org")
        payload = {
            "event_id": e["event_id"],
            "subject": e["subject"],
            "start_time": e["start_time"],
            "end_time": e["end_time"],
            "organizer_id": e["organizer_id"],
            "participants_user_ids": in_org,
        }
        return ok(payload, "event detail", refs={"event_ids": [event_id], "user_ids": in_org})

    if tool_name == "cal_get_event_stats":
        period = str(tool_args.get("period") or "").strip()
        if period not in {"today", "week", "month"}:
            return err("invalid_args", "period must be today/week/month")
        now_dt = datetime.now()
        if period == "today":
            start = datetime(now_dt.year, now_dt.month, now_dt.day)
            end = start + timedelta(days=1)
        elif period == "week":
            start = datetime(now_dt.year, now_dt.month, now_dt.day) - timedelta(days=now_dt.weekday())
            end = start + timedelta(days=7)
        else:
            start = datetime(now_dt.year, now_dt.month, 1)
            if now_dt.month == 12:
                end = datetime(now_dt.year + 1, 1, 1)
            else:
                end = datetime(now_dt.year, now_dt.month + 1, 1)
        res = execute_enterprise_tool(conn, org_id, viewer_user_id, "cal_get_events_in_range", {"start_ms": int(start.timestamp() * 1000), "end_ms": int(end.timestamp() * 1000), "user_id": viewer_user_id, "limit": 200})
        if not res.get("ok"):
            return res
        events = (res.get("data") or {}).get("events") or []
        return ok({"period": period, "event_count": len(events)}, "calendar stats", refs={})

    if tool_name == "cross_get_shared_docs":
        other_user_id = str(tool_args.get("other_user_id") or "").strip()
        if not other_user_id:
            return err("invalid_args", "other_user_id is required")
        if not ensure_user_in_org(other_user_id):
            return err("user_not_found", "other_user_not_found_in_org")
        limit = clamp_limit(tool_args.get("limit"), 20)
        rows = conn.execute(
            """
            SELECT d.doc_id, d.title, d.ctype, d.owner, d.create_time
            FROM doc_user_access a1
            JOIN doc_user_access a2 ON a2.org_id=a1.org_id AND a2.doc_id=a1.doc_id
            JOIN doc d ON d.org_id=a1.org_id AND d.doc_id=a1.doc_id
            WHERE a1.org_id=? AND a1.user_id=? AND a2.user_id=?
            ORDER BY CAST(d.create_time AS INTEGER) DESC
            LIMIT ?
            """,
            (org_id, viewer_user_id, other_user_id, limit),
        ).fetchall()
        docs = [{"doc_id": r["doc_id"], "title": r["title"], "ctype": r["ctype"], "owner": r["owner"], "create_time": r["create_time"]} for r in rows]
        return ok({"other_user_id": other_user_id, "shared_docs": docs}, "shared docs", refs={"doc_ids": [d["doc_id"] for d in docs], "user_ids": [other_user_id]}, truncated=len(rows) >= limit)

    if tool_name == "cross_get_common_meetings":
        other_user_id = str(tool_args.get("other_user_id") or "").strip()
        if not other_user_id:
            return err("invalid_args", "other_user_id is required")
        if not ensure_user_in_org(other_user_id):
            return err("user_not_found", "other_user_not_found_in_org")
        start_ms = tool_args.get("start_ms")
        end_ms = tool_args.get("end_ms")
        limit = clamp_limit(tool_args.get("limit"), 20)
        where = ""
        params: list[Any] = [viewer_user_id, other_user_id]
        if start_ms is not None and end_ms is not None:
            try:
                s = int(start_ms)
                e = int(end_ms)
                where = " AND NOT (ce.end_time <= ? OR ce.start_time >= ?) "
                params.extend([s, e])
            except Exception:
                return err("invalid_args", "start_ms/end_ms must be integers")
        params.append(limit)
        rows = conn.execute(
            f"""
            SELECT ce.event_id, ce.subject, ce.start_time, ce.end_time, ce.organizer_id
            FROM calendar_event ce
            JOIN calendar_event_participant p1 ON p1.event_id=ce.event_id AND p1.user_id=?
            JOIN calendar_event_participant p2 ON p2.event_id=ce.event_id AND p2.user_id=?
            WHERE 1=1 {where}
            ORDER BY ce.start_time DESC
            LIMIT ?
            """,
            tuple(params),
        ).fetchall()
        events = [{"event_id": r["event_id"], "subject": r["subject"], "start_time": r["start_time"], "end_time": r["end_time"], "organizer_id": r["organizer_id"]} for r in rows]
        return ok({"other_user_id": other_user_id, "events": events}, "common meetings", refs={"event_ids": [e["event_id"] for e in events], "user_ids": [other_user_id]}, truncated=len(rows) >= limit)

    if tool_name == "cross_get_user_card":
        other_user_id = str(tool_args.get("other_user_id") or "").strip()
        if not other_user_id:
            return err("invalid_args", "other_user_id is required")
        u = ensure_user_in_org(other_user_id)
        if not u:
            return err("user_not_found", "other_user_not_found_in_org")
        manager = lookup_user(u["manager_id"]) if u["manager_id"] else None
        depts = _query_user_departments(conn, org_id, other_user_id)
        card = {
            "user_id": u["id"],
            "name": u["name"],
            "email": u["email"],
            "mobile": _mask_phone_cn(u["mobile"]),
            "role": _role_title(u["role"]),
            "departments": depts,
            "manager": {"user_id": manager["id"], "name": manager["name"]} if manager else None,
        }
        return ok(card, "user card", refs={"user_ids": [other_user_id]})

    return err("unknown_tool", f"unknown_tool: {tool_name}")
