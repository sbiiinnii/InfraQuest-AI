import { ArrowDown, Check, Database, Globe, Server, X } from 'lucide-react'

const ICONS = { WEB: Globe, WAS: Server, DB: Database }

// 내가 직접 점검한 결과만으로 서버의 상태를 요약합니다. (점검하지 않은 서버는 '미점검')
function summarize(checks) {
  if (!checks || checks.length === 0) return { tone: 'none', label: '아직 점검 안 함' }
  const fresh = checks.filter((c) => !c.stale)
  if (fresh.length === 0) return { tone: 'stale', label: '조치 후 다시 확인 필요' }
  if (fresh.some((c) => !c.ok)) return { tone: 'bad', label: '문제 발견' }
  return { tone: 'good', label: '정상 확인' }
}

const TONE = {
  none: { dot: 'bg-slate-600', text: 'text-slate-500' },
  stale: { dot: 'bg-amber-400', text: 'text-amber-300' },
  bad: { dot: 'bg-red-400', text: 'text-red-300' },
  good: { dot: 'bg-emerald-400', text: 'text-emerald-300' },
}

function CheckList({ checks }) {
  if (!checks || checks.length === 0) return null
  return (
    <ul className="mt-1.5 space-y-0.5">
      {checks.map((c) => (
        <li
          key={c.text}
          className={`flex items-center gap-1.5 text-xs ${
            c.stale ? 'text-slate-500 line-through decoration-slate-600' : c.ok ? 'text-emerald-300' : 'text-red-300'
          }`}
        >
          {c.ok ? <Check className="h-3 w-3 shrink-0" /> : <X className="h-3 w-3 shrink-0" />}
          <span>{c.text}</span>
        </li>
      ))}
    </ul>
  )
}

export default function InfraMap({ servers, selected, onSelect, observed = {} }) {
  return (
    <section className="rounded-xl border border-slate-700 bg-slate-900/60 p-4">
      <h2 className="mb-3 text-sm font-semibold text-slate-300">인프라 구성도</h2>
      <div className="flex flex-col items-stretch">
        {servers.map((s, i) => {
          const Icon = ICONS[s.name]
          const active = selected === s.name
          const checks = observed[s.name]
          const status = summarize(checks)
          const tone = TONE[status.tone]
          return (
            <div key={s.name}>
              <button
                onClick={() => onSelect(s.name)}
                className={`w-full rounded-lg border p-3 text-left transition ${
                  active
                    ? 'border-sky-400 bg-sky-500/10 ring-1 ring-sky-400/50'
                    : 'border-slate-700 bg-slate-800/60 hover:border-slate-500'
                }`}
              >
                <div className="flex items-center gap-2">
                  <Icon className={`h-5 w-5 ${active ? 'text-sky-300' : 'text-slate-400'}`} />
                  <span className="font-semibold">{s.name}</span>
                  <span className="text-xs text-slate-400">{s.role}</span>
                </div>
                <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-xs text-slate-400">
                  <dt>IP</dt>
                  <dd className="font-mono text-slate-300">{s.ip}</dd>
                  <dt>소프트웨어</dt>
                  <dd className="text-slate-300">{s.software} · {s.port}번 포트</dd>
                </dl>
                <div className="mt-2 border-t border-slate-700/70 pt-2">
                  <div className={`flex items-center gap-1.5 text-xs font-semibold ${tone.text}`}>
                    <span className={`h-2 w-2 rounded-full ${tone.dot}`} />
                    {status.label}
                  </div>
                  {status.tone === 'none' && (
                    <p className="mt-0.5 text-xs text-slate-500">직접 점검해서 확인하세요</p>
                  )}
                  <CheckList checks={checks} />
                </div>
              </button>
              {i < servers.length - 1 && (
                <div className="flex justify-center py-1 text-slate-600">
                  <ArrowDown className="h-4 w-4" />
                </div>
              )}
            </div>
          )
        })}
      </div>
      <p className="mt-3 text-xs text-slate-500">
        서버를 선택하면 그 서버의 터미널에서 명령어를 실행해요. 상태 표시는 내가 직접 실행한 점검 결과만 반영돼요.
      </p>
    </section>
  )
}
