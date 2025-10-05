import os
from functools import wraps
from flask import Flask, render_template, redirect, url_for, flash, session, request
from dotenv import load_dotenv
from flask_login import LoginManager, current_user
from werkzeug.security import generate_password_hash
from flask_babel import Babel
from flask_mail import Mail
from models import db, User
from forms import LoginForm, RegistrationForm

load_dotenv()

mail = Mail()


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function


# --- APP FACTORY ---
def create_app():
    app = Flask(__name__)

    # --- CONFIGURATION ---
    app.config['SECRET_KEY'] = 'your_super_secret_key'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///library.db'
    app.config['UPLOAD_FOLDER'] = 'uploads'
    app.config['LANGUAGES'] = ['en', 'zu']

    app.config['MAIL_SERVER'] = 'smtp.googlemail.com'
    app.config['MAIL_PORT'] = 587
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')

    # --- INITIALIZE EXTENSIONS ---
    db.init_app(app)
    mail.init_app(app)

    def get_locale():
        if 'language' in session:
            return session['language']
        return request.accept_languages.best_match(app.config['LANGUAGES'])

    babel = Babel(app, locale_selector=get_locale)

    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # --- CLI COMMANDS ---
    # FIXED: Restored the full create-admin function
    @app.cli.command("create-admin")
    def create_admin():
        """Creates the admin user via the command line."""
        username = input("Enter admin username: ")
        email = input("Enter admin email: ")
        password = input("Enter admin password: ")

        user = User.query.filter_by(email=email).first()
        if user:
            print("Admin with that email already exists.")
            return

        admin_user = User(
            username=username,
            email=email,
            password=generate_password_hash(
                password, method='pbkdf2:sha256'),
            role='admin'
        )
        db.session.add(admin_user)
        db.session.commit()
        print(f"Admin user '{username}' created successfully!")

    # --- BLUEPRINTS ---
    from routes.auth import auth_bp
    from routes.admin import admin_bp
    from routes.main import main_bp
    from routes.user import user_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(user_bp)

    # --- CREATE DATABASE TABLES ---
    with app.app_context():
        db.create_all()

    return app


# --- RUN APPLICATION ---
if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
