import os
import requests
import pandas as pd
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()

JIRA_DOMAIN = os.environ["JIRA_DOMAIN"]
JIRA_EMAIL = os.environ["JIRA_EMAIL"]
JIRA_API_TOKEN = os.environ["JIRA_API_TOKEN"]

PLATFORMS = {"JTAMP", "JTAES", "JTAEN", "SVB"}
STATUSES = {"TARGET", "PASS", "FAIL", "UNRESOLVED"}

BASE_URL = f"https://{JIRA_DOMAIN}/rest/api/3"
AUTH = (JIRA_EMAIL, JIRA_API_TOKEN)
HEADERS = {"Accept": "application/json", "Content-Type": "application/json"}

def get_project_statuses(project_key):
    url = f"{BASE_URL}/project/{project_key}/statuses"
    response = requests.get(url, auth=AUTH, headers=HEADERS)
    response.raise_for_status()
    statuses = []
    for issue_type in response.json():
        for status in issue_type.get("statuses", []):
            statuses.append(status["name"])
    return list(set(statuses))

def find_filter_id_by_name(filter_name):
    url = f"{BASE_URL}/filter/search?filterName={filter_name}"
    response = requests.get(url, auth=AUTH, headers=HEADERS)
    if response.status_code == 200:
        filters = response.json().get("values", [])
        for f in filters:
            if f.get("name", "") == filter_name:
                return f.get("id")
    return None

def create_filter(filter_name, jql, description=""):
    url = f"{BASE_URL}/filter"
    payload = {
        "name": filter_name,
        "jql": jql,
        "description": description,
        "favourite": False
    }
    response = requests.post(url, json=payload, auth=AUTH, headers=HEADERS)
    
    if response.status_code == 201:
        return response.json().get("id")
    elif response.status_code == 400 and "A filter with this name already exists" in response.text:
        return find_filter_id_by_name(filter_name)
    else:
        print(f"Failed to create filter '{filter_name}':", response.status_code, response.text)
        existing_id = find_filter_id_by_name(filter_name)
        if existing_id:
            return existing_id
        return None

def ensure_selected_status_filters(project_key):
    statuses = get_project_statuses(project_key)
    status_map = {
        "Pass": "Pass",
        "Fail": "Fail",
        "Target": None,  
        "Unresolved": ["To Do", "In Progress"] 
    }
    filter_ids = {}

    filter_name = "overall_status_filter_Target"
    jql = f'project = "{project_key}"'
    filter_id = find_filter_id_by_name(filter_name)
    if not filter_id:
        filter_id = create_filter(
            filter_name,
            jql,
            description="Auto-created filter for all issues (Target)"
        )
        print(f"Created filter '{filter_name}' with ID {filter_id}")
    else:
        print(f"Filter '{filter_name}' already exists with ID {filter_id}")
    filter_ids["Target"] = filter_id


    for key in ["Pass", "Fail"]:
        if status_map[key] in statuses:
            filter_name = f"overall_status_filter_{key}"
            jql = f'project = "{project_key}" AND status = "{status_map[key]}"'
            filter_id = find_filter_id_by_name(filter_name)
            if not filter_id:
                filter_id = create_filter(
                    filter_name,
                    jql,
                    description=f"Auto-created filter for status '{status_map[key]}'"
                )
                print(f"Created filter '{filter_name}' with ID {filter_id}")
            else:
                print(f"Filter '{filter_name}' already exists with ID {filter_id}")
            filter_ids[key] = filter_id
        else:
            print(f"Status '{status_map[key]}' not found in project.")

    unresolved_statuses = [s for s in status_map["Unresolved"] if s in statuses]
    if unresolved_statuses:
        filter_name = "overall_status_filter_Unresolved"
        status_jql = " OR ".join([f'status = "{s}"' for s in unresolved_statuses])
        jql = f'project = "{project_key}" AND ({status_jql})'
        filter_id = find_filter_id_by_name(filter_name)
        if not filter_id:
            filter_id = create_filter(
                filter_name,
                jql,
                description=f"Auto-created filter for unresolved statuses: {', '.join(unresolved_statuses)}"
            )
            print(f"Created filter '{filter_name}' with ID {filter_id}")
        else:
            print(f"Filter '{filter_name}' already exists with ID {filter_id}")
        filter_ids["Unresolved"] = filter_id
    else:
        print("No unresolved statuses found in project.")

    return filter_ids

def fetch_issues_for_filter(filter_id):
    url = f"https://{JIRA_DOMAIN}/rest/api/3/filter/{filter_id}"
    headers = {"Accept": "application/json"}
    filter_response = requests.get(url, headers=headers, auth=HTTPBasicAuth(JIRA_EMAIL, JIRA_API_TOKEN))
    if filter_response.status_code != 200:
        print(f"Failed to fetch filter {filter_id}")
        return []
    filter_data = filter_response.json()
    jql_query = filter_data["jql"]

    search_url = f"https://{JIRA_DOMAIN}/rest/api/3/search"
    params = {
        "jql": jql_query,
        "maxResults": 100,
        "fields": "summary,status,duedate,resolution,labels"
    }
    response = requests.get(search_url, headers=headers, params=params, auth=HTTPBasicAuth(JIRA_EMAIL, JIRA_API_TOKEN))
    data = response.json()
    issues = []
    for issue in data.get("issues", []):
        fields = issue["fields"]
        labels = fields.get("labels", [])
        plat = ""
        ip = ""
        for label in labels:
            label_clean = label.strip().upper()
            if label_clean in PLATFORMS:
                plat = label_clean
            elif not ip and label_clean not in STATUSES:
                ip = label
        issues.append({
            "Issue Key": issue["key"],
            "Filter": filter_data["name"],
            "Summary": fields.get("summary", ""),
            "Platform": plat,
            "IP": ip,
            "Status": fields.get("status", {}).get("name", ""),
            "Due Date": fields.get("duedate", "") or "Not Set",
            "Resolution": fields.get("resolution", {}).get("name", "") if fields.get("resolution") else "Unresolved",
        })
    return issues

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    excel_path = os.path.join(base_dir, "data.xlsx")
    with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
        for filter_type, filter_id in FILTER_IDS.items():
            issues = fetch_issues_for_filter(filter_id)
            if issues:
                df = pd.DataFrame(issues)
                df.to_excel(writer, sheet_name=filter_type, index=False)
    print("Excel file updated")

if __name__ == "__main__":
    project_key = "DS"
    FILTER_IDS = ensure_selected_status_filters(project_key)
    print("FILTER_IDS =", FILTER_IDS)
    main()