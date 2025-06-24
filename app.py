import os
import json
from flask import Flask, render_template, redirect, url_for, flash, request
from werkzeug.utils import secure_filename
from config import Config
from models import db, User, Equipment, Booking 
# --- Import login_required and the new form ---
from flask_login import LoginManager, current_user, login_user, logout_user, login_required
from forms import LoginForm, RegistrationForm, EquipmentForm, RentalRequestForm, UniversityApprovalForm
from authlib.integrations.flask_client import OAuth

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# --- Login Manager Setup ---
login = LoginManager(app)
login.login_view = 'login' # Redirect users to the 'login' page if they try to access a protected page

@login.user_loader
def load_user(id):
    return User.query.get(int(id))

# --- OAuth (Google Sign-In) Setup ---
oauth = OAuth(app)
oauth.register(
    name='google',
    client_id=app.config['GOOGLE_CLIENT_ID'],
    client_secret=app.config['GOOGLE_CLIENT_SECRET'],
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)
# -----------------------------------

# --- Routes ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/threads')
def threads():
    return render_template('threads.html', title='Threads')

@app.route('/about')
def about():
    return render_template('about.html', title='About Us')

# LIGO-new/app.py

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        # If already logged in, redirect them to their respective home page
        if current_user.is_university:
            return redirect(url_for('my_equipment'))
        else:
            return redirect(url_for('index'))
            
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('Invalid email or password')
            return redirect(url_for('login'))
        login_user(user, remember=form.remember_me.data)
        
        # --- ADD THIS LOGIC ---
        # Check if the user is a university and redirect accordingly
        if user.is_university:
            flash(f'Welcome, {user.username}!')
            return redirect(url_for('my_equipment'))
        else:
            flash(f'Welcome back, {user.username}!')
            return redirect(url_for('index'))
            
    return render_template('login.html', title='Sign In', form=form)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        if form.user_type.data == 'university':
            user.is_university = True
        db.session.add(user)
        db.session.commit()
        flash('Congratulations, you are now a registered user!')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)

@app.route('/google/login')
def google_login():
    # Redirect to Google's authorization page
    return oauth.google.authorize_redirect(url_for('google_callback', _external=True))

# In app.py

# LIGO-new/app.py

@app.route('/google/callback')
def google_callback():
    token = oauth.google.authorize_access_token()
    user_info = token.get('userinfo')
    
    if user_info:
        user = User.query.filter_by(email=user_info['email']).first()
        if not user:
            # Note: You may want a separate process for universities to register via Google
            # For now, we assume they are regular users if they don't exist
            user = User(
                username=user_info['name'],
                email=user_info['email'],
                is_university=False # Default to False
            )
            db.session.add(user)
            db.session.commit()
        
        login_user(user)
        flash(f'Successfully logged in with Google, {user.username}!')
        
        # --- ADD THIS LOGIC ---
        if user.is_university:
            return redirect(url_for('my_equipment'))
        else:
            return redirect(url_for('index'))

    flash('Google Sign-In failed.')
    return redirect(url_for('login'))

@app.route('/register_equipment', methods=['GET', 'POST'])
@login_required
def register_equipment():
    # Only allow universities to access this page
    if not current_user.is_university:
        flash('Only university accounts can list equipment.')
        return redirect(url_for('index'))

    form = EquipmentForm()
    if form.validate_on_submit():
        new_equipment = Equipment(
            name=form.name.data,
            category=form.category.data,
            description=form.description.data,
            model_number=form.model_number.data,
            manufacturer=form.manufacturer.data,
            safety_requirements=form.safety_requirements.data,
            cost_onsite=form.cost_onsite.data,
            cost_remote=form.cost_remote.data,
            university_id=current_user.id
        )

        # --- File Upload Handling ---
        upload_folder = app.config['UPLOAD_FOLDER']

        # Helper function to save a file
        def save_file(file_field, prefix):
            if file_field and file_field.data:
                filename = secure_filename(file_field.data.filename)
                # Add a prefix to avoid name collisions
                unique_filename = f"{prefix}_{current_user.id}_{filename}"
                file_path = os.path.join(upload_folder, unique_filename)
                file_field.data.save(file_path)
                return unique_filename
            return None

        new_equipment.primary_image_filename = save_file(form.primary_image, 'primary')
        new_equipment.tech_specs_pdf_filename = save_file(form.tech_specs_pdf, 'specs')
        new_equipment.instruction_manual_pdf_filename = save_file(form.instruction_manual_pdf, 'manual')
        new_equipment.terms_pdf_filename = save_file(form.terms_pdf, 'terms')

        # Handle multiple secondary images
        if form.secondary_images.data:
            sec_filenames = []
            for i, image_file in enumerate(form.secondary_images.data):
                if image_file:
                    filename = secure_filename(image_file.filename)
                    unique_filename = f"secondary_{current_user.id}_{i}_{filename}"
                    image_file.save(os.path.join(upload_folder, unique_filename))
                    sec_filenames.append(unique_filename)
            new_equipment.secondary_images_filenames = json.dumps(sec_filenames)

        db.session.add(new_equipment)
        db.session.commit()
        flash('Your equipment has been listed successfully!')
        return redirect(url_for('market'))

    return render_template('equip_regis.html', title='Register Equipment', form=form)



