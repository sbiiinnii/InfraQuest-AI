import { useEffect, useState } from 'react'

// 불러오는 중이 오래(기본 4초) 걸리면 true. 무료 서버가 잠들어 있을 때 '멈춘 게 아니에요'를 알려 주려고 써요.
export function useSlow(active, ms = 4000) {
  const [slow, setSlow] = useState(false)
  useEffect(() => {
    if (!active) {
      setSlow(false)
      return undefined
    }
    const t = setTimeout(() => setSlow(true), ms)
    return () => clearTimeout(t)
  }, [active, ms])
  return slow
}

export const WAKING_TEXT = '서버가 잠에서 깨어나는 중이에요. 처음에는 최대 1분 걸려요. 조금만 기다려 주세요.'
