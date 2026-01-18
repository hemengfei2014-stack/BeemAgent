# IM（即时通讯）系统离线数据 Schema

## 业务场景说明

本文件用于模拟 IM（即时通讯）系统的两类核心离线数据：

1. **消息明细表** `ods_im_message_min`：用于对话回放、检索、审计、统计等。
2. **会话参与关系表** `ods_im_session_participant_min`：用于“用户是否有权访问某个session”的判断（列表聚合版，无时间边界控制）。

## 关键概念

- **org_id**：租户/组织隔离维度。任何查询/回放/权限判断必须先按 `org_id` 过滤。
- **session_id**：会话唯一ID，用于将同一对话线程的所有消息聚合在一起。
    - **单聊**：`min(userA,userB) + '_' + max(userA,userB)`，保证双方计算一致（顺序无关）。
    - **群聊**：群ID（例如 `group_123`）。
- **conversation_type**：会话类型（当前仅约定 `1`=单聊，`3`=群聊）。

## 消息类型与内容简化约定

- **message_type**：`1`=纯文本；`2`=链接（网页/在线文档等）；`3`=文件。
- **content**：纯文本字段。为简化示例，这里仅保存：
    - `message_type=1`：文本内容
    - `message_type=2`：链接标题（如需 URL 等元信息，建议扩展字段或增加扩展表）
    - `message_type=3`：文件名称（如需大小/下载地址等元信息，建议扩展字段或增加扩展表）

## 权限/参与关系（等价访问权限）说明

- **规则**：用户“参与”某个 `session_id`，即拥有该 `session_id` 的访问权限。
    - **单聊**：参与者固定为两人（`from_user_id` 与 `target_id` 两侧用户）。
    - **群聊**：参与者随入群/退群变化。
- **参与关系简化**：按用户聚合其可访问的 session 列表，不记录时间窗口；即认为用户对列表中的 session 内全部消息均有访问权限。

### 典型使用方式（示意）

- **回放消息前先做参与关系过滤**：
    从参与表取 `(org_id,user_id)` 的 `session_id` 列表，判断 `msg.session_id` ∈ 该列表。

---

## 表结构定义

### 1. 消息明细表 (ods_im_message_min)

```sql
CREATE TABLE IF NOT EXISTS ods_im_message_min (
  org_id            STRING  COMMENT '组织/企业ID（Organization ID）。同一套Hive表可混存多个组织数据，所有查询/回放必须先按org_id过滤，避免跨租户串数据',
  session_id        STRING  COMMENT '会话唯一ID（Conversation/Session ID，用来把同一“对话线程”的所有消息聚在一起，是重建对话的第一主键维度）。规则：单聊=min(userA,userB) + ''_'' + max(userA,userB)（保证双方发消息得到相同session_id）；群聊=群ID（例如 group_123）',
  conversation_type INT     COMMENT '会话类型：1=单聊，3=群聊。用于解释session_id/target_id语义，并支持按单聊/群聊过滤',
  message_id        STRING  COMMENT '消息唯一ID（业务生成，不是Hive行号）。用于去重/幂等写入；以 (org_id, message_id) 作为幂等键，也可作为同一毫秒内的稳定排序tie-break',
  from_user_id      STRING  COMMENT '发送者用户ID（谁发的）。重建对话时用于判断消息气泡方向/头像/名称等',
  target_id         STRING  COMMENT '接收方标识（对端/目标）。单聊场景=对方用户ID；群聊场景=群ID（与session_id一致）',
  send_time_ms      BIGINT  COMMENT '消息发送时间戳（Unix Epoch 毫秒，固定为毫秒单位）。用于会话内按时间排序与按时间范围拉取',
  message_type      INT     COMMENT '消息类型：1=纯文本；2=链接（可能是网页、在线文档等）；3=文件',
  content           STRING  COMMENT '消息内容（简化为纯文本）。当 message_type=1 时保存文本内容；当 message_type=2 时保存链接标题；当 message_type=3 时保存文件名称'
)
STORED AS ORC
TBLPROPERTIES ('orc.compress'='SNAPPY');
```

### 2. 会话参与关系表 (ods_im_session_participant_min)

```sql
CREATE TABLE IF NOT EXISTS ods_im_session_participant_min (
  org_id            STRING  COMMENT '组织/企业ID（Organization ID）。同一套Hive表可混存多个组织数据，所有权限判断必须先按org_id过滤，避免跨租户越权',
  user_id           STRING  COMMENT '用户ID（主键的一部分）。表示“谁”拥有某些 session 的访问权限（参与者=可访问）',
  session_ids       ARRAY<STRING> COMMENT '会话ID列表。保存该用户可访问的所有 session_id；与消息表 ods_im_message_min.session_id 一致',
  conversation_types ARRAY<INT>   COMMENT '会话类型列表：1=单聊，3=群聊。按顺序与 session_ids 一一对应，用于解释各 session 的类型'
)
COMMENT '用户-会话参与关系聚合快照（等价访问权限）。规则：用户拥有其 session_ids 列表中所有会话的访问权限；不记录时间窗口'
STORED AS ORC
TBLPROPERTIES ('orc.compress'='SNAPPY');
```

---

## 判权逻辑示例（伪代码）

**目标**：判断访问者 `(viewer_org_id, viewer_user_id)` 是否有权访问某条消息 `(msg.org_id, msg.message_id)`

**输入前提**：
1. 消息记录 `msg` 取自 `ods_im_message_min`
2. 用户参与关系 `participant` 取自 `ods_im_session_participant_min`
   (筛选条件：`org_id=viewer_org_id AND user_id=viewer_user_id AND array_contains(session_ids, msg.session_id)`)

**伪代码**：

```javascript
// 0. 消息是否存在
if (msg == null) {
  return false;
}

// 1. 租户隔离检查
if (viewer_org_id != msg.org_id) {
  return false;
}

// 2. 参与关系列表判定（只看 session 是否在列表中）
// 说明：
// - 每个用户保存其可访问的 session_id 列表与对应的 conversation_types（按相同顺序对齐）
// - 判权只需判断 msg.session_id 是否属于该列表
can_access = exists ods_im_session_participant_min p where
  p.org_id = viewer_org_id
  AND p.user_id = viewer_user_id
  AND array_contains(p.session_ids, msg.session_id)

return can_access
```
