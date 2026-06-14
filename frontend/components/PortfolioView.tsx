"use client";

import Image from "next/image";

import DashboardHeader from "@/components/DashboardHeader";
import PortfolioPanel from "@/components/PortfolioPanel";

/** 포트폴리오(영상 관리) 공용 페이지. accountId 가 있으면 관리자 대행, 없으면 본인. */
export default function PortfolioView({ accountId }: { accountId?: number }) {
  const isProxy = accountId != null;

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
        <h1 className="text-2xl sm:text-3xl font-bold text-white drop-shadow-lg mb-6">
          포트폴리오{isProxy ? " 관리" : ""}
        </h1>
        <PortfolioPanel accountId={accountId} variant="dark" />
      </main>
    </div>
  );
}
