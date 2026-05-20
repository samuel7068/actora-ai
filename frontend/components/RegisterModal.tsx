"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Building2, Check, User, X } from "lucide-react";
import { useEffect, useState } from "react";

import { useAuth } from "@/store/auth";

type Props = {
  open: boolean;
  onClose: () => void;
};

type AccountType = "TALENT" | "AGENCY";

const AGENCY_TYPE_OPTIONS: {
  value: "AGENCY" | "PRODUCTION" | "BRAND" | "CASTING";
  label: string;
}[] = [
  { value: "AGENCY", label: "연예/모델 에이전시" },
  { value: "PRODUCTION", label: "영상/영화 제작사" },
  { value: "BRAND", label: "브랜드/기업" },
  { value: "CASTING", label: "광고/캐스팅 대행사" },
];

export default function RegisterModal({ open, onClose }: Props) {
  const { registerTalent, registerAgency, loading, error, account } = useAuth();

  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [accountType, setAccountType] = useState<AccountType | null>(null);

  // 공통
  const [loginId, setLoginId] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");

  // talent
  const [stageName, setStageName] = useState("");

  // agency
  const [agencyName, setAgencyName] = useState("");
  const [agencyType, setAgencyType] = useState<
    "AGENCY" | "PRODUCTION" | "BRAND" | "CASTING"
  >("AGENCY");
  const [businessNumber, setBusinessNumber] = useState("");

  // ESC 닫기
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  // 모달 닫힐 때 초기화
  useEffect(() => {
    if (!open) {
      setStep(1);
      setAccountType(null);
      setLoginId("");
      setEmail("");
      setPassword("");
      setName("");
      setStageName("");
      setAgencyName("");
      setAgencyType("AGENCY");
      setBusinessNumber("");
    }
  }, [open]);

  // step 3 에서 4초 후 자동 닫기
  useEffect(() => {
    if (step !== 3) return;
    const t = setTimeout(() => onClose(), 4000);
    return () => clearTimeout(t);
  }, [step, onClose]);

  const onSelectType = (t: AccountType) => {
    setAccountType(t);
    setStep(2);
  };

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (loading || !accountType) return;
    try {
      if (accountType === "TALENT") {
        await registerTalent({
          login_id: loginId.trim(),
          email: email.trim(),
          password,
          name: name.trim(),
          stage_name: stageName.trim() || undefined,
        });
      } else {
        await registerAgency({
          login_id: loginId.trim(),
          email: email.trim(),
          password,
          name: name.trim(),
          agency_name: agencyName.trim(),
          agency_type: agencyType,
          business_number: businessNumber.trim() || undefined,
        });
      }
      setStep(3);
    } catch {
      /* error 표시 — store 에 보관됨 */
    }
  };

  const canSubmit =
    loginId.trim().length >= 3 &&
    email.trim().length > 0 &&
    password.length >= 4 &&
    name.trim().length >= 1 &&
    (accountType !== "AGENCY" || agencyName.trim().length >= 1);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          key="backdrop"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm px-4"
          onClick={onClose}
        >
          <motion.div
            initial={{ opacity: 0, y: 16, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.98 }}
            transition={{ duration: 0.25, ease: "easeOut" as const }}
            className="relative w-full max-w-lg rounded-2xl bg-white p-7 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              type="button"
              onClick={onClose}
              aria-label="닫기"
              className="absolute right-4 top-4 text-zinc-400 hover:text-zinc-700 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>

            {/* Step 1: 유형 선택 */}
            {step === 1 && (
              <motion.div
                key="step1"
                initial={{ opacity: 0, x: 16 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -16 }}
                transition={{ duration: 0.2 }}
              >
                <h2 className="text-2xl font-bold text-zinc-900 tracking-tight">회원가입</h2>
                <p className="mt-1 text-sm text-zinc-500">어떤 유형으로 가입하시나요?</p>

                <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <button
                    type="button"
                    onClick={() => onSelectType("TALENT")}
                    className="group rounded-xl border-2 border-zinc-200 hover:border-zinc-900 p-6 text-left transition-colors"
                  >
                    <User className="w-10 h-10 text-zinc-700 group-hover:text-zinc-900" strokeWidth={1.5} />
                    <div className="mt-4 font-bold text-zinc-900 text-lg">연기자·모델</div>
                    <div className="mt-1 text-xs text-zinc-500">
                      본인의 프로필을 등록하고 캐스팅에 지원하세요
                    </div>
                  </button>

                  <button
                    type="button"
                    onClick={() => onSelectType("AGENCY")}
                    className="group rounded-xl border-2 border-zinc-200 hover:border-zinc-900 p-6 text-left transition-colors"
                  >
                    <Building2 className="w-10 h-10 text-zinc-700 group-hover:text-zinc-900" strokeWidth={1.5} />
                    <div className="mt-4 font-bold text-zinc-900 text-lg">광고주·제작사</div>
                    <div className="mt-1 text-xs text-zinc-500">
                      인재를 찾고 캐스팅을 진행하세요
                    </div>
                  </button>
                </div>

                <p className="mt-5 text-center text-sm text-zinc-500">
                  이미 계정이 있으신가요?{" "}
                  <button
                    type="button"
                    onClick={onClose}
                    className="font-semibold text-zinc-900 hover:underline"
                  >
                    로그인
                  </button>
                </p>
              </motion.div>
            )}

            {/* Step 2: 가입 정보 */}
            {step === 2 && (
              <motion.form
                key="step2"
                onSubmit={onSubmit}
                initial={{ opacity: 0, x: 16 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -16 }}
                transition={{ duration: 0.2 }}
              >
                <h2 className="text-2xl font-bold text-zinc-900 tracking-tight">
                  {accountType === "TALENT" ? "연기자·모델 가입" : "광고주·제작사 가입"}
                </h2>
                <p className="mt-1 text-sm text-zinc-500">기본 정보를 입력해주세요</p>

                <div className="mt-5 space-y-4">
                  <Field label="로그인 아이디" required>
                    <input
                      type="text"
                      value={loginId}
                      onChange={(e) => setLoginId(e.target.value)}
                      autoComplete="off"
                      required
                      minLength={3}
                      className={inputCls}
                      placeholder="3자 이상"
                    />
                  </Field>

                  <Field label="이메일" required>
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      autoComplete="off"
                      required
                      className={inputCls}
                    />
                  </Field>

                  <Field label="비밀번호" required>
                    <input
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      autoComplete="new-password"
                      required
                      minLength={4}
                      className={inputCls}
                      placeholder="4자 이상"
                    />
                  </Field>

                  <Field label="본명" required>
                    <input
                      type="text"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      autoComplete="off"
                      required
                      className={inputCls}
                    />
                  </Field>

                  {accountType === "TALENT" && (
                    <Field label="활동명 (선택)">
                      <input
                        type="text"
                        value={stageName}
                        onChange={(e) => setStageName(e.target.value)}
                        autoComplete="off"
                        className={inputCls}
                      />
                    </Field>
                  )}

                  {accountType === "AGENCY" && (
                    <>
                      <Field label="회사명" required>
                        <input
                          type="text"
                          value={agencyName}
                          onChange={(e) => setAgencyName(e.target.value)}
                          autoComplete="off"
                          required
                          className={inputCls}
                        />
                      </Field>
                      <Field label="업체 유형" required>
                        <select
                          value={agencyType}
                          onChange={(e) =>
                            setAgencyType(e.target.value as typeof agencyType)
                          }
                          className={inputCls}
                        >
                          {AGENCY_TYPE_OPTIONS.map((o) => (
                            <option key={o.value} value={o.value}>
                              {o.label}
                            </option>
                          ))}
                        </select>
                      </Field>
                      <Field label="사업자등록번호 (선택)">
                        <input
                          type="text"
                          value={businessNumber}
                          onChange={(e) => setBusinessNumber(e.target.value)}
                          autoComplete="off"
                          className={inputCls}
                          placeholder="000-00-00000"
                        />
                      </Field>
                    </>
                  )}
                </div>

                {error && (
                  <div className="mt-4 rounded-lg bg-red-50 border border-red-200 px-3.5 py-2.5 text-sm text-red-700">
                    {error}
                  </div>
                )}

                <div className="mt-6 flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setStep(1)}
                    className="flex-shrink-0 rounded-lg px-4 py-3 text-sm font-medium text-zinc-700 hover:bg-zinc-100 transition-colors"
                  >
                    ← 이전
                  </button>
                  <button
                    type="submit"
                    disabled={loading || !canSubmit}
                    className="flex-1 rounded-lg bg-zinc-900 px-4 py-3 text-sm font-semibold text-white hover:bg-zinc-800 disabled:bg-zinc-400 disabled:cursor-not-allowed transition-colors"
                  >
                    {loading ? "가입 중..." : "가입 완료"}
                  </button>
                </div>
              </motion.form>
            )}

            {/* Step 3: 환영 */}
            {step === 3 && account && (
              <motion.div
                key="step3"
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.3 }}
                className="text-center py-6"
              >
                <div className="mx-auto w-14 h-14 rounded-full bg-emerald-100 flex items-center justify-center">
                  <Check className="w-7 h-7 text-emerald-600" strokeWidth={2.5} />
                </div>
                <h2 className="mt-4 text-2xl font-bold text-zinc-900">
                  {account.name}님, 환영합니다!
                </h2>
                <p className="mt-2 text-sm text-zinc-500">
                  {account.role_display_name} 계정이 생성되었습니다.
                  <br />
                  자동으로 로그인됩니다.
                </p>
                <button
                  type="button"
                  onClick={onClose}
                  className="mt-6 rounded-lg bg-zinc-900 px-5 py-2.5 text-sm font-semibold text-white hover:bg-zinc-800 transition-colors"
                >
                  시작하기
                </button>
              </motion.div>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

const inputCls =
  "w-full rounded-lg border border-zinc-300 px-3.5 py-2.5 text-zinc-900 placeholder:text-zinc-400 focus:border-zinc-900 focus:outline-none transition-colors";

function Field({
  label,
  required,
  children,
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-zinc-700 mb-1.5">
        {label}
        {required && <span className="ml-1 text-red-500">*</span>}
      </label>
      {children}
    </div>
  );
}
