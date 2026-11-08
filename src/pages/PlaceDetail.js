import React, { useState, useEffect, useRef } from "react";
import { useParams } from "react-router-dom";
import Header from "../components/Header";
import Footer from "../components/Footer";
import { getPlaceDetail, getReviewsByPlace } from "../api/reviewAPI";
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

function PlaceDetail() {
  const { id } = useParams();
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
                    <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px" }}>
                      <span style={{ color: "#aaa", fontSize: "0.8rem" }}>{r.created_at?.slice(0, 10)}</span>
                    </div>
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