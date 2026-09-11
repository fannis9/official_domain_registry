<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { api, ApiError, formatDate, tokenStore } from "../../api.js";

const filters = reactive({ q: "", status: "", type: "", sort: "newest", page: 1 });
const rows = ref([]);
const total = ref(0);
const totalPages = ref(1);
const stats = ref({ pending: 0, verified: 0, rejected: 0, revoked: 0, official: 0, free: 0 });
const feedback = ref("");
const selected = ref(new Set());
const batchReason = ref("");
const CATEGORIES = ["software", "nonprofit", "technology", "infrastructure", "finance", "government", "education", "media", "ecommerce", "gaming", "ai", "cloud", "security", "other"];

const STATUS = { pending: ["待审核", "warn"], verified: ["已验证", "ok"], rejected: ["已驳回", "err"], revoked: ["已撤销", "err"] };
const ACTION_LABELS = { submitted: "提交", verified: "审核通过", rejected: "驳回", revoked: "撤销", restored: "恢复验证", reopened: "重新打开", type_changed: "类型调整", category_changed: "类别调整", org_changed: "组织调整", org_removed: "移出组织", organized: "信息整理", ownership_verified: "所有权验证通过", official_confirmed: "官方身份确认" };

const hasFilter = computed(() => !!(filters.q || filters.status || filters.type));

async function load() {
  const params = new URLSearchParams({
    q: filters.q, status: filters.status, type: filters.type, sort: filters.sort, page: String(filters.page),
  });
  try {
    const data = await api("/api/v1/admin/domains?" + params.toString(), { admin: true });
    rows.value = data.items;
    total.value = data.total;
    totalPages.value = data.total_pages;
    filters.page = data.page;
    selected.value = new Set();
  } catch (e) {
    feedback.value = e instanceof ApiError ? e.message : "加载失败";
  }
}

async function loadStats() {
  try {
    stats.value = await api("/api/v1/admin/stats", { admin: true });
  } catch { /* ignore */ }
}

async function act(d, action, payload = {}) {
  try {
    await api(`/api/v1/admin/domains/${d.id}/${action}`, { method: "POST", admin: true, body: payload });
    await load();
    await loadStats();
  } catch (e) {
    feedback.value = e instanceof ApiError ? e.message : "操作失败";
  }
}

async function saveOrg(d) {
  const org = prompt("组织名（修改后域名归入该组织）：", d.organization);
  if (!org || !org.trim()) return;
  await act(d, "set-org", { organization: org.trim() });
}

function togglePick(id) {
  const next = new Set(selected.value);
  next.has(id) ? next.delete(id) : next.add(id);
  selected.value = next;
}

async function batch(action) {
  try {
    await api("/api/v1/admin/batch", {
      method: "POST", admin: true,
      body: { ids: Array.from(selected.value).join(","), action, reason: batchReason.value },
    });
    await load();
    await loadStats();
  } catch (e) {
    feedback.value = e instanceof ApiError ? e.message : "批量操作失败";
  }
}

function setStatus(s) {
  filters.status = s;
  filters.page = 1;
  load();
}

function logout() {
  tokenStore.clearAdmin();
  window.location.href = "/admin/login";
}

onMounted(() => { load(); loadStats(); });
</script>

