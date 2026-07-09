from datetime import datetime
from app import db, login_manager
from flask_login import UserMixin

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(db.Model, UserMixin):  # ← شيلت _tablename_
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')
    properties = db.relationship('Property', backref='author', lazy=True, cascade="all, delete-orphan")

    def _repr_(self):
        return f"User('{self.username}', '{self.email}')"

class Property(db.Model):  # ← شيلت _tablename_
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text, nullable=False)
    location = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(20), nullable=False)
    property_type = db.Column(db.String(50), nullable=False)
    is_approved = db.Column(db.Boolean, default=False, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # ← غيرت 'users.id' لـ 'user.id'
    date_posted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    images = db.relationship('PropertyImage', backref='property', lazy=True, cascade="all, delete-orphan")
    bedrooms = db.Column(db.Integer, default=0)
    bathrooms = db.Column(db.Integer, default=0)
    area = db.Column(db.Integer, default=0)
    finishing = db.Column(db.String(50)) # نص زي: سوبر لوكس، نص تشطيب
    phone = db.Column(db.String(20)) # رقم المعلن
    views = db.Column(db.Integer, default=0) # عدد المشاهدات
    negotiable = db.Column(db.Boolean, default=False)
    whatsapp = db.Column(db.String(20))


    def _repr_(self):
        return f"Property('{self.title}', '{self.price}')"

class PropertyImage(db.Model):  # ← شيلت _tablename_
    id = db.Column(db.Integer, primary_key=True)
    image_file = db.Column(db.String(100), nullable=False)
    property_id = db.Column(db.Integer, db.ForeignKey('property.id'), nullable=False)  # ← غيرت 'properties.id' لـ 'property.id'

    def _repr_(self):
        return f"PropertyImage('{self.image_file}')"