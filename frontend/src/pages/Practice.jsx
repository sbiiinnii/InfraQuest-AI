import { useCallback, useEffect, useState } from 'react'
import { ArrowLeft, History, Info, Loader2, RotateCcw, ShieldAlert } from 'lucide-react'
import { api } from '../lib/api'
import { completedIds, recordCompletion } from '../lib/progress'
import { totalXp } from '../lib/growth'
import DataNotice from '../components/DataNotice'
import DemoGuide from '../components/DemoGuide'
import { WAKING_TEXT, useSlow } from '../hooks/useSlow'
import InfraMap from '../components/InfraMap'
import Terminal from '../components/Terminal'
import SidePanel from '../components/SidePanel'
import HintPanel, { SolutionCard } from '../components/HintPanel'
import SuccessModal from '../components/SuccessModal'
import ReviewModal from '../components/ReviewModal'

const KEY = (missionId) => `iq_sid_${missionId}`

// 미션 1 시연 가이드의 단계. 사용자가 직접 입력하는 것과 똑같은 명령어를 서버에 보내요.
const WEB_URL = 'http://192.168.111.100'
const WAS_URL = 'http://192.168.111.200:8080'
const DEMO_STEPS = [
  { label: '① 증상 확인(502)', server: 'WEB', command: `curl ${WEB_URL}` },
  { label: '② WAS 직접 요청', server: 'WAS', command: `curl ${WAS_URL}` },
  { label: '③ 서비스 상태', server: 'WAS', command: 'systemctl status tomcat10' },
  { label: '④ 포트 확인', server: 'WAS', command: 'ss -tulnp' },
  { label: '⑤ 원인 가설 제출', hypothesis: 'WAS의 Tomcat이 중단되어 8080 포트가 닫혀 있고, Nginx가 연결에 실패해서 502가 발생했다.' },
  { label: '⑥ 복구', server: 'WAS', command: 'systemctl start tomcat10' },
  { label: '⑦ 검증: WAS 직접', server: 'WEB', command: `curl ${WAS_URL}` },
  { label: '⑧ 검증: WEB 경유', server: 'WEB', command: `curl ${WEB_URL}` },
]

