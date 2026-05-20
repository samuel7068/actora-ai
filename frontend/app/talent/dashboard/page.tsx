"use client";

import Link from "next/link";

import DashboardHeader from "@/components/DashboardHeader";
import { useDashboardGuard } from "@/components/DashboardGuard";
import { TALENT_MENU, filterMenusByPermission } from "@/lib/menus";
import { useAuth } from "@/store/auth";

export default function TalentDashboard() {
  const ready = useDashboardGuard("TALENT");
  const account = useAuth((s) => s.account);

  if (!ready || !account) return null;

  const menus = filterMenusByPermission(TALENT_MENU, account.permission);

  return (
    <div className="min-h-screen bg-zinc-50">
      <DashboardHeader />
      <main className="max-w-6xl mx-auto px-4 sm:px-6 py-10">
        <h1 className="text-2xl sm:text-3xl font-bold text-zinc-900">
          안녕하세요, {account.name}님
        </h1>
        <p className="mt-1 text-zinc-500">
          {account.role_display_name} · 연기자 대시보드 (개발 중)
        </p>

        <div className="mt-8 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {menus.map((m) => (
            <Link
              key={m.key}
              href={m.href}
              className="rounded-xl bg-white border border-zinc-200 p-5 hover:shadow-md hover:border-zinc-300 transition-all"
            >
              <m.Icon className="w-7 h-7 text-zinc-700" strokeWidth={1.5} />
              <div className="mt-3 font-semibold text-zinc-900">{m.label}</div>
              <div className="mt-1 text-xs text-zinc-400">{m.href}</div>
            </Link>
          ))}
        </div>
      </main>
    </div>
  );
}
