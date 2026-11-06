// 배포할 때는 VITE_API_BASE 에 백엔드 주소(예: https://xxx.onrender.com)를 넣어요. 비워 두면 같은 주소의 /api 를 써요. (내 컴퓨터 개발용)
const BASE = (import.meta.env.VITE_API_BASE || '').replace(/\/+$/, '')

async function req(path, options = {}) {
  let res
  try {
    res = await fetch(BASE + path, { headers: { 'Content-Type': 'application/json' }, ...options })
  } catch {
    const err = new Error('백엔드 서버에 연결할 수 없어요. 서버가 켜져 있는지 확인해 주세요.')
    err.status = 0
    throw err
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    const err = new Error(typeof body.detail === 'string' ? body.detail : `오류가 발생했어요. (${res.status})`)
    err.status = res.status
    throw err
  }
  return res.json()
}

const post = (path, body = {}) => req(path, { method: 'POST', body: JSON.stringify(body) })

export const api = {
  createSession: (missionId) => post('/api/sessions', { mission_id: missionId }),
  missions: () => req('/api/missions'),
  getSession: (sid) => req(`/api/sessions/${sid}`),
  run: (sid, server, command) => post(`/api/sessions/${sid}/command`, { server, command }),
  submitHypothesis: (sid, text) => post(`/api/sessions/${sid}/hypothesis`, { text }),
  reset: (sid) => post(`/api/sessions/${sid}/reset`),
  hint: (sid) => post(`/api/sessions/${sid}/hint`),
  solution: (sid) => post(`/api/sessions/${sid}/solution`),
  recommendation: (sid, doneIds = []) => req(`/api/sessions/${sid}/recommendation?done=${encodeURIComponent(doneIds.join(','))}`),
  review: (sid, force = false) => post(`/api/sessions/${sid}/review${force ? '?force=true' : ''}`),
}
