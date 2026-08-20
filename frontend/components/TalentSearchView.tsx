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

// 키·나이는 위에서 따로 고르므로, 예시는 영상에서만 알 수 있는
// 감정·연기·분위기 위주로 둔다.
const EXAMPLES = [
  "울음을 참으며 눌러 담는 감정 연기",
  "분노를 터뜨리는 격한 장면",
  "차분한 아나운서 느낌",
  "밝고 친근한 리액션",
  "영어 가능한 청순한 이미지",
];

// 영상 속 **역할**의 연령대 — scene payload 의 age_range.
// 인재의 실제 나이와 별개다 (20대 배우가 40대 엄마 역을 연기한 장면).
const ROLE_AGE_OPTIONS: { value: string; label: string }[] = [
  { value: "child_actor", label: "아역 (5~7세)" },
  { value: "elementary", label: "초등 (8~12세)" },
  { value: "middle_school", label: "중등 (13~16세)" },
  { value: "high_school", label: "고등 (17~19세)" },
  { value: "20s", label: "20대 역" },
  { value: "30s", label: "30대 역" },
  { value: "40s", label: "40대 역" },
  { value: "50s", label: "50대 역" },
  { value: "60s", label: "60대 역" },
  { value: "70s_plus", label: "70대 이상 역" },
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

// 연령대 (선택) — 고르면 문장에서 추출한 나이 조건보다 우선한다
type RangeOption = { value: string; label: string; min: number | null; max: number | null };
const AGE_OPTIONS: RangeOption[] = [
  { value: "10s", label: "10대", min: 10, max: 19 },
  { value: "20s", label: "20대", min: 20, max: 29 },
  { value: "30s", label: "30대", min: 30, max: 39 },
  { value: "40s", label: "40대", min: 40, max: 49 },
  { value: "50s", label: "50대 이상", min: 50, max: null },
];
// 키 (선택)
const HEIGHT_OPTIONS: RangeOption[] = [
  { value: "-159", label: "159cm 이하", min: null, max: 159 },
  { value: "160-169", label: "160~169cm", min: 160, max: 169 },
  { value: "170-179", label: "170~179cm", min: 170, max: 179 },
  { value: "180-", label: "180cm 이상", min: 180, max: null },
];

const findRange = (opts: RangeOption[], value: string) =>
  opts.find((o) => o.value === value) ?? null;

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
  // 선택 필터 — 연령대 / 키
  const [ageRange, setAgeRange] = useState("");
  const [heightRange, setHeightRange] = useState("");
  // 영상 장면 조건 — 연기한 역할의 연령대
  const [roleAgeRange, setRoleAgeRange] = useState("");
  // 마지막으로 검색에 적용된 필터(결과 헤더 칩 표시용)
  const [applied, setApplied] = useState<{
    category: string;
    gender: string;
    age: string;
    height: string;
    roleAge: string;
  } | null>(null);

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
    const age = findRange(AGE_OPTIONS, ageRange);
    const height = findRange(HEIGHT_OPTIONS, heightRange);
    try {
      const res = await api.get<{
        count: number;
        results: SearchResult[];
        conditions: Conditions;
      }>("/agency/search", {
        params: {
          q: term,
          main_category: mainCategory,
          gender,
          // 선택하지 않은 범위는 아예 보내지 않는다 (undefined 는 axios 가 제외)
          age_min: age?.min ?? undefined,
          age_max: age?.max ?? undefined,
          height_min: height?.min ?? undefined,
          height_max: height?.max ?? undefined,
          role_age_range: roleAgeRange || undefined,
          limit: 30,
        },
      });
      setResults(res.data.results);
      setConditions(res.data.conditions);
      setApplied({
        category: mainCategory,
        gender,
        age: ageRange,
        height: heightRange,
        roleAge: roleAgeRange,
      });
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
          <b className="text-amber-100">인재 프로필</b>로 후보를 좁히고,{" "}
          <b className="text-amber-100">영상 장면</b>에서 연기·연출된 모습을 문장으로 검색합니다.
        </p>
        <p className="mt-1 text-white/60 text-sm drop-shadow">
          실제 나이와 연기한 나이대는 따로 고를 수 있습니다. 특기·언어는 검색 문장에서 자동 인식합니다.
        </p>

        {/* ── 구역 1: 인재 프로필 — 등록된 실제 정보로 후보를 좁힌다 ── */}
        <section className="mt-8 rounded-xl border border-white/15 bg-white/5 backdrop-blur-md p-4">
          <div className="flex flex-wrap items-center gap-2 mb-3">
            <span className="w-5 h-5 shrink-0 rounded-full bg-amber-100 text-zinc-900 text-[11px] font-bold flex items-center justify-center">
              1
            </span>
            <h2 className="text-sm font-semibold text-white">인재 프로필</h2>
            <span className="text-xs text-white/50">
              프로필에 등록된 실제 정보 — 주 분야·성별은 필수
            </span>
          </div>
          <div className="flex flex-wrap gap-2">
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
            <select
              value={ageRange}
              onChange={(e) => setAgeRange(e.target.value)}
              className="rounded-lg border border-white/20 bg-white/10 backdrop-blur-md px-3 py-2.5 text-white focus:outline-none focus:border-white/40 [&>option]:text-zinc-900"
            >
              <option value="">실제 나이 (전체)</option>
              {AGE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
            <select
              value={heightRange}
              onChange={(e) => setHeightRange(e.target.value)}
              className="rounded-lg border border-white/20 bg-white/10 backdrop-blur-md px-3 py-2.5 text-white focus:outline-none focus:border-white/40 [&>option]:text-zinc-900"
            >
              <option value="">키 (전체)</option>
              {HEIGHT_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
        </section>

        {/* ── 구역 2: 영상 장면 — 업로드된 영상에서 연기·연출된 모습 (RAG) ── */}
        <section className="mt-4 rounded-xl border border-white/15 bg-white/5 backdrop-blur-md p-4">
          <div className="flex flex-wrap items-center gap-2 mb-3">
            <span className="w-5 h-5 shrink-0 rounded-full bg-amber-100 text-zinc-900 text-[11px] font-bold flex items-center justify-center">
              2
            </span>
            <h2 className="text-sm font-semibold text-white">영상 장면</h2>
            <span className="text-xs text-white/50">
              영상에서 연기·연출된 모습 — 실제 나이와 달라도 됩니다
            </span>
          </div>
          <div className="flex flex-wrap gap-2">
            <select
              value={roleAgeRange}
              onChange={(e) => setRoleAgeRange(e.target.value)}
              className="rounded-lg border border-white/20 bg-white/10 backdrop-blur-md px-3 py-2.5 text-white focus:outline-none focus:border-white/40 [&>option]:text-zinc-900"
            >
              <option value="">연기한 나이대 (전체)</option>
              {ROLE_AGE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>

          <div className="mt-2 flex gap-2">
            <input
              type="text"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && runSearch(q)}
              placeholder="예: 울음을 참으며 눌러 담는 감정 연기"
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

          {/* 예시 칩 — 클릭 시 검색 문장만 채움 */}
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
        </section>

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
                  {/* 화면에서 직접 고른 연령대·키는 문장 추출 조건과 구분해 함께 표시 */}
                  {applied.age &&
                    ` · ${findRange(AGE_OPTIONS, applied.age)?.label ?? applied.age}`}
                  {applied.height &&
                    ` · ${findRange(HEIGHT_OPTIONS, applied.height)?.label ?? applied.height}`}
                </span>
              )}
              {/* 영상 장면 조건은 프로필 조건과 색을 달리해 구분 */}
              {applied?.roleAge && (
                <span className="px-2 py-0.5 rounded-full bg-sky-400/25 text-sky-100 text-[11px] font-semibold">
                  연기{" "}
                  {ROLE_AGE_OPTIONS.find((o) => o.value === applied.roleAge)?.label ??
                    applied.roleAge}
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
