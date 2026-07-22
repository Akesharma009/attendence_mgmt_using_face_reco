# FaceTrack — Student Management System with Face Recognition

A full-stack Python/Flask application for student registration, face-recognition
attendance, and role-based dashboards for **Admin**, **Teacher**, and **Student**.

---

## ✨ Features

- **3 separate login portals** — Admin, Teacher, Student — each with its own form,
  role-based access control, hashed passwords (Werkzeug), and server-side sessions
  (Flask-Login).
- **Self-service account creation** for all 3 portals ("Create one" link on each
  login page → `/register/admin`, `/register/teacher`, `/register/student`). An
  account is only created if no existing account matches the username/email (and,
  for teachers/students, the Teacher/Student ID); otherwise the person is told an
  account already exists and is sent to the login page instead.
- **Automatic time-in / time-out from face recognition**: the first time a
  student's face is recognized for a class on a given day, `time_in` is stamped.
  Every later recognition that same day keeps pushing `time_out` forward, so
  `time_out` always reflects the last moment the student was seen, and
  `time_out − time_in` gives the hours/minutes the student actually sat in class.
  This shows up as "Hrs in Class" in the attendance tables/exports — no separate
  checkout camera or button needed.
- **Student registration** with webcam-based multi-shot face capture (5 angles),
  automatic 128-d face-embedding generation (`face_recognition` / dlib ResNet),
  edit/delete, and one-click face re-registration.
- **Live attendance** via webcam: detects & recognizes faces in real time, marks
  attendance **once per student per class per day**, flags unknown faces, computes
  "late" status from the class start time.
- **Normalized relational schema** (see `schema_postgres.sql`) — users, students,
  teachers, courses, class_sessions, enrollments, face_embeddings, attendance,
  unknown_face_logs, audit_logs, camera_status — with FKs, unique constraints, and
  indexes. Works on **SQLite** (zero-config default), **PostgreSQL**, or **MySQL**
  via a single `DATABASE_URL` env var (SQLAlchemy).
- **Admin dashboard**: KPIs, 14-day attendance trend chart, student/teacher CRUD,
  course & class management, searchable/filterable attendance records, CSV / Excel
  / PDF export, audit log viewer, camera status + unknown-face gallery.
- **Teacher dashboard**: their classes only, live attendance capture, filtered
  records & exports, per-class trend chart.
- **Student dashboard**: personal attendance %, per-class breakdown, history.
- **Audit logging** on login/logout, student/teacher/course/class CRUD, face
  registration, and report exports.

---

## 🗂 Project Structure

```
sms/
├── app/
│   ├── __init__.py          # App factory, blueprint registration
│   ├── models.py            # SQLAlchemy models (normalized schema)
│   ├── auth.py               # 3 login routes + logout
│   ├── api.py                 # Webcam AJAX endpoints (register/recognize)
│   ├── face_utils.py         # Face detection/encoding/matching engine
│   ├── attendance.py         # Once-per-day marking logic
│   ├── reports.py            # CSV/Excel/PDF export + analytics
│   ├── routes_admin.py
│   ├── routes_teacher.py
│   ├── routes_student.py
│   ├── utils.py               # roles_required decorator, audit logger
│   ├── static/{css,js,uploads}
│   └── templates/{auth,admin,teacher,student}
├── config.py
├── run.py
├── seed_db.py                # Creates default admin + demo data
├── schema_postgres.sql        # Reference DDL (auto-created by SQLAlchemy too)
├── requirements.txt
└── .env.example
```

---

## 🚀 Setup

### 1. System dependencies (for `face_recognition` / dlib)

`face_recognition` depends on `dlib`, which needs CMake and a C++ compiler.

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install -y build-essential cmake libopenblas-dev liblapack-dev
```
**macOS:**
```bash
brew install cmake
```
**Windows:** install [CMake](https://cmake.org/download/) and Visual Studio Build
Tools (C++ workload) before `pip install`.

### 2. Python environment

```bash
cd sms
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

> Tip: `dlib` compiles from source and can take several minutes.

### 3. Configure environment

```bash
cp .env.example .env
# edit .env — set SECRET_KEY, and DATABASE_URL if using PostgreSQL/MySQL
```

By default the app uses **SQLite** at `instance/sms.db` — nothing else to configure.

