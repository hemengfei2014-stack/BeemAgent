"""
组织系统数据加载和查询工具
用于回答 org_qa.md 中的问题

主要功能：
- 加载组织、用户、部门数据
- 提供员工信息查询（按ID、姓名、手机号、邮箱）
- 提供部门信息查询（按ID、名称）
- 提供组织架构查询（上下级、子部门、兄弟部门）
- 提供角色和性别查询

数据表说明：
- org.txt: 组织表（id, name）
- user.txt: 用户表（id, name, mobile, email, role, gender, join_date, manager_id, org_id）
- dept.txt: 部门表（id, name, level, leader_id, parent_id, org_id）
- dept_user.txt: 部门-用户关联表（dept_id, user_id）
"""
import pandas as pd
import os
from datetime import datetime
from typing import Optional, List, Dict, Any

# 数据路径（相对路径）
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                         "fake_beem", "simplified_schema", "synthetic_data", "org_system", "data")

# 当前用户上下文
# "我" = 籍钧良，Jaco组织的后端部门leader
CURRENT_ORG_ID = 1  # Jaco
CURRENT_USER_ID = 10042  # 籍钧良

# 角色映射表
# role_id -> 角色名称
ROLE_MAP = {
    1: "产品经理",
    2: "开发工程师",
    3: "算法工程师",
    4: "HR",
    5: "Android工程师",
    6: "iOS工程师",
    7: "测试工程师",
    8: "二级部门leader",
    9: "一级部门leader"
}

# 性别映射表
# gender_id -> 性别名称
GENDER_MAP = {
    0: "未知",
    1: "男",
    2: "女"
}


