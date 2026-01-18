
import os
import csv
import json
import datetime

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOC_DIR = os.path.join(BASE_DIR, '../data')
ORG_DATA_DIR = os.path.join(BASE_DIR, "../../org_system/data")
OUTPUT_FILE = os.path.join(BASE_DIR, '../web/doc_data.json')

def load_data():
    data = {
        'orgs': {},
        'users': {},
        'docs': []
    }
    
    # 1. Load Orgs
    with open(os.path.join(ORG_DATA_DIR, 'org.txt'), 'r') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            data['orgs'][row['id']] = row['name']
            
    # 2. Load Users
    with open(os.path.join(ORG_DATA_DIR, 'user.txt'), 'r') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            data['users'][row['id']] = {
                'name': row['name'],
                'org_id': row['org_id']
            }
            
    # 3. Load Access Data (User -> DocIDs)
    # We need to reverse this to Doc -> UserIDs
    doc_access_map = {} # doc_id -> set(user_ids)
    
    with open(os.path.join(DOC_DIR, 'dwd_user_doc_access_min.txt'), 'r') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            user_id = row['user_id']
            doc_ids = row['doc_ids'].split(',') if row['doc_ids'] else []
            for did in doc_ids:
                if did not in doc_access_map:
                    doc_access_map[did] = set()
                doc_access_map[did].add(user_id)
                
    # 4. Load Docs
    with open(os.path.join(DOC_DIR, 'ods_docs_min.txt'), 'r') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            doc_id = row['doc_id']
            
            # Get access list
            access_uids = list(doc_access_map.get(doc_id, []))
            
            doc_item = {
                'org_id': row['org_id'],
                'doc_id': doc_id,
                'create_time': int(row['create_time']),
                'create_time_str': datetime.datetime.fromtimestamp(int(row['create_time'])).strftime('%Y-%m-%d %H:%M:%S'),
                'ctype': row['ctype'],
                'title': row['title'],
                'note': row['note'],
                'owner': row['owner'],
                'access_list': access_uids
            }
            data['docs'].append(doc_item)
            
    # Sort docs by time desc
    data['docs'].sort(key=lambda x: x['create_time'], reverse=True)
    
    return data

def main():
    print("Converting Doc data to JSON...")
    data = load_data()
    
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Data saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
