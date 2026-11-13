import API from "./axiosInstance";
import { API_ROUTES } from "../config";

export const getPlaceDetail = (id) =>
  API.get(`${API_ROUTES.PLACE_DETAIL}${id}/`);

export const getReviewsByPlace = (id) =>
  API.get(`${API_ROUTES.REVIEWS_BY_PLACE}${id}/`);

export const createReview = (placeId, content) =>
  API.post(API_ROUTES.CREATE_REVIEW, { place: placeId, place_id: placeId, content });

export const getMyReviews = () =>
  API.get(API_ROUTES.MY_REVIEWS);

export const deleteReview = (id) =>
  API.delete(`/api/reviews/${id}/`);