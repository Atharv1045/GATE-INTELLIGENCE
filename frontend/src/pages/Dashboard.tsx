import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  Database,
  CheckCircle2,
  XCircle,
  Target,
  Trophy,
  BarChart3,
  BookOpen,
  ArrowRight,
  TrendingUp,
  FileText,
  Clock,
  Sparkles,
} from 'lucide-react';
import { gateApi } from '../services/api';

export const Dashboard: React.FC<{ paperCode: string }> = ({ paperCode }) => {
  // Query real metrics from backend
  const { data: metrics, isLoading: isMetricsLoading } = useQuery({
    queryKey: ['dashboard_metrics', paperCode],
    queryFn: () => gateApi.getDashboardMetrics(paperCode),
  });

  // Query subject-wise progress
  const { data: progressData } = useQuery({
    queryKey: ['dashboard_progress', paperCode],
    queryFn: () => gateApi.getDashboardProgress(paperCode),
  });

  // Query recent practice activity
  const { data: recentData } = useQuery({
    queryKey: ['dashboard_recent', paperCode],
    queryFn: () => gateApi.getDashboardRecent(paperCode, 6),
  });

  const subjects = progressData?.subjects || [];
  const activities = recentData?.activity || [];
  const latestTest = metrics?.latest_test;

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Header Banner */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2.5">
            <span>Student Preparation Dashboard</span>
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 font-semibold border border-indigo-500/30">
              GATE {paperCode}
            </span>
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Real-time preparation metrics, syllabus coverage, and recent CBT mock test results.
          </p>
        </div>

        {/* Quick Launch Buttons */}
        <div className="flex flex-wrap items-center gap-2.5">
          <Link
            to="/questions"
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow transition-colors"
          >
            <Database className="w-4 h-4" /> Practice Questions
          </Link>
          <Link
            to="/tests"
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-[#1C2541] hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700 transition-colors"
          >
            <Target className="w-4 h-4" /> Take Mock Test
          </Link>
        </div>
      </div>

      {/* KPI Stats Row */}
      <div className="grid grid-cols-2 sm:grid-cols-2 lg:grid-cols-5 gap-3.5">
        {/* Total Questions Available */}
        <div className="bg-[#0B132B] border border-slate-800 rounded-xl p-4 shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase tracking-wider">
            <span>Questions in Bank</span>
            <Database className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="my-2">
            <span className="text-2xl sm:text-3xl font-extrabold text-white">
              {metrics?.total_questions ?? 0}
            </span>
          </div>
          <span className="text-[11px] text-slate-400">Available across papers</span>
        </div>

        {/* Questions Attempted */}
        <div className="bg-[#0B132B] border border-slate-800 rounded-xl p-4 shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase tracking-wider">
            <span>Total Solved</span>
            <TrendingUp className="w-4 h-4 text-sky-400" />
          </div>
          <div className="my-2">
            <span className="text-2xl sm:text-3xl font-extrabold text-white">
              {metrics?.total_attempted ?? 0}
            </span>
          </div>
          <span className="text-[11px] text-slate-400">Recorded student attempts</span>
        </div>

        {/* Correct Answers */}
        <div className="bg-[#0B132B] border border-slate-800 rounded-xl p-4 shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase tracking-wider">
            <span>Correct Answers</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="my-2">
            <span className="text-2xl sm:text-3xl font-extrabold text-emerald-400">
              {metrics?.correct_answers ?? 0}
            </span>
          </div>
          <span className="text-[11px] text-slate-400">
            {metrics?.incorrect_answers ?? 0} incorrect
          </span>
        </div>

        {/* Accuracy % */}
        <div className="bg-[#0B132B] border border-slate-800 rounded-xl p-4 shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase tracking-wider">
            <span>Accuracy Rate</span>
            <Target className="w-4 h-4 text-amber-400" />
          </div>
          <div className="my-2">
            <span className="text-2xl sm:text-3xl font-extrabold text-amber-400">
              {metrics?.accuracy_percent ?? 0}%
            </span>
          </div>
          <span className="text-[11px] text-slate-400">On attempted questions</span>
        </div>

        {/* Tests Completed */}
        <div className="bg-[#0B132B] border border-slate-800 rounded-xl p-4 shadow-sm flex flex-col justify-between col-span-2 lg:col-span-1">
          <div className="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase tracking-wider">
            <span>Tests Completed</span>
            <Trophy className="w-4 h-4 text-purple-400" />
          </div>
          <div className="my-2">
            <span className="text-2xl sm:text-3xl font-extrabold text-purple-400">
              {metrics?.tests_completed ?? 0}
            </span>
          </div>
          <span className="text-[11px] text-slate-400">Official CBT exams evaluated</span>
        </div>
      </div>

      {/* Main Grid: Subject Progress & Latest Test/Recent Feed */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column (2 Cols): Subject-Wise Progress Bars */}
        <div className="lg:col-span-2 bg-[#0B132B] border border-slate-800 rounded-xl p-5 shadow-sm space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div>
              <h2 className="text-base font-bold text-white flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-indigo-400" /> Subject-wise Syllabus Progress
              </h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Questions solved and accuracy per syllabus subject in GATE {paperCode}
              </p>
            </div>
            <Link
              to="/analytics"
              className="text-xs text-indigo-400 hover:text-indigo-300 font-medium flex items-center gap-1"
            >
              Full Analytics <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          {subjects.length === 0 ? (
            <div className="p-8 text-center text-xs text-slate-400">
              No subject progress recorded yet. Solve questions in the Question Bank to track progress.
            </div>
          ) : (
            <div className="space-y-3.5">
              {subjects.map((s: any) => (
                <div key={s.subject_name} className="space-y-1.5">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-semibold text-slate-200">{s.subject_name}</span>
                    <div className="flex items-center gap-3 text-slate-400">
                      <span>
                        {s.attempted_questions} / {s.total_questions} solved ({s.coverage_percent}%)
                      </span>
                      <span className="font-semibold text-indigo-400">
                        {s.accuracy_percent}% accuracy
                      </span>
                    </div>
                  </div>
                  {/* Two-layer progress bar: base for coverage, top for accuracy */}
                  <div className="w-full bg-[#1C2541] rounded-full h-2 overflow-hidden flex">
                    <div
                      className="bg-indigo-600 h-full rounded-full transition-all duration-500"
                      style={{ width: `${Math.min(100, s.coverage_percent)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right Column (1 Col): Latest Test & Quick Shortcuts */}
        <div className="space-y-6">
          {/* Latest Test Result Card */}
          <div className="bg-[#0B132B] border border-slate-800 rounded-xl p-5 shadow-sm space-y-3">
            <h2 className="text-sm font-bold text-white flex items-center gap-2 border-b border-slate-800 pb-2.5">
              <Trophy className="w-4 h-4 text-amber-400" /> Latest Mock Test Evaluation
            </h2>

            {latestTest ? (
              <div className="space-y-3 text-xs">
                <div>
                  <h3 className="font-semibold text-slate-200 text-sm">
                    {latestTest.test_title || 'GATE Mock Test'}
                  </h3>
                  <span className="text-[11px] text-slate-400">
                    {new Date(latestTest.created_at).toLocaleDateString()}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-2 bg-[#1C2541]/50 p-3 rounded-lg border border-slate-800">
                  <div>
                    <span className="text-slate-400 block text-[11px]">Score Obtained</span>
                    <span className="text-lg font-bold text-emerald-400">
                      {latestTest.marks_obtained} / {latestTest.total_marks}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-400 block text-[11px]">Accuracy</span>
                    <span className="text-lg font-bold text-indigo-300">
                      {latestTest.accuracy_percent}%
                    </span>
                  </div>
                </div>

                <div className="flex items-center justify-between text-slate-400 text-[11px] pt-1">
                  <span>Correct: {latestTest.correct_count}</span>
                  <span>Incorrect: {latestTest.incorrect_count}</span>
                  <span>Unattempted: {latestTest.unattempted_count}</span>
                </div>

                <Link
                  to={`/tests`}
                  className="block text-center w-full py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg font-semibold text-xs transition"
                >
                  View Tests & Results
                </Link>
              </div>
            ) : (
              <div className="py-6 text-center space-y-2 text-xs text-slate-400">
                <Target className="w-8 h-8 text-slate-600 mx-auto" />
                <p>No CBT mock test attempted yet.</p>
                <Link
                  to="/tests"
                  className="inline-block px-3 py-1.5 bg-indigo-600 text-white rounded-lg font-medium text-xs mt-1"
                >
                  Start First Exam
                </Link>
              </div>
            )}
          </div>

          {/* Navigation Shortcuts */}
          <div className="bg-[#0B132B] border border-slate-800 rounded-xl p-5 shadow-sm space-y-3">
            <h2 className="text-sm font-bold text-white border-b border-slate-800 pb-2.5">
              Preparation Shortcuts
            </h2>

            <div className="grid grid-cols-2 gap-2 text-xs">
              <Link
                to="/questions"
                className="p-3 rounded-lg bg-[#1C2541]/60 hover:bg-[#1C2541] border border-slate-800 hover:border-slate-700 text-slate-200 flex flex-col justify-between transition"
              >
                <Database className="w-4 h-4 text-indigo-400 mb-1" />
                <span className="font-semibold">Question Bank</span>
                <span className="text-[10px] text-slate-400 mt-0.5">Topic-wise practice</span>
              </Link>

              <Link
                to="/papers"
                className="p-3 rounded-lg bg-[#1C2541]/60 hover:bg-[#1C2541] border border-slate-800 hover:border-slate-700 text-slate-200 flex flex-col justify-between transition"
              >
                <FileText className="w-4 h-4 text-emerald-400 mb-1" />
                <span className="font-semibold">Paper Library</span>
                <span className="text-[10px] text-slate-400 mt-0.5">Past year papers</span>
              </Link>

              <Link
                to="/tests"
                className="p-3 rounded-lg bg-[#1C2541]/60 hover:bg-[#1C2541] border border-slate-800 hover:border-slate-700 text-slate-200 flex flex-col justify-between transition"
              >
                <Target className="w-4 h-4 text-purple-400 mb-1" />
                <span className="font-semibold">CBT Mock Test</span>
                <span className="text-[10px] text-slate-400 mt-0.5">180-min official test</span>
              </Link>

              <Link
                to="/analytics"
                className="p-3 rounded-lg bg-[#1C2541]/60 hover:bg-[#1C2541] border border-slate-800 hover:border-slate-700 text-slate-200 flex flex-col justify-between transition"
              >
                <BarChart3 className="w-4 h-4 text-amber-400 mb-1" />
                <span className="font-semibold">PYQ Analytics</span>
                <span className="text-[10px] text-slate-400 mt-0.5">Topic weightages</span>
              </Link>
            </div>
          </div>
        </div>
      </div>

      {/* Recent Activity Log */}
      <div className="bg-[#0B132B] border border-slate-800 rounded-xl p-5 shadow-sm space-y-3">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <h2 className="text-base font-bold text-white flex items-center gap-2">
            <Clock className="w-4 h-4 text-indigo-400" /> Recent Practice & Exam Activity
          </h2>
          <span className="text-xs text-slate-400">{activities.length} recorded items</span>
        </div>

        {activities.length === 0 ? (
          <p className="text-xs text-slate-400 py-4 text-center">
            No recent activity recorded. Start by solving questions in the Question Bank.
          </p>
        ) : (
          <div className="divide-y divide-slate-800/60">
            {activities.map((a: any) => (
              <div key={a.id} className="py-2.5 flex items-center justify-between text-xs">
                <div className="flex items-center gap-3">
                  {a.is_correct ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                  ) : (
                    <XCircle className="w-4 h-4 text-rose-400 shrink-0" />
                  )}
                  <div>
                    <span className="font-semibold text-slate-200">{a.title}</span>
                    <div className="text-[11px] text-slate-400 flex items-center gap-2">
                      <span>{a.subject_name}</span>
                      <span>•</span>
                      <span>{a.topic_name}</span>
                    </div>
                  </div>
                </div>

                <div className="text-right">
                  <span
                    className={`font-bold ${
                      a.is_correct ? 'text-emerald-400' : 'text-slate-400'
                    }`}
                  >
                    {a.marks_awarded > 0 ? `+${a.marks_awarded}` : a.marks_awarded} Marks
                  </span>
                  <div className="text-[10px] text-slate-400">
                    {new Date(a.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
