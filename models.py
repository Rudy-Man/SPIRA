from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

# Create a database instance
db = SQLAlchemy()

# Define the User table
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    is_university = db.Column(db.Boolean, default=False)
    equipment= db.relationship('Equipment', back_populates='university', lazy='dynamic')
    bookings = db.relationship('Booking', foreign_keys='Booking.user_id', back_populates='renter', lazy='dynamic')

    # New method to hash the password
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    # New method to check the password
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
class Equipment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text)
    
    # New fields based on the wireframe
    model_number = db.Column(db.String(100))
    manufacturer = db.Column(db.String(100))
    
    primary_image_filename = db.Column(db.String(100))
    secondary_images_filenames = db.Column(db.JSON) # Store list of filenames
    
    tech_specs_pdf_filename = db.Column(db.String(100))
    instruction_manual_pdf_filename = db.Column(db.String(100))
    terms_pdf_filename = db.Column(db.String(100))
    
    safety_requirements = db.Column(db.Text)
    
    cost_onsite = db.Column(db.Float)
    cost_remote = db.Column(db.Float)

    # Foreign Key to link to the User (University)
    university_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    university = db.relationship('User', back_populates='equipment')
    

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    
    # Foreign keys to link the booking to a user and equipment
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    equipment_id = db.Column(db.Integer, db.ForeignKey('equipment.id'), nullable=False)

    # --- Data from the 5-step rental process ---
    experiment_description = db.Column(db.Text, nullable=False)
    samples_list = db.Column(db.Text) # Storing as a simple text field for now
    
    # Status to track the booking's progress
    # e.g., 'Pending Approval', 'Approved', 'Rejected', 'Completed'
    status = db.Column(db.String(50), nullable=False, default='Pending Approval')
    
    # Fields for the university to fill in
    final_cost = db.Column(db.Float)
    university_notes = db.Column(db.Text) # For any notes back to the renter

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    renter = db.relationship('User', back_populates='bookings')
    equipment = db.relationship('Equipment', backref='bookings')