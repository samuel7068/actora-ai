"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Film, Loader2, Play, Upload, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { tokenStorage } from "@/lib/api";

type Props = {
  open: boolean;
  onClose: () => void;
  /** 관리자 대행 업로드 시 대상 인재 account_id. 없으면 본인 업로드. */
  accountId?: number;
};

const SUMMARY_TAB_KEY = "__summary__";

type Stage = {
  stage: string;
  label: string;
  success: boolean;
  elapsed_ms: number;
  data?: unknown;
  error?: string | null;
};

type AnalyzeResponse = {
  job_id: string;
  original_filename: string;
  upload_size_bytes: number;
  total_elapsed_ms: number;
  stages: Stage[];
  talent_media_id?: number | null;
  persisted_path?: string | null;
  persisted_size_bytes?: number | null;
  rag_scenes?: Record<string, unknown>[] | null;
};

/** 분석 중 서버가 NDJSON 으로 흘려보내는 진행 이벤트 */
type ProgressEvent =
  | {
      type: "stage";
      stage: string;
      label: string;
      success: boolean;
      elapsed_ms: number;
      error?: string | null;
    }
  | {
      type: "scene_start";
      index: number;
      total: number;
      scene_id: string;
      start_sec?: number | null;
      end_sec?: number | null;
    }
  | {
      type: "scene";
      index: number;
      total: number;
      scene_id: string;
      start_sec?: number | null;
      end_sec?: number | null;
      summary?: string | null;
      target_identified?: boolean | null;
      target_similarity?: number | null;
      error?: string;
    }
  | { type: "start" }
  // 프록시가 연결을 끊지 않도록 서버가 주기적으로 보내는 신호 (내용 없음)
  | { type: "ping" }
  | { type: "summary"; summary: string }
  | { type: "result"; result: AnalyzeResponse }
  | { type: "error"; error: string; status?: number };

/** 진행 화면에 쌓이는 한 줄 */
type FeedItem = {
  id: string;
  kind: "stage" | "scene" | "summary";
  title: string;
  body?: string | null;
  ok?: boolean;
  meta?: string;
};

const fmtSec = (v?: number | null) =>
  typeof v === "number" ? v.toFixed(1) : "?";

