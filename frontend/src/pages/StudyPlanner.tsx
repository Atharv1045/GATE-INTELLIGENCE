import React from 'react';
import { Navigate } from 'react-router-dom';

export const StudyPlanner: React.FC<{ paperCode: string }> = () => {
  return <Navigate to="/" replace />;
};
