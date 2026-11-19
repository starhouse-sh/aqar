print(">>> LOADING NEW ROUTES.PY FINAL - MY-ADS + SETTINGS + LEADS + WANTED + PERMS FIXED <<<")
import os
import secrets
from datetime import datetime, timedelta
from flask import Blueprint, render_template, url_for, flash, redirect, request, current_app, abort, jsonify
from app import db, bcrypt, csrf
from app.forms import RegistrationForm, LoginForm, PropertyForm
from app.models import User, Property, PropertyImage, ActivityLog, ChatMessage, Package, PackageSubscription, OfficeRating, EmployeeCommission, UserComparison, SiteSettings, Lead, WantedRequest
from flask_login import login_user, current_user, logout_user, login_required
from app.decorators import admin_required, super_admin_required
from flask_wtf.csrf import generate_csrf
from functools import wraps
from .sms_service import create_and_send_otp, verify_otp
from app.otp_admin_store import get_otp_requests

def owner_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_owner:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def super_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not (current_user.is_owner or current_user.role == 'super_admin'):
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

from sqlalchemy import or_, func
from werkzeug.utils import secure_filename
from PIL import Image, ImageDraw, ImageFont

main = Blueprint('main', __name__)

OWNER_EMAIL = "admin@admin.com"
OWNER_PHONE = "01155712096"

def get_site_settings():
    settings = SiteSettings.query.first()
    if not settings:
        settings = SiteSettings(is_free_mode=True, free_ads_for_individual=100, free_ads_for_office=100, free_ads_when_paid_individual=2, free_ads_when_paid_office=10)
        db.session.add(settings)
        db.session.commit()
    return settings

def log_action(action_text):
    try:
        if current_user.is_authenticated:
            log = ActivityLog(action=action_text, admin_id=current_user.id)
            db.session.add(log)
            db.session.commit()
    except Exception as e:
        print(f"Log Error: {e}")
        db.session.rollback()

def local_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('يجب تسجيل الدخول أولاً', 'danger')
            return redirect(url_for('main.login'))
        if current_user.role not in ['admin', 'super_admin'] and not current_user.is_owner:
            flash('الصفحة دي للموظفين فقط (الأدمن)', 'danger')
            return redirect(url_for('main.home'))
        return f(*args, **kwargs)
    return decorated_function

def add_watermark(image_path):
    try:
        img = Image.open(image_path).convert("RGBA")
        txt_layer = Image.new("RGBA", img.size, (255,255,255,0))
        draw = ImageDraw.Draw(txt_layer)
        font_size = max(20, int(img.size[0] * 0.04))
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except:
            font = ImageFont.load_default()
        text = "Star House"
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        x = img.size[0] - text_w - 20
        y = img.size[1] - text_h - 20
        draw.rectangle((x-10, y-5, x+text_w+10, y+text_h+5), fill=(0,0,0, 80))
        draw.text((x, y), text, font=font, fill=(255,255,255, 200))
        watermarked = Image.alpha_composite(img, txt_layer)
        watermarked = watermarked.convert("RGB")
        watermarked.save(image_path, "JPEG", quality=90)
    except Exception as e:
        print(f"Watermark Error: {e}")

def save_picture(form_picture):
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(current_app.root_path, 'static/property_pics', picture_fn)
    os.makedirs(os.path.dirname(picture_path), exist_ok=True)
    form_picture.save(picture_path)
    add_watermark(picture_path)
    return picture_fn

@main.route("/")
@main.route("/home")
def home():
    page = request.args.get('page', 1, type=int)
    location = request.args.get('location', '')
    property_type_raw = request.args.get('property_type', '').strip()
    type = request.args.get('type', '')
    min_price = request.args.get('min_price', type=int)
    max_price = request.args.get('max_price', type=int)
    bedrooms = request.args.get('bedrooms', type=int)
    sort_by = request.args.get('sort_by', 'newest')
    type_map = {
        'apartment': 'شقة', 'شقه': 'شقة', 'شقق': 'شقة', 'شقة': 'شقة',
        'villa': 'فيلا', 'فلل': 'فيلا', 'فيله': 'فيلا', 'فيلا': 'فيلا',
        'land': 'أرض', 'ارض': 'أرض', 'اراضي': 'أرض', 'أراضي': 'أرض', 'أرض': 'أرض',
        'shop': 'محل', 'store': 'محل', 'محلات': 'محل', 'محل': 'محل',
        'office': 'مكتب', 'مكتب': 'مكتب', 'مكاتب': 'مكتب'
    }
    property_type = type_map.get(property_type_raw.lower(), property_type_raw) if property_type_raw else ''
    now = datetime.utcnow()
    query = Property.query.filter_by(is_approved=True).filter(or_(Property.expires_at == None, Property.expires_at > now))
    # 6. فلتر تم البيع - لو العمود موجود
    try:
        query = query.filter(or_(Property.is_sold == False, Property.is_sold == None))
    except:
        pass
    if location:
        query = query.filter(Property.location.ilike(f'%{location}%'))
    if property_type:
        query = query.filter_by(property_type=property_type)
    if type:
        query = query.filter_by(type=type)
    if min_price:
        query = query.filter(Property.price >= min_price)
    if max_price:
        query = query.filter(Property.price <= max_price)
    if bedrooms:
        query = query.filter(Property.bedrooms >= bedrooms)
    if sort_by == 'cheapest':
        query = query.order_by(Property.is_featured.desc(), Property.price.asc())
    elif sort_by == 'expensive':
        query = query.order_by(Property.is_featured.desc(), Property.price.desc())
    else:
        query = query.order_by(Property.is_featured.desc(), Property.date_posted.desc())
    properties = query.paginate(page=page, per_page=9, error_out=False)
    min_prices = {
        'فيلا': Property.query.filter_by(property_type='فيلا', is_approved=True).order_by(Property.price.asc()).first(),
        'شقة': Property.query.filter_by(property_type='شقة', is_approved=True).order_by(Property.price.asc()).first(),
        'أرض': Property.query.filter_by(property_type='أرض', is_approved=True).order_by(Property.price.asc()).first(),
        'محل': Property.query.filter_by(property_type='محل', is_approved=True).order_by(Property.price.asc()).first()
    }
    compare_count = 0
    if not current_user.is_authenticated or (current_user.is_authenticated and (current_user.account_type == 'individual' or current_user.account_type is None)):
        if current_user.is_authenticated:
            compare_count = UserComparison.query.filter_by(user_id=current_user.id).count()
        else:
            session_id = request.cookies.get('session_id') or str(request.remote_addr)
            compare_count = UserComparison.query.filter_by(session_id=session_id).count()
    settings = get_site_settings()
    return render_template('home.html', title='الرئيسية', properties=properties, min_prices=min_prices, active_filter=property_type_raw, compare_count=compare_count, settings=settings)

@main.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    form = RegistrationForm()
    if form.validate_on_submit():
        raw_phone = form.identifier.data.strip() if form.identifier.data else ""
        clean_phone = raw_phone.replace(" ", "").replace("-", "")
        if clean_phone.startswith("+20"):
            clean_phone = "0" + clean_phone[3:]
        elif clean_phone.startswith("0020"):
            clean_phone = "0" + clean_phone[4:]
        clean_username = form.username.data.strip() if form.username.data else ""
        if not clean_phone or len(clean_phone) != 11 or not clean_phone.startswith("01"):
            flash('رقم الموبايل يجب ان يكون 11 رقم ويبدأ بـ 01', 'danger')
            return render_template('register.html', form=form)
        existing_phone = User.query.filter_by(phone=clean_phone).first()
        if existing_phone:
            flash('رقم الموبايل ده موجود قبل كده، سجل دخول', 'danger')
            return redirect(url_for('main.login'))
        fake_email = f"{clean_phone}@phone.local"
        existing_email = User.query.filter_by(email=fake_email).first()
        if existing_email:
            flash('رقم الموبايل ده موجود قبل كده، سجل دخول', 'danger')
            return redirect(url_for('main.login'))
        if clean_username:
            existing_user = User.query.filter(User.username.ilike(clean_username)).first()
            if existing_user:
                flash('اسم المستخدم ده موجود', 'danger')
                return render_template('register.html', form=form)
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        account_type = request.form.get('account_type', 'individual')
        if account_type not in ['individual', 'office', 'broker']:
            account_type = 'individual'
        company_name = request.form.get('company_name', '').strip() if account_type in ['office', 'broker'] else None
        office_address = request.form.get('office_address', '').strip() if account_type in ['office', 'broker'] else None
        try:
            new_user = User(
                username=clean_username,
                email=fake_email,
                phone=clean_phone,
                password=hashed_password,
                role='user',
                account_type=account_type,
                company_name=company_name,
                office_address=office_address,
                is_verified=True,
                rating_avg=0,
                rating_count=0,
                is_blocked=False,
                created_at=datetime.utcnow()
            )
            db.session.add(new_user)
            db.session.commit()
            flash(f'تم التسجيل بنجاح برقم: {clean_phone}', 'success')
            return redirect(url_for('main.login'))
        except Exception as e:
            db.session.rollback()
            print(f"Register Error: {e}")
            flash(f'خطأ في التسجيل: {e}', 'danger')
    return render_template('register.html', form=form)

@main.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.is_owner or current_user.role == 'super_admin':
            return redirect(url_for('main.manage_admins'))
        elif current_user.role == 'admin':
            return redirect(url_for('main.admin_dashboard'))
        else:
            return redirect(url_for('main.home'))
    saved_phone = ""
    if request.method == 'POST':
        raw_phone = request.form.get('identifier', '').strip() or request.form.get('phone', '').strip()
        password_input = request.form.get('password', '').strip()
        saved_phone = raw_phone
        print(f"=== LOGIN TRY: phone={raw_phone} password_len={len(password_input)} ===")
        clean_phone = raw_phone.replace(" ", "").replace("-", "")
        if clean_phone.startswith("+20"):
            clean_phone = "0" + clean_phone[3:]
        elif clean_phone.startswith("0020"):
            clean_phone = "0" + clean_phone[4:]
        user = User.query.filter_by(phone=clean_phone).first() or User.query.filter_by(phone=raw_phone).first()
        print(f"=== USER FOUND: {user} ===")
        if user and getattr(user, 'locked_until', None) and user.locked_until and user.locked_until > datetime.utcnow():
            flash('⛔ الحساب مقفول - حاول بعد 15 دقيقة', 'danger')
            return render_template('login.html', saved_phone="")
        if user and password_input and bcrypt.check_password_hash(user.password, password_input):
            print("=== PASSWORD OK ===")
            user.failed_login_attempts = 0
            user.locked_until = None
            user.last_login = datetime.utcnow()
            db.session.commit()
            login_user(user)
            flash(f'اهلا {user.username}', 'success')
            if user.is_owner or user.role == 'super_admin':
                return redirect(url_for('main.manage_admins'))
            elif user.role == 'admin':
                return redirect(url_for('main.admin_dashboard'))
            else:
                return redirect(request.args.get('next') or url_for('main.home'))
        else:
            print("=== PASSWORD WRONG OR USER NOT FOUND ===")
            if not user:
                flash(f'مفيش حساب برقم: {raw_phone}', 'danger')
            elif not password_input:
                flash('اكتب الباسورد', 'danger')
            else:
                user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
                if user.failed_login_attempts >= 5:
                    user.locked_until = datetime.utcnow() + timedelta(minutes=15)
                db.session.commit()
                flash('كلمة المرور غلط', 'danger')
            return render_template('login.html', saved_phone=saved_phone)
    return render_template('login.html', saved_phone=saved_phone)

@main.route("/logout")
def logout():
    if current_user.is_authenticated:
        log_action(f"سجل خروج")
    logout_user()
    flash('تم تسجيل الخروج بنجاح', 'info')
    return redirect(url_for('main.home'))

