# 文档系统问题解答总结

## 文件结构
```
doc_qa_solutions/
├── utils.py              # 文档数据加载和查询工具
├── 001-050.md           # 可访问文档列表、我创建的文档
├── 051-200.md           # 类型统计、关键词搜索
├── 201-300.md           # 更多搜索、共享文档、文档详情
└── 301-460.md           # 文档详情、长度统计、时间范围
```

## 当前用户上下文
- **"我"** = Jaco组织 + 用户ID **10042**（籍钧良）

## 文档数据结构

### 数据表
1. **ods_docs_min.txt** (文档表)
   - org_id: 组织ID
   - doc_id: 文档ID
   - create_time: 创建时间
   - ctype: 文档类型 (doc, pdf, slide, sheet等)
   - title: 文档标题
   - note: 文档内容/备注
   - owner: 创建者用户ID

2. **dwd_user_doc_access_min.txt** (用户文档访问权限表)
   - user_org_id: 用户所属组织ID
   - user_id: 用户ID
   - doc_ids: 可访问的文档ID列表（逗号分隔）

### 文档类型
- doc: Word文档
- pdf: PDF文档
- slide: 演示文稿
- sheet: Excel表格

## 当前用户文档数据概况

### 文档统计
- 可访问文档: 2个
- 创建的文档: 0个
- 类型分布: doc(1个), pdf(1个)

### 文档列表
1. 申诉相关一样教育（Word文档，李世创建）
2. 流量相关发现法律（PDF文档，华伯克创建）

### 创建时间
- 最早: 2022-01-13
- 最新: 2022-05-09
- 全部是2022年创建，近期无新文档

## 数据权限说明
- 文档数据严格权限控制
- 用户只能访问有权限的文档
- 包括：自己创建的文档 + 别人共享的文档

## 依赖
```bash
pip install pandas
```

## 使用方法
```python
from utils import doc_loader, CURRENT_USER_ID

# 获取可访问文档
docs = doc_loader.get_user_docs(CURRENT_USER_ID)

# 搜索关键词
results = doc_loader.search_docs_by_keyword("申诉", CURRENT_USER_ID)

# 按类型获取
pdf_docs = doc_loader.get_docs_by_type("pdf", CURRENT_USER_ID)
```
