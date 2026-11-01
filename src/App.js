import { BrowserRouter as Router, Routes, Route } from "react-router-dom";

import MainGuest from "./pages/MainGuest";
import Login from "./pages/Login";
import Signup from "./pages/Signup";
import MainUser from "./pages/MainUser";
import Contact from "./pages/Contact";
import MyInquiry from "./pages/MyInquiry";
import SearchResults from "./pages/SearchResults";
import InquiryDetail from "./pages/InquiryDetail";
import PlaceDetail from "./pages/PlaceDetail";
import MyReviews from "./pages/MyReviews";
import MyPlaces from "./pages/MyPlaces";
import MyPage from "./pages/MyPage";
import Admin from "./pages/Admin";

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<MainGuest />} />
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />
        <Route path="/main" element={<MainUser />} />
        <Route path="/mypage" element={<MyPage />} />
        <Route path="/my-places" element={<MyPlaces />} />
        <Route path="/contact" element={<Contact />} />
        <Route path="/inquiries" element={<MyInquiry />} />
        <Route path="/search" element={<SearchResults />} />
        <Route path="/inquiry/:id" element={<InquiryDetail />} />
        <Route path="/place/:id" element={<PlaceDetail />} />
        <Route path="/reviews" element={<MyReviews />} />
        <Route path="/admin" element={<Admin />} />
      </Routes>
    </Router>
  );
}

export default App;