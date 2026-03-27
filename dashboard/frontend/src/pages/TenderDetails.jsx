import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import {
  ArrowLeft, FileText, Calendar, MapPin, Package,
  History, CheckCircle2, AlertTriangle, FileUp,
  Save, X, ChevronRight, ExternalLink, Download, ClipboardList
} from 'lucide-react';
import { format } from 'date-fns';

const API_BASE = "http://192.168.1.15:5001/api";

const TenderDetails = () => {
  const { bidNo } = useParams();
  const navigate = useNavigate();
  const [tender, setTender] = useState(null);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(false);
  const [note, setNote] = useState('');

  const statuses = ['new', 'pre-approved', 'working', 'closed'];

  const fetchDetails = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API_BASE}/tenders/${encodeURIComponent(bidNo)}`);
      setTender(res.data);
    } catch (err) {
      console.error("Failed to fetch details:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDetails();
  }, [bidNo]);

  const handleStatusChange = async (newStatus) => {
    if (newStatus === tender.status && !note) return;
    setUpdating(true);
    try {
      await axios.patch(`${API_BASE}/tenders/${encodeURIComponent(bidNo)}/status`, {
        status: newStatus,
        message: note || `Status changed to ${newStatus}`
      });
      await fetchDetails();
      setNote('');
    } catch (err) {
      alert("Failed to update status");
    } finally {
      setUpdating(false);
    }
  };

  if (loading) return <div>Loading details...</div>;
  if (!tender) return <div>Tender not found.</div>;

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button onClick={() => navigate(-1)} className="p-2 hover:bg-white rounded-full transition-colors">
          <ArrowLeft size={24} />
        </button>
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-3">
            {tender.bid_no}
            <span className={`text-xs font-bold uppercase px-2 py-1 rounded bg-slate-200 text-slate-700`}>
              {tender.status}
            </span>
          </h2>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Left Column: Info and Status */}
        <div className="col-span-2 space-y-6">
          <div className="card p-8">
            <h3 className="text-lg font-bold mb-6 flex items-center gap-2">
              <ClipboardList size={20} className="text-primary-600" />
              Tender Information
            </h3>

            <div className="grid grid-cols-2 gap-x-12 gap-y-8">
              <InfoItem icon={Calendar} label="Start Date" value={tender.start_date} />
              <InfoItem icon={Calendar} label="End Date" value={tender.end_date} />
              <div className="col-span-2">
                <InfoItem icon={FileText} label="Items / Data" value={tender.items} vertical />
              </div>
              <InfoItem icon={Package} label="Quantity" value={tender.quantity} />
              <InfoItem icon={MapPin} label="Department / Address" value={tender.department_name_and_address} vertical />
            </div>
          </div>

          <div className="card p-8">
            <h3 className="text-lg font-bold mb-6 flex items-center gap-2">
              <History size={20} className="text-primary-600" />
              Activity Log
            </h3>
            <div className="space-y-4">
              {tender.updates && tender.updates.map((update, idx) => (
                <div key={idx} className="flex gap-4 p-4 rounded-lg bg-slate-50 border border-slate-100">
                  <div className="mt-1">
                    <CheckCircle2 size={16} className="text-primary-500" />
                  </div>
                  <div className="flex-1">
                    <div className="flex justify-between items-center mb-1">
                      <span className="font-bold text-slate-800 text-sm">{update.status.toUpperCase()}</span>
                      <span className="text-xs text-slate-500">{new Date(update.timestamp).toLocaleString()}</span>
                    </div>
                    <p className="text-slate-600 text-sm leading-relaxed">{update.message}</p>
                    <p className="text-[10px] text-slate-400 mt-2">By {update.by}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column: Files and Actions */}
        <div className="space-y-6">
          <div className="card p-6">
            <h3 className="text-lg font-bold mb-6 flex items-center gap-2">
              <CheckCircle2 size={20} className="text-primary-600" />
              Manage Status
            </h3>
            <div className="space-y-4">
              <div>
                <label className="text-sm font-semibold text-slate-500 mb-2 block">Change Stage</label>
                <div className="flex flex-col gap-2">
                  {statuses.map(s => (
                    <button
                      key={s}
                      onClick={() => handleStatusChange(s)}
                      disabled={updating || tender.status === s}
                      className={`flex items-center justify-between w-full p-3 rounded-lg border text-sm font-medium transition-all ${tender.status === s
                          ? 'bg-primary-600 text-white border-primary-600'
                          : 'bg-white text-slate-600 border-slate-200 hover:border-primary-400'
                        }`}
                    >
                      <span className="capitalize">{s}</span>
                      {tender.status === s && <CheckCircle2 size={16} />}
                    </button>
                  ))}
                </div>
              </div>
              <div className="pt-4 border-t border-slate-100">
                <label className="text-sm font-semibold text-slate-500 mb-2 block">Add Work Note</label>
                <textarea
                  className="w-full h-24 p-3 bg-slate-50 border border-slate-200 rounded-lg text-sm outline-none focus:ring-2 focus:ring-primary-500"
                  placeholder="Record what was done..."
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                />
              </div>
            </div>
          </div>

          <div className="card p-6">
            <h3 className="text-lg font-bold mb-6 flex items-center gap-2">
              <FileUp size={20} className="text-primary-600" />
              Tender Documents
            </h3>
            <div className="space-y-2">
              {tender.files && tender.files.length > 0 ? (
                tender.files.map((file, idx) => (
                  <div key={idx} className="flex items-center justify-between p-3 bg-slate-50 rounded-lg group transition-colors hover:bg-white border border-transparent hover:border-slate-200">
                    <div className="flex items-center gap-3 truncate">
                      <FileText size={18} className="text-slate-400" />
                      <span className="text-sm text-slate-700 font-medium truncate py-1">
                        {file}
                      </span>
                    </div>
                    <a
                      href={`http://192.168.1.150:5001/api/files/${encodeURIComponent(tender.bid_no.replace('/', '-'))}/${encodeURIComponent(file)}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="p-1 text-slate-400 hover:text-primary-600 transition-colors"
                      title="View PDF"
                    >
                      <Download size={18} />
                    </a>
                  </div>
                ))
              ) : (
                <div className="text-center py-8">
                  <AlertTriangle className="mx-auto text-amber-500 mb-3" size={32} />
                  <p className="text-slate-500 text-sm">No files found for this bid.</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

const InfoItem = ({ icon: Icon, label, value, vertical = false }) => (
  <div className={`flex ${vertical ? 'flex-col gap-2' : 'gap-4'}`}>
    {!vertical && (
      <div className="p-2 bg-slate-50 rounded-lg h-fit">
        <Icon size={18} className="text-slate-500" />
      </div>
    )}
    <div>
      <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1 flex items-center gap-2">
        {vertical && <Icon size={14} className="text-slate-400" />}
        {label}
      </h4>
      <p className="text-slate-700 font-medium leading-relaxed overflow-hidden break-words">
        {value || 'Not available'}
      </p>
    </div>
  </div>
);

export default TenderDetails;
