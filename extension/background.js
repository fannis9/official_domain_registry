const DEFAULT_SERVER = "https://registry.fannis.cc.cd";

const BADGE = {
  verified: { text: "✓", color: "#16a34a" },
  pending: { text: "…", color: "#d97706" },
  rejected: { text: "✕", color: "#dc2626" },
  revoked: { text: "✕", color: "#dc2626" },
  unknown: { text: "?", color: "#6b7280" },
  err: { text: "!", color: "#b91c1c" },
};

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

async function setBadge(tabId, key, data) {
  const b = BADGE[key] || BADGE.unknown;
  await chrome.action.setBadgeText({ tabId, text: b.text });
  await chrome.action.setBadgeBackgroundColor({ tabId, color: b.color });
  await chrome.storage.session.set({ last: { key, data } });
}

async function checkTab(tabId) {
  let tab;
  try {
    tab = await chrome.tabs.get(tabId);
  } catch {
    return;
  }
  if (!tab || !tab.url) return;
  const domain = extractDomain(tab.url);
  if (!domain) {
    await setBadge(tabId, "unknown", { domain: null });
    return;
  }
  if (isLocalHost(domain)) {
    await chrome.action.setBadgeText({ tabId, text: "" });
    await chrome.storage.session.set({ last: { key: "local", data: { domain, local: true } } });
    return;
  }
  try {
    const server = await getServer();
    const res = await fetch(`${server}/api/v1/status/${encodeURIComponent(domain)}`, {
      signal: AbortSignal.timeout(8000),
    });
    const data = await res.json();
    const key = data.in_registry ? data.status : "unknown";
    await setBadge(tabId, key, data);
    if (key === "unknown") {
      const submitted = await autoSubmit(server, domain);
      if (submitted) {
        await setBadge(tabId, "pending", {
          domain,
          in_registry: true,
          status: "pending",
          organization: domain,
          registry_type: "free",
          verification_level: 0,
        });
      }
    }
  } catch {
    await setBadge(tabId, "err", { domain, in_registry: false, status: "err" });
  }
}

async function autoSubmit(server, domain) {
  try {
    const { auto_submit_v2, submitted } = await chrome.storage.local.get(["auto_submit_v2", "submitted"]);
    if (auto_submit_v2 !== true) return false;
    const apiKey = await getApiKey();
    if (!apiKey) return false;
    const seen = submitted || {};
    const last = seen[domain];
    if (last && Date.now() - last < 24 * 3600 * 1000) return false;
    const res = await fetch(`${server}/api/v1/submissions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        domain,
        organization: domain,
        registry_type: "free",
        notes: "浏览器插件自动提交",
      }),
      signal: AbortSignal.timeout(15000),
    });
    if (!res.ok) return false;
    seen[domain] = Date.now();
    await chrome.storage.local.set({ submitted: seen });
    return true;
  } catch {
    return false;
  }
}

chrome.webNavigation.onCommitted.addListener((d) => {
  if (d.frameId === 0) checkTab(d.tabId);
});
chrome.tabs.onUpdated.addListener((tabId, info) => {
  if (info.status === "complete") checkTab(tabId);
});
chrome.tabs.onActivated.addListener((a) => checkTab(a.tabId));
