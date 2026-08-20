"use client";

import { useCallback, useEffect, useState } from "react";
import { Film, Loader2, Play, Trash2, Upload } from "lucide-react";

import VideoAnalysisModal from "@/components/VideoAnalysisModal";
import VideoPlayerModal from "@/components/VideoPlayerModal";
import { api } from "@/lib/api";

type MediaItem = {
  talent_media_id: number;
  media_type: string;
  title?: string | null;
  original_file_name?: string | null;
  ai_summary?: string | null;
  created_at: string;
  view_count: number;
  is_main: boolean;
  stream_url: string;
  /** 영상 포스터 키. 값이 있으면 /api/media/{id}/thumbnail 로 받을 수 있다 */
  thumbnail_path?: string | null;
};

/**
 * 영상 카드의 포스터.
 *
 * 분석 때 뽑아 둔 대표 프레임(얼굴이 가장 잘 잡힌 장면)을 640px WebP 로 받는다.
 * 포스터가 아직 없는 영상이나 로드 실패 시에는 필름 아이콘으로 폴백한다 —
 * 카드 레이아웃이 흔들리지 않도록 자리는 그대로 차지한다.
 */
function Poster({
  mediaId,
  hasThumb,
  iconCls,
}: {
  mediaId: number;
  hasThumb: boolean;
  iconCls: string;
}) {
  const [failed, setFailed] = useState(false);

  if (!hasThumb || failed) {
    return <Film className={iconCls} strokeWidth={1.5} />;
  }
  return (
    <img
      src={`/api/media/${mediaId}/thumbnail`}
      alt=""
      loading="lazy"
      decoding="async"
      className="absolute inset-0 w-full h-full object-cover"
      onError={() => setFailed(true)}
    />
  );
}

// 아티스트당 등록 가능한 영상 수 (관리자 대행 업로드에 적용)
const ADMIN_MAX = 10;

type Variant = "dark" | "light";

/**
 * 영상(포트폴리오) 목록·업로드·재생 패널. 페이지 크롬 없이 콘텐츠만 렌더.
 * - dark: 어두운 배경 페이지(PortfolioView)용
 * - light: 흰 배경 모달(프로필 모달의 '동영상' 탭)용
 * accountId 가 있으면 관리자 대행(최대 5개), 없으면 본인.
 */
