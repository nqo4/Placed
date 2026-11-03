import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { analyzeReview } from "../api/analyzeAPI";
import "../pages_CSS/AdCheck.css";

function AdCheck() {
    const navigate = useNavigate();
    const [content, setContent] = useState("");
    const [result, setResult] = useState(null);
    const [loading, setLoading] = useState(false);

    const handleAnalyze = async () => {
        if (!content.trim()) {
            alert("분석할 텍스트를 입력해주세요.");
            return;
        }

        setLoading(true);
        setResult(null);

        try {
            // name은 임의로 현재 시간이나 'User Input'으로 설정
            const res = await analyzeReview("User Input", content);
            setResult(res.data);
        } catch (err) {
            console.error(err);
            alert("분석 중 오류가 발생했습니다.");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="ad-check-page">
            <header className="user-header">
                <div className="logo" onClick={() => navigate("/main")}>
                    <img src="/placed_logo.png" alt="PLACED Logo" className="logo-img" />
                    <span className="logo-text">PLACED</span>
                </div>
                <nav className="nav">
                    <button onClick={() => navigate("/main")}>홈</button>
                    <button onClick={() => navigate("/reviews")}>내 리뷰</button>
                    <button onClick={() => navigate("/inquiries")}>문의하기</button>
                </nav>
            </header>

            <div className="ad-check-container">
                <h2>광고 판독기 🕵️‍♂️</h2>
                <p>의심스러운 리뷰 텍스트를 붙여넣으세요. AI가 광고 여부를 분석해줍니다.</p>

                <textarea
                    className="ad-input"
                    placeholder="여기에 리뷰 내용을 입력하세요..."
                    value={content}
                    onChange={(e) => setContent(e.target.value)}
                />

                <button className="analyze-btn" onClick={handleAnalyze} disabled={loading}>
                    {loading ? "분석 중..." : "판독 시작"}
                </button>

                {result && (
                    <div className={`result-box ${result.is_ad ? "ad" : "organic"}`}>
                        <h3>분석 결과</h3>
                        <p className="probability">
                            광고 확률: <strong>{result.probability}%</strong>
                        </p>
                        <p className="summary">{result.reason}</p>
                        {result.is_ad ? (
                            <div className="badge ad-badge">🚨 광고 의심</div>
                        ) : (
                            <div className="badge organic-badge">✅ 실제 후기</div>
                        )}
                        <p className="model-info">Model used: {result.model_used}</p>
                    </div>
                )}
            </div>
        </div>
    );
}

export default AdCheck;
