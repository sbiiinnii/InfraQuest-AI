import { CheckCircle2, Loader2, PartyPopper } from 'lucide-react'
import NextMissionCard from './NextMissionCard'
import { GrowthGain } from './GrowthCard'

export default function SuccessModal({ progress, hasReview, reviewing, reviewError, onReview, onClose, onReset, recommendation, xpBefore = 0 }) {
  const v = progress.verification
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="max-h-[90vh] w-full max-w-4xl overflow-y-auto rounded-2xl border border-emerald-500/50 bg-slate-900 p-6 shadow-2xl shadow-emerald-500/10">
        <div className="mb-4 flex items-center gap-3">
          <PartyPopper className="h-9 w-9 text-emerald-400" />
          <div>
            <h2 className="text-xl font-bold text-emerald-300">서비스 정상화 성공!</h2>
            <p className="text-sm text-slate-400">장애를 해결하고 정상 동작까지 확인했어요.</p>
          </div>
        </div>

        <div className="grid gap-6 md:grid-cols-2">
        <dl className="space-y-4 text-sm">
          <div className="flex justify-between rounded-lg bg-slate-800/60 px-3 py-2">
            <dt className="text-slate-400">실행한 명령어 수</dt>
            <dd className="font-semibold">{progress.commands_total}개</dd>
          </div>

          <div>
            <dt className="mb-1 font-semibold text-slate-300">확인한 증거</dt>
            <dd>
              {progress.evidence.length ? (
                <ul className="space-y-1">
                  {progress.evidence.map((e) => (
                    <li key={e} className="flex gap-2 text-slate-300">
                      <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" /> {e}
                    </li>
                  ))}
                </ul>
              ) : (
                <span className="text-amber-300">원인을 확인한 기록이 없어요. 진단 없이 바로 조치했어요.</span>
              )}
            </dd>
          </div>

          <div>
            <dt className="mb-1 font-semibold text-slate-300">수행한 복구 조치</dt>
            <dd>
              <ul className="space-y-1 text-slate-300">
                {progress.recovery_actions.map((a) => (
                  <li key={a}>• {a}</li>
                ))}
                {progress.other_actions.map((a) => (
                  <li key={a} className="text-slate-400">• {a} (복구와 직접 관련 없는 조치)</li>
                ))}
              </ul>
              {progress.risky_actions?.length > 0 && (
                <ul className="mt-2 space-y-1 rounded-lg border border-amber-500/40 bg-amber-500/10 p-2 text-amber-200">
                  {progress.risky_actions.map((a) => (
                    <li key={a}>⚠ {a}</li>
                  ))}
                </ul>
              )}
            </dd>
          </div>

          <div>
            <dt className="mb-1 font-semibold text-slate-300">정상화 검증 결과</dt>
            <dd className="space-y-1 text-slate-300">
              <div className="flex gap-2">
                <CheckCircle2 className={`h-4 w-4 ${v.was_direct ? 'text-emerald-400' : 'text-slate-600'}`} />
                WAS 직접 요청 (192.168.111.200:8080) 성공
              </div>
              <div className="flex gap-2">
                <CheckCircle2 className={`h-4 w-4 ${v.web ? 'text-emerald-400' : 'text-slate-600'}`} />
                WEB(Nginx) 경유 요청 (192.168.111.100) 성공
              </div>
            </dd>
          </div>
        </dl>

        <div className="flex flex-col gap-4">
          <GrowthGain xpBefore={xpBefore} />
          <NextMissionCard recommendation={recommendation} onRetry={onReset} mascot />
        <div className="grid gap-2">
          <button
            onClick={onReview}
            disabled={reviewing}
            className="flex items-center justify-center gap-2 rounded-lg bg-sky-600 py-2.5 text-sm font-semibold text-white hover:bg-sky-500 disabled:cursor-wait disabled:bg-slate-700 disabled:text-slate-300"
          >
            {reviewing && <Loader2 className="h-4 w-4 animate-spin" />}
            {reviewing
              ? 'AI가 실행 기록을 분석하는 중... (최대 1분)'
              : reviewError
                ? 'AI 리뷰 다시 시도'
                : hasReview
                  ? 'AI 선임 엔지니어 리뷰 다시 보기'
                  : 'AI 선임 엔지니어 리뷰 받기'}
          </button>
          {reviewError && !reviewing && (
            <p role="alert" className="rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-300">
              {reviewError}
            </p>
          )}
          <div className="grid grid-cols-2 gap-2">
            <button onClick={onClose} className="rounded-lg bg-slate-700 py-2 text-sm hover:bg-slate-600">
              화면으로 돌아가기
            </button>
            <button onClick={onReset} className="rounded-lg bg-slate-700 py-2 text-sm hover:bg-slate-600">
              처음부터 다시
            </button>
          </div>
        </div>
        </div>
        </div>
      </div>
    </div>
  )
}
