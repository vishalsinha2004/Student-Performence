import io
import csv
from flask import Flask, render_template, request, redirect, url_for, session, Response, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import joblib
import pandas as pd
import os

# --- NEW: Import our custom chatbot logic ---
from chatbot import get_ai_response
from chatbot import get_ai_response, generate_timetable

app = Flask(__name__)
app.secret_key = 'edupredict_secret_2026'

# Load ML models
try:
    linear_model = joblib.load('models/linear_model.pkl')
    logistic_model = joblib.load('models/logistic_model.pkl')
except Exception as e:
    print(f"Error loading models: {e}")

def init_db():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, email TEXT UNIQUE, password TEXT, role TEXT DEFAULT 'student', created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS predictions (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, hours REAL, scores REAL, sleep REAL, papers REAL, predicted_score REAL, result TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS todos (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, task TEXT, is_completed BOOLEAN DEFAULT 0, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def home():
    is_logged_in = 'user' in session
    return render_template('landing.html', logged_in=is_logged_in)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username=?", (username,))
        user = cursor.fetchone()
        conn.close()
        
        if user and check_password_hash(user[3], password): 
            session['user'] = username
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error="Invalid Credentials")
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form.get('email', f"{username}@example.com") 
        password = request.form['password']
        hashed_password = generate_password_hash(password)
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)", (username, email, hashed_password))
            conn.commit()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            return render_template('signup.html', error="Username or Email already exists!")
        finally:
            conn.close()
    return render_template('signup.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/index')
def index():
    if 'user' not in session: return redirect(url_for('login'))
    return render_template('index.html', username=session['user'])

@app.route('/todo')
def todo():
    if 'user' not in session: return redirect(url_for('login'))
    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM todos WHERE username=? ORDER BY is_completed ASC, timestamp DESC", (session['user'],))
    todos = cursor.fetchall()
    conn.close()
    return render_template('todo.html', username=session['user'], todos=todos)

@app.route('/add_todo', methods=['POST'])
def add_todo():
    if 'user' not in session: return redirect(url_for('login'))
    task = request.form.get('task')
    if task:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO todos (username, task) VALUES (?, ?)", (session['user'], task))
        conn.commit()
        conn.close()
    return redirect(url_for('todo'))

@app.route('/toggle_todo/<int:todo_id>', methods=['POST'])
def toggle_todo(todo_id):
    if 'user' not in session: return redirect(url_for('login'))
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE todos SET is_completed = NOT is_completed WHERE id=? AND username=?", (todo_id, session['user']))
    conn.commit()
    conn.close()
    return redirect(url_for('todo'))

@app.route('/delete_todo/<int:todo_id>', methods=['POST'])
def delete_todo(todo_id):
    if 'user' not in session: return redirect(url_for('login'))
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM todos WHERE id=? AND username=?", (todo_id, session['user']))
    conn.commit()
    conn.close()
    return redirect(url_for('todo'))

@app.route('/predict', methods=['POST'])
def predict():
    if 'user' not in session: return redirect(url_for('login'))
    hours = float(request.form['hours'])
    scores = float(request.form['scores'])
    sleep = float(request.form['sleep'])
    papers = float(request.form['papers'])

    data = pd.DataFrame([[hours, scores, sleep, papers]], columns=['Hours Studied', 'Previous Scores', 'Sleep Hours', 'Sample Question Papers Practiced'])
    predicted_score = round(min(max(linear_model.predict(data)[0], 0), 100), 2)
    is_high = logistic_model.predict(data)[0]
    result_text = "High Performer (>=70)" if is_high == 1 else "Needs Improvement (<70)"

    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('''INSERT INTO predictions (username, hours, scores, sleep, papers, predicted_score, result) VALUES (?, ?, ?, ?, ?, ?, ?)''', (session['user'], hours, scores, sleep, papers, predicted_score, result_text))
    conn.commit()
    conn.close()

    return render_template('result.html', prediction=predicted_score, result=result_text, hours=hours, scores=scores, sleep=sleep, papers=papers, username=session['user'])

@app.route('/all_predictions')
def all_predictions():
    if 'user' not in session: return redirect(url_for('login'))
    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row 
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM predictions WHERE username=? ORDER BY timestamp DESC", (session['user'],))
    records = cursor.fetchall()
    conn.close()
    return render_template('all_predictions.html', records=records, username=session['user'])

@app.route('/export_csv')
def export_csv():
    if 'user' not in session: return redirect(url_for('login'))
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("SELECT hours, scores, sleep, papers, predicted_score, result, timestamp FROM predictions WHERE username=? ORDER BY timestamp DESC", (session['user'],))
    records = cursor.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Hours Studied', 'Past Score', 'Sleep (Hrs)', 'Papers Practiced', 'Predicted Score (%)', 'Target Status', 'Date & Time'])
    for row in records: writer.writerow(row)

    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": f"attachment;filename={session['user']}_study_data.csv"})

# --- UPDATED CHAT ROUTE ---
@app.route('/chat', methods=['POST'])
def chat():
    if 'user' not in session: 
        return jsonify({"response": "Please log in to use the chat assistant."}), 401
        
    user_msg = request.json.get('message', '')
    username = session['user']
    
    # Send to the chatbot.py file to handle the Groq AI
    response_text = get_ai_response(user_msg, username)
    
    return jsonify({"response": response_text})

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

@app.route('/timetable')
def timetable():
    if 'user' not in session: return redirect(url_for('login'))
    return render_template('timetable.html', username=session['user'])

@app.route('/api/generate_plan', methods=['POST'])
def api_generate_plan():
    if 'user' not in session: return jsonify({"error": "Unauthorized"}), 401
    
    # Grab the subject typed by the user
    user_subject = request.json.get('subject', 'General Studies')
    
    # Fetch the user's latest prediction from the database
    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM predictions WHERE username=? ORDER BY timestamp DESC LIMIT 1", (session['user'],))
    row = cursor.fetchone()
    conn.close()

    # If they haven't made a prediction yet
    if not row:
        error_html = """
        <div style='text-align:center; padding: 20px;'>
            <h2 style='color:#ff4f8b; margin-bottom:15px;'>No Data Found! 🛑</h2>
            <p>Please make a prediction on the Dashboard first so the AI can analyze your habits.</p>
        </div>
        """
        return jsonify({"html": error_html})

    # Prepare metrics for the AI
    metrics = {
        'hours': row['hours'],
        'scores': row['scores'],
        'sleep': row['sleep'],
        'predicted_score': row['predicted_score'],
        'result': row['result']
    }

    # Generate HTML from Llama 3.1, passing the subject along!
    plan_html = generate_timetable(session['user'], metrics, user_subject)
    
    return jsonify({"html": plan_html})

if __name__ == '__main__':
    app.run(debug=True)