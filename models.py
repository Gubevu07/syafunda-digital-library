from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from itsdangerous import URLSafeTimedSerializer as Serializer
from flask import current_app

db = SQLAlchemy()

favorites = db.Table('favorites',
                     db.Column('user_id', db.Integer, db.ForeignKey(
                         'user.id'), primary_key=True),
                     db.Column('resource_id', db.Integer, db.ForeignKey(
                         'resource.id'), primary_key=True)
                     )

resource_categories = db.Table('resource_categories',
                               db.Column('resource_id', db.Integer, db.ForeignKey(
                                   'resource.id'), primary_key=True),
                               db.Column('category_id', db.Integer, db.ForeignKey(
                                   'category.id'), primary_key=True)
                               )


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(80), nullable=False, default='user')
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    theme_preference = db.Column(
        db.String(10), nullable=False, default='light')

    favorite_resources = db.relationship('Resource', secondary=favorites, lazy='subquery',
                                         backref=db.backref('favorited_by', lazy=True))
    downloads = db.relationship('DownloadLog', backref='user', lazy=True)
    search_history = db.relationship(
        'SearchHistory', backref='user', lazy=True, cascade="all, delete-orphan")

    def get_reset_token(self):
        s = Serializer(current_app.config['SECRET_KEY'])
        return s.dumps({'user_id': self.id})

    @staticmethod
    def verify_reset_token(token, expires_sec=1800):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            user_id = s.loads(token, max_age=expires_sec)['user_id']
        except:
            return None
        return User.query.get(user_id)


class Resource(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(100), nullable=False)
    upload_date = db.Column(db.DateTime, nullable=False,
                            default=datetime.utcnow)
    title = db.Column(db.String(200), nullable=False)
    creator = db.Column(db.String(150), nullable=False)
    subject = db.Column(db.String(200))
    description = db.Column(db.Text)
    publisher = db.Column(db.String(150))
    publication_date = db.Column(db.Date)
    resource_type = db.Column(db.String(50), nullable=False)
    format = db.Column(db.String(50))
    language = db.Column(db.String(50))
    rights = db.Column(db.String(250))
    preview_image = db.Column(db.String(100), nullable=True)
    downloads = db.relationship(
        'DownloadLog', backref='resource', lazy=True, cascade="all, delete-orphan")
    categories = db.relationship('Category', secondary=resource_categories, lazy='subquery',
                                 backref=db.backref('resources', lazy=True))

    def __repr__(self):
        return f"Resource('{self.title}', '{self.creator}')"


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)

    def __repr__(self):
        return f"Category('{self.name}')"


class DownloadLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    resource_id = db.Column(db.Integer, db.ForeignKey(
        'resource.id'), nullable=False)
    download_date = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f'<DownloadLog {self.user.username} -> {self.resource.title}>'


class SearchHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # RENAMED: from 'query' to 'query_text'
    query_text = db.Column(db.String(200), nullable=False)
    search_date = db.Column(db.DateTime, nullable=False,
                            default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __repr__(self):
        return f'<SearchHistory "{self.query_text}" by {self.user.username}>'


class SearchQueryLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # RENAMED: from 'query' to 'query_text'
    query_text = db.Column(db.String(200), nullable=False)
    results_count = db.Column(db.Integer, nullable=False)
    search_date = db.Column(db.DateTime, nullable=False,
                            default=datetime.utcnow)

    def __repr__(self):
        return f'<SearchQueryLog "{self.query_text}" ({self.results_count} results)>'
