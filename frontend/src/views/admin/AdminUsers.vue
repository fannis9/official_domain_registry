<script setup>
import { onMounted, ref } from "vue";
import { api, ApiError, formatDate } from "../../api.js";

const users = ref([]);
const q = ref("");
const feedback = ref("");

async function load() {
  try {
    users.value = await api("/api/v1/admin/users?q=" + encodeURIComponent(q.value), { admin: true });
  } catch (e) {
    feedback.value = e instanceof ApiError ? e.message : "加载失败";
  }
}

async function removeUser(u) {
  const reason = prompt(`移除用户「${u.username}」，请填写移除理由（必填，将发送到用户邮箱）：`);
  if (!reason || !reason.trim()) { alert("移除理由必填"); return; }
  if (!confirm(`确认移除用户「${u.username}」？其提交记录将保留为匿名。`)) return;
  try {
    await api(`/api/v1/admin/users/${u.id}/remove`, { method: "POST", admin: true, body: { reason } });
    await load();
  } catch (e) {
    feedback.value = e instanceof ApiError ? e.message : "移除失败";
  }
}

onMounted(load);
</script>

<template>
  <div class="page-head">
    <div>
      <h1>用户管理</h1>
      <p class="sub">已注册账号及其提交情况。</p>
    </div>
    <router-link class="btn secondary" to="/admin">返回审核队列</router-link>
  </div>

  <div v-if="feedback" class="alert err">{{ feedback }}</div>

  <div class="toolbar">
    <input v-model.trim="q" placeholder="搜索用户名或邮箱…" style="flex: 1 1 260px" @keyup.enter="load">
    <button class="btn" @click="load">搜索</button>
  </div>

  <div class="card" style="margin-top: 16px; overflow: hidden">
    <div class="row" v-for="u in users" :key="u.id" style="grid-template-columns: 1.2fr 1.6fr 1fr 90px auto">
      <a class="domain" style="color: var(--accent-strong)">{{ u.username }}</a>
      <div class="muted">{{ u.email || '—' }}</div>
      <div class="muted">{{ formatDate(u.created_at).slice(0, 10) }}</div>
      <div class="muted">{{ u.submissions }}</div>
      <div style="display: flex; gap: 6px">
        <button class="btn danger small" @click="removeUser(u)">移除</button>
      </div>
    </div>
    <div v-if="!users.length" class="empty">没有找到用户。</div>
  </div>
</template>
