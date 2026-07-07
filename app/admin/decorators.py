from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('يجب تسجيل الدخول أولاً', 'danger')
            return redirect(url_for('main.login'))
        
        if current_user.role not in ['admin', 'super_admin']:
            flash('ليس لديك صلاحية للوصول لهذه الصفحة', 'danger')
            return redirect(url_for('main.home'))
        
        return f(*args, **kwargs)
    return decorated_function


def super_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('يجب تسجيل الدخول أولاً', 'danger')
            return redirect(url_for('main.login'))
        
        if current_user.role != 'super_admin':
            flash('هذه الصفحة للسوبر ادمن فقط', 'danger')
            return redirect(url_for('admin.admin_dashboard'))
        
        return f(*args, **kwargs)
    return decorated_function