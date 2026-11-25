from flask import Blueprint, request, jsonify
from sqlalchemy import func
from datetime import datetime, date
from extensions import db
from models.daily_register import DailyRegister, brazil_now
from models.sale import Sale
from models.withdrawal import Withdrawal

# Precisamos importar o admin_required. 
# Para evitar import circular, vamos mover o admin_required para cá ou criar um arquivo separado. 
# Por enquanto, vamos importar do app.py (mas faremos isso com cuidado).
# Na verdade, para evitar problemas, vamos recriar o decorator aqui:
from flask_jwt_extended import verify_jwt_in_request, get_jwt
from functools import wraps

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        claims = get_jwt()
        if claims.get("role") != "admin":
            return jsonify({"error": "Acesso restrito a administradores."}), 403
        return fn(*args, **kwargs)
    return wrapper

reports_bp = Blueprint('reports', __name__)

@reports_bp.route('/reports/monthly', methods=['GET'])
@admin_required
def report_monthly():
    year = request.args.get('year')
    month = request.args.get('month')
    try:
        year = int(year) if year else brazil_now().year
        if not (2000 <= year <= 2100):
            raise ValueError
        month = int(month) if month else brazil_now().month
        if not (1 <= month <= 12):
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"error": "Ano e mês inválidos. Use ?year=2026&month=9"}), 400

    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)

    total_sales = db.session.query(func.sum(Sale.amount)).join(
        DailyRegister, Sale.daily_register_id == DailyRegister.id
    ).filter(
        DailyRegister.date >= start,
        DailyRegister.date < end
    ).scalar() or 0

    total_withdrawals = db.session.query(func.sum(Withdrawal.amount)).join(
        DailyRegister, Withdrawal.daily_register_id == DailyRegister.id
    ).filter(
        DailyRegister.date >= start,
        DailyRegister.date < end
    ).scalar() or 0

    return jsonify({
        "year": year,
        "month": month,
        "total_sales": total_sales,
        "total_withdrawals": total_withdrawals,
        "net_total": total_sales - total_withdrawals
    }), 200

@reports_bp.route('/reports/yearly', methods=['GET'])
@admin_required
def report_yearly():
    year = request.args.get('year')
    try:
        year = int(year) if year else brazil_now().year
        if not (2000 <= year <= 2100):
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"error": "Ano inválido. Use ?year=2026"}), 400

    start = date(year, 1, 1)
    end = date(year + 1, 1, 1)

    total_sales = db.session.query(func.sum(Sale.amount)).join(
        DailyRegister, Sale.daily_register_id == DailyRegister.id
    ).filter(
        DailyRegister.date >= start,
        DailyRegister.date < end
    ).scalar() or 0

    total_withdrawals = db.session.query(func.sum(Withdrawal.amount)).join(
        DailyRegister, Withdrawal.daily_register_id == DailyRegister.id
    ).filter(
        DailyRegister.date >= start,
        DailyRegister.date < end
    ).scalar() or 0

    return jsonify({
        "year": year,
        "total_sales": total_sales,
        "total_withdrawals": total_withdrawals,
        "net_total": total_sales - total_withdrawals
    }), 200

@reports_bp.route('/reports/daily', methods=['GET'])
@admin_required
def report_daily():
    requested_date = request.args.get('date')
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

    caixas_do_dia = DailyRegister.query.filter_by(date=target_date).order_by(DailyRegister.opened_at).all()
    
    registers = []
    for caixa in caixas_do_dia:
        vendas = Sale.query.filter_by(daily_register_id=caixa.id).all()
        retiradas = Withdrawal.query.filter_by(daily_register_id=caixa.id).all()
        total_vendas = sum(v.amount for v in vendas)
        total_retiradas = sum(r.amount for r in retiradas)
        liquido = total_vendas - total_retiradas

        registers.append({
            "id": caixa.id,
            "opened_at": caixa.opened_at.strftime('%d-%m-%Y %H:%M:%S'),
            "closed_at": caixa.closed_at.strftime('%d-%m-%Y %H:%M:%S') if caixa.closed_at else None,
            "status": caixa.status,
            "total_sales": total_vendas,
            "total_withdrawals": total_retiradas,
            "net_total": liquido
        })

    return jsonify({
        "date": target_date.strftime('%d-%m-%Y'),
        "registers": registers
    }), 200