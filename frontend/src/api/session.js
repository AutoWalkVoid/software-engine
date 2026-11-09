import { ref } from 'vue'

/*
 * 身份来源：localStorage.token（A 的登录页写入）。
 * 本前端不实现登录注册，只消费令牌；令牌失效时清掉本地令牌，
 * 公开页面照常以匿名身份继续浏览（契约 2.2）。
 */
export const TOKEN_KEY = 'token'

function readToken() {
  try {
    return window.localStorage.getItem(TOKEN_KEY) || ''
  } catch (err) {
    return ''
  }
}

/** 响应式令牌：PostImage 等组件依赖它判断图片是否需要带令牌请求。 */
export const tokenRef = ref(readToken())

export function getToken() {
  return tokenRef.value || ''
}

export function hasToken() {
  return !!tokenRef.value
}

export function setToken(token) {
  const value = typeof token === 'string' ? token.trim() : ''
  try {
    if (value) window.localStorage.setItem(TOKEN_KEY, value)
    else window.localStorage.removeItem(TOKEN_KEY)
  } catch (err) {
    /* 隐私模式下 localStorage 可能不可用，退化为内存令牌 */
  }
  tokenRef.value = value
}

export function clearToken() {
  setToken('')
}

/** 令牌被服务端判定失效后通知界面（不清除表单内容）。 */
export function notifyTokenLost(detail) {
  try {
    window.dispatchEvent(new CustomEvent('auth:lost', { detail: detail || {} }))
  } catch (err) {
    /* 忽略 */
  }
}
