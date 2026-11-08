import API from "./axiosInstance";
import { API_ROUTES } from "../config";

// ⭐ 광고 분석 요청
export const analyzeReview = (name, content) =>
    API.post(API_ROUTES.ANALYZE, {
        name,
        content,
    });