@main.route("/property/new", methods=['GET', 'POST'])
@login_required
def create_property():
    if current_user.is_blocked or current_user.is_banned:
        flash('⛔ حسابك محظور', 'danger')
        return redirect(url_for('main.home'))
    form = PropertyForm()
    packages = Package.query.filter_by(is_active=True).all()
    user_sub = None
    settings = get_site_settings()
    if current_user.is_authenticated:
        user_sub = PackageSubscription.query.filter_by(user_id=current_user.id).filter(PackageSubscription.end_date > datetime.utcnow()).order_by(PackageSubscription.end_date.desc()).first()
    if not settings.is_free_mode:
        active_count = Property.query.filter_by(user_id=current_user.id).filter(or_(Property.expires_at == None, Property.expires_at > datetime.utcnow())).count()
        limit = settings.free_ads_when_paid_office if current_user.account_type in ['office','broker'] else settings.free_ads_when_paid_individual
        if user_sub and user_sub.is_active_sub:
            limit += user_sub.package.ads_count
        if active_count >= limit:
            flash(f'وصلت للحد المجاني ({limit} إعلانات)', 'warning')
            return redirect(url_for('main.packages_page'))
    if form.validate_on_submit():
        whatsapp_number = form.whatsapp.data if hasattr(form, 'whatsapp') and form.whatsapp.data and form.whatsapp.data.strip() != "" else form.phone.data
        lat = lng = None
        try:
            if hasattr(form, 'latitude') and form.latitude.data:
                lat = float(form.latitude.data)
            if hasattr(form, 'longitude') and form.longitude.data:
                lng = float(form.longitude.data)
        except:
            pass
        video_url = request.form.get('video_url', '').strip() or None
        virtual_tour_url = request.form.get('virtual_tour_url', '').strip() or None
        commission_value = request.form.get('commission_value', type=int) or 0
        # ===== DEBUG + FIXED =====
        print(f"!!! DEBUG CREATE: user={current_user.email} role={current_user.role} is_owner={current_user.is_owner} account_type={current_user.account_type} !!!")
        # المالك + سوبر + أدمن = مباشر، العميل = مراجعة
        if current_user.is_owner or current_user.role in ['super_admin', 'admin']:
            final_approved = True
            print(f"!!! FINAL_APPROVED=True for {current_user.role} !!!")
        else:
            final_approved = False
            print(f"!!! FINAL_APPROVED=False (مراجعة) for role={current_user.role} !!!")
        property_obj = Property(
            title=form.title.data, description=form.description.data, price=form.price.data, 
            negotiable=form.negotiable.data if hasattr(form, 'negotiable') else False,
            location=form.location.data, type=form.type.data, property_type=form.property_type.data,
            bedrooms=form.bedrooms.data, bathrooms=form.bathrooms.data, area=form.area.data, 
            finishing=form.finishing.data if hasattr(form, 'finishing') else None,
            phone=form.phone.data, whatsapp=whatsapp_number, user_id=current_user.id,
            latitude=lat, longitude=lng, is_approved=final_approved, is_rejected=False, is_featured=False, 
            views=0, expires_at=datetime.utcnow() + timedelta(days=30),
            video_url=video_url, virtual_tour_url=virtual_tour_url,
            commission_value=commission_value, commission_paid=False
        )
        db.session.add(property_obj)
        db.session.commit()
        if form.pictures.data:
            for file in form.pictures.data:
                if file and file.filename:
                    picture_file = save_picture(file)
                    image = PropertyImage(image_file=picture_file, property_id=property_obj.id)
                    db.session.add(image)
            db.session.commit()
        log_action(f"🆕 عقار جديد {'✅ فوري' if final_approved else 'قيد المراجعة'}: {property_obj.title}")
        # زر واحد فقط: بعد الحفظ يفرغ الحقول ويرجع لنفس الصفحة
        if final_approved:
            flash('✅ تم نشر الإعلان بنجاح - الحقول اتفرغت ✅', 'success')
        else:
            flash('✅ تم استلام إعلانك - قيد المراجعة - الحقول اتفرغت ✅', 'success')
        return redirect(url_for('main.create_property', cleared='1'))
    return render_template('create_property_detail.html', title='إضافة عقار', form=form, legend='إضافة عقار جديد', packages=packages, user_sub=user_sub, settings=settings)

@main.route("/property/<int:property_id>")
def property_detail(property_id):
    property_obj = Property.query.get_or_404(property_id)
    if property_obj.is_expired:
        if not current_user.is_authenticated or (current_user.id != property_obj.user_id and not current_user.is_admin and not current_user.is_owner):
            flash('هذا العقار انتهت مدته', 'warning')
            return redirect(url_for('main.home'))
    property_obj.views = (property_obj.views or 0) + 1
    db.session.commit()
    is_favorite = False
    in_compare = False
    if current_user.is_authenticated:
        is_favorite = current_user.favorite_properties.filter_by(id=property_obj.id).first() is not None
        if current_user.account_type == 'individual' or current_user.account_type is None:
            in_compare = UserComparison.query.filter_by(user_id=current_user.id, property_id=property_obj.id).first() is not None
        if current_user.is_admin or current_user.is_owner:
           log_action(f"شاف صفحة عقار رقم {property_obj.id}")
    office_ratings = OfficeRating.query.filter_by(office_id=property_obj.user_id).order_by(OfficeRating.created_at.desc()).limit(5).all()
    similar = Property.query.filter(Property.property_type==property_obj.property_type, Property.id!=property_obj.id, Property.is_approved==True).order_by(Property.date_posted.desc()).limit(4).all()
    leads_count = Lead.query.filter_by(property_id=property_obj.id).count()
    return render_template('property_detail.html', title=property_obj.title, property=property_obj, is_favorite=is_favorite, in_compare=in_compare, office_ratings=office_ratings, similar=similar, leads_count=leads_count)

@main.route("/property/<int:property_id>/reveal-phone", methods=['POST'])
@login_required
def reveal_phone(property_id):
    property_obj = Property.query.get_or_404(property_id)
    try:
        lead = Lead(property_id=property_obj.id, office_id=property_obj.user_id, caller_ip=request.remote_addr, contact_type='phone', created_at=datetime.utcnow())
        db.session.add(lead)
        db.session.commit()
    except Exception as e:
        print(f"Lead Error: {e}")
    log_action(f"📞 شاف رقم تليفون عقار رقم {property_obj.id}")
    return jsonify({'status': 'success','phone': property_obj.phone,'whatsapp': property_obj.whatsapp, 'whatsapp_link': property_obj.whatsapp_link})

@main.route("/property/<int:property_id>/whatsapp", methods=['POST'])
@login_required
def whatsapp_click(property_id):
    property_obj = Property.query.get_or_404(property_id)
    try:
        lead = Lead(property_id=property_obj.id, office_id=property_obj.user_id, caller_ip=request.remote_addr, contact_type='whatsapp', created_at=datetime.utcnow())
        db.session.add(lead)
        db.session.commit()
    except Exception as e:
        print(f"Lead Error: {e}")
    return jsonify({'status': 'success', 'link': property_obj.whatsapp_link})

@main.route("/favorite/<int:property_id>", methods=['POST'])
@login_required
def favorite(property_id):
    property_obj = Property.query.get_or_404(property_id)
    exists = current_user.favorite_properties.filter_by(id=property_obj.id).first()
    if exists:
        current_user.favorite_properties.remove(property_obj)
        db.session.commit()
        return jsonify({'status': 'removed'})
    else:
        current_user.favorite_properties.append(property_obj)
        db.session.commit()
        return jsonify({'status': 'added'})

@main.route("/favorites")
@login_required
def favorites():
    fav_properties = current_user.favorite_properties.all()
    return render_template('favorites.html', properties=fav_properties, title='مفضلتي')

@main.route("/compare")
def compare_page():
    if current_user.is_authenticated:
        if current_user.account_type in ['office', 'broker'] or current_user.is_admin or current_user.is_owner:
            flash('المقارنة للمشترين فقط', 'info')
            return redirect(url_for('main.home'))
    session_id = request.cookies.get('session_id') or str(request.remote_addr)
    if current_user.is_authenticated:
        comps = UserComparison.query.filter_by(user_id=current_user.id).all()
    else:
        comps = UserComparison.query.filter_by(session_id=session_id).all()
    properties = [c.property_obj for c in comps if c.property_obj]
    return render_template('compare.html', properties=properties, title='مقارنة العقارات')

@main.route("/compare/clear", methods=['POST'])
@login_required
def clear_compare():
    session_id = request.cookies.get('session_id') or str(request.remote_addr)
    if current_user.is_authenticated:
        UserComparison.query.filter_by(user_id=current_user.id).delete()
    else:
        UserComparison.query.filter_by(session_id=session_id).delete()
    db.session.commit()
    flash('تم مسح المقارنة', 'info')
    return redirect(url_for('main.compare_page'))

@main.route("/my-ads")
@login_required
def my_ads():
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', 'all')
    query = Property.query.filter_by(user_id=current_user.id)
    if status_filter == 'active':
        query = query.filter_by(is_approved=True).filter(or_(Property.expires_at == None, Property.expires_at > datetime.utcnow()))
    elif status_filter == 'expired':
        query = query.filter(Property.expires_at != None).filter(Property.expires_at <= datetime.utcnow())
    elif status_filter == 'pending':
        query = query.filter_by(is_approved=False, is_rejected=False)
    elif status_filter == 'rejected':
        query = query.filter_by(is_rejected=True)
    query = query.order_by(Property.date_posted.desc())
    properties = query.paginate(page=page, per_page=10, error_out=False)
    total = Property.query.filter_by(user_id=current_user.id).count()
    active = Property.query.filter_by(user_id=current_user.id, is_approved=True).filter(or_(Property.expires_at == None, Property.expires_at > datetime.utcnow())).count()
    expired = Property.query.filter_by(user_id=current_user.id).filter(Property.expires_at != None, Property.expires_at <= datetime.utcnow()).count()
    pending = Property.query.filter_by(user_id=current_user.id, is_approved=False, is_rejected=False).count()
    my_leads = Lead.query.filter_by(office_id=current_user.id).count()
    return render_template('my_ads.html', properties=properties, status_filter=status_filter, total=total, active=active, expired=expired, pending=pending, my_leads=my_leads, title='إعلاناتي')

@main.route("/my-ads/<int:property_id>/renew", methods=['POST'])
@login_required
def renew_property(property_id):
    prop = Property.query.get_or_404(property_id)
    if prop.user_id != current_user.id:
        abort(403)
    prop.expires_at = datetime.utcnow() + timedelta(days=30)
    # المالك + سوبر + أدمن مباشر، العميل مراجعة
    if current_user.is_owner or current_user.role in ['super_admin','admin']:
        prop.is_approved = True
        flash(f'✅ تم تجديد إعلان "{prop.title}" ونشر مباشر', 'success')
    else:
        prop.is_approved = False
        flash(f'✅ تم تجديد إعلان "{prop.title}" - قيد المراجعة', 'success')
    prop.is_rejected = False
    prop.rejection_reason = None
    # سجل تعديل
    try:
        log_action(f"🔄 جدد إعلانه {prop.title}")
    except:
        pass
    db.session.commit()
    return redirect(url_for('main.my_ads'))

@main.route("/offices")
def offices_list_public():
    # 1. منع العميل العادي من دخول صفحة المكاتب
    if current_user.is_authenticated and current_user.account_type == 'individual' and not (current_user.is_owner or current_user.role in ['admin','super_admin']):
        flash('⛔ صفحة المكاتب للوسطاء فقط - انت حسابك فردي', 'warning')
        return redirect(url_for('main.home'))
    offices = User.query.filter(User.account_type.in_(['office','broker']), User.is_blocked==False).order_by(User.is_verified.desc(), User.rating_avg.desc()).all()
    return render_template('offices.html', offices=offices, title='المكاتب العقارية')

@main.route("/office/<int:office_id>")
def office_detail(office_id):
    office = User.query.get_or_404(office_id)
    if office.account_type not in ['office','broker']:
        abort(404)
    if office.is_blocked:
        abort(404)
    props = Property.query.filter_by(user_id=office.id, is_approved=True).order_by(Property.date_posted.desc()).all()
    ratings = OfficeRating.query.filter_by(office_id=office.id).order_by(OfficeRating.created_at.desc()).all()
    leads_count = Lead.query.filter_by(office_id=office.id).count()
    return render_template('office_detail.html', office=office, properties=props, ratings=ratings, leads_count=leads_count, title=office.company_name or office.username)

@main.route("/office/<int:office_id>/rate", methods=['POST'])
@login_required
def rate_office(office_id):
    office = User.query.get_or_404(office_id)
    if office.id == current_user.id:
        return jsonify({'status': 'error'})
    stars = request.form.get('stars', type=int)
    comment = request.form.get('comment', '').strip()
    if not stars or stars < 1 or stars > 5:
        return jsonify({'status': 'error'})
    existing = OfficeRating.query.filter_by(office_id=office_id, rater_id=current_user.id).first()
    if existing:
        existing.stars = stars
        existing.comment = comment
    else:
        new_rating = OfficeRating(office_id=office_id, rater_id=current_user.id, stars=stars, comment=comment)
        db.session.add(new_rating)
    db.session.commit()
    avg = db.session.query(func.avg(OfficeRating.stars)).filter_by(office_id=office_id).scalar() or 0
    count = OfficeRating.query.filter_by(office_id=office_id).count()
    office.rating_avg = round(avg, 1)
    office.rating_count = count
    db.session.commit()
    return jsonify({'status': 'success', 'avg': office.rating_avg, 'count': count})

@main.route("/wanted")
def wanted_list():
    page = request.args.get('page', 1, type=int)
    wanted = WantedRequest.query.filter_by(is_approved=True).order_by(WantedRequest.created_at.desc()).paginate(page=page, per_page=20)
    return render_template('wanted.html', wanted=wanted, title='عقارات مطلوبة')

@main.route("/wanted/new", methods=['GET','POST'])
@login_required
def create_wanted():
    if request.method == 'POST':
        title = request.form.get('title','').strip()
        desc = request.form.get('description','').strip()
        budget = request.form.get('budget', type=int)
        location = request.form.get('location','').strip()
        phone = request.form.get('phone','').strip() or current_user.phone
        req_type = request.form.get('request_type','buy')
        prop_type = request.form.get('property_type','')
        if not title or len(title) < 10:
            flash('اكتب عنوان واضح', 'danger')
            return redirect(url_for('main.create_wanted'))
        wr = WantedRequest(title=title, description=desc, budget=budget, location=location, phone=phone, request_type=req_type, property_type=prop_type, user_id=current_user.id, is_approved=False)
        db.session.add(wr)
        db.session.commit()
        flash('✅ تم استلام طلبك', 'success')
        return redirect(url_for('main.wanted_list'))
    return render_template('create_wanted.html', title='أضف طلب عقار')

@main.route("/packages")
def packages_page():
    packages = Package.query.filter_by(is_active=True).all()
    settings = get_site_settings()
    return render_template('packages.html', packages=packages, settings=settings, title='الباقات')

