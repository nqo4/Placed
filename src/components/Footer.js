import React from "react";
import { Link } from "react-router-dom";
import "./Footer.css";

function Footer() {
  return (
    <footer className="common-footer">
      © 2026 PLACED | <Link to="/terms">이용약관</Link> | <Link to="/privacy">개인정보처리방침</Link>
    </footer>
  );
}

export default Footer;
