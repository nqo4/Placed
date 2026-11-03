import React, { useEffect, useState } from "react";
// import { getMyReviews, updateReview, deleteReview } from "../api/reviewAPI"; // 백엔드 연결 시 주석 해제, 아래 더미 블록 삭제
import Header from "../components/Header";
import Footer from "../components/Footer";
import "../pages_CSS/MyReviews.css";

// 임시 더미데이터
const DUMMY_REVIEWS = [
  {
    id: 1,
    place_name: "성심당 본점 (더미)",
    rating: 5,
    content: "튀김소보로가 정말 맛있어요! 줄 서서 먹을 가치 있음",
    created_at: "2025-03-15",
  },
  {
    id: 2,
    place_name: "카페 온도 (더미)",
    rating: 4,
    content: "분위기 너무 좋고 커피도 맛있어요. 주말엔 웨이팅 있음",
    created_at: "2025-04-02",
  },
  {
    id: 3,
    place_name: "대전 엑스포 과학공원 (더미)",
    rating: 3,
    content: "넓고 볼거리는 많은데 일부 시설이 오래됐어요",
    created_at: "2025-04-20",
  },
];

function MyReviews() {
  const [reviews, setReviews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState(null);
  const [editForm, setEditForm] = useState({ content: "", rating: 5 });

  useEffect(() => {
    // 백엔드 연결 시 아래로 교체
    // getMyReviews()
    //   .then((res) => setReviews(res.data))
    //   .catch((err) => console.error(err))
    //   .finally(() => setLoading(false));

    setTimeout(() => {
      setReviews(DUMMY_REVIEWS);
      setLoading(false);
    }, 300);
  }, []);

  const handleEditClick = (review) => {
    setEditingId(review.id);
    setEditForm({ content: review.content, rating: review.rating });
  };

  const handleEditSave = (id) => {
    // 백엔드 연결 시 아래로 교체
    // updateReview(id, editForm.content, editForm.rating)
    //   .then(() => { ... })
    //   .catch((err) => console.error(err));

    setReviews((prev) =>
      prev.map((r) =>
        r.id === id ? { ...r, content: editForm.content, rating: editForm.rating } : r
      )
    );
    setEditingId(null);
  };

  const handleDelete = (id) => {
    if (!window.confirm("리뷰를 삭제하시겠습니까?")) return;

    // 백엔드 연결 시 아래로 교체
    // deleteReview(id)
    //   .then(() => setReviews((prev) => prev.filter((r) => r.id !== id)))
    //   .catch((err) => console.error(err));

    setReviews((prev) => prev.filter((r) => r.id !== id));
  };

  if (loading) return <p className="loading">불러오는 중...</p>;

  return (
    <div className="review-page">
      <Header />

      <section className="review-section">
        <h2>내 리뷰 <span className="review-count">({reviews.length}개)</span></h2>

        {reviews.length === 0 ? (
          <p className="empty">아직 작성한 리뷰가 없습니다.</p>
        ) : (
          <ul className="review-list">
            {reviews.map((r) => (
              <li key={r.id} className="review-item">
                {editingId === r.id ? (
                  <div className="edit-form">
                    <h4>{r.place_name}</h4>
                    <div className="edit-rating">
                      <label>별점</label>
                      <select
                        value={editForm.rating}
                        onChange={(e) =>
                          setEditForm({ ...editForm, rating: Number(e.target.value) })
                        }
                      >
                        {[1, 2, 3, 4, 5].map((n) => (
                          <option key={n} value={n}>{"⭐".repeat(n)} ({n}점)</option>
                        ))}
                      </select>
                    </div>
                    <textarea
                      className="edit-textarea"
                      value={editForm.content}
                      onChange={(e) =>
                        setEditForm({ ...editForm, content: e.target.value })
                      }
                    />
                    <div className="edit-buttons">
                      <button className="save-btn" onClick={() => handleEditSave(r.id)}>저장</button>
                      <button className="cancel-btn" onClick={() => setEditingId(null)}>취소</button>
                    </div>
                  </div>
                ) : (
                  <>
                    <div className="review-header">
                      <h4>{r.place_name}</h4>
                      <div className="review-actions">
                        <button className="edit-btn" onClick={() => handleEditClick(r)}>수정</button>
                        <button className="delete-btn" onClick={() => handleDelete(r.id)}>삭제</button>
                      </div>
                    </div>
                    <p className="rating">{"⭐".repeat(r.rating)} ({r.rating}점)</p>
                    <p className="review-content">{r.content}</p>
                    <small className="review-date">{r.created_at}</small>
                  </>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <Footer />
    </div>
  );
}

export default MyReviews;