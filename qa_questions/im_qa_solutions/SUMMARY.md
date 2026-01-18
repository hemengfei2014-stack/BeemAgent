# IM系统问题解答总结

## 文件结构
```
im_qa_solutions/
├── utils.py              # IM数据加载和查询工具
├── 001-050.md           # 最近联系人、发送/接收时间、消息统计
├── 051-150.md           # 特定用户聊天记录、关键词搜索、文件/链接统计
├── 151-249.md           # 共同群聊、全局关键词搜索、群聊统计
└── 250-298.md           # 群组搜索、素材/网红资料、会话统计
```

## 当前用户上下文
- **"我"** = Jaco组织 + 用户ID **10042**（籍钧良）

## IM数据结构

### 数据表
1. **ods_im_session_participant_min.txt** (会话参与表)
   - org_id: 组织ID
   - user_id: 用户ID
   - session_ids: 会话ID列表（逗号分隔）
   - conversation_types: 会话类型列表（1=私聊, 3=群聊）

2. **ods_im_message_min.txt** (消息表)
   - org_id: 组织ID
   - session_id: 会话ID
   - conversation_type: 会话类型
   - message_id: 消息ID
   - from_user_id: 发送者用户ID
   - target_id: 接收者用户ID
   - send_time_ms: 发送时间（毫秒时间戳）
   - message_type: 消息类型（1=文本, 2=链接, 3=文件）
   - content: 消息内容

### 会话类型
- 1: 私聊
- 3: 群聊

### 消息类型
- 1: 文本消息
- 2: 链接消息
- 3: 文件消息

## 当前用户IM数据概况

### 会话统计
- 总会话数: 1个
- 私聊: 1个（与萧翔 10051）
- 群聊: 0个

### 消息统计
- 总消息数: 16条
- 主要联系人: 萧翔

## 数据权限说明
- IM数据严格权限控制
- 用户只能访问自己参与的会话消息
- 包括：1:1私聊 + 群聊

## 依赖
```bash
pip install pandas
```

## 使用方法
```python
from utils import im_loader, CURRENT_USER_ID

# 获取用户会话
sessions = im_loader.get_user_sessions(CURRENT_USER_ID)

# 获取与特定用户的聊天记录
messages = im_loader.get_messages_between_users(CURRENT_USER_ID, 10051)

# 搜索关键词
results = search_keyword("带货")
```
