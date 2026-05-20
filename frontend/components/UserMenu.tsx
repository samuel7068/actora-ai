"use client";

import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, LayoutDashboard, LogOut, User } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { getDashboardPath } from "@/lib/menus";
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
    const textCls =
      variant === "dark"
        ? "text-white hover:text-zinc-300 drop-shadow"
        : "text-zinc-700 hover:text-zinc-900";
    const cta =
      variant === "dark"
        ? "bg-white text-black hover:bg-zinc-200"
        : "bg-zinc-900 text-white hover:bg-zinc-800";
    return (
      <div className="flex items-center gap-2 sm:gap-3">
        <button
          type="button"
          onClick={onLoginClick}
          className={`text-sm sm:text-base font-medium transition-colors px-3 py-2 ${textCls}`}
        >
          로그인
        </button>
        <button
          type="button"
          onClick={onRegisterClick}
          className={`px-4 py-2 text-sm sm:text-base font-semibold rounded-full transition-colors ${cta}`}
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

  const triggerCls =
    variant === "dark"
      ? "text-white hover:bg-white/10 drop-shadow"
      : "text-zinc-700 hover:bg-zinc-100";
  const muted = variant === "dark" ? "text-zinc-300" : "text-zinc-500";

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpenMenu((v) => !v)}
        className={`flex items-center gap-2 px-3 py-2 rounded-full text-sm sm:text-base font-medium transition-colors ${triggerCls}`}
      >
        <span>
          {account.name} <span className={muted}>({displayLabel})</span>
        </span>
        <ChevronDown className="w-4 h-4 opacity-80" />
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
              <LayoutDashboard className="w-4 h-4" />
              대시보드
            </button>

            <button
              type="button"
              className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-zinc-700 hover:bg-zinc-50 transition-colors"
            >
              <User className="w-4 h-4" />
              마이페이지
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
