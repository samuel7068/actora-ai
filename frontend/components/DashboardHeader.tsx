"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";

import UserMenu from "@/components/UserMenu";
import { useAuth } from "@/store/auth";
import {
  PUBLIC_NAV_CLS,
  PUBLIC_NAV_LINK_ACTIVE_CLS,
  PUBLIC_NAV_LINK_CLS,
  filterMenusByPermission,
  getMenusForAccountType,
  getPublicNavMenu,
} from "@/lib/menus";

type Variant = "light" | "dark";

type Props = {
  onLoginClick?: () => void;
  variant?: Variant; // light: 흰 배경 (agency/admin 기본) / dark: 메인 홈과 동일한 투명 + 흰 텍스트
  /**
   * role   : 계정 타입별 대시보드 메뉴 (기본) — 대시보드 화면용
   * public : 랜딩과 동일한 공용 메뉴 — 공용 화면(아티스트 탐색 등)에서
   *          상단 메뉴가 바뀌지 않도록 유지한다
   */
  menu?: "role" | "public";
};

export default function DashboardHeader({
  onLoginClick,
  variant = "light",
  menu = "role",
}: Props) {
  const account = useAuth((s) => s.account);
  const pathname = usePathname();
  const menus =
    menu === "public"
      ? getPublicNavMenu(account)
      : account
        ? filterMenusByPermission(
            getMenusForAccountType(account.account_type),
            account.permission,
          )
        : [];

  const headerCls =
    variant === "dark"
      ? "w-full bg-transparent px-4 sm:px-6 py-3 flex items-center justify-between absolute top-0 left-0 right-0 z-30"
      : "w-full bg-white border-b border-zinc-200 px-4 sm:px-6 py-3 flex items-center justify-between sticky top-0 z-30";

  // 메뉴 스타일은 lib/menus.ts 상수를 공유한다 (랜딩과 어긋나지 않도록)
  const roleLinkCls =
    variant === "dark"
      ? "px-3 py-2 text-sm font-medium text-white hover:text-zinc-200 hover:bg-white/10 rounded-lg transition-colors flex items-center gap-1.5 drop-shadow"
      : "px-3 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100 rounded-lg transition-colors flex items-center gap-1.5";

  // 지금 보고 있는 메뉴 하나만 고른다.
  // 경로가 겹치는 메뉴(/explore 와 /explore/ai)가 있어서, 접두사로만 판정하면
  // 하위 페이지에서 상위 메뉴까지 같이 켜진다 → href 가 가장 긴 것만 활성으로 본다.
  const activeHref = menus.reduce<string | null>((best, m) => {
    const hit =
      pathname === m.href ||
      (m.href !== "/" && pathname.startsWith(`${m.href}/`));
    if (!hit) return best;
    return best && best.length >= m.href.length ? best : m.href;
  }, null);

  const navCls =
    menu === "public"
      ? `${PUBLIC_NAV_CLS} mx-6`
      : "hidden md:flex flex-1 items-center justify-center gap-1 mx-6";

  return (
    <header className={headerCls}>
      <Link href="/" className="flex-shrink-0">
        <Image
          src="/images/Actora_logo.png"
          alt="Actora"
          width={845}
          height={264}
          priority
          className={
            // public 모드는 랜딩 헤더와 같은 크기 — 로고 높이가 다르면
            // 헤더 높이가 달라져 메뉴의 수직 위치까지 어긋난다
            menu === "public"
              ? "h-16 w-auto drop-shadow-lg"
              : variant === "dark"
                ? "h-12 w-auto drop-shadow-lg"
                : "h-10 w-auto"
          }
        />
      </Link>

      <nav className={navCls}>
        {menus.map((m) => {
          const active = m.href === activeHref;
          const cls =
            menu === "public"
              ? active
                ? PUBLIC_NAV_LINK_ACTIVE_CLS
                : PUBLIC_NAV_LINK_CLS
              : roleLinkCls;
          return (
            <Link key={m.key} href={m.href} className={cls}>
              {/* 공용 메뉴는 랜딩과 같은 모양(텍스트만)을 유지한다 */}
              {menu === "role" && <m.Icon className="w-4 h-4" />}
              {m.label}
            </Link>
          );
        })}
      </nav>

      <div className="flex-shrink-0">
        <UserMenu
          onLoginClick={onLoginClick ?? (() => {})}
          variant={variant}
        />
      </div>
    </header>
  );
}
