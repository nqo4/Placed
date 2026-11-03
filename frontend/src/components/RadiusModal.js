import React, { useEffect, useRef, useState } from "react";
import "../pages_CSS/RadiusModal.css";

function RadiusModal({ distance, setDistance, onClose }) {
  const mapRef = useRef(null);
  const mapInstance = useRef(null);
  const circleRef = useRef(null);
  const timerRef = useRef(null);
  const isMounted = useRef(true);
  const [mapLoaded, setMapLoaded] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    isMounted.current = true;

    const initMap = (lat, lng) => {
      if (!isMounted.current) return;

      if (window.kakao && window.kakao.maps && mapRef.current) {
        try {
          const center = new window.kakao.maps.LatLng(lat, lng);
          const d = parseFloat(distance);

          const map = new window.kakao.maps.Map(mapRef.current, {
            center: center,
            level: getZoomLevel(d),
          });
          mapInstance.current = map;

          const circle = new window.kakao.maps.Circle({
            map: map,
            center: center,
            radius: d * 2000,
            strokeWeight: 2,
            strokeColor: "#007bff",
            strokeOpacity: 0.8,
            strokeStyle: "solid",
            fillColor: "#007bff",
            fillOpacity: 0.2,
          });
          circleRef.current = circle;

          new window.kakao.maps.Marker({
            map: map,
            position: center,
          });

          setMapLoaded(true);
          setErrorMsg("");
        } catch (err) {
          setErrorMsg("지도 생성 실패: " + err.message);
        }
      } else {
        timerRef.current = setTimeout(() => initMap(lat, lng), 300);
      }
    };

    const loadMap = () => {
      if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
          (pos) => {
            const lat = pos.coords.latitude;
            const lng = pos.coords.longitude;
            initMap(lat, lng);
          },
          () => {
            initMap(36.4523, 127.4258);
          },
          { timeout: 10000, enableHighAccuracy: true }
        );
      } else {
        initMap(36.4523, 127.4258);
      }
    };

    timerRef.current = setTimeout(loadMap, 300);

    return () => {
      isMounted.current = false;
      if (timerRef.current) clearTimeout(timerRef.current);
      try {
        if (circleRef.current) circleRef.current.setMap(null);
      } catch (e) {}
      circleRef.current = null;
      mapInstance.current = null;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    try {
      if (circleRef.current) {
        const d = parseFloat(distance);
        circleRef.current.setRadius(d * 2000);
        if (mapInstance.current) {
          mapInstance.current.setLevel(getZoomLevel(d));
        }
      }
    } catch (e) {}
  }, [distance]);

  const getZoomLevel = (d) => {
    if (d <= 0.5) return 5;
    if (d <= 1)   return 6;
    if (d <= 2)   return 7;
    if (d <= 3)   return 8;
    return 9;
  };

  return (
    <div className="modal-overlay" style={{
      position: "fixed", top: 0, left: 0, width: "100%", height: "100%",
      background: "rgba(0,0,0,0.5)", display: "flex", justifyContent: "center",
      alignItems: "center", zIndex: 9999,
    }}>
      <div className="modal-content" style={{
        background: "white", padding: "36px", borderRadius: "20px",
        width: "900px", maxWidth: "95vw",
        boxShadow: "0 10px 25px rgba(0,0,0,0.2)",
      }}>
        <div className="modal-header" style={{
          display: "flex", justifyContent: "space-between",
          alignItems: "center", marginBottom: "24px",
        }}>
          <h3 style={{ fontWeight: "bold", fontSize: "18px" }}>📍 검색 반경 설정</h3>
          <button onClick={onClose} style={{
            background: "none", border: "none", fontSize: "20px", cursor: "pointer",
          }}>✕</button>
        </div>

        <div className="modal-body" style={{ display: "flex", gap: "24px" }}>
          <div ref={mapRef} style={{
            flex: 2, height: "450px", borderRadius: "12px",
            background: "#eee", position: "relative", overflow: "hidden",
          }}>
            {!mapLoaded && !errorMsg && (
              <div style={{
                position: "absolute", top: "50%", left: "50%",
                transform: "translate(-50%,-50%)", color: "#888",
              }}>
                📍 내 위치를 불러오는 중...
              </div>
            )}
            {errorMsg && (
              <div style={{ color: "red", padding: "20px" }}>{errorMsg}</div>
            )}
          </div>

          <div style={{
            flex: 1, display: "flex", flexDirection: "column",
            justifyContent: "center", alignItems: "center", gap: "16px",
          }}>
            <p style={{ fontSize: "16px" }}>
              설정 거리: <strong style={{ fontSize: "20px" }}>{distance}km</strong>
            </p>
            <input
              type="range" min="0.1" max="2.5" step="0.1"
              value={distance}
              onChange={(e) => setDistance(e.target.value)}
              style={{ width: "100%" }}
            />
            <button onClick={onClose} style={{
              width: "100%", padding: "14px", background: "#007bff",
              color: "white", border: "none", borderRadius: "8px",
              cursor: "pointer", fontSize: "15px", fontWeight: "bold",
            }}>
              적용하기
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default RadiusModal;