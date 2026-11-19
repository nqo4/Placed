import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getInquiryDetail } from "../api/inquiryAPI";
import Footer from "../components/Footer";
import Header from "../components/Header";
import "../pages_CSS/InquiryDetail.css";

const CATEGORY_LABEL = { account: "계정 문의", service: "서비스 이용", etc: "기타" };

function InquiryDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [inquiry, setInquiry] = useState(null);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    getInquiryDetail(id)    
      .then((res) => setInquiry(res.data))
      .catch(() => setLoadError(true));
  }, [id]);

  return (
    <div className="detail-page">
    
      <Header />

   
      <section className="detail-section">
        <h2>문의 상세보기</h2>

        {!inquiry && !loadError && <p>불러오는 중...</p>}
        {loadError && (
          <div className="detail-box">
            <p className="error">문의를 불러오지 못했어요. 잠시 후 다시 시도해주세요.</p>
            <button className="back-btn" onClick={() => navigate("/inquiries")}>
              ← 목록으로 돌아가기
            </button>
          </div>
        )}

        {inquiry && (
          <div className="detail-box">
            <p><strong>문의 유형:</strong> {CATEGORY_LABEL[inquiry.category] || inquiry.category}</p>
            <p><strong>문의 내용:</strong></p>
            <p className="content">{inquiry.message}</p>
            <p className="date"><strong>작성일:</strong> {inquiry.created_at?.slice(0, 10)}</p>

            <div className={`answer-box ${inquiry.answer ? "" : "empty"}`}>
              <p className="answer-title">관리자 답변</p>
              {inquiry.answer ? (
                <p className="answer-text">{inquiry.answer}</p>
              ) : (
                <p className="answer-text">아직 답변이 등록되지 않았어요. 조금만 기다려 주세요.</p>
              )}
            </div>

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
