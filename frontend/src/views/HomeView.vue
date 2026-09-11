<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";
import { api, ApiError } from "../api.js";
import { useAuth } from "../stores/auth.js";

const auth = useAuth();
const router = useRouter();

const form = ref({ domain: "", organization: "", category: "", email: "", method: "dns_txt", type: "free", notes: "" });
const error = ref("");
const busy = ref(false);
const dup = ref(null);
const errModal = ref("");

function openDup(domain, status) {
  dup.value = { domain, status };
}
function closeDup() {
  dup.value = null;
}
function closeErr() {
  errModal.value = "";
}

async function submit() {
  error.value = "";
  if (!form.value.domain) { errModal.value = "请填写域名"; return; }
  try {
    const check = await api("/api/v1/check?domain=" + encodeURIComponent(form.value.domain.trim()));
    if (check.exists) { openDup(check.domain, check.status); return; }
  } catch { /* 预检查失败继续提交 */ }

  busy.value = true;
  try {
    const data = await api("/api/v1/submissions", {
      method: "POST",
      auth: true,
      body: {
        domain: form.value.domain,
        organization: form.value.organization,
        category: form.value.category || null,
        ownership_method: form.value.method,
        registry_type: form.value.type,
        notes: form.value.notes || null,
      },
    });
    router.push({ name: "submitted", state: data });
  } catch (e) {
    if (e instanceof ApiError) errModal.value = e.message;
    else errModal.value = "网络错误，请稍后重试";
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <section class="hero">
    <h1>官方域名注册服务</h1>
    <p class="sub">社区提交、团队审核、公共 API。为浏览器、安全软件、企业网关与 AI Agent 提供独立的可信官网域名来源。</p>
    <div class="hero-actions">
      <router-link class="btn" to="/domains">浏览已验证域名库</router-link>
      <router-link class="btn secondary" to="/domains">查看 API</router-link>
    </div>
  </section>

  <div class="grid-cards">
    <section class="card pad">
      <h2>提交域名</h2>
      <template v-if="auth.loggedIn">
        <p class="sub">提交后需通过 DNS 可解析检查，并等待人工审核。</p>
        <form @submit.prevent="submit" style="margin-top: 18px">
          <div class="field">
            <label>域名 <span class="req">*</span></label>
            <input v-model.trim="form.domain" placeholder="example.com" required>
          </div>
          <div class="field">
            <label>组织 / 公司 <span class="req">*</span></label>
            <input v-model.trim="form.organization" placeholder="Example Inc." required>
          </div>
          <div class="field">
            <label>类别</label>
            <input v-model.trim="form.category" placeholder="software">
          </div>
          <div class="field">
            <label>所有权验证方式</label>
            <select v-model="form.method">
              <option value="dns_txt">DNS TXT 记录</option>
              <option value="well_known">/.well-known 文件</option>
            </select>
          </div>
          <div class="field">
            <label>申请类型</label>
            <div class="seg">
              <input type="radio" id="t-free" value="free" v-model="form.type">
              <label for="t-free">自由域名</label>
              <input type="radio" id="t-official" value="official" v-model="form.type">
              <label for="t-official">申请官方域名</label>
            </div>
            <div class="seg-hint">新提交一律先入自由域名，申请官方后由审核团队评估确认。</div>
          </div>
          <div class="field">
            <label>备注</label>
            <textarea v-model.trim="form.notes" rows="3" placeholder="补充说明（可选）"></textarea>
          </div>
          <button class="btn block" type="submit" :disabled="busy">{{ busy ? "提交中…" : "提交审核" }}</button>
        </form>
      </template>
      <template v-else>
        <p class="sub">提交域名需要登录账号。未注册用户可自由搜索域名库。</p>
        <div style="margin-top: 18px; display: flex; gap: 10px; flex-wrap: wrap">
          <router-link class="btn" to="/login">登录</router-link>
          <router-link class="btn secondary" to="/register">注册账号</router-link>
        </div>
      </template>
    </section>

    <section class="card pad">
      <h2>审核流程</h2>
      <ol class="steps">
        <li><div><strong>提交</strong><span>填写域名与组织信息</span></div></li>
        <li><div><strong>自动检查</strong><span>DNS 可解析 + HTTPS/TLS 连通性</span></div></li>
        <li><div><strong>人工审核</strong><span>团队确认域名归属与用途</span></div></li>
        <li><div><strong>入库公开</strong><span>进入已验证域名库与 API</span></div></li>
      </ol>
    </section>

    <section class="card pad">
      <h2>面向使用者</h2>
      <p class="sub">验证结果仅供安全产品参考，不等于对网站当前安全性的保证。</p>
      <ul class="list">
        <li>浏览器与安全软件扩展</li>
        <li>企业网关与 DNS 过滤</li>
        <li>AI Agent 可信来源</li>
      </ul>
    </section>
  </div>

  <div v-if="dup" class="modal-overlay" @click.self="closeDup">
    <div class="modal card">
      <h3>域名已存在</h3>
      <p><b>{{ dup.domain }}</b> 已提交过（状态：{{ dup.status }}），无法重复提交。</p>
      <div class="modal-actions">
        <router-link class="btn" to="/domains">查看域名库</router-link>
        <button class="btn secondary" @click="closeDup">知道了</button>
      </div>
    </div>
  </div>

  <div v-if="errModal" class="modal-overlay" @click.self="closeErr">
    <div class="modal card">
      <h3>提交失败</h3>
      <p>{{ errModal }}</p>
      <div class="modal-actions">
        <button class="btn secondary" @click="closeErr">知道了</button>
      </div>
    </div>
  </div>
</template>
