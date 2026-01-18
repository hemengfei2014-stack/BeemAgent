# 日历会议系统 Schema

## 业务场景描述

企业内部的日历系统（类似飞书、钉钉里面的日历系统），下面是这个系统底层日历和会议的部分数据表 Schema。

---

## 表结构定义

### 1. 日历表 (calendar)

```sql
CREATE TABLE `calendar` (
  `id` bigint NOT NULL /*T![auto_rand] AUTO_RANDOM(5) */ COMMENT '主键',
  `cal_id` varchar(32) NOT NULL COMMENT '日历id',
  `oid` int NOT NULL COMMENT '日历组织',
  `ocode` varchar(64) DEFAULT NULL COMMENT '邀请人组织code',
  `user_id` varchar(64) NOT NULL COMMENT '用户id',
  `subject` varchar(200) DEFAULT NULL COMMENT '日历标题',
  `description` varchar(500) DEFAULT NULL COMMENT '日历描述',
  `location` varchar(255) DEFAULT NULL COMMENT '位置',
  `default_cal` tinyint DEFAULT NULL COMMENT '1 - 默认日历',
  `status` tinyint NOT NULL COMMENT '1:add;2:upt:3:del',
  `pub_status` tinyint NOT NULL COMMENT '订阅权限 1 - 隐私 2 - 占用壳间 3 - 详情可见',
  `crt_time` bigint NOT NULL COMMENT '创建时间',
  `upt_time` bigint NOT NULL COMMENT '修改时间',
  `pub_view` smallint NOT NULL DEFAULT '1' COMMENT '发布详情 0 - 详情 1 - 摘要 ',
  `work_day_begin` smallint NOT NULL DEFAULT '1' COMMENT '工作日开始于  0 - sunday and so on',
  `notice_code` bigint NOT NULL DEFAULT '8' COMMENT '默认提醒',
  `sync_external` varchar(5000) DEFAULT NULL COMMENT '外部日历同步json',
  `work_time` varchar(128) DEFAULT NULL COMMENT '工作时间',
  `def_duration` bigint DEFAULT '1800000' COMMENT '默认日程持续时间单位：毫秒',
  `notice_code_day` bigint DEFAULT '1024' COMMENT '提醒全天',
  `cal_type` tinyint DEFAULT '0' COMMENT '0- beem ,1-outlook,2-google',
  `source_id` varchar(256) DEFAULT '' COMMENT '来源 id',
  `biz_name` varchar(256) DEFAULT '' COMMENT '来源name',
  `group_id` varchar(64) DEFAULT '' COMMENT '群id',
  `master_event _id` varchar(32) DEFAULT '-1' COMMENT '主事件 ID 默认-1只有特例才有',
  PRIMARY KEY (`id`) /*T![clustered_index] CLUSTERED */,
  UNIQUE KEY `cal_id` (`cal_id`),
  KEY `idx_uid` (`user_id`),
  KEY `idx_calId_status_calType` (`cal_id`,`status`,`cal_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin /*T![auto_rand_base] AUTO_RANDOM_BASE=1770001 */;
