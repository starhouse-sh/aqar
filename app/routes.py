import os
import secrets
from flask import Blueprint, render_template, url_for, flash, redirect, request, current_app, abort
from app import db, bcrypt
from app.forms import RegistrationForm, LoginForm, PropertyForm
from app.models import User, Property, PropertyImage
from flask_login import login_user, current_user, logout_user, login_required
from app.models import User, Property
from app.decorators import admin_required, super_admin_required
from app.forms import SearchForm
main = Blueprint('main', __name__)

def save_picture(form_picture):
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(current_app.root_path, 'static/property_pics', picture_fn)
    
    os.makedirs(os.path.dirname(picture_path), exist_ok=True)
    form_picture.save(picture_path)
    return picture_fn

@main.route('/')
@main.route('/home')
def home():
    form = SearchForm()
    page = request.args.get('page', 1, type=int)
    
    query = Property.query
    
    if request.args.get('city'):
        query = query.filter(Property.location.contains(request.args.get('city')))
    if request.args.get('type'):
        query = query.filter_by(type=request.args.get('type'))
    if request.args.get('property_type'):
        query = query.filter_by(property_type=request.args.get('property_type'))
    if request.args.get('min_price'):
        query = query.filter(Property.price >= request.args.get('min_price'))
    if request.args.get('max_price'):
        query = query.filter(Property.price <= request.args.get('max_price'))
    
    # السطر ده هو اللي اتعدل ← استخدم query مش Property.query
    properties = query.filter_by(is_approved=True).paginate(page=page, per_page=9)
    
    return render_template('home.html', properties=properties, form=form)

@main.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    
    form = RegistrationForm()  # ← لازم السطر ده يكون موجود
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        
        new_user = User(
            username=form.username.data,
            email=form.email.data,
            password=hashed_password
        )
        new_user.is_approved = True
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('تم التسجيل بنجاح. تقدر تسجل دخول دلوقتي', 'success')
        return redirect(url_for('main.login'))
    
    return render_template('register.html', form=form)  # ← لازم تبعت form هنا

@main.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.role == 'super_admin':
            return redirect(url_for('main.manage_admins'))
        elif current_user.role == 'admin':
            return redirect(url_for('main.admin_dashboard'))
        else:
            return redirect(url_for('main.home'))
            
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user)
            
            # الكود ده مهم عشان نشوف ايه اللي بيحصل
            print(f"User Email: {user.email}")
            print(f"User Role: {user.role}")
            print(f"Check: {user.role in ['admin', 'super_admin']}")
            
            if user.role == 'super_admin':
                return redirect(url_for('main.manage_admins'))
            elif user.role == 'admin':
                return redirect(url_for('main.admin_dashboard'))
            else:
                return redirect(url_for('main.home'))
        else:
            flash('Login Unsuccessful. Please check email and password', 'danger')
    return render_template('login.html', form=form)
@main.route("/logout")
def logout():
    logout_user()
    flash('تم تسجيل الخروج بنجاح', 'info')
    return redirect(url_for('main.home'))

@main.route("/property/new", methods=['GET', 'POST'])
@login_required
def create_property():
    form = PropertyForm()
    if form.validate_on_submit():
        property = Property(
            title=form.title.data,
            description=form.description.data,
            price=form.price.data,
            location=form.location.data,
            type=form.type.data,
            property_type=form.property_type.data,
            user_id=current_user.id
        )
        db.session.add(property)
        
        if form.pictures.data:
            for picture in form.pictures.data:
                if picture and picture.filename != '':
                    picture_file = save_picture(picture)
                    image = PropertyImage(image_file=picture_file, property=property)
                    db.session.add(image)
        
        db.session.commit()
        flash('تم اضافة العقار بنجاح', 'success')
        return redirect(url_for('main.home'))
    
    if request.method == 'POST':
        print("Form Errors:", form.errors)
    
    return render_template('create_property.html', title='عقار جديد', form=form, legend='اضافة عقار جديد')

