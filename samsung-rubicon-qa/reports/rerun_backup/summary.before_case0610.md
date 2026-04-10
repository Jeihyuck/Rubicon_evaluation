# Samsung Rubicon QA Summary

결과 확인 우선순위: `reports/latest_conversation.md` -> `reports/latest_results.json` -> `reports/latest_results.csv` -> `reports/summary.md`
성공 케이스는 스크린샷이나 비디오 경로가 비어 있어도 정상이며, 실패 케이스에서만 최소 증거 캡처가 남을 수 있다.

## 집계

- 총 케이스 수: 10
- 성공 수: 8
- 실패 수: 0
- invalid_capture 수: 2
- DOM 추출 성공 수: 8
- OCR fallback 사용 수: 0
- baseline 이후 새 응답 감지 수: 8
- 평균 overall score: 3.99
- human review 필요 건수: 8

## 최저 점수 케이스

- case_id: case06
- score: 0.00
- reason: Invalid capture: no_editable_candidate_after_transition

## 에러 케이스

- case06: No ready chat input candidate available
- case10: No ready chat input candidate available
