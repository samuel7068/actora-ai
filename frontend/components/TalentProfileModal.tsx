"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Check, ImagePlus, Trash2, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { api, tokenStorage } from "@/lib/api";

type Props = {
  open: boolean;
  onClose: () => void;
};

type Gender = "MALE" | "FEMALE" | "SELF_DESCRIBED" | "";
type Region =
  | "SEOUL" | "BUSAN" | "INCHEON" | "DAEGU" | "DAEJEON" | "GWANGJU" | "ULSAN"
  | "SEJONG" | "GYEONGGI" | "GANGWON" | "CHUNGBUK" | "CHUNGNAM" | "JEONBUK"
  | "JEONNAM" | "GYEONGBUK" | "GYEONGNAM" | "JEJU" | "OVERSEAS" | "";
type Category =
  | "ACTOR" | "MODEL" | "INFLUENCER" | "VOCAL" | "DANCER" | "MC" | "CREATOR" | "";
type WeightRange =
  | "skinny" | "slim" | "standard" | "toned" | "muscular"
  | "chubby" | "sturdy" | "plus_size" | "";
type CareerLevel = "NEWBIE" | "PRO" | "";
type EduLevel = "MIDDLE_SCHOOL" | "HIGH_SCHOOL" | "BACHELOR" | "GRADUATE" | "";

const GENDER_OPTIONS: { value: Gender; label: string }[] = [
  { value: "MALE", label: "남자" },
  { value: "FEMALE", label: "여자" },
  { value: "SELF_DESCRIBED", label: "직접 입력" },
];
const REGION_OPTIONS: { value: Region; label: string }[] = [
  { value: "SEOUL", label: "서울" }, { value: "BUSAN", label: "부산" },
  { value: "INCHEON", label: "인천" }, { value: "DAEGU", label: "대구" },
  { value: "DAEJEON", label: "대전" }, { value: "GWANGJU", label: "광주" },
  { value: "ULSAN", label: "울산" }, { value: "SEJONG", label: "세종" },
  { value: "GYEONGGI", label: "경기" }, { value: "GANGWON", label: "강원" },
  { value: "CHUNGBUK", label: "충북" }, { value: "CHUNGNAM", label: "충남" },
  { value: "JEONBUK", label: "전북" }, { value: "JEONNAM", label: "전남" },
  { value: "GYEONGBUK", label: "경북" }, { value: "GYEONGNAM", label: "경남" },
  { value: "JEJU", label: "제주" }, { value: "OVERSEAS", label: "해외" },
];
const CATEGORY_OPTIONS: { value: Category; label: string }[] = [
  { value: "ACTOR", label: "연기자" }, { value: "MODEL", label: "모델" },
  { value: "INFLUENCER", label: "인플루언서" }, { value: "VOCAL", label: "보컬" },
  { value: "DANCER", label: "댄서" }, { value: "MC", label: "MC" },
  { value: "CREATOR", label: "크리에이터" },
];
const WEIGHT_RANGE_OPTIONS: { value: WeightRange; label: string }[] = [
  { value: "skinny", label: "마름" },
  { value: "slim", label: "슬림" },
  { value: "standard", label: "보통" },
  { value: "toned", label: "탄탄함" },
  { value: "muscular", label: "근육형" },
  { value: "chubby", label: "통통함" },
  { value: "sturdy", label: "건장함" },
  { value: "plus_size", label: "플러스사이즈" },
];

type Opt = { value: string; label: string };

const BODY_TYPE_OPTIONS: Opt[] = [
  { value: "chubby", label: "통통한 체형" },
  { value: "skinny", label: "마른 체형" },
  { value: "slim", label: "슬림 체형" },
  { value: "muscular", label: "근육형" },
  { value: "sturdy", label: "건장한 체형" },
  { value: "broad_shoulders", label: "어깨 넓음" },
  { value: "upper_dominant", label: "상체 발달형" },
  { value: "lower_dominant", label: "하체 발달형" },
  { value: "glamorous", label: "글래머형" },
  { value: "petite", label: "왜소한 체형" },
  { value: "balanced", label: "균형형" },
  { value: "small_frame", label: "작은 체구" },
  { value: "large_frame", label: "큰 체구" },
  { value: "long_limbs", label: "긴 팔다리" },
  { value: "short_body", label: "짧은 체형" },
  { value: "flexible", label: "유연한 체형" },
  { value: "strong_impression", label: "강한 인상 체형" },
  { value: "soft_body", label: "부드러운 체형" },
];

