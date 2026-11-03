import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getMyInquiries } from "../api/inquiryAPI";
import Footer from "../components/Footer";
import "../pages_CSS/MyInquiry.css";

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
     
      <header className="user-header">
        <div className="logo" onClick={() => navigate("/main")}>
          <img src="/placed_logo.png" alt="PLACED Logo" className="logo-img" />
          <span className="logo-text">PLACED</span>
        </div>

        <nav className="nav">
          <button onClick={() => navigate("/main")}>홈</button>
          <button onClick={() => navigate("/contact")}>문의하기</button>
        </nav>
      </header>

     
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
                <p><strong>유형:</strong> {item.category}</p>
                <p><strong>내용:</strong> {item.message}</p>
                <p className="date">{item.created_at}</p>
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
