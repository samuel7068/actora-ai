import { create } from "zustand";

import { api, tokenStorage } from "@/lib/api";

export type AccountInfo = {
  account_id: number;
  login_id: string;
  email: string;
  name: string;
  account_type: "ADMIN" | "TALENT" | "AGENCY";
  role_code: string | null; // SUPER/OPERATOR/CS or DEFAULT
  role_display_name: string | null; // "최고관리자", "연기자" 등
  last_login_at: string | null;
  permission: {
    menu?: string[]; // ["profile","portfolio",...] 또는 ["*"]
    [key: string]: unknown;
  };
};

export type TalentRegisterData = {
  login_id: string;
  email: string;
  password: string;
  name: string;
  stage_name?: string;
};

export type AgencyRegisterData = {
  login_id: string;
  email: string;
  password: string;
  name: string;
  agency_name: string;
  agency_type: "AGENCY" | "PRODUCTION" | "BRAND" | "CASTING";
  business_number?: string;
};

type AuthState = {
  account: AccountInfo | null;
  loading: boolean;
  error: string | null;

  login: (identifier: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  restore: () => Promise<void>;
  registerTalent: (data: TalentRegisterData) => Promise<void>;
  registerAgency: (data: AgencyRegisterData) => Promise<void>;
};


function mapRegisterError(detail: string): string {
  const map: Record<string, string> = {
    DUPLICATE_LOGIN_ID: "이미 사용 중인 아이디입니다",
    DUPLICATE_EMAIL: "이미 사용 중인 이메일입니다",
    DUPLICATE_LOGIN_ID_OR_EMAIL: "이미 사용 중인 아이디 또는 이메일입니다",
    DUPLICATE_BUSINESS_NUMBER: "이미 등록된 사업자번호입니다",
  };
  return map[detail] ?? "회원가입에 실패했습니다";
}

export const useAuth = create<AuthState>((set) => ({
  account: null,
  loading: false,
  error: null,

  login: async (identifier, password) => {
    set({ loading: true, error: null });
    try {
      const res = await api.post("/auth/login", { identifier, password });
      tokenStorage.set(res.data.access_token);
      set({ account: res.data.account, loading: false });
    } catch (e) {
      const detail =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "LOGIN_FAILED";
      const msg =
        detail === "INVALID_CREDENTIALS"
          ? "아이디 또는 비밀번호가 올바르지 않습니다"
          : detail === "INACTIVE_ACCOUNT"
            ? "비활성화된 계정입니다"
            : "로그인에 실패했습니다";
      set({ error: msg, loading: false });
      throw e;
    }
  },

  logout: async () => {
    try {
      await api.post("/auth/logout");
    } catch {
      /* stateless 라 실패해도 무시 */
    }
    tokenStorage.clear();
    set({ account: null, error: null });
  },

  restore: async () => {
    if (!tokenStorage.get()) return;
    try {
      const res = await api.get("/auth/me");
      set({ account: res.data.account });
    } catch {
      tokenStorage.clear();
      set({ account: null });
    }
  },

  registerTalent: async (data) => {
    set({ loading: true, error: null });
    try {
      const res = await api.post("/auth/register/talent", data);
      tokenStorage.set(res.data.access_token);
      set({ account: res.data.account, loading: false });
    } catch (e) {
      const detail =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "";
      set({ error: mapRegisterError(detail), loading: false });
      throw e;
    }
  },

  registerAgency: async (data) => {
    set({ loading: true, error: null });
    try {
      const res = await api.post("/auth/register/agency", data);
      tokenStorage.set(res.data.access_token);
      set({ account: res.data.account, loading: false });
    } catch (e) {
      const detail =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "";
      set({ error: mapRegisterError(detail), loading: false });
      throw e;
    }
  },
}));