class OrgDataLoader:
    """
    组织数据加载器

    用于加载和查询组织架构系统数据，包括用户、部门、组织等信息。

    示例：
        >>> loader = OrgDataLoader()
        >>> user = loader.get_user_by_id(10042)
        >>> print(user['name'])  # 输出: 籍钧良

        >>> dept = loader.get_dept_by_name("后端")
        >>> print(dept[0].name)  # 输出: 后端
    """

    def __init__(self, data_dir: str = DATA_DIR):
        """
        初始化组织数据加载器

        参数：
            data_dir: 数据目录路径，默认为 DATA_DIR

        功能：
            加载组织、用户、部门、部门用户关联四张数据表
        """
        self.data_dir = data_dir
        self._load_data()

    def _load_data(self):
        """
        加载所有数据表（内部方法）

        加载的数据表：
        - org.txt: 组织表
        - dept.txt: 部门表
        - user.txt: 用户表
        - dept_user.txt: 部门-用户关联表
        """
        self.org_df = pd.read_csv(f"{self.data_dir}/org.txt", sep='\t')
        self.dept_df = pd.read_csv(f"{self.data_dir}/dept.txt", sep='\t')
        self.user_df = pd.read_csv(f"{self.data_dir}/user.txt", sep='\t')
        self.dept_user_df = pd.read_csv(f"{self.data_dir}/dept_user.txt", sep='\t')

    # ==================== 组织相关方法 ====================

    def get_org_name(self, org_id: int) -> str:
        """
        获取组织名称

        参数：
            org_id: 组织ID

        返回：
            str: 组织名称，如果不存在则返回空字符串

        示例：
            >>> loader.get_org_name(1)
            'Jaco'
            >>> loader.get_org_name(999)
            ''
        """
        org = self.org_df[self.org_df['id'] == org_id]
        if not org.empty:
            return org.iloc[0]['name']
        return ""

    # ==================== 用户查询方法 ====================

    def get_user_by_id(self, user_id: int) -> Optional[pd.Series]:
        """
        根据用户ID获取用户信息

        参数：
            user_id: 用户ID（工号）

        返回：
            pd.Series: 用户信息，包含以下字段：
                - id: 用户ID
                - name: 姓名
                - mobile: 手机号
                - email: 邮箱
                - role: 角色ID
                - gender: 性别ID
                - join_date: 入职时间戳（秒）
                - manager_id: 上级ID
                - org_id: 组织ID
            如果用户不存在则返回 None

        示例：
            >>> user = loader.get_user_by_id(10042)
            >>> print(user['name'])  # 籍钧良
            >>> print(user['mobile'])  # 13900000042
            >>> print(user['email'])  # j.jin@company.com
        """
        users = self.user_df[self.user_df['id'] == user_id]
        if users.empty:
            return None
        return users.iloc[0]

    def get_user_by_name(self, name: str, org_id: int = None) -> List[pd.Series]:
        """
        根据姓名精确搜索用户

        参数：
            name: 用户姓名（精确匹配）
            org_id: 组织ID，如果不指定则搜索所有组织

        返回：
            List[pd.Series]: 匹配的用户列表

        示例：
            >>> users = loader.get_user_by_name("籍钧良", org_id=1)
            >>> len(users)  # 1
            >>> users[0].id  # 10042

            >>> users = loader.get_user_by_name("马云")
            >>> users[0].id  # 10001（CEO）
        """
        users = self.user_df[self.user_df['name'] == name]
        if org_id is not None:
            users = users[users['org_id'] == org_id]
        return list(users.itertuples())

    def get_user_by_mobile(self, mobile_suffix: str, org_id: int = None) -> List[pd.Series]:
        """
        根据手机号后缀搜索用户

        参数：
            mobile_suffix: 手机号后缀（如 "8888" 匹配尾号为8888的手机号）
            org_id: 组织ID，如果不指定则搜索所有组织

        返回：
            List[pd.Series]: 匹配的用户列表

        示例：
            >>> users = loader.get_user_by_mobile("0042")
            >>> users[0].name  # 籍钧良（手机号：13900000042）

            >>> users = loader.get_user_by_mobile("8888")
            >>> len(users)  # 0（没有尾号8888的用户）
        """
        users = self.user_df[self.user_df['mobile'].str.endswith(mobile_suffix)]
        if org_id is not None:
            users = users[users['org_id'] == org_id]
        return list(users.itertuples())

    def get_user_by_email(self, email: str, org_id: int = None) -> Optional[pd.Series]:
        """
        根据邮箱精确搜索用户

        参数：
            email: 用户邮箱（精确匹配）
            org_id: 组织ID，如果不指定则搜索所有组织

        返回：
            pd.Series: 用户信息，如果不存在则返回 None

        示例：
            >>> user = loader.get_user_by_email("j.jin@company.com")
            >>> user.name  # 籍钧良

            >>> user = loader.get_user_by_email("kai.bei@company.com")
            >>> user  # None（该邮箱不存在）
        """
        users = self.user_df[self.user_df['email'] == email]
        if org_id is not None:
            users = users[users['org_id'] == org_id]
        if users.empty:
            return None
        return users.iloc[0]

    def get_users_by_name_pattern(self, pattern: str, org_id: int = None) -> List[pd.Series]:
        """
        根据姓名模式模糊搜索用户

        参数：
            pattern: 姓名中的关键词（支持模糊匹配）
            org_id: 组织ID，如果不指定则搜索所有组织

        返回：
            List[pd.Series]: 匹配的用户列表

        示例：
            >>> users = loader.get_users_by_name_pattern("张")
            >>> [u.name for u in users]
            ['张松言']

            >>> users = loader.get_users_by_name_pattern("章")
            >>> [u.name for u in users]
            ['章伟', '章东朗']

        注意：
            - 姓"张"和姓"章"是不同的姓氏
            - 搜索区分精确字符
        """
        users = self.user_df[self.user_df['name'].str.contains(pattern, na=False)]
        if org_id is not None:
            users = users[users['org_id'] == org_id]
        return list(users.itertuples())

    # ==================== 部门查询方法 ====================

    def get_dept_by_id(self, dept_id: int) -> Optional[pd.Series]:
        """
        根据部门ID获取部门信息

        参数：
            dept_id: 部门ID

        返回：
            pd.Series: 部门信息，包含以下字段：
                - id: 部门ID
                - name: 部门名称
                - level: 部门层级（1=一级部门，2=二级部门）
                - leader_id: 部门负责人ID
                - parent_id: 上级部门ID
                - org_id: 组织ID
            如果部门不存在则返回 None

        示例：
            >>> dept = loader.get_dept_by_id(4)
            >>> dept['name']  # 后端
            >>> dept['leader_id']  # 10042（籍钧良）
        """
        depts = self.dept_df[self.dept_df['id'] == dept_id]
        if depts.empty:
            return None
        return depts.iloc[0]

    def get_dept_by_name(self, name: str, org_id: int = None) -> List[pd.Series]:
        """
        根据部门名称搜索部门

        参数：
            name: 部门名称（支持精确匹配和模糊匹配）
            org_id: 组织ID，如果不指定则搜索所有组织

        返回：
            List[pd.Series]: 匹配的部门列表

        匹配规则：
            1. 先尝试精确匹配（如 "后端" 匹配 "后端"）
            2. 如果精确匹配无结果，再尝试模糊匹配（如 "用增" 可以匹配 "用户增长"）

        示例：
            >>> depts = loader.get_dept_by_name("后端", org_id=1)
            >>> depts[0].id  # 部门ID

            >>> depts = loader.get_dept_by_name("用增", org_id=1)
            >>> depts[0].name  # 用户增长（"用增"是简称）

            >>> depts = loader.get_dept_by_name("财务", org_id=1)
            >>> len(depts)  # 0（Jaco组织没有财务部）
        """
        # 精确匹配
        depts = self.dept_df[self.dept_df['name'] == name]
        if org_id is not None:
            depts = depts[depts['org_id'] == org_id]
        if not depts.empty:
            return list(depts.itertuples())
        # 模糊匹配（简称）
        depts = self.dept_df[self.dept_df['name'].str.contains(name, na=False)]
        if org_id is not None:
            depts = depts[depts['org_id'] == org_id]
        return list(depts.itertuples())

    def get_dept_users(self, dept_id: int) -> List[pd.Series]:
        """
        获取部门成员列表

        参数：
            dept_id: 部门ID

        返回：
            List[pd.Series]: 部门成员列表

        示例：
            >>> users = loader.get_dept_users(4)  # 后端部门
            >>> len(users)  # 部门人数
            >>> [u.name for u in users]
            ['家才', '贝冠', '谢邦家', ...]
        """
        user_ids = self.dept_user_df[self.dept_user_df['dept_id'] == dept_id]['user_id'].tolist()
        users = self.user_df[self.user_df['id'].isin(user_ids)]
        return list(users.itertuples())

    def get_dept_count(self, dept_id: int) -> int:
        """
        获取部门人数

        参数：
            dept_id: 部门ID

        返回：
            int: 部门成员数量

        示例：
            >>> loader.get_dept_count(4)  # 后端部门人数
            11

            >>> loader.get_dept_count(3)  # 产品部门人数
            10
        """
        return len(self.dept_user_df[self.dept_user_df['dept_id'] == dept_id])

    # ==================== 用户-部门关系方法 ====================

    def get_user_dept(self, user_id: int) -> Optional[pd.Series]:
        """
        获取用户的主部门

        参数：
            user_id: 用户ID

        返回：
            pd.Series: 用户的主部门信息，如果用户未分配部门则返回 None

        示例：
            >>> dept = loader.get_user_dept(10042)
            >>> dept['name']  # 后端

            >>> dept = loader.get_user_dept(10001)  # CEO
            >>> dept  # None（CEO没有部门）
        """
        dept_user = self.dept_user_df[self.dept_user_df['user_id'] == user_id]
        if dept_user.empty:
            return None
        dept_id = dept_user.iloc[0]['dept_id']
        return self.get_dept_by_id(dept_id)

    def get_user_depts(self, user_id: int) -> List[pd.Series]:
        """
        获取用户的所有部门（含兼职部门）

        参数：
            user_id: 用户ID

        返回：
            List[pd.Series]: 用户所属的部门列表

        说明：
            - 支持用户同时属于多个部门的情况（如兼职）
            - 大多数情况下用户只属于一个部门

        示例：
            >>> depts = loader.get_user_depts(10042)
            >>> len(depts)  # 通常为1
            >>> depts[0]['name']  # 后端
        """
        dept_ids = self.dept_user_df[self.dept_user_df['user_id'] == user_id]['dept_id'].tolist()
        depts = []
        for dept_id in dept_ids:
            dept = self.get_dept_by_id(dept_id)
            if dept is not None:
                depts.append(dept)
        return depts

    # ==================== 上下级关系方法 ====================

    def get_subordinates(self, manager_id: int, org_id: int = None) -> List[pd.Series]:
        """
        获取直属下级列表

        参数：
            manager_id: 上级用户ID
            org_id: 组织ID，如果不指定则搜索所有组织

        返回：
            List[pd.Series]: 直属下级列表

        说明：
            - 只返回直属下级（直接汇报关系），不包括更下级的员工
            - 通过 user 表的 manager_id 字段查询

        示例：
            >>> subs = loader.get_subordinates(10042)  # 籍钧良的下属
            >>> len(subs)  # 9（后端部门有9个成员向籍钧良汇报）

            >>> subs = loader.get_subordinates(10001)  # CEO的下属
            >>> len(subs)  # 6（一级部门leader直接向CEO汇报）
        """
        users = self.user_df[self.user_df['manager_id'] == manager_id]
        if org_id is not None:
            users = users[users['org_id'] == org_id]
        return list(users.itertuples())

    # ==================== 角色和性别辅助方法 ====================

    def get_role_name(self, role_id: int) -> str:
        """
        获取角色名称

        参数：
            role_id: 角色ID

        返回：
            str: 角色名称

        角色映射：
            1 -> 产品经理
            2 -> 开发工程师
            3 -> 算法工程师
            4 -> HR
            5 -> Android工程师
            6 -> iOS工程师
            7 -> 测试工程师
            8 -> 二级部门leader
            9 -> 一级部门leader

        示例：
            >>> loader.get_role_name(1)
            '产品经理'
            >>> loader.get_role_name(9)
            '一级部门leader'
            >>> loader.get_role_name(999)
            '未知角色(999)'
        """
        return ROLE_MAP.get(role_id, f"未知角色({role_id})")

    def get_gender_name(self, gender_id: int) -> str:
        """
        获取性别名称

        参数：
            gender_id: 性别ID

        返回：
            str: 性别名称

        性别映射：
            0 -> 未知
            1 -> 男
            2 -> 女

        示例：
            >>> loader.get_gender_name(1)
            '男'
            >>> loader.get_gender_name(2)
            '女'
        """
        return GENDER_MAP.get(gender_id, f"未知({gender_id})")

    # ==================== 时间转换方法 ====================

    def timestamp_to_date(self, timestamp: int) -> str:
        """
        时间戳转日期字符串

        参数：
            timestamp: Unix时间戳（秒）

        返回：
            str: 格式化的日期字符串 (YYYY-MM-DD)

        示例：
            >>> loader.timestamp_to_date(1623715200)
            '2021-06-15'
        """
        return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')

    def timestamp_to_year(self, timestamp: int) -> int:
        """
        时间戳转年份

        参数：
            timestamp: Unix时间戳（秒）

        返回：
            int: 年份

        示例：
            >>> loader.timestamp_to_year(1623715200)
            2021
        """
        return datetime.fromtimestamp(timestamp).year

    # ==================== 组织级别查询方法 ====================

    def get_org_users(self, org_id: int) -> List[pd.Series]:
        """
        获取组织所有用户

        参数：
            org_id: 组织ID

        返回：
            List[pd.Series]: 组织内的所有用户列表

        示例：
            >>> users = loader.get_org_users(1)  # Jaco组织
            >>> len(users)  # 61
        """
        users = self.user_df[self.user_df['org_id'] == org_id]
        return list(users.itertuples())

    def get_org_depts(self, org_id: int) -> List[pd.Series]:
        """
        获取组织所有部门

        参数：
            org_id: 组织ID

        返回：
            List[pd.Series]: 组织内的所有部门列表

        示例：
            >>> depts = loader.get_org_depts(1)  # Jaco组织
            >>> len(depts)  # 6
        """
        depts = self.dept_df[self.dept_df['org_id'] == org_id]
        return list(depts.itertuples())

    def get_top_level_depts(self, org_id: int) -> List[pd.Series]:
        """
        获取一级部门

        参数：
            org_id: 组织ID

        返回：
            List[pd.Series]: 一级部门列表

        说明：
            - 一级部门是指 level=1 的部门
            - 一级部门直接向CEO/Owner汇报

        示例：
            >>> depts = loader.get_top_level_depts(1)
            >>> [d.name for d in depts]
            ['机器学习', '产品', '用户增长', '前端', '后端', '人力资源']
        """
        depts = self.dept_df[(self.dept_df['org_id'] == org_id) & (self.dept_df['level'] == 1)]
        return list(depts.itertuples())

    # ==================== 部门层级关系方法 ====================

    def get_child_depts(self, parent_id: int) -> List[pd.Series]:
        """
        获取子部门

        参数：
            parent_id: 父部门ID

        返回：
            List[pd.Series]: 子部门列表

        说明：
            - 通过 parent_id 字段查询直接下级部门

        示例：
            >>> children = loader.get_child_depts(4)
            >>> len(children)  # 子部门数量
        """
        depts = self.dept_df[self.dept_df['parent_id'] == parent_id]
        return list(depts.itertuples())

    def get_sibling_depts(self, dept_id: int) -> List[pd.Series]:
        """
        获取兄弟部门（同级部门）

        参数：
            dept_id: 部门ID

        返回：
            List[pd.Series]: 兄弟部门列表

        说明：
            - 兄弟部门是指具有相同父部门的部门
            - 对于一级部门，兄弟部门是其他一级部门

        示例：
            >>> siblings = loader.get_sibling_depts(4)  # 后端部门的兄弟部门
            >>> [d.name for d in siblings]
            ['机器学习', '产品', '用户增长', '前端', '人力资源']
        """
        dept = self.get_dept_by_id(dept_id)
        if dept is None:
            return []
        parent_id = dept['parent_id']
        if pd.isna(parent_id):
            # 一级部门
            depts = self.dept_df[
                (self.dept_df['org_id'] == dept['org_id']) &
                (self.dept_df['level'] == dept['level']) &
                (self.dept_df['id'] != dept_id)
            ]
        else:
            depts = self.dept_df[
                (self.dept_df['parent_id'] == parent_id) &
                (self.dept_df['id'] != dept_id)
            ]
        return list(depts.itertuples())

    # ==================== 按角色查询方法 ====================

    def get_users_by_role(self, role_id: int, org_id: int = None) -> List[pd.Series]:
        """
        根据角色获取用户列表

        参数：
            role_id: 角色ID
            org_id: 组织ID，如果不指定则搜索所有组织

        返回：
            List[pd.Series]: 具有该角色的用户列表

        示例：
            >>> pms = loader.get_users_by_role(1, org_id=1)  # 产品经理
            >>> len(pms)  # 9
            >>> [pm.name for pm in pms]
            ['虞裕', '易亨强', '冉心', ...]

            >>> leaders = loader.get_users_by_role(9, org_id=1)  # 一级部门leader
            >>> len(leaders)  # 7（包含CEO）
        """
        users = self.user_df[self.user_df['role'] == role_id]
        if org_id is not None:
            users = users[users['org_id'] == org_id]
        return list(users.itertuples())

    # ==================== 部门路径方法 ====================

    def get_dept_tree_path(self, dept_id: int) -> str:
        """
        获取部门的层级路径

        参数：
            dept_id: 部门ID

        返回：
            str: 部门的完整层级路径，用 " > " 连接

        说明：
            - 从当前部门向上追溯到顶级部门
            - 路径格式：顶级部门 > 中级部门 > 当前部门

        示例：
            >>> loader.get_dept_tree_path(4)
            '后端'

            >>> # 如果有多级部门，路径会是：顶级 > 中级 > 当前
        """
        path = []
        current = self.get_dept_by_id(dept_id)
        while current is not None:
            path.insert(0, current['name'])
            parent_id = current['parent_id']
            if pd.isna(parent_id):
                break
            current = self.get_dept_by_id(int(parent_id))
        return " > ".join(path)


# 创建全局实例
# 使用方法：直接调用 loader 的方法
# 示例：user = loader.get_user_by_id(10042)
loader = OrgDataLoader()


def get_current_user() -> pd.Series:
    """
    获取当前用户（"我"）

    返回：
        pd.Series: 当前用户（籍钧良）的信息

    说明：
        - CURRENT_USER_ID = 10042（籍钧良）
        - 用于回答关于"我"的问题

    示例：
        >>> me = get_current_user()
        >>> me['name']  # 籍钧良
        >>> me['id']  # 10042
    """
    return loader.get_user_by_id(CURRENT_USER_ID)


def get_current_org() -> pd.Series:
    """
    获取当前组织

    返回：
        pd.Series: 当前组织（Jaco）的信息

    说明：
        - CURRENT_ORG_ID = 1（Jaco）

    示例：
        >>> org = get_current_org()
        >>> org['name']  # Jaco
    """
    org = loader.org_df[loader.org_df['id'] == CURRENT_ORG_ID]
    if not org.empty:
        return org.iloc[0]
    return None
