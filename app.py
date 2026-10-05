from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from zoneinfo import ZoneInfo
from sqlalchemy import func
from datetime import datetime, timedelta, date
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///loja.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

BRAZIL_TIMEZONE = ZoneInfo('America/Sao_Paulo')


def brazil_now():
    return datetime.now(BRAZIL_TIMEZONE).replace(tzinfo=None)

class DailyRegister(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    opened_at = db.Column(db.DateTime, default=brazil_now, nullable=False)
    closed_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), nullable=False, default='aberto')  # 'open' or 'closed'

class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, default=brazil_now, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(20), nullable=False)
    daily_register_id = db.Column(db.Integer, db.ForeignKey('daily_register.id', name='fk_sale_daily_register'), nullable=True)
    daily_register = db.relationship('DailyRegister', backref='sales')

class Withdrawal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, default=brazil_now, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    reason = db.Column(db.String(200), nullable=False)
    daily_register_id = db.Column(
        db.Integer, db.ForeignKey('daily_register.id', name='fk_withdrawal_daily_register'), nullable=True)
    daily_register = db.relationship('DailyRegister', backref='withdrawals')

@app.route('/daily/open', methods=['POST'])
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
    db.session.flush()   # ← dá ID ao objeto sem commitar ainda

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

@app.route('/daily/close', methods=['POST'])
def close_daily():
    # 1. Buscar caixa aberto
    caixa_aberto = DailyRegister.query.filter_by (
        status='aberto',
        date=brazil_now().date()
    ).first()
    if not caixa_aberto:
        return jsonify({"error": "Não existe caixa aberto."}), 400

    # 2. Atualizar status e closed_at
    caixa_aberto.status = 'fechado'
    caixa_aberto.closed_at = brazil_now()

    # 3. Buscar vendas e retiradas vinculadas a este caixa
    vendas = Sale.query.filter_by(daily_register_id=caixa_aberto.id).all()
    retiradas = Withdrawal.query.filter_by(daily_register_id=caixa_aberto.id).all()

    # 4. Calcular totais
    total_vendas = sum(v.amount for v in vendas)
    total_retiradas = sum(r.amount for r in retiradas)
    liquido = total_vendas - total_retiradas

    # 5. Commit único
    db.session.commit()

    # 6. Retornar resumo
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

@app.route('/daily/status', methods=['GET'])
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

@app.route('/reports/monthly', methods=['GET'])
def report_monthly():
    # 1. Ler e validar os parâmetros
    year = request.args.get('year')
    month = request.args.get('month')
    try:
        year = int(year) if year else brazil_now().year
        month = int(month) if month else brazil_now().month
        if not (1 <= month <= 12):
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"error": "Ano e mês inválidos. Use ?year=2026&month=9"}), 400

    # 2. Calcular início e fim do mês
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)

    # 3. Soma das vendas (JOIN com DailyRegister)
    total_sales = db.session.query(func.sum(Sale.amount)).join(
        DailyRegister, Sale.daily_register_id == DailyRegister.id
    ).filter(
        DailyRegister.date >= start,
        DailyRegister.date < end
    ).scalar() or 0

    # 4. Soma das retiradas (JOIN com DailyRegister)
    total_withdrawals = db.session.query(func.sum(Withdrawal.amount)).join(
        DailyRegister, Withdrawal.daily_register_id == DailyRegister.id
    ).filter(
        DailyRegister.date >= start,
        DailyRegister.date < end
    ).scalar() or 0

    # 5. Retornar
    return jsonify({
        "year": year,
        "month": month,
        "total_sales": total_sales,
        "total_withdrawals": total_withdrawals,
        "net_total": total_sales - total_withdrawals
    }), 200


@app.route('/reports/yearly', methods=['GET'])
def report_yearly():
    # 1. Ler e validar o ano
    year = request.args.get('year')
    try:
        year = int(year) if year else brazil_now().year
    except (ValueError, TypeError):
        return jsonify({"error": "Ano inválido. Use ?year=2026"}), 400

    # 2. Início e fim do ano
    start = date(year, 1, 1)
    end = date(year + 1, 1, 1)

    # 3. Soma das vendas
    total_sales = db.session.query(func.sum(Sale.amount)).join(
        DailyRegister, Sale.daily_register_id == DailyRegister.id
    ).filter(
        DailyRegister.date >= start,
        DailyRegister.date < end
    ).scalar() or 0

    # 4. Soma das retiradas
    total_withdrawals = db.session.query(func.sum(Withdrawal.amount)).join(
        DailyRegister, Withdrawal.daily_register_id == DailyRegister.id
    ).filter(
        DailyRegister.date >= start,
        DailyRegister.date < end
    ).scalar() or 0

    # 5. Retornar
    return jsonify({
        "year": year,
        "total_sales": total_sales,
        "total_withdrawals": total_withdrawals,
        "net_total": total_sales - total_withdrawals
    }), 200

@app.route('/sales', methods=['POST'])
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

@app.route('/sales', methods=['GET'])
def get_sales():
    requested_date = request.args.get('date')
    requested_register_id = request.args.get('daily_register_id')

    if requested_register_id:
        try:
            requested_register_id = int(requested_register_id)
        except (ValueError, TypeError):
            return jsonify({"error": "ID do caixa inválido."}), 400

        caixa = DailyRegister.query.get(requested_register_id)
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

        # Busca todos os caixas do dia (pode ter mais de um)
        caixas_do_dia = DailyRegister.query.filter_by(date=target_date).all()
        ids_caixas = [c.id for c in caixas_do_dia]

        # Busca vendas e retiradas vinculadas a qualquer um desses caixas
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

@app.route('/withdrawals', methods=['POST'])
def create_withdrawal():

    data = request.get_json()
    if data is None:
        return jsonify({"error": "Nenhum dado enviado."}), 400
    amount = data.get('amount')
    if amount is None or not isinstance(amount, (int, float)) or amount <= 0:
        return jsonify({"error": "Valor inválido. Deve ser um número maior que zero."}),400
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

if __name__ == '__main__':
    app.run(debug=True)