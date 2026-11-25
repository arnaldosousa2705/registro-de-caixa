from extensions import db
from datetime import datetime
from zoneinfo import ZoneInfo

BRAZIL_TIMEZONE = ZoneInfo('America/Sao_Paulo')

def brazil_now():
    return datetime.now(BRAZIL_TIMEZONE).replace(tzinfo=None)

class DailyRegister(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    opened_at = db.Column(db.DateTime, default=brazil_now, nullable=False)
    closed_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), nullable=False, default='aberto')  # 'open' or 'closed'