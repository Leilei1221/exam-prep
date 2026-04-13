from __future__ import annotations
import json
import os
import csv
import io
from datetime import datetime, date, timedelta

from flask import (Flask, render_template, request, redirect, url_for,
                   jsonify, flash, abort)
from werkzeug.middleware.proxy_fix import ProxyFix

from models import db, Category, Question, UserAnswer, DailyPlan, StudySession, WrongQuestion, DailyStats
from utils import calc_next_review, calc_accuracy, calc_streak, get_difficulty_label, get_difficulty_color

# ── App Setup ───────────────────────────────────────────────

app = Flask(__name__)
app.config.from_pyfile('config.py')
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

db.init_app(app)

with app.app_context():
    if app.config['SQLALCHEMY_DATABASE_URI'].startswith('sqlite'):
        from sqlalchemy import event as sa_event

        @sa_event.listens_for(db.engine, 'connect')
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute('PRAGMA journal_mode=WAL')
            cursor.execute('PRAGMA busy_timeout=5000')
            cursor.close()

    db.create_all()

    from seed import seed_all
    seed_all(app, db)


# ── Helpers ─────────────────────────────────────────────────

def get_or_create_today_stats():
    today = date.today()
    stats = DailyStats.query.filter_by(stat_date=today).first()
    if not stats:
        # Calculate streak
        all_stats = DailyStats.query.order_by(DailyStats.stat_date.desc()).all()
        streak = calc_streak(all_stats)
        stats = DailyStats(stat_date=today, streak_days=streak)
        db.session.add(stats)
        db.session.commit()
    return stats


def update_today_stats(correct_delta=0, total_delta=0, minutes_delta=0):
    stats = get_or_create_today_stats()
    stats.questions_done += total_delta
    stats.correct_count += correct_delta
    stats.study_minutes += minutes_delta
    db.session.commit()
    return stats


def get_current_day_plan():
    """根據今日日期取得當前計劃日"""
    # 找第一個有 plan_date 的計劃
    first_plan = DailyPlan.query.filter(DailyPlan.plan_date.isnot(None)).order_by(DailyPlan.day_number).first()
    if not first_plan:
        return None
    start_date = first_plan.plan_date
    delta = (date.today() - start_date).days
    day_number = delta + 1
    if day_number < 1 or day_number > 30:
        return None
    return DailyPlan.query.filter_by(day_number=day_number).first()


def parse_options(question):
    try:
        return json.loads(question.options_json) if question.options_json else []
    except Exception:
        return []


def parse_key_points(question):
    try:
        return json.loads(question.key_points_json) if question.key_points_json else []
    except Exception:
        return []


# ── 首頁 / 儀表板 ────────────────────────────────────────────

@app.route('/')
def index():
    stats = get_or_create_today_stats()
    today_plan = get_current_day_plan()

    # 今日已答題數
    today_start = datetime.combine(date.today(), datetime.min.time())
    today_answers = UserAnswer.query.filter(UserAnswer.answered_at >= today_start).all()
    today_done = len(today_answers)
    today_correct = sum(1 for a in today_answers if a.is_correct)

    # 待複習錯題數
    pending_review = WrongQuestion.query.filter_by(is_mastered=False).filter(
        (WrongQuestion.next_review_at <= date.today()) | (WrongQuestion.next_review_at.is_(None))
    ).count()

    # 總統計
    total_answers = UserAnswer.query.count()
    total_correct = UserAnswer.query.filter_by(is_correct=True).count()

    # 計劃是否已設定開始日期
    plan_started = DailyPlan.query.filter(DailyPlan.plan_date.isnot(None)).count() > 0

    return render_template('index.html',
        stats=stats,
        today_plan=today_plan,
        today_done=today_done,
        today_correct=today_correct,
        pending_review=pending_review,
        total_answers=total_answers,
        total_correct=total_correct,
        plan_started=plan_started,
    )


