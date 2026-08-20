"use client";

import Image from "next/image";
import { Hammer, type LucideIcon } from "lucide-react";
import { useEffect, useState } from "react";

import DashboardHeader from "@/components/DashboardHeader";
import LoginModal from "@/components/LoginModal";
import RegisterModal from "@/components/RegisterModal";
import { useAuth } from "@/store/auth";

type Props = {
  /** 페이지 제목 */
  title: string;
  /** 제목 아래 한 줄 설명 */
  description: string;
  /** 메뉴와 같은 아이콘 (lib/menus.ts 의 Icon) */
  Icon: LucideIcon;
  /** 본문 안내에 덧붙일 문장 (선택) */
  note?: string;
};

/**
 * 아직 만들지 않은 공용 페이지의 자리 화면.
 *
 * 배경·헤더·여백을 아티스트 탐색 화면과 동일하게 맞춰, 메뉴를 오갈 때
 * 레이아웃이 튀지 않게 한다. 헤더는 menu="public" 으로 랜딩과 같은 메뉴를 쓴다.
 */
export default function ComingSoonView({
  title,
  description,
  Icon,
  note,
}: Props) {
  const restore = useAuth((s) => s.restore);
  const account = useAuth((s) => s.account);
  const [loginOpen, setLoginOpen] = useState(false);
  const [registerOpen, setRegisterOpen] = useState(false);

  // 공용 경로로 직접 들어온 경우 인증 상태를 한 번 복원해 둔다
  // (헤더의 '마이 페이지' 표시가 로그인 여부에 따라 달라진다)
  useEffect(() => {
    if (!account) restore();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="relative min-h-screen w-full overflow-hidden">
      <Image
        src="/images/Backgroud.jpg"
        alt=""
        fill
        priority
        sizes="100vw"
        className="object-cover -z-10"
      />
      <div className="absolute inset-0 bg-black/55 -z-10" />

      <DashboardHeader
        variant="dark"
        menu="public"
        onLoginClick={() => setLoginOpen(true)}
      />

      <main className="relative max-w-7xl mx-auto px-4 sm:px-6 pt-28 pb-12">
        <h1 className="text-2xl sm:text-3xl font-bold text-white drop-shadow-lg flex items-center gap-2">
          <Icon className="w-7 h-7 text-amber-100" />
          {title}
        </h1>
        <p className="mt-1 text-white/80 drop-shadow">{description}</p>

        <div className="mt-10 rounded-xl border border-white/15 bg-white/5 backdrop-blur-md px-6 py-16 text-center">
          <Hammer className="w-10 h-10 mx-auto text-amber-100/70" strokeWidth={1.5} />
          <p className="mt-4 text-lg font-semibold text-white drop-shadow">
            개발 중입니다
          </p>
          <p className="mt-2 text-sm text-white/70">
            {note ?? "이 기능은 준비 중입니다. 곧 만나보실 수 있습니다."}
          </p>
        </div>
      </main>

      <LoginModal
        open={loginOpen}
        onClose={() => setLoginOpen(false)}
        onSwitchToRegister={() => setRegisterOpen(true)}
      />
      <RegisterModal open={registerOpen} onClose={() => setRegisterOpen(false)} />
    </div>
  );
}
