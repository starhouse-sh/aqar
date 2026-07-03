import os

class Config:
    SECRET_KEY = 'd7f4c3d69b2f1a8d4c4bd0b3f7a1d1c9a1b2c3d4e5'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///site.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join('app', 'static', 'property_pics')