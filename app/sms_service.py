import os
import random
import requests
from datetime import datetime, timedelta

# === حماية البيانات من .env ===
try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

try:
    from app.otp_admin_store import add_otp_request
    HAS_ADMIN_STORE = True
except:
    def add_otp_request(phone, otp, name="عميل"):
        print(f"[ADMIN FALLBACK] {phone} => {otp}")
    HAS_ADMIN_STORE = False

otp_store = {}

# === قراءة من Environment بدل ما تبقى مكشوفة ===
API_USERNAME = os.getenv("SMS_API_USERNAME", "")
API_PASSWORD = os.getenv("SMS_API_PASSWORD", "")
SENDER_TOKEN = os.getenv("SMS_SENDER_TOKEN", "")

def create_and_send_otp(phone):
    clean = phone.strip().replace(" ", "").replace("-", "")
    if clean.startswith("+20"):
        clean = "0" + clean[3:]
    elif clean.startswith("0020"):
        clean = "0" + clean[4:]
    if len(clean) != 11 or not clean.startswith("01"):
        return False, None, "رقم غير صحيح"

    otp = str(random.randint(100000, 999999))
    otp_store[clean] = {'otp': otp, 'expires': datetime.utcnow() + timedelta(minutes=5)}
    mobile_20 = "20" + clean[1:]
    print(f"=== SENDING to {clean} / {mobile_20} OTP={otp} ===")
    try:
        add_otp_request(clean, otp)
    except Exception as e:
        print(f"Admin log error: {e}")

    # لو مفيش بيانات SMS هنشتغل محلي
    if not API_USERNAME or not API_PASSWORD:
        print("No SMS creds in env - using local fallback")
        return True, otp, f"تم (محلي - مفيش بيانات SMS) - الكود: {otp}"

    try:
        resp = requests.post(
            "https://smsmisr.com/api/SMS/",
            data={
                "environment": "2",
                "username": API_USERNAME,
                "password": API_PASSWORD,
                "sender": SENDER_TOKEN,
                "mobile": mobile_20,
                "language": "1",
                "message": f"Star House code: {otp}"
            },
            timeout=15
        )
        print(f"SMS API Response: {resp.status_code} - {resp.text}")
        if "1901" in resp.text:
            return True, otp, f"تم الارسال بنجاح - الكود: {otp}"
        if "1903" in resp.text:
            return True, otp, f"تم (محلي) - الكود: {otp} - ملاحظة: رد الشركة {resp.text[:100]}"
        if "1902" in resp.text:
            return True, otp, f"تم (محلي) - مفيش رصيد لكن الكود: {otp}"
        return True, otp, f"تم - الكود: {otp}"

    except Exception as e:
        print(f"Proxy/Connection Error (PythonAnywhere free): {e}")
        print(f"FALLBACK: Using local OTP {otp} for {clean}")
        return True, otp, f"تم (وضع تجريبي - PythonAnywhere المجاني بيمنع SMS) - الكود: {otp}"

def verify_otp(phone, user_otp):
    clean = phone.strip().replace(" ", "").replace("-", "")
    if clean.startswith("+20"):
        clean = "0" + clean[3:]
    rec = otp_store.get(clean) or otp_store.get(phone)
    if not rec:
        return False, "مفيش كود"
    if datetime.utcnow() > rec['expires']:
        return False, "انتهى"
    if rec['otp'] == user_otp.strip():
        return True, "صح"
    return False, "غلط"
