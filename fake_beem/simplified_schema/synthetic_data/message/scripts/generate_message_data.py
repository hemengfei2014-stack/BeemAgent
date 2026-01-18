import os
import random
import time
import csv
from faker import Faker
from datetime import datetime, timedelta

# Initialize Faker
fake = Faker('zh_CN')

# Constants
ORG_SYSTEM_DATA_DIR = '/root/hemengfei/beemagent/fake_beem/simplified_schema/synthetic_data/org_system/data'
OUTPUT_DIR = '/root/hemengfei/beemagent/fake_beem/simplified_schema/synthetic_data/message/data'
JACO_ORG_ID = '1'
BEEM_ORG_ID = '2'

# Data Holders
users = {}  # userid -> {org_id, dept_id}
depts = {}  # deptid -> {org_id, parent_id}
org_users = {JACO_ORG_ID: [], BEEM_ORG_ID: []}
dept_users = {} # dept_id -> [user_ids]
org_depts = {JACO_ORG_ID: [], BEEM_ORG_ID: []} # org_id -> [dept_ids]

# Load Data
def load_data():
    print("Loading data...")
    
    # Load Depts
    with open(os.path.join(ORG_SYSTEM_DATA_DIR, 'dept.txt'), 'r') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            depts[row['id']] = row
            org_id = row['org_id']
            if org_id in org_depts:
                org_depts[org_id].append(row['id'])

    # Load Dept_User (to map user to dept)
    user_dept_map = {}
    with open(os.path.join(ORG_SYSTEM_DATA_DIR, 'dept_user.txt'), 'r') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            user_dept_map[row['user_id']] = row['dept_id']
            if row['dept_id'] not in dept_users:
                dept_users[row['dept_id']] = []
            dept_users[row['dept_id']].append(row['user_id'])

    # Load Users
    with open(os.path.join(ORG_SYSTEM_DATA_DIR, 'user.txt'), 'r') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            uid = row['id']
            org_id = row['org_id']
            dept_id = user_dept_map.get(uid)
            
            users[uid] = {
                'id': uid,
                'org_id': org_id,
                'dept_id': dept_id,
                'name': row['name']
            }
            if org_id in org_users:
                org_users[org_id].append(uid)

    print(f"Loaded {len(users)} users, {len(depts)} depts.")

# Content Generators
short_video_topics = ['抖音', '快手', '短视频', '直播', '网红', '流量', '变现', '算法', '推荐', '拍摄', '剪辑', '特效', 'BGM', '涨粉', '带货']
enterprise_topics = ['SaaS', 'CRM', 'ERP', '协同办公', '飞书', '钉钉', '企业微信', '考勤', '审批', '报销', 'OKR', 'KPI', '项目管理', '文档', '会议']

def generate_content(topic_list, msg_type):
    topic = random.choice(topic_list)
    if msg_type == 1: # Text
        return f"关于{topic}的{fake.sentence()}"
    elif msg_type == 2: # Link
        return f"{topic}相关资料: {fake.uri()}"
    elif msg_type == 3: # File
        return f"{topic}_需求文档_{fake.file_name(extension='pdf')}"
    return "Unknown"

def get_message_type():
    # 80% Text (1), 10% Link (2), 10% File (3) (Assuming Webpage -> File/Link split or using File to ensure coverage)
    # The user said "10% Link, 10% Webpage". Since Webpage is Type 2 in Schema, but we need to exercise Type 3?
    # Let's strictly follow the user prompt text: "10% link, 10% webpage".
    # And Schema: 2=Link(Webpage), 3=File.
    # If I produce Type 3, I am technically generating "File".
    # I will stick to: 80% Type 1, 10% Type 2, 10% Type 3.
    r = random.random()
    if r < 0.8:
        return 1
    elif r < 0.9:
        return 2
    else:
        return 3

# Data Structures for Output
messages = []
participants = {} # (org_id, user_id) -> {session_ids: [], types: []}

def add_participant(org_id, user_id, session_id, conversation_type):
    key = (org_id, user_id)
    if key not in participants:
        participants[key] = {'session_ids': [], 'types': []}
    
    # Avoid duplicates if any (though logic shouldn't produce them for same session unless re-added)
    if session_id not in participants[key]['session_ids']:
        participants[key]['session_ids'].append(session_id)
        participants[key]['types'].append(conversation_type)

def generate_session_messages(org_id, session_id, user_ids, conversation_type, num_msgs, topic_list):
    base_time = int(time.time() * 1000) - random.randint(0, 10000000)
    
    for i in range(num_msgs):
        sender = random.choice(user_ids)
        if conversation_type == 1: # Single
            target = [u for u in user_ids if u != sender][0]
        else: # Group
            target = session_id
            
        msg_type = get_message_type()
        content = generate_content(topic_list, msg_type)
        
        msg = {
            'org_id': org_id,
            'session_id': session_id,
            'conversation_type': conversation_type,
            'message_id': fake.uuid4(),
            'from_user_id': sender,
            'target_id': target,
            'send_time_ms': base_time + (i * random.randint(1000, 60000)),
            'message_type': msg_type,
            'content': content
        }
        messages.append(msg)

    # Register participants
    for uid in user_ids:
        add_participant(org_id, uid, session_id, conversation_type)

