import { History as HistoryIcon, Moon, Plus, Settings, Sun } from "lucide-react";
import { useState } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import History from "./pages/History";
import NewPush from "./pages/NewPush";
import Push from "./pages/Push";
import Review from "./pages/Review";
import SettingsPage from "./pages/SettingsPage";

const link = ({ isActive }: { isActive: boolean }) =>
  `flex items-center gap-2 rounded px-3 py-2 text-sm ${isActive ? "bg-panel text-fg" : "text-mute hover:text-fg"}`;

export default function App() {
  const [dark, setDark] = useState(() => localStorage.getItem("theme") !== "light");
  document.documentElement.classList.toggle("dark", dark);
  const toggle = () => { localStorage.setItem("theme", dark ? "light" : "dark"); setDark(!dark); };
  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      <aside className="flex shrink-0 flex-col border-b border-line p-3 md:w-56 md:border-b-0 md:border-r">
        <div className="mb-4 px-3 py-2 text-base font-semibold">RepoPilot</div>
        <nav className="flex gap-1 md:block md:space-y-1">
          <NavLink to="/" end className={link}><Plus size={16} />New push</NavLink>
          <NavLink to="/history" className={link}><HistoryIcon size={16} />History</NavLink>
          <NavLink to="/settings" className={link}><Settings size={16} />Settings</NavLink>
        </nav>
        <div className="mt-3 px-3 text-xs text-mute md:mt-auto">
          <button onClick={toggle} className="mb-3 flex items-center gap-2 hover:text-fg" aria-label="Toggle theme">{dark ? <Sun size={14} /> : <Moon size={14} />}{dark ? "Light mode" : "Dark mode"}</button>
          <div className="text-fg">RepoPilot</div><div>Local AI Git Publisher</div><div>v1.0.0</div>
        </div>
      </aside>
      <main className="min-w-0 flex-1 p-4 md:p-8">
        <Routes>
          <Route path="/" element={<NewPush />} />
          <Route path="/jobs/:id/review" element={<Review />} />
          <Route path="/jobs/:id/push" element={<Push />} />
          <Route path="/history" element={<History />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </main>
    </div>
  );
}