const FACE_TYPE_OPTIONS: Opt[] = [
  { value: "round", label: "둥근형" },
  { value: "oval", label: "계란형" },
  { value: "long", label: "긴형" },
  { value: "square", label: "각진형" },
  { value: "inverted_triangle", label: "역삼각형" },
  { value: "heart", label: "하트형" },
  { value: "rectangle", label: "사각형" },
  { value: "cheekbone", label: "광대 있는 얼굴형" },
  { value: "short_face", label: "짧은 얼굴형" },
  { value: "long_face", label: "긴 얼굴형" },
  { value: "small_face", label: "작은 얼굴형" },
  { value: "large_face", label: "큰 얼굴형" },
];

const VISUAL_KEYWORD_GROUPS: { title: string; options: Opt[] }[] = [
  {
    title: "이미지 계열",
    options: [
      { value: "warm", label: "따뜻한 이미지" },
      { value: "cold", label: "차가운 이미지" },
      { value: "urban", label: "도회적" },
      { value: "innocent", label: "청순함" },
      { value: "luxurious", label: "고급스러움" },
      { value: "sophisticated", label: "세련됨" },
      { value: "pure", label: "순수함" },
      { value: "intense", label: "강렬함" },
      { value: "androgynous", label: "중성적" },
      { value: "friendly", label: "친근함" },
      { value: "plain", label: "수수함" },
      { value: "trustworthy", label: "신뢰감" },
    ],
  },
  {
    title: "역할 계열",
    options: [
      { value: "mother_image", label: "엄마상" },
      { value: "father_image", label: "아빠상" },
      { value: "student_image", label: "학생상" },
      { value: "office_worker_image", label: "회사원상" },
      { value: "detective_image", label: "형사상" },
      { value: "chaebol_image", label: "재벌상" },
      { value: "teacher_image", label: "교사상" },
      { value: "doctor_image", label: "의사상" },
      { value: "soldier_image", label: "군인상" },
      { value: "gangster_image", label: "조폭상" },
      { value: "villain_image", label: "빌런상" },
      { value: "leader_image", label: "리더형" },
    ],
  },
  {
    title: "나이/분위기 계열",
    options: [
      { value: "baby_face", label: "동안 이미지" },
      { value: "mature", label: "성숙한 이미지" },
      { value: "middle_aged", label: "중년 이미지" },
      { value: "boyish", label: "소년미" },
      { value: "girlish", label: "소녀미" },
      { value: "adult_like", label: "어른스러움" },
    ],
  },
  {
    title: "감성 계열",
    options: [
      { value: "cozy", label: "포근함" },
      { value: "charismatic", label: "카리스마" },
      { value: "intellectual", label: "지적인 느낌" },
      { value: "cute", label: "귀여움" },
      { value: "strong", label: "강인함" },
      { value: "elegant", label: "우아함" },
      { value: "mysterious", label: "신비로움" },
      { value: "sensitive", label: "예민한 느낌" },
      { value: "dark_mood", label: "어두운 분위기" },
      { value: "bright_mood", label: "밝은 분위기" },
    ],
  },
];
const CAREER_LEVEL_OPTIONS: { value: CareerLevel; label: string }[] = [
  { value: "NEWBIE", label: "신인" }, { value: "PRO", label: "프로" },
];
const EDU_LEVEL_OPTIONS: { value: EduLevel; label: string }[] = [
  { value: "MIDDLE_SCHOOL", label: "중졸" }, { value: "HIGH_SCHOOL", label: "고졸" },
  { value: "BACHELOR", label: "대졸" }, { value: "GRADUATE", label: "대학원졸" },
];

const csvToArr = (s: string): string[] =>
  s.split(",").map((x) => x.trim()).filter(Boolean);
const arrToCsv = (a: string[] | null | undefined): string => (a ?? []).join(", ");

// YYYY-MM-DD → 만 나이 (실패 시 null)
function calcAge(isoDate: string): number | null {
  if (!isoDate) return null;
  const [y, m, d] = isoDate.split("-").map((x) => Number(x));
  if (!y || !m || !d) return null;
  const today = new Date();
  let age = today.getFullYear() - y;
  const mDiff = today.getMonth() + 1 - m;
  if (mDiff < 0 || (mDiff === 0 && today.getDate() < d)) age--;
  if (age < 0 || age > 150) return null;
  return age;
}

type TabKey = "required" | "basic" | "physical" | "career" | "sns";