@app.route('/plan/set-start', methods=['POST'])
def set_plan_start():
    start_date_str = request.form.get('start_date')
    if not start_date_str:
        flash('請選擇開始日期', 'danger')
        return redirect(url_for('plan'))
    try:
        start_date = date.fromisoformat(start_date_str)
    except ValueError:
        flash('日期格式錯誤', 'danger')
        return redirect(url_for('plan'))

    plans = DailyPlan.query.order_by(DailyPlan.day_number).all()
    for plan in plans:
        plan.plan_date = start_date + timedelta(days=plan.day_number - 1)
    db.session.commit()
    flash('讀書計劃已設定！', 'success')
    return redirect(url_for('plan'))


# ── 30天計劃 ─────────────────────────────────────────────────

@app.route('/plan')
def plan():
    plans = DailyPlan.query.order_by(DailyPlan.day_number).all()
    today_plan = get_current_day_plan()
    plan_started = any(p.plan_date for p in plans)

    # 計算各天完成進度
    progress = {}
    for p in plans:
        today_start = datetime.combine(date.today(), datetime.min.time())
        if p.plan_date:
            day_start = datetime.combine(p.plan_date, datetime.min.time())
            day_end = day_start + timedelta(days=1)
            done = UserAnswer.query.filter(
                UserAnswer.answered_at >= day_start,
                UserAnswer.answered_at < day_end,
                UserAnswer.day_number == p.day_number,
            ).count()
        else:
            done = 0
        progress[p.day_number] = done

    return render_template('plan.html',
        plans=plans,
        today_plan=today_plan,
        plan_started=plan_started,
        progress=progress,
        today=date.today(),
    )


@app.route('/plan/<int:day>')
def plan_day(day):
    plan = DailyPlan.query.filter_by(day_number=day).first_or_404()

    # 本日已作答
    answers = UserAnswer.query.filter_by(day_number=day).all()
    done_count = len(answers)
    correct_count = sum(1 for a in answers if a.is_correct)

    # 取得相關題目（依計劃中的分類和標籤）
    tags = [t.strip() for t in plan.key_points.split(',') if t.strip()]
    cat_codes = [c.strip() for c in plan.category_codes.split(',') if c.strip()]

    # Build query for related questions
    from sqlalchemy import or_
    cats = Category.query.filter(Category.code.in_(cat_codes)).all() if cat_codes else []
    cat_ids = [c.id for c in cats]

    query = Question.query
    if cat_ids:
        query = query.filter(Question.category_id.in_(cat_ids))
    related_questions = query.limit(5).all()

    return render_template('plan_day.html',
        plan=plan,
        done_count=done_count,
        correct_count=correct_count,
        related_questions=related_questions,
        tags=tags,
    )


@app.route('/api/plan/<int:day>/adjust', methods=['POST'])
def api_plan_adjust(day):
    plan = DailyPlan.query.filter_by(day_number=day).first_or_404()
    data = request.get_json() or {}
    if 'target_questions' in data:
        plan.target_questions = int(data['target_questions'])
    if 'notes' in data:
        plan.notes = data['notes']
    db.session.commit()
    return jsonify({'ok': True})


# ── 練習作答 ─────────────────────────────────────────────────

@app.route('/practice')
def practice():
    # 篩選參數
    category_id = request.args.get('category_id', type=int)
    difficulty = request.args.get('difficulty', type=int)
    q_type = request.args.get('q_type', '')
    day = request.args.get('day', type=int)
    tags_filter = request.args.get('tags', '')
    session_id = request.args.get('session_id', type=int)

    categories = Category.query.order_by(Category.sort_order).all()

    # 建構查詢
    query = Question.query.filter(Question.q_type.in_(['single', 'multiple']))
    if category_id:
        query = query.filter_by(category_id=category_id)
    if difficulty:
        query = query.filter_by(difficulty=difficulty)
    if q_type:
        query = query.filter_by(q_type=q_type)
    if tags_filter:
        query = query.filter(Question.tags.contains(tags_filter))

    from sqlalchemy.sql.expression import func
    question = query.order_by(func.random()).first()

    active_session = None
    if session_id:
        active_session = StudySession.query.get(session_id)

    today_plan = get_current_day_plan()

    return render_template('practice.html',
        question=question,
        options=parse_options(question) if question else [],
        categories=categories,
        category_id=category_id,
        difficulty=difficulty,
        q_type=q_type,
        tags_filter=tags_filter,
        active_session=active_session,
        today_plan=today_plan,
        day=day,
        get_difficulty_label=get_difficulty_label,
        get_difficulty_color=get_difficulty_color,
    )


