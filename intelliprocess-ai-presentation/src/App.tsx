import { Navigate, Route, Routes } from 'react-router-dom';
import { PresentationShell } from './components/presentation/PresentationShell';
import { OverviewPage } from './pages/presentation/Overview';
import { CoverPage } from './pages/presentation/Cover';
import { ProblemPage } from './pages/presentation/Problem';
import { TransformationPage } from './pages/presentation/Transformation';
import { SolutionPage } from './pages/presentation/Solution';
import { HowItWorksPage } from './pages/presentation/HowItWorks';
import { DocumentProcessingPage } from './pages/presentation/DocumentProcessing';
import { ThreeWayMatchingPage } from './pages/presentation/ThreeWayMatching';
import { ExceptionsPage } from './pages/presentation/Exceptions';
import { DashboardPage } from './pages/presentation/Dashboard';
import { AskYourRecordsPage } from './pages/presentation/AskYourRecords';
import { PlatformPage } from './pages/presentation/Platform';
import { ArchitecturePage } from './pages/presentation/Architecture';
import { SecurityPage } from './pages/presentation/Security';
import { BusinessValuePage } from './pages/presentation/BusinessValue';
import { DemoPage } from './pages/presentation/Demo';
import { ClosingPage } from './pages/presentation/Closing';

function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/presentation" replace />} />
      <Route path="/presentation" element={<PresentationShell />}>
        <Route index element={<CoverPage />} />
        <Route path="overview" element={<OverviewPage />} />
        <Route path="problem" element={<ProblemPage />} />
        <Route path="transformation" element={<TransformationPage />} />
        <Route path="solution" element={<SolutionPage />} />
        <Route path="how-it-works" element={<HowItWorksPage />} />
        <Route path="document-processing" element={<DocumentProcessingPage />} />
        <Route path="three-way-matching" element={<ThreeWayMatchingPage />} />
        <Route path="exceptions" element={<ExceptionsPage />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="ask-your-records" element={<AskYourRecordsPage />} />
        <Route path="platform" element={<PlatformPage />} />
        <Route path="architecture" element={<ArchitecturePage />} />
        <Route path="security" element={<SecurityPage />} />
        <Route path="business-value" element={<BusinessValuePage />} />
        <Route path="demo" element={<DemoPage />} />
        <Route path="closing" element={<ClosingPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/presentation" replace />} />
    </Routes>
  );
}

export default App;
