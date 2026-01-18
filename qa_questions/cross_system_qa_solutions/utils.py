"""
跨系统数据加载和查询工具
用于回答 cross_system_qa.md 中的问题

主要功能：
- 整合组织、消息、文档、日程四个系统的数据
- 提供跨系统的关联查询
- 支持复杂的业务场景分析

数据来源：
- 组织系统 (org): 用户信息、部门信息、组织架构
- 消息系统 (im): 聊天记录、会话信息
- 文档系统 (doc): 文档信息、访问权限
- 日程系统 (calendar): 会议安排、日程事件

权限说明：
- 组织数据：组织内公开
- 消息数据：只能访问自己参与的会话
- 文档数据：只能访问自己有权限的文档
- 日程数据：组织内公开

使用场景：
- 查询某同事的信息 + 聊天记录
- 查询某同事创建/共享的文档
- 查询与某同事的共同会议
- 复杂的跨系统关联查询
"""
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
import sys
import os

# 导入各系统的数据加载器
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from org_qa_solutions.utils import OrgDataLoader, CURRENT_ORG_ID, CURRENT_USER_ID
from im_qa_solutions.utils import IMDataLoader
from doc_qa_solutions.utils import DocDataLoader
from calendar_qa_solutions.utils import CalendarDataLoader


