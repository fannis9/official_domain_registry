export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

const ACCESS_KEY = "odr_access_token";
const REFRESH_KEY = "odr_refresh_token";
const USER_KEY = "odr_user";
const ADMIN_KEY = "odr_admin_token";

export const tokenStore = {
  get access() { return localStorage.getItem(ACCESS_KEY) || ""; },
  set access(v) { v ? localStorage.setItem(ACCESS_KEY, v) : localStorage.removeItem(ACCESS_KEY); },
  get refresh() { return localStorage.getItem(REFRESH_KEY) || ""; },
  set refresh(v) { v ? localStorage.setItem(REFRESH_KEY, v) : localStorage.removeItem(REFRESH_KEY); },
  get user() { try { return JSON.parse(localStorage.getItem(USER_KEY) || "null"); } catch { return null; } },
  set user(v) { v ? localStorage.setItem(USER_KEY, JSON.stringify(v)) : localStorage.removeItem(USER_KEY); },
  get admin() { return localStorage.getItem(ADMIN_KEY) || ""; },
  set admin(v) { v ? localStorage.setItem(ADMIN_KEY, v) : localStorage.removeItem(ADMIN_KEY); },
  get adminRefresh() { return localStorage.getItem("odr_admin_refresh_token") || ""; },
  set adminRefresh(v) { v ? localStorage.setItem("odr_admin_refresh_token", v) : localStorage.removeItem("odr_admin_refresh_token"); },
  clearUser() { this.access = ""; this.refresh = ""; this.user = null; },
  clearAdmin() { this.admin = ""; this.adminRefresh = ""; },
};

async function request(path, { method = "GET", body, token } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(path, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  let data = null;
  try { data = await res.json(); } catch { /* non-json */ }
  if (!res.ok) {
    throw new ApiError(res.status, (data && data.detail) || `请求失败 (${res.status})`);
  }
  return data;
}

async function tryRefresh() {
  const refresh = tokenStore.refresh;
  if (!refresh) return false;
  try {
    const data = await request("/api/v1/auth/refresh", { method: "POST", body: { refresh_token: refresh } });
    tokenStore.access = data.access_token;
    tokenStore.refresh = data.refresh_token;
    return true;
  } catch {
    return false;
  }
}

async function tryRefreshAdmin() {
  const refresh = tokenStore.adminRefresh;
  if (!refresh) return false;
  try {
    const data = await request("/api/v1/auth/refresh", { method: "POST", body: { refresh_token: refresh } });
    tokenStore.admin = data.access_token;
    tokenStore.adminRefresh = data.refresh_token || refresh;
    return true;
  } catch {
    return false;
  }
}

export async function api(path, { method = "GET", body, auth = false, admin = false, retry = true } = {}) {
  const token = admin ? tokenStore.admin : tokenStore.access;
  try {
    return await request(path, { method, body, token: auth || admin ? token : undefined });
  } catch (e) {
    if (e instanceof ApiError && e.status === 401 && auth && !admin && retry) {
      if (await tryRefresh()) {
        return api(path, { method, body, auth, admin, retry: false });
      }
      tokenStore.clearUser();
      window.dispatchEvent(new Event("odr-auth-expired"));
    }
    if (e instanceof ApiError && e.status === 401 && admin && retry) {
      if (await tryRefreshAdmin()) {
        return api(path, { method, body, auth, admin, retry: false });
      }
      tokenStore.clearAdmin();
      window.location.href = "/admin/login";
    }
    throw e;
  }
}

export function formatDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}
