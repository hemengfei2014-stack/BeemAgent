# 组织架构系统 Schema

## 业务场景描述

企业内部的组织系统（类似飞书、钉钉里面的组织架构），下面是这个系统底层的部分数据表 Schema。

---

## 表结构定义

### 1. 组织表 (bw_organize)

```sql
-- beemchat.bw_organize definition
CREATE TABLE `bw_organize` (
  `id` varchar(64) NOT NULL COMMENT '主键',
  `display_id` varchar(64) DEFAULT NULL COMMENT 'enterprise ID exposed to the tenant',
  `org_name` varchar(256) NOT NULL COMMENT '组织名称',
  `i18n_name` text NOT NULL COMMENT '名称多语言',
  `short_name` varchar(50) DEFAULT NULL COMMENT '组织简称',
  `scale_code` varchar(128) NOT NULL DEFAULT '' COMMENT '人员规模',
  `logo` varchar(1024) DEFAULT NULL COMMENT '组织图标',
  `auth_status` tinyint DEFAULT '0' COMMENT '认证状态：0:未认证；1:已认证',
  `type` tinyint NOT NULL DEFAULT '1' COMMENT '组织类型：1:企业组织；2:个人组织；3:政府部门',
  `industry_type_level_code` varchar(128) NOT NULL DEFAULT '' COMMENT '行业类目层级码',
  `is_need_approve` tinyint NOT NULL DEFAULT '0' COMMENT '是否需要审批0不审批1审批',
  `is_enable_invite` tinyint DEFAULT '1' COMMENT '是否启用邀请：0:不启用；1:启用',
  `invite_expire_days` int DEFAULT '3' COMMENT '组织邀请过期天数：-1为永不过期',
  `allow_user_quit` tinyint DEFAULT '1' COMMENT '允许用户主动退出: 0:不允许, 1:允许',
  `description` varchar(512) DEFAULT NULL COMMENT '组织介绍',
  `owner_id` varchar(64) DEFAULT NULL COMMENT '组织拥有者',
  `count` int DEFAULT '0' COMMENT '人数',
  `status` tinyint DEFAULT '0' COMMENT '组织状态 ：1正常，2解散中，3解散',
  `gid` varchar(64) DEFAULT NULL COMMENT '全员群ID',
  `crt_time` bigint NOT NULL COMMENT '创建时间',
  `crt_id` varchar(64) NOT NULL COMMENT '创建人',
  `upt_time` bigint DEFAULT NULL COMMENT '修改时间',
  `upt_id` varchar(64) DEFAULT NULL COMMENT '修改人',
  `channel` varchar(32) DEFAULT 'ADMIN' COMMENT '创建组织渠道识别码',
  `visibility_version` bigint NOT NULL DEFAULT '0' COMMENT '团队可见性版本号',
  `visibility_config` text DEFAULT NULL COMMENT '团队可见性配置json',
  `custom_config` text DEFAULT NULL COMMENT '自定义配置json',
  `secret` varchar(20) DEFAULT NULL,
  `front_param` text DEFAULT NULL,
  `back_param` text DEFAULT NULL,
  `dissolve_time` bigint DEFAULT '0' COMMENT '解散时间',
  `idaas_cfg` text DEFAULT NULL COMMENT 'idaas集成配置',
  `enable_idaas_sync` tinyint DEFAULT '0' COMMENT 'enable idaas sync: 0:disabled; 1:enable;',
  `team_domain` varchar(128) DEFAULT NULL COMMENT '组织域名',
  `screenshot_protect` tinyint DEFAULT '0' COMMENT '是否开启截屏保护：0:否；1：是',
  `message_protect` tinyint DEFAULT '0' COMMENT '消息防止外漏开关: 0：OFF;1：ON',
  `secret_chat` tinyint NOT NULL DEFAULT '0' COMMENT '密聊开关 0关闭 1是开启',
  `mobile_show_inner` tinyint DEFAULT '1' COMMENT '组织内展示手机号展示开关: 0：OFF；1：ON',
  `mobile_show_external` tinyint DEFAULT '1' COMMENT '组织外手机号展示开关: 0：OFF；1：ON',
  `org_domain_name` varchar(255) DEFAULT NULL COMMENT '组织域名',
  `edit_msg_limit` bigint DEFAULT '86400' COMMENT '开关时长：秒',
  PRIMARY KEY (`id`) /*T![clustered_index] NONCLUSTERED */,
  KEY `idx_name` (`org_name`),
  KEY `idx_owner_id` (`owner_id`),
  KEY `idx_team_domain` (`team_domain`),
  KEY `idx_crt_time` (`crt_time`),
  KEY `index_display_id` (`display_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin COMMENT='组织';
