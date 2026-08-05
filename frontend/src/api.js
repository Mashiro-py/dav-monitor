// 统一 API 封装。后端不可达时回退 mock，保证页面不崩。
import { ref } from 'vue'
import { MOCK_STATS, mockPosts } from './mock.js'

const BASE = (import.meta.env.VITE_API_BASE || '').replace(/\/+$/, '')
export const usingMock = ref(false)

async function getJSON(path) {
  const ctrl = new AbortController()
  const t = setTimeout(() => ctrl.abort(), 8000)
  try {
    const r = await fetch(BASE + path, { signal: ctrl.signal })
    clearTimeout(t)
    if (!r.ok) throw new Error('HTTP ' + r.status)
    return await r.json()
  } catch (e) {
    clearTimeout(t)
    throw e
  }
}

export async function getStats() {
  try {
    const d = await getJSON('/api/stats')
    usingMock.value = false
    return d
  } catch {
    usingMock.value = true
    return MOCK_STATS
  }
}

export async function getPosts(params = {}) {
  const q = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== '' && v !== null && v !== undefined) q.set(k, v)
  }
  try {
    const d = await getJSON('/api/posts?' + q.toString())
    usingMock.value = false
    return d
  } catch {
    usingMock.value = true
    return mockPosts(params)
  }
}

/* ===== AI 热点态势分析 ===== */
// 读取类接口：失败静默返回 null，由组件显示占位
export async function getAnalysisLatest() {
  try { return (await getJSON('/api/analysis/latest')).analysis } catch { return null }
}
export async function getAnalysisQuota() {
  try { return await getJSON('/api/analysis/quota') } catch { return null }
}
export async function getAnalysisHistory(limit = 30) {
  try { return (await getJSON(`/api/analysis/history?limit=${limit}`)).items || [] } catch { return [] }
}

// 触发分析：不设前端超时（模型生成 30~90s，nginx 侧已放宽到 180s）。
// token 由 nginx 服务端注入（方案A），前端不带任何密钥。
// 返回 {ok, analysis, quota}；失败抛 Error(可读中文文案)。
export async function runAnalysis() {
  let r
  try {
    r = await fetch(BASE + '/api/analysis/run', { method: 'POST' })
  } catch {
    throw new Error('无法连接后端，请检查服务是否在运行')
  }
  let body = null
  try { body = await r.json() } catch {}
  if (!r.ok) {
    throw new Error((body && body.detail) || `分析失败（HTTP ${r.status}）`)
  }
  return body
}
