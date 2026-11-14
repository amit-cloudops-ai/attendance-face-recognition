import { getConfig } from "./shared/config.js";
import { accessToken, hasGroup, login, logout, requireGroup } from "./shared/auth.js";
import { api, uploadPresigned } from "./shared/api.js";

const video = document.querySelector("#camera");
const canvas = document.querySelector("#capture");
const button = document.querySelector("#capture-button");
const message = document.querySelector("#message");
const result = document.querySelector("#result");
const title = document.querySelector("#result-title");
const detail = document.querySelector("#result-detail");
const signIn = document.querySelector("#sign-in");
let stream;
let cameraReady = false;

function status(text, kind = "") {
  message.textContent = text;
  message.className = `status ${kind}`;
}

function showResult(data) {
  result.classList.remove("hidden");
  const labels = {
    matched: data.action === "clock_out" ? "Clock-out recorded" : data.action === "duplicate_ignored" ? "Already clocked in" : "Clock-in recorded",
    no_match: "Face not recognised",
    no_face: "No face detected",
    multiple_faces: "One person at a time",
    low_quality: "Improve lighting and focus",
    inactive: "Account inactive",
    error: "Could not complete attendance"
  };
  title.textContent = data.name || labels[data.code] || "Processing";
  detail.textContent = data.message || "";
  status(data.message || labels[data.code] || "Attendance result received.", data.code === "matched" ? "" : "pending");
}

async function startCamera() {
  if (!navigator.mediaDevices?.getUserMedia) throw new Error("This browser does not support camera access. Use a recent Chrome or Safari browser.");
  stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false });
  video.srcObject = stream;
  await video.play();
  button.disabled = false;
  cameraReady = true;
  button.textContent = "Capture attendance";
  status("Camera ready. Position your face in the frame.");
}

async function jpegFile() {
  const width = video.videoWidth;
  const height = video.videoHeight;
  if (!width || !height) throw new Error("Camera is not ready yet.");
  const scale = Math.min(1, 1280 / Math.max(width, height));
  canvas.width = Math.round(width * scale);
  canvas.height = Math.round(height * scale);
  canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
  for (const quality of [0.86, 0.76, 0.66, 0.56, 0.46]) {
    const blob = await new Promise(resolve => canvas.toBlob(resolve, "image/jpeg", quality));
    if (blob && blob.size >= 1024 && blob.size <= 1_048_576) return new File([blob], "capture.jpg", { type: "image/jpeg" });
  }
  throw new Error("Unable to prepare a clear image within the upload size limit.");
}

async function poll(requestId) {
  const deadline = Date.now() + 8000;
  while (Date.now() < deadline) {
    const data = await api(`/kiosk/result/${encodeURIComponent(requestId)}`);
    if (data.code !== "pending") return data;
    await new Promise(resolve => setTimeout(resolve, 350));
  }
  throw new Error("Recognition is taking longer than expected. Please try again or ask reception for help.");
}

async function capture() {
  button.disabled = true;
  result.classList.add("hidden");
  try {
    status("Preparing secure upload…", "pending");
    const file = await jpegFile();
    const request = await api("/kiosk/upload-url", { method: "POST", body: "{}" });
    await uploadPresigned(request.upload, file);
    status("Image uploaded. Checking attendance…", "pending");
    showResult(await poll(request.request_id));
  } catch (error) {
    status(error.message || "Unable to complete attendance.", "error");
  } finally {
    button.disabled = false;
    button.textContent = "Capture attendance";
  }
}

signIn.addEventListener("click", () => accessToken() ? logout() : login());
button.addEventListener("click", async () => {
  if (!accessToken()) return login();
  if (!cameraReady) {
    try { await startCamera(); } catch (error) { status(error.message || "Camera unavailable.", "error"); }
    return;
  }
  await capture();
});

try {
  await getConfig();
  if (accessToken()) {
    requireGroup("kiosk");
    signIn.textContent = "Sign out";
    await startCamera();
  } else {
    signIn.textContent = "Sign in";
    status("Sign in with your kiosk account to begin.");
    button.textContent = "Sign in to continue";
    button.disabled = false;
  }
} catch (error) {
  status(error.message || "Unable to start the kiosk.", "error");
  if (accessToken()) {
    button.disabled = false;
    button.textContent = "Retry camera";
  }
}
