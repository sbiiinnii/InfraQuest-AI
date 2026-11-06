import { Info } from 'lucide-react'

// '가상(시뮬레이션)'인 것과 '실제로 저장·생성되는' 것을 구분해서 보여 줘요. (심사·사용자가 헷갈리지 않게)
export default function DataNotice() {
  return (
    <div className="rounded-xl border border-slate-700 bg-slate-900/60 p-5 text-left">
      <h2 className="mb-3 flex items-center gap-2 font-semibold">
        <Info className="h-4 w-4 text-sky-400" /> 무엇이 가상이고, 무엇이 실제인가요?
      </h2>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-4">
          <p className="mb-2 text-sm font-semibold text-amber-300">가상(시뮬레이션) · 실제 서버가 아니에요</p>
          <ul className="list-disc space-y-1 pl-5 text-sm text-slate-300">
            <li>WEB · WAS · DB 서버와 IP 주소</li>
            <li>명령어 실행 결과, 서버 상태(장애·복구)</li>
            <li>복구 성공 여부 판정 (규칙으로 계산)</li>
          </ul>
        </div>
        <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-4">
          <p className="mb-2 text-sm font-semibold text-emerald-300">실제로 저장·생성되는 것</p>
          <ul className="list-disc space-y-1 pl-5 text-sm text-slate-300">
            <li>
              <b className="text-slate-100">이번 실습의 명령어·가설</b>: 서버 메모리에 임시 보관돼요. 서버가 다시 켜지면 사라져요.
            </li>
            <li>
              <b className="text-slate-100">완료 기록·경험치·레벨·뱃지</b>: 이 브라우저에만 저장돼요. 로그인이 없어서 다른 기기에서는 처음부터 시작해요.
            </li>
            <li>
              <b className="text-slate-100">AI 리뷰·힌트</b>: 실제 AI가 만든 글이에요. 틀릴 수 있어요.
            </li>
          </ul>
        </div>
      </div>
    </div>
  )
}
