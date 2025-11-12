from flask import Flask, render_template, request, redirect, url_for, session
import os
import sqlite3

app = Flask(__name__)
app.secret_key = 'supersecretkey'
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# Database setup

def init_db():
    with sqlite3.connect('database.db') as conn:
        conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT
        )''')

        conn.execute('''
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY,
            title TEXT,
            description TEXT,
            file TEXT,
            status TEXT,
            user_id INTEGER
        )''')


@app.route('/')
def index():
    with sqlite3.connect('database.db') as conn:
        projects = conn.execute('SELECT * FROM projects WHERE status="approved"').fetchall()
    return render_template('index.html', projects=projects)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = 'student'
        with sqlite3.connect('database.db') as conn:
            try:
                conn.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
                             (username, password, role))
                return redirect(url_for('login'))
            except:
                return 'Username already exists'
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        with sqlite3.connect('database.db') as conn:
            user = conn.execute('SELECT * FROM users WHERE username=? AND password=?',
                                (username, password)).fetchone()
            if user:
                session['user_id'] = user[0]
                session['username'] = user[1]
                session['role'] = user[3]
                return redirect(url_for('index'))
            return 'Invalid credentials'
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        file = request.files['file']
        filename = file.filename
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        with sqlite3.connect('database.db') as conn:
            conn.execute('INSERT INTO projects (title, description, file, status, user_id) VALUES (?, ?, ?, ?, ?)',
                         (title, description, filename, "pending", session['user_id']))
        return redirect(url_for('index'))
    return render_template('upload.html')

@app.route('/admin')
def admin():
    if session.get('role') != 'admin':
        return 'Access denied'
    with sqlite3.connect('database.db') as conn:
        projects = conn.execute('SELECT * FROM projects').fetchall()
    return render_template('admin.html', projects=projects)

@app.route('/approve/<int:id>')
def approve(id):
    if session.get('role') != 'admin':
        return 'Access denied'
    with sqlite3.connect('database.db') as conn:
        conn.execute('UPDATE projects SET status="approved" WHERE id=?', (id,))
    return redirect(url_for('admin'))

@app.route('/project/<int:id>')
def project_detail(id):
    with sqlite3.connect('database.db') as conn:
        project = conn.execute('SELECT * FROM projects WHERE id=?', (id,)).fetchone()
    return render_template('project_detail.html', project=project)

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
