import React, { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import {
  Bot,
  BarChart3,
  TrendingUp,
  UserCheck,
  HelpCircle,
  FileText,
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  BookOpen,
  ArrowRight,
  Search,
} from 'lucide-react';
import { gateApi } from '../services/api';
import { MarkdownRenderer } from '../components/MarkdownRenderer';

export const Agents: React.FC<{ paperCode: string }> = ({ paperCode }) => {
  const [activeTab, setActiveTab] = useState<'pyq' | 'perf' | 'assistant' | 'paper'>('pyq');

  // Agent 1: PYQ Analysis state
  const [pyqSubjectFilter, setPyqSubjectFilter] = useState<string>('');

  // Agent 3: Question Assistant state
  const [selectedQuestionId, setSelectedQuestionId] = useState<string>('');
  const [questionSearchQuery, setQuestionSearchQuery] = useState<string>('');

  // Agent 4: Paper Analysis state
  const [paperYear, setPaperYear] = useState<number>(2012);

  // Queries for the 4 agents
  const { data: pyqResult, isLoading: isPyqLoading } = useQuery({
    queryKey: ['agent_pyq', paperCode, pyqSubjectFilter],
    queryFn: () => gateApi.runPyqAnalysis({ paper_code: paperCode, subject_name: pyqSubjectFilter || undefined }),
    enabled: activeTab === 'pyq',
  });

  const { data: perfResult, isLoading: isPerfLoading } = useQuery({
    queryKey: ['agent_performance', paperCode],
    queryFn: () => gateApi.runPerformanceAnalysis({ paper_code: paperCode }),
    enabled: activeTab === 'perf',
  });

  const { data: paperResult, isLoading: isPaperLoading } = useQuery({
    queryKey: ['agent_paper', paperCode, paperYear],
    queryFn: () => gateApi.runPaperAnalysis({ year: paperYear, paper_code: paperCode }),
    enabled: activeTab === 'paper',
  });

  // Questions query for Question Assistant selector
  const { data: qListData } = useQuery({
    queryKey: ['assistant_questions_list', paperCode, questionSearchQuery],
    queryFn: () =>
      gateApi.listQuestions({
        paper_code: paperCode,
        q: questionSearchQuery || undefined,
        page: 1,
        page_size: 25,
      }),
    enabled: activeTab === 'assistant',
  });

  // Assistant query when question is selected
  const { data: assistantResult, isLoading: isAssistantLoading } = useQuery({
    queryKey: ['agent_assistant', selectedQuestionId],
    queryFn: () =>
      selectedQuestionId ? gateApi.runQuestionAssistant({ question_id: selectedQuestionId }) : null,
    enabled: activeTab === 'assistant' && !!selectedQuestionId,
  });

  // Auto-select first question if available and none selected
  React.useEffect(() => {
    if (activeTab === 'assistant' && !selectedQuestionId && qListData?.items?.length > 0) {
      setSelectedQuestionId(qListData.items[0].id);
    }
  }, [activeTab, qListData, selectedQuestionId]);

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="border-b border-slate-800 pb-5">
        <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2.5">
          <Bot className="w-7 h-7 text-indigo-400" />
          <span>Practical Lightweight Agents</span>
          <span className="text-xs px-2.5 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 font-semibold border border-indigo-500/30">
            100% Offline • Local Python Logic
          </span>
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          Four deterministic, zero-latency local analysis agents running on SQLite data with no external AI API dependencies.
        </p>
      </div>

      {/* Agent Selector Tabs */}
      <div className="flex flex-wrap items-center gap-2.5 bg-[#0B132B] p-1.5 rounded-xl border border-slate-800">
        <button
          onClick={() => setActiveTab('pyq')}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-xs font-semibold transition ${
            activeTab === 'pyq'
              ? 'bg-indigo-600 text-white shadow'
              : 'text-slate-300 hover:bg-[#1C2541] hover:text-white'
          }`}
        >
          <BarChart3 className="w-4 h-4" /> Agent 1: PYQ Analysis
        </button>

        <button
          onClick={() => setActiveTab('perf')}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-xs font-semibold transition ${
            activeTab === 'perf'
              ? 'bg-indigo-600 text-white shadow'
              : 'text-slate-300 hover:bg-[#1C2541] hover:text-white'
          }`}
        >
          <UserCheck className="w-4 h-4" /> Agent 2: Performance & Recommendations
        </button>

        <button
          onClick={() => setActiveTab('assistant')}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-xs font-semibold transition ${
            activeTab === 'assistant'
              ? 'bg-indigo-600 text-white shadow'
              : 'text-slate-300 hover:bg-[#1C2541] hover:text-white'
          }`}
        >
          <HelpCircle className="w-4 h-4" /> Agent 3: Question Assistant
        </button>

        <button
          onClick={() => setActiveTab('paper')}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-xs font-semibold transition ${
            activeTab === 'paper'
              ? 'bg-indigo-600 text-white shadow'
              : 'text-slate-300 hover:bg-[#1C2541] hover:text-white'
          }`}
        >
          <FileText className="w-4 h-4" /> Agent 4: Paper Structural Analysis
        </button>
      </div>

      {/* =====================================================================
          TAB 1: PYQ ANALYSIS AGENT
         ===================================================================== */}
      {activeTab === 'pyq' && (
        <div className="space-y-5">
          <div className="bg-[#0B132B] border border-slate-800 rounded-xl p-5 shadow-sm space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-3">
              <div>
                <h2 className="text-base font-bold text-white flex items-center gap-2">
                  <BarChart3 className="w-4 h-4 text-indigo-400" /> Historical PYQ Frequency & Topic Recurrence
                </h2>
                <p className="text-xs text-slate-400 mt-0.5">
                  Analyzes {pyqResult?.total_questions_analyzed || 0} questions in active database
                </p>
              </div>

              {/* Filter */}
              <select
                value={pyqSubjectFilter}
                onChange={(e) => setPyqSubjectFilter(e.target.value)}
                className="bg-[#1C2541] border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
              >
                <option value="">All Subjects</option>
                {pyqResult?.subject_distribution?.map((s: any) => (
                  <option key={s.subject_name} value={s.subject_name}>
                    {s.subject_name}
                  </option>
                ))}
              </select>
            </div>

            {/* Insights Banner */}
            {pyqResult?.insights && (
              <div className="bg-indigo-950/40 border border-indigo-500/30 rounded-xl p-4 space-y-1.5">
                <span className="text-xs font-bold text-indigo-300 flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5" /> Agent Insights
                </span>
                <ul className="text-xs text-slate-200 list-disc list-inside space-y-1">
                  {pyqResult.insights.map((ins: string, idx: number) => (
                    <li key={idx}>{ins}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Top Recurring Topics Table */}
            <div>
              <h3 className="text-sm font-semibold text-white mb-2.5">
                Top Recurring Syllabus Topics
              </h3>
              <div className="bg-[#070D1E] border border-slate-800 rounded-xl overflow-hidden">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="bg-[#1C2541]/70 border-b border-slate-800 text-slate-400 uppercase">
                      <th className="py-2.5 px-4">Topic Name</th>
                      <th className="py-2.5 px-4">Subject</th>
                      <th className="py-2.5 px-4">Questions</th>
                      <th className="py-2.5 px-4">Total Marks</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {pyqResult?.top_recurring_topics?.map((t: any, idx: number) => (
                      <tr key={idx} className="hover:bg-[#1C2541]/30">
                        <td className="py-2.5 px-4 font-semibold text-slate-100">{t.topic_name}</td>
                        <td className="py-2.5 px-4 text-slate-400">{t.subject_name}</td>
                        <td className="py-2.5 px-4 font-bold text-indigo-400">{t.count}</td>
                        <td className="py-2.5 px-4 text-slate-300">{t.total_marks} Marks</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* =====================================================================
          TAB 2: PERFORMANCE AGENT
         ===================================================================== */}
      {activeTab === 'perf' && (
        <div className="space-y-5">
          <div className="bg-[#0B132B] border border-slate-800 rounded-xl p-5 shadow-sm space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <h2 className="text-base font-bold text-white flex items-center gap-2">
                  <UserCheck className="w-4 h-4 text-emerald-400" /> Candidate Performance Evaluation & Targeted Guidance
                </h2>
                <p className="text-xs text-slate-400 mt-0.5">
                  Calculated from actual recorded practice questions and CBT mock test scores
                </p>
              </div>
              <span className="text-xs px-2.5 py-1 rounded bg-[#1C2541] text-slate-300 font-semibold">
                {perfResult?.total_attempts || 0} Attempts Evaluated
              </span>
            </div>

            {/* Performance Stats Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
              <div className="bg-[#1C2541]/40 p-3 rounded-lg border border-slate-800 text-center">
                <span className="text-[11px] text-slate-400 uppercase font-semibold">Overall Accuracy</span>
                <div className="text-2xl font-bold text-indigo-300 mt-1">
                  {perfResult?.accuracy_percentage ?? 0}%
                </div>
              </div>
              <div className="bg-[#1C2541]/40 p-3 rounded-lg border border-slate-800 text-center">
                <span className="text-[11px] text-slate-400 uppercase font-semibold">Correct Answers</span>
                <div className="text-2xl font-bold text-emerald-400 mt-1">
                  {perfResult?.correct_count ?? 0}
                </div>
              </div>
              <div className="bg-[#1C2541]/40 p-3 rounded-lg border border-slate-800 text-center">
                <span className="text-[11px] text-slate-400 uppercase font-semibold">Incorrect Answers</span>
                <div className="text-2xl font-bold text-rose-400 mt-1">
                  {perfResult?.incorrect_count ?? 0}
                </div>
              </div>
              <div className="bg-[#1C2541]/40 p-3 rounded-lg border border-slate-800 text-center">
                <span className="text-[11px] text-slate-400 uppercase font-semibold">Weak Subjects</span>
                <div className="text-2xl font-bold text-amber-400 mt-1">
                  {perfResult?.weak_subjects?.length ?? 0}
                </div>
              </div>
            </div>

            {/* Actionable Recommendations */}
            <div className="bg-[#070D1E] border border-slate-800 rounded-xl p-4 space-y-2">
              <h3 className="text-xs font-bold text-amber-300 flex items-center gap-1.5 uppercase tracking-wider">
                <Sparkles className="w-3.5 h-3.5" /> Prioritized Revision Recommendations
              </h3>
              <ul className="text-xs text-slate-200 space-y-1.5 list-disc list-inside">
                {perfResult?.recommendations?.map((rec: string, idx: number) => (
                  <li key={idx} className="leading-relaxed">
                    {rec}
                  </li>
                ))}
              </ul>
            </div>

            {/* Subject Performance Breakdown */}
            {perfResult?.subject_performance && perfResult.subject_performance.length > 0 && (
              <div>
                <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-2">
                  Subject-by-Subject Accuracy Breakdown
                </h3>
                <div className="bg-[#070D1E] border border-slate-800 rounded-xl overflow-hidden">
                  <table className="w-full text-left text-xs border-collapse">
                    <thead>
                      <tr className="bg-[#1C2541]/70 border-b border-slate-800 text-slate-400 uppercase">
                        <th className="py-2.5 px-4">Subject</th>
                        <th className="py-2.5 px-4">Attempted</th>
                        <th className="py-2.5 px-4">Correct</th>
                        <th className="py-2.5 px-4">Accuracy</th>
                        <th className="py-2.5 px-4">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60">
                      {perfResult.subject_performance.map((s: any) => (
                        <tr key={s.subject_name} className="hover:bg-[#1C2541]/30">
                          <td className="py-2.5 px-4 font-semibold text-slate-100">{s.subject_name}</td>
                          <td className="py-2.5 px-4 text-slate-300">{s.attempted}</td>
                          <td className="py-2.5 px-4 text-slate-300">{s.correct}</td>
                          <td className="py-2.5 px-4 font-bold text-white">{s.accuracy_percent}%</td>
                          <td className="py-2.5 px-4">
                            {s.accuracy_percent < 50 ? (
                              <span className="text-[10px] font-semibold text-rose-400 bg-rose-500/10 border border-rose-500/30 px-2 py-0.5 rounded-full">
                                Needs Revision
                              </span>
                            ) : (
                              <span className="text-[10px] font-semibold text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 px-2 py-0.5 rounded-full">
                                Proficient
                              </span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* =====================================================================
          TAB 3: QUESTION ASSISTANT
         ===================================================================== */}
      {activeTab === 'assistant' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Question Selector List (Left) */}
          <div className="bg-[#0B132B] border border-slate-800 rounded-xl p-4 space-y-3">
            <h2 className="text-sm font-bold text-white flex items-center gap-1.5">
              <Search className="w-4 h-4 text-indigo-400" /> Select Question to Analyze
            </h2>

            <input
              type="text"
              placeholder="Search by topic or text..."
              value={questionSearchQuery}
              onChange={(e) => setQuestionSearchQuery(e.target.value)}
              className="w-full bg-[#1C2541] border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white placeholder-slate-400"
            />

            <div className="space-y-1.5 max-h-[60vh] overflow-y-auto divide-y divide-slate-800/60">
              {qListData?.items?.map((q: any) => (
                <button
                  key={q.id}
                  onClick={() => setSelectedQuestionId(q.id)}
                  className={`w-full text-left p-2.5 rounded-lg text-xs transition block ${
                    selectedQuestionId === q.id
                      ? 'bg-indigo-600/30 border border-indigo-500 text-white'
                      : 'hover:bg-[#1C2541]/60 text-slate-300'
                  }`}
                >
                  <div className="flex items-center justify-between text-[11px] font-bold text-indigo-400 mb-0.5">
                    <span>Q.{q.question_number} ({q.examination_year})</span>
                    <span>{q.marks} Mark</span>
                  </div>
                  <p className="line-clamp-2 text-slate-200 text-[11px]">
                    {q.question_text}
                  </p>
                </button>
              ))}
            </div>
          </div>

          {/* Question Breakdown & Explanation (Right 2 cols) */}
          <div className="lg:col-span-2 bg-[#0B132B] border border-slate-800 rounded-xl p-5 space-y-4">
            {isAssistantLoading ? (
              <div className="py-12 text-center text-xs text-slate-400">
                Loading structured explanation...
              </div>
            ) : !assistantResult ? (
              <div className="py-12 text-center text-xs text-slate-400">
                Select a question from the list to view its structured analysis.
              </div>
            ) : (
              <div className="space-y-4">
                {/* Header info */}
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-3 text-xs">
                  <div className="flex items-center gap-2">
                    <span className="px-2.5 py-1 rounded bg-indigo-500/20 text-indigo-300 font-bold border border-indigo-500/30">
                      GATE {assistantResult.paper_code} {assistantResult.year} • Q.{assistantResult.question_number}
                    </span>
                    <span className="px-2 py-0.5 rounded bg-[#1C2541] text-slate-300">
                      {assistantResult.question_type} • {assistantResult.marks} Mark(s)
                    </span>
                    <span className="text-slate-400">{assistantResult.subject_name}</span>
                  </div>

                  <div>
                    {assistantResult.official_answer?.is_verified ? (
                      <span className="inline-flex items-center gap-1 text-[11px] text-emerald-400 font-semibold bg-emerald-500/10 border border-emerald-500/30 px-2 py-0.5 rounded-full">
                        <CheckCircle2 className="w-3.5 h-3.5" /> Verified IIT Key
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-[11px] text-amber-400 font-medium bg-amber-500/10 border border-amber-500/30 px-2 py-0.5 rounded-full">
                        <AlertTriangle className="w-3.5 h-3.5" /> Key Unverified
                      </span>
                    )}
                  </div>
                </div>

                {/* Question Stem */}
                <div className="text-xs sm:text-sm text-slate-100 leading-relaxed">
                  <MarkdownRenderer content={assistantResult.question_text || ''} />
                </div>

                {/* Visual Assets if any */}
                {assistantResult.visual_assets &&
                  assistantResult.visual_assets
                    .filter((a: any) => a.asset_role === 'stem')
                    .map((a: any) => (
                      <div key={a.id} className="my-2 flex justify-center">
                        <img
                          src={gateApi.getAssetImageUrl(a.id)}
                          alt="Question diagram"
                          className="max-h-64 rounded border border-slate-700 bg-white p-1.5 object-contain"
                        />
                      </div>
                    ))}

                {/* Official Solution Card */}
                <div className="bg-[#070D1E] border border-slate-800 rounded-xl p-4 space-y-2.5 text-xs">
                  <h3 className="font-bold text-indigo-300 flex items-center gap-1.5 uppercase tracking-wider text-[11px]">
                    <BookOpen className="w-3.5 h-3.5" /> Official Answer Key & Derivation
                  </h3>

                  <p className="font-semibold text-emerald-400 text-sm">
                    {assistantResult.guidance}
                  </p>

                  {assistantResult.official_explanation ? (
                    <div className="pt-2 border-t border-slate-800 text-slate-200 leading-relaxed">
                      <MarkdownRenderer content={assistantResult.official_explanation} />
                    </div>
                  ) : (
                    <p className="text-slate-400 italic pt-1 border-t border-slate-800/80">
                      Step-by-step written explanation has not been transcribed yet for this item. Official key provenance: {assistantResult.official_answer?.provenance || 'unverified'}.
                    </p>
                  )}
                </div>

                {/* Concept Breakdown Badges */}
                <div className="pt-2 border-t border-slate-800/80">
                  <span className="block text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-2">
                    Key Syllabus Concepts
                  </span>
                  <div className="flex flex-wrap gap-2">
                    {assistantResult.concepts?.map((c: string, idx: number) => (
                      <span
                        key={idx}
                        className="px-2.5 py-1 rounded bg-[#1C2541] border border-slate-700 text-slate-300 text-xs"
                      >
                        {c}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* =====================================================================
          TAB 4: PAPER ANALYSIS AGENT
         ===================================================================== */}
      {activeTab === 'paper' && (
        <div className="space-y-5">
          <div className="bg-[#0B132B] border border-slate-800 rounded-xl p-5 shadow-sm space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-3">
              <div>
                <h2 className="text-base font-bold text-white flex items-center gap-2">
                  <FileText className="w-4 h-4 text-purple-400" /> Structural Paper Composition Analysis
                </h2>
                <p className="text-xs text-slate-400 mt-0.5">
                  General Aptitude vs Core balance, question types, and answer key coverage
                </p>
              </div>

              {/* Year Selector */}
              <div className="flex items-center gap-2 text-xs">
                <span className="text-slate-400">Exam Paper:</span>
                <select
                  value={paperYear}
                  onChange={(e) => setPaperYear(Number(e.target.value))}
                  className="bg-[#1C2541] border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
                >
                  <option value="2012">GATE CS 2012 (65 Questions • 100 Marks)</option>
                  <option value="2013">GATE CS 2013 (68 Questions)</option>
                </select>
              </div>
            </div>

            {/* Paper Overview Stats */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center">
              <div className="bg-[#1C2541]/40 p-3 rounded-lg border border-slate-800">
                <span className="text-[11px] text-slate-400 uppercase font-semibold">Total Questions</span>
                <div className="text-2xl font-bold text-white mt-1">
                  {paperResult?.total_questions || 0}
                </div>
                <span className="text-[11px] text-slate-400">{paperResult?.total_marks || 0} Marks</span>
              </div>

              <div className="bg-[#1C2541]/40 p-3 rounded-lg border border-slate-800">
                <span className="text-[11px] text-slate-400 uppercase font-semibold">General Aptitude</span>
                <div className="text-2xl font-bold text-indigo-300 mt-1">
                  {paperResult?.general_aptitude?.marks || 0} Marks
                </div>
                <span className="text-[11px] text-slate-400">{paperResult?.general_aptitude?.question_count || 0} Qs</span>
              </div>

              <div className="bg-[#1C2541]/40 p-3 rounded-lg border border-slate-800">
                <span className="text-[11px] text-slate-400 uppercase font-semibold">Core Discipline</span>
                <div className="text-2xl font-bold text-emerald-400 mt-1">
                  {paperResult?.core_subject?.marks || 0} Marks
                </div>
                <span className="text-[11px] text-slate-400">{paperResult?.core_subject?.question_count || 0} Qs</span>
              </div>

              <div className="bg-[#1C2541]/40 p-3 rounded-lg border border-slate-800">
                <span className="text-[11px] text-slate-400 uppercase font-semibold">Key Coverage</span>
                <div className="text-2xl font-bold text-amber-400 mt-1">
                  {paperResult?.answer_key_coverage_percent || 0}%
                </div>
                <span className="text-[11px] text-slate-400">{paperResult?.verified_answer_keys || 0} verified</span>
              </div>
            </div>

            {/* Agent Summary Notes */}
            {paperResult?.summary && (
              <div className="bg-[#070D1E] border border-slate-800 rounded-xl p-4 space-y-1.5">
                <span className="text-xs font-bold text-purple-300 uppercase tracking-wider block">
                  Structural Balance Summary
                </span>
                <ul className="text-xs text-slate-200 list-disc list-inside space-y-1">
                  {paperResult.summary.map((s: string, idx: number) => (
                    <li key={idx}>{s}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Subject Distribution inside this Paper */}
            {paperResult?.subject_breakdown && (
              <div>
                <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-2">
                  Subject Breakdown for {paperResult.paper_title}
                </h3>
                <div className="bg-[#070D1E] border border-slate-800 rounded-xl overflow-hidden">
                  <table className="w-full text-left text-xs border-collapse">
                    <thead>
                      <tr className="bg-[#1C2541]/70 border-b border-slate-800 text-slate-400 uppercase">
                        <th className="py-2.5 px-4">Subject</th>
                        <th className="py-2.5 px-4">Questions</th>
                        <th className="py-2.5 px-4">Total Marks</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60">
                      {paperResult.subject_breakdown.map((s: any) => (
                        <tr key={s.subject_name} className="hover:bg-[#1C2541]/30">
                          <td className="py-2 px-4 font-semibold text-slate-100">{s.subject_name}</td>
                          <td className="py-2 px-4 font-bold text-indigo-400">{s.count}</td>
                          <td className="py-2 px-4 text-slate-300">{s.marks} Marks</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