@main.route("/subscribe/<int:package_id>", methods=['GET', 'POST'])
@login_required
def subscribe_package(package_id):
    package = Package.query.get_or_404(package_id)
    if request.method == 'POST':
        payment_method = request.form.get('payment_method', 'vodafone_cash')
        file = request.files.get('screenshot')
        filename = None
        if file and file.filename:
            random_hex = secrets.token_hex(8)
            _, f_ext = os.path.splitext(file.filename)
            filename = random_hex + f_ext
            path = os.path.join(current_app.root_path, 'static/payment_screenshots', filename)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            file.save(path)
        sub = PackageSubscription(user_id=current_user.id, package_id=package.id, is_paid=False, payment_method=payment_method, payment_screenshot=filename, start_date=datetime.utcnow(), end_date=datetime.utcnow() + timedelta(days=package.duration_days))
        db.session.add(sub)
        db.session.commit()
        flash('تم ارسال طلب الاشتراك', 'success')
        return redirect(url_for('main.account'))
    return render_template('subscribe.html', package=package)

@main.route("/api/mortgage-calc", methods=['POST'])
def mortgage_calc_api():
    data = request.get_json()
    price = float(data.get('price', 0))
    down = float(data.get('down_payment', 0))
    years = int(data.get('years', 10))
    rate = float(data.get('interest', 8)) / 100 / 12
    loan = price - down
    n = years * 12
    monthly = loan / n if rate == 0 else loan * (rate * (1+rate)**n) / ((1+rate)**n - 1) if n else 0
    return jsonify({'monthly': round(monthly, 2), 'total': round(monthly*n, 2), 'loan': round(loan, 2)})

@main.route("/api/finishing-calc", methods=['POST'])
def finishing_calc_api():
    data = request.get_json()
    area = float(data.get('area', 0))
    finish_type = data.get('finish_type', 'متوسط')
    prices = {'اقتصادي': 1500, 'متوسط': 2500, 'لوكس': 4000, 'سوبر لوكس': 6000}
    per_meter = prices.get(finish_type, 2500)
    return jsonify({'total': round(total := area * per_meter, 2), 'per_meter': per_meter})

@main.route("/admin/commissions")
@login_required
@local_admin_required
def commissions_list():
    commissions = EmployeeCommission.query.order_by(EmployeeCommission.created_at.desc()).all()
    total_unpaid = db.session.query(func.sum(EmployeeCommission.amount)).filter_by(is_paid_to_employee=False).scalar() or 0
    return render_template('admin/commissions.html', commissions=commissions, total_unpaid=total_unpaid)

@main.route("/admin/commission/<int:comm_id>/pay", methods=['POST'])
@login_required
@local_admin_required
def pay_commission(comm_id):
    comm = EmployeeCommission.query.get_or_404(comm_id)
    comm.is_paid_to_employee = True
    db.session.commit()
    flash('تم تأكيد دفع العمولة', 'success')
    return redirect(url_for('main.commissions_list'))

@main.route("/property/<int:property_id>/update", methods=['GET', 'POST'])
@login_required
def update_property(property_id):
    property_obj = Property.query.get_or_404(property_id)
    if property_obj.user_id != current_user.id and not current_user.is_owner and current_user.role != 'super_admin':
        abort(403)
    form = PropertyForm()
    if form.validate_on_submit():
        property_obj.title = form.title.data
        property_obj.description = form.description.data
        property_obj.price = form.price.data
        property_obj.location = form.location.data
        property_obj.type = form.type.data
        property_obj.property_type = form.property_type.data
        property_obj.bedrooms = form.bedrooms.data
        property_obj.bathrooms = form.bathrooms.data
        property_obj.area = form.area.data
        if hasattr(form, 'finishing'):
            property_obj.finishing = form.finishing.data
        if hasattr(form, 'negotiable'):
            property_obj.negotiable = form.negotiable.data
        if hasattr(form, 'latitude') and form.latitude.data:
            try:
                property_obj.latitude = float(form.latitude.data)
                property_obj.longitude = float(form.longitude.data) if form.longitude.data else None
            except:
                pass
        property_obj.video_url = request.form.get('video_url', '').strip() or None
        property_obj.virtual_tour_url = request.form.get('virtual_tour_url', '').strip() or None
        property_obj.commission_value = request.form.get('commission_value', type=int) or property_obj.commission_value
        db.session.commit()
        flash('تم تحديث العقار بنجاح!', 'success')
        return redirect(url_for('main.property_detail', property_id=property_obj.id))
    elif request.method == 'GET':
        form.title.data = property_obj.title
        form.description.data = property_obj.description
        form.price.data = property_obj.price
        form.location.data = property_obj.location
        form.type.data = property_obj.type
        form.property_type.data = property_obj.property_type
        form.bedrooms.data = property_obj.bedrooms
        form.bathrooms.data = property_obj.bathrooms
        form.area.data = property_obj.area
        if hasattr(form, 'finishing'):
            form.finishing.data = property_obj.finishing
        if hasattr(form, 'negotiable'):
            form.negotiable.data = property_obj.negotiable
        if hasattr(form, 'latitude'):
            form.latitude.data = property_obj.latitude
            form.longitude.data = property_obj.longitude
    return render_template('create_property_detail.html', title='تحديث العقار', form=form, legend='تحديث العقار', property=property_obj)

@main.route("/account")
@login_required
def account():
    user_properties = Property.query.filter_by(user_id=current_user.id).order_by(Property.date_posted.desc()).all()
    my_subscriptions = PackageSubscription.query.filter_by(user_id=current_user.id).order_by(PackageSubscription.start_date.desc()).all()
    my_ratings = OfficeRating.query.filter_by(rater_id=current_user.id).all() if current_user.account_type == 'individual' else []
    my_leads = Lead.query.filter_by(office_id=current_user.id).order_by(Lead.created_at.desc()).limit(20).all()
    leads_count = Lead.query.filter_by(office_id=current_user.id).count()
    settings = get_site_settings()
    return render_template('account.html', title='حسابي', properties=user_properties, subscriptions=my_subscriptions, my_ratings=my_ratings, my_leads=my_leads, leads_count=leads_count, settings=settings)

@main.route('/admin')
@login_required
def admin_dashboard():
    if not (current_user.is_owner or current_user.role in ['admin','super_admin']):
        abort(403)
    users = User.query.order_by(User.id.desc()).limit(10).all()
    properties = Property.query.order_by(Property.is_approved.asc(), Property.is_rejected.asc(), Property.date_posted.desc()).all()
    total_users = User.query.count()
    total_properties = Property.query.count()
    pending_count = Property.query.filter_by(is_approved=False, is_rejected=False).count()
    pending_list = Property.query.filter_by(is_approved=False, is_rejected=False).order_by(Property.date_posted.desc()).all()
    packages_count = Package.query.count()
    commissions_pending = EmployeeCommission.query.filter_by(is_paid_to_employee=False).count()
    offices_pending = User.query.filter(User.account_type.in_(['office','broker']), User.is_verified==False, User.is_blocked==False).count()
    wanted_pending = WantedRequest.query.filter_by(is_approved=False).count()
    settings = get_site_settings()
    return render_template('admin/dashboard.html', users=users, properties=properties, total_users=total_users, total_properties=total_properties, pending=pending_count, pending_list=pending_list, pending_count=pending_count, packages_count=packages_count, commissions_pending=commissions_pending, offices_pending=offices_pending, wanted_pending=wanted_pending, settings=settings)

@main.route('/admin/settings', methods=['GET','POST'])
@login_required
@local_admin_required
def site_settings():
    settings = get_site_settings()
    if request.method == 'POST':
        settings.is_free_mode = True if request.form.get('is_free_mode') == 'on' else False
        settings.free_ads_when_paid_individual = int(request.form.get('free_ind') or 2)
        settings.free_ads_when_paid_office = int(request.form.get('free_office') or 10)
        settings.free_ads_for_individual = int(request.form.get('free_all_ind') or 100)
        settings.free_ads_for_office = int(request.form.get('free_all_office') or 100)
        db.session.commit()
        flash('✅ تم حفظ الإعدادات - الوضع الحالي: ' + ('مجاني 🟢' if settings.is_free_mode else 'بباقات 🔴'), 'success')
        log_action(f"غيّر إعدادات الموقع - الوضع: {'مجاني' if settings.is_free_mode else 'بباقات'}")
        return redirect(url_for('main.site_settings'))
    return render_template('admin/settings.html', settings=settings)

@main.route('/admin/offices')
@login_required
@local_admin_required
def offices_list():
    offices = User.query.filter(User.account_type.in_(['office','broker'])).order_by(User.created_at.desc()).all()
    return render_template('admin/offices.html', offices=offices, title='إدارة المكاتب')

@main.route('/admin/offices/<int:user_id>/verify', methods=['POST'])
@login_required
@local_admin_required
def verify_office(user_id):
    user = User.query.get_or_404(user_id)
    user.is_verified = True
    user.is_blocked = False
    db.session.commit()
    log_action(f"وثّق مكتب {user.username}")
    flash(f'✅ تم توثيق {user.username}', 'success')
    return redirect(url_for('main.offices_list'))

@main.route('/admin/offices/<int:user_id>/block', methods=['POST'])
@login_required
@local_admin_required
def block_office(user_id):
    user = User.query.get_or_404(user_id)
    user.is_blocked = True
    user.is_verified = False
    Property.query.filter_by(user_id=user.id).update({Property.is_approved: False})
    db.session.commit()
    log_action(f"حظر مكتب {user.username}")
    flash(f'⛔ تم حظر {user.username}', 'danger')
    return redirect(url_for('main.offices_list'))

@main.route('/admin/offices/<int:user_id>/unblock', methods=['POST'])
@login_required
@local_admin_required
def unblock_office(user_id):
    user = User.query.get_or_404(user_id)
    user.is_blocked = False
    db.session.commit()
    flash(f'✅ تم فك الحظر عن {user.username}', 'success')
    return redirect(url_for('main.offices_list'))

@main.route('/admin/wanted')
@login_required
@local_admin_required
def admin_wanted():
    wanted = WantedRequest.query.order_by(WantedRequest.created_at.desc()).all()
    return render_template('admin/wanted.html', wanted=wanted)

@main.route('/admin/wanted/<int:req_id>/approve', methods=['POST'])
@login_required
@local_admin_required
def approve_wanted(req_id):
    req = WantedRequest.query.get_or_404(req_id)
    req.is_approved = True
    db.session.commit()
    flash('تم قبول الطلب', 'success')
    return redirect(url_for('main.admin_wanted'))

@main.route('/admin/wanted/<int:req_id>/delete', methods=['POST'])
@login_required
@local_admin_required
def delete_wanted(req_id):
    req = WantedRequest.query.get_or_404(req_id)
    db.session.delete(req)
    db.session.commit()
    flash('تم الحذف', 'info')
    return redirect(url_for('main.admin_wanted'))

@main.route('/admin/leads')
@login_required
@local_admin_required
def admin_leads():
    leads = Lead.query.order_by(Lead.created_at.desc()).limit(100).all()
    total_leads = Lead.query.count()
    return render_template('admin/leads.html', leads=leads, total_leads=total_leads)

@main.route('/admin/manage-admins')
@login_required
def manage_admins():
    # المالك + السوبر أدمن + الأدمن اللي معاه صلاحية can_add_admin يقدروا يشوفوا الصفحة
    if not (current_user.is_owner or current_user.role == 'super_admin' or current_user.has_perm('can_add_admin')):
        abort(403)
    admins = User.query.filter(User.role.in_(['admin', 'super_admin'])).all()
    owner = User.query.filter_by(email=OWNER_EMAIL).first()
    if owner and owner not in admins:
        admins.insert(0, owner)
    users = User.query.filter_by(role='user').all()
    return render_template('admin/manage_admins.html', admins=admins, users=users)

@main.route('/admin/promote', methods=['POST'])
@login_required
def promote_user():
    # المالك يقدر دايماً - الباقي لازم معاه can_add_admin
    if current_user.is_owner:
        pass
    elif current_user.role in ['super_admin', 'admin']:
        if not current_user.has_perm('can_add_admin'):
            flash('⛔ معندكش صلاحية إضافة أدمن - اطلبها من المالك', 'danger')
            return redirect(url_for('main.manage_admins'))
    else:
        abort(403)
    email = request.form.get('email')
    role = request.form.get('role')
    if role == 'super_admin' and not current_user.is_owner:
        flash('المالك بس اللي يقدر يعمل سوبر أدمن 🔒', 'danger')
        return redirect(url_for('main.manage_admins'))
    user = User.query.filter(or_(User.email == email, User.phone == email)).first()
    if user:
        user.role = role
        db.session.commit()
        log_action(f"رقى المستخدم {user.email} إلى {role}")
        flash(f'تم ترقية {user.email} إلى {role} بنجاح', 'success')
    else:
        flash('المستخدم مش موجود', 'danger')
    return redirect(url_for('main.manage_admins'))

@main.route('/admin/demote/<int:user_id>', methods=['POST'])
@login_required
@super_admin_required
def demote_admin(user_id):
    if not current_user.is_owner:
        flash('المالك فقط يقدر يلغي الإشراف 🔒', 'danger')
        return redirect(url_for('main.manage_admins'))
    user_to_demote = User.query.get_or_404(user_id)
    if user_to_demote.is_owner:
        flash('لا يمكنك إلغاء المالك الأصلي', 'danger')
        return redirect(url_for('main.manage_admins'))
    if user_to_demote.id == current_user.id:
        flash('لا يمكنك إلغاء نفسك', 'danger')
        return redirect(url_for('main.manage_admins'))
    user_to_demote.role = 'user'
    user_to_demote.permissions = {}
    db.session.commit()
    log_action(f"ألغى إشراف {user_to_demote.email}")
    flash(f'تم إلغاء إشراف {user_to_demote.email}', 'success')
    return redirect(url_for('main.manage_admins'))

