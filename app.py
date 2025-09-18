from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy # type: ignore
from werkzeug.security import generate_password_hash, check_password_hash
import os
import uuid
from werkzeug.utils import secure_filename
from datetime import datetime
import re

app = Flask(__name__)
app.secret_key = "your_secret_key"

# Configure SQLite Database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Configure Upload Folder
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure the upload folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)

    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(10), nullable=False)  # 'donor', 'receiver', 'admin'
    contact = db.Column(db.String(20), nullable=False)


class Donation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    donor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    food_name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    quantity = db.Column(db.String(50), nullable=False)
    food_type = db.Column(db.String(10), nullable=False)
    expiry_date = db.Column(db.String(20), nullable=False)
    pickup_location = db.Column(db.String(255), nullable=False)
    contact_info = db.Column(db.String(100), nullable=False)
    food_image = db.Column(db.String(255), nullable=True)

class ReceiverHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    donation_id = db.Column(db.Integer, db.ForeignKey('donation.id'), nullable=False)
    food_name = db.Column(db.String(200), nullable=False)
    pickup_location = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), default='Not Claimed')  # New: Track claim status

# Check and initialize the database if it doesn't exist
def init_db():
    if not os.path.exists("database.db"):
        with app.app_context():
            db.create_all()
            # Add an admin user if none exist
            if not User.query.filter_by(role='admin').first():
                admin_user = User(
                    name="Admin",
                    email="admin@gmail.com",
                    password=generate_password_hash("admin@123"),
                    role="admin",
                    contact="1234567890"
                )
                db.session.add(admin_user)
                db.session.commit()

# Call init_db function to ensure the database is initialized when app starts
init_db()

@app.route('/')
def home():
    return render_template('login.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = User.query.filter_by(email=email).first()

        if user:
            if check_password_hash(user.password, password):
                session['user_id'] = user.id
                session['role'] = user.role
                return redirect(url_for('admin_panel' if user.role == 'admin' else ('donor' if user.role == 'donor' else 'donations')))
            else:
                return render_template('login.html', error="Incorrect password!")  # Show password error
        else:
            return render_template('login.html', error="Email not found! Please register.")

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        contact = request.form['contact']
        password = generate_password_hash(request.form['password'])
        role = request.form['role']

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return render_template('register.html', error="Email already registered!")

        hashed_password = password
        new_user = User(name=name, email=email, password=   hashed_password, role=role,contact=contact)
        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/donor', methods=['GET', 'POST'])
def donor():
    if 'user_id' not in session or session['role'] != 'donor':
        return redirect(url_for('login'))

    if request.method == 'POST':
        food_name = request.form['food_name']
        description = request.form['description']
        quantity = request.form['quantity']
        food_type = request.form['food_type']
        expiry_date = request.form['expiry_date']
        pickup_location = request.form['pickup_location']
        contact_info = request.form['contact_info']

        # Handle file upload
        food_image = request.files['food_image']
        image_filename = None

        if food_image and food_image.filename:
            filename = secure_filename(food_image.filename)
            image_filename = str(uuid.uuid4()) + "_" + filename
            food_image.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))

        new_donation = Donation(
            donor_id=session['user_id'],
            food_name=food_name,
            description=description,
            quantity=quantity,
            food_type=food_type,
            expiry_date=expiry_date,
            pickup_location=pickup_location,
            contact_info=contact_info,
            food_image=image_filename
        )

        db.session.add(new_donation)
        db.session.commit()

        return redirect(url_for('donor'))

    return render_template('donor.html')

@app.route('/donations')
def donations():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    today = datetime.today().strftime('%Y-%m-%d')
    Donation.query.filter(Donation.expiry_date < today).delete()
    db.session.commit()

    # Fetch all donation IDs that have been requested
    requested_donation_ids = {item.donation_id for item in ReceiverHistory.query.all()}

    # Exclude requested donations from the available list
    donation_list = Donation.query.filter(~Donation.id.in_(requested_donation_ids)).all()

    return render_template('donations.html', donations=donation_list)

@app.route('/request_food/<int:donation_id>')
def request_food(donation_id):
    if 'user_id' not in session or session['role'] != 'receiver':
        return redirect(url_for('login'))

    donation = Donation.query.get(donation_id)
    if donation:
        requested_item = ReceiverHistory(
            receiver_id=session['user_id'],
            donation_id=donation.id,
            food_name=donation.food_name,
            pickup_location=donation.pickup_location
        )
        db.session.add(requested_item)
        db.session.commit()

    return redirect(url_for('history'))

@app.route('/history')
def history():
    if 'user_id' not in session or session['role'] != 'receiver':
        return redirect(url_for('login'))

    requested_items = ReceiverHistory.query.filter_by(receiver_id=session['user_id'], status='Not Claimed').all()
    return render_template('history.html', requested_items=requested_items)

@app.route('/donor_history')
def donor_history():
    if 'user_id' not in session or session['role'] != 'donor':
        return redirect(url_for('login'))

    donor_id = session['user_id']

    # Get all donations by this donor
    donations = Donation.query.filter_by(donor_id=donor_id).all()

    # Get all claimed donations
    claimed_donations = {req.donation_id for req in ReceiverHistory.query.filter_by(status="Claimed").all()}

    # Get all requested donations
    requested_donations = {req.donation_id for req in ReceiverHistory.query.filter_by(status="Not Claimed").all()}

    return render_template(
        "donor_history.html",
        donations=donations,
        claimed_donations=claimed_donations,
        requested_donations=requested_donations
    )

@app.route('/admin', methods=['GET', 'POST'])
def admin_panel():
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    requests = ReceiverHistory.query.all()

    # Fetch all donors
    donors = User.query.filter_by(role='donor').all()

    # Fetch all receivers
    receivers = User.query.filter_by(role='receiver').all()

    if request.method == 'POST':
        request_id = request.form.get('request_id')
        request_item = ReceiverHistory.query.get(request_id)
        if request_item:
            request_item.status = "Claimed"
            db.session.commit()

    return render_template('admin.html', requests=requests, donors=donors, receivers=receivers)

@app.route('/cancel_request/<int:request_id>', methods=['POST'])
def cancel_request(request_id):
    if 'user_id' not in session or session['role'] != 'receiver':
        return redirect(url_for('login'))

    request_item = ReceiverHistory.query.get(request_id)

    if request_item and request_item.receiver_id == session['user_id']:
        db.session.delete(request_item)  # Remove the request
        db.session.commit()

    return redirect(url_for('history'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)