from flask import Flask, jsonify, send_from_directory, request
import pandas as pd
import os
from threading import Lock
import subprocess
import sys

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
excel_path = os.path.join(BASE_DIR, "data.xlsx")

data_cache = {
    'ip_test_details': None,
}
cache_lock = Lock()

def get_ip_test_details_df():
    try:
        xls = pd.ExcelFile(excel_path)
        target_df = pd.read_excel(xls, 'Target')
        pass_df = pd.read_excel(xls, 'Pass')
        fail_df = pd.read_excel(xls, 'Fail')
        unresolved_df = pd.read_excel(xls, 'Unresolved')

        target_df['SheetType'] = 'Target'
        pass_df['SheetType'] = 'Pass'
        fail_df['SheetType'] = 'Fail'
        unresolved_df['SheetType'] = 'Unresolved'

        df = pd.concat([target_df, pass_df, fail_df], ignore_index=True)

        with cache_lock:
            data_cache['ip_test_details'] = df
            data_cache['unresolved'] = unresolved_df
    except (FileNotFoundError, PermissionError):
        with cache_lock:
            df = data_cache.get('ip_test_details')
            unresolved_df = data_cache.get('unresolved')
        if df is None or unresolved_df is None:
            raise RuntimeError('Test case data unavailable and cache is empty')
    except Exception as e:
        raise RuntimeError(str(e))
    return df, unresolved_df, None


@app.route('/data/<module_name>')
def get_module_data(module_name):
    try:
        df, _, _ = get_ip_test_details_df()
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 503

    df = df[df['Platform'] == module_name]
    target_ips = set(df[df['SheetType'] == 'Target']['IP'])
    df = df[df['IP'].isin(target_ips)]

    grouped = df.groupby('IP').agg(
        Target=('SheetType', lambda x: (x == 'Target').sum()),
        Pass=('SheetType', lambda x: (x == 'Pass').sum()),
        Fail=('SheetType', lambda x: (x == 'Fail').sum()),
        Unresolved=('Resolution', lambda x: (x == 'Unresolved').sum())
    ).reset_index().rename(columns={'IP': 'Interface'})

    return jsonify(grouped.to_dict(orient='records'))

@app.route('/data/module_testcases/<interface>/<status>')
def get_module_testcases(interface, status):
    try:
        df, unresolved_df, _ = get_ip_test_details_df()
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 503

    platform = request.args.get('platform')
    if platform:
        df = df[df['Platform'] == platform]
        unresolved_df = unresolved_df[unresolved_df['Platform'] == platform]

    target_ips = set(df[df['SheetType'] == 'Target']['IP'])
    if interface not in target_ips:
        return jsonify([])

    status_lower = status.lower()
    if status_lower == "unresolved":
        filtered = unresolved_df[
            (unresolved_df['IP'].fillna('').str.strip().str.lower() == interface.strip().lower())
        ]
    elif status_lower == "target":
        filtered = df[
            (df['IP'].fillna('').str.strip().str.lower() == interface.strip().lower()) &
            (df['SheetType'] == 'Target')
        ]
    else:
        filtered = df[
            (df['IP'].fillna('').str.strip().str.lower() == interface.strip().lower()) &
            (df['Filter'].fillna('').str.lower().str.contains(status_lower))
        ]

    cases = []
    for idx, (_, row) in enumerate(filtered.iterrows(), 1):
        details = row.get('Summary', '')
        status_val = row.get('Status', '')
        cases.append({
            'no': str(idx),
            'details': '' if pd.isna(details) else str(details),
            'status': '' if pd.isna(status_val) else str(status_val)
        })
    return jsonify(cases)

@app.route('/data/module_testcases/<interface>')
def get_all_testcases_for_ip(interface):
    try:
        df, _, _ = get_ip_test_details_df()
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 503
    
    platform = request.args.get('platform')
    if platform:
        df = df[df['Platform'] == platform]

    filtered = df[df['IP'] == interface]
    cases = []
    for idx, (_, row) in enumerate(filtered.iterrows(), 1):
        details = row.get('Summary', '')
        status_val = row.get('Status', '')
        cases.append({
            'no': str(idx),
            'details': '' if pd.isna(details) else str(details),
            'status': '' if pd.isna(status_val) else str(status_val)
        })
    return jsonify(cases)

