# ------------------------------------------------------------
# Real-Time Security System (Final PyTorch 2.6+ Compatible)
# YOLOv8 + Face Recognition + DeepFace + Voice + Email Alerts
# ------------------------------------------------------------

import cv2, os, numpy as np, face_recognition, torch, io, pickle, datetime, logging, sqlite3, smtplib, threading, warnings
from email.mime.text import MIMEText
from ultralytics import YOLO
from ultralytics.nn import modules
from ultralytics.nn.tasks import DetectionModel
from torch.nn.modules.container import Sequential
from torch.nn.modules import Module
from deepface import DeepFace

# --- SUPPRESS WARNINGS ---
warnings.filterwarnings("ignore", category=UserWarning, module="face_recognition_models")
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

# --- VOICE FALLBACK ---
try:
    from ai_core.voice_output import speak
except ImportError:
    import pyttsx3
    def speak(text):
        try:
            engine = pyttsx3.init()
            engine.setProperty('rate', 175)
            engine.say(text)
            engine.runAndWait()
        except Exception as e:
            print(f"[Voice Error] {e}")

# --- LOGGER FALLBACK ---
try:
    from logger import log_message
except ImportError:
    def log_message(tag, msg): print(f"[{tag}] {msg}")

log_message("DETECT", "Logger working ✅")
log_message("AI_CORE", "Voice assistant online.")
log_message("AUTO", "Listening for automation commands...")

# --- DEVICE INFO ---
DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'
print(f"--- System Info ---")
print(f"PyTorch using: {DEVICE}")
try:
    import tensorflow as tf
    gpus = tf.config.list_physical_devices('GPU')
    print(f"TensorFlow using: {gpus[0].name}" if gpus else "TensorFlow using: CPU")
except Exception as e:
    print(f"TensorFlow check failed: {e}")
print("--------------------")

