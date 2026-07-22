from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user

from app.models import db, Student, ClassSession, CameraStatus
from app.face_utils import register_face_images, recognize_from_data_url, invalidate_cache
from app.attendance import mark_attendance, is_enrolled
from app.utils import roles_required, log_action

api_bp = Blueprint("api", __name__)


@api_bp.route("/students/<int:student_id>/register-face", methods=["POST"])
@login_required
@roles_required("admin")
def register_face(student_id):
    student = db.session.get(Student, student_id)
    if not student:
        return jsonify({"ok": False, "message": "Student not found"}), 404

    frames = request.json.get("frames", [])
    if not frames:
        return jsonify({"ok": False, "message": "No frames received"}), 400

    saved, errors = register_face_images(
        student, frames,
        upload_dir=current_app.config["STUDENT_FACE_DIR"],
        detection_model=current_app.config["FACE_DETECTION_MODEL"],
    )
    log_action("FACE_REGISTER", f"student={student.student_code} saved={saved} errors={len(errors)}")

    return jsonify({
        "ok": saved > 0,
        "saved": saved,
        "errors": errors,
        "message": f"{saved} face sample(s) saved." + (f" {len(errors)} frame(s) skipped." if errors else "")
    })


@api_bp.route("/students/<int:student_id>/reset-face", methods=["POST"])
@login_required
@roles_required("admin")
def reset_face(student_id):
    student = db.session.get(Student, student_id)
    if not student:
        return jsonify({"ok": False, "message": "Student not found"}), 404
    for fe in list(student.embeddings):
        db.session.delete(fe)
    student.is_face_registered = False
    db.session.commit()
    invalidate_cache()
    log_action("FACE_RESET", f"student={student.student_code}")
    return jsonify({"ok": True, "message": "Face data cleared. You can re-register now."})


@api_bp.route("/attendance/recognize", methods=["POST"])
@login_required
@roles_required("admin", "teacher")
def recognize_and_mark():
    """
    Receives one webcam frame + class_id, recognizes faces present,
    and marks attendance (once per day per student per class).
    """
    payload = request.json or {}
    frame = payload.get("frame")
    class_id = payload.get("class_id")

    if not frame or not class_id:
        return jsonify({"ok": False, "message": "frame and class_id are required"}), 400

    class_session = db.session.get(ClassSession, int(class_id))
    if not class_session:
        return jsonify({"ok": False, "message": "Class not found"}), 404

    results = recognize_from_data_url(
        frame,
        tolerance=current_app.config["FACE_MATCH_TOLERANCE"],
        detection_model=current_app.config["FACE_DETECTION_MODEL"],
        save_unknown_dir=current_app.config["UNKNOWN_FACE_DIR"],
        class_id=class_session.id,
    )

    response_people = []
    for r in results:
        if not r["matched"]:
            response_people.append({"matched": False, "box": r["box"]})
            continue

        student = db.session.get(Student, r["student_id"])
        if not student:
            continue

        if not is_enrolled(student.id, class_session.id):
            response_people.append({
                "matched": True, "enrolled": False, "student_code": student.student_code,
                "name": student.user.full_name, "box": r["box"], "confidence": r["confidence"],
            })
            continue

        record, created, message = mark_attendance(
            student.id, class_session.id, confidence=r["confidence"],
            marked_by="system", late_after_minutes=current_app.config["LATE_AFTER_MINUTES"],
        )
        response_people.append({
            "matched": True, "enrolled": True, "created": created, "message": message,
            "student_code": student.student_code, "name": student.user.full_name,
            "status": record.status, "confidence": r["confidence"], "box": r["box"],
        })

    return jsonify({"ok": True, "people": response_people})


@api_bp.route("/camera/ping", methods=["POST"])
@login_required
def camera_ping():
    """Browser reports webcam availability so the dashboard can show live status."""
    payload = request.json or {}
    name = payload.get("camera_name", f"{current_user.username}-webcam")
    status = payload.get("status", "online")

    cam = CameraStatus.query.filter_by(camera_name=name).first()
    if not cam:
        cam = CameraStatus(camera_name=name, location=payload.get("location", "browser"))
        db.session.add(cam)
    cam.status = status
    from datetime import datetime
    cam.last_ping = datetime.utcnow()
    db.session.commit()
    return jsonify({"ok": True})