export default function PortfolioPanel({
  accountId,
  variant = "dark",
}: {
  accountId?: number;
  variant?: Variant;
}) {
  const isProxy = accountId != null;
  const listUrl = isProxy
    ? `/admin/talents/${accountId}/media`
    : "/talent/me/media";
  const light = variant === "light";

  const [media, setMedia] = useState<MediaItem[]>([]);
  const [loadingMedia, setLoadingMedia] = useState(true);
  const [analyzeOpen, setAnalyzeOpen] = useState(false);
  const [player, setPlayer] = useState<{
    src: string;
    title: string | null;
    summary: string | null;
  } | null>(
    null,
  );

  const fetchMedia = useCallback(async () => {
    setLoadingMedia(true);
    try {
      const res = await api.get<{ items: MediaItem[]; total: number }>(listUrl);
      setMedia(res.data.items);
    } catch {
      setMedia([]);
    } finally {
      setLoadingMedia(false);
    }
  }, [listUrl]);

  useEffect(() => {
    fetchMedia();
  }, [fetchMedia]);

  const handleDelete = useCallback(
    async (m: MediaItem) => {
      const name =
        m.title || m.original_file_name || `영상 #${m.talent_media_id}`;
      if (
        !window.confirm(
          `'${name}' 영상을 삭제할까요?\n분석 데이터(RAG·검색 색인)도 함께 삭제되며 되돌릴 수 없습니다.`,
        )
      )
        return;
      const url = isProxy
        ? `/admin/talents/${accountId}/media/${m.talent_media_id}`
        : `/talent/me/media/${m.talent_media_id}`;
      try {
        await api.delete(url);
        setMedia((prev) =>
          prev.filter((x) => x.talent_media_id !== m.talent_media_id),
        );
      } catch {
        alert("삭제에 실패했습니다. 잠시 후 다시 시도해 주세요.");
      }
    },
    [isProxy, accountId],
  );

  const limitReached = isProxy && media.length >= ADMIN_MAX;

  // variant 별 클래스
  const descCls = light ? "text-zinc-500" : "text-zinc-200 drop-shadow";
  const cardCls = light
    ? "group relative rounded-xl border border-zinc-200 bg-white overflow-hidden hover:border-zinc-300 hover:shadow-lg transition-all"
    : "group relative rounded-xl border border-white/15 bg-white/5 backdrop-blur-md overflow-hidden hover:bg-white/10 hover:border-white/30 hover:shadow-2xl transition-colors";
  const thumbCls = light
    ? "relative aspect-video bg-zinc-100 flex items-center justify-center"
    : "relative aspect-video bg-black/40 flex items-center justify-center";
  const filmCls = light ? "w-10 h-10 text-zinc-300" : "w-10 h-10 text-white/40";
  const titleTextCls = light
    ? "text-sm font-semibold text-zinc-900 truncate"
    : "text-sm font-semibold text-white truncate drop-shadow";
  // 기본 2줄 → 카드 hover 시 전체 표시.
  // ai_summary 는 scene 요약을 이어붙인 것이라 수천 자에 달할 수 있어,
  // 최대 높이를 두고 그 안에서 스크롤하게 한다 (카드가 무한정 길어지는 것을 방지).
  const summaryCls = light
    ? "mt-1.5 text-xs leading-relaxed text-zinc-600 select-text cursor-text line-clamp-2 group-hover:line-clamp-none group-hover:max-h-48 group-hover:overflow-y-auto group-hover:pr-1"
    : "mt-1.5 text-xs leading-relaxed text-white/75 select-text cursor-text line-clamp-2 drop-shadow group-hover:line-clamp-none group-hover:max-h-48 group-hover:overflow-y-auto group-hover:pr-1";
  const metaCls = light ? "mt-2 text-[11px] text-zinc-400" : "mt-2 text-[11px] text-white/60";
  const emptyCls = light
    ? "rounded-xl border border-zinc-200 bg-zinc-50 p-10 text-center text-zinc-500"
    : "rounded-xl border border-white/15 bg-white/5 backdrop-blur-md p-10 text-center text-white/80 drop-shadow";
  const loadingCls = light
    ? "flex items-center justify-center gap-2 py-16 text-zinc-500"
    : "flex items-center justify-center gap-2 py-20 text-white/70 drop-shadow";

  return (
    <div>
      <div className="flex items-center justify-between mb-5">
        <p className={"text-sm " + descCls}>
          {isProxy
            ? `영상을 올리면 AI 가 분석해 매칭에 사용합니다. (최대 ${ADMIN_MAX}개 · 현재 ${media.length}개)`
            : "영상을 올리면 AI 가 분석해 매칭에 사용합니다."}
        </p>
        <button
          type="button"
          onClick={() => setAnalyzeOpen(true)}
          disabled={limitReached}
          title={limitReached ? `최대 ${ADMIN_MAX}개까지 등록 가능합니다.` : ""}
          className={
            light
              ? "inline-flex items-center gap-2 rounded-lg bg-zinc-900 text-white px-4 py-2 text-sm font-semibold hover:bg-zinc-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed shrink-0"
              : "inline-flex items-center gap-2 rounded-full bg-amber-100 text-zinc-900 px-5 py-2.5 text-sm font-semibold hover:bg-amber-200 transition-colors shadow disabled:opacity-50 disabled:cursor-not-allowed shrink-0"
          }
        >
          <Upload className="w-4 h-4" />
          영상 올리기
        </button>
      </div>

      {loadingMedia ? (
        <div className={loadingCls}>
          <Loader2 className="w-5 h-5 animate-spin" />
          목록을 불러오는 중…
        </div>
      ) : media.length === 0 ? (
        <div className={emptyCls}>
          아직 올린 영상이 없습니다.
          <br />
          <b className={light ? "text-zinc-900" : "text-amber-100"}>영상 올리기</b>{" "}
          버튼으로 첫 영상을 업로드해 보세요.
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {media.map((m) => (
            <div key={m.talent_media_id} className={cardCls}>
              <button
                type="button"
                onClick={() => handleDelete(m)}
                aria-label="영상 삭제"
                className="absolute top-2 right-2 z-10 rounded-full p-1.5 bg-black/50 text-white/80 opacity-0 group-hover:opacity-100 hover:bg-red-600 hover:text-white transition-all"
              >
                <Trash2 className="w-4 h-4" />
              </button>

              <button
                type="button"
                onClick={() =>
                  setPlayer({
                    src: m.stream_url,
                    title: m.title || m.original_file_name || null,
                    summary: m.ai_summary ?? null,
                  })
                }
                className="block w-full text-left"
              >
                <div className={thumbCls}>
                  <Poster
                    mediaId={m.talent_media_id}
                    hasThumb={Boolean(m.thumbnail_path)}
                    iconCls={filmCls}
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
                <div className="px-3 pt-3">
                  <div className={titleTextCls}>
                    {m.title ||
                      m.original_file_name ||
                      `영상 #${m.talent_media_id}`}
                  </div>
                </div>
              </button>

              {/* 요약·메타는 재생 버튼 밖에 둔다 —
                  button 안에 있으면 브라우저가 드래그를 버튼 조작으로 처리해
                  텍스트를 선택·복사할 수 없다. */}
              <div className="px-3 pb-3">
                {m.ai_summary && <p className={summaryCls}>{m.ai_summary}</p>}
                <div className={metaCls}>
                  조회 {m.view_count} ·{" "}
                  {new Date(m.created_at).toLocaleDateString("ko-KR")}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <VideoAnalysisModal
        open={analyzeOpen}
        onClose={() => {
          setAnalyzeOpen(false);
          fetchMedia();
        }}
        accountId={accountId}
      />

      <VideoPlayerModal
        open={player !== null}
        onClose={() => setPlayer(null)}
        src={player?.src ?? null}
        title={player?.title ?? null}
        summary={player?.summary ?? null}
      />
    </div>
  );
}
