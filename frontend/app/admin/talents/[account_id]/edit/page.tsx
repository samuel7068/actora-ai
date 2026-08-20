"use client";

import Image from "next/image";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Film, ImagePlus, Loader2, Save } from "lucide-react";

import BirthDateSelect from "@/components/BirthDateSelect";
import DashboardHeader from "@/components/DashboardHeader";
import { useDashboardGuard } from "@/components/DashboardGuard";
import { api, tokenStorage } from "@/lib/api";

type Opt = { v: string; l: string };
const GENDER: Opt[] = [
  { v: "", l: "선택 안 함" },
  { v: "FEMALE", l: "여자" },
  { v: "MALE", l: "남자" },
  { v: "SELF_DESCRIBED", l: "직접 입력" },
];
const REGION: Opt[] = [
  { v: "", l: "선택 안 함" },
  ...[
    ["SEOUL", "서울"], ["BUSAN", "부산"], ["INCHEON", "인천"], ["DAEGU", "대구"],
    ["DAEJEON", "대전"], ["GWANGJU", "광주"], ["ULSAN", "울산"], ["SEJONG", "세종"],
    ["GYEONGGI", "경기"], ["GANGWON", "강원"], ["CHUNGBUK", "충북"], ["CHUNGNAM", "충남"],
    ["JEONBUK", "전북"], ["JEONNAM", "전남"], ["GYEONGBUK", "경북"], ["GYEONGNAM", "경남"],
    ["JEJU", "제주"], ["OVERSEAS", "해외"],
  ].map(([v, l]) => ({ v, l })),
];
const CATEGORY: Opt[] = [
  { v: "", l: "선택 안 함" },
  ...[
    ["ACTOR", "연기자"], ["MODEL", "모델"], ["INFLUENCER", "인플루언서"],
    ["VOCAL", "보컬"], ["DANCER", "댄서"], ["MC", "MC"], ["CREATOR", "크리에이터"],
  ].map(([v, l]) => ({ v, l })),
];

const LABEL = "block text-sm text-white/80 mb-1 drop-shadow";
const FIELD =
  "w-full rounded-lg border border-white/20 bg-white/10 backdrop-blur-md px-3 py-2 text-sm text-white placeholder-white/40 focus:outline-none focus:border-white/40 [&>option]:text-zinc-900";

function withToken(url: string): string {
  const t = tokenStorage.get();
  if (!t) return url;
  return `${url}${url.includes("?") ? "&" : "?"}token=${t}`;
}

type Detail = {
  name: string;
  stage_name: string | null;
  gender: string | null;
  birth_date: string | null;
  height_cm: number | null;
  weight_kg: number | null;
  region_code: string | null;
  main_category: string | null;
  skills: string[];
  languages: string[];
  introduction: string | null;
  profile_image_urls: string[];
};

