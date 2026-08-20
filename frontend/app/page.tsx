"use client";

import Image from "next/image";
import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion, type Variants } from "framer-motion";
import {
  Sparkles,
  UserPlus,
  Flame,
  Clapperboard,
  Trophy,
  LayoutGrid,
  ArrowRight,
  type LucideIcon,
} from "lucide-react";

import LoginModal from "@/components/LoginModal";
import RegisterModal from "@/components/RegisterModal";
import RollingList from "@/components/RollingList";
import TaskShareModal from "@/components/TaskShareModal";
import UserMenu from "@/components/UserMenu";
import {
  PUBLIC_NAV_CLS,
  PUBLIC_NAV_LINK_CLS,
  getPublicNavMenu,
} from "@/lib/menus";
import { isHiddenToday } from "@/lib/taskShare";
import { useAuth } from "@/store/auth";

// 비로그인 공용 메뉴는 lib/menus.ts 의 PUBLIC_MENU 사용

type CardItem = {
  Icon: LucideIcon;
  title: string;
  subtitle: string;
  href: string;
  samples: string[];
  /**
   * 카드별 액센트. 아이콘 배지·상단 라인·hover 테두리에 쓴다.
   * 6장이 모두 같은 색이면 정보 구분이 안 되고 화면이 평평해 보인다.
   */
  accent: {
    badge: string; // 아이콘 배지 그라디언트
    line: string; // 카드 상단 1px 라인
    ring: string; // hover 시 테두리 그라디언트
    glow: string; // hover 시 발광
  };
};

// 배경이 짙은 청색이라 인접 색조(하늘·청록·보라)를 중심으로 낮은 채도로 배치했다.
const ACCENTS: CardItem["accent"][] = [
  {
    badge: "from-sky-400 to-cyan-500",
    line: "from-sky-400/70 via-cyan-300/30 to-transparent",
    ring: "group-hover:from-sky-400/60 group-hover:via-cyan-400/25",
    glow: "group-hover:shadow-[0_8px_40px_-12px_rgba(56,189,248,0.45)]",
  },
  {
    badge: "from-emerald-400 to-teal-500",
    line: "from-emerald-400/70 via-teal-300/30 to-transparent",
    ring: "group-hover:from-emerald-400/60 group-hover:via-teal-400/25",
    glow: "group-hover:shadow-[0_8px_40px_-12px_rgba(52,211,153,0.45)]",
  },
  {
    badge: "from-rose-400 to-orange-500",
    line: "from-rose-400/70 via-orange-300/30 to-transparent",
    ring: "group-hover:from-rose-400/60 group-hover:via-orange-400/25",
    glow: "group-hover:shadow-[0_8px_40px_-12px_rgba(251,113,133,0.45)]",
  },
  {
    badge: "from-violet-400 to-indigo-500",
    line: "from-violet-400/70 via-indigo-300/30 to-transparent",
    ring: "group-hover:from-violet-400/60 group-hover:via-indigo-400/25",
    glow: "group-hover:shadow-[0_8px_40px_-12px_rgba(167,139,250,0.45)]",
  },
  {
    badge: "from-amber-300 to-yellow-500",
    line: "from-amber-300/70 via-yellow-200/30 to-transparent",
    ring: "group-hover:from-amber-300/60 group-hover:via-yellow-300/25",
    glow: "group-hover:shadow-[0_8px_40px_-12px_rgba(252,211,77,0.45)]",
  },
  {
    badge: "from-blue-400 to-sky-500",
    line: "from-blue-400/70 via-sky-300/30 to-transparent",
    ring: "group-hover:from-blue-400/60 group-hover:via-sky-400/25",
    glow: "group-hover:shadow-[0_8px_40px_-12px_rgba(96,165,250,0.45)]",
  },
];

