import { accessToken, hasGroup, login, logout } from "./shared/auth.js";
import { api, uploadPresigned } from "./shared/api.js";

const message = document.querySelector("#message");
const employeesBody = document.querySelector("#employees-body");
const attendanceBody = document.querySelector("#attendance-body");
const reportOutput = document.querySelector("#report-output");
const csvDownload = document.querySelector("#csv-download");
const overrideDialog = document.querySelector("#override-dialog");
let nextCursor = null;
let maxPhotos = 5;

function status(text, isError = false) {
  message.textContent = text;
  message.className = isError ? "status error" : "status";
}

function cell(row, value) {
  const td = document.createElement("td");
  td.textContent = value == null || value === "" ? "—" : String(value);
  row.append(td);
  return td;
}

async function loadEmployees() {
  const data = await api("/admin/employees");
  employeesBody.replaceChildren();
  for (const employee of data.items || []) {
    const row = document.createElement("tr");
    cell(row, employee.employee_id);
    cell(row, employee.name);
    cell(row, employee.department);
    cell(row, `${employee.shift_start}–${employee.shift_end}`);
    const active = cell(row, "");
    const activePill = document.createElement("span");
    activePill.className = "pill";
    activePill.textContent = employee.active ? "Active" : "Inactive";
    active.append(activePill);
    cell(row, `${employee.photo_count || 0}/${maxPhotos}`);
    const actions = document.createElement("td");
    const group = document.createElement("div");
    group.className = "actions";
    const enroll = document.createElement("button");
    enroll.className = "secondary";
    enroll.textContent = "Enroll photos";
    enroll.disabled = !employee.active;
    enroll.addEventListener("click", () => enrollPhotos(employee));
    group.append(enroll);
    if (employee.active) {
      const deactivate = document.createElement("button");
      deactivate.className = "danger";
      deactivate.textContent = "Deactivate";
      deactivate.addEventListener("click", () => deactivateEmployee(employee.employee_id));
      group.append(deactivate);
    } else if (employee.has_face_templates) {
      const cleanup = document.createElement("button");
      cleanup.className = "danger";
      cleanup.textContent = "Retry face cleanup";
      cleanup.addEventListener("click", () => deleteFaceTemplates(employee.employee_id));
      group.append(cleanup);
    }
    actions.append(group);
    row.append(actions);
    employeesBody.append(row);
  }
  if (!employeesBody.children.length) {
    const row = document.createElement("tr");
    const td = cell(row, "No employees yet.");
    td.colSpan = 7;
    employeesBody.append(row);
  }
}

const enrollDialog = document.querySelector("#enroll-dialog");
const enrollVideo = document.querySelector("#enroll-camera");
const enrollCanvas = document.querySelector("#enroll-capture-canvas");
const enrollInstructions = document.querySelector("#enroll-instructions");
const enrollMessage = document.querySelector("#enroll-status");
const enrollPreviews = document.querySelector("#enroll-previews");
const enrollCaptureButton = document.querySelector("#enroll-capture");
const enrollRetakeButton = document.querySelector("#enroll-retake");
const enrollSubmitButton = document.querySelector("#enroll-submit");
let enrollmentStream = null;
let enrollmentEmployee = null;
let enrollmentFiles = [];
let enrollmentPreviewUrls = [];
let enrollmentMinimum = 3;
let enrollmentRemaining = 0;
let enrollmentUploading = false;

function stopEnrollmentCamera() {
  if (enrollmentStream) {
    for (const track of enrollmentStream.getTracks()) track.stop();
    enrollmentStream = null;
  }
  enrollVideo.srcObject = null;
}

function clearEnrollmentPreviews() {
  for (const url of enrollmentPreviewUrls) URL.revokeObjectURL(url);
  enrollmentPreviewUrls = [];
  enrollPreviews.replaceChildren();
}

function enrollmentPrompt() {
  if (Number(enrollmentEmployee?.photo_count || 0) > 0) {
    return "Look straight at the camera. Use even lighting and keep your face unobstructed.";
  }
  const prompts = [
    "Photo 1 of 3 — look straight at the camera.",
    "Photo 2 of 3 — turn your head slightly to your left.",
    "Photo 3 of 3 — turn your head slightly to your right.",
    "Optional — capture another natural angle.",
    "Optional — capture one final natural angle."
  ];
  return prompts[enrollmentFiles.length] || "Enrollment photo limit reached.";
}

