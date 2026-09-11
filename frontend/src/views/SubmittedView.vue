<script setup>
import { computed } from "vue";
import { useRouter } from "vue-router";

const router = useRouter();
const data = router.currentRoute.value.history.state || {};
const token = data.verification_token || "";
const method = data.ownership_method || "dns_txt";
const domain = data.domain || "";
const registryType = data.requested_type || "free";
</script>

<template>
  <div class="login-wrap" style="max-width: 560px">
    <div class="card pad" style="text-align: center">
      <h1 style="font-size: 26px">提交成功</h1>
      <p class="sub">域名 <b style="color: var(--text)">{{ domain }}</b> 已进入审核队列，状态：待审核{{ registryType === 'official' ? '，已申请官方域名' : '' }}。</p>
      <div class="token-box">{{ token }}</div>
      <div style="text-align:left;margin:12px 0;padding:12px 14px;border:1px solid var(--line);border-radius:12px;background:var(--bg);font-size:13.5px;color:var(--muted);line-height:1.8">
        <b style="color: var(--text)">验证域名所有权：</b>
        <template v-if="method === 'well_known'">
          在网站根目录放置文件 <code style="word-break: break-all">/.well-known/odr-verification.txt</code>，内容为上方 Token。
        </template>
        <template v-else>
          为域名添加 TXT 记录（主机记录 @），值为 <code style="word-break: break-all">odr-verify={{ token }}</code>。
        </template>
        <br>配置完成后到 <router-link to="/me" style="color: var(--accent); font-weight: 600">个人中心</router-link> 点击"验证所有权"。
      </div>
      <div style="margin-top: 22px; display: flex; gap: 10px; justify-content: center; flex-wrap: wrap">
        <router-link class="btn" to="/domains">浏览域名库</router-link>
        <router-link class="btn secondary" to="/">返回首页</router-link>
      </div>
    </div>
  </div>
</template>
