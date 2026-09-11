<script setup>
import { useAuth } from "./stores/auth.js";

const auth = useAuth();

function logout() {
  auth.logout();
  window.location.href = "/login";
}
</script>

<template>
  <nav class="nav">
    <div class="wrap nav-inner">
      <a class="brand" href="/">
        <svg viewBox="0 0 24 24"><path fill="var(--accent)" d="M12 2l8 3v6c0 5-3.4 9.4-8 11-4.6-1.6-8-6-8-11V5l8-3z"/><path fill="var(--card)" d="M10.6 14.6l-2.2-2.2-1.4 1.4 3.6 3.6 6.4-6.4-1.4-1.4z"/></svg>
        Official Domain Registry
      </a>
      <div class="nav-links">
        <router-link to="/">提交</router-link>
        <router-link to="/domains">域名库</router-link>
        <template v-if="auth.loggedIn">
          <router-link to="/me">个人中心</router-link>
          <span class="nav-user">{{ auth.user.username }}</span>
          <button @click="logout">退出</button>
        </template>
        <template v-else>
          <router-link to="/login">登录</router-link>
          <router-link to="/register">注册</router-link>
        </template>
      </div>
    </div>
  </nav>
  <main class="wrap">
    <router-view />
  </main>
  <footer>
    <div class="wrap">查询结果只代表注册库当前的审核状态，不等同于对网站当前安全性的保证。 · Official Domain Registry v2</div>
  </footer>
</template>
