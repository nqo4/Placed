import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getInquiryDetail } from "../api/inquiryAPI";
import Footer from "../components/Footer";
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
    
      <header className="user-header">
        <div className="logo" onClick={() => navigate("/main")}>
          <img src="/placed_logo.png" alt="PLACED Logo" className="logo-img" />
          <span className="logo-text">PLACED</span>
        </div>

        <nav className="nav">
          <button onClick={() => navigate("/main")}>홈</button>
          <button onClick={() => navigate("/inquiries")}>내 문의내역</button>
        </nav>
      </header>

   
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
