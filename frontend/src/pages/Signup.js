import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { signupUser, checkDuplicateId } from "../api/userAPI";
import Footer from "../components/Footer";
import "../pages_CSS/Signup.css";

function Signup() {
  const navigate = useNavigate();
  
  const [id, setId] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [name, setName] = useState("");
  const [toast, setToast] = useState({ msg: "", type: "" });

  const showToast = (msg, type = "info") => {
    setToast({ msg, type });
    setTimeout(() => setToast({ msg: "", type: "" }), 2500);
  };

  const handleCheckDuplicate = async () => {
    if (!id.trim()) return showToast("아이디를 입력하세요.", "error");
    try {
      const res = await checkDuplicateId(id);
      res.data.isAvailable
        ? showToast("사용 가능한 아이디입니다.", "success")
        : showToast("이미 사용 중인 아이디입니다.", "error");
    } catch (err) {
      console.error(err);
      showToast("중복확인 중 오류가 발생했습니다.", "error");
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (password !== confirm) {
      return showToast("비밀번호가 일치하지 않습니다.", "error");
    }

    try {
      await signupUser(id, password, name);
      showToast("회원가입 완료!", "success");
      setTimeout(() => navigate("/login"), 1500);
    } catch (err) {
      console.error(err);
      showToast("회원가입에 실패했습니다.", "error");
    }
  };

  return (
    <>
      {toast.msg && (
        <div style={{
          position: "fixed", top: "24px", left: "50%", transform: "translateX(-50%)",
          background: toast.type === "success" ? "#28a745" : toast.type === "error" ? "#dc3545" : "#333",
          color: "white", padding: "12px 28px", borderRadius: "30px",
          fontSize: "0.9rem", fontWeight: 600, zIndex: 9999,
          boxShadow: "0 4px 16px rgba(0,0,0,0.15)"
        }}>
          {toast.msg}
        </div>
      )}
      <div className="signup-page">
        <div className="signup-card">
        <h1 className="placed-logo">PLACED</h1>

        <form onSubmit={handleSubmit}>
          <div className="input-group">
            <label>이메일 계정</label>
            <div className="input-row">
              <input
                type="text"
                placeholder="user@example.com"
                value={id}
                onChange={(e) => setId(e.target.value)}
                required
              />
              <button type="button" className="check-btn" onClick={handleCheckDuplicate}>
                중복 확인
              </button>
            </div>
          </div>

          <div className="input-group">
            <label>비밀번호</label>
            <input
              type="password"
              placeholder="8자 이상 영문/숫자 조합"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>

          <div className="input-group">
            <label>비밀번호 확인</label>
            <input
              type="password"
              placeholder="비밀번호 다시 입력"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              required
            />
          </div>

          <div className="input-group">
            <label>이름</label>
            <input
              type="text"
              placeholder="이름을 입력하세요"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </div>

          <button type="submit" className="submit-btn">가입하기</button>
        </form>

        <p className="login-prompt">
          이미 계정이 있으신가요?{" "}
          <span onClick={() => navigate("/login")}>로그인</span>
        </p>
        </div>
      </div>
      <Footer />
    </>
  );
}

export default Signup;