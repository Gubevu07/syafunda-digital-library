# routes/user.py

from flask import Blueprint, render_template, flash, redirect, url_for, request
from flask_login import login_required, current_user
from models import db, Resource, SearchHistory
from flask_babel import gettext as _

user_bp = Blueprint('user', __name__)


@user_bp.route('/my-account')
@login_required
def my_account():
    # Paginate favorites - 6 per page
    page = request.args.get('page', 1, type=int)

    # Get IDs of user's favorite resources
    favorite_ids = [fav.id for fav in current_user.favorite_resources]

    # Query and paginate favorites
    favorites_query = Resource.query.filter(Resource.id.in_(
        favorite_ids)) if favorite_ids else Resource.query.filter(Resource.id == -1)

    favorites_pagination = favorites_query.order_by(Resource.title.asc()).paginate(
        page=page, per_page=6, error_out=False
    )

    favorites = favorites_pagination.items

    # Get the user's recent search history - limit to 10
    search_history = SearchHistory.query.filter_by(user_id=current_user.id)\
                                        .order_by(SearchHistory.search_date.desc())\
                                        .limit(10).all()

    return render_template('my_account.html',
                           title=_('My Account'),
                           favorites=favorites,
                           favorites_pagination=favorites_pagination,
                           search_history=search_history)


@user_bp.route('/add-favorite/<int:resource_id>', methods=['POST'])
@login_required
def add_favorite(resource_id):
    resource = Resource.query.get_or_404(resource_id)
    if resource not in current_user.favorite_resources:
        current_user.favorite_resources.append(resource)
        db.session.commit()
        flash(_('Resource added to your favorites!'), 'success')
    else:
        flash(_('This resource is already in your favorites.'), 'info')
    return redirect(request.referrer or url_for('main.browse'))


@user_bp.route('/remove-favorite/<int:resource_id>', methods=['POST'])
@login_required
def remove_favorite(resource_id):
    resource = Resource.query.get_or_404(resource_id)
    if resource in current_user.favorite_resources:
        current_user.favorite_resources.remove(resource)
        db.session.commit()
        flash(_('Resource removed from your favorites.'), 'success')
    else:
        flash(_('This resource is not in your favorites.'), 'info')
    return redirect(request.referrer or url_for('user.my_account'))
