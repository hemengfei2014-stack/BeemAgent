import os
import random
import time
import uuid
from datetime import datetime, timedelta
from faker import Faker

# Constants
BASE_DIR = '/Users/hemengfei/company/work/beemagent/fake_beem/simplified_schema/synthetic_data'
USER_FILE = os.path.join(BASE_DIR, 'org_system/data/user.txt')
OUTPUT_FILE = os.path.join(BASE_DIR, 'calendar/data/calendar_event.txt')

fake = Faker('zh_CN')

def load_users():
    jaco_users = []
    beem_users = []
    
    with open(USER_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        # Skip header
        headers = lines[0].strip().split('\t')
        try:
            org_id_idx = headers.index('org_id')
            user_id_idx = headers.index('id')
        except ValueError:
            # Fallback if header parsing fails, assuming standard order based on previous `cat`
            # id org_id name ...
            user_id_idx = 0
            org_id_idx = 1
            
        for line in lines[1:]:
            parts = line.strip().split('\t')
            if len(parts) < 2:
                continue
            
            user_id = parts[user_id_idx]
            org_id = parts[org_id_idx]
            
            if org_id == '1':
                jaco_users.append(user_id)
            elif org_id == '2':
                beem_users.append(user_id)
                
    return jaco_users, beem_users

def generate_time_window(category):
    now = datetime.now()
    if category == 'gt_3m':
        # 3 months to 6 months ago
        start = now - timedelta(days=180)
        end = now - timedelta(days=90)
    elif category == '2_3m':
        # 2 to 3 months ago
        start = now - timedelta(days=90)
        end = now - timedelta(days=60)
    elif category == 'lt_1m':
        # Past month
        start = now - timedelta(days=30)
        end = now
    elif category == 'future':
        # Future 1 week
        start = now
        end = now + timedelta(days=7)
    else:
        start = now
        end = now
        
    random_start = fake.date_time_between(start_date=start, end_date=end)
    # Duration ~1 hour (between 45 min and 75 min)
    duration_minutes = random.randint(45, 75)
    random_end = random_start + timedelta(minutes=duration_minutes)
    
    return int(random_start.timestamp() * 1000), int(random_end.timestamp() * 1000)

def generate_events(users, org_name, count, time_categories):
    events = []
    
    # Topics
    if org_name == 'Jaco':
        topics = ['短视频', '直播', '网红', '流量', '算法', '推荐', '拍摄', '剪辑', '特效', '滤镜', '粉丝', '互动', '变现', '带货', '内容', '创作', '平台', '审核', '运营', '推广']
        suffix = '讨论会'
    else: # Beem
        topics = ['协同', '办公', '文档', '会议', '即时通讯', '云盘', '审批', '考勤', 'OKR', '绩效', '组织架构', '权限', '安全', 'API', '集成', 'SaaS', '私有化', '部署', '客户', '服务']
        suffix = '沟通会'

    for i in range(count):
        # Determine time category
        category = time_categories[i % len(time_categories)]
        start_time, end_time = generate_time_window(category)
        
        # Organizer
        organizer = random.choice(users)
        
        # Participants (10 unique users)
        # Ensure we don't pick the organizer again if possible, but list says 10 people.
        # Assuming organizer is NOT in participants list or IS? Schema says "participatns list". Usually includes others.
        possible_participants = [u for u in users if u != organizer]
        if len(possible_participants) < 10:
             participants_list = possible_participants # Take all if not enough
        else:
            participants_list = random.sample(possible_participants, 10)
            
        participants_str = ",".join(participants_list)
        
        # Subject
        topic = random.choice(topics)
        # Generate a subject ~20 chars
        # Using faker to generate some text and combining with topic
        # increased word count to get closer to 20 chars
        extra_text = fake.sentence(nb_words=6, variable_nb_words=True)
        # Clean up punctuation
        extra_text = extra_text.replace('.', '').replace('。', '')
        subject = f"关于{topic}的{extra_text}{suffix}"
        # Truncate or pad to be around 20 chars visually (not strict byte count)
        if len(subject) > 30:
            subject = subject[:30]
        
        event_id = uuid.uuid4().hex
        
        events.append({
            'event_id': event_id,
            'subject': subject,
            'start_time': start_time,
            'end_time': end_time,
            'organizer_id': organizer,
            'participants': participants_str
        })
        
    return events

def main():
    jaco_users, beem_users = load_users()
    print(f"Loaded {len(jaco_users)} Jaco users and {len(beem_users)} Beem users.")
    
    # Time distribution for 20 events:
    # 30% = 6
    # 30% = 6
    # 30% = 6
    # 10% = 2
    categories = ['gt_3m'] * 6 + ['2_3m'] * 6 + ['lt_1m'] * 6 + ['future'] * 2
    random.shuffle(categories)
    
    jaco_events = generate_events(jaco_users, 'Jaco', 20, categories)
    beem_events = generate_events(beem_users, 'Beem', 20, categories) # Re-use shuffled categories or shuffle again? 
    # Let's shuffle again for randomness
    random.shuffle(categories)
    beem_events = generate_events(beem_users, 'Beem', 20, categories)
    
    all_events = jaco_events + beem_events
    
    # Write to file
    header = ['event_id', 'subject', 'start_time', 'end_time', 'organizer_id', 'participants']
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        # Write header
        f.write('\t'.join(header) + '\n')
        
        for event in all_events:
            row = [
                str(event['event_id']),
                str(event['subject']),
                str(event['start_time']),
                str(event['end_time']),
                str(event['organizer_id']),
                str(event['participants'])
            ]
            f.write('\t'.join(row) + '\n')
            
    print(f"Successfully generated {len(all_events)} events to {OUTPUT_FILE}")

if __name__ == '__main__':
    main()