class CrossSystemLoader:
    """
    跨系统数据加载器

    整合组织、消息、文档、日程四个系统的数据，提供跨系统查询能力。

    示例：
        >>> loader = CrossSystemLoader()
        >>> profile = loader.get_user_profile(10042)
        >>> print(f"姓名: {profile['name']}, 部门: {loader.get_user_dept(10042)['name']}")
        姓名: 籍钧良, 部门: 后端
    """

    def __init__(self):
        """
        初始化跨系统数据加载器

        功能：
            - 创建各系统的数据加载器实例
            - org_loader: 组织系统
            - im_loader: 消息系统
            - doc_loader: 文档系统
            - calendar_loader: 日程系统
        """
        self.org_loader = OrgDataLoader()
        self.im_loader = IMDataLoader()
        self.doc_loader = DocDataLoader()
        self.calendar_loader = CalendarDataLoader()

    # ==================== 用户资料相关方法 ====================

    def get_user_profile(self, user_id: int) -> Optional[pd.Series]:
        """
        获取用户完整资料

        参数：
            user_id: 用户ID

        返回：
            pd.Series: 用户完整信息，包含以下字段：
                - id: 用户ID
                - name: 姓名
                - mobile: 手机号
                - email: 邮箱
                - role: 角色ID
                - gender: 性别ID
                - join_date: 入职时间
                - manager_id: 上级ID
                - org_id: 组织ID
            如果用户不存在则返回 None

        示例：
            >>> profile = cross_loader.get_user_profile(10042)
            >>> profile['name']  # 籍钧良
            >>> profile['mobile']  # 13900000042

        应用场景：
            - 查询同事的完整信息
            - 作为其他查询的基础
        """
        return self.org_loader.get_user_by_id(user_id)

    def get_user_contact_info(self, user_id: int) -> Dict:
        """
        获取用户联系方式

        参数：
            user_id: 用户ID

        返回：
            Dict: 联系方式信息，包含：
                - name: 姓名
                - mobile: 手机号
                - email: 邮箱
                - dept: 部门名称

        示例：
            >>> contact = cross_loader.get_user_contact_info(10042)
            >>> contact['name']  # 籍钧良
            >>> contact['dept']  # 后端
            >>> contact['mobile']  # 13900000042

        应用场景：
            - 快速获取同事的联系信息
            - 查找某人的联系方式
        """
        user = self.org_loader.get_user_by_id(user_id)
        if user is None:
            return {}

        return {
            'name': user['name'],
            'mobile': user['mobile'],
            'email': user['email'],
            'dept': self.org_loader.get_user_dept(user_id)
        }

    # ==================== 用户关系相关方法 ====================

    def get_chat_history_between_users(self, user1_id: int, user2_id: int) -> pd.DataFrame:
        """
        获取两个用户之间的聊天记录

        参数：
            user1_id: 第一个用户ID
            user2_id: 第二个用户ID

        返回：
            pd.DataFrame: 聊天消息列表，包含：
                - from_user_id: 发送者ID
                - content: 消息内容
                - send_time_ms: 发送时间
                等...

        示例：
            >>> messages = cross_loader.get_chat_history_between_users(10042, 10051)
            >>> len(messages)  # 消息总数
            >>> messages.iloc[0]['content']  # 第一条消息内容

        应用场景：
            - 查看与某同事的聊天记录
            - 分析沟通内容
        """
        return self.im_loader.get_messages_between_users(user1_id, user2_id)

    def get_latest_chat_time(self, user1_id: int, user2_id: int) -> Optional[int]:
        """
        获取两个用户最后一次聊天时间

        参数：
            user1_id: 第一个用户ID
            user2_id: 第二个用户ID

        返回：
            Optional[int]: 最后一次聊天的毫秒时间戳
                          如果没有聊天记录则返回 None

        示例：
            >>> timestamp = cross_loader.get_latest_chat_time(10042, 10051)
            >>> if timestamp:
            ...     print(im_loader.timestamp_to_datetime(timestamp))

        应用场景：
            - 查看与某人最后一次联系的时间
            - 判断是否长期未沟通
        """
        messages = self.get_chat_history_between_users(user1_id, user2_id)
        if messages.empty:
            return None
        return messages['send_time_ms'].max()

    def get_shared_docs(self, user1_id: int, user2_id: int) -> List[pd.Series]:
        """
        获取两个用户都可访问的文档

        参数：
            user1_id: 第一个用户ID
            user2_id: 第二个用户ID

        返回：
            List[pd.Series]: 共享可访问的文档列表

        说明：
            - 找出两个用户都能访问的文档
            - 通过计算用户可访问文档集合的交集

        示例：
            >>> docs = cross_loader.get_shared_docs(10042, 10051)
            >>> len(docs)  # 共享文档数量
            >>> docs[0].title  # 第一个共享文档的标题

        应用场景：
            - 查找与某同事共同协作的文档
            - 确认文档的共享情况
        """
        docs1 = set(self.doc_loader.get_user_accessible_docs(user1_id))
        docs2 = set(self.doc_loader.get_user_accessible_docs(user2_id))

        common_ids = docs1 & docs2
        common_docs = []
        for doc_id in common_ids:
            doc = self.doc_loader.get_doc_by_id(doc_id)
            if doc is not None:
                common_docs.append(doc)

        return common_docs

    def get_meetings_between_users(self, user1_id: int, user2_id: int) -> List[pd.Series]:
        """
        获取两个用户的共同会议

        参数：
            user1_id: 第一个用户ID
            user2_id: 第二个用户ID

        返回：
            List[pd.Series]: 共同参与的会议列表

        说明：
            - 找出两个用户都参与的会议
            - 通过比较 event_id 来判断共同会议

        示例：
            >>> meetings = cross_loader.get_meetings_between_users(10042, 10051)
            >>> len(meetings)  # 共同会议数量
            >>> meetings[0].title  # 第一个共同会议的主题

        应用场景：
            - 查看与某同事的共同会议
            - 分析协作关系
        """
        # 获取两个用户的所有会议事件
        events1 = self.calendar_loader.get_user_events(user1_id)
        events2 = self.calendar_loader.get_user_events(user2_id)

        # 找出共同参与的会议
        # 通过比较 event_id 来判断共同会议
        event_ids_1 = {event.event_id for event in events1}
        common_events = []
        for event in events2:
            if event.event_id in event_ids_1:
                common_events.append(event)

        return common_events

    # ==================== 团队相关方法 ====================

    def get_team_members(self, manager_id: int) -> List[pd.Series]:
        """
        获取团队成员（直属下级）

        参数：
            manager_id: 上级用户ID

        返回：
            List[pd.Series]: 直属下级列表

        说明：
            - 只返回直属下级，不包括更下级的员工
            - 通过 manager_id 字段查询

        示例：
            >>> members = cross_loader.get_team_members(10042)
            >>> len(members)  # 团队成员数量
            >>> [m.name for m in members]  # 成员姓名列表

        应用场景：
            - 查看某人的团队成员
            - 获取下属列表
        """
        return self.org_loader.get_subordinates(manager_id, CURRENT_ORG_ID)

    def get_dept_members(self, dept_id: int) -> List[pd.Series]:
        """
        获取部门成员

        参数：
            dept_id: 部门ID

        返回：
            List[pd.Series]: 部门成员列表

        示例：
            >>> members = cross_loader.get_dept_members(4)  # 后端部门
            >>> len(members)  # 部门人数
            >>> [m.name for m in members]  # 成员姓名列表

        应用场景：
            - 查看部门成员
            - 获取部门人员列表
        """
        return self.org_loader.get_dept_users(dept_id)

    # ==================== 消息相关方法 ====================

    def search_user_messages_by_keyword(self, user_id: int, keyword: str) -> List[pd.Series]:
        """
        搜索用户发送的包含关键词的消息

        参数：
            user_id: 用户ID
            keyword: 搜索关键词

        返回：
            List[pd.Series]: 包含关键词的消息列表

        说明：
            - 只搜索用户发送的消息
            - 在消息内容中查找关键词（不区分大小写）

        示例：
            >>> messages = cross_loader.search_user_messages_by_keyword(10042, "算法")
            >>> len(messages)  # 包含"算法"的消息数
            >>> messages[0].content  # 第一条匹配消息的内容

        应用场景：
            - 查找某用户关于特定主题的发言
            - 搜索历史消息中的关键词
        """
        sent = self.im_loader.get_user_sent_messages(user_id)
        matching = sent[sent['content'].str.contains(keyword, na=False, case=False)]
        return list(matching.itertuples())

    def get_recent_messages_from_user(self, from_user_id: int, to_user_id: int, limit: int = 5):
        """
        获取指定用户最近发来的消息

        参数：
            from_user_id: 发送者用户ID
            to_user_id: 接收者用户ID
            limit: 返回消息数量限制，默认5

        返回：
            pd.DataFrame: 最近的消息列表，按时间倒序

        说明：
            - 只获取从 from_user 发给 to_user 的消息
            - 按时间倒序排列，最新的在前

        示例：
            >>> messages = cross_loader.get_recent_messages_from_user(10051, 10042)
            >>> len(messages)  # 消息数量
            >>> messages.iloc[0]['content']  # 最新消息内容

        应用场景：
            - 查看某人最近发来的消息
            - 快速了解最新对话内容
        """
        messages = self.im_loader.get_messages_between_users(from_user_id, to_user_id)

        # 只获取从from_user发来的消息
        from_messages = messages[messages['from_user_id'] == from_user_id]

        return from_messages.sort_values('send_time_ms', ascending=False).head(limit)

    # ==================== 组织架构相关方法 ====================

    def get_user_dept_info(self, user_id: int) -> Dict:
        """
        获取用户部门信息

        参数：
            user_id: 用户ID

        返回：
            Dict: 部门信息，包含：
                - dept_id: 部门ID
                - dept_name: 部门名称
                - dept_level: 部门层级
                - leader: 部门负责人信息（如果有）

        示例：
            >>> dept_info = cross_loader.get_user_dept_info(10042)
            >>> dept_info['dept_name']  # 后端
            >>> dept_info['leader']['name']  # 籍钧良（自己）

        应用场景：
            - 查询同事的部门信息
            - 了解部门结构
        """
        dept = self.org_loader.get_user_dept(user_id)
        if dept is None:
            return {}

        return {
            'dept_id': dept['id'],
            'dept_name': dept['name'],
            'dept_level': dept['level'],
            'leader': self.org_loader.get_user_by_id(int(dept['leader_id'])) if dept['leader_id'] else None
        }

    def get_user_manager_info(self, user_id: int) -> Dict:
        """
        获取用户的上级信息

        参数：
            user_id: 用户ID

        返回：
            Dict: 上级信息，包含：
                - manager_id: 上级ID
                - manager_name: 上级姓名
                - manager_role: 上级角色名称

        示例：
            >>> manager_info = cross_loader.get_user_manager_info(10042)
            >>> manager_info['manager_name']  # 马云（CEO）
            >>> manager_info['manager_role']  # 一级部门leader

        应用场景：
            - 查询某人的上级是谁
            - 了解汇报关系
        """
        user = self.org_loader.get_user_by_id(user_id)
        if user is None or pd.isna(user['manager_id']):
            return {}

        manager = self.org_loader.get_user_by_id(int(user['manager_id']))
        if manager is None:
            return {}

        return {
            'manager_id': manager['id'],
            'manager_name': manager['name'],
            'manager_role': self.org_loader.get_role_name(manager['role'])
        }


# 创建全局实例
# 使用方法：直接调用 cross_loader 的方法
# 示例：profile = cross_loader.get_user_profile(10042)
cross_loader = CrossSystemLoader()
