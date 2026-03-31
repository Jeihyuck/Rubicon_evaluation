# Samsung Rubicon QA

https://www.samsung.com/sec/ 공개 페이지에서 로그인 없이 Rubicon 챗 위젯을 열고, 미리 정의된 질문을 입력한 뒤, DOM 우선으로 답변을 추출하고 OpenAI Responses API로 평가하는 Codespaces 실행용 브라우저 QA 프로젝트다.

## 프로젝트 개요

- 대상 URL은 항상 https://www.samsung.com/sec/ 이다.
- 로그인 버튼 클릭, 계정 인증, 세션 우회는 구현하지 않는다.
- 답변 추출은 DOM 우선이며 OCR은 실패 시에만 백업으로 사용한다.
- 실행 명령은 python run.py 이다.
- 결과는 터미널, reports 폴더, artifacts 폴더에서 즉시 확인할 수 있다.

## Codespaces 실행 전제

- Python 3.11 기준으로 작성했다.
- Playwright Chromium이 없으면 실행 시 자동 설치를 시도한다.
- HEADLESS 기본값은 false 이므로 브라우저가 실제로 열리는 장면을 볼 수 있다.

## 실행 방법

OPENAI_API_KEY가 이미 .env 또는 Codespaces 환경변수에 있다면 바로 아래만 실행하면 된다.

```bash
cd samsung-rubicon-qa
pip install -r requirements.txt
python run.py
```

.env 파일이 아직 없다면 아래를 먼저 실행한다.

```bash
cd samsung-rubicon-qa
cp .env.example .env
pip install -r requirements.txt
python run.py
```

OCR fallback을 켜려면 추가로 아래를 설치한다.

```bash
pip install Pillow pytesseract
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-kor
```

## 실행 후 어디서 결과를 보는지

- 터미널: 각 케이스마다 질문, 답변, 추출 소스, overall score, human review 필요 여부, 스크린샷 경로가 출력된다.
- CSV: reports/latest_results.csv
- JSON: reports/latest_results.json
- 요약: reports/summary.md
- 챗 스크린샷: artifacts/chatbox/
- 전체 화면 스크린샷: artifacts/fullpage/
- 비디오: artifacts/video/
- 트레이스: artifacts/trace/

## reports/latest_results.csv 보는 방법

- spreadsheet 도구로 열거나 터미널에서 head reports/latest_results.csv 로 확인한다.

## reports/summary.md 보는 방법

- 마크다운 프리뷰로 열거나 터미널에서 cat reports/summary.md 로 확인한다.

## artifacts/chatbox/ 스크린샷 보는 방법

- 각 케이스별 챗 영역 PNG와 DOM HTML fragment가 저장된다.
- 파일명은 타임스탬프와 case id를 포함한다.

## video / trace 확인 방법

- video 파일은 artifacts/video/*.webm 에 저장된다.
- trace 파일은 artifacts/trace/*.zip 에 저장된다.
- trace 확인 명령:

```bash
playwright show-trace artifacts/trace/<trace-file>.zip
```

## DOM 추출 우선, OCR fallback 정책

- 1순위는 마지막 bot message DOM 추출이다.
- 2순위는 DOM 기반 전체 history 추출이다.
- 3순위는 챗 컨테이너 HTML fragment 저장이다.
- 4순위가 OCR fallback 이다.
- ENABLE_OCR_FALLBACK=false 가 기본값이다.

## 로그인 금지 설계 설명

- 시작 URL은 https://www.samsung.com/sec/ 로 고정된다.
- 허용되지 않은 외부 URL은 설정 단계에서 원래 URL로 되돌린다.
- 로그인 버튼 클릭이나 인증 관련 로직은 구현하지 않았다.
- 평가지침에도 로그인 전용 안내는 감점 대상으로 반영된다.

## selector 수정 방법

챗 UI가 바뀌면 app/samsung_rubicon.py 의 후보 배열을 먼저 조정한다.

- LAUNCHER_CANDIDATES
- INPUT_CANDIDATES
- SEND_BUTTON_CANDIDATES
- BOT_MESSAGE_CANDIDATES
- HISTORY_CANDIDATES
- CONTAINER_CANDIDATES
- LOADING_CANDIDATES

우선순위는 get_by_role, get_by_label, get_by_placeholder, get_by_text, data-testid, aria-label/CSS fallback 순서다.

## iframe 디버깅 방법

- page DOM에서 먼저 입력창을 찾고, 실패하면 page.frames 를 순회한다.
- 가장 높은 점수를 받은 frame을 실제 챗 컨텍스트로 선택한다.
- trace, fullpage 스크린샷, chatbox HTML fragment를 같이 보면 frame 구조를 빠르게 파악할 수 있다.

## 실패 케이스 디버깅 방법

- reports/runtime.log 에서 예외 메시지를 먼저 확인한다.
- reports/summary.md 에서 실패 케이스와 reason을 확인한다.
- artifacts/chatbox/*.html 로 실제 DOM fragment를 확인한다.
- artifacts/chatbox/*.png 와 artifacts/fullpage/*.png 를 함께 비교한다.
- trace 파일을 열어 launcher 클릭, 질문 입력, 답변 대기 구간을 재생한다.

## 금지 사항

- GitHub Actions 생성 금지
- 로그인 시도 금지
- OCR을 기본 추출 경로로 사용하는 변경 금지
- artifact 저장 생략 금지
- 콘솔 출력 생략 금지
- summary 리포트 생략 금지

이 프로젝트의 1차 목표는 Codespaces에서 브라우저를 실제로 열어 질문 입력, 답변 표시, 평가 결과를 사람이 즉시 확인 가능하게 만드는 것이다.
