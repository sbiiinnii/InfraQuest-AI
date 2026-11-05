import { Terminal } from 'lucide-react'

export default function SiteHeader({ active }) {
  const link = (href, label, key) => (
    <a
      href={href}
      className={`rounded-lg px-3 py-1.5 text-sm ${
        active === key ? 'bg-slate-800 text-white' : 'text-slate-400 hover:text-white'
      }`}
    >
      {label}
    </a>
  )
  return (
    <header className="border-b border-slate-800 bg-slate-950/80">
      <div className="mx-auto flex max-w-6xl items-center gap-4 px-4 py-3">
        <a href="#/" className="flex items-center gap-2 font-bold">
          <Terminal className="h-5 w-5 text-emerald-400" />
          InfraQuest <span className="text-emerald-400">AI</span>
        </a>
        <nav className="ml-auto flex gap-1">
          {link('#/', '홈', 'home')}
          {link('#/missions', '미션', 'missions')}
        </nav>
      </div>
    </header>
  )
}