@app.route('/equipment/<int:equipment_id>')
def equipment_info(equipment_id):
    equipment = Equipment.query.get_or_404(equipment_id)
    # The secondary images are stored as a JSON string, so we need to load it
    secondary_images = []
    if equipment.secondary_images_filenames:
        secondary_images = json.loads(equipment.secondary_images_filenames)
        
    return render_template('equip_info.html', title=equipment.name, equipment=equipment, secondary_images=secondary_images)

@app.route('/market')
def market():
    all_equipment = Equipment.query.all()
    return render_template('market.html', title='Marketplace', equipment_list=all_equipment)
    
@app.route('/my_equipment')
@login_required
def my_equipment():
    if not current_user.is_university:
        flash('This page is for university accounts only.')
        return redirect(url_for('index'))
    
    # Fetch equipment listed by the currently logged-in university
    university_equipment = Equipment.query.filter_by(university_id=current_user.id).all()
    bookings = Booking.query.join(Equipment).filter(Equipment.university_id == current_user.id).order_by(Booking.created_at.desc()).all()
    return render_template('equip_list.html', title='My Equipment', equipment_list=university_equipment, bookings=bookings)

@app.route('/equipment/<int:equipment_id>/request', methods=['GET', 'POST'])
@login_required
def request_equipment(equipment_id):
    equipment = Equipment.query.get_or_404(equipment_id)
    form = RentalRequestForm()

    if form.validate_on_submit():
        # Create a new booking record
        new_booking = Booking(
            user_id=current_user.id,
            equipment_id=equipment.id,
            experiment_description=form.experiment_description.data,
            samples_list=form.samples_list.data
        )
        db.session.add(new_booking)
        db.session.commit()
        
        flash('Your request has been sent to the university!')
        # This will eventually redirect to a page for Step 3 (Processing)
        return redirect(url_for('equipment_info', equipment_id=equipment.id))
        
    # We will use purchase.html for this page
    return render_template('purchase.html', title='Request Equipment', form=form, equipment=equipment)

@app.route('/booking/<int:booking_id>/manage', methods=['GET', 'POST'])
@login_required
def manage_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    # Security check: ensure the current user is the university that owns the equipment
    if not current_user.is_university or booking.equipment.university_id != current_user.id:
        flash('You do not have permission to manage this booking.')
        return redirect(url_for('my_equipment'))

    form = UniversityApprovalForm()
    if form.validate_on_submit():
        booking.status = form.status.data
        if form.final_cost.data is not None:
            booking.final_cost = form.final_cost.data
        if form.university_notes.data:
            booking.university_notes = form.university_notes.data
        
        db.session.commit()
        flash('Booking has been updated successfully.')
        return redirect(url_for('my_equipment'))

    # Pre-populate form on GET request
    form.university_notes.data = booking.university_notes
    form.final_cost.data = booking.final_cost

    return render_template('manage_booking.html', title='Manage Booking', form=form, booking=booking)

@app.route('/my_orders')
@login_required
def my_orders():
    # This route is now only for regular users to see their own requests.
    if current_user.is_university:
        # Redirect universities to their main dashboard if they land here
        return redirect(url_for('my_equipment'))

    bookings = Booking.query.filter_by(user_id=current_user.id).order_by(Booking.created_at.desc()).all()
    return render_template('user_orders.html', title="My Requests", bookings=bookings)

# This part is needed to create the database file and tables from your models.
# It runs only when you execute 'python app.py' directly.
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)