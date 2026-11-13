import React from "react";
import { useNavigate } from "react-router-dom";
import "./Header.css";

function Header({ hideNav = false }) {
  const navigate = useNavigate();
  const isLoggedIn = !!localStorage.getItem("token");
  const home = isLoggedIn ? "/main" : "/";

  return (
    <header className="common-header">
      <div className="header-left" onClick={() => navigate(home)}>
        <img
          src={process.env.PUBLIC_URL + "/placed_logo.png"}
          alt="PLACED Logo"
          className="header-logo-img"
        />
        <h1 className="logo-text">PLACED</h1>
      </div>

      {!hideNav && (
        <nav className="header-nav">
          <button onClick={() => navigate(home)}>홈</button>
          {isLoggedIn ? (
            <>
              <button onClick={() => navigate("/my-places")}>최근 본 장소</button>
              <button onClick={() => navigate("/mypage")}>마이페이지</button>
            </>
          ) : (
            <button className="header-login-btn" onClick={() => navigate("/login")}>로그인</button>
          )}
        </nav>
      )}
    </header>
  );
}

export default Header;