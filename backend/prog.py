import requests
import pandas as pd
from requests.auth import HTTPBasicAuth
import os
from dotenv import load_dotenv

load_dotenv()

JIRA_DOMAIN = os.environ.get("JIRA_DOMAIN")
JIRA_EMAIL = os.environ.get("JIRA_EMAIL")
JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN")

FILTER_IDS = {
    "Target": 10033,
    "Pass": 10203,
    "Fail": 10204,
    "Unresolved": 10205
}

PLATFORMS = {"JTAMP", "JTAES", "JTAEN", "SVB"}
STATUSES = {"TARGET", "PASS", "FAIL", "UNRESOLVED"}

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
    main()
