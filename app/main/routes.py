from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
import os
from app import db, bcrypt
from app.models import User, Property, PropertyImage

main = Blueprint('main', __name__)

@main.route('/')
def home():
    properties = Property.query.filter_by(is_approved=True, is_rejected=False).order_by(Property.date_posted.desc()).all()
    return render_template('home.html', properties=properties)

@main.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        if User.query.filter_by(email=email).first():
            flash('الايميل موجود بالفعل', 'danger')
            return redirect(url_for('main.register'))
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        user = User(username=username, email=email, password=hashed_password)
        db.session.add(user)
        db.session.commit()
        flash('تم انشاء الحساب بنجاح', 'success')
        return redirect(url_for('main.login'))
    return render_template('register.html')

@main.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('main.home'))
        else:
            flash('بيانات الدخول غير صحيحة', 'danger')
    return render_template('login.html')

@main.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('main.home'))

# === ده المهم - من غير login_required عشان يفتح للزوار ===
@main.route('/property/new', methods=['GET', 'POST'])
def create_property():
    if request.method == 'POST':
        title = request.form.get('title')
        price = request.form.get('price')
        description = request.form.get('description')
        location = request.form.get('location')
        phone = request.form.get('phone')
        whatsapp = request.form.get('whatsapp')
        property_type = request.form.get('property_type', 'شقة')
        type_ = request.form.get('type', 'بيع')
        
        # لو مسجل ياخد id بتاعه، لو زائر يبقى None
        owner_id = current_user.id if current_user.is_authenticated else None
        
        prop = Property(
            title=title,
            price=int(price) if price else 0,
            description=description,
            location=location,
            phone=phone,
            whatsapp=whatsapp,
            property_type=property_type,
            type=type_,
            user_id=owner_id,
            is_approved=False
        )
        db.session.add(prop)
        db.session.commit()
        
        # حفظ الصور لو فيه
        if 'images' in request.files:
            files = request.files.getlist('images')
            for file in files:
                if file.filename:
                    filename = secure_filename(file.filename)
                    upload_path = os.path.join(current_app.root_path, 'static/property_pics', filename)
                    os.makedirs(os.path.dirname(upload_path), exist_ok=True)
                    file.save(upload_path)
                    img = PropertyImage(image_file=filename, property_id=prop.id)
                    db.session.add(img)
            db.session.commit()
        
        flash('تم اضافة العقار بنجاح، في انتظار موافقة الادمن', 'success')
        return redirect(url_for('main.home'))
    
    return render_template('create_property.html')

@main.route('/property/<int:property_id>')
def property_detail(property_id):
    prop = Property.query.get_or_404(property_id)
    prop.views = (prop.views or 0) + 1
    db.session.commit()
    return render_template('property_detail.html', property=prop)
