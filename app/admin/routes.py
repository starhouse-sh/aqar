from flask import render_template, flash, redirect, url_for, request
from flask_login import login_required, current_user
from app.models import User, Property
from app import db
from app.admin import admin_bp
from app.decorators import admin_required, super_admin_required  # ← تعديل: غيرنا المسار عشان decorators.py في app مش app.admin

@admin_bp.route('/dashboard')
@login_required
@admin_required
def admin_dashboard():
    total_users = User.query.count()
    total_admins = User.query.filter(User.role.in_(['admin', 'super_admin'])).count()
    total_properties = Property.query.count()
    approved_properties = Property.query.filter_by(is_approved=True).count()
    pending_properties = Property.query.filter_by(is_approved=False).count()
    
    # ← تعديل: ضفنا دول عشان dashboard.html بيستخدمهم
    users = User.query.order_by(User.date_posted.desc()).limit(10).all()
    properties = Property.query.order_by(Property.date_posted.desc()).limit(10).all()
    
    return render_template('admin/dashboard.html',
                           total_users=total_users,
                           total_admins=total_admins,
                           total_properties=total_properties,
                           approved_properties=approved_properties,
                           pending_properties=pending_properties,
                           users=users,  # ← جديد
                           properties=properties)  # ← جديد

# ← تعديل: ضفنا route الموافقة على العقار
@admin_bp.route('/approve_property/<int:property_id>', methods=['POST'])
@login_required
@admin_required
def approve_property(property_id):
    property = Property.query.get_or_404(property_id)
    property.is_approved = not property.is_approved  # تبديل الحالة: لو مقبول يبقى مرفوض والعكس
    db.session.commit()
    
    if property.is_approved:
        flash(f'تم قبول العقار: {property.title}', 'success')
    else:
        flash(f'تم إلغاء قبول العقار: {property.title}', 'warning')
    
    return redirect(url_for('main.admin_dashboard'))

# ← تعديل: ضفنا route حذف العقار من الأدمن
@admin_bp.route('/delete_property/<int:property_id>', methods=['POST'])
@login_required
@admin_required
def delete_property(property_id):
    property = Property.query.get_or_404(property_id)
    
    # امسح الصور من الهارد
    for image in property.images:
        image_path = os.path.join(current_app.root_path, 'static/property_pics', image.image_file)
        try:
            if os.path.exists(image_path):
                os.remove(image_path)
        except:
            pass
    
    db.session.delete(property)
    db.session.commit()
    flash('تم حذف العقار وصوره بنجاح', 'success')
    return redirect(url_for('main.admin_dashboard'))

@admin_bp.route('/manage-admins')
@login_required
@super_admin_required
def manage_admins():
    admins = User.query.filter(User.role.in_(['admin', 'super_admin'])).all()
    users = User.query.filter_by(role='user').all()
    return render_template('admin/manage_admins.html', admins=admins, users=users)

@admin_bp.route('/promote', methods=['POST'])
@login_required
@super_admin_required
def promote_user():
    user_id = request.form.get('user_id')
    new_role = request.form.get('role')
    user = User.query.get(user_id)
    if user:
        user.role = new_role
        db.session.commit()
        flash(f'تم ترقية {user.email} إلى {new_role}', 'success')
    return redirect(url_for('main.manage_admins'))

@admin_bp.route('/demote/<int:user_id>')
@login_required
@super_admin_required
def demote_user(user_id):
    user = User.query.get(user_id)
    if user and user.email != current_user.email:  # متمسحش نفسك
        user.role = 'user'
        db.session.commit()
        flash(f'تم إلغاء اشراف {user.email}', 'success')
    return redirect(url_for('main.manage_admins'))

@admin_bp.route('/toggle_admin/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def toggle_admin(user_id):
    user = User.query.get_or_404(user_id)
    
    if user.id == current_user.id:
        flash('لا يمكنك تغيير صلاحياتك', 'danger')
        return redirect(url_for('main.admin_dashboard'))
    
    if user.role == 'super_admin':
        flash('لا يمكن تغيير صلاحية السوبر ادمن', 'danger')
        return redirect(url_for('main.admin_dashboard'))
    
    if user.role == 'admin':
        user.role = 'user'
        flash(f'تم سحب صلاحية الادمن من {user.username}', 'info')
    else:
        user.role = 'admin'
        flash(f'تم ترقية {user.username} الى ادمن', 'success')
    
    db.session.commit()
    return redirect(url_for('main.admin_dashboard'))

@admin_bp.route('/delete_user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    
    if user.id == current_user.id:
        flash('لا يمكنك حذف نفسك', 'danger')
        return redirect(url_for('main.admin_dashboard'))
    
    if user.role == 'super_admin':
        flash('لا يمكن حذف السوبر ادمن', 'danger')
        return redirect(url_for('main.admin_dashboard'))
    
    username = user.username
    db.session.delete(user)
    db.session.commit()
    flash(f'تم حذف المستخدم {username}', 'success')
    return redirect(url_for('main.admin_dashboard'))