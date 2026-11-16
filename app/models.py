from datetime import datetime, timedelta
from app import db
from flask_login import UserMixin
import re

OWNER_EMAIL = "admin@admin.com"
OWNER_PHONE = "01155712096"

ALL_PERMISSIONS = {
    'can_approve': 'الموافقة على العقارات',
    'can_reject': 'رفض العقارات',
    'can_delete': 'مسح العقارات نهائياً',
    'can_feature': 'تثبيت عقار مميز',
    'can_ban_user': 'حظر مستخدم',
    'can_manage_admins': 'إدارة المشرفين',
    'can_add_admin': '➕ إضافة أدمن جديدة / ترقية عميل إلى أدمن',
    'can_view_logs': 'مشاهدة سجل الحركات',
    'can_view_messages': 'مشاهدة رسائل تواصل معنا',
    'can_monitor_chats': 'مراقبة محادثات الموظفين 🕵 (يمنحها المالك)'
}

OWNER_ONLY_PERMISSIONS = ['can_manage_admins']

# ===== التعديل 1: المفضلة - لما العقار يتمسح، يتمسح من المفضلة تلقائي =====
favorites = db.Table('favorites',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), primary_key=True),
    db.Column('property_id', db.Integer, db.ForeignKey('property.id', ondelete='CASCADE'), primary_key=True)
)

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    phone = db.Column(db.String(20), unique=True, nullable=True)
    password = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')
    is_banned = db.Column(db.Boolean, default=False, nullable=False)
    last_login = db.Column(db.DateTime, default=datetime.utcnow)
    is_active_account = db.Column(db.Boolean, default=True)
    permissions = db.Column(db.JSON, default=lambda: {})
    properties = db.relationship('Property', backref='author', lazy=True, cascade="all, delete-orphan")
    favorite_properties = db.relationship('Property', secondary=favorites, backref='favorited_by', lazy='dynamic')

    account_type = db.Column(db.String(20), default='individual', nullable=True)
    company_name = db.Column(db.String(100), nullable=True)
    company_logo = db.Column(db.String(100), nullable=True)
    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    is_blocked = db.Column(db.Boolean, default=False, nullable=False)
    office_doc = db.Column(db.String(200), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    office_address = db.Column(db.String(200), nullable=True)
    rating_avg = db.Column(db.Float, default=0.0, nullable=True)
    rating_count = db.Column(db.Integer, default=0, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    failed_login_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime, nullable=True)

    @property
    def is_owner(self):
        return self.email == OWNER_EMAIL or self.phone == OWNER_PHONE

    @property
    def is_super_admin(self):
        return self.role == 'super_admin'

    @property
    def is_admin(self):
        return self.role in ['admin', 'super_admin']

    @property
    def is_office(self):
        return self.account_type in ['office', 'broker', 'company']

    @property
    def is_broker(self):
        return self.account_type == 'broker'

    @property
    def is_individual(self):
        return self.account_type == 'individual' or self.account_type is None

    @property
    def is_founder(self):
        if not self.created_at:
            return False
        return (datetime.utcnow() - self.created_at).days <= 90 and self.is_office

    @property
    def is_locked(self):
        if not self.locked_until:
            return False
        return datetime.utcnow() < self.locked_until

    def has_perm(self, perm_name):
        if self.is_owner:
            return True
        if perm_name in OWNER_ONLY_PERMISSIONS:
            return False
        if not self.permissions:
            return False
        return self.permissions.get(perm_name, False)

    def can_demote(self, target_user):
        if self.is_owner:
            return target_user.email != OWNER_EMAIL and target_user.id != self.id
        return False

    def set_password(self, password):
        from app import bcrypt
        self.password = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        from app import bcrypt
        try:
            return bcrypt.check_password_hash(self.password, password)
        except Exception:
            return False

    def __repr__(self):
        return f"User('{self.username}', '{self.email}', '{self.role}', '{self.account_type}')"

class Property(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text, nullable=False)
    location = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(20), nullable=False, default='بيع')
    property_type = db.Column(db.String(50), nullable=False, default='شقة')
    is_approved = db.Column(db.Boolean, default=False, nullable=False)
    is_featured = db.Column(db.Boolean, default=False, nullable=False)
    is_rejected = db.Column(db.Boolean, default=False, nullable=False)
    rejection_reason = db.Column(db.String(200))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    date_posted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    images = db.relationship('PropertyImage', backref='property', lazy=True, cascade="all, delete-orphan")
    bedrooms = db.Column(db.Integer, default=0)
    bathrooms = db.Column(db.Integer, default=0)
    area = db.Column(db.Integer, default=0)
    finishing = db.Column(db.String(50))
    phone = db.Column(db.String(20))
    views = db.Column(db.Integer, default=0)
    negotiable = db.Column(db.Boolean, default=False)
    whatsapp = db.Column(db.String(20))
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    featured_until = db.Column(db.DateTime, nullable=True)
    video_url = db.Column(db.String(300), nullable=True)
    virtual_tour_url = db.Column(db.String(300), nullable=True)
    commission_value = db.Column(db.Integer, default=0, nullable=True)
    commission_paid = db.Column(db.Boolean, default=False, nullable=True)
    slug = db.Column(db.String(300), unique=True, nullable=True, index=True)

    # ===== التعديل 2: علاقات الحذف التلقائي - دي اللي بتمنع IntegrityError =====
    # لما العقار يتمسح، كل دول يتمسحوا معاه تلقائي بدل ما يتحولوا لـ NULL
    leads = db.relationship('Lead', backref=db.backref('property_obj', lazy=True), cascade="all, delete-orphan", lazy='dynamic')
    commissions_rel = db.relationship('EmployeeCommission', backref=db.backref('related_property', lazy=True), cascade="all, delete-orphan", lazy='dynamic')
    in_comparisons = db.relationship('UserComparison', backref=db.backref('property_obj', lazy=True), cascade="all, delete-orphan", lazy='dynamic')
    package_subs = db.relationship('PackageSubscription', backref=db.backref('subscribed_property', lazy=True), cascade="all, delete-orphan", lazy='dynamic')

    @property
    def is_expired(self):
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at

    @property
    def is_featured_active(self):
        if not self.is_featured:
            return False
        if self.featured_until and datetime.utcnow() > self.featured_until:
            return False
        return True

    @property
    def youtube_embed(self):
        if not self.video_url:
            return None
        url = self.video_url.strip()
        if "watch?v=" in url:
            vid = url.split("watch?v=")[-1].split("&")[0]
            return f"https://www.youtube.com/embed/{vid}"
        if "youtu.be/" in url:
            vid = url.split("youtu.be/")[-1].split("?")[0]
            return f"https://www.youtube.com/embed/{vid}"
        if "embed/" in url:
            return url
        return None

    @property
    def whatsapp_link(self):
        if not self.phone and not self.whatsapp:
            return None
        num = (self.whatsapp or self.phone or "").strip()
        num = num.replace(" ", "").replace("-", "")
        if num.startswith("0"):
            num = "2" + num
        if num.startswith("01"):
            num = "2" + num
        return f"https://wa.me/{num}?text=مهتم بعقار: {self.title} - {self.location}"

    def get_seo_url(self):
        if self.slug:
            return f"/{self.slug}"
        return f"/property/{self.id}"

