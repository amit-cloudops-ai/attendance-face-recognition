import { login } from "./shared/auth.js";

const button = document.querySelector("#continue-signin");
const message = document.querySelector("#signin-message");
const params = new URLSearchParams(location.search);
const requested = params.get("returnTo");
const returnTo = requested === "/admin/" ? "/admin/" : "/";

button.addEventListener("click", async () => {
  button.disabled = true;
  button.textContent = "Connecting securely…";
  message.textContent = "Redirecting to your organisation’s secure identity service.";
  try {
    await login(returnTo, { hosted: true });
  } catch (error) {
    button.disabled = false;
    button.innerHTML = 'Continue to secure sign in <span aria-hidden="true">↗</span>';
    message.textContent = error.message || "Unable to start sign-in. Please try again.";
    message.classList.add("error");
  }
});
