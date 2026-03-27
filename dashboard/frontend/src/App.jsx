import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import TenderDetails from './pages/TenderDetails';
import { LayoutDashboard, FileCheck, ClipboardList, Archive, ExternalLink, AlertTriangle } from 'lucide-react';

const Layout = ({ children }) => {
  const location = useLocation();
  
  const navItems = [
    { name: 'New', path: '/?status=new', icon: ClipboardList },
    { name: 'Pre-approved', path: '/?status=pre-approved', icon: FileCheck },
    { name: 'Working', path: '/?status=working', icon: LayoutDashboard },
    { name: 'Closed', path: '/?status=closed', icon: Archive },
    { name: 'Rejected', path: '/?status=rejected', icon: AlertTriangle },
  ];

  return (
    <div className="flex h-screen bg-slate-50">
      {/* Sidebar */}
      <aside className="w-64 bg-slate-900 text-white flex flex-col shadow-xl">
        <div className="p-6">
          <h1 className="text-xl font-bold tracking-tight flex items-center gap-2">
            <span className="p-1 bg-primary-600 rounded">GeM</span>
            <span>Tender Manager</span>
          </h1>
        </div>
        <nav className="flex-1 mt-4 px-3 space-y-1">
          {navItems.map((item) => (
            <Link
              key={item.name}
              to={item.path}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors ${
                location.search === item.path.split('?')[1] || (location.pathname === '/' && !location.search && item.name === 'Dashboard')
                  ? 'bg-primary-600 text-white'
                  : 'text-slate-400 hover:bg-slate-800 hover:text-white'
              }`}
            >
              <item.icon size={20} />
              <span className="font-medium">{item.name}</span>
            </Link>
          ))}
        </nav>
        <div className="p-6 border-t border-slate-800">
          <a
            href="https://bidplus.gem.gov.in/all-bids"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 text-sm text-slate-400 hover:text-white transition-colors"
          >
            <ExternalLink size={16} />
            Check GeM BidPlus
          </a>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto p-8">
        {children}
      </main>
    </div>
  );
};

function App() {
  return (
    <Router>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/tender/:bidNo" element={<TenderDetails />} />
        </Routes>
      </Layout>
    </Router>
  );
}

export default App;
