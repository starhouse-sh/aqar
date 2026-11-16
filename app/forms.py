from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, IntegerField, MultipleFileField, SelectField, BooleanField, HiddenField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError, Optional, NumberRange
from flask_wtf.file import FileAllowed
from app.models import User
import re

class RegistrationForm(FlaskForm):
    username = StringField('اسم المستخدم', validators=[DataRequired(message="اسم المستخدم مطلوب"), Length(min=2, max=20, message="اسم المستخدم من 2 لـ 20 حرف")], render_kw={"autocomplete": "off"})
    # === موبايل فقط - مفيش ايميل ===
    phone = StringField('رقم الموبايل', validators=[DataRequired(message="رقم الموبايل مطلوب"), Length(min=11, max=11, message="رقم الموبايل 11 رقم")], render_kw={"autocomplete": "off", "placeholder": "01123456789"})
    password = PasswordField('كلمة السر', validators=[DataRequired(message="كلمة السر مطلوبة"), Length(min=6, message="كلمة السر 6 حروف على الأقل")], render_kw={"autocomplete": "new-password"})
    confirm_password = PasswordField('تأكيد كلمة السر', validators=[DataRequired(message="التأكيد مطلوب"), EqualTo('password', message="الباسورد مش مطابق")], render_kw={"autocomplete": "new-password"})
    submit = SubmitField('تسجيل')

    def validate_username(self, username):
        user = User.query.filter(User.username.ilike(username.data.strip())).first()
        if user:
            raise ValidationError('اسم المستخدم ده موجود بالفعل.')

    def validate_phone(self, phone):
        raw = phone.data.strip().replace(" ", "").replace("-", "") if phone.data else ""
        if raw.startswith("+20"):
            raw = "0" + raw[3:]
        elif raw.startswith("0020"):
            raw = "0" + raw[4:]
        # لازم يبدأ بـ 01 ويكون 11 رقم
        if not re.match(r'^01[0125][0-9]{8}$', raw):
            raise ValidationError('رقم الموبايل لازم يبدأ بـ 010 أو 011 أو 012 أو 015 ويكون 11 رقم - مثال: 01123456789')
        # موجود قبل كده؟
        existing = User.query.filter_by(phone=raw).first()
        if existing:
            raise ValidationError('رقم الموبايل ده متسجل قبل كده - سجل دخول')
        # حدث القيمة المنظفة
        phone.data = raw

    # للتوافق مع الكود القديم اللي بيستخدم identifier
    @property
    def identifier(self):
        return self.phone

class LoginForm(FlaskForm):
    # دخول بالموبايل فقط
    phone = StringField('رقم الموبايل', validators=[DataRequired(message="اكتب رقم الموبايل")], render_kw={"autocomplete": "off", "placeholder": "01123456789"})
    password = PasswordField('كلمة المرور', validators=[DataRequired(message="كلمة المرور مطلوبة")], render_kw={"autocomplete": "off"})
    submit = SubmitField('تسجيل الدخول')

    # للتوافق مع الكود اللي بيستخدم identifier
    @property
    def identifier(self):
        return self.phone

class SearchForm(FlaskForm):
    city = StringField('المدينة', render_kw={"autocomplete": "off"})
    type = SelectField('النوع', choices=[('', 'بيع أو إيجار'), ('بيع', 'للبيع'), ('ايجار', 'للإيجار')], render_kw={"autocomplete": "off"})
    property_type = SelectField('نوع العقار', choices=[('', 'كل الأنواع'), ('شقة', 'شقة'), ('فيلا', 'فيلا'), ('أرض', 'أرض'), ('مكتب', 'مكتب'), ('محل', 'محل')], render_kw={"autocomplete": "off"})
    min_price = IntegerField('السعر من', validators=[Optional()], render_kw={"autocomplete": "off"})
    max_price = IntegerField('السعر إلى', validators=[Optional()], render_kw={"autocomplete": "off"})
    submit = SubmitField('بحث')

class PropertyForm(FlaskForm):
    type = SelectField('الغرض', choices=[('بيع', 'للبيع'), ('ايجار', 'للإيجار')], validators=[DataRequired(message="اختار الغرض - بيع ولا ايجار")], render_kw={"autocomplete": "off"})
    property_type = SelectField('نوع العقار', choices=[
        ('شقة', 'شقة'), ('فيلا', 'فيلا'), ('دوبلكس', 'دوبلكس'), ('روف', 'روف'),
        ('بنتهاوس', 'بنتهاوس'), ('تاون هاوس', 'تاون هاوس'), ('بيزمنت', 'بيزمنت'),
        ('مخزن', 'مخزن'), ('بدروم', 'بدروم'), ('أرض', 'أرض'), ('مكتب', 'مكتب'), ('محل', 'محل')
    ], validators=[DataRequired(message="اختار نوع العقار")], render_kw={"autocomplete": "off"})
    location = StringField('الموقع', validators=[DataRequired(message="الموقع مطلوب - مثال: التجمع الخامس"), Length(min=3, max=100, message="الموقع قصير جدا")], render_kw={"autocomplete": "off"})
    title = StringField('عنوان الاعلان', validators=[DataRequired(message="العنوان مطلوب"), Length(min=5, max=100, message="العنوان لازم اكتر من 5 حروف")], render_kw={"autocomplete": "off"})
    price = IntegerField('السعر', validators=[DataRequired(message="السعر مطلوب - اكتب السعر بالجنيه")], render_kw={"autocomplete": "off"})
    negotiable = BooleanField('قابل للتفاوض')
    area = IntegerField('المساحة م²', validators=[DataRequired(message="المساحة مطلوبة - اكتب المساحة بالمتر")], render_kw={"autocomplete": "off"})
    bedrooms = IntegerField('عدد الغرف', validators=[Optional()], render_kw={"autocomplete": "off"})
    bathrooms = IntegerField('عدد الحمامات', validators=[Optional()], render_kw={"autocomplete": "off"})
    finishing = SelectField('التشطيب', choices=[
        ('بدون تشطيب', 'بدون تشطيب'), ('نص تشطيب', 'نص تشطيب'),
        ('تشطيب كامل', 'تشطيب كامل'), ('سوبر لوكس', 'سوبر لوكس'),
        ('الترا سوبر لوكس', 'الترا سوبر لوكس')
    ], validators=[DataRequired(message="اختار التشطيب")], render_kw={"autocomplete": "off"})
    description = TextAreaField('وصف العقار', validators=[DataRequired(message="الوصف مطلوب"), Length(min=10, message="الوصف لازم اكتر من 10 حروف - اكتب تفاصيل اكتر")], render_kw={"autocomplete": "off"})
    phone = StringField('رقم الموبايل', validators=[DataRequired(message="رقم الموبايل مطلوب"), Length(min=10, max=15, message="رقم الموبايل لازم من 10 لـ 15 رقم - مثال: 01012345678")], render_kw={"autocomplete": "off"})
    whatsapp = StringField('رقم الواتساب', validators=[Optional(), Length(min=10, max=15, message="رقم الواتساب لازم من 10 لـ 15 رقم - مثال: 01012345678 أو سيبه فاضي")], render_kw={"autocomplete": "off"})
    pictures = MultipleFileField('صور العقار', validators=[FileAllowed(['jpg', 'png', 'jpeg', 'webp'], message="الصور لازم تكون jpg, png, jpeg, webp فقط")])
    latitude = HiddenField('latitude', validators=[Optional()])
    longitude = HiddenField('longitude', validators=[Optional()])
    submit = SubmitField('حفظ العقار')
