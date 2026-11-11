import os

# Create templates folder
os.makedirs('templates', exist_ok=True)

# 1. database.sql
with open('database.sql', 'w', encoding='utf-8') as f:
    f.write("""CREATE DATABASE IF NOT EXISTS ideabridge_db;
USE ideabridge_db;

DROP TABLE IF EXISTS increments;
DROP TABLE IF EXISTS problem_collaborators;
DROP TABLE IF EXISTS problems;
DROP TABLE IF EXISTS users;

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    role ENUM('provider', 'solver') NOT NULL,
    org_name VARCHAR(150),
    skills TEXT
);

CREATE TABLE problems (
    id INT AUTO_INCREMENT PRIMARY KEY,
    provider_id INT,
    title VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    domain VARCHAR(100),
    inferred_skills TEXT,
    status ENUM('Open', 'In Progress', 'Solved', 'Patented') DEFAULT 'Open',
    solution_text TEXT,
    monetary_demand DECIMAL(10,2) DEFAULT 0.00,
    FOREIGN KEY (provider_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE problem_collaborators (
    id INT AUTO_INCREMENT PRIMARY KEY,
    problem_id INT,
    solver_id INT,
    FOREIGN KEY (problem_id) REFERENCES problems(id) ON DELETE CASCADE,
    FOREIGN KEY (solver_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE increments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    problem_id INT,
    solver_id INT,
    update_text TEXT NOT NULL,
    feedback_text TEXT,
    satisfaction_rating INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (problem_id) REFERENCES problems(id) ON DELETE CASCADE,
    FOREIGN KEY (solver_id) REFERENCES users(id) ON DELETE CASCADE
);
""")

# 2. ml_engine.py
with open('ml_engine.py', 'w', encoding='utf-8') as f:
    f.write('''from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

DOMAINS_KB = {
    "Healthcare": "hospital patient disease medical doctor treatment health clinical medicine care diagnosis vitals triage",
    "Agriculture": "crop farm soil harvest farmer agriculture plant seed irrigation fertilizer yield pest cold storage",
    "Traffic & Transport": "vehicle traffic road signal transit transport driver commute map navigation route GPS",
    "Fintech": "bank money payment fraud transaction financial wallet credit investment tax standard accounting",
    "Education": "student school university learning course teacher study curriculum exam quiz skills training peer"
}

def categorize_problem(description):
    texts = list(DOMAINS_KB.values()) + [description]
    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform(texts)
    similarity = cosine_similarity(tfidf_matrix[-1], tfidf_matrix[:-1])
    domain_names = list(DOMAINS_KB.keys())
    best_idx = similarity.argmax()
    return domain_names[best_idx]

def calculate_match_percentage(solver_skills_str, problem_desc):
    if not solver_skills_str or not solver_skills_str.strip():
        return 25
    corpus = [solver_skills_str, problem_desc]
    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform(corpus)
    score = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
    percentage = int(score * 100)
    return max(min(percentage, 95), 15) if percentage > 0 else 25
''')

