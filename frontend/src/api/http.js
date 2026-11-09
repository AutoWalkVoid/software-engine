import { clearToken, getToken, notifyTokenLost } from './session.js'

/*
 * 统一接口封装。
 *
 * 后端所有 JSON 接口都使用 { code, message, data, errors? } 包装（契约 2.3 / 2.4）：
 *   - HTTP 2xx 且 code === 'OK'  -> 返回 data
 *   - 其他情况                   -> 抛 ApiError（带 status / code / message / errors）
 * 图片二进制接口不使用包装（契约 5.1 的 B 注记），单独走 fetchImageBlob。
 */

export const API_BASE = (
  import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000/api/v1'
).replace(/\/+$/, '')

export class ApiError extends Error {
  constructor({ status = 0, code = 'NETWORK_ERROR', message = '请求失败', errors = null, payload = null } = {}) {
    super(message || '请求失败')
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.errors = errors && typeof errors === 'object' ? errors : {}
    this.payload = payload
  }

  /** 是否属于字段级校验错误（错误可落到具体输入框） */
  get hasFieldErrors() {
    return this.status === 400 && Object.keys(this.errors).length > 0
  }
}

const STATUS_FALLBACK_MESSAGE = {
  400: '请求参数或填写内容不正确',
  401: '未登录或登录已失效',
  403: '没有操作权限',
  404: '信息不存在或不可见',
  409: '当前状态不允许该操作',
  413: '上传的图片超过 5 MiB',
  415: '不支持的文件格式',
  429: '操作过于频繁，请稍后再试',
  500: '服务端错误，请稍后重试',
}

export const CODE_TEXT = {
  VALIDATION_ERROR: '填写内容有误',
  UNAUTHENTICATED: '未登录或登录已失效',
  FORBIDDEN: '没有操作权限',
  IDENTITY_REQUIRED: '需要先完成校园身份绑定',
  NOT_FOUND: '信息不存在或不可见',
  STATE_CONFLICT: '当前状态不允许该操作',
  DUPLICATE_RESOURCE: '重复提交或资源重复',
  FILE_TOO_LARGE: '图片超过 5 MiB',
  UNSUPPORTED_MEDIA_TYPE: '图片格式不支持',
  RATE_LIMITED: '操作过于频繁，请稍后再试',
  INTERNAL_ERROR: '服务端错误',
  NETWORK_ERROR: '网络异常',
  HTTP_ERROR: '请求失败',
}

/** 把 ApiError 转成一句可直接展示的中文提示（不用于判断业务结果）。 */
export function describeError(err) {
  if (!err) return ''
  if (!(err instanceof ApiError)) return err.message || '未知错误'
  const head = CODE_TEXT[err.code] || (err.status ? `请求失败（HTTP ${err.status}）` : '请求失败')
  const detail = err.message && err.message !== head ? `：${err.message}` : ''
  return `${head}${detail}`
}

function fallbackMessage(status) {
  return STATUS_FALLBACK_MESSAGE[status] || `请求失败（HTTP ${status}）`
}

function buildQuery(query) {
  if (!query) return ''
  const search = new URLSearchParams()
  for (const [key, raw] of Object.entries(query)) {
    if (raw === undefined || raw === null) continue
    const value = typeof raw === 'string' ? raw.trim() : raw
    if (value === '') continue
    search.append(key, String(value))
  }
  const text = search.toString()
  return text ? `?${text}` : ''
}

/**
 * @param {string} path 以 / 开头，不含 /api/v1 前缀
 * @param {object} options
 *   method, query, body(JSON), formData(multipart), withAuth(默认 true：有令牌就带),
 *   anonymousRetry(GET 公开接口：401 时清令牌并匿名重试一次), signal
 */
