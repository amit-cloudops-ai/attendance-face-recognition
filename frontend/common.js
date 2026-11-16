// Shared config, Cognito PKCE auth and API client. No build step.
const S = sessionStorage;
// ---- Local mock mode: only on localhost, enabled by opening index.html?mock=1. No AWS needed.
const LOCAL = ['localhost','127.0.0.1'].includes(location.hostname);
if (LOCAL && new URLSearchParams(location.search).get('mock') === '1') S.setItem('mock', '1');
const mocking = () => LOCAL && S.getItem('mock') === '1';
const db = {n:0, emps:[
  {employee_id:'EMP001', name:'Priya Sharma', department:'Engineering', active:true, photo_count:2},
  {employee_id:'EMP002', name:'Rahul Verma', department:'Sales', active:true, photo_count:0}]};
const CYCLE = ['matched','no_face','low_quality','multiple_faces','no_match','inactive','error'];
async function mockApi(path, {method='GET', body} = {}) {
  await new Promise(r => setTimeout(r, 300));
  const emp = id => db.emps.find(e => e.employee_id === decodeURIComponent(id));
  if (path === '/api/kiosk/upload-url') return {request_id:'scan-' + (++db.n), url:'mock', fields:{}};
  if (path.startsWith('/api/kiosk/result/')) {
    const id = path.split('/').pop();
    if (id.startsWith('enrol-')) return {code:'enrolled'};
    return {code:CYCLE[(Number(id.split('-')[1]) - 1) % CYCLE.length], name:'Priya Sharma', action:'clock_in', time:'2026-01-01T' + new Date().toTimeString().slice(0, 5)};
  }
  if (path === '/api/admin/employees' && method === 'POST') { db.emps.push({...body, active:true, photo_count:0}); return {};}
  if (path === '/api/admin/employees') return {items:db.emps};
  if (path.endsWith('/enroll-url')) { const e = emp(path.split('/')[4]); if (e) e.photo_count++; return {request_id:'enrol-' + (++db.n), url:'mock', fields:{}}; }
  if (path.endsWith('/faces')) { const e = emp(path.split('/')[4]); if (e) e.photo_count = 0; return {}; }
  if (path === '/api/admin/attendance') return {items:[
    {date:'2026-01-01', employee_id:'EMP001', clock_in:'2026-01-01T09:02', clock_out:'2026-01-01T18:05', status:'present'},
    {date:'2026-01-01', employee_id:'EMP002', clock_in:'2026-01-01T09:41', clock_out:'', status:'late'}]};
  if (path === '/api/admin/reports') return {summary:{present:1, late:1, absent:0}};
  return {};
}
let CFG;
export async function cfg() { return CFG ||= await (await fetch('/config.json', {cache:'no-store'})).json(); }
const b64u = b => btoa(String.fromCharCode(...new Uint8Array(b))).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');
const redirectUri = () => location.origin + '/index.html';

