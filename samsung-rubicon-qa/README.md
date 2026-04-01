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

---

## 왜 질문 입력 검증이 필요한가

단순히 `fill()` 또는 `type()`을 호출한 후 바로 전송하면, 실제로 텍스트가 입력창에 들어가지 않아도 전송이 실행될 수 있다. 특히 Sprinklr/Rubicon 위젯처럼 `contenteditable` 또는 커스텀 React controlled input인 경우 DOM 값이 비어 있는 채로 전송이 돼버린다.

따라서 이 프로젝트는 다음 순서로 입력을 시도하고, 각 단계마다 DOM 값을 직접 검증한 뒤 성공 시에만 다음 단계로 진행한다.

1. `locator.fill()` → DOM 값 검증
2. `locator.press_sequentially()` (40ms 딜레이, 시각적 타이핑) → DOM 값 검증
3. `locator.click()` + `page.keyboard.type()` → DOM 값 검증
4. JavaScript `element.value = ...` + event dispatch (최후 수단) → DOM 값 검증

모든 방식이 실패하면 예외를 발생시켜 해당 케이스를 `status=failed`로 처리하고, LLM 평가를 건너뛴다.

## 질문 입력 직전 스크린샷 확인

질문이 입력창에 들어간 직후, 전송 버튼을 누르기 전에 아래 두 스크린샷이 저장된다.

- `artifacts/chatbox/{timestamp}_{case_id}_before_send.png` — 챗 영역
- `artifacts/fullpage/{timestamp}_{case_id}_before_send.png` — 전체 페이지

이 스크린샷에서 입력창에 질문 텍스트가 보이면 실제 입력이 성공한 증거다.

결과 JSON/CSV에서 `before_send_screenshot_path` 필드로 경로를 확인할 수 있다.

## 한 케이스당 최소 3단계 증적

| 단계 | 파일 suffix | 의미 |
|------|-------------|------|
| 챗 위젯 열린 직후 | `_opened.png` | 입력창이 보이는 상태 |
| 질문 입력 직후 전송 전 | `_before_send.png` | 질문 텍스트가 입력창에 들어간 증거 |
| 답변 완료 후 | `_answered.png` | 챗봇 응답이 표시된 상태 |

## 한국어 폰트 설치 방법 (Codespaces/Ubuntu)

챗 위젯에서 한글이 전히 깨지는 경우 아래를 실행하라.

```bash
sudo apt-get update
sudo apt-get install -y fonts-noto-cjk fonts-nanum
fc-cache -f -v
```

폰트 설치 확인:

```bash
fc-list | grep -i "Noto Sans KR\|Nanum"
```

브라우저 locale은 `browser.py`에서 `locale="ko-KR"`, `timezone_id="Asia/Seoul"`로 고정 설정되어 있다.

추가로, 페이지 로드 후 아래 CSS가 자동 주입된다.

```css
* {
  font-family: "Noto Sans KR", "Noto Sans CJK KR", "Nanum Gothic", "Apple SD Gothic Neo", sans-serif !important;
}
```

이 CSS는 메인 페이지와 챗 프레임에 각각 주입을 시도한다.

## 한글 깨짐 발생 시 점검법

1. 폰트 설치 여부 확인: `fc-list | grep -i "Noto\|Nanum"`
2. 결과 JSON에서 `font_fix_applied` 필드 확인 — `true`여야 정상
3. `_before_send.png` 스크린샷에서 한글이 보이는지 확인
4. runtime.log에서 `[FONT]` 로그 라인 확인

## 입력창이 contenteditable일 때의 처리 방식

Sprinklr 위젯은 `<div contenteditable="true">` 구조를 사용하는 경우가 있다. 이 경우:

- `input_value()`는 작동하지 않으므로 `inner_text()` 또는 `text_content()`로 검증한다.
- `fill()`은 Playwright가 contenteditable을 지원하므로 1차 시도에서 동작할 수 있다.
- 동작하지 않을 경우 `press_sequentially()`나 `keyboard.type()`으로 대체된다.
- JavaScript fallback은 `el.textContent = value` 후 `InputEvent('input')` dispatch로 React/Vue 상태를 강제 갱신한다.

## Sprinklr iframe 내부 입력 실패 시 디버깅 방법

1. trace 파일을 열어 어느 frame에서 locator가 탐색됐는지 확인한다.

   ```bash
   playwright show-trace artifacts/trace/<trace-file>.zip
   ```

2. runtime.log에서 `[INPUT]` 로그를 확인한다.

   ```
   [INPUT] locator found via scope: <frame-name>
   [INPUT] detected type: contenteditable
   [INPUT] focus success
   [INPUT] fill failed: empty or mismatched after fill
   [INPUT] press_sequentially attempt success
   [INPUT] verification success: "갤럭시 배터리 교체는 어디서 하나요?"
   [ARTIFACT] before-send screenshot saved: artifacts/chatbox/...png
   [INPUT] send clicked
   ```

3. `artifacts/chatbox/*.html` DOM fragment에서 실제 입력창 선택자를 찾는다.

4. `app/samsung_rubicon.py`의 `INPUT_CANDIDATES` 배열에 새 선택자를 추가한다.

## Playwright Inspector 사용 방법

Inspector를 열면 locator를 실시간으로 탐색하고 actionability를 확인할 수 있다.

```bash
PWDEBUG=1 python run.py
```

또는 코드 내에서 중단점을 설정하려면:

```python
page.pause()
```

Inspector에서 `Pick locator` 버튼을 누르고 챗 입력창을 클릭하면 Playwright가 적절한 locator 문자열을 자동 제안한다.

## Codespaces 실행 전 체크리스트

- [ ] `.env`에 `OPENAI_API_KEY` 설정 완료
- [ ] `pip install -r requirements.txt` 완료
- [ ] Playwright Chromium 설치: `python -m playwright install chromium`
- [ ] 한국어 폰트 설치: `sudo apt-get install -y fonts-noto-cjk fonts-nanum && fc-cache -f -v`
- [ ] 폰트 확인: `fc-list | grep -i "Noto Sans KR\|Nanum"`
- [ ] `HEADLESS=false`로 실행 (기본값)

## 결과 JSON 주요 필드

| 필드 | 설명 |
|------|------|
| `input_verified` | 질문이 DOM에서 검증됐는지 여부 (`true`/`false`) |
| `input_method_used` | 실제로 사용된 입력 방식 (`fill` / `press_sequentially` / `keyboard` / `js`) |
| `before_send_screenshot_path` | 전송 전 입력창 스크린샷 경로 |
| `font_fix_applied` | 한국어 폰트 CSS 주입 여부 |
| `status` | `passed` 또는 `failed` |

`input_verified=false`인 케이스는 LLM 평가를 건너뛰고 `reason="Question input not verified"`로 처리된다.
