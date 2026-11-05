// InfraQuest AI 공식 마스코트: 주니어 엔지니어의 장애 분석을 돕는 'AI 선임 엔지니어' 로봇.
// 이미지는 Vite의 정적 파일 규칙에 따라 public/images 에 두고, 배포 주소(base)가 바뀌어도 맞도록 BASE_URL을 붙여 불러와요.
const SRC = `${import.meta.env.BASE_URL}images/infraquest-mascot.png`
const ASPECT = 1301 / 1209 // 원본 세로/가로 비율 (이미지가 뜨기 전에 자리를 잡아 화면이 흔들리지 않게 함)

// 크기는 한곳에 모아 둬서 화면마다 제각각이 되지 않게 해요. (모바일에서는 한 단계 작게)
const SIZES = {
  coach: { px: 80, cls: 'w-16 sm:w-20' }, // 미션 진행 화면의 AI 선임 (64 → 80px)
  result: { px: 96, cls: 'w-20 sm:w-24' }, // 결과·리뷰 화면 (80 → 96px)
  hero: { px: 128, cls: 'w-24 sm:w-32' }, // 메인 화면 소개 (96 → 128px)
}

export default function Mascot({ size = 'coach', decorative = false, alt = 'InfraQuest AI 선임 엔지니어 로봇', className = '' }) {
  const { px, cls } = SIZES[size]
  return (
    <img
      src={SRC}
      width={px}
      height={Math.round(px * ASPECT)}
      // 옆에 이미 글로 설명이 있는 장식용 배치는 화면 낭독기가 읽지 않게 비워 둬요.
      alt={decorative ? '' : alt}
      aria-hidden={decorative || undefined}
      draggable={false}
      // 이미지가 없거나 못 불러와도 깨진 그림 아이콘이 보이지 않게 숨겨요. (기능에는 영향 없음)
      onError={(e) => {
        e.currentTarget.style.display = 'none'
      }}
      className={`${cls} h-auto shrink-0 select-none object-contain ${className}`}
    />
  )
}
