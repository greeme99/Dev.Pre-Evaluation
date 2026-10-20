# 오픈소스 컴포넌트 및 모델 라이선스 안내 (Model & Open-Source Licenses)

본 문서는 **Dev.Pre-Evaluation**에 사용된 주요 오픈소스 라이브러리 및 모델의 라이선스 고지 사항을 담고 있습니다.

---

## 1. 핵심 파서 및 엔진 라이브러리

| 컴포넌트명 | 버전 | 라이선스 | 용도 |
| --- | --- | --- | --- |
| **PyMuPDF** | $\ge 2.0$ | GNU AGPL v3 / Commercial | PDF 벡터/텍스트 파싱 및 고해상도 래스터화 |
| **ezdxf** | $\ge 1.4.5$ | MIT License | DXF 도면 파싱 및 레이어/엔티티 추출 |
| **FastAPI** | $\ge 0.115.0$ | MIT License | 로컬 REST API 프레임워크 |
| **SQLAlchemy** | $\ge 2.0.0$ | MIT License | 데이터베이스 ORM 및 스키마 관리 |
| **Qdrant Client** | $\ge 1.11.0$ | Apache 2.0 | 임베디드 시각/텍스트 벡터 저장소 |
| **cryptography** | $\ge 43.0.0$ | Apache 2.0 / BSD | AES-256-GCM 패키지 암호화 |
| **argon2-cffi** | $\ge 23.1.0$ | MIT License | Argon2id 키 유도 함수 |
| **openpyxl** | $\ge 3.1.0$ | MIT License | Excel 지식 사례 가져오기 및 내보내기 |

---

## 2. 모델 매니페스트 및 로컬 AI 모델

`packaging/windows/models.json`에 현재 후보로 선언된 모델은 다음과 같습니다.

| 용도 | Manifest 이름 | 형식·런타임 | Manifest 라이선스 | 검증 상태 |
| --- | --- | --- | --- | --- |
| OCR | PaddleOCR-Korean-Mobile | ONNX | Apache-2.0 | URL·revision·SHA-256 미검증 |
| 텍스트 임베딩 | intfloat/multilingual-e5-small | ONNX | MIT | URL·revision·SHA-256 미검증 |
| 시각 임베딩 | openai/clip-vit-base-patch32 | ONNX | MIT | URL·revision·SHA-256 미검증 |
| 로컬 제안 생성 | Qwen3-4B-Instruct-GGUF | GGUF·llama.cpp | Apache-2.0 | URL·revision·SHA-256 미검증 |

현재 manifest 값은 배포 후보를 기술하는 placeholder이며 설치 파일에 모델 바이너리가
포함됐거나 오프라인 실행이 검증됐다는 의미가 아닙니다. 출시 전 각 모델의 실제 저장소,
immutable revision, 라이선스 원문, 파일 크기와 SHA-256을 독립적으로 확인하고 별도
라이선스/SBOM 보고서에 기록해야 합니다.