export async function login(next) {
  const c = await cfg();
  const verifier = b64u(crypto.getRandomValues(new Uint8Array(48)));
  const challenge = b64u(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier)));
  const state = b64u(crypto.getRandomValues(new Uint8Array(16)));
  S.setItem('pkce', JSON.stringify({verifier, state, next}));
  const p = new URLSearchParams({response_type:'code', client_id:c.clientId, redirect_uri:redirectUri(),
    scope:'openid email', code_challenge_method:'S256', code_challenge:challenge, state});
  location.href = `${c.cognitoDomain}/oauth2/authorize?${p}`;
}
export async function handleCallback() {
  const q = new URLSearchParams(location.search), code = q.get('code');
  if (!code) return false;
  const saved = JSON.parse(S.getItem('pkce') || '{}');
  if (q.get('state') !== saved.state) throw new Error('Sign-in could not be verified. Please try again.');
  const c = await cfg();
  const r = await fetch(`${c.cognitoDomain}/oauth2/token`, {method:'POST',
    headers:{'Content-Type':'application/x-www-form-urlencoded'},
    body:new URLSearchParams({grant_type:'authorization_code', client_id:c.clientId, code, redirect_uri:redirectUri(), code_verifier:saved.verifier})});
  if (!r.ok) throw new Error('Sign-in failed. Please try again.');
  S.setItem('tokens', JSON.stringify(await r.json()));
  S.removeItem('pkce');
  location.replace(saved.next || '/index.html');
  return true;
}
const tokens = () => JSON.parse(S.getItem('tokens') || 'null');
const claims = t => JSON.parse(atob(t.id_token.split('.')[1].replace(/-/g,'+').replace(/_/g,'/')));
export function user() {
  if (mocking()) return {email:'mock@localhost', groups:['admin','kiosk']};
  const t = tokens(); if (!t) return null;
  const p = claims(t);
  // An expired id token is fine while a refresh token exists: api() renews it.
  if (p.exp * 1000 < Date.now() && !t.refresh_token) { S.removeItem('tokens'); return null; }
  return {email:p.email, groups:p['cognito:groups'] || []};
}
// Renew the id token shortly before it expires so a kiosk can stay signed in all day.
async function freshToken() {
  const t = tokens(); if (!t) return null;
  if (claims(t).exp * 1000 - Date.now() > 60000) return t.id_token;
  const c = await cfg();
  const r = t.refresh_token && await fetch(`${c.cognitoDomain}/oauth2/token`, {method:'POST',
    headers:{'Content-Type':'application/x-www-form-urlencoded'},
    body:new URLSearchParams({grant_type:'refresh_token', client_id:c.clientId, refresh_token:t.refresh_token})});
  if (!r || !r.ok) { S.removeItem('tokens'); await login(location.pathname); return null; }
  const n = await r.json(); S.setItem('tokens', JSON.stringify({...t, ...n}));
  return n.id_token;
}
// Redirects to sign-in if needed; returns user if they belong to one of the groups.
export async function requireGroup(groups, next) {
  const u = user();
  if (!u) { await login(next); return null; }
  if (!u.groups.some(g => groups.includes(g))) { document.body.innerHTML = '<main><div class="msg bad">Your account does not have access to this page. Ask an administrator to add you to the right group.</div><a class="btn" href="/index.html">Back</a></main>'; return null; }
  return u;
}
export async function logout() {
  if (mocking()) { S.clear(); location.href = '/index.html'; return; }
  const c = await cfg(); S.clear();
  location.href = `${c.cognitoDomain}/logout?client_id=${c.clientId}&logout_uri=${encodeURIComponent(location.origin + '/index.html')}`;
}
// API client: adds JWT, maps {"error":{"code","message"}} bodies to Error(message) with .code
export async function api(path, {method='GET', body, query} = {}) {
  if (mocking()) return mockApi(path, {method, body});
  const c = await cfg(), idToken = await freshToken();
  const qs = query ? '?' + new URLSearchParams(Object.entries(query).filter(([,v]) => v)) : '';
  const r = await fetch(c.apiBase + path + qs, {method, headers:{Authorization:`Bearer ${idToken}`, ...(body ? {'Content-Type':'application/json'} : {})}, body: body ? JSON.stringify(body) : undefined});
  const d = await r.json().catch(() => ({}));
  if (r.status === 401) { S.removeItem('tokens'); await login(location.pathname); }
  if (!r.ok) { const e = new Error(d.error?.message || 'Something went wrong. Please try again.'); e.code = d.error?.code; throw e; }
  return d;
}
// Upload JPEG/blob using a pre-signed POST ({url, fields}); file field must come last.
export async function s3Upload(presign, blob) {
  if (mocking()) return;
  const f = new FormData();
  Object.entries(presign.fields).forEach(([k, v]) => f.append(k, v));
  f.append('file', blob);
  const r = await fetch(presign.url, {method:'POST', body:f});
  if (!r.ok) throw new Error('Photo upload failed. Please try again.');
}
// Poll GET /api/kiosk/result/{id} until code != pending.
export async function pollResult(id, tries = 15) {
  for (let i = 0; i < tries; i++) {
    const d = await api(`/api/kiosk/result/${id}`);
    if (d.code && d.code !== 'pending') return d;
    await new Promise(r => setTimeout(r, 700));
  }
  return {code:'error'};
}
export const presignOf = d => d.upload || d;   // tolerate {request_id, upload:{url,fields}} or flat shape
export const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

if (mocking()) {
  const b = document.createElement('div');
  b.textContent = 'MOCK MODE: fake data, nothing is sent to AWS';
  b.style.cssText = 'background:#9a5b00;color:#fff;text-align:center;padding:4px;font-size:13px';
  document.body.prepend(b);
}
