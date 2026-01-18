# 日历会议系统 Schema（精简版）

## 1. 业务场景
企业内部通用的日历系统（类似飞书、钉钉），核心用于管理个人及团队的日程安排。

---

## 2. 核心数据表

本精简版 Schema 仅包含最核心的日程表：

| 表名 | 作用 |
| :--- | :--- |
| `calendar_event` | 日历日程主表（存储日程时间、主题及参与人） |

---

## 3. 表结构详情

### 日历日程表 `calendar_event`
该表用于定义一个日程的核心要素：**时间范围**、**参与人员**及**基本属性**。

```sql
CREATE TABLE calendar_event (
  event_id      VARCHAR(32)   COMMENT '日程唯一 ID',
  subject       VARCHAR(500)  COMMENT '日程主题',
  start_time    BIGINT        COMMENT '开始时间 (毫秒级时间戳)',
  end_time      BIGINT        COMMENT '结束时间 (毫秒级时间戳)',
  
  organizer_id  VARCHAR(32)   COMMENT '日程发起人 ID',
  participants  VARCHAR(2000) COMMENT '参与人列表 (存储用户 ID，多人之间用英文逗号 "," 分隔)',
  
  PRIMARY KEY (event_id)
) COMMENT '日历日程表';
```
