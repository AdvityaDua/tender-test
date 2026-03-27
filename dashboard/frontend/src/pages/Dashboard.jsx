import React, { useState, useEffect } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import axios from 'axios';
import { Calendar, MapPin, Package, ArrowRight, Loader2, Search, ClipboardList } from 'lucide-react';
import { format } from 'date-fns';

const API_BASE = "http://192.168.1.15:5001/api";

const Dashboard = () => {
  const [searchParams] = useSearchParams();
  const statusFilter = searchParams.get('status') || 'new';
  const [tenders, setTenders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [sortBy, setSortBy] = useState('created_at');
  const [sortOrder, setSortOrder] = useState('desc');

  // Helper to parse GeM date strings: "DD-MM-YYYY HH:mm:ss" or "DD/MM/YYYY HH:mm:ss"
  const parseGemDate = (dateStr) => {
    if (!dateStr) return new Date(0);
    // If it's already ISO format (like created_at), parse directly
    if (typeof dateStr === 'string' && dateStr.includes('T')) return new Date(dateStr);

    try {
      // Split on any of: whitespace, dash, colon, or forward slash
      const parts = dateStr.split(/[\s\-:\/]+/);
      if (parts.length >= 3) {
        // [DD, MM, YYYY, HH, mm, ss]
        const day = parseInt(parts[0], 10);
        const month = parseInt(parts[1], 10) - 1;
        const year = parseInt(parts[2], 10);
        const hour = parseInt(parts[3], 10) || 0;
        const minute = parseInt(parts[4], 10) || 0;
        const second = parseInt(parts[5], 10) || 0;
        return new Date(year, month, day, hour, minute, second);
      }
    } catch (e) { }
    return new Date(dateStr);
  };

  useEffect(() => {
    const fetchTenders = async () => {
      setLoading(true);
      try {
        const res = await axios.get(`${API_BASE}/tenders?status=${statusFilter}`);
        setTenders(res.data);

        // Restore scroll position after data is loaded and rendered
        setTimeout(() => {
          const savedScroll = sessionStorage.getItem(`scroll_${statusFilter}`);
          if (savedScroll) {
            window.scrollTo(0, parseInt(savedScroll, 10));
          }
        }, 100);
      } catch (err) {
        console.error("Failed to fetch tenders:", err);
      } finally {
        setLoading(false);
      }
    };
    fetchTenders();

    // Save scroll position on unmount
    return () => {
      sessionStorage.setItem(`scroll_${statusFilter}`, window.scrollY.toString());
    };
  }, [statusFilter]);

  const filteredTenders = tenders.filter(t =>
    t.bid_no.toLowerCase().includes(searchTerm.toLowerCase()) ||
    t.items.toLowerCase().includes(searchTerm.toLowerCase()) ||
    t.department_name_and_address.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const sortedTenders = [...filteredTenders].sort((a, b) => {
    let valA, valB;
    if (sortBy === 'start_date' || sortBy === 'end_date' || sortBy === 'created_at') {
      valA = parseGemDate(a[sortBy]);
      valB = parseGemDate(b[sortBy]);
    } else {
      valA = a[sortBy] || '';
      valB = b[sortBy] || '';
    }

    if (valA < valB) return sortOrder === 'asc' ? -1 : 1;
    if (valA > valB) return sortOrder === 'asc' ? 1 : -1;
    return 0;
  });

  return (
    <div className="max-w-6xl mx-auto">
      <header className="flex justify-between items-center mb-8">
        <div>
          <h2 className="text-3xl font-bold capitalize text-slate-800">{statusFilter} Tenders</h2>
          <p className="text-slate-500 mt-1">Found {filteredTenders.length} tenders in {statusFilter} stage.</p>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 bg-white border border-slate-200 rounded-lg p-1 shadow-sm px-3 py-2">
            <span className="text-xs font-bold text-slate-400 uppercase">Sort By:</span>
            <select
              className="text-sm font-medium bg-transparent outline-none cursor-pointer"
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
            >
              <option value="created_at">Created At</option>
              <option value="start_date">Start Date</option>
              <option value="end_date">End Date</option>
              <option value="bid_no">Bid Number</option>
            </select>
            <button
              onClick={() => setSortOrder(prev => prev === 'asc' ? 'desc' : 'asc')}
              className="ml-2 p-1 hover:bg-slate-100 rounded text-slate-500 transition-colors"
              title={sortOrder === 'asc' ? 'Ascending' : 'Descending'}
            >
              {sortOrder === 'asc' ? '↑' : '↓'}
            </button>
          </div>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
            <input
              type="text"
              placeholder="Search bid number or items..."
              className="pl-10 pr-4 py-2 bg-white border border-slate-200 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none shadow-sm w-72"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
        </div>
      </header>

      {loading ? (
        <div className="flex flex-col items-center justify-center py-20 bg-white rounded-2xl shadow-sm border border-slate-100">
          <Loader2 className="animate-spin text-primary-600 mb-4" size={40} />
          <p className="text-slate-500 font-medium">Crunching tender data...</p>
        </div>
      ) : sortedTenders.length === 0 ? (
        <div className="text-center py-20 bg-white rounded-2xl border border-slate-100 shadow-sm">
          <ClipboardList className="mx-auto text-slate-300 mb-4" size={48} />
          <p className="text-slate-500 font-medium text-lg">No tenders found in this stage.</p>
          <p className="text-slate-400">Tenders from the scraper will appear here automatically.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-6">
          {sortedTenders.map((tender) => (
            <div key={tender.bid_no} className="card group hover:shadow-md transition-shadow">
              <div className="p-6">
                <div className="flex justify-between items-start mb-4">
                  <span className="text-xs font-bold text-primary-700 bg-primary-50 px-2 py-1 rounded uppercase tracking-wider">
                    {tender.status}
                  </span>
                  <div className="flex items-center gap-4 text-sm text-slate-500">
                    <div className="flex items-center gap-1">
                      <Calendar size={14} className="text-slate-400" />
                      <span>Starts: {tender.start_date}</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <Calendar size={14} className="text-slate-400" />
                      <span>Ends: {tender.end_date}</span>
                    </div>
                  </div>
                </div>

                <h3 className="text-xl font-bold text-slate-800 mb-2 truncate group-hover:text-primary-600 transition-colors">
                  {tender.bid_no}
                </h3>

                <p className="text-slate-600 line-clamp-2 mb-4 text-sm leading-relaxed">
                  {tender.items}
                </p>

                <div className="grid grid-cols-2 gap-4 border-t border-slate-50 pt-4 mt-2">
                  <div className="flex items-center gap-2 text-sm text-slate-600">
                    <Package size={16} className="text-slate-400 shrink-0" />
                    <span className="truncate">{tender.quantity}</span>
                  </div>
                  <div className="flex items-center gap-2 text-sm text-slate-600">
                    <MapPin size={16} className="text-slate-400 shrink-0" />
                    <span className="truncate">{tender.department_name_and_address}</span>
                  </div>
                </div>
              </div>
              <footer className="bg-slate-50 border-t border-slate-100 p-4 px-6 flex justify-end">
                <Link
                  to={`/tender/${encodeURIComponent(tender.bid_no)}`}
                  className="flex items-center gap-2 text-primary-600 font-semibold hover:text-primary-700 text-sm transition-colors"
                >
                  View Details & Documents
                  <ArrowRight size={16} />
                </Link>
              </footer>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default Dashboard;