@app.route('/api/answer', methods=['POST'])
def api_answer():
    data = request.get_json() or {}
    question_id = data.get('question_id')
    user_answer = data.get('answer', '').strip().upper()
    session_id = data.get('session_id')
    mode = data.get('mode', 'practice')
    day_number = data.get('day_number')

    q = Question.query.get(question_id)
    if not q:
        return jsonify({'error': 'Question not found'}), 404

    # 判斷對錯
    if q.q_type == 'multiple':
        correct_set = set(q.answer.upper().split(','))
        user_set = set(user_answer.split(',')) if user_answer else set()
        is_correct = correct_set == user_set
    else:
        is_correct = user_answer == q.answer.upper()

    # 記錄作答
    ans = UserAnswer(
        question_id=question_id,
        user_answer=user_answer,
        is_correct=is_correct,
        mode=mode,
        session_id=session_id,
        day_number=day_number,
    )
    db.session.add(ans)

    # 更新錯題本
    if not is_correct:
        wq = WrongQuestion.query.filter_by(question_id=question_id).first()
        if wq:
            wq.wrong_count += 1
            wq.last_wrong_at = datetime.utcnow()
            wq.next_review_at = calc_next_review(wq.wrong_count)
            wq.is_mastered = False
        else:
            wq = WrongQuestion(
                question_id=question_id,
                wrong_count=1,
                next_review_at=calc_next_review(1),
            )
            db.session.add(wq)
    else:
        # 若之前錯過，重新計算下次複習（答對也要繼續複習）
        wq = WrongQuestion.query.filter_by(question_id=question_id).first()
        if wq and not wq.is_mastered:
            wq.next_review_at = calc_next_review(wq.wrong_count + 3)

    # 更新 session
    if session_id:
        ss = StudySession.query.get(session_id)
        if ss:
            ss.total_questions += 1
            if is_correct:
                ss.correct_count += 1

    # 更新每日統計
    update_today_stats(
        correct_delta=1 if is_correct else 0,
        total_delta=1,
    )

    db.session.commit()

    return jsonify({
        'is_correct': is_correct,
        'correct_answer': q.answer,
        'explanation': q.explanation,
        'options': parse_options(q),
    })


@app.route('/api/session/start', methods=['POST'])
def api_session_start():
    data = request.get_json() or {}
    ss = StudySession(
        mode=data.get('mode', 'practice'),
        day_number=data.get('day_number'),
    )
    db.session.add(ss)
    db.session.commit()
    return jsonify({'session_id': ss.id})


