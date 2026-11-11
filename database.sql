CREATE DATABASE IF NOT EXISTS ideabridge_db;
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
