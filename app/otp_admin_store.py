
from datetime import datetime
import threading

# قائمة الطلبات - هتفضل في الذاكرة + ملف
otp_requests = []
_lock = threading.Lock()

def add_otp_request(phone, otp, name="عميل"):
    with _lock:
        item = {
            "id": len(otp_requests) + 1,
            "phone": phone,
            "otp": otp,
            "name": name,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "pending"
        }
        otp_requests.insert(0, item)  # الجديد فوق
        # احتفظ بآخر 100 طلب بس
        if len(otp_requests) > 100:
            otp_requests.pop()
        print(f"[ADMIN OTP] {phone} => {otp}")
        return item

def get_otp_requests():
    with _lock:
        return list(otp_requests)

def mark_sent(request_id):
    with _lock:
        for r in otp_requests:
            if r["id"] == request_id:
                r["status"] = "sent"
                break
