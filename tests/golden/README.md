# Golden Set Evaluation Benchmark (TC-101, TC-102)

본 디렉터리는 개발도면 사전검토 자동화 시스템의 품질 및 성능 예산을 객관적으로 평가하기 위한 골든셋 매니페스트 및 가이드라인을 정의합니다.

---

## 1. 품질 게이트 기준 (Quality Gate Thresholds)

`plan.md` 및 `DOC-DEVPLAN-001` (NFR-001, NFR-002, TC-101, TC-102)에 정의된 필수 통과 기준:

| 항목 (Metric) | 목표 임계값 (Threshold) | 참조 표준 |
| --- | --- | --- |
| **도면 요소 추출 성공률** | $\ge 95.0\%$ | NFR-002, TC-102 |
| **검토 위반 정밀도 (Precision)** | $\ge 90.0\%$ | NFR-002, TC-102 |
| **검토 위반 재현율 (Recall)** | $\ge 80.0\%$ | NFR-002, TC-102 |
| **근거 검색 Top-5 적중률** | $\ge 80.0\%$ | NFR-002, TC-102 |
| **P95 분석 지연시간 (성능 예산)** | $\le 180.0\text{초}$ (PDF 20p / DXF 50MB) | NFR-001, TC-101 |

---

## 2. 데이터셋 분할 및 보안 원칙

1. **Tuning vs Final 분리**:
   - `tuning`: 규칙 및 검색 파라미터 튜닝에 사용할 수 있는 학습/검증 샘플.
   - `final`: 튜닝에 절대 참조하지 않으며 최종 릴리스 승인 검증에만 사용하는 블라인드 골든셋.
2. **SHA-256 무결성 보장**:
   - 모든 샘플 파일은 `sha256` 해시가 고정되며 실행 전 무결성 검증을 거칩니다.
   - 위변조나 파일 손상 시 즉시 평가가 중단됩니다.
3. **완전 비식별화 및 보안**:
   - 실제 고객사명, 도면번호, 개인정보, 절대 경로는 철저히 배제된 합성·가상 fixture만 커밋합니다.

---

## 3. 평가 실행 방법

### PowerShell CLI (Windows 10/11)
```powershell
.\scripts\run_golden_evaluation.ps1 -ManifestPath tests\golden\manifest.json -Split final -OutputReport report.md
```

### Python API
```python
from dev_pre_review.evaluation import EvaluationDatasetSplit, EvaluationManifest, EvaluationRunner

manifest = EvaluationManifest.from_file(Path("tests/golden/manifest.json"))
manifest.verify_integrity()

runner = EvaluationRunner(manifest=manifest)
report = runner.evaluate(
    split=EvaluationDatasetSplit.FINAL,
    eval_fn=my_pipeline_evaluator,
)
print(report.to_markdown())
```
