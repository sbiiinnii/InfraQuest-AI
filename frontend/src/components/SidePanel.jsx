import { useState } from 'react'
import Mascot from './Mascot'
import { AlertTriangle, CheckCircle2, Circle, Target } from 'lucide-react'

// AI 선임 엔지니어(마스코트)가 지금 단계에 맞게 '질문'을 던집니다.
// 정답을 알려 주지 않고, 서버·원인도 말하지 않아요. 스스로 추론하도록 생각할 거리만 줍니다. (AI 호출 없이 고정 문구)
function coachSays({ commands, hypotheses, completed }) {
  if (completed) return '해결했어요! 어떤 증거로 원인을 찾았는지 되짚어 보고, 결과에서 다음 미션도 확인해 보세요.'
  if (hypotheses > 0) return '좋은 가설이에요. 그 가설이 맞다면 어떤 결과가 나와야 할까요? 확인하고, 조치한 뒤에는 꼭 다시 점검해요.'
  if (commands === 0) return '장애가 났어요. 어디부터 볼까요? 먼저 사용자가 보는 증상부터 직접 확인해 보세요.'
  return '단서가 모이고 있나요? 지금까지 본 결과로 원인이 뭘지, 어떤 증거 때문에 그렇게 생각하는지 적어 보세요.'
}

// 오른쪽 패널: 장애 상황 · 미션 목표 · 진행 상태 · 원인 가설
// (AI 힌트와 정답 해설은 터미널 아래로 옮겼어요. 이 패널이 아래로 너무 길어지지 않게 하려고요.)
export default function SidePanel({ mission, progress, hypotheses, onSubmitHypothesis }) {
  const [text, setText] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const latest = hypotheses[hypotheses.length - 1]

  async function submit(e) {
    e.preventDefault()
    if (!text.trim() || sending) return
    setSending(true)
    setError('')
    try {
      await onSubmitHypothesis(text)
      setText('')
    } catch (err) {
      setError(err.message)
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <section className="rounded-xl border border-red-500/40 bg-red-500/10 p-4">
        <h2 className="mb-2 flex items-center gap-2 text-sm font-semibold text-red-300">
          <AlertTriangle className="h-4 w-4" /> 장애 상황
        </h2>
        <p className="text-sm leading-relaxed text-slate-200">{mission.situation}</p>
      </section>

      <section className="rounded-xl border border-slate-700 bg-slate-900/60 p-4">
        <h2 className="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-300">
          <Target className="h-4 w-4" /> 미션 목표
        </h2>
        <p className="text-sm leading-relaxed text-slate-300">{mission.goal}</p>
      </section>

      <section className="rounded-xl border border-slate-700 bg-slate-900/60 p-4">
        <h2 className="mb-2 text-sm font-semibold text-slate-300">진행 상태</h2>
        <ul className="space-y-1.5">
          {progress.steps.map((s) => (
            <li key={s.key} className="flex items-center gap-2 text-sm">
              {s.done ? (
                <CheckCircle2 className="h-4 w-4 text-emerald-400" />
              ) : (
                <Circle className="h-4 w-4 text-slate-600" />
              )}
              <span className={s.done ? 'text-slate-100' : 'text-slate-500'}>{s.label}</span>
            </li>
          ))}
        </ul>
        <p className="mt-2 text-xs text-slate-500">체크는 실제로 실행한 행동을 기준으로 표시돼요.</p>
      </section>

      <section className="rounded-xl border border-slate-700 bg-slate-900/60 p-4">
        <h2 className="mb-2 text-sm font-semibold text-slate-300">원인 가설</h2>
        <div className="mb-3 flex items-start gap-3">
          <Mascot size="coach" alt="AI 선임 엔지니어 로봇" />
          <div className="min-w-0 flex-1 rounded-xl rounded-tl-none border border-sky-500/30 bg-sky-500/5 p-2.5">
            <div className="mb-0.5 text-[11px] font-semibold text-sky-300">AI 선임 엔지니어</div>
            <p className="text-xs leading-relaxed text-slate-200">
              {coachSays({ commands: progress.commands_total, hypotheses: hypotheses.length, completed: progress.completed })}
            </p>
          </div>
        </div>
        <p className="mb-2 text-xs text-slate-500">
          무엇이 원인인지, 어떤 근거로 그렇게 판단했는지 적어 보세요. 나중에 AI가 평가에 참고해요.
        </p>
        <form onSubmit={submit}>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={4}
            maxLength={2000}
            placeholder="예) WEB에서 WAS 8080 포트에 연결할 수 없었고, WAS에서 ..."
            className="w-full resize-none rounded-lg border border-slate-700 bg-slate-950 p-2 text-sm text-slate-100 placeholder:text-slate-600 focus:border-sky-400 focus:outline-none"
          />
          <button
            type="submit"
            disabled={!text.trim() || sending}
            className="mt-2 w-full rounded-lg bg-sky-600 py-2 text-sm font-semibold text-white transition hover:bg-sky-500 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-500"
          >
            {latest ? '가설 다시 제출' : '가설 제출'}
          </button>
        </form>
        {error && <p className="mt-2 text-xs text-red-400">{error}</p>}
        {latest && (
          <div className="mt-3 rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-2 text-xs text-slate-300">
            <div className="mb-1 font-semibold text-emerald-400">제출한 가설 ({hypotheses.length}회)</div>
            <p className="whitespace-pre-wrap break-words">{latest}</p>
          </div>
        )}
      </section>
    </div>
  )
}