```

### 2. 组织用户信息表 (bw_organize_user)

```sql
-- beemchat.bw_organize_user definition
CREATE TABLE `bw_organize_user` (
  `id` varchar(64) NOT NULL COMMENT '主键',
  `oid` varchar(64) NOT NULL COMMENT '组织id',
  `uid` varchar(64) NOT NULL COMMENT '用户id',
  `member_id` varchar(19) NOT NULL COMMENT '成员id',
  `real_name` varchar(100) DEFAULT NULL COMMENT '名字',
  `role` tinyint NOT NULL DEFAULT '0' COMMENT '身份: 10:normal,20:admin,30:owner',
  `region` varchar(5) DEFAULT NULL COMMENT '国家码',
  `mobile` varchar(128) DEFAULT NULL COMMENT '手机号',
  `phone_hash` char(32) DEFAULT NULL COMMENT '手机号的phoneHash:MD5(region+mobile)',
  `time_zone_id` varchar(64) DEFAULT NULL COMMENT '用户时区ID',
  `avatar_url` varchar(1024) DEFAULT NULL COMMENT '用户头像',
  `avatar_map` text DEFAULT NULL COMMENT 'avatar multi-size mapping',
  `email` varchar(320) DEFAULT NULL COMMENT '邮箱',
  `id_card` varchar(255) DEFAULT NULL,
  `employee_id` varchar(100) DEFAULT NULL COMMENT '工号',
  `shift` tinyint(1) DEFAULT NULL COMMENT '班次, 0早上 1晚上',
  `country` varchar(100) DEFAULT NULL COMMENT '国籍',
  `professional` varchar(100) DEFAULT NULL,
  `sex` tinyint(1) DEFAULT NULL COMMENT '性别',
  `manager` varchar(100) DEFAULT NULL COMMENT '直线上级负责人id',
  `unit` varchar(1000) DEFAULT NULL COMMENT '工作单位',
  `i18n_name` text NOT NULL COMMENT '名称多语言',
  `join_type` tinyint NOT NULL COMMENT '加入方式: 1:后台导入；2:APP邀请；3:组织邀请码申请加入；4:扫二维码申请加入',
  `invite_uid` varchar(64) DEFAULT NULL COMMENT '邀请人',
  `active_status` tinyint DEFAULT NULL COMMENT '激活状态：0激活 1未激活',
  `active_time` bigint NOT NULL COMMENT '激活时间',
  `status` tinyint NOT NULL COMMENT '数据同步状态 1:add;2:update;3:remove;4:quit',
  `crt_time` bigint NOT NULL COMMENT '创建时间',
  `crt_id` varchar(64) NOT NULL COMMENT '创建人',
  `upt_time` bigint NOT NULL COMMENT '修改时间',
  `upt_id` varchar(64) DEFAULT NULL COMMENT '修改人',
  `sync_time` bigint DEFAULT NULL COMMENT '同步时间戳',
  `extra_json` text DEFAULT NULL COMMENT '扩展字段',
  `outer_uid` varchar(1024) DEFAULT NULL COMMENT '外部系统id',
  `idaas_sync_id` varchar(255) NOT NULL DEFAULT '0' COMMENT 'IDAAS同步ID',
  `idaas_active` tinyint DEFAULT '1' COMMENT 'idaas active: 0:inactive; 1:active;',
  `meeting_room_no` varchar(255) DEFAULT NULL COMMENT '会议室code',
  `meeting_room_name` varchar(255) DEFAULT NULL COMMENT '会议名称',
  `user_room_domain` varchar(255) DEFAULT NULL COMMENT '个人会议链接域名',
  `enable_password` tinyint DEFAULT '1' COMMENT '是否开启密码 0 不开启 1 开启',
  `enable_wait` tinyint DEFAULT '1' COMMENT '是否开启等候室 0 不开启，1开启',
  `meeting_password` varchar(255) DEFAULT NULL COMMENT '用户密码',
  `idass_original` json DEFAULT NULL COMMENT 'IDASS 同步的原始数据 JSON',
  PRIMARY KEY (`id`) /*T![clustered_index] NONCLUSTERED */,
  UNIQUE KEY `unique_uid_oid` (`uid`,`oid`),
  KEY `oid_role_idx` (`oid`,`role`),
  KEY `idx_mobile` (`mobile`),
  KEY `idx_meeting_room_no` (`meeting_room_no`),
  KEY `idx_oid_uid_status_active_status_crt_time` (`oid`,`uid`,`status`,`active_status`,`crt_time`),
  KEY `oid_status` (`oid`,`status`),
  KEY `bw_organize_user_oid_idass_id_index` (`oid`,`idaas_sync_id`),
  KEY `idx_oid_phone_hash` (`phone_hash`,`oid`),
  KEY `idx_sync` (`oid`,`sync_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin /*T! SHARD_ROW_ID_BITS=4 */ COMMENT='组织用户';
```

### 3. 部门表 (bw_dept)

```sql
-- beemchat.bw_dept definition
CREATE TABLE `bw_dept` (
  `id` varchar(64) NOT NULL COMMENT 'id',
  `oid` varchar(64) DEFAULT NULL COMMENT 'oid',
  `dept_code` varchar(32) DEFAULT NULL,
  `level_code` varchar(100) DEFAULT '0' COMMENT '部门编号，4位一级 每级从1000开始',
  `dept_name` varchar(500) DEFAULT NULL,
  `i18n_name` text NOT NULL COMMENT '名称多语言',
  `description` varchar(512) DEFAULT NULL COMMENT '描述',
  `user_count` int NOT NULL DEFAULT '0' COMMENT '子部门数量',
  `child_count` int NOT NULL DEFAULT '0' COMMENT '子部门数量',
  `pid` varchar(64) NOT NULL COMMENT '父部门id',
  `dept_type` tinyint NOT NULL COMMENT '类型0组织1普通部门1子公司',
  `dept_sort` int DEFAULT '0' COMMENT '排序',
  `status` tinyint DEFAULT NULL COMMENT '状态 1:add;2:update;3:remove',
  `group_name` varchar(255) DEFAULT NULL,
  `group_status` tinyint DEFAULT NULL COMMENT '部门群状态 0:未建群, 1:需要建群 ，2:已成功建群',
  `gid` varchar(32) DEFAULT '' COMMENT '群组ID',
  `crt_time` bigint DEFAULT NULL COMMENT '创建时间',
  `crt_id` varchar(64) DEFAULT NULL COMMENT '创建人',
  `upt_time` bigint DEFAULT NULL COMMENT '修改时间',
  `upt_id` varchar(64) DEFAULT NULL COMMENT '修改人',
  `outer_id` varchar(1024) DEFAULT NULL COMMENT '外部系统部门id',
  `outer_pid` varchar(1024) DEFAULT NULL COMMENT '外部系统部门pid',
  `sync_id` varchar(255) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT 'IDAAS同步ID',
  `sync_pid` varchar(64) DEFAULT NULL COMMENT '同步父ID',
  PRIMARY KEY (`id`) /*T![clustered_index] NONCLUSTERED */,
  UNIQUE KEY `unique_oid_levelcode` (`oid`,`level_code`),
  KEY `index_oid_pid` (`oid`,`pid`),
  KEY `idx_oid_upt_time` (`oid`,`upt_time`),
  KEY `index_oid_dept_code` (`oid`,`dept_code`),
  KEY `idx_oid_syncId` (`oid`,`sync_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin COMMENT='部门表';
```

### 4. 部门用户表 (bw_dept_user)

```sql
-- beemchat.bw_dept_user definition
CREATE TABLE `bw_dept_user` (
  `id` varchar(64) NOT NULL COMMENT '主键',
  `oid` varchar(64) NOT NULL COMMENT '组织id',
  `dept_id` varchar(64) NOT NULL COMMENT '部门id',
  `uid` varchar(64) NOT NULL COMMENT '用户id',
  `status` tinyint NOT NULL COMMENT '数据同步状态 1:add;2:update;3:remove;',
  `crt_time` bigint NOT NULL COMMENT '创建时间',
  `crt_id` varchar(64) NOT NULL COMMENT '创建人',
  `upt_time` bigint DEFAULT NULL COMMENT '修改时间',
  `upt_id` varchar(64) DEFAULT NULL COMMENT '修改人',
  `sync_time` bigint DEFAULT NULL COMMENT '同步时间戳',
  `sort` int NOT NULL DEFAULT '0' COMMENT '排序字段',
  `main_dept` tinyint(1) DEFAULT '0' COMMENT '主部门  0否 1是',
  PRIMARY KEY (`id`) /*T![clustered_index] NONCLUSTERED */,
  KEY `idx_uid` (`uid`),
  KEY `idx_oid_sync_time` (`oid`,`sync_time`),
  UNIQUE KEY `idx_oid_dept_uid` (`oid`,`dept_id`,`uid`),
  KEY `idx_oid_uid_status` (`oid`,`uid`,`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin /*T! SHARD_ROW_ID_BITS=2 */ COMMENT='部门用户';
```

### 5. 外部联系人表 (bw_outside_contact)

```sql
CREATE TABLE `bw_outside_contact` (
  `id` varchar(64) NOT NULL COMMENT '主键',
  `oid` varchar(64) NOT NULL COMMENT '组织id',
  `uid` varchar(64) NOT NULL DEFAULT '' COMMENT '用户id',
  `invite_uid` varchar(64) DEFAULT NULL COMMENT '邀请人',
  `external_oid` varchar(64) DEFAULT NULL COMMENT '外部联系人机构',
  `external_uid` varchar(64) NOT NULL COMMENT '外部联系人id',
  `status` tinyint DEFAULT NULL COMMENT '状态 0:未添加; 1:申请中;2:已添加;3:对方申请中;4:已删除;5:对方已删除',
  `biz_status` tinyint DEFAULT '0' COMMENT 'final state 0: not added; 2: Added; 4:已删除',
  `type` tinyint NOT NULL COMMENT '类型0个人的1是企业的',
  `source` tinyint NOT NULL COMMENT '来源1是Added via searching for phone number; 2是Added via contact card',
  `crt_time` bigint NOT NULL COMMENT '创建时间',
  `crt_id` varchar(64) NOT NULL COMMENT '创建人',
  `upt_time` bigint DEFAULT NULL COMMENT '修改时间',
  `upt_id` varchar(64) DEFAULT NULL COMMENT '修改人',
  `expire_time` bigint DEFAULT NULL COMMENT '过期时间',
  `apply_reason` varchar(256) DEFAULT NULL COMMENT '申请原因',
  PRIMARY KEY (`id`) /*T![clustered_index] NONCLUSTERED */,
  KEY `idx_external_uid` (`external_uid`),
  KEY `idx_uid_upt_time` (`uid`,`upt_time`),
  KEY `idx_external_oid` (`external_oid`),
  UNIQUE KEY `idx_uid_external_uid` (`uid`,`external_uid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin COMMENT='外部联系人V3';
```
