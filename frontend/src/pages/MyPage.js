import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Header from "../components/Header";
import Footer from "../components/Footer";
import "../pages_CSS/MyPage.css";
import { clearAuth } from "../api/axiosInstance";
import { getProfile, updateName, changePassword, deleteAccount } from "../api/userAPI";
import { setFlash } from "../components/FlashMessage";

// 받침 있으면 첫 번째, 없으면 두 번째 조사
const josa = (word, withFinal, withoutFinal) => {
  const code = word.charCodeAt(word.length - 1) - 0xac00;
  return word + (code >= 0 && code % 28 !== 0 ? withFinal : withoutFinal);
};

// ["이름", "비밀번호"] → "이름과 비밀번호"
const joinItems = (items) =>
  items.length > 1 ? `${josa(items[0], "과", "와")} ${items.slice(1).join(", ")}` : items[0];

function MyPage() {
  const navigate = useNavigate();

  const savedUser = JSON.parse(localStorage.getItem("user") || "{}");
  const emptyPasswords = { currentPassword: "", newPassword: "", confirmPassword: "" };
  const [profile, setProfile] = useState({ name: savedUser.first_name || "", username: savedUser.username || "" });
  const [userInfo, setUserInfo] = useState({ name: savedUser.first_name || "", ...emptyPasswords });
  const [message, setMessage] = useState({ text: "", type: "" });
  const [saving, setSaving] = useState(false);
  const [showWithdraw, setShowWithdraw] = useState(false);
  const [withdrawPassword, setWithdrawPassword] = useState("");
  const [withdrawError, setWithdrawError] = useState("");
  const [withdrawing, setWithdrawing] = useState(false);

  // 서버에서 최신 내 정보 불러오기
  useEffect(() => {
    getProfile()
      .then((res) => {
        const next = { name: res.data.first_name || "", username: res.data.username };
        setProfile(next);
        setUserInfo((prev) => ({ ...prev, name: next.name }));
      })
      .catch(() => {});
  }, []);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setUserInfo({ ...userInfo, [name]: value });
  };

  const handleLogout = () => {
    clearAuth();
    navigate("/");
  };

  const openWithdraw = () => {
    setShowWithdraw(true);
    setTimeout(() => document.querySelector(".withdraw-area")?.scrollIntoView({ behavior: "smooth", block: "center" }), 0);
  };

  const handleWithdraw = async () => {
    if (!withdrawPassword) {
      setWithdrawError("비밀번호를 입력해주세요.");
      return;
    }
    if (!window.confirm("정말 탈퇴하시겠어요? 되돌릴 수 없어요.")) return;
    setWithdrawing(true);
    try {
      await deleteAccount(withdrawPassword);
      clearAuth();
      setFlash("탈퇴가 완료되었어요.", "success");
      navigate("/");
    } catch (err) {
      setWithdrawError(err.response?.data?.message || "탈퇴에 실패했어요. 잠시 후 다시 시도해주세요.");
    } finally {
      setWithdrawing(false);
    }
  };

  const handleCancel = () => {
    setUserInfo({ name: profile.name, ...emptyPasswords });
    setMessage({ text: "", type: "" });
  };

  const errorText = (err, fallback) =>
    err.response?.data?.message || err.response?.data?.first_name?.[0] || fallback;

  const handleSave = async (e) => {
    e.preventDefault();
    const name = userInfo.name.trim();
    const nameChanged = name !== profile.name;
    const wantsPassword = !!userInfo.newPassword;

    if (!nameChanged && !wantsPassword) {
      setMessage({ text: "변경된 내용이 없어요.", type: "info" });
      return;
    }
    if (nameChanged && !name) {
      setMessage({ text: "이름을 입력해주세요.", type: "error" });
      return;
    }
    if (wantsPassword) {
      if (!userInfo.currentPassword) {
        setMessage({ text: "비밀번호를 바꾸려면 현재 비밀번호를 입력해주세요.", type: "error" });
        return;
      }
      if (userInfo.newPassword.length < 8) {
        setMessage({ text: "새 비밀번호는 8자 이상이어야 해요.", type: "error" });
        return;
      }
      if (userInfo.newPassword !== userInfo.confirmPassword) {
        setMessage({ text: "새 비밀번호와 확인이 일치하지 않아요.", type: "error" });
        return;
      }
    }

    setSaving(true);
    const done = [];
    try {
      if (nameChanged) {
        const res = await updateName(name);
        const newName = res.data.first_name;
        setProfile((prev) => ({ ...prev, name: newName }));
        localStorage.setItem("user", JSON.stringify({ ...savedUser, first_name: newName }));
        done.push("이름");
      }
      if (wantsPassword) {
        await changePassword(userInfo.currentPassword, userInfo.newPassword);
        done.push("비밀번호");
      }
      setUserInfo((prev) => ({ ...prev, ...emptyPasswords }));
      setMessage({ text: `${josa(joinItems(done), "을", "를")} 변경했어요.`, type: "success" });
    } catch (err) {
      const prefix = done.length ? `${josa(joinItems(done), "은", "는")} 변경했지만, ` : "";
      setMessage({ text: prefix + errorText(err, "저장에 실패했어요. 잠시 후 다시 시도해주세요."), type: "error" });
    } finally {
      setSaving(false);
    }
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
            <button className="menu-btn" onClick={() => navigate("/my-places")}>최근 본 장소</button>
            <button className="menu-btn" onClick={() => navigate("/inquiries")}>내 문의</button>
            <div className="sidebar-divider"></div>
            <button className="menu-btn logout-btn" onClick={handleLogout}>
              로그아웃
            </button>
            <button className="menu-btn withdraw-menu" onClick={openWithdraw}>
              회원 탈퇴
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
              <p className="profile-name">{profile.name || profile.username}</p>
            </div>
          </div>

          <form className="settings-form" onSubmit={handleSave}>
            <div className="form-row">
              <div className="form-field">
                <label>아이디</label>
                <input type="text" value={profile.username} readOnly />
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
                <label>현재 비밀번호</label>
                <input
                  type="password"
                  name="currentPassword"
                  placeholder="비밀번호를 바꿀 때만 입력"
                  value={userInfo.currentPassword}
                  onChange={handleChange}
                  autoComplete="current-password"
                />
              </div>
            </div>
            <div className="form-row">
              <div className="form-field">
                <label>새 비밀번호</label>
                <input
                  type="password"
                  name="newPassword"
                  placeholder="8자 이상"
                  value={userInfo.newPassword}
                  onChange={handleChange}
                  autoComplete="new-password"
                />
              </div>
              <div className="form-field">
                <label>비밀번호 확인</label>
                <input
                  type="password"
                  name="confirmPassword"
                  placeholder="새 비밀번호 재입력"
                  value={userInfo.confirmPassword}
                  onChange={handleChange}
                  autoComplete="new-password"
                />
              </div>
            </div>
            {message.text && <p className={`form-message ${message.type}`}>{message.text}</p>}
            <div className="form-buttons">
              <button type="button" className="cancel-btn" onClick={handleCancel}>
                취소
              </button>
              <button type="submit" className="save-btn" disabled={saving}>
                {saving ? "저장 중..." : "변경 사항 저장"}
              </button>
            </div>
          </form>

          <div className="withdraw-area">
            {showWithdraw && (
              <div className="withdraw-box">
                <p className="withdraw-title">회원 탈퇴</p>
                <p className="withdraw-desc">
                  탈퇴하면 계정, 작성한 후기, 최근 본 기록이 모두 삭제되고 되돌릴 수 없어요.
                </p>
                <input
                  type="password"
                  placeholder="비밀번호 확인"
                  value={withdrawPassword}
                  onChange={(e) => { setWithdrawPassword(e.target.value); setWithdrawError(""); }}
                  autoComplete="current-password"
                />
                {withdrawError && <p className="form-message error">{withdrawError}</p>}
                <div className="withdraw-buttons">
                  <button
                    type="button"
                    className="cancel-btn"
                    onClick={() => { setShowWithdraw(false); setWithdrawPassword(""); setWithdrawError(""); }}
                  >
                    취소
                  </button>
                  <button type="button" className="withdraw-btn" onClick={handleWithdraw} disabled={withdrawing}>
                    {withdrawing ? "처리 중..." : "탈퇴하기"}
                  </button>
                </div>
              </div>
            )}
          </div>
        </main>
        <div className="mobile-account">
          <button className="mobile-logout" onClick={handleLogout}>로그아웃</button>
          <span>·</span>
          <button className="mobile-withdraw" onClick={openWithdraw}>회원 탈퇴</button>
        </div>
      </div>
      <Footer />
    </div>
  );
}

export default MyPage;