@main.route("/property/<int:property_id>")
def property_detail(property_id):
    property = Property.query.get_or_404(property_id)
    return render_template('property.html', title=property.title, property=property)

@main.route("/property/<int:property_id>/update", methods=['GET', 'POST'])
@login_required
def update_property(property_id):
    property = Property.query.get_or_404(property_id)
    if property.user_id != current_user.id:
        abort(403)
    form = PropertyForm()
    if form.validate_on_submit():
        property.title = form.title.data
        property.description = form.description.data
        property.price = form.price.data
        property.location = form.location.data
        property.type = form.type.data
        property.property_type = form.property_type.data
        
        if form.pictures.data:
            for picture in form.pictures.data:
                if picture and picture.filename != '':
                    picture_file = save_picture(picture)
                    image = PropertyImage(image_file=picture_file, property_id=property.id)
                    db.session.add(image)
                db.session.commit()
        flash('تم تحديث العقار بنجاح!', 'success')
        return redirect(url_for('main.property_detail', property_id=property.id))
    elif request.method == 'GET':
        form.title.data = property.title
        form.description.data = property.description
        form.price.data = property.price
        form.location.data = property.location
        form.type.data = property.type
        form.property_type.data = property.property_type
    return render_template('create_property.html', title='تحديث العقار', form=form, legend='تحديث العقار')


@main.route("/account")
@login_required
def account():
    user_properties = Property.query.filter_by(user_id=current_user.id).order_by(Property.date_posted.desc()).all()
    return render_template('account.html', title='حسابي', properties=user_properties)

from functools import wraps

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('يجب تسجيل الدخول أولاً', 'danger')
            return redirect(url_for('main.login'))
        
        # السطر ده اتغير: بيشيك على role بدل is_admin
        if current_user.role not in ['admin', 'super_admin']:
            flash('لازم تكون ادمن عشان تدخل الصفحة دي', 'danger')
            return redirect(url_for('main.home'))  # ← غير main.index لـ main.home
        
        return f(*args, **kwargs)
    return decorated_function

@main.route('/admin') 
@login_required
@admin_required
def admin_dashboard():
    users = User.query.all()
    properties = Property.query.all()  # لو اسم الموديل مختلف قولي
    total_users = User.query.count()
    total_properties = Property.query.count()
    properties = Property.query.order_by(Property.id.desc()).all()
    return render_template('admin/dashboard.html', 
                         users=users, 
                         properties=properties,
                         total_users=total_users,
                         total_properties=total_properties)

