import os
import secrets
from datetime import datetime
from flask import Blueprint, render_template, url_for, flash, redirect, request, current_app, abort, jsonify
from app import db, bcrypt
from app.forms import RegistrationForm, LoginForm, PropertyForm
from app.models import User, Property, PropertyImage, ActivityLog
from flask_login import login_user, current_user, logout_user, login_required
from sqlalchemy import or_
from functools import wraps

main = Blueprint('main', __name__)

# ---------- Decorators - متصلح ----------
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('سجل دخول الأول', 'warning')
            return redirect(url_for('main.login', next=request.url))
        
        # ننضف الـ role من المسافات والحروف الكبيرة
        role = str(current_user.role).strip().lower() if current_user.role else ''
        print(f"DEBUG admin_required: user={current_user.email}, role='{current_user.role}' cleaned='{role}'") # هتشوفه في التيرمنال
        
        if role not in ['admin', 'super_admin']:
            flash(f'لازم تكون ادمن - انت حاليا {current_user.role}', 'danger')
            return redirect(url_for('main.home'))
        if getattr(current_user, 'is_banned', False):
            logout_user()
            flash('حسابك محظور', 'danger')
            return redirect(url_for('main.login'))
        return f(*args, **kwargs)
    return decorated

def super_admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('main.login'))
        role = str(current_user.role).strip().lower() if current_user.role else ''
        if role != 'super_admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated

def save_picture(form_picture):
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(current_app.root_path, 'static/property_pics', picture_fn)
    os.makedirs(os.path.dirname(picture_path), exist_ok=True)
    form_picture.save(picture_path)
    return picture_fn

# ---------- HOME FINAL ----------
@main.route("/")
@main.route("/home")
def home():
    page = request.args.get('page', 1, type=int)
    property_type_param = request.args.get('property_type', '').strip()
    location = request.args.get('location', '').strip()
    sale_type = request.args.get('type', '').strip()

    TYPE_GROUPS = {
        'apartment': ['شقة', 'شقه', 'شقق', 'apartment'],
        'villa': ['فيلا', 'فله', 'فلة', 'فلل', 'فيلات', 'villa'],
        'land': ['أرض', 'ارض', 'أراضي', 'اراضي', 'land'],
        'shop': ['محل', 'محلات', 'shop', 'store']
    }

    if current_user.is_authenticated and str(getattr(current_user, 'role', None)).strip().lower() == 'super_admin':
        query = Property.query
    else:
        query = Property.query.filter_by(is_approved=True)

    if location:
        query = query.filter(Property.location.ilike(f'%{location}%'))

    if property_type_param:
        matched = None
        pt_low = property_type_param.lower()
        for values in TYPE_GROUPS.values():
            if property_type_param in values or pt_low in [v.lower() for v in values]:
                matched = values
                break
        if matched:
            query = query.filter(Property.property_type.in_(matched))
        else:
            query = query.filter(Property.property_type == property_type_param)

    if sale_type:
        query = query.filter(Property.type == sale_type)

    properties = query.order_by(Property.is_featured.desc(), Property.date_posted.desc()).paginate(page=page, per_page=9, error_out=False)

    min_prices = {}
    for key, label in [('villa','فيلا'), ('apartment','شقة'), ('land','أرض'), ('shop','محل')]:
        vals = TYPE_GROUPS[key]
        min_prices[label] = Property.query.filter(Property.property_type.in_(vals), Property.is_approved==True).order_by(Property.price.asc()).first()

    return render_template('home.html', properties=properties, min_prices=min_prices)

# ---------- AUTH - متصلح ----------
@main.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        new_user = User(username=form.username.data, email=form.email.data, password=hashed_password, role='user')
        # لو الموديل بيستخدم password_hash
        if hasattr(new_user, 'password_hash'):
            new_user.password_hash = hashed_password
        db.session.add(new_user)
        db.session.commit()
        flash('تم التسجيل بنجاح', 'success')
        return redirect(url_for('main.login'))
    return render_template('register.html', form=form)

