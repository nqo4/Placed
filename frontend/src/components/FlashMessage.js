import React, { useEffect, useState } from "react";
import "./FlashMessage.css";

const KEY = "flash";

// 다른 화면으로 이동한 뒤 보여줄 안내 (새로고침으로 이동해도 남도록 sessionStorage 사용)
export const setFlash = (text, type = "info") => {
  try {
    sessionStorage.setItem(KEY, JSON.stringify({ text, type }));
  } catch {}
  window.dispatchEvent(new Event("flash"));
};

const takeFlash = () => {
  try {
    const raw = sessionStorage.getItem(KEY);
    sessionStorage.removeItem(KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
};

function FlashMessage() {
  const [flash, setFlashState] = useState(null);

  useEffect(() => {
    const show = () => {
      const next = takeFlash();
      if (next) setFlashState(next);
    };
    show();
    window.addEventListener("flash", show);
    return () => window.removeEventListener("flash", show);
  }, []);

  useEffect(() => {
    if (!flash) return;
    const timer = setTimeout(() => setFlashState(null), 4000);
    return () => clearTimeout(timer);
  }, [flash]);

  if (!flash) return null;

  return (
    <div className={`flash-message ${flash.type}`} onClick={() => setFlashState(null)}>
      {flash.text}
    </div>
  );
}

export default FlashMessage;
