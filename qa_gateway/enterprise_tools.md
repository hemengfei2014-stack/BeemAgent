# Enterprise Tools（从 enterprise.py 抽取）

来源代码：[enterprise.py:L608-L1612](qa_gateway/enterprise.py#L608-L1612)

本文件把 `enterprise_tool_schemas()` 中声明的 tool（定义）以及 `execute_enterprise_tool()` 中对应的分支实现（实现）抽取出来，并为每个 tool 给出解释（入参、权限/可见性、数据来源、返回结构与典型错误）。

## 通用约定

### Tool Schema（定义）

所有 tool 以 OpenAI function tool schema 的形式声明：

- `type: "function"`
- `function.name`: tool 名称（下面每节的标题）
- `function.description`: 供模型选择 tool 时阅读的描述
- `function.parameters`: JSON Schema 形式的入参定义

`enterprise_tool_schemas()` 定义了两个常用参数 schema（其中当前仅 `limit_param` 被实际使用）：

```python
positive_int = {"type": "integer", "minimum": 1}
limit_param = {"type": "integer", "minimum": 1, "maximum": 200, "default": 20}
```

其中 `limit_param` 只做 schema 级别的约束；在实现中仍会通过 `clamp_limit()` 做兜底和最大值限制。

### 统一返回结构（实现）

`execute_enterprise_tool()` 对所有 tool 统一返回以下形状：

- 成功：`{"ok": True, "tool": tool_name, "summary": str, "evidence_refs": dict, "truncated": bool, "data": Any}`
- 失败：`{"ok": False, "tool": tool_name, "error": {"code": str, "message": str}, "evidence_refs": {}, "truncated": False, "data": None, "summary": message}`

相关辅助函数（实现中实际使用）：

```python
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
```

`truncated` 通常在“结果条数达到 limit”时置为 True（注意实现里用的是 `len(rows) >= limit`，并不严格判断是否“多于 limit”，但足以提示上层“可能未返回全量”）。

辅助函数含义与使用方式：

- `clamp_limit(value, default, maximum=200)`：把外部传入的 `limit` 参数安全地转换为整数并限制范围。
  - 如果 `value` 不能转成 int（例如 None、空字符串、非数字），回退为 `default`。
  - 然后把值夹在 `[1, maximum]` 之间，防止 0/负数导致空结果或异常，也防止过大 limit 带来响应过大/查询过慢。
  - 这是实现层面的兜底，与 schema 中的 `limit_param` 约束互补。
- `ok(data, summary, refs=None, truncated=False)`：构造统一的成功返回包裹。
  - `tool` 固定写入当前执行的 `tool_name`，便于上层日志/调试。
  - `summary` 是一句话摘要，便于 UI 或日志快速显示。
  - `evidence_refs` 用于承载“证据引用”的 id 列表（例如 `user_ids/doc_ids/event_ids/session_ids/message_ids/dept_ids`），方便答案侧做可追溯引用；传入 `None` 时会变成空字典。
  - `truncated` 标记结果是否可能因为 limit 截断，便于调用方在需要时继续分页/放大 limit 再查。
- `err(code, message)`：构造统一的失败返回包裹。
  - `error.code` 用于程序化处理（例如区分 `permission_denied` 与 `not_found`）。
  - `error.message` 与 `summary` 同步为对人可读的错误描述（当前实现里通常直接用固定字符串）。
  - 失败时强制 `evidence_refs={}`、`truncated=False`、`data=None`，避免上层误用残留数据。

### 权限/可见性原则（实现）

`execute_enterprise_tool(conn, org_id, viewer_user_id, ...)` 的权限控制主要靠以下点：

- 组织边界：所有查询都带 `org_id=?` 或通过 `_lookup_user_by_id(conn, org_id, user_id)` 限定在当前 org。
- 会话可见性：IM 消息相关会 join `im_user_session`，确保 viewer 只看到自己可见 session 的消息。
- 文档可见性：doc 相关会检查 `doc_user_access`。
- 日程可见性：日程查询以“组织内用户 + 是组织者或参与者”为准。

---

## org_get_self_profile

### 定义（Schema）

```python
fn(
    "org_get_self_profile",
    "Get current logged-in user's profile and departments.",
    {"type": "object", "properties": {}, "required": []},
)
```

### 实现（Implementation）

```python
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
```

### 解释

- 作用：返回“当前登录用户（viewer_user_id）”的基础资料、所属部门列表、直属上级（如果有），并带上 org 名称。
- 入参：无（完全由 `viewer_user_id` 决定）。
- 权限：只能拿到当前 org 内、当前用户自己的资料。
- 数据来源：`user`、`org`、以及 `_query_user_departments()`（通常关联 `dept_user` / `dept`）。
- 输出要点：
  - `mobile` 会通过 `_mask_phone_cn()` 做脱敏。
  - `join_date` 由 epoch seconds 转成日期字符串。
  - `evidence_refs.user_ids` 仅包含当前用户 id。
- 典型错误：
  - `current_user_not_found`：viewer_user_id 在当前 org 找不到对应用户。

---

## org_get_org_overview

### 定义（Schema）

```python
fn(
    "org_get_org_overview",
    "Get current org overview: org name, CEO, headcount, department count.",
    {"type": "object", "properties": {}, "required": []},
)
```

### 实现（Implementation）

```python
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
```

### 解释

- 作用：返回组织概览：组织名、CEO（owner_user_id 对应用户）、人数、部门数。
- 入参：无。
- 权限：限定在当前 `org_id`。
- 数据来源：`org`、`user`、`dept` 表的聚合统计。
- 输出要点：
  - `ceo` 可能为 `None`（owner 用户缺失）。
  - `evidence_refs.org_ids` 包含当前 org_id。

---

## org_list_departments

### 定义（Schema）

```python
fn(
    "org_list_departments",
    "List departments in current org.",
    {"type": "object", "properties": {"limit": limit_param}, "required": []},
)
```

### 实现（Implementation）

```python
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
```

### 解释

- 作用：按 level（数值）+ 名称排序返回部门列表，并补充部门 leader 的姓名（如果存在）。
- 入参：
  - `limit`：返回条数上限；实现默认 50，并被 `clamp_limit()` 限制到 [1, 200]。
- 权限：仅当前 org 的部门。
- 数据来源：`dept`，以及左连接 `user` 获取 leader 名称。
- 输出要点：
  - `leader` 可能为 `None`。
  - `truncated` 在 `len(rows) >= limit` 时为 True。

---

## org_resolve_user

### 定义（Schema）

```python
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
)
```

### 实现（Implementation）

```python
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
```

### 解释

- 作用：把“用户识别信息”解析成当前 org 内的用户（可能 0~5 个），用于后续 tool 以 `user_id` 精确查询。
- 入参：`query` 对象，允许以下字段择一：
  - `user_id`：精确 id 匹配（优先级最高）
  - `email`：邮箱精确匹配（最多 5）
  - `mobile_suffix`：手机号后缀（非数字会被剔除），使用 `LIKE '%suffix'`（最多 5）
  - `name`：姓名精确匹配（最多 5）
- 权限：只解析当前 org 的用户。
- 输出要点：
  - 返回数组元素只包含 `user_id` 与 `name`（轻量，适合 disambiguation）。
  - `user_id` 分支查不到不会报错，而是返回空数组（便于“无结果”分支继续推理）。
- 典型错误：
  - `invalid_args`：`query` 不是对象，或所有字段都为空。

---

## org_get_user_profile

### 定义（Schema）

```python
fn(
    "org_get_user_profile",
    "Get a user's profile by user_id within current org.",
    {"type": "object", "properties": {"user_id": {"type": "string"}}, "required": ["user_id"]},
)
```

### 实现（Implementation）

```python
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
```

### 解释

- 作用：查询指定用户的档案信息（role、邮箱、脱敏手机号、入职日期、性别、manager_id）。
- 入参：`user_id`（必填）。
- 权限：目标用户必须在当前 org 内，否则返回 `user_not_found_in_org`。
- 输出要点：字段与 `org_get_self_profile` 类似，但不包含部门列表与 manager 详情，只返回 `manager_id`。

---

## org_get_user_manager

### 定义（Schema）

```python
fn(
    "org_get_user_manager",
    "Get a user's direct manager info within current org.",
    {"type": "object", "properties": {"user_id": {"type": "string"}}, "required": ["user_id"]},
)
```

### 实现（Implementation）

```python
if tool_name == "org_get_user_manager":
    user_id = str(tool_args.get("user_id") or "").strip()
    u = ensure_user_in_org(user_id)
    if not u:
        return err("user_not_found", "user_not_found_in_org")
    manager = lookup_user(u["manager_id"]) if u["manager_id"] else None
    payload = {"user_id": u["id"], "name": u["name"], "manager": {"user_id": manager["id"], "name": manager["name"]} if manager else None}
    return ok(payload, "user manager", refs={"user_ids": [u["id"], manager["id"]] if manager else [u["id"]]})
```

### 解释

- 作用：返回某用户的直属上级（如果有）。
- 入参：`user_id`（必填）。
- 权限：目标用户需在当前 org。
- 输出要点：
  - `manager` 可能为 `None`（无 manager_id 或 manager 不存在）。
  - `evidence_refs.user_ids` 会包含 user 与 manager（若存在）。

---

## org_get_user_departments

### 定义（Schema）

```python
fn(
    "org_get_user_departments",
    "Get a user's departments within current org.",
    {"type": "object", "properties": {"user_id": {"type": "string"}}, "required": ["user_id"]},
)
```

### 实现（Implementation）

```python
if tool_name == "org_get_user_departments":
    user_id = str(tool_args.get("user_id") or "").strip()
    u = ensure_user_in_org(user_id)
    if not u:
        return err("user_not_found", "user_not_found_in_org")
    depts = _query_user_departments(conn, org_id, u["id"])
    return ok({"user_id": u["id"], "name": u["name"], "departments": depts}, "user departments", refs={"user_ids": [u["id"]], "dept_ids": [d["dept_id"] for d in depts]})
```

### 解释

- 作用：返回某用户的部门列表（一个人可能属于多个部门）。
- 入参：`user_id`（必填）。
- 权限：目标用户需在当前 org。
- 输出要点：同时在 `evidence_refs` 中给出 `dept_ids`，方便上层做引用或后续查询。

---

## org_search_users

### 定义（Schema）

```python
fn(
    "org_search_users",
    "Search users by keyword (name/email/mobile suffix) within current org.",
    {"type": "object", "properties": {"query": {"type": "string"}, "limit": limit_param}, "required": ["query"]},
)
```

### 实现（Implementation）

```python
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
```

### 解释

- 作用：按关键字在当前 org 的用户中模糊搜索（姓名/邮箱/手机号/或 id 精确匹配）。
- 入参：
  - `query`：必填；实现会把空白字符去掉再做 `LIKE`。
  - `limit`：默认 20，最大 200。
- 输出要点：
  - 返回每条包含 `user_id/name/email/mobile(role 脱敏)/role(标题化)`。
  - `truncated` 提示是否可能有更多结果。
- 典型错误：`query is required`。

---

## org_get_dept_detail

### 定义（Schema）

```python
fn(
    "org_get_dept_detail",
    "Get department detail by dept_id within current org.",
    {"type": "object", "properties": {"dept_id": {"type": "string"}}, "required": ["dept_id"]},
)
```

### 实现（Implementation）

```python
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
```

### 解释

- 作用：查询部门的基本信息和 leader（如果配置了）。
- 入参：`dept_id`（必填）。
- 权限：部门必须属于当前 org。
- 典型错误：`dept_not_found_in_org`。

---

## org_list_dept_users

### 定义（Schema）

```python
fn(
    "org_list_dept_users",
    "List users in a department by dept_id within current org.",
    {"type": "object", "properties": {"dept_id": {"type": "string"}, "limit": limit_param}, "required": ["dept_id"]},
)
```

### 实现（Implementation）

```python
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
```

### 解释

- 作用：列出某部门的成员列表（按姓名排序）。
- 入参：
  - `dept_id`：必填。
  - `limit`：默认 50，最大 200。
- 权限：部门需在当前 org。
- 数据来源：`dept_user` + `user`。
- 输出要点：同时返回 `dept_name`，减少上层二次查询。

---

## org_get_subordinates

### 定义（Schema）

```python
fn(
    "org_get_subordinates",
    "List direct subordinates of a manager_id within current org.",
    {"type": "object", "properties": {"manager_id": {"type": "string"}, "limit": limit_param}, "required": ["manager_id"]},
)
```

### 实现（Implementation）

```python
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
```

### 解释

- 作用：列出某 manager 的直属下属（基于 `user.manager_id` 字段）。
- 入参：`manager_id`（必填）、`limit`（可选）。
- 权限：manager 必须在当前 org。
- 输出要点：返回 `manager_name`，并把 manager 与下属都放入 `evidence_refs.user_ids`。

---

## org_get_dept_tree_path

### 定义（Schema）

```python
fn(
    "org_get_dept_tree_path",
    "Get department tree path (root to current) by dept_id within current org.",
    {"type": "object", "properties": {"dept_id": {"type": "string"}}, "required": ["dept_id"]},
)
```

### 实现（Implementation）

```python
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
```

### 解释

- 作用：从某部门向上追溯 parent_id，拼出从根到当前部门的路径字符串（用 `/` 连接）。
- 入参：`dept_id`（必填）。
- 安全性：用 `seen` + `max_hops=20` 防止环或异常深度导致死循环。
- 输出要点：
  - `path` 是“根/…/当前”的路径。
  - 如果起始 dept 不存在，返回 `dept_not_found_in_org`。

---

## im_list_my_sessions

### 定义（Schema）

```python
fn(
    "im_list_my_sessions",
    "List sessions visible to current user.",
    {"type": "object", "properties": {"limit": limit_param}, "required": []},
)
```

### 实现（Implementation）

```python
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
```

### 解释

- 作用：列出“当前用户可见”的 IM 会话（session）清单。
- 入参：`limit`（可选），默认 200。
- 权限：只看 `im_user_session` 中属于 viewer_user_id 的 session。
- 输出要点：
  - `conversation_type` 反映会话类型（实现里另外地方用 `'1'` 表示私聊）。

---

## im_get_recent_contacts

### 定义（Schema）

```python
fn(
    "im_get_recent_contacts",
    "Get recent contacts for current user from private chats.",
    {"type": "object", "properties": {"limit": limit_param}, "required": []},
)
```

### 实现（Implementation）

```python
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
```

### 解释

- 作用：从私聊消息中推导“最近联系人列表”，每个联系人取最近一条消息的时间和内容预览。
- 入参：`limit`（默认 10，最大 200）。
- 权限：
  - 必须 join `im_user_session`，确保 viewer 对该 session 可见。
  - 仅私聊：`conversation_type='1'`，且消息的 from/target 包含 viewer。
- 实现细节：
  - 先取最近 500 条私聊消息，再按“对方用户 id”去重取首次出现（即最新一条）。
  - 最终按时间排序后再截断到 `limit`。
- 输出要点：
  - `last_message_preview` 最长 120 字符。
  - `other_user_name` 可能为 None（对方用户找不到）。

---

## im_get_chat_history

### 定义（Schema）

```python
fn(
    "im_get_chat_history",
    "Get chat history between current user and other_user_id (private chat).",
    {"type": "object", "properties": {"other_user_id": {"type": "string"}, "limit": limit_param}, "required": ["other_user_id"]},
)
```

### 实现（Implementation）

```python
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
```

### 解释

- 作用：获取当前用户与另一用户的私聊历史消息。
- 入参：
  - `other_user_id`：必填。
  - `limit`：默认 20。
- 权限：
  - 对方必须在当前 org，否则 `other_user_not_found_in_org`。
  - viewer 必须在 `im_user_session` 中拥有该 `session_id` 的可见性，否则 `session_not_visible_to_current_user`。
- 关键实现：
  - `session_id` 由两个 user_id 排序后拼接 `"{a}_{b}"`，确保双方一致。
  - 先按时间倒序取最近 N 条，再 `reversed()` 变成时间正序返回，便于直接展示。
- 输出要点：每条 `content` 最长 300 字符。

---

## im_get_session_messages

### 定义（Schema）

```python
fn(
    "im_get_session_messages",
    "Get recent messages for a session_id visible to current user.",
    {"type": "object", "properties": {"session_id": {"type": "string"}, "limit": limit_param}, "required": ["session_id"]},
)
```

### 实现（Implementation）

```python
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
```

### 解释

- 作用：获取指定 session 的最近消息（不限定私聊/群聊，由 session_id 决定）。
- 入参：`session_id`（必填）、`limit`（默认 20）。
- 权限：viewer 必须对该 session 可见，否则 `session_not_visible_to_current_user`。
- 输出要点：
  - 相比 `im_get_chat_history`，这里返回消息里的 `target_id`。
  - 内容同样截断到 300 字符，且按时间正序返回。

---

## im_search_my_messages

### 定义（Schema）

```python
fn(
    "im_search_my_messages",
    "Search messages by keyword within sessions visible to current user.",
    {"type": "object", "properties": {"keyword": {"type": "string"}, "limit": limit_param}, "required": ["keyword"]},
)
```

### 实现（Implementation）

> 注意：该实现也复用给 `cross_search_user_messages_by_keyword`（见下方同名 tool）。

```python
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
```

### 解释

- 作用：在“当前用户可见的所有 session”里按关键词搜索消息内容。
- 入参：
  - `keyword`：必填。
  - `limit`：默认 20。
- 权限：通过 join `im_user_session`，确保只返回 viewer 可见会话中的消息。
- 输出要点：
  - `matches` 每条消息内容截断到 200 字符（比 history/列表更短）。
  - `evidence_refs.session_ids` 是去重后的 session_id 集合。

---

## im_get_message_stats

### 定义（Schema）

```python
fn(
    "im_get_message_stats",
    "Get message stats for current user in period today/week/month.",
    {
        "type": "object",
        "properties": {"period": {"type": "string", "enum": ["today", "week", "month"]}},
        "required": ["period"],
    },
)
```

### 实现（Implementation）

```python
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
```

### 解释

- 作用：统计某个时间段内的消息数量：
  - `sent_count`：当前用户发送的消息数
  - `visible_message_count`：当前用户可见的消息总数（包含别人发的）
- 入参：`period` 必须是 `today|week|month`。
- 时间窗口：
  - today：当天 0 点起
  - week：本周周一 0 点起（`tm_wday` 计算）
  - month：本月 1 号 0 点起
- 权限：统计范围仍通过 join `im_user_session` 限定到 viewer 可见会话。

---

## doc_list_accessible

### 定义（Schema）

```python
fn(
    "doc_list_accessible",
    "List documents accessible to current user.",
    {"type": "object", "properties": {"limit": limit_param}, "required": []},
)
```

### 实现（Implementation）

```python
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
```

### 解释

- 作用：列出当前用户可访问文档（按更新时间倒序）。
- 入参：`limit`（默认 50）。
- 权限：通过 `doc_user_access` 精确控制可见性。
- 输出要点：返回 `note_preview`（最多 160 字符）用于列表展示。

---

## doc_search_accessible

### 定义（Schema）

```python
fn(
    "doc_search_accessible",
    "Search documents accessible to current user by keywords.",
    {"type": "object", "properties": {"keywords": {"type": "string"}, "limit": limit_param}, "required": ["keywords"]},
)
```

### 实现（Implementation）

```python
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
```

### 解释

- 作用：基于全文索引（`doc_fts`）在“用户可访问文档集合”里搜索。
- 入参：
  - `keywords`：必填；按空白切分成 tokens。
  - `limit`：默认 10。
- 关键实现：
  - tokens 最多取 6 个。
  - FTS 查询字符串使用 `" AND "` 连接，意味着每个 token 都必须命中。
  - 仍然 join `doc_user_access` 做权限过滤。
- 输出要点：返回时把实际参与搜索的 tokens（截断后）回传在 `keywords` 字段里，便于追踪搜索口径。

---

## doc_get_detail

### 定义（Schema）

```python
fn(
    "doc_get_detail",
    "Get document detail by doc_id if current user has access.",
    {"type": "object", "properties": {"doc_id": {"type": "string"}}, "required": ["doc_id"]},
)
```

### 实现（Implementation）

```python
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
```

### 解释

- 作用：获取某篇文档的详情（含 note 内容片段）。
- 入参：`doc_id`（必填）。
- 权限：先查 `doc_user_access`，无权限直接 `permission_denied`。
- 输出要点：
  - `note` 会截断到 2000 字符，避免响应过大。
  - `user_ids` 可能包含 owner（如果 owner 字段存在）。

---

## doc_get_stats

### 定义（Schema）

```python
fn(
    "doc_get_stats",
    "Get stats of accessible documents for current user grouped by ctype.",
    {"type": "object", "properties": {}, "required": []},
)
```

### 实现（Implementation）

```python
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
```

### 解释

- 作用：按文档类型（`ctype`）聚合统计当前用户可访问文档数。
- 入参：无。
- 权限：统计口径仍是 `doc_user_access` 限定的集合。
- 输出要点：`total` 为按 `by_ctype` 求和的总数。

---

## doc_list_recently_updated

### 定义（Schema）

```python
fn(
    "doc_list_recently_updated",
    "List recently updated documents accessible to current user.",
    {"type": "object", "properties": {"limit": limit_param}, "required": []},
)
```

### 实现（Implementation）

```python
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
```

### 解释

- 作用：返回最近更新的可访问文档列表（无 note 预览，更偏“时间线”）。
- 入参：`limit`（默认 20）。
- 权限：通过 `doc_user_access` 限定。

---

## doc_list_created_by_me

### 定义（Schema）

```python
fn(
    "doc_list_created_by_me",
    "List documents created by current user.",
    {"type": "object", "properties": {"limit": limit_param}, "required": []},
)
```

### 实现（Implementation）

```python
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
```

### 解释

- 作用：列出“当前用户作为 owner”的文档（创建时间倒序）。
- 入参：`limit`（默认 20）。
- 权限：owner=viewer_user_id 且 org_id 匹配。

---

## cal_get_events_in_range

### 定义（Schema）

```python
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
)
```

### 实现（Implementation）

```python
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
```

### 解释

- 作用：查询某用户在一个时间区间内的日程事件（半开区间 [start_ms, end_ms)）。
- 入参：
  - `start_ms`/`end_ms`：必填，必须能转 int。
  - `user_id`：可选，默认 viewer_user_id。
  - `limit`：默认 50。
- 权限：`user_id` 必须在当前 org，否则 `target_user_not_in_current_org`。
- 可见性口径：事件必须满足“该用户是参与者或组织者”。
- 时间重叠判断：通过 `NOT (end <= start_ms OR start >= end_ms)`，即只返回与区间有交集的事件。

---

## cal_get_events_on_date

### 定义（Schema）

```python
fn(
    "cal_get_events_on_date",
    "Get calendar events for a user on a date (YYYY-MM-DD) within current org.",
    {"type": "object", "properties": {"date": {"type": "string"}, "user_id": {"type": "string"}, "limit": limit_param}, "required": ["date"]},
)
```

### 实现（Implementation）

```python
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
```

### 解释

- 作用：按日期（YYYY-MM-DD）查询日程事件；内部转换为一天的起止 ms 后复用 `cal_get_events_in_range` 的逻辑。
- 入参：`date` 必填；`user_id`/`limit` 可选。
- 权限：同 `cal_get_events_in_range`。
- 输出：完全等价于调用 `cal_get_events_in_range` 的返回结构。

---

## cal_search_events

### 定义（Schema）

```python
fn(
    "cal_search_events",
    "Search calendar events by keyword within current org.",
    {"type": "object", "properties": {"keyword": {"type": "string"}, "limit": limit_param}, "required": ["keyword"]},
)
```

### 实现（Implementation）

```python
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
```

### 解释

- 作用：按主题（subject）关键词搜索日程事件。
- 入参：`keyword` 必填，`limit` 默认 20。
- 可见性口径（粗粒度 org 级）：
  - 事件只要“存在一个参与者属于当前 org”或“组织者属于当前 org”就会被纳入结果。
  - 这与“只看 viewer 自己的日程”不同，更像“组织范围事件库搜索”。
- 输出：返回事件列表，不包含参与者明细。

---

## cal_check_freebusy

### 定义（Schema）

```python
fn(
    "cal_check_freebusy",
    "Check if a user is busy in [start_ms, end_ms) within current org.",
    {
        "type": "object",
        "properties": {"start_ms": {"type": "integer"}, "end_ms": {"type": "integer"}, "user_id": {"type": "string"}},
        "required": ["start_ms", "end_ms", "user_id"],
    },
)
```

### 实现（Implementation）

```python
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
```

### 解释

- 作用：检查某用户在一个时间段内是否“忙”（是否存在冲突事件）。
- 入参：`start_ms/end_ms/user_id` 全必填。
- 权限：目标用户需在当前 org。
- 实现方式：复用 `cal_get_events_in_range`，只要返回事件列表非空就判定 `busy=True`，并把冲突事件列表原样透传在 `conflicts`。

---

## cal_get_event_detail

### 定义（Schema）

```python
fn(
    "cal_get_event_detail",
    "Get event detail by event_id within current org.",
    {"type": "object", "properties": {"event_id": {"type": "string"}}, "required": ["event_id"]},
)
```

### 实现（Implementation）

```python
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
```

### 解释

- 作用：查询单个事件的详情，并返回“属于当前 org 的参与者 user_id 列表”。
- 入参：`event_id` 必填。
- 权限判定：
  - 先查 event 是否存在。
  - 再查参与者列表，只要参与者里没有任何一个属于当前 org，就认为该 event 不属于当前 org（`event_not_in_current_org`）。
  - 这里并没有检查 viewer 是否为参与者；只要事件“在 org 内”就可见。

---

## cal_get_event_stats

### 定义（Schema）

```python
fn(
    "cal_get_event_stats",
    "Get calendar stats for current user in period today/week/month.",
    {"type": "object", "properties": {"period": {"type": "string", "enum": ["today", "week", "month"]}}, "required": ["period"]},
)
```

### 实现（Implementation）

```python
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
```

### 解释

- 作用：统计当前用户在某个 period 内的事件数量（event_count）。
- 入参：`period` 必须为 `today|week|month`。
- 实现方式：计算 period 对应的时间窗口，然后复用 `cal_get_events_in_range`，并对结果 events 计数。

---

## cross_get_shared_docs

### 定义（Schema）

```python
fn(
    "cross_get_shared_docs",
    "Get docs accessible by both current user and other_user_id in current org.",
    {"type": "object", "properties": {"other_user_id": {"type": "string"}, "limit": limit_param}, "required": ["other_user_id"]},
)
```

### 实现（Implementation）

```python
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
```

### 解释

- 作用：找出“当前用户与另一用户共同可访问”的文档集合（交集）。
- 入参：`other_user_id` 必填，`limit` 默认 20。
- 权限：对方必须在当前 org；文档可见性交集通过 `doc_user_access` 的自连接实现。

---

## cross_get_common_meetings

### 定义（Schema）

```python
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
)
```

### 实现（Implementation）

```python
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
```

### 解释

- 作用：查询“当前用户与另一用户共同参加”的会议（即同一 event 同时有两人的 participant 记录）。
- 入参：
  - `other_user_id`：必填。
  - `start_ms/end_ms`：可选；两者都提供时才启用时间重叠过滤。
  - `limit`：默认 20。
- 权限：对方用户必须在当前 org。
- 输出要点：结果按 `start_time` 倒序。

---

## cross_get_user_card

### 定义（Schema）

```python
fn(
    "cross_get_user_card",
    "Get a combined user card for other_user_id: profile, departments, manager.",
    {"type": "object", "properties": {"other_user_id": {"type": "string"}}, "required": ["other_user_id"]},
)
```

### 实现（Implementation）

```python
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
```

### 解释

- 作用：返回“对方用户”的一张综合名片：基础信息 + 部门 + 直属上级（详情）。
- 入参：`other_user_id` 必填。
- 权限：对方必须在当前 org。
- 输出要点：相比 `org_get_user_profile`，这里额外包含 `departments` 与 `manager` 详情。

---

## cross_search_user_messages_by_keyword

### 定义（Schema）

```python
fn(
    "cross_search_user_messages_by_keyword",
    "Search current user's messages by keyword.",
    {"type": "object", "properties": {"keyword": {"type": "string"}, "limit": limit_param}, "required": ["keyword"]},
)
```

### 实现（Implementation）

该 tool 与 [im_search_my_messages](#im_search_my_messages) 完全共用同一段实现：

```python
if tool_name == "im_search_my_messages" or tool_name == "cross_search_user_messages_by_keyword":
    ...
```

### 解释

- 作用：语义上属于 cross 组，但功能等价于“在当前用户可见 session 里搜索消息”。
- 入参/权限/输出：同 `im_search_my_messages`。
