import io
import os
import random
import re
import secrets
from datetime import datetime, timedelta
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, abort, jsonify, redirect, render_template, request, send_file, session, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

app = Flask(__name__, instance_relative_config=True)
os.makedirs(app.instance_path, exist_ok=True)
default_database = f"sqlite:///{os.path.join(app.instance_path, 'telecare.db')}"
app.config.update(
    SECRET_KEY=os.getenv('SECRET_KEY', 'dev-only-change-me'),
    SQLALCHEMY_DATABASE_URI=os.getenv('DATABASE_URL', default_database),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    OTP_MODE=os.getenv('OTP_MODE', 'development'),
)
db = SQLAlchemy(app)

SPECIALIZATIONS = ['General Physician', 'Cardiology', 'Dermatology', 'Pediatrics', 'Gynecology', 'Orthopedics', 'Neurology', 'ENT', 'Ophthalmology', 'Psychiatry']
VIDEO_URLS = {
    'home': '/static/videos/home.mp4', 'appointments': '/static/videos/appointments.mp4',
    'consultation': '/static/videos/consultation.mp4', 'prescriptions': '/static/videos/prescriptions.mp4',
    'dashboard': '/static/videos/patient-dashboard.mp4', 'about': '/static/videos/about.mp4',
}
PAGE_BACKGROUNDS = {
    'login': '/static/images/login.jpg', 'register': '/static/images/registration.jpg', 'forgot_password': '/static/images/records.jpg',
    'patient_dashboard': '/static/images/patient-dashboard.jpg',
    'doctor_dashboard': '/static/images/doctor-dashboard.jpg', 'admin_dashboard': '/static/images/admin-dashboard.jpg',
    'appointments_page': '/static/images/appointments.jpg', 'consultation': '/static/images/consultation.jpg',
    'doctors_page': '/static/images/doctors.jpg', 'prescriptions': '/static/images/prescriptions.jpg',
    'records': '/static/images/records.jpg', 'queue': '/static/images/queue.jpg',
    'about': '/static/images/about.jpg', 'contact': '/static/images/contact.jpg',
}

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False)
    phone = db.Column(db.String(30))
    role = db.Column(db.String(20), nullable=False, default='patient')
    approval_status = db.Column(db.String(20), nullable=False, default='Approved')
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    doctor = db.relationship('Doctor', backref='user', uselist=False, cascade='all, delete-orphan')

    def set_password(self, value): self.password_hash = generate_password_hash(value)
    def check_password(self, value): return check_password_hash(self.password_hash, value)

class Doctor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    specialization = db.Column(db.String(80), nullable=False)
    qualification = db.Column(db.String(160), default='MBBS')
    experience = db.Column(db.Integer, default=5)
    bio = db.Column(db.Text, default='Compassionate care through accessible telemedicine.')
    verified = db.Column(db.Boolean, default=True)
    available = db.Column(db.Boolean, default=True)

class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    age = db.Column(db.Integer)
    gender = db.Column(db.String(40))
    address = db.Column(db.String(255))
    village = db.Column(db.String(120))
    district = db.Column(db.String(120), default='Patiala')
    blood_group = db.Column(db.String(10))
    emergency_contact = db.Column(db.String(30))
    user = db.relationship('User', backref=db.backref('patient', uselist=False))

class OTPVerification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    contact = db.Column(db.String(160), nullable=False)
    code_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    attempts = db.Column(db.Integer, default=0)
    used = db.Column(db.Boolean, default=False)

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'), nullable=False)
    scheduled_for = db.Column(db.DateTime, nullable=False)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='Pending', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    patient = db.relationship('Patient', backref='appointments')
    doctor = db.relationship('Doctor', backref='appointments')
    __table_args__ = (db.UniqueConstraint('doctor_id', 'scheduled_for', name='uq_doctor_slot'),)

class Consultation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointment.id'), unique=True, nullable=False)
    room_code = db.Column(db.String(64), unique=True, nullable=False)
    notes = db.Column(db.Text, default='')
    started_at = db.Column(db.DateTime)
    ended_at = db.Column(db.DateTime)
    appointment = db.relationship('Appointment', backref=db.backref('consultation', uselist=False))

