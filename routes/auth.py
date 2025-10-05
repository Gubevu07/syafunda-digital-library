from flask import render_template, url_for, flash, redirect, Blueprint, request
from flask_login import login_user, current_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Message
from app import mail
from models import db, User
from forms import RegistrationForm, LoginForm, RequestResetForm, ResetPasswordForm
from flask_babel import gettext as _
import traceback


auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    form = RegistrationForm()

    if form.validate_on_submit():
        try:
            # Check if email already exists (additional backend check)
            existing_user = User.query.filter_by(
                email=form.email.data.lower()).first()
            if existing_user:
                flash(
                    _('That email is already registered. Please use a different email or login.'), 'danger')
                return render_template('register.html', title=_('Register'), form=form)

            # Check if username already exists
            existing_username = User.query.filter_by(
                username=form.username.data).first()
            if existing_username:
                flash(
                    _('That username is already taken. Please choose a different one.'), 'danger')
                return render_template('register.html', title=_('Register'), form=form)

            # Create new user
            hashed_password = generate_password_hash(
                form.password.data, method='pbkdf2:sha256')
            new_user = User(
                username=form.username.data,
                email=form.email.data.lower(),
                password=hashed_password
            )

            db.session.add(new_user)
            db.session.commit()

            flash(
                _('Your account has been created successfully! You can now log in.'), 'success')
            return redirect(url_for('auth.login'))

        except Exception as e:
            db.session.rollback()
            print(f"Registration error: {str(e)}")
            traceback.print_exc()
            flash(
                _('An error occurred during registration. Please try again later.'), 'danger')
            return render_template('register.html', title=_('Register'), form=form)

    return render_template('register.html', title=_('Register'), form=form)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    form = LoginForm()

    if form.validate_on_submit():
        try:
            # Query user by email (case-insensitive)
            user = User.query.filter_by(email=form.email.data.lower()).first()

            # Check if user exists
            if not user:
                flash(
                    _('No account found with that email address. Please check your email or register.'), 'danger')
                return render_template('login.html', title=_('Sign In'), form=form)

            # Check password
            if not check_password_hash(user.password, form.password.data):
                flash(
                    _('Incorrect password. Please try again or use "Forgot Password" to reset it.'), 'danger')
                return render_template('login.html', title=_('Sign In'), form=form)

            # Check if account is active
            if not user.is_active:
                flash(
                    _('Your account has been deactivated. Please contact the administrator for assistance.'), 'warning')
                return render_template('login.html', title=_('Sign In'), form=form)

            # Successful login
            login_user(user)

            # Handle next page redirect
            next_page = request.args.get('next')

            flash(_('Welcome back, %(username)s!',
                  username=user.username), 'success')

            # Redirect to next page or home
            if next_page:
                return redirect(next_page)
            else:
                # Redirect based on role
                if user.role == 'admin':
                    return redirect(url_for('admin.dashboard'))
                else:
                    return redirect(url_for('main.index'))

        except Exception as e:
            print(f"Login error: {str(e)}")
            traceback.print_exc()
            flash(_('An error occurred during login. Please try again later.'), 'danger')
            return render_template('login.html', title=_('Sign In'), form=form)

    return render_template('login.html', title=_('Sign In'), form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    try:
        logout_user()
        flash(_('You have been logged out successfully.'), 'info')
    except Exception as e:
        print(f"Logout error: {str(e)}")
        flash(_('Logged out.'), 'info')

    return redirect(url_for('main.index'))


# Password reset functions
def send_reset_email(user):
    try:
        token = user.get_reset_token()
        msg = Message(_('Password Reset Request'),
                      sender='noreply@syafunda.com',
                      recipients=[user.email])
        msg.body = f'''{_('To reset your password, visit the following link:')}
{url_for('auth.reset_token', token=token, _external=True)}

{_('If you did not make this request, simply ignore this email and no changes will be made.')}

{_('This link will expire in 30 minutes.')}
'''
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Email sending error: {str(e)}")
        traceback.print_exc()
        return False


@auth_bp.route("/reset-password", methods=['GET', 'POST'])
def request_reset():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    form = RequestResetForm()

    if form.validate_on_submit():
        try:
            user = User.query.filter_by(email=form.email.data.lower()).first()

            if user:
                if send_reset_email(user):
                    flash(
                        _('An email has been sent with instructions to reset your password.'), 'info')
                else:
                    flash(
                        _('There was an error sending the reset email. Please try again later.'), 'danger')
            else:
                # Don't reveal if email exists or not for security
                flash(
                    _('If an account exists with that email, a password reset link has been sent.'), 'info')

            return redirect(url_for('auth.login'))

        except Exception as e:
            print(f"Password reset request error: {str(e)}")
            traceback.print_exc()
            flash(_('An error occurred. Please try again later.'), 'danger')

    return render_template('request_reset.html', title=_('Reset Password'), form=form)


@auth_bp.route("/reset-password/<token>", methods=['GET', 'POST'])
def reset_token(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    try:
        user = User.verify_reset_token(token)

        if user is None:
            flash(
                _('That reset link is invalid or has expired. Please request a new one.'), 'warning')
            return redirect(url_for('auth.request_reset'))

        form = ResetPasswordForm()

        if form.validate_on_submit():
            try:
                hashed_password = generate_password_hash(
                    form.password.data, method='pbkdf2:sha256')
                user.password = hashed_password
                db.session.commit()

                flash(
                    _('Your password has been updated successfully! You can now log in with your new password.'), 'success')
                return redirect(url_for('auth.login'))

            except Exception as e:
                db.session.rollback()
                print(f"Password reset error: {str(e)}")
                traceback.print_exc()
                flash(
                    _('An error occurred while resetting your password. Please try again.'), 'danger')

        return render_template('reset_token.html', title=_('Reset Password'), form=form)

    except Exception as e:
        print(f"Token verification error: {str(e)}")
        traceback.print_exc()
        flash(_('An error occurred. Please request a new password reset link.'), 'danger')
        return redirect(url_for('auth.request_reset'))
