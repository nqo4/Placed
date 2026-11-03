import React from "react";
import { useNavigate } from "react-router-dom";
import Footer from "../components/Footer";
import "../pages_CSS/MainGuest.css";

function MainGuest() {
  const navigate = useNavigate();

  return (
    <div className="guest-page">
     
      <header className="guest-header">
        <div className="logo" onClick={() => navigate("/")}>
          <img src="/placed_logo.png" alt="PLACED Logo" className="logo-img" />
          <span className="logo-text">PLACED</span>
        </div>

        <nav className="nav">
          <button onClick={() => navigate("/login")} className="nav-btn">
            로그인
          </button>
          <button onClick={() => navigate("/signup")} className="nav-btn signup">
            회원가입
          </button>
        </nav>
      </header>

     
      <section className="hero">
        <div className="hero-content">
          <h1>광고 없는 진짜 리뷰,<br />이제 진짜만 보세요.</h1>

          <p>
            PLACED는 AI가 광고 게시물을 걸러내고,<br />
            신뢰할 수 있는 리뷰만을 보여주는 공간 추천 플랫폼입니다.
          </p>
          <button className="cta-btn" onClick={() => navigate("/login")}>
            지금 시작하기
          </button>
        </div>
      </section>

      
      <section className="features">
        <h2>PLACED의 주요 기능</h2>
        <div className="feature-list">
          <div className="feature-card">
            <img src="https://cdn-icons-png.flaticon.com/512/4712/4712107.png" alt="AI 광고 감지" />
            <h3>AI 광고 감지</h3>
            <p>AI가 광고성 게시물을 자동으로 필터링합니다.</p>
          </div>
          <div className="feature-card">
            <img src="https://cdn-icons-png.flaticon.com/512/751/751463.png" alt="키워드 검색" />
            <h3>키워드 검색</h3>
            <p>“감성 카페”, “모임 공간” 등 자연어 검색 지원</p>
          </div>
          <div className="feature-card">
            <img src="https://cdn-icons-png.flaticon.com/512/1029/1029183.png" alt="개인 맞춤 추천" />
            <h3>개인 맞춤 추천</h3>
            <p>사용자 취향을 학습하여 최적의 공간을 추천합니다.</p>
          </div>
        </div>
      </section>

     
      <section className="recommend">
        <h2>지금 인기 있는 공간</h2>
        <div className="card-list">
          <div className="card">
            <img src="https://t4.ftcdn.net/jpg/16/79/44/21/240_F_1679442196_OEsi0AFKie6hYMBpvmXwwRgRYGV4U6Lz.jpg" alt="카페" />
            <p>카페</p>
          </div>
          <div className="card">
            <img src="https://t4.ftcdn.net/jpg/16/79/44/21/240_F_1679442196_OEsi0AFKie6hYMBpvmXwwRgRYGV4U6Lz.jpg" alt="식당" />
            <p>식당</p>
          </div>
          <div className="card">
            <img src="https://t4.ftcdn.net/jpg/16/79/44/21/240_F_1679442196_OEsi0AFKie6hYMBpvmXwwRgRYGV4U6Lz.jpg" alt="모임공간" />
            <p>스터디룸</p>
          </div>
        </div>
      </section>

     
      <Footer />
    </div>
  );
}

export default MainGuest;