# 3. app.py
with open('app.py', 'w', encoding='utf-8') as f:
    f.write('''from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
from ml_engine import categorize_problem, calculate_match_percentage

app = Flask(__name__)
app.secret_key = "ideabridge_secret_key"

db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'ideabridge_db'
}

def get_db_connection():
    return mysql.connector.connect(**db_config)

@app.route('/')
def index():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    email = request.form['email']
    password = request.form['password']
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s AND password = %s", (email, password))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        if user:
            session['user_id'] = user['id']
            session['name'] = user['name']
            session['role'] = user['role']
            return redirect(url_for('provider_dashboard' if user['role'] == 'provider' else 'solver_dashboard'))
        flash("Invalid email or password!", "danger")
    except Exception as e:
        flash(f"Database error: {e}", "danger")
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']
        org_name = request.form.get('org_name', '')
        skills = request.form.get('skills', '')
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (name, email, password, role, org_name, skills) VALUES (%s, %s, %s, %s, %s, %s)",
                           (name, email, password, role, org_name, skills))
            conn.commit()
            cursor.close()
            conn.close()
            flash("Registration successful! Please login.", "success")
            return redirect(url_for('index'))
        except Exception as e:
            flash(f"Registration error: {e}", "danger")
            
    return render_template('register.html')

@app.route('/provider_dashboard', methods=['GET', 'POST'])
def provider_dashboard():
    if 'user_id' not in session or session['role'] != 'provider':
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        domain = categorize_problem(description)
        cursor.execute("INSERT INTO problems (provider_id, title, description, domain, status) VALUES (%s, %s, %s, %s, 'Open')",
                       (session['user_id'], title, description, domain))
        conn.commit()
        flash("Problem successfully posted!", "success")
        
    cursor.execute("SELECT * FROM problems WHERE provider_id = %s ORDER BY id DESC", (session['user_id'],))
    problems = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('provider_dashboard.html', problems=problems)

@app.route('/solver_dashboard')
def solver_dashboard():
    if 'user_id' not in session or session['role'] != 'solver':
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT skills FROM users WHERE id = %s", (session['user_id'],))
    solver = cursor.fetchone()
    solver_skills = solver['skills'] if solver else ""
    
    cursor.execute("SELECT p.*, u.name as provider_name FROM problems p JOIN users u ON p.provider_id = u.id ORDER BY p.id DESC")
    problems = cursor.fetchall()
    
    for prob in problems:
        prob['match_percentage'] = calculate_match_percentage(solver_skills, prob['description'])
        cursor.execute("SELECT COUNT(*) as count FROM problem_collaborators WHERE problem_id = %s", (prob['id'],))
        prob['active_workers'] = cursor.fetchone()['count']
        
    problems.sort(key=lambda x: x['match_percentage'], reverse=True)
    cursor.close()
    conn.close()
    return render_template('solver_dashboard.html', problems=problems)

@app.route('/problem/<int:problem_id>')
def problem_detail(problem_id):
    if 'user_id' not in session:
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT p.*, u.name as provider_name FROM problems p JOIN users u ON p.provider_id = u.id WHERE p.id = %s", (problem_id,))
    problem = cursor.fetchone()
    
    cursor.execute("SELECT i.*, u.name as solver_name FROM increments i JOIN users u ON i.solver_id = u.id WHERE i.problem_id = %s ORDER BY i.created_at ASC", (problem_id,))
    increments = cursor.fetchall()
    
    cursor.execute("SELECT u.name FROM problem_collaborators pc JOIN users u ON pc.solver_id = u.id WHERE pc.problem_id = %s", (problem_id,))
    collaborators = cursor.fetchall()
    
    cursor.close()
    conn.close()
    return render_template('problem_detail.html', problem=problem, increments=increments, collaborators=collaborators)

@app.route('/join_problem/<int:problem_id>')
def join_problem(problem_id):
    if session.get('role') == 'solver':
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO problem_collaborators (problem_id, solver_id) VALUES (%s, %s)", (problem_id, session['user_id']))
            conn.commit()
            flash("You have joined this problem team!", "success")
        except:
            flash("You are already collaborating on this problem.", "info")
        cursor.close()
        conn.close()
    return redirect(url_for('problem_detail', problem_id=problem_id))

@app.route('/submit_increment/<int:problem_id>', methods=['POST'])
def submit_increment(problem_id):
    if session.get('role') == 'solver':
        update_text = request.form['update_text']
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO increments (problem_id, solver_id, update_text) VALUES (%s, %s, %s)",
                       (problem_id, session['user_id'], update_text))
        cursor.execute("UPDATE problems SET status = 'In Progress' WHERE id = %s AND status = 'Open'", (problem_id,))
        conn.commit()
        cursor.close()
        conn.close()
        flash("Progress update posted!", "success")
    return redirect(url_for('problem_detail', problem_id=problem_id))

@app.route('/provide_feedback/<int:inc_id>/<int:problem_id>', methods=['POST'])
def provide_feedback(inc_id, problem_id):
    feedback = request.form['feedback_text']
    rating = request.form['satisfaction_rating']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE increments SET feedback_text = %s, satisfaction_rating = %s WHERE id = %s", (feedback, rating, inc_id))
    conn.commit()
    cursor.close()
    conn.close()
    flash("Feedback sent to solver!", "success")
    return redirect(url_for('problem_detail', problem_id=problem_id))

@app.route('/finalize_solution/<int:problem_id>', methods=['POST'])
def finalize_solution(problem_id):
    solution_text = request.form['solution_text']
    monetary_demand = request.form.get('monetary_demand', 0.00)
    action_type = request.form['action_type']
    status = 'Patented' if action_type == 'patented' else 'Solved'
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE problems SET solution_text = %s, monetary_demand = %s, status = %s WHERE id = %s",
                   (solution_text, monetary_demand, status, problem_id))
    conn.commit()
    cursor.close()
    conn.close()
    flash("Solution submitted and finalized!", "success")
    return redirect(url_for('problem_detail', problem_id=problem_id))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
''')

