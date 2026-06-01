"use client";

import Image from "next/image";
import { useState } from "react";
import { FlaskConical } from "lucide-react";

import DashboardHeader from "@/components/DashboardHeader";
import { useDashboardGuard } from "@/components/DashboardGuard";
import VideoAnalysisModal from "@/components/VideoAnalysisModal";
import { useAuth } from "@/store/auth";

export default function TalentPortfolioPage() {
  const ready = useDashboardGuard("TALENT");
  const account = useAuth((s) => s.account);
  const [analyzeOpen, setAnalyzeOpen] = useState(false);

  if (!ready || !account) return null;

  return (
    <div className="relative min-h-screen w-full overflow-hidden">
      <Image
        src="/images/Backgroud.jpg"
        alt=""
        fill
        priority
        sizes="100vw"
        className="object-cover -z-10"
      />
      <div className="absolute inset-0 bg-black/55 -z-10" />

      <DashboardHeader variant="dark" />

      <main className="relative max-w-6xl mx-auto px-4 sm:px-6 pt-28 pb-12">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-white drop-shadow-lg">
              포트폴리오
            </h1>
            <p className="mt-1 text-zinc-200 drop-shadow">
              영상을 올리면 AI 가 분석해 매칭에 사용합니다.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setAnalyzeOpen(true)}
            className="inline-flex items-center gap-2 rounded-full bg-amber-100 text-zinc-900 px-5 py-2.5 text-sm font-semibold hover:bg-amber-200 transition-colors shadow"
          >
            <FlaskConical className="w-4 h-4" />
            영상 분석 디버그
          </button>
        </div>

        <div className="rounded-xl border border-white/15 bg-white/5 backdrop-blur-md p-10 text-center text-white/80 drop-shadow">
          포트폴리오 미디어 목록은 추후 추가됩니다.
          <br />
          현재는 우상단 <b className="text-amber-100">영상 분석 디버그</b> 버튼으로
          파이프라인(1~4단계)을 검증할 수 있습니다.
        </div>
      </main>

      <VideoAnalysisModal
        open={analyzeOpen}
        onClose={() => setAnalyzeOpen(false)}
      />
    </div>
  );
}