export default function Practice({ missionId }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [server, setServer] = useState('WEB')
  const [busy, setBusy] = useState(false)
  const [showSuccess, setShowSuccess] = useState(false)
  const [xpBefore, setXpBefore] = useState(0) // 이번 미션을 끝내기 전의 경험치 (얼마나 올랐는지 보여 주려고)
  const slow = useSlow(!data && !error)
  const [termError, setTermError] = useState('')
  const [showReview, setShowReview] = useState(false)
  const [reviewing, setReviewing] = useState(false)
  const [reviewError, setReviewError] = useState('')
  const [hinting, setHinting] = useState(false)
  const [hintError, setHintError] = useState('')
  const [solutionError, setSolutionError] = useState('')
  const [recommendation, setRecommendation] = useState(null)

  const load = useCallback(async () => {
    setError('')
    try {
      const saved = localStorage.getItem(KEY(missionId))
      let d = null
      if (saved) {
        try {
          d = await api.getSession(saved)
        } catch (e) {
          if (e.status !== 404) throw e // 세션이 사라진 경우(404)만 새로 만듭니다
        }
      }
      if (!d) {
        d = await api.createSession(missionId)
        localStorage.setItem(KEY(missionId), d.sid)
      }
      setData(d)
    } catch (e) {
      setError(e.message)
    }
  }, [missionId])

  useEffect(() => {
    load()
  }, [load])

  // 정상화(복구 + 검증)를 마친 미션은 학습 기록에 남깁니다.
  useEffect(() => {
    if (data?.progress.completed) {
      recordCompletion(missionId, {
        commands: data.progress.commands_total,
        reviewed: !!data.review,
        solutionViewed: !!data.solution,
        hints: data.hints?.length ?? 0,
        risky: (data.progress.risky_actions?.length ?? 0) > 0,
      })
    }
  }, [data, missionId])

  // 미션을 끝내면 내 기록을 보고 다음 미션을 추천받습니다. (규칙 기반이라 AI 리뷰와 상관없이 바로 나와요)
  const sid = data?.sid
  const completedNow = !!data?.progress.completed
  const commandsTotal = data?.progress.commands_total
  useEffect(() => {
    if (!completedNow || !sid) return undefined
    let alive = true
    api
      .recommendation(sid, completedIds())
      .then((r) => alive && setRecommendation(r))
      .catch(() => alive && setRecommendation(null)) // 추천을 못 받아도 나머지 화면은 그대로 써요
    return () => {
      alive = false
    }
  }, [completedNow, sid, commandsTotal])

  async function runCommand(command, srv = server) {
    setBusy(true)
    setTermError('')
    try {
      const wasDone = data.progress.completed
      const before = totalXp()
      const d = await api.run(data.sid, srv, command)
      if (!wasDone && d.progress.completed) setXpBefore(before)
      setData(d)
      if (!wasDone && d.progress.completed) setShowSuccess(true)
      return true
    } catch (e) {
      setTermError(e.message)
      return false
    } finally {
      setBusy(false)
    }
  }

  // 시연 가이드 한 단계 실행: 서버를 고르고 명령어를 보내거나, 가설을 제출해요.
  async function runDemoStep(step) {
    setTermError('')
    if (step.hypothesis) {
      try {
        await submitHypothesis(step.hypothesis)
        return true
      } catch (e) {
        setTermError(e.message)
        return false
      }
    }
    setServer(step.server)
    return runCommand(step.command, step.server)
  }

  async function submitHypothesis(text) {
    setData(await api.submitHypothesis(data.sid, text))
  }

  async function requestHint() {
    if (hinting) return
    setHinting(true)
    setHintError('')
    try {
      setData(await api.hint(data.sid))
    } catch (e) {
      setHintError(e.message)
    } finally {
      setHinting(false)
    }
  }

  async function requestSolution() {
    setSolutionError('')
    try {
      setData(await api.solution(data.sid))
    } catch (e) {
      setSolutionError(e.message)
    }
  }

  async function requestReview(force = false) {
    if (reviewing) return
    setReviewing(true)
    setReviewError('')
    try {
      const d = await api.review(data.sid, force)
      setData(d)
      setShowSuccess(false)
      setShowReview(true)
    } catch (e) {
      setReviewError(e.message)
      if (force) setShowReview(false)
      setShowSuccess(true) // 오류 안내가 보이도록 결과 창으로 돌아갑니다
    } finally {
      setReviewing(false)
    }
  }

  async function reset() {
    if (!window.confirm('실습을 처음 상태로 되돌릴까요? 지금까지의 명령어 기록과 가설이 모두 지워져요.')) return
    try {
      setData(await api.reset(data.sid))
      setShowSuccess(false)
      setShowReview(false)
      setReviewError('')
      setHintError('')
      setSolutionError('')
      setRecommendation(null)
      setTermError('')
      setServer('WEB')
    } catch (e) {
      setTermError(e.message)
    }
  }

  if (error) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-3 p-6 text-center">
        <p className="text-red-400">{error}</p>
        <div className="flex gap-2">
          <button onClick={load} className="rounded-lg bg-sky-600 px-4 py-2 text-sm font-semibold hover:bg-sky-500">
            다시 시도
          </button>
          <a href="#/missions" className="rounded-lg border border-slate-600 px-4 py-2 text-sm hover:bg-slate-800">
            미션 목록으로
          </a>
        </div>
      </div>
    )
  }
  if (!data) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-2 text-slate-400">
        <div className="flex items-center">
          <Loader2 className="mr-2 h-5 w-5 animate-spin" /> 실습 환경을 준비하는 중...
        </div>
        {slow && <p className="text-sm text-amber-300">{WAKING_TEXT}</p>}
      </div>
    )
  }

  const { mission, progress, servers, history, hypotheses } = data
  const current = servers.find((s) => s.name === server)
  const doneCount = progress.steps.filter((s) => s.done).length
  const completed = progress.completed
  const commandHistory = history.map((h) => h.command)

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-800 bg-slate-950/80 px-4 py-3">
        <div className="mx-auto flex max-w-[1500px] flex-wrap items-center gap-x-6 gap-y-2">
          <a
            href="#/missions"
            className="flex items-center gap-1 rounded-lg px-2 py-1.5 text-sm text-slate-400 hover:bg-slate-800 hover:text-white"
          >
            <ArrowLeft className="h-4 w-4" /> 미션 목록
          </a>
          <div>
            <div className="text-xs text-slate-500">MISSION {String(mission.number).padStart(2, '0')}</div>
            <h1 className="text-lg font-bold">{mission.title}</h1>
          </div>
          <span
            className={`rounded-full px-3 py-1 text-xs font-semibold ${
              completed
                ? 'bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/40'
                : 'bg-red-500/15 text-red-300 ring-1 ring-red-500/40'
            }`}
          >
            {completed ? '● 정상화 완료' : '● 장애 대응 중'}
          </span>
          <div className="text-sm text-slate-400">
            진행 {doneCount}/{progress.steps.length} 단계 · 실행한 명령어 {progress.commands_total}개
          </div>
          <div className="ml-auto flex items-center gap-2">
            {completed && (
              <button
                onClick={() => setShowSuccess(true)}
                className="rounded-lg bg-emerald-600 px-3 py-1.5 text-sm font-semibold hover:bg-emerald-500"
              >
                결과 보기
              </button>
            )}
            {data.review && (
              <button
                onClick={() => setShowReview(true)}
                className="rounded-lg bg-sky-600 px-3 py-1.5 text-sm font-semibold hover:bg-sky-500"
              >
                AI 리뷰 보기
              </button>
            )}
            <button
              onClick={reset}
              className="flex items-center gap-1.5 rounded-lg border border-slate-600 px-3 py-1.5 text-sm hover:bg-slate-800"
            >
              <RotateCcw className="h-4 w-4" /> 미션 초기화
            </button>
          </div>
        </div>
      </header>

      <details className="border-b border-amber-500/20 bg-amber-500/10 px-4 py-1.5 text-center text-xs text-amber-200">
        <summary className="cursor-pointer list-none">
          <ShieldAlert className="mr-1 inline h-3.5 w-3.5" />
          시뮬레이션 환경입니다. 모든 서버와 명령어 결과는 가상이며, 실제 서버에는 아무 영향이 없어요.{' '}
          <span className="underline">무엇이 가상이고 실제인가요?</span>
        </summary>
        <div className="mx-auto mt-2 max-w-4xl">
          <DataNotice />
        </div>
      </details>

      {/* 넓은 화면: 왼쪽(서버 카드)·오른쪽(상황/가설)은 두 줄에 걸쳐 길게, 가운데는 위에 터미널·아래에 힌트를 둬서
          어느 열도 비어 보이지 않게 해요. 좁은 화면(모바일)은 위에서 아래로: 서버 → 터미널 → 상황·가설 → 힌트 순서예요. */}
      <main className="mx-auto grid max-w-[1500px] gap-4 p-4 lg:grid-cols-[280px_minmax(0,1fr)_340px] lg:grid-rows-[auto_1fr] lg:items-start">
        {/* 서버 카드는 스크롤을 내려도 따라와서(고정), 힌트를 읽는 동안 왼쪽이 비어 보이지 않고 바로 눌러 볼 수 있어요. */}
        <aside className="lg:sticky lg:top-4 lg:col-start-1 lg:row-span-2 lg:row-start-1">
          <InfraMap servers={servers} selected={server} onSelect={setServer} observed={data.observed} />
        </aside>

        <section className="flex min-w-0 flex-col gap-3 lg:col-start-2 lg:row-start-1">
          <Terminal
            server={current}
            lines={history.filter((h) => h.server === server)}
            commandHistory={commandHistory}
            busy={busy}
            onRun={runCommand}
          />
          {termError && <p className="text-sm text-red-400">{termError}</p>}

          {missionId === 'mission01' && !completed && <DemoGuide steps={DEMO_STEPS} busy={busy} onRunStep={runDemoStep} />}

          <div className="rounded-xl border border-slate-700 bg-slate-900/60 p-3">
            <h2 className="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-300">
              <History className="h-4 w-4" /> 실행 기록 ({history.length})
            </h2>
            {history.length === 0 ? (
              <p className="flex items-center gap-1.5 text-xs text-slate-500">
                <Info className="h-3.5 w-3.5" /> 아직 실행한 명령어가 없어요. 터미널에 명령어를 입력해 보세요.
              </p>
            ) : (
              <ol className="max-h-32 space-y-0.5 overflow-y-auto font-mono text-xs">
                {history.map((h) => (
                  <li key={h.seq} className="flex gap-2 text-slate-400">
                    <span className="w-5 shrink-0 text-right text-slate-600">{h.seq}</span>
                    <span className="w-10 shrink-0 text-sky-400">{h.server}</span>
                    <span className="truncate text-slate-300">{h.command}</span>
                  </li>
                ))}
              </ol>
            )}
          </div>
        </section>

        <aside className="lg:col-start-3 lg:row-span-2 lg:row-start-1">
          <SidePanel
            mission={mission}
            progress={progress}
            hypotheses={hypotheses}
            onSubmitHypothesis={submitHypothesis}
          />
        </aside>

        <div className="min-w-0 lg:col-start-2 lg:row-start-2">
          <HintPanel
            completed={completed}
            hints={data.hints}
            hintMax={data.hint_max}
            hinting={hinting}
            hintError={hintError}
            onRequestHint={requestHint}
            solution={data.solution}
            solutionError={solutionError}
            onRequestSolution={requestSolution}
          />
        </div>
      </main>

      {/* 정답 해설은 격자 '바깥'의 전체 폭 줄이에요. 고정된 서버 카드가 격자 끝에서 멈춰서 해설과 겹치지 않아요. */}
      {data.solution && (
        <div className="mx-auto max-w-[1500px] px-4 pb-6">
          <SolutionCard solution={data.solution} />
        </div>
      )}

      {showSuccess && (
        <SuccessModal
          progress={progress}
          hasReview={!!data.review}
          reviewing={reviewing}
          reviewError={reviewError}
          onReview={() => (data.review ? (setShowSuccess(false), setShowReview(true)) : requestReview())}
          onClose={() => setShowSuccess(false)}
          onReset={reset}
          recommendation={recommendation}
          xpBefore={xpBefore}
        />
      )}
      {showReview && data.review && (
        <ReviewModal
          review={data.review}
          progress={progress}
          history={history}
          retrying={reviewing}
          onRetry={() => requestReview(true)}
          onClose={() => setShowReview(false)}
          recommendation={recommendation}
          onRestart={reset}
        />
      )}
    </div>
  )
}