class Prescription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointment.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    diagnosis = db.Column(db.String(255), nullable=False)
    medicines = db.Column(db.Text, nullable=False)
    dosage = db.Column(db.String(255), default='As directed')
    duration = db.Column(db.String(120), default='As advised')
    instructions = db.Column(db.Text, default='')
    follow_up_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    appointment = db.relationship('Appointment', backref='prescriptions')
    doctor = db.relationship('Doctor')
    patient = db.relationship('Patient')

class MedicalRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointment.id'))
    title = db.Column(db.String(180), nullable=False)
    summary = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    patient = db.relationship('Patient', backref='records')

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    action = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


def current_user():
    uid = session.get('user_id')
    return db.session.get(User, uid) if uid else None

@app.context_processor
def inject_globals():
    endpoint = request.endpoint or ''
    selected = PAGE_BACKGROUNDS.get(endpoint)
    return {
        'current_user': current_user(), 'video_urls': VIDEO_URLS,
        'specializations': SPECIALIZATIONS, 'page_background': selected or '/static/images/patient-dashboard.jpg',
    }

def login_required(role=None):
    def decorator(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            user = current_user()
            if not user:
                if request.path.startswith('/api/'): return jsonify(error='Authentication required'), 401
                flash('Please sign in to continue.', 'warning'); return redirect(url_for('login', next=request.path))
            if role and user.role != role:
                if request.path.startswith('/api/'): return jsonify(error='Insufficient permissions'), 403
                abort(403)
            return fn(*args, **kwargs)
        return wrapped
    return decorator

def serialize_doctor(d):
    return {'id': d.id, 'name': d.user.name, 'specialization': d.specialization, 'qualification': d.qualification, 'experience': d.experience, 'bio': d.bio, 'verified': d.verified, 'available': d.available}

def serialize_appointment(a):
    return {'id': a.id, 'doctor': a.doctor.user.name, 'patient': a.patient.user.name, 'scheduled_for': a.scheduled_for.isoformat(), 'reason': a.reason, 'status': a.status}

def seed_data():
    if User.query.count(): return
    admin = User(name='Platform Admin', email='admin@nabha-telecare.local', role='admin', password_hash=generate_password_hash('Admin@123'))
    patient_user = User(name='Harpreet Kaur', email='patient@nabha-telecare.local', phone='+91 98765 43210', role='patient', password_hash=generate_password_hash('Patient@123'))
    patient = Patient(user=patient_user, age=34, gender='Female', village='Nabha', district='Patiala', blood_group='B+', emergency_contact='+91 98765 43211')
    doctors = []
    for name, email, spec, qual, exp in [('Dr. Amandeep Singh', 'doctor@nabha-telecare.local', 'General Physician', 'MBBS, MD', 12), ('Dr. Simran Gill', 'simran@nabha-telecare.local', 'Pediatrics', 'MBBS, DCH', 8), ('Dr. Mehak Sharma', 'mehak@nabha-telecare.local', 'Dermatology', 'MBBS, DDVL', 10)]:
        u = User(name=name, email=email, role='doctor', password_hash=generate_password_hash('Doctor@123'))
        db.session.add(u); db.session.flush()
        doctors.append(Doctor(user_id=u.id, specialization=spec, qualification=qual, experience=exp))
    db.session.add_all([admin, patient_user, patient, *doctors])
    db.session.commit()

def migrate_prescription_columns():
    """Add prescription detail columns to older local SQLite databases safely."""
    columns = {col['name'] for col in inspect(db.engine).get_columns('prescription')}
    with db.engine.begin() as connection:
        if 'dosage' not in columns: connection.execute(text("ALTER TABLE prescription ADD COLUMN dosage VARCHAR(255) DEFAULT 'As directed'"))
        if 'duration' not in columns: connection.execute(text("ALTER TABLE prescription ADD COLUMN duration VARCHAR(120) DEFAULT 'As advised'"))

def migrate_admin_columns():
    columns = {col['name'] for col in inspect(db.engine).get_columns('user')}
    if 'approval_status' not in columns:
        with db.engine.begin() as connection:
            connection.execute(text("ALTER TABLE user ADD COLUMN approval_status VARCHAR(20) NOT NULL DEFAULT 'Approved'"))

@app.route('/')
def home():
    doctors = Doctor.query.filter_by(verified=True).limit(3).all()
    stats = {'patients': User.query.filter_by(role='patient').count(), 'doctors': Doctor.query.count(), 'consultations': Consultation.query.count()}
    return render_template('home.html', doctors=doctors, stats=stats)

@app.route('/doctors')
def doctors_page():
    q, spec = request.args.get('q', '').strip(), request.args.get('specialization', '')
    query = Doctor.query.join(User).filter(Doctor.verified.is_(True), Doctor.available.is_(True), User.approval_status == 'Approved')
    if q: query = query.filter(User.name.ilike(f'%{q}%'))
    if spec: query = query.filter(Doctor.specialization == spec)
    return render_template('doctors.html', doctors=query.all(), q=q, selected_spec=spec)

@app.route('/appointments', methods=['GET', 'POST'])
@login_required('patient')
def appointments_page():
    patient = current_user().patient
    if request.method == 'POST':
        try:
            doctor_id = int(request.form['doctor_id'])
            scheduled = datetime.fromisoformat(request.form['scheduled_for'])
            if scheduled < datetime.now(): raise ValueError('Choose a future time.')
            if Appointment.query.filter_by(doctor_id=doctor_id, scheduled_for=scheduled).first(): raise ValueError('That time slot is already booked.')
            a = Appointment(patient_id=patient.id, doctor_id=doctor_id, scheduled_for=scheduled, reason=request.form['reason'].strip())
            db.session.add(a); db.session.commit()
            flash('Appointment request submitted. The doctor will review it shortly.', 'success')
            return redirect(url_for('appointments_page'))
        except (ValueError, KeyError) as exc:
            db.session.rollback(); flash(str(exc), 'danger')
    return render_template('appointments.html', doctors=Doctor.query.join(User).filter(Doctor.verified.is_(True), Doctor.available.is_(True), User.approval_status == 'Approved').all(), appointments=Appointment.query.filter_by(patient_id=patient.id).order_by(Appointment.scheduled_for.desc()).all())

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip(); email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip(); dob = request.form.get('date_of_birth', '').strip()
        gender = request.form.get('gender', '').strip(); password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')
        if not name or not email or not phone or not dob or not gender or not password:
            flash('Please complete all required fields.', 'danger')
        elif not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
            flash('Enter a valid email address.', 'danger')
        elif not re.match(r'^\+?[0-9\s-]{10,16}$', phone):
            flash('Enter a valid mobile number.', 'danger')
        elif password != confirm:
            flash('Passwords do not match.', 'danger')
        elif len(password) < 8:
            flash('Password must be at least 8 characters.', 'danger')
        elif User.query.filter_by(email=email).first():
            flash('An account with this email already exists. Please log in.', 'danger')
        else:
            try:
                birth_date = datetime.strptime(dob, '%Y-%m-%d').date()
                today = datetime.utcnow().date(); age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
                if age < 0 or age > 120: raise ValueError
                user = User(name=name, email=email, phone=phone, role='patient', approval_status='Pending', password_hash=generate_password_hash(password))
                db.session.add(user); db.session.flush(); db.session.add(Patient(user_id=user.id, age=age, gender=gender, district='Patiala'))
                db.session.commit(); flash('Your account has been created. Please log in.', 'success'); return redirect(url_for('login', role='patient'))
            except ValueError:
                db.session.rollback(); flash('Enter a valid date of birth.', 'danger')
    return render_template('register.html')

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    development_otp = None; step = request.form.get('step', 'request')
    if request.method == 'POST' and step == 'request':
        email = request.form.get('email', '').strip().lower(); user = User.query.filter_by(email=email).first()
        if not user:
            flash('We could not find that account. Please create an account to continue.', 'warning')
        else:
            code = f'{random.randint(0, 999999):06d}'; db.session.add(OTPVerification(contact=email, role=user.role, code_hash=generate_password_hash(code), expires_at=datetime.utcnow()+timedelta(minutes=5))); db.session.commit()
            session['reset_contact'] = email; session['reset_role'] = user.role; step = 'reset'
            if app.config['OTP_MODE'] == 'development': development_otp = code
            flash('Enter the verification code and choose a new password.', 'info')
    elif request.method == 'POST' and step == 'reset':
        email = session.get('reset_contact'); role = session.get('reset_role'); code = request.form.get('code', '')
        new_password = request.form.get('new_password', ''); confirm = request.form.get('confirm_password', '')
        otp = OTPVerification.query.filter_by(contact=email, role=role, used=False).order_by(OTPVerification.id.desc()).first()
        if not otp or otp.expires_at < datetime.utcnow() or not check_password_hash(otp.code_hash, code): flash('That verification code is invalid or expired.', 'danger'); step = 'reset'
        elif len(new_password) < 8: flash('Password must be at least 8 characters.', 'danger'); step = 'reset'
        elif new_password != confirm: flash('Passwords do not match.', 'danger'); step = 'reset'
        else:
            user = User.query.filter_by(email=email, role=role).first(); user.password_hash = generate_password_hash(new_password); otp.used = True; db.session.commit(); session.pop('reset_contact', None); session.pop('reset_role', None); flash('Your password has been reset successfully. Please log in.', 'success'); return redirect(url_for('login', role=role))
    return render_template('forgot_password.html', step=step, development_otp=development_otp)

@app.route('/consult-remotely', methods=['GET', 'POST'])
@login_required('patient')
def consult_remotely():
    patient = current_user().patient
    if request.method == 'POST':
        doctor = db.session.get(Doctor, request.form.get('doctor_id'))
        reason = request.form.get('reason', '').strip()
        if not doctor or not doctor.available: flash('That doctor is not currently available for remote consultation.', 'warning')
        elif not reason: flash('Please describe the reason for your consultation.', 'danger')
        else:
            scheduled = (datetime.now() + timedelta(hours=1)).replace(second=0, microsecond=0)
            while Appointment.query.filter_by(doctor_id=doctor.id, scheduled_for=scheduled).first(): scheduled += timedelta(minutes=15)
            db.session.add(Appointment(patient_id=patient.id, doctor_id=doctor.id, scheduled_for=scheduled, reason='Remote consultation: '+reason, status='Pending')); db.session.commit(); flash('Remote consultation request sent to the doctor.', 'success'); return redirect(url_for('consult_remotely'))
    return render_template('consult_remotely.html', doctors=Doctor.query.join(User).filter(Doctor.verified.is_(True), Doctor.available.is_(True), User.approval_status == 'Approved').all(), appointments=Appointment.query.filter_by(patient_id=patient.id).filter(Appointment.reason.like('Remote consultation:%')).order_by(Appointment.created_at.desc()).all())

@app.route('/role-selection')
def role_selection():
    return render_template('role_selection.html')

@app.route('/login', methods=['GET', 'POST'])
@app.route('/login/<role>', methods=['GET', 'POST'])
def login(role=None):
    if request.method == 'GET' and role not in {'patient', 'doctor', 'admin'}:
        return redirect(url_for('role_selection'))
    if request.method == 'POST':
        identifier, password, selected_role = request.form.get('identifier', '').strip(), request.form.get('password', ''), role or request.form.get('role', 'patient')
        if selected_role not in {'patient', 'doctor', 'admin'}: return redirect(url_for('role_selection'))
        user = User.query.filter((User.email == identifier) | (User.phone == identifier)).first()
        if not user:
            flash('Account not found. Please create an account to continue.', 'danger')
        elif user.role != selected_role:
            flash('This account uses a different role. Please return to role selection.', 'danger')
        elif user.approval_status != 'Approved':
            flash('This account is awaiting admin approval or has been rejected.', 'warning')
        elif user.check_password(password):
            session['user_id'] = user.id; flash(f'Welcome back, {user.name.split()[0]}.', 'success')
            return redirect(url_for({'patient':'patient_dashboard','doctor':'doctor_dashboard','admin':'admin_dashboard'}[selected_role]))
        else:
            flash('Incorrect password. Please try again or use Forgot Password.', 'danger')
    return render_template('login.html', selected_role=role or request.form.get('role', 'patient'))

@app.route('/logout')
def logout(): session.clear(); flash('You have been signed out.', 'info'); return redirect(url_for('role_selection'))

@app.route('/patient/dashboard')
@login_required('patient')
def patient_dashboard():
    p = current_user().patient
    return render_template('dashboard.html', mode='patient', patient=p, appointments=Appointment.query.filter_by(patient_id=p.id).order_by(Appointment.scheduled_for.desc()).limit(5).all(), prescriptions=Prescription.query.filter_by(patient_id=p.id).order_by(Prescription.created_at.desc()).limit(5).all(), records=MedicalRecord.query.filter_by(patient_id=p.id).order_by(MedicalRecord.created_at.desc()).all())

@app.route('/doctor/dashboard')
@login_required('doctor')
def doctor_dashboard():
    d = current_user().doctor
    return render_template('dashboard.html', mode='doctor', doctor=d, appointments=Appointment.query.filter_by(doctor_id=d.id).order_by(Appointment.scheduled_for.desc()).all())

@app.route('/admin/dashboard')
@login_required('admin')
def admin_dashboard():
    return render_template('dashboard.html', mode='admin', stats={'patients': User.query.filter_by(role='patient').count(), 'doctors': Doctor.query.count(), 'appointments': Appointment.query.count(), 'pending': Appointment.query.filter_by(status='Pending').count()})

@app.route('/admin/overview')
@login_required('admin')
def admin_overview():
    return render_template('admin_overview.html', stats={
        'patients': User.query.filter_by(role='patient').count(),
        'pending_patients': User.query.filter_by(role='patient', approval_status='Pending').count(),
        'doctors': Doctor.query.count(),
        'pending_doctors': Doctor.query.filter_by(verified=False).count(),
        'appointments': Appointment.query.count(),
        'pending_appointments': Appointment.query.filter_by(status='Pending').count(),
        'completed_appointments': Appointment.query.filter_by(status='Completed').count(),
    })

@app.route('/admin/pending-patients')
@login_required('admin')
def admin_pending_patients():
    patients = User.query.filter_by(role='patient', approval_status='Pending').order_by(User.created_at.desc()).all()
    return render_template('admin_patients.html', patients=patients, view='pending')

@app.route('/admin/patients/<int:user_id>')
@login_required('admin')
def admin_patient_detail(user_id):
    patient = User.query.filter_by(id=user_id, role='patient').first_or_404()
    return render_template('admin_patient_detail.html', patient=patient)

@app.post('/admin/patients/<int:user_id>/approve')
@login_required('admin')
def approve_patient(user_id):
    patient = User.query.filter_by(id=user_id, role='patient').first_or_404(); patient.approval_status = 'Approved'; db.session.commit(); flash('Patient approved successfully.', 'success'); return redirect(url_for('admin_pending_patients'))

@app.post('/admin/patients/<int:user_id>/reject')
@login_required('admin')
def reject_patient(user_id):
    patient = User.query.filter_by(id=user_id, role='patient').first_or_404(); patient.approval_status = 'Rejected'; db.session.commit(); flash('Patient rejected. The account remains stored but cannot sign in.', 'warning'); return redirect(url_for('admin_pending_patients'))

@app.route('/admin/doctors')
@login_required('admin')
def admin_doctors():
    query = Doctor.query.join(User).order_by(User.created_at.desc())
    search = request.args.get('q', '').strip()
    if search: query = query.filter((User.name.ilike(f'%{search}%')) | (User.email.ilike(f'%{search}%')))
    return render_template('admin_doctors.html', doctors=query.all(), search=search)

@app.route('/admin/doctors/<int:doctor_id>')
@login_required('admin')
def admin_doctor_detail(doctor_id):
    doctor = db.session.get(Doctor, doctor_id) or abort(404)
    return render_template('admin_doctor_detail.html', doctor=doctor)

@app.post('/admin/doctors/<int:doctor_id>/approve')
@login_required('admin')
def approve_doctor(doctor_id):
    doctor = db.session.get(Doctor, doctor_id) or abort(404); doctor.verified = True; doctor.user.approval_status = 'Approved'; db.session.commit(); flash('Doctor approved and made eligible for booking.', 'success'); return redirect(url_for('admin_doctors'))

@app.post('/admin/doctors/<int:doctor_id>/reject')
@login_required('admin')
def reject_doctor(doctor_id):
    doctor = db.session.get(Doctor, doctor_id) or abort(404); doctor.verified = False; doctor.available = False; doctor.user.approval_status = 'Rejected'; db.session.commit(); flash('Doctor rejected and removed from booking.', 'warning'); return redirect(url_for('admin_doctors'))

@app.post('/admin/doctors/<int:doctor_id>/toggle')
@login_required('admin')
def toggle_doctor(doctor_id):
    doctor = db.session.get(Doctor, doctor_id) or abort(404); doctor.available = not doctor.available; db.session.commit(); flash(f'Doctor is now {"active" if doctor.available else "inactive"}.', 'success'); return redirect(url_for('admin_doctors'))

@app.route('/admin/appointments')
@login_required('admin')
def admin_appointments():
    selected_status = request.args.get('status', 'All')
    query = Appointment.query.order_by(Appointment.scheduled_for.desc())
    actual_status = 'Confirmed' if selected_status == 'Approved' else selected_status
    if actual_status != 'All': query = query.filter_by(status=actual_status)
    return render_template('admin_appointments.html', appointments=query.all(), selected_status=selected_status)

@app.post('/admin/appointments/<int:appointment_id>/status')
@login_required('admin')
def admin_appointment_status(appointment_id):
    appointment = db.session.get(Appointment, appointment_id) or abort(404); status = request.form.get('status', '')
    if status not in {'Pending', 'Confirmed', 'Completed', 'Cancelled', 'Rejected'}: flash('Invalid appointment status.', 'danger')
    else: appointment.status = status; db.session.commit(); flash('Appointment status updated.', 'success')
    return redirect(url_for('admin_appointments'))

@app.route('/admin/records')
@login_required('admin')
def admin_records():
    records = MedicalRecord.query.order_by(MedicalRecord.created_at.desc()).all()
    return render_template('admin_records.html', records=records)

@app.route('/consultation/<int:appointment_id>')
@login_required()
def consultation(appointment_id):
    a = db.session.get(Appointment, appointment_id)
    user = current_user()
    if not a or (user.role == 'patient' and a.patient.user_id != user.id) or (user.role == 'doctor' and a.doctor.user_id != user.id): abort(403)
    if a.status != 'Confirmed': flash('The doctor must confirm this appointment before joining.', 'warning'); return redirect(url_for('patient_dashboard' if user.role == 'patient' else 'doctor_dashboard'))
    if not a.consultation:
        a.consultation = Consultation(room_code=secrets.token_urlsafe(12), started_at=datetime.utcnow()); db.session.commit()
    return render_template('consultation.html', appointment=a)

@app.route('/prescriptions', methods=['GET', 'POST'])
@login_required()
def prescriptions_page():
    user = current_user()
    if request.method == 'POST':
        if user.role != 'doctor': abort(403)
        appointment = db.session.get(Appointment, request.form.get('appointment_id'))
        if not appointment or appointment.doctor.user_id != user.id: abort(403)
        diagnosis = request.form.get('diagnosis', '').strip(); medicines = request.form.get('medicines', '').strip()
        if not diagnosis or not medicines:
            flash('Diagnosis and prescribed medicines are required.', 'danger')
        else:
            follow_up = request.form.get('follow_up_date', '').strip() or None
            prescription = Prescription(appointment_id=appointment.id, doctor_id=appointment.doctor_id, patient_id=appointment.patient_id, diagnosis=diagnosis, medicines=medicines, dosage=request.form.get('dosage', '').strip() or 'As directed', duration=request.form.get('duration', '').strip() or 'As advised', instructions=request.form.get('instructions', '').strip(), follow_up_date=datetime.strptime(follow_up, '%Y-%m-%d').date() if follow_up else None)
            db.session.add(prescription); db.session.commit(); flash('Prescription saved successfully.', 'success'); return redirect(url_for('prescriptions_page'))
    if user.role == 'patient':
        prescriptions = Prescription.query.filter_by(patient_id=user.patient.id).order_by(Prescription.created_at.desc()).all()
        return render_template('prescriptions.html', prescriptions=prescriptions, mode='patient', appointments=[])
    if user.role == 'doctor':
        doctor = user.doctor; prescriptions = Prescription.query.filter_by(doctor_id=doctor.id).order_by(Prescription.created_at.desc()).all()
        appointments = Appointment.query.filter_by(doctor_id=doctor.id).order_by(Appointment.scheduled_for.desc()).all()
        return render_template('prescriptions.html', prescriptions=prescriptions, mode='doctor', appointments=appointments)
    abort(403)

@app.route('/prescriptions/<int:prescription_id>/edit', methods=['GET', 'POST'])
@login_required('doctor')
def edit_prescription(prescription_id):
    prescription = db.session.get(Prescription, prescription_id)
    if not prescription or prescription.doctor.user_id != current_user().id: abort(403)
    if request.method == 'POST':
        prescription.diagnosis = request.form.get('diagnosis', '').strip(); prescription.medicines = request.form.get('medicines', '').strip(); prescription.dosage = request.form.get('dosage', '').strip() or 'As directed'; prescription.duration = request.form.get('duration', '').strip() or 'As advised'; prescription.instructions = request.form.get('instructions', '').strip(); follow_up = request.form.get('follow_up_date', '').strip(); prescription.follow_up_date = datetime.strptime(follow_up, '%Y-%m-%d').date() if follow_up else None
        if not prescription.diagnosis or not prescription.medicines: flash('Diagnosis and prescribed medicines are required.', 'danger')
        else: db.session.commit(); flash('Prescription updated successfully.', 'success'); return redirect(url_for('prescriptions_page'))
    return render_template('prescription_form.html', prescription=prescription, appointment=prescription.appointment, editing=True)

@app.route('/prescription/<int:prescription_id>/pdf')
@login_required()
def prescription_pdf(prescription_id):
    p = db.session.get(Prescription, prescription_id); user = current_user()
    if not p or (user.role == 'patient' and p.patient.user_id != user.id) or (user.role == 'doctor' and p.doctor.user_id != user.id): abort(403)
    stream = io.BytesIO(); pdf = canvas.Canvas(stream, pagesize=A4); pdf.setTitle('Nabha TeleCare Prescription')
    pdf.setFont('Helvetica-Bold', 18); pdf.drawString(54, 790, 'Nabha TeleCare')
    pdf.setFont('Helvetica', 10); pdf.drawString(54, 772, 'Digital Prescription | Rural healthcare access for Nabha')
    y = 730
    for label, value in [('Prescription ID', p.id), ('Patient', f'{p.patient.user.name} (ID: {p.patient.id})'), ('Doctor', p.doctor.user.name), ('Date', p.created_at.strftime('%d %b %Y')), ('Diagnosis', p.diagnosis), ('Medicines', p.medicines), ('Dosage', p.dosage or 'As directed'), ('Duration', p.duration or 'As advised'), ('Instructions', p.instructions), ('Follow-up', p.follow_up_date.strftime('%d %b %Y') if p.follow_up_date else 'As advised')]:
        pdf.setFont('Helvetica-Bold', 11); pdf.drawString(54, y, label + ':'); pdf.setFont('Helvetica', 11)
        text = pdf.beginText(145, y); text.textLines(str(value)); pdf.drawText(text); y -= 34
    pdf.setFont('Helvetica-Oblique', 9); pdf.drawString(54, 54, 'This document is for the named patient. Follow your doctor\'s instructions.')
    pdf.save(); stream.seek(0); return send_file(stream, as_attachment=True, download_name=f'prescription-{p.id}.pdf', mimetype='application/pdf')

@app.route('/api/auth/request-otp', methods=['POST'])
def request_otp():
    data = request.get_json(silent=True) or request.form
    contact, role = (data.get('contact') or '').strip(), data.get('role', 'patient')
    user = User.query.filter((User.email == contact) | (User.phone == contact)).filter_by(role=role).first()
    if not user: return jsonify(error='No matching account found for that role.'), 404
    code = f'{random.randint(0, 999999):06d}'
    otp = OTPVerification(contact=contact, role=role, code_hash=generate_password_hash(code), expires_at=datetime.utcnow()+timedelta(minutes=5))
    db.session.add(otp); db.session.commit()
    response = {'message': 'OTP generated in development mode.' if app.config['OTP_MODE'] == 'development' else 'OTP delivery requested.', 'expires_in': 300}
    if app.config['OTP_MODE'] == 'development': response['development_otp'] = code
    return jsonify(response)

@app.route('/api/auth/verify-otp', methods=['POST'])
def verify_otp():
    data = request.get_json(silent=True) or request.form
    otp = OTPVerification.query.filter_by(contact=data.get('contact'), role=data.get('role'), used=False).order_by(OTPVerification.id.desc()).first()
    if not otp or otp.expires_at < datetime.utcnow() or otp.attempts >= 5: return jsonify(error='OTP expired or invalid.'), 400
    otp.attempts += 1
    if not check_password_hash(otp.code_hash, data.get('code', '')): db.session.commit(); return jsonify(error='Incorrect OTP.'), 400
    user = User.query.filter((User.email == otp.contact) | (User.phone == otp.contact)).filter_by(role=otp.role).first(); otp.used = True; db.session.commit(); session['user_id'] = user.id
    return jsonify(message='Verified', redirect=url_for({'patient':'patient_dashboard','doctor':'doctor_dashboard','admin':'admin_dashboard'}[user.role]))

@app.route('/api/doctors')
def doctors_api(): return jsonify(doctors=[serialize_doctor(d) for d in Doctor.query.filter_by(verified=True).all()])

@app.route('/api/appointments', methods=['GET', 'POST'])
@login_required('patient')
def appointments_api():
    patient = current_user().patient
    if request.method == 'GET': return jsonify(appointments=[serialize_appointment(a) for a in patient.appointments])
    data = request.get_json() or {}
    try: scheduled = datetime.fromisoformat(data['scheduled_for'])
    except (KeyError, ValueError): return jsonify(error='scheduled_for must be ISO datetime'), 400
    if Appointment.query.filter_by(doctor_id=int(data['doctor_id']), scheduled_for=scheduled).first(): return jsonify(error='That time slot is already booked.'), 409
    a = Appointment(patient_id=patient.id, doctor_id=int(data['doctor_id']), scheduled_for=scheduled, reason=data.get('reason', '').strip())
    if not a.reason: return jsonify(error='Reason is required.'), 400
    db.session.add(a); db.session.commit(); return jsonify(appointment=serialize_appointment(a)), 201

@app.route('/api/appointments/<int:appointment_id>/<action>', methods=['POST'])
@login_required()
def appointment_action(appointment_id, action):
    a = db.session.get(Appointment, appointment_id); user = current_user()
    if not a: return jsonify(error='Appointment not found'), 404
    if user.role == 'doctor' and a.doctor.user_id == user.id and action in {'confirm', 'reject', 'complete'}: a.status = {'confirm':'Confirmed','reject':'Rejected','complete':'Completed'}[action]
    elif user.role == 'patient' and a.patient.user_id == user.id and action == 'cancel': a.status = 'Cancelled'
    else: return jsonify(error='Not authorized'), 403
    db.session.commit(); return jsonify(appointment=serialize_appointment(a))

@app.route('/api/consultations/<int:appointment_id>/notes', methods=['POST'])
@login_required()
def consultation_notes(appointment_id):
    a = db.session.get(Appointment, appointment_id); user = current_user()
    if not a or not a.consultation: return jsonify(error='Consultation not found'), 404
    if user.role != 'doctor' or a.doctor.user_id != user.id: return jsonify(error='Doctor access required'), 403
    a.consultation.notes = (request.get_json() or {}).get('notes', '')[:5000]; db.session.commit(); return jsonify(message='Notes saved')

@app.route('/api/prescriptions', methods=['POST'])
@login_required('doctor')
def create_prescription():
    data = request.get_json() or {}; a = db.session.get(Appointment, data.get('appointment_id'))
    if not a or a.doctor.user_id != current_user().id: return jsonify(error='Authorized appointment required'), 403
    p = Prescription(appointment_id=a.id, doctor_id=a.doctor_id, patient_id=a.patient_id, diagnosis=data.get('diagnosis','').strip(), medicines=data.get('medicines','').strip(), instructions=data.get('instructions','').strip())
    if not p.diagnosis or not p.medicines: return jsonify(error='Diagnosis and medicines are required'), 400
    db.session.add(p); db.session.commit(); return jsonify(id=p.id), 201

@app.route('/api/admin/stats')
@login_required('admin')
def admin_stats(): return jsonify(patients=User.query.filter_by(role='patient').count(), doctors=Doctor.query.count(), appointments=Appointment.query.count(), pending=Appointment.query.filter_by(status='Pending').count())

with app.app_context():
    db.create_all(); migrate_prescription_columns(); migrate_admin_columns(); seed_data()

@app.before_request
def ensure_database_ready():
    db.create_all()
    migrate_prescription_columns()
    migrate_admin_columns()
    if not User.query.first():
        seed_data()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=os.getenv('FLASK_DEBUG', '0') == '1', use_reloader=False)
