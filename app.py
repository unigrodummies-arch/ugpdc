import os
import logging
import xmlrpc.client
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

app = Flask(__name__)

# Error Logging configuration
logging.basicConfig(level=logging.DEBUG)

# Database & Security Configuration
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'unigro-secure-key-2026' 

db = SQLAlchemy(app)

# Login Manager Configuration
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Odoo Credentials
ODOO_URL = "https://ug-group-erp.odoo.com/"
ODOO_DB = "alliontechnologies-odoo-uni-gro-master-1235186"
ODOO_USER = "hariramanumakanth@gmail.com"
ODOO_PASS = "71@Galleroad"

# --- Database Models ---

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)

class ReturnedCheque(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cheque_no = db.Column(db.String(50), unique=True, nullable=False)
    cheque_date = db.Column(db.String(50)) 
    customer = db.Column(db.String(200))
    amount = db.Column(db.Float)
    paid_amount = db.Column(db.Float, default=0.0)
    balance_amount = db.Column(db.Float)
    bank = db.Column(db.String(100))
    status = db.Column(db.String(20), default="Pending")
    date_returned = db.Column(db.DateTime, default=datetime.now)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Initialize Database and Create Default User
with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', password='password123')
        db.session.add(admin)
        db.session.commit()

# --- Routes ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.password == password:
            login_user(user)
            return jsonify({'success': True})
        return jsonify({'success': False, 'message': 'Invalid credentials'})
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return render_template('login.html')

@app.route('/')
@login_required
def home():
    return render_template('home.html')

@app.route('/return_cheque')
@login_required
def return_cheque():
    return render_template('return_cheque.html')

@app.route('/payment_entry')
@login_required
def payment_entry():
    return render_template('payment_entry.html')

@app.route('/reports')
@login_required
def reports():
    return render_template('reports.html')

# Odoo Integration with Graceful Error Handling
@app.route('/search_odoo', methods=['POST'])
@login_required
def search_odoo():
    cheque_input = request.json.get('cheque_no', '').strip()
    try:
        common = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/common')
        uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_PASS, {})
        models = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/object')
        
        ids = models.execute_kw(ODOO_DB, uid, ODOO_PASS, 'account.payment', 'search', [[('cheque_no', '=', cheque_input)]])
        
        if ids:
            fields = ['cheque_no', 'cheque_date', 'partner_id', 'amount', 'journal_id', 'date']
            payments_data = models.execute_kw(ODOO_DB, uid, ODOO_PASS, 'account.payment', 'read', [ids], {'fields': fields})
            
            total_amount = sum(p.get('amount', 0.0) for p in payments_data)
            first_record = payments_data[0]
            final_date = first_record.get('cheque_date') or first_record.get('date')
            
            return jsonify({
                'success': True,
                'cheque_no': first_record.get('cheque_no'),
                'customer': first_record.get('partner_id')[1] if first_record.get('partner_id') else "N/A",
                'amount': total_amount,
                'bank': first_record.get('journal_id')[1] if first_record.get('journal_id') else "N/A",
                'cheque_date': final_date 
            })
        return jsonify({'success': False, 'message': 'No records found in Odoo.'})
    except Exception as e:
        return jsonify({'success': False, 'message': f"Odoo Error: {str(e)}"})

@app.route('/save_returned', methods=['POST'])
@login_required
def save_returned():
    data = request.json
    try:
        amt = float(data.get('amount', 0))
        new_return = ReturnedCheque(
            cheque_no=str(data.get('cheque_no')),
            cheque_date=str(data.get('cheque_date')),
            customer=str(data.get('customer')),
            amount=amt,
            paid_amount=0.0,
            balance_amount=amt,
            bank=str(data.get('bank')),
            status="Pending"
        )
        db.session.add(new_return)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/get_history', methods=['GET'])
@login_required
def get_history():
    try:
        # Fetch all records to show in the history table
        records = ReturnedCheque.query.all()
        history_list = []
        for r in records:
            history_list.append({
                'id': r.id,
                'cheque_no': r.cheque_no,
                'cheque_date': r.cheque_date,
                'customer': r.customer,
                'amount': r.amount,
                'status': r.status,
                'date_saved': r.date_returned.strftime('%Y-%m-%d %H:%M')
            })
        return jsonify({'success': True, 'history': history_list})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# Add this route to app.py to support the Payment Entry page
@app.route('/get_pending_cheques', methods=['GET'])
@login_required
def get_pending_cheques():
    try:
        # Fetch only cheques that are NOT fully settled
        records = ReturnedCheque.query.filter(ReturnedCheque.status != 'Settled').all()
        pending_list = []
        for r in records:
            pending_list.append({
                'id': r.id,
                'cheque_no': r.cheque_no,
                'customer': r.customer,
                'amount': r.amount,
                'balance_amount': r.balance_amount
            })
        return jsonify({'success': True, 'pending': pending_list})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/settle_cheque', methods=['POST'])
@login_required
def settle_cheque():
    data = request.json
    try:
        record = ReturnedCheque.query.get(data['id'])
        pay_amt = float(data.get('pay_amount', 0))
        if record:
            record.paid_amount += pay_amt
            record.balance_amount = record.amount - record.paid_amount
            record.status = 'Settled' if record.balance_amount <= 0 else 'Partial'
            if record.balance_amount < 0: record.balance_amount = 0
            db.session.commit()
            return jsonify({'success': True, 'new_balance': record.balance_amount})
        return jsonify({'success': False, 'message': 'Record not found'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

# Report Routes
@app.route('/get_outstanding_report', methods=['GET'])
@login_required
def get_outstanding_report():
    try:
        records = ReturnedCheque.query.filter(ReturnedCheque.balance_amount > 0).all()
        data = [{'customer': r.customer, 'cheque_no': r.cheque_no, 'chq_date': r.cheque_date,
                 'total_amount': r.amount, 'paid': r.paid_amount, 'balance': r.balance_amount, 
                 'status': r.status} for r in records]
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/get_payments_report', methods=['GET'])
@login_required
def get_payments_report():
    try:
        records = ReturnedCheque.query.filter(ReturnedCheque.paid_amount > 0).all()
        data = [{'customer': r.customer, 'cheque_no': r.cheque_no, 'amount_paid': r.paid_amount,
                 'status': r.status, 'date': r.date_returned.strftime('%Y-%m-%d')} for r in records]
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

if __name__ == '__main__':
    # host='0.0.0.0' is required for Tailscale access
    app.run(host='0.0.0.0', port=5000)