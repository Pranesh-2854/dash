import requests
import os
from dotenv import load_dotenv

load_dotenv()

JIRA_DOMAIN = os.environ.get("JIRA_DOMAIN")
JIRA_EMAIL = os.environ.get("JIRA_EMAIL")
JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN")

BASE_URL = f"https://{JIRA_DOMAIN}/rest/api/3"

HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json"
}

AUTH = (JIRA_EMAIL, JIRA_API_TOKEN)

def get_project_id(project_key):
    url = f"{BASE_URL}/project/{project_key}"
    response = requests.get(url, auth=AUTH, headers=HEADERS)
    if response.status_code == 200:
        return response.json().get("id")
    print(f"[ERROR] Project ID fetch failed: {response.status_code} - {response.text}")
    return None


def get_project_role_id(project_key, role_name):
    url = f"{BASE_URL}/project/{project_key}/role"
    response = requests.get(url, auth=AUTH, headers=HEADERS)
    if response.status_code != 200:
        print(f"[ERROR] Roles fetch failed: {response.status_code} - {response.text}")
        return None

    roles = response.json()
    for name, link in roles.items():
        if name.lower() == role_name.lower():
            return link.rstrip("/").split("/")[-1]

    print(f"[ERROR] Role '{role_name}' not found in project '{project_key}'")
    return None


def list_filter_permissions(filter_id):
    url = f"{BASE_URL}/filter/{filter_id}/permission"
    response = requests.get(url, auth=AUTH)
    if response.status_code == 200:
        return response.json()
    print(f"[ERROR] Failed to list permissions: {response.status_code} - {response.text}")
    return []


def add_viewer_permission(filter_id, project_id, role_id):
    url = f"{BASE_URL}/filter/{filter_id}/permission"
    payload = {
        "type": "projectRole",
        "projectId": project_id,
        "projectRoleId": role_id
    }
    response = requests.post(url, json=payload, auth=AUTH, headers=HEADERS)
    print(f"[ADD] Permission: {response.status_code} - {response.text}")

def add_editor_permission(filter_id, project_id, role_id):
    url = f"{BASE_URL}/filter/{filter_id}/permission"
    payload = {
        "type": "projectRole",
        "projectId": project_id,
        "projectRoleId": role_id,
        "view": True,
        "edit": True
    }
    response = requests.post(url, json=payload, auth=AUTH, headers=HEADERS)
    print(f"[ADD EDITOR] {response.status_code} - {response.text}")

def remove_editor_permission(filter_id, project_id, role_id):
    permissions = list_filter_permissions(filter_id)
    for perm in permissions:
        if (
            perm.get("type") == "project" and
            str(perm.get("project", {}).get("id")) == str(project_id) and
            "role" in perm and
            str(perm.get("role", {}).get("id")) == str(role_id)
        ):
            perm_id = perm["id"]
            url = f"{BASE_URL}/filter/{filter_id}/permission/{perm_id}"
            response = requests.delete(url, auth=AUTH)
            print(f"[REMOVE EDITOR] Removed project+role editor (ID: {perm_id}): {response.status_code} - {response.text}")
            return
    print("[INFO] No matching project role editor permission found.")



def remove_viewer_permission(filter_id, project_id, role_id):
    permissions = list_filter_permissions(filter_id)
    for perm in permissions:
        print("[DEBUG] Permission Entry:", perm)

        if (
            perm["type"] == "project"
            and str(perm.get("project", {}).get("id")) == str(project_id)
            and str(perm.get("role", {}).get("id")) == str(role_id)
        ):
            perm_id = perm["id"]
            url = f"{BASE_URL}/filter/{filter_id}/permission/{perm_id}"
            response = requests.delete(url, auth=AUTH)
            print(f"[REMOVE] project (ID: {perm_id}): {response.status_code} - {response.text}")
            return
    print("[INFO] No matching project viewer permission found.")


def remove_all_viewers(filter_id):
    while True:
        permissions = list_filter_permissions(filter_id)
        removed = False
        for perm in permissions:
            if perm["type"] in {"project", "projectRole", "user", "group", "global"}:
                perm_id = perm["id"]
                url = f"{BASE_URL}/filter/{filter_id}/permission/{perm_id}"
                response = requests.delete(url, auth=AUTH)
                print(f"[REMOVE ALL] Removed {perm['type']} viewer ID {perm_id}: {response.status_code}")
                removed = True
                break
        if not removed:
            break

def print_permissions(title, permissions):
    print(f"\n--- {title} ---")
    for perm in permissions:
        print(perm)
    print("--- End ---\n")

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 6 and sys.argv[1] != "remove-all":
        print("Usage: roles.py <add|remove> <viewer|editor> <filter_id> <project_key> <role_name>", file=sys.stderr)
        print("For remove-all: roles.py remove-all <filter_id> <project_key> <dummy>", file=sys.stderr)
        sys.exit(1)

    action = sys.argv[1]      
    if action in ("add", "remove"):
        role_type = sys.argv[2] 
        filter_id = sys.argv[3]
        project_key = sys.argv[4]
        role_name = sys.argv[5]
    elif action == "remove-all":
        filter_id = sys.argv[2]
        project_key = sys.argv[3]
    else:
        print("Unknown action", file=sys.stderr)
        sys.exit(1)

    project_id = get_project_id(project_key)
    if not project_id:
        print("Invalid project", file=sys.stderr)
        sys.exit(1)

    if action == "add":
        role_id = get_project_role_id(project_key, role_name)
        if not role_id:
            print("Invalid role", file=sys.stderr)
            sys.exit(1)
        if role_type == "viewer":
            add_viewer_permission(filter_id, project_id, role_id)
        elif role_type == "editor":
            add_editor_permission(filter_id, project_id, role_id)
        else:
            print("Invalid role type", file=sys.stderr)
            sys.exit(1)

    elif action == "remove":
        role_id = get_project_role_id(project_key, role_name)
        if not role_id:
            print("Invalid role", file=sys.stderr)
            sys.exit(1)
        if role_type == "viewer":
            remove_viewer_permission(filter_id, project_id, role_id)
        elif role_type == "editor":
            remove_editor_permission(filter_id, project_id, role_id)
        else:
            print("Invalid role type", file=sys.stderr)
            sys.exit(1)

    elif action == "remove-all":
        remove_all_viewers(filter_id)

    else:
        print("Unknown action", file=sys.stderr)
        sys.exit(1)