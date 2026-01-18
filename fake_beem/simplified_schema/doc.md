# 文档系统离线数据 Schema

## 业务场景说明

本文件用于模拟企业文档系统（类似飞书/钉钉/Google Doc）的两类核心离线数据：

1. **文档底层明细表** `ods_docs_min`：作为 Elasticsearch 索引 `search_docs_index` 的唯一“事实源”（source of truth），用于全量构建与增量更新。
2. **用户-文档可访问关系快照表** `dwd_user_doc_access_min`：用于“用户是否有权访问某个文档”的判断（列表聚合版，无时间边界控制）。

## 关键概念

- **org_id**：租户/组织隔离维度。任何查询/同步/统计都必须先按 `org_id` 过滤。
- **doc_id**：业务侧文档唯一ID。同一 `org_id` 下唯一；与搜索索引中的一条文档一一对应。
- **ctype**：文档类型（当前约定 `doc`=在线文档；`sheet`=表格；`slide`=幻灯片；`pdf`=PDF）。

## 字段与内容简化约定

- **title**：标题原文。Hive 保存原始字符串；搜索侧基于该字段做全文索引与高亮。
- **note**：正文抽取后的纯文本原文。Hive 保存用于索引的文本源；搜索侧基于该字段做全文索引与高亮。
- **owner**：当前所有者，仅用于展示。所有权的变更应同步更新 `dwd_user_doc_access_min` 中的权限列表。

## 权限/参与关系（等价访问权限）说明

- **规则**：用户在 `dwd_user_doc_access_min` 表的 `doc_ids` 列表中包含某 `doc_id`，即拥有该文档的访问权限。
- **权限唯一事实源**：`dwd_user_doc_access_min`。
    - 即使是 `owner`，也必须在此表中拥有记录才被视为可访问（通常业务逻辑会自动维护）。
- **跨租户访问**：本示例默认不支持（需 `user_org_id == doc_org_id`）。

### 典型使用方式（示意）

- **搜索前先做权限过滤**：
    从权限表取 `(user_org_id, user_id)` 的 `doc_ids` 列表，作为搜索条件（terms query）注入 ES。

---

## 表结构定义

### 1. 文档底层明细表 (ods_docs_min)

```sql
CREATE TABLE IF NOT EXISTS ods_docs_min (
  org_id              STRING        COMMENT '组织/企业ID。同一套表可混存多个组织数据；任何查询/同步必须先按 org_id 过滤，禁止跨租户读取',
  doc_id              STRING        COMMENT '文档业务唯一ID（主键）。同一 org_id 下唯一；用于幂等写入（幂等键：(org_id, doc_id)）',
  create_time         BIGINT        COMMENT '创建时间（Unix Epoch 毫秒）。定义：doc_id 首次创建的时间点',
  ctype               STRING        COMMENT '业务文档类型。本示例约定取值范围：doc=在线文档；sheet=表格；slide=幻灯片；pdf=PDF。用于产品类型过滤/聚合',
  title               STRING        COMMENT '标题原文。Hive 保存原始字符串；搜索侧基于该字段做全文索引与高亮',
  note                STRING        COMMENT '正文抽取后的纯文本原文。Hive 保存用于索引的文本源；搜索侧基于该字段做全文索引与高亮',
  owner               STRING        COMMENT '文档所有者用户ID（在 org_id 内唯一）。定义：当前“归属/所有权”持有人，可发生转让；用于按所有者筛选与展示'
)
COMMENT '企业文档底层明细最小集（用于构建ES索引 search_docs_index 的源数据）'
STORED AS ORC
TBLPROPERTIES ('orc.compress'='SNAPPY');
```

### 2. 用户-文档可访问关系快照表 (dwd_user_doc_access_min)

```sql
CREATE TABLE IF NOT EXISTS dwd_user_doc_access_min (
  user_org_id        STRING  COMMENT '访问者所属组织ID。用于租户隔离；与 user_id 组合后可唯一定位一个用户',
  user_id            STRING  COMMENT '用户ID（主键的一部分）。在 user_org_id 内唯一',
  doc_ids            ARRAY<STRING> COMMENT '用户可访问的文档ID列表（仅限 user_org_id 组织内）。用于快速回答“该用户能访问哪些文档”'
)
COMMENT '用户-文档可访问关系聚合快照（权限唯一事实源）'
STORED AS ORC
TBLPROPERTIES ('orc.compress'='SNAPPY');
```

---

## 判权逻辑示例（伪代码）

**目标**：判断用户 `(user_org_id, user_id)` 是否可访问文档 `(doc.org_id, doc.doc_id)`

**输入前提**：
1. 文档记录 `doc` 取自 `ods_docs_min`
2. 用户权限关系 `access` 取自 `dwd_user_doc_access_min`
   (筛选条件：`user_org_id=user_org_id AND user_id=user_id AND array_contains(access.doc_ids, doc.doc_id)`)

**伪代码**：

```javascript
// 0. 文档是否存在
if (doc == null) {
  return false;
}

// 1. 租户隔离检查 (本示例不支持跨租户)
if (user_org_id != doc.org_id) {
  return false;
}

// 2. 权限列表判定 (唯一事实源)
// 说明：
// - 每个用户保存其可访问的 doc_id 列表与对应的 doc_types (按相同顺序对齐)
// - 判权只需判断 doc.doc_id 是否属于该列表
can_access = exists dwd_user_doc_access_min a where
  a.user_org_id = user_org_id
  AND a.user_id = user_id
  AND array_contains(a.doc_ids, doc.doc_id)

return can_access
```
