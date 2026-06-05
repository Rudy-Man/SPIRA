import os
import json

# Load .env for local development (no-op in production where env vars are set directly)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
from datetime import date, timedelta
from flask import Flask, render_template, redirect, url_for, flash, request, session
from sqlalchemy import or_, func, text, inspect
import math
from werkzeug.utils import secure_filename
from config import Config
from models import db, User, Equipment, Booking, Rating, ReviewReply, EquipmentBlockedDate, calculate_average_rating, update_equipment_rating_cache, get_blocked_dates, get_booking_blocked_dates, get_manual_closed_dates
from flask_login import LoginManager, current_user, login_user, logout_user, login_required
from forms import (
    LoginForm,
    RegistrationForm,
    EquipmentForm,
    RentalRequestForm,
    UniversityApprovalForm,
    ReviewForm,
    DeleteReviewForm,
    ReviewReplyForm,
    DeleteReplyForm,
    ManageAvailabilityForm,
    RemoveBlockedDateForm,
)
from authlib.integrations.flask_client import OAuth
from flask_wtf.csrf import generate_csrf

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

# --- Profile context processor ---
@app.context_processor
def inject_profile_data():
    if not current_user.is_authenticated:
        return {}
    try:
        if current_user.is_university:
            eq_ids = [r[0] for r in Equipment.query.filter_by(university_id=current_user.id).with_entities(Equipment.id).all()]
            equipment_count = len(eq_ids)
            total_bookings = Booking.query.filter(Booking.equipment_id.in_(eq_ids)).count() if eq_ids else 0
            approved_bookings = Booking.query.filter(Booking.equipment_id.in_(eq_ids), Booking.status == 'Approved').count() if eq_ids else 0
            recent_bookings = (Booking.query.filter(Booking.equipment_id.in_(eq_ids))
                               .order_by(Booking.created_at.desc()).limit(3).all()) if eq_ids else []
            return dict(profile_data={
                'equipment_count': equipment_count,
                'total_bookings': total_bookings,
                'approved_bookings': approved_bookings,
                'recent_bookings': recent_bookings,
            })
        else:
            total_requests = Booking.query.filter_by(user_id=current_user.id).count()
            approved_requests = Booking.query.filter_by(user_id=current_user.id, status='Approved').count()
            recent_requests = (Booking.query.filter_by(user_id=current_user.id)
                               .order_by(Booking.created_at.desc()).limit(3).all())
            return dict(profile_data={
                'total_requests': total_requests,
                'approved_requests': approved_requests,
                'recent_requests': recent_requests,
            })
    except Exception:
        return {}

# --- Routes ---
@app.route('/')
def index():
    # Fetch some equipment for display on the homepage.  Adjust the number as needed.
    equipment_list = Equipment.query.limit(4).all()  
    return render_template('index.html', equipment_list=equipment_list)

@app.route('/about')
def about():
    return render_template('about.html', title='About Us')

