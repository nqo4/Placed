import API from "./axiosInstance";

// 나중에 백엔드에서 IsAdminUser 권한 체크 추가하면 토큰 자동으로 붙음 (axiosInstance에 있음)
export const getAdminUsers = () => API.get("/api/admin/users/");
export const getAdminPlaces = () => API.get("/api/admin/places/");
export const getAdminAnalysis = () => API.get("/api/admin/analysis/");
export const getAdminReviews = () => API.get("/api/admin/reviews/");
export const getAdminInquiries = () => API.get("/api/admin/inquiries/");
