import { Sparkles, TrendingUp } from 'lucide-react'
import Mascot from './Mascot'
import { earnedBadges, levelInfo, totalXp } from '../lib/growth'

function XpBar({ info, xp }) {
  return (
    <div>
      <div className="mb-1 flex justify-between text-xs text-slate-400">
        <span>{xp} XP</span>
        <span>{info.next ? `다음 레벨(${info.next.title})까지 ${info.toNext} XP` : '최고 레벨이에요!'}</span>
      </div>
      <div className="h-2.5 overflow-hidden rounded-full bg-slate-800" role="progressbar" aria-valuenow={info.pct} aria-valuemin={0} aria-valuemax={100} aria-label="경험치">
        <div className={`h-full rounded-full transition-all ${info.bar}`} style={{ width: `${info.pct}%` }} />
      </div>
    </div>
  )
}

export function BadgeRow({ badges }) {
  return (
    <ul className="flex flex-wrap gap-2">
      {badges.map((b) => (
        <li
          key={b.id}
          title={b.earned ? b.desc : `잠금: ${b.desc}`}
          className={`flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs ${
            b.earned ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-200' : 'border-slate-700 bg-slate-900/60 text-slate-500'
          }`}
        >
          <span className={b.earned ? '' : 'opacity-40 grayscale'}>{b.icon}</span>
          {b.name}
        </li>
      ))}
    </ul>
  )
}

// 메인 화면의 '내 캐릭터' 카드
export default function GrowthCard() {
  const xp = totalXp()
  const info = levelInfo(xp)
  const badges = earnedBadges()
  const got = badges.filter((b) => b.earned).length

  return (
    <section aria-label="내 캐릭터" className="mx-auto mt-8 max-w-3xl rounded-2xl border border-slate-700 bg-slate-900/60 p-5 text-left">
      <div className="flex items-center gap-4">
        <div className={`rounded-2xl bg-slate-800/80 p-2 ring-2 ${info.ring}`}>
          <Mascot size="result" decorative />
        </div>
        <div className="flex-1">
          <p className="text-xs font-semibold tracking-wider text-slate-500">내 캐릭터</p>
          <p className={`text-xl font-bold ${info.text}`}>
            Lv.{info.lv} {info.title}
          </p>
          <div className="mt-2">
            <XpBar info={info} xp={xp} />
          </div>
        </div>
      </div>
      <div className="mt-4">
        <p className="mb-2 text-xs text-slate-400">
          뱃지 {got}/{badges.length} · 미션을 깰수록 경험치와 뱃지를 얻어요
        </p>
        <BadgeRow badges={badges} />
      </div>
    </section>
  )
}

// 미션을 끝낸 직후 팝업에 보여 주는 '이번에 얻은 것'
export function GrowthGain({ xpBefore }) {
  const after = totalXp()
  const gained = after - xpBefore
  const before = levelInfo(xpBefore)
  const now = levelInfo(after)
  const levelUp = now.lv > before.lv
  const badges = earnedBadges()

  return (
    <div className="rounded-xl border border-amber-500/40 bg-amber-500/10 p-4">
      <div className="flex items-center gap-2 font-semibold text-amber-200">
        <Sparkles className="h-5 w-5" />
        {gained > 0 ? `경험치 +${gained} XP 획득!` : '이미 받은 보상이에요. 새 경험치는 없어요.'}
      </div>
      {levelUp && (
        <p className="mt-2 flex items-center gap-2 rounded-lg bg-amber-400/20 px-3 py-2 text-sm font-bold text-amber-100">
          <TrendingUp className="h-4 w-4" /> 레벨 업! Lv.{now.lv} {now.title} 달성!
        </p>
      )}
      <div className="mt-3">
        <XpBar info={now} xp={after} />
      </div>
      <p className="mt-3 mb-1.5 text-xs text-slate-400">뱃지</p>
      <BadgeRow badges={badges} />
      <p className="mt-2 text-xs text-slate-500">AI 리뷰를 받으면 +20 XP를 더 얻어요.</p>
    </div>
  )
}
