# fake_beem 目录说明

本目录包含用于模拟企业级应用（如文档系统、IM 即时通讯、组织架构）的核心数据 Schema。为了便于理解和使用，数据被划分为“原始底层实现”和“简化业务逻辑”两个部分。

## 目录结构

### 1. `original_schema` (原始底层数据表)
此目录包含系统实际运行或设计时使用的底层详细数据结构，包括 Elasticsearch 映射配置和完整的数据库 Schema。

- **`doc_mapping.jsonc`**: 文档搜索索引的 Elasticsearch Mapping 定义。包含字段类型、分词器配置（如 `cn_max_word`）、多语言支持等底层细节。
- **`message_mapping.jsonc`**: IM 消息搜索索引的 Elasticsearch Mapping 定义。包含消息内容、类型、发送者、接收者等字段的索引配置。
- **`org_system_schema.md`**: 组织架构系统的完整 SQL 表结构设计。包含组织表 (`bw_organize`)、用户表 (`bw_organize_user`)、部门表 (`bw_dept`) 等详细字段定义。

### 2. `simplified_schema` (简化业务核心表)
此目录包含经过抽象和简化的数据表设计，旨在保留满足核心业务逻辑（如权限判断、搜索、回放）所需的关键字段，忽略非核心的底层实现细节。

- **`doc.md`**: 文档系统的简化离线数据 Schema。
    - `ods_docs_min`: 文档底层明细表，作为搜索索引的唯一事实源。
    - `dwd_user_doc_access_min`: 用户-文档可访问关系快照表，用于权限判断。
- **`message.md`**: IM 系统的简化离线数据 Schema。
    - `ods_im_message_min`: 消息明细表，用于对话回放和检索。
    - `ods_im_session_participant_min`: 会话参与关系表，用于判断用户是否有权访问某个会话。
- **`org_system_schema_simplified.md`**: 组织架构系统的简化版 Schema。
    - 仅保留核心表：`org` (组织)、`user` (用户)、`dept` (部门)、`dept_user` (部门-用户关系)，去除冗余字段，专注于回答核心业务问题（如“谁的领导是谁”、“某部门有哪些人”）。
