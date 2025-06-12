import requests
import os
from dotenv import load_dotenv

load_dotenv()

JIRA_DOMAIN = os.environ.get("JIRA_DOMAIN")
JIRA_EMAIL = os.environ.get("JIRA_EMAIL")
JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN")

def get_transition_id(issue_key, target_status):
    url = f"https://{JIRA_DOMAIN}/rest/api/3/issue/{issue_key}/transitions"
    headers = {"Accept": "application/json"}
    response = requests.get(url, headers=headers, auth=(JIRA_EMAIL, JIRA_API_TOKEN))
    transitions = response.json().get("transitions", [])

    for transition in transitions:
        if transition["to"]["name"].lower() == target_status.lower():
            return transition["id"]
    return None

def transition_issue(issue_key, target_status):
    transition_id = get_transition_id(issue_key, target_status)
    if transition_id:
        url = f"https://{JIRA_DOMAIN}/rest/api/3/issue/{issue_key}/transitions"
        payload = {"transition": {"id": transition_id}}
        headers = {"Content-Type": "application/json"}
        response = requests.post(url, json=payload, headers=headers, auth=(JIRA_EMAIL, JIRA_API_TOKEN))
        print(f"Issue {issue_key} transitioned to {target_status}.")
    else:
        print(f"No valid transition to '{target_status}' for issue {issue_key}.")

def delete_all_attachments(issue_key):
    url = f"https://{JIRA_DOMAIN}/rest/api/3/issue/{issue_key}?fields=attachment"
    headers = {"Accept": "application/json"}
    response = requests.get(url, headers=headers, auth=(JIRA_EMAIL, JIRA_API_TOKEN))
    attachments = response.json().get("fields", {}).get("attachment", [])
    for att in attachments:
        att_id = att["id"]
        del_url = f"https://{JIRA_DOMAIN}/rest/api/3/attachment/{att_id}"
        del_resp = requests.delete(del_url, headers=headers, auth=(JIRA_EMAIL, JIRA_API_TOKEN))
        if del_resp.status_code == 204:
            print(f"Deleted attachment {att_id} from {issue_key}")
        else:
            print(f"Failed to delete attachment {att_id} from {issue_key}")

def attach_file(issue_key, file_path):
    delete_all_attachments(issue_key)
    url = f"https://{JIRA_DOMAIN}/rest/api/3/issue/{issue_key}/attachments"
    headers = {
        "X-Atlassian-Token": "no-check"
    }
    files = {
        'file': (os.path.basename(file_path), open(file_path, 'rb'))
    }
    response = requests.post(url, headers=headers, files=files, auth=(JIRA_EMAIL, JIRA_API_TOKEN))
    print(f"Attached file to issue {issue_key}.")

def process_txt_files(folder_path):
    for filename in os.listdir(folder_path):
        if filename.endswith(".txt"):
            parts = filename.split("_")
            if len(parts) == 2:
                issue_key = parts[0]
                status = parts[1].replace(".txt", "")
                file_path = os.path.join(folder_path, filename)

                transition_issue(issue_key, status)
                attach_file(issue_key, file_path)

process_txt_files("text_files")
