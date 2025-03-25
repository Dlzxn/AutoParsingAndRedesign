from WebApp.BackEnd.db.create_tables import User
from WebApp.BackEnd.db.create_database import SessionLocal


class CRUD:
    def __init__(self):
        self.db = SessionLocal()

    def create_user(self, email, password):
        user = User(email=email, password=password)
        self.db.add(user)
        self.db.commit()
        return user

    def verify_user(self, username, password):
        """Проверяем, существует ли пользователь с указанными данными"""
        user = self.db.query(User).filter(
            User.username == username,
            User.password == password
        ).first()

        return user

db = CRUD()