# LIGO-new/app.py

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.is_university:
            return redirect(url_for('my_equipment'))
        return redirect(url_for('index'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user is None or not user.check_password(form.password.data):
            form.password.errors.append('Invalid email or password.')
            return render_template('login.html', title='Sign In', form=form)

        login_user(user, remember=form.remember_me.data)
        flash('Signed in successfully.', 'success')
        if user.is_university:
            return redirect(url_for('my_equipment'))
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
        flash('Congratulations, you are now a registered user!', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)

@app.route('/google/login')
def google_login():
    user_type = request.args.get('user_type', 'user')
    session['google_user_type'] = user_type
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
            google_user_type = session.pop('google_user_type', 'user')
            user = User(
                username=user_info['name'],
                email=user_info['email'],
                is_university=(google_user_type == 'university')
            )
            db.session.add(user)
            db.session.commit()
        
        login_user(user)
        flash('Signed in successfully with Google.', 'success')
        
        # --- ADD THIS LOGIC ---
        if user.is_university:
            return redirect(url_for('my_equipment'))
        else:
            return redirect(url_for('index'))

    flash('Google Sign-In failed.', 'error')
    return redirect(url_for('login'))

@app.route('/register_equipment', methods=['GET', 'POST'])
@login_required
def register_equipment():
    # Only allow universities to access this page
    if not current_user.is_university:
        flash('Only university accounts can list equipment.', 'warning')
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

        new_equipment.available_days = ','.join(form.available_days.data) if form.available_days.data else '0,1,2,3,4'

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
        flash('Your equipment has been listed successfully!', 'success')
        return redirect(url_for('market'))

    return render_template('equip_regis.html', title='Register Equipment', form=form)



def _get_secondary_images(equipment):
    secondary_images = []
    if equipment.secondary_images_filenames:
        if isinstance(equipment.secondary_images_filenames, str):
            secondary_images = json.loads(equipment.secondary_images_filenames)
        else:
            secondary_images = equipment.secondary_images_filenames
    return secondary_images


def _gather_equipment_page_context(equipment, review_form=None, edit_review_id=None):
    secondary_images = _get_secondary_images(equipment)
    reviews = Rating.query.filter_by(equipment_id=equipment.id).order_by(Rating.created_at.desc()).all()
    ratings_count = len(reviews)
    avg_rating = round(sum(review.rating for review in reviews) / ratings_count, 1) if ratings_count else 0
    star_width = (avg_rating / 5) * 100 if ratings_count else 0

    if review_form is None and current_user.is_authenticated and not current_user.is_university:
        review_form = ReviewForm()

    target_review = None
    if edit_review_id and current_user.is_authenticated:
        target_review = next((r for r in reviews if r.id == edit_review_id and r.user_id == current_user.id), None)
        if target_review:
            if review_form is None:
                review_form = ReviewForm()
            review_form.review_id.data = str(target_review.id)
            review_form.rating.data = target_review.rating
            review_form.comment.data = target_review.comment or ''

    user_reviews = []
    if current_user.is_authenticated:
        user_reviews = [review for review in reviews if review.user_id == current_user.id]

    delete_review_forms = {
        review.id: DeleteReviewForm(review_id=str(review.id))
        for review in reviews
    }

    available_days = [int(d) for d in (equipment.available_days or '0,1,2,3,4').split(',') if d.strip()]
    booked_dates = get_booking_blocked_dates(equipment.id)
    manual_closed_dates = get_manual_closed_dates(equipment.id)

    return dict(
        title=equipment.name,
        equipment=equipment,
        secondary_images=secondary_images,
        reviews=reviews,
        ratings_count=ratings_count,
        avg_rating=avg_rating,
        star_width=star_width,
        review_form=review_form,
        edit_review_id=target_review.id if target_review else None,
        user_reviews=user_reviews,
        delete_review_forms=delete_review_forms,
        available_days=available_days,
        booked_dates=booked_dates,
        manual_closed_dates=manual_closed_dates,
    )


@app.route('/equipment/<int:equipment_id>')
def equipment_info(equipment_id):
    equipment = Equipment.query.get_or_404(equipment_id)
    edit_review_id = request.args.get('edit_review_id', type=int)
    context = _gather_equipment_page_context(equipment, edit_review_id=edit_review_id)
    return render_template('equip_info.html', **context)


@app.route('/equipment/<int:equipment_id>/reviews', methods=['POST'])
@login_required
def submit_review(equipment_id):
    equipment = Equipment.query.get_or_404(equipment_id)
    if current_user.is_university:
        flash("Universities can't rate their own equipment.", 'warning')
        return redirect(url_for('equipment_info', equipment_id=equipment_id))

    form = ReviewForm()
    if form.validate_on_submit():
        review_id = form.review_id.data
        review = None
        if review_id:
            try:
                review_id = int(review_id)
            except (TypeError, ValueError):
                review_id = None

        if review_id:
            review = Rating.query.filter_by(
                id=review_id,
                equipment_id=equipment.id,
                user_id=current_user.id
            ).first()
            if not review:
                flash('Review not found or you do not have permission to edit it.', 'error')
                return redirect(url_for('equipment_info', equipment_id=equipment.id, _anchor='reviews'))

        created_new = False
        if not review:
            review = Rating(equipment_id=equipment.id, user_id=current_user.id)
            db.session.add(review)
            created_new = True

        review.rating = form.rating.data
        review.comment = form.comment.data.strip()
        db.session.commit()
        update_equipment_rating_cache(equipment.id)

        flash('Your review has been {}!'.format('submitted' if created_new else 'updated'), 'success')
        return redirect(url_for('equipment_info', equipment_id=equipment.id, _anchor='reviews'))

    for field_errors in form.errors.values():
        for error in field_errors:
            flash(error, 'error')

    edit_id = None
    if form.review_id.data:
        try:
            edit_id = int(form.review_id.data)
        except (TypeError, ValueError):
            edit_id = None

    context = _gather_equipment_page_context(
        equipment,
        review_form=form,
        edit_review_id=edit_id
    )
    response = render_template('equip_info.html', **context)
    return response, 400


@app.route('/equipment/<int:equipment_id>/reviews/<int:review_id>/delete', methods=['POST'])
@login_required
def delete_review(equipment_id, review_id):
    equipment = Equipment.query.get_or_404(equipment_id)
    review = Rating.query.filter_by(id=review_id, equipment_id=equipment.id).first_or_404()

    if review.user_id != current_user.id:
        flash('You do not have permission to delete this review.', 'error')
        return redirect(url_for('equipment_info', equipment_id=equipment.id, _anchor='reviews'))

    form = DeleteReviewForm()
    if not form.validate_on_submit() or not form.review_id.data:
        flash('Invalid delete request.', 'error')
        return redirect(url_for('equipment_info', equipment_id=equipment.id, _anchor='reviews'))

    try:
        form_review_id = int(form.review_id.data)
    except (TypeError, ValueError):
        flash('Invalid delete request.', 'error')
        return redirect(url_for('equipment_info', equipment_id=equipment.id, _anchor='reviews'))

    if form_review_id != review.id:
        flash('Invalid delete request.', 'error')
        return redirect(url_for('equipment_info', equipment_id=equipment.id, _anchor='reviews'))

    db.session.delete(review)
    db.session.commit()
    update_equipment_rating_cache(equipment.id)
    flash('Your review has been deleted.', 'success')
    return redirect(url_for('equipment_info', equipment_id=equipment.id, _anchor='reviews'))

@app.route('/equipment/<int:equipment_id>/delete', methods=['POST'])
@login_required
def delete_equipment(equipment_id):
    equipment = Equipment.query.get_or_404(equipment_id)
    if not current_user.is_university or equipment.university_id != current_user.id:
        flash('You do not have permission to delete this equipment.', 'error')
        return redirect(url_for('equipment_info', equipment_id=equipment_id))

    db.session.delete(equipment)
    db.session.commit()
    flash('Equipment listing has been removed.', 'success')
    return redirect(url_for('my_equipment'))
        
    return render_template('equip_info.html', title=equipment.name, equipment=equipment, secondary_images=secondary_images)


@app.route('/market')
def market():
    # Get filter values from query string, providing defaults
    search_term = request.args.get('search', '').strip()
    category = request.args.get('category', '')
    university_id_str = request.args.get('university_id', '')
    min_rating_str = request.args.get('min_rating', '').strip()

    # Find the global maximum costs to set the slider range dynamically
    global_max_onsite = db.session.query(func.max(Equipment.cost_onsite)).scalar() or 0
    global_max_remote = db.session.query(func.max(Equipment.cost_remote)).scalar() or 0

    # Round up to the nearest 50 for a cleaner slider, with a sensible minimum.
    slider_max_onsite = max(2000, math.ceil(global_max_onsite / 50) * 50)
    slider_max_remote = max(2000, math.ceil(global_max_remote / 50) * 50)

    # Get slider values from request, defaulting to the max value (which means "Any")
    max_cost_onsite_str = request.args.get('max_cost_onsite', str(slider_max_onsite))
    max_cost_remote_str = request.args.get('max_cost_remote', str(slider_max_remote))
    university_id = int(university_id_str) if university_id_str.isdigit() else None

    try:
        min_rating = int(min_rating_str)
        if not 1 <= min_rating <= 5:
            min_rating = 0
    except (ValueError, TypeError):
        min_rating = 0

    try:
        max_cost_onsite = float(max_cost_onsite_str)
        # If the slider is at its max, it means "Any", so we don't apply this filter.
        if max_cost_onsite >= slider_max_onsite:
            max_cost_onsite = None
    except (ValueError, TypeError):
        max_cost_onsite = None

    try:
        max_cost_remote = float(max_cost_remote_str)
        if max_cost_remote >= slider_max_remote:
            max_cost_remote = None
    except (ValueError, TypeError):
        max_cost_remote = None

    # Start with a base query and join with User to access university name easily
    query = Equipment.query.join(User).order_by(Equipment.name)

    # Apply search term filter (on equipment name and description)
    if search_term:
        search_filter = f'%{search_term}%'
        query = query.filter(
            or_(
                Equipment.name.ilike(search_filter),
                Equipment.description.ilike(search_filter)
            )
        )

    # Apply category filter
    if category:
        query = query.filter(Equipment.category == category)

    # Apply university filter
    if university_id:
        query = query.filter(Equipment.university_id == university_id)

    if min_rating:
        query = query.filter(Equipment.average_rating_cache != None, Equipment.average_rating_cache >= min_rating)

    # Apply cost filters only if a max value is set
    if max_cost_onsite is not None:
        # Filter for equipment that has a defined on-site cost less than or equal to the max
        query = query.filter(Equipment.cost_onsite != None, Equipment.cost_onsite <= max_cost_onsite)

    if max_cost_remote is not None:
        # Filter for equipment that has a defined remote cost less than or equal to the max
        query = query.filter(Equipment.cost_remote != None, Equipment.cost_remote <= max_cost_remote)

    filtered_equipment = query.all()

    # Get all universities to populate the filter dropdown
    all_universities = User.query.filter_by(is_university=True).order_by(User.username).all()

    # Calculate average rating and rating count for each equipment in the list
    for equipment in filtered_equipment:
        avg_rating = calculate_average_rating(equipment.id) or 0
        ratings_count = equipment.ratings_count_cache or 0
        equipment.average_rating = avg_rating
        equipment.ratings_count_display = ratings_count
        equipment.star_width = (avg_rating / 5) * 100 if ratings_count else 0
    return render_template(
        'market.html',
        equipment_list=filtered_equipment,
        universities=all_universities,
        search_term=search_term,
        selected_category=category,
        selected_university_id=university_id,
        slider_max_onsite=slider_max_onsite,
        slider_max_remote=slider_max_remote,
        selected_max_cost_onsite=float(max_cost_onsite_str),
        selected_max_cost_remote=float(max_cost_remote_str),
        selected_min_rating=min_rating
    )
    
@app.route('/my_equipment')
@login_required
def my_equipment():
    if not current_user.is_university:
        flash('This page is for university accounts only.', 'warning')
        return redirect(url_for('index'))
    
    # Fetch equipment listed by the currently logged-in university
    university_equipment = Equipment.query.filter_by(university_id=current_user.id).all()
    bookings = Booking.query.join(Equipment).filter(Equipment.university_id == current_user.id).order_by(Booking.created_at.desc()).all()
    return render_template('uni_home.html', title='My Equipment', equipment_list=university_equipment, bookings=bookings, csrf_token_val=generate_csrf())

@app.route('/equipment/<int:equipment_id>/request', methods=['GET', 'POST'])
@login_required
def request_equipment(equipment_id):
    equipment = Equipment.query.get_or_404(equipment_id)
    form = RentalRequestForm()

    available_days = [int(d) for d in (equipment.available_days or '0,1,2,3,4').split(',') if d.strip()]
    booked_dates = get_booking_blocked_dates(equipment_id)
    manual_closed_dates = get_manual_closed_dates(equipment_id)
    all_blocked = set(booked_dates) | set(manual_closed_dates)

    if form.validate_on_submit():
        raw = form.selected_dates.data or ''
        try:
            selected = json.loads(raw) if raw else []
            if not isinstance(selected, list) or len(selected) == 0:
                raise ValueError('empty')
        except (ValueError, TypeError):
            flash('Please select at least one date on the calendar.', 'error')
            selected = []

        if selected:
            from datetime import datetime as dt_parse
            errors = []
            parsed = []
            for s in selected:
                try:
                    d = dt_parse.strptime(s, '%Y-%m-%d').date()
                except ValueError:
                    errors.append(f'Invalid date: {s}')
                    break
                if d < date.today():
                    errors.append(f'{s} is in the past.')
                    break
                if d.weekday() not in available_days:
                    errors.append(f'{d.strftime("%A %b %d")} is not an available day.')
                    break
                if s in all_blocked:
                    errors.append(f'{d.strftime("%A %b %d")} is already booked or closed.')
                    break
                parsed.append(d)

            if errors:
                for msg in errors:
                    flash(msg, 'error')
            else:
                new_booking = Booking(
                    user_id=current_user.id,
                    equipment_id=equipment.id,
                    start_date=min(parsed),
                    end_date=max(parsed),
                    selected_dates=selected,
                    experiment_description=form.experiment_description.data,
                    samples_list=form.samples_list.data
                )
                db.session.add(new_booking)
                db.session.commit()
                flash('Your request has been sent to the university!', 'success')
                return redirect(url_for('equipment_info', equipment_id=equipment.id))

    return render_template(
        'purchase.html',
        title='Request Equipment',
        form=form,
        equipment=equipment,
        available_days_json=json.dumps(available_days),
        booked_dates_json=json.dumps(booked_dates),
        manual_closed_json=json.dumps(manual_closed_dates),
    )

@app.route('/booking/<int:booking_id>/manage', methods=['GET', 'POST'])
@login_required
def manage_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    # Security check: ensure the current user is the university that owns the equipment
    if not current_user.is_university or booking.equipment.university_id != current_user.id:
        flash('You do not have permission to manage this booking.', 'error')
        return redirect(url_for('my_equipment'))

    form = UniversityApprovalForm()
    if form.validate_on_submit():
        booking.status = form.status.data
        if form.final_cost.data is not None:
            booking.final_cost = form.final_cost.data
        if form.university_notes.data:
            booking.university_notes = form.university_notes.data

        # Auto-block dates when a booking is approved
        if form.status.data == 'Approved':
            from datetime import datetime as dt_parse
            dates_to_block = []
            if booking.selected_dates:
                dates_to_block = [dt_parse.strptime(s, '%Y-%m-%d').date() for s in booking.selected_dates]
            elif booking.start_date and booking.end_date:
                # legacy bookings without selected_dates — block the full range
                cur = booking.start_date
                while cur <= booking.end_date:
                    dates_to_block.append(cur)
                    cur += timedelta(days=1)
            for d in dates_to_block:
                existing = EquipmentBlockedDate.query.filter_by(
                    equipment_id=booking.equipment_id, date=d
                ).first()
                if not existing:
                    db.session.add(EquipmentBlockedDate(
                        equipment_id=booking.equipment_id,
                        date=d,
                        booking_id=booking.id
                    ))

        db.session.commit()
        flash('Booking has been updated successfully.', 'success')
        return redirect(url_for('my_equipment'))

    # Pre-populate form on GET request
    form.status.data = booking.status
    form.university_notes.data = booking.university_notes
    form.final_cost.data = booking.final_cost

    return render_template('manage_booking.html', title='Manage Booking', form=form, booking=booking)

@app.route('/booking/<int:booking_id>/delete', methods=['POST'])
@login_required
def delete_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if not current_user.is_university or booking.equipment.university_id != current_user.id:
        flash('You do not have permission to cancel this booking.', 'error')
        return redirect(url_for('my_equipment'))
    # Release any dates that were blocked by this booking
    EquipmentBlockedDate.query.filter_by(booking_id=booking.id).delete()
    db.session.delete(booking)
    db.session.commit()
    flash('Booking has been cancelled and its dates are now available again.', 'success')
    return redirect(url_for('my_equipment'))


@app.route('/my_orders')
@login_required
def my_orders():
    # This route is now only for regular users to see their own requests.
    if current_user.is_university:
        # Redirect universities to their main dashboard if they land here
        return redirect(url_for('my_equipment'))

    bookings = Booking.query.filter_by(user_id=current_user.id).order_by(Booking.created_at.desc()).all()
    return render_template('user_orders.html', title="My Requests", bookings=bookings)


@app.route('/equipment/<int:equipment_id>/availability', methods=['GET', 'POST'])
@login_required
def manage_availability(equipment_id):
    equipment = Equipment.query.get_or_404(equipment_id)
    if not current_user.is_university or equipment.university_id != current_user.id:
        flash('You do not have permission to manage this equipment.', 'error')
        return redirect(url_for('my_equipment'))

    form = ManageAvailabilityForm()
    remove_form = RemoveBlockedDateForm()

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'save_schedule' and form.validate_on_submit():
            equipment.available_days = ','.join(form.available_days.data) if form.available_days.data else '0,1,2,3,4'
            if form.block_start.data and form.block_end.data:
                if form.block_end.data < form.block_start.data:
                    flash('Block end date must be on or after block start date.', 'error')
                else:
                    current_day = form.block_start.data
                    while current_day <= form.block_end.data:
                        existing = EquipmentBlockedDate.query.filter_by(
                            equipment_id=equipment.id, date=current_day
                        ).first()
                        if not existing:
                            db.session.add(EquipmentBlockedDate(
                                equipment_id=equipment.id,
                                date=current_day,
                                booking_id=None
                            ))
                        current_day += timedelta(days=1)
            db.session.commit()
            flash('Availability updated successfully.', 'success')
            return redirect(url_for('manage_availability', equipment_id=equipment_id))

        elif action == 'remove_date' and remove_form.validate_on_submit():
            from datetime import datetime as dt
            try:
                target_date = dt.strptime(remove_form.date.data, '%Y-%m-%d').date()
            except ValueError:
                flash('Invalid date.', 'error')
                return redirect(url_for('manage_availability', equipment_id=equipment_id))
            blocked = EquipmentBlockedDate.query.filter_by(
                equipment_id=equipment.id, date=target_date, booking_id=None
            ).first()
            if blocked:
                db.session.delete(blocked)
                db.session.commit()
                flash('Date unblocked.', 'success')
            return redirect(url_for('manage_availability', equipment_id=equipment_id))

    # Pre-populate form with current values
    current_days = [d.strip() for d in (equipment.available_days or '0,1,2,3,4').split(',') if d.strip()]
    form.available_days.data = current_days

    manual_blocked = EquipmentBlockedDate.query.filter_by(
        equipment_id=equipment.id, booking_id=None
    ).order_by(EquipmentBlockedDate.date).all()

    booking_blocked = EquipmentBlockedDate.query.filter(
        EquipmentBlockedDate.equipment_id == equipment.id,
        EquipmentBlockedDate.booking_id != None
    ).order_by(EquipmentBlockedDate.date).all()

    available_days = [int(d) for d in current_days if d]

    return render_template(
        'manage_availability.html',
        equipment=equipment,
        form=form,
        remove_form=remove_form,
        manual_blocked=manual_blocked,
        booking_blocked=booking_blocked,
        available_days_json=json.dumps(available_days),
        booked_dates_json=json.dumps(get_booking_blocked_dates(equipment_id)),
        manual_closed_json=json.dumps(get_manual_closed_dates(equipment_id)),
    )


# This part is needed to create the database file and tables from your models.
# It runs only when you execute 'python app.py' directly.
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Add new columns to existing tables if they don't exist (SQLite migration)
        inspector = inspect(db.engine)
        with db.engine.connect() as conn:
            equip_cols = [c['name'] for c in inspector.get_columns('equipment')]
            if 'available_days' not in equip_cols:
                conn.execute(text("ALTER TABLE equipment ADD COLUMN available_days VARCHAR(20) DEFAULT '0,1,2,3,4'"))
                conn.commit()
            if 'booking' in inspector.get_table_names():
                booking_cols = [c['name'] for c in inspector.get_columns('booking')]
                if 'start_date' not in booking_cols:
                    conn.execute(text("ALTER TABLE booking ADD COLUMN start_date DATE"))
                    conn.commit()
                if 'end_date' not in booking_cols:
                    conn.execute(text("ALTER TABLE booking ADD COLUMN end_date DATE"))
                    conn.commit()
                if 'selected_dates' not in booking_cols:
                    conn.execute(text("ALTER TABLE booking ADD COLUMN selected_dates JSON"))
                    conn.commit()
    app.run(debug=True)
