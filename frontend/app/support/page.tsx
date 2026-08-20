"use client";

import { HelpCircle } from "lucide-react";

import ComingSoonView from "@/components/ComingSoonView";

export default function SupportPage() {
  return (
    <ComingSoonView
      Icon={HelpCircle}
      title="고객지원"
      description="이용 중 궁금한 점이나 문제를 해결해 드립니다."
      note="문의 접수와 자주 묻는 질문을 준비하고 있습니다. 그동안은 관리자에게 직접 연락해 주세요."
    />
  );
}
