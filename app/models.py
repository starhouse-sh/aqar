from datetime import datetime
from app import db, login_manager
from flask_login import UserMixin

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    properties = db.relationship('Property', backref='author', lazy=True, cascade="all, delete-orphan")
    is_admin = db.Column(db.Boolean, default=False)
    def _repr_(self):
        return f"User('{self.username}', '{self.email}')"

class Property(db.Model):
    __tablename__ = 'properties'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text, nullable=False)
    location = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(50), nullable=False)         
    property_type = db.Column(db.String(50), nullable=False)     
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    images = db.relationship('PropertyImage', backref='property', lazy=True, cascade="all, delete-orphan")

    def _repr_(self):
        return f"Property('{self.title}', '{self.price}')"

class PropertyImage(db.Model):
    __tablename__ = 'property_images'
    id = db.Column(db.Integer, primary_key=True)
    image_file = db.Column(db.String(20), nullable=False, default='default.jpg')
    property_id = db.Column(db.Integer, db.ForeignKey('properties.id'), nullable=False)

    def _repr_(self):
        return f"PropertyImage('{self.image_file}')"