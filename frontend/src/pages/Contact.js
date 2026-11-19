import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { createInquiry } from "../api/inquiryAPI";
import Header from "../components/Header";
import Footer from "../components/Footer";
import "../pages_CSS/Contact.css";

function Contact() {
  const navigate = useNavigate();
  const [category, setCategory] = useState("");
  const [message, setMessage] = useState("");
  const [notice, setNotice] = useState(null);
  const [sending, setSending] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!category || !message.trim()) {
      setNotice({ type: "error", text: "문의 유형과 내용을 입력해주세요." });
      return;
    }

    setSending(true);
    try {
      await createInquiry(category, message);
      setNotice({ type: "success", text: "문의가 접수되었어요. 답변은 마이페이지 > 내 문의에서 확인할 수 있어요." });
      setCategory("");
      setMessage("");
    } catch (error) {
      setNotice({ type: "error", text: "문의 접수에 실패했어요. 잠시 후 다시 시도해주세요." });
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="contact-page">
      <Header />

      <section className="contact-section">
        <h2>문의하기</h2>
        <p>서비스 이용 중 불편사항이나 제안이 있다면 알려주세요</p>

        <form onSubmit={handleSubmit} className="contact-form">
          <select value={category} onChange={(e) => { setCategory(e.target.value); setNotice(null); }}>
            <option value="">문의 선택</option>
            <option value="account">계정 문의</option>
            <option value="service">서비스 이용</option>
            <option value="etc">기타</option>
          </select>

          <textarea
            placeholder="문의 내용을 입력해주세요."
            value={message}
            onChange={(e) => { setMessage(e.target.value); setNotice(null); }}
          ></textarea>

          {notice && <p className={`form-notice ${notice.type}`}>{notice.text}</p>}
          <button type="submit" disabled={sending}>{sending ? "보내는 중..." : "문의 보내기"}</button>
        </form>

        <button type="button" className="inquiry-history-link" onClick={() => navigate("/inquiries")}>
          내 문의 내역 보기 ›
        </button>
      </section>

      <Footer />
    </div>
  );
}

export default Contact;