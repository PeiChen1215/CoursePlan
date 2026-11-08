import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./hooks/useAuth";
import { LoginPage } from "./pages/LoginPage";
import { BoardPage } from "./pages/BoardPage";
import { ConstraintPage } from "./pages/ConstraintPage";
import { DraftPage } from "./pages/DraftPage";
import { VersionsPage } from "./pages/VersionsPage";
import { AdminPage } from "./pages/AdminPage";

function Guard({ children }: { children: React.ReactNode }) {
  const { me, loading } = useAuth();
  if (loading) return <p className="p-8 text-sm text-slate-500">加载中…</p>;
  if (!me) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/board" element={<Guard><BoardPage /></Guard>} />
      <Route path="/constraint" element={<Guard><ConstraintPage /></Guard>} />
      <Route path="/draft" element={<Guard><DraftPage /></Guard>} />
      <Route path="/versions" element={<Guard><VersionsPage /></Guard>} />
      <Route path="/admin" element={<Guard><AdminPage /></Guard>} />
      <Route path="*" element={<Navigate to="/board" replace />} />
    </Routes>
  );
}
