import API from "./axiosInstance";
import { API_ROUTES } from "../config";

export const searchKeyword = (keyword) =>
  API.get(`${API_ROUTES.SEARCH_ELASTIC}?search=${keyword}`);

export const getDailyRecommendations = () =>
  API.get(API_ROUTES.RECOMMEND_DAILY);
