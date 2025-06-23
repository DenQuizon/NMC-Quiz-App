import os
import random
import time
import json
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

# --- Basic App Setup ---
basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)
app.config['SECRET_KEY'] = 'a-very-secret-key-that-no-one-would-guess'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'quiz_app.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- DATABASE MODELS ---

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_supporter = db.Column(db.Boolean, default=False, nullable=False)
    saved_quiz_ids = db.Column(db.String, nullable=True)
    saved_quiz_index = db.Column(db.Integer, nullable=True)
    saved_quiz_score = db.Column(db.Integer, nullable=True)
    marked_for_review = db.Column(db.Text, nullable=True) 

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question_text = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.String(200), nullable=False)
    option_b = db.Column(db.String(200), nullable=False)
    option_c = db.Column(db.String(200), nullable=False)
    option_d = db.Column(db.String(200), nullable=False)
    correct_answer = db.Column(db.String(1), nullable=False)
    explanation = db.Column(db.Text, nullable=True)
    topic = db.Column(db.String(100), nullable=True)
    difficulty = db.Column(db.String(50), nullable=True)
    source = db.Column(db.String(200), nullable=True)

class AnswerAttempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_answer = db.Column(db.String(10), nullable=False)
    is_correct = db.Column(db.Boolean, nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    quiz_history_id = db.Column(db.Integer, db.ForeignKey('quiz_history.id'), nullable=False)
    question = db.relationship('Question')

class QuizHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    total_questions = db.Column(db.Integer, nullable=False)
    date_taken = db.Column(db.DateTime, server_default=db.func.now())
    topic = db.Column(db.String(100))
    attempts = db.relationship('AnswerAttempt', backref='quiz', lazy='dynamic')
    
class UserAnswered(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)

# --- WEB ROUTES ---

@app.route('/')
def index():
    if 'username' in session:
        user = User.query.filter_by(username=session['username']).first()
        if user is None: return redirect(url_for('logout'))
        answered_count = UserAnswered.query.filter_by(user_id=user.id).count()
        total_question_count = Question.query.count()
        has_saved_quiz = bool(user.saved_quiz_ids)
        return render_template('index.html', user=user, answered_count=answered_count, total_question_count=total_question_count, has_saved_quiz=has_saved_quiz)
    else:
        return redirect(url_for('signup'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username, password = request.form['username'], request.form['password']
        if User.query.filter_by(username=username).first():
            flash('Username already exists. Please choose a different name or login.', 'error')
            return redirect(url_for('signup'))
        new_user = User(username=username, password_hash=generate_password_hash(password))
        db.session.add(new_user)
        db.session.commit()
        flash('Account created successfully! Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username, password = request.form['username'], request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session['username'] = user.username
            flash(f'Welcome back, {user.username}!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password.', 'error')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been successfully logged out.', 'success')
    return redirect(url_for('login'))

@app.route('/new', methods=['GET', 'POST'])
def new_test():
    if 'username' not in session: return redirect(url_for('login'))
    user = User.query.filter_by(username=session['username']).first()
    if not user: return redirect(url_for('logout'))

    if request.method == 'POST':
        topic, difficulty = request.form['topic'], request.form['difficulty']
        num_questions = int(request.form['num_questions'])
        
        answered_question_ids = [ua.question_id for ua in UserAnswered.query.filter_by(user_id=user.id).all()]
        query = Question.query
        if topic != 'all': query = query.filter_by(topic=topic)
        if difficulty != 'all': query = query.filter_by(difficulty=difficulty)
        query = query.filter(Question.id.notin_(answered_question_ids))
        available_questions = query.all()
        random.shuffle(available_questions)
        final_questions = available_questions[:num_questions]
        question_ids = [str(q.id) for q in final_questions]

        if not question_ids:
            flash("No new questions found for the selected criteria.", 'error')
            return redirect(url_for('new_test'))
            
        new_history_entry = QuizHistory(user_id=user.id, score=0, total_questions=len(final_questions), topic=topic if topic != 'all' else "All Topics")
        db.session.add(new_history_entry)
        
        user.saved_quiz_ids = ",".join(question_ids)
        user.saved_quiz_index, user.saved_quiz_score = 0, 0
        user.marked_for_review = json.dumps([]) 
        db.session.commit()

        session['quiz_history_id'] = new_history_entry.id
        session['timer_enabled'] = False # Timer feature removed for now
        session.pop('review_mode', None)
        
        return redirect(url_for('quiz_page'))

    topics_from_db = db.session.query(Question.topic.distinct()).order_by(Question.topic).all()
    topics = [topic[0] for topic in topics_from_db if topic[0] and topic[0].strip()]
    difficulties_from_db = db.session.query(Question.difficulty.distinct()).order_by(Question.difficulty).all()
    difficulties = [difficulty[0] for difficulty in difficulties_from_db if difficulty[0] and difficulty[0].strip()]
    return render_template('new_test.html', topics=topics, difficulties=difficulties)

@app.route('/quiz', methods=['GET', 'POST'])
def quiz_page():
    if 'username' not in session: return redirect(url_for('login'))
    user = User.query.filter_by(username=session['username']).first()
    if not user or not user.saved_quiz_ids: return redirect(url_for('new_test'))
    
    # --- THIS IS THE BUG FIX ---
    # If we are resuming a quiz, the history ID might not be in the session.
    # So, we create a new one to store the upcoming answer attempts.
    if 'quiz_history_id' not in session:
        question_ids_list = [int(id_str) for id_str in user.saved_quiz_ids.split(',')]
        temp_history = QuizHistory(
            user_id=user.id, 
            score=user.saved_quiz_score, 
            total_questions=len(question_ids_list), 
            topic="Resumed Quiz"
        )
        db.session.add(temp_history)
        db.session.commit()
        session['quiz_history_id'] = temp_history.id
        flash("Resuming your previous quiz.", "success")
    # --- END OF BUG FIX ---
    
    quiz_history_id = session.get('quiz_history_id')
    question_ids = [int(id_str) for id_str in user.saved_quiz_ids.split(',')]
    current_index = user.saved_quiz_index
    question = Question.query.get(question_ids[current_index])

    if request.method == 'POST':
        user_answer = request.form.get('answer')
        if not user_answer:
            flash("Please select an answer.", 'error')
            return redirect(url_for('quiz_page'))

        attempt = AnswerAttempt.query.filter_by(quiz_history_id=quiz_history_id, question_id=question.id).first()
        if not attempt: attempt = AnswerAttempt(question_id=question.id, quiz_history_id=quiz_history_id)
        
        is_correct = (user_answer == question.correct_answer)
        # Update score only if the answer is newly correct
        was_previously_correct = attempt.is_correct
        if is_correct and not was_previously_correct:
            user.saved_quiz_score += 1
        elif not is_correct and was_previously_correct:
            user.saved_quiz_score -= 1
        
        attempt.user_answer, attempt.is_correct = user_answer, is_correct
        db.session.add(attempt)
        db.session.commit()
        
        review_mode = session.get('review_mode', False)
        return render_template('result.html',is_correct=is_correct,correct_answer=question.correct_answer,explanation=question.explanation,source=question.source, review_mode=review_mode)

    marked_ids = json.loads(user.marked_for_review or '[]')
    is_marked = question.id in marked_ids
    previous_attempt = AnswerAttempt.query.filter_by(quiz_history_id=quiz_history_id, question_id=question.id).first()
    previous_answer = previous_attempt.user_answer if previous_attempt else None
    return render_template('quiz.html',question=question,current_q_number=current_index + 1,total_questions=len(question_ids), is_marked=is_marked, previous_answer=previous_answer)

@app.route('/mark/<int:question_id>', methods=['POST'])
def mark_question(question_id):
    if 'username' not in session: return redirect(url_for('login'))
    user = User.query.filter_by(username=session['username']).first()
    if not user: return redirect(url_for('logout'))

    selected_option = request.form.get('selected_option')
    if selected_option:
        quiz_history_id = session.get('quiz_history_id')
        attempt = AnswerAttempt.query.filter_by(quiz_history_id=quiz_history_id, question_id=question_id).first()
        if not attempt:
            attempt = AnswerAttempt(question_id=question_id, quiz_history_id=quiz_history_id, is_correct=False, user_answer=selected_option)
        else:
            attempt.user_answer = selected_option
        db.session.add(attempt)

    marked_ids = json.loads(user.marked_for_review or '[]')
    if question_id in marked_ids: marked_ids.remove(question_id)
    else: marked_ids.append(question_id)
    user.marked_for_review = json.dumps(marked_ids)
    db.session.commit()
    return redirect(url_for('quiz_page'))

@app.route('/next')
def next_question():
    if 'username' not in session: return redirect(url_for('login'))
    user = User.query.filter_by(username=session['username']).first()
    if not user or not user.saved_quiz_ids: return redirect(url_for('new_test'))
    if session.get('review_mode'):
        session.pop('review_mode', None)
        return redirect(url_for('quiz_summary'))
    
    user.saved_quiz_index += 1
    question_ids = [int(id_str) for id_str in user.saved_quiz_ids.split(',')]
    if user.saved_quiz_index >= len(question_ids):
        return redirect(url_for('quiz_summary'))
    
    db.session.commit()
    return redirect(url_for('quiz_page'))

@app.route('/summary')
def quiz_summary():
    if 'username' not in session: return redirect(url_for('login'))
    user = User.query.filter_by(username=session['username']).first()
    if not user or not user.saved_quiz_ids: return redirect(url_for('new_test'))

    question_ids = [int(id_str) for id_str in user.saved_quiz_ids.split(',')]
    marked_ids = json.loads(user.marked_for_review or '[]')
    
    questions_for_summary = []
    for i, q_id in enumerate(question_ids):
        questions_for_summary.append({'number': i + 1, 'id': q_id, 'is_marked': q_id in marked_ids})
    return render_template('summary.html', questions=questions_for_summary)

@app.route('/jump_to/<int:question_index>')
def jump_to_question(question_index):
    if 'username' not in session: return redirect(url_for('login'))
    user = User.query.filter_by(username=session['username']).first()
    if not user or not user.saved_quiz_ids: return redirect(url_for('new_test'))
    
    user.saved_quiz_index = question_index
    session['review_mode'] = True
    db.session.commit()
    return redirect(url_for('quiz_page'))

@app.route('/finish', methods=['POST'])
def finish_quiz():
    if 'username' not in session: return redirect(url_for('login'))
    user = User.query.filter_by(username=session['username']).first()
    if not user or not user.saved_quiz_ids: return redirect(url_for('new_test'))
    
    quiz_history_id = session.get('quiz_history_id')
    
    question_ids = [int(id_str) for id_str in user.saved_quiz_ids.split(',')]
    total_questions = len(question_ids)
    
    # Ensure every question has an answer attempt before finishing
    for q_id in question_ids:
        attempt = AnswerAttempt.query.filter_by(quiz_history_id=quiz_history_id, question_id=q_id).first()
        if not attempt:
            attempt = AnswerAttempt(user_answer='skipped', is_correct=False, question_id=q_id, quiz_history_id=quiz_history_id)
            db.session.add(attempt)
    db.session.commit()

    final_score = AnswerAttempt.query.filter_by(quiz_history_id=quiz_history_id, is_correct=True).count()
    if quiz_history_id:
        quiz_history = QuizHistory.query.get(quiz_history_id)
        if quiz_history:
            quiz_history.score = final_score
    
    for q_id in question_ids:
        answered_record = UserAnswered(user_id=user.id, question_id=q_id)
        db.session.add(answered_record)
    
    user.saved_quiz_ids, user.saved_quiz_index, user.saved_quiz_score, user.marked_for_review = None, None, None, None
    db.session.commit()
    
    session.clear()
    session['username'] = user.username # Keep user logged in

    return render_template('quiz_complete.html', score=final_score, total_questions=total_questions)

@app.route('/history')
def history():
    if 'username' not in session: return redirect(url_for('login'))
    user = User.query.filter_by(username=session['username']).first()
    if not user: return redirect(url_for('logout'))
    user_quizzes = QuizHistory.query.filter_by(user_id=user.id).order_by(QuizHistory.date_taken.desc()).all()
    return render_template('history.html', quizzes=user_quizzes)

@app.route('/review/<int:quiz_id>')
def review_page(quiz_id):
    if 'username' not in session: return redirect(url_for('login'))
    user = User.query.filter_by(username=session['username']).first()
    quiz_history = QuizHistory.query.get_or_404(quiz_id)
    if not user or quiz_history.user_id != user.id:
        flash("You do not have permission to view this quiz.", 'error')
        return redirect(url_for('history'))
    incorrect_attempts = quiz_history.attempts.filter_by(is_correct=False).all()
    return render_template('review.html', incorrect_attempts=incorrect_attempts, quiz=quiz_history)

@app.route('/reset', methods=['POST'])
def reset_progress():
    if 'username' not in session: return redirect(url_for('login'))
    user = User.query.filter_by(username=session['username']).first()
    if user:
        UserAnswered.query.filter_by(user_id=user.id).delete()
        user.saved_quiz_ids, user.saved_quiz_index, user.saved_quiz_score, user.marked_for_review = None, None, None, None
        db.session.commit()
        flash('Your progress has been reset! You can now answer all questions again.', 'success')
    return redirect(url_for('index'))