To use **PostgreSQL**:
```
DATABASE_URL=postgresql+psycopg2://sms_user:password@localhost:5432/student_management
```
To use **MySQL**:
```
DATABASE_URL=mysql+pymysql://sms_user:password@localhost:3306/student_management
```
(Create the empty database first — SQLAlchemy will create the tables.)

### 4. Seed the database (creates tables + a default admin account)

```bash
python seed_db.py
```
This prints the generated demo credentials:
- **Admin** → `admin` / `Admin@123`
- **Teacher** → `teacher1` / `Teacher@123`
- **Student** → `student1` / `Student@123`

**⚠️ Change these passwords (or delete the demo accounts) before any real deployment.**

### 5. Run

```bash
python run.py
```
Visit **http://localhost:5000** → choose a portal → sign in.

Webcam features require the browser to grant camera permission and generally
require **HTTPS or `localhost`** (browsers block camera access on plain HTTP for
any other host) — deploy behind TLS in production.

---

## 🧠 How face recognition works

1. **Registration** (`admin/students/<id>/face`): the browser captures 5 webcam
   frames as base64 JPEGs and posts them to `/api/students/<id>/register-face`.
   The server detects a face in each frame (`face_recognition.face_locations`,
   HOG by default), computes a 128-d embedding, and stores it in
   `face_embeddings` (one row per captured sample — averaging multiple samples
   per student improves robustness to pose/lighting).
2. **Live attendance** (`admin/teacher attendance/live`): the browser grabs a
   frame roughly every 2 seconds and posts it to `/api/attendance/recognize`.
   The server compares the detected embedding(s) against all known embeddings
   (Euclidean distance, threshold = `FACE_MATCH_TOLERANCE`, default `0.45`),
   and on a match, calls `mark_attendance()` which enforces the **unique
   `(student_id, class_id, date)` constraint** — so re-detecting the same
   student in the same session is a no-op, not a duplicate row. Unmatched
   faces are logged to `unknown_face_logs` with a saved snapshot.
3. **Performance**: known-face embeddings are cached in memory
   (`face_utils._ENCODING_CACHE`) and invalidated on registration/reset, so
   recognition doesn't hit the DB per frame. Detection model is configurable:
   `FACE_DETECTION_MODEL=hog` (CPU, default, fast) or `cnn` (GPU, requires a
   CUDA-enabled dlib build — much higher accuracy on angled/low-light faces).

---

## 🔐 Security notes

- Passwords are hashed with Werkzeug's `generate_password_hash` (PBKDF2).
- Sessions via Flask-Login; `SECRET_KEY` **must** be changed in `.env` for
  production.
- Every login/logout, CRUD action, face registration, and report export is
  written to `audit_logs` with the acting user, action, details, and IP.
- Role-based access is enforced per-blueprint (`roles_required` decorator) —
  a student can never reach `/admin/*` or `/teacher/*` routes.
- For a production deployment, also add: HTTPS/TLS, CSRF protection
  (Flask-WTF), rate limiting on login routes, and a proper reverse proxy
  (gunicorn + nginx).

---

## 📈 Extending this project

- **JWT API layer**: the current auth is session-based (ideal for the
  server-rendered dashboard). If you need a separate mobile/SPA client, add
  `Flask-JWT-Extended` alongside the existing session auth for the `/api/*`
  blueprint.
- **GPU acceleration**: set `FACE_DETECTION_MODEL=cnn` with a CUDA build of
  dlib for faster, more accurate detection at scale.
- **Async/queueing**: for many simultaneous cameras, move recognition calls
  to a task queue (Celery + Redis) instead of synchronous request handling.
- **Multi-face-per-frame** is already supported by `face_utils.py` (it loops
  over every detected face in a frame) — the live-attendance UI already draws
  a box + label per detected person.

---

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3, Flask, Flask-Login, Flask-SQLAlchemy |
| Face Recognition | `face_recognition` (dlib ResNet, 128-d embeddings), OpenCV |
| Database | SQLite / PostgreSQL / MySQL (SQLAlchemy ORM) |
| Frontend | Jinja2 templates, vanilla JS (`getUserMedia`), Chart.js |
| Reports | pandas, openpyxl (Excel), reportlab (PDF) |

---

## License

Provided as-is for educational/demo purposes. Review and harden before any
production or student-data use — in particular, verify compliance with your
institution's data-privacy policies (biometric data is sensitive personal data
under most privacy laws, e.g. GDPR/FERPA).
