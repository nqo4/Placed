import React, { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import Header from "../components/Header";
import Footer from "../components/Footer";
import { getPlaceDetail, getReviewsByPlace } from "../api/reviewAPI";
import "../pages_CSS/PlaceDetail.css";

function ImageSlider({ images }) {
  const [current, setCurrent] = useState(0);

  // PlaceImage 데이터가 없는 장소에서 images가 빈 배열로 올 경우 슬라이더 크래시 방지 — 틀은 유지하고 '이미지 준비 중' 표시
  if (!images || images.length === 0) {
    return (
      <div style={{ position: "relative", width: "100%", height: "300px", borderRadius: "12px", overflow: "hidden", background: "#eee", display: "flex", alignItems: "center", justifyContent: "center", color: "#aaa", fontSize: "1rem" }}>
        이미지 준비 중
      </div>
    );
  }

  const prev = () => setCurrent((current - 1 + images.length) % images.length);
  const next = () => setCurrent((current + 1) % images.length);

  return (
    <div style={{ position: "relative", width: "100%", height: "300px", borderRadius: "12px", overflow: "hidden", background: "#eee" }}>
      <img
        src={images[current]?.url || images[current]}
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

function PlaceDetail() {
  const { id } = useParams();
  const [placeData, setPlaceData] = useState(null);
  const [reviews, setReviews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showDescModal, setShowDescModal] = useState(false);

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

  const handleDirections = () => {
    if (!placeData) return;
    const { name, lat, lng } = placeData;

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

  const avgRating = reviews.length
    ? (reviews.reduce((sum, r) => sum + r.rating, 0) / reviews.length).toFixed(1)
    : 0;

  if (loading) return <div className="loading-box">데이터 분석 중...</div>;

  const reliability = placeData.non_ad_probability ?? "85 (더미)";
  const reviewCount = reviews.length;
  const analysis = placeData.ai_filtering_reason
    ? [{ id: 1, type: 'positive', text: placeData.ai_filtering_reason }]
    : [
        { id: 1, type: 'positive', text: '실제 방문자들의 긍정적인 반응이 많습니다. (더미)' },
        { id: 2, type: 'positive', text: '광고성 키워드 비중이 낮아 신뢰할 수 있습니다. (더미)' },
        { id: 3, type: 'warning', text: '최근 리뷰 중 일부 서비스 불만이 감지되었습니다. (더미)' },
      ];

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
            <div className="desc" style={{ maxHeight: '300px', overflowY: 'auto', paddingRight: '6px' }}>
              {parseDescription(placeData.description).map((block, i) => (
                <div key={i} style={{ marginBottom: '12px', borderBottom: '1px solid #f0f0f0', paddingBottom: '10px' }}>
                  {block.title && <p style={{ fontWeight: 600, fontSize: '0.85rem', color: '#555', marginBottom: '4px' }}>[{block.title}]</p>}
                  <p style={{ fontSize: '0.9rem', lineHeight: '1.6', color: '#333', margin: 0 }}>{block.content}</p>
                </div>
              ))}
            </div>

            <div style={{ display: 'flex', flexDirection: 'row', alignItems: 'center', gap: '6px', marginTop: '16px', flexWrap: 'nowrap' }}>
              {Array.from({ length: 5 }, (_, i) => (
                <span key={i} style={{ color: i < Math.round(avgRating) ? '#ffc107' : '#ddd', fontSize: '1.1rem', lineHeight: 1 }}>★</span>
              ))}
              <span style={{ fontWeight: 700, color: '#2a7fff', fontSize: '1.1rem' }}>{avgRating}</span>
              <span style={{ color: '#aaa', fontSize: '0.9rem' }}>({reviews.length}명) (더미)</span>
            </div>
          </div>
        </section>

        <section className="report-card">
          <div className="report-header">
            <h3>🤖 AI 광고 분석 리포트</h3>
          </div>
          <div className="score-box">
            <span className="score">{reliability}%</span>
            <p className="score-label">실사용자 리뷰 신뢰도</p>
            <p className="score-sub">리뷰 {reviewCount}개를 분석한 결과입니다.</p>
          </div>
          <div className="analysis-list">
            {analysis.map((item) => (
              <div key={item.id} className={`analysis-item ${item.type}`}>
                <span className="icon">{item.type === "warning" ? "!" : "✓"}</span>
                <p>{item.text}</p>
              </div>
            ))}
          </div>
          <button className="view-reviews-btn">전체 리뷰 보기</button>
        </section>
      </main>

      <Footer />
    </div>
  );
}

export default PlaceDetail;