"use client";

import { useDashboardGuard } from "@/components/DashboardGuard";
import TalentSearchView from "@/components/TalentSearchView";

export default function AgencyExplorePage() {
  const ready = useDashboardGuard("AGENCY");
  if (!ready) return null;
  return <TalentSearchView />;
}
