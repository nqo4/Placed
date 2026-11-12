import React, { useState, useEffect } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import Header from "../components/Header";
import Footer from "../components/Footer";
import { searchKeyword } from "../api/searchAPI";
import "../pages_CSS/SearchResults.css";

const PAGE_SIZE = 10;

const BLOCK_SIZE = 5;

function SearchResults() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const keyword = searchParams.get("keyword") || "";

  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [query, setQuery] = useState(keyword);

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
              placeholder="어디로 갈까요?"
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
              "{keyword}"에 대한 <strong>AI 분석 완료</strong> 리스트입니다. (총 {results.length}곳)
            </p>
            <div className="results-grid">
              {pageResults.map((item) => (
                <div key={item.id} className="result-card" onClick={() => navigate(`/place/${item.id}`)}>
                  <div className="card-img-box">
                    <img
                      src={item.image || item.images?.[0]?.url || item.images?.[0] || item.image_url || "https://images.unsplash.com/photo-1579871494447-9811cf80d66c?q=80&w=500"}
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
              <img src="/no_result_icon.png" alt="No Result" className="error-icon" />
              <p>검색 결과가 없습니다.</p>
              <button className="back-btn" onClick={() => navigate("/main")}>
                다른 검색어로 찾아보기
              </button>
            </div>
          </div>
        )}
      </main>

      <Footer />
    </div>
  );
}

export default SearchResults;