const TABS: { key: TabKey; label: string }[] = [
  { key: "required", label: "필수 정보" },
  { key: "basic", label: "기본 정보" },
  { key: "physical", label: "신체 · 비주얼" },
  { key: "career", label: "학력 · 경력 · 특기" },
  { key: "sns", label: "SNS" },
];

type ProfileResponse = {
  stage_name: string | null;
  gender: Gender | null;
  gender_self_description: string | null;
  birth_date: string | null;
  nationality: string | null;
  region_code: Region | null;
  main_category: Category | null;
  sub_categories: string[] | null;
  profile_image_url: string | null;
  profile_image_urls: string[] | null;
  introduction: string | null;
  height_cm: number | null;
  weight_kg: number | null;
  weight_range: WeightRange | null;
  body_type: string[] | null;
  face_type: string[] | null;
  visual_keywords: string[] | null;
  languages: string[] | null;
  skills: string[] | null;
  education_level: EduLevel | null;
  education_major: string | null;
  instagram_url: string | null;
  youtube_url: string | null;
  tiktok_url: string | null;
  career_level: CareerLevel | null;
  career_years: number | null;
  profile_completion_rate: number;
};

export default function TalentProfileModal({ open, onClose }: Props) {
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [savedFlash, setSavedFlash] = useState(false);

  // 필수
  const [gender, setGender] = useState<Gender>("");
  const [genderSelfDesc, setGenderSelfDesc] = useState("");
  const [birthDate, setBirthDate] = useState("");
  const [nationality, setNationality] = useState("");
  const [mainCategory, setMainCategory] = useState<Category>("");
  const [heightCm, setHeightCm] = useState<string>("");
  const [weightKg, setWeightKg] = useState<string>("");

  // 옵션
  const [stageName, setStageName] = useState("");
  const [regionCode, setRegionCode] = useState<Region>("");
  const [subCategoriesCsv, setSubCategoriesCsv] = useState("");
  const [profileImageUrl, setProfileImageUrl] = useState("");
  // 다중 프로필 사진 (5 슬롯). 빈 문자열도 슬롯으로 유지.
  const [profileImageUrls, setProfileImageUrls] = useState<string[]>([
    "", "", "", "", "",
  ]);
  const [introduction, setIntroduction] = useState("");
  const [weightRange, setWeightRange] = useState<WeightRange>("");
  const [bodyType, setBodyType] = useState<string[]>([]);
  const [faceType, setFaceType] = useState<string[]>([]);
  const [visualKeywords, setVisualKeywords] = useState<string[]>([]);
  const [languagesCsv, setLanguagesCsv] = useState("");
  const [skillsCsv, setSkillsCsv] = useState("");
  const [educationLevel, setEducationLevel] = useState<EduLevel>("");
  const [educationMajor, setEducationMajor] = useState("");
  const [instagramUrl, setInstagramUrl] = useState("");
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [tiktokUrl, setTiktokUrl] = useState("");
  const [careerLevel, setCareerLevel] = useState<CareerLevel>("");
  const [careerYears, setCareerYears] = useState<string>("");

  const [completionRate, setCompletionRate] = useState<number | null>(null);
  const [activeTab, setActiveTab] = useState<TabKey>("required");

  // 열릴 때마다 필수 탭으로 초기화
  useEffect(() => {
    if (open) setActiveTab("required");
  }, [open]);

  // ESC 닫기
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  // 열릴 때마다 GET 으로 기존 값 로드
  useEffect(() => {
    if (!open) return;
    let aborted = false;
    setErr(null);
    setLoading(true);
    api
      .get<ProfileResponse>("/talent/profile")
      .then((res) => {
        if (aborted) return;
        const d = res.data;
        setGender((d.gender ?? "") as Gender);
        setGenderSelfDesc(d.gender_self_description ?? "");
        setBirthDate(d.birth_date ?? "");
        setNationality(d.nationality ?? "");
        setMainCategory((d.main_category ?? "") as Category);
        setHeightCm(d.height_cm != null ? String(d.height_cm) : "");
        setWeightKg(d.weight_kg != null ? String(d.weight_kg) : "");

        setStageName(d.stage_name ?? "");
        setRegionCode((d.region_code ?? "") as Region);
        setSubCategoriesCsv(arrToCsv(d.sub_categories));
        setProfileImageUrl(d.profile_image_url ?? "");
        // 기존 URL 들 + 빈 슬롯으로 5칸 채움
        const existing = d.profile_image_urls ?? [];
        setProfileImageUrls(
          [...existing, "", "", "", "", ""].slice(0, 5),
        );
        setIntroduction(d.introduction ?? "");
        setWeightRange((d.weight_range ?? "") as WeightRange);
        setBodyType(d.body_type ?? []);
        setFaceType(d.face_type ?? []);
        setVisualKeywords(d.visual_keywords ?? []);
        setLanguagesCsv(arrToCsv(d.languages));
        setSkillsCsv(arrToCsv(d.skills));
        setEducationLevel((d.education_level ?? "") as EduLevel);
        setEducationMajor(d.education_major ?? "");
        setInstagramUrl(d.instagram_url ?? "");
        setYoutubeUrl(d.youtube_url ?? "");
        setTiktokUrl(d.tiktok_url ?? "");
        setCareerLevel((d.career_level ?? "") as CareerLevel);
        setCareerYears(d.career_years != null ? String(d.career_years) : "");
        setCompletionRate(d.profile_completion_rate);
      })
      .catch((e) => {
        if (aborted) return;
        setErr(e?.response?.data?.detail ?? "프로필을 불러오지 못했습니다.");
      })
      .finally(() => {
        if (!aborted) setLoading(false);
      });
    return () => {
      aborted = true;
    };
  }, [open]);

  const profileImageCount = useMemo(
    () => profileImageUrls.filter((u) => u.trim()).length,
    [profileImageUrls],
  );

  const requiredFilled = useMemo(
    () =>
      gender !== "" &&
      birthDate !== "" &&
      nationality.trim() !== "" &&
      mainCategory !== "" &&
      heightCm !== "" &&
      weightKg !== "" &&
      profileImageCount >= 1 &&
      (gender !== "SELF_DESCRIBED" || genderSelfDesc.trim() !== "") &&
      (educationLevel !== "BACHELOR" && educationLevel !== "GRADUATE"
        ? true
        : educationMajor.trim() !== ""),
    [
      gender, birthDate, nationality, mainCategory, heightCm, weightKg,
      profileImageCount, genderSelfDesc, educationLevel, educationMajor,
    ],
  );

  const onSubmit = async () => {
    setErr(null);
    if (!requiredFilled) {
      setErr("필수 항목을 모두 입력해주세요.");
      return;
    }
    setSaving(true);
    try {
      const payload: Record<string, unknown> = {
        gender,
        birth_date: birthDate,
        nationality: nationality.trim(),
        main_category: mainCategory,
        height_cm: Number(heightCm),
        weight_kg: Number(weightKg),
      };
      if (gender === "SELF_DESCRIBED") {
        payload.gender_self_description = genderSelfDesc.trim();
      }
      if (stageName.trim()) payload.stage_name = stageName.trim();
      if (regionCode) payload.region_code = regionCode;
      if (subCategoriesCsv.trim()) payload.sub_categories = csvToArr(subCategoriesCsv);
      if (profileImageUrl.trim()) payload.profile_image_url = profileImageUrl.trim();
      payload.profile_image_urls = profileImageUrls
        .map((u) => u.trim())
        .filter(Boolean);
      if (introduction.trim()) payload.introduction = introduction.trim();
      if (weightRange) payload.weight_range = weightRange;
      if (bodyType.length) payload.body_type = bodyType;
      if (faceType.length) payload.face_type = faceType;
      if (visualKeywords.length) payload.visual_keywords = visualKeywords;
      if (languagesCsv.trim()) payload.languages = csvToArr(languagesCsv);
      if (skillsCsv.trim()) payload.skills = csvToArr(skillsCsv);
      if (educationLevel) payload.education_level = educationLevel;
      if (
        (educationLevel === "BACHELOR" || educationLevel === "GRADUATE") &&
        educationMajor.trim()
      ) {
        payload.education_major = educationMajor.trim();
      }
      if (instagramUrl.trim()) payload.instagram_url = instagramUrl.trim();
      if (youtubeUrl.trim()) payload.youtube_url = youtubeUrl.trim();
      if (tiktokUrl.trim()) payload.tiktok_url = tiktokUrl.trim();
      if (careerLevel) payload.career_level = careerLevel;
      if (careerYears !== "") payload.career_years = Number(careerYears);

      const res = await api.put<ProfileResponse>("/talent/profile", payload);
      setCompletionRate(res.data.profile_completion_rate);
      setSavedFlash(true);
      setTimeout(() => {
        setSavedFlash(false);
        onClose();
      }, 1200);
    } catch (e) {
      const detail =
        (e as { response?: { data?: { detail?: unknown } } })?.response?.data
          ?.detail;
      setErr(
        typeof detail === "string"
          ? detail
          : "저장 중 오류가 발생했습니다.",
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <AnimatePresence>
      {open && (
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
            className="relative w-full max-w-5xl h-[90vh] flex flex-col rounded-2xl bg-white shadow-2xl overflow-hidden"
          >
            <button
              type="button"
              onClick={onClose}
              aria-label="닫기"
              className="absolute right-4 top-4 z-10 rounded-full p-1.5 text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="px-6 sm:px-8 pt-6 pb-3">
              <h2 className="text-xl sm:text-2xl font-bold text-zinc-900">
                내 프로필 정보 입력
              </h2>
              <p className="mt-1 text-sm text-zinc-500">
                회원가입에 입력하지 않은 추가 정보를 입력하세요.
                {completionRate != null && (
                  <span className="ml-2 text-zinc-700 font-medium">
                    완성도 {completionRate}%
                  </span>
                )}
              </p>
            </div>

            <div className="bg-white border-b border-zinc-200 px-6 sm:px-8">
              <nav className="flex gap-1 overflow-x-auto -mb-px">
                {TABS.map((t) => {
                  const isActive = activeTab === t.key;
                  const showRequiredDot =
                    t.key === "required" && !loading && !requiredFilled;
                  return (
                    <button
                      key={t.key}
                      type="button"
                      onClick={() => setActiveTab(t.key)}
                      className={
                        "relative px-3.5 py-3 text-sm font-medium whitespace-nowrap border-b-2 transition-colors " +
                        (isActive
                          ? "border-zinc-900 text-zinc-900"
                          : "border-transparent text-zinc-500 hover:text-zinc-800")
                      }
                    >
                      {t.label}
                      {showRequiredDot && (
                        <span className="ml-1.5 inline-block w-1.5 h-1.5 rounded-full bg-red-500 align-middle" />
                      )}
                    </button>
                  );
                })}
              </nav>
            </div>

            <div className="flex-1 overflow-y-auto px-6 sm:px-8 py-4 space-y-6">
              {loading ? (
                <div className="py-12 text-center text-zinc-500">불러오는 중…</div>
              ) : (
                <>
                  {activeTab === "required" && (
                  <>
                  <SectionBare>
                    <div className="sm:col-span-2 grid grid-cols-1 sm:grid-cols-3 gap-x-4 gap-y-3">
                      <Row label="성별 *">
                        <select
                          value={gender}
                          onChange={(e) => setGender(e.target.value as Gender)}
                          className={selectCls}
                        >
                          <option value="">선택</option>
                          {GENDER_OPTIONS.map((o) => (
                            <option key={o.value} value={o.value}>
                              {o.label}
                            </option>
                          ))}
                        </select>
                      </Row>
                      <Row label="생년월일 *">
                        <input
                          type="date"
                          value={birthDate}
                          onChange={(e) => setBirthDate(e.target.value)}
                          className={inputCls}
                        />
                      </Row>
                      <Row label="나이 (자동 계산)">
                        <div
                          className={
                            inputCls +
                            " bg-zinc-50 text-zinc-700 font-medium cursor-default select-none"
                          }
                        >
                          {calcAge(birthDate) != null
                            ? `만 ${calcAge(birthDate)}세`
                            : "—"}
                        </div>
                      </Row>
                    </div>
                    {gender === "SELF_DESCRIBED" && (
                      <Row label="성별 자기기술 *">
                        <input
                          value={genderSelfDesc}
                          onChange={(e) => setGenderSelfDesc(e.target.value)}
                          className={inputCls}
                          maxLength={50}
                        />
                      </Row>
                    )}
                    <Row label="국적 *">
                      <input
                        value={nationality}
                        onChange={(e) => setNationality(e.target.value)}
                        placeholder="대한민국"
                        className={inputCls}
                        maxLength={50}
                      />
                    </Row>
                    <Row label="주 분야 *">
                      <select
                        value={mainCategory}
                        onChange={(e) =>
                          setMainCategory(e.target.value as Category)
                        }
                        className={selectCls}
                      >
                        <option value="">선택</option>
                        {CATEGORY_OPTIONS.map((o) => (
                          <option key={o.value} value={o.value}>
                            {o.label}
                          </option>
                        ))}
                      </select>
                    </Row>
                    <Row label="키 (cm) *">
                      <input
                        type="number"
                        min={50}
                        max={250}
                        value={heightCm}
                        onChange={(e) => setHeightCm(e.target.value)}
                        className={inputCls}
                      />
                    </Row>
                    <Row label="몸무게 (kg) *">
                      <input
                        type="number"
                        min={20}
                        max={300}
                        value={weightKg}
                        onChange={(e) => setWeightKg(e.target.value)}
                        className={inputCls}
                      />
                    </Row>
                  </SectionBare>
                  </>
                  )}

                  {activeTab === "basic" && (
                  <>
                  <SectionBare>
                    <Row label="예명">
                      <input
                        value={stageName}
                        onChange={(e) => setStageName(e.target.value)}
                        className={inputCls}
                        maxLength={100}
                      />
                    </Row>
                    <Row label="거주 지역">
                      <select
                        value={regionCode}
                        onChange={(e) => setRegionCode(e.target.value as Region)}
                        className={selectCls}
                      >
                        <option value="">선택</option>
                        {REGION_OPTIONS.map((o) => (
                          <option key={o.value} value={o.value}>
                            {o.label}
                          </option>
                        ))}
                      </select>
                    </Row>
                    <Row label="부 분야 (쉼표 구분)" hint="예: MODEL, MC">
                      <input
                        value={subCategoriesCsv}
                        onChange={(e) => setSubCategoriesCsv(e.target.value)}
                        className={inputCls}
                      />
                    </Row>
                    <Row label="대표 프로필 URL (옵션)">
                      <input
                        value={profileImageUrl}
                        onChange={(e) => setProfileImageUrl(e.target.value)}
                        className={inputCls}
                        maxLength={500}
                      />
                    </Row>
                    <Row
                      label={`프로필 사진 (${profileImageCount}/5, 최소 1장 필수) *`}
                      hint="이미지 파일 업로드. 1번 슬롯이 대표 사진. jpg/png/webp, 최대 10MB."
                      fullWidth
                    >
                      <div className="grid grid-cols-3 sm:grid-cols-5 gap-3">
                        {profileImageUrls.map((url, idx) => (
                          <ProfilePhotoSlot
                            key={idx}
                            index={idx}
                            url={url}
                            onUploaded={(u) => {
                              const next = [...profileImageUrls];
                              next[idx] = u;
                              setProfileImageUrls(next);
                            }}
                            onRemove={() => {
                              const next = [...profileImageUrls];
                              next[idx] = "";
                              setProfileImageUrls(next);
                            }}
                          />
                        ))}
                      </div>
                    </Row>
                    <Row label="자기소개" fullWidth>
                      <textarea
                        value={introduction}
                        onChange={(e) => setIntroduction(e.target.value)}
                        className={`${inputCls} min-h-[80px]`}
                        rows={3}
                      />
                    </Row>
                  </SectionBare>
                  </>
                  )}

                  {activeTab === "physical" && (
                  <>
                  <SectionBare>
                    <Row label="체형 분류">
                      <select
                        value={weightRange}
                        onChange={(e) =>
                          setWeightRange(e.target.value as WeightRange)
                        }
                        className={selectCls}
                      >
                        <option value="">선택</option>
                        {WEIGHT_RANGE_OPTIONS.map((o) => (
                          <option key={o.value} value={o.value}>
                            {o.label}
                          </option>
                        ))}
                      </select>
                    </Row>
                  </SectionBare>

                  {/* 체형 키워드 */}
                  <Section title={`체형 키워드 (다중 선택)`}>
                    <ChipFieldRow>
                      <ChipMultiSelect
                        options={BODY_TYPE_OPTIONS}
                        selected={bodyType}
                        onChange={setBodyType}
                      />
                    </ChipFieldRow>
                  </Section>

                  {/* 얼굴형 */}
                  <Section title="얼굴형 (다중 선택)">
                    <ChipFieldRow>
                      <ChipMultiSelect
                        options={FACE_TYPE_OPTIONS}
                        selected={faceType}
                        onChange={setFaceType}
                      />
                    </ChipFieldRow>
                  </Section>

                  {/* 비주얼 키워드 */}
                  <Section title="비주얼 키워드 (다중 선택) — 캐스팅 인상">
                    <ChipFieldRow>
                      <div className="space-y-3">
                        {VISUAL_KEYWORD_GROUPS.map((g) => (
                          <div key={g.title}>
                            <div className="text-[11px] font-semibold text-zinc-500 mb-1.5">
                              {g.title}
                            </div>
                            <ChipMultiSelect
                              options={g.options}
                              selected={visualKeywords}
                              onChange={setVisualKeywords}
                            />
                          </div>
                        ))}
                      </div>
                    </ChipFieldRow>
                  </Section>
                  </>
                  )}

                  {activeTab === "career" && (
                  <>
                  {/* 학력/경력 */}
                  <Section title="학력 · 경력">
                    <Row label="학력">
                      <select
                        value={educationLevel}
                        onChange={(e) =>
                          setEducationLevel(e.target.value as EduLevel)
                        }
                        className={selectCls}
                      >
                        <option value="">선택</option>
                        {EDU_LEVEL_OPTIONS.map((o) => (
                          <option key={o.value} value={o.value}>
                            {o.label}
                          </option>
                        ))}
                      </select>
                    </Row>
                    {(educationLevel === "BACHELOR" ||
                      educationLevel === "GRADUATE") && (
                      <Row label="전공 *">
                        <input
                          value={educationMajor}
                          onChange={(e) => setEducationMajor(e.target.value)}
                          placeholder="연극영화과"
                          className={inputCls}
                          maxLength={100}
                        />
                      </Row>
                    )}
                    <Row label="경력 등급">
                      <select
                        value={careerLevel}
                        onChange={(e) =>
                          setCareerLevel(e.target.value as CareerLevel)
                        }
                        className={selectCls}
                      >
                        <option value="">선택</option>
                        {CAREER_LEVEL_OPTIONS.map((o) => (
                          <option key={o.value} value={o.value}>
                            {o.label}
                          </option>
                        ))}
                      </select>
                    </Row>
                    <Row label="경력 연차 (숫자)">
                      <input
                        type="number"
                        min={0}
                        max={80}
                        value={careerYears}
                        onChange={(e) => setCareerYears(e.target.value)}
                        className={inputCls}
                      />
                    </Row>
                  </Section>

                  {/* 언어 / 특기 */}
                  <Section title="언어 · 특기">
                    <Row
                      label="사용 언어 (쉼표 구분)"
                      hint="예: 한국어, 영어, 스페인어, 중국어, 일어"
                    >
                      <input
                        value={languagesCsv}
                        onChange={(e) => setLanguagesCsv(e.target.value)}
                        className={inputCls}
                      />
                    </Row>
                    <Row label="특기 (쉼표 구분)" hint="예: 승마, 피아노">
                      <input
                        value={skillsCsv}
                        onChange={(e) => setSkillsCsv(e.target.value)}
                        className={inputCls}
                      />
                    </Row>
                  </Section>
                  </>
                  )}

                  {activeTab === "sns" && (
                  <>
                  <SectionBare>
                    <Row label="Instagram URL">
                      <input
                        value={instagramUrl}
                        onChange={(e) => setInstagramUrl(e.target.value)}
                        className={inputCls}
                        maxLength={500}
                      />
                    </Row>
                    <Row label="YouTube URL">
                      <input
                        value={youtubeUrl}
                        onChange={(e) => setYoutubeUrl(e.target.value)}
                        className={inputCls}
                        maxLength={500}
                      />
                    </Row>
                    <Row label="TikTok URL">
                      <input
                        value={tiktokUrl}
                        onChange={(e) => setTiktokUrl(e.target.value)}
                        className={inputCls}
                        maxLength={500}
                      />
                    </Row>
                  </SectionBare>
                  </>
                  )}
                </>
              )}

              {err && (
                <div className="rounded-lg bg-red-50 text-red-700 text-sm px-4 py-2">
                  {err}
                </div>
              )}
            </div>

            <div className="bg-white border-t border-zinc-200 px-6 sm:px-8 py-4 flex items-center justify-between gap-3">
              <div className="text-xs text-zinc-500">
                * 표시는 필수 항목입니다.
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100 rounded-lg"
                >
                  취소
                </button>
                <button
                  type="button"
                  onClick={onSubmit}
                  disabled={loading || saving || !requiredFilled}
                  className={`px-5 py-2 text-sm font-semibold rounded-lg inline-flex items-center gap-1.5 transition-colors ${
                    loading || saving || !requiredFilled
                      ? "bg-zinc-200 text-zinc-400 cursor-not-allowed"
                      : "bg-zinc-900 text-white hover:bg-zinc-800"
                  }`}
                >
                  {savedFlash ? (
                    <>
                      <Check className="w-4 h-4" /> 저장됨
                    </>
                  ) : saving ? (
                    "저장 중…"
                  ) : (
                    "확인"
                  )}
                </button>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

const inputCls =
  "w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-zinc-900/10 focus:border-zinc-500";
const selectCls = inputCls + " pr-8";

function Section({
  title,
  required,
  children,
}: {
  title: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <h3 className="text-sm font-bold text-zinc-900">{title}</h3>
        {required && (
          <span className="text-[10px] text-red-600 bg-red-50 rounded px-1.5 py-0.5 font-semibold">
            필수
          </span>
        )}
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-3">
        {children}
      </div>
    </div>
  );
}

// 제목 없는 Section — 탭과 동일한 제목 중복 제거용
function SectionBare({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-3">
      {children}
    </div>
  );
}

function Row({
  label,
  hint,
  fullWidth,
  children,
}: {
  label: string;
  hint?: string;
  fullWidth?: boolean;
  children: React.ReactNode;
}) {
  return (
    <label className={`block ${fullWidth ? "sm:col-span-2" : ""}`}>
      <div className="text-xs font-medium text-zinc-700 mb-1">{label}</div>
      {children}
      {hint && <div className="mt-1 text-[11px] text-zinc-400">{hint}</div>}
    </label>
  );
}

// Section 의 grid 안에서 좌우 1행 전체를 차지하는 wrapper
function ChipFieldRow({ children }: { children: React.ReactNode }) {
  return <div className="sm:col-span-2">{children}</div>;
}

function ProfilePhotoSlot({
  index,
  url,
  onUploaded,
  onRemove,
}: {
  index: number;
  url: string;
  onUploaded: (url: string) => void;
  onRemove: () => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const onPick = async (file: File | null) => {
    if (!file) return;
    setErr(null);
    setUploading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await api.post<{ url: string }>(
        "/talent/profile/photo",
        form,
      );
      onUploaded(res.data.url);
    } catch (e) {
      const detail = (e as { response?: { data?: { detail?: unknown } } })
        ?.response?.data?.detail;
      setErr(typeof detail === "string" ? detail : "업로드 실패");
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  // img src 에 토큰 부착 (인증된 요청용)
  const token = tokenStorage.get();
  const imgSrc = url
    ? url + (url.includes("?") ? "&" : "?") + "token=" + encodeURIComponent(token ?? "")
    : "";

  return (
    <div className="relative aspect-square rounded-lg border border-zinc-300 bg-zinc-50 overflow-hidden group">
      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp,image/gif"
        className="hidden"
        onChange={(e) => onPick(e.target.files?.[0] ?? null)}
      />
      {url ? (
        <>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={imgSrc}
            alt={`프로필 ${index + 1}`}
            className="w-full h-full object-cover"
          />
          <div className="absolute top-1 left-1 bg-black/60 text-white text-[10px] font-bold rounded px-1.5 py-0.5">
            {index === 0 ? "대표" : index + 1}
          </div>
          <div className="absolute inset-x-0 bottom-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex">
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              className="flex-1 text-white text-xs py-1.5 hover:bg-black/30"
              disabled={uploading}
            >
              변경
            </button>
            <button
              type="button"
              onClick={onRemove}
              className="flex-1 text-white text-xs py-1.5 hover:bg-red-600/60 border-l border-white/20"
            >
              <Trash2 className="w-3.5 h-3.5 inline" />
            </button>
          </div>
        </>
      ) : (
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          disabled={uploading}
          className="absolute inset-0 flex flex-col items-center justify-center gap-1 text-zinc-400 hover:text-zinc-700 hover:bg-zinc-100 transition-colors"
        >
          {uploading ? (
            <span className="text-xs">업로드중…</span>
          ) : (
            <>
              <ImagePlus className="w-6 h-6" />
              <span className="text-[11px] font-medium">
                {index === 0 ? "대표 사진" : `사진 ${index + 1}`}
              </span>
            </>
          )}
        </button>
      )}
      {err && (
        <div className="absolute inset-x-0 bottom-0 bg-red-600 text-white text-[10px] px-1 py-0.5 truncate">
          {err}
        </div>
      )}
    </div>
  );
}

function ChipMultiSelect({
  options,
  selected,
  onChange,
}: {
  options: { value: string; label: string }[];
  selected: string[];
  onChange: (next: string[]) => void;
}) {
  const toggle = (v: string) => {
    if (selected.includes(v)) onChange(selected.filter((x) => x !== v));
    else onChange([...selected, v]);
  };
  return (
    <div className="flex flex-wrap gap-1.5">
      {options.map((o) => {
        const active = selected.includes(o.value);
        return (
          <button
            key={o.value}
            type="button"
            onClick={() => toggle(o.value)}
            className={
              "px-2.5 py-1 rounded-full text-xs font-medium border transition-colors " +
              (active
                ? "bg-zinc-900 text-white border-zinc-900 hover:bg-zinc-800"
                : "bg-white text-zinc-700 border-zinc-300 hover:bg-zinc-50")
            }
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
