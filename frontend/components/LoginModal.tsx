"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { useRouter } from "next/navigation";

import { getDashboardPath } from "@/lib/menus";
import { useAuth } from "@/store/auth";

type Props = {
  open: boolean;
  onClose: () => void;
  onSwitchToRegister?: () => void;
};

export default function LoginModal({ open, onClose, onSwitchToRegister }: Props) {
  const { login, loading, error } = useAuth();
  const router = useRouter();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  useEffect(() => {
    if (!open) {
      setIdentifier("");
      setPassword("");
    }
  }, [open]);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (loading) return;
    try {
      await login(identifier.trim(), password);
      onClose();
      // 로그인 성공 후 자동 이동:
      //   TALENT/AGENCY → 자기 dashboard
      //   ADMIN         → 메인 유지 (관리자 대시보드는 추후 구현)
      const acc = useAuth.getState().account;
      if (acc && acc.account_type !== "ADMIN") {
        router.push(getDashboardPath(acc.account_type));
      }
    } catch {
      /* error 는 store 에서 표시 */
    }
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          key="backdrop"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm px-4"
          onClick={onClose}
        >
          <motion.div
            initial={{ opacity: 0, y: 16, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.98 }}
            transition={{ duration: 0.25, ease: "easeOut" as const }}
            className="relative w-full max-w-sm rounded-2xl bg-white p-7 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              type="button"
              onClick={onClose}
              aria-label="닫기"
              className="absolute right-4 top-4 text-zinc-400 hover:text-zinc-700 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>

            <h2 className="text-2xl font-bold text-zinc-900 tracking-tight">로그인</h2>
            <p className="mt-1 text-sm text-zinc-500">이메일 또는 아이디로 로그인하세요</p>

            <form onSubmit={onSubmit} className="mt-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-zinc-700 mb-1.5">
                  이메일 또는 아이디
                </label>
                <input
                  type="text"
                  value={identifier}
                  onChange={(e) => setIdentifier(e.target.value)}
                  autoFocus
                  required
                  autoComplete="off"
                  className="w-full rounded-lg border border-zinc-300 px-3.5 py-2.5 text-zinc-900 placeholder:text-zinc-400 focus:border-zinc-900 focus:outline-none transition-colors"
                  placeholder="이메일 또는 아이디"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-zinc-700 mb-1.5">비밀번호</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  autoComplete="new-password"
                  className="w-full rounded-lg border border-zinc-300 px-3.5 py-2.5 text-zinc-900 placeholder:text-zinc-400 focus:border-zinc-900 focus:outline-none transition-colors"
                  placeholder="비밀번호 입력"
                />
              </div>

              {error && (
                <div className="rounded-lg bg-red-50 border border-red-200 px-3.5 py-2.5 text-sm text-red-700">
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={loading || !identifier.trim() || !password}
                className="w-full rounded-lg bg-zinc-900 px-4 py-3 text-sm font-semibold text-white hover:bg-zinc-800 disabled:bg-zinc-400 disabled:cursor-not-allowed transition-colors"
              >
                {loading ? "로그인 중..." : "로그인"}
              </button>
            </form>

            <p className="mt-5 text-center text-sm text-zinc-500">
              계정이 없으신가요?{" "}
              <button
                type="button"
                onClick={() => {
                  onClose();
                  onSwitchToRegister?.();
                }}
                className="font-semibold text-zinc-900 hover:underline"
              >
                회원가입
              </button>
            </p>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
