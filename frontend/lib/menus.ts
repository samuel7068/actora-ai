import {
  BarChart3,
  Briefcase,
  Building2,
  CreditCard,
  FileText,
  Folder,
  Heart,
  HelpCircle,
  LayoutDashboard,
  Megaphone,
  Search,
  Send,
  Settings,
  Sparkles,
  User,
  Users,
  type LucideIcon,
} from "lucide-react";

import type { AccountInfo } from "@/store/auth";

export type MenuItem = {
  key: string; // role_master.permission_json.menu 의 키와 매칭
  label: string;
  href: string;
  Icon: LucideIcon;
};

// ──────────────────────────────────────────────────────────────────
// 비로그인 공용 (Landing 헤더) — role 없음, 코드 기반 고정
// ──────────────────────────────────────────────────────────────────
export const PUBLIC_MENU: MenuItem[] = [
  { key: "ai_recommend", label: "AI 추천 인재", href: "/explore/ai", Icon: Sparkles },
  { key: "casting_search", label: "캐스팅 찾기", href: "/castings", Icon: Megaphone },
  { key: "talent_explore", label: "인재 탐색", href: "/explore", Icon: Search },
  { key: "pricing", label: "요금제", href: "/pricing", Icon: CreditCard },
  { key: "support", label: "고객지원", href: "/support", Icon: HelpCircle },
];

// ──────────────────────────────────────────────────────────────────
// Talent dashboard
//   role_master(TALENT/DEFAULT).permission_json.menu 와 매칭
// ──────────────────────────────────────────────────────────────────
export const TALENT_MENU: MenuItem[] = [
  { key: "profile", label: "내 프로필", href: "/talent/profile", Icon: User },
  { key: "portfolio", label: "포트폴리오", href: "/talent/portfolio", Icon: Folder },
  { key: "applications", label: "지원한 캐스팅", href: "/talent/applications", Icon: Send },
  { key: "recommended", label: "추천 캐스팅", href: "/talent/recommended", Icon: Sparkles },
  { key: "ai_report", label: "AI 분석 리포트", href: "/talent/ai-report", Icon: BarChart3 },
  { key: "settings", label: "계정 설정", href: "/talent/settings", Icon: Settings },
];

// ──────────────────────────────────────────────────────────────────
// Agency dashboard
//   role_master(AGENCY/DEFAULT).permission_json.menu 와 매칭
// ──────────────────────────────────────────────────────────────────
export const AGENCY_MENU: MenuItem[] = [
  { key: "ai_recommend", label: "AI 추천 인재", href: "/agency/ai-recommend", Icon: Sparkles },
  { key: "talent_explore", label: "인재 탐색", href: "/agency/explore", Icon: Search },
  { key: "casting_register", label: "캐스팅 등록", href: "/agency/castings/new", Icon: FileText },
  { key: "casting_active", label: "진행 중 캐스팅", href: "/agency/castings", Icon: Briefcase },
  { key: "applicants", label: "지원자 관리", href: "/agency/applicants", Icon: Users },
  { key: "favorites", label: "관심 인재", href: "/agency/favorites", Icon: Heart },
  { key: "company_settings", label: "회사 설정", href: "/agency/settings", Icon: Building2 },
];

// ──────────────────────────────────────────────────────────────────
// Admin dashboard — 추후 세분화
//   SUPER 는 permission.menu=["*"] 로 모두 허용
// ──────────────────────────────────────────────────────────────────
export const ADMIN_MENU: MenuItem[] = [
  { key: "dashboard", label: "대시보드", href: "/admin/dashboard", Icon: LayoutDashboard },
  // 추후 추가: 계정 관리, 통계, 매칭 모니터링, 시스템 설정 등
];

// ──────────────────────────────────────────────────────────────────
// account_type → 해당 메뉴 정의 반환
// ──────────────────────────────────────────────────────────────────
export function getMenusForAccountType(
  accountType: AccountInfo["account_type"],
): MenuItem[] {
  if (accountType === "TALENT") return TALENT_MENU;
  if (accountType === "AGENCY") return AGENCY_MENU;
  if (accountType === "ADMIN") return ADMIN_MENU;
  return [];
}

// ──────────────────────────────────────────────────────────────────
// account_type 별 dashboard 진입 라우트
// ──────────────────────────────────────────────────────────────────
export function getDashboardPath(
  accountType: AccountInfo["account_type"],
): string {
  if (accountType === "TALENT") return "/talent/dashboard";
  if (accountType === "AGENCY") return "/agency/dashboard";
  if (accountType === "ADMIN") return "/admin/dashboard";
  return "/";
}

// ──────────────────────────────────────────────────────────────────
// 코드 메뉴 ∩ DB permission.menu 키 → 실제 표시 메뉴
//   permission.menu 가 ["*"] 면 모든 메뉴 허용
// ──────────────────────────────────────────────────────────────────
type Permission = { menu?: string[] };

export function filterMenusByPermission(
  menus: MenuItem[],
  permission: Permission | null | undefined,
): MenuItem[] {
  const keys = permission?.menu ?? [];
  if (keys.includes("*")) return menus;
  const allowed = new Set(keys);
  return menus.filter((m) => allowed.has(m.key));
}
