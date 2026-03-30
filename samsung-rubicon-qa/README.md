# Samsung Rubicon QA

삼성닷컴 공개 영역인 https://www.samsung.com/sec/ 에서 로그인 없이 Rubicon 챗봇을 실제 브라우저 UI로 조작하고, 질문-답변 pair를 수집한 뒤 OpenAI Responses API로 평가하는 QA 및 회귀 테스트 프로젝트다.

이 프로젝트의 핵심은 OCR이 아니라 브라우저 DOM 기반 질문-답변 pair 수집이며, OCR은 DOM 추출 실패 시에만 백업으로 사용한다.

## 프로젝트 개요

- 대상 페이지: https://www.samsung.com/sec/
- 로그인 시도 금지: 로그인 버튼 클릭, 계정 인증 플로우 진입, 세션 우회 로직을 구현하지 않는다.
- 수집 방식: DOM 텍스트 추출 우선, 실패 시에만 OCR fallback 사용
- 증적 보존: 전체 페이지 스크린샷, 챗 영역 스크린샷, Playwright video, Playwright trace 저장
- 평가 방식: OpenAI Responses API Structured Outputs(JSON Schema)

## 디렉터리 구조

```text
samsung-rubicon-qa/
├─ app/
│  ├─ __init__.py
│  ├─ main.py
│  ├─ config.py
│  ├─ logger.py
│  ├─ models.py
│  ├─ csv_loader.py
│  ├─ browser.py
│  ├─ samsung_rubicon.py
│  ├─ dom_extractor.py
│  ├─ ocr_fallback.py
│  ├─ evaluator.py
│  ├─ report_writer.py
│  └─ utils.py
├─ testcases/
│  └─ questions.csv
├─ artifacts/
│  ├─ fullpage/
│  ├─ chatbox/
│  ├─ video/
│  └─ trace/
├─ reports/
├─ .github/workflows/
│  └─ samsung-rubicon-qa.yml
├─ .env.example
├─ .gitignore
├─ requirements.txt
├─ README.md
└─ run.py
```

## 동작 흐름

1. https://www.samsung.com/sec/ 접속
2. 팝업 또는 배너가 챗 UI를 가리면 닫기
3. 우하단 Rubicon 아이콘 또는 챗 런처 찾기
4. page DOM 우선, 실패 시 iframe 순회로 채팅 컨텍스트 찾기
5. 질문 입력 후 전송
6. 마지막 bot message가 안정화될 때까지 대기
7. DOM 기반으로 질문-답변 pair 추출
8. 전체 페이지, 챗 박스 스크린샷 저장
9. video 및 trace 저장
10. OpenAI로 구조화 평가 수행
11. JSON, CSV, Markdown 리포트 생성

## 로컬 실행 방법

### 1) 가상환경 생성

```bash
cd samsung-rubicon-qa
python3.11 -m venv .venv
source .venv/bin/activate
```

### 2) 의존성 설치

```bash
pip install --upgrade pip
pip install -r requirements.txt
playwright install --with-deps chromium
```

OCR fallback을 실제로 쓰는 경우에만 추가 의존성을 설치한다.

```bash
pip install Pillow pytesseract
```

그리고 시스템에 tesseract가 있어야 한다.

```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-kor
```

### 3) 환경변수 설정

```bash
cp .env.example .env
```

필수 항목:

- OPENAI_API_KEY

### 4) 실행

```bash
python run.py
```

## Playwright 설치 방법

Playwright 브라우저는 Python 패키지 설치와 별도로 설치해야 한다.

```bash
playwright install --with-deps chromium
```

## GitHub Actions 설정 방법

워크플로 파일은 .github/workflows/samsung-rubicon-qa.yml 이다.

- workflow_dispatch 수동 실행 지원
- schedule 일일 실행 지원
- ubuntu-latest 에서 Python 3.11 사용
- Chromium 설치 후 python run.py 실행
- 실패해도 artifacts/reports 업로드

## Secrets 설정 방법

GitHub 저장소 Settings > Secrets and variables > Actions 에서 아래를 추가한다.

- OPENAI_API_KEY

## CSV 작성 방법

testcases/questions.csv 컬럼:

- id
- category
- locale
- page_url
- question
- expected_keywords
- forbidden_keywords

복수 키워드는 | 로 구분한다.

## DOM 추출 우선 / OCR fallback 정책

- 1순위: 마지막 bot message DOM 텍스트
- 2순위: message history DOM 추출
- 3순위: chat HTML fragment 저장
- 4순위: OCR fallback

DOM 추출에 성공하면 OCR은 수행하지 않는다.

## 결과 파일 설명

- reports/latest_results.json: 전체 실행 결과 배열
- reports/latest_results.csv: 평탄화된 결과 테이블
- reports/summary.md: 사람이 읽기 좋은 요약 리포트
- reports/runtime.log: 런타임 로그

## video / trace 확인 방법

- video: artifacts/video/
- trace: artifacts/trace/

trace는 아래 명령으로 볼 수 있다.

```bash
playwright show-trace artifacts/trace/<trace-file>.zip
```

## selector 수정 방법

챗 UI 구조가 바뀌면 app/samsung_rubicon.py 의 후보 배열을 먼저 수정한다.

- LAUNCHER_CANDIDATES
- INPUT_CANDIDATES
- SEND_BUTTON_CANDIDATES
- BOT_MESSAGE_CANDIDATES
- HISTORY_CANDIDATES
- CONTAINER_CANDIDATES
- LOADING_CANDIDATES

## iframe 디버깅 방법

- page DOM에서 입력창이 안 잡히면 iframe 내부인지 확인한다.
- app/samsung_rubicon.py 의 _iter_scopes 와 resolve_chat_context 를 기준으로 frame 순회를 점검한다.
- trace와 chatbox 스크린샷을 함께 확인한다.

## OpenAI 비용 주의사항

- 질문 수가 많을수록 평가 비용이 증가한다.
- MAX_QUESTIONS 값을 낮춰 점진적으로 검증하는 편이 안전하다.

## 실서비스 자동화 주의사항

- 공개 영역만 대상으로 한다.
- 로그인, 세션 우회, 인증 플로우 자동화는 구현하지 않는다.
- 팝업, iframe, selector 변경에 민감하므로 주기적 유지보수가 필요하다.

## 병렬 실행 최소화 권고

이 프로젝트는 실서비스 브라우저 UI를 실제로 조작하므로 병렬 실행을 최소화하는 편이 안정적이다. 기본 구현은 케이스를 순차 실행한다.
