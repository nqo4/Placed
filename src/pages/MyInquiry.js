import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getMyInquiries } from "../api/inquiryAPI";
import Header from "../components/Header";
import Footer from "../components/Footer";
import "../pages_CSS/MyInquiry.css";

const CATEGORY_LABEL = { account: "계정 문의", service: "서비스 이용", etc: "기타" };

function MyInquiry() {
  const navigate = useNavigate();
  const [inquiries, setInquiries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    getMyInquiries()
      .then((res) => {
        setInquiries(res.data);
      })
      .catch((err) => {
        console.error(err);
        setError("문의 내역을 불러오는 중 오류가 발생했습니다.");
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="inquiry-page">
     
      <Header />

     
      <section className="inquiry-section">
        <h2>내 문의내역</h2>

        {loading && <p className="loading">불러오는 중...</p>}
        {error && <p className="error">{error}</p>}

        {!loading && inquiries.length === 0 && (
          <p className="empty">아직 문의내역이 없습니다.</p>
        )}

        {!loading && inquiries.length > 0 && (
          <ul className="inquiry-list">
            {inquiries.map((item) => (
              <li 
                key={item.id} 
                className="inquiry-item"
                onClick={() => navigate(`/inquiry/${item.id}`)}
              >
                <div className="inquiry-item-top">
                  <span className="inquiry-category">{CATEGORY_LABEL[item.category] || item.category}</span>
                  <span className={`inquiry-status ${item.answer ? "done" : "wait"}`}>
                    {item.answer ? "답변 완료" : "답변 대기"}
                  </span>
                </div>
                <p className="inquiry-text">{item.message}</p>
                <p className="date">{item.created_at?.slice(0, 10)}</p>
              </li>
            ))}
          </ul>
        )}

        <button className="write-btn" onClick={() => navigate("/contact")}>
          문의 작성하기
        </button>
      </section>

    
      <Footer />
    </div>
  );
}

export default MyInquiry;
