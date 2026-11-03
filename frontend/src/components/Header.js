import React from "react";
import { useNavigate } from "react-router-dom";
import "./Header.css";

function Header({ hideNav = false }) {
  const navigate = useNavigate();

  return (
    <header className="common-header">
      <div className="header-left" onClick={() => navigate("/main")}>
        <img
          src={process.env.PUBLIC_URL + "/placed_logo.png"}
          alt="PLACED Logo"
          className="header-logo-img"
        />
        <h1 className="logo-text">PLACED</h1>
      </div>

      {!hideNav && (
        <nav className="header-nav">
          <button onClick={() => navigate("/main")}>홈</button>
          <button onClick={() => navigate("/my-places")}>내 장소</button>
          <button onClick={() => navigate("/mypage")}>마이페이지</button>
        </nav>
      )}
    </header>
  );
}

export default Header;