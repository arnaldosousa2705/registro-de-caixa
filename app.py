from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///loja.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(20), nullable=False) 

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
       "date": new_sale.date.isoformat(),
       "amount": new_sale.amount,
       "payment_method": new_sale.payment_method
    }), 201

if __name__ == '__main__':
    app.run(debug=True)