@main.route('/login', methods=['GET', 'POST'])
def login():
    # لو مسجل دخول قبل كده
    if current_user.is_authenticated:
        role = str(current_user.role).strip().lower()
        if role == 'super_admin':
            return redirect(url_for('main.manage_admins'))
        elif role == 'admin':
            return redirect(url_for('main.admin_dashboard'))
        return redirect(url_for('main.home'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password if hasattr(user, 'password') else user.password_hash, form.password.data):
            if getattr(user, 'is_banned', False):
                flash('حسابك محظور تواصل مع الادارة', 'danger')
                return redirect(url_for('main.login'))
            
            login_user(user)
            try:
                user.last_login = datetime.utcnow()
                db.session.commit()
            except:
                pass
            
            next_page = request.args.get('next')
            # نتجاهل next لو رايح للرئيسية واليوزر ادمن
            role = str(user.role).strip().lower()
            print(f"LOGIN DEBUG: {user.email} role={role} next={next_page}")

            if role == 'super_admin':
                if next_page and '/admin' in next_page:
                    return redirect(next_page)
                return redirect(url_for('main.manage_admins'))
            elif role == 'admin':
                if next_page and '/admin' in next_page:
                    return redirect(next_page)
                return redirect(url_for('main.admin_dashboard'))
            
            # يوزر عادي
            if next_page:
                return redirect(next_page)
            return redirect(url_for('main.home'))
        else:
            flash('الايميل او الباسورد غلط', 'danger')
    return render_template('login.html', form=form)

@main.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('main.home'))

# ---------- PROPERTY CRUD ----------
@main.route("/property/new", methods=['GET', 'POST'])
@login_required
def create_property():
    form = PropertyForm()
    if form.validate_on_submit():
        try:
            whatsapp_number = form.whatsapp.data if form.whatsapp.data else form.phone.data
            bedrooms_val = form.bedrooms.data if form.bedrooms.data is not None else 0
            bathrooms_val = form.bathrooms.data if form.bathrooms.data is not None else 0

            prop = Property(
                title=form.title.data, 
                description=form.description.data, 
                price=form.price.data,
                negotiable=form.negotiable.data, 
                location=form.location.data, 
                type=form.type.data,
                property_type=form.property_type.data, 
                bedrooms=bedrooms_val,
                bathrooms=bathrooms_val, 
                area=form.area.data, 
                finishing=form.finishing.data,
                phone=form.phone.data, 
                whatsapp=whatsapp_number, 
                user_id=current_user.id,
                is_approved=False if str(current_user.role).strip().lower() == 'user' else True
            )
            db.session.add(prop)
            db.session.commit()

            if form.pictures.data:
                for file in form.pictures.data:
                    if file and file.filename != '':
                        picture_file = save_picture(file)
                        img = PropertyImage(image_file=picture_file, property_id=prop.id)
                        db.session.add(img)
                db.session.commit()

            flash('تم إضافة العقار بنجاح', 'success')
            return redirect(url_for('main.property_detail', property_id=prop.id))
        except Exception as e:
            db.session.rollback()
            print(f"ERROR CREATING PROPERTY: {e}")
            import traceback; traceback.print_exc()
            flash(f'حصل خطأ: {str(e)}', 'danger')
    else:
        if request.method == 'POST':
            print("FORM ERRORS:", form.errors)

    return render_template('create_property.html', form=form, legend='إضافة عقار جديد')

@main.route("/property/<int:property_id>")
def property_detail(property_id):
    prop = Property.query.get_or_404(property_id)
    prop.views = (prop.views or 0) + 1
    db.session.commit()
    is_favorite = prop in current_user.favorite_properties if current_user.is_authenticated else False
    from flask_wtf.csrf import generate_csrf
    return render_template('property_detail.html', property=prop, is_favorite=is_favorite, csrf_token=generate_csrf())

@main.route("/favorite/<int:property_id>", methods=['POST'])
@login_required
def favorite(property_id):
    prop = Property.query.get_or_404(property_id)
    if prop in current_user.favorite_properties:
        current_user.favorite_properties.remove(prop)
        db.session.commit()
        return jsonify({'status': 'removed'})
    else:
        current_user.favorite_properties.append(prop)
        db.session.commit()
        return jsonify({'status': 'added'})

@main.route("/favorites")
@login_required
def favorites():
    return render_template('favorites.html', properties=current_user.favorite_properties.all())

@main.route("/account")
@login_required
def account():
    props = Property.query.filter_by(user_id=current_user.id).order_by(Property.date_posted.desc()).all()
    return render_template('account.html', properties=props)

# ---------- ADMIN DASHBOARD ----------
@main.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    total_users = User.query.count()
    total_properties = Property.query.count()
    pending = Property.query.filter_by(is_approved=False).count()
    users = User.query.order_by(User.id.desc()).limit(10).all()
    properties = Property.query.order_by(Property.date_posted.desc()).limit(20).all()
    return render_template('admin/dashboard.html', total_users=total_users, total_properties=total_properties, pending=pending, users=users, properties=properties)

