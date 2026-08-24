"""Cria/atualiza a conta inicial do Administrador no banco do Render.
A senha nunca é exibida na tela de login e fica armazenada como hash.
"""
import os
from app import Session, User, generate_password_hash

USERNAME = os.getenv("ADMIN_USERNAME", "jader").strip().lower()
NAME = os.getenv("ADMIN_NAME", "Jader")
PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

with Session() as db:
    user = db.query(User).filter(User.username == USERNAME).first()
    if user is None:
        user = User(
            name=NAME,
            username=USERNAME,
            password_hash=generate_password_hash(PASSWORD),
            role="admin",
            active=True,
            failed=0,
            locked_until=None,
        )
        db.add(user)
    else:
        user.name = NAME
        user.password_hash = generate_password_hash(PASSWORD)
        user.role = "admin"
        user.active = True
        user.failed = 0
        user.locked_until = None
    db.commit()
    print("Administrador inicial configurado com sucesso.")
