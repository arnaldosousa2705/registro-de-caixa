from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from extensions import db
from models.withdrawal import Withdrawal
from models.daily_register import DailyRegister, brazil_now

withdrawals_bp = Blueprint('withdrawals', __name__)

@withdrawals_bp.route('/withdrawals', methods=['POST'])
@jwt_required()
def create_withdrawal():
    data = request.get_json()
    if data is None:
        return jsonify({"error": "Nenhum dado enviado."}), 400
    amount = data.get('amount')
    if amount is None or not isinstance(amount, (int, float)) or amount <= 0:
        return jsonify({"error": "Valor inválido. Deve ser um número maior que zero."}), 400
    reason = data.get('reason')
    if not reason or not isinstance(reason, str) or not reason.strip() or len(reason) > 200:
        return jsonify({"error": "Motivo inválido."}), 400
    
    caixa_aberto = DailyRegister.query.filter_by(
        status='aberto',
        date=brazil_now().date()
    ).first()
    
    new_withdrawal = Withdrawal(
        amount=amount,
        reason=reason.strip(),
        daily_register_id=caixa_aberto.id if caixa_aberto else None)
    db.session.add(new_withdrawal)
    db.session.commit()

    return jsonify({
        "id": new_withdrawal.id,
        "date": new_withdrawal.date.strftime('%d-%m-%Y %H:%M:%S'),
        "amount": new_withdrawal.amount,
        "reason": new_withdrawal.reason
    }), 201

@withdrawals_bp.route('/withdrawals/<int:withdrawal_id>', methods=['PUT'])
@jwt_required()
def update_withdrawal(withdrawal_id):
    retirada = Withdrawal.query.get(withdrawal_id)
    if not retirada:
        return jsonify({"error": "Retirada não encontrada."}), 404

    if retirada.daily_register and retirada.daily_register.status == 'fechado':
        return jsonify({"error": "Não é possível alterar uma retirada de um caixa fechado."}), 400

    data = request.get_json()
    if data is None:
        return jsonify({"error": "Nenhum dado enviado."}), 400

    amount = data.get('amount')
    if amount is None or not isinstance(amount, (int, float)) or amount <= 0:
        return jsonify({"error": "Valor inválido. Deve ser um número maior que zero."}), 400

    reason = data.get('reason')
    if not reason or not isinstance(reason, str) or not reason.strip() or len(reason) > 200:
        return jsonify({"error": "Motivo inválido."}), 400

    retirada.amount = amount
    retirada.reason = reason.strip()
    db.session.commit()

    return jsonify({
        "id": retirada.id,
        "date": retirada.date.strftime('%d-%m-%Y %H:%M:%S'),
        "amount": retirada.amount,
        "reason": retirada.reason
    }), 200

@withdrawals_bp.route('/withdrawals/<int:withdrawal_id>', methods=['DELETE'])
@jwt_required()
def delete_withdrawal(withdrawal_id):
    retirada = Withdrawal.query.get(withdrawal_id)
    if not retirada:
        return jsonify({"error": "Retirada não encontrada."}), 404

    if retirada.daily_register and retirada.daily_register.status == 'fechado':
        return jsonify({"error": "Não é possível deletar uma retirada de um caixa fechado."}), 400

    db.session.delete(retirada)
    db.session.commit()

    return jsonify({"message": "Retirada deletada com sucesso."}), 200