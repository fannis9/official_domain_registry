<script setup>
import { onMounted, ref } from "vue";
import { api, ApiError, formatDate } from "../../api.js";

const users = ref([]);
const q = ref("");
const feedback = ref("");
const removeTarget = ref(null);
const removeReason = ref("");

async function load() {
  try {
    users.value = await api("/api/v1/admin/users?q=" + encodeURIComponent(q.value), { admin: true });
  } catch (e) {
    feedback.value = e instanceof ApiError ? e.message : "加载失败";
  }
}

function openRemove(u) {
  removeTarget.value = u;
  removeReason.value = "";
}

async function confirmRemove() {
  const u = removeTarget.value;
  if (!u) return;
  if (!removeReason.value.trim()) {
    feedback.value = "移除理由必填";
    return;
  }
  try {
    await api(`/api/v1/admin/users/${u.id}/remove`, { method: "POST", admin: true, body: { reason: removeReason.value.trim() } });
    removeTarget.value = null;
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
      <p class="sub">已注册账号及其提交情况。移除需填写理由，理由将发送到用户邮箱。</p>
    </div>
    <router-link class="btn secondary" to="/admin">返回审核队列</router-link>
  </div>

  <div v-if="feedback" class="alert err">{{ feedback }}<button class="btn secondary small" style="margin-left:10px" @click="feedback = ''">关闭</button></div>

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
        <button class="btn danger small" @click="openRemove(u)">移除</button>
      </div>
    </div>
    <div v-if="!users.length" class="empty">没有找到用户。</div>
  </div>

  <div v-if="removeTarget" class="modal-overlay" @click.self="removeTarget = null">
    <div class="modal card">
      <h3>移除用户 {{ removeTarget.username }}</h3>
      <p style="color: var(--text)">其提交记录将保留为匿名，移除理由会发送到用户邮箱。</p>
      <input v-model.trim="removeReason" placeholder="移除理由（必填）" style="margin-bottom: 14px">
      <div class="modal-actions">
        <button class="btn secondary" @click="removeTarget = null">取消</button>
        <button class="btn danger" @click="confirmRemove">确认移除</button>
      </div>
    </div>
  </div>
</template>
