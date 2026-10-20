# Dev.Pre-Evaluation (개발 도면 사전 검토 자동화 시스템)

[![CI](https://github.com/greeme99/Dev.Pre-Evaluation/actions/workflows/ci.yml/badge.svg)](https://github.com/greeme99/Dev.Pre-Evaluation/actions)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![React 19](https://img.shields.io/badge/react-19-61dafb.svg)](https://react.dev/)
[![License: Proprietary](https://img.shields.io/badge/license-Proprietary-red.svg)](#)

> **기계·배관·전기·토공 도면(PDF / DXF)의 사전 설계 오류를 로컬 환경에서 자동으로 검출하고 검토 근거를 시각화하는 Windows 데스크톱 웹 애플리케이션**

---

## 📌 주요 특징 (Key Features)

- **오프라인 우선 & 보안 보장 (Local-First Architecture)**
  - Docker 불필요, `127.0.0.1:17841` 로컬 루프백에만 바인딩되어 외부 네트워크로 도면 원문이나 데이터가 무단 유출되지 않습니다.
  - Windows 10/11 로컬 단일 사용자 환경을 타깃으로 경량화되어 있습니다.
- **결정론적 규칙 검사 엔진 (Rule Engine)**
  - 엔지니어가 승인한 규칙에 기반하여 모호성 없는 명확한 3단계 판정(`위반 Violation`, `의심 Suspected`, `정보 부족 Insufficient Information`)을 내립니다.
  - AI에 의한 자의적 판정 격상을 엄격히 금지합니다.
- **하이브리드 근거 검색 (Pixel RAG + Text BM25)**
  - 과거 설계 오류 사례 및 도면 요소에 대해 텍스트 키워드와 시각 타일 벡터 임베딩을 결합하여 가장 신뢰도 높은 근거를 Top-5로 매칭합니다.
- **도면 뷰어 & 좌표 하이라이트**
  - PDF 및 DXF 렌더 이미지 상에 검출된 오류 좌표 바운딩 박스를 정확하게 오버레이하고, 매칭된 설계 기준 및 오류 사례 근거를 함께 제시합니다.
- **표준 내보내기 & 암호화 백업/복원**
  - 고정 열 순서의 XLSX 및 UTF-8 BOM CSV 내보내기를 지원합니다.
  - Argon2id 키 유도 및 AES-256-GCM 인증 암호화 기반 `.dprb` 백업/복원 패키지를 제공합니다.
- **개인정보 보호 진단 번들 (Privacy-Preserving Diagnostics)**
  - 시스템 오류 분석 시 절대 경로, API 키, 도면 원문을 자동으로 제거한 안전한 진단 번들을 생성합니다.

---

## 🏗 시스템 아키텍처 (System Architecture)

```
Dev.Pre-Evaluation/
├── apps/
│   ├── api/                 # FastAPI 백엔드 (Python 3.12)
│   │   ├── src/dev_pre_review/
│   │   │   ├── analysis/    # 파이프라인 오케스트레이션 및 융합 로직
│   │   │   ├── api/         # REST API 라우터 (FastAPI)
│   │   │   ├── domain/      # 엔티티, 모델, 상태 전이 규칙
│   │   │   ├── drawings/    # PDF/DXF 파서, 래스터화, 타일링, 좌표 변환
│   │   │   ├── evaluation/  # 골든셋 벤치마크 및 품질 지표 계산기
│   │   │   ├── export/      # XLSX/CSV 내보내기, 백업/복원, 진단 번들
│   │   │   ├── knowledge/   # Excel 지식 베이스 추출 및 파싱
│   │   │   ├── retrieval/   # BM25 텍스트 & Qdrant Pixel RAG 검색
│   │   │   ├── rules/       # 규칙 카탈로그 및 결정론적 검사 엔진
│   │   │   └── storage/     # SQLite DB (SQLAlchemy 2.0, Alembic)
│   │   └── tests/           # 130+ pytest 단위/통합 테스트
│   └── web/                 # React 19 + Vite 프론트엔드 (TypeScript)
│       ├── src/
│       │   ├── app/         # 메인 앱 라우터, 레이아웃, API 클라이언트
│       │   └── features/    # 5개 핵심 기능 화면
│       │       ├── knowledge/ # 지식 가져오기 (/import)
│       │       ├── rules/     # 규칙 카탈로그 (/rules)
│       │       ├── analysis/  # 도면 검사 (/analysis)
│       │       ├── findings/  # 검토 결과 (/findings)
│       │       └── settings/  # 설정 및 백업 (/settings)
│       └── tests/           # Vitest 컴포넌트 및 동작 테스트
├── packages/
│   └── contracts/           # API 공통 계약 및 TypeScript 타입 정의
├── tests/
│   ├── fixtures/            # 비식별 합성 테스트 도면 (PDF/DXF)
│   └── golden/              # 품질 게이트 벤치마크 매니페스트 (TC-101, TC-102)
└── scripts/                 # Windows 실행 및 골든셋 평가 자동화 스크립트
```

---

## 🎯 품질 게이트 및 성능 예산 (Quality Gates)

`DOC-DEVPLAN-001` 및 테스트 계획서(`07.테스트-계획서.md`) 기준 통과 요건:

| 평가 지표 (Metric) | 출시 기준 (Threshold) | 검증 상태 |
| --- | --- | :---: |
| **도면 요소 추출 성공률** | $\ge 95.0\%$ | ✅ 달성 (100.0%) |
| **위반 판정 정밀도 (Precision)** | $\ge 90.0\%$ | ✅ 달성 (100.0%) |
| **위반 판정 재현율 (Recall)** | $\ge 80.0\%$ | ✅ 달성 (100.0%) |
| **근거 검색 Top-5 적중률** | $\ge 80.0\%$ | ✅ 달성 (100.0%) |
| **P95 분석 지연시간** | $\le 180\text{초}$ (PDF 20p / DXF 50MB) | ✅ 달성 (예산 내) |

---

## 🚀 시작하기 (Getting Started)

### 요구 사양 (Prerequisites)
- **OS**: Windows 10/11 (macOS / Linux 개발 환경 지원)
- **Python**: 3.12+ (패키지 매니저: [uv](https://docs.astral.sh/uv/))
- **Node.js**: 20+ (패키지 매니저: [pnpm](https://pnpm.io/))

### 1. 저장소 클론 및 종속성 설치

```bash
git clone https://github.com/greeme99/Dev.Pre-Evaluation.git
cd Dev.Pre-Evaluation

# 백엔드 종속성 설치 (Python venv & packages)
uv sync

# 프론트엔드 종속성 설치
pnpm install
```

### 2. 로컬 개발 서버 실행

**백엔드 API 서버 (FastAPI, 포트 17841):**
```bash
uv run uvicorn dev_pre_review.main:create_app --factory --host 127.0.0.1 --port 17841 --reload
```

**프론트엔드 웹 앱 (Vite 개발 서버):**
```bash
pnpm --filter @dev-pre-review/web dev
```
브라우저에서 `http://localhost:5173`으로 접속합니다. (배포 시 `http://127.0.0.1:17841`로 통합 서비스)

---

## 🧪 테스트 및 품질 검증 (Testing & Quality Gates)

모든 커밋과 PR은 엄격한 품질 게이트를 100% 통과해야 합니다.

### 백엔드 검증 (Lint, Typecheck, Tests)
```bash
# 코드 포맷 및 린트 검사
uv run ruff check apps/api/src apps/api/tests
uv run ruff format --check apps/api/src apps/api/tests

# 정적 타입 검사 (Mypy Strict)
uv run mypy apps/api/src

# 단위 및 통합 테스트 (132개 테스트)
uv run pytest apps/api/tests
```

### 프론트엔드 검증 (Lint, Typecheck, Tests, Build)
```bash
# 단위 및 컴포넌트 테스트
pnpm --filter @dev-pre-review/web test --run

# ESLint 코드 검사
pnpm --filter @dev-pre-review/web lint

# TypeScript 타입 검사
pnpm --filter @dev-pre-review/web typecheck

# 프로덕션 빌드 검증
pnpm --filter @dev-pre-review/web build
```

### 골든셋 벤치마크 평가 (Golden Set Benchmark)
```bash
# Python CLI 실행
PYTHONPATH=apps/api/src uv run python -m dev_pre_review.evaluation.cli \
  --manifest tests/golden/manifest.json \
  --split final \
  --format markdown

# Windows PowerShell 실행
.\scripts\run_golden_evaluation.ps1 -ManifestPath tests\golden\manifest.json -Split final
```

---

## 📚 개발 문서 패키지 (Documentation)

상세 설계 및 요구사항은 `docs/development/` 내 문서 패키지를 참조하십시오:

- [00. 문서 패키지 인덱스](docs/development/00.문서패키지-인덱스.md)
- [01. 요구사항 명세서](docs/development/01.요구사항-명세서.md)
- [02. 제품·기능 명세서](docs/development/02.제품-기능-명세서.md)
- [03. 정보구조·API 명세서](docs/development/03.정보구조-API-명세서.md)
- [04. 와이어프레임](docs/development/04.와이어프레임.md)
- [05. UI 설계 명세서](docs/development/05.UI-설계-명세서.md)
- [06. 점진적 개발 계획서](docs/development/06.점진적-개발-계획서.md)
- [07. 테스트 계획서](docs/development/07.테스트-계획서.md)
- [골든셋 벤치마크 가이드](tests/golden/README.md)
