from app import create_app, db, bcrypt
from app.models import User

app = create_app()
app.app_context().push()

hashed_password = bcrypt.generate_password_hash('Mmm99998765').decode('utf-8')
admin = User(username='mosadyassein23', email='mosadyassein23@gmail.com', password=hashed_password, role='super_admin')
db.session.add(admin)
db.session.commit()

print("تم إنشاء السوبر أدمن بنجاح!")