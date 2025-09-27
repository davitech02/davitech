from flask import Flask, send_file, request, jsonify, session, url_for, redirect, flash
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from flask_mail import Mail, Message
import os
import requests
import uuid
import json
from config import Config

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.config.from_object(Config)
# Configure upload folder and secret key
app.config['UPLOAD_FOLDER'] = os.path.join(app.static_folder, 'images')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload size
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-here')

# Initialize extensions
db = SQLAlchemy(app)
jwt = JWTManager(app)
mail = Mail(app)

# Models
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    profile_picture = db.Column(db.String(200), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    address = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    appointments = db.relationship('Appointment', backref='user', lazy=True, cascade='all, delete-orphan')

class Doctor(db.Model):
    __tablename__ = 'doctors'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    specialty = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    appointments = db.relationship('Appointment', backref='doctor', lazy=True)

class Appointment(db.Model):
    __tablename__ = 'appointments'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.String(10), nullable=False)
    reason = db.Column(db.Text, nullable=True)
    payment_status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    payment = db.relationship('Payment', backref='appointment', lazy=True, uselist=False, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'doctor': self.doctor.name,
            'date': self.date.strftime('%Y-%m-%d'),
            'time': self.time,
            'reason': self.reason,
            'status': self.payment_status,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }

class Payment(db.Model):
    __tablename__ = 'payments'
    id = db.Column(db.Integer, primary_key=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointments.id'), nullable=False)
    transaction_id = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), nullable=False)
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)
    
class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'content': self.content,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }

# Seed doctors
def seed_doctors():
    if not Doctor.query.first():
        doctors = [
            Doctor(name="Dr. John Smith", specialty="IVF Specialist", email="john.smith@graceland.com", bio="Experienced IVF specialist with over 10 years of practice."),
            Doctor(name="Dr. Jane Doe", specialty="Antenatal Care", email="jane.doe@graceland.com", bio="Specialized in providing comprehensive antenatal care."),
            Doctor(name="Dr. Emily Brown", specialty="Neonatal Care", email="emily.brown@graceland.com", bio="Expert in neonatal intensive care with advanced training."),
            Doctor(name="Dr. Michael Lee", specialty="General Specialist", email="michael.lee@graceland.com", bio="General specialist with expertise in various medical fields."),
        ]
        db.session.bulk_save_objects(doctors)
        db.session.commit()
        print("Doctors seeded successfully")

# Seed test user
def seed_test_user():
    if not User.query.filter_by(email='test@example.com').first():
        test_user = User(
            name='Test User', 
            email='test@example.com', 
            password=generate_password_hash('testpass123', method='pbkdf2:sha256'),
            phone='1234567890',
            address='123 Test Street, Test City'
        )
        db.session.add(test_user)
        db.session.commit()
        print("Test user created: test@example.com / testpass123")

# Utility to save profile picture
def save_profile_picture(file, user_id):
    if file and file.filename:
        # Generate a unique filename to prevent overwriting
        unique_id = uuid.uuid4().hex[:8]
        filename = secure_filename(f"user_{user_id}_{unique_id}.jpg")
        
        # Create profile_pictures directory if it doesn't exist
        profile_pics_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'profile_pictures')
        os.makedirs(profile_pics_dir, exist_ok=True)
        
        file_path = os.path.join(profile_pics_dir, filename)
        file.save(file_path)
        return f"/static/images/profile_pictures/{filename}"
    return None

# Send appointment confirmation email
def send_appointment_email(user, appointment, doctor):
    try:
        msg = Message(
            subject="Graceland Hospital - Appointment Confirmation",
            recipients=[user.email, app.config['MAIL_DEFAULT_SENDER']],
            body=f"""
Dear {user.name},

Your appointment has been confirmed with the following details:

Doctor: {doctor.name} ({doctor.specialty})
Date: {appointment.date.strftime('%A, %B %d, %Y')}
Time: {appointment.time}
Reason: {appointment.reason or 'Not specified'}

Thank you for choosing Graceland Hospital. If you need to reschedule or cancel, please contact us at least 24 hours before your appointment.

Best regards,
Graceland Hospital Team
            """
        )
        mail.send(msg)
        print(f"Appointment confirmation email sent to {user.email}")
        return True
    except Exception as e:
        print(f"Failed to send email: {str(e)}")
        return False

# Routes
@app.route('/')
def index():
    return send_file('html/index.html')

@app.route('/services')
def services():
    return send_file('html/services.html')

@app.route('/about')
def about():
    return send_file('html/about.html')

