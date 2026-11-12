import API from "./axiosInstance";
import { API_ROUTES } from "../config";

export const getRecentPlaces = (limit = 20) =>
  API.get(`${API_ROUTES.RECENT_PLACES}?limit=${limit}`);
