"use client";

import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, LogOut, User } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { getDashboardPath } from "@/lib/menus";
import { PUBLIC_NAV_TEXT } from "@/lib/menus";
import { useAuth, type AccountInfo } from "@/store/auth";

const FALLBACK_TYPE_LABEL: Record<AccountInfo["account_type"], string> = {
  ADMIN: "관리자",
  TALENT: "연기자",
  AGENCY: "에이전시",
};

type Variant = "dark" | "light";

type Props = {
  onLoginClick: () => void;
  onRegisterClick?: () => void;
  variant?: Variant; // dark: 어두운 배경(메인) / light: 밝은 배경(dashboard)
};

export default function UserMenu({
  onLoginClick,
  onRegisterClick,
  variant = "dark",
}: Props) {
  const account = useAuth((s) => s.account);
  const logout = useAuth((s) => s.logout);
  const router = useRouter();
  const [openMenu, setOpenMenu] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onClickOutside = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpenMenu(false);
      }
    };
    window.addEventListener("mousedown", onClickOutside);
    return () => window.removeEventListener("mousedown", onClickOutside);
  }, []);

  if (!account) {
    // 로그인 — 메뉴 알약과 같은 유리 질감. 보조 동작이라 배경을 채우지 않는다.
    const textCls =
      variant === "dark"
        ? "text-white/80 ring-1 ring-white/15 bg-white/[0.06] hover:bg-white/[0.12] hover:text-white hover:ring-white/25"
        : "text-zinc-700 ring-1 ring-zinc-200 bg-white hover:bg-zinc-50 hover:text-zinc-900";
    // 회원가입 — 헤더에서 유일한 강조 버튼.
    // 메뉴의 활성 항목이 흰 알약이라, 회원가입까지 흰색이면 서로 경쟁한다.
    // 아바타와 같은 하늘→보라 그라디언트로 구분하고 같은 색 glow 를 준다.
    const cta =
      variant === "dark"
        ? "text-white bg-gradient-to-r from-sky-500 to-violet-500 hover:from-sky-400 hover:to-violet-400 ring-1 ring-white/20 shadow-[0_6px_24px_-6px_rgba(129,140,248,0.75)]"
        : "text-white bg-gradient-to-r from-sky-600 to-violet-600 hover:from-sky-500 hover:to-violet-500 shadow-[0_6px_20px_-8px_rgba(79,70,229,0.6)]";
    return (
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onLoginClick}
          // 메뉴와 같은 글자 크기·굵기 (PUBLIC_NAV_TEXT)
          className={`rounded-full px-4 py-2 ${PUBLIC_NAV_TEXT} transition-all duration-200 hover:-translate-y-px ${textCls}`}
        >
          로그인
        </button>
        <button
          type="button"
          onClick={onRegisterClick}
          className={`rounded-full px-5 py-2 ${PUBLIC_NAV_TEXT} transition-all duration-200 hover:-translate-y-px ${cta}`}
        >
          회원가입
        </button>
      </div>
    );
  }

  // 표시 라벨: account_type 한국어 라벨 ("관리자" / "연기자" / "에이전시")
  // (role_display_name '최고관리자' 같은 세분은 노출하지 않음)
  const displayLabel =
    FALLBACK_TYPE_LABEL[account.account_type] ?? account.account_type;

  // 아바타에 넣을 이니셜 — 한글은 첫 글자, 영문은 첫 두 글자
  const initial = /^[A-Za-z]/.test(account.name)
    ? account.name.slice(0, 2).toUpperCase()
    : account.name.slice(0, 1);

  // 이름 한 줄로 늘어놓는 대신 아바타 + 이름/역할 2행으로 묶어
  // 헤더 우측에 하나의 덩어리로 보이게 한다.
  const triggerCls =
    variant === "dark"
      ? "ring-white/15 bg-white/[0.06] hover:bg-white/[0.12] hover:ring-white/30"
      : "ring-zinc-200 bg-white hover:bg-zinc-50 hover:ring-zinc-300";
  const nameCls = variant === "dark" ? "text-white" : "text-zinc-900";
  const muted = variant === "dark" ? "text-white/50" : "text-zinc-500";
  const chevronCls = variant === "dark" ? "text-white/50" : "text-zinc-400";

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpenMenu((v) => !v)}
        aria-expanded={openMenu}
        className={`group flex items-center gap-2.5 rounded-full py-1.5 pl-1.5 pr-3 ring-1 transition-all duration-200 ${triggerCls}`}
      >
        <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-gradient-to-br from-sky-400 to-violet-500 text-[11px] font-bold text-white ring-1 ring-white/25 shadow-sm">
          {initial}
        </span>
        <span className="flex flex-col items-start leading-tight">
          <span className={`text-[15px] lg:text-[17px] font-semibold ${nameCls}`}>
            {account.name}
          </span>
          <span className={`text-xs ${muted}`}>{displayLabel}</span>
        </span>
        <ChevronDown
          className={`w-4 h-4 shrink-0 transition-transform duration-200 ${chevronCls} ${
            openMenu ? "rotate-180" : ""
          }`}
        />
      </button>

      <AnimatePresence>
        {openMenu && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.15 }}
            className="absolute right-0 mt-2 w-60 rounded-xl bg-white shadow-2xl border border-zinc-200 overflow-hidden"
          >
            <div className="px-4 py-3 border-b border-zinc-100">
              <div className="text-sm font-semibold text-zinc-900">{account.name}</div>
              <div className="text-xs text-zinc-500 mt-0.5">{displayLabel}</div>
              <div className="text-xs text-zinc-400 mt-1 truncate">{account.email}</div>
            </div>

            <button
              type="button"
              onClick={() => {
                setOpenMenu(false);
                router.push(getDashboardPath(account.account_type));
              }}
              className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-zinc-700 hover:bg-zinc-50 transition-colors"
            >
              <User className="w-4 h-4" />
              마이 페이지
            </button>

            <button
              type="button"
              onClick={async () => {
                setOpenMenu(false);
                await logout();
                router.push("/");
              }}
              className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-zinc-700 hover:bg-zinc-50 transition-colors border-t border-zinc-100"
            >
              <LogOut className="w-4 h-4" />
              로그아웃
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