<template>
  <div class="page-head">
    <div>
      <h1>审核队列</h1>
      <p class="sub">通过人工审核的域名会进入公开域名库与 API。撤销后立即从公开库移除。</p>
    </div>
    <div style="display: flex; gap: 10px">
      <router-link class="btn secondary" to="/admin/orgs">组织管理</router-link>
      <router-link class="btn secondary" to="/admin/users">用户管理</router-link>
      <button class="btn secondary" @click="logout">退出登录</button>
    </div>
  </div>

  <div class="stats">
    <div class="stat warn"><strong>{{ stats.pending }}</strong><span>待审核</span></div>
    <div class="stat ok"><strong>{{ stats.verified }}</strong><span>已验证</span></div>
    <div class="stat"><strong>{{ stats.official }}</strong><span>官方域名</span></div>
    <div class="stat"><strong>{{ stats.free }}</strong><span>自由域名</span></div>
    <div class="stat err"><strong>{{ stats.rejected }}</strong><span>已驳回</span></div>
    <div class="stat err"><strong>{{ stats.revoked }}</strong><span>已撤销</span></div>
  </div>

  <div class="tabs">
    <button class="tab" :class="{ active: !filters.status }" @click="setStatus('')">全部</button>
    <button class="tab" :class="{ active: filters.status === 'pending' }" @click="setStatus('pending')">待审核 {{ stats.pending }}</button>
    <button class="tab" :class="{ active: filters.status === 'verified' }" @click="setStatus('verified')">已验证 {{ stats.verified }}</button>
    <button class="tab" :class="{ active: filters.status === 'rejected' }" @click="setStatus('rejected')">已驳回 {{ stats.rejected }}</button>
    <button class="tab" :class="{ active: filters.status === 'revoked' }" @click="setStatus('revoked')">已撤销 {{ stats.revoked }}</button>
  </div>

  <div v-if="feedback" class="alert err">{{ feedback }}</div>

  <div class="toolbar">
    <input v-model.trim="filters.q" placeholder="搜索域名或组织…" style="flex: 1 1 220px" @keyup.enter="filters.page = 1; load()">
    <select v-model="filters.status" @change="filters.page = 1; load()">
      <option value="">全部状态</option>
      <option value="pending">待审核</option>
      <option value="verified">已验证</option>
      <option value="rejected">已驳回</option>
      <option value="revoked">已撤销</option>
    </select>
    <select v-model="filters.type" @change="filters.page = 1; load()">
      <option value="">全部类型</option>
      <option value="official">官方域名</option>
      <option value="free">自由域名</option>
    </select>
    <select v-model="filters.sort" @change="load()">
      <option value="newest">最新提交</option>
      <option value="oldest">最早提交</option>
      <option value="domain">域名 A-Z</option>
      <option value="reviewed">最近审核</option>
    </select>
    <button class="btn" @click="filters.page = 1; load()">搜索</button>
    <button v-if="hasFilter" class="btn secondary" @click="filters.q = ''; filters.status = ''; filters.type = ''; filters.page = 1; load()">重置</button>
  </div>

  <div v-if="selected.size" class="card pad" style="margin: 16px 0; display: flex; gap: 10px; flex-wrap: wrap; align-items: center">
    <b>已选 {{ selected.size }} 项</b>
    <button class="btn ok small" @click="batch('verify')">批量通过</button>
    <input v-model.trim="batchReason" placeholder="批量驳回理由（可选）" style="width: 180px">
    <button class="btn danger small" @click="batch('reject')">批量驳回</button>
    <button class="btn accent small" @click="batch('official')">设为官方</button>
    <button class="btn secondary small" @click="batch('free')">设为自由</button>
  </div>

  <div style="display: flex; flex-direction: column; gap: 14px; margin: 16px 0 36px">
    <article v-for="d in rows" :key="d.id" class="card q-item" :class="'q-' + d.status">
      <div>
        <div class="q-title">
          <input type="checkbox" :checked="selected.has(d.id)" @change="togglePick(d.id)" style="width: auto">
          <a class="domain" :href="'https://' + d.domain" target="_blank" rel="noopener noreferrer">{{ d.domain }}</a>
          <span class="badge" :class="d.registry_type === 'official' ? 'accent' : 'neutral'">{{ d.registry_type === 'official' ? '官方域名' : '自由域名' }}</span>
          <span v-if="d.requested_type === 'official' && d.registry_type === 'free'" class="badge warn">申请官方</span>
          <span v-if="d.ownership_verified" class="badge ok">所有权已验证</span>
          <span v-if="d.category" class="badge neutral">{{ d.category }}</span>
          <span class="badge" :class="STATUS[d.status]?.[1]">{{ STATUS[d.status]?.[0] }}</span>
          <span v-if="d.official_verified" class="badge accent">官方认证</span>
        </div>
        <div class="q-meta">{{ d.organization }} · 信任等级 L{{ d.verification_level }} · 提交于 {{ formatDate(d.created_at) }}</div>
        <div class="q-meta">
          提交者：<template v-if="d.submitter_username">{{ d.submitter_username }}</template><template v-else>{{ d.submitter_email || '匿名' }}</template>
          <template v-if="d.submitter_username && d.submitter_email"> · {{ d.submitter_email }}</template>
        </div>
        <div v-if="d.notes" class="q-meta">备注：{{ d.notes }}</div>
        <div v-if="d.audit_logs && d.audit_logs.length" class="q-log">
          <div v-for="log in d.audit_logs" :key="log.created_at" class="q-log-item">
            <b>{{ ACTION_LABELS[log.action] || log.action }}</b> · {{ log.actor }} · {{ formatDate(log.created_at) }}<template v-if="log.detail && log.action !== 'submitted'"> — {{ log.detail }}</template>
          </div>
        </div>
      </div>
      <div class="q-actions">
        <div style="display: flex; gap: 6px">
          <input :value="d.organization" style="font-size: 13px; padding: 7px 8px; flex: 1" readonly>
          <button class="btn secondary small" style="flex: none" title="修改组织（域名归入对应组织）" @click="saveOrg(d)">改组织</button>
        </div>
        <div v-if="d.registry_type === 'official'">
          <button class="btn secondary small block" @click="act(d, 'set-type', { registry_type: 'free' })">设为自由域名</button>
        </div>
        <div v-else>
          <button class="btn accent small block" @click="act(d, 'set-type', { registry_type: 'official' })">设为官方域名</button>
        </div>
        <div style="display: flex; gap: 6px">
          <select :value="d.category || ''" @change="act(d, 'set-category', { category: $event.target.value })" style="font-size: 13px; padding: 7px 8px; flex: 1">
            <option value="">未分类</option>
            <option v-for="c in CATEGORIES" :key="c" :value="c">{{ c }}</option>
          </select>
        </div>
        <div v-if="d.status === 'pending'" style="display: flex; gap: 6px">
          <button class="btn ok small" style="flex: 1" @click="act(d, 'verify')">通过</button>
          <button class="btn danger small" style="flex: 1" @click="act(d, 'reject', { reason: prompt('驳回理由（可选）') || '' })">驳回</button>
        </div>
        <div v-else-if="d.status === 'verified'">
          <button v-if="d.registry_type === 'official' && !d.official_verified" class="btn accent small block" @click="act(d, 'confirm-official')">确认官方身份</button>
          <button class="btn danger small block" @click="act(d, 'revoke', { reason: prompt('撤销理由（可选）') || '' })">撤销</button>
        </div>
        <div v-else-if="d.status === 'revoked'" style="display: flex; gap: 6px">
          <button class="btn ok small" style="flex: 1" @click="act(d, 'restore')">恢复验证</button>
          <button class="btn danger small" style="flex: 1" @click="act(d, 'delete')">删除</button>
        </div>
        <div v-else-if="d.status === 'rejected'" style="display: flex; gap: 6px">
          <button class="btn secondary small" style="flex: 1" @click="act(d, 'reopen')">重新打开</button>
          <button class="btn danger small" style="flex: 1" @click="act(d, 'delete')">删除</button>
        </div>
      </div>
    </article>
    <div v-if="!rows.length" class="card empty">没有符合条件的域名。</div>
  </div>

  <div style="display: flex; justify-content: space-between; align-items: center; margin: 0 0 36px" v-if="totalPages > 1">
    <div class="muted">第 {{ filters.page }} / {{ totalPages }} 页，共 {{ total }} 条</div>
    <div style="display: flex; gap: 8px">
      <button class="btn secondary" :disabled="filters.page <= 1" @click="filters.page--; load()">上一页</button>
      <button class="btn" :disabled="filters.page >= totalPages" @click="filters.page++; load()">下一页</button>
    </div>
  </div>
</template>
