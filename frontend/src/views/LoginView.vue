<script setup>
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { api, ApiError } from "../api.js";
import { useAuth } from "../stores/auth.js";

const router = useRouter();
const route = useRoute();
const auth = useAuth();

const username = ref("");
const password = ref("");
const error = ref("");
const busy = ref(false);

async function submit() {
  error.value = "";
  busy.value = true;
  try {
    const data = await api("/api/v1/auth/login", { method: "POST", body: { username: username.value, password: password.value } });
    auth.setSession(data);
    router.push(route.query.next || "/");
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
        <h2>账号登录</h2>
        <p class="sub">登录后可以提交域名</p>
      </div>
      <div v-if="error" class="alert err">{{ error }}</div>
      <form @submit.prevent="submit">
        <div class="field">
          <label>用户名</label>
          <input v-model.trim="username" required autofocus>
        </div>
        <div class="field">
          <label>密码</label>
          <input v-model="password" type="password" required>
        </div>
        <button class="btn block" type="submit" :disabled="busy">{{ busy ? "登录中…" : "登录" }}</button>
      </form>
      <p class="sub" style="margin-top: 14px; text-align: center">
        还没有账号？<router-link to="/register" style="color: var(--accent); font-weight: 600">立即注册</router-link>
      </p>
    </div>
  </div>
</template>
