import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getInquiryDetail } from "../api/inquiryAPI";
import Footer from "../components/Footer";
import Header from "../components/Header";
import "../pages_CSS/InquiryDetail.css";

function InquiryDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [inquiry, setInquiry] = useState(null);

  useEffect(() => {
    getInquiryDetail(id)    
      .then((res) => setInquiry(res.data))
      .catch(() => alert("문의 상세를 불러오지 못했습니다."));
  }, [id]);

  return (
    <div className="detail-page">
    
      <Header />

   
      <section className="detail-section">
        <h2>문의 상세보기</h2>

        {!inquiry && <p>불러오는 중...</p>}

        {inquiry && (
          <div className="detail-box">
            <p><strong>문의 유형:</strong> {inquiry.category}</p>
            <p><strong>문의 내용:</strong></p>
            <p className="content">{inquiry.message}</p>
            <p className="date"><strong>작성일:</strong> {inquiry.created_at}</p>

            <button className="back-btn" onClick={() => navigate("/inquiries")}>
              ← 목록으로 돌아가기
            </button>
          </div>
        )}
      </section>

     
      <Footer />
    </div>
  );
}

export default InquiryDetail;
