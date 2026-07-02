import { BrowserRouter, Routes, Route, NavLink, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth/AuthProvider";
import Login from "./auth/Login";
import Home from "./pages/Home";
import Practice from "./pages/Practice";
import Mock from "./pages/Mock";
import Review from "./pages/Review";
import Analytics from "./pages/Analytics";

function Shell() {
  const { user, loading, signOut } = useAuth();

  if (loading) return <div className="boot">Loading…</div>;
  if (!user) return <Login />;

  return (
    <BrowserRouter>
      <nav className="topnav">
        <NavLink to="/" className="brand">DQE Prep</NavLink>
        <div className="navlinks">
          <NavLink to="/practice">Practice</NavLink>
          <NavLink to="/mock">Mock</NavLink>
          <NavLink to="/review">Review</NavLink>
          <NavLink to="/analytics">Analytics</NavLink>
        </div>
        <button className="link signout" onClick={signOut}>Sign out</button>
      </nav>
      <main>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/practice" element={<Practice />} />
          <Route path="/mock" element={<Mock />} />
          <Route path="/review" element={<Review />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </BrowserRouter>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <Shell />
    </AuthProvider>
  );
}
