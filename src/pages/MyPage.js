import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import Header from "../components/Header";
import Footer from "../components/Footer";
import "../pages_CSS/MyPage.css";

function MyPage() {
  const navigate = useNavigate();

  const savedUser = JSON.parse(localStorage.getItem("user") || "{}");
  const [userInfo, setUserInfo] = useState({
    name: savedUser.username || "사용자 (더미)",
    email: savedUser.email || "user@example.com (더미)",
    newPassword: "",
    confirmPassword: "",
  });

  const handleChange = (e) => {
    const { name, value } = e.target;
    setUserInfo({ ...userInfo, [name]: value });
  };

  const handleSave = (e) => {
    e.preventDefault();
    if (userInfo.newPassword !== userInfo.confirmPassword) {
      alert("비밀번호가 일치하지 않습니다!");
      return;
    }
    alert("변경 사항이 저장되었습니다.");
  };

  return (
    <div className="mypage-wrapper">
      <Header />

      <div className="mypage-layout">
        {/* 왼쪽 사이드바 메뉴 */}
        <aside className="mypage-sidebar">
          <nav>
            <button className="menu-btn active">내 계정 관리</button>
            <button className="menu-btn" onClick={() => navigate("/reviews")}>리뷰 관리</button>
            <button className="menu-btn" onClick={() => navigate("/my-places")}>내 장소</button>
            <button className="menu-btn" onClick={() => navigate("/contact")}>문의하기</button>
            <div className="sidebar-divider"></div>
            <button className="menu-btn logout-btn" onClick={() => {
              localStorage.removeItem("token");
              navigate("/");
            }}>
              로그아웃
            </button>
          </nav>
        </aside>

        {/* 오른쪽 계정 설정 카드 */}
        <main className="settings-section">
          <h2>계정 설정</h2>
          <div className="profile-banner">
            <div className="profile-avatar">
              <span className="avatar-icon">👤</span>
            </div>
            <div className="profile-text">
              <p className="profile-name">{userInfo.name}</p>
            </div>
          </div>

          <form className="settings-form" onSubmit={handleSave}>
            <div className="form-row">
              <div className="form-field">
                <label>아이디</label>
                <input type="text" value={userInfo.email} readOnly />
              </div>
              <div className="form-field">
                <label>이름</label>
                <input
                  type="text"
                  name="name"
                  value={userInfo.name}
                  onChange={handleChange}
                />
              </div>
            </div>
            <div className="form-row">
              <div className="form-field">
                <label>새 비밀번호</label>
                <input
                  type="password"
                  name="newPassword"
                  placeholder="변경할 비밀번호"
                  onChange={handleChange}
                />
              </div>
              <div className="form-field">
                <label>비밀번호 확인</label>
                <input
                  type="password"
                  name="confirmPassword"
                  placeholder="비밀번호 재입력"
                  onChange={handleChange}
                />
              </div>
            </div>
            <div className="form-buttons">
              <button type="button" className="cancel-btn" onClick={() => navigate("/main")}>
                취소
              </button>
              <button type="submit" className="save-btn">
                변경 사항 저장
              </button>
            </div>
          </form>
        </main>
      </div>
      <Footer />
    </div>
  );
}

export default MyPage;