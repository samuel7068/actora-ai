"use client";

import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, ChevronUp, X } from "lucide-react";
import { useEffect, useState } from "react";

type Props = {
  open: boolean;
  onClose: () => void;
  src: string | null;
  title?: string | null;
  /** 먼저 보이는 분석. 검색 결과에서는 **검색어와 맞은 장면** 설명이 들어온다
   *  (카드에서 읽은 글과 같아야 클릭 전후가 어긋나지 않는다) */
  summary?: string | null;
  /** 펼쳤을 때 보여줄 **영상 전체 분석**. 없으면 펼치기 버튼이 나오지 않는다 */
  fullSummary?: string | null;
};

/**
 * 분석 요약.
 *
 * 접힌 상태는 이 장면 설명, 펼치면 영상 전체 분석을 보여준다.
 * 전에는 펼쳐도 같은 글의 나머지 줄만 나와서, "분석 내용 전체 보기" 라는 문구와
 * 실제로 나오는 내용이 달랐다.
 * src 를 key 로 주어 영상이 바뀌면 접힌 상태로 초기화된다.
 */
function SummaryBlock({ text, full }: { text: string; full?: string | null }) {
  const [expanded, setExpanded] = useState(false);
  // 전체 분석이 이 글과 같으면 따로 보여줄 것이 없다
  const hasFull = Boolean(full && full.trim() && full.trim() !== text.trim());

  return (
    <div className="mt-2">
      {/* 접혀 있을 때는 3줄. 펼치면 전문을 스크롤로 본다
          (프로필 화면처럼 전체 분석 하나만 넘어오는 경우도 다 읽혀야 한다) */}
      <p
        className={
          expanded
            ? "text-sm leading-relaxed text-white/80 max-h-40 overflow-y-auto pr-1 select-text"
            : "text-sm leading-relaxed text-white/80 line-clamp-3 select-text"
        }
      >
        {text}
      </p>

      {/* 검색 결과에서는 위가 '맞은 장면', 여기가 '영상 전체' 다 */}
      {hasFull && expanded && (
        <div className="mt-3 rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2.5">
          <div className="text-[11px] font-semibold text-amber-100/80">
            이 영상 전체 분석
          </div>
          <p className="mt-1.5 text-sm leading-relaxed text-white/75 max-h-48 overflow-y-auto pr-1 select-text">
            {full}
          </p>
        </div>
      )}

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
            <ChevronDown className="w-3.5 h-3.5" />{" "}
            {hasFull ? "이 영상 전체 분석 보기" : "분석 내용 전체 보기"}
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
  fullSummary,
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
                {summary && (
                  <SummaryBlock key={src} text={summary} full={fullSummary} />
                )}
              </div>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