# --- LOGGING & DATABASE ---
logging.basicConfig(filename="security_log.txt", level=logging.INFO,
                    format="[%(asctime)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger()
conn = sqlite3.connect("security_events.db")
conn.execute("CREATE TABLE IF NOT EXISTS events (timestamp TEXT, event_type TEXT, details TEXT)")
conn.commit()
def log_to_db(event_type, details):
    t = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("INSERT INTO events VALUES (?,?,?)", (t, event_type, details))
    conn.commit()

# --- PATHS ---
YOLO_MODEL_PATH = "models/yolov8n.pt"
AUTHORIZED_FOLDER = r"J:\AI-Security-System-main\data\authorized_faces"
ENCODINGS_CACHE = "authorized_encodings.pkl"
VIDEO_OUTPUT_DIR = "recordings"
os.makedirs(VIDEO_OUTPUT_DIR, exist_ok=True)

# --- SAFE LOAD FOR PYTORCH ≥2.6 ---
torch.serialization.add_safe_globals([
    modules.Conv, modules.C2f, modules.C3, modules.RepC3, modules.Detect,
    DetectionModel, Sequential, Module
])
from torch.serialization import add_safe_globals
add_safe_globals([
    modules.Conv, modules.C2f, modules.C3, modules.RepC3, modules.Detect,
    DetectionModel, Sequential, Module
])
_original_load = torch.load
def patched_load(*args, **kwargs):
    kwargs["weights_only"] = False
    return _original_load(*args, **kwargs)
torch.load = patched_load

# --- LOAD YOLO MODEL ---
print("Loading YOLOv8 model...")
try:
    yolo_model = YOLO(YOLO_MODEL_PATH)
    yolo_model.to(DEVICE)
    print(f"✅ YOLOv8 model loaded and running on: {yolo_model.device}")
except Exception as e:
    print(f"❌ YOLO model load failed: {e}")
    raise SystemExit("🚫 Fatal: Could not load YOLO model.")

# --- EMAIL ALERTS ---
EMAIL_ADDRESS = "jashwanthinsrirama@gmail.com"
EMAIL_PASSWORD = "jwbrsskuwubmbibz"
def send_email_alert(subject, body):
    try:
        msg = MIMEText(body)
        msg["Subject"], msg["From"], msg["To"] = subject, EMAIL_ADDRESS, EMAIL_ADDRESS
        with smtplib.SMTP("smtp.gmail.com", 587) as s:
            s.starttls(); s.login(EMAIL_ADDRESS, EMAIL_PASSWORD); s.send_message(msg)
        print("📧 Email alert sent successfully")
    except Exception as e: print(f"❌ Email failed: {e}")

# --- VOICE ALERT ---
def issue_voice_alert(msg): threading.Thread(target=speak, args=(msg,), daemon=True).start()

# --- LOAD AUTHORIZED ENCODINGS ---
AUTHORIZED_NAMES = [n for n in os.listdir(AUTHORIZED_FOLDER)
                    if os.path.isdir(os.path.join(AUTHORIZED_FOLDER, n))]
UNAUTHORIZED_OBJECTS = ["knife", "gun", "weapon"]
AUTHORIZED_ENCODINGS = {}

if os.path.exists(ENCODINGS_CACHE):
    with open(ENCODINGS_CACHE, "rb") as f:
        AUTHORIZED_ENCODINGS = pickle.load(f)
    print("✅ Loaded cached encodings")
else:
    print("⚠ Cache not found, computing encodings...")
    for name in AUTHORIZED_NAMES:
        folder = os.path.join(AUTHORIZED_FOLDER, name)
        for img_name in os.listdir(folder):
            if img_name.lower().endswith((".jpg", ".jpeg", ".png")):
                path = os.path.join(folder, img_name)
                img = face_recognition.load_image_file(path)
                enc = face_recognition.face_encodings(img)
                if enc:
                    AUTHORIZED_ENCODINGS[name] = enc[0]
                    print(f"✅ Added {name}")
                    break
    with open(ENCODINGS_CACHE, "wb") as f:
        pickle.dump(AUTHORIZED_ENCODINGS, f)
    print("✅ Encodings cached")

# --- FRAME PROCESSING ---
recording, video_writer, recording_start_time = False, None, None
RECORD_DURATION = 10

def process_frame(frame):
    global recording, video_writer, recording_start_time, AUTHORIZED_ENCODINGS
    unauthorized, status = False, "All Clear"
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cv2.putText(frame, timestamp, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2)

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    faces = face_recognition.face_locations(rgb)
    encs = face_recognition.face_encodings(rgb, faces)

    for (top, right, bottom, left), enc in zip(faces, encs):
        recognized, color = "Unknown", (0,0,255)
        if AUTHORIZED_ENCODINGS:
            distances = {n: np.linalg.norm(enc - e) for n, e in AUTHORIZED_ENCODINGS.items()}
            closest, min_dist = min(distances, key=distances.get), min(distances.values())
            if min_dist < 0.5:
                recognized, color = closest, (0,255,0)
                log_to_db("Authorized", recognized)
            else:
                unauthorized, status = True, "ALERT: Unauthorized Person"
                log_to_db("Unauthorized", "Unknown")
                send_email_alert("Security Alert - Unauthorized Person", f"Detected at {timestamp}")
                issue_voice_alert("Warning. Unauthorized person detected.")

        try:
            emotion = DeepFace.analyze(frame[top:bottom, left:right],
                                       actions=["emotion"], enforce_detection=False)[0]['dominant_emotion']
            label = f"{recognized} - {emotion.capitalize()}"
        except Exception:
            label = recognized

        cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
        cv2.putText(frame, label, (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    # YOLO Detection
    results = yolo_model(frame, device=DEVICE, verbose=False)
    for r in results:
        for box in r.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            label, conf = r.names[int(box.cls[0])], float(box.conf[0])
            if label in UNAUTHORIZED_OBJECTS and conf > 0.5:
                unauthorized, status = True, f"ALERT: {label.upper()}"
                cv2.rectangle(frame, (x1,y1), (x2,y2), (0,0,255), 2)
                cv2.putText(frame, f"ALERT: {label}", (x1,y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,255), 2)
                log_to_db("Unauthorized Object", label)
                send_email_alert(f"Security Alert - {label}", f"Detected {label} at {timestamp}")
                issue_voice_alert(f"Unauthorized object detected: {label}")
            else:
                cv2.rectangle(frame, (x1,y1), (x2,y2), (255,0,0), 2)
                cv2.putText(frame, label, (x1,y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,0,0), 2)

    color = (0,255,0) if status=="All Clear" else (0,0,255)
    cv2.putText(frame, status, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    if unauthorized and not recording:
        recording, recording_start_time = True, datetime.datetime.now()
        filename = os.path.join(VIDEO_OUTPUT_DIR, f"alert_{recording_start_time.strftime('%Y%m%d_%H%M%S')}.avi")
        video_writer = cv2.VideoWriter(filename, cv2.VideoWriter_fourcc(*'XVID'), 20.0, (frame.shape[1], frame.shape[0]))
        print(f"🎥 Recording started: {filename}")
    if recording:
        video_writer.write(frame)
        if (datetime.datetime.now() - recording_start_time).total_seconds() > RECORD_DURATION:
            recording = False; video_writer.release(); print("📁 Recording saved")
    return frame

# --- MAIN LOOP ---
if __name__ == "__main__":
    cap = cv2.VideoCapture(0)
    while True:
        ok, frame = cap.read()
        if not ok: break
        cv2.imshow("Real-Time Security System", process_frame(frame))
        if cv2.waitKey(1) & 0xFF == ord("q"): break
    if recording and video_writer: video_writer.release()
    conn.close(); cap.release(); cv2.destroyAllWindows()
