# 组织架构系统 Schema（精简版）

## 业务场景描述

企业内部的组织系统（类似飞书、钉钉里面的组织架构），下面是这个系统底层的精简后部分数据表 Schema。

---

## 一、整体表结构总览（最终保留 4 张核心表）

| 表名 | 作用 |
| :--- | :--- |
| `org` | 公司 / 组织 |
| `user` | 组织内员工（含扩展信息） |
| `dept` | 部门 / 团队 |
| `dept_user` | 用户 ↔ 部门 关系 |

> ✅ **保留**：组织结构、上下级、部门归属、管理关系

---

## 二、组织表 `org`

```sql
CREATE TABLE org (
  id            BIGINT COMMENT '组织ID（公司ID），主键',

  name          VARCHAR(128) COMMENT '组织名称（公司名）',
  short_name    VARCHAR(64) COMMENT '组织简称',

  owner_user_id BIGINT COMMENT '组织负责人（CEO / 公司Owner）的用户ID',

  created_at    BIGINT COMMENT '组织创建时间（时间戳）'
) COMMENT '组织（公司）表';
```

### 能回答的问题

*   公司叫什么？
*   公司 CEO 是谁？
*   公司是否有效？
*   公司创建时间？

---

## 三、用户表 `user`

```sql
CREATE TABLE user (
  id            BIGINT COMMENT '用户ID（工号），组织内唯一标识，主键',

  org_id        BIGINT COMMENT '所属组织ID',
  
  name          VARCHAR(64) COMMENT '用户姓名（展示名）',

  manager_id    BIGINT COMMENT '直属上级用户ID（领导）',

  role          TINYINT COMMENT '用户角色：1=产品经理，2=开发工程师，3=算法工程师，4=HR, 5=Android工程师, 6=iOS工程师, 7=测试工程师, 8=二级部门leader, 9=一级部门leader',

  -- ===== 基础联系信息 =====
  mobile        VARCHAR(32) COMMENT '手机号',
  email         VARCHAR(128) COMMENT '邮箱',

  -- ===== 人事信息 =====
  join_date     BIGINT COMMENT '入职时间',

  -- ===== 扩展信息 =====
  gender        TINYINT COMMENT '性别：0=未知，1=男，2=女',
  birthday      BIGINT COMMENT '生日时间戳'

) COMMENT '组织用户（员工）表';
```

### 能回答的问题（核心）

*   某某是谁？
*   某某是否在职？
*   某某的领导是谁？
*   某某的邮箱 / 手机号？
*   CEO 的名字？
*   公司有多少人？
*   某个领导下面有多少人？

---

## 四、部门表 `dept`

```sql
CREATE TABLE dept (
  id            BIGINT COMMENT '部门ID，主键',

  org_id        BIGINT COMMENT '所属组织ID',

  name          VARCHAR(128) COMMENT '部门名称',

  parent_id     BIGINT COMMENT '父部门ID（NULL 表示一级部门）',

  leader_id     BIGINT COMMENT '部门负责人用户ID',

  level         INT COMMENT '部门层级（1=一级部门）',

  created_at    BIGINT COMMENT '部门创建时间'

) COMMENT '部门表';
```

### 能回答的问题

*   公司有哪些部门？
*   某部门的上级部门是谁？
*   某部门负责人是谁？
*   部门层级结构是怎样的？
*   组织树 / 部门树？

---

## 五、部门用户关系表 `dept_user`

```sql
CREATE TABLE dept_user (

  org_id        BIGINT COMMENT '组织ID',
  dept_id       BIGINT COMMENT '部门ID',
  user_id       BIGINT COMMENT '用户ID',

  created_at    BIGINT COMMENT '加入部门时间'

) COMMENT '部门-用户关系表（主键：org_id + user_id）';
```

### 能回答的问题

*   某某在哪个部门？
*   某部门有多少人？
*   某部门有哪些成员？
*   跨部门兼职关系
