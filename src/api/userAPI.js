import API from "./axiosInstance";
import axios from "axios";
import { API_ROUTES, BASE_URL } from "../config";

// 토큰 없는 인스턴스 (회원가입/중복확인 등 공개 API용)
const publicAPI = axios.create({
  baseURL: BASE_URL,
  headers: { "Content-Type": "application/json" },
});

export const loginUser = (id, password) =>
  publicAPI.post(API_ROUTES.LOGIN, { id, password });

export const signupUser = (id, password) =>
  publicAPI.post(API_ROUTES.SIGNUP, { username: id, password });

export const checkDuplicateId = (id) =>
  publicAPI.get(`${API_ROUTES.CHECK_ID}?id=${id}`);
