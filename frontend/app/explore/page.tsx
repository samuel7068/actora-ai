"use client";

import TalentSearchView from "@/components/TalentSearchView";

/**
 * 인재 탐색 (공용 경로). 화면은 누구나 볼 수 있고,
 * 검색 실행 시점에 TalentSearchView 내부에서 로그인·권한(에이전시/관리자)을 요구한다.
 */
export default function ExplorePage() {
  return <TalentSearchView />;
}
