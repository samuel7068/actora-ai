"use client";

import Image from "next/image";
import { useCallback, useEffect, useState } from "react";
import { ChevronDown, Database, Loader2, Search } from "lucide-react";

import DashboardHeader from "@/components/DashboardHeader";
import { useDashboardGuard } from "@/components/DashboardGuard";
import { api } from "@/lib/api";

type MediaRow = {
  talent_media_id: number;
  account_id: number;
  account_name: string;
  original_file_name?: string | null;
  ai_summary?: string | null;
  created_at: string;
};
type SceneRow = { id: number | string; payload: Record<string, unknown> };

export default function AdminRagPage() {
  const ready = useDashboardGuard("ADMIN");
  const [name, setName] = useState("");
  const [items, setItems] = useState<MediaRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  // 펼친 행의 scene 데이터 캐시
  const [openId, setOpenId] = useState<number | null>(null);
  const [scenesById, setScenesById] = useState<Record<number, SceneRow[]>>({});
  const [scenesLoading, setScenesLoading] = useState<number | null>(null);

  const fetchList = useCallback(async (nameQuery: string) => {
    setLoading(true);
    setErr(null);
    try {
      const res = await api.get<{ items: MediaRow[]; total: number }>(
        "/admin/media",
        { params: nameQuery.trim() ? { name: nameQuery.trim() } : {} },
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
    if (ready) fetchList("");
  }, [ready, fetchList]);

  const toggleScenes = async (id: number) => {
    if (openId === id) {
      setOpenId(null);
      return;
    }
    setOpenId(id);
    if (!scenesById[id]) {
      setScenesLoading(id);
      try {
        const res = await api.get<{ scenes: SceneRow[] }>(
          `/admin/media/${id}/scenes`,
        );
        setScenesById((prev) => ({ ...prev, [id]: res.data.scenes }));
      } catch {
        setScenesById((prev) => ({ ...prev, [id]: [] }));
      } finally {
        setScenesLoading(null);
      }
    }
  };

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

      <main className="relative max-w-5xl mx-auto px-4 sm:px-6 pt-28 pb-12">
        <h1 className="text-2xl sm:text-3xl font-bold text-white drop-shadow-lg flex items-center gap-2">
          <Database className="w-7 h-7" />
          RAG 데이터 조회 (Qdrant)
        </h1>
        <p className="mt-1 text-white/80 drop-shadow">
          적재된 영상 전체 목록입니다. 행을 누르면 scene payload 가 펼쳐집니다.
        </p>

        {/* 이름 검색 */}
        <div className="mt-8 flex gap-2">
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && fetchList(name)}
            placeholder="연기자 이름으로 검색 (비우면 전체)"
            className="flex-1 rounded-lg border border-white/20 bg-white/10 backdrop-blur-md px-4 py-2.5 text-white placeholder-white/40 focus:outline-none focus:border-white/40"
          />
          <button
            type="button"
            onClick={() => fetchList(name)}
            className="inline-flex items-center gap-2 rounded-lg bg-amber-100 text-zinc-900 px-5 py-2.5 text-sm font-semibold hover:bg-amber-200 transition-colors"
          >
            <Search className="w-4 h-4" />
            검색
          </button>
        </div>

        {err && (
          <div className="mt-4 rounded-lg bg-red-500/20 border border-red-400/40 text-red-100 text-sm px-4 py-2.5">
            {err}
          </div>
        )}

        {/* 목록 */}
        {loading ? (
          <div className="flex items-center justify-center gap-2 py-20 text-white/70 drop-shadow">
            <Loader2 className="w-5 h-5 animate-spin" />
            불러오는 중…
          </div>
        ) : items.length === 0 ? (
          <div className="mt-6 rounded-xl border border-white/15 bg-white/5 backdrop-blur-md p-8 text-center text-white/70">
            적재된 영상이 없습니다.
          </div>
        ) : (
          <div className="mt-6 space-y-2">
            <div className="text-sm text-white/70 mb-1">
              총 <b className="text-white">{items.length}</b>건
            </div>
            {items.map((m) => {
              const isOpen = openId === m.talent_media_id;
              const scenes = scenesById[m.talent_media_id];
              return (
                <div
                  key={m.talent_media_id}
                  className="rounded-xl border border-white/15 bg-white/5 backdrop-blur-md overflow-hidden"
                >
                  <button
                    type="button"
                    onClick={() => toggleScenes(m.talent_media_id)}
                    className="w-full text-left px-4 py-3 flex items-center gap-3 hover:bg-white/5 transition-colors"
                  >
                    <ChevronDown
                      className={
                        "w-4 h-4 text-white/50 shrink-0 transition-transform " +
                        (isOpen ? "rotate-180" : "")
                      }
                    />
                    <span className="text-amber-100 font-semibold shrink-0">
                      #{m.talent_media_id}
                    </span>
                    <span className="text-white font-medium shrink-0">
                      {m.account_name}
                    </span>
                    <span className="text-white/60 text-sm truncate">
                      {m.ai_summary ||
                        m.original_file_name ||
                        "(요약 없음)"}
                    </span>
                    <span className="ml-auto text-[11px] text-white/40 shrink-0">
                      {new Date(m.created_at).toLocaleDateString("ko-KR")}
                    </span>
                  </button>

                  {isOpen && (
                    <div className="border-t border-white/10 px-4 py-3 bg-black/20">
                      {scenesLoading === m.talent_media_id ? (
                        <div className="flex items-center gap-2 text-white/60 text-sm py-3">
                          <Loader2 className="w-4 h-4 animate-spin" />
                          scene 불러오는 중…
                        </div>
                      ) : !scenes || scenes.length === 0 ? (
                        <div className="text-white/50 text-sm py-2">
                          적재된 scene 이 없습니다.
                        </div>
                      ) : (
                        <div className="space-y-2">
                          <div className="text-xs text-white/50">
                            scene {scenes.length}개
                          </div>
                          {scenes.map((s) => {
                            const p = s.payload || {};
                            const keywords = Array.isArray(p.search_keywords)
                              ? (p.search_keywords as string[])
                              : [];
                            return (
                              <details
                                key={s.id}
                                className="rounded-lg border border-white/10 bg-white/5"
                              >
                                <summary className="cursor-pointer px-3 py-2 text-sm text-white/90 hover:bg-white/5">
                                  {(p.scene_id as string) ?? `point ${s.id}`}
                                  {typeof p.scene_summary === "string" && (
                                    <span className="ml-2 text-white/60 font-normal">
                                      {(p.scene_summary as string).slice(0, 50)}…
                                    </span>
                                  )}
                                </summary>
                                <div className="px-3 pb-3 space-y-2">
                                  {keywords.length > 0 && (
                                    <div className="flex flex-wrap gap-1.5">
                                      {keywords.map((k) => (
                                        <span
                                          key={k}
                                          className="px-2 py-0.5 rounded-full bg-emerald-400/20 text-emerald-100 text-[11px]"
                                        >
                                          {k}
                                        </span>
                                      ))}
                                    </div>
                                  )}
                                  <pre className="text-[11px] leading-relaxed bg-black/40 text-zinc-100 rounded-lg p-3 overflow-x-auto whitespace-pre-wrap break-words">
                                    {JSON.stringify(p, null, 2)}
                                  </pre>
                                </div>
                              </details>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
