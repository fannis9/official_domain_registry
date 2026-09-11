const DEFAULT_SERVER = "https://registry.fannis.cc.cd";

const LABELS = {
  verified: "已验证",
  pending: "待审核",
  rejected: "已驳回",
  revoked: "已撤销",
  unknown: "未收录",
  err: "核验失败",
};

const TIPS = {
  verified: "该域名已通过审核，收录于官方域名注册库。",
  pending: "该域名已提交，正在等待审核团队处理。",
  rejected: "该域名曾被驳回，未被注册库收录。",
  revoked: "该域名曾被撤销，当前不在注册库中。",
  unknown: "该域名未在注册库中，可点击下方“提交审核”提交给审核团队。",
  err: "无法连接核验服务器，请检查服务器地址后重试。",
};

let currentDomain = null;

async function getServer() {
  const { server_url } = await chrome.storage.local.get("server_url");
  return (server_url || DEFAULT_SERVER).replace(/\/+$/, "");
}

async function getApiKey() {
  const { api_key } = await chrome.storage.local.get("api_key");
  return api_key || "";
}

function extractDomain(url) {
  try {
    const u = new URL(url);
    if (u.protocol !== "http:" && u.protocol !== "https:") return null;
    return u.hostname.toLowerCase().replace(/\.+$/, "");
  } catch {
    return null;
  }
}

function isLocalHost(host) {
  if (!host) return true;
  if (host === "localhost" || host.endsWith(".localhost")) return true;
  if (/^(\d{1,3}\.){3}\d{1,3}$/.test(host)) return true;
  if (host.includes(":")) return true;
  return false;
}

function setFeedback(text, ok = true) {
  const el = document.getElementById("feedback");
  el.textContent = text;
  el.style.color = ok ? "#067647" : "#b42318";
  el.classList.toggle("hidden", !text);
}

function render(key, data) {
  currentDomain = (data && data.domain) || null;
  const badge = document.getElementById("badge");
  const meta = document.getElementById("meta");
  const tip = document.getElementById("tip");
  badge.className = "badge " + key;
  badge.textContent = LABELS[key] || key;
  tip.textContent = TIPS[key] || "";

  const submitBtn = document.getElementById("submit-domain");
  submitBtn.style.display = key === "unknown" ? "" : "none";
  if (key === "err") submitBtn.style.display = "none";

  if (!data || !data.in_registry) {
    document.getElementById("domain").textContent = currentDomain || "—";
    meta.innerHTML = "";
    return;
  }
  document.getElementById("domain").textContent = data.domain;
  const rows = [];
  if (data.organization) rows.push(`<b>组织</b>：${escapeHtml(data.organization)}`);
  if (data.registry_type) rows.push(`<b>类型</b>：${data.registry_type === "official" ? "官方域名" : "自由域名"}`);
  if (data.category) rows.push(`<b>类别</b>：${escapeHtml(data.category)}`);
  rows.push(`<b>信任等级</b>：L${data.verification_level ?? 0}`);
  meta.innerHTML = rows.join("<br>");
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

async function refresh() {
  setFeedback("");
  document.getElementById("badge").className = "badge unknown";
  document.getElementById("badge").textContent = "查询中…";
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const domain = tab && tab.url ? extractDomain(tab.url) : null;
  if (!domain) {
    render("unknown", { domain: null });
    return;
  }
  if (isLocalHost(domain)) {
    render("unknown", { domain });
    document.getElementById("badge").className = "badge unknown";
    document.getElementById("badge").textContent = "本机地址";
    document.getElementById("tip").textContent = "本机地址（localhost / IP）不参与核验与提交。";
    document.getElementById("submit-domain").style.display = "none";
    return;
  }
  try {
    const server = await getServer();
    const res = await fetch(`${server}/api/v1/status/${encodeURIComponent(domain)}`, {
      signal: AbortSignal.timeout(8000),
    });
    const data = await res.json();
    render(data.in_registry ? data.status : "unknown", data);
  } catch {
    render("err", { domain });
  }
}

async function checkLogin() {
  try {
    const server = await getServer();
    const apiKey = await getApiKey();
    const bar = document.getElementById("login-bar");
    if (!apiKey) {
      bar.style.display = "";
      return false;
    }
    const res = await fetch(`${server}/api/v1/auth/whoami`, {
      headers: { Authorization: `Bearer ${apiKey}` },
      signal: AbortSignal.timeout(5000),
    });
    const data = await res.json().catch(() => null);
    const ok = res.ok && data && data.logged_in;
    bar.style.display = ok ? "none" : "";
    if (ok && data.username) {
      const el = document.getElementById("username");
      el.textContent = data.username;
      document.getElementById("user-bar").style.display = "";
    } else {
      document.getElementById("user-bar").style.display = "none";
    }
    return ok;
  } catch {
    document.getElementById("login-bar").style.display = "none";
    document.getElementById("user-bar").style.display = "none";
    return false;
  }
}

async function submitCurrent() {
  if (!currentDomain) return;
  setFeedback("提交中…", true);
  const server = await getServer();
  const apiKey = await getApiKey();
  try {
    const res = await fetch(`${server}/api/v1/submissions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        domain: currentDomain,
        organization: currentDomain,
        registry_type: "free",
        notes: "浏览器插件提交",
      }),
      signal: AbortSignal.timeout(15000),
    });
    if (res.status === 401) {
      setFeedback("API Key 无效，请在网站个人中心生成后填入", false);
      document.getElementById("login-bar").style.display = "";
      return;
    }
    if (res.ok) {
      setFeedback("已提交审核，可在网站个人中心查看进度", true);
      render("pending", { domain: currentDomain, in_registry: true, status: "pending", organization: currentDomain, registry_type: "free", verification_level: 0 });
      const tab = (await chrome.tabs.query({ active: true, currentWindow: true }))[0];
      if (tab) {
        chrome.action.setBadgeText({ tabId: tab.id, text: "…" });
        chrome.action.setBadgeBackgroundColor({ tabId: tab.id, color: "#d97706" });
      }
    } else {
      let detail = "提交失败（HTTP " + res.status + "）";
      try { const j = await res.json(); if (j.detail) detail = j.detail; } catch {}
      setFeedback(detail, false);
    }
  } catch {
    setFeedback("提交失败，无法连接服务器", false);
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  const { server_url, api_key, auto_submit_v2 } = await chrome.storage.local.get(["server_url", "api_key", "auto_submit_v2"]);
  document.getElementById("server-url").value = server_url || DEFAULT_SERVER;
  document.getElementById("api-key").value = api_key || "";
  document.getElementById("auto-submit").checked = auto_submit_v2 === true;
  await checkLogin();
  await refresh();

  document.getElementById("refresh").onclick = refresh;
  document.getElementById("submit-domain").onclick = submitCurrent;
  document.getElementById("go-login").onclick = async () => {
    const server = await getServer();
    chrome.tabs.create({ url: `${server}/login` });
  };
  document.getElementById("save-server").onclick = async () => {
    const url = document.getElementById("server-url").value.trim() || DEFAULT_SERVER;
    await chrome.storage.local.set({ server_url: url });
    await refresh();
  };
  document.getElementById("save-api-key").onclick = async () => {
    const key = document.getElementById("api-key").value.trim();
    await chrome.storage.local.set({ api_key: key });
    await checkLogin();
    await refresh();
  };
  document.getElementById("auto-submit").onchange = async (e) => {
    await chrome.storage.local.set({ auto_submit_v2: e.target.checked });
  };
  document.getElementById("open-list").onclick = async () => {
    const server = await getServer();
    chrome.tabs.create({ url: `${server}/domains` });
  };
});
