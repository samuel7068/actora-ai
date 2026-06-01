"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Loader2, X } from "lucide-react";
import { useEffect, useState } from "react";

import { api, tokenStorage } from "@/lib/api";

// 프로필 사진 서빙 경로는 인증 필요 → <img> 용으로 ?token= 쿼리를 붙인다.
function withToken(url: string): string {
  const t = tokenStorage.get();
  if (!t) return url;
  return `${url}${url.includes("?") ? "&" : "?"}token=${t}`;
}

type Props = {
  accountId: number | null;
  onClose: () => void;
};

type TalentDetail = {
  account_id: number;
  name: string;
  stage_name?: string | null;
  gender?: string | null;
  age?: number | null;
  nationality?: string | null;
  region_code?: string | null;
  main_category?: string | null;
  sub_categories?: string[];
  height_cm?: number | null;
  weight_kg?: number | null;
  weight_range?: string | null;
  skills?: string[];
  languages?: string[];
  education_level?: string | null;
  education_major?: string | null;
  career_level?: string | null;
  career_years?: number | null;
  introduction?: string | null;
  profile_image_urls?: string[];
  instagram_url?: string | null;
  youtube_url?: string | null;
  tiktok_url?: string | null;
};

const GENDER: Record<string, string> = {
  MALE: "남자",
  FEMALE: "여자",
  SELF_DESCRIBED: "직접 입력",
};
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
const CAREER: Record<string, string> = { NEWBIE: "신인", PRO: "프로" };
const EDU: Record<string, string> = {
  MIDDLE_SCHOOL: "중졸", HIGH_SCHOOL: "고졸", BACHELOR: "학사", GRADUATE: "대학원",
};
const WEIGHT_RANGE: Record<string, string> = {
  skinny: "마름", slim: "슬림", standard: "보통", toned: "탄탄함",
  muscular: "근육형", chubby: "통통함", sturdy: "건장함", plus_size: "플러스사이즈",
};

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  if (value == null || value === "" || (Array.isArray(value) && value.length === 0))
    return null;
  return (
    <div className="flex gap-3 py-1.5 text-sm border-b border-zinc-100 last:border-0">
      <span className="w-24 shrink-0 text-zinc-500">{label}</span>
      <span className="text-zinc-900">{value}</span>
    </div>
  );
}

export default function TalentDetailModal({ accountId, onClose }: Props) {
  const [data, setData] = useState<TalentDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (accountId == null) return;
    setData(null);
    setErr(null);
    setLoading(true);
    api
      .get<TalentDetail>(`/agency/talent/${accountId}`)
      .then((res) => setData(res.data))
      .catch(() => setErr("프로필을 불러오지 못했습니다."))
      .finally(() => setLoading(false));
  }, [accountId]);

  useEffect(() => {
    if (accountId == null) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [accountId, onClose]);

  const chips = (arr?: string[]) =>
    arr && arr.length > 0 ? (
      <span className="flex flex-wrap gap-1.5">
        {arr.map((x) => (
          <span
            key={x}
            className="px-2 py-0.5 rounded-full bg-zinc-100 text-zinc-700 text-xs"
          >
            {x}
          </span>
        ))}
      </span>
    ) : null;

  return (
    <AnimatePresence>
      {accountId != null && (
        <motion.div
          className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center px-4 py-6"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
        >
          <motion.div
            initial={{ opacity: 0, y: 24, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 24, scale: 0.96 }}
            transition={{ duration: 0.22, ease: "easeOut" }}
            onClick={(e) => e.stopPropagation()}
            className="relative w-full max-w-lg max-h-[88vh] overflow-y-auto rounded-2xl bg-white shadow-2xl"
          >
            <button
              type="button"
              onClick={onClose}
              aria-label="닫기"
              className="absolute top-3 right-3 rounded-full p-1.5 text-zinc-500 hover:bg-zinc-100"
            >
              <X className="w-5 h-5" />
            </button>

            {loading && (
              <div className="flex items-center justify-center gap-2 py-20 text-zinc-500">
                <Loader2 className="w-5 h-5 animate-spin" />
                불러오는 중…
              </div>
            )}
            {err && <div className="p-10 text-center text-red-600">{err}</div>}

            {data && (
              <div className="p-6">
                {/* 헤더 */}
                <div className="flex items-center gap-4">
                  {data.profile_image_urls && data.profile_image_urls[0] ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={withToken(data.profile_image_urls[0])}
                      alt={data.name}
                      className="w-20 h-20 rounded-full object-cover bg-zinc-100"
                    />
                  ) : (
                    <div className="w-20 h-20 rounded-full bg-zinc-200 flex items-center justify-center text-2xl font-bold text-zinc-500">
                      {data.name?.[0] ?? "?"}
                    </div>
                  )}
                  <div>
                    <div className="text-xl font-bold text-zinc-900">
                      {data.name}
                      {data.stage_name && (
                        <span className="ml-2 text-sm font-normal text-zinc-500">
                          {data.stage_name}
                        </span>
                      )}
                    </div>
                    <div className="mt-1 text-sm text-zinc-500">
                      {[
                        data.gender ? GENDER[data.gender] ?? data.gender : null,
                        data.age != null ? `${data.age}세` : null,
                        data.main_category
                          ? CATEGORY[data.main_category] ?? data.main_category
                          : null,
                      ]
                        .filter(Boolean)
                        .join(" · ")}
                    </div>
                  </div>
                </div>

                {/* 상세 */}
                <div className="mt-5">
                  <Row
                    label="신체"
                    value={[
                      data.height_cm ? `${data.height_cm}cm` : null,
                      data.weight_kg ? `${data.weight_kg}kg` : null,
                      data.weight_range
                        ? WEIGHT_RANGE[data.weight_range] ?? data.weight_range
                        : null,
                    ]
                      .filter(Boolean)
                      .join(" · ") || null}
                  />
                  <Row
                    label="지역"
                    value={
                      data.region_code
                        ? REGION[data.region_code] ?? data.region_code
                        : null
                    }
                  />
                  <Row label="국적" value={data.nationality} />
                  <Row
                    label="분야"
                    value={chips(
                      (data.sub_categories ?? []).map((c) => CATEGORY[c] ?? c),
                    )}
                  />
                  <Row label="특기" value={chips(data.skills)} />
                  <Row label="언어" value={chips(data.languages)} />
                  <Row
                    label="학력"
                    value={[
                      data.education_level
                        ? EDU[data.education_level] ?? data.education_level
                        : null,
                      data.education_major,
                    ]
                      .filter(Boolean)
                      .join(" · ") || null}
                  />
                  <Row
                    label="경력"
                    value={[
                      data.career_level
                        ? CAREER[data.career_level] ?? data.career_level
                        : null,
                      data.career_years != null ? `${data.career_years}년` : null,
                    ]
                      .filter(Boolean)
                      .join(" · ") || null}
                  />
                  <Row label="소개" value={data.introduction} />
                </div>

                {/* SNS */}
                {(data.instagram_url || data.youtube_url || data.tiktok_url) && (
                  <div className="mt-4 flex flex-wrap gap-3 text-sm">
                    {data.instagram_url && (
                      <a
                        href={data.instagram_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-pink-600 hover:underline"
                      >
                        Instagram
                      </a>
                    )}
                    {data.youtube_url && (
                      <a
                        href={data.youtube_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-red-600 hover:underline"
                      >
                        YouTube
                      </a>
                    )}
                    {data.tiktok_url && (
                      <a
                        href={data.tiktok_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-zinc-900 hover:underline"
                      >
                        TikTok
                      </a>
                    )}
                  </div>
                )}
              </div>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
