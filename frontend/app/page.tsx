"use client";

import Image from "next/image";
import { useEffect, useState } from "react";
import { AnimatePresence, motion, type Variants } from "framer-motion";
import {
  Sparkles,
  UserPlus,
  Flame,
  Clapperboard,
  Trophy,
  LayoutGrid,
  type LucideIcon,
} from "lucide-react";

import LoginModal from "@/components/LoginModal";
import RegisterModal from "@/components/RegisterModal";
import RollingList from "@/components/RollingList";
import TaskShareModal from "@/components/TaskShareModal";
import UserMenu from "@/components/UserMenu";
import { PUBLIC_MENU } from "@/lib/menus";
import { useAuth } from "@/store/auth";

// 비로그인 공용 메뉴는 lib/menus.ts 의 PUBLIC_MENU 사용

type CardItem = {
  Icon: LucideIcon;
  title: string;
  subtitle: string;
  href: string;
  samples: string[];
};

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
  },
  {
    Icon: UserPlus,
    title: "새로운 프로필",
    subtitle: "신규 합류 인재",
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

  // ADMIN 으로 account 가 채워질 때마다 task-share 모달 자동 노출 (로그인 / 페이지 진입 모두)
  useEffect(() => {
    if (account?.account_type === "ADMIN") {
      setTaskShareOpen(true);
    }
  }, [account?.account_id, account?.account_type]);

  useEffect(() => {
    restore();
  }, [restore]);

  useEffect(() => {
    const t = setTimeout(() => setShowIntro(false), 4000);
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
              className="flex items-center md:flex-1 md:ml-8 mr-4 sm:mr-6"
            >
              <ul className="hidden md:flex flex-1 items-center justify-around">
                {PUBLIC_MENU.map((item) => (
                  <li key={item.key}>
                    <a
                      href={item.href}
                      className="text-sm sm:text-base font-medium text-white hover:text-zinc-300 transition-colors drop-shadow"
                    >
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
                작품에 꼭 맞는 인재를 AI가 찾아드립니다.
              </p>
            </motion.div>
          ) : (
            <motion.section
              key="cards"
              variants={cardsContainer}
              initial="hidden"
              animate="visible"
              className="w-full max-w-7xl grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-20 gap-y-16 sm:gap-x-24 sm:gap-y-20"
            >
              {CARDS.map((card) => (
                <motion.a
                  key={card.title}
                  href={card.href}
                  variants={cardItem}
                  whileHover={{ y: -6, scale: 1.02 }}
                  transition={{ duration: 0.2, ease: "easeOut" }}
                  className="group relative overflow-hidden rounded-2xl border border-white/15 bg-white/10 backdrop-blur-md p-6 sm:p-7 shadow-lg hover:bg-white/15 hover:border-white/30 hover:shadow-2xl transition-colors"
                >
                  <div className="flex items-center gap-3 mb-1">
                    <card.Icon
                      className="w-7 h-7 sm:w-8 sm:h-8 text-amber-100 shrink-0 drop-shadow-lg"
                      strokeWidth={1.5}
                    />
                    <h3 className="text-xl sm:text-2xl font-bold text-amber-100 tracking-tight drop-shadow">
                      {card.title}
                    </h3>
                  </div>
                  <p className="text-sm text-amber-100/70 drop-shadow">
                    {card.subtitle}
                  </p>
                  <RollingList
                    items={card.samples}
                    visible={4}
                    intervalMs={3000}
                    className="mt-4 space-y-1.5 text-[13px] leading-snug text-white font-medium min-h-[7.5rem]"
                  />
                  <span className="absolute right-5 bottom-5 text-white/60 group-hover:text-white transition-colors text-xl">
                    →
                  </span>
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
