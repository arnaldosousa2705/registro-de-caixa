from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///loja.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

BRAZIL_TIMEZONE = ZoneInfo('America/Sao_Paulo')


def brazil_now():
    return datetime.now(BRAZIL_TIMEZONE).replace(tzinfo=None)


class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, default=brazil_now, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(20), nullable=False) 

@app.route('/sales', methods=['GET'])
def get_sales():
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

    start = datetime.combine(target_date, datetime.min.time())
    end = start + timedelta(days=1)
    sales = Sale.query.filter(
        Sale.date >= start,
        Sale.date < end
    ).order_by(Sale.id.desc()).all()

    return jsonify({
        "date": target_date.strftime('%d-%m-%Y'),
        "sales": [{
            "id": sale.id,
            "date": sale.date.strftime('%d-%m-%Y %H:%M:%S'),
            "amount": sale.amount,
            "payment_method": sale.payment_method
        } for sale in sales],
        "total": sum(sale.amount for sale in sales)
    }), 200

@app.route('/sales', methods=['POST'])
def create_sale():

    data = request.get_json()
    if data is None:
        return jsonify({"error": "Nenhum dado enviado."}), 400
    
    if data.get('payment_method') not in ['debito', 'credito', 'pix']:
        return jsonify({"error": "Forma de pagamento inválida. Use 'debito', 'credito' ou 'pix'."}), 400
    
    amount = data.get('amount')
    if amount is None or not isinstance(amount, (int, float)) or amount <= 0:
        return jsonify({"error": "Valor inválido. Deve ser um número maior que zero."}), 400

    new_sale = Sale(amount=amount, payment_method=data.get('payment_method'))
    db.session.add(new_sale)
    db.session.commit()

    return jsonify({
       "id": new_sale.id,
         "date": new_sale.date.strftime('%d-%m-%Y %H:%M:%S'),
       "amount": new_sale.amount,
       "payment_method": new_sale.payment_method
    }), 201

if __name__ == '__main__':
    app.run(debug=True)