"""
IM系统数据加载和查询工具
用于回答 im_qa.md 中的问题

主要功能：
- 加载会话参与者和消息数据
- 获取用户的会话列表
- 查询私聊和群聊消息
- 统计发送/接收消息数量
- 查找最近联系人
- 关键词搜索消息

数据表说明：
- ods_im_session_participant_min.txt: 会话参与表（org_id, user_id, session_ids, conversation_types）
  - session_ids: 用户参与的会话ID列表（逗号分隔）
  - conversation_types: 对应的会话类型列表（逗号分隔）
- ods_im_message_min.txt: 消息表（org_id, session_id, from_user_id, target_id,
  conversation_type, content, msg_type, send_time_ms）

会话类型：
- 1: 私聊（两个人一对一聊天）
- 2: 单聊（同私聊）
- 3: 群聊

消息类型：
- 1: 文本消息
- 2: 链接消息
- 3: 文件消息

权限说明：
- 用户只能访问自己参与的会话
- 私聊会话ID格式：小ID_大ID（如 10042_10051）
"""
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from org_qa_solutions.utils import OrgDataLoader, CURRENT_ORG_ID, CURRENT_USER_ID

# IM数据路径（相对路径）
IM_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                            "fake_beem", "simplified_schema", "synthetic_data", "message", "data")

# 会话类型映射表
# conversation_type -> 类型名称
CONVERSATION_TYPE = {
    1: "私聊",
    2: "单聊",
    3: "群聊",
}

# 消息类型映射表
# msg_type -> 类型名称
MESSAGE_TYPE = {
    1: "文本",
    2: "链接",
    3: "文件",
}


