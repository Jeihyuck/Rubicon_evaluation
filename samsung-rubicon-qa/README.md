# Samsung Rubicon QA

이 프로젝트는 GitHub PR 댓글 응답 agent가 아니다.
이 프로젝트는 실제 삼성닷컴 상담 챗창 질문-답변 실행 agent다.

대상은 공개 페이지인 <https://www.samsung.com/sec/> 뿐이며, 로그인 자동화는 구현하지 않는다. 목표는 Codespaces 안에서 실제 브라우저를 띄우고 우측 하단 루비콘 아이콘을 눌러 챗봇을 연 뒤, 질문을 실제로 입력하고, 새 답변만 저장하고, 그 실제 답변만 OpenAI로 평가하는 것이다.

사용자가 결과를 볼 때 가장 먼저 봐야 할 파일은 reports/latest_conversation.md 이다.
이 파일에 질문, 입력 검증 여부, 새 응답 여부, 실제 답변, 평가 결과, 스크린샷 경로를 모두 기록하라.
before_send 스크린샷은 질문 입력 성공 증거다.
after_send 스크린샷은 제출 효과 증거다.
after_answer 스크린샷은 새 답변 생성 증거다.
mock answer나 simulated result는 절대 생성하지 않는다.
DOM 값 변경만으로는 질문 제출 성공이 아니다.
js 입력은 임시 fallback이며 신뢰도가 낮다.
가장 중요한 것은 submit_effect_verified 와 new_bot_response_detected 다.
비디오는 저장하지 않는다.
긴 답변은 챗창 내부를 스크롤하며 여러 장으로 캡처한다.
실제 저장용 답변 원본은 DOM에서 추출한 answer_raw, answer_normalized 다.

## 결과 확인 순서

