"use client";

import { Sparkles } from "lucide-react";

import ComingSoonView from "@/components/ComingSoonView";

export default function CastingsPage() {
  return (
    <ComingSoonView
      Icon={Sparkles}
      title="AI 캐스팅"
      description="프로젝트에 맞는 아티스트를 AI 가 찾아주고, 캐스팅 공고도 함께 관리합니다."
      note="AI 추천과 공고 등록·지원·심사 흐름을 준비하고 있습니다. 지금은 AI 아티스트 메뉴에서 문장으로 검색해 보실 수 있습니다."
    />
  );
}