class IMDataLoader:
    """
    IM数据加载器

    用于加载和查询即时通讯系统数据，包括会话、消息等信息。

    示例：
        >>> loader = IMDataLoader()
        >>> sessions = loader.get_user_sessions(10042)
        >>> for session_id, conv_type in sessions:
        ...     print(f"会话ID: {session_id}, 类型: {conv_type}")
    """

    def __init__(self, data_dir: str = IM_DATA_DIR, org_id: int = CURRENT_ORG_ID):
        """
        初始化IM数据加载器

        参数：
            data_dir: 数据目录路径，默认为 IM_DATA_DIR
            org_id: 组织ID，默认为当前组织（Jaco，ID=1）

        功能：
            加载会话参与表和消息表
            解析用户的会话列表
            只加载指定组织的数据
        """
        self.data_dir = data_dir
        self.org_id = org_id
        self.org_loader = OrgDataLoader()
        self._load_data()

    def _load_data(self):
        """
        加载IM数据表（内部方法）

        加载的数据表：
        - ods_im_session_participant_min.txt: 会话参与表
        - ods_im_message_min.txt: 消息表

        过滤规则：
            - 只保留当前组织（org_id）的数据
        """
        # 加载会话参与表
        self.participant_df = pd.read_csv(f"{self.data_dir}/ods_im_session_participant_min.txt", sep='\t')
        # 只保留当前组织的数据
        self.participant_df = self.participant_df[self.participant_df['org_id'] == self.org_id]

        # 加载消息表
        self.message_df = pd.read_csv(f"{self.data_dir}/ods_im_message_min.txt", sep='\t')
        # 只保留当前组织的数据
        self.message_df = self.message_df[self.message_df['org_id'] == self.org_id]

        # 解析用户的会话列表
        self._parse_user_sessions()

    def _parse_user_sessions(self):
        """
        解析用户的会话列表（内部方法）

        生成数据结构：
            self.user_sessions = {user_id: [(session_id, conversation_type), ...]}

        说明：
            - 从会话参与表中解析每个用户参与的会话
            - session_ids 和 conversation_types 是逗号分隔的字符串
        """
        self.user_sessions = {}  # {user_id: [(session_id, conversation_type), ...]}

        for _, row in self.participant_df.iterrows():
            user_id = row['user_id']
            session_ids = str(row['session_ids']).split(',')
            conv_types = str(row['conversation_types']).split(',')

            sessions = []
            for sid, ctype in zip(session_ids, conv_types):
                sessions.append((sid, int(ctype)))

            self.user_sessions[user_id] = sessions

    # ==================== 会话查询方法 ====================

    def get_user_sessions(self, user_id: int) -> List[Tuple[str, int]]:
        """
        获取用户的所有会话

        参数：
            user_id: 用户ID

        返回：
            List[Tuple[str, int]]: 会话列表，每个元素为 (session_id, conversation_type)

        会话类型：
            - 1: 私聊
            - 2: 单聊
            - 3: 群聊

        示例：
            >>> sessions = im_loader.get_user_sessions(10042)
            >>> for session_id, conv_type in sessions:
            ...     print(f"会话: {session_id}, 类型: {conv_type}")
            会话: 10042_10051, 类型: 1  # 与萧翔的私聊

        注意：
            - 用户只能获取自己参与的会话
            - 这是权限控制的核心
        """
        return self.user_sessions.get(user_id, [])

    def get_session_messages(self, session_id: str, conversation_type: int = None) -> pd.DataFrame:
        """
        获取会话的所有消息

        参数：
            session_id: 会话ID
            conversation_type: 会话类型（可选），用于过滤

        返回：
            pd.DataFrame: 消息列表，包含以下字段：
                - session_id: 会话ID
                - from_user_id: 发送者ID
                - target_id: 接收者ID（私聊）
                - conversation_type: 会话类型
                - content: 消息内容
                - msg_type: 消息类型
                - send_time_ms: 发送时间（毫秒时间戳）

        示例：
            >>> messages = im_loader.get_session_messages("10042_10051")
            >>> len(messages)  # 16条消息
            >>> messages.iloc[0]['content']  # 第一条消息内容
        """
        messages = self.message_df[self.message_df['session_id'] == session_id]
        if conversation_type is not None:
            messages = messages[messages['conversation_type'] == conversation_type]
        return messages

    # ==================== 用户间消息查询方法 ====================

    def get_messages_between_users(self, user1_id: int, user2_id: int) -> pd.DataFrame:
        """
        获取两个用户之间的私聊消息

        参数：
            user1_id: 第一个用户ID
            user2_id: 第二个用户ID

        返回：
            pd.DataFrame: 两个用户之间的所有私聊消息

        会话ID格式：
            - 私聊会话ID为 "小ID_大ID"
            - 例如：用户10042和10051的会话ID为 "10042_10051"

        示例：
            >>> messages = im_loader.get_messages_between_users(10042, 10051)
            >>> len(messages)  # 16条消息
            >>> # 获取用户10042发送的消息
            >>> sent = messages[messages['from_user_id'] == 10042]

        应用场景：
            - 查看与某个同事的聊天记录
            - 统计与某人的沟通频率
        """
        # 私聊会话ID格式: 小ID_大ID
        session_id = f"{min(user1_id, user2_id)}_{max(user1_id, user2_id)}"
        return self.get_session_messages(session_id, conversation_type=1)

    # ==================== 发送/接收消息方法 ====================

    def get_user_sent_messages(self, user_id: int, session_id: str = None) -> pd.DataFrame:
        """
        获取用户发送的消息

        参数：
            user_id: 用户ID
            session_id: 会话ID（可选），如果指定则只返回该会话中发送的消息

        返回：
            pd.DataFrame: 用户发送的消息列表

        示例：
            >>> sent = im_loader.get_user_sent_messages(10042)
            >>> len(sent)  # 发送的消息总数

            >>> # 指定会话
            >>> sent = im_loader.get_user_sent_messages(10042, "10042_10051")
            >>> len(sent)  # 在该会话中发送的消息数
        """
        messages = self.message_df[self.message_df['from_user_id'] == user_id]
        if session_id is not None:
            messages = messages[messages['session_id'] == session_id]
        return messages

    def get_user_received_messages(self, user_id: int, session_id: str = None) -> pd.DataFrame:
        """
        获取用户接收的消息

        参数：
            user_id: 用户ID
            session_id: 会话ID（可选），如果指定则只返回该会话中接收的消息

        返回：
            pd.DataFrame: 用户接收的消息列表

        消息接收规则：
            - 私聊：target_id 等于 user_id 的消息
            - 群聊：from_user_id 不等于 user_id 的消息（排除自己发的）

        示例：
            >>> received = im_loader.get_user_received_messages(10042)
            >>> len(received)  # 接收的消息总数

        应用场景：
            - 统计接收的消息数量
            - 查看来自特定人的消息
        """
        # 对于私聊，target_id是接收者
        # 对于群聊，需要从from_user_id中排除用户自己
        private_messages = self.message_df[
            (self.message_df['conversation_type'] == 1) &
            (self.message_df['target_id'] == user_id)
        ]

        # 对于群聊，排除自己发的消息
        group_messages = self.message_df[
            (self.message_df['conversation_type'] == 3) &
            (self.message_df['from_user_id'] != user_id)
        ]

        # 获取用户的群聊会话
        user_sessions = self.get_user_sessions(user_id)
        group_session_ids = [s[0] for s in user_sessions if s[1] == 3]

        group_messages = group_messages[group_messages['session_id'].isin(group_session_ids)]

        messages = pd.concat([private_messages, group_messages])

        if session_id is not None:
            messages = messages[messages['session_id'] == session_id]

        return messages

    # ==================== 联系人查询方法 ====================

    def get_recent_contacts(self, user_id: int, limit: int = 10) -> List[Dict]:
        """
        获取最近联系的联系人

        参数：
            user_id: 用户ID
            limit: 返回数量限制，默认10

        返回：
            List[Dict]: 最近联系人列表，每个元素包含：
                - id: 联系人ID（群聊时为session_id）
                - last_time: 最后一次联系时间（毫秒时间戳）
                - is_group: 是否为群聊
                - session_id: 会话ID

        示例：
            >>> contacts = im_loader.get_recent_contacts(10042)
            >>> contacts[0]['id']  # 最近联系的用户ID
            >>> im_loader.timestamp_to_datetime(contacts[0]['last_time'])

        应用场景：
            - 回答"最近和谁聊过天"
            - 找到最常联系的同事
        """
        sent = self.get_user_sent_messages(user_id)
        received = self.get_user_received_messages(user_id)

        all_messages = pd.concat([sent, received])
        all_messages = all_messages.sort_values('send_time_ms', ascending=False)

        # 统计每个联系人的最后一条消息时间
        contacts = {}
        for _, msg in all_messages.iterrows():
            other_id = msg['target_id'] if msg['from_user_id'] == user_id else msg['from_user_id']

            # 对于群聊，记录群组ID
            if msg['conversation_type'] == 3:
                other_id = msg['session_id']

            if other_id not in contacts:
                contacts[other_id] = {
                    'id': other_id,
                    'last_time': msg['send_time_ms'],
                    'is_group': msg['conversation_type'] == 3,
                    'session_id': msg['session_id']
                }
            else:
                if msg['send_time_ms'] > contacts[other_id]['last_time']:
                    contacts[other_id]['last_time'] = msg['send_time_ms']

        # 按最后联系时间排序
        sorted_contacts = sorted(contacts.values(), key=lambda x: x['last_time'], reverse=True)
        return sorted_contacts[:limit]

    # ==================== 消息统计方法 ====================

    def get_message_count_by_sender(self, user_id: int, days: int = None) -> Dict[int, int]:
        """
        统计发送给指定用户的消息数量（按发信人统计）

        参数：
            user_id: 接收者用户ID
            days: 天数限制（可选），如果指定则只统计最近N天的消息

        返回：
            Dict[int, int]: 发信人ID -> 消息数量的映射

        示例：
            >>> counts = im_loader.get_message_count_by_sender(10042)
            >>> # counts = {10051: 16} 表示用户10051发来了16条消息
            >>> counts.get(10051, 0)  # 获取特定发信人的消息数

            >>> # 统计最近7天的消息
            >>> counts = im_loader.get_message_count_by_sender(10042, days=7)

        应用场景：
            - 统计谁给我发消息最多
            - 分析沟通频率
        """
        messages = self.get_user_received_messages(user_id)

        if days is not None:
            cutoff_time = datetime.now().timestamp() * 1000 - (days * 24 * 3600 * 1000)
            messages = messages[messages['send_time_ms'] >= cutoff_time]

        # 统计每个发信人的消息数
        counts = {}
        for _, msg in messages.iterrows():
            sender_id = msg['from_user_id']
            counts[sender_id] = counts.get(sender_id, 0) + 1

        return counts

    # ==================== 会话活跃度方法 ====================

    def get_recent_sessions(self, user_id: int, limit: int = 5) -> List[Dict]:
        """
        获取最近活跃的会话

        参数：
            user_id: 用户ID
            limit: 返回数量限制，默认5

        返回：
            List[Dict]: 最近活跃的会话列表，每个元素包含：
                - session_id: 会话ID
                - conversation_type: 会话类型
                - last_time: 最后一条消息时间
                - last_message_from: 最后一条消息的发送者ID

        示例：
            >>> sessions = im_loader.get_recent_sessions(10042)
            >>> sessions[0]['session_id']  # 最近活跃的会话ID
            >>> sessions[0]['conversation_type']  # 会话类型

        应用场景：
            - 找到最近聊天的会话
            - 快速回到活跃对话
        """
        messages = pd.concat([
            self.get_user_sent_messages(user_id),
            self.get_user_received_messages(user_id)
        ])
        messages = messages.sort_values('send_time_ms', ascending=False)

        sessions = {}
        for _, msg in messages.iterrows():
            session_id = msg['session_id']
            if session_id not in sessions:
                sessions[session_id] = {
                    'session_id': session_id,
                    'conversation_type': msg['conversation_type'],
                    'last_time': msg['send_time_ms'],
                    'last_message_from': msg['from_user_id']
                }

        sorted_sessions = sorted(sessions.values(), key=lambda x: x['last_time'], reverse=True)
        return sorted_sessions[:limit]

    def get_unreplied_sessions(self, user_id: int) -> List[Dict]:
        """
        获取未回复的会话（对方最后发言且我未回复）

        参数：
            user_id: 用户ID

        返回：
            List[Dict]: 未回复的会话列表，按时间倒序排列

        判断逻辑：
            - 会话的最后一条消息不是当前用户发的
            - 表示对方发了消息，但我还没有回复

        示例：
            >>> unreplied = im_loader.get_unreplied_sessions(10042)
            >>> for session in unreplied:
            ...     print(f"会话 {session['session_id']} 需要回复")

        应用场景：
            - 找到需要回复的消息
            - 提醒用户处理待回复的会话
        """
        # 获取用户参与的所有会话
        user_sessions = self.get_user_sessions(user_id)

        unreplied = []
        for session_id, conv_type in user_sessions:
            # 获取该会话的最后一条消息
            messages = self.get_session_messages(session_id)
            if messages.empty:
                continue

            messages = messages.sort_values('send_time_ms', ascending=False)
            last_message = messages.iloc[0]

            # 如果最后一条消息不是用户发的，说明未回复
            if last_message['from_user_id'] != user_id:
                unreplied.append({
                    'session_id': session_id,
                    'conversation_type': conv_type,
                    'last_message_from': last_message['from_user_id'],
                    'last_time': last_message['send_time_ms']
                })

        # 按时间排序
        unreplied.sort(key=lambda x: x['last_time'], reverse=True)
        return unreplied

    # ==================== 综合统计方法 ====================

    def get_message_stats(self, user_id: int, date: str = None) -> Dict:
        """
        获取用户的消息统计

        参数：
            user_id: 用户ID
            date: 日期字符串（可选），格式为 "YYYY-MM-DD"
                   如果指定，只统计该日期的消息

        返回：
            Dict: 消息统计信息，包含：
                - sent_total: 发送消息总数
                - sent_private: 私聊发送数
                - sent_group: 群聊发送数
                - received_total: 接收消息总数
                - received_private: 私聊接收数
                - received_group: 群聊接收数

        示例：
            >>> stats = im_loader.get_message_stats(10042)
            >>> stats['sent_total']  # 发送消息总数
            >>> stats['received_total']  # 接收消息总数

            >>> # 统计特定日期
            >>> stats = im_loader.get_message_stats(10042, "2026-01-15")

        应用场景：
            - 回答"今天发了多少消息"
            - 统计沟通活跃度
        """
        sent = self.get_user_sent_messages(user_id)
        received = self.get_user_received_messages(user_id)

        if date:
            # 按日期过滤
            date_obj = datetime.strptime(date, '%Y-%m-%d')
            start_ts = int(date_obj.timestamp() * 1000)
            end_ts = int((date_obj + timedelta(days=1)).timestamp() * 1000)

            sent = sent[(sent['send_time_ms'] >= start_ts) & (sent['send_time_ms'] < end_ts)]
            received = received[(received['send_time_ms'] >= start_ts) & (received['send_time_ms'] < end_ts)]

        # 统计私聊和群聊
        sent_private = sent[sent['conversation_type'] == 1]
        sent_group = sent[sent['conversation_type'] == 3]
        received_private = received[received['conversation_type'] == 1]
        received_group = received[received['conversation_type'] == 3]

        return {
            'sent_total': len(sent),
            'sent_private': len(sent_private),
            'sent_group': len(sent_group),
            'received_total': len(received),
            'received_private': len(received_private),
            'received_group': len(received_group)
        }

    # ==================== 辅助方法 ====================

    def timestamp_to_datetime(self, timestamp_ms: int) -> str:
        """
        毫秒时间戳转日期时间字符串

        参数：
            timestamp_ms: 毫秒时间戳

        返回：
            str: 格式化的日期时间 (YYYY-MM-DD HH:MM:SS)

        示例：
            >>> im_loader.timestamp_to_datetime(1736899200000)
            '2026-01-15 00:00:00'
        """
        return datetime.fromtimestamp(timestamp_ms / 1000).strftime('%Y-%m-%d %H:%M:%S')

    def get_user_name(self, user_id: int) -> str:
        """
        获取用户姓名

        参数：
            user_id: 用户ID

        返回：
            str: 用户姓名，如果用户不存在则返回 "用户{user_id}"

        示例：
            >>> im_loader.get_user_name(10042)
            '籍钧良'
            >>> im_loader.get_user_name(99999)
            '用户99999'

        说明：
            - 通过 OrgDataLoader 查询用户信息
        """
        user = self.org_loader.get_user_by_id(user_id)
        if user is not None:
            return user['name']
        return f"用户{user_id}"

    # ==================== 会话参与者方法 ====================

    def get_session_participants(self, session_id: str, conversation_type: int) -> List[int]:
        """
        获取会话的参与者

        参数：
            session_id: 会话ID
            conversation_type: 会话类型

        返回：
            List[int]: 参与者用户ID列表

        私聊会话：
            - session_id 格式为 "user1_user2"
            - 直接解析出两个用户ID

        群聊会话：
            - 从会话参与表中查找所有参与该会话的用户

        示例：
            >>> participants = im_loader.get_session_participants("10042_10051", 1)
            >>> participants  # [10042, 10051]

            >>> # 群聊会话
            >>> participants = im_loader.get_session_participants("group_123", 3)
            >>> len(participants)  # 群成员数量

        应用场景：
            - 查看群聊成员
            - 确认私聊对象
        """
        if conversation_type == 1:
            # 私聊：session_id格式为 "user1_user2"
            parts = session_id.split('_')
            return [int(parts[0]), int(parts[1])]
        else:
            # 群聊：从会话参与表中查找
            participants = []
            for user_id, sessions in self.user_sessions.items():
                for sid, ctype in sessions:
                    if sid == session_id and ctype == conversation_type:
                        participants.append(user_id)
            return participants


# 创建全局实例
# 使用方法：直接调用 im_loader 的方法
# 示例：sessions = im_loader.get_user_sessions(10042)
im_loader = IMDataLoader()
