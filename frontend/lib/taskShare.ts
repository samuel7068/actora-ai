// Task Share 노트 "오늘 하루 그만 보기" 공통 헬퍼

export const TASK_SHARE_HIDDEN_KEY = "actora.taskshare.hiddenDate";

/** 로컬 기준 오늘 날짜 문자열 (YYYY-M-D). */
export function todayStr(): string {
  const d = new Date();
  return `${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}`;
}

/** 오늘 "그만 보기"가 설정돼 있는지. */
export function isHiddenToday(): boolean {
  if (typeof window === "undefined") return false;
  return localStorage.getItem(TASK_SHARE_HIDDEN_KEY) === todayStr();
}