# 4. templates/login.html (Awesome Landing/Login Page)
with open('templates/login.html', 'w', encoding='utf-8') as f:
    f.write('''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IdeaBridge 2.0 - Collaborative Problem Solving Platform</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
    <style>
        .hero-section {
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: white;
            min-height: 100vh;
        }
        .login-card {
            border: none;
            border-radius: 16px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        .feature-icon {
            font-size: 2rem;
            color: #2a5298;
        }
    </style>
</head>
<body class="hero-section d-flex align-items-center">
    <div class="container py-5">
        <div class="row align-items-center g-5">
            <div class="col-lg-7">
                <div class="badge bg-warning text-dark px-3 py-2 rounded-pill mb-3 fw-bold">
                    <i class="bi bi-cpu-fill me-1"></i> AI-Powered Matching Engine
                </div>
                <h1 class="display-4 fw-bold mb-3">Bridge Real Problems with Innovative Solutions.</h1>
                <p class="lead text-light mb-4">
                    IdeaBridge 2.0 connects Problem Providers with skilled Engineers and Solvers. Track progress incrementally, iterate with continuous feedback, and secure patents seamlessly.
                </p>
                <div class="row g-4 mt-2">
                    <div class="col-md-4">
                        <div class="d-flex align-items-center">
                            <i class="bi bi-diagram-3-fill fs-3 text-warning me-3"></i>
                            <div>
                                <h6 class="mb-0 fw-bold">TF-IDF Scoring</h6>
                                <small class="text-light opacity-75">Automated skill matching</small>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div class="d-flex align-items-center">
                            <i class="bi bi-arrow-repeat fs-3 text-warning me-3"></i>
                            <div>
                                <h6 class="mb-0 fw-bold">Incremental Feedback</h6>
                                <small class="text-light opacity-75">Step-by-step milestones</small>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div class="d-flex align-items-center">
                            <i class="bi bi-shield-check fs-3 text-warning me-3"></i>
                            <div>
                                <h6 class="mb-0 fw-bold">Patent Ready</h6>
                                <small class="text-light opacity-75">Monetize solutions</small>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="col-lg-5">
                <div class="card login-card p-4 text-dark bg-white">
                    <div class="text-center mb-4">
                        <h3 class="fw-bold text-primary">Welcome Back</h3>
                        <p class="text-muted small">Access your IdeaBridge workspace</p>
                    </div>

                    {% with messages = get_flashed_messages(with_categories=true) %}
                        {% if messages %}
                            {% for category, message in messages %}
                                <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
                                    {{ message }}
                                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                                </div>
                            {% endfor %}
                        {% endif %}
                    {% endwith %}

                    <form action="/login" method="POST">
                        <div class="mb-3">
                            <label class="form-label fw-bold small">Email address</label>
                            <div class="input-group">
                                <span class="input-group-text"><i class="bi bi-envelope"></i></span>
                                <input type="email" name="email" class="form-control" placeholder="name@domain.com" required>
                            </div>
                        </div>
                        <div class="mb-3">
                            <label class="form-label fw-bold small">Password</label>
                            <div class="input-group">
                                <span class="input-group-text"><i class="bi bi-lock"></i></span>
                                <input type="password" name="password" class="form-control" placeholder="••••••••" required>
                            </div>
                        </div>
                        <button type="submit" class="btn btn-primary w-100 py-2 fw-bold shadow-sm mb-3">
                            Sign In <i class="bi bi-arrow-right ms-1"></i>
                        </button>
                        <div class="text-center">
                            <span class="text-muted small">New to IdeaBridge?</span>
                            <a href="/register" class="fw-bold text-decoration-none ms-1">Create an Account</a>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    </div>
    <script https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js></script>
</body>
</html>''')

