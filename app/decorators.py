from functools import wraps
from flask import redirect, url_for, flash
from flask_login import current_user

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('سجل دخول الاول عشان تدخل الصفحة دي', 'warning')
            return redirect(url_for('main.login'))
        
        # بيدخل الادمن والسوبر ادمن
        if current_user.role not in ['admin', 'super_admin']:
            flash('معندكش صلاحية تدخل لوحة التحكم', 'danger')
            return redirect(url_for('main.login'))
        
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('سجل دخول الاول', 'warning')
            return redirect(url_for('main.login'))
        
        if current_user.role not in ['admin', 'super_admin']:
            flash('ليس لديك صلاحية الادمن', 'danger')
            return redirect(url_for('main.home'))  # ← home مش login
        return f(*args, **kwargs)
    return decorated_function

def super_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('سجل دخول الاول', 'warning')
            return redirect(url_for('main.login'))
        
        if current_user.role != 'super_admin':  # ← صلحناها
            flash('الصفحة دي للسوبر ادمن فقط', 'danger')
            return redirect(url_for('main.home'))  # ← home مش login
        return f(*args, **kwargs)
    return decorated_function