import json
from pathlib import Path

creds_path = Path('serviceAccountKey.json')
if creds_path.exists():
    with open(creds_path) as f:
        creds = json.load(f)
    print(f"Service Account Email: {creds.get('client_email')}")
    print(f"Project ID: {creds.get('project_id')}")
else:
    print('serviceAccountKey.json not found')