# 5. templates/register.html
with open('templates/register.html', 'w', encoding='utf-8') as f:
    f.write('''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Register - IdeaBridge 2.0</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
    <style>
        body { background: #f4f7f6; min-height: 100vh; display: flex; align-items: center; }
        .reg-card { border: none; border-radius: 16px; box-shadow: 0 10px 25px rgba(0,0,0,0.08); }
    </style>
</head>
<body>
    <div class="container py-5">
        <div class="row justify-content-center">
            <div class="col-md-6">
                <div class="card reg-card p-4 bg-white">
                    <h3 class="text-center fw-bold text-primary mb-1">Create Your Workspace</h3>
                    <p class="text-center text-muted small mb-4">Join as a Problem Provider or Problem Solver</p>

                    {% with messages = get_flashed_messages(with_categories=true) %}
                        {% if messages %}
                            {% for category, message in messages %}
                                <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
                                    {{ message }}
                                </div>
                            {% endfor %}
                        {% endif %}
                    {% endwith %}

                    <form action="/register" method="POST">
                        <div class="mb-3">
                            <label class="form-label fw-semibold">Full Name</label>
                            <input type="text" name="name" class="form-control" placeholder="Jane Doe" required>
                        </div>
                        <div class="mb-3">
                            <label class="form-label fw-semibold">Email Address</label>
                            <input type="email" name="email" class="form-control" placeholder="jane@example.com" required>
                        </div>
                        <div class="mb-3">
                            <label class="form-label fw-semibold">Password</label>
                            <input type="password" name="password" class="form-control" placeholder="••••••••" required>
                        </div>
                        <div class="mb-3">
                            <label class="form-label fw-semibold">Platform Role</label>
                            <select name="role" id="roleSelect" class="form-select" onchange="toggleRoleFields()" required>
                                <option value="solver">Problem Solver (Engineer / Student / Researcher)</option>
                                <option value="provider">Problem Provider (Organization / NGO / Industry)</option>
                            </select>
                        </div>
                        <div class="mb-3" id="orgField" style="display:none;">
                            <label class="form-label fw-semibold">Organization / Institution Name</label>
                            <input type="text" name="org_name" class="form-control" placeholder="e.g. Apex HealthTech">
                        </div>
                        <div class="mb-3" id="skillsField">
                            <label class="form-label fw-semibold">Key Technical Skills</label>
                            <input type="text" name="skills" class="form-control" placeholder="e.g. Python, Machine Learning, Flask, SQL, React">
                            <div class="form-text small">Used by AI engine to match you with suitable problems.</div>
                        </div>
                        <button type="submit" class="btn btn-success w-100 py-2 fw-bold mb-3">Complete Registration</button>
                        <div class="text-center">
                            <a href="/" class="text-decoration-none small text-muted">Already registered? Log in</a>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    </div>
    <script>
        function toggleRoleFields() {
            let role = document.getElementById('roleSelect').value;
            if(role === 'provider') {
                document.getElementById('orgField').style.display = 'block';
                document.getElementById('skillsField').style.display = 'none';
            } else {
                document.getElementById('orgField').style.display = 'none';
                document.getElementById('skillsField').style.display = 'block';
            }
        }
    </script>
</body>
</html>''')

