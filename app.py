from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
from ml_engine import categorize_problem, calculate_match_percentage

app = Flask(__name__)
app.secret_key = "ideabridge_secret_key"

db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'ideabridge'
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
        category = categorize_problem(description)
        cursor.execute("INSERT INTO problems (user_id, title, description, category) VALUES (%s, %s, %s, %s)",
                       (session['user_id'], title, description, category))
        conn.commit()
        flash("Problem successfully posted!", "success")
        
    cursor.execute("SELECT * FROM problems WHERE user_id = %s ORDER BY id DESC", (session['user_id'],))
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
    
    cursor.execute("SELECT p.*, u.name as provider_name FROM problems p JOIN users u ON p.user_id = u.id ORDER BY p.id DESC")
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
    cursor.execute("SELECT p.*, u.name as provider_name FROM problems p JOIN users u ON p.user_id = u.id WHERE p.id = %s", (problem_id,))
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
    if session.get('role') == 'solver':
        solution_text = request.form.get('solution_text')
        monetary_demand = request.form.get('monetary_demand')
        action_type = request.form.get('action_type')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO increments (problem_id, solver_id, update_text) 
            VALUES (%s, %s, %s)
        """, (problem_id, session['user_id'], f"FINAL SOLUTION: {solution_text} | Demand: ₹{monetary_demand} | Type: {action_type}"))
        conn.commit()
        cursor.close()
        conn.close()
        flash("Final solution submitted successfully!", "success")
    return redirect(url_for('problem_detail', problem_id=problem_id))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)