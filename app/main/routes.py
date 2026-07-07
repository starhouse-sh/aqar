from flask import Blueprint, render_template, redirect, url_for, flash, request
from app.models import User, Property
from app.forms import RegisterForm, LoginForm, PropertyForm
from app.extensions import db, bcrypt
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
import os

main = Blueprint('main', __name__)

def save_picture(form_picture):
    random_hex = os.urandom(8).hex()
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join('app/static/property_pics', picture_fn)
    form_picture.save(picture_path)
    return picture_fn

@main.route('/')
@main.route('/home')
def home():
    properties = Property.query.filter_by(is_approved=True).all()  # ← ده أهم سطر
    print(f"عدد العقارات المعروضة: {len(properties)}")  # ← ضيف ده عشان تتأكد
    return render_template('home.html', properties=properties)

@main_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        # اعمل check الاول
        user_by_email = User.query.filter_by(email=email).first()
        if user_by_email:
            flash('الايميل ده متسجل قبل كده، جرب تسجل دخول', 'danger')
            return redirect(url_for('main.register'))
        
        user_by_username = User.query.filter_by(username=username).first()
        if user_by_username:
            flash('اسم المستخدم ده موجود، اختار اسم تاني', 'danger')
            return redirect(url_for('main.register'))
        
        # لو كله تمام، اعمل اليوزر
        hashed_password = generate_password_hash(password)
        new_user = User(username=username, email=email, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        
        flash('تم التسجيل بنجاح! سجل دخول دلوقتي', 'success')
        return redirect(url_for('main.login'))
    
    return render_template('register.html',form = form)

@main.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            user = User(name=form.name.data,
            email=form.email.data,
            password=hashed_password,
            company_name=form.company_name.data)
            next_page = request.args.get('next')
            flash('تم تسجيل الدخول بنجاح', 'success')
            return redirect(next_page) if next_page else redirect(url_for('main.home'))
        else:
            flash('الايميل أو كلمة المرور غلط', 'danger')
    return render_template('login.html', form=form)

@main.route('/logout')
def logout():
    logout_user()
    flash('تم تسجيل الخروج', 'info')
    return redirect(url_for('main.home'))

@main.route('/property/new', methods=['GET', 'POST'])
def new_property():
    form = PropertyForm()
    if form.validate_on_submit():
        image_file = 'default.jpg'
        if form.image.data:
            image_file = save_picture(form.image.data)
        
        user_id = current_user.id if current_user.is_authenticated else None
            
        property = Property(
            user_id=user_id,
            title=form.title.data,
            price=form.price.data,
            type=form.type.data,
            property_type=form.property_type.data,
            area=form.area.data,
            rooms=form.rooms.data,
            baths=form.baths.data,
            floor=form.floor.data,
            address=form.address.data,
            city=form.city.data,
            description=form.description.data,
            image_file=image_file
            is_approved=false
        )
        db.session.add(property)
        db.session.commit()
        flash('تم إضافة العقار بنجاح!', 'success')
        return redirect(url_for('main.home'))
    return render_template('create_property.html', form=form, legend='إضافة عقار جديد')