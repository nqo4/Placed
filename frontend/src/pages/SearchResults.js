import React, { useState, useEffect } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import Header from "../components/Header";
import Footer from "../components/Footer";
import { searchKeyword } from "../api/searchAPI";
import "../pages_CSS/SearchResults.css";

const PAGE_SIZE = 10;

const BLOCK_SIZE = 5;
const SUGGESTED_KEYWORDS = ["유성 맛집", "도안동", "카페"];
const FALLBACK_IMG = process.env.PUBLIC_URL + "/placeholder.svg";

const imageOf = (item) => item.image || item.images?.[0]?.url || item.images?.[0] || item.image_url || FALLBACK_IMG;

const loadViewMode = () => {
  try {
    return localStorage.getItem("searchView") === "table" ? "table" : "card";
  } catch {
    return "card";
  }
};

function SearchResults() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const keyword = searchParams.get("keyword") || "";

  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [query, setQuery] = useState(keyword);
  const [viewMode, setViewMode] = useState(loadViewMode);

  const changeView = (mode) => {
    setViewMode(mode);
    try {
      localStorage.setItem("searchView", mode);
    } catch {}
  };

  useEffect(() => {
    setQuery(keyword);
  }, [keyword]);

  const totalPages = Math.max(1, Math.ceil(results.length / PAGE_SIZE));
  const page = Math.min(Math.max(1, Number(searchParams.get("page")) || 1), totalPages);
  const pageResults = results.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  // 5개씩 묶어서 번호 표시
  const blockStart = Math.floor((page - 1) / BLOCK_SIZE) * BLOCK_SIZE + 1;
  const blockEnd = Math.min(blockStart + BLOCK_SIZE - 1, totalPages);

  const handleSearch = (e) => {
    e.preventDefault();
    const q = query.trim();
    if (!q) return;
    navigate(`/search?keyword=${encodeURIComponent(q)}`);
  };

  const goToPage = (n) => {
    setSearchParams({ keyword, page: String(n) });
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  useEffect(() => {
    if (!keyword) return;

    setLoading(true);
    setError(null);

    searchKeyword(keyword)
      .then((res) => {
        setResults(Array.isArray(res.data) ? res.data : res.data.results ?? []);
      })
      .catch(() => {
        setError("검색 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.");
      })
      .finally(() => {
        setLoading(false);
      });
  }, [keyword]);

  return (
    <div className="search-results-page">
      <Header />

      <main className="results-container">
        <div className="search-title-section">
          <h2>검색 결과</h2>
          <p className="keyword-info">"{keyword}"에 대한 검색 결과입니다.</p>
          <form className="results-search" onSubmit={handleSearch}>
            <input
              type="text"
             
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <button type="submit">검색</button>
          </form>
        </div>

        {loading ? (
          <div className="no-result-wrapper">
            <div className="empty-box">
              <p>검색 중입니다...</p>
            </div>
          </div>
        ) : error ? (
          <div className="no-result-wrapper">
            <div className="empty-box">
              <p>{error}</p>
              <button className="back-btn" onClick={() => navigate("/main")}>
                메인으로 돌아가기
              </button>
            </div>
          </div>
        ) : results.length > 0 ? (
          <div className="results-list-wrapper">
            <p className="ai-notice-text">
              "{keyword}"에 대한 <strong>AI 분석 완료</strong> 리스트입니다.
            </p>
            <div className="results-toolbar">
              <span className="results-total">총 <strong>{results.length}</strong>곳</span>
              <div className="view-toggle">
                <button
                  className={viewMode === "card" ? "active" : ""}
                  onClick={() => changeView("card")}
                  title="사진으로 보기"
                  aria-label="사진으로 보기"
                >
                  <svg viewBox="0 0 16 16" width="16" height="16" fill="currentColor">
                    <rect x="1" y="1" width="6" height="6" rx="1.5" />
                    <rect x="9" y="1" width="6" height="6" rx="1.5" />
                    <rect x="1" y="9" width="6" height="6" rx="1.5" />
                    <rect x="9" y="9" width="6" height="6" rx="1.5" />
                  </svg>
                </button>
                <button
                  className={viewMode === "table" ? "active" : ""}
                  onClick={() => changeView("table")}
                  title="목록으로 보기"
                  aria-label="목록으로 보기"
                >
                  <svg viewBox="0 0 16 16" width="16" height="16" fill="currentColor">
                    <rect x="1" y="2" width="14" height="2.5" rx="1.25" />
                    <rect x="1" y="6.75" width="14" height="2.5" rx="1.25" />
                    <rect x="1" y="11.5" width="14" height="2.5" rx="1.25" />
                  </svg>
                </button>
              </div>
            </div>
            {viewMode === "table" ? (
              <ul className="results-list">
                {pageResults.map((item) => (
                  <li key={item.id} className="list-row" onClick={() => navigate(`/place/${item.id}`)}>
                    <img
                      className="list-thumb"
                      src={imageOf(item)}
                      alt={item.name}
                      onError={(e) => { e.currentTarget.src = FALLBACK_IMG; }}
                    />
                    <div className="list-main">
                      <h3>{item.name}</h3>
                      <p>{item.address}</p>
                    </div>
                    <div className="list-meta">
                      <span className="meta-review">후기 {item.review_total ?? 0}</span>
                      {item.ad_excluded > 0 && <span className="meta-ad">광고 {item.ad_excluded} 제외</span>}
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
            <div className="results-grid">
              {pageResults.map((item) => (
                <div key={item.id} className="result-card" onClick={() => navigate(`/place/${item.id}`)}>
                  <div className="card-img-box">
                    <img
                      src={imageOf(item)}
                      alt={item.name}
                      className="result-img"
                    />
                  </div>
                  <div className="card-info-box">
                    <div className="card-title-line">
                      <h3>{item.name}</h3>
                      <span className="ai-status-badge">AI 분석 완료</span>
                    </div>
                    <p className="card-address">주소 : {item.address}</p>
                    {item.review_total > 0 && (
                      <p className="card-review-count">
                        후기 {item.review_total}개 분석
                        {item.ad_excluded > 0 && (
                          <> · <span className="ad-excluded">광고 의심 {item.ad_excluded}개 제외</span></>
                        )}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
            )}
            {totalPages > 1 && (
              <nav className="pagination">
                <button disabled={blockStart === 1} onClick={() => goToPage(blockStart - BLOCK_SIZE)}>‹</button>
                {Array.from({ length: blockEnd - blockStart + 1 }, (_, i) => blockStart + i).map((n) => (
                  <button key={n} className={n === page ? "active" : ""} onClick={() => goToPage(n)}>
                    {n}
                  </button>
                ))}
                <button disabled={blockEnd === totalPages} onClick={() => goToPage(blockEnd + 1)}>›</button>
              </nav>
            )}
          </div>
        ) : (
          <div className="no-result-wrapper">
            <div className="empty-box">
              <div className="empty-icon">🔍</div>
              <p className="empty-title">"{keyword}"에 대한 결과가 없어요</p>
              <p className="empty-hint">
                지금은 <strong>대전 지역</strong> 장소만 검색돼요.<br />
                '유성', '카페'처럼 짧게 검색해 보세요.
              </p>
              <div className="suggest-list">
                {SUGGESTED_KEYWORDS.map((word) => (
                  <button key={word} onClick={() => navigate(`/search?keyword=${encodeURIComponent(word)}`)}>
                    {word}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}
      </main>

      <Footer />
    </div>
  );
}

export default SearchResults;
