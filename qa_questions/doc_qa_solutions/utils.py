"""
文档系统数据加载和查询工具
用于回答 doc_qa.md 中的问题

主要功能：
- 加载文档和用户访问权限数据
- 获取用户可访问的文档列表
- 按文档类型、关键词搜索
- 获取用户创建的文档
- 文档统计信息

数据表说明：
- ods_docs_min.txt: 文档表（doc_id, org_id, owner, ctype, title,
  note, create_time, update_time, content_length）
  - doc_id: 文档唯一标识
  - owner: 创建者用户ID
  - ctype: 文档类型（doc/sheet/slide/pdf等）
  - title: 文档标题
  - note: 文档备注/说明
  - content_length: 内容长度（字符数）

- dwd_user_doc_access_min.txt: 用户文档访问权限表（user_org_id, user_id, doc_ids）
  - user_org_id: 用户所属组织ID
  - user_id: 用户ID
  - doc_ids: 用户可访问的文档ID列表（逗号分隔）

文档类型：
- doc/docx: Word文档
- sheet/xls/xlsx: Excel表格
- slide/ppt/pptx: PPT演示文稿
- pdf: PDF文档
- txt: 文本文件

权限说明：
- 用户只能访问自己拥有或被共享的文档
- 通过访问权限表判断用户可访问的文档
"""
import pandas as pd
from datetime import datetime
from typing import Optional, List, Dict, Any
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from org_qa_solutions.utils import OrgDataLoader, CURRENT_ORG_ID, CURRENT_USER_ID

# 文档数据路径（相对路径）
DOC_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                             "fake_beem", "simplified_schema", "synthetic_data", "doc", "data")

# 文档类型映射表
# ctype -> 类型名称
DOC_TYPES = {
    'doc': 'Word文档',
    'docx': 'Word文档',
    'pdf': 'PDF文档',
    'ppt': 'PPT演示文稿',
    'pptx': 'PPT演示文稿',
    'slide': '演示文稿',
    'xls': 'Excel表格',
    'xlsx': 'Excel表格',
    'sheet': '表格',
    'txt': '文本文件',
}


