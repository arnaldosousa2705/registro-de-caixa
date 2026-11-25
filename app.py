from dotenv import load_dotenv
load_dotenv() # Carrega as variáveis do arquivo .env
from flask import Flask, request, jsonify 
from flask_cors import CORS
from werkzeug.security import generate_password_hash
import click
from flask_jwt_extended import create_access_token 
from extensions import db, migrate, jwt
from config import DevelopmentConfig
from models.user import User
from models.daily_register import DailyRegister, brazil_now
from models.sale import Sale
from models.withdrawal import Withdrawal

# Imports dos Blueprints
from routes.auth import auth_bp
from routes.daily import daily_bp
from routes.sales import sales_bp
from routes.withdrawals import withdrawals_bp
from routes.reports import reports_bp



app = Flask(__name__)
CORS(app)
app.config.from_object(DevelopmentConfig)

db.init_app(app)
migrate.init_app(app, db)
jwt.init_app(app)

app.register_blueprint(auth_bp)
app.register_blueprint(daily_bp)
app.register_blueprint(sales_bp)
app.register_blueprint(withdrawals_bp)
app.register_blueprint(reports_bp)


@app.cli.command("create-admin")
@click.argument("email")
@click.argument("password")
def create_admin(email, password):
    if User.query.filter_by(email=email).first():
        print(f"Usuário com email {email} já existe.")
        return

    hashed_password = generate_password_hash(password)
    new_admin = User(email=email, password_hash=hashed_password, role='admin')
    db.session.add(new_admin)
    db.session.commit()
    print(f"Administrador criado com sucesso: {email}")

@app.cli.command("create-user")
@click.argument("email")
@click.argument("password")
@click.option("--role", default="funcionario", type=click.Choice(["admin", "funcionario"]))
def create_user(email, password, role):
    if User.query.filter_by(email=email).first():
        print(f"Usuário com email {email} já existe.")
        return

    hashed_password = generate_password_hash(password)
    new_user = User(email=email, password_hash=hashed_password, role=role)
    db.session.add(new_user)
    db.session.commit()
    print(f"Usuário criado: {email} ({role})")

if __name__ == '__main__':
    app.run(debug=True)