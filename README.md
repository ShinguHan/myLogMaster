# 고급 로그 분석기 (Advanced Log Analyzer)

## 1. 프로젝트 소개

복잡한 공정 로그(`CSV` 형식)를 분석하기 위해 개발된 전문가용 데스크톱 애플리케이션입니다. SECS/GEM 및 MES 통신 로그를 파싱하고, 다양한 분석 도구를 통해 시스템의 성능 분석 및 문제 해결을 지원합니다.

## 2. 주요 기능

- **강력한 파싱 엔진:** 복잡한 멀티라인 CSV 로그 파싱 및 SECS-II Body 자동 해석
- **실시간 필터링:** 모든 컬럼을 대상으로 하는 빠른 실시간 텍스트 필터링
- **고급 쿼리 빌더:**
  - SQL처럼 다중 조건(AND/OR)을 조합하여 정밀한 필터링 가능
  - 날짜/시간 범위, 정규식(Regex) 등 동적 조건 지원
  - 자주 사용하는 쿼리 조건을 저장하고 다시 불러오는 기능
- **시나리오 기반 검증 엔진:**
  - `scenarios` 폴더에 정의된 정상 업무 흐름(시퀀스, 타임아웃)을 기준으로 로그를 자동 검증
  - 검증 결과 및 실패 원인 리포트
- **스크립트 분석 엔진:**
  - 사용자가 직접 Python 코드를 작성하여 자유롭고 복잡한 분석 수행
  - 분석 결과를 테이블에 하이라이트 표시 (`result.add_marker`)
  - 분석으로 생성된 새로운 데이터를 별도 창으로 표시 (`result.show_dataframe`)
- **시각화 도구:**
  - SECS 통신 시나리오 시퀀스 다이어그램
  - 시나리오 규칙 브라우저

## 3. 설치 및 실행

### 요구사항

- Python 3.10 이상

### 설치

```bash
# 1. 가상 환경 생성 및 활성화
python -m venv venv
# Windows: venv\Scripts\activate
# macOS/Linux: source venv/bin/activate

# 2. 필요한 라이브러리 설치
pip install -r requirements.txt
```

### 4. 프로젝트 구조

main.py: 애플리케이션 실행 파일

app_controller.py: 데이터 처리 및 핵심 로직 담당

main_window.py: 메인 UI 및 이벤트 처리

universal_parser.py: 로그 파싱 엔진

models/: 데이터 모델 (테이블)

dialogs/: 각종 대화상자 UI

scenarios/: 시나리오 검증 규칙 파일 (.json)

filters.json: 저장된 고급 필터 규칙

config.json: UI 설정 저장
