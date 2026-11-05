import { ArrowRight, Clock, Compass, RotateCcw, Signal } from 'lucide-react'
import Mascot from './Mascot'

// 개인별 다음 미션 추천. 서버가 내 실행 기록을 보고 규칙으로 정한 결과예요. (AI가 정하지 않아요)
// mascot: 같은 화면에 이미 마스코트가 있으면(AI 리뷰 화면) false로 둬서 화면이 복잡해지지 않게 해요.
export default function NextMissionCard({ recommendation, onRetry, mascot = false }) {
  if (!recommendation) return null
  const r = recommendation
  const m = r.mission
  return (
    <section data-testid="next-mission" className="rounded-xl border border-violet-500/40 bg-violet-500/5 p-4">
      <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-violet-300">
        <Compass className="h-4 w-4" /> 나에게 맞는 다음 미션
      </h3>

      <div className="flex items-start gap-3">
        {mascot && <Mascot size="result" decorative className="-mt-1" />}
        <div className="min-w-0 flex-1">
          <div className="mb-2 inline-block rounded-full bg-violet-500/15 px-2.5 py-0.5 text-xs font-semibold text-violet-200 ring-1 ring-violet-500/40">
            연습할 것 · {r.focus}
          </div>
          <p className="text-sm leading-relaxed text-slate-200">{r.reason}</p>
        </div>
      </div>

      {r.evidence.length > 0 && (
        <ul className="mt-2 space-y-0.5 text-xs text-slate-400">
          {r.evidence.map((e) => (
            <li key={e}>· {e}</li>
          ))}
        </ul>
      )}

      {m ? (
        <div className="mt-3 rounded-lg border border-slate-700 bg-slate-900/70 p-3">
          <div className="text-xs font-semibold tracking-wider text-slate-500">
            MISSION {String(m.number).padStart(2, '0')}
            {r.retry && ' · 같은 미션 다시 도전'}
            {r.already_done && ' · 이미 푼 미션'}
          </div>
          <div className="mt-0.5 font-bold text-slate-100">{m.title}</div>
          <p className="mt-1 text-xs leading-relaxed text-slate-400">{m.training}</p>
          <div className="mt-2 flex gap-2 text-xs text-slate-400">
            <span className="flex items-center gap-1">
              <Signal className="h-3 w-3" /> 난이도 {m.difficulty}
            </span>
            <span className="flex items-center gap-1">
              <Clock className="h-3 w-3" /> 약 {m.minutes}분
            </span>
          </div>
          {r.retry ? (
            <button
              onClick={onRetry}
              className="mt-3 flex w-full items-center justify-center gap-2 rounded-lg bg-violet-600 py-2 text-sm font-semibold text-white hover:bg-violet-500"
            >
              <RotateCcw className="h-4 w-4" /> 처음부터 다시 도전하기
            </button>
          ) : (
            <a
              href={`#/practice/${m.id}`}
              className="mt-3 flex w-full items-center justify-center gap-2 rounded-lg bg-violet-600 py-2 text-sm font-semibold text-white hover:bg-violet-500"
            >
              MISSION {String(m.number).padStart(2, '0')} 시작하기 <ArrowRight className="h-4 w-4" />
            </a>
          )}
        </div>
      ) : (
        <p className="mt-3 rounded-lg bg-slate-900/70 p-3 text-xs text-slate-400">
          지금 있는 미션을 모두 마쳤어요. 새 미션은 준비 중이에요.
        </p>
      )}
    </section>
  )
}
