// 백엔드 서버 주소 (배포 시 REACT_APP_API_URL 환경변수로 지정)
export const BASE_URL = process.env.REACT_APP_API_URL || "http://localhost:8000";




export const API_ROUTES = {

  LOGIN: "/api/users/login/",
  LOGIN_REFRESH: "/api/users/login/refresh/",
  SIGNUP: "/api/users/signup/",
  CHECK_ID: "/api/users/check-id/",


  CREATE_INQUIRY: "/api/inquiries/create/",
  MY_INQUIRIES: "/api/inquiries/mine/",
  INQUIRY_DETAIL: "/api/inquiries/",

  PLACE_DETAIL: "/api/places/",
  RECENT_PLACES: "/api/places/recent/",
  REVIEWS_BY_PLACE: "/api/reviews/place/",
  CREATE_REVIEW: "/api/reviews/create/",
  MY_REVIEWS: "/api/reviews/mine/",


  SEARCH: "/api/search",
  SEARCH_ELASTIC: "/api/search/elastic/",
  RECOMMEND_DAILY: "/api/search/recommend/daily/",

  ANALYZE: "/api/analyze/",
};
