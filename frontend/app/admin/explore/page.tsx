"use client";

import { useDashboardGuard } from "@/components/DashboardGuard";
import TalentSearchView from "@/components/TalentSearchView";

export default function AdminExplorePage() {
  const ready = useDashboardGuard("ADMIN");
  if (!ready) return null;
  return <TalentSearchView />;
}
