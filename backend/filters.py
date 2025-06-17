import sys
import os
import requests
from dotenv import load_dotenv

load_dotenv()

JIRA_DOMAIN = os.environ.get("JIRA_DOMAIN")
JIRA_EMAIL = os.environ.get("JIRA_EMAIL")
JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN")
BASE_URL = f"https://{JIRA_DOMAIN}/rest/api/3"
AUTH = (JIRA_EMAIL, JIRA_API_TOKEN)
HEADERS = {"Accept": "application/json", "Content-Type": "application/json"}

def get_filter_by_name(name):
    url = f"{BASE_URL}/filter/search?filterName={name}"
    response = requests.get(url, auth=AUTH, headers=HEADERS)
    if response.status_code == 200:
        filters = response.json().get("values", [])
        for f in filters:
            if f["name"] == name:
                return f
    return None

def get_filter_jql_by_id(filter_id):
    url = f"{BASE_URL}/filter/{filter_id}"
    response = requests.get(url, auth=AUTH, headers=HEADERS)
    if response.status_code == 200:
        return response.json().get("jql")
    return None

def get_issues_for_jql(jql):
    url = f"{BASE_URL}/search"
    params = {"jql": jql, "maxResults": 1000}
    response = requests.get(url, params=params, auth=AUTH, headers=HEADERS)
    if response.status_code == 200:
        return [issue["key"] for issue in response.json().get("issues", [])]
    return []

def delete_issue(issue_key):
    url = f"{BASE_URL}/issue/{issue_key}"
    response = requests.delete(url, auth=AUTH, headers=HEADERS)
    return response.status_code == 204

def create_filter(name, jql):
    url = f"{BASE_URL}/filter"
    payload = {"name": name, "jql": jql, "favourite": False}
    response = requests.post(url, json=payload, auth=AUTH, headers=HEADERS)
    if response.status_code == 201:
        print("Filter created!")
        return True
    else:
        print("Failed to create filter:", response.status_code, response.text, file=sys.stderr)
        return False

def update_filter_jql(filter_id, new_jql):
    url = f"{BASE_URL}/filter/{filter_id}"
    payload = {"jql": new_jql}
    response = requests.put(url, json=payload, auth=AUTH, headers=HEADERS)
    if response.status_code == 200:
        print("Filter JQL updated!")
        return True
    else:
        print("Failed to update filter:", response.status_code, response.text, file=sys.stderr)
        return False

def create_or_update_filter(name, jql):
    existing = get_filter_by_name(name)
    if existing:
        return update_filter_jql(existing["id"], jql)
    else:
        return create_filter(name, jql)

if __name__ == "__main__":
    if '--remove' in sys.argv:
        identifier = sys.argv[sys.argv.index('--remove') + 1]
        if identifier.isdigit():
            filter_id = identifier
        elif '-' not in identifier:
            filter_obj = get_filter_by_name(identifier)
            if not filter_obj:
                print(f"Filter with name '{identifier}' not found.", file=sys.stderr)
                sys.exit(1)
            filter_id = str(filter_obj["id"])
        elif '-' in identifier:
            issue_key = identifier
            if delete_issue(issue_key):
                print(f"Deleted {issue_key}")
                sys.exit(0)
            else:
                print(f"Failed to delete {issue_key}", file=sys.stderr)
                sys.exit(1)
        else:
            print("Invalid identifier for deletion. Provide a filter ID, filter name, or issue key (e.g., PROJ-123).", file=sys.stderr)
            sys.exit(1)

        jql = get_filter_jql_by_id(filter_id)
        if not jql:
            print("Could not retrieve JQL for filter", file=sys.stderr)
            sys.exit(1)
        issues = get_issues_for_jql(jql)
        print(f"Found {len(issues)} issues to delete.")
        for key in issues:
            if delete_issue(key):
                print(f"Deleted {key}")
            else:
                print(f"Failed to delete {key}", file=sys.stderr)
        print("Done.")
        sys.exit(0)
    elif len(sys.argv) >= 3:
        name = sys.argv[1]
        jql = sys.argv[2]
        create_or_update_filter(name, jql)
    else:
        print("Name and JQL required", file=sys.stderr)
        sys.exit(1)