const startBtn = document.getElementById("startBtn");
const stopBtn = document.getElementById("stopBtn");
const videoFeed = document.getElementById("videoFeed");
const cameraPlaceholder = document.getElementById("cameraPlaceholder");
const cameraFullMount = document.getElementById("cameraFullMount");
const cameraWrapDash = document.getElementById("cameraWrapDash");
const statusPill = document.getElementById("statusPill");
const statusText = document.getElementById("statusText");
const deviceInfo = document.getElementById("deviceInfo");
const facesCount = document.getElementById("facesCount");
const recordingState = document.getElementById("recordingState");
const emailState = document.getElementById("emailState");
const emailStateDash = document.getElementById("emailStateDash");
const emailFrom = document.getElementById("emailFrom");
const emailTo = document.getElementById("emailTo");
const deviceInfoSys = document.getElementById("deviceInfoSys");
const facesCountSys = document.getElementById("facesCountSys");
const recordingStateSys = document.getElementById("recordingStateSys");
const testEmailBtn = document.getElementById("testEmailBtn");
const saveRecipientBtn = document.getElementById("saveRecipientBtn");
const recipientEmail = document.getElementById("recipientEmail");
const recipientEmail2 = document.getElementById("recipientEmail2");
const eventsList = document.getElementById("eventsList");
const eventsListDash = document.getElementById("eventsListDash");
const refreshFacesBtn = document.getElementById("refreshFacesBtn");
const toast = document.getElementById("toast");
const navRail = document.getElementById("navRail");
const menuToggle = document.getElementById("menuToggle");
const pageTitle = document.getElementById("pageTitle");
const pageSubtitle = document.getElementById("pageSubtitle");

const pageCopy = {
  dashboard: ["Dashboard", "Real Time Security monitoring overview"],
  camera: ["Live Camera", "Full-screen secure camera feed"],
  features: ["Features", "Enable or disable detection modules"],
  email: ["Email Alerts", "Send alerts to two inboxes at once"],
  events: ["Events", "Latest security activity log"],
  system: ["System Info", "Runtime and storage details"],
};

let pollTimer = null;

function showToast(message) {
  toast.textContent = message;
  toast.classList.remove("hidden");
  setTimeout(() => toast.classList.add("hidden"), 3500);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  return response.json();
}

function setView(viewName) {
  document.querySelectorAll(".view").forEach((view) => {
    view.classList.toggle("active", view.id === `view-${viewName}`);
  });
  document.querySelectorAll(".nav-item").forEach((item) => {
    item.classList.toggle("active", item.dataset.view === viewName);
  });

  const copy = pageCopy[viewName] || pageCopy.dashboard;
  pageTitle.textContent = copy[0];
  pageSubtitle.textContent = copy[1];

  if (viewName === "camera") {
    cameraFullMount.appendChild(videoFeed);
    cameraFullMount.appendChild(cameraPlaceholder);
  } else {
    cameraWrapDash.appendChild(cameraPlaceholder);
    cameraWrapDash.appendChild(videoFeed);
  }

  navRail.classList.remove("open");
}

function fillRecipientInputs(recipients) {
  const list = Array.isArray(recipients) ? recipients : [];
  const active =
    document.activeElement === recipientEmail ||
    document.activeElement === recipientEmail2;
  if (active) return;
  recipientEmail.value = list[0] || "";
  recipientEmail2.value = list[1] || "";
}

function updateStatusUI(data) {
  statusText.textContent = data.status;
  deviceInfo.textContent = data.device.toUpperCase();
  facesCount.textContent = data.authorized_faces;
  recordingState.textContent = data.recording ? "Yes" : "No";
  deviceInfoSys.textContent = data.device.toUpperCase();
  facesCountSys.textContent = data.authorized_faces;
  recordingStateSys.textContent = data.recording ? "Yes" : "No";
  emailFrom.textContent = data.email_from || "-";
  emailTo.textContent = data.email_to || "-";
  fillRecipientInputs(data.email_recipients || []);

  const emailLabel = data.email_configured ? "Ready" : "Not configured";
  emailState.textContent = emailLabel;
  emailStateDash.textContent = emailLabel;
  emailState.classList.toggle("alert-text", !data.email_configured);
  emailStateDash.classList.toggle("alert-text", !data.email_configured);

  statusPill.classList.remove("active", "alert");
  if (data.camera_active) {
    statusPill.classList.add("active");
  }
  if (data.status.includes("ALERT")) {
    statusPill.classList.add("alert");
  }

  document.querySelectorAll("[data-setting]").forEach((input) => {
    const key = input.dataset.setting;
    if (key in data.settings) {
      input.checked = data.settings[key];
    }
  });

  if (data.camera_active) {
    startBtn.disabled = true;
    stopBtn.disabled = false;
    cameraPlaceholder.classList.add("hidden");
    videoFeed.classList.remove("hidden");
  } else {
    startBtn.disabled = false;
    stopBtn.disabled = true;
    cameraPlaceholder.classList.remove("hidden");
    videoFeed.classList.add("hidden");
  }
}

