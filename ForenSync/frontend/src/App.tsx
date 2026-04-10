import { useState, useMemo } from 'react';
import axios from 'axios';
import {
  Upload, Search, Download,
  ChevronRight, X, Globe, Shield, Database, Zap, FileSpreadsheet, FileText,
  Copy, Check
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import * as XLSX from 'xlsx';
import { jsPDF } from 'jspdf';
import autoTable from 'jspdf-autotable';
import initSqlJs from 'sql.js';

const API_BASE = window.location.origin;

interface TimelineEvent {
  event_id: string;
  timestamp_utc: string;
  timestamp_unix: number;
  source_type: string;
  artifact_type: string;
  source_file: string;
  title: string;
  description: string;
  dedupe_key: string;
  confidence: number;
  fidelity_rank: number;
  tags: string[];
  metadata: Record<string, any>;
  raw_timestamp: string | null;
}

interface CaseData {
  case_name: string;
  events: TimelineEvent[];
  scanned_files: string[];
  warnings: string[];
  anomalies: string[];
  summary_md: string;
}

/** 
 * HOMEPAGE / LANDING AREA
 */
function LandingPage({ onUpload }: { onUpload: (fd: FormData) => void }) {
  return (
    <div className="h-screen w-screen flex items-center justify-center p-6 bg-slate-950">
      <div className="bg-vignette" />
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="max-w-2xl w-full glass p-12 rounded-lg space-y-12 relative text-center pt-24 overflow-hidden"
      >
        <div className="absolute top-8 left-8">
           <img src="/logo.png" alt="ForenSync" className="h-10 opacity-70" />
        </div>
        <div className="space-y-4 pb-8 border-b">
          <p className="text-slate-500 font-mono text-sm uppercase tracking-[0.3em]">Temporal Evidence Normalization</p>
        </div>
        <div className="space-y-6 pt-4">
          <input
            type="file" multiple className="hidden" id="initial-upload"
            onChange={(e) => {
              if (e.target.files?.length) {
                const formData = new FormData();
                for (let i = 0; i < e.target.files.length; i++) formData.append('files', e.target.files[i]);
                onUpload(formData);
              }
            }}
          />
          <button
            onClick={() => document.getElementById('initial-upload')?.click()}
            className="flex items-center justify-center space-x-3 w-full py-6 bg-teal-500 text-white font-bold rounded-lg cursor-pointer hover:bg-teal-600 transition-all shadow-sm"
          >
            <Upload size={20} />
            <span className="text-xl uppercase tracking-wider"></span>
          </button>
          <p className="text-[10px] text-slate-500 font-mono italic">Team : RansomWhere? | Track 3 : Cybersecurity</p>
        </div>
      </motion.div>
    </div>
  );
}

/** 
 * LOADING SCREEN
 */
function LoadingScreen() {
  return (
    <div className="h-screen w-screen flex flex-col items-center justify-center space-y-6 bg-slate-950">
      <div className="bg-grid opacity-20" />
      <div className="text-center space-y-4">
        <h2 className="text-3xl font-serif text-slate-200">Processing Evidence...</h2>
        <div className="w-64 h-[1px] bg-slate-300 mx-auto relative overflow-hidden">
          <motion.div
            initial={{ x: '-100%' }}
            animate={{ x: '100%' }}
            transition={{ repeat: Infinity, duration: 1.5, ease: "linear" }}
            className="absolute inset-0 bg-teal-500"
          />
        </div>
        <p className="text-slate-500 text-xs font-mono uppercase tracking-widest">Reconstructing Registry | Parsing Logs</p>
      </div>
    </div>
  );
}

export default function App() {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<CaseData | null>(null);
  const [search, setSearch] = useState('');
  const [selectedSource, setSelectedSource] = useState('all');
  const [selectedEvent, setSelectedEvent] = useState<TimelineEvent | null>(null);
  const [activeTab, setActiveTab] = useState<'timeline' | 'insights'>('timeline');
  const [showExport, setShowExport] = useState(false);

  const filteredEvents = useMemo(() => {
    if (!data) return [];
    return data.events.filter(e => {
      const haystack = `${e.title} ${e.description} ${e.source_file} ${e.source_type} ${Object.values(e.metadata).join(' ')}`.toLowerCase();
      const matchSearch = haystack.includes(search.toLowerCase());
      const matchSource = selectedSource === 'all' || e.source_type === selectedSource;
      return matchSearch && matchSource;
    });
  }, [data, search, selectedSource]);

  if (!data && !loading) {
    return (
      <LandingPage
        onUpload={(formData) => {
          setLoading(true);
          axios.post(`${API_BASE}/api/upload`, formData).then(res => {
            setData(res.data);
            setLoading(false);
          }).catch(() => setLoading(false));
        }}
      />
    );
  }

  if (loading) return <LoadingScreen />;

  return (
    <div className={`dashboard-grid ${selectedEvent ? 'has-detail' : ''} bg-slate-950`}>
      <div className="bg-vignette" />

      {/* NAV */}
      <nav className="header-nav grid-area-nav">
        <div className="flex items-center gap-2 pl-6">
          <img src="/logo.png" alt="ForenSync" className="h-5" />
          <div className="h-4 w-[1px] bg-border mx-1" />
        </div>

        <div className="flex-1 flex justify-center">
          <div className="relative w-full max-w-xl group">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" size={14} />
            <input
              type="text"
              placeholder="Filter case files..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full bg-slate-950 border rounded-lg pl-12 pr-4 py-2 text-sm focus:outline-none focus:border-slate-400 transition-all font-serif italic"
            />
          </div>
        </div>

        <div className="flex items-center justify-end gap-4 w-[280px]">
          <button
            onClick={() => setShowExport(true)}
            className="p-2 border rounded hover:bg-slate-900 transition-colors bg-accent text-white border-accent"
            title="Export Evidence"
          >
            <Download size={18} />
          </button>
          <button
            onClick={() => setData(null)}
            className="px-5 py-2 text-[10px] font-black uppercase tracking-widest border border-slate-300 hover:bg-slate-100 transition-all rounded-lg"
          >
            Close Case
          </button>
        </div>
      </nav>

      {/* SIDEBAR */}
      <aside className="grid-area-sidebar p-panel flex flex-col space-y-10">
        <div className="space-y-10">
          <section className="space-y-4">
            <h3 className="text-[10px] font-black text-slate-500 tracking-widest uppercase border-b pb-2">Analysis Index</h3>
            <div className="grid gap-3">
              <SidebarStat label="RECORDS FOUND" value={data?.events.length || 0} />
              <SidebarStat label="ARTEFACT SOURCES" value={data?.scanned_files.length || 0} />
            </div>
          </section>

          <section className="space-y-4">
            <h3 className="text-[10px] font-black text-slate-500 tracking-widest uppercase border-b pb-2">Artefact Filter</h3>
            <div className="space-y-1">
              {['all', 'browser_history', 'event_log', 'registry', 'prefetch', 'generic_csv', 'generic_log'].map(source => (
                <button
                  key={source}
                  onClick={() => setSelectedSource(source)}
                  className={`w-full flex items-center justify-between px-4 py-2 rounded-sm text-sm transition-all border ${selectedSource === source ? 'bg-white border-slate-300 shadow-sm' : 'border-transparent text-slate-500 hover:bg-white/50'
                    }`}
                >
                  <div className="flex items-center gap-2 capitalize font-serif italic">
                    {source.replace('_', ' ')}
                  </div>
                </button>
              ))}
            </div>
          </section>
        </div>

        <div className="mt-auto pt-8 border-t border-border">
          <p className="text-[10px] text-slate-500 font-mono uppercase">Case Signature: FS-RECON-8F3E2</p>
        </div>
      </aside>

      {/* EXPORT MODAL */}
      <AnimatePresence>
        {showExport && (
          <div className="export-menu-overlay" onClick={() => setShowExport(false)}>
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="export-card"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center justify-between mb-8 border-b-2 border-accent pb-4">
                <h2 className="text-2xl font-serif text-slate-800">Export Evidence Dossier</h2>
                <button onClick={() => setShowExport(false)} className="p-2 hover:bg-slate-100 border-none bg-transparent rounded-full transition-colors">
                  <X size={20} />
                </button>
              </div>

              <div className="space-y-2">
                <ExportOption
                  label="Structured Hierarchical (JSON)"
                  desc="Full fidelity raw data export"
                  onClick={() => exportJSON(data?.events)}
                />
                <ExportOption
                  label="Relational Database (SQLite)"
                  desc="Indexed evidence for SQL queries"
                  onClick={() => exportSQLite(data?.events)}
                />
                <ExportOption
                  label="Forensic Spreadsheet (XLSX)"
                  desc="Excel formatted with data types"
                  onClick={() => exportXLSX(data?.events)}
                />
                <ExportOption
                  label="Flat Timeline (CSV)"
                  desc="Universal interoperable format"
                  onClick={() => exportCSV(data?.events)}
                />
                <ExportOption
                  label="Investigative Report (PDF)"
                  desc="Visual read-only chronology"
                  onClick={() => exportPDF(data?.events, data?.summary_md)}
                />
              </div>

              <div className="mt-8 pt-4 border-t border-border flex justify-between items-center text-[9px] text-slate-400 uppercase font-mono tracking-widest">
                <span>Total records: {data?.events.length}</span>
                <span>Case File: {new Date().getFullYear()}-{Math.random().toString(36).substring(7).toUpperCase()}</span>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* MAIN */}
      <main className="grid-area-main">
        <div className="flex items-center justify-center border-b sticky top-0 z-20 bg-white">
          {['timeline', 'insights'].map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab as any)}
              className={`px-8 py-3 mx-2 my-2 text-[10px] font-black tracking-[0.2em] uppercase transition-all relative rounded-lg border-none ${activeTab === tab ? 'bg-teal-500/10 text-teal-500' : 'text-slate-400 hover:bg-slate-50'
                }`}
            >
              {tab}
              {activeTab === tab && (
                <motion.div layoutId="tab-underline" className="absolute bottom-0 left-0 right-0 h-[2px] bg-teal-500" />
              )}
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-y-auto custom-scrollbar">
          <AnimatePresence mode="wait">
            {activeTab === 'timeline' ? (
              <motion.div
                key="timeline"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="divide-y border-t"
              >
                {filteredEvents.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-48 text-slate-300 space-y-6">
                    <div className="w-16 h-16 rounded-full border-2 border-dashed border-slate-200 flex items-center justify-center">
                      <Search size={24} className="text-slate-200" />
                    </div>
                    <div className="text-center space-y-2">
                      <p className="font-serif italic text-lg text-slate-400">Archive Stream Awaiting Ingestion</p>
                      <p className="text-[10px] font-mono uppercase tracking-[0.2em] text-slate-300">No records matching active filter</p>
                    </div>
                  </div>
                ) : (
                  filteredEvents.map((event, idx) => (
                    <TimelineItem
                      key={event.event_id}
                      event={event}
                      index={idx}
                      isSelected={selectedEvent?.event_id === event.event_id}
                      onClick={() => setSelectedEvent(event === selectedEvent ? null : event)}
                    />
                  ))
                )}
              </motion.div>
            ) : (
              <motion.div
                key="insights"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="p-panel max-w-4xl mx-auto forensic-report"
              >
                <ReactMarkdown>{data?.summary_md}</ReactMarkdown>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </main>

      {/* DETAIL DRAWER */}
      <AnimatePresence>
        {selectedEvent && (
          <motion.aside
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: 440, opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            className="grid-area-detail border-l bg-white z-30 flex flex-col h-full overflow-hidden"
          >
            <div className="p-8 border-b flex items-center justify-between">
              <div>
                <h3 className="font-serif font-black text-xl text-slate-200">Record Audit</h3>
                <p className="text-[10px] text-slate-500 font-mono mt-1">Ref: {selectedEvent.event_id}</p>
              </div>
              <button onClick={() => setSelectedEvent(null)} className="p-2 border rounded-full hover:bg-slate-50"><X size={16} /></button>
            </div>

            <div className="flex-1 overflow-y-auto p-8 space-y-8 custom-scrollbar">
              <section className="space-y-4">
                <label className="text-[10px] font-black text-slate-500 tracking-widest uppercase border-b pb-2 block">Temporal Context</label>
                <div className="space-y-2">
                  <div className="flex justify-between items-center"><span className="text-xs italic text-slate-500">UTC Time</span><span className="text-sm font-mono text-teal-500 font-bold">{selectedEvent.timestamp_utc}</span></div>
                  <div className="flex justify-between items-center"><span className="text-xs italic text-slate-500">Unix</span><span className="text-xs font-mono text-slate-400">{selectedEvent.timestamp_unix}</span></div>
                </div>
              </section>

              <section className="space-y-4">
                <label className="text-[10px] font-black text-slate-500 tracking-widest uppercase border-b pb-2 block">Extracted Evidence Metadata</label>
                <div className="space-y-5">
                  {Object.entries(selectedEvent.metadata).map(([key, val]) => (
                    <MetadataRow key={key} label={key.replace(/_/g, ' ')} value={val} />
                  ))}
                </div>
              </section>
            </div>
          </motion.aside>
        )}
      </AnimatePresence>
    </div>
  );
}

function MetadataRow({ label, value }: { label: string, value: any }) {
  const [copied, setCopied] = useState(false);
  const strValue = typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value);

  const handleCopy = () => {
    navigator.clipboard.writeText(strValue);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-1.5 group/meta">
      <div className="flex items-center justify-between">
        <span className="text-[9px] text-slate-400 font-mono uppercase tracking-tight">{label}</span>
        <button
          onClick={handleCopy}
          className="p-1 opacity-0 group-hover/meta:opacity-100 transition-opacity border-none bg-transparent hover:bg-slate-100 rounded text-slate-400"
        >
          {copied ? <Check size={10} className="text-success" /> : <Copy size={10} />}
        </button>
      </div>
      <div className="text-xs font-mono text-slate-600 bg-[#f8f6f2] p-3 border border-[#e7e1d9] rounded-sm break-all leading-relaxed shadow-[inset_0_1px_3px_rgba(0,0,0,0.02)]">
        {strValue}
      </div>
    </div>
  );
}

function SidebarStat({ label, value }: { label: string, value: any }) {
  return (
    <div className="py-4 border-b border-slate-300 flex flex-col gap-1 relative overflow-hidden group">
      <span className="text-[9px] font-black tracking-widest text-slate-500 uppercase">{label}</span>
      <span className="text-3xl font-black font-mono text-slate-800 transition-transform group-hover:translate-x-1">{value}</span>
      <div className="absolute bottom-0 left-0 h-[2px] w-0 bg-accent transition-all duration-300 group-hover:w-full opacity-30" />
    </div>
  );
}

function TimelineItem({ event, index, isSelected, onClick }: { event: TimelineEvent, index: number, isSelected: boolean, onClick: () => void }) {
  const Icon = useMemo(() => {
    switch (event.source_type) {
      case 'browser_history': return Globe;
      case 'event_log': return Shield;
      case 'registry': return Database;
      case 'prefetch': return Zap;
      case 'generic_csv': return FileSpreadsheet;
      case 'generic_log': return FileText;
      default: return FileText;
    }
  }, [event.source_type]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: Math.min(index * 0.01, 0.3) }}
      onClick={onClick}
      className={`flex items-start gap-6 p-6 cursor-pointer transition-all group relative overflow-hidden ${isSelected ? 'bg-accent-light' : 'hover:bg-[#fbf9f6]'}`}
    >
      {isSelected && <div className="absolute left-0 top-0 bottom-0 w-1 bg-accent" />}

      <div className="flex flex-col items-center gap-1 pt-1.5">
        <div className={`p-2 rounded border ${isSelected ? 'bg-white border-accent text-accent shadow-sm' : 'bg-slate-50 border-slate-200 text-slate-400 group-hover:border-slate-300 group-hover:text-slate-600'} transition-all`}>
          <Icon size={16} />
        </div>
        <div className="w-[1px] flex-1 bg-slate-200 mt-1" />
      </div>

      <div className="flex-1 space-y-2.5 min-w-0">
        <div className="flex justify-between items-center">
          <div className="flex items-center gap-2">
            <span className={`px-2 py-0.5 rounded-full text-[9px] font-black tracking-widest uppercase border ${isSelected ? 'bg-accent text-white border-accent' : 'bg-white text-accent border-accent/20'}`}>
              {event.source_type.replace('_', ' ')}
            </span>
            <span className="text-[10px] font-mono text-slate-400">{event.timestamp_utc.split('T')[1].split('.')[0]}</span>
          </div>
          <span className="text-[9px] font-black text-slate-300 uppercase tracking-widest group-hover:text-slate-500 transition-colors">{event.artifact_type}</span>
        </div>
        <h4 className={`text-base font-bold truncate ${isSelected ? 'text-accent' : 'text-slate-800'}`}>{event.title}</h4>
        <p className="text-sm text-slate-500 line-clamp-2 leading-relaxed font-serif italic">{event.description}</p>
      </div>

      <div className="flex items-center self-center pl-4">
        <ChevronRight size={18} className={`transition-all ${isSelected ? 'text-accent rotate-90 scale-125' : 'text-slate-200 group-hover:text-slate-400 translate-x-0 group-hover:translate-x-1'}`} />
      </div>
    </motion.div>
  );
}

