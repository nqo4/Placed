import API from "./axiosInstance";
import { API_ROUTES } from "../config";

export const createInquiry = (category, message) =>
  API.post(API_ROUTES.CREATE_INQUIRY, { category, message });

export const getMyInquiries = () =>
  API.get(API_ROUTES.MY_INQUIRIES);

export const getInquiryDetail = (id) =>
  API.get(`${API_ROUTES.INQUIRY_DETAIL}${id}/`);