```

### 2. 用户日程表 (user_cal_schedule)

```sql
CREATE TABLE `user_cal_schedule` (
  `id` bigint NOT NULL /*T![auto_rand] AUTO_RANDOM(5) */ COMMENT '主键',
  `oid` int NOT NULL COMMENT '组织id',
  `ocode` varchar(64) DEFAULT NULL COMMENT '组织code',
  `event_id` varchar(32) NOT NULL COMMENT '日程id',
  `subject` varchar(500) DEFAULT NULL COMMENT '日程主题',
  `description` varchar(5000) DEFAULT NULL COMMENT '日程描述',
  `location` varchar(255) DEFAULT NULL COMMENT '日程位置',
  `period_start_time` bigint NOT NULL COMMENT '周期开始时间',
  `period_end_time` bigint NOT NULL COMMENT '周期结束时间',
  `start_time` bigint NOT NULL COMMENT '首次开始时间',
  `end_time` bigint NOT NULL COMMENT '首次结束时间',
  `period_type` tinyint NOT NULL COMMENT '周期类型',
  `period` int NOT NULL COMMENT '周期',
  `reminder_id` varchar(255) DEFAULT NULL COMMENT '提醒列表',
  `parent` varchar(64) DEFAULT NULL COMMENT '父日程',
  `parent_oid` int NOT NULL DEFAULT '0' COMMENT '父日程组织',
  `parent_ocode` varchar(64) DEFAULT NULL COMMENT '父组织code',
  `parent_user_id` varchar(64) DEFAULT NULL COMMENT '父日程所属用户',
  `repeat_time` int DEFAULT NULL COMMENT '重复次数',
  `cal_id` varchar(64) DEFAULT NULL COMMENT '所属日历 ',
  `user_id` varchar(64) DEFAULT NULL COMMENT '用户id',
  `meeting_id` varchar(64) DEFAULT NULL COMMENT '会议id',
  `pr_flag` tinyint DEFAULT '0' COMMENT '是否是个人会议：0不是 1 是',
  `meeting_room_no` varchar(32) DEFAULT '' COMMENT '个人会议 No',
  `all_day` tinyint NOT NULL DEFAULT '0' COMMENT '全天事件标识',
  `guest` int NOT NULL DEFAULT '0' COMMENT '邀请人员，0-否 1-是',
  `guest_group` int NOT NULL DEFAULT '0' COMMENT '是否邀请群组，0-否 1-是',
  `external_schedule` int NOT NULL DEFAULT '0' COMMENT '是否外部日程(0、否；1、是)',
  `meeting_number` varchar(64) DEFAULT NULL COMMENT '会议id',
  `status` tinyint NOT NULL COMMENT '1:有效;2:拒绝;3:删除; ',
  `reminder_ver` int NOT NULL DEFAULT '0' COMMENT '提醒和时间版本号',
  `crt_time` bigint NOT NULL,
  `upt_time` bigint NOT NULL,
  `upt_user` varchar(64) NOT NULL,
  `files` varchar(5000) DEFAULT NULL COMMENT '日程附件',
  `period_extra` varchar(5000) DEFAULT NULL COMMENT '扩展规则信息',
  `timezone_offset` bigint NOT NULL DEFAULT '0' COMMENT '扩展规则信息',
  `source_id` varchar(256) DEFAULT '' COMMENT '来源 id',
  `source_type` tinyint DEFAULT '0',
  `event_type` tinyint DEFAULT '0' COMMENT '0 signle 1:重复日程，2特例衍生',
  `special_source_type` int DEFAULT NULL COMMENT '特例生成来源',
  `group_id` varchar(64) DEFAULT '' COMMENT '群id',
  `group_biz_id` varchar(64) DEFAULT NULL COMMENT 'group_biz_id',
  `group_oid` varchar(64) DEFAULT NULL COMMENT '群组织id',
  `group_type` int DEFAULT NULL COMMENT '群组类型，0-内部群 1-外部群',
  `master_event_id` varchar(32) DEFAULT '-1' COMMENT '主事件 ID 默认-1只有特例才有',
  `trusted_org_id` json DEFAULT NULL COMMENT '关联组织',
  `accept_status` tinyint(1) NOT NULL DEFAULT '2' COMMENT '接受状态 1 - 未处理 2 - 接受 3 - 待决 4 - 拒绝 5 - 撤销',
  `join_ticket` varchar(32) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '会议密码',
  `invited_meeting` tinyint NOT NULL DEFAULT '1' COMMENT 'conference reservation 1 yes 0 no',
  PRIMARY KEY (`id`) /*T![clustered_index] CLUSTERED */,
  KEY `idx_ucs_eid` (`event_id`),
  KEY `idx_ucs_pid` (`parent`),
  KEY `idx_ucs_cid_ptbe` (`cal_id`,`period_start_time`,`period_end_time`),
  KEY `idx_eventId_status_calId` (`event_id`,`status`,`cal_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin /*T![auto_rand_base] AUTO_RANDOM_BASE=30001 */;
```

### 3. 日程邀请表 (cal_invite)

```sql
CREATE TABLE `cal_invite` (
  `id` bigint NOT NULL /*T![auto_rand] AUTO_RANDOM(5) */ COMMENT '主键',
  `invite_id` char(32) NOT NULL COMMENT '邀请id',
  `oid` varchar(64) NOT NULL COMMENT '邀请人组织',
  `event_id` varchar(32) NOT NULL COMMENT '事件id',
  `calendar_id` varchar(32) NOT NULL COMMENT '日历id',
  `from_user_id` varchar(64) NOT NULL COMMENT '邀请人id',
  `to_user_id` varchar(64) NOT NULL COMMENT '被邀请人id',
  `to_user_oid` varchar(64) NOT NULL COMMENT '被邀请人组织',
  `invite_type` tinyint NOT NULL DEFAULT '0' COMMENT '邀请类型0-单独邀请 1-群组邀请',
  `invite_group_id` varchar(64) DEFAULT NULL COMMENT '邀请人所属群组id',
  `last_notify_time` bigint NOT NULL DEFAULT '0' COMMENT '上次提醒时间',
  `status` tinyint NOT NULL COMMENT '接收状态 1 - 未处理 2 - 接受 3 - 待决 4 - 拒绝 5 - 撤销',
  `co_host_state` tinyint NOT NULL DEFAULT '0' COMMENT '联席主持人状态(0、否；1、是)',
  `participate_status` tinyint NOT NULL DEFAULT '0' COMMENT '可参选状态 0-必参与 1-可参选 默认为0必参与',
  `access` tinyint NOT NULL COMMENT '权限 1 - 可见 2 - 可编辑 3 - 可邀请 4 - 所有权限',
  `child_schedule` varchar(32) DEFAULT NULL COMMENT '子事件/日程id',
  `crt_time` bigint NOT NULL COMMENT '创建时间',
  `upt_time` bigint NOT NULL COMMENT '更新时间',
  `email_address` varchar(255) DEFAULT '' COMMENT '来源第三方邮箱',
  PRIMARY KEY (`id`) /*T![clustered_index] CLUSTERED */,
  KEY `to_uid_eid_idx` (`to_user_id`,`event_id`),
  KEY `eventId_idx` (`event_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin /*T![auto_rand_base] AUTO_RANDOM_BASE=90001 */;
```

### 4. 历史会议记录信息表 (rtc_meeting_history_user_info)

```sql
CREATE TABLE `rtc_meeting_history_user_info` (
  `seq_id` bigint unsigned NOT NULL COMMENT '会议用户历史序号id',
  `app_id` bigint NOT NULL DEFAULT '0' COMMENT '应用Id',
  `user_id` varchar(30) CHARACTER SET utf8 COLLATE utf8_general_ci NOT NULL COMMENT '用户id',
  `user_id_hash` int NOT NULL DEFAULT '0' COMMENT '用户ID的hash值',
  `instance_type` tinyint NOT NULL DEFAULT '0' COMMENT '用户的终端设备类型：\r\n0：未知；1：WIN;2：Mac;3：Android;4：iOS;5：Web;6：iPad;7：Android Pad;8：小程序',
  `device_id` varchar(128) CHARACTER SET utf8 COLLATE utf8_general_ci DEFAULT NULL COMMENT '设备id',
  `meeting_life_id` bigint NOT NULL DEFAULT '0' COMMENT '会议实例id',
  `meeting_id` varchar(32) COLLATE utf8mb4_general_ci NOT NULL DEFAULT '0' COMMENT '会议id',
  `pr_flag` tinyint DEFAULT '0' COMMENT '是否是个人会议：0不是 1 是',
  `meeting_room_no` varchar(32) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '个人会议 No',
  `meeting_code` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '会议号',
  `meeting_subject` varchar(300) COLLATE utf8mb4_general_ci NOT NULL COMMENT '会议标题',
  `meeting_type` tinyint NOT NULL DEFAULT '0' COMMENT '会议类型(0：快速会议;1：固定预约会议；2：周期预约会议)',
  `org_id` varchar(32) COLLATE utf8mb4_bin DEFAULT NULL COMMENT '组织机构ID',
  `event_id` varchar(32) COLLATE utf8mb4_bin DEFAULT NULL COMMENT '日程id',
  `crt_user_id` varchar(30) COLLATE utf8mb4_bin NOT NULL COMMENT '创建用户Id',
  `host_ids` varchar(256) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '联席主持人拼接串',
  `sys_state` int NOT NULL DEFAULT '0' COMMENT '用户系统状态',
  `meeting_crt_time` bigint NOT NULL COMMENT 'meeting创建时间(当前时间到1970-1-1 00:00:00的总毫秒数)',
  `meeting_order_start_time` bigint DEFAULT NULL COMMENT 'meeting预定开始通话时间(当前时间到1970-1-1 00:00:00的总毫秒数',
  `meeting_order_end_time` bigint DEFAULT NULL COMMENT 'meeting预定结束通话时间(当前时间到1970-1-1 00:00:00的总毫秒数',
  `meeting_start_time` bigint NOT NULL COMMENT 'meeting开始通话时间(当前时间到1970-1-1 00:00:00的总毫秒数',
  `meeting_end_time` bigint NOT NULL COMMENT 'meeting结束时间(当前时间到1970-1-1 0:00:00的总毫秒数',
  `meeting_duration` bigint NOT NULL DEFAULT '0' COMMENT '会议时长(总毫秒数)',
  `first_join_meeting_time` bigint NOT NULL COMMENT '首次入会时间(当前时间到1970-1-1 00:00:00的总毫秒数)',
  `last_exit_meeting_time` bigint NOT NULL COMMENT '最后退会时间(当前时间到1970-1-1 00:00:00的总毫秒数)',
  `del_tag` tinyint NOT NULL DEFAULT '0' COMMENT '删除标记(0：不是；1：是)',
  `event_del` tinyint NOT NULL DEFAULT '0' COMMENT '日程是否删除(0：不是；1：是)',
  `meeting_ver` tinyint NOT NULL DEFAULT '2' COMMENT '会议版本(老meeting:1；新meeting:2)',
  `sync_time` bigint NOT NULL COMMENT '同步时间戳(当前时间到1970-1-1 00:00:00的总微秒数)',
  `schedule_model` tinyint NOT NULL DEFAULT '0' COMMENT '预约模型(0：非预约；1:beem；2:outllok)',
  `meeting_avg_duration` bigint NOT NULL DEFAULT '0' COMMENT '用户参会平均时长(毫秒数)',
  `instance_id` varchar(64) COLLATE utf8mb4_general_ci DEFAULT '' COMMENT '日程事件实例 Id',
  `external` tinyint NOT NULL DEFAULT '0' COMMENT '是否是外部会议：0-否 1-是',
  PRIMARY KEY (`seq_id`) /*T![clustered_index] CLUSTERED */,
  KEY `ix_meeting_history_user_sync_time` (`sync_time`),
  KEY `ix_meeting_history_user_info` (`user_id`,`sync_time`),
  KEY `ix_meeting_life_id` (`meeting_life_id`),
  KEY `idx_meeting_id_time` (`meeting_id`,`meeting_start_time`),
  KEY `idx_meeting_room` (`meeting_room_no`),
  KEY `idx_meeting_time` (`meeting_start_time`,`meeting_end_time`),
  KEY `idex_meeting_code` (`meeting_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='历史会议记录信息表';
```

### 5. 会议信息表 (rtc_meeting_info)

```sql
CREATE TABLE `rtc_meeting_info` (
  `meeting_id` varchar(32) COLLATE utf8mb4_general_ci NOT NULL DEFAULT '0' COMMENT '会议id',
  `pr_flag` tinyint DEFAULT '0' COMMENT '是否是个人会议：0不是 1 是',
  `meeting_room_no` varchar(32) COLLATE utf8mb4_general_ci DEFAULT '' COMMENT '个人会议 No',
  `meeting_code` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '会议号码',
  `app_id` bigint NOT NULL DEFAULT '0' COMMENT '应用Id',
  `meeting_subject` varchar(300) COLLATE utf8mb4_general_ci NOT NULL COMMENT '会议标题',
  `meeting_type` tinyint NOT NULL DEFAULT '0' COMMENT '会议类型(0：快速会议;1：周期性会议)',
  `meeting_password` varchar(32) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '会议密码',
  `public_password` varchar(32) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '公开密码',
  `host_ids_join` varchar(225) COLLATE utf8mb4_general_ci NOT NULL COMMENT '主持人id拼接串',
  `org_id` char(31) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '组织机构Id',
  `event_id` varchar(32) COLLATE utf8mb4_bin DEFAULT NULL COMMENT '日程id',
  `members_limit` int NOT NULL DEFAULT '0' COMMENT '成员最多人数',
  `enable_password` tinyint NOT NULL DEFAULT '0' COMMENT '是否开启密码认证(0：不开启;1：开启)',
  `enable_waiting` tinyint NOT NULL COMMENT '是否开启等候室(0：不开启;1：开启)',
  `enable_live` tinyint NOT NULL DEFAULT '0' COMMENT '是否开启直播(0：不开启;1：开启)',
  `enable_doc_upload` tinyint NOT NULL DEFAULT '1' COMMENT '是否允许成员上传文档(0：不允许;1：允许)',
  `mute_enable_join` tinyint NOT NULL COMMENT '加入会议时是否静音(0：否;1：是)',
  `close_camera_enable_join` tinyint NOT NULL DEFAULT '0' COMMENT '加入会议时是关闭摄像头(0：否;1：是)',
  `meeting_state` int NOT NULL DEFAULT '0' COMMENT '会议状态',
  `crt_user_id` char(22) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '创建用户Id',
  `crt_user_name` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '创建用户名称',
  `order_start_time` bigint DEFAULT NULL COMMENT 'meeting预定开始通话时间(当前时间到1970-1-1 00:00:00的总毫秒数',
  `order_end_time` bigint DEFAULT NULL COMMENT 'meeting预定结束通话时间(当前时间到1970-1-1 00:00:00的总毫秒数',
  `start_time` bigint DEFAULT NULL COMMENT '会议开始时间戳(当前时间到1970-1-1 00:00:00的总毫秒数',
  `end_time` bigint DEFAULT NULL COMMENT '会议结束时间戳(当前时间到1970-1-1 0:00:00的总毫秒数',
  `crt_time` bigint NOT NULL COMMENT '创建时间(当前时间到1970-1-1 00:00:00的总毫秒数)',
  `sync_time` bigint NOT NULL COMMENT '更新时间(当前时间到1970-1-1 00:00:00的总毫秒数)',
  `meeting_ver` tinyint NOT NULL DEFAULT '2' COMMENT '会议版本(老meeting:1；新meeting:2)',
  `external` tinyint NOT NULL DEFAULT '0' COMMENT '是否是外部会议：0-否 1-是',
  PRIMARY KEY (`meeting_id`) /*T![clustered_index] NONCLUSTERED */,
  KEY `ix_meeting_info_state` (`meeting_state`),
  KEY `ix_meeting_info_code` (`meeting_code`,`app_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='会议信息表';
```

### 6. 会议历史共享文件表 (rtc_meeting_history_share_file)

```sql
CREATE TABLE `rtc_meeting_history_share_file` (
  `seq_id` bigint unsigned NOT NULL DEFAULT '0' COMMENT '序号id',
  `meeting_id` varchar(32) COLLATE utf8mb4_general_ci NOT NULL DEFAULT '0' COMMENT '会议id',
  `meeting_life_id` bigint NOT NULL DEFAULT '0' COMMENT '会议实例id',
  `share_user_id` varchar(30) CHARACTER SET utf8 COLLATE utf8_general_ci NOT NULL COMMENT '用户id',
  `orig_file_name` varchar(256) CHARACTER SET utf8 COLLATE utf8_general_ci NOT NULL COMMENT '原始文件名',
  `file_url` varchar(1024) COLLATE utf8mb4_general_ci NOT NULL COMMENT '文件url',
  `sync_time` bigint NOT NULL COMMENT '同步时间戳(当前时间到1970-1-1 00:00:00的总微秒数)',
  `content_type` varchar(50) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '内容类型',
  PRIMARY KEY (`seq_id`) /*T![clustered_index] CLUSTERED */,
  KEY `ix_meeting_life_id` (`meeting_life_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin COMMENT='会议历史共享文件表';
```

### 7. 会议历史成员表 (rtc_meeting_history_member)

```sql
CREATE TABLE `rtc_meeting_history_member` (
  `seq_id` bigint unsigned NOT NULL DEFAULT '0' COMMENT '序号id',
  `app_id` bigint NOT NULL DEFAULT '0' COMMENT '应用Id',
  `meeting_id` varchar(32) COLLATE utf8mb4_general_ci NOT NULL DEFAULT '0' COMMENT '会议id',
  `meeting_life_id` bigint NOT NULL DEFAULT '0' COMMENT '会议实例id',
  `user_id` varchar(30) CHARACTER SET utf8 COLLATE utf8_general_ci NOT NULL COMMENT '用户id',
  `user_nick_name` varchar(100) COLLATE utf8mb4_general_ci NOT NULL COMMENT '用户昵称',
  `user_type` int NOT NULL DEFAULT '0' COMMENT '用户类型(0、正式用户；1、匿名用户)',
  `user_pic` varchar(1024) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT 'avatar_url',
  `sync_time` bigint NOT NULL COMMENT '同步时间戳(当前时间到1970-1-1 00:00:00的总微秒数)',
  `once_speaker_state` int NOT NULL DEFAULT '0' COMMENT '曾经是否主讲人(0：不是；1：是)',
  `join_meeting_time` bigint NOT NULL DEFAULT '0' COMMENT '同步时间戳(当前时间到1970-1-1 00:00:00的总毫秒数)',
  `org_id` varchar(32) COLLATE utf8mb4_bin DEFAULT NULL COMMENT '组织机构ID',
  PRIMARY KEY (`seq_id`) /*T![clustered_index] CLUSTERED */,
  KEY `ix_meeting_life_id` (`meeting_life_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='会议历史成员表';
```
