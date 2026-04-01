# Samsung Rubicon QA

삼성닷컴 공개 영역인 https://www.samsung.com/sec/ 에서 로그인 없이 Rubicon 챗봇을 실제 브라우저 UI로 조작하고, 질문-답변 pair를 수집한 뒤 OpenAI Responses API로 평가하는 QA 및 회귀 테스트 프로젝트다.

이 프로젝트의 핵심은 OCR이 아니라 브라우저 DOM 기반 질문-답변 pair 수집이며, OCR은 DOM 추출 실패 시에만 백업으로 사용한다.

## 프로젝트 개요

- 대상 페이지: https://www.samsung.com/sec/
- 로그인 시도 금지: 로그인 버튼 클릭, 계정 인증 플로우 진입, 세션 우회 로직을 구현하지 않는다.
- 수집 방식: DOM 텍스트 추출 우선, 실패 시에만 OCR fallback 사용
- 증적 보존: 전체 페이지 스크린샷, 챗 박스 스크린샷, Playwright video, Playwright trace 저장
- 평가 방식: OpenAI Responses API Structured Outputs(JSON Schema)
- 질문 입력 검증: DOM 값 확인 후에만 전송 — 검증 실패 시 평가 미실시

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
2. 한국어 폰트 CSS 주입 (Noto Sans KR / Nanum Gothic)
3. 팝업 또는 배너가 챗 UI를 가리면 닫기
4. 우하단 Rubicon 아이콘 또는 챗 런처 찾기
5. page DOM 우선, 실패 시 iframe 순회로 채팅 컨텍스트 찾기
6. **챗 열림 직후 스크린샷 저장** (`{case}_opened.png`)
7. **질문 입력 (4단계 전략: fill → press_sequentially → keyboard → JS)**
8. **DOM 값 검증으로 입력 성공 확인**
9. **입력 성공 시에만** `{case}_before_send.png` 저장 후 전송
10. 마지막 bot message가 안정화될 때까지 대기
11. **답변 완료 후 스크린샷 저장** (`{case}_after_answer.png`)
12. DOM 기반으로 질문-답변 pair 추출
13. video 및 trace 저장
14. 입력 검증 성공 케이스만 OpenAI 평가 수행
15. JSON, CSV, Markdown 리포트 생성

## 로컬 실행 방법

### 1) 가상환경 생성

```bash
cd samsung-rubicon-qa
python3.11 -m venv .venv
source .venv/bin/activate
```

### 2) 한국어 폰트 설치 (Ubuntu/Codespaces)

챗 위젯 한글 깨짐 방지를 위해 반드시 설치한다.

```bash
sudo apt-get update
sudo apt-get install -y fonts-noto-cjk fonts-nanum
fc-cache -f -v
```

폰트가 정상 설치됐는지 확인:

```bash
fc-list | grep -i "Noto Sans KR\|Nanum"
```

### 3) 의존성 설치

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

### 4) 환경변수 설정

```bash
cp .env.example .env
```

필수 항목:

- OPENAI_API_KEY

### 5) 실행 전 체크리스트

```bash
# API 키 확인
grep OPENAI_API_KEY .env

# 폰트 확인
fc-list | grep -i "Noto Sans KR\|Nanum"

# Playwright 확인
playwright --version
```

### 6) 실행

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
- **한국어 폰트 자동 설치** (fonts-noto-cjk, fonts-nanum)
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

## 질문 입력 검증 필요 이유

챗봇 UI에 `fill()` 한 번 호출했다고 해서 텍스트가 실제로 입력창에 들어갔다는 보장이 없다.
특히 Sprinklr / Rubicon 같은 커스텀 위젯은 아래 케이스에서 `fill()`이 동작하지 않을 수 있다.

- `contenteditable` 기반 입력창 (Playwright `fill`이 값 미반영)
- React/Vue SPA에서 상태가 update되지 않은 경우
- iframe 내부 포커스 문제

**입력 실패 상태에서 답변을 평가하면 챗봇의 기본 응대 문구나 이전 답변이 평가 대상이 되어 결과를 신뢰할 수 없다.**

따라서 이 프로젝트는 4단계 전략을 순서대로 시도하고, 각 단계마다 DOM 값을 읽어서 일치 여부를 확인한다:

