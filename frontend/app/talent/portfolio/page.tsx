"use client";

import { useDashboardGuard } from "@/components/DashboardGuard";
import PortfolioView from "@/components/PortfolioView";
import { useAuth } from "@/store/auth";

export default function TalentPortfolioPage() {
  const ready = useDashboardGuard("TALENT");
  const account = useAuth((s) => s.account);
  if (!ready || !account) return null;
  return <PortfolioView />;
}
