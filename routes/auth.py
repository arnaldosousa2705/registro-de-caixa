from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token
from werkzeug.security import check_password_hash
from models.user import User

# Cria o Blueprint de autenticação
auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if data is None:
        return jsonify({"error": "Nenhum dado enviado."}), 400

    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"error": "Email e senha são obrigatórios."}), 400

    user = User.query.filter_by(email=email).first()
    if user and check_password_hash(user.password_hash, password):
        token = create_access_token(
            identity=str(user.id),
            additional_claims={"role": user.role}
        )
        return jsonify({"token": token, "role": user.role}), 200
    return jsonify({"error": "Email ou senha inválidos."}), 401