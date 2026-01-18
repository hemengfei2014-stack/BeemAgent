# 日程系统问题解答总结

## 文件结构
```
calendar_qa_solutions/
├── utils.py              # 日程数据加载和查询工具
├── 001-150.md           # 今天会议、时段安排、空闲时间
└── 151-300.md           # 未来会议、会议详情、搜索
```

## 当前用户上下文
- **"我"** = Jaco组织 + 用户ID **10042**（籍钧良）

## 日程数据结构

### 数据表
**calendar_event.txt** (日程表)
- event_id: 事件ID
- subject: 事件主题
- start_time: 开始时间（毫秒时间戳）
- end_time: 结束时间（毫秒时间戳）
- organizer_id: 组织者用户ID
- participants: 参与者用户ID列表（逗号分隔）

## 当前用户日程数据概况

### 会议统计
- 总参与会议: 6场
- 作为组织者: 1场
- 作为参与者: 5场
- 平均时长: 60分钟

### 会议列表
1. 关于短视频的市场... (2025-12-02)
2. 关于滤镜的世界... (2025-11-27)
3. 关于带货的文章... (2025-11-20)
4. 关于粉丝的你们... (2025-11-18)
5. 关于流量的处理... (2025-11-28)
6. 关于互动的资源... (2025-07-19)

### 与特定人的会议
- 与萧翔（10051）: 4场共同会议

### 时间分布
- 所有会议都是2025年的历史会议
- 今天和未来没有会议安排

## 数据权限说明
- 日历数据组织内公开访问
- 员工可以查看所有人的日程安排

## 依赖
```bash
pip install pandas
```

## 使用方法
```python
from utils import calendar_loader, CURRENT_USER_ID
from datetime import date

# 获取今天的会议
today = date.today()
events = calendar_loader.get_events_by_date(CURRENT_USER_ID, today)

# 获取空闲时段
free_slots = calendar_loader.get_free_time_slots(CURRENT_USER_ID, today)

# 搜索关键词
for event in all_events:
    if "流量" in event.subject:
        print(event.subject)
```