function renderEnrollment() {
  const count = enrollmentFiles.length;
  enrollInstructions.textContent = enrollmentPrompt();
  enrollMessage.textContent = count + " of " + enrollmentRemaining + " photos captured. " + enrollmentMinimum + " required.";
  enrollCaptureButton.disabled = enrollmentUploading || count >= enrollmentRemaining || !enrollmentStream;
  enrollRetakeButton.disabled = enrollmentUploading || count === 0;
  enrollSubmitButton.disabled = enrollmentUploading || count < enrollmentMinimum;
  document.querySelector("#enroll-close").disabled = enrollmentUploading;
  enrollSubmitButton.textContent = enrollmentUploading ? "Uploading…" : "Upload " + count + " photo" + (count === 1 ? "" : "s");
}

async function openEnrollmentCamera() {
  if (!navigator.mediaDevices?.getUserMedia) {
    throw new Error("Camera access is unavailable in this browser. Open the secure HTTPS site in a recent Chrome or Safari browser.");
  }
  enrollmentStream = await navigator.mediaDevices.getUserMedia({
    video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 720 } },
    audio: false
  });
  enrollVideo.srcObject = enrollmentStream;
  await enrollVideo.play();
  renderEnrollment();
}

async function captureEnrollmentFrame() {
  const width = enrollVideo.videoWidth;
  const height = enrollVideo.videoHeight;
  if (!width || !height) throw new Error("The camera is still starting. Please wait a moment and try again.");
  const scale = Math.min(1, 1280 / Math.max(width, height));
  enrollCanvas.width = Math.round(width * scale);
  enrollCanvas.height = Math.round(height * scale);
  const context = enrollCanvas.getContext("2d");
  if (!context) throw new Error("This browser could not prepare the camera image.");
  context.drawImage(enrollVideo, 0, 0, enrollCanvas.width, enrollCanvas.height);
  for (const quality of [0.86, 0.76, 0.66, 0.56, 0.46]) {
    const blob = await new Promise(resolve => enrollCanvas.toBlob(resolve, "image/jpeg", quality));
    if (blob && blob.size >= 1024 && blob.size <= 1048576) {
      return new File([blob], "enrollment-" + (enrollmentFiles.length + 1) + ".jpg", { type: "image/jpeg" });
    }
  }
  throw new Error("The captured image could not be compressed below the 1 MB upload limit. Improve lighting and try again.");
}

async function enrollPhotos(employee) {
  const currentCount = Number(employee.photo_count || 0);
  enrollmentRemaining = Math.max(0, maxPhotos - currentCount);
  if (!enrollmentRemaining) {
    status(employee.employee_id + " has reached the " + maxPhotos + "-photo enrollment limit.", true);
    return;
  }
  enrollmentEmployee = employee;
  enrollmentFiles = [];
  enrollmentMinimum = currentCount > 0 ? 1 : 3;
  enrollmentUploading = false;
  clearEnrollmentPreviews();
  enrollMessage.textContent = "Requesting camera permission…";
  enrollDialog.showModal();
  renderEnrollment();
  try {
    await openEnrollmentCamera();
    status("Camera ready for " + employee.employee_id + ". Capture at least " + enrollmentMinimum + " photo(s).");
  } catch (error) {
    enrollMessage.textContent = error.message || "Unable to open the camera.";
    enrollCaptureButton.disabled = true;
    status(enrollMessage.textContent, true);
  }
}

enrollCaptureButton.addEventListener("click", async () => {
  try {
    enrollCaptureButton.disabled = true;
    const file = await captureEnrollmentFrame();
    enrollmentFiles.push(file);
    const url = URL.createObjectURL(file);
    enrollmentPreviewUrls.push(url);
    const preview = document.createElement("img");
    preview.src = url;
    preview.alt = "Captured enrollment photo " + enrollmentFiles.length;
    preview.className = "enroll-preview";
    enrollPreviews.append(preview);
    renderEnrollment();
  } catch (error) {
    enrollMessage.textContent = error.message || "Unable to capture this photo.";
    renderEnrollment();
  }
});

enrollRetakeButton.addEventListener("click", () => {
  if (!enrollmentFiles.length || enrollmentUploading) return;
  enrollmentFiles.pop();
  const url = enrollmentPreviewUrls.pop();
  if (url) URL.revokeObjectURL(url);
  const preview = enrollPreviews.lastElementChild;
  if (preview) preview.remove();
  renderEnrollment();
});

