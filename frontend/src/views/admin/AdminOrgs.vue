<script setup>
import { onMounted, ref } from "vue";
import { api, ApiError } from "../../api.js";

const orgs = ref([]);
const feedback = ref("");
const editing = ref(null);
const editName = ref("");

async function load() {
  try {
    orgs.value = await api("/api/v1/admin/orgs", { admin: true });
  } catch (e) {
    feedback.value = e instanceof ApiError ? e.message : "加载失败";
  }
}

function startRename(o) {
  editing.value = o.organization;
  editName.value = o.organization;
}

function cancelRename() {
  editing.value = null;
}

async function confirmRename(o) {
  const name = editName.value.trim();
  if (!name) { feedback.value = "组织名不能为空"; return; }
  if (name === o.organization) { editing.value = null; return; }
  try {
    await api("/api/v1/admin/orgs/rename", { method: "POST", admin: true, body: { old: o.organization, new: name } });
    editing.value = null;
    await load();
  } catch (e) {
    feedback.value = e instanceof ApiError ? e.message : "操作失败";
  }
}

async function dissolve(o) {
  if (!window.confirm(`解散组织「${o.organization}」？所有成员将变为独立域名。`)) return;
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
      <p class="sub">重命名会把该组织下所有域名一起移动；解散组织让成员成为独立域名。组织名=唯一成员域名的独立域名不在此显示。</p>
    </div>
    <router-link class="btn secondary" to="/admin">返回审核队列</router-link>
  </div>

  <div v-if="feedback" class="alert err">{{ feedback }}<button class="btn secondary small" style="margin-left:10px" @click="feedback = ''">关闭</button></div>

  <div style="display: flex; flex-direction: column; gap: 14px; margin-bottom: 36px">
    <article v-for="o in orgs" :key="o.organization" class="card q-item">
      <div>
        <div class="q-title">
          <template v-if="editing === o.organization">
            <input v-model.trim="editName" style="max-width: 320px">
            <button class="btn accent small" @click="confirmRename(o)">保存</button>
            <button class="btn secondary small" @click="cancelRename">取消</button>
          </template>
          <template v-else>
            <b style="font-size: 16px">{{ o.organization }}</b>
            <span class="badge neutral">{{ o.members.length }} 个域名</span>
          </template>
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
        <button class="btn accent small" @click="startRename(o)">重命名</button>
        <button class="btn danger small" @click="dissolve(o)">解散组织</button>
      </div>
    </article>
    <div v-if="!orgs.length" class="card empty">还没有任何组织。</div>
  </div>
</template>
