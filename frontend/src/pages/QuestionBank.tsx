import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Search,
  CheckCircle2,
  XCircle,
  HelpCircle,
  Bookmark,
  BookmarkCheck,
  ChevronDown,
  ChevronUp,
  RotateCcw,
  Sparkles,
  BookOpen,
} from 'lucide-react';
import { gateApi } from '../services/api';
import { MarkdownRenderer } from '../components/MarkdownRenderer';

interface QuestionBankProps {
  paperCode: string;
}

export const QuestionBank: React.FC<QuestionBankProps> = ({ paperCode }) => {
  const queryClient = useQueryClient();

  // Filters state
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedSubject, setSelectedSubject] = useState<string>('');
  const [selectedTopic, setSelectedTopic] = useState<string>('');
  const [qTypeFilter, setQTypeFilter] = useState<string>('');
  const [marksFilter, setMarksFilter] = useState<string>('');
  const [yearFilter, setYearFilter] = useState<string>('');
  const [page, setPage] = useState<number>(1);

  // Interactive practice state: per-question candidate responses and results
  const [userSelections, setUserSelections] = useState<Record<string, string[]>>({});
  const [userNatAnswers, setUserNatAnswers] = useState<Record<string, number | undefined>>({});
  const [checkResults, setCheckResults] = useState<Record<string, any>>({});
  const [expandedSolutions, setExpandedSolutions] = useState<Record<string, boolean>>({});
  const [bookmarkedIds, setBookmarkedIds] = useState<Record<string, boolean>>(() => {
    try {
      const saved = localStorage.getItem(`gate_bookmarks_${paperCode}`);
      return saved ? JSON.parse(saved) : {};
    } catch {
      return {};
    }
  });

  // Query subjects taxonomy
  const { data: subjectsData } = useQuery({
    queryKey: ['taxonomy_subjects', paperCode],
    queryFn: () => gateApi.listSubjects(paperCode),
  });

  const subjectsList = subjectsData?.subjects || [];
  const currentSubjectObj = subjectsList.find((s: any) => s.name === selectedSubject);
  const topicsList = currentSubjectObj?.topics || [];

  // Query questions from backend
  const { data: questionsData, isLoading } = useQuery({
    queryKey: [
      'questions',
      paperCode,
      selectedSubject,
      selectedTopic,
      qTypeFilter,
      marksFilter,
      yearFilter,
      searchTerm,
      page,
    ],
    queryFn: () =>
      gateApi.listQuestions({
        paper_code: paperCode,
        subject_name: selectedSubject || undefined,
        topic_name: selectedTopic || undefined,
        question_type: qTypeFilter || undefined,
        marks: marksFilter ? Number(marksFilter) : undefined,
        examination_year: yearFilter ? Number(yearFilter) : undefined,
        q: searchTerm.trim() || undefined,
        page,
        page_size: 20,
      }),
  });

  const totalQuestions = questionsData?.total || 0;
  const questions = questionsData?.items || [];
  const totalPages = Math.ceil(totalQuestions / 20) || 1;

  // Toggle bookmark
  const toggleBookmark = (qId: string) => {
    const updated = { ...bookmarkedIds, [qId]: !bookmarkedIds[qId] };
    setBookmarkedIds(updated);
    try {
      localStorage.setItem(`gate_bookmarks_${paperCode}`, JSON.stringify(updated));
    } catch {
      // storage error
    }
  };

  // Option selection handler
  const handleSelectOption = (qId: string, qType: string, optLabel: string) => {
    if (qType === 'MCQ') {
      setUserSelections((prev) => ({ ...prev, [qId]: [optLabel] }));
    } else if (qType === 'MSQ') {
      const current = userSelections[qId] || [];
      const exists = current.includes(optLabel);
      const updated = exists ? current.filter((l) => l !== optLabel) : [...current, optLabel];
      setUserSelections((prev) => ({ ...prev, [qId]: updated.sort() }));
    }
  };

  // Check answer mutation
  const checkMutation = useMutation({
    mutationFn: ({ qId, payload }: { qId: string; payload: any }) =>
      gateApi.checkAnswer(qId, payload),
    onSuccess: (data, variables) => {
      setCheckResults((prev) => ({ ...prev, [variables.qId]: data }));
      // Automatically expand explanation drawer
      setExpandedSolutions((prev) => ({ ...prev, [variables.qId]: true }));
      queryClient.invalidateQueries({ queryKey: ['dashboard_metrics'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard_progress'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard_recent'] });
    },
  });

  const handleCheckAnswer = (q: any) => {
    const qId = q.id;
    const qType = (q.question_type || 'MCQ').toUpperCase();
    const payload: any = {};

    if (qType === 'NAT') {
      payload.numerical_answer = userNatAnswers[qId];
    } else {
      payload.selected_options = userSelections[qId] || [];
    }

    checkMutation.mutate({ qId, payload });
  };

  const handleResetQuestion = (qId: string) => {
    setUserSelections((prev) => {
      const copy = { ...prev };
      delete copy[qId];
      return copy;
    });
    setUserNatAnswers((prev) => {
      const copy = { ...prev };
      delete copy[qId];
      return copy;
    });
    setCheckResults((prev) => {
      const copy = { ...prev };
      delete copy[qId];
      return copy;
    });
    setExpandedSolutions((prev) => {
      const copy = { ...prev };
      delete copy[qId];
      return copy;
    });
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2.5">
            <span>Topic-wise Question Bank</span>
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 font-semibold border border-indigo-500/30">
              GATE {paperCode}
            </span>
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Browse, filter, and practice real GATE questions with authoritative mathematical formulas rendered in KaTeX.
          </p>
        </div>
        <div className="text-right">
          <span className="text-xs text-slate-400">Total in Bank</span>
          <div className="text-xl font-bold text-white">{totalQuestions} Questions</div>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="bg-[#0B132B] border border-slate-800 rounded-xl p-4 shadow-sm space-y-3">
        {/* Top search & type/year row */}
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
          <div className="md:col-span-2 relative">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
            <input
              type="text"
              placeholder="Search question prompt, topic, keyword..."
              value={searchTerm}
              onChange={(e) => {
                setSearchTerm(e.target.value);
                setPage(1);
              }}
              className="w-full bg-[#1C2541] border border-slate-700/80 rounded-lg pl-9 pr-3 py-2 text-sm text-white placeholder-slate-400 focus:outline-none focus:border-indigo-500"
            />
          </div>

          <div>
            <select
              value={qTypeFilter}
              onChange={(e) => {
                setQTypeFilter(e.target.value);
                setPage(1);
              }}
              className="w-full bg-[#1C2541] border border-slate-700/80 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
            >
              <option value="">All Question Types</option>
              <option value="MCQ">MCQ (Single Choice)</option>
              <option value="MSQ">MSQ (Multiple Select)</option>
              <option value="NAT">NAT (Numerical Answer)</option>
            </select>
          </div>

          <div>
            <select
              value={marksFilter}
              onChange={(e) => {
                setMarksFilter(e.target.value);
                setPage(1);
              }}
              className="w-full bg-[#1C2541] border border-slate-700/80 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
            >
              <option value="">All Marks (1 or 2)</option>
              <option value="1">1 Mark</option>
              <option value="2">2 Marks</option>
            </select>
          </div>
        </div>

        {/* Syllabus subject & topic hierarchy row */}
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 pt-1 border-t border-slate-800/60">
          <div>
            <label className="block text-[11px] uppercase tracking-wider text-slate-400 font-semibold mb-1">
              Subject
            </label>
            <select
              value={selectedSubject}
              onChange={(e) => {
                setSelectedSubject(e.target.value);
                setSelectedTopic('');
                setPage(1);
              }}
              className="w-full bg-[#1C2541] border border-slate-700/80 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
            >
              <option value="">All Subjects</option>
              {subjectsList.map((s: any) => (
                <option key={s.id || s.name} value={s.name}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-[11px] uppercase tracking-wider text-slate-400 font-semibold mb-1">
              Topic
            </label>
            <select
              value={selectedTopic}
              onChange={(e) => {
                setSelectedTopic(e.target.value);
                setPage(1);
              }}
              disabled={!selectedSubject}
              className="w-full bg-[#1C2541] border border-slate-700/80 rounded-lg px-3 py-2 text-xs text-slate-200 disabled:opacity-50 focus:outline-none focus:border-indigo-500"
            >
              <option value="">All Topics</option>
              {topicsList.map((t: any) => (
                <option key={t.id || t.name} value={t.name}>
                  {t.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-[11px] uppercase tracking-wider text-slate-400 font-semibold mb-1">
              Exam Year
            </label>
            <select
              value={yearFilter}
              onChange={(e) => {
                setYearFilter(e.target.value);
                setPage(1);
              }}
              className="w-full bg-[#1C2541] border border-slate-700/80 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
            >
              <option value="">All Available Years</option>
              <option value="2012">2012 (65 Questions • 100% Official Key)</option>
              <option value="2013">2013 (68 Questions • Multi-Session)</option>
            </select>
          </div>
        </div>
      </div>

      {/* Questions Feed */}
      {isLoading ? (
        <div className="bg-[#0B132B] border border-slate-800 rounded-xl p-12 text-center text-slate-400">
          <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto mb-3"></div>
          <p className="text-sm">Loading Question Bank...</p>
        </div>
      ) : questions.length === 0 ? (
        <div className="bg-[#0B132B] border border-slate-800 rounded-xl p-12 text-center space-y-3">
          <BookOpen className="w-12 h-12 text-slate-600 mx-auto" />
          <h3 className="text-lg font-bold text-white">No Questions Matched</h3>
          <p className="text-sm text-slate-400 max-w-md mx-auto">
            Try adjusting your search query, selecting "All Subjects", or resetting filters.
          </p>
          <button
            onClick={() => {
              setSearchTerm('');
              setSelectedSubject('');
              setSelectedTopic('');
              setQTypeFilter('');
              setMarksFilter('');
              setYearFilter('');
              setPage(1);
            }}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold"
          >
            Reset Filters
          </button>
        </div>
      ) : (
        <div className="space-y-5">
          {questions.map((q: any) => {
            const qId = q.id;
            const qType = (q.question_type || 'MCQ').toUpperCase();
            const marks = q.marks || 1.0;
            const neg = q.negative_marks !== undefined ? Number(q.negative_marks).toFixed(2) : (marks / 3).toFixed(2);
            const isBookmarked = !!bookmarkedIds[qId];
            const checkResult = checkResults[qId];
            const isSolutionExpanded = !!expandedSolutions[qId];

            const selectedOptions = userSelections[qId] || [];
            const natVal = userNatAnswers[qId];

            return (
              <div
                key={qId}
                className="bg-[#0B132B] border border-slate-800 rounded-xl p-5 shadow-sm hover:border-slate-700/80 transition-colors space-y-4"
              >
                {/* Question metadata badge bar */}
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800/80 pb-3">
                  <div className="flex flex-wrap items-center gap-2 text-xs">
                    <span className="px-2.5 py-1 rounded bg-indigo-500/20 text-indigo-300 font-bold border border-indigo-500/30">
                      GATE {q.paper_code} {q.examination_year} • Q.{q.question_number}
                    </span>
                    <span className="px-2.5 py-1 rounded bg-[#1C2541] text-slate-200 font-semibold">
                      {qType}
                    </span>
                    <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-medium text-[11px]">
                      +{marks} Mark{marks > 1 ? 's' : ''} {qType === 'MCQ' ? `(-${neg})` : '(No Negative)'}
                    </span>
                    <span className="text-slate-400 text-xs hidden sm:inline">•</span>
                    <span className="text-slate-300 text-xs font-medium">
                      {q.subject_name || 'General'}
                    </span>
                    {q.primary_topic_name && (
                      <span className="text-indigo-400 text-xs font-medium">
                        → {q.primary_topic_name}
                      </span>
                    )}
                  </div>

                  <div className="flex items-center gap-2">
                    {/* Official answer key status pill */}
                    {q.answer_key?.is_verified ? (
                      <span className="inline-flex items-center gap-1 text-[11px] text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 px-2 py-0.5 rounded-full font-medium">
                        <CheckCircle2 className="w-3.5 h-3.5" /> Official IIT Key
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-[11px] text-amber-400 bg-amber-500/10 border border-amber-500/30 px-2 py-0.5 rounded-full font-medium">
                        <HelpCircle className="w-3.5 h-3.5" /> Unverified Key
                      </span>
                    )}

                    {/* Bookmark toggle */}
                    <button
                      onClick={() => toggleBookmark(qId)}
                      className={`p-1.5 rounded-lg border transition-colors ${
                        isBookmarked
                          ? 'bg-amber-500/20 text-amber-400 border-amber-500/40'
                          : 'bg-[#1C2541] text-slate-400 hover:text-white border-slate-700'
                      }`}
                      title={isBookmarked ? 'Remove Bookmark' : 'Bookmark Question'}
                    >
                      {isBookmarked ? <BookmarkCheck className="w-4 h-4" /> : <Bookmark className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                {/* Question Stem (Rendered with KaTeX fidelity) */}
                <div className="text-sm text-slate-100 leading-relaxed">
                  <MarkdownRenderer content={q.question_text || ''} />
                </div>

                {/* Visual Asset Schematics/Diagrams (Stem) */}
                {q.visual_assets &&
                  q.visual_assets
                    .filter((a: any) => a.asset_role === 'stem')
                    .map((a: any) => (
                      <div key={a.id} className="my-3 flex justify-center">
                        <img
                          src={gateApi.getAssetImageUrl(a.id)}
                          alt={`Diagram for Q.${q.question_number}`}
                          className="max-h-80 rounded-lg border border-slate-700 bg-white p-2 shadow object-contain"
                          loading="lazy"
                        />
                      </div>
                    ))}

                {/* Interactive Options / Answer Input Section */}
                <div className="pt-2">
                  {qType === 'NAT' ? (
                    /* NAT input box */
                    <div className="max-w-xs space-y-1.5">
                      <label className="block text-xs font-semibold text-slate-300">
                        Enter Numerical Answer:
                      </label>
                      <input
                        type="number"
                        step="any"
                        placeholder="e.g. 42 or 3.14"
                        value={natVal !== undefined ? natVal : ''}
                        onChange={(e) =>
                          setUserNatAnswers((prev) => ({
                            ...prev,
                            [qId]: e.target.value === '' ? undefined : Number(e.target.value),
                          }))
                        }
                        className="w-full bg-[#1C2541] border border-slate-700 rounded-lg px-3 py-2 text-sm text-white font-mono focus:outline-none focus:border-indigo-500"
                      />
                    </div>
                  ) : (
                    /* MCQ / MSQ Options */
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                      {q.options &&
                        q.options.map((opt: any) => {
                          const isSelected = selectedOptions.includes(opt.option_label);
                          const optAsset = q.visual_assets?.find(
                            (a: any) => a.asset_role === 'option' && a.option_label === opt.option_label
                          );

                          // Highlight styling if evaluated
                          let borderClass = 'border-slate-800 bg-[#1C2541]/40 hover:bg-[#1C2541]/80';
                          if (isSelected) {
                            borderClass = 'border-indigo-500 bg-indigo-600/20 text-white font-medium';
                          }
                          if (checkResult && checkResult.is_correct !== null) {
                            const isOfficialCorrect = checkResult.correct_options?.includes(opt.option_label);
                            if (isOfficialCorrect) {
                              borderClass = 'border-emerald-500 bg-emerald-500/20 text-emerald-200';
                            } else if (isSelected && !isOfficialCorrect) {
                              borderClass = 'border-rose-500 bg-rose-500/20 text-rose-200';
                            }
                          }

                          return (
                            <button
                              key={opt.option_label}
                              type="button"
                              onClick={() => handleSelectOption(qId, qType, opt.option_label)}
                              className={`p-3 rounded-xl border text-left transition-all flex flex-col justify-between ${borderClass}`}
                            >
                              <div className="flex items-start gap-2.5">
                                <span className="font-bold text-indigo-400 shrink-0 text-sm">
                                  ({opt.option_label})
                                </span>
                                <div className="text-xs sm:text-sm text-slate-200 leading-normal flex-1">
                                  <MarkdownRenderer content={opt.option_text || ''} />
                                </div>
                              </div>
                              {optAsset && (
                                <div className="mt-2 flex justify-center">
                                  <img
                                    src={gateApi.getAssetImageUrl(optAsset.id)}
                                    alt={`Option (${opt.option_label}) Diagram`}
                                    className="max-h-36 rounded border border-slate-700 bg-white p-1 object-contain"
                                    loading="lazy"
                                  />
                                </div>
                              )}
                            </button>
                          );
                        })}
                    </div>
                  )}
                </div>

                {/* Practice Action Controls */}
                <div className="pt-3 border-t border-slate-800/80 flex flex-wrap items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleCheckAnswer(q)}
                      className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow flex items-center gap-1.5 transition-colors"
                    >
                      <Sparkles className="w-3.5 h-3.5" /> Check Answer
                    </button>
                    {(selectedOptions.length > 0 || natVal !== undefined || checkResult) && (
                      <button
                        onClick={() => handleResetQuestion(qId)}
                        className="px-3 py-2 rounded-lg bg-[#1C2541] hover:bg-slate-700 text-slate-300 text-xs font-medium flex items-center gap-1 transition-colors"
                      >
                        <RotateCcw className="w-3.5 h-3.5" /> Clear
                      </button>
                    )}
                  </div>

                  {/* Toggle Solution Drawer */}
                  <button
                    onClick={() =>
                      setExpandedSolutions((prev) => ({ ...prev, [qId]: !prev[qId] }))
                    }
                    className="text-xs text-indigo-400 hover:text-indigo-300 font-medium flex items-center gap-1 transition-colors"
                  >
                    <span>{isSolutionExpanded ? 'Hide Solution' : 'View Official Solution'}</span>
                    {isSolutionExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                  </button>
                </div>

                {/* Check Answer Feedback Banner */}
                {checkResult && (
                  <div
                    className={`p-3.5 rounded-xl border text-xs flex items-center justify-between gap-3 ${
                      checkResult.is_correct === true
                        ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                        : checkResult.is_correct === false
                        ? 'bg-rose-500/10 border-rose-500/30 text-rose-300'
                        : 'bg-amber-500/10 border-amber-500/30 text-amber-300'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      {checkResult.is_correct === true ? (
                        <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
                      ) : checkResult.is_correct === false ? (
                        <XCircle className="w-5 h-5 text-rose-400 shrink-0" />
                      ) : (
                        <HelpCircle className="w-5 h-5 text-amber-400 shrink-0" />
                      )}
                      <div>
                        <span className="font-bold">
                          {checkResult.is_correct === true
                            ? `Correct! (+${checkResult.marks_awarded} Marks)`
                            : checkResult.is_correct === false
                            ? `Incorrect (${checkResult.marks_awarded} Marks)`
                            : 'Unverified Answer Key'}
                        </span>
                        <p className="text-slate-300 text-[11px] mt-0.5">
                          {checkResult.is_correct !== null && checkResult.correct_options?.length > 0
                            ? `Official Answer: (${checkResult.correct_options.join(', ')})`
                            : checkResult.message}
                        </p>
                      </div>
                    </div>
                  </div>
                )}

                {/* Official Solution Drawer */}
                {isSolutionExpanded && (
                  <div className="bg-[#070D1E] border border-slate-800 rounded-xl p-4 space-y-2.5 animate-fadeIn">
                    <div className="flex items-center justify-between text-xs border-b border-slate-800 pb-2">
                      <span className="font-bold text-indigo-300 flex items-center gap-1.5">
                        <BookOpen className="w-4 h-4 text-indigo-400" /> Official Answer Key & Derivation
                      </span>
                      <span className="text-[11px] text-slate-400">
                        Provenance: <strong className="text-slate-200">{q.answer_key?.provenance || 'unverified'}</strong>
                      </span>
                    </div>

                    <div className="text-xs text-slate-300 space-y-2 leading-relaxed">
                      {q.answer_key?.correct_options && q.answer_key.correct_options.length > 0 && (
                        <p className="font-semibold text-emerald-400">
                          Official Correct Option(s): {q.answer_key.correct_options.map((o: string) => `(${o})`).join(', ')}
                        </p>
                      )}
                      {q.answer_key?.numerical_min !== null && q.answer_key?.numerical_min !== undefined && (
                        <p className="font-semibold text-emerald-400">
                          Accepted Range: [{q.answer_key.numerical_min}, {q.answer_key.numerical_max}]
                        </p>
                      )}

                      {q.answer_key?.explanation ? (
                        <div className="mt-2 text-slate-200">
                          <MarkdownRenderer content={q.answer_key.explanation} />
                        </div>
                      ) : (
                        <p className="text-slate-400 italic">
                          Official answer key is confirmed ({q.answer_key?.correct_options?.join(', ') || 'N/A'}). Detailed step-by-step written derivation pending ingestion.
                        </p>
                      )}
                    </div>
                  </div>
                )}
              </div>
            );
          })}

          {/* Pagination Controls */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between pt-4 border-t border-slate-800 text-xs text-slate-400">
              <span>
                Page {page} of {totalPages} ({totalQuestions} total questions)
              </span>
              <div className="flex items-center gap-2">
                <button
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  className="px-3 py-1.5 rounded-lg bg-[#0B132B] border border-slate-800 disabled:opacity-40 hover:bg-[#1C2541] text-white"
                >
                  Previous
                </button>
                <button
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  className="px-3 py-1.5 rounded-lg bg-[#0B132B] border border-slate-800 disabled:opacity-40 hover:bg-[#1C2541] text-white"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
