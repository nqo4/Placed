import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { createInquiry } from "../api/inquiryAPI";
import Header from "../components/Header";
import Footer from "../components/Footer";
import "../pages_CSS/Contact.css";

function Contact() {
  const navigate = useNavigate();
  const [category, setCategory] = useState("문의 선택");
  const [message, setMessage] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!category || !message.trim()) {
      alert("문의 유형과 내용을 입력해주세요.");
      return;
    }

    try {
      await createInquiry(category, message);
      alert("문의가 정상적으로 접수되었습니다!");
      setCategory("문의 선택");
      setMessage("");
    } catch (error) {
      console.error(error);
      alert("문의 접수 중 오류가 발생했습니다.");
    }
  };

  return (
    <div className="contact-page">
      <Header />

      <section className="contact-section">
        <h2>문의하기</h2>
        <p>서비스 이용 중 불편사항이나 제안이 있다면 알려주세요</p>

        <form onSubmit={handleSubmit} className="contact-form">
          <select value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="">문의 선택</option>
            <option value="account">계정 문의</option>
            <option value="service">서비스 이용</option>
            <option value="etc">기타</option>
          </select>

          <textarea
            placeholder="문의 내용을 입력해주세요."
            value={message}
            onChange={(e) => setMessage(e.target.value)}
          ></textarea>

          <button type="submit">문의 보내기</button>
        </form>
      </section>

      <Footer />
    </div>
  );
}

export default Contact;