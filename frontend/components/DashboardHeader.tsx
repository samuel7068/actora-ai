"use client";

import Image from "next/image";
import Link from "next/link";

import UserMenu from "@/components/UserMenu";
import { useAuth } from "@/store/auth";
import {
  filterMenusByPermission,
  getMenusForAccountType,
} from "@/lib/menus";

type Variant = "light" | "dark";

type Props = {
  onLoginClick?: () => void;
  variant?: Variant; // light: 흰 배경 (agency/admin 기본) / dark: 메인 홈과 동일한 투명 + 흰 텍스트
};

export default function DashboardHeader({ onLoginClick, variant = "light" }: Props) {
  const account = useAuth((s) => s.account);
  const menus = account
    ? filterMenusByPermission(
        getMenusForAccountType(account.account_type),
        account.permission,
      )
    : [];

  const headerCls =
    variant === "dark"
      ? "w-full bg-transparent px-4 sm:px-6 py-3 flex items-center justify-between absolute top-0 left-0 right-0 z-30"
      : "w-full bg-white border-b border-zinc-200 px-4 sm:px-6 py-3 flex items-center justify-between sticky top-0 z-30";

  const navLinkCls =
    variant === "dark"
      ? "px-3 py-2 text-sm font-medium text-white hover:text-zinc-200 hover:bg-white/10 rounded-lg transition-colors flex items-center gap-1.5 drop-shadow"
      : "px-3 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100 rounded-lg transition-colors flex items-center gap-1.5";

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
            variant === "dark"
              ? "h-12 w-auto drop-shadow-lg"
              : "h-10 w-auto"
          }
        />
      </Link>

      <nav className="hidden md:flex flex-1 items-center justify-center gap-1 mx-6">
        {menus.map((m) => (
          <Link key={m.key} href={m.href} className={navLinkCls}>
            <m.Icon className="w-4 h-4" />
            {m.label}
          </Link>
        ))}
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
