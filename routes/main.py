from flask import Blueprint, render_template, send_from_directory, current_app, request, redirect, url_for, session, jsonify
from sqlalchemy import or_, and_, not_, extract, func
from flask_login import login_required, current_user
from datetime import datetime
from models import db, Resource, DownloadLog, Category, SearchHistory, SearchQueryLog
from forms import AdvancedSearchForm

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    return render_template('index.html')


@main_bp.route('/about')
def about():
    return render_template('about.html')


@main_bp.route('/browse')
@login_required
def browse():
    page = request.args.get('page', 1, type=int)
    pagination = Resource.query.order_by(Resource.upload_date.desc()).paginate(
        page=page, per_page=6, error_out=False
    )
    resources = pagination.items
    return render_template('browse.html',
                           title='Browse',
                           resources=resources,
                           pagination=pagination,
                           page=page)


@main_bp.route('/resource/<int:resource_id>')
@login_required
def resource_detail(resource_id):
    resource = Resource.query.get_or_404(resource_id)
    return render_template('resource_detail.html', title=resource.title, resource=resource)


@main_bp.route('/uploads/<path:filename>')
def serve_upload(filename):
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)


@main_bp.route('/download/<int:resource_id>')
@login_required
def download(resource_id):
    resource = Resource.query.get_or_404(resource_id)

    new_log = DownloadLog(user_id=current_user.id, resource_id=resource.id)
    db.session.add(new_log)
    db.session.commit()

    return send_from_directory(
        current_app.config['UPLOAD_FOLDER'], resource.filename, as_attachment=True
    )


@main_bp.route('/search')
@login_required
def search():
    query = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)
    sort_by = request.args.get('sort', 'date_desc')
    active_types = request.args.getlist('type')
    active_langs = request.args.getlist('lang')
    active_categories = request.args.getlist('cat')

    start_year_str = request.args.get('start_year', '')
    end_year_str = request.args.get('end_year', '')
    current_year = datetime.utcnow().year

    start_year, end_year = None, None
    try:
        if start_year_str:
            temp_start = int(start_year_str)
            if 1000 <= temp_start <= current_year:
                start_year = temp_start
    except (ValueError, TypeError):
        pass

    try:
        if end_year_str:
            temp_end = int(end_year_str)
            if 1000 <= temp_end <= current_year:
                end_year = temp_end
    except (ValueError, TypeError):
        pass

    if not query:
        return redirect(url_for('main.browse'))

    if query:
        new_search = SearchHistory(query_text=query, user_id=current_user.id)
        db.session.add(new_search)
        db.session.commit()

    base_query = Resource.query.filter(
        or_(
            Resource.title.ilike(f'%{query}%'),
            Resource.description.ilike(f'%{query}%'),
            Resource.creator.ilike(f'%{query}%'),
            Resource.subject.ilike(f'%{query}%')
        )
    )

    type_counts_query = base_query.with_entities(Resource.resource_type, func.count(
        Resource.id)).group_by(Resource.resource_type).all()
    type_counts = dict(type_counts_query)

    lang_counts_query = base_query.with_entities(
        Resource.language, func.count(Resource.id)).group_by(Resource.language).all()
    lang_counts = dict(lang_counts_query)

    category_counts = {}
    search_results_ids = [
        r.id for r in base_query.with_entities(Resource.id).all()]
    if search_results_ids:
        category_counts_query = db.session.query(Category.id, func.count(Resource.id)).join(
            Category.resources).filter(Resource.id.in_(search_results_ids)).group_by(Category.id).all()
        category_counts = dict(category_counts_query)

    filtered_query = base_query

    if active_types:
        filtered_query = filtered_query.filter(
            Resource.resource_type.in_(active_types))

    if active_langs:
        filtered_query = filtered_query.filter(
            Resource.language.in_(active_langs))

    if active_categories:
        active_category_ids = [int(c) for c in active_categories]
        filtered_query = filtered_query.filter(
            Resource.categories.any(Category.id.in_(active_category_ids)))

    if start_year:
        filtered_query = filtered_query.filter(
            extract('year', Resource.publication_date) >= start_year)

    if end_year:
        filtered_query = filtered_query.filter(
            extract('year', Resource.publication_date) <= end_year)

    if sort_by == 'date_asc':
        filtered_query = filtered_query.order_by(
            Resource.publication_date.asc())
    elif sort_by == 'title_asc':
        filtered_query = filtered_query.order_by(Resource.title.asc())
    elif sort_by == 'title_desc':
        filtered_query = filtered_query.order_by(Resource.title.desc())
    else:
        filtered_query = filtered_query.order_by(
            Resource.publication_date.desc())

    pagination = filtered_query.paginate(
        page=page, per_page=5, error_out=False)
    results = pagination.items

    log_search = SearchQueryLog(
        query_text=query, results_count=pagination.total)
    db.session.add(log_search)
    db.session.commit()

    all_types = ['E-book', 'Journal',
                 'Research Paper', 'Magazine', 'Newspaper']
    all_langs = db.session.query(Resource.language).distinct().all()
    all_categories = Category.query.order_by(Category.name.asc()).all()

    return render_template('search_results.html',
                           title='Search Results',
                           pagination=pagination,
                           results=results,
                           query=query,
                           all_types=all_types,
                           all_langs=[l[0] for l in all_langs],
                           active_types=active_types,
                           active_langs=active_langs,
                           start_year=start_year,
                           end_year=end_year,
                           sort_by=sort_by,
                           type_counts=type_counts,
                           lang_counts=lang_counts,
                           all_categories=all_categories,
                           active_categories=active_categories,
                           category_counts=category_counts,
                           now=datetime.utcnow())


