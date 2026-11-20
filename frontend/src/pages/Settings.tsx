import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Settings as SettingsIcon,
  HardDrive,
  DownloadCloud,
  RotateCcw,
  Upload,
  CheckCircle2,
  AlertTriangle,
  Info,
  ShieldCheck,
  FileJson,
  Moon,
  Sun,
  Save,
} from 'lucide-react';
import { gateApi } from '../services/api';

export const Settings: React.FC = () => {
  const queryClient = useQueryClient();

  // Preferences local state
  const [theme, setTheme] = useState<'dark' | 'light'>('dark');
  const [defaultPaper, setDefaultPaper] = useState<string>('CS');
  const [timerAlertMinutes, setTimerAlertMinutes] = useState<number>(15);

  // Backup state
  const [backupStatus, setBackupStatus] = useState<any | null>(null);

  // Reset confirmation state
  const [showResetModal, setShowResetModal] = useState<boolean>(false);
  const [resetStatusMsg, setResetStatusMsg] = useState<string | null>(null);

  // Dataset Import state
  const [importJsonText, setImportJsonText] = useState<string>('');
  const [importResult, setImportResult] = useState<any | null>(null);
  const [importError, setImportError] = useState<string | null>(null);

  // Load system diagnostics
  const { data: sysInfo, isLoading: isInfoLoading } = useQuery({
    queryKey: ['system_info'],
    queryFn: () => gateApi.getSystemInfo(),
  });

  // Load saved preferences
  const { data: savedPrefs } = useQuery({
    queryKey: ['user_preferences'],
    queryFn: () => gateApi.getPreferences(),
  });

  React.useEffect(() => {
    if (savedPrefs) {
      setTheme((savedPrefs.theme as 'dark' | 'light') || 'dark');
      setDefaultPaper(savedPrefs.default_paper || 'CS');
      setTimerAlertMinutes(savedPrefs.timer_alert_minutes || 15);
    }
  }, [savedPrefs]);

  // Save preferences mutation
  const savePrefsMutation = useMutation({
    mutationFn: (payload: any) => gateApi.savePreferences(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['user_preferences'] });
    },
  });

  // Backup mutation
  const backupMutation = useMutation({
    mutationFn: () => gateApi.createBackup(),
    onSuccess: (data) => {
      setBackupStatus(data);
      queryClient.invalidateQueries({ queryKey: ['system_info'] });
    },
  });

  // Reset progress mutation
  const resetMutation = useMutation({
    mutationFn: () => gateApi.resetProgress(true),
    onSuccess: (data) => {
      setShowResetModal(false);
      setResetStatusMsg(data.message || 'Student progress reset successfully.');
      queryClient.invalidateQueries({ queryKey: ['dashboard_metrics'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard_progress'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard_recent'] });
      queryClient.invalidateQueries({ queryKey: ['test_history'] });
      queryClient.invalidateQueries({ queryKey: ['system_info'] });
    },
  });

  // Import JSON mutation
  const importMutation = useMutation({
    mutationFn: (payload: any) => gateApi.importJsonDataset(payload),
    onSuccess: (data) => {
      setImportResult(data);
      setImportError(null);
      setImportJsonText('');
      queryClient.invalidateQueries({ queryKey: ['papers_catalog'] });
      queryClient.invalidateQueries({ queryKey: ['questions'] });
      queryClient.invalidateQueries({ queryKey: ['system_info'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard_metrics'] });
    },
    onError: (err: any) => {
      setImportError(err?.response?.data?.detail || err.message || 'Import failed.');
      setImportResult(null);
    },
  });

  const handleImportSubmit = () => {
    try {
      setImportError(null);
      const parsed = JSON.parse(importJsonText);
      importMutation.mutate(parsed);
    } catch (e: any) {
      setImportError(`Invalid JSON format: ${e.message}`);
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (event) => {
      const content = event.target?.result as string;
      setImportJsonText(content);
    };
    reader.readAsText(file);
  };

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div className="border-b border-slate-800 pb-5">
        <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2.5">
          <SettingsIcon className="w-6 h-6 text-indigo-400" />
          <span>Settings & Data Management</span>
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          Customize application preferences, import verified question datasets, and safely manage SQLite database backups.
        </p>
      </div>

      {/* Grid: 2 Columns */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Card 1: User Preferences */}
        <div className="bg-[#0B132B] border border-slate-800 rounded-xl p-5 shadow-sm space-y-4">
          <h2 className="text-base font-bold text-white flex items-center gap-2 border-b border-slate-800 pb-2.5">
            <Moon className="w-4 h-4 text-indigo-400" /> Application Preferences
          </h2>

          <div className="space-y-3 text-xs">
            <div>
              <label className="block text-slate-400 mb-1 font-semibold uppercase tracking-wider text-[10px]">
                Color Theme
              </label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setTheme('dark')}
                  className={`py-2 px-3 rounded-lg border text-xs font-semibold flex items-center justify-center gap-2 transition ${
                    theme === 'dark'
                      ? 'bg-indigo-600/20 border-indigo-500 text-white'
                      : 'bg-[#1C2541]/40 border-slate-800 text-slate-400'
                  }`}
                >
                  <Moon className="w-3.5 h-3.5" /> Dark Mode (Default)
                </button>
                <button
                  type="button"
                  onClick={() => setTheme('light')}
                  className={`py-2 px-3 rounded-lg border text-xs font-semibold flex items-center justify-center gap-2 transition ${
                    theme === 'light'
                      ? 'bg-indigo-600/20 border-indigo-500 text-white'
                      : 'bg-[#1C2541]/40 border-slate-800 text-slate-400'
                  }`}
                >
                  <Sun className="w-3.5 h-3.5" /> Light Mode
                </button>
              </div>
            </div>

            <div>
              <label className="block text-slate-400 mb-1 font-semibold uppercase tracking-wider text-[10px]">
                Default GATE Discipline
              </label>
              <select
                value={defaultPaper}
                onChange={(e) => setDefaultPaper(e.target.value)}
                className="w-full bg-[#1C2541] border border-slate-700 rounded-lg px-3 py-2 text-xs text-white"
              >
                <option value="CS">CS — Computer Science and Information Technology</option>
                <option value="DA">DA — Data Science and Artificial Intelligence</option>
                <option value="EC">EC — Electronics and Communication Engineering</option>
                <option value="EE">EE — Electrical Engineering</option>
                <option value="ME">ME — Mechanical Engineering</option>
                <option value="CE">CE — Civil Engineering</option>
              </select>
            </div>

            <div>
              <label className="block text-slate-400 mb-1 font-semibold uppercase tracking-wider text-[10px]">
                CBT Mock Test Timer Alert (Minutes Remaining)
              </label>
              <input
                type="number"
                min={5}
                max={60}
                value={timerAlertMinutes}
                onChange={(e) => setTimerAlertMinutes(Number(e.target.value))}
                className="w-full bg-[#1C2541] border border-slate-700 rounded-lg px-3 py-2 text-xs text-white"
              />
            </div>

            <div className="pt-2">
              <button
                onClick={() =>
                  savePrefsMutation.mutate({
                    theme,
                    default_paper: defaultPaper,
                    timer_alert_minutes: timerAlertMinutes,
                  })
                }
                disabled={savePrefsMutation.isPending}
                className="w-full py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-lg text-xs flex items-center justify-center gap-1.5 shadow"
              >
                <Save className="w-3.5 h-3.5" />
                {savePrefsMutation.isPending ? 'Saving...' : 'Save Preferences'}
              </button>
            </div>
          </div>
        </div>

        {/* Card 2: Database Management & Backups */}
        <div className="bg-[#0B132B] border border-slate-800 rounded-xl p-5 shadow-sm space-y-4">
          <h2 className="text-base font-bold text-white flex items-center gap-2 border-b border-slate-800 pb-2.5">
            <HardDrive className="w-4 h-4 text-emerald-400" /> Database & Safety
          </h2>

          <div className="space-y-3 text-xs">
            <div className="bg-[#1C2541]/40 p-3 rounded-lg border border-slate-800 space-y-1.5">
              <div className="flex items-center justify-between text-slate-400">
                <span>Database File:</span>
                <span className="font-mono text-slate-200 text-[11px]">storage/gate_intelligence.db</span>
              </div>
              <div className="flex items-center justify-between text-slate-400">
                <span>Size on Disk:</span>
                <span className="font-semibold text-slate-200">{sysInfo?.database_size_mb || 0} MB</span>
              </div>
              <div className="flex items-center justify-between text-slate-400">
                <span>Questions in Bank:</span>
                <span className="font-bold text-indigo-400">{sysInfo?.total_questions_in_bank || 0}</span>
              </div>
              <div className="flex items-center justify-between text-slate-400">
                <span>Completed Tests:</span>
                <span className="font-bold text-emerald-400">{sysInfo?.total_tests_completed || 0}</span>
              </div>
            </div>

            {/* On-demand backup button */}
            <div>
              <button
                onClick={() => backupMutation.mutate()}
                disabled={backupMutation.isPending}
                className="w-full py-2 bg-[#1C2541] hover:bg-slate-700 border border-slate-700 text-slate-200 font-semibold rounded-lg text-xs flex items-center justify-center gap-1.5 transition"
              >
                <DownloadCloud className="w-3.5 h-3.5 text-indigo-400" />
                {backupMutation.isPending ? 'Backing up SQLite...' : 'Create Instant Database Backup'}
              </button>
              {backupStatus && (
                <div className="mt-2 p-2 bg-emerald-500/10 border border-emerald-500/30 rounded text-emerald-300 text-[11px] flex items-center gap-1.5">
                  <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
                  <span>Backup created: {backupStatus.backup_filename} ({backupStatus.size_mb} MB)</span>
                </div>
              )}
            </div>

            {/* Progress Reset Button */}
            <div className="pt-2 border-t border-slate-800/80">
              <div className="flex items-center justify-between">
                <div>
                  <span className="font-semibold text-rose-400 block">Reset Practice Progress</span>
                  <span className="text-[11px] text-slate-400">Clears attempts & tests. Preserves questions.</span>
                </div>
                <button
                  onClick={() => setShowResetModal(true)}
                  className="px-3 py-1.5 bg-rose-500/15 hover:bg-rose-500/25 border border-rose-500/40 text-rose-300 rounded-lg text-xs font-semibold transition"
                >
                  Reset History
                </button>
              </div>

              {resetStatusMsg && (
                <div className="mt-2 p-2 bg-indigo-500/10 border border-indigo-500/30 rounded text-indigo-300 text-[11px]">
                  {resetStatusMsg}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Card 3: Validated JSON Dataset Importer */}
      <div className="bg-[#0B132B] border border-slate-800 rounded-xl p-5 shadow-sm space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-3">
          <div>
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              <FileJson className="w-4 h-4 text-amber-400" /> Validated JSON Dataset Importer
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Safely import official GATE questions and answer keys without modifying source code. Performs duplicate detection and idempotent upsert.
            </p>
          </div>

          <div>
            <label className="cursor-pointer inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#1C2541] hover:bg-slate-700 text-xs font-medium text-slate-200 border border-slate-700 transition">
              <Upload className="w-3.5 h-3.5 text-indigo-400" />
              <span>Load JSON File</span>
              <input type="file" accept=".json,application/json" onChange={handleFileUpload} className="hidden" />
            </label>
          </div>
        </div>

        <div className="space-y-3">
          <textarea
            rows={5}
            placeholder='Paste verified paper JSON dataset (e.g. { "paper_code": "CS", "examination_year": 2026, "session_set": "Set-1", "questions": [...] })'
            value={importJsonText}
            onChange={(e) => setImportJsonText(e.target.value)}
            className="w-full bg-[#1C2541] border border-slate-700 rounded-lg p-3 text-xs text-white font-mono placeholder-slate-500 focus:outline-none focus:border-indigo-500"
          />

          <div className="flex items-center justify-between">
            <span className="text-[11px] text-slate-400">
              Validates schema: <code className="text-indigo-300">paper_code</code>, <code className="text-indigo-300">examination_year</code>, <code className="text-indigo-300">question_number</code>, <code className="text-indigo-300">options</code>, <code className="text-indigo-300">answer_key</code>.
            </span>
            <button
              onClick={handleImportSubmit}
              disabled={!importJsonText.trim() || importMutation.isPending}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-semibold rounded-lg text-xs flex items-center gap-1.5 shadow"
            >
              <Upload className="w-3.5 h-3.5" />
              {importMutation.isPending ? 'Validating & Ingesting...' : 'Validate & Import Dataset'}
            </button>
          </div>

          {/* Import Result Audit Report */}
          {importResult && (
            <div className="p-4 bg-emerald-500/10 border border-emerald-500/30 rounded-xl text-xs space-y-2">
              <div className="flex items-center gap-2 text-emerald-300 font-bold">
                <CheckCircle2 className="w-4 h-4 shrink-0" />
                <span>Import Succeeded for GATE {importResult.paper_code} {importResult.examination_year}</span>
              </div>
              <div className="grid grid-cols-4 gap-2 pt-1 text-center">
                <div className="bg-[#0B132B] p-2 rounded">
                  <span className="text-[10px] text-slate-400 uppercase">Imported</span>
                  <div className="font-bold text-white text-sm">{importResult.imported}</div>
                </div>
                <div className="bg-[#0B132B] p-2 rounded">
                  <span className="text-[10px] text-slate-400 uppercase">Updated</span>
                  <div className="font-bold text-indigo-300 text-sm">{importResult.updated}</div>
                </div>
                <div className="bg-[#0B132B] p-2 rounded">
                  <span className="text-[10px] text-slate-400 uppercase">Invalid</span>
                  <div className="font-bold text-rose-400 text-sm">{importResult.invalid}</div>
                </div>
                <div className="bg-[#0B132B] p-2 rounded">
                  <span className="text-[10px] text-slate-400 uppercase">Total In Paper</span>
                  <div className="font-bold text-emerald-400 text-sm">{importResult.total_in_paper}</div>
                </div>
              </div>
            </div>
          )}

          {importError && (
            <div className="p-3 bg-rose-500/10 border border-rose-500/30 rounded-lg text-xs text-rose-300 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0 text-rose-400" />
              <span>{importError}</span>
            </div>
          )}
        </div>
      </div>

      {/* Card 4: Application Information */}
      <div className="bg-[#0B132B] border border-slate-800 rounded-xl p-5 shadow-sm space-y-3 text-xs">
        <h2 className="text-base font-bold text-white flex items-center gap-2 border-b border-slate-800 pb-2.5">
          <Info className="w-4 h-4 text-sky-400" /> Application Information
        </h2>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-slate-300">
          <div>
            <span className="text-slate-400 block text-[11px]">Application Name:</span>
            <strong className="text-white">{sysInfo?.app_name || 'GATE Intelligence'}</strong>
          </div>
          <div>
            <span className="text-slate-400 block text-[11px]">Architecture Version:</span>
            <strong className="text-indigo-300">v2.0.0 (Simplified Offline)</strong>
          </div>
          <div>
            <span className="text-slate-400 block text-[11px]">Runtime Mode:</span>
            <strong className="text-emerald-400">100% Offline Desktop Mode</strong>
          </div>
        </div>
      </div>

      {/* Two-step Progress Reset Confirmation Modal */}
      {showResetModal && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center p-4 z-50 animate-fadeIn">
          <div className="bg-[#0B132B] border border-slate-700 rounded-xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <h3 className="text-base font-bold text-rose-400 flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-rose-400" /> Confirm Student Progress Reset
            </h3>
            <p className="text-xs text-slate-300 leading-relaxed">
              This action will delete all candidate practice answers and CBT mock test histories.
            </p>
            <div className="bg-[#1C2541]/60 p-3 rounded-lg border border-slate-800 text-xs text-emerald-300 flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
              <span>Question Bank questions, official answer keys, and papers catalog will NOT be affected.</span>
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <button
                onClick={() => setShowResetModal(false)}
                className="px-4 py-2 bg-slate-800 text-slate-300 rounded-lg text-xs font-medium"
              >
                Cancel
              </button>
              <button
                onClick={() => resetMutation.mutate()}
                disabled={resetMutation.isPending}
                className="px-4 py-2 bg-rose-600 hover:bg-rose-500 text-white rounded-lg text-xs font-semibold"
              >
                {resetMutation.isPending ? 'Resetting...' : 'Yes, Reset Student Progress'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
