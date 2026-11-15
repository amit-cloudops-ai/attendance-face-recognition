import { getConfig } from "./config.js";

const ACCESS = "attendance.accessToken";
const ID = "attendance.idToken";
const REFRESH = "attendance.refreshToken";
const STATE = "attendance.oauthState";
const VERIFIER = "attendance.pkceVerifier";
const NONCE = "attendance.oauthNonce";
const RETURN_TO = "attendance.returnTo";

function randomString(bytes = 32) {
  const data = crypto.getRandomValues(new Uint8Array(bytes));
  return btoa(String.fromCharCode(...data)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

async function challenge(verifier) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier));
  return btoa(String.fromCharCode(...new Uint8Array(digest)))
    .replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function decodeJwt(token) {
  try {
    const part = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    const padded = part + "=".repeat((4 - part.length % 4) % 4);
    const bytes = Uint8Array.from(atob(padded), character => character.charCodeAt(0));
    return JSON.parse(new TextDecoder().decode(bytes));
  } catch {
    return {};
  }
}

export function accessToken() {
  const token = sessionStorage.getItem(ACCESS);
  if (!token) return null;
  const claims = decodeJwt(token);
  if (!claims.exp || claims.exp * 1000 <= Date.now() + 30_000) return null;
  return token;
}

export function userClaims() {
  return decodeJwt(sessionStorage.getItem(ID) || "");
}

export function hasGroup(group) {
  const groups = userClaims()["cognito:groups"];
  return Array.isArray(groups) && groups.includes(group);
}

export function clearSession() {
  sessionStorage.removeItem(ACCESS);
  sessionStorage.removeItem(ID);
  sessionStorage.removeItem(REFRESH);
  sessionStorage.removeItem(RETURN_TO);
}

export async function login(returnTo = null, options = {}) {
  const destination = returnTo === "/admin/" || (!returnTo && location.pathname.startsWith("/admin")) ? "/admin/" : "/";
  if (!options.hosted) {
    location.assign("/signin/?returnTo=" + encodeURIComponent(destination));
    return;
  }
  const config = await getConfig();
  const state = randomString();
  const nonce = randomString();
  const verifier = randomString(48);
  const safeReturnTo = destination;
  sessionStorage.setItem(RETURN_TO, safeReturnTo);
  sessionStorage.setItem(STATE, state);
  sessionStorage.setItem(NONCE, nonce);
  sessionStorage.setItem(VERIFIER, verifier);
  const url = new URL("/oauth2/authorize", config.cognitoDomain);
  url.search = new URLSearchParams({
    client_id: config.clientId,
    response_type: "code",
    scope: "openid email profile",
    redirect_uri: `${location.origin}/callback.html`,
    state,
    nonce,
    code_challenge: await challenge(verifier),
    code_challenge_method: "S256"
  });
  location.assign(url);
}

export async function completeLogin() {
  const config = await getConfig();
  const params = new URLSearchParams(location.search);
  const code = params.get("code");
  const returnedState = params.get("state");
  const expectedState = sessionStorage.getItem(STATE);
  const verifier = sessionStorage.getItem(VERIFIER);
  const expectedNonce = sessionStorage.getItem(NONCE);
  if (params.has("error")) throw new Error(params.get("error_description") || "Sign-in was not completed.");
  if (!code || !returnedState || returnedState !== expectedState || !verifier) {
    throw new Error("The sign-in response could not be verified. Please sign in again.");
  }
  const response = await fetch(new URL("/oauth2/token", config.cognitoDomain), {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "authorization_code",
      client_id: config.clientId,
      code,
      redirect_uri: `${location.origin}/callback.html`,
      code_verifier: verifier
    })
  });
  const payload = await response.json();
  if (!response.ok || !payload.access_token || !payload.id_token) {
    throw new Error("Sign-in failed. Please try again.");
  }
  if (decodeJwt(payload.id_token).nonce !== expectedNonce) {
    throw new Error("The sign-in response could not be verified. Please sign in again.");
  }
  sessionStorage.setItem(ACCESS, payload.access_token);
  sessionStorage.setItem(ID, payload.id_token);
  if (payload.refresh_token) sessionStorage.setItem(REFRESH, payload.refresh_token);
  sessionStorage.removeItem(STATE);
  sessionStorage.removeItem(VERIFIER);
  sessionStorage.removeItem(NONCE);
  return userClaims();
}

export async function logout() {
  const config = await getConfig();
  clearSession();
  const url = new URL("/logout", config.cognitoDomain);
  url.search = new URLSearchParams({
    client_id: config.clientId,
    logout_uri: `${location.origin}/`
  });
  location.assign(url);
}

export function requireGroup(group) {
  if (!accessToken()) {
    login();
    return false;
  }
  if (!hasGroup(group) && !(group === "kiosk" && hasGroup("admin"))) {
    throw new Error("Your account does not have access to this page.");
  }
  return true;
}
