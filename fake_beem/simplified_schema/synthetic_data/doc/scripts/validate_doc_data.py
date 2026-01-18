
import os
import csv
import sys

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOC_FILE = os.path.join(BASE_DIR, '../data/ods_docs_min.txt')
ACCESS_FILE = os.path.join(BASE_DIR, '../data/dwd_user_doc_access_min.txt')
ORG_DATA_DIR = os.path.join(BASE_DIR, "../../org_system/data")
USER_FILE = os.path.join(ORG_DATA_DIR, 'user.txt')
ORG_FILE = os.path.join(ORG_DATA_DIR, 'org.txt')

# Colors for output
GREEN = '\033[92m'
RED = '\033[91m'
RESET = '\033[0m'

def log_success(msg):
    print(f"{GREEN}[PASS]{RESET} {msg}")

def log_error(msg):
    print(f"{RED}[FAIL]{RESET} {msg}")
    return False

def load_tsv(filepath):
    data = []
    with open(filepath, 'r') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            data.append(row)
    return data

def validate():
    all_passed = True
    
    print("Loading data...")
    try:
        docs = load_tsv(DOC_FILE)
        access_list = load_tsv(ACCESS_FILE)
        users = load_tsv(USER_FILE)
        orgs = load_tsv(ORG_FILE)
    except Exception as e:
        log_error(f"Failed to load files: {e}")
        return

    # Helper maps
    user_map = {u['id']: u for u in users}
    org_ids = set(o['id'] for o in orgs)
    doc_map = {d['doc_id']: d for d in docs}
    
    # 1. Validate ods_docs_min
    print("\nValidating ods_docs_min...")
    valid_ctypes = {'doc', 'sheet', 'slide', 'pdf'}
    
    for i, doc in enumerate(docs):
        # Schema checks
        if not doc['doc_id']:
            all_passed = log_error(f"Row {i}: Missing doc_id")
        if doc['org_id'] not in org_ids:
            all_passed = log_error(f"Row {i}: Invalid org_id {doc['org_id']}")
        if doc['owner'] not in user_map:
            all_passed = log_error(f"Row {i}: Owner {doc['owner']} not found in user table")
        elif user_map[doc['owner']]['org_id'] != doc['org_id']:
            all_passed = log_error(f"Row {i}: Owner {doc['owner']} org ({user_map[doc['owner']]['org_id']}) mismatch doc org ({doc['org_id']})")
        
        if doc['ctype'] not in valid_ctypes:
            all_passed = log_error(f"Row {i}: Invalid ctype {doc['ctype']}")
            
        try:
            int(doc['create_time'])
        except ValueError:
            all_passed = log_error(f"Row {i}: Invalid create_time {doc['create_time']}")

    log_success(f"Checked {len(docs)} documents.")

    # 2. Validate dwd_user_doc_access_min
    print("\nValidating dwd_user_doc_access_min...")
    
    # Build a map of who can access what for cross-check
    # doc_id -> set(user_ids)
    doc_access_map = {} 
    
    for i, row in enumerate(access_list):
        uid = row['user_id']
        u_org = row['user_org_id']
        doc_ids_str = row['doc_ids']
        
        # User validation
        if uid not in user_map:
            all_passed = log_error(f"Row {i}: User {uid} not found")
        else:
            if user_map[uid]['org_id'] != u_org:
                all_passed = log_error(f"Row {i}: User {uid} org mismatch. Table: {u_org}, Real: {user_map[uid]['org_id']}")
        
        # Access list validation
        if doc_ids_str:
            dids = doc_ids_str.split(',')
            for did in dids:
                if did not in doc_map:
                    all_passed = log_error(f"Row {i}: User {uid} has access to non-existent doc {did}")
                    continue
                
                target_doc = doc_map[did]
                
                # Tenant Isolation Check
                if target_doc['org_id'] != u_org:
                    all_passed = log_error(f"Row {i}: Cross-tenant access detected. User {uid} ({u_org}) accessing Doc {did} ({target_doc['org_id']})")
                
                # Record for reverse check
                if did not in doc_access_map:
                    doc_access_map[did] = set()
                doc_access_map[did].add(uid)

    log_success(f"Checked access records for {len(access_list)} users.")

    # 3. Business Rule: Owner MUST have access
    print("\nValidating Business Rules (Owner Access)...")
    for doc in docs:
        did = doc['doc_id']
        owner = doc['owner']
        
        if did not in doc_access_map or owner not in doc_access_map[did]:
            all_passed = log_error(f"Doc {did}: Owner {owner} does not have access in dwd_user_doc_access_min")
            
    log_success("Owner access check complete.")

    if all_passed:
        print(f"\n{GREEN}All Validations Passed!{RESET}")
    else:
        print(f"\n{RED}Validation Failed with errors.{RESET}")
        sys.exit(1)

if __name__ == "__main__":
    validate()
