import os
from datetime import datetime, date, time, timedelta
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, jsonify, Response
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
from sqlalchemy import func, extract
from io import BytesIO
from xhtml2pdf import pisa
from models import db, Resource, User, DownloadLog, Category, SearchQueryLog
from forms import ResourceForm, CategoryForm
from app import admin_required
from flask_babel import gettext as _

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    # --- Basic Stats ---
    total_resources = Resource.query.count()
    total_users = User.query.filter_by(is_active=True).count()
    total_downloads = DownloadLog.query.count()

    # --- Recent Activity Pagination ---
    activity_page = request.args.get('activity_page', 1, type=int)
    recent_downloads_pagination = DownloadLog.query.order_by(
        DownloadLog.download_date.desc()
    ).paginate(page=activity_page, per_page=4, error_out=False)

    # --- Search Trend Analytics ---
    popular_searches = db.session.query(
        SearchQueryLog.query_text,
        func.count(SearchQueryLog.id).label('count')
    ).group_by(SearchQueryLog.query_text).order_by(func.count(SearchQueryLog.id).desc()).limit(5).all()

    zero_result_searches = SearchQueryLog.query.filter_by(results_count=0)\
        .order_by(SearchQueryLog.search_date.desc()).limit(5).all()

    # --- Resource Pagination with Filtering ---
    resource_page = request.args.get('resource_page', 1, type=int)
    type_filter = request.args.get('type_filter', None)

    resources_query = Resource.query
    if type_filter:
        resources_query = resources_query.filter_by(resource_type=type_filter)

    resources_pagination = resources_query.order_by(Resource.upload_date.desc()).paginate(
        page=resource_page, per_page=5, error_out=False
    )
    all_resource_types = [r[0] for r in db.session.query(
        Resource.resource_type).distinct().order_by(Resource.resource_type).all()]

    # --- User Pagination ---
    user_page = request.args.get('user_page', 1, type=int)
    users_pagination = User.query.order_by(User.id.asc()).paginate(
        page=user_page, per_page=5, error_out=False
    )

    # --- Category Management Data ---
    category_form = CategoryForm()
    all_categories = Category.query.order_by(Category.name.asc()).all()

    return render_template('admin/dashboard.html',
                           title=_('Admin Dashboard'),
                           total_resources=total_resources,
                           total_users=total_users,
                           total_downloads=total_downloads,
                           recent_downloads_pagination=recent_downloads_pagination,
                           popular_searches=popular_searches,
                           zero_result_searches=zero_result_searches,
                           resources_pagination=resources_pagination,
                           users_pagination=users_pagination,
                           category_form=category_form,
                           all_categories=all_categories,
                           all_resource_types=all_resource_types,
                           current_filter=type_filter)


@admin_bp.route('/analytics/downloads-by-day')
@login_required
@admin_required
def download_analytics_by_day():
    try:
        period_days = int(request.args.get('period', 7))
    except (ValueError, TypeError):
        period_days = 7

    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=period_days - 1)

    downloads_query = db.session.query(
        func.date(DownloadLog.download_date).label('download_day'),
        func.count(DownloadLog.id).label('count')
    ).filter(
        func.date(DownloadLog.download_date).between(start_date, end_date)
    ).group_by('download_day').all()

    downloads_by_day = {str(d.download_day): d.count for d in downloads_query}

    labels = []
    data = []
    for i in range(period_days):
        current_date = start_date + timedelta(days=i)
        date_str = str(current_date)
        labels.append(current_date.strftime('%b %d'))
        data.append(downloads_by_day.get(date_str, 0))

    return jsonify({'labels': labels, 'data': data})