# 6. templates/provider_dashboard.html
with open('templates/provider_dashboard.html', 'w', encoding='utf-8') as f:
    f.write('''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Provider Workspace - IdeaBridge</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
</head>
<body class="bg-light">
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark px-4 shadow-sm">
        <a class="navbar-brand fw-bold" href="#"><i class="bi bi-lightbulb-fill text-warning me-2"></i>IdeaBridge Provider Workspace</a>
        <div class="ms-auto">
            <span class="text-white me-3">Welcome, <strong>{{ session['name'] }}</strong></span>
            <a href="/logout" class="btn btn-outline-light btn-sm">Logout</a>
        </div>
    </nav>
    <div class="container my-5">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
                        {{ message }}
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        <div class="card shadow-sm border-0 p-4 mb-4">
            <h4 class="mb-3 text-primary fw-bold"><i class="bi bi-plus-circle me-2"></i>Post a New Problem Statement</h4>
            <form method="POST">
                <div class="mb-3">
                    <label class="form-label fw-semibold">Problem Title</label>
                    <input type="text" name="title" class="form-control" placeholder="e.g. Low-bandwidth diagnostic triage system" required>
                </div>
                <div class="mb-3">
                    <label class="form-label fw-semibold">Detailed Description</label>
                    <textarea name="description" rows="4" class="form-control" placeholder="Describe the background, current pain points, and target requirements..." required></textarea>
                    <div class="form-text small">Our TF-IDF model will automatically extract key terms and categorize your domain.</div>
                </div>
                <button type="submit" class="btn btn-primary fw-bold px-4">Post & Categorize Problem</button>
            </form>
        </div>

        <h4 class="mb-3 fw-bold text-secondary">Your Posted Problems</h4>
        <div class="row g-3">
            {% for p in problems %}
            <div class="col-md-4">
                <div class="card h-100 shadow-sm border-0">
                    <div class="card-body d-flex flex-column">
                        <div class="mb-2">
                            <span class="badge bg-primary">{{ p.domain }}</span>
                            <span class="badge bg-info text-dark">{{ p.status }}</span>
                        </div>
                        <h5 class="card-title fw-bold">{{ p.title }}</h5>
                        <p class="card-text text-muted small flex-grow-1">{{ p.description[:110] }}...</p>
                        <a href="/problem/{{ p.id }}" class="btn btn-outline-primary btn-sm w-100 mt-2">Manage & Review Progress</a>
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>
</body>
</html>''')

# 7. templates/solver_dashboard.html
with open('templates/solver_dashboard.html', 'w', encoding='utf-8') as f:
    f.write('''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Solver Hub - IdeaBridge</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
</head>
<body class="bg-light">
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark px-4 shadow-sm">
        <a class="navbar-brand fw-bold" href="#"><i class="bi bi-gear-fill text-warning me-2"></i>IdeaBridge Solver Hub</a>
        <div class="ms-auto">
            <span class="text-white me-3">Welcome, <strong>{{ session['name'] }}</strong></span>
            <a href="/logout" class="btn btn-outline-light btn-sm">Logout</a>
        </div>
    </nav>
    <div class="container my-5">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <div>
                <h3 class="fw-bold text-primary mb-1">Smart Matched Problems</h3>
                <p class="text-muted small mb-0">Ranked dynamically by similarity to your listed skill set.</p>
            </div>
        </div>

        <div class="row g-4">
            {% for p in problems %}
            <div class="col-md-4">
                <div class="card shadow-sm border-0 h-100">
                    <div class="card-body d-flex flex-column">
                        <div class="d-flex justify-content-between align-items-center mb-2">
                            <span class="badge bg-secondary">{{ p.domain }}</span>
                            <span class="badge bg-success"><i class="bi bi-lightning-charge-fill me-1"></i>Match: {{ p.match_percentage }}%</span>
                        </div>
                        <h5 class="card-title fw-bold mb-1">{{ p.title }}</h5>
                        <h6 class="text-muted small mb-3">Posted by: {{ p.provider_name }}</h6>
                        <p class="card-text text-muted small flex-grow-1">{{ p.description[:120] }}...</p>
                        <div class="mb-3">
                            <span class="badge bg-info text-dark me-1">Status: {{ p.status }}</span>
                            <span class="badge bg-warning text-dark">Collaborators: {{ p.active_workers }}</span>
                        </div>
                        <a href="/problem/{{ p.id }}" class="btn btn-primary btn-sm w-100 fw-bold">View Details & Work</a>
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>
</body>
</html>''')