export default function AdminTalentEditPage() {
  const ready = useDashboardGuard("ADMIN");
  const router = useRouter();
  const params = useParams<{ account_id: string }>();
  const accountId = Number(params.account_id);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [currentPhoto, setCurrentPhoto] = useState<string | null>(null);

  const [form, setForm] = useState({
    name: "", stage_name: "", gender: "", birth_date: "", height_cm: "",
    weight_kg: "", region_code: "", main_category: "", skills: "",
    languages: "", introduction: "",
  });

  const photoInputRef = useRef<HTMLInputElement>(null);
  const [photoFile, setPhotoFile] = useState<File | null>(null);
  const [photoPreview, setPhotoPreview] = useState<string | null>(null);

  useEffect(() => {
    if (!ready) return;
    let alive = true;
    (async () => {
      setLoading(true);
      try {
        const res = await api.get<Detail>(`/admin/talents/${accountId}`);
        if (!alive) return;
        const d = res.data;
        setForm({
          name: d.name ?? "",
          stage_name: d.stage_name ?? "",
          gender: d.gender ?? "",
          birth_date: d.birth_date ?? "",
          height_cm: d.height_cm != null ? String(d.height_cm) : "",
          weight_kg: d.weight_kg != null ? String(d.weight_kg) : "",
          region_code: d.region_code ?? "",
          main_category: d.main_category ?? "",
          skills: (d.skills ?? []).join(", "),
          languages: (d.languages ?? []).join(", "),
          introduction: d.introduction ?? "",
        });
        setCurrentPhoto(d.profile_image_urls?.[0] ?? null);
      } catch {
        if (alive) setErr("프로필을 불러오지 못했습니다.");
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, accountId]);

  if (!ready) return null;

  const set = (k: keyof typeof form, v: string) =>
    setForm((f) => ({ ...f, [k]: v }));
  const csv = (s: string) => s.split(",").map((x) => x.trim()).filter(Boolean);

  const onPickPhoto = (f: File | null) => {
    if (!f) return;
    if (!f.type.startsWith("image/")) {
      setErr("이미지 파일만 업로드 가능합니다.");
      return;
    }
    setErr(null);
    if (photoPreview) URL.revokeObjectURL(photoPreview);
    setPhotoFile(f);
    setPhotoPreview(URL.createObjectURL(f));
  };

  const submit = async () => {
    if (!form.name.trim()) {
      setErr("이름은 필수입니다.");
      return;
    }
    setSaving(true);
    setErr(null);
    setOk(null);
    try {
      await api.put(`/admin/talents/${accountId}`, {
        name: form.name.trim(),
        stage_name: form.stage_name.trim() || null,
        gender: form.gender || null,
        birth_date: form.birth_date || null,
        height_cm: form.height_cm ? Number(form.height_cm) : null,
        weight_kg: form.weight_kg ? Number(form.weight_kg) : null,
        region_code: form.region_code || null,
        main_category: form.main_category || null,
        skills: csv(form.skills),
        languages: csv(form.languages),
        introduction: form.introduction.trim() || null,
      });
      if (photoFile) {
        const fd = new FormData();
        fd.append("file", photoFile);
        const res = await api.post<{ url: string }>(
          `/admin/talents/${accountId}/photo`,
          fd,
        );
        setCurrentPhoto(res.data.url);
        if (photoPreview) URL.revokeObjectURL(photoPreview);
        setPhotoFile(null);
        setPhotoPreview(null);
      }
      setOk("저장되었습니다.");
    } catch {
      setErr("저장에 실패했습니다. 잠시 후 다시 시도해 주세요.");
    } finally {
      setSaving(false);
    }
  };

  const photoSrc = photoPreview ?? (currentPhoto ? withToken(currentPhoto) : null);

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

      <main className="relative max-w-3xl mx-auto px-4 sm:px-6 pt-28 pb-12">
        <h1 className="text-2xl sm:text-3xl font-bold text-white drop-shadow-lg">
          인재 프로필 수정
        </h1>
        <p className="mt-1 text-white/80 drop-shadow">account_id={accountId}</p>

        {loading ? (
          <div className="flex items-center justify-center gap-2 py-20 text-white/70">
            <Loader2 className="w-5 h-5 animate-spin" />
            불러오는 중…
          </div>
        ) : (
          <div className="mt-8 rounded-xl border border-white/15 bg-white/5 backdrop-blur-md p-6 space-y-6">
            {/* 프로필 사진 */}
            <section>
              <h2 className="text-sm font-semibold text-amber-100 mb-3">프로필 사진</h2>
              <div className="flex items-center gap-4">
                <input
                  ref={photoInputRef}
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={(e) => onPickPhoto(e.target.files?.[0] ?? null)}
                />
                <button
                  type="button"
                  onClick={() => photoInputRef.current?.click()}
                  className="w-24 h-24 rounded-full border-2 border-dashed border-white/30 hover:border-white/50 bg-white/5 overflow-hidden flex items-center justify-center transition-colors"
                >
                  {photoSrc ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={photoSrc} alt="" className="w-full h-full object-cover" />
                  ) : (
                    <ImagePlus className="w-7 h-7 text-white/50" />
                  )}
                </button>
                <div className="text-xs text-white/60">
                  사진을 바꾸려면 원형 영역을 누르세요.
                </div>
              </div>
            </section>

            {/* 프로필 필드 */}
            <section>
              <h2 className="text-sm font-semibold text-amber-100 mb-3">프로필</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className={LABEL}>이름 *</label>
                  <input className={FIELD} value={form.name}
                    onChange={(e) => set("name", e.target.value)} />
                </div>
                <div>
                  <label className={LABEL}>예명</label>
                  <input className={FIELD} value={form.stage_name}
                    onChange={(e) => set("stage_name", e.target.value)} />
                </div>
                <div>
                  <label className={LABEL}>성별</label>
                  <select className={FIELD} value={form.gender}
                    onChange={(e) => set("gender", e.target.value)}>
                    {GENDER.map((o) => <option key={o.v} value={o.v}>{o.l}</option>)}
                  </select>
                </div>
                <div>
                  <label className={LABEL}>생년월일</label>
                  <BirthDateSelect
                    value={form.birth_date}
                    onChange={(v) => set("birth_date", v)}
                    className={FIELD}
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className={LABEL}>키(cm)</label>
                    <input className={FIELD} type="number" value={form.height_cm}
                      onChange={(e) => set("height_cm", e.target.value)} />
                  </div>
                  <div>
                    <label className={LABEL}>몸무게(kg)</label>
                    <input className={FIELD} type="number" value={form.weight_kg}
                      onChange={(e) => set("weight_kg", e.target.value)} />
                  </div>
                </div>
                <div>
                  <label className={LABEL}>지역</label>
                  <select className={FIELD} value={form.region_code}
                    onChange={(e) => set("region_code", e.target.value)}>
                    {REGION.map((o) => <option key={o.v} value={o.v}>{o.l}</option>)}
                  </select>
                </div>
                <div>
                  <label className={LABEL}>주 분야</label>
                  <select className={FIELD} value={form.main_category}
                    onChange={(e) => set("main_category", e.target.value)}>
                    {CATEGORY.map((o) => <option key={o.v} value={o.v}>{o.l}</option>)}
                  </select>
                </div>
                <div>
                  <label className={LABEL}>특기 (쉼표)</label>
                  <input className={FIELD} placeholder="예: 자전거, 수영" value={form.skills}
                    onChange={(e) => set("skills", e.target.value)} />
                </div>
                <div>
                  <label className={LABEL}>언어 (쉼표)</label>
                  <input className={FIELD} placeholder="예: 영어, 중국어" value={form.languages}
                    onChange={(e) => set("languages", e.target.value)} />
                </div>
              </div>
              <div className="mt-3">
                <label className={LABEL}>소개</label>
                <textarea className={FIELD + " min-h-[80px] resize-y"} value={form.introduction}
                  onChange={(e) => set("introduction", e.target.value)} />
              </div>
            </section>

            {err && (
              <div className="rounded-lg bg-red-500/20 border border-red-400/40 text-red-100 text-sm px-4 py-2.5">
                {err}
              </div>
            )}
            {ok && (
              <div className="rounded-lg bg-emerald-500/20 border border-emerald-400/40 text-emerald-100 text-sm px-4 py-2.5">
                {ok}
              </div>
            )}

            <div className="flex gap-2 justify-end">
              <button
                type="button"
                onClick={() => router.push(`/admin/talents/${accountId}/portfolio`)}
                className="inline-flex items-center gap-2 rounded-lg border border-amber-200/40 text-amber-100 px-4 py-2.5 text-sm hover:bg-amber-100/10 transition-colors mr-auto"
              >
                <Film className="w-4 h-4" />
                포트폴리오
              </button>
              <button
                type="button"
                onClick={() => router.push("/admin/talents")}
                className="rounded-lg border border-white/20 text-white/80 px-4 py-2.5 text-sm hover:bg-white/10 transition-colors"
              >
                취소
              </button>
              <button
                type="button"
                onClick={submit}
                disabled={saving}
                className="inline-flex items-center gap-2 rounded-lg bg-amber-100 text-zinc-900 px-5 py-2.5 text-sm font-semibold hover:bg-amber-200 transition-colors disabled:opacity-50"
              >
                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                저장
              </button>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
