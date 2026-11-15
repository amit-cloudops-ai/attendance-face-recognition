import { completeLogin } from "./auth.js";

const message = document.querySelector("#message");
try {
  const claims = await completeLogin();
  const groups = claims["cognito:groups"] || [];
  const requestedPath = sessionStorage.getItem("attendance.returnTo");
  sessionStorage.removeItem("attendance.returnTo");

  // Only allow the two application entry points; never redirect to an
  // arbitrary path supplied through browser storage.
  const destination = requestedPath === "/admin/" ? "/admin/" : "/";
  if (destination === "/admin/" && !groups.includes("admin")) {
    location.replace("/admin/");
  } else {
    location.replace(destination);
  }
} catch (error) {
  message.textContent = error.message || "Unable to sign in.";
  message.classList.add("error");
  const link = document.createElement("a");
  link.href = "/";
  link.textContent = "Return to sign in";
  message.after(link);
}
