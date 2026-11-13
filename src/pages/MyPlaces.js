import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getRecentPlaces } from "../api/placeAPI";
import Header from "../components/Header";
import Footer from "../components/Footer";
import "../pages_CSS/MyPlaces.css";

const FALLBACK_IMG = process.env.PUBLIC_URL + "/placeholder.svg";

function timeAgo(value) {
  const date = new Date(value);
  const diff = (Date.now() - date.getTime()) / 1000;
  if (diff < 60) return "방금 전";
  if (diff < 3600) return `${Math.floor(diff / 60)}분 전`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}시간 전`;
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)}일 전`;
  return `${String(date.getMonth() + 1).padStart(2, "0")}.${String(date.getDate()).padStart(2, "0")}`;
}

function MyPlaces() {
  const navigate = useNavigate();
  const isLoggedIn = !!localStorage.getItem("token");
  const [places, setPlaces] = useState([]);
  const [loading, setLoading] = useState(isLoggedIn);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!isLoggedIn) return;
    getRecentPlaces()
      .then((res) => setPlaces(res.data))
      .catch(() => setError("최근 본 장소를 불러오지 못했습니다."))
      .finally(() => setLoading(false));
  }, [isLoggedIn]);

  const renderBody = () => {
    if (!isLoggedIn) {
      return (
        <div className="empty">
          <p>로그인하면 최근 본 장소를 볼 수 있어요.</p>
          <button className="detail-btn" onClick={() => navigate("/login")}>로그인</button>
        </div>
      );
    }
    if (loading) return <p className="loading">불러오는 중...</p>;
    if (error) return <p className="empty">{error}</p>;
    if (places.length === 0) return <p className="empty">아직 본 장소가 없어요.</p>;

    return (
      <ul className="places-list">
        {places.map((p) => (
          <li key={p.id} className="place-item" onClick={() => navigate(`/place/${p.id}`)}>
            <img
              className="place-thumb"
              src={p.images?.[0]?.url || p.image_url || FALLBACK_IMG}
              alt={p.name}
              onError={(e) => { e.currentTarget.src = FALLBACK_IMG; }}
            />
            <div className="place-info">
              <h4>{p.name}</h4>
              <p>{p.address}</p>
            </div>
            <span className="place-viewed">{timeAgo(p.viewed_at)}</span>
          </li>
        ))}
      </ul>
    );
  };

  return (
    <div className="places-page">
      <Header />

      <section className="places-section">
        <h2>
          최근 본 장소
          {isLoggedIn && !loading && !error && <span className="places-count"> ({places.length}개)</span>}
        </h2>
        {renderBody()}
      </section>

      <Footer />
    </div>
  );
}

export default MyPlaces;
