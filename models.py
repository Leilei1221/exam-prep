from __future__ import annotations
from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30), unique=True, nullable=False)   # exam_senior / exam_junior / technician / curriculum108
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, default='')
    sort_order = db.Column(db.Integer, default=0)
    questions = db.relationship('Question', backref='category', lazy=True)


class Question(db.Model):
    __tablename__ = 'questions'
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    q_type = db.Column(db.String(20), nullable=False, default='single')  # single / multiple / essay
    year = db.Column(db.Integer, nullable=True)
    source = db.Column(db.String(100), default='')
    stem = db.Column(db.Text, nullable=False)
    options_json = db.Column(db.Text, default='[]')     # [{"key":"A","text":"..."}]
    answer = db.Column(db.String(20), nullable=False)   # "A" or "A,B" for multiple or key points marker
    key_points_json = db.Column(db.Text, default='[]')  # essay key points array
    explanation = db.Column(db.Text, default='')
    difficulty = db.Column(db.Integer, default=2)       # 1=easy 2=medium 3=hard
    tags = db.Column(db.String(200), default='')        # comma-separated
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    answers = db.relationship('UserAnswer', backref='question', lazy=True)


class UserAnswer(db.Model):
    __tablename__ = 'user_answers'
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    user_answer = db.Column(db.String(50), default='')
    is_correct = db.Column(db.Boolean, default=False)
    answered_at = db.Column(db.DateTime, default=datetime.utcnow)
    mode = db.Column(db.String(20), default='practice')  # practice / review / exam / oral
    session_id = db.Column(db.Integer, db.ForeignKey('study_sessions.id'), nullable=True)
    day_number = db.Column(db.Integer, nullable=True)


class DailyPlan(db.Model):
    __tablename__ = 'daily_plans'
    id = db.Column(db.Integer, primary_key=True)
    day_number = db.Column(db.Integer, unique=True, nullable=False)  # 1-30
    title = db.Column(db.String(200), nullable=False)
    key_points = db.Column(db.Text, default='')         # comma-separated tags
    target_questions = db.Column(db.Integer, default=20)
    is_review_day = db.Column(db.Boolean, default=False)
    category_codes = db.Column(db.String(200), default='')  # comma-separated category codes
    plan_date = db.Column(db.Date, nullable=True)        # set after user sets start date
    is_completed = db.Column(db.Boolean, default=False)
    notes = db.Column(db.Text, default='')


class StudySession(db.Model):
    __tablename__ = 'study_sessions'
    id = db.Column(db.Integer, primary_key=True)
    mode = db.Column(db.String(20), default='practice')  # practice / review / exam / oral
    day_number = db.Column(db.Integer, nullable=True)
    total_questions = db.Column(db.Integer, default=0)
    correct_count = db.Column(db.Integer, default=0)
    duration_sec = db.Column(db.Integer, default=0)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    ended_at = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    answers = db.relationship('UserAnswer', backref='study_session', lazy=True)


class WrongQuestion(db.Model):
    __tablename__ = 'wrong_questions'
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), unique=True, nullable=False)
    wrong_count = db.Column(db.Integer, default=1)
    last_wrong_at = db.Column(db.DateTime, default=datetime.utcnow)
    next_review_at = db.Column(db.Date, nullable=True)
    is_mastered = db.Column(db.Boolean, default=False)
    question = db.relationship('Question', lazy=True)


class DailyStats(db.Model):
    __tablename__ = 'daily_stats'
    id = db.Column(db.Integer, primary_key=True)
    stat_date = db.Column(db.Date, unique=True, nullable=False)
    questions_done = db.Column(db.Integer, default=0)
    correct_count = db.Column(db.Integer, default=0)
    study_minutes = db.Column(db.Integer, default=0)
    streak_days = db.Column(db.Integer, default=0)
