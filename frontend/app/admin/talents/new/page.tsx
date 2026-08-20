"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { ImagePlus, Loader2, UserPlus } from "lucide-react";

import BirthDateSelect from "@/components/BirthDateSelect";
import DashboardHeader from "@/components/DashboardHeader";
import { useDashboardGuard } from "@/components/DashboardGuard";
import VideoAnalysisModal from "@/components/VideoAnalysisModal";
import { api } from "@/lib/api";

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

export default function AdminTalentNewPage() {
  const ready = useDashboardGuard("ADMIN");
  const router = useRouter();

  const [form, setForm] = useState({
    name: "",
    stage_name: "",
    gender: "",
    birth_date: "",
    height_cm: "",
    weight_kg: "",
    region_code: "",
    main_category: "",
    skills: "",
    languages: "",
    introduction: "",
  });
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  // 방금 등록한 인재 (영상 업로드 대상)
  const [registered, setRegistered] = useState<{ id: number; name: string } | null>(
    null,
  );
  const [analyzeOpen, setAnalyzeOpen] = useState(false);
  // 프로필 사진
  const photoInputRef = useRef<HTMLInputElement>(null);
  const [photoFile, setPhotoFile] = useState<File | null>(null);
  const [photoPreview, setPhotoPreview] = useState<string | null>(null);

  if (!ready) return null;

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

  const set = (k: keyof typeof form, v: string) =>
    setForm((f) => ({ ...f, [k]: v }));

  const csv = (s: string) =>
    s.split(",").map((x) => x.trim()).filter(Boolean);

  const submit = async () => {
    if (!form.name.trim()) {
      setErr("이름은 필수입니다.");
      return;
    }
    setSaving(true);
    setErr(null);
    setOk(null);
    try {
      const body = {
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
      };
      const res = await api.post<{ account_id: number; name: string }>(
        "/admin/talents",
        body,
      );
      const newId = res.data.account_id;
      // 사진이 선택돼 있으면 등록 직후 업로드
      if (photoFile) {
        const fd = new FormData();
        fd.append("file", photoFile);
        try {
          await api.post(`/admin/talents/${newId}/photo`, fd);
        } catch {
          setErr("프로필은 등록됐으나 사진 업로드에 실패했습니다.");
        }
      }
      setOk(`'${res.data.name}' 등록 완료 (account_id=${newId})`);
      setRegistered({ id: newId, name: res.data.name });
      // 폼 초기화 (연속 등록)
      setForm({
        name: "", stage_name: "", gender: "", birth_date: "", height_cm: "",
        weight_kg: "", region_code: "", main_category: "", skills: "",
        languages: "", introduction: "",
      });
      if (photoPreview) URL.revokeObjectURL(photoPreview);
      setPhotoFile(null);
      setPhotoPreview(null);
    } catch {
      setErr("등록에 실패했습니다. 잠시 후 다시 시도해 주세요.");
    } finally {
      setSaving(false);
    }
  };

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
        <h1 className="text-2xl sm:text-3xl font-bold text-white drop-shadow-lg flex items-center gap-2">
          <UserPlus className="w-7 h-7 text-amber-100" />
          인재 등록
        </h1>
        <p className="mt-1 text-white/80 drop-shadow">
          연기자·MC 계정과 프로필을 대행 등록합니다. (영상은 등록 후 별도 업로드)
        </p>

        <div className="mt-8 rounded-xl border border-white/15 bg-white/5 backdrop-blur-md p-6 space-y-6">
          <p className="text-xs text-white/50">
            로그인 계정이 아닌 검색용 시드 데이터입니다. 계정 ID·이메일·비밀번호는
            자동 생성되며, 추후 본인이 가입할 때 연결됩니다.
          </p>

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
                {photoPreview ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={photoPreview}
                    alt="미리보기"
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <ImagePlus className="w-7 h-7 text-white/50" />
                )}
              </button>
              <div className="text-xs text-white/60">
                {photoFile ? (
                  <>
                    <div className="text-white/90">{photoFile.name}</div>
                    <button
                      type="button"
                      onClick={() => {
                        if (photoPreview) URL.revokeObjectURL(photoPreview);
                        setPhotoFile(null);
                        setPhotoPreview(null);
                      }}
                      className="mt-1 text-red-300 hover:underline"
                    >
                      제거
                    </button>
                  </>
                ) : (
                  "원형 영역을 눌러 사진을 선택하세요 (선택)"
                )}
              </div>
            </div>
          </section>

          {/* 프로필 */}
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
            <div className="rounded-lg bg-emerald-500/20 border border-emerald-400/40 text-emerald-100 text-sm px-4 py-3 flex flex-wrap items-center justify-between gap-2">
              <span>{ok}</span>
              {registered && (
                <button
                  type="button"
                  onClick={() => setAnalyzeOpen(true)}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-100 text-emerald-900 px-3 py-1.5 text-xs font-semibold hover:bg-emerald-200 transition-colors"
                >
                  ‘{registered.name}’ 영상 업로드
                </button>
              )}
            </div>
          )}

          <div className="flex gap-2 justify-end">
            <button
              type="button"
              onClick={() => router.push("/admin/dashboard")}
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
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <UserPlus className="w-4 h-4" />}
              저장
            </button>
          </div>
        </div>
      </main>

      <VideoAnalysisModal
        open={analyzeOpen}
        onClose={() => setAnalyzeOpen(false)}
        accountId={registered?.id}
      />
    </div>
  );
}
