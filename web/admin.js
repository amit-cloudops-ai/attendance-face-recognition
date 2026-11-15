import { accessToken, hasGroup, login, logout } from "./shared/auth.js";
import { api, uploadPresigned } from "./shared/api.js";

const message = document.querySelector("#message");
const employeesBody = document.querySelector("#employees-body");
const attendanceBody = document.querySelector("#attendance-body");
const reportOutput = document.querySelector("#report-output");
const csvDownload = document.querySelector("#csv-download");
const overrideDialog = document.querySelector("#override-dialog");
let nextCursor = null;

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
    cell(row, `${employee.photo_count || 0}/5`);
    const actions = document.createElement("td");
    const group = document.createElement("div");
    group.className = "actions";
    const enroll = document.createElement("button");
    enroll.className = "secondary";
    enroll.textContent = "Enroll photos";
    enroll.disabled = !employee.active;
    enroll.addEventListener("click", () => enrollPhotos(employee.employee_id));
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

async function enrollPhotos(employeeId) {
  const picker = document.createElement("input");
  picker.type = "file";
  picker.accept = "image/jpeg,image/png,image/webp";
  picker.multiple = true;
  picker.addEventListener("change", async () => {
    const files = Array.from(picker.files || []);
    if (files.length < 3 || files.length > 5) {
      status("Select 3 to 5 varied employee photos for enrollment.", true);
      return;
    }
    try {
      for (let index = 0; index < files.length; index += 1) {
        status(`Enrolling photo ${index + 1} of ${files.length} for ${employeeId}…`);
        const file = await normalizePhoto(files[index]);
        const request = await api(`/admin/employees/${encodeURIComponent(employeeId)}/enroll-url`, { method: "POST", body: "{}" });
        await uploadPresigned(request.upload, file);
        const outcome = await pollEnrollment(request.request_id);
        if (outcome.code !== "enrolled") throw new Error(outcome.message || `Photo ${index + 1} was not accepted (${outcome.code}).`);
      }
      status(`Enrollment completed for ${employeeId}.`);
      await loadEmployees();
    } catch (error) {
      status(error.message || "Enrollment failed.", true);
    }
  });
  picker.click();
}

async function normalizePhoto(file) {
  const bitmap = await createImageBitmap(file);
  const scale = Math.min(1, 1280 / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  canvas.getContext("2d").drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();
  for (const quality of [0.86, 0.76, 0.66, 0.56, 0.46]) {
    const blob = await new Promise(resolve => canvas.toBlob(resolve, "image/jpeg", quality));
    if (blob && blob.size >= 1024 && blob.size <= 1_048_576) return new File([blob], "enrollment.jpg", { type: "image/jpeg" });
  }
  throw new Error("One selected photo could not be compressed to the 1 MB upload limit.");
}

async function pollEnrollment(requestId) {
  const deadline = Date.now() + 12000;
  while (Date.now() < deadline) {
    const data = await api(`/kiosk/result/${encodeURIComponent(requestId)}`);
    if (data.code !== "pending") return data;
    await new Promise(resolve => setTimeout(resolve, 400));
  }
  throw new Error("Enrollment processing timed out. Check the employee's photo count before retrying.");
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
  if (!cursor) attendanceBody.replaceChildren();
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
document.querySelector("#report-form").addEventListener("submit", async event => {
  event.preventDefault();
  const type = document.querySelector("#report-type").value;
  const period = document.querySelector("#report-period").value.trim();
  try {
    const data = await api(`/admin/reports?type=${encodeURIComponent(type)}&period=${encodeURIComponent(period)}`);
    reportOutput.textContent = JSON.stringify(data.summary, null, 2);
    if (data.csv_url) {
      csvDownload.href = data.csv_url;
      csvDownload.classList.remove("hidden");
    } else {
      csvDownload.classList.add("hidden");
    }
  } catch (error) {
    reportOutput.textContent = error.message || "Report could not be loaded.";
    csvDownload.classList.add("hidden");
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
    await Promise.all([loadEmployees(), loadSettings()]);
    status("Administration ready.");
  } else {
    status("Sign in with your administrator account to continue.");
    login();
  }
} catch (error) {
  status(error.message || "Unable to load administration.", true);
}
