import requests
import os
from dotenv import load_dotenv

load_dotenv()

JIRA_DOMAIN = os.environ.get("JIRA_DOMAIN")
JIRA_EMAIL = os.environ.get("JIRA_EMAIL")
JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN")
BASE_URL = f"https://{JIRA_DOMAIN}/rest/api/3"
AUTH = (JIRA_EMAIL, JIRA_API_TOKEN)
HEADERS = {"Accept": "application/json", "Content-Type": "application/json"}

def create_filter(name, jql, description="Created via API"):
    url = f"{BASE_URL}/filter"
    payload = {
        "name": name,
        "jql": jql,
        "description": description,
        "favourite": False
    }
    response = requests.post(url, json=payload, auth=AUTH, headers=HEADERS)
    print(f"[SUCCESS] Created filter '{name}' (ID: {response.json()['id']})")
    return response.json()

def find_filter_by_name(name):
    url = f"{BASE_URL}/filter/search?filterName={name}"
    response = requests.get(url, auth=AUTH, headers=HEADERS)
    if response.status_code == 200:
        filters = response.json().get("values", [])
        for f in filters:
            if f["name"] == name:
                return f["id"]
    return None

def update_filter_jql(filter_id, new_jql):
    url = f"{BASE_URL}/filter/{filter_id}"
    payload = {"jql": new_jql}
    response = requests.put(url, json=payload, auth=AUTH, headers=HEADERS)
    if response.status_code == 200:
        print(f"[UPDATE] Updated filter {filter_id} JQL.")
    else:
        print(f"[ERROR] Failed to update filter {filter_id}: {response.status_code} - {response.text}")

def create_or_update_filter(name, jql):
    filter_id = find_filter_by_name(name)
    if filter_id:
        update_filter_jql(filter_id, jql)
    else:
        create_filter(name, jql)

if __name__ == "__main__":
    filters_to_create = [
        {"name": "Temp2", "jql": 'project = DS AND labels= SVB'},
        {"name": "Temp3", "jql": 'project=DS AND labels=JTAMP'}
    ]

    for f in filters_to_create:
        create_or_update_filter(f["name"], f["jql"])