# 8. templates/problem_detail.html
with open('templates/problem_detail.html', 'w', encoding='utf-8') as f:
    f.write('''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Problem Workspace - IdeaBridge</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
</head>
<body class="bg-light">
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark px-4 shadow-sm">
        <a class="navbar-brand fw-bold" href="#">IdeaBridge Workspace</a>
        <div class="ms-auto">
            <a href="{{ url_for('provider_dashboard' if session['role'] == 'provider' else 'solver_dashboard') }}" class="btn btn-outline-light btn-sm me-2">Back to Dashboard</a>
            <a href="/logout" class="btn btn-outline-danger btn-sm">Logout</a>
        </div>
    </nav>

    <div class="container my-5">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
                        {{ message }}
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        <div class="card shadow-sm border-0 p-4 mb-4">
            <div class="d-flex justify-content-between align-items-start mb-2">
                <h2 class="fw-bold text-primary mb-0">{{ problem.title }}</h2>
                <span class="badge bg-info text-dark fs-6">{{ problem.status }}</span>
            </div>
            <h6 class="text-muted mb-3">Domain: <strong>{{ problem.domain }}</strong> | Posted by: <strong>{{ problem.provider_name }}</strong></h6>
            <p class="fs-6 text-secondary">{{ problem.description }}</p>
            
            <hr>
            <div class="d-flex justify-content-between align-items-center">
                <div>
                    <strong class="me-2">Active Collaborators:</strong>
                    {% for c in collaborators %}
                        <span class="badge bg-secondary me-1 p-2">{{ c.name }}</span>
                    {% else %}
                        <span class="text-muted small">No solvers joined yet.</span>
                    {% endfor %}
                </div>
                {% if session['role'] == 'solver' %}
                <a href="/join_problem/{{ problem.id }}" class="btn btn-success btn-sm fw-bold"><i class="bi bi-person-plus-fill me-1"></i> Join Collaboration Team</a>
                {% endif %}
            </div>
        </div>

        {% if problem.status not in ['Solved', 'Patented'] %}
        <div class="card shadow-sm border-0 p-4 mb-4">
            <h4 class="mb-3 text-primary fw-bold"><i class="bi bi-journal-text me-2"></i>Incremental Progress & Feedback Loop</h4>
            
            {% for inc in increments %}
            <div class="border rounded p-3 mb-3 bg-white shadow-sm">
                <div class="d-flex justify-content-between">
                    <strong class="text-dark"><i class="bi bi-person-circle me-1"></i> {{ inc.solver_name }}</strong>
                    <span class="text-muted small">{{ inc.created_at }}</span>
                </div>
                <p class="mt-2 mb-2 text-secondary">{{ inc.update_text }}</p>
                
                {% if inc.feedback_text %}
                    <div class="bg-light p-3 rounded border mt-2">
                        <div class="text-primary fw-bold small mb-1"><i class="bi bi-chat-left-dots me-1"></i> Provider Review:</div>
                        <div>{{ inc.feedback_text }}</div>
                        <div class="mt-1"><span class="badge bg-warning text-dark">Rating: {{ inc.satisfaction_rating }}/5 Stars</span></div>
                    </div>
                {% elif session['role'] == 'provider' %}
                    <form action="/provide_feedback/{{ inc.id }}/{{ problem.id }}" method="POST" class="mt-3 bg-light p-2 rounded">
                        <div class="row g-2">
                            <div class="col-md-7">
                                <input type="text" name="feedback_text" placeholder="Write feedback for this update..." class="form-control form-control-sm" required>
                            </div>
                            <div class="col-md-3">
                                <select name="satisfaction_rating" class="form-select form-select-sm" required>
                                    <option value="5">⭐⭐⭐⭐⭐ (5/5)</option>
                                    <option value="4">⭐⭐⭐⭐ (4/5)</option>
                                    <option value="3">⭐⭐⭐ (3/5)</option>
                                    <option value="2">⭐⭐ (2/5)</option>
                                    <option value="1">⭐ (1/5)</option>
                                </select>
                            </div>
                            <div class="col-md-2">
                                <button type="submit" class="btn btn-sm btn-primary w-100 fw-bold">Submit Review</button>
                            </div>
                        </div>
                    </form>
                {% endif %}
            </div>
            {% else %}
            <p class="text-muted small mb-0">No updates posted yet.</p>
            {% endfor %}

            {% if session['role'] == 'solver' %}
            <hr class="my-4">
            <form action="/submit_increment/{{ problem.id }}" method="POST">
                <h5 class="fw-bold mb-2">Submit Milestone Update</h5>
                <div class="mb-3">
                    <textarea name="update_text" rows="3" class="form-control" placeholder="Share your latest design, code snippet, or progress notes..." required></textarea>
                </div>
                <button type="submit" class="btn btn-secondary fw-bold">Post Update</button>
            </form>
            {% endif %}
        </div>

        {% if session['role'] == 'solver' %}
        <div class="card shadow-sm border-0 p-4 mb-4 border-top border-success border-4">
            <h4 class="text-success fw-bold mb-3"><i class="bi bi-check-circle-fill me-2"></i>Final Solution Submission & Patent Settlement</h4>
            <form action="/finalize_solution/{{ problem.id }}" method="POST">
                <div class="mb-3">
                    <label class="form-label fw-semibold">Final Solution & Repository / Patent Documentation</label>
                    <textarea name="solution_text" rows="3" class="form-control" placeholder="Detailed architectural breakdown, GitHub link, or patent abstract..." required></textarea>
                </div>
                <div class="row g-3 mb-3">
                    <div class="col-md-6">
                        <label class="form-label fw-semibold">Monetary Demand (₹) (Optional)</label>
                        <input type="number" step="0.01" name="monetary_demand" class="form-control" value="0.00">
                    </div>
                    <div class="col-md-6">
                        <label class="form-label fw-semibold">Action Type</label>
                        <select name="action_type" class="form-select" required>
                            <option value="solved">Mark as Solved</option>
                            <option value="patented">Mark as Patented & Solved (Lock Problem)</option>
                        </select>
                    </div>
                </div>
                <button type="submit" class="btn btn-success fw-bold px-4">Finalize & Submit Solution</button>
            </form>
        </div>
        {% endif %}
        
        {% else %}
        <div class="card shadow-sm border-0 p-4 bg-success text-white">
            <h3 class="fw-bold mb-2"><i class="bi bi-award-fill me-2"></i>Problem Finalized (Status: {{ problem.status }})</h3>
            <p class="fs-5 mt-2"><strong>Final Solution:</strong> {{ problem.solution_text }}</p>
            {% if problem.monetary_demand > 0 %}
            <p class="mb-0 fs-6"><strong>Monetary Reward / Royalty Demand:</strong> ₹{{ problem.monetary_demand }}</p>
            {% endif %}
        </div>
        {% endif %}
    </div>
</body>
</html>''')

print("PROJECT CREATED SUCCESSFULLY!")