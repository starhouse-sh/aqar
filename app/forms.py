from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, IntegerField, MultipleFileField, SelectField
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
    # حقول البحث اللي في home.html
    city = StringField('المدينة')
    type = SelectField('النوع', choices=[('', 'بيع أو إيجار'), ('sale', 'للبيع'), ('rent', 'للإيجار')])
    property_type = SelectField('نوع العقار', choices=[('', 'كل الأنواع'), ('apartment', 'شقة'), ('villa', 'فيلا'), ('land', 'أرض'), ('office', 'مكتب'), ('shop', 'محل')])
    min_price = IntegerField('السعر من')
    max_price = IntegerField('السعر إلى')
    
    # حقول إضافة العقار - دي اللي عندك اصلاً
    title = StringField('عنوان الاعلان', validators=[DataRequired(), Length(min=5, max=100)])
    description = TextAreaField('وصف العقار', validators=[DataRequired(), Length(min=10)])
    price = IntegerField('السعر', validators=[DataRequired()])
    location = StringField('الموقع', validators=[DataRequired(), Length(min=3, max=100)])
    # ← حقول مكررة بس بفاليديتور مختلف عشان create_property.html
    type = SelectField('النوع', choices=[('sale', 'للبيع'), ('rent', 'للإيجار')], validators=[DataRequired()])
    property_type = SelectField('نوع العقار', choices=[('apartment', 'شقة'), ('villa', 'فيلا'), ('land', 'أرض'), ('office', 'مكتب'), ('shop', 'محل')], validators=[DataRequired()])
    pictures = MultipleFileField('صور العقار', validators=[FileAllowed(['jpg', 'png', 'jpeg', 'webp'])])
    
    submit = SubmitField('حفظ العقار')