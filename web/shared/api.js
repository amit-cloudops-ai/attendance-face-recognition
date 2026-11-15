import { getConfig } from "./config.js";
import { accessToken, clearSession, login } from "./auth.js";

export async function api(path, options = {}) {
  const config = await getConfig();
  const token = accessToken();
  if (!token) {
    clearSession();
    await login();
    throw new Error("Your session has expired. Sign in again.");
  }
  const headers = new Headers(options.headers || {});
  headers.set("Authorization", `Bearer ${token}`);
  if (options.body && !(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const response = await fetch(`${config.apiBase.replace(/\/$/, "")}${path}`, {
    ...options,
    headers
  });
  const payload = await response.json().catch(() => ({}));
  if (response.status === 401) {
    clearSession();
    await login();
    throw new Error("Your session has expired. Sign in again.");
  }
  if (!response.ok) {
    throw new Error(payload?.error?.message || `Request failed (${response.status}).`);
  }
  return payload;
}

export async function uploadPresigned(upload, file) {
  const form = new FormData();
  for (const [key, value] of Object.entries(upload.fields || {})) form.append(key, value);
  form.append("file", file);

  let response;
  try {
    response = await fetch(upload.url, { method: "POST", body: form });
  } catch (error) {
    if (error instanceof TypeError) {
      throw new Error("The browser could not reach the secure image-upload endpoint. Check the site's security policy, S3 CORS and network connection; no upload was confirmed.");
    }
    throw error;
  }

  if (!response.ok) {
    const body = await response.text().catch(() => "");
    const code = body.match(/<Code>([^<]+)<\/Code>/)?.[1];
    throw new Error(
      "S3 rejected the image upload (HTTP " + response.status +
      (code ? ", " + code : "") + "). Check the upload configuration before retrying."
    );
  }
}
