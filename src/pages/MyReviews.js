import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getMyReviews, deleteReview } from "../api/reviewAPI";
import Header from "../components/Header";
import Footer from "../components/Footer";
import "../pages_CSS/MyReviews.css";

function MyReviews() {
  const navigate = useNavigate();
  const isLoggedIn = !!localStorage.getItem("token");
  const [reviews, setReviews] = useState([]);
  const [loading, setLoading] = useState(isLoggedIn);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!isLoggedIn) return;
    getMyReviews()
      .then((res) => setReviews(res.data))
      .catch(() => setError("내 리뷰를 불러오지 못했습니다."))
      .finally(() => setLoading(false));
  }, [isLoggedIn]);

  const handleDelete = (id) => {
    if (!window.confirm("리뷰를 삭제하시겠습니까?")) return;
    deleteReview(id)
      .then(() => setReviews((prev) => prev.filter((r) => r.id !== id)))
      .catch(() => alert("삭제에 실패했습니다. 잠시 후 다시 시도해주세요."));
  };

  const renderBody = () => {
    if (!isLoggedIn) {
      return (
        <div className="empty">
          <p>로그인하면 내가 쓴 리뷰를 볼 수 있어요.</p>
          <button className="login-btn" onClick={() => navigate("/login")}>로그인</button>
        </div>
      );
    }
    if (loading) return <p className="loading">불러오는 중...</p>;
    if (error) return <p className="empty">{error}</p>;
    if (reviews.length === 0) {
      return <p className="empty">아직 작성한 리뷰가 없어요. 장소 상세페이지에서 후기를 남겨보세요.</p>;
    }

    return (
      <ul className="review-list">
        {reviews.map((r) => (
          <li key={r.id} className="review-item">
            <div className="review-header">
              <h4 className="review-place" onClick={() => navigate(`/place/${r.place}`)}>
                {r.place_name} ›
              </h4>
              <button className="delete-btn" onClick={() => handleDelete(r.id)}>삭제</button>
            </div>
            <p className="review-content">{r.content}</p>
            <small className="review-date">{r.created_at?.slice(0, 10)}</small>
          </li>
        ))}
      </ul>
    );
  };

  return (
    <div className="review-page">
      <Header />

      <section className="review-section">
        <h2>
          내 리뷰
          {isLoggedIn && !loading && !error && <span className="review-count"> ({reviews.length}개)</span>}
        </h2>
        {renderBody()}
      </section>

      <Footer />
    </div>
  );
}

export default MyReviews;
