"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import TalentSearchView from "@/components/TalentSearchView";
import { useAuth } from "@/store/auth";

/** 인재 탐색 (공용 경로). 로그인 + 에이전시/관리자만 사용 가능. */
export default function ExplorePage() {
  const router = useRouter();
  const account = useAuth((s) => s.account);
  const restore = useAuth((s) => s.restore);
  const [ok, setOk] = useState(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      if (!account) await restore();
      if (!alive) return;
      const acc = useAuth.getState().account;
      if (!acc) {
        alert("로그인 후 사용이 가능한 기능입니다.");
        router.replace("/");
        return;
      }
      if (acc.account_type === "ADMIN" || acc.account_type === "AGENCY") {
        setOk(true);
      } else {
        alert("인재 탐색은 에이전시·관리자 전용 기능입니다.");
        router.replace("/talent/dashboard");
      }
    })();
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!ok) return null;
  return <TalentSearchView />;
}
