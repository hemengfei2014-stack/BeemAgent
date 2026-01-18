"""
日程系统数据加载和查询工具
用于回答 calendar_qa.md 中的问题

主要功能：
- 加载用户日程事件数据
- 按日期、时间段查询会议
- 查找空闲时间段
- 获取会议参与者
- 日程统计信息

数据表说明：
- calendar_event.txt: 日程事件表（event_id, org_id, organizer_id, title,
  start_time, end_time, participants, location, notes）
  - event_id: 事件唯一标识
  - organizer_id: 发起人用户ID
  - title: 会议主题
  - start_time: 开始时间（毫秒时间戳）
  - end_time: 结束时间（毫秒时间戳）
  - participants: 参与者ID列表（逗号分隔）

权限说明：
- 日程数据在组织内公开
- 可以查看组织内任何用户的日历（包括会议安排）
- 用于协调会议时间、查看同事空闲状态
"""
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from org_qa_solutions.utils import OrgDataLoader, CURRENT_ORG_ID, CURRENT_USER_ID

# 日程数据路径（相对路径）
CALENDAR_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                                  "fake_beem", "simplified_schema", "synthetic_data", "calendar", "data")


class CalendarDataLoader:
    """
    日程数据加载器

    用于加载和查询日程管理系统数据，包括会议、事件等。

    示例：
        >>> loader = CalendarDataLoader()
        >>> events = loader.get_user_events(10042)
        >>> for event in events:
        ...     print(f"会议: {event.title}, 时间: {event.start_time}")
    """

    def __init__(self, data_dir: str = CALENDAR_DATA_DIR, org_id: int = CURRENT_ORG_ID):
        """
        初始化日程数据加载器

        参数：
            data_dir: 数据目录路径，默认为 CALENDAR_DATA_DIR
            org_id: 组织ID，默认为当前组织（Jaco，ID=1）

        功能：
            加载日程事件表
            解析参与者列表
        """
        self.data_dir = data_dir
        self.org_id = org_id
        self.org_loader = OrgDataLoader()
        self._load_data()

    def _load_data(self):
        """
        加载日程数据表（内部方法）

        加载的数据表：
        - calendar_event.txt: 日程事件表

        处理步骤：
            1. 加载原始数据
            2. 解析参与者列表（从逗号分隔的字符串转为列表）
        """
        # 加载日程表
        self.events_df = pd.read_csv(f"{self.data_dir}/calendar_event.txt", sep='\t')

        # 解析参与者列表
        self._parse_participants()

    def _parse_participants(self):
        """
        解析参与者列表（内部方法）

        生成数据结构：
            self.event_participants = {event_id: [user_id, ...]}

        说明：
            - 从日程表中解析每个事件的参与者
            - participants 字段是逗号分隔的字符串
        """
        self.event_participants = {}  # {event_id: [user_id, ...]}

        for _, row in self.events_df.iterrows():
            event_id = row['event_id']
            participants = str(row['participants']).split(',')
            self.event_participants[event_id] = [int(p) for p in participants if p]

    # ==================== 用户事件查询方法 ====================

    def get_user_events(self, user_id: int) -> List[pd.Series]:
        """
        获取用户参与的所有日程

        参数：
            user_id: 用户ID

        返回：
            List[pd.Series]: 用户参与的日程列表

        包含的日程：
            - 用户作为发起者（organizer_id）的日程
            - 用户作为参与者（在 participants 列表中）的日程

        示例：
            >>> events = calendar_loader.get_user_events(10042)
            >>> len(events)  # 参与的日程总数
            >>> events[0].title  # 第一个日程的主题

        应用场景：
            - 查看某人的所有会议
            - 统计用户的日程数量
        """
        # 用户作为组织者或参与者
        organized = self.events_df[self.events_df['organizer_id'] == user_id]

        participated_ids = []
        for event_id, participants in self.event_participants.items():
            if user_id in participants:
                participated_ids.append(event_id)

        participated = self.events_df[self.events_df['event_id'].isin(participated_ids)]

        # 合并并去重
        all_events = pd.concat([organized, participated]).drop_duplicates(subset=['event_id'])
        return list(all_events.itertuples())

    # ==================== 按日期查询方法 ====================

    def get_events_by_date(self, user_id: int, date: datetime.date) -> List[pd.Series]:
        """
        获取指定日期的日程

        参数：
            user_id: 用户ID
            date: 日期（datetime.date 对象）

        返回：
            List[pd.Series]: 指定日期的日程列表

        说明：
            - 匹配 start_time 在指定日期内的所有日程
            - 日期范围：从 date 00:00:00 到 date 23:59:59

        示例：
            >>> from datetime import date
            >>> events = calendar_loader.get_events_by_date(10042, date(2026, 1, 15))
            >>> len(events)  # 该日期的日程数量

        应用场景：
            - 查看"今天有哪些会议"
            - 查看特定日期的安排
        """
        events = self.get_user_events(user_id)

        start_ts = int(datetime.combine(date, datetime.min.time()).timestamp() * 1000)
        end_ts = int((datetime.combine(date, datetime.max.time()) + timedelta(days=1)).timestamp() * 1000)

        date_events = [e for e in events if e.start_time >= start_ts and e.start_time < end_ts]
        return date_events

    def get_events_by_date_range(self, user_id: int, start_date: datetime.date, end_date: datetime.date) -> List[pd.Series]:
        """
        获取日期范围内的日程

        参数：
            user_id: 用户ID
            start_date: 开始日期
            end_date: 结束日期

        返回：
            List[pd.Series]: 日期范围内的日程列表

        说明：
            - 包含从 start_date 00:00:00 到 end_date 23:59:59 的所有日程
            - 适用于查询"本周"、"下周"等时间范围的会议

        示例：
            >>> from datetime import date
            >>> events = calendar_loader.get_events_by_date_range(
            ...     10042,
            ...     date(2026, 1, 15),
            ...     date(2026, 1, 21)
            ... )
            >>> len(events)  # 该时间范围内的日程数量

        应用场景：
            - 查看本周会议
            - 查看下周安排
        """
        events = self.get_user_events(user_id)

        start_ts = int(datetime.combine(start_date, datetime.min.time()).timestamp() * 1000)
        end_ts = int((datetime.combine(end_date, datetime.max.time()) + timedelta(days=1)).timestamp() * 1000)

        range_events = [e for e in events if e.start_time >= start_ts and e.start_time < end_ts]
        return range_events

    # ==================== 按时段查询方法 ====================

    def get_events_by_period(self, user_id: int, date: datetime.date, period: str) -> List[pd.Series]:
        """
        获取指定日期的特定时段日程

        参数：
            user_id: 用户ID
            date: 日期
            period: 时段，可选值：
                - '上午': 6:00-12:00
                - '下午': 12:00-18:00
                - '晚上': 18:00-24:00

        返回：
            List[pd.Series]: 指定时段的日程列表

        示例：
            >>> from datetime import date
            >>> events = calendar_loader.get_events_by_period(10042, date(2026, 1, 15), '上午')
            >>> len(events)  # 上午的会议数量

            >>> # 查看下午的会议
            >>> events = calendar_loader.get_events_by_period(10042, date(2026, 1, 15), '下午')

        应用场景：
            - 查看"上午有哪些会议"
            - 查看特定时段的安排
        """
        events = self.get_events_by_date(user_id, date)

        hour_ranges = {
            '上午': (6, 12),
            '下午': (12, 18),
            '晚上': (18, 24)
        }

        if period not in hour_ranges:
            return events

        start_hour, end_hour = hour_ranges[period]

        period_events = []
        for event in events:
            dt = datetime.fromtimestamp(event.start_time / 1000)
            if start_hour <= dt.hour < end_hour:
                period_events.append(event)

        return period_events

    # ==================== 空闲时间方法 ====================

    def get_free_time_slots(self, user_id: int, date: datetime.date) -> List[Dict]:
        """
        获取指定日期的空闲时段

        参数：
            user_id: 用户ID
            date: 日期

        返回：
            List[Dict]: 空闲时段列表，每个元素包含：
                - start: 空闲开始时间（毫秒时间戳）
                - end: 空闲结束时间（毫秒时间戳）
                - duration: 空闲时长（毫秒）

        工作时间：
            - 假设工作时间为 9:00 - 18:00
            - 在此时间范围内的会议之间计算空闲时间

        示例：
            >>> from datetime import date
            >>> slots = calendar_loader.get_free_time_slots(10042, date(2026, 1, 15))
            >>> len(slots)  # 空闲时段数量
            >>> slots[0]['duration'] / 3600000  # 第一个空闲时段的小时数

        应用场景：
            - 找到适合安排新会议的时间
            - 查看某天的空闲时间
        """
        events = self.get_events_by_date(user_id, date)

        # 按开始时间排序
        events.sort(key=lambda x: x.start_time)

        free_slots = []

        # 一天的开始和结束
        day_start = int(datetime.combine(date, datetime.min.time()).timestamp() * 1000)
        day_end = int(datetime.combine(date, datetime.max.time()).timestamp() * 1000)

        # 假设工作时间为 9:00 - 18:00
        work_start = day_start + 9 * 3600 * 1000
        work_end = day_start + 18 * 3600 * 1000

        current_time = work_start

        for event in events:
            if event.start_time > current_time:
                free_slots.append({
                    'start': current_time,
                    'end': event.start_time,
                    'duration': event.start_time - current_time
                })
            current_time = max(current_time, event.end_time)

        if current_time < work_end:
            free_slots.append({
                'start': current_time,
                'end': work_end,
                'duration': work_end - current_time
            })

        return free_slots

    # ==================== 参与者方法 ====================

    def get_event_participants(self, event_id: str) -> List[int]:
        """
        获取日程的参与者

        参数：
            event_id: 日程事件ID

        返回：
            List[int]: 参与者用户ID列表

        示例：
            >>> participants = calendar_loader.get_event_participants("evt_001")
            >>> len(participants)  # 参与者数量
            >>> participants[0]  # 第一个参与者ID

        应用场景：
            - 查看会议有哪些人参加
            - 确认参会人员
        """
        return self.event_participants.get(event_id, [])

    # ==================== 辅助方法 ====================

    def timestamp_to_datetime(self, timestamp_ms: int) -> str:
        """
        毫秒时间戳转日期时间字符串

        参数：
            timestamp_ms: 毫秒时间戳

        返回：
            str: 格式化的日期时间 (YYYY-MM-DD HH:MM:SS)

        示例：
            >>> calendar_loader.timestamp_to_datetime(1736899200000)
            '2026-01-15 00:00:00'
        """
        return datetime.fromtimestamp(timestamp_ms / 1000).strftime('%Y-%m-%d %H:%M:%S')

    def timestamp_to_time(self, timestamp_ms: int) -> str:
        """
        毫秒时间戳转时间字符串

        参数：
            timestamp_ms: 毫秒时间戳

        返回：
            str: 格式化的时间 (HH:MM)

        示例：
            >>> calendar_loader.timestamp_to_time(1736899200000)
            '00:00'
        """
        return datetime.fromtimestamp(timestamp_ms / 1000).strftime('%H:%M')

    def get_user_name(self, user_id: int) -> str:
        """
        获取用户姓名

        参数：
            user_id: 用户ID

        返回：
            str: 用户姓名，如果用户不存在则返回 "用户{user_id}"

        示例：
            >>> calendar_loader.get_user_name(10042)
            '籍钧良'
            >>> calendar_loader.get_user_name(99999)
            '用户99999'

        说明：
            - 通过 OrgDataLoader 查询用户信息
        """
        user = self.org_loader.get_user_by_id(user_id)
        if user is not None:
            return user['name']
        return f"用户{user_id}"

    # ==================== 统计方法 ====================

    def get_event_stats(self, user_id: int, date: datetime.date) -> Dict:
        """
        获取指定日期的日程统计

        参数：
            user_id: 用户ID
            date: 日期

        返回：
            Dict: 日程统计信息，包含：
                - total: 日程总数
                - morning: 上午日程数
                - afternoon: 下午日程数
                - evening: 晚上日程数
                - first_start: 第一场会议开始时间
                - last_end: 最后一场会议结束时间

        示例：
            >>> from datetime import date
            >>> stats = calendar_loader.get_event_stats(10042, date(2026, 1, 15))
            >>> stats['total']  # 总会议数
            >>> stats['morning']  # 上午会议数

        应用场景：
            - 查看某天的会议概况
            - 统计会议分布
        """
        events = self.get_events_by_date(user_id, date)

        # 按时段统计
        morning = self.get_events_by_period(user_id, date, '上午')
        afternoon = self.get_events_by_period(user_id, date, '下午')
        evening = self.get_events_by_period(user_id, date, '晚上')

        return {
            'total': len(events),
            'morning': len(morning),
            'afternoon': len(afternoon),
            'evening': len(evening),
            'first_start': min([e.start_time for e in events]) if events else None,
            'last_end': max([e.end_time for e in events]) if events else None
        }


# 创建全局实例
# 使用方法：直接调用 calendar_loader 的方法
# 示例：events = calendar_loader.get_user_events(10042)
calendar_loader = CalendarDataLoader()
