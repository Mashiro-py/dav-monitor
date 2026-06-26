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
