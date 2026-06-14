"use client";

import Image from "next/image";
import { useEffect, useState } from "react";
import { Loader2, Play, Search, Sparkles } from "lucide-react";

import DashboardHeader from "@/components/DashboardHeader";
import LoginModal from "@/components/LoginModal";
import RegisterModal from "@/components/RegisterModal";
import TalentDetailModal from "@/components/TalentDetailModal";
import VideoPlayerModal from "@/components/VideoPlayerModal";
import { api } from "@/lib/api";
import { useAuth } from "@/store/auth";

type ScenePayload = {
  talent_media_id?: number;
  account_id?: number;
  scene_id?: string;
  scene_summary?: string;
  search_keywords?: string[];
};
type Profile = {
  account_id: number;
  name: string;
  age: number | null;
  height_cm: number | null;
  weight_kg: number | null;
};
type SearchResult = { score: number; payload: ScenePayload; profile?: Profile | null };
type Conditions = {
  age_min: number | null;
  age_max: number | null;
  gender: string | null;
  height_min: number | null;
  height_max: number | null;
  weight_min: number | null;
  weight_max: number | null;
  skills: string[];
  languages: string[];
};

const EXAMPLES = [
  "키 170 이상 친근한 인상",
  "영어 가능한 청순한 이미지",
  "자전거 잘 타는 활동적인",
  "차분한 아나운서 느낌",
];

// 주 분야 (필수) — talent_master.main_category 와 동일 코드
const CATEGORY_OPTIONS: { value: string; label: string }[] = [
  { value: "ACTOR", label: "연기자" },
  { value: "MODEL", label: "모델" },
  { value: "INFLUENCER", label: "인플루언서" },
  { value: "VOCAL", label: "보컬" },
  { value: "DANCER", label: "댄서" },
  { value: "MC", label: "MC" },
  { value: "CREATOR", label: "크리에이터" },
];
// 성별 (필수)
const GENDER_OPTIONS: { value: string; label: string }[] = [
  { value: "FEMALE", label: "여성" },
  { value: "MALE", label: "남성" },
];

// 유사도(0~1)에 따른 3구간 판정 — 적합(45%↑) / 보통(35~45%) / 부족(35%↓)
function scoreTier(score: number): { label: string; color: string } {
  const pct = score * 100;
  if (pct >= 45) return { label: "적합", color: "text-emerald-300" };
  if (pct >= 35) return { label: "보통", color: "text-amber-300" };
  return { label: "부족", color: "text-red-400" };
}

// 요약을 앞에서 n단어까지만 잘라 "…" 붙임
function truncateWords(text: string, n = 25): string {
  const words = text.trim().split(/\s+/);
  return words.length <= n ? text : words.slice(0, n).join(" ") + " …";
}

// 추출된 DB 조건을 사람이 읽는 칩 문자열로
function conditionChips(c: Conditions): string[] {
  const chips: string[] = [];
  const range = (lo: number | null, hi: number | null, unit: string) =>
    lo != null && hi != null
      ? `${lo}~${hi}${unit}`
      : lo != null
        ? `${lo}${unit} 이상`
        : hi != null
          ? `${hi}${unit} 이하`
          : null;
  const age = range(c.age_min, c.age_max, "세");
  if (age) chips.push(`나이 ${age}`);
  if (c.gender) chips.push(c.gender === "FEMALE" ? "여성" : "남성");
  const h = range(c.height_min, c.height_max, "cm");
  if (h) chips.push(`키 ${h}`);
  const w = range(c.weight_min, c.weight_max, "kg");
  if (w) chips.push(`몸무게 ${w}`);
  c.skills.forEach((s) => chips.push(`특기·${s}`));
  c.languages.forEach((l) => chips.push(`언어·${l}`));
  return chips;
}

/**
 * 인재 탐색 화면. 화면 자체는 누구나 볼 수 있고(공용 /explore 진입),
 * 검색 실행 시점에 로그인·권한(에이전시/관리자)을 요구한다.
 * 에이전시·관리자 대시보드 경로에서는 이미 가드를 통과한 상태라 그대로 통과한다.
 */
