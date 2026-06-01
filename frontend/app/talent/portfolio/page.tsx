"use client";

import Image from "next/image";
import { useCallback, useEffect, useState } from "react";
import { Film, Loader2, Play, Trash2, Upload } from "lucide-react";

import DashboardHeader from "@/components/DashboardHeader";
import { useDashboardGuard } from "@/components/DashboardGuard";
import VideoAnalysisModal from "@/components/VideoAnalysisModal";
import VideoPlayerModal from "@/components/VideoPlayerModal";
import { api } from "@/lib/api";
import { useAuth } from "@/store/auth";

type MediaItem = {
  talent_media_id: number;
  media_type: string; // PHOTO / MOVIE
  title?: string | null;
  original_file_name?: string | null;
  ai_summary?: string | null;
  created_at: string;
  view_count: number;
  is_main: boolean;
  stream_url: string;
};

export default function TalentPortfolioPage() {
  const ready = useDashboardGuard("TALENT");
  const account = useAuth((s) => s.account);
  const [analyzeOpen, setAnalyzeOpen] = useState(false);

  const [media, setMedia] = useState<MediaItem[]>([]);
  const [loadingMedia, setLoadingMedia] = useState(true);

  // 재생 모달
  const [player, setPlayer] = useState<{ src: string; title: string | null } | null>(
    null,
  );

  const fetchMedia = useCallback(async () => {
    setLoadingMedia(true);
    try {
      const res = await api.get<{ items: MediaItem[]; total: number }>(
        "/talent/me/media",
      );
      setMedia(res.data.items);
    } catch {
      setMedia([]);
    } finally {
      setLoadingMedia(false);
    }
  }, []);

  useEffect(() => {
    if (ready && account) fetchMedia();
  }, [ready, account, fetchMedia]);

  const handleDelete = useCallback(async (m: MediaItem) => {
    const name =
      m.title || m.original_file_name || `영상 #${m.talent_media_id}`;
    if (
      !window.confirm(
        `'${name}' 영상을 삭제할까요?\n분석 데이터(RAG·검색 색인)도 함께 삭제되며 되돌릴 수 없습니다.`,
      )
    )
      return;
    try {
      await api.delete(`/talent/me/media/${m.talent_media_id}`);
      setMedia((prev) =>
        prev.filter((x) => x.talent_media_id !== m.talent_media_id),
      );
    } catch {
      alert("삭제에 실패했습니다. 잠시 후 다시 시도해 주세요.");
    }
  }, []);

  if (!ready || !account) return null;

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
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-white drop-shadow-lg">
              포트폴리오
            </h1>
            <p className="mt-1 text-zinc-200 drop-shadow">
              영상을 올리면 AI 가 분석해 매칭에 사용합니다.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setAnalyzeOpen(true)}
            className="inline-flex items-center gap-2 rounded-full bg-amber-100 text-zinc-900 px-5 py-2.5 text-sm font-semibold hover:bg-amber-200 transition-colors shadow"
          >
            <Upload className="w-4 h-4" />
            영상 올리기
          </button>
        </div>

        {/* 미디어 목록 */}
        {loadingMedia ? (
          <div className="flex items-center justify-center gap-2 py-20 text-white/70 drop-shadow">
            <Loader2 className="w-5 h-5 animate-spin" />
            목록을 불러오는 중…
          </div>
        ) : media.length === 0 ? (
          <div className="rounded-xl border border-white/15 bg-white/5 backdrop-blur-md p-10 text-center text-white/80 drop-shadow">
            아직 올린 영상이 없습니다.
            <br />
            <b className="text-amber-100">영상 올리기</b> 버튼으로 첫 영상을
            업로드해 보세요.
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {media.map((m) => (
              <div
                key={m.talent_media_id}
                className="group relative rounded-xl border border-white/15 bg-white/5 backdrop-blur-md overflow-hidden hover:bg-white/10 hover:border-white/30 hover:shadow-2xl transition-colors"
              >
                {/* 삭제 버튼 (재생 영역과 분리) */}
                <button
                  type="button"
                  onClick={() => handleDelete(m)}
                  aria-label="영상 삭제"
                  className="absolute top-2 right-2 z-10 rounded-full p-1.5 bg-black/50 text-white/80 opacity-0 group-hover:opacity-100 hover:bg-red-600 hover:text-white transition-all"
                >
                  <Trash2 className="w-4 h-4" />
                </button>

                {/* 재생 영역 */}
                <button
                  type="button"
                  onClick={() =>
                    setPlayer({
                      src: m.stream_url,
                      title: m.title || m.original_file_name || null,
                    })
                  }
                  className="block w-full text-left"
                >
                  <div className="relative aspect-video bg-black/40 flex items-center justify-center">
                    <Film
                      className="w-10 h-10 text-white/40"
                      strokeWidth={1.5}
                    />
                    <div className="absolute inset-0 flex items-center justify-center bg-black/0 group-hover:bg-black/30 transition-colors">
                      <Play className="w-12 h-12 text-white opacity-0 group-hover:opacity-100 drop-shadow transition-opacity" />
                    </div>
                    {m.is_main && (
                      <span className="absolute top-2 left-2 rounded-full bg-amber-100 text-zinc-900 text-[10px] font-bold px-2 py-0.5">
                        대표
                      </span>
                    )}
                  </div>
                  <div className="p-3">
                    <div className="text-sm font-semibold text-white truncate drop-shadow">
                      {m.title ||
                        m.original_file_name ||
                        `영상 #${m.talent_media_id}`}
                    </div>
                    {m.ai_summary && (
                      <p className="mt-1.5 text-xs leading-relaxed text-white/75 line-clamp-2 drop-shadow">
                        {m.ai_summary}
                      </p>
                    )}
                    <div className="mt-2 text-[11px] text-white/60">
                      조회 {m.view_count} ·{" "}
                      {new Date(m.created_at).toLocaleDateString("ko-KR")}
                    </div>
                  </div>
                </button>
              </div>
            ))}
          </div>
        )}
      </main>

      <VideoAnalysisModal
        open={analyzeOpen}
        onClose={() => {
          setAnalyzeOpen(false);
          // 업로드/분석 후 목록 갱신
          fetchMedia();
        }}
      />

      <VideoPlayerModal
        open={player !== null}
        onClose={() => setPlayer(null)}
        src={player?.src ?? null}
        title={player?.title ?? null}
      />
    </div>
  );
}
