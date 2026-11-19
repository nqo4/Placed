import React, { useEffect, useState } from "react";
import "./PopupNotice.css";

const HIDE_UNTIL_KEY = "popupHideDate";
const CLOSED_KEY = "popupClosed";

const today = () => {
  const d = new Date();
  return `${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}`;
};

// 오늘 하루 숨김은 모든 화면 공통, 닫기는 화면(page)마다 따로
const shouldShow = (page) => {
  try {
    if (localStorage.getItem(HIDE_UNTIL_KEY) === today()) return false;
    if (sessionStorage.getItem(`${CLOSED_KEY}_${page}`) === "1") return false;
  } catch {}
  return true;
};

function PopupNotice({ page = "main" }) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    setOpen(shouldShow(page));
  }, [page]);

  const close = () => {
    try {
      sessionStorage.setItem(`${CLOSED_KEY}_${page}`, "1");
    } catch {}
    setOpen(false);
  };

  const hideToday = () => {
    try {
      localStorage.setItem(HIDE_UNTIL_KEY, today());
    } catch {}
    setOpen(false);
  };

  if (!open) return null;

  return (
    <div className="popup-layer">
      <div className="popup-box">
        <div className="popup-image">
          <img
            src={process.env.PUBLIC_URL + "/popup/festival-poster.jpg"}
            alt="2026 AI융합페스티벌 제39회 컴퓨터융합학부 학술제 포스터"
          />
        </div>
        <div className="popup-actions">
          <button onClick={hideToday}>오늘 하루 이 창을 열지 않음</button>
          <button className="popup-close" onClick={close}>닫기</button>
        </div>
      </div>
    </div>
  );
}

export default PopupNotice;
