import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import Shell from "./Shell";
import AlertsPage from "./pages/AlertsPage";
import BookPage from "./pages/BookPage";
import HistoryPage from "./pages/HistoryPage";
import HomePage from "./pages/HomePage";
import LoginPage from "./pages/LoginPage";
import OnBehalfPage from "./pages/OnBehalfPage";
import RegisterPage from "./pages/RegisterPage";
import SchedulePage from "./pages/SchedulePage";
import VisitPage from "./pages/VisitPage";
import LandingPage from "./portal/LandingPage";
import PublicLayout from "./portal/PublicLayout";
import StaffRoute from "./portal/StaffRoute";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<PublicLayout />}>
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
        </Route>
        <Route path="/app" element={<Shell />}>
          <Route index element={<HomePage />} />
          <Route path="book" element={<BookPage />} />
          <Route path="history" element={<HistoryPage />} />
          <Route path="visits/:id" element={<VisitPage />} />
          <Route path="alerts" element={<AlertsPage />} />
          <Route element={<StaffRoute />}>
            <Route path="schedule" element={<SchedulePage />} />
            <Route path="on-behalf" element={<OnBehalfPage />} />
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