const CARDS: CardItem[] = [
  {
    Icon: Sparkles,
    title: "오늘의 AI 픽",
    subtitle: "AI 큐레이션 추천",
    href: "#",
    samples: [
      "김지윤 · 모델 · 매칭 98%",
      "박서준 · 연기자 · 매칭 95%",
      "이하늘 · 인플루언서 · 매칭 92%",
      "정유나 · 모델 · 매칭 91%",
      "한지석 · 연기자 · 매칭 90%",
      "류수아 · 보컬 · 매칭 89%",
      "강민혁 · 댄서 · 매칭 88%",
      "송지현 · MC · 매칭 87%",
      "노예진 · 모델 · 매칭 86%",
    ],
    accent: ACCENTS[0],
  },
  {
    Icon: UserPlus,
    title: "새로운 프로필",
    subtitle: "신규 합류 아티스트",
    href: "#",
    samples: [
      "정민아 · 모델 · 24세",
      "강현우 · 연기자 · 28세",
      "윤소연 · 보컬 · 21세",
      "김도윤 · 연기자 · 26세",
      "이서연 · 모델 · 23세",
      "박지훈 · 인플루언서 · 25세",
      "최가은 · 댄서 · 22세",
      "한태우 · MC · 30세",
      "오하린 · 모델 · 19세",
    ],
    accent: ACCENTS[1],
  },
  {
    Icon: Flame,
    title: "인기 프로필",
    subtitle: "이번 주 TOP",
    href: "#",
    samples: [
      "1위 최태영 · 연기자",
      "2위 한예린 · 모델",
      "3위 서지호 · MC",
      "4위 김선우 · 연기자",
      "5위 박혜원 · 모델",
      "6위 임재현 · 보컬",
      "7위 신유경 · 인플루언서",
      "8위 강도현 · 댄서",
      "9위 윤아라 · 모델",
    ],
    accent: ACCENTS[2],
  },
  {
    Icon: Clapperboard,
    title: "진행 중인 캐스팅",
    subtitle: "모집 중인 프로젝트",
    href: "#",
    samples: [
      "화장품 광고 메인 모델 · D-3",
      "단편영화 주연 (20대 男) · D-7",
      "웹드라마 조연 3명 · D-10",
      "글로벌 의류 캠페인 모델 · D-5",
      "뮤직비디오 출연자 · D-2",
      "자동차 광고 라이프스타일 · D-14",
      "가구 카탈로그 부부 모델 · D-6",
      "라이브 커머스 쇼호스트 · D-1",
      "게임 광고 액션 모델 · D-8",
    ],
    accent: ACCENTS[3],
  },
  {
    Icon: Trophy,
    title: "성공 매칭 사례",
    subtitle: "함께한 작품들",
    href: "#",
    samples: [
      "글로벌 패션 브랜드 SS26 캠페인 [2026년 2월]",
      "Netflix 오리지널 시리즈 조연 [2026년 4월]",
      "현대차 TVC 메인 모델 [2025년 11월]",
      "쿠팡플레이 드라마 주연 [2025년 8월]",
      "아모레퍼시픽 브랜드 화보 [2026년 3월]",
      "디즈니플러스 다큐 내레이션 [2025년 9월]",
      "CGV 멀티플렉스 광고 [2025년 6월]",
      "카카오엔터 음원 데뷔 [2026년 1월]",
      "삼성전자 갤럭시 캠페인 [2026년 4월]",
    ],
    accent: ACCENTS[4],
  },
  {
    Icon: LayoutGrid,
    title: "분야별 탐색",
    subtitle: "모델·연기자·인플루언서",
    href: "#",
    samples: [
      "모델 · 연기자 · 인플루언서",
      "보컬 · 댄서 · MC",
      "어린이 · 시니어 · 외국인",
      "성우 · 코미디언 · 진행자",
      "피트니스 · 스포츠 · 키즈",
      "패션쇼 · 광고 · 영상",
      "뷰티 · 헬스 · 라이프스타일",
      "사극 · SF · 스릴러",
      "보컬 듀오 · 그룹 · 솔로",
    ],
    accent: ACCENTS[5],
  },
];

const cardsContainer: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { delayChildren: 0.3, staggerChildren: 0.1 },
  },
};

