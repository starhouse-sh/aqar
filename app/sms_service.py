"""
Star House SMS Service - SMS Misr Integration
Uses Test Sender (ACTIVE) - Token from your account 5479604896
"""
import requests
import random
import time

# بيانات حسابك - SMS Misr - شغالة بالباسورد الجديد
SMS_CONFIG = {
    "username": "6f2c14b0-6e2a-4ce2-9c64-ec2b15471612",
    "token": "212577447e1492658a79c6f18d98592e9f23f9953b2b162e08efca61e6999b18",
    "password": "212577447e1492658a79c6f18d98592e9f23f9953b2b162e08efca61e6999b18",
    "sender_id": "b611afb996655a94c8e942a823f1421de42bf8335d24ba1f84c437b2ab11ca27",
    "sender": "b611afb996655a94c8e942a823f1421de42bf8335d24ba1f84c437b2ab11ca27",
    "api_url": "https://smsmisr.com/api/SMS/"
}

# متغير يحفظ الأكواد مؤقتا (في الإنتاج استخدم DB أو Cache)
otp_storage = {}

def generate_otp():
    return str(random.randint(100000, 999999))

def send_sms_otp(phone_number, otp_code):
    """
    phone_number: 01155712096 -> هيتحول لـ 201155712096
    """
    # نظف الرقم
    phone = phone_number.strip().replace("+", "").replace(" ", "")
    if phone.startswith("0"):
        phone = "2" + phone  # 011 -> 2011
    if not phone.startswith("2"):
        phone = "2" + phone

    message = f"Your Star House verification code is: {otp_code} - Valid for 5 minutes - starh.pythonanywhere.com"

    payload = {
        "username": SMS_CONFIG["username"],
        "password": SMS_CONFIG["token"],  # SMS Misr بيستخدم password = token
        "language": "1",
        "sender": SMS_CONFIG["sender_id"],
        "mobile": phone,
        "message": message
    }

    try:
        # API V3 الجديد
        url = "https://smsmisr.com/api/SMS/"
        params = {
            "username": SMS_CONFIG["username"],
            "password": SMS_CONFIG["token"],
            "sender": SMS_CONFIG["sender_id"],
            "mobile": phone,
            "language": "1",
            "message": message
        }
                # جرب الـ POST method - SMS Misr مش بتدعم GET
        params["environment"] = "2"
        response = requests.post(url, data=params, timeout=10)
        print(f"SMS Response: {response.text}")
        # كود 1901 = تم الإرسال بنجاح في SMS Misr
        if "1901" in response.text or "OK" in response.text or response.status_code == 200:
            return True, response.text
        else:
            # لو فشل جرب الطريقة التانية
            response2 = requests.post("https://smsmisr.com/api/SMS/", data=payload, timeout=10)
            print(f"SMS Response2: {response2.text}")
            return True, response2.text

    except Exception as e:
        print(f"SMS Error: {e}")
        return False, str(e)
def create_and_send_otp(phone):
    otp = generate_otp()
    otp_storage[phone] = {
        "otp": otp,
        "time": time.time(),
        "attempts": 0
    }
    success, resp = send_sms_otp(phone, otp)
    return success, otp, resp

def verify_otp(phone, user_otp):
    data = otp_storage.get(phone)
    if not data:
        return False, "لا يوجد كود لهذا الرقم"
    
    # انتهاء بعد 5 دقايق
    if time.time() - data["time"] > 300:
        del otp_storage[phone]
        return False, "الكود انتهى - اطلب كود جديد"
    
    if data["otp"] == user_otp.strip():
        del otp_storage[phone]
        return True, "تم التحقق"
    else:
        data["attempts"] += 1
        if data["attempts"] >= 3:
            del otp_storage[phone]
            return False, "حاولت 3 مرات غلط - اطلب كود جديد"
        return False, f"كود غلط - باقي {3 - data['attempts']} محاولات"
