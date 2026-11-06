import { CheckCircle2, Clock, Lock, Play, RotateCcw, Signal } from 'lucide-react'
import SiteHeader from '../components/SiteHeader'
import { useMissions } from '../hooks/useMissions'
import { WAKING_TEXT, useSlow } from '../hooks/useSlow'
import { hasSession, loadProgress } from '../lib/progress'
import { missionXp } from '../lib/growth'

function MissionCard({ m, record }) {
  const available = m.status === 'available'
  const completed = !!record
  const inProgress = !completed && hasSession(m.id)
  const label = completed ? '결과 보기 · 다시 도전' : inProgress ? '이어서 하기' : '미션 시작'

  return (
    <article
      className={`flex flex-col rounded-xl border p-5 ${
        available ? 'border-slate-700 bg-slate-900/60' : 'border-slate-800 bg-slate-900/30 opacity-75'
      }`}
    >
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs font-semibold tracking-wider text-slate-500">
          MISSION {String(m.number).padStart(2, '0')}
        </span>
        {!available ? (
          <span className="flex items-center gap-1 rounded-full bg-slate-800 px-2.5 py-0.5 text-xs text-slate-400">
            <Lock className="h-3 w-3" /> 준비 중
          </span>
        ) : completed ? (
          <span className="flex items-center gap-1 rounded-full bg-emerald-500/15 px-2.5 py-0.5 text-xs font-semibold text-emerald-300">
            <CheckCircle2 className="h-3.5 w-3.5" /> 완료
          </span>
        ) : inProgress ? (
          <span className="rounded-full bg-amber-500/15 px-2.5 py-0.5 text-xs font-semibold text-amber-300">진행 중</span>
        ) : (
          <span className="rounded-full bg-slate-800 px-2.5 py-0.5 text-xs text-slate-400">미완료</span>
        )}
      </div>

      <h2 className="text-lg font-bold">{m.title}</h2>
      <p className="mt-1 flex-1 text-sm text-slate-400">{m.summary}</p>

      <div className="mt-4 flex flex-wrap gap-2 text-xs text-slate-300">
        <span className="rounded bg-slate-800 px-2 py-1">{m.category}</span>
        <span className="flex items-center gap-1 rounded bg-slate-800 px-2 py-1">
          <Signal className="h-3 w-3" /> 난이도 {m.difficulty}
        </span>
        <span className="flex items-center gap-1 rounded bg-slate-800 px-2 py-1">
          <Clock className="h-3 w-3" /> 약 {m.minutes}분
        </span>
      </div>

      {completed && (
        <p className="mt-3 text-xs text-slate-500">
          {new Date(record.completedAt).toLocaleDateString('ko-KR')} 완료 · 명령어 {record.commands}개 · +{missionXp(record)} XP
          {record.reviewed ? ' · AI 리뷰 받음' : ''}
          {record.solutionViewed ? ' · 해설 보고 푼 미션' : ''}
        </p>
      )}

      {available ? (
        <a
          href={`#/practice/${m.id}`}
          className="mt-4 flex items-center justify-center gap-2 rounded-lg bg-emerald-600 py-2.5 text-sm font-semibold text-white hover:bg-emerald-500"
        >
          {completed ? <RotateCcw className="h-4 w-4" /> : <Play className="h-4 w-4" />} {label}
        </a>
      ) : (
        <button
          disabled
          className="mt-4 flex cursor-not-allowed items-center justify-center gap-2 rounded-lg bg-slate-800 py-2.5 text-sm text-slate-500"
        >
          <Lock className="h-4 w-4" /> 아직 열리지 않았어요
        </button>
      )}
    </article>
  )
}

export default function Missions() {
  const { missions, error, reload } = useMissions()
  const slow = useSlow(!missions && !error)
  const progress = loadProgress()

  return (
    <div className="min-h-screen">
      <SiteHeader active="missions" />
      <main className="mx-auto max-w-6xl px-4 py-10">
        <h1 className="text-2xl font-bold">미션 선택</h1>
        <p className="mt-1 mb-6 text-sm text-slate-400">
          같은 증상이라도 원인은 다를 수 있어요. 미션을 하나씩 해결하며 진단 습관을 키워 보세요.
        </p>
        {error ? (
          <div className="rounded-xl border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-300">
            {error}{' '}
            <button onClick={reload} className="underline">
              다시 시도
            </button>
          </div>
        ) : !missions ? (
          <p className="text-slate-500">
            불러오는 중...{slow && <span className="ml-2 text-amber-300">{WAKING_TEXT}</span>}
          </p>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {missions.map((m) => (
              <MissionCard key={m.id} m={m} record={progress[m.id]} />
            ))}
          </div>
        )}
      </main>
    </div>
  )
}
