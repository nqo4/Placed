import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { loginUser } from "../api/userAPI";
import Footer from "../components/Footer";
import "../pages_CSS/Login.css";

function Login() {
  const navigate = useNavigate();
  const [id, setId] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loggingIn, setLoggingIn] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!id.trim() || !password) {
      setError("아이디와 비밀번호를 입력해주세요.");
      return;
    }
    setLoggingIn(true);
    setError("");
    try {
      const res = await loginUser(id.trim(), password);
      localStorage.setItem("token", res.data.token);
      localStorage.setItem("refresh", res.data.refresh);
      localStorage.setItem("is_admin", res.data.is_staff ? "true" : "false");
      localStorage.setItem("user", JSON.stringify(res.data.user));
      if (res.data.is_staff) {
        navigate("/admin");
      } else {
        navigate("/main");
      }
    } catch (err) {
      setError(
        err.response
          ? "아이디 또는 비밀번호가 맞지 않아요. 다시 확인해주세요."
          : "서버에 연결하지 못했어요. 잠시 후 다시 시도해주세요."
      );
    } finally {
      setLoggingIn(false);
    }
  };

  return (
    <>
      <div className="login-container">
        <div className="login-box">
        <h1>PLACED 로그인</h1>

        <form onSubmit={handleSubmit} noValidate>
          <input
            type="text"
            placeholder="아이디(이메일)를 입력하세요"
            value={id}
            onChange={(e) => { setId(e.target.value); setError(""); }}
            autoComplete="username"
          />
          <input
            type="password"
            placeholder="비밀번호를 입력하세요"
            value={password}
            onChange={(e) => { setPassword(e.target.value); setError(""); }}
            autoComplete="current-password"
          />
          {error && <p className="login-error">{error}</p>}
          <button type="submit" disabled={loggingIn}>
            {loggingIn ? "로그인 중..." : "로그인"}
          </button>
        </form>

        <p className="signup-link">
          계정이 없으신가요?{" "}
          <span onClick={() => navigate("/signup")}>회원가입</span>
        </p>
        </div>
      </div>
      <Footer />
    </>
  );
}

export default Login;