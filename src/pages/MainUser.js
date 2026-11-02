import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Header from "../components/Header";
import RadiusModal from "../components/RadiusModal";
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
  const [distance, setDistance] = useState("1");
  const [isModalOpen, setIsModalOpen] = useState(false);
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
      <section className="welcome" style={{ textAlign: "center", padding: "60px 0" }}>
        <h1>안녕하세요 👋</h1>
        <p>당신에게 어울리는 새로운 공간을 찾아보세요.</p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            navigate(`/search?keyword=${keyword}&dist=${distance}`);
          }}
          style={{ margin: "20px 0" }}
        >
          <input
            type="text"
            placeholder="어디로 갈까요?"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            style={{
              padding: "12px", width: "350px", border: "1px solid #ddd",
              borderRadius: "30px 0 0 30px", outline: "none",
            }}
          />
          <button
            type="submit"
            style={{
              padding: "12px 25px", background: "#007bff", color: "white",
              border: "none", borderRadius: "0 30px 30px 0",
            }}
          >
            검색
          </button>
        </form>
        <button
          onClick={() => setIsModalOpen(true)}
          style={{
            background: "white", border: "1px solid #ddd", borderRadius: "20px",
            padding: "10px 20px", cursor: "pointer",
          }}
        >
          ⚙️ 검색 반경 설정 ({distance}km)
        </button>
      </section>

      {isModalOpen && (
        <RadiusModal
          distance={distance}
          setDistance={setDistance}
          onClose={() => setIsModalOpen(false)}
        />
      )}

      <section className="recommend" style={{ padding: "40px", textAlign: "center", width: "100%", boxSizing: "border-box" }}>
        <h2>오늘의 추천 장소</h2>
        {recommended.length > 0 ? (
          <div className="card-grid" style={{ marginTop: "30px" }}>
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
          <p style={{ color: "#888", marginTop: "30px" }}>{recommendMessage}</p>
        )}
      </section>

      <footer style={{ textAlign: "center", padding: "24px", color: "#aaa", fontSize: "0.85rem", borderTop: "1px solid #eef0f3" }}>
        © 2026 PLACED | <a href="#" style={{ color: "#aaa", textDecoration: "none" }}>이용약관</a> | <a href="#" style={{ color: "#aaa", textDecoration: "none" }}>개인정보처리방침</a>
      </footer>
    </div>
  );
}

export default MainUser;