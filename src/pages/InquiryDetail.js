import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getInquiryDetail, deleteInquiry } from "../api/inquiryAPI";
import { setFlash } from "../components/FlashMessage";
import Footer from "../components/Footer";
import Header from "../components/Header";
import "../pages_CSS/InquiryDetail.css";

const CATEGORY_LABEL = { account: "계정 문의", service: "서비스 이용", etc: "기타" };

function InquiryDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [inquiry, setInquiry] = useState(null);
  const [loadError, setLoadError] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState("");

  // 본인이 쓴 문의만 삭제 가능 (관리자도 남의 문의는 못 지움)
  const myUsername = (() => {
    try {
      return JSON.parse(localStorage.getItem("user") || "{}").username;
    } catch {
      return undefined;
    }
  })();

  useEffect(() => {
    getInquiryDetail(id)    
      .then((res) => setInquiry(res.data))
      .catch(() => setLoadError(true));
  }, [id]);

  const handleDelete = async () => {
    if (!window.confirm("문의를 삭제하시겠습니까?")) return;
    setDeleting(true);
    setDeleteError("");
    try {
      await deleteInquiry(id);
      setFlash("문의가 삭제되었어요.", "success");
      navigate("/inquiries");
    } catch {
      setDeleteError("삭제에 실패했어요. 잠시 후 다시 시도해주세요.");
      setDeleting(false);
    }
  };

  const isMine = inquiry && inquiry.user?.username === myUsername;

  return (
    <div className="detail-page">
    
      <Header />

   
      <section className="detail-section">
        <h2>내 문의</h2>

        {!inquiry && !loadError && <p>불러오는 중...</p>}
        {loadError && (
          <div className="detail-box">
            <p className="error">문의를 불러오지 못했어요. 잠시 후 다시 시도해주세요.</p>
            <div className="inquiry-bottom">
              <button className="inquiry-back-btn" onClick={() => navigate("/inquiries")}>← 목록으로</button>
            </div>
          </div>
        )}

        {inquiry && (
          <div className="detail-box">
            <div className="inquiry-head">
              <span className="inquiry-badge">{CATEGORY_LABEL[inquiry.category] || inquiry.category}</span>
              <span className="inquiry-date">{inquiry.created_at?.slice(0, 10).replaceAll("-", ".")}</span>
            </div>

            <p className="inquiry-body">{inquiry.message}</p>

            <div className={`answer-box ${inquiry.answer ? "" : "empty"}`}>
              <p className="answer-title">💬 관리자 답변</p>
              {inquiry.answer ? (
                <p className="answer-text">{inquiry.answer}</p>
              ) : (
                <p className="answer-text">아직 답변이 없어요. 확인 후 답변드릴게요.</p>
              )}
            </div>

            {deleteError && <p className="error">{deleteError}</p>}

            <div className="inquiry-bottom">
              <button className="inquiry-back-btn" onClick={() => navigate("/inquiries")}>← 목록으로</button>
              {isMine && (
                <button className="inquiry-delete-btn" onClick={handleDelete} disabled={deleting}>
                  {deleting ? "삭제 중..." : "문의 삭제"}
                </button>
              )}
            </div>
          </div>
        )}
      </section>

     
      <Footer />
    </div>
  );
}

export default InquiryDetail;