/** 
 * EXPORT HELPERS 
 */
function ExportOption({ label, desc, onClick }: { label: string, desc: string, onClick: () => void }) {
  return (
    <div
      className="export-option-row cursor-pointer"
      onClick={() => {
        console.log(`Triggering export: ${label}`);
        onClick();
      }}
    >
      <div>
        <span className="export-option-label">{label}</span>
        <span className="export-option-desc">{desc}</span>
      </div>
      <ChevronRight size={16} className="text-slate-300" />
    </div>
  );
}

const exportJSON = (events?: TimelineEvent[]) => {
  if (!events) return;
  const blob = new Blob([JSON.stringify(events, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `forensync_export_${new Date().toISOString()}.json`;
  link.click();
};

const exportCSV = (events?: TimelineEvent[]) => {
  if (!events) return;
  const worksheet = XLSX.utils.json_to_sheet(events.map(e => ({
    timestamp: e.timestamp_utc,
    source: e.source_type,
    artifact: e.artifact_type,
    title: e.title,
    description: e.description,
    confidence: e.confidence,
    source_file: e.source_file
  })));
  const csv = XLSX.utils.sheet_to_csv(worksheet);
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `forensync_timeline_${new Date().getTime()}.csv`;
  link.click();
};

const exportXLSX = (events?: TimelineEvent[]) => {
  if (!events) return;
  const wb = XLSX.utils.book_new();
  const ws = XLSX.utils.json_to_sheet(events.map(e => ({
    Timestamp_UTC: e.timestamp_utc,
    Source: e.source_type,
    Artifact: e.artifact_type,
    Title: e.title,
    Description: e.description,
    Confidence: e.confidence,
    Fidelity: e.fidelity_rank,
    Source_Path: e.source_file,
    Metadata: JSON.stringify(e.metadata)
  })));
  XLSX.utils.book_append_sheet(wb, ws, "Timeline");
  XLSX.writeFile(wb, `forensync_report_${new Date().getTime()}.xlsx`);
};

const exportPDF = (events?: TimelineEvent[], summary?: string) => {
  if (!events) return;
  const doc = new jsPDF();

  doc.setFont("times", "bold");
  doc.setFontSize(22);
  doc.text("ForenSync Investigative Report", 14, 20);

  doc.setFontSize(10);
  doc.setFont("courier", "normal");
  doc.text(`Generated: ${new Date().toUTCString()}`, 14, 28);
  doc.text(`Case ID: FS-${Math.floor(Date.now() / 100000)}`, 14, 33);

  // Add Executive Summary if available
  if (summary) {
    doc.setFont("times", "bold");
    doc.setFontSize(14);
    doc.text("Executive Summary", 14, 45);
    doc.setFont("times", "normal");
    doc.setFontSize(10);
    const splitSummary = doc.splitTextToSize(summary.replace(/[#*]/g, ''), 180);
    doc.text(splitSummary, 14, 52);
  }

  autoTable(doc, {
    startY: summary ? 120 : 45,
    head: [['Timestamp (UTC)', 'Source', 'Activity', 'Details']],
    body: events.map(e => [
      e.timestamp_utc.replace('T', '\n'),
      e.source_type.toUpperCase(),
      e.title,
      e.description
    ]),
    headStyles: { fillColor: [120, 53, 15] },
    theme: 'grid',
    styles: { fontSize: 8, font: 'times' }
  });

  doc.save(`forensync_investigation_${new Date().getTime()}.pdf`);
};

const exportSQLite = async (events?: TimelineEvent[]) => {
  if (!events) return;
  try {
    const SQL = await initSqlJs({
      locateFile: file => `https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.12.0/${file}`
    });
    const db = new SQL.Database();

    db.run(`
      CREATE TABLE events (
        id TEXT PRIMARY KEY,
        timestamp_utc TEXT,
        timestamp_unix INTEGER,
        source_type TEXT,
        artifact_type TEXT,
        title TEXT,
        description TEXT,
        confidence REAL,
        source_file TEXT,
        metadata_json TEXT
      )
    `);

    const stmt = db.prepare(`
      INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?)
    `);

    events.forEach(e => {
      stmt.run([
        e.event_id,
        e.timestamp_utc,
        e.timestamp_unix,
        e.source_type,
        e.artifact_type,
        e.title,
        e.description,
        e.confidence,
        e.source_file,
        JSON.stringify(e.metadata)
      ]);
    });
    stmt.free();

    const binaryArray = db.export();
    const blob = new Blob([binaryArray as any], { type: 'application/x-sqlite3' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `forensync_evidence_${new Date().getTime()}.db`;
    link.click();
  } catch (err) {
    console.error("SQLite Export Failed", err);
    alert("SQLite export failed focus. Check console for details.");
  }
};
