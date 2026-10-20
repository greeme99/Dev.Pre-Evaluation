import { type KeyboardEvent, useState } from "react";
import { KnowledgeImport } from "../features/knowledge/KnowledgeImport";
import { RuleCatalog } from "../features/rules/RuleCatalog";
import { AnalysisWorkflow } from "../features/analysis/AnalysisWorkflow";
import { FindingsViewer } from "../features/findings/FindingsViewer";
import { SettingsView } from "../features/settings/SettingsView";
import type { Finding, ImprovementSuggestion, RuleDefinition } from "@dev-pre-review/contracts";

export type TabId = "knowledge" | "rules" | "analysis" | "findings" | "settings";

interface TabItem {
  id: TabId;
  label: string;
}

const TABS: TabItem[] = [
  { id: "knowledge", label: "지식 가져오기" },
  { id: "rules", label: "규칙 카탈로그" },
  { id: "analysis", label: "도면 검사 실행" },
  { id: "findings", label: "검토 결과" },
  { id: "settings", label: "환경 설정" },
];

const mockInitialRules: RuleDefinition[] = [
  {
    id: "r1",
    code: "RULE-DIM-001",
    title: "최소 축경 10mm 기준",
    description: "동력 전달 축 최소 직경",
    discipline: "MACHINING",
    state: "approved",
    severity: "critical",
    operator: "min",
    field_name: "shaft_diameter",
    parameters: { value: 10 },
    version: 1,
    created_at: "2026-10-20T00:00:00Z",
    updated_at: "2026-10-20T00:00:00Z",
  },
  {
    id: "r2",
    code: "RULE-SURF-002",
    title: "외경 표면 거칠기",
    description: "조도 Ra 0.8 이하",
    discipline: "SURFACE",
    state: "draft",
    severity: "major",
    operator: "max",
    field_name: "roughness_ra",
    parameters: { value: 0.8 },
    version: 1,
    created_at: "2026-10-20T00:00:00Z",
    updated_at: "2026-10-20T00:00:00Z",
  },
];

const mockInitialFindings: Finding[] = [
  {
    id: "f1",
    job_id: "job-1",
    rule_code: "RULE-DIM-001",
    status: "violation",
    severity: "critical",
    message: "모터 축 직경 9.2mm로 기준 10.0mm 미달입니다.",
    bbox: { page_or_layout: 1, x0: 25, y0: 35, x1: 50, y1: 60 },
    evidences: [
      { kind: "rule", ref_id: "RULE-DIM-001" },
      { kind: "case", ref_id: "CASE-2025-01" },
    ],
  },
];

const mockInitialSuggestions: ImprovementSuggestion[] = [
  {
    finding_id: "f1",
    suggested_action: "가공 여유치수를 +0.8mm 조정하십시오.",
    rationale: "유사 샤프트 마모 불량 사례 기반",
  },
];

export function AppRouter() {
  const [activeTab, setActiveTab] = useState<TabId>("analysis");

  const handleKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const currentIndex = TABS.findIndex((t) => t.id === activeTab);
    if (e.key === "ArrowRight") {
      const nextIndex = (currentIndex + 1) % TABS.length;
      const target = TABS[nextIndex];
      if (target) setActiveTab(target.id);
    } else if (e.key === "ArrowLeft") {
      const prevIndex = (currentIndex - 1 + TABS.length) % TABS.length;
      const target = TABS[prevIndex];
      if (target) setActiveTab(target.id);
    }
  };

  return (
    <div className="router-container">
      <nav
        className="tabs-nav"
        role="tablist"
        aria-label="메인 탐색 탭"
        onKeyDown={handleKeyDown}
      >
        {TABS.map((tab) => {
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
        {activeTab === "knowledge" && <KnowledgeImport projectId="p-demo" />}
        {activeTab === "rules" && <RuleCatalog initialRules={mockInitialRules} />}
        {activeTab === "analysis" && <AnalysisWorkflow projectId="p-demo" />}
        {activeTab === "findings" && (
          <FindingsViewer
            findings={mockInitialFindings}
            suggestions={mockInitialSuggestions}
          />
        )}
        {activeTab === "settings" && <SettingsView />}
      </main>
    </div>
  );
}
