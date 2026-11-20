import React, { useState, useEffect, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import {
  Play,
  Clock,
  CheckCircle2,
  XCircle,
  AlertCircle,
  HelpCircle,
  ChevronLeft,
  ChevronRight,
  RotateCcw,
  Flag,
  Save,
  Send,
  Award,
  BookOpen,
  ArrowRight,
} from 'lucide-react';
import { gateApi } from '../services/api';
import { MarkdownRenderer } from '../components/MarkdownRenderer';

// 5 Official GATE CBT Palette States:
// 1: NOT_VISITED (Gray)
// 2: NOT_ANSWERED (Red)
// 3: ANSWERED (Green)
// 4: MARKED_FOR_REVIEW (Purple)
// 5: ANSWERED_AND_MARKED (Purple with Green badge)

export const MockTests: React.FC<{ paperCode: string }> = ({ paperCode }) => {
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();

  // Test setup state
  const [testMode, setTestMode] = useState<string>('full');
  const [selectedSubject, setSelectedSubject] = useState<string>('');
  const [selectedYear, setSelectedYear] = useState<number | undefined>(2012);
  const [durationMinutes, setDurationMinutes] = useState<number>(180);

  // Active test session state
  const [activeTest, setActiveTest] = useState<any | null>(null);
  const [currentIndex, setCurrentIndex] = useState<number>(0);
  const [timeRemainingSeconds, setTimeRemainingSeconds] = useState<number>(180 * 60);
  const [showSubmitModal, setShowSubmitModal] = useState<boolean>(false);

  // Responses per question_id:
  // { selected_options: string[], numerical_answer?: number, marked_for_review: boolean, is_visited: boolean, time_spent: number }
  const [candidateResponses, setCandidateResponses] = useState<Record<string, any>>({});

  // Scorecard / Post-test review
  const [scorecardResult, setScorecardResult] = useState<any | null>(null);

  // Check URL params for auto-launch
  const launchPaperId = searchParams.get('launch_paper_id');
  const launchYear = searchParams.get('launch_year');

  // Query subjects for drill down
  const { data: subjectsData } = useQuery({
    queryKey: ['taxonomy_subjects', paperCode],
    queryFn: () => gateApi.listSubjects(paperCode),
  });
  const subjects = subjectsData?.subjects || [];

  // Query past test history
  const { data: historyData } = useQuery({
    queryKey: ['test_history', paperCode],
    queryFn: () => gateApi.getTestHistory(paperCode),
    enabled: !activeTest,
  });

  // Start test mutation
  const startTestMutation = useMutation({
    mutationFn: (payload: any) => gateApi.startTest(payload),
    onSuccess: (data) => {
      setActiveTest(data);
      setCurrentIndex(0);
      setTimeRemainingSeconds(data.duration_seconds || 180 * 60);
      setScorecardResult(null);
      setShowSubmitModal(false);

      // Initialize question states
      const initial: Record<string, any> = {};
      data.questions.forEach((q: any, idx: number) => {
        initial[q.question_id] = {
          selected_options: [],
          numerical_answer: undefined,
          marked_for_review: false,
          is_visited: idx === 0, // first question is visited
          time_spent: 0,
        };
      });
      setCandidateResponses(initial);
    },
  });

  // Submit test mutation
  const submitTestMutation = useMutation({
    mutationFn: (payload: any) => gateApi.submitTest(activeTest.test_id, payload),
    onSuccess: (result) => {
      setScorecardResult(result);
      setActiveTest(null);
      setShowSubmitModal(false);
      queryClient.invalidateQueries({ queryKey: ['dashboard_metrics'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard_progress'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard_recent'] });
      queryClient.invalidateQueries({ queryKey: ['test_history'] });
    },
  });

  // Countdown timer hook with auto-submission upon 00:00:00
  useEffect(() => {
    if (!activeTest || scorecardResult) return;

    const timer = setInterval(() => {
      setTimeRemainingSeconds((prev) => {
        if (prev <= 1) {
          clearInterval(timer);
          handleForceAutoSubmit();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [activeTest, scorecardResult]);

  // Auto-launch from URL query params
  useEffect(() => {
    if (launchPaperId && !activeTest && !scorecardResult) {
      startTestMutation.mutate({
        paper_code: paperCode,
        test_mode: 'paper',
        paper_id: launchPaperId,
        duration_minutes: 180,
      });
    } else if (launchYear && !activeTest && !scorecardResult) {
      startTestMutation.mutate({
        paper_code: paperCode,
        test_mode: 'paper',
        year: Number(launchYear),
        duration_minutes: 180,
      });
    }
  }, [launchPaperId, launchYear]);

  // Current question helpers
  const questions = activeTest?.questions || [];
  const currentQ = questions[currentIndex];
  const currentResp = currentQ ? candidateResponses[currentQ.question_id] || {} : {};

  // Mark current question as visited
  const markVisited = (idx: number) => {
    if (!questions[idx]) return;
    const qid = questions[idx].question_id;
    setCandidateResponses((prev) => ({
      ...prev,
      [qid]: {
        ...(prev[qid] || { selected_options: [], marked_for_review: false }),
        is_visited: true,
      },
    }));
  };

  // Option selection
  const handleSelectOption = (optLabel: string) => {
    if (!currentQ) return;
    const qid = currentQ.question_id;
    const qType = (currentQ.question_type || 'MCQ').toUpperCase();

    if (qType === 'MCQ') {
      setCandidateResponses((prev) => ({
        ...prev,
        [qid]: {
          ...(prev[qid] || {}),
          selected_options: [optLabel],
          is_visited: true,
        },
      }));
    } else if (qType === 'MSQ') {
      const existing = currentResp.selected_options || [];
      const updated = existing.includes(optLabel)
        ? existing.filter((l: string) => l !== optLabel)
        : [...existing, optLabel];
      setCandidateResponses((prev) => ({
        ...prev,
        [qid]: {
          ...(prev[qid] || {}),
          selected_options: updated.sort(),
          is_visited: true,
        },
      }));
    }
  };

  // NAT number input
  const handleNatInput = (val: string) => {
    if (!currentQ) return;
    const qid = currentQ.question_id;
    setCandidateResponses((prev) => ({
      ...prev,
      [qid]: {
        ...(prev[qid] || {}),
        numerical_answer: val === '' ? undefined : Number(val),
        is_visited: true,
      },
    }));
  };

  // Candidate Controls
  const handleSaveAndNext = () => {
    // Unmarks for review if was marked, keeps answers
    if (currentQ) {
      const qid = currentQ.question_id;
      setCandidateResponses((prev) => ({
        ...prev,
        [qid]: {
          ...(prev[qid] || {}),
          marked_for_review: false,
          is_visited: true,
        },
      }));
    }
    if (currentIndex < questions.length - 1) {
      const nextIdx = currentIndex + 1;
      setCurrentIndex(nextIdx);
      markVisited(nextIdx);
    }
  };

  const handleMarkForReviewAndNext = () => {
    if (currentQ) {
      const qid = currentQ.question_id;
      setCandidateResponses((prev) => ({
        ...prev,
        [qid]: {
          ...(prev[qid] || {}),
          marked_for_review: true,
          is_visited: true,
        },
      }));
    }
    if (currentIndex < questions.length - 1) {
      const nextIdx = currentIndex + 1;
      setCurrentIndex(nextIdx);
      markVisited(nextIdx);
    }
  };

  const handleClearResponse = () => {
    if (!currentQ) return;
    const qid = currentQ.question_id;
    setCandidateResponses((prev) => ({
      ...prev,
      [qid]: {
        selected_options: [],
        numerical_answer: undefined,
        marked_for_review: false,
        is_visited: true,
        time_spent: prev[qid]?.time_spent || 0,
      },
    }));
  };

  const handlePrevious = () => {
    if (currentIndex > 0) {
      const prevIdx = currentIndex - 1;
      setCurrentIndex(prevIdx);
      markVisited(prevIdx);
    }
  };

  const handleNext = () => {
    if (currentIndex < questions.length - 1) {
      const nextIdx = currentIndex + 1;
      setCurrentIndex(nextIdx);
      markVisited(nextIdx);
    }
  };

  const handleJumpToQuestion = (idx: number) => {
    setCurrentIndex(idx);
    markVisited(idx);
  };

  // Force auto-submit when timer expires
  const handleForceAutoSubmit = () => {
    if (!activeTest) return;
    const formatted = questions.map((q: any) => {
      const r = candidateResponses[q.question_id] || {};
      return {
        question_id: q.question_id,
        selected_options: r.selected_options || [],
        numerical_answer: r.numerical_answer,
        marked_for_review: !!r.marked_for_review,
        time_spent_seconds: r.time_spent || 30,
      };
    });
    submitTestMutation.mutate({ responses: formatted });
  };

  const handleUserSubmit = () => {
    handleForceAutoSubmit();
  };

  // Calculate palette status for any question:
  // 1. Not Visited (Gray)
  // 2. Not Answered (Red)
  // 3. Answered (Green)
  // 4. Marked for Review (Purple)
  // 5. Answered & Marked for Review (Purple with dot)
  const getQuestionPaletteState = (q: any) => {
    const r = candidateResponses[q.question_id];
    if (!r || !r.is_visited) return 'NOT_VISITED';

    const hasAnswer =
      (r.selected_options && r.selected_options.length > 0) || r.numerical_answer !== undefined;
    const isMarked = !!r.marked_for_review;

    if (hasAnswer && isMarked) return 'ANSWERED_AND_MARKED';
    if (isMarked) return 'MARKED_FOR_REVIEW';
    if (hasAnswer) return 'ANSWERED';
    return 'NOT_ANSWERED';
  };

  // Palette counts
  let countNotVisited = 0;
  let countNotAnswered = 0;
  let countAnswered = 0;
  let countMarked = 0;
  let countAnsweredAndMarked = 0;

  questions.forEach((q: any) => {
    const state = getQuestionPaletteState(q);
    if (state === 'NOT_VISITED') countNotVisited++;
    else if (state === 'NOT_ANSWERED') countNotAnswered++;
    else if (state === 'ANSWERED') countAnswered++;
    else if (state === 'MARKED_FOR_REVIEW') countMarked++;
    else if (state === 'ANSWERED_AND_MARKED') countAnsweredAndMarked++;
  });

  // Format seconds to HH:MM:SS
  const formatTimer = (secs: number) => {
    const h = Math.floor(secs / 3600);
    const m = Math.floor((secs % 3600) / 60);
    const s = secs % 60;
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  };

  // =========================================================================
  // VIEW 1: CBT TEST SETUP / LAUNCHER (when no test active & no scorecard)
  // =========================================================================
  if (!activeTest && !scorecardResult) {
    return (
      <div className="p-6 max-w-5xl mx-auto space-y-6">
        <div className="border-b border-slate-800 pb-5">
          <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2.5">
            <span>Computer Based Test (CBT) Mock Examination</span>
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 font-semibold border border-indigo-500/30">
              GATE {paperCode}
            </span>
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Simulate the authentic GATE CBT examination environment with live 180-minute timer, official 5-state palette, and authoritative backend scoring.
          </p>
        </div>

        {/* Test Configuration Card */}
        <div className="bg-[#0B132B] border border-slate-800 rounded-xl p-6 shadow-sm space-y-5">
          <h2 className="text-base font-bold text-white flex items-center gap-2">
            <Play className="w-4 h-4 text-indigo-400 fill-current" /> Select Examination Mode
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Full Length Exam */}
            <button
              type="button"
              onClick={() => {
                setTestMode('full');
                setSelectedYear(2012);
              }}
              className={`p-4 rounded-xl border text-left transition-all flex flex-col justify-between ${
                testMode === 'full'
                  ? 'border-indigo-500 bg-indigo-600/20 text-white'
                  : 'border-slate-800 bg-[#1C2541]/40 hover:bg-[#1C2541] text-slate-300'
              }`}
            >
              <div>
                <span className="font-bold text-sm block text-indigo-300">
                  Full-Length GATE Exam
                </span>
                <p className="text-xs text-slate-400 mt-1">
                  65 Questions • 100 Marks • 180 Minutes (Official 2012 Paper with 100% verified keys)
                </p>
              </div>
              <span className="text-[11px] font-semibold text-emerald-400 mt-3 block">
                Recommended Baseline
              </span>
            </button>

            {/* Paper-Based Exam */}
            <button
              type="button"
              onClick={() => {
                setTestMode('paper');
                setSelectedYear(2013);
              }}
              className={`p-4 rounded-xl border text-left transition-all flex flex-col justify-between ${
                testMode === 'paper'
                  ? 'border-indigo-500 bg-indigo-600/20 text-white'
                  : 'border-slate-800 bg-[#1C2541]/40 hover:bg-[#1C2541] text-slate-300'
              }`}
            >
              <div>
                <span className="font-bold text-sm block text-indigo-300">
                  Past Paper Test
                </span>
                <p className="text-xs text-slate-400 mt-1">
                  Select any historical paper (2012, 2013) to solve in simulated exam conditions.
                </p>
              </div>
              <span className="text-[11px] font-semibold text-indigo-400 mt-3 block">
                Paper-Specific Drill
              </span>
            </button>

            {/* Custom Subject Drill */}
            <button
              type="button"
              onClick={() => setTestMode('subject')}
              className={`p-4 rounded-xl border text-left transition-all flex flex-col justify-between ${
                testMode === 'subject'
                  ? 'border-indigo-500 bg-indigo-600/20 text-white'
                  : 'border-slate-800 bg-[#1C2541]/40 hover:bg-[#1C2541] text-slate-300'
              }`}
            >
              <div>
                <span className="font-bold text-sm block text-indigo-300">
                  Subject Mock Drill
                </span>
                <p className="text-xs text-slate-400 mt-1">
                  Focus on a specific subject (e.g. Operating Systems or Algorithms).
                </p>
              </div>
              <span className="text-[11px] font-semibold text-purple-400 mt-3 block">
                Targeted Weak Areas
              </span>
            </button>
          </div>

          {/* Conditional drill options */}
          {testMode === 'paper' && (
            <div className="pt-2">
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                Select Exam Paper Year:
              </label>
              <select
                value={selectedYear}
                onChange={(e) => setSelectedYear(Number(e.target.value))}
                className="w-full sm:w-72 bg-[#1C2541] border border-slate-700 rounded-lg px-3 py-2 text-xs text-white"
              >
                <option value="2012">GATE CS 2012 (65 Questions • 100% Official IIT Key)</option>
                <option value="2013">GATE CS 2013 (65 Questions • Multi-Session)</option>
              </select>
            </div>
          )}

          {testMode === 'subject' && (
            <div className="pt-2">
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                Select Subject for Drill:
              </label>
              <select
                value={selectedSubject}
                onChange={(e) => setSelectedSubject(e.target.value)}
                className="w-full sm:w-80 bg-[#1C2541] border border-slate-700 rounded-lg px-3 py-2 text-xs text-white"
              >
                <option value="">Choose a syllabus subject...</option>
                {subjects.map((s: any) => (
                  <option key={s.id || s.name} value={s.name}>
                    {s.name}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div className="pt-4 border-t border-slate-800 flex items-center justify-between">
            <div className="text-xs text-slate-400">
              Exam Rules: +1 / -0.33 (1-Mark MCQ) • +2 / -0.66 (2-Mark MCQ) • No negative marking on MSQ & NAT.
            </div>
            <button
              onClick={() =>
                startTestMutation.mutate({
                  paper_code: paperCode,
                  test_mode: testMode,
                  year: selectedYear,
                  subject_name: selectedSubject || undefined,
                  duration_minutes: durationMinutes,
                })
              }
              disabled={startTestMutation.isPending || (testMode === 'subject' && !selectedSubject)}
              className="px-6 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-semibold text-sm shadow flex items-center gap-2 transition"
            >
              <Play className="w-4 h-4 fill-current" />
              {startTestMutation.isPending ? 'Generating Exam...' : 'Start CBT Examination'}
            </button>
          </div>
        </div>

        {/* Previous Completed Tests History */}
        <div className="bg-[#0B132B] border border-slate-800 rounded-xl p-5 shadow-sm space-y-3">
          <h2 className="text-sm font-bold text-white flex items-center gap-2 border-b border-slate-800 pb-2.5">
            <Award className="w-4 h-4 text-amber-400" /> Previous Test History
          </h2>

          {historyData?.history && historyData.history.length > 0 ? (
            <div className="divide-y divide-slate-800/80 text-xs">
              {historyData.history.map((t: any) => (
                <div key={t.id} className="py-3 flex items-center justify-between">
                  <div>
                    <h3 className="font-semibold text-slate-200">{t.title}</h3>
                    <div className="text-slate-400 text-[11px] mt-0.5">
                      Completed: {new Date(t.created_at).toLocaleString()} • Duration:{' '}
                      {Math.round(t.time_taken_seconds / 60)} mins
                    </div>
                  </div>
                  <div className="text-right">
                    <span className="font-bold text-emerald-400 text-sm">
                      {t.marks_obtained} / {t.total_marks} Marks
                    </span>
                    <div className="text-[11px] text-indigo-300">
                      {t.accuracy_percent}% accuracy ({t.correct_count} correct)
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-slate-400 py-3">No completed test attempts recorded yet.</p>
          )}
        </div>
      </div>
    );
  }

  // =========================================================================
  // VIEW 2: COMPREHENSIVE POST-TEST SCORECARD & QUESTION REVIEW
  // =========================================================================
  if (scorecardResult) {
    const res = scorecardResult;
    return (
      <div className="p-6 max-w-6xl mx-auto space-y-6">
        {/* Scorecard Header */}
        <div className="bg-[#0B132B] border border-emerald-500/40 rounded-xl p-6 shadow-lg space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-4">
            <div>
              <span className="text-xs px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 font-semibold border border-emerald-500/30">
                Official GATE CBT Evaluation
              </span>
              <h1 className="text-2xl font-bold text-white mt-1">{res.test_title}</h1>
            </div>
            <button
              onClick={() => {
                setScorecardResult(null);
                setActiveTest(null);
              }}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold"
            >
              Back to CBT Mock Home
            </button>
          </div>

          {/* Marks summary grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center">
            <div className="bg-[#1C2541]/50 p-3 rounded-lg border border-slate-800">
              <span className="text-[11px] text-slate-400 uppercase font-semibold">Marks Obtained</span>
              <div className="text-2xl sm:text-3xl font-extrabold text-emerald-400 mt-1">
                {res.marks_obtained}
              </div>
              <span className="text-[11px] text-slate-400">out of {res.total_marks}</span>
            </div>

            <div className="bg-[#1C2541]/50 p-3 rounded-lg border border-slate-800">
              <span className="text-[11px] text-slate-400 uppercase font-semibold">Overall Accuracy</span>
              <div className="text-2xl sm:text-3xl font-extrabold text-indigo-300 mt-1">
                {res.accuracy_percent}%
              </div>
              <span className="text-[11px] text-slate-400">on attempted questions</span>
            </div>

            <div className="bg-[#1C2541]/50 p-3 rounded-lg border border-slate-800">
              <span className="text-[11px] text-slate-400 uppercase font-semibold">Correct / Incorrect</span>
              <div className="text-xl sm:text-2xl font-extrabold text-white mt-1">
                <span className="text-emerald-400">{res.correct_count}</span> /{' '}
                <span className="text-rose-400">{res.incorrect_count}</span>
              </div>
              <span className="text-[11px] text-slate-400">{res.attempted_count} attempted</span>
            </div>

            <div className="bg-[#1C2541]/50 p-3 rounded-lg border border-slate-800">
              <span className="text-[11px] text-slate-400 uppercase font-semibold">Unattempted</span>
              <div className="text-2xl sm:text-3xl font-extrabold text-slate-400 mt-1">
                {res.unattempted_count}
              </div>
              <span className="text-[11px] text-slate-400">0 penalty</span>
            </div>
          </div>

          {/* Sectional scores */}
          {res.section_breakdown && (
            <div className="bg-[#070D1E] p-3 rounded-lg border border-slate-800 text-xs flex flex-wrap items-center justify-around gap-4">
              {Object.entries(res.section_breakdown).map(([sec, val]: [string, any]) => (
                <div key={sec} className="text-center">
                  <span className="text-slate-400 uppercase font-semibold">{sec}</span>
                  <div className="text-sm font-bold text-white mt-0.5">
                    {Number(val.marks_obtained).toFixed(2)} / {val.total_marks} Marks
                  </div>
                  <span className="text-[10px] text-indigo-400">
                    {val.correct}/{val.attempted} correct
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Detailed Question Review List */}
        <div className="bg-[#0B132B] border border-slate-800 rounded-xl p-5 shadow-sm space-y-4">
          <h2 className="text-base font-bold text-white flex items-center gap-2 border-b border-slate-800 pb-3">
            <BookOpen className="w-4 h-4 text-indigo-400" /> Question-by-Question Solution Review ({res.question_reviews?.length} Questions)
          </h2>

          <div className="space-y-4 divide-y divide-slate-800/80">
            {res.question_reviews?.map((q: any) => (
              <div key={q.question_id} className="pt-4 first:pt-0 space-y-2.5">
                <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-indigo-300">Q.{q.question_number}</span>
                    <span className="px-2 py-0.5 rounded bg-[#1C2541] text-slate-300">
                      {q.question_type} • {q.marks} Mark(s)
                    </span>
                    <span className="text-slate-400">{q.subject_name}</span>
                  </div>

                  <div>
                    {q.is_correct === true ? (
                      <span className="inline-flex items-center gap-1 font-semibold text-emerald-400 bg-emerald-500/10 px-2.5 py-0.5 rounded-full">
                        <CheckCircle2 className="w-3.5 h-3.5" /> Correct (+{q.marks_awarded})
                      </span>
                    ) : q.is_correct === false ? (
                      <span className="inline-flex items-center gap-1 font-semibold text-rose-400 bg-rose-500/10 px-2.5 py-0.5 rounded-full">
                        <XCircle className="w-3.5 h-3.5" /> Incorrect ({q.marks_awarded})
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-slate-400 bg-slate-800 px-2.5 py-0.5 rounded-full">
                        Unattempted (0.0)
                      </span>
                    )}
                  </div>
                </div>

                <div className="text-xs sm:text-sm text-slate-100 leading-relaxed">
                  <MarkdownRenderer content={q.question_text || ''} />
                </div>

                <div className="bg-[#1C2541]/40 p-3 rounded-lg border border-slate-800 text-xs space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">
                      Your Response:{' '}
                      <strong className="text-white">
                        {q.user_selected_options?.length > 0
                          ? `(${q.user_selected_options.join(', ')})`
                          : q.user_numerical_answer !== null && q.user_numerical_answer !== undefined
                          ? q.user_numerical_answer
                          : 'None (Unattempted)'}
                      </strong>
                    </span>
                    <span className="text-slate-400">
                      Official GATE Key:{' '}
                      <strong className="text-emerald-400">
                        {q.official_correct_options?.length > 0
                          ? `(${q.official_correct_options.join(', ')})`
                          : q.official_numerical_range
                          ? `[${q.official_numerical_range.join(', ')}]`
                          : 'Unverified'}
                      </strong>
                    </span>
                  </div>

                  {q.explanation && (
                    <div className="mt-2 pt-2 border-t border-slate-700/60 text-slate-200">
                      <span className="font-semibold text-indigo-300 block mb-1">Official Solution:</span>
                      <MarkdownRenderer content={q.explanation} />
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  // =========================================================================
  // VIEW 3: LIVE GATE CBT TEST ENVIRONMENT (Authentic Examination UI)
  // =========================================================================
  const qType = (currentQ?.question_type || 'MCQ').toUpperCase();
  const isTimeCritical = timeRemainingSeconds < 15 * 60; // < 15 minutes left

  return (
    <div className="h-screen flex flex-col bg-[#060B19] select-none text-slate-100 overflow-hidden">
      {/* Top Header Bar */}
      <header className="bg-[#0B132B] border-b border-slate-800 px-5 py-3 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-indigo-600/20 border border-indigo-500/40 flex items-center justify-center text-indigo-400 font-bold text-xs">
            {paperCode}
          </div>
          <div>
            <h1 className="text-sm font-bold text-white">{activeTest.title}</h1>
            <span className="text-[11px] text-slate-400">
              Section: <strong className="text-indigo-300">{currentQ?.section || 'Core'}</strong>
            </span>
          </div>
        </div>

        {/* Persistent 180-Minute Countdown Clock */}
        <div className="flex items-center gap-4">
          <div
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg border font-mono text-sm font-bold transition-colors ${
              isTimeCritical
                ? 'bg-rose-500/20 text-rose-300 border-rose-500/50 animate-pulse'
                : 'bg-[#1C2541] text-emerald-400 border-slate-700'
            }`}
          >
            <Clock className="w-4 h-4" />
            <span>Time Left: {formatTimer(timeRemainingSeconds)}</span>
          </div>

          <button
            onClick={() => setShowSubmitModal(true)}
            className="px-4 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs shadow flex items-center gap-1.5 transition"
          >
            <Send className="w-3.5 h-3.5" /> Submit Exam
          </button>
        </div>
      </header>

      {/* Main Content Area: Left Question Area + Right Question Palette */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left: Question Stem & Input (70-75% width) */}
        <div className="flex-1 flex flex-col justify-between overflow-y-auto p-6 border-r border-slate-800/80">
          <div className="space-y-4 max-w-4xl">
            {/* Question Info Bar */}
            <div className="flex items-center justify-between border-b border-slate-800 pb-2 text-xs">
              <span className="font-bold text-indigo-300 text-sm">
                Question No. {currentIndex + 1}
              </span>
              <div className="flex items-center gap-2">
                <span className="px-2 py-0.5 rounded bg-[#1C2541] text-slate-300 font-medium">
                  {qType}
                </span>
                <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                  +{currentQ?.marks} Marks | -{Number(currentQ?.negative_marks || (currentQ?.marks / 3)).toFixed(2)} Negative
                </span>
              </div>
            </div>

            {/* Question Stem (KaTeX fidelity) */}
            <div className="text-sm text-slate-100 leading-relaxed pt-1">
              <MarkdownRenderer content={currentQ?.question_text || ''} />
            </div>

            {/* Stem Visual Assets */}
            {currentQ?.visual_assets &&
              currentQ.visual_assets
                .filter((a: any) => a.asset_role === 'stem')
                .map((a: any) => (
                  <div key={a.id} className="my-3 flex justify-center">
                    <img
                      src={gateApi.getAssetImageUrl(a.id)}
                      alt="Question diagram"
                      className="max-h-80 rounded-lg border border-slate-700 bg-white p-2 shadow object-contain"
                    />
                  </div>
                ))}

            {/* Answer Options / NAT Input */}
            <div className="pt-3">
              {qType === 'NAT' ? (
                <div className="max-w-xs space-y-2">
                  <label className="block text-xs font-semibold text-slate-300">
                    Numerical Response:
                  </label>
                  <input
                    type="number"
                    step="any"
                    placeholder="Enter answer"
                    value={currentResp.numerical_answer !== undefined ? currentResp.numerical_answer : ''}
                    onChange={(e) => handleNatInput(e.target.value)}
                    className="w-full bg-[#1C2541] border border-slate-700 rounded-lg px-3 py-2 text-sm text-white font-mono focus:outline-none focus:border-indigo-500"
                  />
                </div>
              ) : (
                <div className="space-y-2.5">
                  {currentQ?.options?.map((opt: any) => {
                    const isSelected = (currentResp.selected_options || []).includes(opt.option_label);
                    return (
                      <button
                        key={opt.option_label}
                        type="button"
                        onClick={() => handleSelectOption(opt.option_label)}
                        className={`w-full p-3 rounded-xl border text-left flex items-start gap-3 transition-colors ${
                          isSelected
                            ? 'bg-indigo-600/20 border-indigo-500 text-white font-medium'
                            : 'bg-[#1C2541]/40 border-slate-800 hover:bg-[#1C2541]/80 text-slate-200'
                        }`}
                      >
                        <span className="font-bold text-indigo-400 shrink-0 text-sm">
                          ({opt.option_label})
                        </span>
                        <div className="text-xs sm:text-sm text-slate-200 leading-normal flex-1">
                          <MarkdownRenderer content={opt.option_text || ''} />
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          {/* Bottom Candidate Control Buttons */}
          <div className="pt-4 mt-6 border-t border-slate-800 flex flex-wrap items-center justify-between gap-3 bg-[#060B19]">
            <div className="flex items-center gap-2">
              <button
                onClick={handleSaveAndNext}
                className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs shadow flex items-center gap-1.5 transition"
              >
                <Save className="w-3.5 h-3.5" /> Save & Next
              </button>
              <button
                onClick={handleMarkForReviewAndNext}
                className="px-3.5 py-2 rounded-lg bg-purple-700 hover:bg-purple-600 text-white font-semibold text-xs shadow flex items-center gap-1.5 transition"
              >
                <Flag className="w-3.5 h-3.5" /> Mark for Review & Next
              </button>
              <button
                onClick={handleClearResponse}
                className="px-3 py-2 rounded-lg bg-[#1C2541] hover:bg-slate-700 text-slate-300 font-medium text-xs flex items-center gap-1 transition"
              >
                <RotateCcw className="w-3.5 h-3.5" /> Clear Response
              </button>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={handlePrevious}
                disabled={currentIndex === 0}
                className="px-3.5 py-2 rounded-lg bg-[#0B132B] border border-slate-800 disabled:opacity-30 hover:bg-[#1C2541] text-slate-300 text-xs font-semibold flex items-center gap-1"
              >
                <ChevronLeft className="w-4 h-4" /> Previous
              </button>
              <button
                onClick={handleNext}
                disabled={currentIndex === questions.length - 1}
                className="px-3.5 py-2 rounded-lg bg-[#0B132B] border border-slate-800 disabled:opacity-30 hover:bg-[#1C2541] text-slate-300 text-xs font-semibold flex items-center gap-1"
              >
                Next <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>

        {/* Right: Question Palette & Legend (25-30% width) */}
        <div className="w-80 bg-[#0B132B] border-l border-slate-800 flex flex-col justify-between shrink-0 select-none">
          <div className="p-4 space-y-4 overflow-y-auto">
            {/* Candidate Info */}
            <div className="p-3 rounded-lg bg-[#1C2541]/50 border border-slate-800 text-xs space-y-1">
              <div className="font-semibold text-white">GATE Aspirant</div>
              <div className="text-slate-400 text-[11px]">Discipline: GATE {paperCode}</div>
            </div>

            {/* Official 5-State Color Legend */}
            <div className="space-y-1.5 text-[11px] text-slate-300 border-b border-slate-800 pb-3">
              <div className="grid grid-cols-2 gap-2">
                <div className="flex items-center gap-2">
                  <span className="w-5 h-5 rounded bg-slate-700 text-white font-bold text-[10px] flex items-center justify-center">
                    {countNotVisited}
                  </span>
                  <span>Not Visited</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-5 h-5 rounded bg-rose-600 text-white font-bold text-[10px] flex items-center justify-center">
                    {countNotAnswered}
                  </span>
                  <span>Not Answered</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-5 h-5 rounded bg-emerald-600 text-white font-bold text-[10px] flex items-center justify-center">
                    {countAnswered}
                  </span>
                  <span>Answered</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-5 h-5 rounded bg-purple-600 text-white font-bold text-[10px] flex items-center justify-center">
                    {countMarked}
                  </span>
                  <span>Marked for Review</span>
                </div>
              </div>
              <div className="flex items-center gap-2 pt-1">
                <span className="relative w-5 h-5 rounded bg-purple-600 text-white font-bold text-[10px] flex items-center justify-center">
                  <span className="absolute bottom-0 right-0 w-2 h-2 rounded-full bg-emerald-400 border border-purple-800" />
                  {countAnsweredAndMarked}
                </span>
                <span>Answered & Marked (Evaluated)</span>
              </div>
            </div>

            {/* Question Palette Number Grid */}
            <div>
              <span className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2.5">
                Question Palette ({questions.length})
              </span>
              <div className="grid grid-cols-5 gap-2">
                {questions.map((q: any, idx: number) => {
                  const state = getQuestionPaletteState(q);
                  const isCurrent = idx === currentIndex;

                  let bgClass = 'bg-slate-700 hover:bg-slate-600 text-white'; // NOT_VISITED
                  if (state === 'NOT_ANSWERED') {
                    bgClass = 'bg-rose-600 hover:bg-rose-500 text-white';
                  } else if (state === 'ANSWERED') {
                    bgClass = 'bg-emerald-600 hover:bg-emerald-500 text-white';
                  } else if (state === 'MARKED_FOR_REVIEW') {
                    bgClass = 'bg-purple-600 hover:bg-purple-500 text-white';
                  } else if (state === 'ANSWERED_AND_MARKED') {
                    bgClass = 'bg-purple-600 hover:bg-purple-500 text-white';
                  }

                  return (
                    <button
                      key={q.question_id}
                      onClick={() => handleJumpToQuestion(idx)}
                      className={`relative h-9 rounded-lg font-bold text-xs flex items-center justify-center transition-all ${bgClass} ${
                        isCurrent ? 'ring-2 ring-indigo-400 ring-offset-2 ring-offset-[#0B132B]' : ''
                      }`}
                    >
                      {idx + 1}
                      {state === 'ANSWERED_AND_MARKED' && (
                        <span className="absolute bottom-1 right-1 w-2 h-2 rounded-full bg-emerald-400 border border-purple-800" />
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Submit Test Button */}
          <div className="p-4 border-t border-slate-800 bg-[#10182E]">
            <button
              onClick={() => setShowSubmitModal(true)}
              className="w-full py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs shadow transition text-center"
            >
              Submit Examination
            </button>
          </div>
        </div>
      </div>

      {/* Submit Confirmation Modal Dialog */}
      {showSubmitModal && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center p-4 z-50 animate-fadeIn">
          <div className="bg-[#0B132B] border border-slate-700 rounded-xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <Send className="w-4 h-4 text-indigo-400" /> Confirm Exam Submission
            </h3>
            <p className="text-xs text-slate-300">
              Are you sure you want to submit your examination? Once submitted, your answers will be evaluated authoritatively by the backend engine.
            </p>

            {/* Summary counts */}
            <div className="grid grid-cols-2 gap-2 bg-[#1C2541]/60 p-3 rounded-lg border border-slate-800 text-xs">
              <div className="text-slate-300">
                Answered: <strong className="text-emerald-400">{countAnswered + countAnsweredAndMarked}</strong>
              </div>
              <div className="text-slate-300">
                Marked for Review: <strong className="text-purple-400">{countMarked + countAnsweredAndMarked}</strong>
              </div>
              <div className="text-slate-300">
                Not Answered: <strong className="text-rose-400">{countNotAnswered}</strong>
              </div>
              <div className="text-slate-300">
                Not Visited: <strong className="text-slate-400">{countNotVisited}</strong>
              </div>
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <button
                onClick={() => setShowSubmitModal(false)}
                className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs text-slate-300 font-medium"
              >
                Resume Exam
              </button>
              <button
                onClick={handleUserSubmit}
                disabled={submitTestMutation.isPending}
                className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-xs text-white font-semibold flex items-center gap-1.5"
              >
                {submitTestMutation.isPending ? 'Submitting & Evaluating...' : 'Yes, Submit Test'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