@app.route('/blog')
def blog():
    return send_file('html/blog.html')

@app.route('/locations')
def locations():
    return send_file('html/locations.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        data = request.form
        if 'newsletter-email' in data:
            return jsonify({'message': 'Subscribed to newsletter successfully!'})
        return jsonify({'error': 'Feedback sent successfully!'})
    return send_file('html/contact.html')

@app.route('/book', methods=['GET', 'POST'])
def book():
    if request.method == 'POST':
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
            
        data = request.form
        doctor_id = data.get('doctor_id')
        date_str = data.get('date')
        time = data.get('time')
        reason = data.get('reason')
        user_id = session['user_id']

        if not all([doctor_id, date_str, time]):
            return jsonify({'error': 'Doctor, date and time are required'}), 400
            
        try:
            # Validate date format
            date = datetime.strptime(date_str, '%Y-%m-%d')
            
            # Check if date is in the future
            if date.date() < datetime.now().date():
                return jsonify({'error': 'Appointment date must be in the future'}), 400
                
            # Get user and doctor
            user = User.query.get_or_404(user_id)
            doctor = Doctor.query.get_or_404(doctor_id)
            
            # Check for existing appointments at the same time
            existing_appointment = Appointment.query.filter_by(
                doctor_id=doctor_id,
                date=date,
                time=time
            ).first()
            
            if existing_appointment:
                return jsonify({'error': 'This time slot is already booked'}), 400

            # Create payment reference
            tx_ref = f'GRACE_{user_id}_{uuid.uuid4().hex[:8]}_{datetime.now().timestamp()}'
            
            # Prepare payment data for Flutterwave
            payment_data = {
                'tx_ref': tx_ref,
                'amount': 5000,
                'currency': 'NGN',
                'redirect_url': url_for('payment_callback', _external=True),
                'customer': {
                    'email': user.email,
                    'name': user.name,
                    'phone_number': user.phone or 'N/A'
                },
                'customizations': {
                    'title': 'Graceland Hospital Appointment',
                    'description': f'Appointment with {doctor.name} on {date_str} at {time}'
                }
            }
            
            # Initialize payment with Flutterwave
            headers = {'Authorization': f'Bearer {app.config["FLUTTERWAVE_SECRET_KEY"]}'}
            response = requests.post('https://api.flutterwave.com/v3/payments', json=payment_data, headers=headers)
            
            if response.status_code == 200:
                # Create appointment record
                appointment = Appointment(
                    user_id=user_id, 
                    doctor_id=doctor_id, 
                    date=date, 
                    time=time,
                    reason=reason
                )
                db.session.add(appointment)
                db.session.commit()
                
                # Return payment link to frontend
                return jsonify({
                    'message': 'Appointment created, proceed to payment',
                    'payment_url': response.json()['data']['link'],
                    'appointment_id': appointment.id
                })
            else:
                return jsonify({'error': 'Payment initiation failed. Please try again.'}), 400
                
        except ValueError as e:
            return jsonify({'error': f'Invalid date format: {str(e)}'}), 400
        except Exception as e:
            print(f"Appointment booking error: {str(e)}")
            return jsonify({'error': 'An error occurred while booking your appointment'}), 500
            
    # GET request - return booking page
    doctors = Doctor.query.all()
    return send_file('html/book.html')

@app.route('/payment_callback')
def payment_callback():
    tx_ref = request.args.get('tx_ref')
    transaction_id = request.args.get('transaction_id')
    status = request.args.get('status')
    
    if not all([tx_ref, transaction_id, status]):
        return jsonify({'error': 'Invalid callback parameters'}), 400
        
    if status == 'successful':
        try:
            # Verify payment with Flutterwave
            headers = {'Authorization': f'Bearer {app.config["FLUTTERWAVE_SECRET_KEY"]}'}
            response = requests.get(f'https://api.flutterwave.com/v3/transactions/{transaction_id}/verify', headers=headers)
            
            if response.status_code == 200 and response.json()['status'] == 'success':
                # Find the most recent pending appointment
                appointment = Appointment.query.filter_by(payment_status='pending').order_by(Appointment.id.desc()).first()
                
                if appointment:
                    # Update appointment status
                    appointment.payment_status = 'completed'
                    
                    # Create payment record
                    payment = Payment(
                        appointment_id=appointment.id, 
                        transaction_id=transaction_id, 
                        amount=5000, 
                        status='success'
                    )
                    db.session.add(payment)
                    db.session.commit()
                    
                    # Get user and doctor information for email
                    user = User.query.get(appointment.user_id)
                    doctor = Doctor.query.get(appointment.doctor_id)
                    
                    # Send confirmation email
                    send_appointment_email(user, appointment, doctor)
                    
                    return jsonify({
                        'message': 'Payment successful, appointment confirmed!',
                        'appointment': appointment.to_dict(),
                        'redirect': '/profile'
                    })
                else:
                    return jsonify({'error': 'No pending appointment found'}), 400
            else:
                return jsonify({'error': 'Payment verification failed'}), 400
                
        except Exception as e:
            print(f"Payment callback error: {str(e)}")
            return jsonify({'error': f'An error occurred during payment processing: {str(e)}'}), 500
            
    return jsonify({'error': 'Payment was not successful', 'status': status}), 400

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if request.method == 'POST':
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
            
        user_id = session['user_id']
        user = User.query.get_or_404(user_id)
        
        # Update user information
        data = request.form
        if data.get('name'):
            user.name = data.get('name')
        if data.get('email'):
            # Check if email is already taken by another user
            existing_user = User.query.filter_by(email=data.get('email').lower()).first()
            if existing_user and existing_user.id != user_id:
                return jsonify({'error': 'Email already in use by another account'}), 400
            user.email = data.get('email').lower()
        if data.get('phone'):
            user.phone = data.get('phone')
        if data.get('address'):
            user.address = data.get('address')
            
        # Update password if provided
        current_password = data.get('current-password')
        new_password = data.get('new-password')
        confirm_password = data.get('confirm-password')
        
        if current_password and new_password and confirm_password:
            if not check_password_hash(user.password, current_password):
                return jsonify({'error': 'Current password is incorrect'}), 400
            if new_password != confirm_password:
                return jsonify({'error': 'New passwords do not match'}), 400
            if len(new_password) < 8:
                return jsonify({'error': 'Password must be at least 8 characters long'}), 400
                
            user.password = generate_password_hash(new_password, method='pbkdf2:sha256')
        
        # Update profile picture if provided
        profile_picture = request.files.get('profile-picture')
        if profile_picture and profile_picture.filename:
            picture_path = save_profile_picture(profile_picture, user_id)
            if picture_path:
                user.profile_picture = picture_path
        
        try:
            db.session.commit()
            # Update session data
            session['user_name'] = user.name
            session['user_email'] = user.email
            
            return jsonify({
                'message': 'Profile updated successfully!',
                'user': {
                    'name': user.name,
                    'email': user.email,
                    'phone': user.phone,
                    'address': user.address,
                    'profile_picture': user.profile_picture or '/static/images/default-profile.jpg'
                },
                'profile_picture': user.profile_picture or '/static/images/default-profile.jpg'
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': f'Failed to update profile: {str(e)}'}), 400
            
    return send_file('html/profile.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.form
        name = data.get('name')
        email = data.get('email', '').lower()
        password = data.get('password')
        confirm_password = data.get('confirm-password')
        phone = data.get('phone')
        address = data.get('address')
        profile_picture = request.files.get('profile-picture')

        print(f"Register attempt - Name: {name}, Email: {email}")  # Debug log

        if not all([name, email, password, confirm_password]):
            return jsonify({'error': 'Name, email, and password are required'}), 400
        if password != confirm_password:
            return jsonify({'error': 'Passwords do not match'}), 400
        if User.query.filter_by(email=email).first():
            return jsonify({'error': 'Email already exists'}), 400
        if len(password) < 8:
            return jsonify({'error': 'Password must be at least 8 characters long'}), 400

        try:
            hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
            
            # Create new user
            user = User(
                name=name, 
                email=email, 
                password=hashed_password,
                phone=phone,
                address=address
            )
            
            db.session.add(user)
            db.session.commit()
            
            # Save profile picture after user is created to get the ID
            if profile_picture:
                picture_path = save_profile_picture(profile_picture, user.id)
                if picture_path:
                    user.profile_picture = picture_path
                    db.session.commit()
            
            # Create JWT token
            access_token = create_access_token(identity=user.id)
            session['user_id'] = user.id
            
            print(f"User registered successfully: {user.email}")
            return jsonify({
                'message': 'Registered successfully!', 
                'redirect': '/login',
                'access_token': access_token
            })
        except Exception as e:
            db.session.rollback()
            print(f"Registration error: {str(e)}")
            return jsonify({'error': f'Registration failed: {str(e)}'}), 400
    return send_file('html/register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.form
        email = data.get('email', '').lower()
        password = data.get('password', '')
        
        if not email or not password:
            return jsonify({'error': 'Email and password are required'}), 400
            
        try:
            user = User.query.filter_by(email=email).first()
            
            if user and check_password_hash(user.password, password):
                # Create token with 1 day expiration
                access_token = create_access_token(
                    identity=user.id,
                    expires_delta=timedelta(days=1)
                )
                
                # Store user info in session
                session['user_id'] = user.id
                session['user_email'] = user.email
                session['user_name'] = user.name
                
                return jsonify({
                    'message': 'Login successful', 
                    'access_token': access_token,
                    'user': {
                        'id': user.id,
                        'name': user.name,
                        'email': user.email
                    },
                    'redirect': '/'
                })
            else:
                return jsonify({'error': 'Invalid email or password'}), 401
                
        except Exception as e:
            print(f"Login error: {str(e)}")
            return jsonify({'error': 'An error occurred during login'}), 500
            
    return send_file('html/login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return jsonify({'message': 'Logged out successfully', 'redirect': '/login'})

@app.route('/api/doctors')
def get_doctors():
    doctors = Doctor.query.all()
    return jsonify([{'id': d.id, 'name': d.name, 'specialty': d.specialty} for d in doctors])

@app.route('/api/profile')
def get_profile():
    if 'user_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401
        
    user_id = session['user_id']
    user = User.query.get_or_404(user_id)
    appointments = Appointment.query.filter_by(user_id=user_id).order_by(Appointment.date.desc()).all()
    
    return jsonify({
        'user': {
            'id': user.id,
            'name': user.name,
            'email': user.email,
            'phone': user.phone,
            'address': user.address,
            'profile_picture': user.profile_picture or '/static/images/default-profile.jpg',
            'created_at': user.created_at.strftime('%Y-%m-%d')
        },
        'appointments': [appointment.to_dict() for appointment in appointments]
    })
    
@app.route('/api/comments', methods=['GET', 'POST'])
def comments():
    if request.method == 'POST':
        data = request.json
        if not data:
            data = request.form
            
        name = data.get('name')
        email = data.get('email')
        content = data.get('content')
        
        if not all([name, email, content]):
            return jsonify({'error': 'Name, email, and comment are required'}), 400
            
        try:
            # Sanitize input to prevent XSS attacks
            sanitized_content = content.strip()
            
            comment = Comment(name=name, email=email, content=sanitized_content)
            db.session.add(comment)
            db.session.commit()
            
            return jsonify({
                'message': 'Comment submitted successfully!',
                'comment': comment.to_dict()
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': f'Failed to submit comment: {str(e)}'}), 500
    
    # GET request - return all comments
    try:
        comments = Comment.query.order_by(Comment.created_at.desc()).limit(50).all()
        return jsonify({
            'comments': [comment.to_dict() for comment in comments]
        })
    except Exception as e:
        return jsonify({'error': f'Failed to fetch comments: {str(e)}'}), 500

# Separate route for getting comments only
@app.route('/get-comments', methods=['GET'])
def get_comments():
    try:
        comments = Comment.query.order_by(Comment.created_at.desc()).limit(50).all()
        return jsonify({
            'comments': [comment.to_dict() for comment in comments]
        })
    except Exception as e:
        return jsonify({'error': f'Failed to fetch comments: {str(e)}'}), 500
        
# Route to handle comment form submission
@app.route('/submit-comment', methods=['POST'])
def submit_comment():
    name = request.form.get('name')
    email = request.form.get('email')
    content = request.form.get('content')
    
    if not all([name, email, content]):
        flash('All fields are required', 'error')
        return redirect(url_for('index'))
        
    try:
        comment = Comment(name=name, email=email, content=content)
        db.session.add(comment)
        db.session.commit()
        flash('Comment submitted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error submitting comment: {str(e)}', 'error')
    
    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        try:
            db.create_all()
            seed_doctors()
            seed_test_user()
            
            # Add a test comment if none exists
            if not Comment.query.first():
                test_comment = Comment(
                    name='Test User',
                    email='test@example.com',
                    content='This is a test comment. The comment section is working great!'
                )
                db.session.add(test_comment)
                db.session.commit()
                print("Test comment added.")
                
            print("Database initialized and test user created. Auto-reload is disabled.")
        except Exception as e:
            print(f"Failed to initialize database: {str(e)}")
    app.run(debug=True, use_reloader=False)  # Explicitly disable auto-reload