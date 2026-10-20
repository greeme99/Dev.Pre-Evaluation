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

`packaging/windows/models.json`에 정의된 로컬 모델 고지:

1. **Pixel RAG 임베딩 모델 (BGE-Small / MiniLM)**
   - 형식: ONNX
   - 라이선스: Apache 2.0
   - 실행: ONNX Runtime CPU
2. **로컬 제안 생성 모델 (Qwen2.5-Coder-3B-Instruct / Qwen3-4B)**
   - 형식: GGUF (4-bit 양자화)
   - 라이선스: Apache 2.0
   - 실행: llama.cpp CPU 전용 바인딩
