"use client";

import Image from "next/image";
import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Loader2, Search, Trash2, UserPlus, Users } from "lucide-react";

import DashboardHeader from "@/components/DashboardHeader";
import { useDashboardGuard } from "@/components/DashboardGuard";
import TalentProfileModal from "@/components/TalentProfileModal";
import { api } from "@/lib/api";

type TalentRow = {
  account_id: number;
  name: string;
  created_at: string;
  stage_name: string | null;
  gender: string | null;
  age: number | null;
  height_cm: number | null;
  weight_kg: number | null;
  region_code: string | null;
  main_category: string | null;
  skills: string[];
  languages: string[];
  career_level: string | null;
  career_years: number | null;
  profile_completion_rate: number | null;
  media_count: number;
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
const CAREER_LEVEL: Record<string, string> = { NEWBIE: "신인", PRO: "프로" };

// 완성도(%)에 따른 텍스트 색 — 높을수록 녹색
function completionColor(rate: number | null): string {
  if (rate == null) return "text-white/40";
  if (rate >= 80) return "text-emerald-300";
  if (rate >= 50) return "text-amber-300";
  return "text-red-300";
}

// 헤더·데이터 모두 가로 중앙정렬
const PAGE_SIZE = 20;
const TH = "px-3 py-2 text-center font-semibold text-white/70 whitespace-nowrap";
const TD = "px-3 py-2 text-center text-white/90 whitespace-nowrap";

export default function AdminTalentsPage() {
  const ready = useDashboardGuard("ADMIN");
  const [items, setItems] = useState<TalentRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [editId, setEditId] = useState<number | null>(null);
  // 삭제 확인 모달 대상 (null 이면 모달 닫힘)
  const [deleteTarget, setDeleteTarget] = useState<TalentRow | null>(null);
  const [deleting, setDeleting] = useState(false);

  // 검색 입력값 — 검색 버튼을 눌러야 applied 로 넘어가 조회에 반영된다
  const [q, setQ] = useState("");
  const [gender, setGender] = useState("");
  const [applied, setApplied] = useState({ q: "", gender: "" });
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);

  const fetchList = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const res = await api.get<{
        items: TalentRow[];
        total: number;
        total_pages: number;
      }>("/admin/talents", {
        params: {
          q: applied.q || undefined,
          gender: applied.gender || undefined,
          page,
          size: PAGE_SIZE,
        },
      });
      setItems(res.data.items);
      setTotal(res.data.total);
      setTotalPages(res.data.total_pages);
    } catch {
      setErr("목록을 불러오지 못했습니다.");
      setItems([]);
      setTotal(0);
      setTotalPages(1);
    } finally {
      setLoading(false);
    }
  }, [applied, page]);

  // 검색은 항상 1페이지부터
  const runSearch = useCallback(() => {
    setPage(1);
    setApplied({ q: q.trim(), gender });
  }, [q, gender]);

  const resetSearch = useCallback(() => {
    setQ("");
    setGender("");
    setPage(1);
    setApplied({ q: "", gender: "" });
  }, []);

  // 인재 등록: 이름만 받아 생성 → 곧바로 프로필 편집 모달 오픈
  const handleCreate = useCallback(async () => {
    const name = window.prompt("등록할 인재 이름을 입력하세요");
    if (!name || !name.trim()) return;
    try {
      const res = await api.post<{ account_id: number }>("/admin/talents", {
        name: name.trim(),
      });
      await fetchList();
      setEditId(res.data.account_id);
    } catch {
      alert("등록에 실패했습니다.");
    }
  }, [fetchList]);

  // 인재 완전 삭제 — 확인 모달에서 호출. 계정+프로필+영상/사진+RAG+Qdrant 전부 제거.
  const handleDelete = useCallback(async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await api.delete(`/admin/talents/${deleteTarget.account_id}`);
      setDeleteTarget(null);
      await fetchList();
    } catch {
      alert("삭제에 실패했습니다. 잠시 후 다시 시도해 주세요.");
    } finally {
      setDeleting(false);
    }
  }, [deleteTarget, fetchList]);

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

      <main className="relative max-w-[100rem] mx-auto px-4 sm:px-6 pt-28 pb-12">
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
          <button
            type="button"
            onClick={handleCreate}
            className="inline-flex items-center gap-2 rounded-full bg-amber-100 text-zinc-900 px-5 py-2.5 text-sm font-semibold hover:bg-amber-200 transition-colors shadow"
          >
            <UserPlus className="w-4 h-4" />
            인재 등록
          </button>
        </div>

        {/* 검색 — 이름(예명 포함) · 성별 */}
        <div className="mb-4 flex flex-wrap gap-2">
          <input
            type="text"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && runSearch()}
            placeholder="이름 또는 예명"
            className="w-56 rounded-lg border border-white/20 bg-white/10 backdrop-blur-md px-3 py-2 text-sm text-white placeholder-white/40 focus:outline-none focus:border-white/40"
          />
          <select
            value={gender}
            onChange={(e) => setGender(e.target.value)}
            className="rounded-lg border border-white/20 bg-white/10 backdrop-blur-md px-3 py-2 text-sm text-white focus:outline-none focus:border-white/40 [&>option]:text-zinc-900"
          >
            <option value="">성별 전체</option>
            <option value="FEMALE">여</option>
            <option value="MALE">남</option>
          </select>
          <button
            type="button"
            onClick={runSearch}
            className="inline-flex items-center gap-1.5 rounded-lg bg-amber-100 text-zinc-900 px-4 py-2 text-sm font-semibold hover:bg-amber-200 transition-colors"
          >
            <Search className="w-4 h-4" />
            검색
          </button>
          {(applied.q || applied.gender) && (
            <button
              type="button"
              onClick={resetSearch}
              className="rounded-lg border border-white/20 px-4 py-2 text-sm text-white/70 hover:bg-white/10 transition-colors"
            >
              초기화
            </button>
          )}
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
            {applied.q || applied.gender
              ? "검색 결과가 없습니다."
              : "등록된 인재가 없습니다."}
          </div>
        ) : (
          <div className="rounded-xl border border-white/15 bg-white/5 backdrop-blur-md overflow-hidden">
            <div className="text-xs text-white/60 px-4 py-2 border-b border-white/10">
              총 <b className="text-white">{total}</b>명{totalPages > 1 && <span className="ml-2 text-white/40">· {page} / {totalPages} 페이지</span>}
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-white/5">
                  <tr>
                    <th className={TH}>ID</th>
                    <th className={TH}>이름</th>
                    <th className={TH}>예명</th>
                    <th className={TH}>성별</th>
                    <th className={TH}>나이</th>
                    <th className={TH}>키</th>
                    <th className={TH}>몸무게</th>
                    <th className={TH}>지역</th>
                    <th className={TH}>분야</th>
                    <th className={TH}>경력</th>
                    <th className={TH}>특기</th>
                    <th className={TH}>언어</th>
                    <th className={TH + " text-center"}>영상</th>
                    <th className={TH + " text-center"}>완성도</th>
                    <th className={TH}>등록일</th>
                    <th className={TH + " text-center"}>관리</th>
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
                          onClick={() => setEditId(t.account_id)}
                          className="font-semibold text-white hover:text-amber-100 hover:underline"
                        >
                          {t.name}
                        </button>
                      </td>
                      <td className={TD + " text-white/70"}>{t.stage_name || "—"}</td>
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
                      <td className={TD + " text-white/70"}>
                        {t.career_level
                          ? `${CAREER_LEVEL[t.career_level] ?? t.career_level}${
                              t.career_years != null ? ` ${t.career_years}년` : ""
                            }`
                          : "—"}
                      </td>
                      <td className={TD + " max-w-[160px] truncate"}>
                        {t.skills.length ? t.skills.join(", ") : "—"}
                      </td>
                      <td className={TD + " max-w-[140px] truncate"}>
                        {t.languages.length ? t.languages.join(", ") : "—"}
                      </td>
                      <td className={TD + " text-center"}>
                        {t.media_count > 0 ? (
                          <span className="inline-flex items-center justify-center min-w-[1.5rem] rounded-full bg-amber-100/20 text-amber-100 text-xs font-semibold px-1.5">
                            {t.media_count}
                          </span>
                        ) : (
                          <span className="text-white/30">0</span>
                        )}
                      </td>
                      <td className={TD + " text-center font-semibold " + completionColor(t.profile_completion_rate)}>
                        {t.profile_completion_rate != null
                          ? `${t.profile_completion_rate}%`
                          : "—"}
                      </td>
                      <td className={TD + " text-white/50"}>
                        {new Date(t.created_at).toLocaleDateString("ko-KR")}
                      </td>
                      <td className={TD + " text-center"}>
                        <button
                          type="button"
                          onClick={() => setDeleteTarget(t)}
                          title="인재 삭제"
                          className="inline-flex items-center justify-center rounded-lg p-1.5 text-white/50 hover:text-red-300 hover:bg-red-500/15 transition-colors"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* 페이지네이션 — 페이지가 하나뿐이면 감춘다 */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-1 px-4 py-3 border-t border-white/10">
                <button
                  type="button"
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1}
                  className="rounded-lg px-3 py-1.5 text-sm text-white/70 hover:bg-white/10 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                >
                  이전
                </button>
                {Array.from({ length: totalPages }, (_, i) => i + 1).map((n) => (
                  <button
                    key={n}
                    type="button"
                    onClick={() => setPage(n)}
                    className={
                      n === page
                        ? "min-w-[2rem] rounded-lg bg-amber-100 text-zinc-900 px-2.5 py-1.5 text-sm font-semibold"
                        : "min-w-[2rem] rounded-lg px-2.5 py-1.5 text-sm text-white/70 hover:bg-white/10 transition-colors"
                    }
                  >
                    {n}
                  </button>
                ))}
                <button
                  type="button"
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page >= totalPages}
                  className="rounded-lg px-3 py-1.5 text-sm text-white/70 hover:bg-white/10 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                >
                  다음
                </button>
              </div>
            )}
          </div>
        )}
      </main>

      <TalentProfileModal
        open={editId !== null}
        accountId={editId ?? undefined}
        onClose={() => {
          setEditId(null);
          fetchList();
        }}
      />

      {/* 삭제 확인 모달 */}
      {deleteTarget && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          role="dialog"
          aria-modal="true"
        >
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => !deleting && setDeleteTarget(null)}
          />
          <div className="relative w-full max-w-md rounded-2xl border border-white/15 bg-zinc-900 p-6 shadow-2xl">
            <div className="flex items-start gap-3">
              <div className="flex-shrink-0 rounded-full bg-red-500/15 p-2">
                <AlertTriangle className="w-6 h-6 text-red-400" />
              </div>
              <div className="flex-1">
                <h2 className="text-lg font-bold text-white">인재 삭제</h2>
                <p className="mt-2 text-sm leading-relaxed text-white/80">
                  <b className="text-white">{deleteTarget.name}</b>
                  <span className="text-white/50"> (ID {deleteTarget.account_id})</span>
                  님을 완전히 삭제합니다.
                </p>
                <p className="mt-2 text-sm leading-relaxed text-red-200/90">
                  계정·프로필과 등록된 모든 영상·사진, 분석 데이터가 영구 삭제되며
                  <b> 복구할 수 없습니다.</b>
                </p>
              </div>
            </div>
            <div className="mt-6 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setDeleteTarget(null)}
                disabled={deleting}
                className="rounded-lg px-4 py-2 text-sm font-medium text-white/80 hover:bg-white/10 transition-colors disabled:opacity-50"
              >
                취소
              </button>
              <button
                type="button"
                onClick={handleDelete}
                disabled={deleting}
                className="inline-flex items-center gap-2 rounded-lg bg-red-500 px-4 py-2 text-sm font-semibold text-white hover:bg-red-600 transition-colors disabled:opacity-50"
              >
                {deleting ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Trash2 className="w-4 h-4" />
                )}
                삭제
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
