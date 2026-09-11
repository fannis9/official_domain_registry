<script setup>
import { onMounted, ref } from "vue";
import { api, ApiError } from "../../api.js";

const orgs = ref([]);
const feedback = ref("");

async function load() {
  try {
    orgs.value = await api("/api/v1/admin/orgs", { admin: true });
  } catch (e) {
    feedback.value = e instanceof ApiError ? e.message : "加载失败";
  }
}

async function rename(o) {
  const name = prompt("新组织名（若已存在则合并）：", o.organization);
  if (!name) return;
  try {
    await api("/api/v1/admin/orgs/rename", { method: "POST", admin: true, body: { old: o.organization, new: name } });
    await load();
  } catch (e) {
    feedback.value = e instanceof ApiError ? e.message : "操作失败";
  }
}

async function dissolve(o) {
  if (!confirm(`解散组织「${o.organization}」？所有成员将变为独立域名。`)) return;
  try {
    await api("/api/v1/admin/orgs/dissolve", { method: "POST", admin: true, body: { organization: o.organization } });
    await load();
  } catch (e) {
    feedback.value = e instanceof ApiError ? e.message : "操作失败";
  }
}

async function removeMember(m) {
  try {
    await api(`/api/v1/admin/domains/${m.id}/remove-from-org`, { method: "POST", admin: true, body: {} });
    await load();
  } catch (e) {
    feedback.value = e instanceof ApiError ? e.message : "操作失败";
  }
}

onMounted(load);
</script>

<template>
  <div class="page-head">
    <div>
      <h1>组织管理</h1>
      <p class="sub">重命名会把该组织下所有域名一起移动；解散组织让成员成为独立域名。</p>
    </div>
    <router-link class="btn secondary" to="/admin">返回审核队列</router-link>
  </div>

  <div v-if="feedback" class="alert err">{{ feedback }}</div>

  <div style="display: flex; flex-direction: column; gap: 14px; margin-bottom: 36px">
    <article v-for="o in orgs" :key="o.organization" class="card q-item">
      <div>
        <div class="q-title">
          <b style="font-size: 16px">{{ o.organization }}</b>
          <span class="badge neutral">{{ o.members.length }} 个域名</span>
        </div>
        <div class="q-log" style="margin-top: 10px">
          <div v-for="m in o.members" :key="m.id" class="q-log-item" style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap">
            <a class="domain" :href="'https://' + m.domain" target="_blank" rel="noopener noreferrer" style="font-size: 14px">{{ m.domain }}</a>
            <span class="badge" :class="m.registry_type === 'official' ? 'accent' : 'neutral'">{{ m.registry_type === 'official' ? '官方' : '自由' }}</span>
            <span class="badge" :class="{ pending: 'warn', verified: 'ok', rejected: 'err', revoked: 'err' }[m.status]">{{ m.status }}</span>
            <button class="btn secondary small" @click="removeMember(m)">移出</button>
          </div>
        </div>
      </div>
      <div class="q-actions">
        <button class="btn accent small" @click="rename(o)">重命名</button>
        <button class="btn danger small" @click="dissolve(o)">解散组织</button>
      </div>
    </article>
    <div v-if="!orgs.length" class="card empty">还没有任何域名。</div>
  </div>
</template>
