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
  description?: string; // 대시보드 카드 부제 (헤더 nav 에는 표시 안 함)
};

// ──────────────────────────────────────────────────────────────────
// 비로그인 공용 (Landing 헤더) — role 없음, 코드 기반 고정
// ──────────────────────────────────────────────────────────────────
export const PUBLIC_MENU: MenuItem[] = [
  // AI 추천과 캐스팅 공고는 결국 같은 흐름이라 하나로 합쳤다 (구 ai_recommend 제거)
  { key: "casting_search", label: "AI 캐스팅", href: "/castings", Icon: Sparkles },
  { key: "talent_explore", label: "AI 아티스트", href: "/explore", Icon: Search },
  { key: "pricing", label: "멤버쉽", href: "/pricing", Icon: CreditCard },
  { key: "support", label: "고객지원", href: "/support", Icon: HelpCircle },
];

// ──────────────────────────────────────────────────────────────────
// 공용 헤더의 메뉴 스타일.
//   랜딩(app/page.tsx)과 DashboardHeader(menu="public") 가 같은 문자열을 써야
//   화면을 옮길 때 메뉴 크기·간격이 튀지 않는다. 여기서만 고친다.
// ──────────────────────────────────────────────────────────────────
// 메뉴 전체를 하나의 알약(pill) 안에 담는다.
// 배경 이미지 위에 글자만 떠 있으면 밝은 영역에서 읽기 어렵고 메뉴로 인식되지 않는다.
export const PUBLIC_NAV_CLS =
  "hidden md:inline-flex mx-auto items-center gap-1.5 lg:gap-3 rounded-full " +
  "bg-white/[0.07] ring-1 ring-white/10 backdrop-blur-xl px-3 py-2 " +
  "shadow-[0_8px_32px_-8px_rgba(0,0,0,0.6)]";

// 글자 크기(PUBLIC_NAV_TEXT)는 로그인·회원가입 버튼과 **같은 값**을 쓴다.
// 헤더 안에서 크기가 섞이면 정돈되지 않아 보인다.
// 좁은 화면에서는 15px, 큰 화면에서 17px — 고정값으로 키우면
// 항목 6개가 로고·사용자 영역과 부딪힌다.
export const PUBLIC_NAV_TEXT = "text-[15px] lg:text-[17px] font-medium";

// hover 는 "유리가 살짝 볼록해지는" 느낌으로.
//   · 배경: 위가 밝고 아래로 옅어지는 그라디언트 (평평한 반투명보다 입체감이 있다)
//   · 안쪽 링 + 위쪽 1px 하이라이트로 눌린 자리를 분명히 한다
//   · 글자는 완전한 흰색으로 올려 대비를 준다
export const PUBLIC_NAV_LINK_CLS =
  `block rounded-full px-5 lg:px-7 py-2 ${PUBLIC_NAV_TEXT} ` +
  "text-white/65 transition-all duration-200 whitespace-nowrap " +
  "hover:text-white hover:bg-gradient-to-b hover:from-white/[0.18] hover:to-white/[0.05] " +
  "hover:ring-1 hover:ring-inset hover:ring-white/20 " +
  "hover:shadow-[inset_0_1px_0_0_rgba(255,255,255,0.22)]";

/** 현재 경로에 해당하는 메뉴 — 알약 안에서 한 칸만 밝게 채운다 */
export const PUBLIC_NAV_LINK_ACTIVE_CLS =
  `block rounded-full px-5 lg:px-7 py-2 ${PUBLIC_NAV_TEXT} ` +
  "text-zinc-900 whitespace-nowrap transition-all duration-200 " +
  // 순백 단색보다 아주 옅은 그라디언트가 덜 납작해 보인다
  "bg-gradient-to-b from-white to-zinc-100 " +
  "shadow-[0_2px_8px_-2px_rgba(0,0,0,0.35)]";

// ──────────────────────────────────────────────────────────────────
// 공용 화면(랜딩 · 인재 탐색)의 헤더 메뉴
//   로그인했으면 맨 뒤에 '마이 페이지' 를 붙인다.
//   랜딩과 인재 탐색이 같은 메뉴를 쓰도록 한 곳에서 만든다 —
//   화면을 옮길 때 상단 메뉴가 바뀌면 사용자가 길을 잃는다.
// ──────────────────────────────────────────────────────────────────
export function getPublicNavMenu(
  account: AccountInfo | null | undefined,
): MenuItem[] {
  if (!account) return PUBLIC_MENU;
  return [
    ...PUBLIC_MENU,
    {
      key: "mypage",
      label: "마이 페이지",
      href: getDashboardPath(account.account_type),
      Icon: User,
    },
  ];
}

// ──────────────────────────────────────────────────────────────────
// Talent dashboard
//   role_master(TALENT/DEFAULT).permission_json.menu 와 매칭
// ──────────────────────────────────────────────────────────────────
export const TALENT_MENU: MenuItem[] = [
  {
    key: "profile",
    label: "내 프로필",
    href: "/talent/profile",
    Icon: User,
    description: "프로필을 완성하여 더 많은 매칭 기회를 잡으세요.",
  },
  {
    key: "portfolio",
    label: "포트폴리오",
    href: "/talent/portfolio",
    Icon: Folder,
    description: "좋은 영상은 좋은 캐스팅으로 이어집니다.",
  },
  {
    key: "applications",
    label: "지원한 캐스팅",
    href: "/talent/applications",
    Icon: Send,
    description: "지원한 캐스팅의 진행 상황을 한눈에 확인하세요.",
  },
  {
    key: "recommended",
    label: "추천 캐스팅",
    href: "/talent/recommended",
    Icon: Sparkles,
    description: "AI가 당신에게 어울리는 캐스팅을 찾아드립니다.",
  },
  {
    key: "ai_report",
    label: "AI 분석 리포트",
    href: "/talent/ai-report",
    Icon: BarChart3,
    description: "AI가 분석한 당신의 강점과 매력 포인트를 확인하세요.",
  },
  {
    key: "settings",
    label: "계정 설정",
    href: "/talent/settings",
    Icon: Settings,
    description: "계정·알림·공개 범위를 관리하세요.",
  },
];

// ──────────────────────────────────────────────────────────────────
// Agency dashboard
//   role_master(AGENCY/DEFAULT).permission_json.menu 와 매칭
// ──────────────────────────────────────────────────────────────────
export const AGENCY_MENU: MenuItem[] = [
  { key: "ai_recommend", label: "AI 캐스팅", href: "/agency/ai-recommend", Icon: Sparkles },
  { key: "talent_explore", label: "AI 아티스트", href: "/agency/explore", Icon: Search },
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
  // 인재 등록 / 벡터 DB 조회는 대시보드 카드로 진입 (헤더 nav 에는 미노출)
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
