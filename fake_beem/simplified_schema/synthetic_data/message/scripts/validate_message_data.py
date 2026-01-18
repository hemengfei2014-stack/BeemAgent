import os
import csv
import sys
from collections import defaultdict

# Paths
ORG_DATA_DIR = '/root/hemengfei/beemagent/fake_beem/simplified_schema/synthetic_data/org_system/data'
MSG_DATA_DIR = '/root/hemengfei/beemagent/fake_beem/simplified_schema/synthetic_data/message/data'

# Load Org Data
users = {} # uid -> {org_id, dept_id}
depts = {} # did -> {org_id, parent_id, level}
dept_users = defaultdict(list)

def load_org_data():
    print("Loading Org Data...")
    # Depts
    with open(os.path.join(ORG_DATA_DIR, 'dept.txt'), 'r') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            depts[row['id']] = row
    
    # Dept Users (for mapping)
    user_dept = {}
    with open(os.path.join(ORG_DATA_DIR, 'dept_user.txt'), 'r') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            user_dept[row['user_id']] = row['dept_id']
            dept_users[row['dept_id']].append(row['user_id'])

    # Users
    with open(os.path.join(ORG_DATA_DIR, 'user.txt'), 'r') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            uid = row['id']
            users[uid] = {
                'org_id': row['org_id'],
                'dept_id': user_dept.get(uid)
            }
    print(f"Loaded {len(users)} users, {len(depts)} depts.")

def validate_schema_and_constraints():
    print("\nValidating Schema and Basic Constraints...")
    
    msg_file = os.path.join(MSG_DATA_DIR, 'ods_im_message_min.txt')
    part_file = os.path.join(MSG_DATA_DIR, 'ods_im_session_participant_min.txt')
    
    messages = []
    sessions = defaultdict(list) # session_id -> list of messages
    session_meta = {} # session_id -> {org_id, type}
    
    # 1. Validate Message Table
    with open(msg_file, 'r') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for i, row in enumerate(reader):
            # Check fields
            assert 'org_id' in row
            assert 'session_id' in row
            assert 'conversation_type' in row
            
            # Check User existence
            if row['from_user_id'] not in users:
                print(f"Error Line {i+2}: User {row['from_user_id']} not found in Org System")
            
            # Check Org ID consistency
            user_org = users[row['from_user_id']]['org_id']
            if user_org != row['org_id']:
                print(f"Error Line {i+2}: User {row['from_user_id']} belongs to Org {user_org}, but msg has Org {row['org_id']}")
                
            # Check Session ID format
            sess_id = row['session_id']
            conv_type = int(row['conversation_type'])
            if conv_type == 1:
                parts = sess_id.split('_')
                if len(parts) != 2 or parts[0] > parts[1]:
                    # Assuming min_max rule implies parts[0] <= parts[1], strictly min_max usually means parts[0] < parts[1] unless self chat
                    # But IDs are strings, so string comparison
                    pass
                # Check if target_id is correct
                if row['target_id'] == row['from_user_id']:
                    pass # Self chat? Prompt implies 2 different people.
                elif row['target_id'] not in sess_id:
                     print(f"Error Line {i+2}: Single chat target_id {row['target_id']} not in session_id {sess_id}")

            elif conv_type == 3:
                # Target ID should be session ID (Group ID)
                if row['target_id'] != sess_id:
                     print(f"Error Line {i+2}: Group chat target_id {row['target_id']} != session_id {sess_id}")
            
            messages.append(row)
            sessions[sess_id].append(row)
            session_meta[sess_id] = {'org_id': row['org_id'], 'type': conv_type}

    print(f"Validated {len(messages)} messages across {len(sessions)} sessions.")

    # 2. Validate Participant Table
    participants_map = defaultdict(set) # session_id -> set(user_ids)
    
    with open(part_file, 'r') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            uid = row['user_id']
            oid = row['org_id']
            
            # Check User
            if uid not in users:
                print(f"Error Participant: User {uid} not found")
            if users[uid]['org_id'] != oid:
                print(f"Error Participant: User {uid} org mismatch")
                
            # Parse arrays
            s_ids = row['session_ids'].split(',') if row['session_ids'] else []
            types = row['conversation_types'].split(',') if row['conversation_types'] else []
            
            if len(s_ids) != len(types):
                print(f"Error Participant: User {uid} session_ids length != types length")
            
            for sid in s_ids:
                participants_map[sid].add(uid)

    # 3. Cross Validate Participants vs Messages
    for sess_id, msgs in sessions.items():
        # Check if all senders are participants
        senders = set(m['from_user_id'] for m in msgs)
        real_participants = participants_map.get(sess_id, set())
        
        # In Single chat, participants are fixed 2. In Group, all senders must be participants (and maybe silent members)
        if not senders.issubset(real_participants):
            print(f"Error: Session {sess_id} has senders {senders - real_participants} not in participant list")
            
        # Check single chat has exactly 2 participants
        if session_meta[sess_id]['type'] == 1:
            if len(real_participants) != 2:
                print(f"Error: Single chat {sess_id} has {len(real_participants)} participants: {real_participants}")
        
        # Check group chat has 4 participants (as per generation rule)
        if session_meta[sess_id]['type'] == 3:
            if len(real_participants) != 4:
                print(f"Error: Group chat {sess_id} has {len(real_participants)} participants (Expected 4 per prompt)")

    return messages, sessions, participants_map

