import { useState } from 'react'
import { CheckCircle2, ChevronDown, Loader2, Play } from 'lucide-react'

// 미션 1 전용 '2분 시연 가이드'. 눌러서 한 단계씩 실행해요. (스포일러라 기본은 접혀 있어요)
// 각 단계는 사용자가 직접 입력하는 것과 똑같이 서버에 명령어를 보내요. 가짜 결과를 끼워 넣지 않아요.
export default function DemoGuide({ steps, busy, onRunStep }) {
  const [open, setOpen] = useState(false)
  const [next, setNext] = useState(0)
  const [running, setRunning] = useState(false)
  const done = next >= steps.length

  async function runNext() {
    if (done || busy || running) return
    setRunning(true)
    try {
      const ok = await onRunStep(steps[next])
      if (ok) setNext(next + 1)
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="rounded-xl border border-violet-500/30 bg-violet-500/5">
      <button
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-2 px-3 py-2.5 text-left text-sm font-semibold text-violet-200"
      >
        <span>🎬 2분 시연 가이드 (미션 1 · 정답이 나와 있어요)</span>
        <ChevronDown className={`h-4 w-4 shrink-0 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div className="border-t border-violet-500/20 px-3 py-3">
          <p className="mb-2 text-xs text-slate-400">
            스스로 풀어 보고 싶다면 열지 마세요. 시연이나 빠른 체험용이에요. 버튼을 누를 때마다 한 단계씩 실제로 실행돼요.
          </p>
          <ol className="mb-3 space-y-1 text-xs">
            {steps.map((s, i) => (
              <li key={s.label} className={`flex items-start gap-2 ${i < next ? 'text-slate-500' : i === next ? 'text-violet-100' : 'text-slate-400'}`}>
                <span className="mt-0.5 w-4 shrink-0">
                  {i < next ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" /> : <span className="text-slate-600">{i + 1}</span>}
                </span>
                <span>
                  <b>{s.label}</b>
                  {s.server && <span className="ml-1 font-mono text-sky-400">{s.server}</span>}
                  {s.command && <span className="ml-1 font-mono text-slate-300">{s.command}</span>}
                </span>
              </li>
            ))}
          </ol>
          {done ? (
            <p className="rounded-lg bg-emerald-500/10 px-3 py-2 text-xs text-emerald-200">
              다 됐어요! 성공 창에서 <b>"AI 선임 엔지니어 리뷰 받기"</b> 버튼을 눌러 보세요. (AI가 분석하는 데 10~30초 걸려요)
            </p>
          ) : (
            <button
              onClick={runNext}
              disabled={busy || running}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-violet-600 py-2 text-sm font-semibold text-white hover:bg-violet-500 disabled:cursor-wait disabled:bg-slate-700 disabled:text-slate-300"
            >
              {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              다음 단계 실행 ({next + 1}/{steps.length})
            </button>
          )}
        </div>
      )}
    </div>
  )
}
