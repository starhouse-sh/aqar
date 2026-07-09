from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, IntegerField, MultipleFileField, SelectField, BooleanField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError, Optional
from flask_wtf.file import FileAllowed
from app.models import User


class RegistrationForm(FlaskForm):
    username = StringField('اسم المستخدم', validators=[DataRequired(), Length(min=2, max=20)])
    email = StringField('الايميل', validators=[DataRequired(), Email()])
    password = PasswordField('كلمة السر', validators=[DataRequired()])
    confirm_password = PasswordField('تأكيد كلمة السر', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('تسجيل')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('اسم المستخدم ده موجود بالفعل.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('الايميل ده متسجل قبل كده.')


class LoginForm(FlaskForm):
    email = StringField('البريد الالكتروني', validators=[DataRequired(), Email()])
    password = PasswordField('كلمة المرور', validators=[DataRequired()])
    submit = SubmitField('تسجيل الدخول')


class SearchForm(FlaskForm):
    city = StringField('المدينة')
    type = SelectField('النوع', choices=[('', 'بيع أو إيجار'), ('sale', 'للبيع'), ('rent', 'للإيجار')])
    property_type = SelectField('نوع العقار', choices=[('', 'كل الأنواع'), ('apartment', 'شقة'), ('villa', 'فيلا'), ('land', 'أرض'), ('office', 'مكتب'), ('shop', 'محل')])
    min_price = IntegerField('السعر من', validators=[Optional()])
    max_price = IntegerField('السعر إلى', validators=[Optional()])
    submit = SubmitField('بحث')


class PropertyForm(FlaskForm):
    # 1. في الأعلى: الغرض ونوع العقار
    type = SelectField('الغرض', choices=[('sale', 'للبيع'), ('rent', 'للإيجار')], validators=[DataRequired()])
    property_type = SelectField('نوع العقار', choices=[
        ('apartment', 'شقة'), 
        ('villa', 'فيلا'), 
        ('duplex', 'دوبلكس'),
        ('roof', 'روف'),
        ('penthouse', 'بنتهاوس'),
        ('townhouse', 'تاون هاوس'),
        ('besement', 'بيزمنت'),
        ('warehouse', 'مخزن'),
        ('cellar', 'بدروم'),
        ('land', 'أرض'), 
        ('office', 'مكتب'), 
        ('shop', 'محل')
    ], validators=[DataRequired()])
    
    # 2. الموقع
    location = StringField('الموقع', validators=[DataRequired(), Length(min=3, max=100)])
    
    # 3. عنوان الاعلان
    title = StringField('عنوان الاعلان', validators=[DataRequired(), Length(min=5, max=100)])
    
    # 4. السعر + قابل للتفاوض
    price = IntegerField('السعر', validators=[DataRequired()])
    negotiable = BooleanField('قابل للتفاوض')
    
    # 5. تفاصيل العقار: مساحة ثم غرف ثم حمامات
    area = IntegerField('المساحة م²', validators=[DataRequired()])
    bedrooms = IntegerField('عدد الغرف', validators=[DataRequired()])
    bathrooms = IntegerField('عدد الحمامات', validators=[DataRequired()])
    finishing = SelectField('التشطيب', choices=[
        ('', 'اختر التشطيب'),
        ('بدون تشطيب', 'بدون تشطيب'),
        ('نص تشطيب', 'نص تشطيب'),
        ('تشطيب كامل', 'تشطيب كامل'),
        ('سوبر لوكس', 'سوبر لوكس'),
        ('الترا سوبر لوكس', 'الترا سوبر لوكس')
    ], validators=[DataRequired()])
    
    # 6. وصف العقار
    description = TextAreaField('وصف العقار', validators=[DataRequired(), Length(min=10)])
    
    # 7. أرقام التواصل
    phone = StringField('رقم الموبايل', validators=[DataRequired(), Length(min=11, max=11)])
    whatsapp = StringField('رقم الواتساب', validators=[Optional(), Length(min=11, max=11)])
    
    # 8. الصور
    pictures = MultipleFileField('صور العقار', validators=[FileAllowed(['jpg', 'png', 'jpeg', 'webp'])])
    
    submit = SubmitField('حفظ العقار')