class DocDataLoader:
    """
    文档数据加载器

    用于加载和查询文档系统数据，包括文档信息、访问权限等。

    示例：
        >>> loader = DocDataLoader()
        >>> docs = loader.get_user_docs(10042)
        >>> for doc in docs:
        ...     print(f"文档: {doc.title}, 类型: {doc.ctype}")
    """

    def __init__(self, data_dir: str = DOC_DATA_DIR, org_id: int = CURRENT_ORG_ID):
        """
        初始化文档数据加载器

        参数：
            data_dir: 数据目录路径，默认为 DOC_DATA_DIR
            org_id: 组织ID，默认为当前组织（Jaco，ID=1）

        功能：
            加载文档表和用户访问权限表
            解析用户的可访问文档列表
            只加载指定组织的数据
        """
        self.data_dir = data_dir
        self.org_id = org_id
        self.org_loader = OrgDataLoader()
        self._load_data()

    def _load_data(self):
        """
        加载文档数据表（内部方法）

        加载的数据表：
        - ods_docs_min.txt: 文档表
        - dwd_user_doc_access_min.txt: 用户文档访问权限表

        过滤规则：
            - 只保留当前组织（org_id）的数据
        """
        # 加载文档表
        self.docs_df = pd.read_csv(f"{self.data_dir}/ods_docs_min.txt", sep='\t')
        # 只保留当前组织的数据
        self.docs_df = self.docs_df[self.docs_df['org_id'] == self.org_id]

        # 加载用户文档访问权限表
        self.access_df = pd.read_csv(f"{self.data_dir}/dwd_user_doc_access_min.txt", sep='\t')
        # 只保留当前组织的数据
        self.access_df = self.access_df[self.access_df['user_org_id'] == self.org_id]

        # 解析用户的可访问文档列表
        self._parse_user_docs()

    def _parse_user_docs(self):
        """
        解析用户的可访问文档列表（内部方法）

        生成数据结构：
            self.user_docs = {user_id: [doc_id, ...]}

        说明：
            - 从访问权限表中解析每个用户可访问的文档
            - doc_ids 是逗号分隔的字符串
        """
        self.user_docs = {}  # {user_id: [doc_id, ...]}

        for _, row in self.access_df.iterrows():
            user_id = row['user_id']
            doc_ids = str(row['doc_ids']).split(',')

            self.user_docs[user_id] = doc_ids

    # ==================== 用户文档查询方法 ====================

    def get_user_accessible_docs(self, user_id: int) -> List[str]:
        """
        获取用户可访问的文档ID列表

        参数：
            user_id: 用户ID

        返回：
            List[str]: 可访问文档的ID列表

        说明：
            - 返回用户拥有权限的所有文档ID
            - 包括自己创建和被共享的文档
            - 这是权限控制的核心方法

        示例：
            >>> doc_ids = doc_loader.get_user_accessible_docs(10042)
            >>> len(doc_ids)  # 可访问文档数量
            >>> doc_ids[0]  # 第一个文档ID

        应用场景：
            - 查看用户能访问哪些文档
            - 作为其他查询的基础
        """
        return self.user_docs.get(user_id, [])

    def get_doc_by_id(self, doc_id: str) -> Optional[pd.Series]:
        """
        根据文档ID获取文档信息

        参数：
            doc_id: 文档ID

        返回：
            pd.Series: 文档信息，包含以下字段：
                - doc_id: 文档ID
                - org_id: 组织ID
                - owner: 创建者用户ID
                - ctype: 文档类型
                - title: 文档标题
                - note: 文档备注
                - create_time: 创建时间（秒时间戳）
                - update_time: 更新时间（秒时间戳）
                - content_length: 内容长度
            如果文档不存在则返回 None

        示例：
            >>> doc = doc_loader.get_doc_by_id("doc_001")
            >>> doc['title']  # 文档标题
            >>> doc['ctype']  # 文档类型
            >>> doc['owner']  # 创建者ID
        """
        docs = self.docs_df[self.docs_df['doc_id'] == doc_id]
        if docs.empty:
            return None
        return docs.iloc[0]

    def get_user_docs(self, user_id: int) -> List[pd.Series]:
        """
        获取用户可访问的所有文档（完整信息）

        参数：
            user_id: 用户ID

        返回：
            List[pd.Series]: 用户可访问的文档列表

        说明：
            - 返回的是文档的完整信息，不只是ID
            - 只返回用户有权限访问的文档

        示例：
            >>> docs = doc_loader.get_user_docs(10042)
            >>> len(docs)  # 可访问文档数量
            >>> docs[0].title  # 第一个文档的标题
            >>> docs[0].ctype  # 第一个文档的类型

        应用场景：
            - 列出用户能看到的所有文档
            - 显示文档列表
        """
        doc_ids = self.get_user_accessible_docs(user_id)
        docs = self.docs_df[self.docs_df['doc_id'].isin(doc_ids)]
        return list(docs.itertuples())

    def get_user_created_docs(self, user_id: int) -> List[pd.Series]:
        """
        获取用户创建的文档

        参数：
            user_id: 用户ID

        返回：
            List[pd.Series]: 用户创建的文档列表

        说明：
            - 通过 owner 字段查询
            - 返回用户作为创建者的所有文档

        示例：
            >>> docs = doc_loader.get_user_created_docs(10042)
            >>> len(docs)  # 创建的文档数量
            >>> [d.title for d in docs]  # 文档标题列表

        应用场景：
            - 查看"我创建的文档"
            - 统计用户的创作数量
        """
        docs = self.docs_df[self.docs_df['owner'] == user_id]
        return list(docs.itertuples())

    # ==================== 按类型查询方法 ====================

    def get_docs_by_type(self, doc_type: str, user_id: int = None) -> List[pd.Series]:
        """
        根据文档类型获取文档

        参数：
            doc_type: 文档类型（如 'doc', 'sheet', 'slide', 'pdf'）
            user_id: 用户ID（可选），如果指定则只返回该用户可访问的文档

        返回：
            List[pd.Series]: 指定类型的文档列表

        文档类型：
            - doc/docx: Word文档
            - sheet/xls/xlsx: Excel表格
            - slide/ppt/pptx: PPT演示文稿
            - pdf: PDF文档

        示例：
            >>> docs = doc_loader.get_docs_by_type('doc', user_id=10042)
            >>> len(docs)  # Word文档数量

            >>> # 获取所有slide类型文档（不限制用户）
            >>> docs = doc_loader.get_docs_by_type('slide')

        应用场景：
            - 查看特定类型的文档
            - 按类型筛选文档列表
        """
        docs = self.docs_df[self.docs_df['ctype'] == doc_type]

        if user_id is not None:
            accessible_ids = self.get_user_accessible_docs(user_id)
            docs = docs[docs['doc_id'].isin(accessible_ids)]

        return list(docs.itertuples())

    # ==================== 搜索方法 ====================

    def search_docs_by_keyword(self, keyword: str, user_id: int = None) -> List[pd.Series]:
        """
        根据关键词搜索文档（标题和备注）

        参数：
            keyword: 搜索关键词
            user_id: 用户ID（可选），如果指定则只搜索该用户可访问的文档

        返回：
            List[pd.Series]: 匹配的文档列表

        搜索范围：
            - 文档标题（title）
            - 文档备注（note）

        搜索规则：
            - 不区分大小写
            - 支持部分匹配（contains）

        示例：
            >>> docs = doc_loader.search_docs_by_keyword("MCN", user_id=10042)
            >>> len(docs)  # 包含"MCN"的文档数量
            >>> docs[0].title  # 第一个匹配文档的标题

            >>> # 搜索包含"算法"的文档
            >>> docs = doc_loader.search_docs_by_keyword("算法")

        应用场景：
            - 查找特定主题的文档
            - 按关键词筛选文档
        """
        # 搜索标题
        title_match = self.docs_df[self.docs_df['title'].str.contains(keyword, na=False, case=False)]
        # 搜索备注
        note_match = self.docs_df[self.docs_df['note'].str.contains(keyword, na=False, case=False)]

        docs = pd.concat([title_match, note_match]).drop_duplicates()

        if user_id is not None:
            accessible_ids = self.get_user_accessible_docs(user_id)
            docs = docs[docs['doc_id'].isin(accessible_ids)]

        return list(docs.itertuples())

    # ==================== 辅助方法 ====================

    def get_doc_type_name(self, ctype: str) -> str:
        """
        获取文档类型名称

        参数：
            ctype: 文档类型代码

        返回：
            str: 文档类型的中文名称

        示例：
            >>> doc_loader.get_doc_type_name('doc')
            'Word文档'
            >>> doc_loader.get_doc_type_name('sheet')
            '表格'
            >>> doc_loader.get_doc_type_name('unknown')
            'unknown'
        """
        return DOC_TYPES.get(ctype, ctype)

    def timestamp_to_datetime(self, timestamp: int) -> str:
        """
        时间戳转日期时间字符串

        参数：
            timestamp: Unix时间戳（秒）

        返回：
            str: 格式化的日期时间 (YYYY-MM-DD HH:MM:SS)

        示例：
            >>> doc_loader.timestamp_to_datetime(1623715200)
            '2021-06-15 00:00:00'
        """
        return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')

    def timestamp_to_date(self, timestamp: int) -> str:
        """
        时间戳转日期字符串

        参数：
            timestamp: Unix时间戳（秒）

        返回：
            str: 格式化的日期 (YYYY-MM-DD)

        示例：
            >>> doc_loader.timestamp_to_date(1623715200)
            '2021-06-15'
        """
        return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')

    def get_user_name(self, user_id: int) -> str:
        """
        获取用户姓名

        参数：
            user_id: 用户ID

        返回：
            str: 用户姓名，如果用户不存在则返回 "用户{user_id}"

        示例：
            >>> doc_loader.get_user_name(10042)
            '籍钧良'
            >>> doc_loader.get_user_name(99999)
            '用户99999'

        说明：
            - 通过 OrgDataLoader 查询用户信息
        """
        user = self.org_loader.get_user_by_id(user_id)
        if user is not None:
            return user['name']
        return f"用户{user_id}"

    # ==================== 统计方法 ====================

    def get_doc_stats(self, user_id: int) -> Dict:
        """
        获取用户文档统计

        参数：
            user_id: 用户ID

        返回：
            Dict: 文档统计信息，包含：
                - accessible_count: 可访问文档数量
                - created_count: 创建文档数量
                - type_counts: 按类型统计的字典 {ctype: count}

        示例：
            >>> stats = doc_loader.get_doc_stats(10042)
            >>> stats['accessible_count']  # 可访问文档数
            >>> stats['created_count']  # 创建文档数
            >>> stats['type_counts']  # {'doc': 1, 'slide': 1, ...}

        应用场景：
            - 查看用户的文档概况
            - 统计文档分布
        """
        accessible = self.get_user_docs(user_id)
        created = self.get_user_created_docs(user_id)

        # 按类型统计
        type_counts = {}
        for doc in accessible:
            ctype = doc.ctype
            type_counts[ctype] = type_counts.get(ctype, 0) + 1

        return {
            'accessible_count': len(accessible),
            'created_count': len(created),
            'type_counts': type_counts
        }


# 创建全局实例
# 使用方法：直接调用 doc_loader 的方法
# 示例：docs = doc_loader.get_user_docs(10042)
doc_loader = DocDataLoader()