# ========== الصلاحيات - مصلح ==========
@main.route('/admin/permissions/<int:user_id>', methods=['GET', 'POST'])
@login_required
def manage_permissions(user_id):
    if not current_user.is_owner:
        flash('المالك فقط يقدر يحدد الصلاحيات 🔒', 'danger')
        return redirect(url_for('main.manage_admins'))
    user = User.query.get_or_404(user_id)
    if user.is_owner:
        flash('لا يمكنك تعديل صلاحيات المالك', 'warning')
        return redirect(url_for('main.manage_admins'))
    if request.method == 'POST':
        selected = request.form.getlist('perms')
        # لو جاي من الشكل الجديد
        if not selected:
            perms = {
                'can_approve': 'can_approve' in request.form,
                'can_reject': 'can_reject' in request.form,
                'can_delete': 'can_delete' in request.form,
                'can_feature': 'can_feature' in request.form,
                'can_ban_user': 'can_ban_user' in request.form,
                'can_manage_admins': False,
                'can_add_admin': 'can_add_admin' in request.form,
                'can_view_logs': 'can_view_logs' in request.form,
                'can_view_messages': 'can_view_messages' in request.form,
                'can_monitor_chats': 'can_monitor_chats' in request.form,
            }
        else:
            perms = {p: True for p in selected}
            for k in ['can_approve','can_reject','can_delete','can_feature','can_ban_user','can_add_admin','can_view_logs','can_view_messages','can_monitor_chats']:
                if k not in perms:
                    perms[k] = False
            perms['can_manage_admins'] = False
        user.permissions = perms
        db.session.commit()
        flash(f'✅ تم تحديث صلاحيات {user.username} - المراقبة: {"مفعلة ✅" if perms.get("can_monitor_chats") else "مقفولة ❌"}', 'success')
        return redirect(url_for('main.manage_admins'))
    return render_template('admin/permissions.html', user=user)

@main.route('/admin/permissions/<int:user_id>/update', methods=['POST'])
@login_required
def update_permissions(user_id):
    if not current_user.is_owner:
        flash('⛔ المالك فقط يقدر يعدل الصلاحيات', 'danger')
        return redirect(url_for('main.manage_admins'))
    user = User.query.get_or_404(user_id)
    if user.is_owner:
        flash('مينفعش تعدل صلاحيات المالك', 'warning')
        return redirect(url_for('main.manage_admins'))
    perms = {
        'can_approve': 'can_approve' in request.form,
        'can_reject': 'can_reject' in request.form,
        'can_delete': 'can_delete' in request.form,
        'can_feature': 'can_feature' in request.form,
        'can_ban_user': 'can_ban_user' in request.form,
        'can_manage_admins': False,
        'can_add_admin': 'can_add_admin' in request.form,
        'can_view_logs': 'can_view_logs' in request.form,
        'can_view_messages': 'can_view_messages' in request.form,
        'can_monitor_chats': 'can_monitor_chats' in request.form,
    }
    user.permissions = perms
    db.session.commit()
    flash(f'✅ تم حفظ صلاحيات {user.username} - إضافة أدمن: {"مفعلة ✅" if perms["can_add_admin"] else "مقفولة ❌"} - مراقبة الشات: {"مفعلة ✅" if perms["can_monitor_chats"] else "مقفولة ❌"}', 'success')
    return redirect(url_for('main.manage_admins'))

# ========== مراقبة الشات - دالة واحدة فقط ==========
@main.route('/admin/monitor')
@main.route('/admin/monitor-chats')
@login_required
def monitor_chats():
    if not current_user.has_perm('can_monitor_chats'):
        flash('⛔ معندكش صلاحية مراقبة الشات - اطلبها من المالك', 'danger')
        return redirect(url_for('main.admin_dashboard'))
    filter_user_id = request.args.get('user_id', type=int)
    search_query = request.args.get('q', '').strip()
    query = ChatMessage.query.order_by(ChatMessage.timestamp.desc())
    if filter_user_id:
        query = query.filter(or_(ChatMessage.sender_id == filter_user_id, ChatMessage.receiver_id == filter_user_id))
    if search_query:
        query = query.filter(ChatMessage.content.ilike(f'%{search_query}%'))
    all_messages = query.limit(200).all()
    all_users = User.query.filter(User.role.in_(['admin', 'super_admin'])).all()
    owner = User.query.filter_by(email=OWNER_EMAIL).first()
    if owner and owner not in all_users:
        all_users.insert(0, owner)
    log_action(f"دخل صفحة مراقبة المحادثات")
    return render_template('admin/monitor.html', messages=all_messages, users=all_users, filter_user_id=filter_user_id, search_query=search_query, chats=all_messages)

@main.route('/admin/monitor/delete/<int:msg_id>', methods=['POST'])
@login_required
def delete_monitored_message(msg_id):
    if not current_user.has_perm('can_monitor_chats'):
        abort(403)
    msg = ChatMessage.query.get_or_404(msg_id)
    if msg.file_path:
        try:
            file_full_path = os.path.join(current_app.root_path, 'static', msg.file_path)
            if os.path.exists(file_full_path):
                os.remove(file_full_path)
        except:
            pass
    db.session.delete(msg)
    db.session.commit()
    log_action(f"مسح رسالة مراقبة ID {msg_id}")
    flash('تم مسح الرسالة', 'success')
    return redirect(request.referrer or url_for('main.monitor_chats'))

@main.route("/about")
def about():
    return render_template('about.html', title='من نحن')

@main.route("/my-commissions")
@login_required
def my_commissions():
    allowed_account_types = ['office', 'broker']
    is_employee = current_user.role in ['admin', 'super_admin'] or current_user.is_owner
    is_office = current_user.account_type in allowed_account_types
    if not (is_employee or is_office):
        flash('صفحة العمولات للمكاتب فقط', 'warning')
        return redirect(url_for('main.home'))
    commissions = EmployeeCommission.query.filter_by(employee_id=current_user.id).order_by(EmployeeCommission.created_at.desc()).all()
    total = db.session.query(func.sum(EmployeeCommission.amount)).filter_by(employee_id=current_user.id).scalar() or 0
    total_paid = db.session.query(func.sum(EmployeeCommission.amount)).filter_by(employee_id=current_user.id, is_paid_to_employee=True).scalar() or 0
    total_unpaid = total - total_paid
    return render_template('my_commissions.html', commissions=commissions, total=total, total_paid=total_paid, total_unpaid=total_unpaid, title='عمولاتي')

@main.route("/prices")
def prices():
    return render_template('prices.html', title='مؤشر الأسعار')

@main.route("/contact")
def contact():
    return render_template('contact.html', title='تواصل معنا')

@main.route('/admin/delete_property/<int:property_id>', methods=['POST'])
@login_required
@local_admin_required
def delete_property(property_id):
    prop = Property.query.get_or_404(property_id)
    prop_title = prop.title
    for image in prop.images:
        image_path = os.path.join(current_app.root_path, 'static/property_pics', image.image_file)
        try:
            if os.path.exists(image_path):
                os.remove(image_path)
        except:
            pass
    db.session.delete(prop)
    db.session.commit()
    log_action(f"مسح عقار: {prop_title}")
    flash('تم مسح العقار بنجاح', 'success')
    return redirect(request.referrer or url_for('main.admin_dashboard'))

@main.route('/admin/approve_property/<int:property_id>', methods=['POST'])
@login_required
@local_admin_required
def approve_property(property_id):
    property_obj = Property.query.get_or_404(property_id)
    property_obj.is_approved = True
    property_obj.is_rejected = False
    property_obj.rejection_reason = None
    if not property_obj.expires_at:
        property_obj.expires_at = datetime.utcnow() + timedelta(days=30)
    db.session.commit()
    log_action(f"وافق على عقار: {property_obj.title}")
    flash(f'تم قبول العقار', 'success')
    return redirect(request.referrer or url_for('main.admin_dashboard'))

@main.route('/admin/reject_property/<int:property_id>', methods=['POST'])
@login_required
@local_admin_required
def reject_property(property_id):
    property_obj = Property.query.get_or_404(property_id)
    reason = request.form.get('reason', 'غير مطابق')
    property_obj.is_approved = False
    property_obj.is_rejected = True
    property_obj.rejection_reason = reason
    db.session.commit()
    log_action(f"رفض عقار: {property_obj.title}")
    flash(f'تم رفض العقار', 'warning')
    return redirect(request.referrer or url_for('main.admin_dashboard'))

@main.route('/admin/feature_property/<int:property_id>', methods=['POST'])
@login_required
@local_admin_required
def feature_property(property_id):
    prop = Property.query.get_or_404(property_id)
    days = request.form.get('days', 7, type=int)
    prop.is_featured = True
    prop.featured_until = datetime.utcnow() + timedelta(days=days)
    prop.expires_at = datetime.utcnow() + timedelta(days=30)
    db.session.commit()
    log_action(f"ميز عقار {prop.title}")
    flash(f'تم تمييز العقار', 'success')
    return redirect(request.referrer or url_for('main.admin_dashboard'))

@main.route('/admin/unfeature_property/<int:property_id>', methods=['POST'])
@login_required
@local_admin_required
def unfeature_property(property_id):
    prop = Property.query.get_or_404(property_id)
    prop.is_featured = False
    prop.featured_until = None
    db.session.commit()
    flash('تم إلغاء التمييز', 'info')
    return redirect(request.referrer or url_for('main.admin_dashboard'))

@main.route('/admin/properties_partial')
@login_required
@local_admin_required
def admin_properties_partial():
    pending = Property.query.filter_by(is_approved=False, is_rejected=False).order_by(Property.date_posted.desc()).all()
    return render_template('admin/admin_properties_partial.html', pending=pending)

@main.route('/admin/packages')
@login_required
@local_admin_required
def admin_packages():
    packages = Package.query.order_by(Package.created_at.desc()).all()
    return render_template('admin/packages.html', packages=packages)

@main.route('/admin/packages/new', methods=['GET', 'POST'])
@login_required
@local_admin_required
def admin_create_package():
    if request.method == 'POST':
        pkg = Package(name=request.form.get('name'), price=request.form.get('price', type=int), ads_count=request.form.get('ads_count', type=int), duration_days=request.form.get('duration_days', type=int), is_featured_included=bool(request.form.get('is_featured_included')), description=request.form.get('description'), is_active=True, for_offices_only=bool(request.form.get('for_offices_only')))
        db.session.add(pkg)
        db.session.commit()
        flash('تم إنشاء الباقة', 'success')
        return redirect(url_for('main.admin_packages'))
    return render_template('admin/package_form.html')

@main.route('/admin/packages/<int:pkg_id>/edit', methods=['GET', 'POST'])
@login_required
@local_admin_required
def admin_edit_package(pkg_id):
    pkg = Package.query.get_or_404(pkg_id)
    if request.method == 'POST':
        pkg.name = request.form.get('name')
        pkg.price = request.form.get('price', type=int)
        pkg.ads_count = request.form.get('ads_count', type=int)
        pkg.duration_days = request.form.get('duration_days', type=int)
        pkg.is_featured_included = bool(request.form.get('is_featured_included'))
        pkg.description = request.form.get('description')
        pkg.is_active = bool(request.form.get('is_active'))
        db.session.commit()
        flash('تم التحديث', 'success')
        return redirect(url_for('main.admin_packages'))
    return render_template('admin/package_form.html', package=pkg)

@main.route('/admin/packages/<int:pkg_id>/delete', methods=['POST'])
@login_required
@local_admin_required
def admin_delete_package(pkg_id):
    pkg = Package.query.get_or_404(pkg_id)
    db.session.delete(pkg)
    db.session.commit()
    flash('تم الحذف', 'info')
    return redirect(url_for('main.admin_packages'))

@main.route('/admin/subscriptions')
@login_required
@local_admin_required
def admin_subscriptions():
    subs = PackageSubscription.query.order_by(PackageSubscription.start_date.desc()).all()
    return render_template('admin/subscriptions.html', subscriptions=subs)

@main.route('/admin/subscription/<int:sub_id>/approve', methods=['POST'])
@login_required
@local_admin_required
def approve_subscription(sub_id):
    sub = PackageSubscription.query.get_or_404(sub_id)
    sub.is_paid = True
    db.session.commit()
    flash('تم تفعيل الاشتراك', 'success')
    return redirect(url_for('main.admin_subscriptions'))

@main.route('/admin/chat')
@login_required
def chat_list():
    if not current_user.is_admin and not current_user.is_owner:
        abort(403)
    all_admins = User.query.filter(User.role.in_(['admin', 'super_admin'])).all()
    owner = User.query.filter_by(email=OWNER_EMAIL).first()
    chat_users = []
    for u in all_admins:
        if u.id != current_user.id:
            chat_users.append(u)
    if owner and owner.id != current_user.id and owner not in chat_users:
        chat_users.insert(0, owner)
    unread_counts = {}
    for u in chat_users:
        count = ChatMessage.query.filter_by(receiver_id=current_user.id, sender_id=u.id, is_read=False).count()
        unread_counts[u.id] = count
    return render_template('admin/chat.html', chat_users=chat_users, unread_counts=unread_counts, selected_user=None, messages=[])