1. reports/latest_conversation.md
2. reports/latest_results.json
3. reports/latest_results.csv
4. reports/summary.md
5. artifacts/chatbox/*_before_send.png 와 artifacts/chatbox/*_after_answer.png

콘솔 로그도 같은 우선순위로 결과 경로를 출력한다.

## 프로젝트 구조

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
├─ .env.example
├─ .gitignore
├─ requirements.txt
├─ README.md
└─ run.py
```

## 실행 환경

기본 실행 환경은 Codespaces 다. 기본값은 아래와 같다.

- HEADLESS=false
- DEFAULT_LOCALE=ko-KR
- ENABLE_VIDEO=false
- ENABLE_TRACE=false
- ENABLE_OCR_FALLBACK=false

즉, python run.py 한 줄로 실행했을 때 사람이 브라우저를 직접 볼 수 있어야 한다.

## 사전 준비

### 1. 가상환경

```bash
cd samsung-rubicon-qa
python3 -m venv .venv
source .venv/bin/activate
```

### 2. 한글 폰트 설치

Codespaces에서 한글이 깨지지 않도록 아래 명령을 먼저 실행한다.

```bash
sudo apt-get update
sudo apt-get install -y fonts-noto-cjk fonts-nanum
fc-cache -f -v
```

### 3. 의존성 설치

```bash
pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install chromium
```

브라우저 바이너리가 없으면 앱이 실행 중 자동으로 한 번 더 설치를 시도한다.

### 4. 환경 변수

```bash
cp .env.example .env
```

필수 값은 OPENAI_API_KEY 다.

## 실행 방법

```bash
python run.py
```

디버깅이 필요하면 headed Inspector 모드로 실행한다.

```bash
PWDEBUG=1 python run.py
```

## 실제 실행 흐름

프로그램은 아래 순서를 따른다.

1. <https://www.samsung.com/sec/> 접속
2. 한국어 폰트 fallback CSS 주입
3. 팝업, 쿠키, 배너 등 챗 UI를 가리는 요소 닫기
4. 우측 하단 루비콘 아이콘 탐색 및 클릭
5. page DOM에서 입력창 탐색
6. 없으면 page.frames 순회로 iframe 안 입력창 탐색
7. 챗이 열리면 opened 스크린샷 저장
8. 질문 입력 시 press_sequentially -> keyboard.type -> fill -> JS fallback 순서로 시도
9. DOM input state 검증
10. before_send 스크린샷 저장
11. send button click -> input Enter -> page Enter -> active element Enter 순서로 제출 시도
12. after_send 스크린샷 저장
13. input clear, user echo, history 변화, visible text 변화 등 submit effect 검증
14. 질문 전 baseline bot message 개수와 baseline text snapshot 기록
15. 전송 후 bot count 증가 또는 baseline 에 없던 bot text 출현을 새 응답 후보로 인정
16. baseline 이후 새 응답이 안정화되면 after_answer 스크린샷 저장
17. submit_effect_verified 와 new_bot_response_detected 가 모두 참일 때만 질문/답변 pair 를 평가

## 입력 검증 규칙

질문 입력 성공은 DOM 값 변경만으로 인정하지 않는다.

질문 입력 및 제출 성공으로 인정되려면 아래가 반드시 참이어야 한다.

1. input_dom_verified 가 True 다.
2. submit_effect_verified 가 True 다.
3. before_send 스크린샷이 실제로 저장된다.

추가 검증:

- 가능하면 전송 후 user message echo 가 chat history 에 나타나는지 확인한다.
- user echo 가 없어도 submit_effect_verified 와 new_bot_response_detected 가 함께 참이면 통과할 수 있다.

입력 검증이 실패하면 status 는 invalid_capture 이며, OpenAI 평가는 진행하지 않는다.

현재 실패의 본질은 입력창 DOM 값 변경과 실제 질문 제출을 동일하게 취급한 데 있다. 앞으로는 submit effect가 검증되지 않으면 질문 제출 성공으로 간주하지 말고 invalid_capture로 처리하라.

js fallback으로 input value만 바뀐 경우는 가짜 성공일 수 있다. send button 활성화, input clear, user echo, history 변화, new bot response 중 최소 핵심 신호가 있어야만 실제 질문 제출 성공으로 간주하라.

## 새 답변 감지 규칙

초기 메뉴나 웰컴 문구를 질문 답변으로 채택하면 안 된다.

- 질문 전 baseline bot message 개수를 기록한다.
- 질문 전 baseline bot text snapshot 을 기록한다.
- 질문 후 current_count > baseline_bot_count 일 때만 새 응답 후보를 인정한다.
- 아래 텍스트만 보이면 baseline menu 로 간주한다.

```text
아래에서 원하는 항목을 선택해 주세요
구매 상담사 연결
주문·배송 조회
모바일 케어플러스
가전 케어플러스
서비스 센터
FAQ
```

새 bot response 가 baseline 과 동일하거나 baseline 메뉴만 보이면 invalid_capture 로 처리한다.

## 저장 파일

필수 아티팩트:

```text
artifacts/chatbox/{timestamp}_{case}_opened.png
artifacts/chatbox/{timestamp}_{case}_before_send.png
artifacts/chatbox/{timestamp}_{case}_after_send.png
artifacts/chatbox/{timestamp}_{case}_after_answer.png
artifacts/fullpage/{timestamp}_{case}_opened.png
artifacts/fullpage/{timestamp}_{case}_before_send.png
artifacts/fullpage/{timestamp}_{case}_after_send.png
artifacts/fullpage/{timestamp}_{case}_after_answer.png
```

긴 답변은 필요 시 아래처럼 여러 장으로 저장한다.

```text
artifacts/chatbox/{timestamp}_{case}_after_answer_part_01.png
artifacts/chatbox/{timestamp}_{case}_after_answer_part_02.png
artifacts/chatbox/{timestamp}_{case}_after_answer_final.png
```

## 결과 파일

### reports/latest_conversation.md

메인 결과 파일이다. 각 케이스별로 아래를 기록한다.

- 질문
- Input DOM Verified
- Submit Effect Verified
- 입력 검증 여부
- 입력 방식
- 제출 방식
- 질문 echo 여부
- 새 응답 감지 여부
- baseline menu 감지 여부
- 실제 답변
- answer_raw
- extraction_source
- 평가 결과
- opened, before_send, after_send, after_answer 스크린샷 경로
- answer_screenshot_paths, html fragment 경로

콘솔도 케이스마다 아래 순서로 출력한다.

```text
==================================================
CASE: case01
QUESTION: 갤럭시 S24 배터리 교체는 어디서 할 수 있나요?
INPUT DOM VERIFIED: True
SUBMIT EFFECT VERIFIED: True
INPUT VERIFIED: True
INPUT METHOD: press_sequentially
SUBMIT METHOD USED: button_click
USER MESSAGE ECHO VERIFIED: True
NEW BOT RESPONSE DETECTED: True
BASELINE MENU DETECTED: False
ANSWER: ...
OVERALL SCORE: 0.84
NEEDS HUMAN REVIEW: False
CHECK FIRST: reports/latest_conversation.md
BEFORE SEND SCREENSHOT: artifacts/chatbox/..._before_send.png
AFTER ANSWER SCREENSHOTS: artifacts/chatbox/..._after_answer_part_01.png, artifacts/chatbox/..._after_answer_final.png
==================================================
```

### reports/latest_results.json

최소 아래 필드를 포함한다.

```json
{
  "run_timestamp": "",
  "case_id": "",
  "category": "",
  "page_url": "https://www.samsung.com/sec/",
  "question": "",
  "answer": "",
  "answer_raw": "",
  "answer_normalized": "",
  "input_dom_verified": false,
  "submit_effect_verified": false,
  "input_verified": false,
  "input_method_used": "",
  "submit_method_used": "",
  "user_message_echo_verified": false,
  "new_bot_response_detected": false,
  "baseline_menu_detected": false,
  "status": "",
  "error_message": "",
  "reason": "",
  "fix_suggestion": "",
  "message_history": [],
  "html_fragment_path": "",
  "extraction_source": "dom",
  "ocr_text": "",
  "ocr_confidence": 0.0,
  "before_send_screenshot_path": "",
  "after_send_screenshot_path": "",
  "after_answer_screenshot_path": "",
  "answer_screenshot_paths": [],
  "after_answer_multi_page": false,
  "full_screenshot_path": "",
  "overall_score": 0.0,
  "needs_human_review": true
}
```

## 상태값 정의

- success: 질문 입력 검증 성공, 새 bot response 감지 성공, 답변 추출 성공, 평가 완료
- failed: locator 실패, 타임아웃, 예외 등 일반 실패
- invalid_capture: 질문 입력 검증 실패, before_send 증적 부재, 새 응답 감지 실패, baseline 메뉴만 추출된 경우

invalid_capture 에서는 GPT 정상 평가는 건너뛰고 fallback 평가만 남긴다.

## Debugging Disabled Composer

Sprinklr 챗 UI는 footer가 열려 있어도 실제 composer가 ready 상태가 아닐 수 있다.
이 프로젝트는 이제 disabled textarea를 입력 실패의 증거로만 남기고, 최종 입력 대상은 Grade A/B editable 후보로만 제한한다.

핵심 확인 순서:

1. reports/latest_conversation.md 의 Input Candidates 섹션에서 top candidate가 disabled인지 본다.
2. reports/runtime.log 에서 ` [INPUT_V2][FRAME_INVENTORY] `, ` [INPUT_V2][RANKED_CANDIDATES] `, ` [SPR][ACTIVATION] ` 로그를 본다.
3. opened_footer 스크린샷에서 footer만 열린 상태인지, before_send 스크린샷에서 실제 입력값이 보이는지 확인한다.

## Meaning of invalid_capture

invalid_capture 는 단순 locator miss가 아니라, 열린 footer와 실제 제출 가능한 composer를 구분하지 못했거나, 제출 증거가 부족한 경우를 뜻한다.

주요 분류:

- top_candidate_disabled
- no_editable_candidate_after_rescan
- failover_exhausted
- user_echo_not_found

반대로 answer_not_extracted 는 입력과 전송 이후 응답을 얻지 못한 케이스라 failed 로 남길 수 있다.

## latest_conversation.md 보는 법

최우선 확인 파일은 reports/latest_conversation.md 다.

케이스별로 아래를 한 번에 본다.

- Open Method Used
- SDK Status
- Availability Status
- Input Scope / Input Selector / Input Candidate Score
- Top Candidate Disabled
- Activation Attempted / Activation Steps Tried
- Failover Attempts / Final Input Target Frame
- Input Failure Category / Input Failure Reason
- Actual Answer / Answer Raw / Extraction Source

## opened_footer / before_send / after_answer 스크린샷 의미

- opened_footer: 챗 footer가 열렸는지, 아직 disabled shell 인지 확인하는 증거
- before_send: 최종 입력 후보에 질문 텍스트가 실제 반영됐는지 확인하는 증거
- after_answer: baseline 이후 새 bot 응답이 실제로 생성됐는지 확인하는 증거

opened_footer 는 open 성공과 composer ready 를 분리해서 보는 용도다.
before_send 가 없거나 비어 있으면 제출 이전 캡처가 부족한 것이다.
after_answer 가 없거나 answer_not_extracted 로 끝나면 입력은 됐어도 실제 응답 확보에는 실패한 것이다.

## runtime.log 핵심 prefix

다음 prefix 순서대로 보면 어디서 멈췄는지 빠르게 알 수 있다.

- ` [SPR][SDK_STATUS] `
- ` [SPR][OPEN][TRY] `
- ` [SPR][OPEN][FALLBACK] `
- ` [SPR][OPEN][OK] `
- ` [SPR][OPEN][FAIL] `
- ` [SPR][AVAILABILITY][SUBSCRIBED] `
- ` [SPR][AVAILABILITY][STATE] `
- ` [INPUT_V2][FRAME_INVENTORY] `
- ` [INPUT_V2][RANKED_CANDIDATES] `
- ` [SPR][ACTIVATION][START] `
- ` [SPR][ACTIVATION][CLICK] `
- ` [SPR][ACTIVATION][STATE] `
- ` [SPR][ACTIVATION][SUCCESS] `
- ` [SPR][ACTIVATION][EXHAUSTED] `
- ` [INPUT_V2][FAILOVER][TRY] `
- ` [INPUT_V2][FAILOVER][SUCCESS] `
- ` [INPUT_V2][FAILOVER][EXHAUSTED] `
- ` [INPUT_V2][ECHO][FOUND] `
- ` [INPUT_V2][ECHO][NOT_FOUND] `
- ` [ARTIFACT][SAVE] `

## 실패 판정 기준

아래 중 하나면 invalid_capture 또는 failed 로 판정한다.

1. 루비콘 아이콘 또는 입력창을 찾지 못함
2. 질문 DOM 값 검증 실패
3. before_send 스크린샷 저장 실패
4. 전송 후 current_count > baseline_bot_count 를 만족하는 새 응답이 없음
5. baseline 메뉴만 다시 보임
6. 새 답변 텍스트 추출 실패
7. Playwright 예외, 타임아웃, locator actionability 실패

## Playwright Inspector와 Trace

Playwright를 버리는 것이 아니라, headed 모드와 증적 저장을 강화하는 것이 이 프로젝트의 방향이다.

### Inspector

```bash
PWDEBUG=1 python run.py
```

확인 포인트:

1. 루비콘 아이콘 locator 가 실제로 잡히는지
2. 입력창이 page DOM 인지 iframe 인지
3. fill 과 press_sequentially 중 어떤 전략이 먹는지
4. before_send 시점에 입력창 DOM 값과 화면 표시가 일치하는지

### Trace Viewer

정상 경로에서는 trace를 저장하지 않는다. 아래는 디버깅 모드에서 수동으로 ENABLE_TRACE=true 로 켰을 때만 사용한다.

```bash
playwright show-trace artifacts/trace/<trace-file>.zip
```

확인 포인트:

1. locator actionability 오류
2. iframe 내부 전환 시점
3. send 클릭 이후 bot message 개수 증가 여부

## selector 수정 포인트

챗 UI 구조가 바뀌면 아래 후보 배열을 우선 수정한다.

- app/samsung_rubicon.py 의 LAUNCHER_CANDIDATES
- app/samsung_rubicon.py 의 INPUT_CANDIDATES
- app/samsung_rubicon.py 의 SEND_BUTTON_CANDIDATES
- app/samsung_rubicon.py 의 BOT_MESSAGE_CANDIDATES
- app/samsung_rubicon.py 의 USER_MESSAGE_CANDIDATES
- app/samsung_rubicon.py 의 HISTORY_CANDIDATES
- app/samsung_rubicon.py 의 CONTAINER_CANDIDATES
- app/samsung_rubicon.py 의 LOADING_CANDIDATES

우선 page DOM 기준으로 조정하고, 다음으로 iframe 내부 locator 를 조정한다.

## 테스트

```bash
pytest
```

## 한 줄 결론

어제 페이지와 챗봇이 뜬 건 Playwright가 완전히 틀린 선택이 아니라는 신호이고, 지금 필요한 건 Playwright를 버리는 게 아니라 Codespaces에서 headed 모드로 입력 검증과 새 응답 감지를 강하게 만드는 것이다.
