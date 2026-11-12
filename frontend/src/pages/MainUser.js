import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Header from "../components/Header";
import { getDailyRecommendations } from "../api/searchAPI";
import "../pages_CSS/MainUser.css";

function RecommendCard({ type, place, onClick }) {
  // 외부 사진은 링크가 끊긴 경우가 있어, 불러오지 못하면 다음 사진을 보여줍니다.
  const [imageIndex, setImageIndex] = useState(0);
  const imageUrl = place.images?.[imageIndex]?.url;
  const tags = place.keywords?.mood?.length ? place.keywords.mood : place.keywords?.category || [];

  return (
    <div className="card" onClick={onClick}>
      {imageUrl ? (
        <img src={imageUrl} alt={place.name} onError={() => setImageIndex(imageIndex + 1)} />
      ) : (
        <div className="card-no-image">사진 준비 중</div>
      )}
      <div className="card-info">
        <span className="card-type">{type}</span>
        <h4>{place.name}</h4>
        <div className="card-tags">
          {tags.slice(0, 3).map((tag) => (
            <span key={tag}>#{tag}</span>
          ))}
        </div>
      </div>
    </div>
  );
}

function MainUser() {
  const navigate = useNavigate();
  const [keyword, setKeyword] = useState("");
  const [recommended, setRecommended] = useState([]);
  const [recommendMessage, setRecommendMessage] = useState("");

  useEffect(() => {
    if (!localStorage.getItem("token")) {
      setRecommendMessage("로그인하면 맞춤 추천을 볼 수 있어요.");
      return;
    }
    getDailyRecommendations()
      .then((res) => {
        const places = Object.entries(res.data.results || {})
          .filter(([, place]) => place)
          .map(([type, place]) => ({ type, place }));
        setRecommended(places);
        if (places.length === 0) {
          setRecommendMessage(res.data.message || "아직 추천할 장소가 없습니다.");
        }
      })
      .catch(() => setRecommendMessage("추천 장소를 불러오지 못했습니다."));
  }, []);

  return (
    <div className="user-page">
      <Header />
      <section className="welcome">
        <h1>안녕하세요 👋</h1>
        <p>PLACED는 AI가 광고 글을 걸러내고 진짜 후기만 보여주는 장소 검색 사이트예요.</p>
        <form
          className="main-search"
          onSubmit={(e) => {
            e.preventDefault();
            navigate(`/search?keyword=${keyword}`);
          }}
        >
          <input
            type="text"
            placeholder="어디로 갈까요?"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
          />
          <button type="submit">검색</button>
        </form>
      </section>

      <section className="recommend">
        <h2>오늘의 추천 장소</h2>
        {recommended.length > 0 ? (
          <div className="card-grid">
            {recommended.map(({ type, place }) => (
              <RecommendCard
                key={place.id}
                type={type}
                place={place}
                onClick={() => navigate(`/place/${place.id}`)}
              />
            ))}
          </div>
        ) : (
          <p className="recommend-message">{recommendMessage}</p>
        )}
      </section>

      <footer className="user-footer">
        © 2026 PLACED | <a href="#">이용약관</a> | <a href="#">개인정보처리방침</a>
      </footer>
    </div>
  );
}

export default MainUser;
