import os
import csv
import sys

# Define constants
ROLE_PM = 1
ROLE_DEV = 2
ROLE_ALGO = 3
ROLE_HR = 4
ROLE_ANDROID = 5
ROLE_IOS = 6
ROLE_QA = 7
ROLE_L2_LEADER = 8
ROLE_L1_LEADER = 9

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "../data")

FILES = {
    'org': os.path.join(DATA_DIR, 'org.txt'),
    'user': os.path.join(DATA_DIR, 'user.txt'),
    'dept': os.path.join(DATA_DIR, 'dept.txt'),
    'dept_user': os.path.join(DATA_DIR, 'dept_user.txt')
}

def load_data(filepath):
    data = []
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            data.append(row)
    return data

def validate():
    print("Starting validation...")
    errors = []

    # Load data
    try:
        orgs = load_data(FILES['org'])
        users = load_data(FILES['user'])
        depts = load_data(FILES['dept'])
        dept_users = load_data(FILES['dept_user'])
    except Exception as e:
        print(f"Failed to load files: {e}")
        return

    # Indexing for quick lookup
    org_map = {o['id']: o for o in orgs}
    user_map = {u['id']: u for u in users}
    dept_map = {d['id']: d for d in depts}
    
    # --- 1. Schema Constraints ---

    # Uniqueness Checks
    user_ids = [u['id'] for u in users]
    if len(user_ids) != len(set(user_ids)):
        errors.append("Duplicate User IDs found.")

    dept_ids = [d['id'] for d in depts]
    if len(dept_ids) != len(set(dept_ids)):
        errors.append("Duplicate Dept IDs found.")

    mobiles = [u['mobile'] for u in users if u['mobile']]
    if len(mobiles) != len(set(mobiles)):
        errors.append("Duplicate Mobiles found.")
    
    emails = [u['email'] for u in users if u['email']]
    if len(emails) != len(set(emails)):
        errors.append("Duplicate Emails found.")

    # Foreign Key Checks
    for u in users:
        if u['org_id'] not in org_map:
            errors.append(f"User {u['id']} has invalid org_id {u['org_id']}")
        if u['manager_id'] and u['manager_id'] not in user_map:
            errors.append(f"User {u['id']} has invalid manager_id {u['manager_id']}")
        if u['role'] and int(u['role']) not in range(1, 10):
            errors.append(f"User {u['id']} has invalid role {u['role']}")
        if u['gender'] and int(u['gender']) not in [0, 1, 2]:
             errors.append(f"User {u['id']} has invalid gender {u['gender']}")

    for d in depts:
        if d['org_id'] not in org_map:
            errors.append(f"Dept {d['id']} has invalid org_id {d['org_id']}")
        if d['parent_id'] and d['parent_id'] not in dept_map:
            errors.append(f"Dept {d['id']} has invalid parent_id {d['parent_id']}")
        if d['leader_id'] and d['leader_id'] not in user_map:
            errors.append(f"Dept {d['id']} has invalid leader_id {d['leader_id']}")
        
        # Level check
        if d['parent_id']:
            parent = dept_map[d['parent_id']]
            expected_level = int(parent['level']) + 1
            if int(d['level']) != expected_level:
                errors.append(f"Dept {d['id']} level mismatch. Expected {expected_level}, got {d['level']}")
        else:
            if int(d['level']) != 1:
                errors.append(f"Dept {d['id']} is root but level is {d['level']}")

    # Dept User Relationships
    user_dept_map = {} # user_id -> dept_id
    for du in dept_users:
        if du['org_id'] not in org_map:
            errors.append(f"DeptUser entry has invalid org_id {du['org_id']}")
        if du['dept_id'] not in dept_map:
            errors.append(f"DeptUser entry has invalid dept_id {du['dept_id']}")
        if du['user_id'] not in user_map:
            errors.append(f"DeptUser entry has invalid user_id {du['user_id']}")
        
        if du['user_id'] in user_dept_map:
             errors.append(f"User {du['user_id']} assigned to multiple departments.")
        user_dept_map[du['user_id']] = du['dept_id']

    # Check all users are in a dept (implied by typical org structure, though not strictly schema enforced, usually good to check)
    # EXCEPTION: Organization Owners (CEOs) might not be in a specific department.
    owner_ids = set(o['owner_user_id'] for o in orgs)
    
    for uid in user_map:
        if uid not in user_dept_map and uid not in owner_ids:
             errors.append(f"User {uid} is not assigned to any department.")

    # --- 2. Business Logic & Generation Requirements ---
    
    # Helper to get dept members
    def get_dept_members(dept_id):
        return [u for u in users if user_dept_map.get(u['id']) == str(dept_id)]

    # Helper to check roles distribution
    def check_roles(members, role_counts, leader_role_expected):
        # role_counts: dict {role_id: count} excluding leader
        # Verify Leader
        leaders = [m for m in members if int(m['role']) == leader_role_expected]
        if len(leaders) != 1:
            return f"Expected 1 leader with role {leader_role_expected}, found {len(leaders)}"
        
        # Verify Members
        actual_counts = {}
        for m in members:
            r = int(m['role'])
            if r == leader_role_expected: continue
            actual_counts[r] = actual_counts.get(r, 0) + 1
        
        for r, count in role_counts.items():
            if actual_counts.get(r, 0) != count:
                return f"Role {r} count mismatch. Expected {count}, got {actual_counts.get(r, 0)}"
        
        # Check for unexpected roles
        expected_roles = set(role_counts.keys())
        actual_roles = set(actual_counts.keys())
        if not actual_roles.issubset(expected_roles):
             return f"Found unexpected roles: {actual_roles - expected_roles}"
        return None

    # === Jaco Validation ===
    jaco = next((o for o in orgs if o['name'] == 'Jaco'), None)
    if not jaco:
        errors.append("Org Jaco not found")
    else:
        if jaco['owner_user_id'] not in user_map:
             errors.append("Jaco CEO not found")
        else:
            ceo = user_map[jaco['owner_user_id']]
            if ceo['name'] != '马云': errors.append(f"Jaco CEO name mismatch: {ceo['name']}")
        
        jaco_depts = [d for d in depts if d['org_id'] == jaco['id']]
        
        # Check Dept Names and Counts
        expected_jaco_depts = {
            "机器学习": {ROLE_DEV: 1, ROLE_ALGO: 8}, # 2 Dev, 8 Algo -> 1 Leader (from Dev), 1 Dev, 8 Algo
            "产品": {ROLE_PM: 9}, # 10 PM -> 1 Leader, 9 PM
            "用户增长": {ROLE_DEV: 1, ROLE_ALGO: 8}, # Same as ML
            "前端": {ROLE_ANDROID: 4, ROLE_IOS: 5}, # 5 Android, 5 iOS -> Leader (Android), 4 And, 5 iOS
            "后端": {ROLE_DEV: 9},
            "人力资源": {ROLE_HR: 9}
        }

        # Validate Depts
        for d_name, expected_roles in expected_jaco_depts.items():
            d = next((d for d in jaco_depts if d['name'] == d_name), None)
            if not d:
                errors.append(f"Jaco dept {d_name} not found")
                continue
            
            if d['parent_id']:
                errors.append(f"Jaco dept {d_name} should be L1")
            
            members = get_dept_members(d['id'])
            if len(members) != 10:
                errors.append(f"Jaco dept {d_name} should have 10 members, found {len(members)}")
            
            # Check Leader Reporting
            leader_id = d['leader_id']
            leader = user_map.get(leader_id)
            if leader:
                if leader['manager_id'] != jaco['owner_user_id']:
                     errors.append(f"Jaco dept {d_name} leader should report to CEO")
            
            # Check Members Reporting
            for m in members:
                if m['id'] != leader_id:
                    if m['manager_id'] != leader_id:
                        errors.append(f"Jaco dept {d_name} member {m['name']} should report to leader")

            # Check Roles
            # Note: For Frontend, the leader could be Android OR iOS depending on random choice or order.
            # My generator logic: `roles` list was [Android]*5 + [iOS]*5. Leader taken from index 0 -> Android.
            # So expected is Leader + 4 Android + 5 iOS.
            
            err = check_roles(members, expected_roles, ROLE_L1_LEADER)
            if err:
                errors.append(f"Jaco dept {d_name} role error: {err}")

    # === Beem Validation ===
    beem = next((o for o in orgs if o['name'] == 'Beem'), None)
    if not beem:
        errors.append("Org Beem not found")
    else:
        if beem['owner_user_id'] not in user_map:
             errors.append("Beem CEO not found")
        else:
            ceo = user_map[beem['owner_user_id']]
            if ceo['name'] != '马化腾': errors.append(f"Beem CEO name mismatch: {ceo['name']}")
        
        beem_depts = [d for d in depts if d['org_id'] == beem['id']]
        
        # L1 Depts
        l1_names = ["产品", "测试", "前端", "后端", "人力资源"]
        l1_depts = [d for d in beem_depts if not d['parent_id']]
        found_l1 = [d['name'] for d in l1_depts]
        if set(l1_names) != set(found_l1):
            errors.append(f"Beem L1 depts mismatch. Expected {l1_names}, found {found_l1}")
            
        # Check specific L1s
        # Frontend has sub-depts, others are flat
        for d in l1_depts:
            if d['name'] == "前端":
                # Should have NO members directly assigned except leader? 
                # Or prompt said: "前端的二级部门有..." 
                # Usually in this schema, users belong to a department. 
                # If Frontend has L2, do users sit in L1?
                # Prompt: "如果一个部门有二级部门：先生成一级部门leader；然后分别生成每个二级部门...每个二级部门5个人...leader向一级部门leader汇报"
                # It does NOT say there are members in L1 Frontend, only the Leader.
                members = get_dept_members(d['id'])
                if len(members) != 1: # Only leader
                     errors.append(f"Beem Frontend (L1) should only have 1 member (Leader), found {len(members)}")
                
                # Check Sub-depts
                sub_depts = [sd for sd in beem_depts if sd['parent_id'] == d['id']]
                sub_names = ["web工程", "ios工程", "Android工程"]
                found_sub = [sd['name'] for sd in sub_depts]
                if set(sub_names) != set(found_sub):
                     errors.append(f"Beem Frontend sub-depts mismatch. Expected {sub_names}, found {found_sub}")
                
                sub_specs = {
                    "web工程": {ROLE_DEV: 4}, # 5 Total -> 1 Leader (8), 4 Dev
                    "ios工程": {ROLE_IOS: 4},
                    "Android工程": {ROLE_ANDROID: 4}
                }

                for sd in sub_depts:
                    if sd['level'] != '2':
                         errors.append(f"Beem sub-dept {sd['name']} level should be 2")
                    
                    smembers = get_dept_members(sd['id'])
                    if len(smembers) != 5:
                         errors.append(f"Beem sub-dept {sd['name']} should have 5 members, found {len(smembers)}")
                    
                    # Leader Reporting
                    sleader_id = sd['leader_id']
                    sleader = user_map.get(sleader_id)
                    if sleader and sleader['manager_id'] != d['leader_id']:
                         errors.append(f"Beem sub-dept {sd['name']} leader should report to L1 Leader")

                    # Role Check
                    spec = sub_specs.get(sd['name'])
                    if spec:
                        err = check_roles(smembers, spec, ROLE_L2_LEADER)
                        if err: errors.append(f"Beem sub-dept {sd['name']} role error: {err}")

            else:
                # Flat L1
                members = get_dept_members(d['id'])
                if len(members) != 10:
                    errors.append(f"Beem dept {d['name']} should have 10 members, found {len(members)}")
                
                # Reporting
                leader_id = d['leader_id']
                leader = user_map.get(leader_id)
                if leader and leader['manager_id'] != beem['owner_user_id']:
                     errors.append(f"Beem dept {d['name']} leader should report to CEO")

                # Roles
                specs = {
                    "产品": {ROLE_PM: 9},
                    "测试": {ROLE_QA: 9},
                    "后端": {ROLE_DEV: 9},
                    "人力资源": {ROLE_HR: 9}
                }
                if d['name'] in specs:
                    err = check_roles(members, specs[d['name']], ROLE_L1_LEADER)
                    if err: errors.append(f"Beem dept {d['name']} role error: {err}")

    # Final Report
    if errors:
        print("\n=== VALIDATION FAILED ===")
        for e in errors:
            print(f"- {e}")
        sys.exit(1)
    else:
        print("\n=== VALIDATION SUCCESS ===")
        print("All data conforms to schema and requirements.")

if __name__ == "__main__":
    validate()
