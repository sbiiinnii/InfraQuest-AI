import { useEffect, useRef } from 'react'
import Rich from './Rich'
import { BookOpen, Lightbulb, Loader2 } from 'lucide-react'

const LEVEL_NAMES = { 1: '점검 방향', 2: '확인할 서버·영역', 3: '명령어 예시' }

// 힌트를 모두 쓰고 '해설 보기'를 눌렀을 때만 나타나는 정답 해설.
// 화면 맨 아래 줄을 전체 폭으로 쓰기 때문에, 한 가운데 열만 길어져서 양옆이 비어 보이는 일이 없어요.
export function SolutionCard({ solution }) {
  const mine = solution.my_checks
  const ref = useRef(null)
  // 해설이 열리면 그 위치로 화면을 내려 줍니다. (화면 아래쪽에 생긴 걸 놓치기 쉬워요)
  useEffect(() => {
    ref.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [])
  return (
    <section ref={ref} className="rounded-xl border border-violet-500/40 bg-violet-500/5 p-4">
      <h2 className="mb-1 flex items-center gap-2 text-sm font-semibold text-violet-300">
        <BookOpen className="h-4 w-4" /> 정답 해설
      </h2>
      <p className="mb-3 text-xs text-slate-500">
        해설을 본 미션은 &lsquo;해설 보고 푼 미션&rsquo;으로 기록돼요. 이어서 직접 복구하고 검증하면 미션을 끝낼 수 있어요.
      </p>

      <div className="grid gap-x-8 gap-y-3 md:grid-cols-2">
        <div>
          <h3 className="mb-1 text-xs font-semibold text-violet-300">원인</h3>
          <p className="mb-3 text-sm leading-relaxed text-slate-200">
            <Rich text={solution.cause} />
          </p>

          <h3 className="mb-1 text-xs font-semibold text-violet-300">내가 지금까지 한 것</h3>
          <ul className="mb-3 space-y-0.5 text-xs text-slate-300">
            <li>
              {mine.root_cause_checked ? '✓ 원인이 있는 서버를 직접 확인했어요' : '✗ 원인이 있는 서버를 직접 확인한 기록이 아직 없어요'}
            </li>
            <li>{mine.hypothesis_submitted ? '✓ 원인 가설을 제출했어요' : '✗ 원인 가설은 아직 제출하지 않았어요'}</li>
            {mine.evidence.map((e) => (
              <li key={e} className="text-slate-400">
                · {e}
              </li>
            ))}
          </ul>

          <p className="rounded-lg bg-slate-900/70 p-2 text-xs leading-relaxed text-slate-300">
            <span className="font-semibold text-violet-300">기억해 두세요 · </span>
            {solution.lesson}
          </p>
        </div>

        <div>
          <h3 className="mb-1 text-xs font-semibold text-violet-300">이렇게 찾아가면 돼요</h3>
          <ol className="mb-3 list-decimal space-y-1 pl-5 text-sm leading-relaxed text-slate-200">
            {solution.path.map((step) => (
              <li key={step}>
                <Rich text={step} />
              </li>
            ))}
          </ol>

          <h3 className="mb-1 text-xs font-semibold text-violet-300">복구 방법</h3>
          <ul className="list-disc space-y-1 pl-5 text-sm leading-relaxed text-slate-200">
            {solution.fix.map((step) => (
              <li key={step}>
                <Rich text={step} />
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  )
}

// AI 힌트(최대 3단계). 터미널 아래쪽 넓은 자리에 둬서, 오른쪽 패널이 아래로 길게 내려가지 않게 해요.
// (solution은 '해설을 이미 봤는지'를 알려 주는 용도로만 써요. 해설 내용은 SolutionCard가 따로 보여 줘요.)
export default function HintPanel({
  completed,
  hints,
  hintMax,
  hinting,
  hintError,
  onRequestHint,
  solution,
  solutionError,
  onRequestSolution,
}) {
  return (
    <div className="min-w-0">
      <section className="rounded-xl border border-slate-700 bg-slate-900/60 p-4">
        <h2 className="mb-1 flex items-center gap-2 text-sm font-semibold text-slate-300">
          <Lightbulb className="h-4 w-4 text-amber-300" /> AI 힌트
          <span className="ml-auto text-xs font-normal text-slate-500">
            {hints.length}/{hintMax} 사용
          </span>
        </h2>
        <p className="mb-2 text-xs text-slate-500">
          막혔을 때만 쓰세요. 정답이나 복구 명령어는 알려 주지 않고, 사용 기록은 AI 리뷰에 반영돼요.
          힌트 {hintMax}개를 모두 쓰고도 막히면 정답 해설을 볼 수 있어요.
        </p>
        {hints.length > 0 && (
          <ol className="mb-2 space-y-2">
            {hints.map((h) => (
              <li key={h.level} className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-2.5 text-sm">
                <div className="mb-1 text-xs font-semibold text-amber-300">
                  {h.level}단계 · {LEVEL_NAMES[h.level]}
                </div>
                <p className="whitespace-pre-wrap break-words leading-relaxed text-slate-200">
                  <Rich text={h.text} />
                </p>
              </li>
            ))}
          </ol>
        )}
        {completed ? (
          <p className="text-xs text-slate-500">정상화를 마쳐서 더 이상 힌트를 받을 수 없어요.</p>
        ) : hints.length >= hintMax ? (
          solution ? (
            <p className="text-xs text-slate-500">힌트를 모두 사용했고, 해설도 확인했어요. 아래 해설을 참고해 이어서 풀어 보세요.</p>
          ) : (
            <div>
              <p className="mb-2 text-xs text-slate-400">힌트를 모두 사용했어요. 그래도 막혔다면 정답 해설을 볼 수 있어요.</p>
              <button
                onClick={() => {
                  if (
                    window.confirm(
                      '정답 해설을 볼까요?\n\n원인과 복구 방법을 알려 줘요. 이 미션은 \'해설 보고 푼 미션\'으로 기록되고, AI 리뷰의 원인 분석 점수에도 반영돼요.',
                    )
                  )
                    onRequestSolution()
                }}
                className="flex w-full items-center justify-center gap-2 rounded-lg bg-violet-600/90 py-2 text-sm font-semibold text-white transition hover:bg-violet-500"
              >
                <BookOpen className="h-4 w-4" /> 정답 해설 보기
              </button>
            </div>
          )
        ) : (
          <button
            onClick={onRequestHint}
            disabled={hinting}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-amber-600/90 py-2 text-sm font-semibold text-white transition hover:bg-amber-500 disabled:cursor-wait disabled:bg-slate-700 disabled:text-slate-300"
          >
            {hinting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" /> AI가 힌트를 만드는 중...
              </>
            ) : (
              <>
                <Lightbulb className="h-4 w-4" /> {hints.length + 1}단계 힌트 받기 ({LEVEL_NAMES[hints.length + 1]})
              </>
            )}
          </button>
        )}
        {hintError && (
          <p role="alert" className="mt-2 rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs text-red-300">
            {hintError}
          </p>
        )}
        {solutionError && (
          <p role="alert" className="mt-2 rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs text-red-300">
            {solutionError}
          </p>
        )}
      </section>
    </div>
  )
}
