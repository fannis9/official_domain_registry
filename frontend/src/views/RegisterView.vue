<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";
import { api, ApiError } from "../api.js";
import { useAuth } from "../stores/auth.js";

const router = useRouter();
const auth = useAuth();

const stepEmail = ref("");
const stepCaptcha = ref("");
const captchaImg = ref("");
const captchaToken = ref("");
const emailToken = ref("");
const sendMsg = ref("");
const sendOk = ref(false);
const countdown = ref(0);

const form = ref({ username: "", password: "", email: "", code: "" });
const error = ref("");
const busy = ref(false);

let timer = null;

async function loadCaptcha() {
  try {
    const data = await api("/api/v1/captcha", { method: "POST", body: {} });
    captchaImg.value = data.image;
    captchaToken.value = data.captcha_token;
  } catch (e) {
    sendMsg.value = e instanceof ApiError ? e.message : "验证码加载失败";
    sendOk.value = false;
  }
}

async function sendCode() {
  sendMsg.value = "";
  if (!stepEmail.value) { sendMsg.value = "请先填写邮箱"; return; }
  if (!stepCaptcha.value) { sendMsg.value = "请先填写图形验证码"; return; }
  try {
    const data = await api("/api/v1/email-code", {
      method: "POST",
      body: { email: stepEmail.value, captcha_token: captchaToken.value, captcha_answer: stepCaptcha.value },
    });
    emailToken.value = data.email_token;
    form.value.email = stepEmail.value;
    sendMsg.value = data.message || "验证码已发送";
    sendOk.value = true;
    countdown.value = 60;
    timer = setInterval(() => {
      countdown.value -= 1;
      if (countdown.value <= 0) clearInterval(timer);
    }, 1000);
  } catch (e) {
    sendMsg.value = e instanceof ApiError ? e.message : "发送失败";
    sendOk.value = false;
  }
  await loadCaptcha();
  stepCaptcha.value = "";
}

async function submit() {
  error.value = "";
  busy.value = true;
  try {
    const data = await api("/api/v1/auth/register", {
      method: "POST",
      body: {
        username: form.value.username,
        password: form.value.password,
        email: form.value.email,
        code: form.value.code,
        email_token: emailToken.value,
      },
    });
    auth.setSession(data);
    router.push("/");
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : "网络错误";
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <div class="login-wrap">
    <div class="card pad">
      <div class="login-head">
        <h2>注册账号</h2>
        <p class="sub">注册后可提交域名，未注册用户可自由搜索域名库</p>
      </div>
      <div v-if="error" class="alert err">{{ error }}</div>

      <div style="padding:14px;border:1px dashed var(--line);border-radius:12px;margin-bottom:16px">
        <div style="font-weight:700;font-size:14px;margin-bottom:12px">第一步 · 验证邮箱</div>
        <div class="field">
          <label>邮箱 <span class="req">*</span></label>
          <input v-model.trim="stepEmail" type="email" placeholder="name@example.com">
        </div>
        <div class="field">
          <label>图形验证码 <span class="req">*</span></label>
          <div class="captcha-row">
            <input v-model.trim="stepCaptcha" placeholder="4 位验证码" autocomplete="off">
            <img :src="captchaImg || undefined" alt="验证码" title="点击刷新" @click="loadCaptcha">
          </div>
        </div>
        <button class="btn secondary block" @click="sendCode" :disabled="countdown > 0">
          {{ countdown > 0 ? countdown + 's 后可重发' : '发送邮箱验证码' }}
        </button>
        <div class="seg-hint" :style="{ color: sendOk ? 'var(--ok)' : 'var(--err)' }" v-if="sendMsg">{{ sendMsg }}</div>
      </div>

      <form @submit.prevent="submit">
        <div class="field">
          <label>用户名 <span class="req">*</span></label>
          <input v-model.trim="form.username" placeholder="3-32 位字母、数字、_ . -" required>
        </div>
        <div class="field">
          <label>密码 <span class="req">*</span></label>
          <input v-model="form.password" type="password" placeholder="至少 8 位" required>
        </div>
        <div class="field">
          <label>邮箱 <span class="req">*</span></label>
          <input v-model.trim="form.email" type="email" placeholder="与上方一致" required>
        </div>
        <div class="field">
          <label>邮箱验证码 <span class="req">*</span></label>
          <input v-model.trim="form.code" inputmode="numeric" maxlength="6" placeholder="6 位数字验证码" required>
        </div>
        <button class="btn block" type="submit" :disabled="busy">{{ busy ? "注册中…" : "注册" }}</button>
      </form>
      <p class="sub" style="margin-top: 14px; text-align: center">
        已有账号？<router-link to="/login" style="color: var(--accent); font-weight: 600">直接登录</router-link>
      </p>
    </div>
  </div>
</template>
