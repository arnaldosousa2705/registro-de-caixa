from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from datetime import datetime
from extensions import db
from models.sale import Sale
from models.withdrawal import Withdrawal
from models.daily_register import DailyRegister, brazil_now

sales_bp = Blueprint('sales', __name__)

@sales_bp.route('/sales', methods=['POST'])
@jwt_required()
def create_sale():
    data = request.get_json()
    if data is None:
        return jsonify({"error": "Nenhum dado enviado."}), 400

    if data.get('payment_method') not in ['debito', 'credito', 'pix', 'dinheiro']:
        return jsonify({"error": "Forma de pagamento inválida. Use 'debito', 'credito', 'pix' ou 'dinheiro'."}), 400

    amount = data.get('amount')
    if amount is None or not isinstance(amount, (int, float)) or amount <= 0:
        return jsonify({"error": "Valor inválido. Deve ser um número maior que zero."}), 400

    caixa_aberto = DailyRegister.query.filter_by(
        status='aberto',
        date=brazil_now().date()
    ).first()
    new_sale = Sale(
        amount=amount,
        payment_method=data.get('payment_method'),
        daily_register_id=caixa_aberto.id if caixa_aberto else None
    )
    db.session.add(new_sale)
    db.session.commit()

    return jsonify({
        "id": new_sale.id,
        "date": new_sale.date.strftime('%d-%m-%Y %H:%M:%S'),
        "amount": new_sale.amount,
        "payment_method": new_sale.payment_method
    }), 201

@sales_bp.route('/sales', methods=['GET'])
@jwt_required()
def get_sales():
    requested_date = request.args.get('date')
    requested_register_id = request.args.get('daily_register_id')

    if requested_register_id:
        try:
            requested_register_id = int(requested_register_id)
        except (ValueError, TypeError):
            return jsonify({"error": "ID do caixa inválido."}), 400

        caixa = db.session.get(DailyRegister, requested_register_id)
        if not caixa:
            return jsonify({"error": "Caixa não encontrado."}), 404

        target_date = caixa.date
        sales = Sale.query.filter_by(daily_register_id=requested_register_id).order_by(Sale.id.desc()).all()
        withdrawals = Withdrawal.query.filter_by(daily_register_id=requested_register_id).order_by(Withdrawal.id.desc()).all()
    else:
        try:
            target_date = (
                datetime.strptime(requested_date, '%Y-%m-%d').date()
                if requested_date
                else brazil_now().date()
            )
            if requested_date and target_date.isoformat() != requested_date:
                raise ValueError
        except ValueError:
            return jsonify({"error": "Data inválida. Use o formato YYYY-MM-DD."}), 400

        caixas_do_dia = DailyRegister.query.filter_by(date=target_date).all()
        ids_caixas = [c.id for c in caixas_do_dia]

        sales = Sale.query.filter(Sale.daily_register_id.in_(ids_caixas)).order_by(Sale.id.desc()).all()
        withdrawals = Withdrawal.query.filter(Withdrawal.daily_register_id.in_(ids_caixas)).order_by(Withdrawal.id.desc()).all()

    total_sales = sum(sale.amount for sale in sales)
    total_withdrawals = sum(withdrawal.amount for withdrawal in withdrawals)
    net_total = total_sales - total_withdrawals

    return jsonify({
        "date": target_date.strftime('%d-%m-%Y'),
        "sales": [{
            "id": sale.id,
            "date": sale.date.strftime('%d-%m-%Y %H:%M:%S'),
            "amount": sale.amount,
            "payment_method": sale.payment_method
        } for sale in sales],
        "total_sales": total_sales,
        "withdrawals": [{
            "id": withdrawal.id,
            "date": withdrawal.date.strftime('%d-%m-%Y %H:%M:%S'),
            "amount": withdrawal.amount,
            "reason": withdrawal.reason
        } for withdrawal in withdrawals],
        "total_withdrawals": total_withdrawals,
        "net_total": net_total
    }), 200

@sales_bp.route('/sales/<int:sale_id>', methods=['PUT'])
@jwt_required()
def update_sale(sale_id):
    venda = Sale.query.get(sale_id)
    if not venda:
        return jsonify({"error": "Venda não encontrada."}), 404

    if venda.daily_register and venda.daily_register.status == 'fechado':
        return jsonify({"error": "Não é possível alterar uma venda de um caixa fechado."}), 400

    data = request.get_json()
    if data is None:
        return jsonify({"error": "Nenhum dado enviado."}), 400

    amount = data.get('amount')
    if amount is None or not isinstance(amount, (int, float)) or amount <= 0:
        return jsonify({"error": "Valor inválido. Deve ser um número maior que zero."}), 400

    payment_method = data.get('payment_method')
    if payment_method not in ['debito', 'credito', 'pix', 'dinheiro']:
        return jsonify({"error": "Forma de pagamento inválida. Use 'debito', 'credito', 'pix' ou 'dinheiro'."}), 400

    venda.amount = amount
    venda.payment_method = payment_method
    db.session.commit()

    return jsonify({
        "id": venda.id,
        "date": venda.date.strftime('%d-%m-%Y %H:%M:%S'),
        "amount": venda.amount,
        "payment_method": venda.payment_method
    }), 200

@sales_bp.route('/sales/<int:sale_id>', methods=['DELETE'])
@jwt_required()
def delete_sale(sale_id):
    venda = Sale.query.get(sale_id)
    if not venda:
        return jsonify({"error": "Venda não encontrada."}), 404

    if venda.daily_register and venda.daily_register.status == 'fechado':
        return jsonify({"error": "Não é possível deletar uma venda de um caixa fechado."}), 400

    db.session.delete(venda)
    db.session.commit()

    return jsonify({"message": "Venda deletada com sucesso."}), 200