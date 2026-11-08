import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import Header from "../components/Header";
import "../pages_CSS/MainUser.css";

function MainUser() {
  const navigate = useNavigate();
  const [keyword, setKeyword] = useState("");

  const recommended = [
    { id: 1, name: "카페 (더미)", img: "https://t4.ftcdn.net/jpg/16/79/44/21/240_F_1679442196_OEsi0AFKie6hYMBpvmXwwRgRYGV4U6Lz.jpg" },
    { id: 2, name: "식당 (더미)", img: "https://t4.ftcdn.net/jpg/16/79/44/21/240_F_1679442196_OEsi0AFKie6hYMBpvmXwwRgRYGV4U6Lz.jpg" },
    { id: 3, name: "스터디룸 (더미)", img: "https://t4.ftcdn.net/jpg/16/79/44/21/240_F_1679442196_OEsi0AFKie6hYMBpvmXwwRgRYGV4U6Lz.jpg" },
  ];

  return (
    <div className="user-page">
      <Header />
      <section className="welcome">
        <h1>안녕하세요 👋</h1>
        <p>당신에게 어울리는 새로운 공간을 찾아보세요.</p>
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
        <div className="card-grid">
          {recommended.map((place) => (
            <div key={place.id} className="card">
              <img src={place.img} alt={place.name} />
              <h4>{place.name}</h4>
            </div>
          ))}
        </div>
      </section>

      <footer className="user-footer">
        © 2026 PLACED | <a href="#">이용약관</a> | <a href="#">개인정보처리방침</a>
      </footer>
    </div>
  );
}

export default MainUser;