export default function VideoAnalysisModal({ open, onClose, accountId }: Props) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [activeStage, setActiveStage] = useState<string>("");
  // 스트리밍 진행 상황
  const [feed, setFeed] = useState<FeedItem[]>([]);
  const [current, setCurrent] = useState<string>("");
  const feedEndRef = useRef<HTMLDivElement>(null);
  const startedAtRef = useRef<number>(0);

  // 모달 닫힐 때 상태 정리
  useEffect(() => {
    if (open) return;
    // unmount 시 blob URL revoke
    if (videoUrl) URL.revokeObjectURL(videoUrl);
    setVideoFile(null);
    setVideoUrl(null);
    setResult(null);
    setErr(null);
    setActiveStage("");
    setFeed([]);
    setCurrent("");
  }, [open, videoUrl]);

  // 새 항목이 쌓이면 맨 아래로 따라 내려간다
  useEffect(() => {
    if (feed.length) {
      feedEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  }, [feed]);

  // ESC 닫기
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !analyzing) onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, analyzing, onClose]);

  const onPickFile = (f: File | null) => {
    if (!f) return;
    if (!f.type.startsWith("video/")) {
      setErr("비디오 파일만 업로드 가능합니다.");
      return;
    }
    setErr(null);
    setResult(null);
    if (videoUrl) URL.revokeObjectURL(videoUrl);
    setVideoFile(f);
    setVideoUrl(URL.createObjectURL(f));
  };

  const handleEvent = (ev: ProgressEvent) => {
    switch (ev.type) {
      case "start":
        setCurrent("영상 업로드 완료 — 분석을 시작합니다");
        break;
      case "ping": {
        // 오래 걸리는 단계에서도 살아 있다는 걸 보여준다
        const sec = Math.round((Date.now() - startedAtRef.current) / 1000);
        setCurrent((c) => `${c.replace(/ \(\d+초 경과\)$/, "")} (${sec}초 경과)`);
        break;
      }
      case "stage":
        setFeed((f) => [
          ...f,
          {
            id: `stage-${ev.stage}-${f.length}`,
            kind: "stage",
            title: ev.label,
            body: ev.error ?? null,
            ok: ev.success,
            meta: `${(ev.elapsed_ms / 1000).toFixed(1)}s`,
          },
        ]);
        setCurrent(`${ev.label} 완료`);
        break;
      case "scene_start":
        setCurrent(`장면 분석 ${ev.index}/${ev.total} · ${ev.scene_id}`);
        break;
      case "scene":
        setFeed((f) => [
          ...f,
          {
            id: `scene-${ev.scene_id}-${f.length}`,
            kind: "scene",
            title: `${ev.scene_id} · ${fmtSec(ev.start_sec)}~${fmtSec(ev.end_sec)}초 (${ev.index}/${ev.total})`,
            body: ev.error ?? ev.summary ?? null,
            ok: !ev.error,
            meta:
              ev.target_identified === false
                ? "인재 미확인"
                : typeof ev.target_similarity === "number"
                  ? `얼굴 일치 ${ev.target_similarity.toFixed(2)}`
                  : undefined,
          },
        ]);
        break;
      case "summary":
        setFeed((f) => [
          ...f,
          {
            id: "summary",
            kind: "summary",
            title: `영상 대표 요약 (${ev.summary.length}자)`,
            body: ev.summary,
            ok: true,
          },
        ]);
        setCurrent("대표 요약 생성 완료");
        break;
      case "result":
        setResult(ev.result);
        if (ev.result.stages.length) setActiveStage(ev.result.stages[0].stage);
        break;
      case "error":
        setErr(ev.error || "분석 실패 (서버 오류)");
        break;
    }
  };

  const onAnalyze = async () => {
    if (!videoFile) return;
    setAnalyzing(true);
    setErr(null);
    setResult(null);
    setFeed([]);
    setCurrent("영상 업로드 중…");
    startedAtRef.current = Date.now();
    try {
      const form = new FormData();
      form.append("file", videoFile);
      if (accountId != null) form.append("account_id", String(accountId));

      const token = tokenStorage.get();
      const res = await fetch("/api/talent/portfolio/analyze-stream", {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
        body: form,
      });
      if (!res.ok || !res.body) {
        throw new Error(`분석 요청 실패 (HTTP ${res.status})`);
      }

      // NDJSON — 줄 단위로 끊어 읽는다. 마지막 조각은 다음 청크와 이어 붙인다.
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";
        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            handleEvent(JSON.parse(line) as ProgressEvent);
          } catch {
            // 깨진 줄은 건너뛴다 — 스트림 전체를 중단시키지 않는다
          }
        }
      }
      if (buffer.trim()) {
        try {
          handleEvent(JSON.parse(buffer) as ProgressEvent);
        } catch {
          /* noop */
        }
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : "분석 실패 (서버 오류)");
    } finally {
      setAnalyzing(false);
      setCurrent("");
    }
  };

  const activeStageData = useMemo(
    () => result?.stages.find((s) => s.stage === activeStage) ?? null,
    [result, activeStage],
  );

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center px-4 py-6"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={() => !analyzing && onClose()}
        >
          <motion.div
            initial={{ opacity: 0, y: 24, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 24, scale: 0.96 }}
            transition={{ duration: 0.22, ease: "easeOut" }}
            onClick={(e) => e.stopPropagation()}
            className="relative w-full max-w-7xl h-[92vh] flex flex-col rounded-2xl bg-white shadow-2xl overflow-hidden"
          >
            {/* Header */}
            <div className="flex items-center justify-between border-b border-zinc-200 px-6 py-4 bg-zinc-50">
              <div className="flex items-center gap-2">
                <Film className="w-5 h-5 text-zinc-700" />
                <h2 className="text-lg font-bold text-zinc-900">
                  AI 영상 분석
                </h2>
                {result && (
                  <>
                    <span className="ml-2 text-xs text-zinc-500">
                      총 {(result.total_elapsed_ms / 1000).toFixed(1)}s
                    </span>
                    {result.talent_media_id && (
                      <span className="ml-2 text-xs font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 rounded px-2 py-0.5">
                        저장됨 · media_id={result.talent_media_id}
                      </span>
                    )}
                  </>
                )}
              </div>
              <button
                type="button"
                onClick={onClose}
                disabled={analyzing}
                aria-label="닫기"
                className="rounded-full p-1.5 text-zinc-500 hover:bg-zinc-200 disabled:opacity-50"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Body — 좌/우 분할 */}
            <div className="flex-1 grid grid-cols-1 lg:grid-cols-[minmax(320px,420px)_1fr] overflow-hidden">
              {/* 좌: 영상 업로드 + 미리보기 */}
              <div className="border-r border-zinc-200 flex flex-col overflow-y-auto p-4 gap-3 bg-zinc-50">
                <div className="text-xs font-semibold text-zinc-600">
                  1. 영상 선택
                </div>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="video/*"
                  className="hidden"
                  onChange={(e) => onPickFile(e.target.files?.[0] ?? null)}
                />
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={analyzing}
                  className="rounded-lg border-2 border-dashed border-zinc-300 hover:border-zinc-500 hover:bg-white transition-colors py-8 text-zinc-500 text-sm flex flex-col items-center gap-1.5 disabled:opacity-50"
                >
                  <Upload className="w-6 h-6" />
                  {videoFile ? "다른 영상 선택" : "비디오 파일 선택"}
                </button>

                {videoFile && (
                  <div className="text-[11px] text-zinc-600 bg-white border border-zinc-200 rounded-lg p-2">
                    <div className="font-medium text-zinc-900 truncate">
                      {videoFile.name}
                    </div>
                    <div className="text-zinc-500 mt-0.5">
                      {(videoFile.size / 1024 / 1024).toFixed(2)} MB ·{" "}
                      {videoFile.type}
                    </div>
                  </div>
                )}

                {videoUrl && (
                  <video
                    src={videoUrl}
                    controls
                    className="w-full rounded-lg bg-black"
                  />
                )}

                <div className="text-xs font-semibold text-zinc-600 mt-2">
                  2. 분석 실행
                </div>
                <button
                  type="button"
                  onClick={onAnalyze}
                  disabled={!videoFile || analyzing}
                  className={
                    "rounded-lg py-2.5 text-sm font-semibold inline-flex items-center justify-center gap-2 transition-colors " +
                    (!videoFile || analyzing
                      ? "bg-zinc-200 text-zinc-400 cursor-not-allowed"
                      : "bg-zinc-900 text-white hover:bg-zinc-800")
                  }
                >
                  {analyzing ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      분석중…
                    </>
                  ) : (
                    <>
                      <Play className="w-4 h-4" />
                      분석 시작
                    </>
                  )}
                </button>

                {err && (
                  <div className="rounded-lg bg-red-50 border border-red-200 text-red-700 text-xs px-3 py-2 whitespace-pre-wrap break-words">
                    {err}
                  </div>
                )}
              </div>

              {/* 우: 디버그 결과 */}
              <div className="flex flex-col overflow-hidden">
                {!result && !analyzing && (
                  <div className="flex-1 flex items-center justify-center text-zinc-400 text-sm p-10 text-center">
                    좌측에서 영상을 선택하고 <b className="mx-1 text-zinc-600">분석 시작</b> 을 누르면
                    <br />
                    AI 가 영상을 분석한 결과가 여기에 표시됩니다.
                  </div>
                )}

                {analyzing && (
                  <div className="flex-1 flex flex-col overflow-hidden">
                    {/* 현재 진행 중인 작업 */}
                    <div className="shrink-0 flex items-center gap-2 px-4 py-3 border-b border-zinc-200 bg-white">
                      <Loader2 className="w-4 h-4 animate-spin text-zinc-500 shrink-0" />
                      <span className="text-sm text-zinc-600 truncate">
                        {current || "분석 진행 중…"}
                      </span>
                    </div>

                    {/* 분석되는 내용이 한 줄씩 쌓인다 */}
                    <div className="flex-1 overflow-y-auto px-4 py-3 space-y-2">
                      {feed.length === 0 && (
                        <div className="text-sm text-zinc-400">
                          영상을 업로드하고 분석을 준비하는 중입니다…
                        </div>
                      )}

                      {feed.map((it) => {
                        if (it.kind === "stage") {
                          return (
                            <div
                              key={it.id}
                              className="flex items-center gap-2 text-xs text-zinc-500"
                            >
                              <span
                                className={
                                  it.ok
                                    ? "shrink-0 w-1.5 h-1.5 rounded-full bg-emerald-500"
                                    : "shrink-0 w-1.5 h-1.5 rounded-full bg-red-500"
                                }
                              />
                              <span className="font-medium text-zinc-700">
                                {it.title}
                              </span>
                              {it.meta && <span>· {it.meta}</span>}
                              {it.body && (
                                <span className="text-red-500 truncate">
                                  {it.body}
                                </span>
                              )}
                            </div>
                          );
                        }

                        if (it.kind === "summary") {
                          return (
                            <div
                              key={it.id}
                              className="rounded-lg border border-amber-200 bg-amber-50 p-3"
                            >
                              <div className="text-xs font-semibold text-amber-700 mb-1">
                                {it.title}
                              </div>
                              <p className="text-sm leading-relaxed text-zinc-800">
                                {it.body}
                              </p>
                            </div>
                          );
                        }

                        // scene — 분석된 문장이 흐르는 본체
                        return (
                          <div
                            key={it.id}
                            className="rounded-lg border border-zinc-200 bg-white p-3"
                          >
                            <div className="flex items-center gap-2 mb-1">
                              <span className="text-[11px] font-medium text-zinc-500">
                                {it.title}
                              </span>
                              {it.meta && (
                                <span
                                  className={
                                    it.meta === "인재 미확인"
                                      ? "text-[10px] px-1.5 py-0.5 rounded-full bg-zinc-100 text-zinc-500"
                                      : "text-[10px] px-1.5 py-0.5 rounded-full bg-emerald-50 text-emerald-700"
                                  }
                                >
                                  {it.meta}
                                </span>
                              )}
                            </div>
                            <p
                              className={
                                it.ok
                                  ? "text-sm leading-relaxed text-zinc-700"
                                  : "text-sm leading-relaxed text-red-500"
                              }
                            >
                              {it.body || "(요약 없음)"}
                            </p>
                          </div>
                        );
                      })}
                      <div ref={feedEndRef} />
                    </div>
                  </div>
                )}

                {result && (
                  <>
                    {/* Stage tabs (+ 전체 요약 가상 탭) */}
                    <div className="flex border-b border-zinc-200 bg-white overflow-x-auto shrink-0">
                      {result.stages.map((s) => {
                        const isActive = s.stage === activeStage;
                        return (
                          <button
                            key={s.stage}
                            type="button"
                            onClick={() => setActiveStage(s.stage)}
                            className={
                              "px-4 py-3 text-xs font-medium whitespace-nowrap border-b-2 transition-colors flex items-center gap-1.5 " +
                              (isActive
                                ? "border-zinc-900 text-zinc-900"
                                : "border-transparent text-zinc-500 hover:text-zinc-800")
                            }
                          >
                            <span
                              className={
                                "w-1.5 h-1.5 rounded-full " +
                                (s.success ? "bg-green-500" : "bg-red-500")
                              }
                            />
                            {s.label}
                            <span className="text-[10px] text-zinc-400 ml-1">
                              {(s.elapsed_ms / 1000).toFixed(1)}s
                            </span>
                          </button>
                        );
                      })}
                      {/* 전체 요약 — 가상 탭 (rag_scenes 집계) */}
                      {result.rag_scenes && result.rag_scenes.length > 0 && (
                        <button
                          type="button"
                          onClick={() => setActiveStage(SUMMARY_TAB_KEY)}
                          className={
                            "px-4 py-3 text-xs font-medium whitespace-nowrap border-b-2 transition-colors flex items-center gap-1.5 " +
                            (activeStage === SUMMARY_TAB_KEY
                              ? "border-amber-600 text-amber-700"
                              : "border-transparent text-zinc-500 hover:text-zinc-800")
                          }
                        >
                          <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
                          전체 요약
                        </button>
                      )}
                    </div>

                    <div className="flex-1 overflow-y-auto p-4">
                      {activeStage === SUMMARY_TAB_KEY ? (
                        <OverallSummaryView
                          scenes={result.rag_scenes ?? []}
                          totalDurationSec={
                            (result.rag_scenes ?? []).reduce(
                              (acc, s) =>
                                acc +
                                (typeof s.scene_end_sec === "number" &&
                                typeof s.scene_start_sec === "number"
                                  ? (s.scene_end_sec as number) -
                                    (s.scene_start_sec as number)
                                  : 0),
                              0,
                            )
                          }
                        />
                      ) : (
                        activeStageData && (
                          <StageResultView
                            stage={activeStageData}
                            ragScenes={result.rag_scenes ?? null}
                          />
                        )
                      )}
                    </div>
                  </>
                )}
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function StageResultView({
  stage,
  ragScenes,
}: {
  stage: Stage;
  ragScenes?: Record<string, unknown>[] | null;
}) {
  // RAG JSON 탭 — 항상(성공/실패 무관) scene JSON 표시
  if (stage.stage === "rag_json") {
    const meta = stage.data as
      | { scene_count?: number; rag_file_path?: string; errors?: string[] }
      | undefined;
    return (
      <div className="space-y-3">
        {stage.error && (
          <div className="rounded-lg bg-red-50 border border-red-200 text-red-700 text-xs px-3 py-2 whitespace-pre-wrap break-words">
            {stage.error}
          </div>
        )}
        {meta?.rag_file_path && (
          <div className="text-xs text-zinc-600">
            저장 파일:{" "}
            <code className="font-mono text-zinc-900 bg-zinc-100 px-1.5 py-0.5 rounded">
              {meta.rag_file_path}
            </code>
            {typeof meta.scene_count === "number" && (
              <span className="ml-2 text-zinc-500">
                · scene {meta.scene_count}개
              </span>
            )}
          </div>
        )}
        {ragScenes && ragScenes.length > 0 ? (
          <div className="space-y-2">
            {ragScenes.map((s, i) => (
              <details
                key={i}
                className="rounded-lg border border-zinc-200 bg-white"
                open={i === 0}
              >
                <summary className="cursor-pointer px-3 py-2 text-xs font-semibold text-zinc-900 hover:bg-zinc-50">
                  {(s.scene_id as string) ?? `scene_${i + 1}`}
                  {typeof s.scene_start_sec === "number" &&
                    typeof s.scene_end_sec === "number" && (
                      <span className="ml-2 text-zinc-500 font-normal">
                        {(s.scene_start_sec as number).toFixed(2)}–
                        {(s.scene_end_sec as number).toFixed(2)}s
                      </span>
                    )}
                  {Array.isArray(s.search_keywords) && (
                    <span className="ml-2 text-emerald-700 font-normal">
                      [{(s.search_keywords as string[]).join(", ")}]
                    </span>
                  )}
                </summary>
                <div className="px-3 pb-3">
                  <JsonView data={s} />
                </div>
              </details>
            ))}
          </div>
        ) : (
          <div className="text-xs text-zinc-400">RAG scenes 없음</div>
        )}
      </div>
    );
  }

  if (!stage.success) {
    return (
      <div className="space-y-3">
        <div className="rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3">
          <div className="font-semibold mb-1">실패</div>
          <div className="text-xs whitespace-pre-wrap break-words">
            {stage.error ?? "(no error detail)"}
          </div>
        </div>
        {stage.data ? <JsonView data={stage.data} /> : null}
      </div>
    );
  }

  // keyframes 단계 — 썸네일 + JSON
  if (stage.stage === "keyframes" && stage.data) {
    const d = stage.data as {
      count: number;
      frames: {
        scene_id: string;
        timestamp_sec: number;
        width: number;
        height: number;
        thumbnail_data_uri: string;
      }[];
    };
    return (
      <div className="space-y-4">
        <div className="text-xs text-zinc-600">
          <b>{d.count}</b>개 키프레임 추출됨
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
          {d.frames.map((f) => (
            <div
              key={f.scene_id}
              className="rounded-lg overflow-hidden border border-zinc-200 bg-zinc-50"
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={f.thumbnail_data_uri}
                alt={f.scene_id}
                className="w-full h-auto"
              />
              <div className="px-2 py-1.5 text-[11px]">
                <div className="font-semibold text-zinc-900">
                  {f.scene_id}
                </div>
                <div className="text-zinc-500">
                  {f.timestamp_sec.toFixed(2)}s · {f.width}×{f.height}
                </div>
              </div>
            </div>
          ))}
        </div>
        <details className="text-xs">
          <summary className="cursor-pointer text-zinc-500 hover:text-zinc-900">
            원본 JSON 보기
          </summary>
          <JsonView data={stage.data} />
        </details>
      </div>
    );
  }

  // STT 단계 — segments 표시 + JSON
  if (stage.stage === "audio_stt" && stage.data) {
    const d = stage.data as {
      audio?: { size_bytes: number; format: string };
      stt?: {
        text?: string;
        language?: string;
        duration?: number;
        segments?: { id?: number; start: number; end: number; text: string }[];
      };
    };
    const stt = d.stt;
    return (
      <div className="space-y-4">
        {d.audio && (
          <div className="text-xs text-zinc-600">
            추출 오디오: {d.audio.format} ·{" "}
            {(d.audio.size_bytes / 1024).toFixed(1)} KB
          </div>
        )}
        {stt?.text && (
          <div className="rounded-lg bg-zinc-50 border border-zinc-200 p-3">
            <div className="text-[10px] text-zinc-500 font-semibold mb-1">
              전체 텍스트 ({stt.language ?? "?"} · {stt.duration?.toFixed(1)}s)
            </div>
            <div className="text-sm text-zinc-900 whitespace-pre-wrap">
              {stt.text}
            </div>
          </div>
        )}
        {stt?.segments && stt.segments.length > 0 && (
          <div className="space-y-1">
            <div className="text-[10px] font-semibold text-zinc-500">
              세그먼트 ({stt.segments.length})
            </div>
            {stt.segments.map((seg, i) => (
              <div
                key={seg.id ?? i}
                className="text-xs flex gap-2 py-1 border-b border-zinc-100"
              >
                <span className="text-zinc-400 shrink-0 w-24 font-mono">
                  {seg.start.toFixed(2)}–{seg.end.toFixed(2)}s
                </span>
                <span className="text-zinc-900">{seg.text}</span>
              </div>
            ))}
          </div>
        )}
        <details className="text-xs">
          <summary className="cursor-pointer text-zinc-500 hover:text-zinc-900">
            원본 JSON 보기
          </summary>
          <JsonView data={stage.data} />
        </details>
      </div>
    );
  }

  // 그 외 — JSON 그대로
  return <JsonView data={stage.data} />;
}