| 단계 | 방법 | 설명 |
|------|------|------|
| 1 | `locator.fill()` | 가장 빠르고 안정적 |
| 2 | `locator.press_sequentially()` | 한 글자씩 타이핑, 비디오에 보임 |
| 3 | `page.keyboard.type()` | 포커스 후 직접 키보드 입력 |
| 4 | JavaScript 직접 주입 | 최후 수단 |

검증 실패 시 전송하지 않고 케이스를 `failed`로 마킹한다.

## 질문 입력 스크린샷 확인 방법

케이스별로 세 단계 스크린샷이 저장된다.

```text
artifacts/chatbox/{timestamp}_{case_id}_opened.png       # 챗 열림 직후
artifacts/chatbox/{timestamp}_{case_id}_before_send.png  # 질문 입력 직후, 전송 전
artifacts/chatbox/{timestamp}_{case_id}_after_answer.png # 답변 완료 후
artifacts/fullpage/{timestamp}_{case_id}_opened.png
artifacts/fullpage/{timestamp}_{case_id}_before_send.png
artifacts/fullpage/{timestamp}_{case_id}_after_answer.png
```

`before_send.png`가 가장 중요한 증거다. 이 파일에서 입력창에 질문 텍스트가 보여야 한다.

## 한글 폰트 설치 방법 및 깨짐 점검

### 설치

```bash
sudo apt-get install -y fonts-noto-cjk fonts-nanum
fc-cache -f -v
```

### 깨짐 발생 시 체크

1. `fc-list | grep -i "Noto\|Nanum"` — 폰트 설치 여부
2. `before_send.png`에서 한글이 □□□로 표시되면 폰트 문제
3. 브라우저 컨텍스트에 `locale="ko-KR"` 적용 여부 확인 (`app/browser.py`)
4. `app/samsung_rubicon.py`의 `inject_korean_font()` 호출 여부 확인

### 원리

- `inject_korean_font()` 함수가 페이지와 모든 프레임에 CSS를 주입
- `font-family: "Noto Sans KR", "Noto Sans CJK KR", "Nanum Gothic", sans-serif`
- 시스템에 해당 폰트가 없으면 CSS 주입이 있어도 깨질 수 있으므로 폰트 설치가 필수

## contenteditable 입력 처리 방식

Sprinklr / Rubicon 챗 위젯은 `<input>` 또는 `<textarea>` 대신 `contenteditable="true"` 요소를 사용할 수 있다.

차이:
- `input/textarea`: `input_value()` 로 현재 값 읽기 가능
- `contenteditable`: `inner_text()` 또는 `text_content()` 로 읽어야 함

`_detect_input_type()` 함수가 자동으로 타입을 판별하고 검증 방식을 선택한다.

## Sprinklr iframe 입력 실패 시 디버깅

```bash
# 1. HEADLESS=false 로 실행해서 눈으로 확인
HEADLESS=false python run.py

# 2. trace로 locator 탐색 경로 확인
playwright show-trace artifacts/trace/<trace-file>.zip

# 3. Playwright Inspector 사용
PWDEBUG=1 python run.py
```

Playwright Inspector (`PWDEBUG=1`)는 브라우저를 천천히 실행하며 각 액션을 inspector 창에서 확인할 수 있다. locator가 제대로 잡히는지 대화형으로 테스트할 수 있다.

## 결과 JSON 필드 설명

`reports/latest_results.json`의 `pair` 섹션에는 아래 필드가 추가됐다.

| 필드 | 타입 | 설명 |
|------|------|------|
| `input_verified` | bool | DOM 기준 입력 텍스트 확인 성공 여부 |
| `input_method_used` | string | 실제로 사용된 입력 방식 (`fill`, `press_sequentially`, `keyboard`, `js`) |
| `before_send_screenshot_path` | string | 전송 전 챗박스 스크린샷 경로 |
| `font_fix_applied` | bool | 한국어 폰트 CSS 주입 성공 여부 |

## DOM 추출 우선 / OCR fallback 정책

- 1순위: 마지막 bot message DOM 텍스트
- 2순위: message history DOM 추출
- 3순위: chat HTML fragment 저장
- 4순위: OCR fallback

DOM 추출에 성공하면 OCR은 수행하지 않는다.

OCR fallback을 사용하는 경우 한국어 언어 옵션이 적용된다.

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
