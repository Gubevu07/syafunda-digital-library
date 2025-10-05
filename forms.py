from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, DateField, SelectField, IntegerField, BooleanField, SelectMultipleField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError, Regexp, Optional
from wtforms.widgets import ListWidget, CheckboxInput
from flask_wtf.file import FileField, FileAllowed
from models import User, Category
from flask_babel import lazy_gettext as _l
from datetime import date, datetime

# --- Custom Validators ---


def valid_date_format(form, field):
    """
    Ensures the date is valid (real calendar date) and within a reasonable range.
    """
    if field.data:
        try:
            # WTForms DateField already parses to a `date` object.
            if isinstance(field.data, date):
                if field.data.year < 1000 or field.data.year > date.today().year:
                    raise ValidationError(
                        _l('Please enter a valid year between 1000 and %(year)s.',
                           year=date.today().year)
                    )
            else:
                # Try parsing manually if not already parsed
                datetime.strptime(str(field.data), "%Y-%m-%d")
        except Exception:
            raise ValidationError(
                _l('Invalid date format. Please use YYYY-MM-DD.'))


def not_in_future(form, field):
    """
    Custom validator to ensure a date field is not in the future.
    """
    if field.data and field.data > date.today():
        raise ValidationError(_l('Publication date cannot be in the future.'))


# --- Form Classes ---

class RegistrationForm(FlaskForm):
    username = StringField(_l('Username'),
                           validators=[DataRequired(), Length(min=2, max=20)])
    email = StringField(_l('Email'),
                        validators=[DataRequired(), Email()])
    password = PasswordField(_l('Password'), validators=[
        DataRequired(),
        Regexp('^(?=.*[a-z])(?=.*[A-Z])(?=.*\\d)[a-zA-Z\\d]{8,}$',
               message=_l('Password must be at least 8 characters long and contain at least one uppercase letter, one lowercase letter, and one number.'))
    ])
    confirm_password = PasswordField(_l('Confirm Password'),
                                     validators=[DataRequired(), EqualTo('password', message=_l('Passwords must match.'))])
    accept_terms = BooleanField(
        _l('I accept the Terms of Use & Privacy Policy'), validators=[DataRequired()])
    submit = SubmitField(_l('Sign Up'))

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError(
                _l('That email is already registered. Please choose a different one.'))


class LoginForm(FlaskForm):
    email = StringField(_l('Email'), validators=[DataRequired(), Email()])
    password = PasswordField(_l('Password'), validators=[DataRequired()])
    submit = SubmitField(_l('Login'))


class ResourceForm(FlaskForm):
    title = StringField(_l('Title'), validators=[DataRequired()])
    creator = StringField(_l('Creator/Author'), validators=[DataRequired()])
    subject = StringField(_l('Subject/Keywords'))
    description = TextAreaField(_l('Description/Abstract'))
    publisher = StringField(_l('Publisher'))
    publication_date = DateField(
        _l('Publication Date (YYYY-MM-DD)'),
        format='%Y-%m-%d',
        validators=[Optional(), valid_date_format, not_in_future]
    )
    resource_type = SelectField(_l('Resource Type'), choices=[
        ('E-book', _l('E-book')),
        ('Journal', _l('Journal')),
        ('Research Paper', _l('Research Paper')),
        ('Magazine', _l('Magazine')),
        ('Newspaper', _l('Newspaper'))
    ], validators=[DataRequired()])
    language = StringField(_l('Language'), default='English')
    rights = StringField(_l('Rights Management'))

    categories = SelectMultipleField(_l('Categories'),
                                     coerce=int,
                                     widget=ListWidget(prefix_label=False),
                                     option_widget=CheckboxInput()
                                     )

    resource_file = FileField(_l('Resource File'), validators=[
        DataRequired(),
        FileAllowed(['pdf', 'epub', 'html'],
                    _l('Only PDF, EPUB, and HTML files are allowed!'))
    ])
    preview_image = FileField(_l('Preview Image (Optional, JPG/PNG)'), validators=[
        FileAllowed(['jpg', 'png', 'jpeg'], _l(
            'Only image files are allowed!'))
    ])
    submit = SubmitField(_l('Upload Resource'))


class CategoryForm(FlaskForm):
    name = StringField(_l('Category Name'), validators=[
                       DataRequired(), Length(min=2, max=100)])
    submit = SubmitField(_l('Add Category'))

    def validate_name(self, name):
        category = Category.query.filter_by(name=name.data).first()
        if category:
            raise ValidationError(
                _l('That category name already exists. Please choose a different one.'))


class AdvancedSearchForm(FlaskForm):
    term1 = StringField(_l('Search Term'), validators=[DataRequired()])
    field1 = SelectField(_l('in'), choices=[
        ('all', _l('All Metadata')), ('title', _l(
            'Title')), ('creator', _l('Creator/Author')),
        ('subject', _l('Subject')), ('description', _l('Description/Abstract'))
    ])
    op2 = SelectField(_l('Operator'), choices=[
                      ('AND', 'AND'), ('OR', 'OR'), ('NOT', 'NOT')])
    term2 = StringField(_l('Search Term'), validators=[Optional()])
    field2 = SelectField(_l('in'), choices=[
        ('all', _l('All Metadata')), ('title', _l(
            'Title')), ('creator', _l('Creator/Author')),
        ('subject', _l('Subject')), ('description', _l('Description/Abstract'))
    ])
    op3 = SelectField(_l('Operator'), choices=[
                      ('AND', 'AND'), ('OR', 'OR'), ('NOT', 'NOT')])
    term3 = StringField(_l('Search Term'), validators=[Optional()])
    field3 = SelectField(_l('in'), choices=[
        ('all', _l('All Metadata')), ('title', _l(
            'Title')), ('creator', _l('Creator/Author')),
        ('subject', _l('Subject')), ('description', _l('Description/Abstract'))
    ])
    # Dynamically generate years
    years = [(str(y), str(y)) for y in range(date.today().year, 1989, -1)]
    start_year = SelectField(_l('Published After (Year)'), choices=[(
        '', '---')] + years, validators=[Optional()])
    end_year = SelectField(_l('Published Before (Year)'), choices=[(
        '', '---')] + years, validators=[Optional()])
    submit = SubmitField(_l('Advanced Search'))


class RequestResetForm(FlaskForm):
    email = StringField(_l('Email'), validators=[DataRequired(), Email()])
    submit = SubmitField(_l('Request Password Reset'))

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user is None:
            raise ValidationError(
                _l('There is no account with that email. You must register first.'))


class ResetPasswordForm(FlaskForm):
    password = PasswordField(_l('New Password'), validators=[
        DataRequired(),
        Regexp('^(?=.*[a-z])(?=.*[A-Z])(?=.*\\d)[a-zA-Z\\d]{8,}$',
               message=_l('Password must be at least 8 characters long and contain at least one uppercase letter, one lowercase letter, and one number.'))
    ])
    confirm_password = PasswordField(_l('Confirm New Password'), validators=[
                                     DataRequired(), EqualTo('password')])
    submit = SubmitField(_l('Reset Password'))
