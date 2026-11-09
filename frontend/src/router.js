import { createRouter, createWebHistory } from 'vue-router'
import ListView from './views/ListView.vue'
import DetailView from './views/DetailView.vue'
import EditorView from './views/EditorView.vue'

/*
 * 只注册 B 子系统的三个页面：公开列表、详情、发布/编辑。
 * 登录注册、我的发布、认领、审核举报都不在本前端内（分属 A / C / 系统管理子系统）。
 *
 * 注：/posts/new 是静态段，vue-router 4 的评分机制保证它优先于 /posts/:id，
 * 所以不需要为 ID 单独写正则；契约里 ID 是字符串，通用 :id 两种都能匹配。
 */
const routes = [
  { path: '/', name: 'post-list', component: ListView },
  { path: '/posts/new', name: 'post-new', component: EditorView },
  { path: '/posts/:id/edit', name: 'post-edit', component: EditorView },
  { path: '/posts/:id', name: 'post-detail', component: DetailView },
  { path: '/:pathMatch(.*)*', redirect: { name: 'post-list' } },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) return savedPosition
    return { top: 0 }
  },
})

export default router
