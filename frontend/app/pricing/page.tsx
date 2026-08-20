"use client";

import { CreditCard } from "lucide-react";

import ComingSoonView from "@/components/ComingSoonView";

export default function PricingPage() {
  return (
    <ComingSoonView
      Icon={CreditCard}
      title="멤버쉽"
      description="에이전시 규모와 이용량에 맞는 멤버쉽을 고를 수 있습니다."
      note="멤버쉽 등급과 혜택을 정리하고 있습니다. 확정되면 이 화면에서 안내드립니다."
    />
  );
}
