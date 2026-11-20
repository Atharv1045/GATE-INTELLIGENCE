import React, { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  FileText,
  CheckCircle2,
  AlertCircle,
  Play,
  Database,
  Eye,
  X,
  Layers,
  Award,
  BookOpen,
  Upload,
} from 'lucide-react';
import { gateApi } from '../services/api';
import { MarkdownRenderer } from '../components/MarkdownRenderer';
import { PdfPaperUploadModal } from '../components/PdfPaperUploadModal';

export const PaperLibrary: React.FC<{ paperCode: string }> = ({ paperCode }) => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [previewPaperId, setPreviewPaperId] = useState<string | null>(null);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState<boolean>(false);

  // Query papers catalog from backend
  const { data: papersData, isLoading } = useQuery({
    queryKey: ['papers_catalog', paperCode],
    queryFn: () => gateApi.listPapers({ paper_code: paperCode }),
  });

  // Query paper questions preview if modal open
  const { data: previewData, isLoading: isPreviewLoading } = useQuery({
    queryKey: ['paper_questions_preview', previewPaperId],
    queryFn: () => (previewPaperId ? gateApi.getPaperQuestions(previewPaperId) : null),
    enabled: !!previewPaperId,
  });

  const papers = papersData?.papers || [];

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2.5">
            <span>Paper Library</span>
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 font-semibold border border-indigo-500/30">
              GATE {paperCode}
            </span>
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Browse authentic historical GATE examination papers. Preview questions or launch full-paper CBT mock tests.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setIsUploadModalOpen(true)}
            className="px-3.5 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center gap-2 shadow transition"
          >
            <Upload className="w-4 h-4" />
            <span>Upload & Ingest PDF Paper</span>
          </button>
          <div className="text-right pl-3 border-l border-slate-800">
            <span className="text-xs text-slate-400">Total in Catalog</span>
            <div className="text-xl font-bold text-white">{papers.length} Papers</div>
          </div>
        </div>
      </div>

      {/* Papers Grid */}
      {isLoading ? (
        <div className="bg-[#0B132B] border border-slate-800 rounded-xl p-12 text-center text-slate-400">
          <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto mb-3"></div>
          <p className="text-sm">Loading Paper Library...</p>
        </div>
      ) : papers.length === 0 ? (
        <div className="bg-[#0B132B] border border-slate-800 rounded-xl p-12 text-center text-slate-400">
          <FileText className="w-12 h-12 text-slate-600 mx-auto mb-3" />
          <h3 className="text-base font-bold text-white">No Papers Cataloged</h3>
          <p className="text-xs mt-1">Import question datasets in Settings to populate the Paper Library.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {papers.map((p: any) => {
            const isReady = p.question_count > 0;
            const hasVerifiedKeys = p.verified_keys_count > 0;

            return (
              <div
                key={p.id}
                className={`bg-[#0B132B] border rounded-xl p-5 shadow-sm flex flex-col justify-between transition-all ${
                  isReady ? 'border-slate-800 hover:border-slate-700' : 'border-slate-800/50 opacity-70'
                }`}
              >
                <div className="space-y-3">
                  {/* Top year badge and status */}
                  <div className="flex items-center justify-between">
                    <span className="text-xs px-2.5 py-1 rounded bg-indigo-500/20 text-indigo-300 font-bold border border-indigo-500/30">
                      {p.examination_year} • {p.session_set || 'Set-1'}
                    </span>
                    {isReady ? (
                      <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 px-2.5 py-0.5 rounded-full">
                        <CheckCircle2 className="w-3.5 h-3.5" /> Ready ({p.question_count} Qs)
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-[11px] font-medium text-slate-400 bg-slate-800 px-2 py-0.5 rounded-full">
                        <AlertCircle className="w-3.5 h-3.5" /> Pending Ingestion
                      </span>
                    )}
                  </div>

                  <div>
                    <h2 className="text-base font-bold text-white leading-snug">
                      {p.title || `GATE ${p.paper_code} ${p.examination_year}`}
                    </h2>
                    <p className="text-xs text-slate-400 mt-1">
                      Official Graduate Aptitude Test in Engineering — {p.paper_code}
                    </p>
                  </div>

                  {/* Question stats pills */}
                  {isReady && (
                    <div className="grid grid-cols-3 gap-2 bg-[#1C2541]/40 p-2.5 rounded-lg border border-slate-800 text-xs">
                      <div>
                        <span className="text-[10px] text-slate-400 block uppercase">Marks</span>
                        <span className="font-bold text-white">{p.total_marks || 100}</span>
                      </div>
                      <div>
                        <span className="text-[10px] text-slate-400 block uppercase">Types</span>
                        <span className="font-bold text-slate-200">
                          {p.mcq_count}M / {p.msq_count}S / {p.nat_count}N
                        </span>
                      </div>
                      <div>
                        <span className="text-[10px] text-slate-400 block uppercase">Answer Key</span>
                        <span
                          className={`font-bold ${
                            hasVerifiedKeys ? 'text-emerald-400' : 'text-amber-400'
                          }`}
                        >
                          {p.verified_keys_count}/{p.question_count}
                        </span>
                      </div>
                    </div>
                  )}
                </div>

                {/* Actions */}
                <div className="pt-4 mt-4 border-t border-slate-800/80 flex items-center justify-between gap-2">
                  {isReady ? (
                    <>
                      <button
                        onClick={() => setPreviewPaperId(p.id)}
                        className="px-3 py-1.5 rounded-lg bg-[#1C2541] hover:bg-slate-700 text-slate-200 text-xs font-medium flex items-center gap-1.5 transition"
                      >
                        <Eye className="w-3.5 h-3.5 text-indigo-400" /> Preview
                      </button>

                      <div className="flex items-center gap-2">
                        <button
                          onClick={() =>
                            navigate(`/questions?paper_code=${p.paper_code}&year=${p.examination_year}`)
                          }
                          className="px-3 py-1.5 rounded-lg bg-[#1C2541] hover:bg-slate-700 text-slate-200 text-xs font-medium flex items-center gap-1 transition"
                          title="Practice in Question Bank"
                        >
                          <Database className="w-3.5 h-3.5 text-emerald-400" /> Practice
                        </button>

                        <button
                          onClick={() =>
                            navigate(`/tests?launch_paper_id=${p.id}&launch_year=${p.examination_year}`)
                          }
                          className="px-3.5 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center gap-1.5 shadow transition"
                          title="Start Full-Length CBT Mock Test"
                        >
                          <Play className="w-3.5 h-3.5 fill-current" /> CBT Test
                        </button>
                      </div>
                    </>
                  ) : (
                    <span className="text-xs text-slate-500 italic">
                      Import dataset in Settings to activate
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Question Preview Slide-over Modal */}
      {previewPaperId && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center p-4 z-50 animate-fadeIn">
          <div className="bg-[#0B132B] border border-slate-700 rounded-xl max-w-4xl w-full max-h-[85vh] flex flex-col overflow-hidden shadow-2xl">
            {/* Modal Header */}
            <div className="p-4 border-b border-slate-800 flex items-center justify-between bg-[#10182E]">
              <div>
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <BookOpen className="w-4 h-4 text-indigo-400" />
                  {previewData?.paper_title || 'Paper Preview'}
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Sequential question listing ({previewData?.total_questions || 0} questions)
                </p>
              </div>
              <button
                onClick={() => setPreviewPaperId(null)}
                className="p-1.5 rounded-lg bg-[#1C2541] hover:bg-slate-700 text-slate-300"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-5 overflow-y-auto space-y-4 divide-y divide-slate-800/80">
              {isPreviewLoading ? (
                <div className="text-center py-10 text-xs text-slate-400">Loading questions preview...</div>
              ) : !previewData || previewData.questions?.length === 0 ? (
                <div className="text-center py-10 text-xs text-slate-400">No questions available in this paper.</div>
              ) : (
                previewData.questions.map((q: any) => (
                  <div key={q.id} className="pt-4 first:pt-0 space-y-2.5">
                    <div className="flex items-center justify-between text-xs">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-indigo-300">Q.{q.question_number}</span>
                        <span className="px-2 py-0.5 rounded bg-[#1C2541] text-slate-300">
                          {q.question_type} • {q.marks} Mark(s)
                        </span>
                        <span className="text-slate-400">{q.subject_name}</span>
                      </div>
                      <div>
                        {q.answer_key?.is_verified ? (
                          <span className="text-emerald-400 font-semibold text-[11px]">
                            Answer: ({q.answer_key.correct_options?.join(', ') || 'Range'})
                          </span>
                        ) : (
                          <span className="text-amber-400 text-[11px]">Key unverified</span>
                        )}
                      </div>
                    </div>

                    <div className="text-xs sm:text-sm text-slate-200">
                      <MarkdownRenderer content={q.question_text || ''} />
                    </div>

                    {q.options && q.options.length > 0 && (
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1 text-xs text-slate-300">
                        {q.options.map((opt: any) => (
                          <div
                            key={opt.option_label}
                            className={`p-2 rounded border ${
                              q.answer_key?.correct_options?.includes(opt.option_label)
                                ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300'
                                : 'border-slate-800 bg-[#1C2541]/40'
                            }`}
                          >
                            <span className="font-bold mr-1.5 text-indigo-400">({opt.option_label})</span>
                            <MarkdownRenderer content={opt.option_text || ''} />
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>

            {/* Modal Footer */}
            <div className="p-4 border-t border-slate-800 flex justify-end gap-3 bg-[#10182E]">
              <button
                onClick={() => setPreviewPaperId(null)}
                className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs text-slate-200 font-medium"
              >
                Close Preview
              </button>
              {previewPaperId && (
                <button
                  onClick={() => {
                    const pid = previewPaperId;
                    setPreviewPaperId(null);
                    navigate(`/tests?launch_paper_id=${pid}`);
                  }}
                  className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-xs text-white font-semibold flex items-center gap-1.5"
                >
                  <Play className="w-3.5 h-3.5 fill-current" /> Start CBT Exam
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* PDF Paper Upload & Ingestion Wizard Modal */}
      <PdfPaperUploadModal
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
        defaultPaperCode={paperCode}
        onImportSuccess={() => {
          queryClient.invalidateQueries({ queryKey: ['papers_catalog'] });
          queryClient.invalidateQueries({ queryKey: ['dashboard_metrics'] });
          queryClient.invalidateQueries({ queryKey: ['dashboard_progress'] });
          queryClient.invalidateQueries({ queryKey: ['questions'] });
        }}
      />
    </div>
  );
};
