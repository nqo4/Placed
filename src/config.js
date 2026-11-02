// 백엔드 서버 주소 — 배포 시 여기서 변경
export const BASE_URL = "http://localhost:8000";




export const API_ROUTES = {

  LOGIN: "/api/users/login/",
  SIGNUP: "/api/users/signup/",
  CHECK_ID: "/api/users/check-id/",


  CREATE_INQUIRY: "/api/inquiries/create/",
  MY_INQUIRIES: "/api/inquiries/mine/",
  INQUIRY_DETAIL: "/api/inquiries/",

  PLACE_DETAIL: "/api/places/",
  REVIEWS_BY_PLACE: "/api/reviews/place/",
  CREATE_REVIEW: "/api/reviews/create/",
  MY_REVIEWS: "/api/reviews/mine/",


  SEARCH: "/api/search",
  SEARCH_ELASTIC: "/api/search/elastic/",

  ANALYZE: "/api/analyze/",
};
