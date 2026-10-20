import { type KeyboardEvent, useState } from "react";
import { AnalysisWorkflow } from "../features/analysis/AnalysisWorkflow";
import { FindingsViewer } from "../features/findings/FindingsViewer";
import type { FindingsResponse } from "@dev-pre-review/contracts";

export type TabId = "analysis" | "findings";

interface TabItem {
  id: TabId;
  label: string;
}

const ANALYSIS_TAB: TabItem = { id: "analysis", label: "도면 검사 실행" };
const FINDINGS_TAB: TabItem = { id: "findings", label: "검토 결과" };

export function AppRouter() {
  const [activeTab, setActiveTab] = useState<TabId>("analysis");
  const [result, setResult] = useState<FindingsResponse | null>(null);
  const tabs = result ? [ANALYSIS_TAB, FINDINGS_TAB] : [ANALYSIS_TAB];

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (tabs.length < 2) return;
    const currentIndex = tabs.findIndex((tab) => tab.id === activeTab);
    if (event.key === "ArrowRight") setActiveTab(tabs[(currentIndex + 1) % tabs.length]!.id);
    else if (event.key === "ArrowLeft") setActiveTab(tabs[(currentIndex - 1 + tabs.length) % tabs.length]!.id);
  };

  const handleComplete = (findings: FindingsResponse) => {
    setResult(findings);
    setActiveTab("findings");
  };

  return (
    <div className="router-container">
      <nav
        className="tabs-nav"
        role="tablist"
        aria-label="메인 탐색 탭"
        onKeyDown={handleKeyDown}
      >
        {tabs.map((tab) => {
          const isSelected = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              role="tab"
              id={`tab-${tab.id}`}
              aria-controls={`panel-${tab.id}`}
              aria-selected={isSelected}
              tabIndex={isSelected ? 0 : -1}
              className={`tab-btn ${isSelected ? "active" : ""}`}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
            </button>
          );
        })}
      </nav>

      <main className="tab-content" id={`panel-${activeTab}`} role="tabpanel" aria-labelledby={`tab-${activeTab}`}>
        {activeTab === "analysis" && <AnalysisWorkflow onComplete={handleComplete} />}
        {activeTab === "findings" && result && (
          <FindingsViewer
            jobId={result.job_id}
            findings={result.findings}
            suggestions={result.suggestions}
          />
        )}
      </main>
    </div>
  );
}
