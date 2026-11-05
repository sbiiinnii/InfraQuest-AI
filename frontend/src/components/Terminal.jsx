import { useEffect, useRef, useState } from 'react'

export default function Terminal({ server, lines, commandHistory, busy, onRun }) {
  const [value, setValue] = useState('')
  const [cursor, setCursor] = useState(null) // 위/아래 화살표로 이전 명령어를 고를 때의 위치
  const [clearedAt, setClearedAt] = useState({}) // 서버별로 'clear' 한 시점
  const bottomRef = useRef(null)
  const inputRef = useRef(null)

  const shown = lines.filter((l) => l.seq > (clearedAt[server.name] || 0))
  const prompt = `root@${server.hostname}:~#`

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: 'end' })
  }, [shown.length, server.name])

  useEffect(() => {
    inputRef.current?.focus()
  }, [server.name, busy])

  async function submit(e) {
    e.preventDefault()
    const cmd = value.trim()
    if (!cmd || busy) return
    setValue('')
    setCursor(null)
    if (cmd === 'clear') {
      // 화면만 비웁니다. (기록은 그대로 남아 있어요)
      const last = lines.length ? lines[lines.length - 1].seq : 0
      setClearedAt((c) => ({ ...c, [server.name]: last }))
      return
    }
    await onRun(cmd)
  }

  function onKeyDown(e) {
    if (e.key === 'ArrowUp' && commandHistory.length) {
      e.preventDefault()
      const next = cursor === null ? commandHistory.length - 1 : Math.max(0, cursor - 1)
      setCursor(next)
      setValue(commandHistory[next])
    } else if (e.key === 'ArrowDown' && cursor !== null) {
      e.preventDefault()
      const next = cursor + 1
      if (next >= commandHistory.length) {
        setCursor(null)
        setValue('')
      } else {
        setCursor(next)
        setValue(commandHistory[next])
      }
    } else if (e.key === 'l' && e.ctrlKey) {
      e.preventDefault()
      const last = lines.length ? lines[lines.length - 1].seq : 0
      setClearedAt((c) => ({ ...c, [server.name]: last }))
    }
  }

  return (
    <div
      className="flex h-[58vh] min-h-[360px] flex-col rounded-xl border border-slate-700 bg-black/80 font-mono text-sm shadow-inner"
      onClick={() => inputRef.current?.focus()}
    >
      <div className="flex items-center justify-between border-b border-slate-800 px-3 py-2 text-xs text-slate-400">
        <span>
          <span className="text-emerald-400">●</span> {server.name} · {server.hostname} · {server.ip}
        </span>
        <span>가상 터미널</span>
      </div>
      <div data-testid="terminal-output" className="flex-1 overflow-y-auto px-3 py-2 leading-relaxed">
        <div className="text-slate-500">
          {server.name} 서버에 연결되었습니다. 이곳은 가상 환경이라 실제 서버에는 영향이 없어요.
          <br />
          사용할 수 있는 명령어는 <span className="text-slate-300">help</span> 를 입력해 보세요.
        </div>
        {shown.map((l) => (
          <div key={l.seq} className="mt-1">
            <div>
              <span className="text-emerald-400">{`root@${server.hostname}:~#`}</span>{' '}
              <span className="text-slate-100">{l.command}</span>
            </div>
            {l.output && (
              <pre
                className={`whitespace-pre-wrap break-words ${
                  l.supported ? 'text-slate-300' : 'text-amber-300'
                }`}
              >
                {l.output}
              </pre>
            )}
          </div>
        ))}
        <form onSubmit={submit} className="mt-1 flex items-center gap-2">
          <label htmlFor="term-input" className="shrink-0 text-emerald-400">
            {prompt}
          </label>
          <input
            id="term-input"
            ref={inputRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={onKeyDown}
            disabled={busy}
            autoComplete="off"
            autoCapitalize="off"
            spellCheck={false}
            className="min-w-0 flex-1 bg-transparent text-slate-100 caret-emerald-400 outline-none"
          />
        </form>
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
