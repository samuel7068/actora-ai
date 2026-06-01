"use client";

import Image from "next/image";
import { useState } from "react";
import { Loader2, Play, Search, Sparkles } from "lucide-react";

import DashboardHeader from "@/components/DashboardHeader";
import TalentDetailModal from "@/components/TalentDetailModal";
import VideoPlayerModal from "@/components/VideoPlayerModal";
import { api } from "@/lib/api";

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
  "40대 키 170 이상 남성 배우",
  "영어 가능한 20대 청순한 여성",
  "자전거 잘 타는 30대 친근한 인상",
  "차분한 아나운서 느낌의 여성",
];

// 유사도(0~1)에 따른 색상 — 높을수록 녹색, 낮을수록 빨강
function scoreColor(score: number): string {
  const pct = score * 100;
  if (pct >= 45) return "text-emerald-300";
  if (pct >= 35) return "text-lime-300";
  if (pct >= 25) return "text-amber-300";
  if (pct >= 18) return "text-orange-400";
  return "text-red-400";
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

/** 인재 탐색 화면 (에이전시·관리자 공용). 가드는 사용하는 페이지에서 처리. */
export default function TalentSearchView() {
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<SearchResult[] | null>(null);
  const [conditions, setConditions] = useState<Conditions | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [player, setPlayer] = useState<{ src: string; title: string | null } | null>(
    null,
  );
  const [detailId, setDetailId] = useState<number | null>(null);

  const runSearch = async (query: string) => {
    const term = query.trim();
    if (!term) return;
    setLoading(true);
    setErr(null);
    setResults(null);
    setConditions(null);
    try {
      const res = await api.get<{
        count: number;
        results: SearchResult[];
        conditions: Conditions;
      }>("/agency/search", { params: { q: term, limit: 30 } });
      setResults(res.data.results);
      setConditions(res.data.conditions);
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

      <DashboardHeader variant="dark" />

      <main className="relative max-w-7xl mx-auto px-4 sm:px-6 pt-28 pb-12">
        <h1 className="text-2xl sm:text-3xl font-bold text-white drop-shadow-lg flex items-center gap-2">
          <Sparkles className="w-7 h-7 text-amber-100" />
          인재 탐색
        </h1>
        <p className="mt-1 text-white/80 drop-shadow">
          한 문장으로 검색하세요. 나이·성별·키·특기·언어는 자동으로 인식해 거르고,
          이미지·분위기는 의미로 찾아줍니다.
        </p>

        {/* 검색 입력 */}
        <div className="mt-8 flex gap-2">
          <input
            type="text"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && runSearch(q)}
            placeholder="예: 40대 초반 키 170 이상 자전거 잘 타는 친근한 남성 배우"
            className="flex-1 rounded-lg border border-white/20 bg-white/10 backdrop-blur-md px-4 py-2.5 text-white placeholder-white/40 focus:outline-none focus:border-white/40"
          />
          <button
            type="button"
            onClick={() => runSearch(q)}
            disabled={loading || !q.trim()}
            className="inline-flex items-center gap-2 rounded-lg bg-amber-100 text-zinc-900 px-5 py-2.5 text-sm font-semibold hover:bg-amber-200 transition-colors disabled:opacity-50"
          >
            {loading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Search className="w-4 h-4" />
            )}
            검색
          </button>
        </div>

        {/* 예시 칩 */}
        <div className="mt-3 flex flex-wrap gap-2">
          {EXAMPLES.map((ex) => (
            <button
              key={ex}
              type="button"
              onClick={() => {
                setQ(ex);
                runSearch(ex);
              }}
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
              {chips.length > 0 && (
                <>
                  <span className="text-white/40 text-xs">· 인식된 조건:</span>
                  {chips.map((c) => (
                    <span
                      key={c}
                      className="px-2 py-0.5 rounded-full bg-amber-100/20 text-amber-100 text-[11px] font-medium"
                    >
                      {c}
                    </span>
                  ))}
                </>
              )}
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
                            "text-xs font-semibold shrink-0 " + scoreColor(r.score)
                          }
                        >
                          유사도 {(r.score * 100).toFixed(1)}%
                        </span>
                      </div>
                      {p.scene_summary && (
                        <p className="mt-2 text-sm leading-relaxed text-white/85">
                          {truncateWords(p.scene_summary, 25)}
                        </p>
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
    </div>
  );
}
