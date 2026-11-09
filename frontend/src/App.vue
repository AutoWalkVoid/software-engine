<script setup>
import AppHeader from './components/AppHeader.vue'
import { API_BASE } from './api/http.js'
</script>

<template>
  <div class="app-shell">
    <AppHeader />

    <main class="app-main">
      <div class="container">
        <RouterView />
      </div>
    </main>

    <footer class="app-footer">
      <div class="container">
        <p class="app-footer__title">校园失物招领系统 · B 子系统（信息发布与浏览）v0</p>
        <p class="app-footer__note">
          页面数据全部来自后端接口 <code>{{ API_BASE }}</code>，不使用假数据。
          登录注册 / 我的发布（A）、认领与站内沟通（C）、图片下架与举报（系统管理子系统）不在本前端范围内。
        </p>
        <p class="app-footer__note">
          时间按北京时间显示；图片可见性由发布人逐张设置，信息撤回后图片一律不可读。
        </p>
      </div>
    </footer>
  </div>
</template>

<style scoped>
.app-shell {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.app-main {
  flex: 1;
  padding: 22px 0 40px;
}

.app-footer {
  border-top: 1px solid var(--line);
  background: var(--surface);
  padding: 18px 0 24px;
  margin-top: auto;
}

.app-footer__title {
  margin: 0 0 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-soft);
}

.app-footer__note {
  margin: 0;
  font-size: 12px;
  color: var(--muted);
  line-height: 1.75;
}

.app-footer__note code {
  font-size: 11.5px;
  background: var(--surface-soft);
  padding: 1px 5px;
  border-radius: 4px;
}
</style>
