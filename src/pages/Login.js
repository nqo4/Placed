import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { loginUser } from "../api/userAPI";
import Footer from "../components/Footer";
import "../pages_CSS/Login.css";

// 임시 더미 계정
// const DUMMY_USERS = [
//   { id: "user1", password: "1234" },
// ];

function Login() {
  const navigate = useNavigate();
  const [id, setId] = useState("");
  const [password, setPassword] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const res = await loginUser(id, password);
      localStorage.setItem("token", res.data.token);
      localStorage.setItem("is_admin", res.data.is_staff ? "true" : "false");
      localStorage.setItem("user", JSON.stringify(res.data.user));
      if (res.data.is_staff) {
        navigate("/admin");
      } else {
        navigate("/main");
      }
    } catch (err) {
      console.error(err);
      alert("아이디 또는 비밀번호가 잘못되었습니다.");
    }

    // 더미 로그인 (백엔드 연결 끊길 시 주석 해제)
    // const user = DUMMY_USERS.find(
    //   (u) => u.id === id && u.password === password
    // );
    // if (user) {
    //   localStorage.setItem("token", "dummy-token");
    //   alert("로그인 성공!");
    //   navigate("/main");
    // } else {
    //   alert("아이디 또는 비밀번호가 잘못되었습니다.");
    // }
  };

  return (
    <>
      <div className="login-container">
        <div className="login-box">
        <h1>PLACED 로그인</h1>

        <form onSubmit={handleSubmit}>
          <input
            type="text"
            placeholder="아이디를 입력하세요"
            value={id}
            onChange={(e) => setId(e.target.value)}
            required
          />
          <input
            type="password"
            placeholder="비밀번호를 입력하세요"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          <button type="submit">로그인</button>
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