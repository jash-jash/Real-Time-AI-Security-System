"""Flask web application for the Real-Time AI Security System."""

import os
import time

from flask import Flask, Response, jsonify, render_template, request

WEB_ONLY = os.getenv("WEB_ONLY", "").lower() in {"1", "true", "yes"}

if WEB_ONLY:
    from lite_engine import CameraManager, SecurityEngine
else:
    from security_engine import CameraManager, SecurityEngine

app = Flask(__name__)
engine = SecurityEngine()
camera = CameraManager(engine)


@app.after_request
def disable_cache(response):
    if request.path.startswith("/static/") or request.path == "/":
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def status():
    return jsonify(engine.get_status())


@app.route("/api/events")
def events():
    limit = request.args.get("limit", 20, type=int)
    return jsonify(engine.get_recent_events(limit))


@app.route("/api/camera/start", methods=["POST"])
def start_camera():
    success, message = camera.start()
    return jsonify({"success": success, "message": message})


@app.route("/api/camera/stop", methods=["POST"])
def stop_camera():
    camera.stop()
    return jsonify({"success": True, "message": "Secure camera stopped"})


@app.route("/api/settings", methods=["POST"])
def update_settings():
    data = request.get_json(silent=True) or {}
    engine.update_settings(data)
    return jsonify({"success": True, "settings": engine.settings})


@app.route("/api/encodings/refresh", methods=["POST"])
def refresh_encodings():
    engine.refresh_encodings()
    return jsonify(
        {
            "success": True,
            "authorized_faces": len(engine.authorized_encodings),
        }
    )


@app.route("/api/email/recipient", methods=["POST"])
def update_email_recipient():
    data = request.get_json(silent=True) or {}
    recipient = data.get("recipient", "")
    recipient2 = data.get("recipient2", "")
    success, message = engine.set_alert_recipient(recipient, recipient2)
    status_code = 200 if success else 400
    return jsonify(
        {
            "success": success,
            "message": message,
            "email_to": engine.alert_recipient,
            "email_recipients": engine.alert_recipients,
        }
    ), status_code


@app.route("/api/email/test", methods=["POST"])
def test_email():
    if not engine.email_password:
        return jsonify(
            {
                "success": False,
                "message": (
                    "Email password not configured. Create a .env file from "
                    ".env.example and set SECURITY_EMAIL_PASSWORD."
                ),
            }
        ), 400

    success = engine.send_test_email()
    if success:
        return jsonify(
            {
                "success": True,
                "message": f"Test email sent to {engine.alert_recipient}",
            }
        )
    return jsonify(
        {
            "success": False,
            "message": engine.last_email_error
            or "Failed to send test email. Check the terminal for details.",
        }
    ), 500


@app.route("/video_feed")
def video_feed():
    def generate():
        while engine.camera_active:
            frame_bytes = camera.get_frame_bytes()
            if frame_bytes:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
                )
            time.sleep(0.05)

    return Response(
        generate(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


def create_app():
    return app