@app.route('/api/session/<int:sid>/end', methods=['POST'])
def api_session_end(sid):
    ss = StudySession.query.get_or_404(sid)
    ss.is_active = False
    ss.ended_at = datetime.utcnow()
    if ss.started_at:
        ss.duration_sec = int((ss.ended_at - ss.started_at).total_seconds())
        update_today_stats(minutes_delta=ss.duration_sec // 60)
    db.session.commit()
    return jsonify({
        'total': ss.total_questions,
        'correct': ss.correct_count,
        'accuracy': calc_accuracy(ss.correct_count, ss.total_questions),
        'duration_sec': ss.duration_sec,
    })


# ── 錯題複習 ─────────────────────────────────────────────────

@app.route('/review')
def review():
    # 今日待複習（next_review_at <= today，尚未熟悉）
    today = date.today()
    due_wqs = WrongQuestion.query.filter_by(is_mastered=False).filter(
        (WrongQuestion.next_review_at <= today) | (WrongQuestion.next_review_at.is_(None))
    ).order_by(WrongQuestion.wrong_count.desc()).all()

    # 近期待複習（future）
    future_wqs = WrongQuestion.query.filter_by(is_mastered=False).filter(
        WrongQuestion.next_review_at > today
    ).order_by(WrongQuestion.next_review_at).all()

    # 已熟悉
    mastered_count = WrongQuestion.query.filter_by(is_mastered=True).count()

    # 取得今日第一題
    current_wq = due_wqs[0] if due_wqs else None
    current_question = current_wq.question if current_wq else None

    return render_template('review.html',
        due_wqs=due_wqs,
        future_wqs=future_wqs,
        mastered_count=mastered_count,
        current_wq=current_wq,
        current_question=current_question,
        options=parse_options(current_question) if current_question else [],
        get_difficulty_label=get_difficulty_label,
        get_difficulty_color=get_difficulty_color,
    )


@app.route('/api/review/master/<int:wq_id>', methods=['POST'])
def api_review_master(wq_id):
    wq = WrongQuestion.query.get_or_404(wq_id)
    wq.is_mastered = True
    db.session.commit()
    return jsonify({'ok': True, 'message': '已標記為熟悉！'})


@app.route('/api/review/next', methods=['GET'])
def api_review_next():
    today = date.today()
    skip_id = request.args.get('skip_id', type=int)
    query = WrongQuestion.query.filter_by(is_mastered=False).filter(
        (WrongQuestion.next_review_at <= today) | (WrongQuestion.next_review_at.is_(None))
    )
    if skip_id:
        query = query.filter(WrongQuestion.id != skip_id)
    wq = query.order_by(WrongQuestion.wrong_count.desc()).first()
    if not wq:
        return jsonify({'done': True})
    q = wq.question
    return jsonify({
        'done': False,
        'wq_id': wq.id,
        'question_id': q.id,
        'stem': q.stem,
        'q_type': q.q_type,
        'options': parse_options(q),
        'difficulty': q.difficulty,
        'wrong_count': wq.wrong_count,
        'tags': q.tags,
    })


# ── 口試模擬 ─────────────────────────────────────────────────

@app.route('/oral')
def oral():
    category_id = request.args.get('category_id', type=int)
    categories = Category.query.order_by(Category.sort_order).all()

    query = Question.query.filter_by(q_type='essay')
    if category_id:
        query = query.filter_by(category_id=category_id)

    from sqlalchemy.sql.expression import func
    question = query.order_by(func.random()).first()

    key_points = parse_key_points(question) if question else []

    return render_template('oral.html',
        question=question,
        key_points=key_points,
        categories=categories,
        category_id=category_id,
    )


@app.route('/api/oral/answer', methods=['POST'])
def api_oral_answer():
    data = request.get_json() or {}
    question_id = data.get('question_id')
    day_number = data.get('day_number')

    q = Question.query.get(question_id)
    if not q:
        return jsonify({'error': 'Not found'}), 404

    ans = UserAnswer(
        question_id=question_id,
        user_answer='essay_attempt',
        is_correct=True,   # essay 視為練習，記為正確
        mode='oral',
        day_number=day_number,
    )
    db.session.add(ans)
    update_today_stats(correct_delta=1, total_delta=1)
    db.session.commit()

    return jsonify({
        'key_points': parse_key_points(q),
        'explanation': q.explanation,
    })


# ── 進度儀表板 ───────────────────────────────────────────────

@app.route('/dashboard')
def dashboard():
    # 過去7天統計
    last7 = []
    for i in range(6, -1, -1):
        d = date.today() - timedelta(days=i)
        s = DailyStats.query.filter_by(stat_date=d).first()
        last7.append({
            'date': d.strftime('%m/%d'),
            'done': s.questions_done if s else 0,
            'correct': s.correct_count if s else 0,
            'minutes': s.study_minutes if s else 0,
        })

    # 分類統計
    categories = Category.query.order_by(Category.sort_order).all()
    cat_stats = []
    for cat in categories:
        q_ids = [q.id for q in cat.questions]
        total = UserAnswer.query.filter(UserAnswer.question_id.in_(q_ids)).count() if q_ids else 0
        correct = UserAnswer.query.filter(UserAnswer.question_id.in_(q_ids), UserAnswer.is_correct == True).count() if q_ids else 0
        cat_stats.append({
            'name': cat.name,
            'total': total,
            'correct': correct,
            'accuracy': round(correct / total * 100, 1) if total else 0,
            'question_count': len(q_ids),
        })

    # 整體統計
    total_answers = UserAnswer.query.count()
    total_correct = UserAnswer.query.filter_by(is_correct=True).count()
    wrong_pending = WrongQuestion.query.filter_by(is_mastered=False).count()
    wrong_mastered = WrongQuestion.query.filter_by(is_mastered=True).count()

    all_stats = DailyStats.query.order_by(DailyStats.stat_date.desc()).all()
    streak = calc_streak(all_stats)
    total_minutes = sum(s.study_minutes for s in all_stats)

    # 30天計劃進度
    plans_done = DailyPlan.query.filter_by(is_completed=True).count()
    current_day = get_current_day_plan()

    return render_template('dashboard.html',
        last7=last7,
        cat_stats=cat_stats,
        total_answers=total_answers,
        total_correct=total_correct,
        wrong_pending=wrong_pending,
        wrong_mastered=wrong_mastered,
        streak=streak,
        total_minutes=total_minutes,
        plans_done=plans_done,
        current_day=current_day,
        accuracy=calc_accuracy(total_correct, total_answers),
    )


@app.route('/api/today-stats')
def api_today_stats():
    stats = get_or_create_today_stats()
    today_start = datetime.combine(date.today(), datetime.min.time())
    today_answers = UserAnswer.query.filter(UserAnswer.answered_at >= today_start).all()
    done = len(today_answers)
    correct = sum(1 for a in today_answers if a.is_correct)

    pending_review = WrongQuestion.query.filter_by(is_mastered=False).filter(
        (WrongQuestion.next_review_at <= date.today()) | (WrongQuestion.next_review_at.is_(None))
    ).count()

    today_plan = get_current_day_plan()

    return jsonify({
        'done': done,
        'correct': correct,
        'accuracy': calc_accuracy(correct, done),
        'streak': stats.streak_days,
        'pending_review': pending_review,
        'today_target': today_plan.target_questions if today_plan else 20,
        'today_plan_title': today_plan.title if today_plan else None,
    })


@app.route('/api/dashboard/stats')
def api_dashboard_stats():
    last7 = []
    for i in range(6, -1, -1):
        d = date.today() - timedelta(days=i)
        s = DailyStats.query.filter_by(stat_date=d).first()
        last7.append({
            'date': d.strftime('%m/%d'),
            'done': s.questions_done if s else 0,
            'correct': s.correct_count if s else 0,
        })
    return jsonify({'last7': last7})


# ── 題庫瀏覽 ─────────────────────────────────────────────────

@app.route('/questions')
def questions():
    category_id = request.args.get('category_id', type=int)
    difficulty = request.args.get('difficulty', type=int)
    q_type = request.args.get('q_type', '')
    tags_filter = request.args.get('tags', '')
    keyword = request.args.get('keyword', '')
    page = request.args.get('page', 1, type=int)

    categories = Category.query.order_by(Category.sort_order).all()

    query = Question.query
    if category_id:
        query = query.filter_by(category_id=category_id)
    if difficulty:
        query = query.filter_by(difficulty=difficulty)
    if q_type:
        query = query.filter_by(q_type=q_type)
    if tags_filter:
        query = query.filter(Question.tags.contains(tags_filter))
    if keyword:
        query = query.filter(Question.stem.contains(keyword))

    total = query.count()
    per_page = 20
    questions_list = query.order_by(Question.id.desc()).offset((page - 1) * per_page).limit(per_page).all()
    total_pages = (total + per_page - 1) // per_page

    return render_template('questions.html',
        questions=questions_list,
        categories=categories,
        category_id=category_id,
        difficulty=difficulty,
        q_type=q_type,
        tags_filter=tags_filter,
        keyword=keyword,
        page=page,
        total=total,
        total_pages=total_pages,
        get_difficulty_label=get_difficulty_label,
        get_difficulty_color=get_difficulty_color,
    )


@app.route('/questions/<int:qid>')
def question_detail(qid):
    q = Question.query.get_or_404(qid)
    options = parse_options(q)
    key_points = parse_key_points(q)
    answers = UserAnswer.query.filter_by(question_id=qid).order_by(UserAnswer.answered_at.desc()).limit(10).all()
    wq = WrongQuestion.query.filter_by(question_id=qid).first()

    return render_template('question_detail.html',
        q=q,
        options=options,
        key_points=key_points,
        answers=answers,
        wq=wq,
        get_difficulty_label=get_difficulty_label,
        get_difficulty_color=get_difficulty_color,
    )


# ── 題庫匯入 ─────────────────────────────────────────────────

@app.route('/admin/import', methods=['GET', 'POST'])
def admin_import():
    categories = Category.query.order_by(Category.sort_order).all()
    result = None

    if request.method == 'POST':
        file = request.files.get('file')
        if not file:
            flash('請選擇檔案', 'danger')
            return redirect(url_for('admin_import'))

        filename = file.filename or ''
        content = file.read().decode('utf-8', errors='replace')
        imported = 0
        errors = []

        if filename.endswith('.json'):
            try:
                data = json.loads(content)
                if isinstance(data, dict):
                    data = [data]
                for i, item in enumerate(data):
                    try:
                        cat_code = item.get('category_code', '')
                        cat = Category.query.filter_by(code=cat_code).first()
                        if not cat:
                            errors.append(f'第{i+1}題：找不到分類 {cat_code}')
                            continue
                        options = item.get('options', [])
                        key_points = item.get('key_points', [])
                        q = Question(
                            category_id=cat.id,
                            q_type=item.get('q_type', 'single'),
                            year=item.get('year'),
                            source=item.get('source', ''),
                            stem=item.get('stem', ''),
                            options_json=json.dumps(options, ensure_ascii=False),
                            answer=item.get('answer', ''),
                            key_points_json=json.dumps(key_points, ensure_ascii=False),
                            explanation=item.get('explanation', ''),
                            difficulty=item.get('difficulty', 2),
                            tags=item.get('tags', ''),
                        )
                        db.session.add(q)
                        imported += 1
                    except Exception as e:
                        errors.append(f'第{i+1}題：{str(e)}')
                db.session.commit()
            except json.JSONDecodeError as e:
                errors.append(f'JSON 格式錯誤：{str(e)}')

        elif filename.endswith('.csv'):
            reader = csv.DictReader(io.StringIO(content))
            for i, row in enumerate(reader):
                try:
                    cat_code = row.get('category_code', '')
                    cat = Category.query.filter_by(code=cat_code).first()
                    if not cat:
                        errors.append(f'第{i+1}行：找不到分類 {cat_code}')
                        continue
                    # Parse options from CSV (A,B,C,D columns)
                    options = []
                    for key in ['A', 'B', 'C', 'D', 'E']:
                        text = row.get(f'option_{key}', '').strip()
                        if text:
                            options.append({'key': key, 'text': text})
                    q = Question(
                        category_id=cat.id,
                        q_type=row.get('q_type', 'single'),
                        year=int(row['year']) if row.get('year') else None,
                        source=row.get('source', ''),
                        stem=row.get('stem', ''),
                        options_json=json.dumps(options, ensure_ascii=False),
                        answer=row.get('answer', ''),
                        explanation=row.get('explanation', ''),
                        difficulty=int(row.get('difficulty', 2)),
                        tags=row.get('tags', ''),
                    )
                    db.session.add(q)
                    imported += 1
                except Exception as e:
                    errors.append(f'第{i+1}行：{str(e)}')
            db.session.commit()
        else:
            errors.append('僅支援 .json 或 .csv 格式')

        result = {'imported': imported, 'errors': errors}

    return render_template('import.html',
        categories=categories,
        result=result,
    )


# ── 主程式 ───────────────────────────────────────────────────

if __name__ == '__main__':
    port = app.config.get('PORT', 5011)
    app.run(host='0.0.0.0', port=port, debug=False)
