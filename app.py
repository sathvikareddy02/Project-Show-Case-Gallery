from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
import os
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'supersecretkey'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'png', 'jpg', 'jpeg', 'gif'}

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def init_db():
    with sqlite3.connect('database.db') as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE,
                password TEXT,
                role TEXT
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY,
                title TEXT,
                description TEXT,
                file TEXT,
                status TEXT,
                user_id INTEGER
            )
        ''')

@app.route('/')
def index():
    with sqlite3.connect('database.db') as conn:
        projects = conn.execute('SELECT * FROM projects WHERE status="approved"').fetchall()
    return render_template('index.html', projects=projects)

@app.route('/browse')
def browse():
    query = request.args.get('q', '').strip().lower()
    with sqlite3.connect('database.db') as conn:
        if query:
            projects = conn.execute('''
                SELECT * FROM projects
                WHERE status="approved" AND 
                      (LOWER(title) LIKE ? OR LOWER(description) LIKE ?)
            ''', (f'%{query}%', f'%{query}%')).fetchall()
        else:
            projects = conn.execute('SELECT * FROM projects WHERE status="approved"').fetchall()
    return render_template('browse.html', projects=projects, query=query)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        role = 'student'
        try:
            with sqlite3.connect('database.db') as conn:
                conn.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
                             (username, password, role))
            flash('Registration successful! Please login.')
            return redirect(url_for('login'))
        except:
            flash('Username already exists.')
            return redirect(url_for('register'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        with sqlite3.connect('database.db') as conn:
            user = conn.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
            if user and check_password_hash(user[2], password):
                session['user_id'] = user[0]
                session['username'] = user[1]
                session['role'] = user[3]
                flash('Logged in successfully!')
                return redirect(url_for('index'))
            flash('Invalid credentials.')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.')
    return redirect(url_for('login'))

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        file = request.files['file']

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            with sqlite3.connect('database.db') as conn:
                cur = conn.cursor()
                cur.execute('''
                    INSERT INTO projects (title, description, file, status, user_id)
                    VALUES (?, ?, ?, ?, ?)''',
                    (title, description, filename, 'approved', session['user_id']))
                project_id = cur.lastrowid
                project = conn.execute('SELECT * FROM projects WHERE id=?', (project_id,)).fetchone()

            flash('Project uploaded successfully.')

            with sqlite3.connect('database.db') as conn:
                approved_projects = conn.execute('SELECT * FROM projects WHERE status="approved"').fetchall()

            return render_template('index.html', projects=approved_projects, new_project=project)

        else:
            flash('Invalid file type. Only PDF, DOC, DOCX, and images (PNG, JPG, JPEG, GIF) are allowed.')
            return redirect(url_for('upload'))

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
    flash('Project approved.')
    return redirect(url_for('admin'))

@app.route('/project/<int:id>')
def project_detail(id):
    with sqlite3.connect('database.db') as conn:
        project = conn.execute('SELECT * FROM projects WHERE id=?', (id,)).fetchone()
    return render_template('project_detail.html', project=project)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/delete/<int:id>', methods=['POST'])
def delete(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    with sqlite3.connect('database.db') as conn:
        project = conn.execute('SELECT * FROM projects WHERE id=?', (id,)).fetchone()

        if session['role'] == 'admin' or (project and project[5] == session['user_id']):
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], project[3])
            if os.path.exists(file_path):
                os.remove(file_path)
            conn.execute('DELETE FROM projects WHERE id=?', (id,))
            flash('Project deleted successfully.')
        else:
            flash('Unauthorized action.')

    return redirect(url_for('index'))

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    with sqlite3.connect('database.db') as conn:
        cur = conn.cursor()
        project = cur.execute('SELECT * FROM projects WHERE id=?', (id,)).fetchone()

        if not project or (session['role'] != 'admin' and project[5] != session['user_id']):
            flash('Unauthorized access.')
            return redirect(url_for('index'))

        if request.method == 'POST':
            title = request.form['title']
            description = request.form['description']
            cur.execute('UPDATE projects SET title=?, description=? WHERE id=?', (title, description, id))
            flash('Project updated successfully.')
            return redirect(url_for('project_detail', id=id))

    return render_template('edit.html', project=project)

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
