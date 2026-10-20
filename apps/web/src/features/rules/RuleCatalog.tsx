import { useState } from "react";
import type { RuleDefinition, RuleState } from "@dev-pre-review/contracts";

interface Props {
  initialRules?: RuleDefinition[];
  onTransition?: (ruleId: string, action: string, version: number) => Promise<void>;
}

export function RuleCatalog({ initialRules = [], onTransition }: Props) {
  const [rules, setRules] = useState<RuleDefinition[]>(initialRules);
  const [filterState, setFilterState] = useState<string>("ALL");
  const [busyRuleId, setBusyRuleId] = useState<string | null>(null);

  const filteredRules = rules.filter((r) => {
    if (filterState === "ALL") return true;
    return r.state.toUpperCase() === filterState;
  });

  const handleAction = async (ruleId: string, action: string, version: number) => {
    setBusyRuleId(ruleId);
    try {
      if (onTransition) {
        await onTransition(ruleId, action, version);
      }
      setRules((prev) =>
        prev.map((r) => {
          if (r.id !== ruleId) return r;
          const nextState: RuleState =
            action === "approve" ? "approved" : action === "deprecate" ? "deprecated" : r.state;
          return { ...r, state: nextState, version: r.version + 1 };
        })
      );
    } finally {
      setBusyRuleId(null);
    }
  };

  return (
    <section className="rule-catalog-panel" aria-labelledby="rule-catalog-title">
      <div className="catalog-header">
        <h2 id="rule-catalog-title">규칙 카탈로그</h2>
        <div className="filter-group">
          <label htmlFor="state-filter">상태 필터:</label>
          <select
            id="state-filter"
            value={filterState}
            onChange={(e) => setFilterState(e.target.value)}
          >
            <option value="ALL">전체 보기</option>
            <option value="DRAFT">초안 (DRAFT)</option>
            <option value="APPROVED">승인됨 (APPROVED)</option>
            <option value="DEPRECATED">사용중단 (DEPRECATED)</option>
          </select>
        </div>
      </div>

      <table className="rules-table" aria-label="규칙 카탈로그 목록">
        <thead>
          <tr>
            <th scope="col">규칙 코드</th>
            <th scope="col">규칙명</th>
            <th scope="col">분야</th>
            <th scope="col">심각도</th>
            <th scope="col">상태</th>
            <th scope="col">동작</th>
          </tr>
        </thead>
        <tbody>
          {filteredRules.length === 0 ? (
            <tr>
              <td colSpan={6} className="empty-row">
                등록된 규칙이 없습니다.
              </td>
            </tr>
          ) : (
            filteredRules.map((rule) => {
              const isBusy = busyRuleId === rule.id;
              return (
                <tr key={rule.id}>
                  <td>
                    <strong>{rule.code}</strong>
                  </td>
                  <td>{rule.title}</td>
                  <td>{rule.discipline}</td>
                  <td>
                    <span className={`badge severity-${rule.severity}`}>{rule.severity}</span>
                  </td>
                  <td>
                    <span className={`badge state-${rule.state}`}>{rule.state.toUpperCase()}</span>
                  </td>
                  <td>
                    {rule.state === "draft" && (
                      <button
                        type="button"
                        disabled={isBusy}
                        onClick={() => handleAction(rule.id, "approve", rule.version)}
                        className="btn btn-sm btn-success"
                      >
                        승인
                      </button>
                    )}
                    {rule.state === "approved" && (
                      <button
                        type="button"
                        disabled={isBusy}
                        onClick={() => handleAction(rule.id, "deprecate", rule.version)}
                        className="btn btn-sm btn-danger"
                      >
                        사용 중단
                      </button>
                    )}
                    {rule.state === "deprecated" && <span className="text-muted">-</span>}
                  </td>
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </section>
  );
}
