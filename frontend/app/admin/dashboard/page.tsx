"use client";

import DashboardHeader from "@/components/DashboardHeader";
import { useDashboardGuard } from "@/components/DashboardGuard";
import { useAuth } from "@/store/auth";

export default function AdminDashboard() {
  const ready = useDashboardGuard("ADMIN");
  const account = useAuth((s) => s.account);

  if (!ready || !account) return null;

  return (
    <div className="min-h-screen bg-zinc-50">
      <DashboardHeader />
      <main className="max-w-6xl mx-auto px-4 sm:px-6 py-10">
        <h1 className="text-2xl sm:text-3xl font-bold text-zinc-900">
          관리자 대시보드
        </h1>
        <p className="mt-1 text-zinc-500">
          {account.name} · {account.role_display_name}
        </p>

        <div className="mt-8 rounded-xl bg-white border border-zinc-200 p-8 text-center">
          <p className="text-zinc-500">관리자 메뉴는 추후 추가 예정입니다.</p>
          <p className="mt-2 text-xs text-zinc-400">
            현재 권한: <code className="bg-zinc-100 px-1.5 py-0.5 rounded">
              {JSON.stringify(account.permission)}
            </code>
          </p>
        </div>
      </main>
    </div>
  );
}
