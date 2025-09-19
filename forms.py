from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    PasswordField,
    BooleanField,
    SubmitField,
    RadioField,
    SelectField,
    TextAreaField,
    FloatField,
    HiddenField,
)
from wtforms.validators import DataRequired, Email, EqualTo, ValidationError, Optional
from flask_wtf.file import FileField, FileAllowed, MultipleFileField
from models import User


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(message='Email is required.'), Email(message='Please enter a valid email address.')])
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

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user is not None:
            raise ValidationError('This username is already taken.')

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


class UniversityApprovalForm(FlaskForm):
    final_cost = FloatField('Final Cost (if different from estimate)', validators=[Optional()])
    university_notes = TextAreaField('Notes for Renter', render_kw={"rows": 4})
    status = SelectField('Update Status', choices=[
        ('Approved', 'Approve'),
        ('Rejected', 'Reject')
    ], validators=[DataRequired()])
    submit = SubmitField('Update Booking')


class ReviewForm(FlaskForm):
    rating = RadioField(
        'Rating',
        choices=[(5, '5 stars'), (4, '4 stars'), (3, '3 stars'), (2, '2 stars'), (1, '1 star')],
        validators=[DataRequired()],
        coerce=int
    )
    review_id = HiddenField('Review ID')
    comment = TextAreaField('Comment', validators=[DataRequired()], render_kw={"rows": 4, "placeholder": "Tell others how this equipment helped your research..."})
    submit = SubmitField('Submit Review')


class DeleteReviewForm(FlaskForm):
    review_id = HiddenField('Review ID', validators=[DataRequired()])
    submit = SubmitField('Delete Review')


class ReviewReplyForm(FlaskForm):
    comment = TextAreaField('Reply', validators=[DataRequired()], render_kw={'rows': 2, 'placeholder': 'Write a reply...'})
    submit = SubmitField('Post Reply')


class DeleteReplyForm(FlaskForm):
    reply_id = HiddenField('Reply ID', validators=[DataRequired()])
    submit = SubmitField('Delete Reply')
