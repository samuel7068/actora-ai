"use client";

import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, ChevronUp, X } from "lucide-react";
import { useEffect, useState } from "react";

type Props = {
  open: boolean;
  onClose: () => void;
  src: string | null;
  title?: string | null;
  /** AI 분석 요약. 길어서 접어 두고 펼쳐 보게 한다 (title 에 넣으면 1줄로 잘린다) */
  summary?: string | null;
};

/** 분석 요약 — 기본 3줄, 펼치면 스크롤. src 를 key 로 주어 영상이 바뀌면 접힌 상태로 초기화된다. */
function SummaryBlock({ text }: { text: string }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="mt-2">
      <p
        className={
          expanded
            ? "text-sm leading-relaxed text-white/80 max-h-48 overflow-y-auto pr-1 select-text"
            : "text-sm leading-relaxed text-white/80 line-clamp-3 select-text"
        }
      >
        {text}
      </p>
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="mt-1.5 inline-flex items-center gap-1 text-xs text-white/50 hover:text-white/80 transition-colors"
      >
        {expanded ? (
          <>
            <ChevronUp className="w-3.5 h-3.5" /> 접기
          </>
        ) : (
          <>
            <ChevronDown className="w-3.5 h-3.5" /> 분석 내용 전체 보기
          </>
        )}
      </button>
    </div>
  );
}

export default function VideoPlayerModal({
  open,
  onClose,
  src,
  title,
  summary,
}: Props) {
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
      {open && src && (
        <motion.div
          className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center px-4 py-6"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
        >
          <motion.div
            initial={{ opacity: 0, y: 24, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 24, scale: 0.96 }}
            transition={{ duration: 0.22, ease: "easeOut" }}
            onClick={(e) => e.stopPropagation()}
            className="relative w-full max-w-4xl rounded-2xl bg-black shadow-2xl overflow-hidden"
          >
            <button
              type="button"
              onClick={onClose}
              aria-label="닫기"
              className="absolute top-3 right-3 z-10 rounded-full p-1.5 bg-black/50 text-white hover:bg-black/70 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
            <video
              src={src}
              controls
              autoPlay
              className="w-full max-h-[70vh] bg-black"
            />
            {(title || summary) && (
              <div className="px-4 py-3 bg-zinc-900">
                {title && (
                  <div className="text-sm font-semibold text-white truncate">
                    {title}
                  </div>
                )}
                {summary && <SummaryBlock key={src} text={summary} />}
              </div>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
