from extensions import db
from models.daily_register import brazil_now

class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, default=brazil_now, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(20), nullable=False)
    daily_register_id = db.Column(db.Integer, db.ForeignKey('daily_register.id', name='fk_sale_daily_register'), nullable=True)
    daily_register = db.relationship('DailyRegister', backref='sales')