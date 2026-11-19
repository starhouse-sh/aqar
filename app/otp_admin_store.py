import json, os
from datetime import datetime

STORE_FILE = os.path.join(os.path.dirname(__file__), 'otp_requests.json')
OTP_EXPIRY_MINUTES = 10

def _load():
    if not os.path.exists(STORE_FILE):
        return []
    try:
        with open(STORE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []

def _save(data):
    try:
        with open(STORE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"OTP Store Save Error: {e}")

def add_otp_request(phone, otp, name="عميل"):
    data = _load()
    now = datetime.utcnow()
    data = [d for d in data if d.get('phone') != phone]
    data.append({
        'phone': phone,
        'otp': otp,
        'name': name,
        'time': now.strftime('%Y-%m-%d %H:%M:%S'),
        'timestamp': now.timestamp()
    })
    data = data[-20:]
    _save(data)
    print(f"[OTP ADMIN] Added {phone} => {otp}")

def get_all_requests():
    data = _load()
    now = datetime.utcnow().timestamp()
    valid = []
    for d in data:
        if now - d.get('timestamp', 0) < OTP_EXPIRY_MINUTES * 60:
            valid.append(d)
    valid.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
    return valid

# ===== الاسم اللي routes.py بيدور عليه =====
def get_otp_requests():
    return get_all_requests()

# أسماء بديلة عشان مفيش خطأ تاني مهما كان الاسم في routes.py
get_requests = get_all_requests
get_pending_requests = get_all_requests
get_otp_codes = get_all_requests

def get_pending_count():
    return len(get_all_requests())

def clear_all():
    _save([])
