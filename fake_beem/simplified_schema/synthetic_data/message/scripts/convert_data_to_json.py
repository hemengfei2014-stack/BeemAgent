import os
import csv
import json
from collections import defaultdict

# Paths
ORG_DATA_DIR = '/root/hemengfei/beemagent/fake_beem/simplified_schema/synthetic_data/org_system/data'
MSG_DATA_DIR = '/root/hemengfei/beemagent/fake_beem/simplified_schema/synthetic_data/message/data'
OUTPUT_FILE = '/root/hemengfei/beemagent/fake_beem/simplified_schema/synthetic_data/message/web/message_data.json'

def load_data():
    data = {
        'users': {},
        'sessions': {},
        'orgs': {}
    }
    
    # Load Orgs
    with open(os.path.join(ORG_DATA_DIR, 'org.txt'), 'r') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            data['orgs'][row['id']] = row['name']

    # Load Users (for names and avatars)
    with open(os.path.join(ORG_DATA_DIR, 'user.txt'), 'r') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            data['users'][row['id']] = {
                'name': row['name'],
                'org_id': row['org_id']
            }

    # Load Messages
    # Structure: sessions -> session_id -> {meta, messages: []}
    with open(os.path.join(MSG_DATA_DIR, 'ods_im_message_min.txt'), 'r') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            sid = row['session_id']
            if sid not in data['sessions']:
                data['sessions'][sid] = {
                    'org_id': row['org_id'],
                    'session_id': sid,
                    'type': int(row['conversation_type']),
                    'participants': set(),
                    'messages': []
                }
            
            # Add message
            data['sessions'][sid]['messages'].append({
                'id': row['message_id'],
                'from': row['from_user_id'],
                'time': int(row['send_time_ms']),
                'type': int(row['message_type']),
                'content': row['content']
            })
            
            # Infer participants from sender (will be enriched by participant table)
            data['sessions'][sid]['participants'].add(row['from_user_id'])

    # Load Participants (to get full list including silent members)
    with open(os.path.join(MSG_DATA_DIR, 'ods_im_session_participant_min.txt'), 'r') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            uid = row['user_id']
            sids = row['session_ids'].split(',') if row['session_ids'] else []
            for sid in sids:
                if sid in data['sessions']:
                    data['sessions'][sid]['participants'].add(uid)

    # Convert sets to lists and sort messages
    for sid in data['sessions']:
        data['sessions'][sid]['participants'] = list(data['sessions'][sid]['participants'])
        data['sessions'][sid]['messages'].sort(key=lambda x: x['time'])
        
        # Add a title for the session
        s = data['sessions'][sid]
        if s['type'] == 1:
            # Single chat: "UserA & UserB"
            names = [data['users'][u]['name'] for u in s['participants'] if u in data['users']]
            s['title'] = " & ".join(names)
        else:
            # Group chat
            s['title'] = f"Group Chat ({len(s['participants'])} people)"

    return data

def main():
    print("Converting data to JSON...")
    data = load_data()
    
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Data saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