enrollSubmitButton.addEventListener("click", async () => {
  if (enrollmentUploading || enrollmentFiles.length < enrollmentMinimum || !enrollmentEmployee) return;
  const employeeId = enrollmentEmployee.employee_id;
  enrollmentUploading = true;
  stopEnrollmentCamera();
  renderEnrollment();
  let completed = 0;
  try {
    for (let index = 0; index < enrollmentFiles.length; index += 1) {
      enrollMessage.textContent = "Uploading and processing photo " + (index + 1) + " of " + enrollmentFiles.length + " for " + employeeId + "…";
      const request = await api("/admin/employees/" + encodeURIComponent(employeeId) + "/enroll-url", {
        method: "POST",
        body: "{}"
      });
      await uploadPresigned(request.upload, enrollmentFiles[index]);
      const outcome = await pollEnrollment(request.request_id);
      if (outcome.code !== "enrolled") {
        throw new Error(outcome.message || "Photo " + (index + 1) + " was rejected (" + outcome.code + ").");
      }
      completed += 1;
    }
    enrollDialog.close();
    status("Enrollment completed for " + employeeId + ": " + completed + " photo(s) indexed.");
  } catch (error) {
    enrollDialog.close();
    const detail = error.message || "Enrollment failed.";
    status(completed
      ? completed + " photo(s) indexed for " + employeeId + "; the next photo failed: " + detail + " Refreshing the confirmed count."
      : "No photo was confirmed for " + employeeId + ": " + detail, true);
  } finally {
    enrollmentUploading = false;
    await loadEmployees().catch(error => status(error.message || "Employee count could not be refreshed.", true));
  }
});

document.querySelector("#enroll-close").addEventListener("click", () => enrollDialog.close());

enrollDialog.addEventListener("cancel", event => {
  if (enrollmentUploading) event.preventDefault();
});
enrollDialog.addEventListener("close", () => {
  stopEnrollmentCamera();
  clearEnrollmentPreviews();
  enrollmentFiles = [];
  enrollmentEmployee = null;
  enrollmentUploading = false;
  renderEnrollment();
});

async function pollEnrollment(requestId) {
  const deadline = Date.now() + 60000;
  let delay = 400;
  while (Date.now() < deadline) {
    const data = await api(`/kiosk/result/${encodeURIComponent(requestId)}`);
    if (data.code !== "pending") return data;
    await new Promise(resolve => setTimeout(resolve, delay));
    delay = Math.min(1500, Math.round(delay * 1.5));
  }
  throw new Error("Enrollment is still processing. Do not upload the same photo again yet; refresh the employee list and check the photo count before starting another enrollment.");
}

async function deleteFaceTemplates(employeeId) {
  try {
    await api(`/admin/employees/${encodeURIComponent(employeeId)}/faces`, { method: "DELETE" });
    status(`${employeeId} biometric templates deleted. Attendance history retained.`);
  } catch (error) {
    status(`${employeeId} is inactive, but biometric cleanup is still pending. Use Retry face cleanup after resolving the error.`, true);
  } finally {
    await loadEmployees().catch(error => status(error.message || "Employee state could not be refreshed.", true));
  }
}

async function deactivateEmployee(employeeId) {
  if (!confirm(`Deactivate ${employeeId} and permanently remove their biometric face templates? Attendance history will be retained.`)) return;
  status(`Deactivating ${employeeId}…`);
  try {
    await api(`/admin/employees/${encodeURIComponent(employeeId)}`, { method: "DELETE" });
  } catch (error) {
    // The response may be lost after the deactivation transaction committed.
    await loadEmployees().catch(() => {});
    status(error.message || "Deactivation could not be confirmed. Refresh employee state before retrying.", true);
    return;
  }
  await deleteFaceTemplates(employeeId);
}

function attendanceQuery(cursor = null) {
  const params = new URLSearchParams();
  const employee = document.querySelector("#filter-employee").value.trim();
  const from = document.querySelector("#filter-from").value;
  const to = document.querySelector("#filter-to").value;
  const statusValue = document.querySelector("#filter-status").value;
  if (employee) params.set("employee_id", employee);
  if (from) params.set("from", from);
  if (to) params.set("to", to);
  if (statusValue) params.set("status", statusValue);
  if (cursor) params.set("cursor", cursor);
  return params.toString();
}

