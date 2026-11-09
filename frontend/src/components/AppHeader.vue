<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { clearImageBlobCache } from '../api/http.js'
import { clearToken, tokenRef } from '../api/session.js'

/*
 * 页面框架导航。本前端不做登录页（归 A），只显示 localStorage.token 是否存在，
 * 并允许清掉本地令牌以匿名身份浏览。A 的登录页写入 token 后刷新本页即可。
 */
const notice = ref('')
let noticeTimer = 0

function onAuthLost() {
  notice.value = '登录令牌已失效，已自动切换为未登录浏览。'
  window.clearTimeout(noticeTimer)
  noticeTimer = window.setTimeout(() => {
    notice.value = ''
  }, 6000)
}

function signOut() {
  clearToken()
  clearImageBlobCache()
  // 重新挂载页面，让所有图片可读性判断按匿名身份重算
  window.location.reload()
}

onMounted(() => {
  window.addEventListener('auth:lost', onAuthLost)
  window.addEventListener('storage', onAuthLost)
})

onBeforeUnmount(() => {
  window.removeEventListener('auth:lost', onAuthLost)
  window.removeEventListener('storage', onAuthLost)
  window.clearTimeout(noticeTimer)
})
</script>

<template>
  <header class="app-header">
    <div class="container app-header__inner">
      <RouterLink class="brand" :to="{ name: 'post-list' }">
        <span class="brand__mark" aria-hidden="true">失</span>
        <span class="brand__text">
          <strong>校园失物招领</strong>
          <small>信息发布与浏览 · B 子系统</small>
        </span>
      </RouterLink>

      <nav class="app-nav" aria-label="主导航">
        <RouterLink :to="{ name: 'post-list' }" class="app-nav__link">信息列表</RouterLink>
        <RouterLink :to="{ name: 'post-new' }" class="app-nav__link">发布信息</RouterLink>
      </nav>

      <div class="app-header__auth">
        <template v-if="tokenRef">
          <span class="badge badge--ok">已登录</span>
          <button type="button" class="btn btn--ghost btn--sm" @click="signOut">退出</button>
        </template>
        <template v-else>
          <span class="badge">未登录 · 可浏览</span>
          <span class="app-header__auth-hint">登录 / 注册由 A 子系统提供</span>
        </template>
      </div>
    </div>

    <p v-if="notice" class="app-header__notice" role="status">{{ notice }}</p>
  </header>
</template>

<style scoped>
.app-header {
  position: sticky;
  top: 0;
  z-index: 20;
  background: #fffffff2;
  backdrop-filter: blur(8px);
  border-bottom: 1px solid var(--line);
}

.app-header__inner {
  display: flex;
  align-items: center;
  gap: 18px;
  padding-top: 12px;
  padding-bottom: 12px;
  flex-wrap: wrap;
}

.brand {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  text-decoration: none;
  color: var(--text);
  margin-right: auto;
}

.brand__mark {
  width: 34px;
  height: 34px;
  border-radius: 9px;
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, var(--primary), #0ea5e9);
  color: #fff;
  font-weight: 700;
  font-size: 15px;
}

.brand__text {
  display: flex;
  flex-direction: column;
  line-height: 1.25;
}

.brand__text strong {
  font-size: 15.5px;
  font-weight: 700;
}

.brand__text small {
  color: var(--muted);
  font-size: 11.5px;
}

.app-nav {
  display: flex;
  gap: 4px;
}

.app-nav__link {
  padding: 7px 12px;
  border-radius: 8px;
  text-decoration: none;
  color: var(--text-soft);
  font-size: 14px;
  font-weight: 500;
}

.app-nav__link:hover {
  background: var(--surface-soft);
  color: var(--text);
}

.app-nav__link.router-link-active {
  background: var(--primary-soft);
  color: var(--primary-dark);
  font-weight: 650;
}

.app-header__auth {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12.5px;
  color: var(--muted);
}

.app-header__auth-hint {
  display: none;
}

.app-header__notice {
  margin: 0;
  padding: 8px 16px;
  background: #fff8e6;
  color: #92400e;
  font-size: 13px;
  text-align: center;
  border-top: 1px solid #f5e2b8;
}

@media (min-width: 720px) {
  .app-header__auth-hint {
    display: inline;
  }
}
</style>
