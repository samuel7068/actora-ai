"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";

type Props = {
  items: string[];
  /** 한 번에 보여줄 행 수 */
  visible?: number;
  /** 한 슬라이드 간격(ms) */
  intervalMs?: number;
  /** 행마다 stagger 지연(ms) */
  staggerMs?: number;
  className?: string;
  /** 각 행(li)에 적용할 클래스 — 불릿·색상 등 항목 단위 스타일용 */
  itemClassName?: string;
};

/**
 * 세로 롤링 리스트.
 * - items 중 'visible' 개를 화면에 노출
 * - intervalMs 마다 인덱스가 1씩 증가 (modulo) → 첫 항목이 위로 빠지고 다음 항목이 아래에 들어옴
 * - items.length <= visible 이면 정적 표시
 */
export default function RollingList({
  items,
  visible = 3,
  intervalMs = 3000,
  staggerMs = 80,
  className = "",
  itemClassName = "truncate drop-shadow",
}: Props) {
  const [start, setStart] = useState(0);

  useEffect(() => {
    if (items.length <= visible) return;
    const t = setInterval(() => {
      setStart((s) => (s + 1) % items.length);
    }, intervalMs);
    return () => clearInterval(t);
  }, [items.length, visible, intervalMs]);

  const window =
    items.length <= visible
      ? items
      : Array.from({ length: visible }, (_, i) => items[(start + i) % items.length]);

  return (
    <ul className={`relative ${className}`}>
      <AnimatePresence mode="popLayout" initial={false}>
        {window.map((item, idx) => (
          <motion.li
            key={`${start}-${idx}-${item}`}
            layout
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={{
              duration: 0.45,
              ease: "easeOut" as const,
              delay: idx * (staggerMs / 1000),
            }}
            className={itemClassName}
          >
            {item}
          </motion.li>
        ))}
      </AnimatePresence>
    </ul>
  );
}