function JsonView({ data }: { data: unknown }) {
  return (
    <pre className="text-[11px] leading-relaxed bg-zinc-900 text-zinc-100 rounded-lg p-3 overflow-x-auto whitespace-pre-wrap break-words">
      {JSON.stringify(data, null, 2)}
    </pre>
  );
}

// ─────────────────────────────────────────────────────────
// 전체 요약 — scene[] 집계해 카테고리별로 시각화
// ─────────────────────────────────────────────────────────
type Scene = Record<string, unknown>;

function pickStr(obj: unknown, ...path: string[]): string | undefined {
  let cur: unknown = obj;
  for (const p of path) {
    if (cur && typeof cur === "object" && p in (cur as Record<string, unknown>)) {
      cur = (cur as Record<string, unknown>)[p];
    } else return undefined;
  }
  return typeof cur === "string" && cur.trim() ? cur.trim() : undefined;
}
function pickArr(obj: unknown, ...path: string[]): string[] {
  let cur: unknown = obj;
  for (const p of path) {
    if (cur && typeof cur === "object" && p in (cur as Record<string, unknown>)) {
      cur = (cur as Record<string, unknown>)[p];
    } else return [];
  }
  return Array.isArray(cur)
    ? cur.filter((x): x is string => typeof x === "string" && x.trim().length > 0)
    : [];
}
function bump(map: Record<string, number>, key: string | undefined) {
  if (!key) return;
  map[key] = (map[key] ?? 0) + 1;
}
function bumpAll(map: Record<string, number>, keys: string[]) {
  for (const k of keys) bump(map, k);
}
function topN(map: Record<string, number>, n = 12): [string, number][] {
  return Object.entries(map)
    .sort((a, b) => b[1] - a[1])
    .slice(0, n);
}

