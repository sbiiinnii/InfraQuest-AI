// `명령어` 처럼 백틱으로 감싼 부분을 코드 모양으로 보여 줍니다.
export default function Rich({ text }) {
  return text.split(/(`[^`]+`)/g).map((part, i) =>
    part.startsWith('`') && part.endsWith('`') && part.length > 2 ? (
      <code key={i} className="rounded bg-slate-800 px-1 py-0.5 font-mono text-[0.85em] text-sky-300">
        {part.slice(1, -1)}
      </code>
    ) : (
      part
    ),
  )
}
