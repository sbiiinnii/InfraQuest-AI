import { useEffect, useState } from 'react'

// 주소 뒤의 #/... 부분으로 화면을 구분합니다. (새로고침해도 같은 화면이 유지돼요)
//   #/                      → 대시보드
//   #/missions              → 미션 선택
//   #/practice/mission01    → 실습 화면
export function parseHash(hash) {
  const parts = hash.replace(/^#\/?/, '').split('/').filter(Boolean)
  if (parts[0] === 'missions') return { page: 'missions' }
  if (parts[0] === 'practice' && parts[1]) return { page: 'practice', missionId: parts[1] }
  return { page: 'home' }
}

export function useRoute() {
  const [route, setRoute] = useState(() => parseHash(window.location.hash))
  useEffect(() => {
    const onChange = () => {
      setRoute(parseHash(window.location.hash))
      window.scrollTo(0, 0)
    }
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  return route
}

export const go = (path) => {
  window.location.hash = path
}
