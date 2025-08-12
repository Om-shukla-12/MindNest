from flask import Flask, render_template, request, redirect, url_for, session, Response
from datetime import datetime
from models.nlp_analysis import analyze_text, get_suggestion
from models.db_models import db, JournalEntry, User
import csv
from functools import wraps
from deepface import DeepFace
import os
from flask import flash
import base64
from io import BytesIO
from PIL import Image

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///journal.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'your_secret_key_here'  # Change this to a strong secret in production

db.init_app(app)

# Simple user credentials (for demo; use a database in production)
USERNAME = 'user'
PASSWORD = 'pass123'

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
@login_required
def home():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
@login_required
def analyze():
    entry = request.form['entry']
    result = analyze_text(entry)
    new_entry = JournalEntry(
        text=entry,
        sentiment=result['mood'],
        emotion=result.get('emotion', 'N/A'),
        suggestion=result['suggestion']
    )
    db.session.add(new_entry)
    db.session.commit()
    return render_template('result.html', result=result, text=entry)

@app.route('/dashboard')
@login_required
def dashboard():
    entries = JournalEntry.query.order_by(JournalEntry.timestamp).all()
    dates = [entry.timestamp.strftime('%Y-%m-%d') for entry in entries]
    moods = [entry.sentiment for entry in entries]
    emotions = [entry.emotion for entry in entries]
    return render_template('dashboard.html', dates=dates, moods=moods, emotions=emotions)

@app.route('/history')
@login_required
def history():
    entries = JournalEntry.query.order_by(JournalEntry.timestamp.desc()).all()
    return render_template('history.html', entries=entries)

@app.route('/delete/<int:entry_id>', methods=['POST'])
@login_required
def delete_entry(entry_id):
    entry = JournalEntry.query.get_or_404(entry_id)
    db.session.delete(entry)
    db.session.commit()
    return ('', 204)

@app.route('/edit/<int:entry_id>', methods=['GET', 'POST'])
@login_required
def edit_entry(entry_id):
    entry = JournalEntry.query.get_or_404(entry_id)
    if request.method == 'POST':
        entry.text = request.form['entry']
        # Re-analyze the updated text
        result = analyze_text(entry.text)
        entry.sentiment = result['mood']
        entry.emotion = result.get('emotion', 'N/A')
        entry.suggestion = result['suggestion']
        db.session.commit()
        return render_template('result.html', result=result, text=entry.text)
    return render_template('edit.html', entry=entry)

@app.route('/export')
@login_required
def export_csv():
    entries = JournalEntry.query.order_by(JournalEntry.timestamp.desc()).all()
    def generate():
        data = [['Date', 'Entry', 'Mood', 'Emotion', 'Suggestion']]
        for e in entries:
            data.append([
                e.timestamp.strftime('%Y-%m-%d %H:%M'),
                e.text,
                e.sentiment,
                e.emotion,
                e.suggestion
            ])
        for row in data:
            yield ','.join('"' + str(item).replace('"', '""') + '"' for item in row) + '\n'
    return Response(generate(), mimetype='text/csv', headers={"Content-Disposition": "attachment;filename=journal_entries.csv"})

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            session['logged_in'] = True
            session['user_id'] = user.id
            return redirect(url_for('home'))
        else:
            error = 'Invalid username or password.'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        if password != confirm_password:
            error = 'Passwords do not match.'
        elif User.query.filter_by(username=username).first():
            error = 'Username already exists.'
        elif User.query.filter_by(email=email).first():
            error = 'Email already registered.'
        else:
            new_user = User(username=username, email=email, password=password)
            db.session.add(new_user)
            db.session.commit()
            return redirect(url_for('login'))
    return render_template('register.html', error=error)

@app.route('/analyze_face', methods=['GET', 'POST'])
@login_required
def analyze_face():
    emotion = None
    suggestion = None
    if request.method == 'POST':
        # Handle webcam image (base64)
        if 'webcam_image' in request.form and request.form['webcam_image']:
            img_data = request.form['webcam_image']
            header, encoded = img_data.split(',', 1)
            img_bytes = base64.b64decode(encoded)
            image = Image.open(BytesIO(img_bytes))
            upload_folder = os.path.join('static', 'uploads')
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder)
            filepath = os.path.join(upload_folder, 'webcam_capture.png')
            image.save(filepath)
            try:
                result = DeepFace.analyze(img_path=filepath, actions=['emotion'], enforce_detection=False)
                if isinstance(result, list):
                    emotion = result[0].get('dominant_emotion', 'No face detected')
                else:
                    emotion = result.get('dominant_emotion', 'No face detected')
                if emotion and emotion != 'No face detected':
                    suggestion = get_suggestion(emotion)
                    # Save to history
                    new_entry = JournalEntry(
                        text='Webcam Entry',
                        sentiment='N/A',
                        emotion=emotion,
                        suggestion=suggestion
                    )
                    db.session.add(new_entry)
                    db.session.commit()
            except Exception as e:
                flash(f'Error analyzing image: {e}')
            os.remove(filepath)
        # Handle file upload
        elif 'face_image' in request.files:
            file = request.files['face_image']
            if file.filename == '':
                flash('No selected file')
                return redirect(request.url)
            if file:
                upload_folder = os.path.join('static', 'uploads')
                if not os.path.exists(upload_folder):
                    os.makedirs(upload_folder)
                filepath = os.path.join(upload_folder, file.filename)
                file.save(filepath)
                try:
                    result = DeepFace.analyze(img_path=filepath, actions=['emotion'], enforce_detection=False)
                    if isinstance(result, list):
                        emotion = result[0].get('dominant_emotion', 'No face detected')
                    else:
                        emotion = result.get('dominant_emotion', 'No face detected')
                    if emotion and emotion != 'No face detected':
                        suggestion = get_suggestion(emotion)
                except Exception as e:
                    flash(f'Error analyzing image: {e}')
                os.remove(filepath)
    return render_template('analyze_face.html', emotion=emotion, suggestion=suggestion)

if __name__ == '__main__':
    app.run(debug=True)