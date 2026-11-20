import React, { useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query';
import { AppLayout } from './layouts/AppLayout';
import { Dashboard } from './pages/Dashboard';
import { QuestionBank } from './pages/QuestionBank';
import { PaperLibrary } from './pages/PaperLibrary';
import { PYQAnalytics } from './pages/PYQAnalytics';
import { MockTests } from './pages/MockTests';
import { Agents } from './pages/Agents';
import { Settings } from './pages/Settings';
import { gateApi } from './services/api';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

const AppRoutes: React.FC = () => {
  const [selectedPaper, setSelectedPaper] = useState<string>('CS');

  const { data: papersData } = useQuery({
    queryKey: ['taxonomy_papers'],
    queryFn: () => gateApi.listSupportedPapers(),
  });

  const supportedPapers = papersData?.papers || [
    { code: 'CS', name: 'Computer Science and Information Technology' },
    { code: 'DA', name: 'Data Science and Artificial Intelligence' },
    { code: 'EC', name: 'Electronics and Communication Engineering' },
    { code: 'EE', name: 'Electrical Engineering' },
    { code: 'ME', name: 'Mechanical Engineering' },
    { code: 'CE', name: 'Civil Engineering' },
  ];

  return (
    <BrowserRouter>
      <AppLayout
        selectedPaper={selectedPaper}
        onSelectPaper={setSelectedPaper}
        supportedPapers={supportedPapers}
      >
        <Routes>
          <Route path="/" element={<Dashboard paperCode={selectedPaper} />} />
          <Route path="/questions" element={<QuestionBank paperCode={selectedPaper} />} />
          <Route path="/papers" element={<PaperLibrary paperCode={selectedPaper} />} />
          <Route path="/analytics" element={<PYQAnalytics paperCode={selectedPaper} />} />
          <Route path="/tests" element={<MockTests paperCode={selectedPaper} />} />
          <Route path="/mock-tests" element={<Navigate to="/tests" replace />} />
          <Route path="/agents" element={<Agents paperCode={selectedPaper} />} />
          <Route path="/settings" element={<Settings />} />

          {/* Legacy route redirects */}
          <Route path="/tutor" element={<Navigate to="/agents" replace />} />
          <Route path="/planner" element={<Navigate to="/" replace />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AppLayout>
    </BrowserRouter>
  );
};

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppRoutes />
    </QueryClientProvider>
  );
}
