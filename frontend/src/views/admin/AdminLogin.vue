<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";
import { api, ApiError, tokenStore } from "../../api.js";

const router = useRouter();
const username = ref("");
const password = ref("");
const error = ref("");
const busy = ref(false);

async function submit() {
  error.value = "";
  busy.value = true;
  try {
    const data = await api("/api/v1/admin/login", { method: "POST", body: { username: username.value, password: password.value } });
    tokenStore.admin = data.access_token;
    router.push("/admin");
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
        <h2>审核后台登录</h2>
        <p class="sub">仅限审核团队使用</p>
      </div>
      <div v-if="error" class="alert err">{{ error }}</div>
      <form @submit.prevent="submit">
        <div class="field">
          <label>管理员账号</label>
          <input v-model.trim="username" required autofocus>
        </div>
        <div class="field">
          <label>密码</label>
          <input v-model="password" type="password" required>
        </div>
        <button class="btn block" type="submit" :disabled="busy">{{ busy ? "登录中…" : "登录" }}</button>
      </form>
      <p class="sub" style="margin-top: 14px; text-align: center">
        <router-link to="/" style="color: var(--accent); font-weight: 600">返回公共站</router-link>
      </p>
    </div>
  </div>
</template>
