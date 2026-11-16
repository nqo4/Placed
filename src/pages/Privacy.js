import React from "react";
import Header from "../components/Header";
import Footer from "../components/Footer";
import "../pages_CSS/Legal.css";

function Privacy() {
  return (
    <div className="legal-page">
      <Header />

      <article className="legal-card">
        <h1>개인정보처리방침</h1>
        <p className="legal-date">시행일: 2026년 11월 20일</p>

        <p className="legal-intro">
          PLACED(이하 "서비스")는 이용자의 개인정보를 소중히 여기며, 「개인정보 보호법」에 따라 다음과 같이
          개인정보를 처리합니다.
        </p>

        <h2>1. 수집하는 개인정보 항목</h2>
        <div className="legal-table-wrap">
          <table className="legal-table">
            <thead>
              <tr><th>구분</th><th>항목</th></tr>
            </thead>
            <tbody>
              <tr><td>회원가입 시 (필수)</td><td>아이디(이메일), 비밀번호, 이름</td></tr>
              <tr><td>서비스 이용 중 자동 생성</td><td>검색 기록, 장소 조회 기록, 작성한 후기·문의 내용, 접속 기록</td></tr>
            </tbody>
          </table>
        </div>
        <ul>
          <li>비밀번호는 복원할 수 없는 방식으로 암호화해 저장하며, 운영자도 알 수 없습니다.</li>
          <li>전화번호 등 위 항목 외의 정보는 수집하지 않습니다.</li>
        </ul>

        <h2>2. 개인정보의 이용 목적</h2>
        <ol>
          <li>회원 식별, 로그인, 회원 탈퇴 등 계정 관리</li>
          <li>검색·조회 기록을 바탕으로 한 맞춤 장소 추천(오늘의 추천)</li>
          <li>후기 게시, 1:1 문의 답변</li>
          <li>서비스 개선을 위한 통계 분석(개인을 알아볼 수 없는 형태로 이용)</li>
        </ol>

        <h2>3. 보유 및 이용 기간</h2>
        <ul>
          <li>회원 탈퇴 시 계정 정보와 검색·조회 기록, 작성한 후기·문의를 지체 없이 삭제합니다.</li>
          <li>서비스 운영이 종료되면 보유한 개인정보를 모두 파기합니다.</li>
        </ul>

        <h2>4. 개인정보의 제3자 제공</h2>
        <p>서비스는 이용자의 개인정보를 제3자에게 제공하지 않습니다.</p>

        <h2>5. 개인정보 처리 위탁 및 국외 이전</h2>
        <p>서비스 운영을 위해 아래 업체의 서버를 이용하며, 이 과정에서 개인정보가 국외 서버에 저장·처리됩니다.</p>
        <div className="legal-table-wrap">
          <table className="legal-table">
            <thead>
              <tr><th>업체</th><th>위탁 업무</th><th>이전 국가</th><th>이전 항목</th></tr>
            </thead>
            <tbody>
              <tr><td>Render Services, Inc.</td><td>서버 운영, 데이터베이스 보관</td><td>싱가포르</td><td>1번의 모든 항목</td></tr>
              <tr><td>Vercel Inc.</td><td>웹사이트 화면 제공</td><td>미국 등</td><td>접속 기록</td></tr>
              <tr><td>Google LLC (Gemini API)</td><td>후기 글의 광고성 여부 AI 분석</td><td>미국</td><td>분석을 요청한 후기 본문(이름·아이디는 보내지 않음)</td></tr>
            </tbody>
          </table>
        </div>
        <ul>
          <li>이전 시기·방법: 서비스 이용 시 네트워크를 통해 전송됩니다.</li>
          <li>국외 이전을 원하지 않으면 회원가입을 하지 않거나 회원 탈퇴를 할 수 있으며, 이 경우 회원 기능은 이용할 수 없습니다.</li>
        </ul>

        <h2>6. 이용자의 권리</h2>
        <p>이용자는 언제든 다음을 할 수 있습니다.</p>
        <ol>
          <li>마이페이지에서 내 정보 조회, 이름·비밀번호 변경</li>
          <li>내가 쓴 후기 삭제</li>
          <li>회원 탈퇴(개인정보 삭제 요청)</li>
        </ol>

        <h2>7. 쿠키 및 브라우저 저장소</h2>
        <p>
          로그인 상태 유지를 위해 로그인 토큰을 브라우저 저장소(localStorage)에 저장합니다. 로그아웃하면 삭제되며,
          광고나 추적 목적의 쿠키는 사용하지 않습니다.
        </p>

        <h2>8. 개인정보의 안전성 확보 조치</h2>
        <p>
          비밀번호 암호화 저장, HTTPS 암호화 통신, 관리자 페이지 접근 제한, 로그인 토큰 만료(1시간, 갱신 토큰 14일)를
          적용하고 있습니다.
        </p>

        <h2>9. 개인정보 보호책임자</h2>
        <ul>
          <li>담당: PLACED 팀</li>
          <li>연락처: 사이트의 1:1 문의</li>
        </ul>
        <p>개인정보 침해 신고·상담은 개인정보침해신고센터(privacy.kisa.or.kr, 국번 없이 118)에도 할 수 있습니다.</p>

        <h2>10. 방침 변경</h2>
        <p>이 방침이 바뀌면 시행 7일 전에 사이트를 통해 알립니다.</p>

        <p className="legal-note">본 서비스는 대학 학술제 프로젝트로 운영됩니다.</p>
      </article>

      <Footer />
    </div>
  );
}

export default Privacy;
