// 학습 기록은 이 브라우저(localStorage)에만 저장합니다. 로그인이나 서버 저장은 없어요.
const KEY = 'iq_progress_v1'

export function loadProgress() {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) || '{}')
    return raw && typeof raw === 'object' ? raw : {}
  } catch {
    return {}
  }
}

// 미션을 정상화(복구 + 검증)했을 때 한 번 기록합니다. 이미 있으면 완료 시각은 유지해요.
export function recordCompletion(missionId, { commands, reviewed, solutionViewed, hints, risky }) {
  const all = loadProgress()
  const prev = all[missionId]
  all[missionId] = {
    completedAt: prev?.completedAt || new Date().toISOString(),
    commands,
    reviewed: !!(reviewed || prev?.reviewed),
    solutionViewed: !!(solutionViewed || prev?.solutionViewed), // 정답 해설을 보고 푼 미션
    // 육성(경험치·뱃지)용. 한 번 늘어난 힌트 수와 위험 조치 기록은 다시 풀어도 줄어들지 않아요.
    hints: Math.max(hints ?? 0, prev?.hints ?? 0),
    risky: !!(risky || prev?.risky),
  }
  localStorage.setItem(KEY, JSON.stringify(all))
}

// 이미 끝낸 미션 id 목록 (다음 미션 추천에서 '아직 안 푼 미션'을 고르는 데 써요)
export const completedIds = () => Object.keys(loadProgress())

export const hasSession = (missionId) => !!localStorage.getItem(`iq_sid_${missionId}`)
