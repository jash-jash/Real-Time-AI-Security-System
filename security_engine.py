"""Core security processing engine for the web-based security system."""

import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

import pickle
import sqlite3
import smtplib
import threading
import datetime
import logging
import time
import warnings
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate, make_msgid

import cv2
import numpy as np
import face_recognition
import torch
from deepface import DeepFace
from ultralytics import YOLO
from ultralytics.nn import modules
from ultralytics.nn.tasks import DetectionModel
from torch.nn.modules.container import Sequential
from torch.nn.modules import Module

warnings.filterwarnings("ignore", category=UserWarning, module="face_recognition_models")
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

try:
    import pyttsx3

    def speak(text):
        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", 175)
            engine.say(text)
            engine.runAndWait()
        except Exception as exc:
            print(f"[Voice Error] {exc}")
except ImportError:
    def speak(text):
        print(f"[Voice] {text}")


class SecurityEngine:
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.authorized_folder = os.path.join(self.base_dir, "data", "authorized_faces")
        self.encodings_cache = os.path.join(self.base_dir, "authorized_encodings.pkl")
        self.video_output_dir = os.path.join(self.base_dir, "recordings")
        self.alert_image_dir = os.path.join(self.base_dir, "alerts")
        self.db_path = os.path.join(self.base_dir, "security_events.db")
        self.log_path = os.path.join(self.base_dir, "security_log.txt")

        os.makedirs(self.authorized_folder, exist_ok=True)
        os.makedirs(self.video_output_dir, exist_ok=True)
        os.makedirs(self.alert_image_dir, exist_ok=True)

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.unauthorized_objects = ["knife", "gun", "weapon"]
        self.record_duration = 10

        self.settings = {
            "face_recognition": True,
            "object_detection": True,
            "emotion_analysis": True,
            "email_alerts": True,
            "voice_alerts": True,
            "auto_recording": True,
        }

        self.camera_active = False
        self.current_status = "Idle"
        self.last_frame = None
        self.frame_lock = threading.Lock()
        self.process_lock = threading.Lock()
        self.authorized_encodings = {}
        self.recording = False
        self.video_writer = None
        self.recording_start_time = None
        self.alert_cooldown = {}
        self.cooldown_seconds = 30
        self.frame_counter = 0

        self.email_address = os.getenv("SECURITY_EMAIL", "realtimesecuritysystem@gmail.com")
        # Gmail App Passwords are often copied with spaces; SMTP expects no spaces.
        self.email_password = os.getenv("SECURITY_EMAIL_PASSWORD", "").replace(" ", "")
        self.alert_recipients = self._load_alert_recipients()
        self.last_email_error = ""

        self._setup_logging()
        self._setup_database()
        self._setup_pytorch()
        self._load_yolo()
        self._load_encodings()
        self._log_email_config()

    @property
    def alert_recipient(self):
        return ", ".join(self.alert_recipients) if self.alert_recipients else ""

    def _load_alert_recipients(self):
        primary = self._normalize_email(
            os.getenv("SECURITY_ALERT_RECIPIENT", "jashwanthinsrirama@gmail.com")
        )
        secondary = self._normalize_email(os.getenv("SECURITY_ALERT_RECIPIENT_2", ""))
        recipients = []
        for email in (primary, secondary):
            if email and email not in recipients and self._is_valid_email(email):
                recipients.append(email)
        return recipients or ["jashwanthinsrirama@gmail.com"]

    def _is_valid_email(self, email):
        if email.count("@") != 1:
            return False
        local, domain = email.split("@", 1)
        return bool(local) and "." in domain

    def _log_email_config(self):
        if not self.email_password:
            print(
                "[Email] Alerts enabled but SECURITY_EMAIL_PASSWORD is not set. "
                "Unauthorized alerts will not be emailed until it is configured."
            )
            return
        if " " not in self.email_password and len(self.email_password) < 16:
            print(
                "[Email] WARNING: SECURITY_EMAIL_PASSWORD does not look like a Gmail "
                "App Password. Create one at https://myaccount.google.com/apppasswords"
            )
        print(
            f"[Email] Alerts will be sent from {self.email_address} "
            f"to {self.alert_recipient}"
        )

    def _setup_logging(self):
        logging.basicConfig(
            filename=self.log_path,
            level=logging.INFO,
            format="[%(asctime)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        self.logger = logging.getLogger("security")

    def _setup_database(self):
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS events (timestamp TEXT, event_type TEXT, details TEXT)"
        )
        self.conn.commit()

    def _setup_pytorch(self):
        torch.serialization.add_safe_globals(
            [
                modules.Conv,
                modules.C2f,
                modules.C3,
                modules.RepC3,
                modules.Detect,
                DetectionModel,
                Sequential,
                Module,
            ]
        )
        original_load = torch.load

        def patched_load(*args, **kwargs):
            kwargs["weights_only"] = False
            return original_load(*args, **kwargs)

        torch.load = patched_load

    def _load_yolo(self):
        self.yolo_model = YOLO("yolov8n.pt")
        self.yolo_model.to(self.device)

    def _load_encodings(self):
        if os.path.exists(self.encodings_cache):
            with open(self.encodings_cache, "rb") as handle:
                self.authorized_encodings = pickle.load(handle)
            return

        names = [
            name
            for name in os.listdir(self.authorized_folder)
            if os.path.isdir(os.path.join(self.authorized_folder, name))
        ]
        for name in names:
            folder = os.path.join(self.authorized_folder, name)
            for img_name in os.listdir(folder):
                if not img_name.lower().endswith((".jpg", ".jpeg", ".png")):
                    continue
                path = os.path.join(folder, img_name)
                image = face_recognition.load_image_file(path)
                encodings = face_recognition.face_encodings(image)
                if encodings:
                    self.authorized_encodings[name] = encodings[0]
                    break

        with open(self.encodings_cache, "wb") as handle:
            pickle.dump(self.authorized_encodings, handle)

    def refresh_encodings(self):
        if os.path.exists(self.encodings_cache):
            os.remove(self.encodings_cache)
        self.authorized_encodings = {}
        self._load_encodings()

    def update_settings(self, new_settings):
        for key, value in new_settings.items():
            if key in self.settings:
                self.settings[key] = bool(value)

    def _normalize_email(self, value):
        email = (value or "").strip()
        # Fix accidental duplicates like user@gmail.com@gmail.com
        while email.lower().endswith("@gmail.com@gmail.com"):
            email = email[: -len("@gmail.com")]
        while email.count("@") > 1:
            local, _, domain = email.rpartition("@")
            if "@" in local and local.lower().endswith("@" + domain.lower()):
                email = local
            else:
                break
        return email

    def set_alert_recipient(self, recipient, recipient2=""):
        email1 = self._normalize_email(recipient)
        email2 = self._normalize_email(recipient2)

        if not self._is_valid_email(email1):
            return False, "Enter a valid primary email address (example: name@gmail.com)."
        if email2 and not self._is_valid_email(email2):
            return False, "Enter a valid second email address (or leave it blank)."
        if email2 and email2.lower() == email1.lower():
            return False, "Use two different email addresses."

        recipients = [email1]
        if email2:
            recipients.append(email2)

        self.alert_recipients = recipients
        self._persist_env_value("SECURITY_ALERT_RECIPIENT", email1)
        self._persist_env_value("SECURITY_ALERT_RECIPIENT_2", email2)
        print(f"[Email] Alert recipients updated to {self.alert_recipient}")
        return True, f"Alert emails will be sent to {self.alert_recipient}"

    def _persist_env_value(self, key, value):
        env_path = os.path.join(self.base_dir, ".env")
        lines = []
        found = False
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as handle:
                lines = handle.read().splitlines()
            updated = []
            for line in lines:
                if line.startswith(f"{key}="):
                    updated.append(f"{key}={value}")
                    found = True
                else:
                    updated.append(line)
            lines = updated
        if not found:
            lines.append(f"{key}={value}")
        with open(env_path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")

    def log_event(self, event_type, details):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.conn.execute(
            "INSERT INTO events VALUES (?,?,?)", (timestamp, event_type, details)
        )
        self.conn.commit()
        self.logger.info(f"{event_type}: {details}")

    def get_recent_events(self, limit=20):
        cursor = self.conn.execute(
            "SELECT timestamp, event_type, details FROM events ORDER BY rowid DESC LIMIT ?",
            (limit,),
        )
        return [
            {"timestamp": row[0], "event_type": row[1], "details": row[2]}
            for row in cursor.fetchall()
        ]

    def _should_alert(self, key):
        now = datetime.datetime.now()
        last = self.alert_cooldown.get(key)
        if last and (now - last).total_seconds() < self.cooldown_seconds:
            return False
        self.alert_cooldown[key] = now
        return True

    def send_email_alert(self, subject, body, frame=None, image_path=None):
        if not self.settings["email_alerts"]:
            self.last_email_error = "Email alerts are disabled in Features."
            return False
        if not self.email_address or not self.email_password:
            self.last_email_error = "SECURITY_EMAIL_PASSWORD is not set in .env"
            print("[Email Error] SECURITY_EMAIL_PASSWORD is not set. Cannot send alert email.")
            return False
        if self.email_password in {"abcdefghijklmnop", "your-16-char-app-password-here"}:
            self.last_email_error = (
                "Replace the example password in .env with a real Gmail App Password."
            )
            print(f"[Email Error] {self.last_email_error}")
            return False
        if not self.alert_recipients:
            self.last_email_error = "No alert recipient emails configured."
            return False
        try:
            msg = MIMEMultipart("mixed")
            msg["Subject"] = subject
            msg["From"] = formataddr(("Real-Time Security System", self.email_address))
            msg["To"] = ", ".join(self.alert_recipients)
            msg["Date"] = formatdate(localtime=True)
            msg["Message-ID"] = make_msgid(domain="gmail.com")
            msg["X-Priority"] = "1"
            msg["Importance"] = "high"
            msg["Reply-To"] = self.email_address

            recipients_line = ", ".join(self.alert_recipients)
            plain_body = (
                f"{body}\n\n"
                f"Recipients: {recipients_line}\n"
                "Sent by Real-Time AI Security System\n"
                f"Sender: {self.email_address}\n"
            )
            html_body = f"""\
<html>
  <body style="font-family: Arial, sans-serif; color: #202124;">
    <p>{body.replace(chr(10), '<br>')}</p>
    <p><strong>Recipients:</strong> {recipients_line}</p>
    <hr>
    <p style="color:#5f6368;font-size:12px;">
      Sent by Real-Time AI Security System<br>
      From: {self.email_address}
    </p>
  </body>
</html>
"""
            alt = MIMEMultipart("alternative")
            alt.attach(MIMEText(plain_body, "plain", "utf-8"))
            alt.attach(MIMEText(html_body, "html", "utf-8"))
            msg.attach(alt)

            image_bytes = None
            if image_path and os.path.exists(image_path):
                with open(image_path, "rb") as handle:
                    image_bytes = handle.read()
            elif frame is not None:
                ok, buffer = cv2.imencode(
                    ".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90]
                )
                if ok:
                    image_bytes = buffer.tobytes()

            if image_bytes:
                image = MIMEImage(image_bytes, _subtype="jpeg")
                image.add_header(
                    "Content-Disposition",
                    "attachment",
                    filename="unauthorized_person.jpg",
                )
                msg.attach(image)

            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.starttls()
                server.login(self.email_address, self.email_password)
                server.send_message(msg, to_addrs=list(self.alert_recipients))
            self.last_email_error = ""
            print(f"[Email] Unauthorized alert image sent to: {self.alert_recipient}")
            return True
        except smtplib.SMTPAuthenticationError:
            self.last_email_error = (
                "Gmail login failed. Use a 16-character App Password from "
                "https://myaccount.google.com/apppasswords for realtimesecuritysystem@gmail.com "
                "(not the normal Gmail password)."
            )
            print(f"[Email Error] {self.last_email_error}")
            return False
        except Exception as exc:
            self.last_email_error = str(exc)
            print(f"[Email Error] {exc}")
            return False

    def send_test_email(self):
        with self.frame_lock:
            frame = self.last_frame.copy() if self.last_frame is not None else None
        return self.send_email_alert(
            "Security System - Test Email",
            "This is a test email from your Real-Time AI Security System.",
            frame=frame,
        )

    def save_alert_image(self, frame, prefix="unauthorized"):
        """Save alert snapshot locally and return the file path."""
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{prefix}_{stamp}.jpg"
        path = os.path.join(self.alert_image_dir, filename)
        ok = cv2.imwrite(path, frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        if ok:
            self.log_event("Alert Image", f"Saved: {filename}")
            print(f"[Alert] Image saved locally: {path}")
            return path
        print("[Alert] Failed to save alert image locally")
        return None

    def _notify_unauthorized_person(self, frame, timestamp):
        """Save unauthorized snapshot locally and email it to all configured recipients."""
        snapshot = frame.copy()
        self.log_event("Unauthorized", "Unknown person detected")
        if not self._should_alert("unauthorized_person"):
            return

        # Always on by default for unauthorized detections.
        self.settings["email_alerts"] = True

        image_path = self.save_alert_image(snapshot, prefix="unauthorized")
        recipients = ", ".join(self.alert_recipients) if self.alert_recipients else "none"
        body = (
            f"Unauthorized person detected at {timestamp}.\n"
            f"Snapshot attached and saved on the security system"
            + (f" as {os.path.basename(image_path)}" if image_path else "")
            + ".\n"
            f"This alert was sent to: {recipients}"
        )

        print(f"[Alert] Emailing unauthorized image to: {recipients}")
        threading.Thread(
            target=self.send_email_alert,
            args=(
                "Security Alert - Unauthorized Person Detected",
                body,
            ),
            kwargs={"frame": snapshot, "image_path": image_path},
            daemon=True,
        ).start()
        self.issue_voice_alert("Warning. Unauthorized person detected.")

    def issue_voice_alert(self, message):
        if self.settings["voice_alerts"]:
            threading.Thread(target=speak, args=(message,), daemon=True).start()

    def process_frame(self, frame):
        with self.process_lock:
            return self._process_frame(frame)

    def _process_frame(self, frame):
        self.frame_counter += 1
        unauthorized = False
        status = "All Clear"
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(
            frame,
            timestamp,
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
        )

        if self.settings["face_recognition"]:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            faces = face_recognition.face_locations(rgb)
            encodings = face_recognition.face_encodings(rgb, faces)

            for (top, right, bottom, left), encoding in zip(faces, encodings):
                recognized = "Unknown"
                color = (0, 0, 255)
                is_authorized = False

                if self.authorized_encodings:
                    distances = {
                        name: np.linalg.norm(encoding - known)
                        for name, known in self.authorized_encodings.items()
                    }
                    closest = min(distances, key=distances.get)
                    min_dist = distances[closest]
                    if min_dist < 0.5:
                        recognized = closest
                        color = (0, 255, 0)
                        is_authorized = True
                        self.log_event("Authorized", recognized)

                if not is_authorized:
                    unauthorized = True
                    status = "ALERT: Unauthorized Person"
                    self._notify_unauthorized_person(frame, timestamp)

                label = recognized
                if (
                    self.settings["emotion_analysis"]
                    and self.frame_counter % 15 == 0
                ):
                    try:
                        emotion = DeepFace.analyze(
                            frame[top:bottom, left:right],
                            actions=["emotion"],
                            enforce_detection=False,
                        )[0]["dominant_emotion"]
                        label = f"{recognized} - {emotion.capitalize()}"
                    except Exception:
                        pass

                cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
                cv2.putText(
                    frame,
                    label,
                    (left, top - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    color,
                    2,
                )

        if self.settings["object_detection"]:
            results = self.yolo_model(frame, device=self.device, verbose=False)
            for result in results:
                for box in result.boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    label = result.names[int(box.cls[0])]
                    confidence = float(box.conf[0])

                    if label in self.unauthorized_objects and confidence > 0.5:
                        unauthorized = True
                        status = f"ALERT: {label.upper()}"
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                        cv2.putText(
                            frame,
                            f"ALERT: {label}",
                            (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.6,
                            (0, 0, 255),
                            2,
                        )
                        self.log_event("Unauthorized Object", label)
                        if self._should_alert(f"object_{label}"):
                            self.send_email_alert(
                                f"Security Alert - {label}",
                                f"Detected {label} at {timestamp}",
                                frame=frame.copy(),
                            )
                            self.issue_voice_alert(f"Unauthorized object detected: {label}")
                    else:
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)
                        cv2.putText(
                            frame,
                            label,
                            (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.6,
                            (255, 0, 0),
                            2,
                        )

        status_color = (0, 255, 0) if status == "All Clear" else (0, 0, 255)
        cv2.putText(
            frame,
            status,
            (10, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            status_color,
            2,
        )

        if self.settings["auto_recording"]:
            if unauthorized and not self.recording:
                self.recording = True
                self.recording_start_time = datetime.datetime.now()
                filename = os.path.join(
                    self.video_output_dir,
                    f"alert_{self.recording_start_time.strftime('%Y%m%d_%H%M%S')}.avi",
                )
                self.video_writer = cv2.VideoWriter(
                    filename,
                    cv2.VideoWriter_fourcc(*"XVID"),
                    20.0,
                    (frame.shape[1], frame.shape[0]),
                )
                self.log_event("Recording", f"Started: {os.path.basename(filename)}")

            if self.recording and self.video_writer is not None:
                self.video_writer.write(frame)
                elapsed = (datetime.datetime.now() - self.recording_start_time).total_seconds()
                if elapsed > self.record_duration:
                    self.recording = False
                    self.video_writer.release()
                    self.video_writer = None
                    self.log_event("Recording", "Saved alert recording")

        self.current_status = status
        with self.frame_lock:
            self.last_frame = frame.copy()
        return frame

    def get_status(self):
        return {
            "camera_active": self.camera_active,
            "status": self.current_status,
            "device": self.device,
            "authorized_faces": len(self.authorized_encodings),
            "recording": self.recording,
            "settings": self.settings,
            "email_configured": bool(self.email_address and self.email_password),
            "email_from": self.email_address,
            "email_to": self.alert_recipient,
            "email_recipients": self.alert_recipients,
        }

    def close(self):
        if self.recording and self.video_writer is not None:
            self.video_writer.release()
        self.conn.close()


class CameraManager:
    def __init__(self, engine: SecurityEngine):
        self.engine = engine
        self.cap = None
        self.thread = None
        self.start_lock = threading.Lock()

    def start(self):
        with self.start_lock:
            if self.engine.camera_active:
                return True, "Camera is already running"
            if self.thread and self.thread.is_alive():
                return True, "Camera is already running"

            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                self.cap = None
                return False, "Could not access webcam. Check permissions and try again."

            self.engine.camera_active = True
            self.engine.current_status = "Monitoring"
            self.engine.log_event("System", "Secure camera started")
            self.thread = threading.Thread(target=self._capture_loop, daemon=True)
            self.thread.start()
            return True, "Secure camera started"

    def stop(self):
        self.engine.camera_active = False
        if self.thread:
            self.thread.join(timeout=2)
            self.thread = None
        if self.cap:
            self.cap.release()
            self.cap = None
        if self.engine.recording and self.engine.video_writer is not None:
            self.engine.video_writer.release()
            self.engine.recording = False
            self.engine.video_writer = None
        self.engine.current_status = "Idle"
        self.engine.log_event("System", "Secure camera stopped")

    def _capture_loop(self):
        while self.engine.camera_active and self.cap is not None:
            try:
                ok, frame = self.cap.read()
                if not ok:
                    self.engine.current_status = "Camera Error"
                    break
                self.engine.process_frame(frame)
            except Exception as exc:
                print(f"[Camera Error] {exc}")
                self.engine.current_status = "Processing Error"
                time.sleep(0.2)

    def get_frame_bytes(self):
        with self.engine.frame_lock:
            if self.engine.last_frame is None:
                return None
            frame = self.engine.last_frame.copy()
        ok, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if not ok:
            return None
        return buffer.tobytes()
