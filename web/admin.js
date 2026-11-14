import { accessToken, hasGroup, login, logout, requireGroup } from "./shared/auth.js";
import { api, uploadPresigned } from "./shared/api.js";

const message = document.querySelector("#message");
const employeesBody = document.querySelector("#employees-body");
const attendanceBody = document.querySelector("#attendance-body");
const reportOutput = document.querySelector("#report-output");
const csvDownload = document.querySelector("#csv-download");
let nextCursor = null;
let lastAttendanceQuery = "";

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
    const active = cell(row, employee.active ? "Active" : "Inactive");
    active.firstChild?.classList?.add("pill");
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

async function deactivateEmployee(employeeId) {
  if (!confirm(`Deactivate ${employeeId} and permanently remove their biometric face templates? Attendance history will be retained.`)) return;
  try {
    status(`Deactivating ${employeeId} and removing face templates…`);
    await api(`/admin/employees/${encodeURIComponent(employeeId)}`, { method: "DELETE" });
    await api(`/admin/employees/${encodeURIComponent(employeeId)}/faces`, { method: "DELETE" });
    status(`${employeeId} deactivated. Face templates deleted; attendance history retained.`);
    await loadEmployees();
  } catch (error) {
    status(error.message || "Offboarding did not complete. Review the employee and face-template state.", true);
  }
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
    attendanceBody.append(row);
  }
  if (!attendanceBody.children.length) {
    const row = document.createElement("tr");
    const td = cell(row, "No matching attendance records.");
    td.colSpan = 7;
    attendanceBody.append(row);
  }
  nextCursor = data.next_cursor;
  document.querySelector("#next-page").disabled = !nextCursor;
  lastAttendanceQuery = query;
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
document.querySelector("#sign-out").addEventListener("click", logout);

try {
  if (accessToken()) {
    if (!hasGroup("admin")) throw new Error("An administrator account is required.");
    await loadEmployees();
    status("Administration ready.");
  } else {
    status("Sign in with your administrator account to continue.");
    login();
  }
} catch (error) {
  status(error.message || "Unable to load administration.", true);
}
