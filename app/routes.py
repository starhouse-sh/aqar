import os
import secrets
from flask import Blueprint, render_template, url_for, flash, redirect, request, current_app, abort
from app import db, bcrypt
from app.forms import RegistrationForm, LoginForm, PropertyForm
from app.models import User, Property, PropertyImage
from flask_login import login_user, current_user, logout_user, login_required
from app.models import User, Property
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
    form = PropertyForm()
    page = request.args.get('page', 1, type=int)
    
    query = Property.query
    
    # فلترة البحث
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
    
    properties = query.order_by(Property.created_at.desc()).paginate(page=page, per_page=6)
    
    return render_template('home.html', properties=properties, form=form)

@main.route("/register", methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(username=form.username.data,
                    email=form.email.data,
                    password=hashed_password)
        db.session.add(user)
        db.session.commit()
        flash('تم انشاء الحساب بنجاح! يمكنك تسجيل الدخول الآن', 'success')
        return redirect(url_for('main.login'))
    return render_template('register.html', title='انشاء حساب', form=form)

@main.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user, remember=True)
            next_page = request.args.get('next')
            flash('تم تسجيل الدخول بنجاح!', 'success')
            return redirect(next_page) if next_page else redirect(url_for('main.home'))
        else:
            flash('فشل تسجيل الدخول. تأكد من البريد الالكتروني وكلمة المرور', 'danger')
    return render_template('login.html', title='تسجيل الدخول', form=form)

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

@main.route("/property/<int:property_id>/delete", methods=['POST'])
@login_required
def delete_property(property_id):
    property = Property.query.get_or_404(property_id)
    if property.user_id != current_user.id:
        abort(403)
    
    # حذف الصور من السيرفر
    for image in property.images:
        image_path = os.path.join(current_app.root_path, 'static/property_pics', image.image_file)
        if os.path.exists(image_path):
            os.remove(image_path)
    
    db.session.delete(property)
    db.session.commit()
    flash('تم حذف العقار بنجاح!', 'success')
    return redirect(url_for('main.home'))

@main.route("/account")
@login_required
def account():
    user_properties = Property.query.filter_by(user_id=current_user.id).order_by(Property.created_at.desc()).all()
    return render_template('account.html', title='حسابي', properties=user_properties)

from functools import wraps

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('لازم تكون ادمن عشان تدخل الصفحة دي', 'danger')
            return redirect(url_for('main.index'))  # ده صح عندك عشان login_view = 'main.login'
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
    
    return render_template('admin/dashboard.html', 
                         users=users, 
                         properties=properties,
                         total_users=total_users,
                         total_properties=total_properties)