<script setup>
import { onMounted, reactive, ref } from "vue";
import { api, ApiError, tokenStore } from "../../api.js";

const filters = reactive({ q: "", status: "", type: "", sort: "newest", page: 1 });
const rows = ref([]);
const feedback = ref("");
const selected = ref(new Set());
const batchReason = ref("");
const CATEGORIES = ["software", "nonprofit", "technology", "infrastructure", "finance", "government", "education", "media", "ecommerce", "gaming", "ai", "cloud", "security", "other"];

const STATUS = { pending: ["待审核", "warn"], verified: ["已验证", "ok"], rejected: ["已驳回", "err"], revoked: ["已撤销", "err"] };

async function load() {
  const params = new URLSearchParams({
    q: filters.q, status: filters.status, type: filters.type, sort: filters.sort, page: String(filters.page),
  });
  try {
    rows.value = await api("/api/v1/admin/domains?" + params.toString(), { admin: true });
    selected.value = new Set();
  } catch (e) {
    feedback.value = e instanceof ApiError ? e.message : "加载失败";
  }
}

async function act(d, action, payload = {}) {
  try {
    await api(`/api/v1/admin/domains/${d.id}/${action}`, { method: "POST", admin: true, body: payload });
    await load();
  } catch (e) {
    feedback.value = e instanceof ApiError ? e.message : "操作失败";
  }
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
  } catch (e) {
    feedback.value = e instanceof ApiError ? e.message : "批量操作失败";
  }
}

function logout() {
  tokenStore.clearAdmin();
  window.location.href = "/admin/login";
}

onMounted(load);
</script>

<template>
  <div class="page-head">
    <div>
      <h1>审核队列</h1>
      <p class="sub">通过人工审核的域名会进入公开域名库与 API。</p>
    </div>
    <div style="display: flex; gap: 10px">
      <router-link class="btn secondary" to="/admin/orgs">组织管理</router-link>
      <router-link class="btn secondary" to="/admin/users">用户管理</router-link>
      <button class="btn secondary" @click="logout">退出登录</button>
    </div>
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
        <div class="q-meta">{{ d.organization }} · L{{ d.verification_level }}</div>
        <div v-if="d.notes" class="q-meta">备注：{{ d.notes }}</div>
      </div>
      <div class="q-actions">
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
</template>
