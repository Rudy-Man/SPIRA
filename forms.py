from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, RadioField, SelectField, TextAreaField, FloatField
from wtforms.validators import DataRequired, Email, EqualTo, ValidationError
from flask_wtf.file import FileField, FileAllowed, MultipleFileField
from models import User
from wtforms import TextAreaField
from wtforms.validators import DataRequired


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    password2 = PasswordField(
        'Repeat Password', validators=[DataRequired(), EqualTo('password', message='Passwords must match.')])
    user_type = RadioField('Register as', choices=[('user', 'User'), ('university', 'University')], default='user')
    submit = SubmitField('Register')

    # Custom validator to ensure username is not already taken
    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user is not None:
            raise ValidationError('This username is already taken.')

    # Custom validator to ensure email is not already taken
    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user is not None:
            raise ValidationError('This email address is already in use.')
        
class EquipmentForm(FlaskForm):
    name = StringField('Equipment Name', validators=[DataRequired()])
    category = SelectField('Category', choices=[
        ('physics', 'Physics'),
        ('chemistry', 'Chemistry'),
        ('biology', 'Biology'),
        ('cs', 'Computer Science'),
        ('other', 'Other')
    ], validators=[DataRequired()])
    description = TextAreaField('Description')
    
    model_number = StringField('Model Number')
    manufacturer = StringField('Manufacturer')
    
    primary_image = FileField('Primary Image (1 image)', validators=[FileAllowed(['jpg', 'png', 'jpeg'], 'Images only!')])
    secondary_images = MultipleFileField('Secondary Images (up to 4)', validators=[FileAllowed(['jpg', 'png', 'jpeg'], 'Images only!')])
    
    tech_specs_pdf = FileField('Technical Specs (PDF)', validators=[FileAllowed(['pdf'], 'PDFs only!')])
    instruction_manual_pdf = FileField('Instruction Manual (PDF)', validators=[FileAllowed(['pdf'], 'PDFs only!')])
    terms_pdf = FileField('Terms and Conditions (PDF)', validators=[FileAllowed(['pdf'], 'PDFs only!')])
    
    safety_requirements = TextAreaField('Safety Requirements')
    cost_onsite = FloatField('Cost for On-site Access (per hour)')
    cost_remote = FloatField('Cost for Remote Access (per hour)')
    
    submit = SubmitField('Register Equipment')

class RentalRequestForm(FlaskForm):
    experiment_description = TextAreaField('Experiment Description', validators=[DataRequired()], render_kw={"rows": 6, "placeholder": "Describe your experiment, methodology, and objectives..."})
    samples_list = TextAreaField('Required Samples', render_kw={"rows": 4, "placeholder": "List each sample on a new line..."})
    submit = SubmitField('Submit Request')