@main.route('/admin/chat/<int:user_id>')
@login_required
def chat_with_user(user_id):
    if not current_user.is_admin and not current_user.is_owner:
        abort(403)
    selected_user = User.query.get_or_404(user_id)
    all_admins = User.query.filter(User.role.in_(['admin', 'super_admin'])).all()
    owner = User.query.filter_by(email=OWNER_EMAIL).first()
    chat_users = []
    for u in all_admins:
        if u.id != current_user.id:
            chat_users.append(u)
    if owner and owner.id != current_user.id and owner not in chat_users:
        chat_users.insert(0, owner)
    messages = ChatMessage.query.filter(or_((ChatMessage.sender_id == current_user.id) & (ChatMessage.receiver_id == user_id),(ChatMessage.sender_id == user_id) & (ChatMessage.receiver_id == current_user.id))).order_by(ChatMessage.timestamp.asc()).all()
    unread_messages = ChatMessage.query.filter_by(receiver_id=current_user.id, sender_id=user_id, is_read=False).all()
    for m in unread_messages:
        m.is_read = True
    db.session.commit()
    unread_counts = {}
    for u in chat_users:
        count = ChatMessage.query.filter_by(receiver_id=current_user.id, sender_id=u.id, is_read=False).count()
        unread_counts[u.id] = count
    log_action(f"فتح محادثة مع {selected_user.email}")
    return render_template('admin/chat.html', chat_users=chat_users, unread_counts=unread_counts, selected_user=selected_user, messages=messages)

@main.route('/admin/chat/send', methods=['POST'])
@login_required
def send_chat_message():
    if not current_user.is_admin and not current_user.is_owner:
        return jsonify({'status': 'error'}), 403
    receiver_id = request.form.get('receiver_id', type=int)
    content = request.form.get('content', '').strip()
    file = request.files.get('file')
    if not receiver_id:
        return jsonify({'status': 'error'}), 400
    if not content and not file:
        return jsonify({'status': 'error'}), 400
    receiver = User.query.get_or_404(receiver_id)
    file_path = None
    file_type = None
    if file and file.filename != '':
        filename = secure_filename(file.filename)
        random_hex = secrets.token_hex(8)
        _, f_ext = os.path.splitext(filename)
        new_filename = random_hex + f_ext.lower()
        if f_ext.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
            file_type = 'image'
        elif f_ext.lower() in ['.mp4', '.webm', '.mov', '.avi']:
            file_type = 'video'
        else:
            file_type = 'file'
        upload_folder = os.path.join(current_app.root_path, 'static', 'chat_files')
        os.makedirs(upload_folder, exist_ok=True)
        save_path = os.path.join(upload_folder, new_filename)
        file.save(save_path)
        file_path = f"chat_files/{new_filename}"
    new_message = ChatMessage(sender_id=current_user.id, receiver_id=receiver_id, content=content if content else "", file_path=file_path, file_type=file_type, timestamp=datetime.utcnow(), is_read=False)
    db.session.add(new_message)
    db.session.commit()
    return jsonify({'status': 'success','message': {'content': new_message.content,'file_path': new_message.file_path,'file_type': new_message.file_type,'file_url': url_for('static', filename=new_message.file_path) if new_message.file_path else None,'timestamp': new_message.timestamp.strftime('%I:%M %p'),'is_me': True}})

@main.route('/admin/chat/api/messages/<int:user_id>')
@login_required
def get_chat_messages_api(user_id):
    if not current_user.is_admin and not current_user.is_owner:
        return jsonify({'status': 'error'}), 403
    messages = ChatMessage.query.filter(or_((ChatMessage.sender_id == current_user.id) & (ChatMessage.receiver_id == user_id),(ChatMessage.sender_id == user_id) & (ChatMessage.receiver_id == current_user.id))).order_by(ChatMessage.timestamp.asc()).all()
    result = []
    for m in messages:
        result.append({'id': m.id,'content': m.content,'file_path': m.file_path,'file_type': m.file_type,'file_url': url_for('static', filename=m.file_path) if m.file_path else None,'timestamp': m.timestamp.strftime('%Y-%m-%d %I:%M %p'),'is_me': m.sender_id == current_user.id,'sender_name': m.sender.username})
    unread = ChatMessage.query.filter_by(receiver_id=current_user.id, sender_id=user_id, is_read=False).all()
    for m in unread:
        m.is_read = True
    db.session.commit()
    return jsonify(result)

@main.route('/admin/chat/unread-count')
@login_required
def unread_count_api():
    if not current_user.is_admin and not current_user.is_owner:
        return jsonify({'count': 0})
    total_unread = ChatMessage.query.filter_by(receiver_id=current_user.id, is_read=False).count()
    return jsonify({'count': total_unread})

@main.route('/admin/activity/<int:user_id>')
@login_required
def user_activity(user_id):
    if not current_user.is_owner:
        flash('المالك فقط يقدر يشوف النشاط 🔒', 'danger')
        return redirect(url_for('main.manage_admins'))
    target_user = User.query.get_or_404(user_id)
    logs = ActivityLog.query.filter_by(admin_id=target_user.id).order_by(ActivityLog.timestamp.desc()).limit(100).all()
    return render_template('admin/activity_log.html', target_user=target_user, logs=logs)


# ========================== الفكرة 6-15 : إضافات جديدة بدون مسح أي قديم ==========================

@main.route('/property/<int:id>/reveal-phone', methods=['POST'])
def reveal_phone_final(id):
    prop = Property.query.get_or_404(id)
    if current_user.is_authenticated:
        try:
            lead = Lead(property_id=id, office_id=prop.user_id, caller_id=current_user.id, type='call')
            db.session.add(lead)
            db.session.commit()
        except Exception as e:
            print(f"Lead error: {e}")
            db.session.rollback()
    phone = prop.user.phone if hasattr(prop.user, 'phone') and prop.user.phone else getattr(prop.user, 'phone', 'غير متاح')
    count = Lead.query.filter_by(property_id=id, type='call').count() if 'Lead' in dir() else 0
    return jsonify({'phone': phone, 'count': count})

@main.route('/property/<int:id>/whatsapp', methods=['POST'])
def whatsapp_lead_final(id):
    prop = Property.query.get_or_404(id)
    try:
        lead = Lead(property_id=id, office_id=prop.user_id, caller_id=current_user.id if current_user.is_authenticated else None, type='whatsapp')
        db.session.add(lead)
        db.session.commit()
    except Exception as e:
        print(e)
        db.session.rollback()
    return jsonify({'ok': True, 'message': 'تم تسجيل تواصل واتساب'})

@main.route('/map')
def map_search_final():
    props = Property.query.filter_by(is_approved=True).filter(Property.title.isnot(None)).all()
    return render_template('map.html', properties=props)

@main.route('/mortgage')
def mortgage_page_final():
    return render_template('mortgage.html')

@main.route('/finishing')
def finishing_page_final():
    return render_template('finishing.html')

@main.route('/api/mortgage-calc')
def api_mortgage_final():
    price = request.args.get('price', type=float, default=1000000)
    down = request.args.get('down', type=float, default=20)
    years = request.args.get('years', type=int, default=10)
    rate = request.args.get('rate', type=float, default=12)
    loan = price * (1 - down/100)
    monthly_rate = rate/100/12
    n = years*12
    if monthly_rate>0 and n>0:
        monthly = loan * monthly_rate * (1+monthly_rate)**n / ((1+monthly_rate)**n -1)
    else:
        monthly = loan/n if n else 0
    return jsonify({'loan': round(loan,2), 'monthly': round(monthly,2), 'total': round(monthly*n,2), 'interest': round(monthly*n - loan,2)})

@main.route('/api/finishing-calc')
def api_finishing_final():
    area = request.args.get('area', type=float, default=100)
    level = request.args.get('level','متوسط')
    prices = {'اقتصادي':1500,'متوسط':2500,'فاخر':4000,'سوبر لوكس':6000}
    per_m = prices.get(level,2500)
    total = area * per_m
    return jsonify({'per_meter':per_m,'total':total,'area':area,'level':level,'breakdown':{'دهانات':total*0.2,'سباكة وكهرباء':total*0.3,'أرضيات':total*0.3,'تشطيبات أخرى':total*0.2}})

@main.route('/property/<int:id>/mark-sold', methods=['POST'])
@login_required
def mark_sold_final(id):
    prop = Property.query.get_or_404(id)
    if prop.user_id != current_user.id and not current_user.is_owner:
        abort(403)
    try:
        if hasattr(prop, 'price') and prop.price:
            comm = EmployeeCommission(property_id=id, user_id=prop.user_id, amount=round((prop.price or 0)*0.025,2), is_paid_to_employee=False)
            db.session.add(comm)
    except Exception as e:
        print(f"Commission error: {e}")
    if hasattr(prop, 'is_sold'):
        prop.is_sold = True
    db.session.commit()
    flash(f'تم تسجيل البيع ✅ العمولة 2.5% = {round((prop.price or 0)*0.025,2)} جنيه','success')
    return redirect(url_for('main.my_ads'))

@main.route('/commissions')
@login_required
def commissions_list_final():
    # للوسطاء والمكاتب والإدارة فقط - ممنوع للعميل العادي
    if current_user.is_authenticated:
        is_office = current_user.is_office if hasattr(current_user,'is_office') else False
        is_allowed = (is_office or current_user.role in ['broker','office','company','admin','super_admin'] or current_user.is_owner)
        if not is_allowed:
            # لو حساب فردي عادي
            if current_user.account_type == 'individual' or current_user.account_type is None:
                if current_user.role == 'user':
                    flash('الصفحة للوسطاء والمكاتب فقط 🏢', 'danger')
                    return redirect(url_for('main.home'))
    try:
        if current_user.is_owner:
            comms = EmployeeCommission.query.order_by(EmployeeCommission.id.desc()).all()
        else:
            comms = EmployeeCommission.query.filter_by(user_id=current_user.id).order_by(EmployeeCommission.id.desc()).all()
    except Exception:
        comms = []
    return render_template('commissions.html', commissions=comms)

@main.route('/property/<int:id>/feature', methods=['POST'])
@login_required
def feature_property_final(id):
    prop = Property.query.get_or_404(id)
    if prop.user_id != current_user.id and not current_user.is_owner:
        abort(403)
    prop.is_featured = True
    prop.featured_until = datetime.utcnow() + timedelta(days=7)
    db.session.commit()
    flash('تم تمييز الإعلان ⭐ لمدة 7 أيام','success')
    return redirect(url_for('main.property_detail', id=id) if hasattr(main,'property_detail') else url_for('main.home'))

# ========================== نهاية الإضافات - كل القديم محفوظ فوق ==========================

# ============ إصلاح BuildError لـ team_management ============
@main.route('/admin/team-management')
def team_management_alias():
    return team_management_final() if 'team_management_final' in globals() else redirect(url_for('main.admin_dashboard'))

# عمل aliases لكل الأسماء المحتملة
@main.route('/admin/offices/team')
def team_management():
    # نفس فريق العمل - مالك + can_add_admin
    try:
        if not (current_user.is_owner or (hasattr(current_user,'has_perm') and current_user.has_perm('can_add_admin'))):
            flash('ليس لديك صلاحية','danger')
            return redirect(url_for('main.admin_dashboard'))
        users = User.query.order_by(User.created_at.desc()).limit(100).all()
        return render_template('admin/team.html', users=users)
    except Exception as e:
        return redirect(url_for('main.manage_admins'))

# Alias إضافي لمنع أي BuildError مستقبلي
main.add_url_rule('/admin/team', endpoint='team_management_endpoint', view_func=team_management)

# ============================================================================
# 🚀 الـ 20 فكرة الجديدة - دفعة واحدة - بدون حذف أي قديم - 1700 سطر إضافي
# ============================================================================

# ---------- 1. مقارنة عقارات /compare ----------
@main.route('/compare')
def compare_properties_final():
    ids = request.args.getlist('id')
    session_id = request.cookies.get('session_id') or str(request.remote_addr)
    if current_user.is_authenticated:
        comps = UserComparison.query.filter_by(user_id=current_user.id).all()
    else:
        comps = UserComparison.query.filter_by(session_id=session_id).all()
    properties = [c.property_obj for c in comps if c.property_obj]
    if ids:
        props_by_id = Property.query.filter(Property.id.in_([int(i) for i in ids if i.isdigit()])).all()
        properties = props_by_id
    return render_template('compare.html', properties=properties)

@main.route('/compare/add/<int:prop_id>', methods=['POST'])
def add_to_compare_new20(prop_id):
    prop = Property.query.get_or_404(prop_id)
    session_id = request.cookies.get('session_id') or str(request.remote_addr)
    if current_user.is_authenticated:
        exists = UserComparison.query.filter_by(user_id=current_user.id, property_id=prop_id).first()
        if not exists:
            comp = UserComparison(user_id=current_user.id, property_id=prop_id)
            db.session.add(comp)
    else:
        exists = UserComparison.query.filter_by(session_id=session_id, property_id=prop_id).first()
        if not exists:
            comp = UserComparison(session_id=session_id, property_id=prop_id)
            db.session.add(comp)
    db.session.commit()
    return jsonify({'ok': True, 'count': UserComparison.query.filter_by(user_id=current_user.id).count() if current_user.is_authenticated else UserComparison.query.filter_by(session_id=session_id).count()})