def generate_property_slug(prop):
    def clean_text(t):
        if not t:
            return ""
        t = t.strip()
        t = re.sub(r'\s+', '-', t)
        t = re.sub(r'[^\w\u0600-\u06FF\-]', '', t)
        t = re.sub(r'-+', '-', t)
        return t.strip('-')
    title_part = clean_text(prop.title)[:50]
    location_part = clean_text(prop.location)[:30]
    area_part = f"{prop.area}م" if prop.area else ""
    price_part = f"{prop.price}" if prop.price else ""
    type_part = clean_text(prop.property_type) if prop.property_type else ""
    parts = [p for p in [type_part, title_part, area_part, location_part, price_part] if p]
    base_slug = "-".join(parts)
    base_slug = base_slug[:200].strip('-')
    final_slug = f"{base_slug}-{prop.id}" if prop.id else base_slug
    final_slug = re.sub(r'-+', '-', final_slug)
    return final_slug

class PropertyImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    image_file = db.Column(db.String(100), nullable=False)
    property_id = db.Column(db.Integer, db.ForeignKey('property.id', ondelete='CASCADE'), nullable=False)

class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(300), nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    admin = db.relationship('User', backref='logs')
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class ContactMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    date_sent = db.Column(db.DateTime, default=datetime.utcnow)

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=True)
    file_path = db.Column(db.String(200), nullable=True)
    file_type = db.Column(db.String(20), nullable=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_messages')
    receiver = db.relationship('User', foreign_keys=[receiver_id], backref='received_messages')

class Package(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Integer, default=0)
    ads_count = db.Column(db.Integer, default=1)
    duration_days = db.Column(db.Integer, default=7)
    is_featured_included = db.Column(db.Boolean, default=True)
    description = db.Column(db.String(300), nullable=True)
    features = db.Column(db.JSON, default=lambda: [])
    is_active = db.Column(db.Boolean, default=True)
    for_offices_only = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class PackageSubscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    package_id = db.Column(db.Integer, db.ForeignKey('package.id'), nullable=False)
    property_id = db.Column(db.Integer, db.ForeignKey('property.id', ondelete='CASCADE'), nullable=True)
    is_paid = db.Column(db.Boolean, default=False)
    payment_method = db.Column(db.String(20), default='free')
    payment_screenshot = db.Column(db.String(100), nullable=True)
    start_date = db.Column(db.DateTime, default=datetime.utcnow)
    end_date = db.Column(db.DateTime, nullable=True)
    user = db.relationship('User', backref='subscriptions')
    package = db.relationship('Package', backref='subscriptions')
    # اتشالت subscribed_property من هنا - بقت في Property فوق مع cascade

    @property
    def is_active_sub(self):
        if not self.end_date:
            return True
        return datetime.utcnow() <= self.end_date

class OfficeRating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    office_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    rater_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    stars = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    office = db.relationship('User', foreign_keys=[office_id], backref='ratings_received')
    rater = db.relationship('User', foreign_keys=[rater_id], backref='ratings_given')

class EmployeeCommission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    property_id = db.Column(db.Integer, db.ForeignKey('property.id', ondelete='CASCADE'), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    is_paid_to_employee = db.Column(db.Boolean, default=False)
    notes = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    employee = db.relationship('User', backref='commissions')
    # اتشالت related_property من هنا - بقت في Property فوق مع cascade

class UserComparison(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    session_id = db.Column(db.String(100), nullable=True)
    property_id = db.Column(db.Integer, db.ForeignKey('property.id', ondelete='CASCADE'), nullable=False)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    # اتشالت property_obj من هنا - بقت في Property فوق مع cascade

    @property
    def compared_property(self):
        return self.property_obj

class SiteSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    is_free_mode = db.Column(db.Boolean, default=True)
    free_ads_for_individual = db.Column(db.Integer, default=100)
    free_ads_for_office = db.Column(db.Integer, default=100)
    free_ads_when_paid_individual = db.Column(db.Integer, default=2)
    free_ads_when_paid_office = db.Column(db.Integer, default=10)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Lead(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey('property.id', ondelete='CASCADE'), nullable=False)
    office_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    caller_ip = db.Column(db.String(50), nullable=True)
    contact_type = db.Column(db.String(20), nullable=False, default='phone')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # اتشالت property_obj من هنا - بقت في Property فوق مع cascade="all, delete-orphan"
    office = db.relationship('User', backref='leads_received')

class WantedRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    budget = db.Column(db.Integer, nullable=True)
    location = db.Column(db.String(100), nullable=True)
    phone = db.Column(db.String(20), nullable=False)
    request_type = db.Column(db.String(20), default='buy')
    property_type = db.Column(db.String(50), nullable=True)
    is_approved = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    author = db.relationship('User', backref='wanted_requests')