export async function request(path, options = {}) {
  const {
    method = 'GET',
    query,
    body,
    formData,
    withAuth = true,
    anonymousRetry = false,
    signal,
    responseType = 'json',
  } = options

  const url = `${API_BASE}${path}${buildQuery(query)}`

  const doFetch = async (token) => {
    const headers = { Accept: responseType === 'json' ? 'application/json' : '*/*' }
    if (token) headers.Authorization = `Bearer ${token}`
    let payload
    if (formData) {
      // 交给浏览器生成 multipart boundary，不要手写 Content-Type
      payload = formData
    } else if (body !== undefined) {
      headers['Content-Type'] = 'application/json'
      payload = JSON.stringify(body)
    }
    return fetch(url, { method, headers, body: payload, signal, cache: 'no-store' })
  }

  const token = withAuth ? getToken() : ''
  let response
  try {
    response = await doFetch(token)
  } catch (err) {
    if (err && err.name === 'AbortError') throw err
    throw new ApiError({
      status: 0,
      code: 'NETWORK_ERROR',
      message: `无法连接后端接口 ${API_BASE}。请确认后端已启动，且已允许前端来源的跨域请求（CORS）。`,
    })
  }

  // 无效令牌访问公开接口时：清令牌后匿名重试一次（契约 2.2）
  if (response.status === 401 && anonymousRetry && token) {
    clearToken()
    notifyTokenLost({ reason: 'expired' })
    try {
      response = await doFetch('')
    } catch (err) {
      if (err && err.name === 'AbortError') throw err
      throw new ApiError({
        status: 0,
        code: 'NETWORK_ERROR',
        message: `无法连接后端接口 ${API_BASE}。`,
      })
    }
  }

  let envelope = null
  const contentType = response.headers.get('content-type') || ''
  if (response.status !== 204 && contentType.includes('application/json')) {
    try {
      envelope = await response.json()
    } catch (err) {
      envelope = null
    }
  }

  if (!response.ok) {
    const error = new ApiError({
      status: response.status,
      code: envelope?.code || (response.status === 401 ? 'UNAUTHENTICATED' : `HTTP_${response.status}`),
      message: envelope?.message || fallbackMessage(response.status),
      errors: envelope?.errors,
      payload: envelope,
    })
    if (response.status === 401 && withAuth) {
      clearToken()
      notifyTokenLost({ reason: 'invalid' })
    }
    throw error
  }

  if (envelope && typeof envelope === 'object' && typeof envelope.code === 'string') {
    if (envelope.code !== 'OK') {
      throw new ApiError({
        status: response.status,
        code: envelope.code,
        message: envelope.message || fallbackMessage(response.status),
        errors: envelope.errors,
        payload: envelope,
      })
    }
    return envelope.data
  }

  // 不符合包装结构的 2xx 响应（正常不应出现；图片走 fetchImageBlob）
  return envelope
}

const imageBlobCache = new Map()

export function clearImageBlobCache() {
  for (const objectUrl of imageBlobCache.values()) {
    try {
      URL.revokeObjectURL(objectUrl)
    } catch (err) {
      /* 忽略 */
    }
  }
  imageBlobCache.clear()
}

/** 未登录可见的图片可以直接当 img src 用（不拼令牌）。 */
export function imageContentUrl(imageId) {
  return `${API_BASE}/post-images/${encodeURIComponent(imageId)}/content`
}

/** is_public=false 或未绑定图片：带 Bearer 令牌取二进制，换成 blob URL 预览。 */
export async function fetchImageBlob(imageId) {
  const key = String(imageId)
  if (imageBlobCache.has(key)) return imageBlobCache.get(key)
  const token = getToken()
  const headers = {}
  if (token) headers.Authorization = `Bearer ${token}`
  let response
  try {
    response = await fetch(imageContentUrl(imageId), { headers, cache: 'no-store' })
  } catch (err) {
    throw new ApiError({
      status: 0,
      code: 'NETWORK_ERROR',
      message: '图片加载失败，请检查网络或后端服务。',
    })
  }
  if (!response.ok) {
    let code = `HTTP_${response.status}`
    let message = fallbackMessage(response.status)
    try {
      const envelope = await response.json()
      code = envelope?.code || code
      message = envelope?.message || message
    } catch (err) {
      /* 非 JSON 错误体 */
    }
    if (response.status === 401) clearToken()
    throw new ApiError({ status: response.status, code, message })
  }
  const blob = await response.blob()
  const objectUrl = URL.createObjectURL(blob)
  imageBlobCache.set(key, objectUrl)
  return objectUrl
}
