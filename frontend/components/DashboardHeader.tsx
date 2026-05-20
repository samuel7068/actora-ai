"use client";

import Image from "next/image";
import Link from "next/link";

import UserMenu from "@/components/UserMenu";
import { useAuth } from "@/store/auth";
import {
  filterMenusByPermission,
  getMenusForAccountType,
} from "@/lib/menus";

type Props = {
  onLoginClick?: () => void;
};

export default function DashboardHeader({ onLoginClick }: Props) {
  const account = useAuth((s) => s.account);
  const menus = account
    ? filterMenusByPermission(
        getMenusForAccountType(account.account_type),
        account.permission,
      )
    : [];

  return (
    <header className="w-full bg-white border-b border-zinc-200 px-4 sm:px-6 py-3 flex items-center justify-between sticky top-0 z-30">
      <Link href="/" className="flex-shrink-0">
        <Image
          src="/images/Actora_logo.png"
          alt="Actora"
          width={845}
          height={264}
          priority
          className="h-10 w-auto"
        />
      </Link>

      <nav className="hidden md:flex flex-1 items-center justify-center gap-1 mx-6">
        {menus.map((m) => (
          <Link
            key={m.key}
            href={m.href}
            className="px-3 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100 rounded-lg transition-colors flex items-center gap-1.5"
          >
            <m.Icon className="w-4 h-4" />
            {m.label}
          </Link>
        ))}
      </nav>

      <div className="flex-shrink-0">
        <UserMenu onLoginClick={onLoginClick ?? (() => {})} variant="light" />
      </div>
    </header>
  );
}
