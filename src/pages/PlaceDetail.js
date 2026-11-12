import React, { useState, useEffect, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import Header from "../components/Header";
import Footer from "../components/Footer";
import { getPlaceDetail, getReviewsByPlace, createReview } from "../api/reviewAPI";
import "../pages_CSS/PlaceDetail.css";

function ImageSlider({ images }) {
  const [current, setCurrent] = useState(0);

  // 이미지 없으면 '이미지 준비 중' 표시
  if (!images || images.length === 0) {
    return (
      <div className="image-slider" style={{ position: "relative", width: "100%", borderRadius: "12px", overflow: "hidden", background: "#eee", display: "flex", alignItems: "center", justifyContent: "center", color: "#aaa", fontSize: "1rem" }}>
        이미지 준비 중
      </div>
    );
  }

  const prev = () => setCurrent((current - 1 + images.length) % images.length);
  const next = () => setCurrent((current + 1) % images.length);

  return (
    <div className="image-slider" style={{ position: "relative", width: "100%", borderRadius: "12px", overflow: "hidden", background: "#eee" }}>
      <img
        src={typeof images[current] === "string" ? images[current] : images[current]?.url}
        alt={`슬라이드 ${current + 1}`}
        style={{ width: "100%", height: "100%", objectFit: "contain", background: "#f0f0f0" }}
      />
      <button onClick={prev} style={{
        position: "absolute", left: "10px", top: "50%", transform: "translateY(-50%)",
        background: "rgba(0,0,0,0.4)", color: "white", border: "none",
        borderRadius: "50%", width: "36px", height: "36px", cursor: "pointer", fontSize: "18px"
      }}>‹</button>
      <button onClick={next} style={{
        position: "absolute", right: "10px", top: "50%", transform: "translateY(-50%)",
        background: "rgba(0,0,0,0.4)", color: "white", border: "none",
        borderRadius: "50%", width: "36px", height: "36px", cursor: "pointer", fontSize: "18px"
      }}>›</button>
      <div style={{
        position: "absolute", bottom: "10px", left: "50%", transform: "translateX(-50%)",
        display: "flex", gap: "6px"
      }}>
        {images.map((_, i) => (
          <div key={i} onClick={() => setCurrent(i)} style={{
            width: "8px", height: "8px", borderRadius: "50%",
            background: i === current ? "white" : "rgba(255,255,255,0.5)",
            cursor: "pointer"
          }} />
        ))}
      </div>
    </div>
  );
}

function PlaceMap({ name, lat, lng }) {
  const mapRef = useRef(null);
  const isMobile = window.matchMedia("(max-width: 768px)").matches;

  useEffect(() => {
    if (!window.kakao?.maps || !mapRef.current) return;
    const { kakao } = window;
    const position = new kakao.maps.LatLng(lat, lng);
    const map = new kakao.maps.Map(mapRef.current, { center: position, level: 3 });
    new kakao.maps.Marker({ map, position });

    // 폰은 스크롤 방해 안 되게 고정, PC는 드래그/확대 가능
    if (isMobile) {
      map.setDraggable(false);
      map.setZoomable(false);
    } else {
      map.addControl(new kakao.maps.ZoomControl(), kakao.maps.ControlPosition.RIGHT);
    }
  }, [lat, lng, isMobile]);

  const kakaoMapUrl = `https://map.kakao.com/link/map/${encodeURIComponent(name)},${lat},${lng}`;

  return (
    <div className="place-map-wrap">
      <div
        ref={mapRef}
        className={`place-map${isMobile ? " tappable" : ""}`}
        onClick={isMobile ? () => window.open(kakaoMapUrl, "_blank") : undefined}
      />
      <a className="place-map-link" href={kakaoMapUrl} target="_blank" rel="noreferrer">
        카카오맵에서 크게 보기 ›
      </a>
    </div>
  );
}

const KEYWORD_EMOJI = {
  "맛있어요": "😋",
  "디저트가 맛있어요": "🍰",
  "양이 많아요": "🍚",
  "메뉴가 다양해요": "📋",
  "가성비가 좋아요": "💰",
  "분위기가 좋아요": "✨",
  "조용해요": "🤫",
  "사진 찍기 좋아요": "📸",
  "매장이 넓어요": "🏠",
  "친절해요": "😊",
  "주차가 편해요": "🚗",
  "단체로 가기 좋아요": "👥",
  "혼밥하기 좋아요": "🙋",
};

const KEYWORD_PREVIEW = 5;

function KeywordSummary({ keywords }) {
  const [showAll, setShowAll] = useState(false);
  const positives = keywords.filter((k) => k.sentiment === "positive");
  const negatives = keywords.filter((k) => k.sentiment === "negative");
  if (positives.length === 0 && negatives.length === 0) return null;

  const max = Math.max(1, ...positives.map((k) => k.count));
  const shown = showAll ? positives : positives.slice(0, KEYWORD_PREVIEW);

  return (
    <div className="keyword-summary">
      {positives.length > 0 && (
        <>
          <p className="keyword-title">이런 점이 좋았어요</p>
          <ul className="keyword-bars">
            {shown.map((k) => (
              <li key={k.keyword}>
                <div className="keyword-bar" style={{ width: `${(k.count / max) * 100}%` }} />
                <span className="keyword-label">
                  {KEYWORD_EMOJI[k.keyword] || "👍"} {k.keyword}
                </span>
                <span className="keyword-count">{k.count}</span>
              </li>
            ))}
          </ul>
          {positives.length > KEYWORD_PREVIEW && (
            <button className="keyword-more" onClick={() => setShowAll(!showAll)}>
              {showAll ? "접기" : `+ ${positives.length - KEYWORD_PREVIEW}개 더보기`}
            </button>
          )}
        </>
      )}
      {negatives.length > 0 && (
        <>
          <p className="keyword-title negative">이런 점은 아쉬웠어요</p>
          <p className="keyword-negatives">
            {negatives.map((k) => `${k.keyword} ${k.count}`).join(" · ")}
          </p>
        </>
      )}
    </div>
  );
}

function PlaceDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const isLoggedIn = !!localStorage.getItem("token");
  const [reviewText, setReviewText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [placeData, setPlaceData] = useState(null);
  const [reviews, setReviews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showDescModal, setShowDescModal] = useState(false);
  const [expandedReview, setExpandedReview] = useState(null);
  const [showAllReviews, setShowAllReviews] = useState(false);

  const parseDescription = (text) => {
    if (!text) return [];
    const parts = text.split(/\n\s*\n/).filter(p => p.trim());
    return parts.map(part => {
      const match = part.match(/^\[([^\]]+)\]([\s\S]*)/);
      if (match) return { title: match[1].trim(), content: match[2].trim() };
      return { title: '', content: part.trim() };
    });
  };

  useEffect(() => {
    setLoading(true);
    Promise.all([getPlaceDetail(id), getReviewsByPlace(id)])
      .then(([placeRes, reviewRes]) => {
        setPlaceData(placeRes.data);
        setReviews(reviewRes.data);
      })
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  }, [id]);

  const handleReviewSubmit = async (e) => {
    e.preventDefault();
    const content = reviewText.trim();
    if (!content || submitting) return;
    setSubmitting(true);
    try {
      await createReview(id, content);
      setReviewText("");
      const res = await getReviewsByPlace(id);
      setReviews(res.data);
    } catch {
      alert("후기 등록에 실패했습니다. 잠시 후 다시 시도해주세요.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDirections = () => {
    if (!placeData) return;
    const { name, address, latitude: lat, longitude: lng } = placeData;

    // 좌표 없으면 카카오맵 검색으로
    if (lat == null || lng == null) {
      window.open(`https://map.kakao.com/link/search/${encodeURIComponent(`${name} ${address || ""}`.trim())}`, "_blank");
      return;
    }

    const openMap = (myLat, myLng) => {
      const url = `https://map.kakao.com/link/from/현재위치,${myLat},${myLng}/to/${encodeURIComponent(name)},${lat},${lng}`;
      window.open(url, "_blank");
    };

    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => openMap(pos.coords.latitude, pos.coords.longitude),
        () => {
          window.open(`https://map.kakao.com/link/to/${encodeURIComponent(name)},${lat},${lng}`, "_blank");
        }
      );
    } else {
      window.open(`https://map.kakao.com/link/to/${encodeURIComponent(name)},${lat},${lng}`, "_blank");
    }
  };

  if (loading) return <div className="loading-box">데이터 분석 중...</div>;


  return (
    <div className="place-detail-page">
      <Header />
      <main className="detail-container">
        <section className="info-card">
          <ImageSlider images={placeData.images} />
          <div className="text-info">
            <div className="title-row">
              <h2>{placeData.name}</h2>
              <button className="dir-btn" onClick={handleDirections}>
                📍 길찾기
              </button>
            </div>
            <p className="addr">주소 : {placeData.address}</p>
            {placeData.latitude != null && placeData.longitude != null && (
              <PlaceMap name={placeData.name} lat={placeData.latitude} lng={placeData.longitude} />
            )}
            <div className="desc" style={{ maxHeight: '300px', overflowY: 'auto', paddingRight: '6px' }}>
              {parseDescription(placeData.description).map((block, i) => (
                <div key={i} style={{ marginBottom: '12px', borderBottom: '1px solid #f0f0f0', paddingBottom: '10px' }}>
                  {block.title && <p style={{ fontWeight: 600, fontSize: '0.85rem', color: '#555', marginBottom: '4px' }}>[{block.title}]</p>}
                  <p style={{ fontSize: '0.9rem', lineHeight: '1.6', color: '#333', margin: 0 }}>{block.content}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="report-card">
          <div className="report-header">
            <h3>💬 리뷰</h3>
            <span style={{ fontSize: "0.9rem", color: "#aaa" }}>{reviews.length}개</span>
          </div>
          <KeywordSummary keywords={placeData.review_keywords || []} />
          {isLoggedIn ? (
            <form className="review-form" onSubmit={handleReviewSubmit}>
              <textarea
                placeholder="이곳에 다녀온 후기를 남겨주세요."
                value={reviewText}
                onChange={(e) => setReviewText(e.target.value)}
                maxLength={1000}
              />
              <button type="submit" disabled={!reviewText.trim() || submitting}>
                {submitting ? "등록 중..." : "등록"}
              </button>
            </form>
          ) : (
            <button className="review-login" onClick={() => navigate("/login")}>
              로그인하고 후기 남기기 ›
            </button>
          )}
          {reviews.length === 0 ? (
            <p style={{ color: "#aaa", fontSize: "0.9rem", padding: "16px 0" }}>등록된 리뷰가 없습니다.</p>
          ) : (
            <>
              <div style={{ display: "flex", flexDirection: "column", gap: "14px", marginTop: "12px" }}>
                {(showAllReviews ? reviews : reviews.slice(0, 3)).map((r) => (
                  <div key={r.id}
                    onClick={() => setExpandedReview(expandedReview === r.id ? null : r.id)}
                    style={{ borderBottom: "1px solid #f0f0f0", paddingBottom: "12px", cursor: "pointer" }}
                  >
                    <div className="review-meta">
                      <span className="review-date">{r.created_at?.slice(0, 10)}</span>
                    </div>
                    {r.keywords?.length > 0 && (
                      <div className="review-keywords">
                        {r.keywords.map((k) => <span key={k}>#{k}</span>)}
                      </div>
                    )}
                    <p style={{
                      fontSize: "0.9rem", color: "#333", lineHeight: "1.6", margin: 0,
                      display: "-webkit-box", WebkitLineClamp: expandedReview === r.id ? "unset" : 2,
                      WebkitBoxOrient: "vertical", overflow: expandedReview === r.id ? "visible" : "hidden"
                    }}>{r.content}</p>
                    {expandedReview !== r.id && r.content?.length > 80 && (
                      <span style={{ fontSize: "0.8rem", color: "#2a7fff", marginTop: "4px", display: "block" }}>더 보기</span>
                    )}
                  </div>
                ))}
              </div>
              {reviews.length > 3 && (
                <button onClick={() => setShowAllReviews(!showAllReviews)} style={{
                  marginTop: "14px", width: "100%", padding: "10px",
                  border: "1px solid #ddd", borderRadius: "8px", background: "white",
                  color: "#555", fontSize: "0.9rem", cursor: "pointer"
                }}>
                  {showAllReviews ? "접기" : `전체 리뷰 ${reviews.length}개 보기`}
                </button>
              )}
            </>
          )}
        </section>
      </main>

      <Footer />
    </div>
  );
}

export default PlaceDetail;