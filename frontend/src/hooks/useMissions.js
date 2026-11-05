import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api'

// 미션 목록을 백엔드에서 불러옵니다. (구현된 미션 / 준비 중인 미션)
export function useMissions() {
  const [missions, setMissions] = useState(null)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setError('')
    try {
      setMissions(await api.missions())
    } catch (e) {
      setError(e.message)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  return { missions, error, reload: load }
}