export default function TalentSearchView() {
  const account = useAuth((s) => s.account);
  const restore = useAuth((s) => s.restore);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<SearchResult[] | null>(null);
  const [conditions, setConditions] = useState<Conditions | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [player, setPlayer] = useState<{ src: string; title: string | null } | null>(
    null,
  );
  const [detailId, setDetailId] = useState<number | null>(null);
  const [loginOpen, setLoginOpen] = useState(false);
  const [registerOpen, setRegisterOpen] = useState(false);
  // 필수 필터 — 주 분야 / 성별
  const [mainCategory, setMainCategory] = useState("");
  const [gender, setGender] = useState("");
  // 마지막으로 검색에 적용된 필터(결과 헤더 칩 표시용)
  const [applied, setApplied] = useState<{ category: string; gender: string } | null>(
    null,
  );

  // 공용 경로로 직접 들어온 경우 인증 상태를 한 번 복원해 둔다.
  // (대시보드 경로는 가드에서 이미 복원하므로 account 가 있으면 생략)
  useEffect(() => {
    if (!account) restore();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const runSearch = async (query: string) => {
    const term = query.trim();
    if (!term) return;
    // 검색 실행 게이트: 로그인 + 에이전시/관리자만 허용
    const acc = useAuth.getState().account;
    if (!acc) {
      setErr("로그인 후 이용할 수 있는 기능입니다.");
      setLoginOpen(true);
      return;
    }
    if (acc.account_type !== "AGENCY" && acc.account_type !== "ADMIN") {
      setErr("인재 탐색은 에이전시·관리자 전용 기능입니다.");
      return;
    }
    // 주 분야·성별은 필수 선택
    if (!mainCategory || !gender) {
      setErr("주 분야와 성별을 먼저 선택해 주세요.");
      return;
    }
    setErr(null);
    setLoading(true);
    setResults(null);
    setConditions(null);
    try {
      const res = await api.get<{
        count: number;
        results: SearchResult[];
        conditions: Conditions;
      }>("/agency/search", {
        params: { q: term, main_category: mainCategory, gender, limit: 30 },
      });
      setResults(res.data.results);
      setConditions(res.data.conditions);
      setApplied({ category: mainCategory, gender });
    } catch {
      setErr("검색에 실패했습니다. 잠시 후 다시 시도해 주세요.");
    } finally {
      setLoading(false);
    }
  };

  const chips = conditions ? conditionChips(conditions) : [];

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

      <DashboardHeader variant="dark" onLoginClick={() => setLoginOpen(true)} />

      <main className="relative max-w-7xl mx-auto px-4 sm:px-6 pt-28 pb-12">
        <h1 className="text-2xl sm:text-3xl font-bold text-white drop-shadow-lg flex items-center gap-2">
          <Sparkles className="w-7 h-7 text-amber-100" />
          인재 탐색
        </h1>
        <p className="mt-1 text-white/80 drop-shadow">
          <b className="text-amber-100">주 분야·성별</b>을 먼저 선택하고, 이미지·분위기를 한 문장으로
          검색하세요. 나이·키·특기·언어는 문장에서 자동으로 인식해 거릅니다.
        </p>

        {/* 필수 필터 — 주 분야 / 성별 */}
        <div className="mt-8 flex flex-wrap gap-2">
          <select
            value={mainCategory}
            onChange={(e) => setMainCategory(e.target.value)}
            className="rounded-lg border border-white/20 bg-white/10 backdrop-blur-md px-3 py-2.5 text-white focus:outline-none focus:border-white/40 [&>option]:text-zinc-900"
          >
            <option value="">주 분야 *</option>
            {CATEGORY_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          <select
            value={gender}
            onChange={(e) => setGender(e.target.value)}
            className="rounded-lg border border-white/20 bg-white/10 backdrop-blur-md px-3 py-2.5 text-white focus:outline-none focus:border-white/40 [&>option]:text-zinc-900"
          >
            <option value="">성별 *</option>
            {GENDER_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>

        {/* 검색 입력 */}
        <div className="mt-2 flex gap-2">
          <input
            type="text"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && runSearch(q)}
            placeholder="예: 키 170 이상 자전거 잘 타는 친근한 인상"
            className="flex-1 rounded-lg border border-white/20 bg-white/10 backdrop-blur-md px-4 py-2.5 text-white placeholder-white/40 focus:outline-none focus:border-white/40"
          />
          <button
            type="button"
            onClick={() => runSearch(q)}
            disabled={loading || !q.trim() || !mainCategory || !gender}
            className="inline-flex items-center gap-2 rounded-lg bg-amber-100 text-zinc-900 px-5 py-2.5 text-sm font-semibold hover:bg-amber-200 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Search className="w-4 h-4" />
            )}
            검색
          </button>
        </div>

        {/* 예시 칩 — 클릭 시 검색 문장만 채움 (주 분야·성별은 직접 선택) */}
        <div className="mt-3 flex flex-wrap gap-2">
          {EXAMPLES.map((ex) => (
            <button
              key={ex}
              type="button"
              onClick={() => setQ(ex)}
              className="px-3 py-1 rounded-full border border-white/20 bg-white/5 text-white/80 text-xs hover:bg-white/15 transition-colors"
            >
              {ex}
            </button>
          ))}
        </div>

        {err && (
          <div className="mt-4 rounded-lg bg-red-500/20 border border-red-400/40 text-red-100 text-sm px-4 py-2.5">
            {err}
          </div>
        )}

        {/* 결과 */}
        {results && (
          <div className="mt-6">
            <div className="flex flex-wrap items-center gap-2 mb-3">
              <span className="text-sm text-white/70">
                결과 <b className="text-white">{results.length}</b>개
              </span>
              {applied && (
                <span className="px-2 py-0.5 rounded-full bg-emerald-400/25 text-emerald-100 text-[11px] font-semibold">
                  {CATEGORY_OPTIONS.find((o) => o.value === applied.category)?.label ??
                    applied.category}
                  {" · "}
                  {applied.gender === "FEMALE" ? "여성" : "남성"}
                </span>
              )}
              {chips.map((c) => (
                <span
                  key={c}
                  className="px-2 py-0.5 rounded-full bg-amber-100/20 text-amber-100 text-[11px] font-medium"
                >
                  {c}
                </span>
              ))}
            </div>

            {results.length === 0 ? (
              <div className="rounded-xl border border-white/15 bg-white/5 backdrop-blur-md p-8 text-center text-white/70">
                조건에 맞는 인재를 찾지 못했습니다.
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                {results.map((r, i) => {
                  const p = r.payload || {};
                  const prof = r.profile;
                  const keywords = Array.isArray(p.search_keywords)
                    ? p.search_keywords
                    : [];
                  const specs = [
                    prof?.age != null ? `${prof.age}세` : null,
                    prof?.height_cm ? `${prof.height_cm}cm` : null,
                    prof?.weight_kg ? `${prof.weight_kg}kg` : null,
                  ].filter(Boolean);
                  return (
                    <div
                      key={`${p.talent_media_id}-${p.scene_id}-${i}`}
                      className="rounded-xl border border-white/15 bg-white/5 backdrop-blur-md p-4"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          {prof ? (
                            <button
                              type="button"
                              onClick={() => setDetailId(prof.account_id)}
                              className="text-white font-semibold hover:text-amber-100 hover:underline transition-colors"
                            >
                              {prof.name}
                            </button>
                          ) : (
                            <span className="text-white font-semibold">
                              이름 미상
                            </span>
                          )}
                          {specs.length > 0 && (
                            <span className="ml-2 text-white/60 text-xs">
                              {specs.join(" · ")}
                            </span>
                          )}
                        </div>
                        <span
                          className={
                            "text-xs font-semibold shrink-0 " + scoreTier(r.score).color
                          }
                        >
                          {scoreTier(r.score).label} · 유사도 {(r.score * 100).toFixed(1)}%
                        </span>
                      </div>
                      {p.scene_summary && (
                        <div className="relative group/sum mt-2">
                          <p className="text-sm leading-relaxed text-white/85 cursor-help">
                            {truncateWords(p.scene_summary, 25)}
                          </p>
                          {/* hover 시 전체 요약 표시 */}
                          <div className="pointer-events-none absolute left-0 top-full z-20 mt-1 w-full opacity-0 group-hover/sum:opacity-100 transition-opacity">
                            <div className="rounded-lg border border-white/15 bg-zinc-900/95 backdrop-blur-md shadow-2xl p-3 text-xs leading-relaxed text-white/90">
                              {p.scene_summary}
                            </div>
                          </div>
                        </div>
                      )}
                      {keywords.length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          {keywords.slice(0, 8).map((k) => (
                            <span
                              key={k}
                              className="px-2 py-0.5 rounded-full bg-emerald-400/20 text-emerald-100 text-[11px]"
                            >
                              {k}
                            </span>
                          ))}
                        </div>
                      )}
                      {p.talent_media_id != null && (
                        <button
                          type="button"
                          onClick={() =>
                            setPlayer({
                              src: `/api/media/${p.talent_media_id}`,
                              title: p.scene_summary ?? null,
                            })
                          }
                          className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-white text-xs px-3 py-1.5 transition-colors"
                        >
                          <Play className="w-3.5 h-3.5" />
                          영상 보기
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </main>

      <VideoPlayerModal
        open={player !== null}
        onClose={() => setPlayer(null)}
        src={player?.src ?? null}
        title={player?.title ?? null}
      />

      <TalentDetailModal accountId={detailId} onClose={() => setDetailId(null)} />

      <LoginModal
        open={loginOpen}
        onClose={() => setLoginOpen(false)}
        onSwitchToRegister={() => setRegisterOpen(true)}
      />
      <RegisterModal open={registerOpen} onClose={() => setRegisterOpen(false)} />
    </div>
  );
}
