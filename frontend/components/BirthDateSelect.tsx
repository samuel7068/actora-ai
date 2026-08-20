"use client";

import { useState } from "react";

/**
 * 생년월일 입력 — 년 / 월 / 일 각각 선택.
 *
 * `<input type="date">` 는 연도를 바꾸려면 달력을 여러 번 넘기거나 좁은 칸에
 * 숫자를 눌러 넣어야 해서, 수십 년 전 생년월일을 고르기가 번거롭다.
 * 값은 기존과 동일하게 "YYYY-MM-DD" 문자열로 주고받는다.
 *
 * 셋 중 하나라도 비어 있으면 빈 문자열("")을 올려보낸다 — 불완전한 날짜가
 * 저장되지 않도록.
 */
type Props = {
  value: string; // "YYYY-MM-DD" 또는 ""
  onChange: (value: string) => void;
  /** 각 select 에 적용할 클래스 (화면마다 테마가 달라 밖에서 주입) */
  className?: string;
  /** 선택 가능한 가장 이른 연도 (기본: 올해 - 90) */
  minYear?: number;
  /** 선택 가능한 가장 늦은 연도 (기본: 올해) */
  maxYear?: number;
  disabled?: boolean;
};

const pad2 = (n: number | string) => String(n).padStart(2, "0");

/** 해당 연·월의 마지막 날 (윤년 반영). 연도가 없으면 31 로 둔다. */
function lastDayOf(year: string, month: string): number {
  if (!year || !month) return 31;
  return new Date(Number(year), Number(month), 0).getDate();
}

function parse(value: string): { y: string; m: string; d: string } | null {
  const m = /^(\d{4})-(\d{1,2})-(\d{1,2})$/.exec(value ?? "");
  if (!m) return null;
  return { y: m[1], m: pad2(m[2]), d: pad2(m[3]) };
}

export default function BirthDateSelect({
  value,
  onChange,
  className = "",
  minYear,
  maxYear,
  disabled,
}: Props) {
  // 셋 중 일부만 고른 동안에는 완성된 날짜가 없어 부모 value 가 "" 가 된다.
  // 그 사이의 선택을 담아두는 버퍼가 draft 다.
  // 표시값은 "부모 value 가 완전한 날짜면 그것, 아니면 draft" — 상태를 effect 로
  // 동기화하지 않고 렌더 중 계산해 두 값이 어긋날 여지를 없앤다.
  const [draft, setDraft] = useState({ y: "", m: "", d: "" });
  const parsed = parse(value);
  const year = parsed?.y ?? draft.y;
  const month = parsed?.m ?? draft.m;
  const day = parsed?.d ?? draft.d;

  const thisYear = new Date().getFullYear();
  const last = maxYear ?? thisYear;
  const first = minYear ?? thisYear - 90;
  // 최근 연도가 위 — 대부분의 등록자가 최근 연도대에 몰려 있다
  const years = Array.from({ length: last - first + 1 }, (_, i) => last - i);
  const maxDay = lastDayOf(year, month);
  const days = Array.from({ length: maxDay }, (_, i) => i + 1);

  const apply = (y: string, m: string, d: string) => {
    setDraft({ y, m, d });
    onChange(y && m && d ? `${y}-${m}-${d}` : "");
  };

  // 2/29 처럼 그 해·그 달에 없는 날짜가 남지 않도록 보정
  const onYear = (y: string) =>
    apply(y, month, day && Number(day) > lastDayOf(y, month) ? "" : day);
  const onMonth = (m: string) =>
    apply(year, m, day && Number(day) > lastDayOf(year, m) ? "" : day);
  const onDay = (d: string) => apply(year, month, d);

  return (
    <div className="flex gap-2">
      <select
        value={year}
        onChange={(e) => onYear(e.target.value)}
        disabled={disabled}
        aria-label="출생 연도"
        className={`${className} flex-[1.3]`}
      >
        <option value="">년</option>
        {years.map((y) => (
          <option key={y} value={String(y)}>
            {y}년
          </option>
        ))}
      </select>
      <select
        value={month}
        onChange={(e) => onMonth(e.target.value)}
        disabled={disabled}
        aria-label="출생 월"
        className={`${className} flex-1`}
      >
        <option value="">월</option>
        {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
          <option key={m} value={pad2(m)}>
            {m}월
          </option>
        ))}
      </select>
      <select
        value={day}
        onChange={(e) => onDay(e.target.value)}
        disabled={disabled}
        aria-label="출생 일"
        className={`${className} flex-1`}
      >
        <option value="">일</option>
        {days.map((d) => (
          <option key={d} value={pad2(d)}>
            {d}일
          </option>
        ))}
      </select>
    </div>
  );
}
