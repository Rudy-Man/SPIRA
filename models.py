from datetime import datetime

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from werkzeug.security import check_password_hash, generate_password_hash


db = SQLAlchemy()


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    is_university = db.Column(db.Boolean, default=False)

    equipment = db.relationship('Equipment', back_populates='university', lazy='dynamic')
    bookings = db.relationship('Booking', foreign_keys='Booking.user_id', back_populates='renter', lazy='dynamic')
    review_replies = db.relationship('ReviewReply', back_populates='user', cascade='all, delete-orphan', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)


class Equipment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text)

    model_number = db.Column(db.String(100))
    manufacturer = db.Column(db.String(100))

    primary_image_filename = db.Column(db.String(100))
    secondary_images_filenames = db.Column(db.JSON)

    tech_specs_pdf_filename = db.Column(db.String(100))
    instruction_manual_pdf_filename = db.Column(db.String(100))
    terms_pdf_filename = db.Column(db.String(100))

    safety_requirements = db.Column(db.Text)

    cost_onsite = db.Column(db.Float)
    cost_remote = db.Column(db.Float)
    average_rating_cache = db.Column(db.Float, default=0)
    ratings_count_cache = db.Column(db.Integer, default=0)

    university_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    university = db.relationship('User', back_populates='equipment')
    reviews = db.relationship('Rating', back_populates='equipment', cascade='all, delete-orphan', lazy='dynamic')

    def average_rating(self):
        return round(self.average_rating_cache or 0, 2)


class Rating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    equipment_id = db.Column(db.Integer, db.ForeignKey('equipment.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('ratings', lazy='dynamic'))
    equipment = db.relationship('Equipment', back_populates='reviews')
    replies = db.relationship('ReviewReply', back_populates='rating', cascade='all, delete-orphan', order_by='ReviewReply.created_at')


class ReviewReply(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    rating_id = db.Column(db.Integer, db.ForeignKey('rating.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    comment = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    rating = db.relationship('Rating', back_populates='replies')
    user = db.relationship('User', back_populates='review_replies')


def calculate_average_rating(equipment_id):
    equipment = Equipment.query.get(equipment_id)
    if equipment:
        return round(equipment.average_rating_cache or 0, 2)
    return 0


def update_equipment_rating_cache(equipment_id):
    equipment = Equipment.query.get(equipment_id)
    if not equipment:
        return
    ratings_query = Rating.query.filter_by(equipment_id=equipment_id)
    count = ratings_query.count()
    avg = ratings_query.with_entities(func.avg(Rating.rating)).scalar() or 0
    equipment.ratings_count_cache = count
    equipment.average_rating_cache = float(avg)
    db.session.commit()


class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    equipment_id = db.Column(db.Integer, db.ForeignKey('equipment.id'), nullable=False)

    experiment_description = db.Column(db.Text, nullable=False)
    samples_list = db.Column(db.Text)

    status = db.Column(db.String(50), nullable=False, default='Pending Approval')

    final_cost = db.Column(db.Float)
    university_notes = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    renter = db.relationship('User', back_populates='bookings')
    equipment = db.relationship('Equipment', backref='bookings')