@admin_bp.route('/reports/download/<report_type>')
@login_required
@admin_required
def download_report(report_type):
    now = datetime.now()
    if report_type == 'resources':
        items = Resource.query.order_by(Resource.title.asc()).all()
        html = render_template(
            'admin/reports/resources_pdf.html', resources=items, now=now)
        filename = 'resources_report.pdf'
    elif report_type == 'users':
        items = User.query.order_by(User.username.asc()).all()
        html = render_template(
            'admin/reports/users_pdf.html', users=items, now=now)
        filename = 'users_report.pdf'
    else:
        flash(_('Invalid report type.'), 'danger')
        return redirect(url_for('admin.dashboard'))

    result = BytesIO()
    pdf = pisa.CreatePDF(BytesIO(html.encode('UTF-8')), dest=result)
    if not pdf.err:
        return Response(result.getvalue(), mimetype='application/pdf',
                        headers={'Content-Disposition': f'attachment;filename={filename}'})
    flash(_('There was an error generating the PDF report.'), 'danger')
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/upload', methods=['GET', 'POST'])
@login_required
@admin_required
def upload():
    form = ResourceForm()
    form.categories.choices = [(c.id, c.name)
                               for c in Category.query.order_by('name')]
    if form.validate_on_submit():
        file = form.resource_file.data
        filename = secure_filename(file.filename)
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        preview_filename = None
        if form.preview_image.data:
            preview_file = form.preview_image.data
            preview_filename = secure_filename(preview_file.filename)
            preview_file.save(os.path.join(
                current_app.config['UPLOAD_FOLDER'], preview_filename))
        new_resource = Resource(
            filename=filename, title=form.title.data, creator=form.creator.data,
            subject=form.subject.data, description=form.description.data,
            publisher=form.publisher.data, publication_date=form.publication_date.data,
            resource_type=form.resource_type.data, format=file.mimetype,
            language=form.language.data, rights=form.rights.data,
            preview_image=preview_filename
        )
        for category_id in form.categories.data:
            category = Category.query.get(category_id)
            if category:
                new_resource.categories.append(category)
        db.session.add(new_resource)
        db.session.commit()
        flash(_('New resource uploaded successfully!'), 'success')
        return redirect(url_for('main.index'))
    return render_template('upload.html', title=_('Upload Resource'), form=form)


@admin_bp.route('/edit/<int:resource_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_resource(resource_id):
    resource = Resource.query.get_or_404(resource_id)
    form = ResourceForm(obj=resource)
    form.categories.choices = [(c.id, c.name)
                               for c in Category.query.order_by('name')]
    from wtforms.validators import DataRequired
    form.resource_file.validators = [
        v for v in form.resource_file.validators if not isinstance(v, DataRequired)]

    if form.validate_on_submit():
        resource.title = form.title.data
        resource.creator = form.creator.data
        resource.subject = form.subject.data
        resource.description = form.description.data
        resource.publisher = form.publisher.data
        resource.publication_date = form.publication_date.data
        resource.resource_type = form.resource_type.data
        resource.language = form.language.data
        resource.rights = form.rights.data
        if isinstance(form.resource_file.data, FileStorage):
            file = form.resource_file.data
            resource.filename = secure_filename(file.filename)
            file.save(os.path.join(
                current_app.config['UPLOAD_FOLDER'], resource.filename))
            resource.format = file.mimetype
        if isinstance(form.preview_image.data, FileStorage):
            preview_file = form.preview_image.data
            resource.preview_image = secure_filename(preview_file.filename)
            preview_file.save(os.path.join(
                current_app.config['UPLOAD_FOLDER'], resource.preview_image))
        resource.categories.clear()
        for category_id in form.categories.data:
            category = Category.query.get(category_id)
            if category:
                resource.categories.append(category)
        db.session.commit()
        flash(_('Resource has been updated!'), 'success')
        return redirect(url_for('main.browse'))
    if request.method == 'GET':
        form.categories.data = [c.id for c in resource.categories]
    return render_template('edit_resource.html', title=_('Edit Resource'), form=form, resource=resource)


@admin_bp.route('/delete/<int:resource_id>', methods=['POST'])
@login_required
@admin_required
def delete_resource(resource_id):
    resource = Resource.query.get_or_404(resource_id)
    db.session.delete(resource)
    db.session.commit()
    flash(_('Resource has been deleted.'), 'success')
    return redirect(url_for('admin.dashboard', _anchor='resource-management'))


@admin_bp.route('/user/toggle-active/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def toggle_user_active(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash(_('You cannot deactivate your own account.'), 'danger')
        return redirect(url_for('admin.dashboard', _anchor='user-management'))
    user.is_active = not user.is_active
    db.session.commit()
    if user.is_active:
        flash(_('User %(username)s has been activated.',
              username=user.username), 'success')
    else:
        flash(_('User %(username)s has been deactivated.',
              username=user.username), 'success')
    return redirect(url_for('admin.dashboard', _anchor='user-management'))


@admin_bp.route('/category/add', methods=['POST'])
@login_required
@admin_required
def add_category():
    form = CategoryForm()
    if form.validate_on_submit():
        new_category = Category(name=form.name.data)
        db.session.add(new_category)
        db.session.commit()
        flash(_('Category "%(name)s" has been added.',
              name=new_category.name), 'success')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(_('Error in %(field_label)s: %(error)s', field_label=getattr(
                    form, field).label.text, error=error), 'danger')
    return redirect(url_for('admin.dashboard', _anchor='category-management'))


@admin_bp.route('/category/delete/<int:category_id>', methods=['POST'])
@login_required
@admin_required
def delete_category(category_id):
    category = Category.query.get_or_404(category_id)
    db.session.delete(category)
    db.session.commit()
    flash(_('Category "%(name)s" has been deleted.', name=category.name), 'success')
    return redirect(url_for('admin.dashboard', _anchor='category-management'))