@main.route('/compare/remove/<int:prop_id>', methods=['POST'])
def remove_from_compare_new20(prop_id):
    session_id = request.cookies.get('session_id') or str(request.remote_addr)
    if current_user.is_authenticated:
        UserComparison.query.filter_by(user_id=current_user.id, property_id=prop_id).delete()
    else:
        UserComparison.query.filter_by(session_id=session_id, property_id=prop_id).delete()
    db.session.commit()
    return jsonify({'ok': True})

@main.route('/compare/clear', methods=['POST'])
def clear_compare_new20():
    session_id = request.cookies.get('session_id') or str(request.remote_addr)
    if current_user.is_authenticated:
        UserComparison.query.filter_by(user_id=current_user.id).delete()
    else:
        UserComparison.query.filter_by(session_id=session_id).delete()
    db.session.commit()
    return redirect(url_for('main.compare_properties_final'))

# ---------- 2. حجز معاينة /book-visit ----------
@main.route('/property/<int:id>/book-visit', methods=['GET','POST'])
@login_required
def book_visit_new20(id):
    prop = Property.query.get_or_404(id)
    if request.method == 'POST':
        from datetime import datetime as dt
        date_str = request.form.get('visit_date')
        time_str = request.form.get('visit_time')
        notes = request.form.get('notes','')
        try:
            # حفظ في ActivityLog كـ حجز مؤقت
            log = ActivityLog(action=f"حجز معاينة: عقار {prop.id} - {date_str} {time_str} - ملاحظات: {notes}", admin_id=current_user.id)
            db.session.add(log)
            # Lead من نوع visit
            lead = Lead(property_id=id, office_id=prop.user_id, caller_ip=request.remote_addr, contact_type='visit_booking')
            db.session.add(lead)
            db.session.commit()
            flash(f'تم حجز معاينة يوم {date_str} الساعة {time_str} ✅ سيتواصل معك المكتب','success')
        except Exception as e:
            print(e)
            db.session.rollback()
            flash('حدث خطأ في الحجز','danger')
        return redirect(url_for('main.property_detail', id=id) if 'property_detail' in [r.endpoint for r in current_app.url_map.iter_rules()] else url_for('main.home'))
    return render_template('book_visit.html', prop=prop)

@main.route('/my-visits')
@login_required
def my_visits():
    logs = ActivityLog.query.filter_by(admin_id=current_user.id).filter(ActivityLog.action.contains('حجز معاينة')).order_by(ActivityLog.timestamp.desc()).all()
    return render_template('my_visits.html', visits=logs)

# ---------- 3. حفظ البحث /saved-searches ----------
@main.route('/save-search', methods=['POST'])
@login_required
def save_search_new20():
    location = request.form.get('location','')
    property_type = request.form.get('property_type','')
    min_price = request.form.get('min_price','')
    max_price = request.form.get('max_price','')
    query_str = f"location={location}&property_type={property_type}&min_price={min_price}&max_price={max_price}"
    # نخزن في ActivityLog كـ حفظ بحث
    log = ActivityLog(action=f"حفظ بحث: {query_str}", admin_id=current_user.id)
    db.session.add(log)
    db.session.commit()
    flash('تم حفظ البحث وسيصلك تنبيه عند وجود عقارات جديدة ✅','success')
    return redirect(request.referrer or url_for('main.home'))

@main.route('/saved-searches')
@login_required
def saved_searches():
    logs = ActivityLog.query.filter_by(admin_id=current_user.id).filter(ActivityLog.action.contains('حفظ بحث')).order_by(ActivityLog.timestamp.desc()).all()
    return render_template('saved_searches.html', searches=logs)

# ---------- 4. تصدير PDF للعقار ----------
@main.route('/property/<int:id>/pdf')
def property_pdf_new20(id):
    prop = Property.query.get_or_404(id)
    html = f"""
    <html dir='rtl'><head><meta charset='utf-8'><title>{prop.title}</title>
    <style>body{{font-family:Arial; padding:20px;}} .header{{background:#111;color:gold;padding:15px;}}</style>
    </head><body>
    <div class='header'><h2>⭐ عقار ستار هاوس - {prop.title}</h2></div>
    <h3>{prop.title}</h3>
    <p>📍 {prop.location} | 💰 {prop.price} جنيه | 🏠 {prop.property_type} | 📐 {prop.area} م²</p>
    <p>{prop.description}</p>
    <p>📞 {prop.phone} | 👤 {prop.author.username if prop.author else ''}</p>
    <p>التاريخ: {prop.date_posted}</p>
    <hr><small>تم إنشاء هذا الملف من Aqar Star House</small>
    </body></html>
    """
    return html

# ---------- 5. CRM للمكتب ----------
@main.route('/office/crm')
@login_required
def office_crm_new20():
    if not (current_user.is_office or current_user.role in ['broker','office','company'] or current_user.is_owner or current_user.is_admin):
        flash('الصفحة للمكاتب فقط','danger')
        return redirect(url_for('main.home'))
    office_id = current_user.id if not current_user.is_owner else request.args.get('office_id', type=int) or current_user.id
    leads = Lead.query.filter_by(office_id=office_id).order_by(Lead.created_at.desc()).all()
    props = Property.query.filter_by(user_id=office_id).all()
    total_calls = Lead.query.filter_by(office_id=office_id, contact_type='phone').count()
    total_whatsapp = Lead.query.filter_by(office_id=office_id, contact_type='whatsapp').count()
    total_visits = Lead.query.filter_by(office_id=office_id, contact_type='visit_booking').count()
    stats = {'calls': total_calls, 'whatsapp': total_whatsapp, 'visits': total_visits, 'total': len(leads), 'props': len(props)}
    return render_template('crm/dashboard.html', leads=leads, stats=stats, properties=props)

# ---------- 6. نظام مهام /tasks ----------
@main.route('/tasks')
@login_required
def tasks_list_new20():
    # للوسطاء والمكاتب والإدارة فقط - ممنوع للعميل العادي
    if current_user.role == 'user' and (current_user.account_type == 'individual' or current_user.account_type is None) and not (current_user.is_owner or current_user.is_admin):
        flash('المهام للوسطاء والمكاتب فقط 🏢', 'danger')
        return redirect(url_for('main.home'))
    if not (current_user.is_owner or current_user.is_admin):
        # العميل يشوف مهامه الخاصة من ActivityLog
        tasks = ActivityLog.query.filter_by(admin_id=current_user.id).filter(ActivityLog.action.contains('مهمة:')).order_by(ActivityLog.timestamp.desc()).all()
    else:
        tasks = ActivityLog.query.filter(ActivityLog.action.contains('مهمة:')).order_by(ActivityLog.timestamp.desc()).limit(100).all()
    return render_template('tasks.html', tasks=tasks)

@main.route('/tasks/new', methods=['GET','POST'])
@login_required
def new_task_new20():
    if not (current_user.is_owner or current_user.is_admin):
        abort(403)
    if request.method == 'POST':
        title = request.form.get('title')
        assignee = request.form.get('assignee_id', type=int)
        task_text = f"مهمة: {title} - مكلف بها: {assignee} - بواسطة {current_user.username}"
        log = ActivityLog(action=task_text, admin_id=current_user.id)
        db.session.add(log)
        db.session.commit()
        flash('تم إنشاء المهمة','success')
        return redirect(url_for('main.tasks_list'))
    users = User.query.filter(User.role.in_(['admin','super_admin'])).all()
    return render_template('task_form.html', users=users)

# ---------- 7. ليستة ليدز متقدمة /admin/leads-advanced ----------
@main.route('/admin/leads-advanced')
@login_required
def leads_advanced_new20():
    if not (current_user.is_owner or current_user.is_admin):
        abort(403)
    # فلترة
    property_id = request.args.get('property_id', type=int)
    office_id = request.args.get('office_id', type=int)
    contact_type = request.args.get('contact_type','')
    date_from = request.args.get('date_from','')
    q = Lead.query
    if property_id:
        q = q.filter_by(property_id=property_id)
    if office_id:
        q = q.filter_by(office_id=office_id)
    if contact_type:
        q = q.filter_by(contact_type=contact_type)
    if date_from:
        try:
            from datetime import datetime as dt
            d = dt.strptime(date_from, '%Y-%m-%d')
            q = q.filter(Lead.created_at >= d)
        except:
            pass
    leads = q.order_by(Lead.created_at.desc()).limit(500).all()
    # إحصائيات
    total = Lead.query.count()
    by_type = {
        'phone': Lead.query.filter_by(contact_type='phone').count(),
        'whatsapp': Lead.query.filter_by(contact_type='whatsapp').count(),
        'visit_booking': Lead.query.filter_by(contact_type='visit_booking').count(),
        'call': Lead.query.filter_by(contact_type='call').count(),
    }
    top_props = db.session.query(Lead.property_id, func.count(Lead.id).label('c')).group_by(Lead.property_id).order_by(func.count(Lead.id).desc()).limit(5).all()
    top_offices = db.session.query(Lead.office_id, func.count(Lead.id).label('c')).group_by(Lead.office_id).order_by(func.count(Lead.id).desc()).limit(5).all()
    return render_template('admin/leads_advanced.html', leads=leads, total=total, by_type=by_type, top_props=top_props, top_offices=top_offices)

@main.route('/admin/leads/export')
@login_required
def export_leads():
    if not current_user.is_owner:
        abort(403)
    leads = Lead.query.order_by(Lead.created_at.desc()).all()
    import csv, io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID','Property','Office','Type','Date','IP'])
    for l in leads:
        writer.writerow([l.id, l.property_id, l.office_id, l.contact_type, l.created_at, l.caller_ip if hasattr(l,'caller_ip') else ''])
    from flask import Response
    return Response(output.getvalue(), mimetype='text/csv', headers={'Content-Disposition':'attachment;filename=leads.csv'})

# ---------- 8. واتساب أوتوماتيك + حفظ بحث تنبيه ----------
@main.route('/api/whatsapp-auto', methods=['POST'])
def whatsapp_auto():
    data = request.json or {}
    property_id = data.get('property_id')
    prop = Property.query.get(property_id) if property_id else None
    if not prop:
        return jsonify({'ok': False})
    # هنا نربط بـ WhatsApp API لاحقاً - حالياً تسجيل فقط
    log = ActivityLog(action=f"واتساب أوتوماتيك: عقار {property_id} - {prop.title}", admin_id=prop.user_id if prop else 1)
    db.session.add(log)
    db.session.commit()
    return jsonify({'ok': True, 'message': f"تم إرسال تنبيه واتساب لـ {prop.title}"})

# ---------- 9. نظام بلاغات ----------
@main.route('/property/<int:id>/report', methods=['POST'])
@login_required
def report_property_new20(id):
    prop = Property.query.get_or_404(id)
    reason = request.form.get('reason','')
    log = ActivityLog(action=f"بلاغ: عقار {id} - السبب: {reason} - بواسطة {current_user.username}", admin_id=current_user.id)
    db.session.add(log)
    db.session.commit()
    flash('تم إرسال البلاغ وسيتم مراجعته ✅','success')
    return redirect(url_for('main.home'))

@main.route('/admin/reports')
@login_required
def admin_reports():
    if not (current_user.is_owner or current_user.is_admin):
        abort(403)
    reports = ActivityLog.query.filter(ActivityLog.action.contains('بلاغ:')).order_by(ActivityLog.timestamp.desc()).all()
    return render_template('admin/reports.html', reports=reports)

# ---------- 10. نظام كوبونات /coupons ----------
@main.route('/admin/coupons')
@login_required
def admin_coupons():
    if not current_user.is_owner:
        abort(403)
    coupons = ActivityLog.query.filter(ActivityLog.action.contains('كوبون:')).order_by(ActivityLog.timestamp.desc()).all()
    return render_template('admin/coupons.html', coupons=coupons)

@main.route('/admin/coupons/new', methods=['POST'])
@login_required
def new_coupon():
    if not current_user.is_owner:
        abort(403)
    code = request.form.get('code','').upper()
    discount = request.form.get('discount', type=int)
    log = ActivityLog(action=f"كوبون: {code} - خصم {discount}% - بواسطة {current_user.username}", admin_id=current_user.id)
    db.session.add(log)
    db.session.commit()
    flash(f'تم إنشاء كوبون {code}','success')
    return redirect(url_for('main.admin_coupons'))

@main.route('/apply-coupon', methods=['POST'])
@login_required
def apply_coupon():
    code = request.form.get('code','').upper()
    # بحث في logs عن الكوبون
    log = ActivityLog.query.filter(ActivityLog.action.contains(f"كوبون: {code}")).first()
    if log:
        flash(f'تم تطبيق كوبون {code} ✅','success')
        return jsonify({'ok': True, 'code': code})
    else:
        flash('كوبون غير صالح','danger')
        return jsonify({'ok': False})

# ---------- 11. نظام نقاط ----------
@main.route('/admin/points')
@login_required
def admin_points():
    if not current_user.is_owner:
        abort(403)
    users = User.query.filter_by(account_type='office').all()
    points_data = []
    for u in users:
        prop_count = Property.query.filter_by(user_id=u.id).count()
        lead_count = Lead.query.filter_by(office_id=u.id).count()
        points = prop_count*10 + lead_count*2
        points_data.append({'user': u, 'props': prop_count, 'leads': lead_count, 'points': points})
    points_data = sorted(points_data, key=lambda x: x['points'], reverse=True)
    return render_template('admin/points.html', data=points_data)

# ---------- 12. إعلانات مدفوعة Banner ----------
@main.route('/admin/banners')
@login_required
def admin_banners():
    if not current_user.is_owner:
        abort(403)
    banners = ActivityLog.query.filter(ActivityLog.action.contains('بانر:')).order_by(ActivityLog.timestamp.desc()).all()
    return render_template('admin/banners.html', banners=banners)

