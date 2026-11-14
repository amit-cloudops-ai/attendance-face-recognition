import { completeLogin } from "./auth.js";

const message = document.querySelector("#message");
try {
  const claims = await completeLogin();
  const groups = claims["cognito:groups"] || [];
  location.replace(groups.includes("admin") ? "/admin/" : "/");
} catch (error) {
  message.textContent = error.message || "Unable to sign in.";
  message.classList.add("error");
  const link = document.createElement("a");
  link.href = "/";
  link.textContent = "Return to sign in";
  message.after(link);
}