@main.route('/admin/properties')
@login_required
@admin_required
def manage_properties():
    status = request.args.get('status','all')
    page = request.args.get('page',1,type=int)
    q = Property.query.order_by(Property.date_posted.desc())
    if status == 'pending': q = q.filter_by(is_approved=False)
    elif status == 'approved': q = q.filter_by(is_approved=True)
    props = q.paginate(page=page, per_page=15)
    return render_template('admin/admin_properties.html', properties=props, status=status)

@main.route('/admin/approve/<int:property_id>', methods=['POST'])
@login_required
@admin_required
def approve_property(property_id):
    prop = Property.query.get_or_404(property_id)
    prop.is_approved = True
    prop.is_rejected = False
    db.session.add(ActivityLog(action=f"وافق على عقار {prop.title}", admin_id=current_user.id))
    db.session.commit()
    flash('تمت الموافقة', 'success')
    return redirect(request.referrer or url_for('main.admin_dashboard'))

@main.route('/admin/reject/<int:property_id>', methods=['POST'])
@login_required
@admin_required
def reject_property(property_id):
    prop = Property.query.get_or_404(property_id)
    prop.is_approved = False
    prop.is_rejected = True
    db.session.commit()
    flash('تم الرفض', 'warning')
    return redirect(request.referrer or url_for('main.admin_dashboard'))

@main.route('/admin/feature/<int:property_id>', methods=['POST'])
@login_required
@super_admin_required
def feature_property(property_id):
    prop = Property.query.get_or_404(property_id)
    prop.is_featured = not prop.is_featured
    db.session.commit()
    return redirect(request.referrer)

@main.route('/admin/delete_property/<int:property_id>', methods=['POST'])
@login_required
@admin_required
def delete_property(property_id):
    prop = Property.query.get_or_404(property_id)
    for img in prop.images:
        try:
            path = os.path.join(current_app.root_path, 'static/property_pics', img.image_file)
            if os.path.exists(path): os.remove(path)
        except: pass
    db.session.delete(prop)
    db.session.commit()
    flash('تم الحذف', 'success')
    return redirect(request.referrer or url_for('main.admin_dashboard'))

# ---------- SUPER ADMIN - ADMINS ----------
@main.route('/admin/manage-admins')
@login_required
@super_admin_required
def manage_admins():
    admins = User.query.filter(User.role.in_(['admin','super_admin'])).all()
    # نجيبهم حتى لو فيه مسافات
    all_users = User.query.all()
    admins = [u for u in all_users if str(u.role).strip().lower() in ['admin', 'super_admin']]
    users = [u for u in all_users if str(u.role).strip().lower() == 'user']
    return render_template('admin/manage_admins.html', admins=admins, users=users)

@main.route('/admin/promote', methods=['POST'])
@login_required
@super_admin_required
def promote_user():
    email = request.form.get('email','').strip()
    role = request.form.get('role','admin').strip().lower()
    print(f"PROMOTE DEBUG: email={email} role={role}")
    user = User.query.filter_by(email=email).first()
    if user:
        user.role = role
        db.session.commit()
        flash(f'تم ترقية {email} الى {role}', 'success')
    else:
        flash('المستخدم مش موجود', 'danger')
    return redirect(url_for('main.manage_admins'))

@main.route('/admin/demote/<int:user_id>', methods=['POST'])
@login_required
@super_admin_required
def demote_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('مينفعش تغير نفسك', 'danger')
    else:
        user.role = 'user'
        db.session.commit()
        flash(f'تم سحب الصلاحية من {user.email}', 'info')
    return redirect(url_for('main.manage_admins'))

@main.route('/admin/toggle-ban/<int:user_id>', methods=['POST'])
@login_required
@super_admin_required
def toggle_ban(user_id):
    user = User.query.get_or_404(user_id)
    user.is_banned = not user.is_banned
    db.session.commit()
    flash(f"{'تم الحظر' if user.is_banned else 'تم فك الحظر'} {user.email}", 'warning')
    return redirect(request.referrer or url_for('main.manage_admins'))

@main.route("/about")
def about(): return render_template('about.html', title='من نحن')
@main.route("/prices")
def prices(): return render_template('prices.html', title='مؤشر الأسعار')
@main.route("/contact")
def contact(): return render_template('contact.html', title='تواصل معنا')

@main.route('/admin/manage-admins')
@login_required
@super_admin_required
def manage_admins():
    admins = User.query.filter(User.role.in_(['admin','super_admin'])).all()
    return render_template('admin/manage_admins.html', 
        admins=admins,
        super_count=User.query.filter_by(role='super_admin').count(),
        admin_count=User.query.filter_by(role='admin').count(),
        user_count=User.query.filter_by(role='user').count()
    )