import csv
import json
import os
import datetime

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "../data")
ORG_DATA_DIR = os.path.join(BASE_DIR, "../../org_system/data")
WEB_DIR = os.path.join(BASE_DIR, "../web")

if not os.path.exists(WEB_DIR):
    os.makedirs(WEB_DIR)

FILES = {
    'calendar_event': os.path.join(DATA_DIR, 'calendar_event.txt'),
    'user': os.path.join(ORG_DATA_DIR, 'user.txt'),
    'org': os.path.join(ORG_DATA_DIR, 'org.txt')
}
OUTPUT_FILE = os.path.join(WEB_DIR, 'calendar_data.json')

def load_data(filepath):
    data = []
    if not os.path.exists(filepath):
        print(f"Warning: File not found: {filepath}")
        return []
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            data.append(row)
    return data

def timestamp_to_date(ts):
    if not ts: return ""
    try:
        # Assuming ms timestamp
        dt = datetime.datetime.fromtimestamp(int(ts) / 1000)
        return dt.strftime('%Y-%m-%d %H:%M')
    except:
        return ts

def process_data():
    events = load_data(FILES['calendar_event'])
    users = load_data(FILES['user'])
    orgs = load_data(FILES['org'])
    
    # Maps
    user_map = {u['id']: u for u in users}
    org_map = {o['id']: o for o in orgs}
    
    # Process events
    processed_events = []
    
    for event in events:
        organizer_id = event['organizer_id']
        organizer = user_map.get(organizer_id, {})
        organizer_name = organizer.get('name', 'Unknown')
        
        # Determine Org (from organizer)
        org_id = organizer.get('org_id')
        org_name = org_map.get(org_id, {}).get('name', 'Unknown')
        
        # Participants
        participant_ids = event['participants'].split(',')
        participant_names = []
        for pid in participant_ids:
            pid = pid.strip()
            if pid in user_map:
                participant_names.append(user_map[pid]['name'])
            else:
                participant_names.append(pid)
        
        processed_events.append({
            'event_id': event['event_id'],
            'subject': event['subject'],
            'start_time': timestamp_to_date(event['start_time']),
            'end_time': timestamp_to_date(event['end_time']),
            'start_ts': int(event['start_time']), # Keep for sorting
            'organizer_id': organizer_id,
            'organizer_name': organizer_name,
            'org_name': org_name,
            'org_id': org_id,
            'participants': participant_names,
            'participant_count': len(participant_names)
        })
        
    # Sort by start time descending
    processed_events.sort(key=lambda x: x['start_ts'], reverse=True)
    
    # Group by Org for the UI tabs
    # Or just return flat list and let UI filter. 
    # Let's return a structure similar to org_system: list of Orgs containing events?
    # Or just a flat list? Org system returns list of Orgs.
    # Let's group by Org.
    
    grouped_data = {}
    for ev in processed_events:
        oid = ev['org_id']
        oname = ev['org_name']
        if not oid: continue
        
        if oid not in grouped_data:
            grouped_data[oid] = {
                'id': oid,
                'name': oname,
                'events': []
            }
        grouped_data[oid]['events'].append(ev)
        
    result = list(grouped_data.values())
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
        
    print(f"Generated {OUTPUT_FILE} with {len(processed_events)} events.")

if __name__ == '__main__':
    process_data()
