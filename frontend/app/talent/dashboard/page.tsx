"use client";

import Image from "next/image";
import Link from "next/link";
import { useState } from "react";

import DashboardHeader from "@/components/DashboardHeader";
import { useDashboardGuard } from "@/components/DashboardGuard";
import TalentProfileModal from "@/components/TalentProfileModal";
import { TALENT_MENU, filterMenusByPermission } from "@/lib/menus";
import { useAuth } from "@/store/auth";

export default function TalentDashboard() {
  const ready = useDashboardGuard("TALENT");
  const account = useAuth((s) => s.account);
  const [profileOpen, setProfileOpen] = useState(false);

  if (!ready || !account) return null;

  const menus = filterMenusByPermission(TALENT_MENU, account.permission);

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
          안녕하세요, {account.name}님
        </h1>

        <div className="mt-10 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-8 sm:gap-10">
          {menus.map((m) => {
            const isProfile = m.key === "profile";
            const className =
              "rounded-xl border border-white/15 bg-white/10 backdrop-blur-md p-8 min-h-[180px] grid grid-cols-[minmax(8rem,auto)_1fr] gap-8 items-center hover:bg-white/15 hover:border-white/30 hover:shadow-2xl transition-colors text-left";
            const inner = (
              <>
                <div>
                  <m.Icon
                    className="w-8 h-8 text-amber-100 drop-shadow"
                    strokeWidth={1.5}
                  />
                  <div className="mt-3 font-semibold text-base text-amber-100 drop-shadow">
                    {m.label}
                  </div>
                </div>
                {m.description && (
                  <div className="text-sm leading-relaxed text-white/80 drop-shadow">
                    {m.description}
                  </div>
                )}
              </>
            );
            return isProfile ? (
              <button
                key={m.key}
                type="button"
                onClick={() => setProfileOpen(true)}
                className={className}
              >
                {inner}
              </button>
            ) : (
              <Link key={m.key} href={m.href} className={className}>
                {inner}
              </Link>
            );
          })}
        </div>
      </main>

      <TalentProfileModal
        open={profileOpen}
        onClose={() => setProfileOpen(false)}
      />
    </div>
  );
}