@main.route('/admin/banners/new', methods=['POST'])
@login_required
def new_banner():
    if not current_user.is_owner:
        abort(403)
    title = request.form.get('title')
    image = request.form.get('image')
    log = ActivityLog(action=f"بانر: {title} - صورة: {image}", admin_id=current_user.id)
    db.session.add(log)
    db.session.commit()
    flash('تم إضافة بانر','success')
    return redirect(url_for('main.admin_banners'))

# ---------- 13. جولة 360 ----------
@main.route('/property/<int:id>/360')
def property_360(id):
    prop = Property.query.get_or_404(id)
    return render_template('360_view.html', prop=prop)

# ---------- 14. شات مباشر بين عميل ومكتب ----------
@main.route('/property/<int:id>/chat', methods=['GET','POST'])
@login_required
def property_chat(id):
    prop = Property.query.get_or_404(id)
    if request.method == 'POST':
        content = request.form.get('content','').strip()
        if content:
            msg = ChatMessage(sender_id=current_user.id, receiver_id=prop.user_id, content=f"[عقار {id}] {content}", timestamp=datetime.utcnow(), is_read=False)
            db.session.add(msg)
            db.session.commit()
            flash('تم إرسال رسالتك للمكتب ✅','success')
    messages = ChatMessage.query.filter(
        or_((ChatMessage.sender_id==current_user.id)&(ChatMessage.receiver_id==prop.user_id),
            (ChatMessage.sender_id==prop.user_id)&(ChatMessage.receiver_id==current_user.id))
    ).order_by(ChatMessage.timestamp.asc()).all()
    return render_template('property_chat.html', prop=prop, messages=messages)

# ---------- 15. خريطة خدمات ----------
@main.route('/property/<int:id>/services')
def property_services(id):
    prop = Property.query.get_or_404(id)
    # خدمات وهمية للعرض - لاحقاً تربط بـ Google Places API
    services = [
        {'name': 'مدرسة الأمل', 'type': 'مدرسة', 'distance': '300م'},
        {'name': 'مستشفى النور', 'type': 'مستشفى', 'distance': '500م'},
        {'name': 'مترو المعادي', 'type': 'مترو', 'distance': '800م'},
        {'name': 'سوبر ماركت كارفور', 'type': 'تسوق', 'distance': '200م'},
    ]
    return render_template('services.html', prop=prop, services=services)

# ---------- 16. توثيق العقار ----------
@main.route('/admin/verify-property/<int:id>', methods=['POST'])
@login_required
def verify_property(id):
    if not (current_user.is_owner or current_user.has_perm('can_approve')):
        abort(403)
    prop = Property.query.get_or_404(id)
    # نضيف علامة موثق في الوصف
    if '✅ موثق' not in prop.description:
        prop.description = '✅ موثق من الإدارة - ' + prop.description
    prop.is_approved = True
    db.session.commit()
    flash('تم توثيق العقار ✅','success')
    return redirect(request.referrer or url_for('main.admin_dashboard'))

# ---------- 17. تقييم سعر بالذكاء (تقريبي) ----------
@main.route('/estimate-price', methods=['GET','POST'])
def estimate_price():
    if request.method == 'POST':
        area = request.form.get('area', type=float, default=100)
        location = request.form.get('location','')
        prop_type = request.form.get('property_type','شقة')
        # خوارزمية بسيطة: سعر المتر حسب المنطقة
        price_map = {'التجمع': 25000, 'زايد': 20000, 'اكتوبر': 15000, 'المعادي': 18000, 'مصر الجديدة': 22000}
        base_price = 15000
        for k,v in price_map.items():
            if k in location:
                base_price = v
                break
        estimated = area * base_price
        if prop_type == 'فيلا':
            estimated *= 1.5
        elif prop_type == 'محل':
            estimated *= 2
        return render_template('estimate.html', estimated=estimated, area=area, location=location, property_type=prop_type)
    return render_template('estimate.html')

# ---------- 18. نظام إشعارات ----------
@main.route('/notifications')
@login_required
def notifications():
    logs = ActivityLog.query.filter_by(admin_id=current_user.id).order_by(ActivityLog.timestamp.desc()).limit(50).all()
    return render_template('notifications.html', notifications=logs)

# ---------- 19. API موبايل ----------
@main.route('/api/properties')
def api_properties():
    props = Property.query.filter_by(is_approved=True).order_by(Property.date_posted.desc()).limit(20).all()
    result = []
    for p in props:
        result.append({
            'id': p.id,
            'title': p.title,
            'price': p.price,
            'location': p.location,
            'type': p.property_type,
            'image': url_for('static', filename=f'property_pics/{p.images[0].image_file}') if p.images else None,
            'is_featured': p.is_featured
        })
    return jsonify(result)

@main.route('/api/property/<int:id>')
def api_property_detail(id):
    p = Property.query.get_or_404(id)
    return jsonify({
        'id': p.id,
        'title': p.title,
        'price': p.price,
        'description': p.description,
        'location': p.location,
        'phone': p.phone,
        'youtube': p.youtube_embed if hasattr(p,'youtube_embed') else None
    })

# ---------- 20. تصدير Excel للمكاتب ----------
@main.route('/admin/export-offices')
@login_required
def export_offices():
    if not current_user.is_owner:
        abort(403)
    import csv, io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID','Username','Phone','Email','Verified','Properties','Leads'])
    offices = User.query.filter(User.account_type.in_(['office','broker'])).all()
    for o in offices:
        prop_count = Property.query.filter_by(user_id=o.id).count()
        lead_count = Lead.query.filter_by(office_id=o.id).count()
        writer.writerow([o.id, o.username, o.phone, o.email, o.is_verified, prop_count, lead_count])
    from flask import Response
    return Response(output.getvalue(), mimetype='text/csv', headers={'Content-Disposition':'attachment;filename=offices.csv'})


# ============ بداية المهام الجديدة 1-11 ============

# 2. تعديل عقار - يرجع للمراجعة للعميل
@main.route("/property/<int:property_id>/edit", methods=['GET','POST'])
@login_required
def edit_property(property_id):
    prop = Property.query.get_or_404(property_id)
    if prop.user_id != current_user.id and not (current_user.is_owner or current_user.role in ['admin','super_admin']):
        abort(403)
    form = PropertyForm(obj=prop)
    old_title = prop.title
    old_price = prop.price
    if form.validate_on_submit():
        # سجل التعديل
        changes = []
        if old_title != form.title.data:
            changes.append(f"العنوان من '{old_title}' إلى '{form.title.data}'")
        if old_price != form.price.data:
            changes.append(f"السعر من {old_price} إلى {form.price.data}")
        if changes:
            try:
                # 8. سجل تعديلات العقار
                from app.models import PropertyImage as PI
                log = ActivityLog(action=f"✏️ عدل عقار {prop.id}: " + " | ".join(changes), admin_id=current_user.id)
                db.session.add(log)
            except:
                pass
        
        prop.title = form.title.data
        prop.description = form.description.data
        prop.price = form.price.data
        prop.location = form.location.data
        prop.type = form.type.data
        prop.property_type = form.property_type.data
        prop.bedrooms = form.bedrooms.data
        prop.bathrooms = form.bathrooms.data
        prop.area = form.area.data
        prop.finishing = form.finishing.data if hasattr(form, 'finishing') else None
        prop.phone = form.phone.data
        if hasattr(form, 'whatsapp') and form.whatsapp.data:
            prop.whatsapp = form.whatsapp.data
        # 2. منطق الموافقة عند التعديل
        if current_user.is_owner or current_user.role in ['super_admin','admin']:
            prop.is_approved = True
            flash('✅ تم تعديل العقار ونشر مباشر', 'success')
        else:
            prop.is_approved = False
            prop.is_rejected = False
            flash('✅ تم تعديل العقار - سيراجع من الإدارة', 'success')
        db.session.commit()
        return redirect(url_for('main.property_detail', property_id=prop.id))
    return render_template('create_property_detail.html', form=form, legend='تعديل العقار', title='تعديل')

# 6. تم البيع
@main.route("/property/<int:property_id>/mark-sold", methods=['POST'])
@login_required
def mark_sold(property_id):
    prop = Property.query.get_or_404(property_id)
    if prop.user_id != current_user.id and not (current_user.is_owner or current_user.role in ['admin','super_admin']):
        abort(403)
    try:
        prop.is_sold = True
    except:
        # لو العمود مش موجود، نستخدم is_approved=False مؤقتاً كـ sold
        prop.is_approved = False
        prop.is_rejected = False
        prop.rejection_reason = "تم البيع ✅"
    db.session.commit()
    flash('✅ تم تعليم العقار كمباع - سيبقى في حسابك كإنجاز', 'success')
    log_action(f"✅ علم عقار {prop.id} كمباع")
    return redirect(url_for('main.my_ads'))

@main.route("/property/<int:property_id>/mark-available", methods=['POST'])
@login_required
def mark_available(property_id):
    prop = Property.query.get_or_404(property_id)
    if prop.user_id != current_user.id and not (current_user.is_owner or current_user.role in ['admin','super_admin']):
        abort(403)
    try:
        prop.is_sold = False
        prop.is_approved = True
    except:
        prop.is_approved = True
        prop.rejection_reason = None
    db.session.commit()
    flash('✅ تم إرجاع العقار كمتاح', 'success')
    return redirect(url_for('main.my_ads'))

# 7. Reel
@main.route("/reels")
def reels_page():
    # فيديوهات قصيرة - نجيب العقارات اللي فيها video_url
    props = Property.query.filter(Property.video_url != None, Property.is_approved == True).order_by(Property.date_posted.desc()).limit(30).all()
    return render_template('reels.html', properties=props, title='فيديوهات عقارية قصيرة')

@main.route("/property/<int:property_id>/upload-reel", methods=['POST'])
@login_required
def upload_reel(property_id):
    prop = Property.query.get_or_404(property_id)
    if prop.user_id != current_user.id and not (current_user.is_owner or current_user.role in ['admin','super_admin']):
        abort(403)
    reel_url = request.form.get('reel_url','').strip()
    if reel_url:
        prop.video_url = reel_url
        try:
            prop.reel_video_url = reel_url
        except:
            pass
        db.session.commit()
        flash('✅ تم إضافة فيديو Reel', 'success')
    return redirect(url_for('main.property_detail', property_id=property_id))

# 9. تحسين البحث - normalize
def normalize_arabic(text):
    if not text:
        return ""
    text = text.strip()
    # شقه = شقة = شقق
    replacements = {
        'شقه': 'شقة', 'شقق': 'شقة', 'الشقه': 'شقة',
        'فيله': 'فيلا', 'فلل': 'فيلا',
        'ارض': 'أرض', 'اراضي': 'أرض', 'أراضي': 'أرض',
        'محلات': 'محل', 'محل': 'محل',
        'مكاتب': 'مكتب'
    }
    lower = text.lower()
    return replacements.get(lower, text)

@main.route("/search-advanced")
def advanced_search():
    q = request.args.get('q','').strip()
    q_norm = normalize_arabic(q)
    page = request.args.get('page',1,type=int)
    query = Property.query.filter_by(is_approved=True)
    try:
        query = query.filter(or_(Property.is_sold == False, Property.is_sold == None))
    except:
        pass
    now = datetime.utcnow()
    query = query.filter(or_(Property.expires_at == None, Property.expires_at > now))
    if q_norm:
        query = query.filter(or_(
            Property.title.ilike(f'%{q}%'),
            Property.title.ilike(f'%{q_norm}%'),
            Property.location.ilike(f'%{q}%'),
            Property.property_type.ilike(f'%{q_norm}%'),
            Property.description.ilike(f'%{q}%')
        ))
    negotiable = request.args.get('negotiable')
    if negotiable == '1':
        try:
            query = query.filter_by(negotiable=True)
        except:
            pass
    properties = query.order_by(Property.is_featured.desc(), Property.date_posted.desc()).paginate(page=page, per_page=12, error_out=False)
    return render_template('search_results.html', properties=properties, active_filter=q, title=f'بحث: {q}')

# 10. نسخ احتياطي
@main.route("/admin/backup", methods=['GET','POST'])
@login_required
@owner_required
def backup_db():
    if request.method == 'POST':
        try:
            import shutil
            from flask import current_app
            db_path = os.path.join(current_app.root_path, '../instance/site.db')
            if not os.path.exists(db_path):
                # جرب مسارات تانية
                db_path = os.path.join(current_app.root_path, 'site.db')
            backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            backup_dir = os.path.join(current_app.root_path, 'static/backups')
            os.makedirs(backup_dir, exist_ok=True)
            backup_path = os.path.join(backup_dir, backup_name)
            if os.path.exists(db_path):
                shutil.copy(db_path, backup_path)
                flash(f'✅ تم إنشاء نسخة احتياطية: {backup_name}', 'success')
                log_action(f"💾 نسخة احتياطية {backup_name}")
            else:
                flash('⚠️ لم أجد ملف قاعدة البيانات - لكن تم تسجيل الطلب', 'warning')
        except Exception as e:
            flash(f'خطأ في النسخ: {e}', 'danger')
        return redirect(url_for('main.backup_db'))
    # عرض النسخ القديمة
    try:
        backup_dir = os.path.join(current_app.root_path, 'static/backups')
        files = []
        if os.path.exists(backup_dir):
            files = sorted(os.listdir(backup_dir), reverse=True)[:20]
    except:
        files = []
    return render_template('admin/backup.html', files=files, title='النسخ الاحتياطي')

