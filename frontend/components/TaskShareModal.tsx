"use client";

import { AnimatePresence, motion } from "framer-motion";
import { ShieldAlert, X } from "lucide-react";
import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkBreaks from "remark-breaks";

import { api } from "@/lib/api";

type Props = {
  open: boolean;
  onClose: () => void;
};

export default function TaskShareModal({ open, onClose }: Props) {
  const [content, setContent] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 열릴 때 마다 fetch
  useEffect(() => {
    if (!open) return;
    let alive = true;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await api.get("/admin/task-share");
        if (!alive) return;
        setContent(res.data.content);
      } catch (e) {
        if (!alive) return;
        const detail =
          (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "";
        setError(detail === "ADMIN_ONLY" ? "관리자만 접근 가능" : "불러오기 실패");
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, [open]);

  // ESC 닫기
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          key="backdrop"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 backdrop-blur-sm px-4 py-8"
          onClick={onClose}
        >
          <motion.div
            initial={{ opacity: 0, y: 16, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.98 }}
            transition={{ duration: 0.25, ease: "easeOut" as const }}
            className="relative w-full max-w-5xl max-h-[92vh] flex flex-col rounded-2xl bg-white shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            {/* 헤더 */}
            <div className="flex items-start justify-between gap-4 px-7 pt-6 pb-4 border-b border-zinc-200">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <ShieldAlert className="w-5 h-5 text-amber-600" />
                  <h2 className="text-xl font-bold text-zinc-900">
                    개발 진행 공유 노트
                  </h2>
                </div>
                <p className="mt-1 text-xs text-amber-700 font-medium">
                  ⚠️ 이 정보는 관리자만 볼 수 있습니다.
                </p>
              </div>
              <button
                type="button"
                onClick={onClose}
                aria-label="닫기"
                className="flex-shrink-0 text-zinc-400 hover:text-zinc-700 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* 본문 (스크롤) */}
            <div className="flex-1 overflow-y-auto px-7 py-5">
              {loading && (
                <div className="text-center text-zinc-500 py-12">불러오는 중...</div>
              )}
              {error && (
                <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
                  {error}
                </div>
              )}
              {!loading && !error && (
                <article className="prose prose-zinc max-w-none">
                  <ReactMarkdown
                    remarkPlugins={[remarkBreaks]}
                    components={{
                      h1: (props) => (
                        <h1 className="text-2xl font-bold text-zinc-900 mt-0 mb-3" {...props} />
                      ),
                      h2: (props) => (
                        <h2 className="text-lg font-bold text-zinc-900 mt-6 mb-2 pb-1 border-b border-zinc-200" {...props} />
                      ),
                      h3: (props) => (
                        <h3 className="text-base font-semibold text-zinc-800 mt-4 mb-1.5" {...props} />
                      ),
                      p: (props) => (
                        <p className="text-sm text-zinc-700 leading-relaxed my-2" {...props} />
                      ),
                      ul: (props) => (
                        <ul className="list-disc list-inside text-sm text-zinc-700 space-y-1 my-2" {...props} />
                      ),
                      ol: (props) => (
                        <ol className="list-decimal list-inside text-sm text-zinc-700 space-y-1 my-2" {...props} />
                      ),
                      li: (props) => <li className="leading-relaxed" {...props} />,
                      code: (props) => (
                        <code className="bg-zinc-100 text-zinc-900 px-1.5 py-0.5 rounded text-xs font-mono" {...props} />
                      ),
                      blockquote: (props) => (
                        <blockquote className="border-l-4 border-amber-300 bg-amber-50 pl-3 py-2 my-3 text-sm text-zinc-700" {...props} />
                      ),
                      a: (props) => (
                        <a className="text-blue-600 hover:underline" target="_blank" rel="noopener noreferrer" {...props} />
                      ),
                      table: (props) => (
                        <div className="overflow-x-auto my-3">
                          <table className="text-sm border-collapse" {...props} />
                        </div>
                      ),
                      th: (props) => (
                        <th className="border border-zinc-300 px-2 py-1 bg-zinc-100 text-left" {...props} />
                      ),
                      td: (props) => (
                        <td className="border border-zinc-300 px-2 py-1" {...props} />
                      ),
                      hr: () => <hr className="my-5 border-zinc-200" />,
                    }}
                  >
                    {content}
                  </ReactMarkdown>
                </article>
              )}
            </div>

            {/* 푸터 */}
            <div className="px-7 py-4 border-t border-zinc-200 flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={onClose}
                className="rounded-lg bg-zinc-900 px-5 py-2 text-sm font-semibold text-white hover:bg-zinc-800 transition-colors"
              >
                확인
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
