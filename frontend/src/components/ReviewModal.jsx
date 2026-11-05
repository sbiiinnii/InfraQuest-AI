import Rich from './Rich'
import Mascot from './Mascot'
import NextMissionCard from './NextMissionCard'
import { BookOpen, CheckCircle2, Compass, ShieldCheck, ThumbsUp, TriangleAlert, X } from 'lucide-react'

const RATING_STYLE = {
  우수: 'bg-emerald-500/15 text-emerald-300 ring-emerald-500/40',
  보통: 'bg-amber-500/15 text-amber-300 ring-amber-500/40',
  미흡: 'bg-red-500/15 text-red-300 ring-red-500/40',
  '해당 없음': 'bg-slate-500/15 text-slate-300 ring-slate-500/40',
}

function Refs({ refs, history }) {
  if (!refs?.length) return null
  return (
    <div className="mt-1 flex flex-wrap gap-1.5">
      {refs.map((n) => {
        const h = history.find((x) => x.seq === n)
        return (
          <span
            key={n}
            title={h ? `${h.server}: ${h.command}` : ''}
            className="rounded bg-slate-800 px-1.5 py-0.5 font-mono text-[11px] text-sky-300"
          >
            근거 #{n}
            {h ? ` · ${h.command.length > 28 ? h.command.slice(0, 28) + '…' : h.command}` : ''}
          </span>
        )
      })}
    </div>
  )
}

function Section({ icon: Icon, title, tone = 'text-slate-200', children }) {
  return (
    <section className="rounded-xl border border-slate-700 bg-slate-800/40 p-4">
      <h3 className={`mb-2 flex items-center gap-2 text-sm font-semibold ${tone}`}>
        <Icon className="h-4 w-4" /> {title}
      </h3>
      {children}
    </section>
  )
}

export default function ReviewModal({ review, progress, history, onClose, onRetry, retrying, recommendation, onRestart }) {
  const v = progress.verification
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/70 p-4">
      <div className="my-6 w-full max-w-2xl rounded-2xl border border-sky-500/40 bg-slate-900 p-6 shadow-2xl">
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <h2 className="text-xl font-bold text-sky-300">AI 선임 엔지니어 리뷰</h2>
            <p className="text-xs text-slate-500">
              실제로 실행한 명령어 기록과 작성한 가설을 근거로 한 평가예요.
            </p>
          </div>
          <button onClick={onClose} aria-label="닫기" className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-800">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="mb-4 flex flex-wrap items-center gap-x-4 gap-y-1 rounded-lg border border-emerald-500/30 bg-emerald-500/5 px-3 py-2 text-xs text-slate-300">
          <span className="flex items-center gap-1 font-semibold text-emerald-300">
            <ShieldCheck className="h-4 w-4" /> 시뮬레이터 판정
          </span>
          <span>복구 {progress.steps.find((s) => s.key === 'recover')?.done ? '✓' : '✗'}</span>
          <span>WAS 직접 확인 {v.was_direct ? '✓' : '✗'}</span>
          <span>WEB 경유 확인 {v.web ? '✓' : '✗'}</span>
          <span className="text-slate-500">(성공 여부는 AI가 아니라 규칙으로 판정해요)</span>
        </div>

        <div className="space-y-3">
          <Section icon={CheckCircle2} title="종합 평가">
            <div className="flex items-start gap-4">
              <Mascot size="result" decorative />
              <p className="min-w-0 flex-1 whitespace-pre-wrap text-sm leading-relaxed text-slate-200"><Rich text={review.overall} /></p>
            </div>
          </Section>

          <Section icon={Compass} title="평가 항목">
            <ul className="space-y-2.5">
              {review.scores.map((s) => (
                <li key={s.key} className="text-sm">
                  <div className="flex items-center gap-2">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ${RATING_STYLE[s.rating]}`}
                    >
                      {s.rating}
                    </span>
                    <span className="font-semibold text-slate-200">{s.label}</span>
                  </div>
                  <p className="mt-1 leading-relaxed text-slate-400"><Rich text={s.reason} /></p>
                </li>
              ))}
            </ul>
          </Section>

          <Section icon={ThumbsUp} title="잘한 점" tone="text-emerald-300">
            {review.strengths.length ? (
              <ul className="space-y-2.5 text-sm">
                {review.strengths.map((p, i) => (
                  <li key={i}>
                    <p className="leading-relaxed text-slate-200"><Rich text={p.text} /></p>
                    <Refs refs={p.refs} history={history} />
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-slate-500">이번 기록에서 뚜렷하게 꼽을 만한 점을 찾지 못했어요.</p>
            )}
          </Section>

          <Section icon={TriangleAlert} title="개선할 점" tone="text-amber-300">
            {review.improvements.length ? (
              <ul className="space-y-2.5 text-sm">
                {review.improvements.map((p, i) => (
                  <li key={i}>
                    <p className="leading-relaxed text-slate-200"><Rich text={p.text} /></p>
                    <Refs refs={p.refs} history={history} />
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-slate-500">이번 기록에서 지적할 점이 없어요.</p>
            )}
          </Section>

          <Section icon={ShieldCheck} title="선임 엔지니어의 조언" tone="text-sky-300">
            <ul className="list-disc space-y-1.5 pl-5 text-sm leading-relaxed text-slate-200">
              {review.senior_advice.map((a, i) => (
                <li key={i}><Rich text={a} /></li>
              ))}
            </ul>
          </Section>

          <NextMissionCard recommendation={recommendation} onRetry={onRestart} />

          <Section icon={BookOpen} title="더 공부해 볼 주제 (AI 제안)" tone="text-violet-300">
            <ul className="space-y-2 text-sm">
              {review.next_learning.map((n, i) => (
                <li key={i}>
                  <div className="font-semibold text-slate-200">{n.title}</div>
                  <p className="leading-relaxed text-slate-400"><Rich text={n.reason} /></p>
                </li>
              ))}
            </ul>
          </Section>
        </div>

        <div className="mt-5 flex items-center justify-between gap-2 text-xs text-slate-500">
          <span>AI의 의견이라 틀릴 수 있어요. 근거 번호는 실행 기록의 번호예요.</span>
          <div className="flex gap-2">
            <button
              onClick={onRetry}
              disabled={retrying}
              className="rounded-lg border border-slate-600 px-3 py-1.5 text-sm text-slate-300 hover:bg-slate-800 disabled:opacity-50"
            >
              {retrying ? '다시 분석하는 중...' : '다시 분석'}
            </button>
            <button onClick={onClose} className="rounded-lg bg-slate-700 px-3 py-1.5 text-sm text-slate-100 hover:bg-slate-600">
              닫기
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
