import "./app.css";

export default function App() {
  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>개발 도면 사전 검토</h1>
        <p className="app-subtitle">PDF·DXF 도면을 승인 규칙과 사례 근거로 사전 점검합니다.</p>
      </header>
      <main className="app-main" aria-label="작업 영역">
        <p className="app-empty">아직 검토 프로젝트가 없습니다.</p>
      </main>
    </div>
  );
}