async function loadAttendance(cursor = null) {
  const query = attendanceQuery(cursor);
  if (!document.querySelector("#filter-employee").value.trim() &&
      !document.querySelector("#filter-from").value &&
      !document.querySelector("#filter-to").value) {
    status("Provide an employee ID or a date filter before searching.", true);
    return;
  }
  if (!cursor) {
    attendanceBody.replaceChildren();
    nextCursor = null;
    document.querySelector("#next-page").disabled = true;
  }
  const data = await api(`/admin/attendance?${query}`);
  for (const item of data.items || []) {
    const row = document.createElement("tr");
    cell(row, item.date);
    cell(row, item.employee_id);
    cell(row, item.name);
    cell(row, item.clock_in ? new Date(item.clock_in).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", timeZone: "Asia/Kolkata" }) : "—");
    cell(row, item.clock_out ? new Date(item.clock_out).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", timeZone: "Asia/Kolkata" }) : "—");
    cell(row, item.status);
    cell(row, (item.flags || []).join(", "));
    const actions = document.createElement("td");
    const override = document.createElement("button");
    override.className = "secondary";
    override.textContent = "Override";
    override.addEventListener("click", () => openOverride(item));
    actions.append(override);
    row.append(actions);
    attendanceBody.append(row);
  }
  if (!attendanceBody.children.length) {
    const row = document.createElement("tr");
    const td = cell(row, "No matching attendance records.");
    td.colSpan = 8;
    attendanceBody.append(row);
  }
  nextCursor = data.next_cursor;
  document.querySelector("#next-page").disabled = !nextCursor;
}

document.querySelector("#employee-form").addEventListener("submit", async event => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const body = Object.fromEntries(form.entries());
  body.consent = document.querySelector("#consent").checked;
  try {
    await api("/admin/employees", { method: "POST", body: JSON.stringify(body) });
    event.currentTarget.reset();
    status(`Employee ${body.employee_id} created. Enroll 3–5 photos next.`);
    await loadEmployees();
  } catch (error) {
    status(error.message || "Employee could not be created.", true);
  }
});

document.querySelector("#refresh-employees").addEventListener("click", () => loadEmployees().catch(error => status(error.message, true)));
document.querySelector("#attendance-form").addEventListener("submit", event => {
  event.preventDefault();
  loadAttendance().catch(error => status(error.message, true));
});
document.querySelector("#next-page").addEventListener("click", () => {
  if (nextCursor) loadAttendance(nextCursor).catch(error => status(error.message, true));
});
function metricCard(label, value, detail = "") {
  const card = document.createElement("article");
  card.className = "report-metric";
  const heading = document.createElement("span");
  heading.className = "report-metric-label";
  heading.textContent = label;
  const number = document.createElement("strong");
  number.className = "report-metric-value";
  number.textContent = String(value);
  card.append(heading, number);
  if (detail) {
    const note = document.createElement("span");
    note.className = "report-metric-detail";
    note.textContent = detail;
    card.append(note);
  }
  return card;
}

function reportTable(headers, rows, emptyMessage) {
  const wrap = document.createElement("div");
  wrap.className = "table-wrap report-table-wrap";
  const table = document.createElement("table");
  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  for (const heading of headers) {
    const th = document.createElement("th");
    th.textContent = heading;
    headRow.append(th);
  }
  thead.append(headRow);
  const tbody = document.createElement("tbody");
  if (!rows.length) {
    const row = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = headers.length;
    td.className = "muted";
    td.textContent = emptyMessage;
    row.append(td);
    tbody.append(row);
  } else {
    for (const values of rows) {
      const row = document.createElement("tr");
      for (const value of values) cell(row, value);
      tbody.append(row);
    }
  }
  table.append(thead, tbody);
  wrap.append(table);
  return wrap;
}

function renderDailyReport(summary) {
  const totals = summary.totals || {};
  const metrics = document.createElement("div");
  metrics.className = "report-metrics";
  metrics.append(
    metricCard("Employees", totals.employees ?? 0, "Active workforce"),
    metricCard("Present", totals.present ?? 0, "On-time attendance"),
    metricCard("Late", totals.late ?? 0, "Late arrivals"),
    metricCard("Absent", totals.absent ?? 0, "No attendance record"),
    metricCard("Missing clock-out", totals.missing_clock_out ?? 0, "Needs follow-up")
  );
  const note = document.createElement("p");
  note.className = summary.skipped ? "status pending report-note" : "muted report-note";
  note.textContent = summary.skipped
    ? "This date was skipped: " + summary.skipped + ". No absence finalization was applied."
    : "Daily attendance for " + (summary.date || "the selected date") + ".";
  const rows = (summary.records || []).map(item => [
    item.employee_id, item.name, item.status,
    item.clock_in ? new Date(item.clock_in).toLocaleTimeString("en-IN", {hour:"2-digit",minute:"2-digit",timeZone:"Asia/Kolkata"}) : "—",
    item.clock_out ? new Date(item.clock_out).toLocaleTimeString("en-IN", {hour:"2-digit",minute:"2-digit",timeZone:"Asia/Kolkata"}) : "—",
    (item.flags || []).join(", ") || "—"
  ]);
  reportOutput.replaceChildren(metrics, note, reportTable(
    ["Employee ID", "Name", "Status", "Clock in", "Clock out", "Flags"],
    rows,
    "No employee records are available for this report."
  ));
}

function renderWeeklyReport(summary) {
  const totals = summary.totals || {};
  const metrics = document.createElement("div");
  metrics.className = "report-metrics";
  metrics.append(
    metricCard("Present rate", (totals.present_pct ?? 0) + "%", "Attendance days with a clock-in"),
    metricCard("Late rate", (totals.late_pct ?? 0) + "%", "Working days marked late"),
    metricCard("Absence rate", (totals.absent_pct ?? 0) + "%", "Working days marked absent"),
    metricCard("Working days", summary.working_days ?? 0, (summary.from || "") + " — " + (summary.to || ""))
  );
  const rows = (summary.employees || []).map(item => [
    item.employee_id, item.name, item.present_days ?? 0, item.late_days ?? 0,
    item.absent_days ?? 0, (item.present_pct ?? 0) + "%",
    (item.late_pct ?? 0) + "%", (item.absent_pct ?? 0) + "%"
  ]);
  reportOutput.replaceChildren(metrics, reportTable(
    ["Employee ID", "Name", "Present", "Late", "Absent", "Present %", "Late %", "Absent %"],
    rows,
    "No employee records are available for this report."
  ));
}

function updateReportPeriodHint() {
  const type = document.querySelector("#report-type").value;
  const period = document.querySelector("#report-period");
  period.placeholder = type === "weekly" ? "YYYY-Www (e.g. 2026-W46)" : "YYYY-MM-DD";
  period.setAttribute("aria-label", type === "weekly" ? "ISO week, YYYY-Www" : "Report date, YYYY-MM-DD");
}

document.querySelector("#report-type").addEventListener("change", updateReportPeriodHint);
updateReportPeriodHint();

document.querySelector("#report-form").addEventListener("submit", async event => {
  event.preventDefault();
  const type = document.querySelector("#report-type").value;
  const period = document.querySelector("#report-period").value.trim();
  const valid = type === "daily" ? /^\\d{4}-\\d{2}-\\d{2}$/.test(period) : /^\\d{4}-W\\d{2}$/.test(period);
  if (!valid) {
    reportOutput.replaceChildren();
    const note = document.createElement("p");
    note.className = "status error";
    note.textContent = type === "weekly" ? "Enter a valid ISO week, for example 2026-W46." : "Enter a date in YYYY-MM-DD format.";
    reportOutput.append(note);
    csvDownload.classList.add("hidden");
    return;
  }
  const button = event.currentTarget.querySelector('button[type="submit"]');
  button.disabled = true;
  button.textContent = "Loading…";
  reportOutput.textContent = "Loading report…";
  csvDownload.classList.add("hidden");
  try {
    const data = await api(`/admin/reports?type=${encodeURIComponent(type)}&period=${encodeURIComponent(period)}`);
    if (type === "daily") renderDailyReport(data.summary || {});
    else renderWeeklyReport(data.summary || {});
    if (data.csv_url) {
      csvDownload.href = data.csv_url;
      csvDownload.classList.remove("hidden");
    }
  } catch (error) {
    reportOutput.replaceChildren();
    const note = document.createElement("p");
    note.className = "status error";
    note.textContent = error.message || "Report could not be loaded.";
    reportOutput.append(note);
  } finally {
    button.disabled = false;
    button.textContent = "Load report";
  }
});
async function loadSettings() {
  const data = await api("/admin/settings");
  document.querySelector("#setting-threshold").value = data.face_match_threshold;
  document.querySelector("#setting-brightness").value = data.min_brightness;
  document.querySelector("#setting-sharpness").value = data.min_sharpness;
  document.querySelector("#setting-grace").value = data.grace_minutes;
  document.querySelector("#setting-debounce").value = data.debounce_minutes;
  document.querySelector("#setting-max-photos").value = data.max_photos_per_employee;
  maxPhotos = data.max_photos_per_employee;
  document.querySelector("#setting-weekends").value = (data.weekend_days || []).join(",");
}

function openOverride(item) {
  document.querySelector("#override-employee").value = item.employee_id;
  document.querySelector("#override-date").value = item.date;
  document.querySelector("#override-status").value = item.status;
  document.querySelector("#override-clock-in").value = item.clock_in ? item.clock_in.slice(11, 16) : "";
  document.querySelector("#override-clock-out").value = item.clock_out ? item.clock_out.slice(11, 16) : "";
  document.querySelector("#override-reason").value = "";
  updateOverrideTimeFields();
  overrideDialog.showModal();
}

function updateOverrideTimeFields() {
  const absent = document.querySelector("#override-status").value === "absent";
  document.querySelector("#override-clock-in").disabled = absent;
  document.querySelector("#override-clock-out").disabled = absent;
}

document.querySelector("#override-status").addEventListener("change", updateOverrideTimeFields);
document.querySelector("#cancel-override").addEventListener("click", () => overrideDialog.close());
document.querySelector("#override-form").addEventListener("submit", async event => {
  event.preventDefault();
  const employeeId = document.querySelector("#override-employee").value;
  const day = document.querySelector("#override-date").value;
  const statusValue = document.querySelector("#override-status").value;
  const body = {
    employee_id: employeeId,
    date: day,
    status: statusValue,
    reason: document.querySelector("#override-reason").value.trim()
  };
  if (statusValue !== "absent") {
    const clockIn = document.querySelector("#override-clock-in").value;
    const clockOut = document.querySelector("#override-clock-out").value;
    if (!clockIn) {
      status("A present or late override requires a clock-in time.", true);
      return;
    }
    body.clock_in = `${day}T${clockIn}:00+05:30`;
    if (clockOut) body.clock_out = `${day}T${clockOut}:00+05:30`;
  }
  try {
    await api("/admin/attendance/override", { method: "POST", body: JSON.stringify(body) });
    overrideDialog.close();
    status(`Attendance override saved for ${employeeId} on ${day}.`);
    await loadAttendance();
  } catch (error) {
    status(error.message || "Attendance override failed.", true);
  }
});

document.querySelector("#settings-form").addEventListener("submit", async event => {
  event.preventDefault();
  const numbers = [
    ["face_match_threshold", "#setting-threshold"],
    ["min_brightness", "#setting-brightness"],
    ["min_sharpness", "#setting-sharpness"],
    ["grace_minutes", "#setting-grace"],
    ["debounce_minutes", "#setting-debounce"],
    ["max_photos_per_employee", "#setting-max-photos"]
  ];
  const body = Object.fromEntries(numbers.map(([key, selector]) => [key, Number(document.querySelector(selector).value)]));
  body.weekend_days = document.querySelector("#setting-weekends").value.split(",").map(value => value.trim()).filter(Boolean).map(Number);
  try {
    await api("/admin/settings", { method: "PUT", body: JSON.stringify(body) });
    await loadSettings();
    await loadEmployees();
    status("Attendance settings saved and audit-logged.");
  } catch (error) {
    status(error.message || "Settings could not be saved.", true);
  }
});

document.querySelector("#reload-settings").addEventListener("click", () => loadSettings().catch(error => status(error.message, true)));
document.querySelector("#sign-out").addEventListener("click", logout);

try {
  if (accessToken()) {
    if (!hasGroup("admin")) throw new Error("An administrator account is required.");
    await loadSettings();
    await loadEmployees();
    status("Administration ready.");
  } else {
    status("Sign in with your administrator account to continue.");
    login();
  }
} catch (error) {
  status(error.message || "Unable to load administration.", true);
}