@main_bp.route('/advanced-search', methods=['GET', 'POST'])
@login_required
def advanced_search():

    if request.method == 'POST':
        form = AdvancedSearchForm()
    else:
        form = AdvancedSearchForm(request.args)

    if form.term1.data:

        query = Resource.query
        filters = []

        def build_condition(term, field):
            search_term = f'%{term}%'
            if field == 'all':
                return or_(Resource.title.ilike(search_term), Resource.creator.ilike(search_term),
                           Resource.subject.ilike(search_term), Resource.description.ilike(search_term))
            else:
                return getattr(Resource, field).ilike(search_term)

        condition1 = build_condition(form.term1.data, form.field1.data)
        filters.append(condition1)

        if form.term2.data:
            condition2 = build_condition(form.term2.data, form.field2.data)
            if form.op2.data == 'OR':
                last_filter = filters.pop()
                filters.append(or_(last_filter, condition2))
            elif form.op2.data == 'NOT':
                filters.append(not_(condition2))
            else:  # AND
                filters.append(condition2)

        if form.term3.data:
            condition3 = build_condition(form.term3.data, form.field3.data)
            if form.op3.data == 'OR':
                last_filter = filters.pop()
                filters.append(or_(last_filter, condition3))
            elif form.op3.data == 'NOT':
                filters.append(not_(condition3))
            else:  # AND
                filters.append(condition3)

        if form.start_year.data:
            try:
                filters.append(extract('year', Resource.publication_date) >= int(
                    form.start_year.data))
            except (ValueError, TypeError):
                pass
        if form.end_year.data:
            try:
                filters.append(
                    extract('year', Resource.publication_date) <= int(form.end_year.data))
            except (ValueError, TypeError):
                pass

        base_query = query.filter(and_(*filters))

        type_counts_query = base_query.with_entities(
            Resource.resource_type, func.count(Resource.id)
        ).group_by(Resource.resource_type).all()
        type_counts = dict(type_counts_query)

        lang_counts_query = base_query.with_entities(
            Resource.language, func.count(Resource.id)
        ).group_by(Resource.language).all()
        lang_counts = dict(lang_counts_query)

        category_counts = {}
        search_results_ids = [
            r.id for r in base_query.with_entities(Resource.id).all()]
        if search_results_ids:
            category_counts_query = db.session.query(
                Category.id, func.count(Resource.id)
            ).join(Category.resources).filter(
                Resource.id.in_(search_results_ids)
            ).group_by(Category.id).all()
            category_counts = dict(category_counts_query)

        page = request.args.get('page', 1, type=int)
        sort_by = request.args.get('sort', 'date_desc')
        active_types = request.args.getlist('type')
        active_langs = request.args.getlist('lang')
        active_categories = request.args.getlist('cat')

        filtered_query = base_query

        if active_types:
            filtered_query = filtered_query.filter(
                Resource.resource_type.in_(active_types))
        if active_langs:
            filtered_query = filtered_query.filter(
                Resource.language.in_(active_langs))
        if active_categories:
            active_category_ids = [int(c)
                                   for c in active_categories if c.isdigit()]
            if active_category_ids:
                filtered_query = filtered_query.filter(
                    Resource.categories.any(Category.id.in_(active_category_ids)))

        if sort_by == 'date_asc':
            filtered_query = filtered_query.order_by(
                Resource.publication_date.asc())
        elif sort_by == 'title_asc':
            filtered_query = filtered_query.order_by(Resource.title.asc())
        elif sort_by == 'title_desc':
            filtered_query = filtered_query.order_by(Resource.title.desc())
        else:
            filtered_query = filtered_query.order_by(
                Resource.publication_date.desc())

        pagination = filtered_query.paginate(
            page=page, per_page=5, error_out=False)
        results = pagination.items

        if request.method == 'POST' and form.validate_on_submit():
            query_text = form.term1.data

            new_search = SearchHistory(
                query_text=query_text, user_id=current_user.id)
            db.session.add(new_search)

            log_search = SearchQueryLog(
                query_text=f"Advanced: {query_text}", results_count=pagination.total)
            db.session.add(log_search)
            db.session.commit()

        all_types = ['E-book', 'Journal',
                     'Research Paper', 'Magazine', 'Newspaper']
        all_langs = [l[0] for l in db.session.query(
            Resource.language).distinct().all()]
        all_categories = Category.query.order_by(Category.name.asc()).all()

        adv_params_for_url = {
            'term1': form.term1.data, 'field1': form.field1.data,
            'op2': form.op2.data, 'term2': form.term2.data, 'field2': form.field2.data,
            'op3': form.op3.data, 'term3': form.term3.data, 'field3': form.field3.data
        }

        link_params = {**adv_params_for_url, **request.args}

        return render_template('search_results.html',
                               title='Advanced Search Results',
                               results=results,
                               query='Advanced Search',
                               pagination=pagination,
                               sort_by=sort_by,
                               all_types=all_types,
                               all_langs=all_langs,
                               all_categories=all_categories,
                               active_types=active_types,
                               active_langs=active_langs,
                               active_categories=active_categories,
                               start_year=form.start_year.data or '',
                               end_year=form.end_year.data or '',
                               type_counts=type_counts,
                               lang_counts=lang_counts,
                               category_counts=category_counts,
                               advanced_params_for_url=adv_params_for_url,
                               link_params=link_params,
                               now=datetime.utcnow()
                               )

    return render_template('advanced_search.html', title='Advanced Search', form=form)


@main_bp.route('/search/suggestions')
def search_suggestions():
    query = request.args.get('q', '').strip()
    if not query or len(query) < 2:
        return jsonify([])

    suggestions = Resource.query.filter(
        Resource.title.ilike(f'%{query}%')).limit(5).all()

    return jsonify([s.title for s in suggestions])


@main_bp.route('/language/<lang>')
def set_language(lang=None):
    session['language'] = lang
    return redirect(request.referrer)


@main_bp.route('/theme/<theme>')
@login_required
def set_theme(theme=None):
    if theme in ['light', 'dark']:
        current_user.theme_preference = theme
        db.session.commit()
        session['theme'] = theme
    return redirect(request.referrer)
