import axios from "axios";
import { BASE_URL } from "../config";

const API = axios.create({
  baseURL: BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// localStorage의 "token" 키로 JWT 읽어서 모든 요청에 자동으로 헤더 붙여줌
// 백엔드 로그인 응답은 반드시 { token: "..." } 형태여야 함
API.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export default API;