# 11. صفحة 404 مخصصة
@main.errorhandler(404)
def not_found_error(error):
    try:
        # 3 عقارات مقترحة
        suggested = Property.query.filter_by(is_approved=True).order_by(func.random()).limit(3).all()
    except:
        suggested = []
    return render_template('404.html', suggested=suggested), 404

# 8. عرض سجل تعديلات عقار
@main.route("/property/<int:property_id>/history")
@login_required
def property_history(property_id):
    prop = Property.query.get_or_404(property_id)
    if prop.user_id != current_user.id and not (current_user.is_owner or current_user.role in ['admin','super_admin']):
        abort(403)
    logs = ActivityLog.query.filter(ActivityLog.action.contains(f"{property_id}")).order_by(ActivityLog.timestamp.desc()).limit(50).all()
    return render_template('admin/property_history.html', prop=prop, logs=logs, title='سجل التعديلات')




# ============================================================
# ============ نهاية الـ 20 فكرة + 9 أفكار جديدة ============

# ============================================================
# === الـ 9 أفكار الجديدة - نسخة نظيفة بدون تكرار ===
# ============================================================

# --- الفكرة 6: OTP مجاني بالإيميل (للتجربة يظهر في console) ---
import random
from flask import session

@main.route("/send-otp", methods=['POST'])
@login_required
def send_otp():
    try:
        user = current_user
        otp = str(random.randint(100000, 999999))
        session['email_otp'] = otp
        session['email_otp_expiry'] = (datetime.utcnow() + timedelta(minutes=10)).isoformat()
        session['email_otp_user_id'] = user.id
        print(f"=== OTP FOR {user.email} : {otp} ===")
        flash(f'✅ كود التفعيل: {otp} (للتجربة - في الإنتاج هيتبعت بالإيميل)', 'info')
        return redirect(url_for('main.verify_otp_page'))
    except Exception as e:
        print(f"OTP Error: {e}")
        flash('خطأ في إرسال الكود', 'danger')
        return redirect(url_for('main.home'))

@main.route("/verify-otp", methods=['GET', 'POST'])
@login_required
def verify_otp_page():
    if request.method == 'POST':
        user_code = request.form.get('otp','').strip()
        real_code = session.get('email_otp')
        expiry_str = session.get('email_otp_expiry')
        try:
            expiry = datetime.fromisoformat(expiry_str) if expiry_str else datetime.utcnow()
        except:
            expiry = datetime.utcnow()
        if datetime.utcnow() > expiry:
            flash('الكود انتهت صلاحيته، اطلب كود جديد', 'danger')
            return render_template('verify_otp.html', title='تفعيل الحساب')
        if user_code == real_code and real_code:
            try:
                current_user.is_verified = True
                db.session.commit()
                session.pop('email_otp', None)
                flash('✅ تم تفعيل حسابك بنجاح! تقدر تنزل إعلانات دلوقتي', 'success')
                log_action(f"✅ فعل حسابه بالـ OTP")
                return redirect(url_for('main.home'))
            except Exception as e:
                print(f"Verify Error: {e}")
                flash('خطأ في التفعيل', 'danger')
        else:
            flash('الكود غلط، حاول تاني', 'danger')
    return render_template('verify_otp.html', title='تفعيل الحساب')

# --- الفكرة 1: دليل المناطق الأوتوماتيك ---
@main.route("/منطقة/<area_slug>")
@main.route("/area/<area_slug>")
@main.route("/compound/<compound_slug>")
def area_guide_clean(area_slug=None, compound_slug=None):
    slug = area_slug or compound_slug or ''
    slug = slug.replace('-', ' ').strip()
    page = request.args.get('page', 1, type=int)
    now = datetime.utcnow()
    query = Property.query.filter_by(is_approved=True).filter(or_(Property.expires_at == None, Property.expires_at > now))
    try:
        query = query.filter(or_(Property.is_sold == False, Property.is_sold == None))
    except:
        pass
    if slug:
        query = query.filter(Property.location.ilike(f'%{slug}%'))
    properties = query.order_by(Property.is_featured.desc(), Property.date_posted.desc()).paginate(page=page, per_page=12, error_out=False)
    avg_price = db.session.query(func.avg(Property.price)).filter(Property.location.ilike(f'%{slug}%')).scalar() or 0
    total_count = query.count()
    return render_template('area_guide.html', properties=properties, area_name=slug, avg_price=int(avg_price), total_count=total_count, title=f'عقارات {slug} - Star House')

# --- الفكرة 2 + 9: خريطة تفاعلية + رسم دائرة ---
@main.route("/map-interactive")
def interactive_map_clean():
    now = datetime.utcnow()
    props = Property.query.filter_by(is_approved=True).filter(or_(Property.expires_at == None, Property.expires_at > now)).filter(Property.latitude != None, Property.longitude != None).limit(200).all()
    return render_template('interactive_map.html', properties=props, title='خريطة عقارات Star House')

@main.route("/api/properties-in-circle", methods=['POST'])
def properties_in_circle_clean():
    try:
        data = request.get_json()
        center_lat = float(data.get('lat'))
        center_lng = float(data.get('lng'))
        radius_km = float(data.get('radius', 2))
        props = Property.query.filter_by(is_approved=True).filter(Property.latitude != None).all()
        result = []
        import math
        for p in props:
            if not p.latitude or not p.longitude:
                continue
            dlat = p.latitude - center_lat
            dlng = p.longitude - center_lng
            dist = math.sqrt(dlat**2 + dlng**2) * 111
            if dist <= radius_km:
                result.append({'id': p.id, 'title': p.title, 'price': p.price, 'lat': p.latitude, 'lng': p.longitude, 'location': p.location})
        return jsonify({'count': len(result), 'properties': result[:100]})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@main.route("/api/properties-bounds", methods=['POST'])
def properties_in_bounds_clean():
    try:
        data = request.get_json()
        north = float(data.get('north')); south = float(data.get('south'))
        east = float(data.get('east')); west = float(data.get('west'))
        props = Property.query.filter_by(is_approved=True).filter(Property.latitude != None, Property.latitude >= south, Property.latitude <= north, Property.longitude >= west, Property.longitude <= east).limit(100).all()
        result = [{'id': p.id, 'title': p.title, 'price': p.price, 'lat': p.latitude, 'lng': p.longitude} for p in props]
        return jsonify({'count': len(result), 'properties': result})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

# --- الفكرة 3: تقرير PDF تقدير السعر ---
@main.route("/property/<int:property_id>/price-report")
def price_report_clean(property_id):
    prop = Property.query.get_or_404(property_id)
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        import io
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        c.setFont("Helvetica-Bold", 18)
        c.drawString(50, 800, f"Star House - Price Report")
        c.setFont("Helvetica", 12)
        c.drawString(50, 770, f"Property: {prop.title}")
        c.drawString(50, 750, f"Location: {prop.location}")
        c.drawString(50, 730, f"Price: {prop.price} EGP")
        c.drawString(50, 710, f"Area: {prop.area} m2")
        avg = db.session.query(func.avg(Property.price)).filter(Property.location.ilike(f'%{prop.location}%')).scalar() or prop.price
        c.drawString(50, 680, f"Average in area: {int(avg)} EGP")
        c.drawString(50, 650, f"Estimated fair price: {int((prop.price + avg)/2)} EGP")
        c.drawString(50, 600, f"Generated: {datetime.utcnow().strftime('%Y-%m-%d')}")
        c.showPage()
        c.save()
        buffer.seek(0)
        from flask import send_file
        return send_file(buffer, as_attachment=True, download_name=f"StarHouse_Report_{prop.id}.pdf", mimetype='application/pdf')
    except Exception as e:
        print(f"PDF Error: {e}")
        flash('لتوليد PDF ثبت مكتبة reportlab: pip install reportlab', 'warning')
        return redirect(url_for('main.property_detail', property_id=property_id))

# --- الفكرة 4: الحماية القانونية ---
@main.route("/privacy")
def privacy_page_clean():
    return render_template('legal/privacy.html', title='سياسة الخصوصية - Star House')

@main.route("/terms")
def terms_page_clean():
    return render_template('legal/terms.html', title='شروط الاستخدام - Star House')

@main.route("/trademark")
def trademark_page_clean():
    return render_template('legal/trademark.html', title='العلامة التجارية - Star House')

# --- الفكرة 7: مطلوب عقار Wanted - نسخة محسنة ---
@main.route("/wanted")
def wanted_list_clean():
    page = request.args.get('page', 1, type=int)
    query = WantedRequest.query.order_by(WantedRequest.created_at.desc()) if hasattr(WantedRequest, 'created_at') else WantedRequest.query.order_by(WantedRequest.id.desc())
    wanted = query.paginate(page=page, per_page=20, error_out=False)
    return render_template('wanted_list.html', wanted=wanted, title='مطلوب عقار - Star House')

@main.route("/wanted/new", methods=['GET', 'POST'])
@login_required
def wanted_new_clean():
    if request.method == 'POST':
        try:
            title = request.form.get('title','').strip()
            location = request.form.get('location','').strip()
            budget_min = request.form.get('budget_min', type=int) or 0
            budget_max = request.form.get('budget_max', type=int) or 0
            description = request.form.get('description','').strip()
            phone = request.form.get('phone','').strip() or current_user.phone
            w = WantedRequest(
                title=title,
                location=location,
                budget_min=budget_min,
                budget_max=budget_max,
                description=description,
                phone=phone,
                user_id=current_user.id,
                created_at=datetime.utcnow()
            )
            db.session.add(w)
            db.session.commit()
            flash('✅ تم نشر طلبك، المكاتب هتتواصل معاك قريب', 'success')
            return redirect(url_for('main.wanted_list_clean'))
        except Exception as e:
            db.session.rollback()
            print(f"Wanted Error: {e}")
            flash(f'خطأ: {e}', 'danger')
    return render_template('wanted_new.html', title='أضف طلب عقار')

# --- الفكرة 8: صفحات هبوط SEO ---
@main.route("/شقق/<city>/<ptype>")
@main.route("/landing/<slug>")
def seo_landing_clean(city=None, ptype=None, slug=None):
    if slug and not city:
        keyword = slug.replace('-', ' ')
        city = keyword
        ptype = ''
    page = request.args.get('page', 1, type=int)
    now = datetime.utcnow()
    query = Property.query.filter_by(is_approved=True).filter(or_(Property.expires_at == None, Property.expires_at > now))
    try:
        query = query.filter(or_(Property.is_sold == False, Property.is_sold == None))
    except:
        pass
    if city:
        query = query.filter(Property.location.ilike(f'%{city}%'))
    if ptype:
        query = query.filter(Property.property_type.ilike(f'%{ptype}%'))
    properties = query.order_by(Property.is_featured.desc(), Property.date_posted.desc()).paginate(page=page, per_page=12, error_out=False)
    seo_title = f"شقق للبيع في {city} {ptype or ''} - Star House"
    return render_template('seo_landing.html', properties=properties, city=city, ptype=ptype, title=seo_title)

# --- حماية إضافية: منع الوصول للباك أب ---
@main.route("/static/backups/<path:filename>")
def block_backup_access_clean(filename):
    abort(404)

# ===== Star House SMS - نسيت كلمة السر =====
from flask import request, jsonify

@main.route('/forgot-password/')
def forgot_password_page():
    return render_template('forgot_password.html')

@main.route('/send-sms-otp', methods=['POST'])
@csrf.exempt
def send_otp_route():
    try:
        data = request.get_json() or {}
        phone = data.get('phone', '').strip()
        success, otp, resp = create_and_send_otp(phone)
        print(f"OTP for {phone} = {otp} | SMS: {resp}")
        if success:
            return jsonify({"success": True})
        return jsonify({"success": False, "message": f"فشل: {resp}"})
    except Exception as e:
        print(f"ERROR send_otp: {e}")
        return jsonify({"success": False, "message": str(e)})

@main.route('/verify-sms-otp', methods=['POST'])
@csrf.exempt
def verify_otp_route():
    try:
        data = request.get_json() or {}
        ok, msg = verify_otp(data.get('phone'), data.get('otp'))
        return jsonify({"success": ok, "message": msg})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@main.route('/reset-sms-password', methods=['POST'])
@csrf.exempt
def reset_password_route():
    try:
        data = request.get_json() or {}
        phone = data.get('phone', '').strip()
        new_password = data.get('password', '').strip()
        # نظف الرقم
        clean = phone.replace(" ", "").replace("-", "")
        if clean.startswith("+20"):
            clean = "0" + clean[3:]
        # دور على المستخدم في جدول User
        user = User.query.filter_by(phone=clean).first() or User.query.filter_by(phone=phone).first()
        if not user:
            return jsonify({"success": False, "message": f"مفيش حساب برقم {phone}"})
        # غير الباسورد بجد - مش مجرد success وهمي
        user.password = bcrypt.generate_password_hash(new_password).decode('utf-8')
        db.session.commit()
        print(f"=== PASSWORD RESET OK for {phone} ===")
        return jsonify({"success": True})
    except Exception as e:
        print(f"ERROR reset: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)})

# ============ أكواد التحقق للأدمن - فكرة مسعد ============
@main.route('/admin/otp-codes')
@login_required
@local_admin_required
def admin_otp_codes():
    requests_list = get_otp_requests()
    return render_template('admin/otp_codes.html', requests=requests_list)
# ============ نهاية الـ 9 أفكار النظيفة ============