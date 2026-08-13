"""Lightweight dashboard engine for website-only cloud hosting (no camera/AI)."""

import os
import sqlite3
import datetime
import logging
import threading

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


class SecurityEngine:
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.db_path = os.path.join(self.base_dir, "security_events.db")
        self.log_path = os.path.join(self.base_dir, "security_log.txt")
        self.alert_image_dir = os.path.join(self.base_dir, "alerts")
        os.makedirs(self.alert_image_dir, exist_ok=True)

        self.device = "cloud"
        self.settings = {
            "face_recognition": False,
            "object_detection": False,
            "emotion_analysis": False,
            "email_alerts": True,
            "voice_alerts": False,
            "auto_recording": False,
        }

        self.camera_active = False
        self.current_status = "Online (Website Only)"
        self.last_frame = None
        self.frame_lock = threading.Lock()
        self.authorized_encodings = {}
        self.recording = False
        self.alert_recipients = self._load_alert_recipients()
        self.email_address = os.getenv("SECURITY_EMAIL", "realtimesecuritysystem@gmail.com")
        self.email_password = os.getenv("SECURITY_EMAIL_PASSWORD", "").replace(" ", "")
        self.last_email_error = (
            "Live camera/AI runs on your local PC. This cloud site is website-only."
        )

        self._setup_logging()
        self._setup_database()
        self.log_event(
            "System",
            "Website-only mode online. Use your PC for live camera monitoring.",
        )
        print("[Mode] WEB_ONLY enabled — dashboard hosted without camera/AI models")

    @property
    def alert_recipient(self):
        return ", ".join(self.alert_recipients) if self.alert_recipients else ""

    def _normalize_email(self, value):
        return (value or "").strip()

    def _is_valid_email(self, email):
        if email.count("@") != 1:
            return False
        local, domain = email.split("@", 1)
        return bool(local) and "." in domain

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

    def set_alert_recipient(self, recipient, recipient2=""):
        email1 = self._normalize_email(recipient)
        email2 = self._normalize_email(recipient2)
        if not self._is_valid_email(email1):
            return False, "Enter a valid primary email address."
        if email2 and not self._is_valid_email(email2):
            return False, "Enter a valid second email address (or leave blank)."
        if email2 and email2.lower() == email1.lower():
            return False, "Use two different email addresses."
        recipients = [email1]
        if email2:
            recipients.append(email2)
        self.alert_recipients = recipients
        self._persist_env_value("SECURITY_ALERT_RECIPIENT", email1)
        self._persist_env_value("SECURITY_ALERT_RECIPIENT_2", email2)
        return True, f"Alert emails will be sent to {self.alert_recipient}"

    def update_settings(self, new_settings):
        for key, value in new_settings.items():
            if key in self.settings:
                self.settings[key] = bool(value)

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

    def refresh_encodings(self):
        return

    def send_test_email(self):
        self.last_email_error = (
            "Cloud website-only mode: send live alert emails from your local PC app."
        )
        return False

    def get_status(self):
        return {
            "camera_active": False,
            "status": self.current_status,
            "device": self.device,
            "authorized_faces": 0,
            "recording": False,
            "settings": self.settings,
            "email_configured": bool(self.email_address and self.email_password),
            "email_from": self.email_address,
            "email_to": self.alert_recipient,
            "email_recipients": self.alert_recipients,
            "web_only": True,
        }

    def close(self):
        self.conn.close()


class CameraManager:
    def __init__(self, engine: SecurityEngine):
        self.engine = engine

    def start(self):
        return (
            False,
            "Website-only cloud mode: live camera runs on your local PC (python main.py).",
        )

    def stop(self):
        return

    def get_frame_bytes(self):
        return None
