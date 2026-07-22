-- ============================================================================
-- FaceTrack Student Management System — Reference PostgreSQL Schema
-- ============================================================================
-- This file documents the normalized relational design. In practice the app
-- creates these tables automatically via SQLAlchemy (db.create_all()), for
-- SQLite, PostgreSQL, or MySQL, depending on DATABASE_URL. Use this .sql file
-- if you prefer to provision the PostgreSQL schema manually / via migration
-- tooling, or just to review the design.
-- ============================================================================

CREATE TABLE users (
    id              SERIAL PRIMARY KEY,
    username        VARCHAR(64)  NOT NULL UNIQUE,
    email           VARCHAR(120) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    role            VARCHAR(20)  NOT NULL CHECK (role IN ('admin','teacher','student')),
    full_name       VARCHAR(120) NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMP NOT NULL DEFAULT now(),
    last_login      TIMESTAMP
);
CREATE INDEX ix_users_role ON users(role);

CREATE TABLE teachers (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    teacher_code    VARCHAR(30) NOT NULL UNIQUE,
    department      VARCHAR(120),
    phone           VARCHAR(30)
);

CREATE TABLE students (
    id                  SERIAL PRIMARY KEY,
    user_id             INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    student_code        VARCHAR(30) NOT NULL UNIQUE,
    dob                 DATE,
    gender              VARCHAR(10),
    phone               VARCHAR(30),
    address             VARCHAR(255),
    enrollment_date     DATE DEFAULT CURRENT_DATE,
    photo_path          VARCHAR(255),
    is_face_registered  BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE courses (
    id              SERIAL PRIMARY KEY,
    code            VARCHAR(20) NOT NULL UNIQUE,
    name            VARCHAR(150) NOT NULL,
    description     TEXT,
    credits         INTEGER DEFAULT 3
);

CREATE TABLE class_sessions (
    id              SERIAL PRIMARY KEY,
    course_id       INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    teacher_id      INTEGER REFERENCES teachers(id) ON DELETE SET NULL,
    class_name      VARCHAR(100) NOT NULL,
    schedule_day    VARCHAR(20),
    start_time      TIME,
    end_time        TIME,
    room            VARCHAR(50),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE INDEX ix_class_course_teacher ON class_sessions(course_id, teacher_id);

CREATE TABLE enrollments (
    id              SERIAL PRIMARY KEY,
    student_id      INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    class_id        INTEGER NOT NULL REFERENCES class_sessions(id) ON DELETE CASCADE,
    enrolled_at     TIMESTAMP NOT NULL DEFAULT now(),
    CONSTRAINT uq_enrollment_student_class UNIQUE (student_id, class_id)
);
CREATE INDEX ix_enrollments_student ON enrollments(student_id);
CREATE INDEX ix_enrollments_class   ON enrollments(class_id);

CREATE TABLE face_embeddings (
    id              SERIAL PRIMARY KEY,
    student_id      INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    embedding_blob  BYTEA NOT NULL,          -- pickled 128-d float vector (dlib/face_recognition)
    image_path      VARCHAR(255),
    created_at      TIMESTAMP NOT NULL DEFAULT now()
);
CREATE INDEX ix_face_embeddings_student ON face_embeddings(student_id);

CREATE TABLE unknown_face_logs (
    id              SERIAL PRIMARY KEY,
    class_id        INTEGER REFERENCES class_sessions(id) ON DELETE SET NULL,
    image_path      VARCHAR(255),
    detected_at     TIMESTAMP NOT NULL DEFAULT now()
);
CREATE INDEX ix_unknown_face_logs_detected_at ON unknown_face_logs(detected_at);

CREATE TABLE attendance (
    id              SERIAL PRIMARY KEY,
    student_id      INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    class_id        INTEGER NOT NULL REFERENCES class_sessions(id) ON DELETE CASCADE,
    date            DATE NOT NULL DEFAULT CURRENT_DATE,
    time_in         TIME,
    time_out        TIME,
    status          VARCHAR(20) NOT NULL DEFAULT 'present' CHECK (status IN ('present','late','absent')),
    confidence      REAL,
    marked_by       VARCHAR(20) DEFAULT 'system',
    created_at      TIMESTAMP NOT NULL DEFAULT now(),
    CONSTRAINT uq_attendance_once_per_day UNIQUE (student_id, class_id, date)
);
CREATE INDEX ix_attendance_date_class ON attendance(date, class_id);
CREATE INDEX ix_attendance_student ON attendance(student_id);

CREATE TABLE audit_logs (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action          VARCHAR(100) NOT NULL,
    details         TEXT,
    ip_address      VARCHAR(50),
    timestamp       TIMESTAMP NOT NULL DEFAULT now()
);
CREATE INDEX ix_audit_logs_timestamp ON audit_logs(timestamp);

CREATE TABLE camera_status (
    id              SERIAL PRIMARY KEY,
    camera_name     VARCHAR(100) NOT NULL,
    location        VARCHAR(120),
    status          VARCHAR(20) DEFAULT 'offline' CHECK (status IN ('online','offline','error')),
    last_ping       TIMESTAMP DEFAULT now()
);

-- ============================================================================
-- Relationship summary
--   users (1) --- (1) students / teachers   (role-specific profile)
--   courses (1) --- (N) class_sessions
--   teachers (1) --- (N) class_sessions
--   students (N) --- (N) class_sessions  via enrollments
--   students (1) --- (N) face_embeddings
--   students (1) --- (N) attendance,  class_sessions (1) --- (N) attendance
--   attendance is unique per (student, class, date) to enforce "once per day"
-- ============================================================================