def validate_business_rules(messages, sessions, participants_map):
    print("\nValidating Business Rules...")
    
    # 1. Message Type Distribution
    type_counts = defaultdict(int)
    for m in messages:
        type_counts[int(m['message_type'])] += 1
    
    total = len(messages)
    print("Message Type Distribution:")
    for t, c in type_counts.items():
        print(f"  Type {t}: {c} ({c/total*100:.2f}%)")
    
    # 2. Conversation Lengths
    print("\nChecking Conversation Lengths...")
    lens = [len(msgs) for msgs in sessions.values()]
    avg_len = sum(lens) / len(lens)
    print(f"  Average Length: {avg_len}")
    print(f"  Min Length: {min(lens)}")
    print(f"  Max Length: {max(lens)}")
    
    # 3. Jaco (Org 1) Generation Logic
    print("\nChecking Jaco (Org 1) Logic...")
    verify_org_logic('1', sessions, participants_map)

    # 4. Beem (Org 2) Generation Logic
    print("\nChecking Beem (Org 2) Logic...")
    verify_org_logic('2', sessions, participants_map)

def verify_org_logic(target_org_id, sessions, participants_map):
    # Filter sessions for this org
    org_sessions = {sid: participants_map[sid] for sid in sessions if sessions[sid][0]['org_id'] == target_org_id}
    
    single_intra_counts = defaultdict(int) # dept_id -> count
    single_inter_count = 0
    group_intra_counts = defaultdict(int)
    group_inter_count = 0
    
    for sid, parts in org_sessions.items():
        # Determine Type
        msg_sample = sessions[sid][0]
        ctype = int(msg_sample['conversation_type'])
        
        # Get Depts of participants
        part_depts = set()
        for uid in parts:
            if uid in users:
                part_depts.add(users[uid]['dept_id'])
        
        is_intra = (len(part_depts) == 1)
        dept_id = list(part_depts)[0] if is_intra else None
        
        if ctype == 1:
            if is_intra:
                single_intra_counts[dept_id] += 1
            else:
                single_inter_count += 1
        elif ctype == 3:
            if is_intra:
                group_intra_counts[dept_id] += 1
            else:
                group_inter_count += 1

    print(f"  Single Inter-Dept Sessions: {single_inter_count} (Expected 10)")
    print(f"  Group Inter-Dept Sessions: {group_inter_count} (Expected 10)")
    
    print("  Single Intra-Dept Sessions per Dept:")
    for d, c in sorted(single_intra_counts.items()):
        if d: print(f"    Dept {d}: {c}")
        
    print("  Group Intra-Dept Sessions per Dept:")
    for d, c in sorted(group_intra_counts.items()):
        if d: print(f"    Dept {d}: {c}")

def main():
    load_org_data()
    messages, sessions, participants_map = validate_schema_and_constraints()
    validate_business_rules(messages, sessions, participants_map)

if __name__ == "__main__":
    main()