@app.route('/')
def index():
    return send_from_directory('../frontend', 'index.html')

@app.route('/module.html')
def module_page():
    return send_from_directory('../frontend', 'module.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('../frontend', path)

@app.route('/data/module_testcases/<interface>/Unresolved')
def get_unresolved_testcases_for_ip(interface):
    try:
        df, unresolved_df, _ = get_ip_test_details_df()
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 503
    
    platform = request.args.get('platform')
    if platform:
        df = df[df['Platform'] == platform]

    filtered = df[(df['IP'] == interface) & (df['Resolution'] == 'Unresolved')]
    cases = []
    for idx, (_, row) in enumerate(filtered.iterrows(), 1):
        details = row.get('Summary', '')
        status_val = row.get('Status', '')
        cases.append({
            'no': str(idx),
            'details': '' if pd.isna(details) else str(details),
            'status': '' if pd.isna(status_val) else str(status_val)
        })
    return jsonify(cases)

@app.route('/refresh-jira', methods=['POST'])
def refresh_jira():
    try:
        subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), 'prog.py')], check=True)
        return jsonify({"status": "Jira data refreshed!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/create-filter', methods=['POST'])
def api_create_filter():
    data = request.get_json()
    name = data.get('name')
    jql = data.get('jql')
    if not name or not jql:
        return jsonify({"status": "error", "message": "Filter name and JQL are required."}), 400
    try:
        result = subprocess.run(
            [sys.executable, os.path.join(os.path.dirname(__file__), 'filters.py'), name, jql],
            capture_output=True, text=True
        )
        print("filters.py stdout:", result.stdout)
        print("filters.py stderr:", result.stderr)
        if result.returncode == 0:
            return jsonify({"status": "success", "message": "Filter created/updated!"})
        else:
            return jsonify({"status": "error", "message": result.stderr}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/remove-issues', methods=['POST'])
def api_remove_issues():
    data = request.get_json()
    identifier = data.get('filter_id') or data.get('issue_key')
    if not identifier:
        return jsonify({"status": "error", "message": "Filter ID or Issue Key is required."}), 400
    try:
        result = subprocess.run(
            [sys.executable, os.path.join(os.path.dirname(__file__), 'filters.py'), '--remove', identifier],
            capture_output=True, text=True
        )
        print("filters.py stdout:", result.stdout)
        print("filters.py stderr:", result.stderr)
        if result.returncode == 0:
            msg = "Issue deleted!" if '-' in identifier else "All issues deleted!"
            return jsonify({"status": "success", "message": msg})
        else:
            return jsonify({"status": "error", "message": result.stderr}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/add-role', methods=['POST'])
def api_add_role():
    data = request.get_json()
    filter_id = data.get('filter_id')
    project_key = data.get('project_key')
    role_name = data.get('role_name')
    role_type = data.get('role_type') 
    if not filter_id or not project_key or not role_name or not role_type:
        return jsonify({"status": "error", "message": "All fields are required."}), 400
    try:
        result = subprocess.run(
            [sys.executable, os.path.join(os.path.dirname(__file__), 'roles.py'), "add", role_type, filter_id, project_key, role_name],
            capture_output=True, text=True
        )
        print("roles.py stdout:", result.stdout)
        print("roles.py stderr:", result.stderr)
        if result.returncode == 0:
            return jsonify({"status": "success", "message": f"{role_type.capitalize()} role added!"})
        else:
            return jsonify({"status": "error", "message": result.stderr}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/remove-role', methods=['POST'])
def api_remove_role():
    data = request.get_json()
    filter_id = data.get('filter_id')
    project_key = data.get('project_key')
    role_name = data.get('role_name')
    role_type = data.get('role_type') 
    if not filter_id or not project_key or not role_name or not role_type:
        return jsonify({"status": "error", "message": "All fields are required."}), 400
    try:
        result = subprocess.run(
            [sys.executable, os.path.join(os.path.dirname(__file__), 'roles.py'), "remove", role_type, filter_id, project_key, role_name],
            capture_output=True, text=True
        )
        print("roles.py stdout:", result.stdout)
        print("roles.py stderr:", result.stderr)
        if result.returncode == 0:
            return jsonify({"status": "success", "message": f"{role_type.capitalize()} role removed!"})
        else:
            return jsonify({"status": "error", "message": result.stderr}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/remove-all-roles', methods=['POST'])
def api_remove_all_roles():
    data = request.get_json()
    filter_id = data.get('filter_id')
    project_key = data.get('project_key')
    if not filter_id or not project_key:
        return jsonify({"status": "error", "message": "Filter ID and project key are required."}), 400
    try:
        result = subprocess.run(
            [sys.executable, os.path.join(os.path.dirname(__file__), 'roles.py'), "remove-all", filter_id, project_key, "dummy"],
            capture_output=True, text=True
        )
        print("roles.py stdout:", result.stdout)
        print("roles.py stderr:", result.stderr)
        if result.returncode == 0:
            return jsonify({"status": "success", "message": "All roles removed!"})
        else:
            return jsonify({"status": "error", "message": result.stderr}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/run-status', methods=['POST'])
def api_run_status():
    import subprocess
    import sys
    import os
    try:
        result = subprocess.run(
            [sys.executable, os.path.join(os.path.dirname(__file__), 'status.py')],
            capture_output=True, text=True
        )
        print("status.py stdout:", result.stdout)
        print("status.py stderr:", result.stderr)
        if result.returncode == 0:
            return jsonify({"status": "success", "message": "Status script executed successfully!"})
        else:
            return jsonify({"status": "error", "message": result.stderr or 'Status script failed.'}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/project-roles', methods=['POST'])
def api_project_roles():
    import requests, os
    data = request.get_json()
    project_key = data.get('project_key')
    if not project_key:
        return jsonify({"status": "error", "message": "Project key required."}), 400

    JIRA_DOMAIN = os.environ.get("JIRA_DOMAIN")
    JIRA_EMAIL = os.environ.get("JIRA_EMAIL")
    JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN")
    BASE_URL = f"https://{JIRA_DOMAIN}/rest/api/3"
    AUTH = (JIRA_EMAIL, JIRA_API_TOKEN)
    HEADERS = {"Accept": "application/json"}

    url = f"{BASE_URL}/project/{project_key}/role"
    response = requests.get(url, auth=AUTH, headers=HEADERS)
    if response.status_code != 200:
        return jsonify({"status": "error", "message": "Could not fetch roles."}), 500

    roles = list(response.json().keys())
    return jsonify({"status": "success", "roles": roles})

@app.route('/api/project-keys', methods=['GET'])
def api_project_keys():
    import requests, os
    JIRA_DOMAIN = os.environ.get("JIRA_DOMAIN")
    JIRA_EMAIL = os.environ.get("JIRA_EMAIL")
    JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN")
    BASE_URL = f"https://{JIRA_DOMAIN}/rest/api/3"
    AUTH = (JIRA_EMAIL, JIRA_API_TOKEN)
    HEADERS = {"Accept": "application/json"}
    url = f"{BASE_URL}/project/search"
    response = requests.get(url, auth=AUTH, headers=HEADERS)
    if response.status_code != 200:
        return jsonify({"status": "error", "message": "Could not fetch projects."}), 500
    projects = response.json().get("values", [])
    project_keys = [proj["key"] for proj in projects]
    return jsonify({"status": "success", "project_keys": project_keys})

@app.route('/api/read-excel')
def read_excel():
    df = pd.read_excel(excel_path)
    return jsonify(df.to_dict(orient='records'))

@app.route('/api/write-excel', methods=['POST'])
def write_excel():
    # Example: write a new DataFrame
    df = pd.DataFrame([{"col1": 1, "col2": 2}])
    df.to_excel(excel_path, index=False)
    return jsonify({"status": "success"})
    
if __name__ == '__main__':
    app.run(debug=True,use_reloader=False)