import { Bot, ChevronRight, Lock, Network, ServerCrash, ShieldAlert, Terminal, Wrench } from 'lucide-react'
import DataNotice from '../components/DataNotice'
import GrowthCard from '../components/GrowthCard'
import Mascot from '../components/Mascot'
import SiteHeader from '../components/SiteHeader'
import { useMissions } from '../hooks/useMissions'
import { WAKING_TEXT, useSlow } from '../hooks/useSlow'
import { loadProgress } from '../lib/progress'

const CATEGORIES = [
  { name: 'Linux 서버 장애', icon: Terminal, desc: '서비스 중단, 디스크, 권한 문제 등' },
  { name: '네트워크 장애', icon: Network, desc: '연결 불가, DNS, 라우팅 문제 등' },
  { name: 'WEB/WAS/DB 서비스 장애', icon: ServerCrash, desc: 'Nginx · Tomcat · MariaDB 3계층 서비스 장애' },
]

const STEPS = [
  { icon: ShieldAlert, title: '1. 장애가 터져요', text: '웹사이트에 오류(502, 500 등)가 나는 가상 서버가 주어져요.' },
  { icon: Wrench, title: '2. 직접 진단하고 복구해요', text: '가상 터미널에서 명령어로 원인을 찾고 서비스를 살려요.' },
  { icon: Bot, title: '3. AI 선임이 평가해요', text: '내가 실제로 한 행동을 근거로 잘한 점과 개선점을 알려 줘요.' },
]

export default function Dashboard() {
  const { missions, error, reload } = useMissions()
  const slow = useSlow(!missions && !error)
  const done = Object.keys(loadProgress())
  const available = missions?.filter((m) => m.status === 'available') ?? []
  const soon = missions?.filter((m) => m.status === 'coming_soon') ?? []
  const doneCount = available.filter((m) => done.includes(m.id)).length

  return (
    <div className="min-h-screen">
      <SiteHeader active="home" />
      <main className="mx-auto max-w-6xl px-4 pb-16">
        <section className="py-14 text-center">
          <div className="mx-auto mb-3 flex justify-center">
            <Mascot size="hero" alt="InfraQuest AI의 마스코트, AI 선임 엔지니어 로봇" />
          </div>
          <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
            InfraQuest <span className="text-emerald-400">AI</span>
          </h1>
          <p className="mt-4 text-2xl font-semibold text-slate-100">장애를 해결하고, 엔지니어로 성장하세요</p>
          <p className="mx-auto mt-3 max-w-2xl text-slate-400">
            AI가 정답을 설명해 주는 서비스가 아니에요. 가상 서버에서 일어난 장애를 <b className="text-slate-200">내가 직접</b>{' '}
            진단하고 복구한 뒤, AI 선임 엔지니어에게 내 문제 해결 과정을 평가받는 실전 훈련이에요.
          </p>
          <a
            href="#/missions"
            className="mt-7 inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-7 py-3 text-base font-semibold text-white shadow-lg shadow-emerald-900/40 hover:bg-emerald-500"
          >
            미션 시작 <ChevronRight className="h-5 w-5" />
          </a>
          <p className="mt-3 text-xs text-slate-500">
            모든 서버와 명령어 결과는 가상(시뮬레이션)이라 실제 서버에는 영향이 없어요.
          </p>
          <GrowthCard />
        </section>

        <section className="grid gap-4 md:grid-cols-3">
          {STEPS.map(({ icon: Icon, title, text }) => (
            <div key={title} className="rounded-xl border border-slate-700 bg-slate-900/60 p-5">
              <Icon className="mb-3 h-6 w-6 text-sky-400" />
              <h2 className="mb-1 font-semibold">{title}</h2>
              <p className="text-sm text-slate-400">{text}</p>
            </div>
          ))}
        </section>

        <section className="mt-10 rounded-xl border border-slate-700 bg-slate-900/60 p-5">
          <h2 className="mb-3 font-semibold">내 학습 진행 상황</h2>
          {error ? (
            <p className="text-sm text-red-400">
              {error}{' '}
              <button onClick={reload} className="underline">
                다시 시도
              </button>
            </p>
          ) : !missions ? (
            <p className="text-sm text-slate-500">
              불러오는 중...{slow && <span className="ml-2 text-amber-300">{WAKING_TEXT}</span>}
            </p>
          ) : (
            <div className="flex flex-wrap items-end gap-x-10 gap-y-3">
              <div>
                <div className="text-3xl font-bold text-emerald-400">
                  {doneCount}
                  <span className="text-lg text-slate-500"> / {available.length}</span>
                </div>
                <div className="text-sm text-slate-400">완료한 미션</div>
              </div>
              <div>
                <div className="text-3xl font-bold text-slate-200">{soon.length}</div>
                <div className="text-sm text-slate-400">준비 중인 미션</div>
              </div>
              <p className="text-xs text-slate-500">학습 기록은 이 브라우저에만 저장돼요.</p>
            </div>
          )}
        </section>

        <section className="mt-6">
          <DataNotice />
        </section>

        <section className="mt-10">
          <h2 className="mb-3 font-semibold">학습 가능한 장애 카테고리</h2>
          <div className="grid gap-4 md:grid-cols-3">
            {CATEGORIES.map(({ name, icon: Icon, desc }) => {
              const count = missions ? available.filter((m) => m.category === name).length : 0
              const open = count > 0
              const Card = open ? 'a' : 'div'
              return (
                <Card
                  key={name}
                  {...(open ? { href: '#/missions' } : {})}
                  className={`rounded-xl border p-5 ${
                    open
                      ? 'border-emerald-500/40 bg-emerald-500/5 hover:bg-emerald-500/10'
                      : 'border-slate-800 bg-slate-900/40 opacity-70'
                  }`}
                >
                  <div className="mb-3 flex items-center justify-between">
                    <Icon className={`h-6 w-6 ${open ? 'text-emerald-400' : 'text-slate-500'}`} />
                    {open ? (
                      <span className="rounded-full bg-emerald-500/15 px-2.5 py-0.5 text-xs font-semibold text-emerald-300">
                        미션 {count}개 이용 가능
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 rounded-full bg-slate-800 px-2.5 py-0.5 text-xs text-slate-400">
                        <Lock className="h-3 w-3" /> 준비 중
                      </span>
                    )}
                  </div>
                  <h3 className="font-semibold">{name}</h3>
                  <p className="mt-1 text-sm text-slate-400">{desc}</p>
                </Card>
              )
            })}
          </div>
        </section>
      </main>
    </div>
  )
}
