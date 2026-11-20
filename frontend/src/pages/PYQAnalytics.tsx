import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Legend,
  Cell,
} from 'recharts';
import {
  BarChart3,
  TrendingUp,
  Layers,
  PieChart as PieIcon,
  Filter,
} from 'lucide-react';
import { gateApi } from '../services/api';

const COLORS = ['#6366f1', '#06b6d4', '#10b981', '#f59e0b', '#ec4899', '#8b5cf6', '#3b82f6'];

export const PYQAnalytics: React.FC<{ paperCode: string }> = ({ paperCode }) => {
  const [selectedSubjectFilter, setSelectedSubjectFilter] = useState<string>('');

  const { data: distData, isLoading } = useQuery({
    queryKey: ['analytics_distributions', paperCode, selectedSubjectFilter],
    queryFn: () => gateApi.getDistributions(paperCode, selectedSubjectFilter || undefined),
  });

  const { data: diffData } = useQuery({
    queryKey: ['analytics_difficulty', paperCode],
    queryFn: () => gateApi.getDifficulty(paperCode),
  });

  const subjectDist = distData?.subject_distribution || [];
  const topicDist = distData?.topic_distribution || [];
  const yearTrends = distData?.year_trends || [];
  const questionTypes = distData?.question_types || [];
  const marksDist = distData?.marks_distribution || [];
  const difficultyDist = diffData?.distribution || [];
  const totalQuestions = distData?.total_questions || 0;

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2.5">
            <span>Historical PYQ Analytics</span>
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 font-semibold border border-indigo-500/30">
              GATE {paperCode}
            </span>
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Factual syllabus distribution, year trends, and question type breakdowns based on active database records.
          </p>
        </div>

        <div className="text-right">
          <span className="text-xs text-slate-400">Sample Size</span>
          <div className="text-xl font-bold text-white">{totalQuestions} Questions</div>
        </div>
      </div>

      {isLoading ? (
        <div className="bg-[#0B132B] border border-slate-800 rounded-xl p-12 text-center text-slate-400">
          <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto mb-3"></div>
          <p className="text-sm">Aggregating historical examination data...</p>
        </div>
      ) : totalQuestions === 0 ? (
        <div className="bg-[#0B132B] border border-slate-800 rounded-xl p-12 text-center text-slate-400">
          <BarChart3 className="w-12 h-12 text-slate-600 mx-auto mb-3" />
          <h3 className="text-base font-bold text-white">No Question Data Available</h3>
          <p className="text-xs mt-1">Import paper datasets in Settings to generate analytics.</p>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Chart 1: Subject-wise Question Count & Weightage */}
          <div className="bg-[#0B132B] border border-slate-800 rounded-xl p-5 shadow-sm space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-3">
              <div>
                <h2 className="text-base font-bold text-white flex items-center gap-2">
                  <BarChart3 className="w-4 h-4 text-indigo-400" /> Subject-wise Question Distribution
                </h2>
                <p className="text-xs text-slate-400 mt-0.5">
                  Number of historical questions across all syllabus subjects in GATE {paperCode}
                </p>
              </div>
            </div>

            <div className="h-72 w-full pt-2">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={subjectDist} margin={{ top: 10, right: 20, left: 0, bottom: 40 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis
                    dataKey="subject_name"
                    angle={-25}
                    textAnchor="end"
                    interval={0}
                    height={60}
                    tick={{ fill: '#94a3b8', fontSize: 11 }}
                  />
                  <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#0B132B', borderColor: '#334155', color: '#f8fafc', borderRadius: '8px' }}
                  />
                  <Bar dataKey="count" name="Questions Count" fill="#6366f1" radius={[4, 4, 0, 0]}>
                    {subjectDist.map((_: any, index: number) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Chart 2: High-Yield Topics Breakdown */}
          <div className="bg-[#0B132B] border border-slate-800 rounded-xl p-5 shadow-sm space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-3">
              <div>
                <h2 className="text-base font-bold text-white flex items-center gap-2">
                  <Layers className="w-4 h-4 text-emerald-400" /> High-Yield Topic Frequency Breakdown
                </h2>
                <p className="text-xs text-slate-400 mt-0.5">
                  Top topics by question frequency {selectedSubjectFilter ? `in "${selectedSubjectFilter}"` : 'across all subjects'}
                </p>
              </div>

              {/* Subject filter for topic drilldown */}
              <div className="flex items-center gap-2">
                <Filter className="w-3.5 h-3.5 text-slate-400" />
                <select
                  value={selectedSubjectFilter}
                  onChange={(e) => setSelectedSubjectFilter(e.target.value)}
                  className="bg-[#1C2541] border border-slate-700 rounded-lg px-2.5 py-1 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
                >
                  <option value="">All Subjects</option>
                  {subjectDist.map((s: any) => (
                    <option key={s.subject_name} value={s.subject_name}>
                      {s.subject_name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="h-80 w-full pt-2">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={topicDist}
                  layout="vertical"
                  margin={{ top: 10, right: 30, left: 100, bottom: 10 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis type="number" tick={{ fill: '#94a3b8', fontSize: 11 }} />
                  <YAxis
                    dataKey="topic_name"
                    type="category"
                    width={180}
                    tick={{ fill: '#94a3b8', fontSize: 11 }}
                  />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#0B132B', borderColor: '#334155', color: '#f8fafc', borderRadius: '8px' }}
                  />
                  <Bar dataKey="count" name="Questions Count" fill="#10b981" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Row of 3 Smaller Charts: Year Trends, Question Types, Marks */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {/* Year-wise Question Volume */}
            <div className="bg-[#0B132B] border border-slate-800 rounded-xl p-5 shadow-sm space-y-3">
              <div>
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <TrendingUp className="w-4 h-4 text-sky-400" /> Year-wise Question Trends
                </h3>
                <p className="text-[11px] text-slate-400 mt-0.5">Questions recorded per exam year</p>
              </div>

              <div className="h-52 w-full pt-2">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={yearTrends} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis dataKey="year" tick={{ fill: '#94a3b8', fontSize: 11 }} />
                    <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#0B132B', borderColor: '#334155', color: '#f8fafc' }}
                    />
                    <Bar dataKey="count" name="Total Questions" fill="#06b6d4" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Question Type Breakdown */}
            <div className="bg-[#0B132B] border border-slate-800 rounded-xl p-5 shadow-sm space-y-3">
              <div>
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <PieIcon className="w-4 h-4 text-purple-400" /> Question Types Breakdown
                </h3>
                <p className="text-[11px] text-slate-400 mt-0.5">MCQ vs MSQ vs NAT proportions</p>
              </div>

              <div className="h-52 w-full pt-2">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={questionTypes} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis dataKey="type" tick={{ fill: '#94a3b8', fontSize: 11 }} />
                    <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#0B132B', borderColor: '#334155', color: '#f8fafc' }}
                    />
                    <Bar dataKey="count" name="Questions Count" fill="#8b5cf6" radius={[4, 4, 0, 0]}>
                      {questionTypes.map((_: any, index: number) => (
                        <Cell key={`cell-${index}`} fill={['#6366f1', '#ec4899', '#f59e0b'][index % 3]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Marks Distribution */}
            <div className="bg-[#0B132B] border border-slate-800 rounded-xl p-5 shadow-sm space-y-3">
              <div>
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <BarChart3 className="w-4 h-4 text-amber-400" /> Marks Distribution
                </h3>
                <p className="text-[11px] text-slate-400 mt-0.5">1-Mark vs 2-Mark questions</p>
              </div>

              <div className="h-52 w-full pt-2">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={marksDist} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis dataKey="marks" tick={{ fill: '#94a3b8', fontSize: 11 }} />
                    <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#0B132B', borderColor: '#334155', color: '#f8fafc' }}
                    />
                    <Bar dataKey="count" name="Questions Count" fill="#f59e0b" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
