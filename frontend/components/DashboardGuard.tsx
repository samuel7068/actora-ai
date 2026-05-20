"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth, type AccountInfo } from "@/store/auth";

/** dashboard 페이지에서 미인증/잘못된 type 접근 시 메인으로 보내는 가드.
 *  client-only — localStorage 에 토큰이 있으면 restore() 가 채워줌.
 */
export function useDashboardGuard(required: AccountInfo["account_type"]) {
  const account = useAuth((s) => s.account);
  const restore = useAuth((s) => s.restore);
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      if (!account) await restore();
      if (!alive) return;
      const acc = useAuth.getState().account;
      if (!acc) {
        router.replace("/");
      } else if (acc.account_type !== required) {
        // 다른 type 으로 로그인 한 경우 자기 dashboard 로
        const map = { ADMIN: "/admin/dashboard", TALENT: "/talent/dashboard", AGENCY: "/agency/dashboard" } as const;
        router.replace(map[acc.account_type] ?? "/");
      } else {
        setReady(true);
      }
    })();
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return ready;
}
