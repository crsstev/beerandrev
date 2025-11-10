import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

AMP_URL = "https://amp.beerandrevolution.net"
AMP_USER = os.getenv('AMP_USER')
AMP_PASS = os.getenv('AMP_PASS')

# Disable SSL warnings
requests.packages.urllib3.disable_warnings()

def login():
    """Login to AMP and return session"""
    url = f"{AMP_URL}/API/Core/Login"
    headers = {
        "Accept": "application/json",
    }
    payload = {
        "username": AMP_USER,
        "password": AMP_PASS,
        "token": "",
        "rememberMe": False
    }
    
    response = requests.post(url, json=payload, headers=headers, verify=False)
    print(f"Login response: {response.status_code}")
    return response

def get_instances(session_id):
    """Get all game server instances"""
    url = f"{AMP_URL}/API/ADSModule/GetInstances"
    headers = {
        "Accept": "application/json",
        "Cookie": f"SessionID={session_id}"
    }
    payload = {}
    
    response = requests.post(url, json=payload, headers=headers, verify=False)
    print(f"GetInstances response: {response.status_code}")
    return response

# Login
login_resp = login()
login_data = login_resp.json()
print(f"\nLogin Response:\n{json.dumps(login_data, indent=2)}")

if login_resp.status_code == 200 and 'SessionID' in login_resp.cookies:
    session_id = login_resp.cookies['SessionID']
    print(f"\n✅ Logged in with SessionID: {session_id}\n")
    
    # Get instances
    instances_resp = get_instances(session_id)
    instances_data = instances_resp.json()
    print(f"\nGetInstances Response:\n{json.dumps(instances_data, indent=2)}")
else:
    print("❌ Login failed!")
