"use client";

import { useParams } from "next/navigation";

import { useDashboardGuard } from "@/components/DashboardGuard";
import PortfolioView from "@/components/PortfolioView";

export default function AdminTalentPortfolioPage() {
  const ready = useDashboardGuard("ADMIN");
  const params = useParams<{ account_id: string }>();
  if (!ready) return null;
  return <PortfolioView accountId={Number(params.account_id)} />;
}
