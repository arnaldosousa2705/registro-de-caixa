from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from extensions import db
from models.daily_register import DailyRegister, brazil_now
from models.sale import Sale
from models.withdrawal import Withdrawal

# Cria o Blueprint do Caixa
daily_bp = Blueprint('daily', __name__)

@daily_bp.route('/daily/open', methods=['POST'])
@jwt_required()
def open_daily():
    # 1. Verificar se já existe caixa aberto
    caixa_aberto = DailyRegister.query.filter_by(
        status='aberto',
        date=brazil_now().date()
    ).first()
    if caixa_aberto:
        return jsonify({"error": "Já existe um caixa aberto."}), 400

    # 2. Criar um novo DailyRegister
    novo_caixa = DailyRegister(date=brazil_now().date())
    db.session.add(novo_caixa)
    db.session.flush()   # dá ID ao objeto sem commitar ainda

    # 3. Adotar vendas pendentes
    vendas_pendentes = Sale.query.filter(Sale.daily_register_id == None).all()
    for venda in vendas_pendentes:
        venda.daily_register_id = novo_caixa.id

    # 4. Adotar retiradas pendentes
    retiradas_pendentes = Withdrawal.query.filter(Withdrawal.daily_register_id == None).all()
    for retirada in retiradas_pendentes:
        retirada.daily_register_id = novo_caixa.id

    # 5. Commit e retornar
    db.session.commit()
    return jsonify({
        "id": novo_caixa.id,
        "date": novo_caixa.date.strftime('%d-%m-%Y'),
        "opened_at": novo_caixa.opened_at.strftime('%d-%m-%Y %H:%M:%S'),
        "status": novo_caixa.status,
        "adopted_sales": len(vendas_pendentes),
        "adopted_withdrawals": len(retiradas_pendentes)
    }), 201

@daily_bp.route('/daily/close', methods=['POST'])
@jwt_required()
def close_daily():
    caixa_aberto = DailyRegister.query.filter_by(
        status='aberto',
        date=brazil_now().date()
    ).first()
    if not caixa_aberto:
        return jsonify({"error": "Não existe caixa aberto."}), 400

    caixa_aberto.status = 'fechado'
    caixa_aberto.closed_at = brazil_now()

    vendas = Sale.query.filter_by(daily_register_id=caixa_aberto.id).all()
    retiradas = Withdrawal.query.filter_by(daily_register_id=caixa_aberto.id).all()

    total_vendas = sum(v.amount for v in vendas)
    total_retiradas = sum(r.amount for r in retiradas)
    liquido = total_vendas - total_retiradas

    db.session.commit()

    return jsonify({
        "id": caixa_aberto.id,
        "date": caixa_aberto.date.strftime('%d-%m-%Y'),
        "opened_at": caixa_aberto.opened_at.strftime('%d-%m-%Y %H:%M:%S'),
        "closed_at": caixa_aberto.closed_at.strftime('%d-%m-%Y %H:%M:%S'),
        "status": caixa_aberto.status,
        "total_sales": total_vendas,
        "total_withdrawals": total_retiradas,
        "net_total": liquido
    }), 200

@daily_bp.route('/daily/status', methods=['GET'])
@jwt_required()
def daily_status():
    caixa_aberto = DailyRegister.query.filter_by(
        status='aberto',
        date=brazil_now().date()
    ).first()
    if not caixa_aberto:
        return jsonify({"status": "fechado", "message": "Nenhum caixa aberto no momento."}), 200
    return jsonify({
        "id": caixa_aberto.id,
        "date": caixa_aberto.date.strftime('%d-%m-%Y'),
        "opened_at": caixa_aberto.opened_at.strftime('%d-%m-%Y %H:%M:%S'),
        "status": caixa_aberto.status
    }), 200