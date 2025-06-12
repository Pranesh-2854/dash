from flask import Flask, jsonify, send_from_directory, request
import pandas as pd
import os
from threading import Lock
import subprocess
import sys

app = Flask(__name__)
ONEDRIVE_PATH = os.path.dirname(os.path.abspath(__file__))
excel_path = os.path.join(ONEDRIVE_PATH, 'jira_issues.xlsx')

data_cache = {
    'ip_test_details': None,
}
cache_lock = Lock()

if not os.path.exists(ONEDRIVE_PATH):
    raise FileNotFoundError(f"OneDrive path does not exist: {ONEDRIVE_PATH}")

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

@app.route('/refresh_jira')
def refresh_jira():
    try:
        subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), 'prog.py')], check=True)
        return jsonify({"status": "refreshed"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True,use_reloader=False)
