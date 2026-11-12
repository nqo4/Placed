import axios from "axios";
import { API_ROUTES, BASE_URL } from "../config";

const API = axios.create({
  baseURL: BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// localStorage의 "token" 키로 JWT 읽어서 모든 요청에 자동으로 헤더 붙여줌
API.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const clearAuth = () => {
  ["token", "refresh", "is_admin", "user"].forEach((key) => localStorage.removeItem(key));
};

// 동시에 여러 요청이 401 나도 재발급은 한 번만
let refreshing = null;

const refreshToken = () => {
  if (!refreshing) {
    refreshing = axios
      .post(`${BASE_URL}${API_ROUTES.LOGIN_REFRESH}`, { refresh: localStorage.getItem("refresh") })
      .then((res) => {
        localStorage.setItem("token", res.data.access);
        if (res.data.refresh) localStorage.setItem("refresh", res.data.refresh);
        return res.data.access;
      })
      .finally(() => {
        refreshing = null;
      });
  }
  return refreshing;
};

// 토큰 만료(401)면 refresh로 새 토큰 받아서 다시 요청, 그것도 실패하면 로그인 화면으로
API.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config;
    if (error.response?.status !== 401 || !original || original._retry) {
      return Promise.reject(error);
    }

    if (!localStorage.getItem("token")) {
      return Promise.reject(error);
    }

    if (localStorage.getItem("refresh")) {
      original._retry = true;
      try {
        const access = await refreshToken();
        original.headers.Authorization = `Bearer ${access}`;
        return API(original);
      } catch (e) {
        // 아래에서 로그아웃 처리
      }
    }

    clearAuth();
    alert("로그인이 만료되었습니다. 다시 로그인해주세요.");
    window.location.href = "/login";
    return Promise.reject(error);
  }
);

export default API;
