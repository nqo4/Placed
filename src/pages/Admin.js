import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import Header from "../components/Header";
import Footer from "../components/Footer";
import {
  getAdminUsers, getAdminPlaces, getAdminAnalysis,
  getAdminReviews, getAdminInquiries
} from "../api/adminAPI";
import "../pages_CSS/Admin.css";
import { clearAuth } from "../api/axiosInstance";

const CATEGORY_LABEL = { account: "계정 문의", service: "서비스 이용", etc: "기타" };

function Admin() {
  const navigate = useNavigate();
  const [tab, setTab] = useState("dashboard");
  const [users, setUsers] = useState([]);
  const [places, setPlaces] = useState([]);
  const [analyses, setAnalyses] = useState([]);
  const [reviews, setReviews] = useState([]);
  const [inquiries, setInquiries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedAnalysis, setSelectedAnalysis] = useState(null);

  useEffect(() => {
    const isAdmin = localStorage.getItem("is_admin");
    if (isAdmin !== "true") {
      alert("관리자 권한이 없습니다.");
      navigate("/main");
      return;
    }

    // 한번에 다 불러오기
    Promise.all([
      getAdminUsers(),
      getAdminPlaces(),
      getAdminAnalysis(),
      getAdminReviews(),
      getAdminInquiries(),
    ])
      .then(([u, p, a, r, i]) => {
        // 페이지네이션 응답이면 results 꺼내고, 아니면 그대로 씀
        const toArr = (d) => (Array.isArray(d) ? d : d.results ?? []);
        setUsers(toArr(u.data));
        setPlaces(toArr(p.data));
        setAnalyses(toArr(a.data));
        setReviews(toArr(r.data));
        setInquiries(toArr(i.data));
      })
      .catch((err) => console.error("관리자 데이터 로딩 실패", err))
      .finally(() => setLoading(false));
  }, [navigate]);

  const stats = [
    { label: "총 회원 수", value: users.length, color: "#2a7fff", tabKey: "users" },
    { label: "총 장소 수", value: places.length, color: "#28a745", tabKey: "places" },
    { label: "AI 분석 건수", value: analyses.length, color: "#fd7e14", tabKey: "analysis" },
    { label: "미답변 문의", value: inquiries.length, color: "#dc3545", tabKey: "inquiries" },
  ];

  const menuItems = [
    { key: "dashboard", label: "대시보드" },
    { key: "users", label: "회원 관리" },
    { key: "places", label: "장소 관리" },
    { key: "analysis", label: "AI 분석 관리" },
    { key: "inquiries", label: "문의 관리" },
  ];

  if (loading) return <div className="loading-box">데이터 불러오는 중...</div>;

  return (
    <div className="admin-wrapper">
      <Header hideNav />
      <div className="admin-layout">
        <aside className="admin-sidebar">
          <p className="admin-sidebar-title">관리자 메뉴</p>
          <nav>
            {menuItems.map((item) => (
              <button
                key={item.key}
                className={`menu-btn ${tab === item.key ? "active" : ""}`}
                onClick={() => setTab(item.key)}
              >
                {item.label}
              </button>
            ))}
            <div className="sidebar-divider" />
            <button className="menu-btn logout-btn" onClick={() => {
              clearAuth();
              navigate("/");
            }}>
              로그아웃
            </button>
          </nav>
        </aside>

        <main className="admin-content">
          {tab === "dashboard" && (
            <div>
              <h2>대시보드</h2>
              <div className="stat-grid">
                {stats.map((s) => (
                  <div key={s.label} className="stat-card" style={{ borderTop: `4px solid ${s.color}`, cursor: "pointer" }} onClick={() => setTab(s.tabKey)}>
                    <p className="stat-value" style={{ color: s.color }}>{s.value}</p>
                    <p className="stat-label">{s.label}</p>
                  </div>
                ))}
              </div>
              <div className="admin-section">
                <h3>최근 문의</h3>
                <table className="admin-table">
                  <thead>
                    <tr><th>번호</th><th>작성자</th><th>카테고리</th><th>내용</th><th>날짜</th></tr>
                  </thead>
                  <tbody>
                    {inquiries.slice(0, 5).map((q) => (
                      <tr key={q.id}>
                        <td>{q.id}</td>
                        <td>{q.user?.username}</td>
                        <td><span className="badge">{CATEGORY_LABEL[q.category] || q.category}</span></td>
                        <td className="td-truncate">{q.message}</td>
                        <td>{q.created_at?.slice(0, 10)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {tab === "users" && (
            <div>
              <h2>회원 관리 ({users.length}명)</h2>
              <div className="table-scroll">
                <table className="admin-table">
                  <thead>
                    <tr><th>번호</th><th>아이디</th><th>이메일</th><th>전화번호</th><th>권한</th><th>가입일</th></tr>
                  </thead>
                  <tbody>
                    {users.map((u) => (
                      <tr key={u.id}>
                        <td>{u.id}</td>
                        <td>{u.username}</td>
                        <td>{u.email || "-"}</td>
                        <td>{u.phone_number || "-"}</td>
                        <td><span className={`badge ${u.is_staff ? "badge-admin" : "badge-user"}`}>{u.is_staff ? "관리자" : "일반"}</span></td>
                        <td>{u.date_joined?.slice(0, 10)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {tab === "places" && (
            <div>
              <h2>장소 관리 ({places.length}개)</h2>
              <div className="table-scroll">
                <table className="admin-table">
                  <thead>
                    <tr><th>번호</th><th>장소명</th><th>주소</th><th>등록일</th><th>상세</th></tr>
                  </thead>
                  <tbody>
                    {places.map((p) => (
                      <tr key={p.id}>
                        <td>{p.id}</td>
                        <td>{p.name}</td>
                        <td>{p.address}</td>
                        <td>{p.created_at?.slice(0, 10)}</td>
                        <td><button className="link-btn" onClick={() => navigate(`/place/${p.id}`)}>보기</button></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {tab === "analysis" && (
            <div>
              <h2>AI 분석 관리 ({analyses.length}건)</h2>
              <div className="table-scroll">
                <table className="admin-table">
                  <thead>
                    <tr><th>번호</th><th>장소명</th><th>광고 여부</th><th>신뢰도</th><th>AI 요약</th><th>분석일</th></tr>
                  </thead>
                  <tbody>
                    {analyses.map((a) => (
                      <tr key={a.id} onClick={() => setSelectedAnalysis(a)} style={{ cursor: "pointer" }}>
                        <td>{a.id}</td>
                        <td>{a.name}</td>
                        <td><span className={`badge ${a.is_ad ? "badge-ad" : "badge-ok"}`}>{a.is_ad ? "광고" : "정상"}</span></td>
                        <td><strong style={{ color: a.ad_probability >= 70 ? "#28a745" : "#dc3545" }}>{a.ad_probability}%</strong></td>
                        <td className="td-truncate">{a.ai_summary}</td>
                        <td>{a.created_at?.slice(0, 10)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {tab === "inquiries" && (
            <div>
              <h2>문의 관리 ({inquiries.length}건)</h2>
              <div className="table-scroll">
                <table className="admin-table">
                  <thead>
                    <tr><th>번호</th><th>작성자</th><th>카테고리</th><th>내용</th><th>날짜</th></tr>
                  </thead>
                  <tbody>
                    {inquiries.map((q) => (
                      <tr key={q.id}>
                        <td>{q.id}</td>
                        <td>{q.user?.username}</td>
                        <td><span className="badge">{CATEGORY_LABEL[q.category] || q.category}</span></td>
                        <td className="td-content">{q.message}</td>
                        <td>{q.created_at?.slice(0, 10)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </main>
      </div>
      {selectedAnalysis && (
        <div className="modal-overlay" onClick={() => setSelectedAnalysis(null)}>
          <div className="modal-box" onClick={(e) => e.stopPropagation()}>
            <h3>{selectedAnalysis.name}</h3>
            <div style={{ display: "flex", gap: "10px", margin: "12px 0" }}>
              <span className={`badge ${selectedAnalysis.is_ad ? "badge-ad" : "badge-ok"}`}>
                {selectedAnalysis.is_ad ? "광고" : "정상"}
              </span>
              <strong style={{ color: selectedAnalysis.ad_probability >= 70 ? "#28a745" : "#dc3545" }}>
                신뢰도 {selectedAnalysis.ad_probability}%
              </strong>
            </div>
            <p style={{ fontSize: "0.9rem", lineHeight: "1.7", color: "#333" }}>{selectedAnalysis.ai_summary}</p>
            <button className="modal-close-btn" onClick={() => setSelectedAnalysis(null)}>닫기</button>
          </div>
        </div>
      )}

      <Footer />
    </div>
  );
}

export default Admin;
