import csv
import json
import os
import datetime

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "../data")
WEB_DIR = os.path.join(BASE_DIR, "../web")
if not os.path.exists(WEB_DIR):
    os.makedirs(WEB_DIR)

FILES = {
    'org': os.path.join(DATA_DIR, 'org.txt'),
    'user': os.path.join(DATA_DIR, 'user.txt'),
    'dept': os.path.join(DATA_DIR, 'dept.txt'),
    'dept_user': os.path.join(DATA_DIR, 'dept_user.txt')
}
OUTPUT_FILE = os.path.join(WEB_DIR, 'org_data.json')

# Role Mapping
ROLE_MAP = {
    '1': 'Product Manager',
    '2': 'Development Engineer',
    '3': 'Algorithm Engineer',
    '4': 'HR',
    '5': 'Android Engineer',
    '6': 'iOS Engineer',
    '7': 'QA Engineer',
    '8': 'L2 Dept Leader',
    '9': 'L1 Dept Leader'
}

GENDER_MAP = {
    '1': 'Male',
    '2': 'Female',
    '0': 'Unknown'
}

def load_data(filepath):
    data = []
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            data.append(row)
    return data

def timestamp_to_date(ts):
    if not ts: return ""
    return datetime.datetime.fromtimestamp(int(ts)).strftime('%Y-%m-%d')

def process_data():
    orgs = load_data(FILES['org'])
    users = load_data(FILES['user'])
    depts = load_data(FILES['dept'])
    dept_users = load_data(FILES['dept_user'])

    # Maps for easy access
    user_map = {u['id']: u for u in users}
    dept_map = {d['id']: d for d in depts}
    
    # Enrich user data
    for u in users:
        u['role_name'] = ROLE_MAP.get(u['role'], 'Employee')
        u['gender_name'] = GENDER_MAP.get(u['gender'], 'Unknown')
        u['join_date_str'] = timestamp_to_date(u['join_date'])
        u['birthday_str'] = timestamp_to_date(u['birthday'])
        
        # Add manager name
        if u['manager_id'] and u['manager_id'] in user_map:
            u['manager_name'] = user_map[u['manager_id']]['name']
        else:
            u['manager_name'] = "None"

    # Group users by dept
    # Note: A user belongs to one dept in this schema based on dept_user table
    dept_members = {} # dept_id -> list of users
    for du in dept_users:
        did = du['dept_id']
        uid = du['user_id']
        if uid in user_map:
            if did not in dept_members:
                dept_members[did] = []
            dept_members[did].append(user_map[uid])

    # Build Tree for each Org
    result = []

    for org in orgs:
        org_id = org['id']
        org_data = {
            "id": org_id,
            "name": org['name'],
            "ceo": None,
            "depts": []
        }

        # Find CEO
        if org['owner_user_id'] in user_map:
            org_data['ceo'] = user_map[org['owner_user_id']]
            # CEO role display fix if needed
            org_data['ceo']['role_name'] = "CEO"

        # Find L1 Depts
        l1_depts = [d for d in depts if d['org_id'] == org_id and (not d['parent_id'] or d['parent_id'] == "")]
        
        # Sort L1 depts by name (optional, but good for consistency)
        # However, requirements say: "点开一级部门...二级部门名称按照字母顺序展开"
        # Let's sort L1s too.
        l1_depts.sort(key=lambda x: x['name'])

        for d in l1_depts:
            d_obj = {
                "id": d['id'],
                "name": d['name'],
                "leader": None,
                "members": [],
                "sub_depts": [],
                "has_sub_depts": False
            }

            # Get Leader
            if d['leader_id'] in user_map:
                d_obj['leader'] = user_map[d['leader_id']]

            # Check for L2 Depts
            l2_depts = [sd for sd in depts if sd['parent_id'] == d['id']]
            
            if l2_depts:
                d_obj['has_sub_depts'] = True
                l2_depts.sort(key=lambda x: x['name'])
                
                for sd in l2_depts:
                    sd_obj = {
                        "id": sd['id'],
                        "name": sd['name'],
                        "leader": None,
                        "members": []
                    }
                    
                    if sd['leader_id'] in user_map:
                        sd_obj['leader'] = user_map[sd['leader_id']]
                    
                    # Members of L2
                    raw_members = dept_members.get(sd['id'], [])
                    # Filter out leader from members list to avoid duplication if requirements imply distinct lists
                    # Req: "排在第一个的是二级部门leader，二级部门组员用户名按照字母顺序展开"
                    # Usually means Leader is shown at top, then others. 
                    # We will separate them in JSON.
                    
                    m_list = [m for m in raw_members if m['id'] != sd['leader_id']]
                    m_list.sort(key=lambda x: x['name'])
                    sd_obj['members'] = m_list
                    
                    d_obj['sub_depts'].append(sd_obj)
            else:
                # No L2 depts, just members
                raw_members = dept_members.get(d['id'], [])
                m_list = [m for m in raw_members if m['id'] != d['leader_id']]
                m_list.sort(key=lambda x: x['name'])
                d_obj['members'] = m_list

            org_data['depts'].append(d_obj)
        
        result.append(org_data)

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"JSON data generated at {OUTPUT_FILE}")

if __name__ == "__main__":
    process_data()