def run_jaco_generation():
    print("Generating Jaco data...")
    org_id = JACO_ORG_ID
    all_users = org_users[org_id]
    
    # 1. Single Chat - Intra Dept
    # Devel 1 depts: 100-105
    for dept_id in ['100', '101', '102', '103', '104', '105']:
        d_users = dept_users.get(dept_id, [])
        if len(d_users) < 2: continue
        
        for _ in range(4): # 4 times per dept
            pair = random.sample(d_users, 2)
            session_id = f"{min(pair)}_{max(pair)}"
            generate_session_messages(org_id, session_id, pair, 1, 20, short_video_topics)

    # 2. Single Chat - Inter Dept (From all users)
    for _ in range(10):
        while True:
            pair = random.sample(all_users, 2)
            # Ensure they are from different departments
            u1_dept = users[pair[0]]['dept_id']
            u2_dept = users[pair[1]]['dept_id']
            if u1_dept != u2_dept:
                break
        session_id = f"{min(pair)}_{max(pair)}"
        generate_session_messages(org_id, session_id, pair, 1, 20, short_video_topics)

    # 3. Group Chat - Intra Dept
    for dept_id in ['100', '101', '102', '103', '104', '105']:
        d_users = dept_users.get(dept_id, [])
        if len(d_users) < 4: continue
        
        for _ in range(3):
            group = random.sample(d_users, 4)
            session_id = f"group_{fake.uuid4()}"
            generate_session_messages(org_id, session_id, group, 3, 25, short_video_topics)

    # 4. Group Chat - Inter Dept
    for _ in range(10):
        while True:
            group = random.sample(all_users, 4)
            # Ensure at least two different departments
            depts_set = set(users[u]['dept_id'] for u in group)
            if len(depts_set) > 1:
                break
        session_id = f"group_{fake.uuid4()}"
        generate_session_messages(org_id, session_id, group, 3, 25, short_video_topics)

def run_beem_generation():
    print("Generating Beem data...")
    org_id = BEEM_ORG_ID
    all_users = org_users[org_id]
    
    # Beem Depts: 106-113
    all_beem_depts = ['106', '107', '108', '109', '110', '111', '112', '113']
    
    # 1. Single Chat - Intra Dept (All depts)
    for dept_id in all_beem_depts:
        d_users = dept_users.get(dept_id, [])
        if len(d_users) < 2: continue
        
        for _ in range(4):
            pair = random.sample(d_users, 2)
            session_id = f"{min(pair)}_{max(pair)}"
            generate_session_messages(org_id, session_id, pair, 1, 20, enterprise_topics)

    # 2. Single Chat - Inter Dept
    for _ in range(10):
        while True:
            pair = random.sample(all_users, 2)
            u1_dept = users[pair[0]]['dept_id']
            u2_dept = users[pair[1]]['dept_id']
            if u1_dept != u2_dept:
                break
        session_id = f"{min(pair)}_{max(pair)}"
        generate_session_messages(org_id, session_id, pair, 1, 20, enterprise_topics)

    # 3. Group Chat - Intra Dept (All depts)
    # Prompt says "Each L1 dept (including L1 and L2)". Interpreting as ALL depts.
    for dept_id in all_beem_depts:
        d_users = dept_users.get(dept_id, [])
        if len(d_users) < 4: continue
        
        for _ in range(3):
            group = random.sample(d_users, 4)
            session_id = f"group_{fake.uuid4()}"
            generate_session_messages(org_id, session_id, group, 3, 25, enterprise_topics)

    # 4. Group Chat - Inter Dept
    for _ in range(10):
        while True:
            group = random.sample(all_users, 4)
            depts_set = set(users[u]['dept_id'] for u in group)
            if len(depts_set) > 1:
                break
        session_id = f"group_{fake.uuid4()}"
        generate_session_messages(org_id, session_id, group, 3, 25, enterprise_topics)

def write_output():
    print(f"Writing output to {OUTPUT_DIR}...")
    
    # Write Message Table
    msg_file = os.path.join(OUTPUT_DIR, 'ods_im_message_min.txt')
    with open(msg_file, 'w', newline='') as f:
        writer = csv.writer(f, delimiter='\t')
        writer.writerow(['org_id', 'session_id', 'conversation_type', 'message_id', 'from_user_id', 'target_id', 'send_time_ms', 'message_type', 'content'])
        for m in messages:
            writer.writerow([
                m['org_id'],
                m['session_id'],
                m['conversation_type'],
                m['message_id'],
                m['from_user_id'],
                m['target_id'],
                m['send_time_ms'],
                m['message_type'],
                m['content']
            ])
            
    # Write Participant Table
    part_file = os.path.join(OUTPUT_DIR, 'ods_im_session_participant_min.txt')
    with open(part_file, 'w', newline='') as f:
        writer = csv.writer(f, delimiter='\t')
        writer.writerow(['org_id', 'user_id', 'session_ids', 'conversation_types'])
        for key, data in participants.items():
            org_id, user_id = key
            # Hive ARRAY<STRING> usually represented as string with delimiter in text formats, 
            # Prompt says: "hive中的ARRAY类型的字段可以用string,各个元素之间用','分隔"
            session_ids_str = ",".join(data['session_ids'])
            types_str = ",".join(map(str, data['types']))
            
            writer.writerow([org_id, user_id, session_ids_str, types_str])

def main():
    load_data()
    run_jaco_generation()
    run_beem_generation()
    write_output()
    print("Done.")

if __name__ == '__main__':
    main()