const AGE_LABEL_KO: Record<string, string> = {
  child_actor: "아역 (5~7)",
  elementary: "초등학생 (8~12)",
  middle_school: "중학생 (13~16)",
  high_school: "고등학생 (17~19)",
  "20s": "20대",
  "30s": "30대",
  "40s": "40대",
  "50s": "50대",
  "60s": "60대",
  "70s_plus": "70대 이상",
};
const GENDER_LABEL_KO: Record<string, string> = {
  female: "여성",
  male: "남성",
  neutral: "중성",
};

function OverallSummaryView({
  scenes,
  totalDurationSec,
}: {
  scenes: Scene[];
  totalDurationSec: number;
}) {
  const ageRanges: Record<string, number> = {};
  const genders: Record<string, number> = {};
  const characterTypes: Record<string, number> = {};
  const occupations: Record<string, number> = {};
  const periods: Record<string, number> = {};
  const settings: Record<string, number> = {};
  const actingStyles: Record<string, number> = {};
  const emotionDeliveries: Record<string, number> = {};
  const speechStyles: Record<string, number> = {};
  const speechSpeeds: Record<string, number> = {};
  const toneKeywords: Record<string, number> = {};
  const voiceCharacteristics: Record<string, number> = {};
  const facialExpressions: Record<string, number> = {};
  const gestures: Record<string, number> = {};
  const bodyLanguages: Record<string, number> = {};
  const eyeContactStyles: Record<string, number> = {};
  const hairLengths: Record<string, number> = {};
  const imageTypes: Record<string, number> = {};
  const eyeSizes: Record<string, number> = {};
  const eyelids: Record<string, number> = {};
  const eyeShapes: Record<string, number> = {};
  const eyeTails: Record<string, number> = {};
  const bodyTypes: Record<string, number> = {};
  const bodyStyles: Record<string, number> = {};
  const skinTones: Record<string, number> = {};
  const impressions: Record<string, number> = {};
  const celebrities: Record<string, number> = {};
  const allKeywords: Record<string, number> = {};
  const sceneSummaries: { sceneId: string; start: number; end: number; text: string }[] = [];
  let celebConfidenceSum = 0;
  let celebConfidenceCount = 0;

  for (const s of scenes) {
    bump(ageRanges, pickStr(s, "role", "age_range"));
    bump(genders, pickStr(s, "role", "gender_appearance"));
    bump(characterTypes, pickStr(s, "role", "character_type"));
    bump(occupations, pickStr(s, "role", "occupation"));
    bump(periods, pickStr(s, "era", "period"));
    bump(settings, pickStr(s, "era", "setting"));
    bumpAll(actingStyles, pickArr(s, "acting_analysis", "acting_style"));
    bump(emotionDeliveries, pickStr(s, "acting_analysis", "emotion_delivery"));
    bumpAll(speechStyles, pickArr(s, "speech_analysis", "speech_style"));
    bump(speechSpeeds, pickStr(s, "speech_analysis", "speech_speed"));
    bumpAll(toneKeywords, pickArr(s, "speech_analysis", "tone_keywords"));
    bumpAll(voiceCharacteristics, pickArr(s, "speech_analysis", "voice_characteristics"));
    bumpAll(facialExpressions, pickArr(s, "physical_expression", "facial_expression_keywords"));
    bumpAll(gestures, pickArr(s, "physical_expression", "gesture_keywords"));
    bumpAll(bodyLanguages, pickArr(s, "physical_expression", "body_language_keywords"));
    bump(eyeContactStyles, pickStr(s, "physical_expression", "eye_contact_style"));
    bump(hairLengths, pickStr(s, "appearance", "hair_length"));
    bump(imageTypes, pickStr(s, "appearance", "image_type"));
    bump(eyeSizes, pickStr(s, "appearance", "eye_size"));
    bump(eyelids, pickStr(s, "appearance", "eyelid"));
    bump(eyeShapes, pickStr(s, "appearance", "eye_shape"));
    bump(eyeTails, pickStr(s, "appearance", "eye_tail"));
    bump(bodyTypes, pickStr(s, "appearance", "body_type"));
    bump(bodyStyles, pickStr(s, "appearance", "body_style"));
    bump(skinTones, pickStr(s, "appearance", "skin_tone"));
    bumpAll(impressions, pickArr(s, "appearance", "impression_keywords"));
    bumpAll(celebrities, pickArr(s, "resembling_celebrities", "candidates"));
    const cConf = (s.resembling_celebrities as { confidence?: number } | undefined)?.confidence;
    if (typeof cConf === "number" && cConf > 0) {
      celebConfidenceSum += cConf;
      celebConfidenceCount += 1;
    }
    bumpAll(allKeywords, pickArr(s, "search_keywords"));
    const summary = pickStr(s, "scene_summary");
    if (summary) {
      sceneSummaries.push({
        sceneId: (s.scene_id as string) ?? "",
        start: (s.scene_start_sec as number) ?? 0,
        end: (s.scene_end_sec as number) ?? 0,
        text: summary,
      });
    }
  }

  const celebConfidenceAvg =
    celebConfidenceCount > 0 ? celebConfidenceSum / celebConfidenceCount : 0;

  return (
    <div className="space-y-5">
      {/* 헤더 */}
      <div className="rounded-lg bg-amber-50 border border-amber-200 px-4 py-3">
        <div className="text-sm font-bold text-amber-900">전체 영상 요약</div>
        <div className="mt-1 text-xs text-amber-800">
          scene <b>{scenes.length}</b>개 · 총 길이 <b>{totalDurationSec.toFixed(1)}초</b>
          {" "}· 모든 scene 의 RAG JSON 결과를 카테고리별로 집계.
        </div>
      </div>

      {/* 외형 프로필 */}
      <SummarySection title="외형 프로필 (Appearance)">
        <Pair label="연령대" entries={topN(ageRanges, 8)} labelMap={AGE_LABEL_KO} />
        <Pair label="외형 성별" entries={topN(genders, 3)} labelMap={GENDER_LABEL_KO} />
        <Pair label="머리 길이" entries={topN(hairLengths, 6)} />
        <Pair label="이미지형" entries={topN(imageTypes, 9)} />
        <Pair label="눈 크기" entries={topN(eyeSizes, 3)} />
        <Pair label="쌍꺼풀" entries={topN(eyelids, 3)} />
        <Pair label="눈 형태" entries={topN(eyeShapes, 3)} />
        <Pair label="눈꼬리" entries={topN(eyeTails, 3)} />
        <Pair label="체형" entries={topN(bodyTypes, 5)} />
        <Pair label="체형 스타일" entries={topN(bodyStyles, 10)} />
        <Pair label="피부톤" entries={topN(skinTones, 3)} />
        <Pair label="인상 키워드" entries={topN(impressions, 8)} />
      </SummarySection>

      {/* 닮은 연예인 */}
      <SummarySection title={`닮은 연예인 (평균 신뢰도 ${celebConfidenceAvg.toFixed(2)})`}>
        <Pair label="후보" entries={topN(celebrities, 10)} />
      </SummarySection>

      {/* 역할 */}
      <SummarySection title="역할 (Role)">
        <Pair label="역할 유형" entries={topN(characterTypes, 8)} />
        <Pair label="직업" entries={topN(occupations, 8)} />
      </SummarySection>

      {/* 시대·장소 */}
      <SummarySection title="시대 · 장소 (Era)">
        <Pair label="시대" entries={topN(periods, 5)} />
        <Pair label="장소" entries={topN(settings, 10)} />
      </SummarySection>

      {/* 연기 분석 */}
      <SummarySection title="연기 (Acting)">
        <Pair label="연기 스타일" entries={topN(actingStyles, 8)} />
        <Pair label="감정 전달" entries={topN(emotionDeliveries, 5)} />
      </SummarySection>

      {/* 음성 / 말투 */}
      <SummarySection title="음성 · 말투 (Speech)">
        <Pair label="말투 스타일" entries={topN(speechStyles, 8)} />
        <Pair label="말 속도" entries={topN(speechSpeeds, 5)} />
        <Pair label="음색 키워드" entries={topN(toneKeywords, 8)} />
        <Pair label="발성 특징" entries={topN(voiceCharacteristics, 8)} />
      </SummarySection>

      {/* 신체 표현 */}
      <SummarySection title="신체 표현 (Physical)">
        <Pair label="표정" entries={topN(facialExpressions, 8)} />
        <Pair label="제스처" entries={topN(gestures, 8)} />
        <Pair label="신체 언어" entries={topN(bodyLanguages, 8)} />
        <Pair label="시선" entries={topN(eyeContactStyles, 5)} />
      </SummarySection>

      {/* 상위 검색 키워드 */}
      <SummarySection title="상위 검색 키워드 (search_keywords)">
        <div className="flex flex-wrap gap-1.5">
          {topN(allKeywords, 30).map(([k, c]) => (
            <span
              key={k}
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 text-[11px] font-medium"
            >
              {k} <span className="text-emerald-600">×{c}</span>
            </span>
          ))}
        </div>
      </SummarySection>

      {/* scene 별 한줄 요약 */}
      <SummarySection title="장면별 한 줄 요약">
        <div className="space-y-1.5">
          {sceneSummaries.map((s) => (
            <div
              key={s.sceneId}
              className="flex gap-2 text-xs border-b border-zinc-100 py-1.5"
            >
              <span className="font-mono text-zinc-400 shrink-0 w-32">
                {s.sceneId} · {s.start.toFixed(1)}–{s.end.toFixed(1)}s
              </span>
              <span className="text-zinc-800">{s.text}</span>
            </div>
          ))}
        </div>
      </SummarySection>
    </div>
  );
}

function SummarySection({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <h3 className="text-xs font-bold text-zinc-900 mb-2 pb-1 border-b border-zinc-200">
        {title}
      </h3>
      <div className="space-y-1.5">{children}</div>
    </div>
  );
}

function Pair({
  label,
  entries,
  labelMap,
}: {
  label: string;
  entries: [string, number][];
  labelMap?: Record<string, string>;
}) {
  if (entries.length === 0) {
    return (
      <div className="flex text-xs">
        <span className="w-24 shrink-0 text-zinc-500">{label}</span>
        <span className="text-zinc-300">—</span>
      </div>
    );
  }
  return (
    <div className="flex text-xs">
      <span className="w-24 shrink-0 text-zinc-500">{label}</span>
      <div className="flex flex-wrap gap-1.5">
        {entries.map(([k, c]) => (
          <span
            key={k}
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-zinc-100 text-zinc-800 text-[11px]"
          >
            {labelMap?.[k] ?? k}
            <span className="text-zinc-500">×{c}</span>
          </span>
        ))}
      </div>
    </div>
  );
}
