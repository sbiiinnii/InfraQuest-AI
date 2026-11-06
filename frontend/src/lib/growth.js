// 캐릭터 육성: 경험치·레벨·뱃지는 '이미 저장된 미션 기록'만 보고 계산해요. (AI·서버 사용 없음)
// 기록은 브라우저(localStorage)에만 있어서 다른 기기에서는 처음부터 시작해요.
import { loadProgress } from './progress'

export const XP = { clear: 100, noSolution: 50, fewHints: 30, reviewed: 20 }
export const FEW_HINTS = 1 // 힌트를 이 개수 이하로 쓰면 보너스

export const LEVELS = [
  { lv: 1, title: '신입 엔지니어', min: 0, ring: 'ring-slate-400', text: 'text-slate-300', bar: 'bg-slate-400' },
  { lv: 2, title: '주니어 엔지니어', min: 150, ring: 'ring-sky-400', text: 'text-sky-300', bar: 'bg-sky-400' },
  { lv: 3, title: '선임 엔지니어', min: 450, ring: 'ring-amber-400', text: 'text-amber-300', bar: 'bg-amber-400' },
]

// 미션 하나가 주는 XP. 예전에 저장된 기록처럼 힌트·위험조치 정보가 없으면 그 보너스는 주지 않아요.
export function missionXp(rec) {
  if (!rec) return 0
  let xp = XP.clear
  if (!rec.solutionViewed) xp += XP.noSolution
  if (typeof rec.hints === 'number' && rec.hints <= FEW_HINTS) xp += XP.fewHints
  if (rec.reviewed) xp += XP.reviewed
  return xp
}

export const totalXp = (progress = loadProgress()) =>
  Object.values(progress).reduce((sum, rec) => sum + missionXp(rec), 0)

export function levelInfo(xp) {
  let idx = 0
  LEVELS.forEach((l, i) => {
    if (xp >= l.min) idx = i
  })
  const cur = LEVELS[idx]
  const next = LEVELS[idx + 1] || null
  const pct = next ? Math.round(((xp - cur.min) / (next.min - cur.min)) * 100) : 100
  return { ...cur, next, pct, toNext: next ? next.min - xp : 0 }
}

export const BADGES = [
  { id: 'first', icon: '🛠️', name: '첫 복구', desc: '장애를 처음으로 복구했어요', has: (r) => r.length >= 1 },
  { id: 'nosol', icon: '🧠', name: '무해설 클리어', desc: '해설을 보지 않고 미션을 풀었어요', has: (r) => r.some((x) => !x.solutionViewed) },
  { id: 'safe', icon: '🛡️', name: '신중한 엔지니어', desc: '위험한 조치 없이 미션을 풀었어요', has: (r) => r.some((x) => x.risky === false) },
  { id: 'review', icon: '📝', name: '피드백 수집가', desc: 'AI 선임 엔지니어의 리뷰를 받았어요', has: (r) => r.some((x) => x.reviewed) },
  { id: 'all', icon: '🏆', name: '미션 3개 정복', desc: '미션 3개를 모두 정상화했어요', has: (r) => r.length >= 3 },
]

export const earnedBadges = (progress = loadProgress()) => {
  const recs = Object.values(progress)
  return BADGES.map((b) => ({ ...b, earned: b.has(recs) }))
}
