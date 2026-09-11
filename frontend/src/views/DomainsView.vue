<script setup>
import { computed, onMounted, ref } from "vue";
import { api } from "../api.js";

const type = ref("all");
const q = ref("");
const domains = ref([]);
const openGroups = ref(new Set());
const loading = ref(false);

const filtered = computed(() => {
  const kw = q.value.trim().toLowerCase();
  if (!kw) return domains.value;
  return domains.value.filter(
    (d) => d.domain.includes(kw) || d.organization.toLowerCase().includes(kw)
  );
});

const groups = computed(() => {
  const map = new Map();
  for (const d of filtered.value) {
    if (!map.has(d.organization)) map.set(d.organization, []);
    map.get(d.organization).push(d);
  }
  return Array.from(map.entries()).sort((a, b) => a[0].localeCompare(b[0]));
});

const stats = computed(() => ({
  total: domains.value.length,
  official: domains.value.filter((d) => d.registry_type === "official").length,
  free: domains.value.filter((d) => d.registry_type === "free").length,
  orgs: groups.value.length,
}));

async function load() {
  loading.value = true;
  try {
    domains.value = await api(`/api/v1/domains?limit=200&type=${type.value}`);
    openGroups.value = new Set(groups.value.length ? [groups.value[0][0]] : []);
  } finally {
    loading.value = false;
  }
}

function toggle(org) {
  const next = new Set(openGroups.value);
  if (next.has(org)) next.delete(org);
  else next.add(org);
  openGroups.value = next;
}

function setAll(open) {
  openGroups.value = open ? new Set(groups.value.map(([o]) => o)) : new Set();
}

onMounted(load);
</script>

<template>
  <div class="page-head">
    <div>
      <h1>已验证域名库</h1>
      <p class="sub">点击域名可直接跳转官网。同一组织的多个域名会折叠在一个分组里。</p>
    </div>
  </div>

  <div class="tabs">
    <button class="tab" :class="{ active: type === 'all' }" @click="type = 'all'; load()">全部</button>
    <button class="tab" :class="{ active: type === 'official' }" @click="type = 'official'; load()">官方域名</button>
    <button class="tab" :class="{ active: type === 'free' }" @click="type = 'free'; load()">自由域名</button>
  </div>

  <div class="toolbar">
    <div class="search">
      <input v-model.trim="q" placeholder="搜索域名或组织，例如 github.com / GitHub">
    </div>
    <router-link class="btn secondary" to="/">提交官网</router-link>
  </div>

  <div class="stats">
    <div class="stat"><strong>{{ stats.orgs }}</strong><span>组织数</span></div>
    <div class="stat ok"><strong>{{ stats.total }}</strong><span>已验证域名</span></div>
    <div class="stat"><strong>{{ stats.official }}</strong><span>官方域名</span></div>
    <div class="stat"><strong>{{ stats.free }}</strong><span>自由域名</span></div>
  </div>

  <div v-if="loading" class="card empty">加载中…</div>

  <template v-else>
    <div v-if="groups.length" style="display:flex;gap:8px;justify-content:flex-end;margin-bottom:10px">
      <button class="btn secondary small" @click="setAll(true)">展开全部</button>
      <button class="btn secondary small" @click="setAll(false)">收起全部</button>
    </div>

    <div v-for="[org, items] in groups" :key="org" class="group">
      <button class="group-head" :class="{ open: openGroups.has(org) }" @click="toggle(org)">
        <span class="caret">&#9654;</span>
        <b>{{ org }}</b>
        <span class="badge neutral">{{ items.length }} 个域名</span>
      </button>
      <div v-if="openGroups.has(org)" class="group-body">
        <div v-for="d in items" :key="d.id" class="row">
          <a class="domain" :href="'https://' + d.domain" target="_blank" rel="noopener noreferrer">{{ d.domain }}</a>
          <div class="muted">{{ d.category || '未分类' }}</div>
          <div><span class="badge" :class="d.registry_type === 'official' ? 'accent' : 'neutral'">{{ d.registry_type === 'official' ? '官方' : '自由' }}</span></div>
          <div><span class="badge ok">已验证</span></div>
        </div>
      </div>
    </div>

    <div v-if="!groups.length" class="card empty">没有找到符合条件的域名。</div>
  </template>
</template>
