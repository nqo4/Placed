import API from "./axiosInstance";
import { API_ROUTES } from "../config";

export const loginUser = (id, password) =>
  API.post(API_ROUTES.LOGIN, { id, password });

export const signupUser = (id, password) =>
  API.post(API_ROUTES.SIGNUP, { username: id, password });

export const checkDuplicateId = (id) =>
  API.get(`${API_ROUTES.CHECK_ID}?id=${id}`);
