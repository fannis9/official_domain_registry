<script setup>
import { onMounted, ref } from "vue";
import { api, ApiError, formatDate } from "../api.js";
import { useAuth } from "../stores/auth.js";

const auth = useAuth();
const domains = ref([]);
const feedback = ref("");
const loading = ref(false);

const emailForm = ref({ email: "", captcha: "", code: "" });
const emailToken = ref("");
const captchaImg = ref("");
const captchaToken = ref("");

const STATUS = { pending: ["待审核", "warn"], verified: ["已验证", "ok"], rejected: ["已驳回", "err"], revoked: ["已撤销", "err"] };

async function load() {
  loading.value = true;
  try {
    domains.value = await api("/api/v1/me/domains", { auth: true });
  } catch (e) {
    feedback.value = e instanceof ApiError ? e.message : "加载失败";
  } finally {
    loading.value = false;
  }
}

async function loadCaptcha() {
  try {
    const data = await api("/api/v1/captcha", { method: "POST", body: {} });
    captchaImg.value = data.image;
    captchaToken.value = data.captcha_token;
  } catch { /* ignore */ }
}

async function sendCode() {
  feedback.value = "";
  try {
    const data = await api("/api/v1/email-code", {
      method: "POST",
      body: { email: emailForm.value.email, captcha_token: captchaToken.value, captcha_answer: emailForm.value.captcha },
    });
    emailToken.value = data.email_token;
    feedback.value = "验证码已发送，10 分钟内有效";
  } catch (e) {
    feedback.value = e instanceof ApiError ? e.message : "发送失败";
  }
  await loadCaptcha();
  emailForm.value.captcha = "";
}

async function updateEmail() {
  feedback.value = "";
  try {
    await api("/api/v1/me/email", {
      method: "POST",
      auth: true,
      body: { email: emailForm.value.email, code: emailForm.value.code, email_token: emailToken.value },
    });
    feedback.value = "邮箱已更新";
    emailForm.value.code = "";
  } catch (e) {
    feedback.value = e instanceof ApiError ? e.message : "更新失败";
  }
}

async function verify(d) {
  try {
    const r = await api("/api/v1/ownership/verify", { method: "POST", auth: true, body: { domain: d.domain } });
    feedback.value = "所有权验证成功，信任等级 L" + r.verification_level;
    await load();
  } catch (e) {
    feedback.value = e instanceof ApiError ? e.message : "验证失败";
  }
}

onMounted(() => { load(); loadCaptcha(); });
</script>

<template>
  <div class="page-head">
    <div>
      <h1>个人中心</h1>
      <p class="sub">查看账号信息与你提交的域名及其审核状态。</p>
    </div>
  </div>

  <div class="stats">
    <div class="stat"><strong>{{ auth.user?.username || '—' }}</strong><span>用户名</span></div>
    <div class="stat"><strong class="stat-mail">{{ auth.user?.email || domains.length ? '—' : '—' }}</strong><span>邮箱</span></div>
    <div class="stat"><strong>{{ domains.length }}</strong><span>提交总数</span></div>
    <div class="stat ok"><strong>{{ domains.filter(d => d.status === 'verified').length }}</strong><span>已验证</span></div>
  </div>

  <div v-if="feedback" class="alert" :class="feedback.includes('成功') || feedback.includes('已更新') || feedback.includes('已发送') ? 'ok' : 'err'">{{ feedback }}</div>

  <section class="card pad" style="margin-bottom: 18px">
    <h2>修改邮箱</h2>
    <p class="sub">需要图形验证码 + 邮箱验证码。</p>
    <div class="field" style="margin-top: 14px">
      <label>新邮箱</label>
      <div style="display: flex; gap: 10px; flex-wrap: wrap">
        <input v-model.trim="emailForm.email" type="email" placeholder="name@example.com" style="flex: 1 1 200px">
        <img :src="captchaImg || undefined" alt="验证码" title="点击刷新" class="captcha" style="height:46px;border:1px solid var(--line);border-radius:11px;cursor:pointer;background:var(--bg)" @click="loadCaptcha">
        <input v-model.trim="emailForm.captcha" placeholder="图形验证码" style="flex: 1 1 110px">
      </div>
    </div>
    <div style="display: flex; gap: 10px; flex-wrap: wrap">
      <input v-model.trim="emailForm.code" inputmode="numeric" maxlength="6" placeholder="邮箱 6 位验证码" style="flex: 1 1 180px">
      <button class="btn secondary" @click="sendCode">发送邮箱验证码</button>
      <button class="btn" @click="updateEmail">更新邮箱</button>
    </div>
  </section>

  <div style="display: flex; flex-direction: column; gap: 14px; margin-bottom: 36px">
    <div v-if="loading" class="card empty">加载中…</div>
    <article v-for="d in domains" :key="d.id" class="card q-item" :class="'q-' + d.status">
      <div>
        <div class="q-title">
          <a class="domain" :href="'https://' + d.domain" target="_blank" rel="noopener noreferrer">{{ d.domain }}</a>
          <span class="badge" :class="d.registry_type === 'official' ? 'accent' : 'neutral'">{{ d.registry_type === 'official' ? '官方' : '自由' }}</span>
          <span v-if="d.ownership_verified" class="badge ok">所有权已验证</span>
          <span class="badge" :class="STATUS[d.status]?.[1]">{{ STATUS[d.status]?.[0] || d.status }}</span>
        </div>
        <div class="q-meta">{{ d.organization }} · 信任等级 L{{ d.verification_level }} · 提交于 {{ formatDate(d.created_at) }}</div>
        <div v-if="!d.ownership_verified && (d.status === 'pending' || d.status === 'verified')" class="q-meta">
          <button class="btn ok small" @click="verify(d)">验证所有权</button>
        </div>
      </div>
    </article>
    <div v-if="!loading && !domains.length" class="card empty">
      你还没有提交过域名。<router-link to="/" style="color: var(--accent); font-weight: 600">去提交第一个</router-link>
    </div>
  </div>
</template>
