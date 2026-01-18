
import os
import random
import time
import uuid
from faker import Faker

# Constants
ORG_DATA_PATH = '/root/hemengfei/beemagent/fake_beem/simplified_schema/synthetic_data/org_system/data/org.txt'
USER_DATA_PATH = '/root/hemengfei/beemagent/fake_beem/simplified_schema/synthetic_data/org_system/data/user.txt'
OUTPUT_DIR = '/root/hemengfei/beemagent/fake_beem/simplified_schema/synthetic_data/doc/data'

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

fake = Faker('zh_CN')

class User:
    def __init__(self, user_id, org_id, join_date):
        self.user_id = user_id
        self.org_id = org_id
        self.join_date = int(join_date)

class Org:
    def __init__(self, org_id, name, created_at):
        self.org_id = org_id
        self.name = name
        self.created_at = int(created_at)

def load_data():
    orgs = {}
    users = []
    
    # Load Orgs
    with open(ORG_DATA_PATH, 'r') as f:
        lines = f.readlines()[1:] # Skip header
        for line in lines:
            parts = line.strip().split('\t')
            if len(parts) >= 5:
                # id, name, short_name, owner_user_id, created_at
                org = Org(parts[0], parts[1], parts[4])
                orgs[parts[0]] = org
    
    # Load Users
    with open(USER_DATA_PATH, 'r') as f:
        lines = f.readlines()[1:] # Skip header
        for line in lines:
            parts = line.strip().split('\t')
            if len(parts) >= 8:
                # id, org_id, name, manager_id, role, mobile, email, join_date, ...
                user = User(parts[0], parts[1], parts[7])
                users.append(user)
                
    return orgs, users

def generate_doc_content(org_name):
    # ctype distribution: 70% doc, 10% sheet, 10% slide, 10% pdf
    r = random.random()
    if r < 0.7:
        ctype = 'doc'
    elif r < 0.8:
        ctype = 'sheet'
    elif r < 0.9:
        ctype = 'slide'
    else:
        ctype = 'pdf'
        
    if 'Jaco' in org_name:
        topic_keywords = ['短视频', '直播', '网红', '流量', '粉丝', '特效', '滤镜', '剪辑', 'BGM', '挑战赛', '带货', '运营', '算法', '推荐', '审核', '违规', '封号', '申诉', 'MCN', '签约']
        base_topic = random.choice(topic_keywords)
        title = f"{base_topic} - {fake.sentence(nb_words=5, variable_nb_words=True)}"[:20] # Limit to ~20 chars roughly, or just ensure it's short
        # Improve title generation to be closer to 20 chars if possible, but schema says "approx 20 chars"
        # Let's make it more realistic
        title = f"{base_topic}相关{fake.word()}{fake.word()}" 
        if len(title) > 20: title = title[:20]
        
        note = f"关于{base_topic}的详细说明：\n" + fake.text(max_nb_chars=140)
        
    else: # Beem
        topic_keywords = ['会议', '日程', 'OKR', '周报', '项目', '排期', '预算', '报销', '审批', '考勤', '打卡', '招聘', '面试', '入职', '离职', '合同', '客户', '销售', '采购', '库存']
        base_topic = random.choice(topic_keywords)
        title = f"{base_topic}管理规范-{fake.word()}"
        if len(title) > 20: title = title[:20]
        
        note = f"本次{base_topic}的主要内容如下：\n" + fake.text(max_nb_chars=140)
        
    return ctype, title, note

def main():
    orgs, users = load_data()
    
    # Filter users by org
    jaco_users = [u for u in users if orgs[u.org_id].name == 'Jaco']
    beem_users = [u for u in users if orgs[u.org_id].name == 'Beem']
    
    # Map org_name to (org_obj, user_list)
    target_orgs = [
        (orgs['1'], jaco_users), # Jaco is id 1
        (orgs['2'], beem_users)  # Beem is id 2
    ]
    
    docs_data = [] # List of dicts
    access_data = {} # (user_org_id, user_id) -> set(doc_ids)
    
    for org, org_users in target_orgs:
        if not org_users:
            print(f"Warning: No users found for {org.name}")
            continue
            
        for i in range(20):
            # 1. Select owner
            owner = random.choice(org_users)
            
            # 2. Generate content
            ctype, title, note = generate_doc_content(org.name)
            
            # 3. Generate ID and timestamp
            doc_id = str(uuid.uuid4())
            
            # Timestamp: > org_create_time, > owner_join_date
            min_time = max(org.created_at, owner.join_date)
            # Add some random seconds, up to 1 year (approx 30m seconds)
            create_time = min_time + random.randint(1, 31536000)
            # Ensure it doesn't exceed current time too much (optional, but good for realism)
            # The env says today is 2026, data is 2021/2022. So it's fine.
            
            # 4. Save Doc
            docs_data.append({
                'org_id': org.org_id,
                'doc_id': doc_id,
                'create_time': create_time,
                'ctype': ctype,
                'title': title,
                'note': note.replace('\n', ' ').replace('\t', ' '), # Clean up for TSV
                'owner': owner.user_id
            })
            
            # 5. Access Rights
            # Randomly extract 6 people (can include owner, or not). 
            # Prompt: "randomly extract 6 people to grant... access"
            # Schema: "owner must be in this table".
            # Strategy: Pick 6 random users. Add owner to the set.
            
            potential_viewers = random.sample(org_users, min(6, len(org_users)))
            viewers = set([u.user_id for u in potential_viewers])
            viewers.add(owner.user_id) # Ensure owner has access
            
            for viewer_id in viewers:
                key = (org.org_id, viewer_id)
                if key not in access_data:
                    access_data[key] = set()
                access_data[key].add(doc_id)

    # Write ods_docs_min
    with open(os.path.join(OUTPUT_DIR, 'ods_docs_min.txt'), 'w') as f:
        # Header
        f.write("org_id\tdoc_id\tcreate_time\tctype\ttitle\tnote\towner\n")
        for doc in docs_data:
            line = f"{doc['org_id']}\t{doc['doc_id']}\t{doc['create_time']}\t{doc['ctype']}\t{doc['title']}\t{doc['note']}\t{doc['owner']}\n"
            f.write(line)
            
    # Write dwd_user_doc_access_min
    with open(os.path.join(OUTPUT_DIR, 'dwd_user_doc_access_min.txt'), 'w') as f:
        # Header
        f.write("user_org_id\tuser_id\tdoc_ids\n")
        for key, doc_ids in access_data.items():
            user_org_id, user_id = key
            # Join with ',' for Hive Array
            doc_ids_str = ",".join(sorted(list(doc_ids)))
            line = f"{user_org_id}\t{user_id}\t{doc_ids_str}\n"
            f.write(line)

if __name__ == "__main__":
    main()
