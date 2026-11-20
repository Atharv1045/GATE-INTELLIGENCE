import React, { useState } from 'react';
import {
  X,
  Upload,
  FileText,
  AlertTriangle,
  CheckCircle2,
  RefreshCw,
  Plus,
  Trash2,
  Eye,
  EyeOff,
  Layers,
  Sparkles,
  HelpCircle,
} from 'lucide-react';
import { gateApi } from '../services/api';
import { MarkdownRenderer } from './MarkdownRenderer';

interface PdfPaperUploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  defaultPaperCode?: string;
  onImportSuccess?: (result: any) => void;
}

export const PdfPaperUploadModal: React.FC<PdfPaperUploadModalProps> = ({
  isOpen,
  onClose,
  defaultPaperCode = 'CS',
  onImportSuccess,
}) => {
  // Wizard steps: 'upload' -> 'extracting' -> 'review' -> 'success'
  const [step, setStep] = useState<'upload' | 'extracting' | 'review' | 'success'>('upload');
  
  // Step 1: Upload & Config form
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [paperCode, setPaperCode] = useState<string>(defaultPaperCode);
  const [year, setYear] = useState<number>(2012);
  const [sessionSet, setSessionSet] = useState<string>('Set-1');
  const [paperTitle, setPaperTitle] = useState<string>('');
  const [answerKeyFile, setAnswerKeyFile] = useState<File | null>(null);
  const [answerKeyText, setAnswerKeyText] = useState<string>('');
  const [enableOcr, setEnableOcr] = useState<boolean>(false);
  const [showAnswerKeyInput, setShowAnswerKeyInput] = useState<boolean>(false);

  // Step 2 & 3: Staged extraction state
  const [isExtracting, setIsExtracting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [stagedData, setStagedData] = useState<any | null>(null);
  const [stagedQuestions, setStagedQuestions] = useState<any[]>([]);
  const [overwriteIfExists, setOverwriteIfExists] = useState<boolean>(true);
  
  // Review screen filter & preview state
  const [searchFilter, setSearchFilter] = useState<string>('');
  const [previewStems, setPreviewStems] = useState<Record<string, boolean>>({});
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [importSummary, setImportSummary] = useState<any | null>(null);

  if (!isOpen) return null;

  const handleStartExtraction = async () => {
    if (!selectedFile) {
      setErrorMessage('Please select a PDF question paper file to upload.');
      return;
    }

    setErrorMessage(null);
    setIsExtracting(true);
    setStep('extracting');

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('paper_code', paperCode.trim().toUpperCase());
      formData.append('examination_year', String(year));
      formData.append('session_set', sessionSet.trim());
      if (paperTitle.trim()) {
        formData.append('title', paperTitle.trim());
      }
      if (answerKeyFile) {
        formData.append('answer_key_file', answerKeyFile);
      }
      if (answerKeyText.trim()) {
        formData.append('answer_key_text', answerKeyText.trim());
      }
      formData.append('enable_ocr', String(enableOcr));

      const res = await gateApi.uploadPaperPdf(formData);
      setStagedData(res);
      setStagedQuestions(res.questions || []);
      setOverwriteIfExists(res.is_duplicate ? true : true);
      setStep('review');
    } catch (err: any) {
      const detail = err.response?.data?.detail || err.message || 'PDF extraction failed.';
      setErrorMessage(detail);
      setStep('upload');
    } finally {
      setIsExtracting(false);
    }
  };

  const handleConfirmImport = async () => {
    if (!stagedData || stagedQuestions.length === 0) {
      setErrorMessage('No questions to import.');
      return;
    }

    setIsSaving(true);
    setErrorMessage(null);

    try {
      const payload = {
        paper_code: stagedData.paper_metadata?.paper_code || paperCode,
        examination_year: Number(stagedData.paper_metadata?.examination_year || year),
        session_set: stagedData.paper_metadata?.session_set || sessionSet,
        paper_title: stagedData.paper_metadata?.title || paperTitle || `GATE ${paperCode} ${year} (${sessionSet})`,
        file_checksum: stagedData.paper_metadata?.file_checksum,
        file_path: stagedData.paper_metadata?.file_path,
        page_count: stagedData.paper_metadata?.page_count || 0,
        is_scanned: stagedData.paper_metadata?.is_scanned || false,
        overwrite_if_exists: overwriteIfExists,
        questions: stagedQuestions,
      };

      const result = await gateApi.confirmPaperImport(payload);
      setImportSummary(result);
      setStep('success');
      if (onImportSuccess) {
        onImportSuccess(result);
      }
    } catch (err: any) {
      const detail = err.response?.data?.detail || err.message || 'Database import failed.';
      setErrorMessage(detail);
    } finally {
      setIsSaving(false);
    }
  };

  // Question editing handlers
  const updateQuestionField = (index: number, field: string, value: any) => {
    setStagedQuestions((prev) => {
      const copy = [...prev];
      copy[index] = { ...copy[index], [field]: value };
      return copy;
    });
  };

  const toggleOptionCorrect = (qIndex: number, optLabel: string) => {
    setStagedQuestions((prev) => {
      const copy = [...prev];
      const q = { ...copy[qIndex] };
      const isMcq = q.question_type === 'MCQ';
      let currentCorrect: string[] = q.correct_options ? [...q.correct_options] : [];

      if (isMcq) {
        currentCorrect = [optLabel];
      } else {
        if (currentCorrect.includes(optLabel)) {
          currentCorrect = currentCorrect.filter((l) => l !== optLabel);
        } else {
          currentCorrect.push(optLabel);
        }
      }

      q.correct_options = currentCorrect;
      q.options = (q.options || []).map((opt: any) => ({
        ...opt,
        is_correct: currentCorrect.includes(opt.option_label),
      }));

      copy[qIndex] = q;
      return copy;
    });
  };

  const updateOptionText = (qIndex: number, optIndex: number, text: string) => {
    setStagedQuestions((prev) => {
      const copy = [...prev];
      const q = { ...copy[qIndex] };
      const opts = [...(q.options || [])];
      opts[optIndex] = { ...opts[optIndex], option_text: text };
      q.options = opts;
      copy[qIndex] = q;
      return copy;
    });
  };

  const deleteQuestion = (index: number) => {
    setStagedQuestions((prev) => prev.filter((_, i) => i !== index));
  };

  const addNewQuestion = () => {
    const nextNum = stagedQuestions.length > 0 ? Math.max(...stagedQuestions.map((q) => q.question_number)) + 1 : 1;
    const newQ = {
      id: `manual_${Date.now()}`,
      question_number: nextNum,
      source_question_label: `Q.${nextNum}`,
      question_type: 'MCQ',
      question_text: 'Enter question stem here...',
      marks: 1.0,
      negative_marks: 0.333333,
      subject_name: 'General Aptitude',
      primary_topic_name: 'Core Concepts',
      difficulty_level: 'Medium',
      options: [
        { option_label: 'A', option_text: '', is_correct: false },
        { option_label: 'B', option_text: '', is_correct: false },
        { option_label: 'C', option_text: '', is_correct: false },
        { option_label: 'D', option_text: '', is_correct: false },
      ],
      correct_options: [],
      extraction_status: 'valid',
      extraction_warnings: ['Manually added question.'],
    };
    setStagedQuestions((prev) => [...prev, newQ]);
  };

  const filteredQuestions = stagedQuestions.filter((q) => {
    if (!searchFilter.trim()) return true;
    const term = searchFilter.toLowerCase();
    return (
      String(q.question_number).includes(term) ||
      (q.question_text || '').toLowerCase().includes(term) ||
      (q.subject_name || '').toLowerCase().includes(term) ||
      (q.primary_topic_name || '').toLowerCase().includes(term) ||
      (q.question_type || '').toLowerCase().includes(term)
    );
  });

  return (
    <div className="fixed inset-0 bg-black/85 flex items-center justify-center p-3 sm:p-5 z-50 animate-fadeIn overflow-hidden">
      <div className="bg-[#0B132B] border border-slate-700 rounded-xl w-full max-w-5xl max-h-[92vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="p-4 sm:p-5 border-b border-slate-800 flex items-center justify-between bg-[#10182E]">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-indigo-500/20 text-indigo-400 border border-indigo-500/30">
              <Upload className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white tracking-tight flex items-center gap-2">
                <span>Upload & Ingest Question Paper PDF</span>
                <span className="text-xs px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 font-semibold border border-indigo-500/30">
                  Step {step === 'upload' ? '1: Setup' : step === 'extracting' ? '2: Extracting' : step === 'review' ? '3: Review' : '4: Complete'}
                </span>
              </h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Local 16-stage PDF extraction, OCR fallback, question segmentation, and human review before database import.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg bg-[#1C2541] hover:bg-slate-700 text-slate-300 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Error Alert */}
        {errorMessage && (
          <div className="mx-5 mt-4 p-3 bg-rose-500/10 border border-rose-500/30 rounded-lg text-rose-300 text-xs flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0 text-rose-400" />
            <span>{errorMessage}</span>
          </div>
        )}

        {/* Modal Body Based on Step */}
        <div className="p-5 overflow-y-auto flex-1 space-y-5">
          {/* STEP 1: Upload Form */}
          {step === 'upload' && (
            <div className="space-y-5 max-w-3xl mx-auto">
              {/* File Dropzone */}
              <div
                className={`border-2 border-dashed rounded-xl p-8 text-center transition-all cursor-pointer ${
                  selectedFile
                    ? 'border-emerald-500/60 bg-emerald-500/5'
                    : 'border-slate-700 hover:border-indigo-500/60 bg-[#1C2541]/30 hover:bg-[#1C2541]/50'
                }`}
                onClick={() => {
                  const input = document.getElementById('pdf-file-input');
                  if (input) input.click();
                }}
              >
                <input
                  id="pdf-file-input"
                  type="file"
                  accept=".pdf"
                  className="hidden"
                  onChange={(e) => {
                    if (e.target.files && e.target.files[0]) {
                      const f = e.target.files[0];
                      setSelectedFile(f);
                      // Try auto-infer year from filename (e.g. 2012_CS.pdf)
                      const m = f.name.match(/\b(199\d|20[0-2]\d)\b/);
                      if (m) setYear(parseInt(m[1], 10));
                    }
                  }}
                />
                <FileText
                  className={`w-12 h-12 mx-auto mb-3 ${
                    selectedFile ? 'text-emerald-400' : 'text-slate-500'
                  }`}
                />
                {selectedFile ? (
                  <div>
                    <p className="text-sm font-semibold text-white">{selectedFile.name}</p>
                    <p className="text-xs text-emerald-400 mt-1">
                      {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB • Ready for extraction
                    </p>
                    <span className="text-[11px] text-slate-400 mt-2 inline-block underline">
                      Click to choose a different PDF
                    </span>
                  </div>
                ) : (
                  <div>
                    <p className="text-sm font-semibold text-white">Click or drag & drop GATE Question Paper PDF</p>
                    <p className="text-xs text-slate-400 mt-1">
                      Supports authentic question booklets with equations, tables, and options.
                    </p>
                  </div>
                )}
              </div>

              {/* Metadata Inputs */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 bg-[#10182E] p-4 rounded-xl border border-slate-800">
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">
                    GATE Discipline Code
                  </label>
                  <input
                    type="text"
                    value={paperCode}
                    onChange={(e) => setPaperCode(e.target.value.toUpperCase())}
                    className="w-full bg-[#1C2541] border border-slate-700 rounded-lg px-3 py-2 text-xs text-white uppercase focus:outline-none focus:border-indigo-500"
                    placeholder="e.g. CS, DA, EC"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">
                    Examination Year
                  </label>
                  <input
                    type="number"
                    value={year}
                    onChange={(e) => setYear(parseInt(e.target.value, 10) || 2012)}
                    className="w-full bg-[#1C2541] border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500"
                    placeholder="e.g. 2012"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">
                    Session / Set
                  </label>
                  <input
                    type="text"
                    value={sessionSet}
                    onChange={(e) => setSessionSet(e.target.value)}
                    className="w-full bg-[#1C2541] border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500"
                    placeholder="e.g. Set-1 or Session-2"
                  />
                </div>

                <div className="sm:col-span-3">
                  <label className="block text-xs font-semibold text-slate-300 mb-1">
                    Paper Title (Optional)
                  </label>
                  <input
                    type="text"
                    value={paperTitle}
                    onChange={(e) => setPaperTitle(e.target.value)}
                    className="w-full bg-[#1C2541] border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500"
                    placeholder={`GATE ${paperCode} ${year} (${sessionSet})`}
                  />
                </div>
              </div>

              {/* OCR Fallback Toggle */}
              <div className="bg-[#10182E] p-4 rounded-xl border border-slate-800 flex items-start gap-3">
                <input
                  type="checkbox"
                  id="enable-ocr-checkbox"
                  checked={enableOcr}
                  onChange={(e) => setEnableOcr(e.target.checked)}
                  className="mt-1 h-4 w-4 rounded border-slate-700 bg-[#1C2541] text-indigo-600 focus:ring-indigo-500"
                />
                <label htmlFor="enable-ocr-checkbox" className="text-xs cursor-pointer">
                  <span className="font-semibold text-slate-200 block">
                    Enable OCR Fallback for Scanned / Image Pages
                  </span>
                  <span className="text-slate-400 block mt-0.5">
                    Uses local Tesseract OCR engine when scanned pages or watermarks are detected. Clean digital text pages bypass OCR automatically for instant speed.
                  </span>
                </label>
              </div>

              {/* Optional Answer Key Section */}
              <div className="bg-[#10182E] p-4 rounded-xl border border-slate-800 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-indigo-400" />
                    <span className="text-xs font-semibold text-slate-200">
                      Attach Official Answer Key (Optional)
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() => setShowAnswerKeyInput(!showAnswerKeyInput)}
                    className="text-xs text-indigo-400 hover:text-indigo-300 underline"
                  >
                    {showAnswerKeyInput ? 'Hide Key Input' : '+ Add Answer Key'}
                  </button>
                </div>

                {showAnswerKeyInput && (
                  <div className="space-y-3 pt-2 border-t border-slate-800 text-xs">
                    <div>
                      <label className="block text-slate-400 mb-1">
                        Upload Key File (.json, .csv, or .txt):
                      </label>
                      <input
                        type="file"
                        accept=".json,.csv,.txt"
                        onChange={(e) => {
                          if (e.target.files && e.target.files[0]) {
                            setAnswerKeyFile(e.target.files[0]);
                          }
                        }}
                        className="text-xs text-slate-400 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-indigo-600 file:text-white hover:file:bg-indigo-500"
                      />
                    </div>

                    <div className="relative">
                      <label className="block text-slate-400 mb-1">
                        Or Paste Key Content (e.g. "Q.1: B", "1,A", or JSON):
                      </label>
                      <textarea
                        rows={3}
                        value={answerKeyText}
                        onChange={(e) => setAnswerKeyText(e.target.value)}
                        placeholder={`Q.1: B\nQ.2: C\nQ.3: 42.5\nQ.4: A, D`}
                        className="w-full bg-[#1C2541] border border-slate-700 rounded-lg p-2 text-xs text-white font-mono focus:outline-none focus:border-indigo-500"
                      />
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* STEP 2: Extracting Spinner */}
          {step === 'extracting' && (
            <div className="py-20 text-center space-y-4 max-w-md mx-auto">
              <div className="w-12 h-12 border-3 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto"></div>
              <h3 className="text-base font-bold text-white">Extracting & Segmenting Question Paper...</h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Analyzing PDF layout, stripping booklet instruction banners, extracting mathematical KaTeX expressions, classifying subject taxonomy, and associating answer keys.
              </p>
            </div>
          )}

          {/* STEP 3: Review Screen */}
          {step === 'review' && stagedData && (
            <div className="space-y-4">
              {/* Duplicate Warning Banner */}
              {stagedData.is_duplicate && (
                <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                  <div className="flex items-start gap-2.5">
                    <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5 sm:mt-0" />
                    <div>
                      <span className="font-bold block text-sm text-amber-200">Duplicate Paper Detected</span>
                      <p className="text-xs text-amber-300/90 mt-0.5">{stagedData.duplicate_reason}</p>
                    </div>
                  </div>
                  <label className="flex items-center gap-2 bg-[#10182E] px-3 py-1.5 rounded-lg border border-amber-500/40 cursor-pointer shrink-0">
                    <input
                      type="checkbox"
                      checked={overwriteIfExists}
                      onChange={(e) => setOverwriteIfExists(e.target.checked)}
                      className="rounded border-slate-700 text-indigo-600 focus:ring-indigo-500"
                    />
                    <span className="font-semibold text-white">Overwrite existing records</span>
                  </label>
                </div>
              )}

              {/* Extraction Metrics Bar */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="bg-[#10182E] p-3 rounded-xl border border-slate-800">
                  <span className="text-[10px] text-slate-400 uppercase font-semibold">Total Questions</span>
                  <div className="text-lg font-bold text-white mt-0.5">{stagedQuestions.length}</div>
                </div>
                <div className="bg-[#10182E] p-3 rounded-xl border border-slate-800">
                  <span className="text-[10px] text-slate-400 uppercase font-semibold">Extracted Pages</span>
                  <div className="text-lg font-bold text-slate-200 mt-0.5">{stagedData.extracted_page_count || 0}</div>
                </div>
                <div className="bg-[#10182E] p-3 rounded-xl border border-slate-800">
                  <span className="text-[10px] text-slate-400 uppercase font-semibold">Answer Keys Matched</span>
                  <div className="text-lg font-bold text-emerald-400 mt-0.5">
                    {stagedQuestions.filter((q) => (q.correct_options && q.correct_options.length > 0) || q.numerical_min !== null).length} / {stagedQuestions.length}
                  </div>
                </div>
                <div className="bg-[#10182E] p-3 rounded-xl border border-slate-800">
                  <span className="text-[10px] text-slate-400 uppercase font-semibold">OCR Status</span>
                  <div className="text-sm font-semibold text-slate-300 mt-1">
                    {stagedData.ocr_used ? 'OCR Recovered' : 'Digital Native'}
                  </div>
                </div>
              </div>

              {/* Review Filter & Add Question Bar */}
              <div className="flex flex-wrap items-center justify-between gap-3 bg-[#10182E] p-3 rounded-xl border border-slate-800">
                <div className="flex items-center gap-2 flex-1 max-w-md">
                  <input
                    type="text"
                    value={searchFilter}
                    onChange={(e) => setSearchFilter(e.target.value)}
                    placeholder="Search questions by number, text, or subject..."
                    className="w-full bg-[#1C2541] border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-indigo-500"
                  />
                  {searchFilter && (
                    <button
                      onClick={() => setSearchFilter('')}
                      className="text-xs text-slate-400 hover:text-white"
                    >
                      Clear
                    </button>
                  )}
                </div>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={addNewQuestion}
                    className="px-3 py-1.5 rounded-lg bg-[#1C2541] hover:bg-slate-700 text-xs font-semibold text-slate-200 flex items-center gap-1.5 transition"
                  >
                    <Plus className="w-3.5 h-3.5 text-indigo-400" /> Add Question
                  </button>
                </div>
              </div>

              {/* Question Review Cards List */}
              <div className="space-y-4 max-h-[50vh] overflow-y-auto pr-1">
                {filteredQuestions.length === 0 ? (
                  <div className="text-center py-10 text-xs text-slate-400">
                    No questions match filter "{searchFilter}".
                  </div>
                ) : (
                  filteredQuestions.map((q, idx) => {
                    // Find actual index in stagedQuestions
                    const realIndex = stagedQuestions.findIndex((item) => item.id === q.id || item.question_number === q.question_number);
                    const isPreview = previewStems[q.id || String(q.question_number)] || false;

                    return (
                      <div
                        key={q.id || idx}
                        className="bg-[#10182E] border border-slate-800 rounded-xl p-4 space-y-3 transition hover:border-slate-700"
                      >
                        {/* Question Top Bar */}
                        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800/80 pb-2.5">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-bold text-sm text-indigo-400">
                              Q.{q.question_number}
                            </span>

                            {/* Type Selector */}
                            <select
                              value={q.question_type}
                              onChange={(e) => updateQuestionField(realIndex, 'question_type', e.target.value)}
                              className="bg-[#1C2541] border border-slate-700 rounded px-2 py-0.5 text-xs text-white font-medium focus:outline-none"
                            >
                              <option value="MCQ">MCQ</option>
                              <option value="MSQ">MSQ</option>
                              <option value="NAT">NAT</option>
                            </select>

                            {/* Marks Selector */}
                            <select
                              value={q.marks}
                              onChange={(e) => {
                                const m = parseFloat(e.target.value);
                                updateQuestionField(realIndex, 'marks', m);
                                updateQuestionField(
                                  realIndex,
                                  'negative_marks',
                                  q.question_type === 'MCQ' ? roundNeg(m / 3.0) : 0.0
                                );
                              }}
                              className="bg-[#1C2541] border border-slate-700 rounded px-2 py-0.5 text-xs text-slate-200 focus:outline-none"
                            >
                              <option value="1">1.0 Mark</option>
                              <option value="2">2.0 Marks</option>
                            </select>

                            {/* Subject */}
                            <input
                              type="text"
                              value={q.subject_name || ''}
                              onChange={(e) => updateQuestionField(realIndex, 'subject_name', e.target.value)}
                              placeholder="Subject"
                              className="bg-[#1C2541] border border-slate-700 rounded px-2 py-0.5 text-xs text-slate-300 w-36 focus:outline-none"
                            />

                            {/* Topic */}
                            <input
                              type="text"
                              value={q.primary_topic_name || ''}
                              onChange={(e) => updateQuestionField(realIndex, 'primary_topic_name', e.target.value)}
                              placeholder="Topic"
                              className="bg-[#1C2541] border border-slate-700 rounded px-2 py-0.5 text-xs text-slate-400 w-44 focus:outline-none"
                            />
                          </div>

                          <div className="flex items-center gap-2">
                            <button
                              type="button"
                              onClick={() => {
                                setPreviewStems((prev) => ({
                                  ...prev,
                                  [q.id || String(q.question_number)]: !isPreview,
                                }));
                              }}
                              className="px-2 py-1 rounded bg-[#1C2541] text-xs text-slate-300 hover:text-white flex items-center gap-1"
                              title="Toggle KaTeX Math Preview"
                            >
                              {isPreview ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5 text-indigo-400" />}
                              <span>{isPreview ? 'Edit' : 'Preview'}</span>
                            </button>

                            <button
                              type="button"
                              onClick={() => deleteQuestion(realIndex)}
                              className="p-1 rounded hover:bg-rose-500/20 text-rose-400 hover:text-rose-300 transition"
                              title="Delete Question"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </div>

                        {/* Question Stem */}
                        <div>
                          {isPreview ? (
                            <div className="bg-[#1C2541]/40 border border-slate-800 rounded-lg p-3 text-xs text-slate-200">
                              <MarkdownRenderer content={q.question_text || ''} />
                            </div>
                          ) : (
                            <textarea
                              rows={2}
                              value={q.question_text || ''}
                              onChange={(e) => updateQuestionField(realIndex, 'question_text', e.target.value)}
                              className="w-full bg-[#1C2541] border border-slate-700 rounded-lg p-2.5 text-xs text-white focus:outline-none focus:border-indigo-500 font-mono"
                            />
                          )}
                        </div>

                        {/* Options Section for MCQ / MSQ */}
                        {q.question_type !== 'NAT' && (
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1">
                            {(q.options || []).map((opt: any, optIdx: number) => {
                              const isCorrect = (q.correct_options || []).includes(opt.option_label);
                              return (
                                <div
                                  key={opt.option_label || optIdx}
                                  className={`flex items-center gap-2 p-2 rounded-lg border text-xs ${
                                    isCorrect
                                      ? 'border-emerald-500/50 bg-emerald-500/10'
                                      : 'border-slate-800 bg-[#1C2541]/40'
                                  }`}
                                >
                                  <button
                                    type="button"
                                    onClick={() => toggleOptionCorrect(realIndex, opt.option_label)}
                                    className={`w-6 h-6 rounded flex items-center justify-center font-bold text-xs shrink-0 transition ${
                                      isCorrect
                                        ? 'bg-emerald-500 text-white shadow'
                                        : 'bg-[#1C2541] border border-slate-700 text-slate-300 hover:border-emerald-500'
                                    }`}
                                    title="Click to toggle correct answer"
                                  >
                                    {opt.option_label}
                                  </button>

                                  <input
                                    type="text"
                                    value={opt.option_text || ''}
                                    onChange={(e) => updateOptionText(realIndex, optIdx, e.target.value)}
                                    placeholder={`Option ${opt.option_label} text...`}
                                    className="w-full bg-transparent border-0 text-xs text-slate-200 focus:outline-none"
                                  />
                                </div>
                              );
                            })}
                          </div>
                        )}

                        {/* NAT Range Inputs */}
                        {q.question_type === 'NAT' && (
                          <div className="flex items-center gap-4 bg-[#1C2541]/30 p-2.5 rounded-lg border border-slate-800 text-xs">
                            <span className="text-slate-400 font-semibold">Accepted Range:</span>
                            <div className="flex items-center gap-2">
                              <span className="text-slate-500">Min:</span>
                              <input
                                type="number"
                                step="any"
                                value={q.numerical_min !== null && q.numerical_min !== undefined ? q.numerical_min : ''}
                                onChange={(e) =>
                                  updateQuestionField(
                                    realIndex,
                                    'numerical_min',
                                    e.target.value === '' ? null : parseFloat(e.target.value)
                                  )
                                }
                                placeholder="Min accepted"
                                className="bg-[#1C2541] border border-slate-700 rounded px-2 py-1 text-xs text-white w-28 focus:outline-none"
                              />
                            </div>
                            <div className="flex items-center gap-2">
                              <span className="text-slate-500">Max:</span>
                              <input
                                type="number"
                                step="any"
                                value={q.numerical_max !== null && q.numerical_max !== undefined ? q.numerical_max : ''}
                                onChange={(e) =>
                                  updateQuestionField(
                                    realIndex,
                                    'numerical_max',
                                    e.target.value === '' ? null : parseFloat(e.target.value)
                                  )
                                }
                                placeholder="Max accepted"
                                className="bg-[#1C2541] border border-slate-700 rounded px-2 py-1 text-xs text-white w-28 focus:outline-none"
                              />
                            </div>
                          </div>
                        )}

                        {/* Extraction Warnings if any */}
                        {q.extraction_warnings && q.extraction_warnings.length > 0 && (
                          <div className="text-[11px] text-amber-400/90 bg-amber-500/10 px-2.5 py-1 rounded border border-amber-500/20">
                            <span className="font-semibold">Notice:</span> {q.extraction_warnings.join(' • ')}
                          </div>
                        )}
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          )}

          {/* STEP 4: Success Screen */}
          {step === 'success' && importSummary && (
            <div className="py-12 text-center space-y-5 max-w-md mx-auto">
              <div className="w-14 h-14 bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 rounded-full flex items-center justify-center mx-auto shadow-lg">
                <CheckCircle2 className="w-8 h-8" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-white">Paper Ingestion Completed!</h3>
                <p className="text-xs text-slate-300 mt-1 leading-relaxed">
                  {importSummary.message}
                </p>
              </div>

              <div className="bg-[#10182E] p-4 rounded-xl border border-slate-800 text-left text-xs space-y-2">
                <div className="flex justify-between">
                  <span className="text-slate-400">Questions Saved:</span>
                  <span className="font-bold text-white">{importSummary.questions_imported}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Total Marks:</span>
                  <span className="font-bold text-white">{importSummary.total_marks}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Verified Answer Keys:</span>
                  <span className="font-bold text-emerald-400">{importSummary.verified_keys_count}</span>
                </div>
                {importSummary.backup_path && (
                  <div className="flex justify-between pt-1 border-t border-slate-800 text-[11px]">
                    <span className="text-slate-400">Safety Backup:</span>
                    <span className="text-slate-300 font-mono truncate max-w-[200px]" title={importSummary.backup_path}>
                      {importSummary.backup_path}
                    </span>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="p-4 sm:p-5 border-t border-slate-800 flex items-center justify-between bg-[#10182E]">
          <div>
            {step === 'review' && (
              <button
                type="button"
                onClick={() => setStep('upload')}
                className="px-3.5 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs text-slate-300 font-medium transition"
              >
                Back to Setup
              </button>
            )}
          </div>

          <div className="flex items-center gap-3">
            {step === 'upload' && (
              <>
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs text-slate-300 font-medium transition"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  disabled={!selectedFile || isExtracting}
                  onClick={handleStartExtraction}
                  className="px-5 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-xs text-white font-semibold flex items-center gap-2 shadow-lg transition"
                >
                  <Sparkles className="w-4 h-4" />
                  <span>Start Extraction & Segmentation</span>
                </button>
              </>
            )}

            {step === 'review' && (
              <>
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs text-slate-300 font-medium transition"
                >
                  Discard
                </button>
                <button
                  type="button"
                  disabled={isSaving || stagedQuestions.length === 0}
                  onClick={handleConfirmImport}
                  className="px-5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-xs text-white font-semibold flex items-center gap-2 shadow-lg transition"
                >
                  {isSaving ? (
                    <>
                      <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                      <span>Saving to Database...</span>
                    </>
                  ) : (
                    <>
                      <CheckCircle2 className="w-4 h-4" />
                      <span>Confirm & Commit {stagedQuestions.length} Questions</span>
                    </>
                  )}
                </button>
              </>
            )}

            {step === 'success' && (
              <button
                type="button"
                onClick={onClose}
                className="px-6 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-xs text-white font-semibold shadow-lg transition"
              >
                Done & View in Library
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

function roundNeg(val: number): number {
  return Math.round(val * 1000000) / 1000000;
}
