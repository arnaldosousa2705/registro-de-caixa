import pytest
from app import app as flask_app
from extensions import db
from models.user import User
from werkzeug.security import generate_password_hash
from flask_jwt_extended import create_access_token

@pytest.fixture
def app():
    # 1. Configura o app para usar um banco em memória (temporário)
    flask_app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
      "JWT_SECRET_KEY": "chave-de-teste-segura-com-mais-de-32-bytes",
    })

    # 2. Cria o contexto e as tabelas no banco de teste
    with flask_app.app_context():
        db.create_all()

        # 3. Cria um usuário admin falso para os testes
        admin = User(
            email="admin@teste.com", 
            password_hash=generate_password_hash("senha123"), 
            role="admin"
        )
        db.session.add(admin)
        db.session.commit()

        yield flask_app # O app fica disponível para os testes

        # 4. Limpa o banco após o teste terminar
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    # Simula o navegador (frontend) fazendo requisições
    return app.test_client()

@pytest.fixture
def auth_headers(app):
    # Gera um token JWT falso válido para pular a trava do @jwt_required()
    with app.app_context():
        token = create_access_token(identity="1", additional_claims={"role": "admin"})
        return {"Authorization": f"Bearer {token}"}