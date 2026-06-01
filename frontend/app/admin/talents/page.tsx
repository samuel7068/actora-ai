"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Loader2, UserPlus, Users } from "lucide-react";

import DashboardHeader from "@/components/DashboardHeader";
import { useDashboardGuard } from "@/components/DashboardGuard";
import { api } from "@/lib/api";

type TalentRow = {
  account_id: number;
  name: string;
  created_at: string;
  gender: string | null;
  age: number | null;
  height_cm: number | null;
  weight_kg: number | null;
  region_code: string | null;
  main_category: string | null;
  skills: string[];
  languages: string[];
};

const GENDER: Record<string, string> = { MALE: "남", FEMALE: "여", SELF_DESCRIBED: "기타" };
const REGION: Record<string, string> = {
  SEOUL: "서울", BUSAN: "부산", INCHEON: "인천", DAEGU: "대구", DAEJEON: "대전",
  GWANGJU: "광주", ULSAN: "울산", SEJONG: "세종", GYEONGGI: "경기", GANGWON: "강원",
  CHUNGBUK: "충북", CHUNGNAM: "충남", JEONBUK: "전북", JEONNAM: "전남",
  GYEONGBUK: "경북", GYEONGNAM: "경남", JEJU: "제주", OVERSEAS: "해외",
};
const CATEGORY: Record<string, string> = {
  ACTOR: "연기자", MODEL: "모델", INFLUENCER: "인플루언서", VOCAL: "보컬",
  DANCER: "댄서", MC: "MC", CREATOR: "크리에이터",
};

const TH = "px-3 py-2 text-left font-semibold text-white/70 whitespace-nowrap";
const TD = "px-3 py-2 text-white/90 whitespace-nowrap";

export default function AdminTalentsPage() {
  const ready = useDashboardGuard("ADMIN");
  const router = useRouter();
  const [items, setItems] = useState<TalentRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const fetchList = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const res = await api.get<{ items: TalentRow[]; total: number }>(
        "/admin/talents",
      );
      setItems(res.data.items);
    } catch {
      setErr("목록을 불러오지 못했습니다.");
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (ready) fetchList();
  }, [ready, fetchList]);

  if (!ready) return null;

  return (
    <div className="relative min-h-screen w-full overflow-hidden">
      <Image
        src="/images/Backgroud.jpg"
        alt=""
        fill
        priority
        sizes="100vw"
        className="object-cover -z-10"
      />
      <div className="absolute inset-0 bg-black/55 -z-10" />

      <DashboardHeader variant="dark" />

      <main className="relative max-w-6xl mx-auto px-4 sm:px-6 pt-28 pb-12">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-white drop-shadow-lg flex items-center gap-2">
              <Users className="w-7 h-7 text-amber-100" />
              인재 관리
            </h1>
            <p className="mt-1 text-white/80 drop-shadow">
              등록된 전체 인재 목록입니다. 이름을 누르면 상세 프로필이 열립니다.
            </p>
          </div>
          <Link
            href="/admin/talents/new"
            className="inline-flex items-center gap-2 rounded-full bg-amber-100 text-zinc-900 px-5 py-2.5 text-sm font-semibold hover:bg-amber-200 transition-colors shadow"
          >
            <UserPlus className="w-4 h-4" />
            인재 등록
          </Link>
        </div>

        {err && (
          <div className="mb-4 rounded-lg bg-red-500/20 border border-red-400/40 text-red-100 text-sm px-4 py-2.5">
            {err}
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center gap-2 py-20 text-white/70 drop-shadow">
            <Loader2 className="w-5 h-5 animate-spin" />
            불러오는 중…
          </div>
        ) : items.length === 0 ? (
          <div className="rounded-xl border border-white/15 bg-white/5 backdrop-blur-md p-10 text-center text-white/70">
            등록된 인재가 없습니다.
          </div>
        ) : (
          <div className="rounded-xl border border-white/15 bg-white/5 backdrop-blur-md overflow-hidden">
            <div className="text-xs text-white/60 px-4 py-2 border-b border-white/10">
              총 <b className="text-white">{items.length}</b>명
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-white/5">
                  <tr>
                    <th className={TH}>ID</th>
                    <th className={TH}>이름</th>
                    <th className={TH}>성별</th>
                    <th className={TH}>나이</th>
                    <th className={TH}>키</th>
                    <th className={TH}>몸무게</th>
                    <th className={TH}>지역</th>
                    <th className={TH}>분야</th>
                    <th className={TH}>특기</th>
                    <th className={TH}>언어</th>
                    <th className={TH}>등록일</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((t) => (
                    <tr
                      key={t.account_id}
                      className="border-t border-white/10 hover:bg-white/5"
                    >
                      <td className={TD + " text-white/50"}>{t.account_id}</td>
                      <td className={TD}>
                        <button
                          type="button"
                          onClick={() =>
                            router.push(`/admin/talents/${t.account_id}/edit`)
                          }
                          className="font-semibold text-white hover:text-amber-100 hover:underline"
                        >
                          {t.name}
                        </button>
                      </td>
                      <td className={TD}>{t.gender ? GENDER[t.gender] ?? t.gender : "—"}</td>
                      <td className={TD}>{t.age != null ? `${t.age}세` : "—"}</td>
                      <td className={TD}>{t.height_cm ? `${t.height_cm}` : "—"}</td>
                      <td className={TD}>{t.weight_kg ? `${t.weight_kg}` : "—"}</td>
                      <td className={TD}>
                        {t.region_code ? REGION[t.region_code] ?? t.region_code : "—"}
                      </td>
                      <td className={TD}>
                        {t.main_category ? CATEGORY[t.main_category] ?? t.main_category : "—"}
                      </td>
                      <td className={TD + " max-w-[160px] truncate"}>
                        {t.skills.length ? t.skills.join(", ") : "—"}
                      </td>
                      <td className={TD + " max-w-[140px] truncate"}>
                        {t.languages.length ? t.languages.join(", ") : "—"}
                      </td>
                      <td className={TD + " text-white/50"}>
                        {new Date(t.created_at).toLocaleDateString("ko-KR")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