@main.route('/toggle_admin/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def toggle_admin(user_id):
    user = User.query.get_or_404(user_id)
    
    # حماية 1: مينفعش تعدل نفسك
    if user.id == current_user.id:
        flash('لا يمكنك تغيير صلاحياتك', 'danger')
        return redirect(url_for('main.admin_dashboard'))
    
    # حماية 2: مينفعش تعدل سوبر ادمن
    if user.role == 'super_admin':
        flash('لا يمكن تغيير صلاحية السوبر ادمن', 'danger')
        return redirect(url_for('main.admin_dashboard'))
    
    # التبديل
    if user.role == 'admin':
        user.role = 'user'
        flash(f'تم سحب صلاحية الادمن من {user.username}', 'info')
    else:
        user.role = 'admin'
        flash(f'تم ترقية {user.username} الى ادمن', 'success')
    
    db.session.commit()
    return redirect(url_for('main.admin_dashboard'))

@main.route('/delete_user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    
    # حماية 1: مينفعش تمسح نفسك
    if user.id == current_user.id:
        flash('لا يمكنك حذف نفسك', 'danger')
        return redirect(url_for('main.admin_dashboard'))
    
    # حماية 2: مينفعش تمسح سوبر ادمن
    if user.role == 'super_admin':
        flash('لا يمكن حذف السوبر ادمن', 'danger')
        return redirect(url_for('main.admin_dashboard'))
    
    username = user.username
    db.session.delete(user)
    db.session.commit()
    flash(f'تم حذف المستخدم {username}', 'success')
    return redirect(url_for('main.admin_dashboard'))



@main.route('/admin/delete_property/<int:property_id>', methods=['POST'])
@login_required
@admin_required
def delete_property(property_id):
    prop = Property.query.get_or_404(property_id)
    
    # امسح الصور من الهارد قبل ما تمسح العقار
    for image in prop.images:
        image_path = os.path.join(current_app.root_path, 'static/property_pics', image.image_file)
        try:
            if os.path.exists(image_path):
                os.remove(image_path)
        except:
            pass # لو الصورة مش موجودة كمل عادي
    
    # امسح العقار - والـ cascade هيمسح الصور من الداتابيز لوحده
    db.session.delete(prop)
    db.session.commit()
    
    flash('تم مسح العقار وصوره بنجاح', 'success')
    return redirect(url_for('main.admin_dashboard'))
from app.decorators import admin_required, super_admin_required
from app.models import User

@main.route('/admin/manage-admins')
@login_required
@super_admin_required  # كده محدش يدخلها غيرك
def manage_admins():
    # هنجيب كل الادمنز والسوبر ادمنز
    admins = User.query.filter(User.role.in_(['admin', 'super_admin'])).all()
    # هنجيب كل اليوزرز العاديين عشان تقدر ترقيهم
    users = User.query.filter_by(role='user').all()
    return render_template('admin/manage_admins.html', admins=admins, users=users)
from app import db

@main.route('/admin/promote', methods=['POST'])
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

@main.route('/admin/demote/<int:user_id>')
@login_required
@super_admin_required
def demote_user(user_id):
    user = User.query.get(user_id)
    if user and user.email != current_user.email:  # متمسحش نفسك
        user.role = 'user'
        db.session.commit()
        flash(f'تم إلغاء اشراف {user.email}', 'success')
    return redirect(url_for('main.manage_admins'))
@main.route('/admin/promote/<int:user_id>', methods=['POST'])
@login_required
def promote_admin(user_id):
    if current_user.role != 'super_admin':
        abort(403)
    user = User.query.get_or_404(user_id)
    if user.role == 'user':
        user.role = 'admin'
    elif user.role == 'admin':
        user.role = 'super_admin'
    db.session.commit()
    flash(f'تم ترقية {user.username}', 'success')
    return redirect(url_for('main.manage_admins'))

@main.route('/admin/demote/<int:user_id>', methods=['POST'])
@login_required
def demote_admin(user_id):
    if current_user.role != 'super_admin':
        abort(403)
    user = User.query.get_or_404(user_id)
    if user.role == 'super_admin':
        user.role = 'admin'
    elif user.role == 'admin':
        user.role = 'user'
    db.session.commit()
    flash(f'تم تخفيض {user.username}', 'success')
    return redirect(url_for('main.manage_admins'))
@main.route('/admin/approve_property/<int:property_id>', methods=['POST'])
@login_required
def approve_property(property_id):
    if current_user.role not in ['admin', 'super_admin']:
        abort(403)
    
    property = Property.query.get_or_404(property_id)
    property.is_approved = True
    db.session.commit()
    flash(f'تم قبول العقار: {property.title}', 'success')
    return redirect(url_for('main.admin_dashboard'))


@main.route('/admin/reject_property/<int:property_id>', methods=['POST'])
@login_required
def reject_property(property_id):
    if current_user.role not in ['admin', 'super_admin']:
        abort(403)
    
    property = Property.query.get_or_404(property_id)
    property.is_approved = False
    db.session.commit()
    flash(f'تم رفض العقار: {property.title}', 'warning')
    return redirect(url_for('main.admin_dashboard'))
@main.route('/admin/properties_partial')
@login_required
def admin_properties_partial():
    if current_user.role not in ['admin', 'super_admin']:
        abort(403)
    pending = Property.query.filter_by(is_approved=False).order_by(Property.date_posted.desc()).all()
    return render_template('admin/admin_properties_partial.html', pending=pending)