function renderEvents(events, target) {
  if (!target) return;
  if (!events.length) {
    target.innerHTML = '<p class="empty-state">No events yet.</p>';
    return;
  }

  target.innerHTML = events
    .map((event) => {
      const isAlert =
        event.event_type.toLowerCase().includes("unauthorized") ||
        event.event_type.toLowerCase().includes("alert");
      return `
        <div class="event-item ${isAlert ? "alert" : ""}">
          <div class="type">${event.event_type}</div>
          <div>${event.details}</div>
          <div class="meta">${event.timestamp}</div>
        </div>
      `;
    })
    .join("");
}

async function refreshDashboard() {
  const [status, events] = await Promise.all([
    api("/api/status"),
    api("/api/events?limit=15"),
  ]);
  updateStatusUI(status);
  renderEvents(events, eventsList);
  renderEvents(events.slice(0, 8), eventsListDash);
}

async function startCamera() {
  const result = await api("/api/camera/start", { method: "POST" });
  showToast(result.message);
  if (!result.success) {
    return;
  }

  startBtn.disabled = true;
  stopBtn.disabled = false;
  cameraPlaceholder.classList.add("hidden");
  videoFeed.classList.remove("hidden");
  videoFeed.src = `/video_feed?ts=${Date.now()}`;
  refreshDashboard();
}

async function stopCamera() {
  await api("/api/camera/stop", { method: "POST" });
  startBtn.disabled = false;
  stopBtn.disabled = true;
  videoFeed.classList.add("hidden");
  videoFeed.src = "";
  cameraPlaceholder.classList.remove("hidden");
  showToast("Secure camera stopped");
  refreshDashboard();
}

async function updateSetting(key, value) {
  await api("/api/settings", {
    method: "POST",
    body: JSON.stringify({ [key]: value }),
  });
  showToast("Settings updated");
}

startBtn.addEventListener("click", startCamera);
stopBtn.addEventListener("click", stopCamera);

menuToggle.addEventListener("click", () => {
  navRail.classList.toggle("open");
});

document.querySelectorAll(".nav-item").forEach((item) => {
  item.addEventListener("click", () => setView(item.dataset.view));
});

refreshFacesBtn.addEventListener("click", async () => {
  const result = await api("/api/encodings/refresh", { method: "POST" });
  showToast(`Loaded ${result.authorized_faces} authorized face(s)`);
  refreshDashboard();
});

testEmailBtn.addEventListener("click", async () => {
  testEmailBtn.disabled = true;
  try {
    const result = await api("/api/email/test", { method: "POST" });
    showToast(result.message);
  } catch (error) {
    showToast("Failed to send test email");
  } finally {
    testEmailBtn.disabled = false;
    refreshDashboard();
  }
});

saveRecipientBtn.addEventListener("click", async () => {
  const recipient = recipientEmail.value.trim();
  const recipient2 = recipientEmail2.value.trim();
  if (!recipient) {
    showToast("Enter a primary email address first");
    return;
  }
  saveRecipientBtn.disabled = true;
  try {
    const result = await api("/api/email/recipient", {
      method: "POST",
      body: JSON.stringify({ recipient, recipient2 }),
    });
    showToast(result.message);
    if (result.success) {
      emailTo.textContent = result.email_to;
      fillRecipientInputs(result.email_recipients || []);
    }
  } catch (error) {
    showToast("Failed to save recipient emails");
  } finally {
    saveRecipientBtn.disabled = false;
    refreshDashboard();
  }
});

[recipientEmail, recipientEmail2].forEach((input) => {
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      saveRecipientBtn.click();
    }
  });
});

document.querySelectorAll("[data-setting]").forEach((input) => {
  input.addEventListener("change", () => {
    const key = input.dataset.setting;
    const value = input.checked;
    document.querySelectorAll(`[data-setting="${key}"]`).forEach((el) => {
      el.checked = value;
    });
    updateSetting(key, value);
  });
});

setView("dashboard");
refreshDashboard();
pollTimer = setInterval(refreshDashboard, 3000);
