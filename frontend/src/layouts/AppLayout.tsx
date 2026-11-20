import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  FileText,
  Database,
  BarChart3,
  Bot,
  CheckSquare,
  Settings,
  Cpu,
  GraduationCap,
} from 'lucide-react';

interface AppLayoutProps {
  selectedPaper: string;
  onSelectPaper: (code: string) => void;
  supportedPapers: { code: string; name: string }[];
  children?: React.ReactNode;
}

export const AppLayout: React.FC<AppLayoutProps> = ({
  selectedPaper,
  onSelectPaper,
  supportedPapers,
  children,
}) => {
  const navItems = [
    { to: '/', label: 'Dashboard', icon: LayoutDashboard },
    { to: '/questions', label: 'Question Bank', icon: Database },
    { to: '/papers', label: 'Paper Library', icon: FileText },
    { to: '/analytics', label: 'PYQ Analytics', icon: BarChart3 },
    { to: '/tests', label: 'Mock Tests (CBT)', icon: CheckSquare },
    { to: '/agents', label: 'Agents', icon: Bot },
    { to: '/settings', label: 'Settings & Data', icon: Settings },
  ];

  return (
    <div className="min-h-screen flex bg-[#060B19] text-slate-100 font-sans antialiased">
      {/* Sidebar */}
      <aside className="w-64 bg-[#0B132B] border-r border-slate-800/80 flex flex-col justify-between shrink-0 select-none">
        <div>
          <div className="p-5 border-b border-slate-800 flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-600/20 border border-indigo-500/40 flex items-center justify-center text-indigo-400">
              <GraduationCap className="w-6 h-6" />
            </div>
            <div>
              <h1 className="font-bold text-base tracking-tight text-white">GATE Intelligence</h1>
              <p className="text-xs text-indigo-400 font-medium">Offline Exam Suite</p>
            </div>
          </div>

          <div className="p-4 border-b border-slate-800/60">
            <label className="block text-[11px] uppercase tracking-wider text-slate-400 font-semibold mb-1.5">
              Active Discipline
            </label>
            <select
              value={selectedPaper}
              onChange={(e) => onSelectPaper(e.target.value)}
              className="w-full bg-[#1C2541] border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-100 focus:outline-none focus:border-indigo-500 cursor-pointer"
            >
              {supportedPapers.map((p) => (
                <option key={p.code} value={p.code}>
                  {p.code} — {p.name}
                </option>
              ))}
            </select>
          </div>

          <nav className="p-3 space-y-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === '/'}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                      isActive
                        ? 'bg-indigo-600 text-white shadow-sm'
                        : 'text-slate-300 hover:bg-[#1C2541] hover:text-white'
                    }`
                  }
                >
                  <Icon className="w-4 h-4 shrink-0" />
                  <span>{item.label}</span>
                </NavLink>
              );
            })}
          </nav>
        </div>

        <div className="p-4 border-t border-slate-800/80 text-xs text-slate-400 space-y-1.5">
          <div className="flex items-center justify-between">
            <span>Runtime</span>
            <span className="text-emerald-400 font-medium flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-400 inline-block animate-pulse"></span>
              100% Offline
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span>Database</span>
            <span className="text-slate-200 font-medium">SQLite Local</span>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 overflow-y-auto bg-[#060B19] min-w-0">
        {children}
      </main>
    </div>
  );
};
