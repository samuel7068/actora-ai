"use client";

import Image from "next/image";
import Link from "next/link";
import { Database, Users } from "lucide-react";

import DashboardHeader from "@/components/DashboardHeader";
import { useDashboardGuard } from "@/components/DashboardGuard";
import { useAuth } from "@/store/auth";

const CARD_CLS =
  "rounded-xl border border-white/15 bg-white/10 backdrop-blur-md p-8 min-h-[180px] grid grid-cols-[minmax(8rem,auto)_1fr] gap-8 items-center hover:bg-white/15 hover:border-white/30 hover:shadow-2xl transition-colors text-left";

export default function AdminDashboard() {
  const ready = useDashboardGuard("ADMIN");
  const account = useAuth((s) => s.account);

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
      <div className="absolute inset-0 bg-black/50 -z-10" />

      <DashboardHeader variant="dark" />

      <main className="relative max-w-6xl mx-auto px-4 sm:px-6 pt-28 pb-12">
        <h1 className="text-2xl sm:text-3xl font-bold text-white drop-shadow-lg">
          관리자 대시보드
        </h1>
        <p className="mt-1 text-white/80 drop-shadow">
          {account.name} · {account.role_display_name}
        </p>

        <div className="mt-10 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-8 sm:gap-10">
          <Link href="/admin/talents" className={CARD_CLS}>
            <div>
              <Users
                className="w-8 h-8 text-amber-100 drop-shadow"
                strokeWidth={1.5}
              />
              <div className="mt-3 font-semibold text-base text-amber-100 drop-shadow">
                인재 관리
              </div>
            </div>
            <div className="text-sm leading-relaxed text-white/80 drop-shadow">
              등록된 전체 인재를 목록으로 조회하고 프로필을 확인합니다.
            </div>
          </Link>

          <Link href="/admin/rag" className={CARD_CLS}>
            <div>
              <Database
                className="w-8 h-8 text-amber-100 drop-shadow"
                strokeWidth={1.5}
              />
              <div className="mt-3 font-semibold text-base text-amber-100 drop-shadow">
                벡터 DB 조회
              </div>
            </div>
            <div className="text-sm leading-relaxed text-white/80 drop-shadow">
              Qdrant 에 적재된 영상 scene 데이터를 talent_media_id 별로 조회합니다.
            </div>
          </Link>
        </div>
      </main>
    </div>
  );
}