const cardItem: Variants = {
  hidden: { opacity: 0, y: 24 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.5, ease: "easeOut" as const },
  },
};

export default function Home() {
  const [showIntro, setShowIntro] = useState(true);
  const [loginOpen, setLoginOpen] = useState(false);
  const [registerOpen, setRegisterOpen] = useState(false);
  const [taskShareOpen, setTaskShareOpen] = useState(false);
  const restore = useAuth((s) => s.restore);
  const account = useAuth((s) => s.account);

  // 헤더 메뉴 — 아티스트 탐색 화면과 **같은 구성**을 쓴다 (lib/menus.ts).
  // 로그인 시 맨 뒤에 '마이 페이지' 가 붙는다.
  const navMenu = useMemo(() => getPublicNavMenu(account), [account]);

  // ADMIN 으로 account 가 채워질 때마다 task-share 모달 자동 노출.
  // 단 "오늘 하루 그만 보기" 설정한 날에는 띄우지 않음.
  useEffect(() => {
    if (account?.account_type === "ADMIN" && !isHiddenToday()) {
      setTaskShareOpen(true);
    }
  }, [account?.account_id, account?.account_type]);

  useEffect(() => {
    restore();
  }, [restore]);

  useEffect(() => {
    const t = setTimeout(() => setShowIntro(false), 1000);
    return () => clearTimeout(t);
  }, []);

  return (
    <div className="relative flex-1 w-full overflow-hidden">
      <Image
        src="/images/Backgroud.jpg"
        alt=""
        fill
        priority
        sizes="100vw"
        className="object-cover -z-10"
      />
      <div className="absolute inset-0 bg-black/50 -z-10" />

      <header className="absolute top-0 left-0 right-0 z-10 flex items-center justify-between pl-4 sm:pl-6 pt-3 sm:pt-4">
        <Image
          src="/images/Actora_logo.png"
          alt="Actora"
          width={1097}
          height={315}
          priority
          className="h-16 w-auto drop-shadow-lg"
        />

        <AnimatePresence>
          {!showIntro && (
            <motion.nav
              key="main-nav"
              initial={{ opacity: 0, y: -20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, ease: "easeOut" }}
              className="flex items-center md:flex-1 md:ml-8 mr-4 sm:mr-6 justify-center"
            >
              {/* 메뉴는 한 덩어리로 모아 둔다 — 화면 폭에 흩뿌리면 그룹으로 안 읽힌다 */}
              <ul className={PUBLIC_NAV_CLS}>
                {navMenu.map((item) => (
                  <li key={item.key}>
                    <a href={item.href} className={PUBLIC_NAV_LINK_CLS}>
                      {item.label}
                    </a>
                  </li>
                ))}
              </ul>
              <div className="md:ml-6">
                <UserMenu
                  onLoginClick={() => setLoginOpen(true)}
                  onRegisterClick={() => setRegisterOpen(true)}
                />
              </div>
            </motion.nav>
          )}
        </AnimatePresence>
      </header>

      <main className="relative flex min-h-screen flex-col items-center justify-center px-6 pt-32 pb-12">
        <AnimatePresence mode="wait">
          {showIntro ? (
            <motion.div
              key="intro"
              initial={{ opacity: 1, y: 0 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -16 }}
              transition={{ duration: 1, ease: "easeOut" }}
              className="text-center"
            >
              <h1 className="text-5xl sm:text-7xl font-bold text-white tracking-tight drop-shadow-2xl">
                Actora AI
              </h1>
              <h2 className="mt-4 text-2xl sm:text-4xl font-semibold text-white tracking-tight drop-shadow-xl">
                AI가 연결하는 캐스팅 매칭 플랫폼
              </h2>
              <p className="mt-6 max-w-2xl text-base sm:text-lg text-zinc-100 drop-shadow-lg leading-relaxed">
                광고주와 영상 제작자를 위한 모델·연기자 추천 서비스.
                <br />
                작품에 꼭 맞는 아티스트를 AI가 찾아드립니다.
              </p>
            </motion.div>
          ) : (
            <motion.section
              key="cards"
              variants={cardsContainer}
              initial="hidden"
              animate="visible"
              className="w-full max-w-7xl grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5 sm:gap-6"
            >
              {CARDS.map((card) => (
                <motion.a
                  key={card.title}
                  href={card.href}
                  variants={cardItem}
                  whileHover={{ y: -5 }}
                  transition={{ duration: 0.2, ease: "easeOut" }}
                  // 마우스 위치를 CSS 변수로 넘겨 카드 안에 스포트라이트를 그린다
                  onMouseMove={(e) => {
                    const r = e.currentTarget.getBoundingClientRect();
                    e.currentTarget.style.setProperty("--mx", `${e.clientX - r.left}px`);
                    e.currentTarget.style.setProperty("--my", `${e.clientY - r.top}px`);
                  }}
                  // 1px 그라디언트 테두리 — 바깥 래퍼가 테두리, 안쪽 div 가 본문
                  className={`group relative rounded-2xl p-px bg-gradient-to-br from-white/20 via-white/10 to-white/5 shadow-xl transition-all duration-300 ${card.accent.ring} ${card.accent.glow}`}
                >
                  <div className="relative h-full overflow-hidden rounded-2xl bg-zinc-950/60 backdrop-blur-xl px-6 pt-6 pb-16 sm:px-7 sm:pt-7">
                    {/* 스포트라이트 — hover 시에만 은은하게 */}
                    <div
                      aria-hidden
                      className="pointer-events-none absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300"
                      style={{
                        background:
                          "radial-gradient(420px circle at var(--mx, 50%) var(--my, 50%), rgba(255,255,255,0.07), transparent 45%)",
                      }}
                    />
                    {/* 카드별 색을 알려주는 상단 1px 라인 */}
                    <div
                      aria-hidden
                      className={`absolute inset-x-0 top-0 h-px bg-gradient-to-r ${card.accent.line}`}
                    />

                    <div className="relative flex items-center gap-3.5">
                      <span
                        className={`grid place-items-center w-11 h-11 shrink-0 rounded-xl bg-gradient-to-br ${card.accent.badge} ring-1 ring-white/20 shadow-lg transition-transform duration-300 group-hover:scale-105`}
                      >
                        <card.Icon className="w-5 h-5 text-white" strokeWidth={2} />
                      </span>
                      <div className="min-w-0">
                        <h3 className="text-lg sm:text-xl font-bold text-white tracking-tight truncate">
                          {card.title}
                        </h3>
                        <p className="mt-0.5 text-xs text-white/45">
                          {card.subtitle}
                        </p>
                      </div>
                    </div>

                    <RollingList
                      items={card.samples}
                      visible={4}
                      intervalMs={3000}
                      className="relative mt-5 space-y-2 text-[13px] leading-snug text-white/85 min-h-[7.5rem]"
                      itemClassName="relative truncate pl-3.5 before:absolute before:left-0 before:top-[0.6em] before:h-1 before:w-1 before:rounded-full before:bg-white/30 before:transition-colors group-hover:before:bg-white/60"
                    />

                    <span className="absolute right-5 bottom-5 grid place-items-center w-9 h-9 rounded-full bg-white/[0.06] ring-1 ring-white/10 text-white/45 transition-all duration-300 group-hover:bg-white/15 group-hover:text-white group-hover:translate-x-0.5">
                      <ArrowRight className="w-4 h-4" />
                    </span>
                  </div>
                </motion.a>
              ))}
            </motion.section>
          )}
        </AnimatePresence>
      </main>

      <LoginModal
        open={loginOpen}
        onClose={() => setLoginOpen(false)}
        onSwitchToRegister={() => setRegisterOpen(true)}
      />
      <RegisterModal open={registerOpen} onClose={() => setRegisterOpen(false)} />
      <TaskShareModal open={taskShareOpen} onClose={() => setTaskShareOpen(false)} />
    </div>
  );
}
