# 돌연변이 기록

**「물게 하는 돌연변이를 실제로 돌려 빨갛게 한 기록이 있을 것」**이 `CLAUDE.md` 의
조건이고, 그 기록이 사는 자리가 정해져 있지 않았다 — 남아 있던 것은 **산문의
주장**뿐이었다(NC-89). `.gitignore` 가 돌연변이를 돌리는 워크트리를 버전관리에서
빼므로 근거가 저장소에 들어올 길이 설계상 닫혀 있었다.

## 이 파일의 규칙

- **돌린 것만 적는다.** 「돌렸을 것이다」는 적지 않는다 — 그것이 NC-89 가 낸 말이다
- **다음 사람이 손으로 재현할 수 있게 적는다**: 무엇을 · 어떻게 어긋냈고 · **어느
  검사가** 빨개졌는가. 검사 이름이 없으면 재현이 아니라 주장이다
- **통과한 돌연변이도 적는다.** 값은 오히려 그쪽에 있다 — 검사가 아무것도 지키지
  않는다는 뜻이기 때문이다
- **묶음마다 잰 커밋을 적는다.** 「그때 빨개졌다」는 그 뒤에 코드가 바뀌면 지금도
  참인지 알 수 없고, **언제의 「그때」인지가 없으면 무엇이 바뀌었는지조차 물을 수
  없다.** 적는 것은 **바탕이 아니라 잰 트리의 커밋**이다 — 「`X` 뒤」는 바탕만
  가리켜 같은 바탕의 두 묶음을 가르지 못한다(실제로 `2fc40f3` 뒤가 둘이고, 옛
  묶음의 그 형태는 소급해 고치지 않는다 — 잰 트리를 지어내는 것이 되기 때문이다).
  `backend/tests/test_prose.py` 가 이 규칙을 문다 (감사 ⑪ NC-132).
  **쓰는 시점에 그 해시를 모르면 회차를 닫을 때 채운다** — 예외를 적지 않았더니
  규칙을 세운 그 회차의 묶음이 「`X` 의 다음 커밋」으로 섰다(감사 ⑫ NC-143)
- 이 파일은 **⑧ 부터의 기록이다.** 그 앞 회차의 돌연변이는 PR 본문이 요약만 들고
  있고, 없는 기록을 소급해 지어내지 않는다
- **통과한 줄은 셋째 칸을 `**없다` 로 연다**(「**없다 — 통과했다**」). 그 줄은 같은 NC 의
  빨강 줄이 **뒤에** 서거나(고쳐서 문다), 아래 「아직 초록인 어긋냄」에 묶음의 커밋과 NC 로
  든다 — `backend/tests/test_prose.py` 가 문다(감사 ㉕ OB-1, 저장소 소유자가 정했다 2026-09-30).
  이 규칙 전의 옛 줄 가운데 다른 말로 연 것은 고치지 않는다
- **빨개진 줄은 셋째 칸을 검사 이름(`` `test_…` ``)이나 「같은 검사」로 연다.** 고치기 전과 뒤를 한 칸에 적지
  않고 초록 줄과 빨강 줄 둘로 나눈다 — 검사 이름이 칸 **어디에** 들어도 빨강으로 세던 때는 `**` 만 빠뜨린
  초록 줄이 빨강으로 읽혀 색인 없이 지났다(감사 ㉘ NC-203, 저장소 소유자가 정했다 2026-09-30). 검사 이름으로
  열어도 고치기 전의 결과(「통과했다」 · 「고치기 전」 따위)를 함께 적은 칸은 빨강으로 세지 않는다(감사 ㉙ NC-214).
  **이 규칙 전에 한 칸에 적은 옛 줄은 고치지 않는다** — 고치기 전의 글자로 연 것은 `backend/tests/test_prose.py` 의
  `_BEFORE_AND_AFTER` 가, 검사 이름으로 연 것은 `_RED_WITH_A_PASS` 가 이름으로 든다(감사 ㉙ NC-218 — 앞의 것만
  적어, 목록 밖에 옛 줄 여섯이 있었다)

## 아직 초록인 어긋냄

**알려진 사각의 색인이다 — 묶음이 아니다.** 어긋냈는데 아무 검사도 빨개지지 않았고, 그 뒤로도
같은 NC 의 빨강 줄이 서지 않은 줄을 여기 모은다. 뒤에 게이트가 생겨 이제 무는 줄과 여전히
초록인 줄이 같은 모양으로 섞여 뽑을 자리가 없었다 — ⑪ ③ · ⑮ OB-1 · ㉕ OB-1 · ㉗ 에서 거듭 났다.
**줄은 닫혀도 지우지 않는다** — 「지금」 칸을 고쳐 언제 어떻게 닫혔는지를 남긴다. 「초록이 맞다」는
대조군이나 의도한 경계라 닫을 것이 없다는 뜻이다.

| 기록 | NC | 무엇이 초록이었나 | 담당 | 닫는 조건 · 지금 |
|---|---|---|---|---|
| `0d9a96d` | 147 | 엔트리포인트의 `set -euo pipefail` 을 지워도 `shellcheck` 가 통과한다 | `audit-quality` | **닫혔다** — 엔트리포인트의 첫 실행 줄을 보는 검사가 문다(감사 ㉕ NC-190, `4abd1b6` 묶음의 190 줄) |
| `1e0a336` | 160 | 스펙의 열거 이름을 더하거나 바꿔도 대조가 통과한다 — 양변이 같은 원천이다 | `audit-contract` | **닫혔다** — 찍어 둔 스펙과 견주는 검사(ADR 0012)가 같은 둘을 빨갛게 한다(「ADR 0012」 묶음). 옛 조건은 「찍어 둔 스펙과 견주는 검사가 서는 날(⑯ OB-1)」 |
| `6402ccb` | 191 | 두 잠금의 같은 하위 의존성을 함께 다른 실재 판으로 바꿔도 `lock.sh --check` 가 통과한다 | `audit-quality` | 초록 — 의도한 경계. 사람의 diff 검토가 그 자리다(`CHECKLIST.md` 「항상」 · ADR 0004) |
| `6402ccb` | — | 잠금 스텝에 `continue-on-error: true` 를 달아도 통과한다(㉕ OB-2) | `audit-quality` | **닫혔다** — CI 의 검사 스텝마다 명령과 실패를 삼키는 장치를 보는 검사가 문다(`bbfb6e8` — 「감사 ㉕ OB-1 · OB-2 의 고침」 묶음) |
| `30ef34f` | 196 | `_AWAITING` 에서 「열림」을 빼도 통과한다 — 뒤의 `0a92e57` 묶음 196 빨강 줄은 **다른** 어긋냄(상태 어휘)을 물어 이 초록을 닫지 않는다 | `audit-quality` | 초록 — 대장에 굵은 「열림」 줄이 서는 회차에 다시 잰다(감사 ㉘ NC-204 가 빠진 이 줄을 더했다) |
| `4abd1b6` | 186 | 옛 절 밑에 덧붙인 둘째 표가 그 절 제목의 커밋을 빌린다 | `audit-quality` | 초록 — 묶음 게이트의 「못 보는 부류」. 새로 잰 것을 새 제목 아래 두는 규칙이 그 자리다 |
| `4abd1b6` | 187 | 부분 닫힘만 드는 「아직」 표 줄에서 지운 줄 표시를 벗겨도 통과한다 | `audit-quality` | 초록 — 번호의 상태로는 재감사가 돌았는지 가를 수 없다(기다리는 표 게이트의 「못 보는 부류」) |
| `30ef34f` | 199 | 개발 잠금 **하나만** 실재 해시로 판을 내려도 설치 · `lock.sh --check` · `pytest` 가 통과한다 | `audit-quality` | 초록 — 의도한 경계. 191 과 같은 자리다 |
| `30ef34f` | 197 | head 위에 리비전을 더하고 목록만 늘리면 목록 곁의 「여덟」 문장이 낡아도 통과한다 | `audit-quality` | 초록 — 게이트의 「못 보는 부류」. 기대던 문장은 ㉗ 의 고침이 뺐다 |
| `0a92e57` | 195 | 커밋을 적은 Setext 제목 아래의 표 | `audit-quality` | 초록이 맞다 — 대조군 |
| `bbfb6e8` | — | `테스트` 스텝의 명령을 `pytest tests/test_api.py` 로 좁혀도 스텝 검사가 통과한다 | `audit-quality` | 초록 — 스텝 검사의 「못 보는 부류」(명령의 인자). 인자까지 무는 날 닫힌다 |
| `7d45282` | 198 | 인용(`>`) 안의 기록 표에 든 이름도 기록으로 센다 | `audit-quality` | 초록이 맞다 — 파서가 인용 안의 표도 표로 읽는다(「PR #38 Codex 리뷰 1 라운드의 고침」 묶음) |
| `ae2170f` | — | 대장 NC 줄의 설명 칸에 이스케이프한 `\|\|` 를 넣어도 상태 칸 검사가 통과한다 | `audit-quality` | 초록이 맞다 — 이스케이프한 구분자는 칸을 가르지 않는다(「PR #38 Codex 리뷰 3 라운드의 고침」 묶음) |
| `356e7e3` | — | 접힌 블록(`run: >`)으로 쓴 명령 · 형제 잡의 `if:` | `audit-quality` | 초록이 맞다 — YAML 이 정한 대로 읽고 `backend` 잡만 본다(「PR #38 Codex 리뷰 4 라운드의 고침」 묶음) |
| `45d9beb` | — | 접힌 블록(`run: >`)으로 쓴 `린트` 명령 | `audit-quality` | 초록이 맞다 — 접힌 줄도 실행 줄 맨 앞의 명령이다(「PR #38 Codex 리뷰 5 라운드의 고침」 묶음) |
| `a35dd14` | 203 | 굵게 하지 않은 초록 줄(`없다 — 통과했다 (…)`)이 초록 검사를 지나고, 같은 NC 의 앞 초록을 닫으며, 기록 검사의 기록을 채운다 | `audit-quality` | **닫혔다** — 빨강을 셋째 칸이 여는 모양으로 가른다(「감사 ㉘ 의 고침」 묶음의 203 줄) |
| `5a4c237` | — | 「재검사를 기다리는 로트」에서 원자재 조건(`Item.material_group IS NOT NULL`)을 빼도 통과한다 — 원자재 말고는 잔량이 있는 로트가 설 길이 없다 | `audit-quality` | 초록 — 생산 입고(반제품 · 완제품 로트의 원장 줄)가 서는 단계에서 그 로트로 다시 잰다 |
| `a35dd14` | 204 | `_AWAITING` 에서 「열림」을 빼도 통과한다 — ㉗ Q-R3a 가 그대로이고, 다른 어긋냄을 문 196 빨강 줄이 그것을 닫은 것으로 읽혔다 | `audit-quality` | 초록 — 대장에 굵은 「열림」 줄이 서는 회차에 다시 잰다(㉘ NC-204) |
| `a35dd14` | 205 | 머리의 셋째 칸이 「결과」인 표의 굵은 초록 줄, 초록 절 안에 둔 커밋 없는 묶음 | `audit-quality` | **닫혔다** — 기록 표가 아닌 표의 `**없다` 칸이 빨갛고, 초록 절은 색인 표만 뺀다(「감사 ㉘ 의 고침」 묶음의 205 줄) |
| `a35dd14` | 206 | 제3 문서의 주석을 「표 18 이 설 때는」으로 되돌려도 통과한다 | `audit-quality` | **닫혔다** — 표 번호 게이트가 문다(「감사 ㉘ 의 고침」 묶음의 206 줄) |
| `a35dd14` | 210 | `린트` 를 `echo \` 다음 줄 `ruff check .` 로 써도 스텝 검사가 통과한다 — 물리적 줄을 실행 줄로 읽는다 | `audit-internal` | 초록 — 의도한 경계. 저장소 소유자가 막지 않고 「못 보는 부류」에 두기로 정했다(㉘ NC-210). 고친 뒤에도 초록(`8154399`) |
| `a35dd14` | — | 원시 HTML `<table>` 로 쓴 묶음을 세 게이트가 모두 보지 않는다 | `audit-quality` | 초록 — ㉘(`audit-quality`) OB-3. 오늘 0 건 |
| `a35dd14` | — | `--exit-zero` · `working-directory` · `\|\|` 뒤의 해시 없는 설치 · CodeQL 잡의 `if: false` 에 스텝 검사가 통과한다 | `audit-quality` | 초록 — ㉘(`audit-quality`) OB-4. `--exit-zero` 를 삼킴 목록에 더하는 날 그 줄이 닫힌다 |
| `a35dd14` | — | NC 칸을 `**196**` 로 쓴 줄이 대장 게이트 셋을 모두 빠져나간다 | `audit-quality` | 초록 — ㉘(`audit-quality`) OB-5. 오늘 0 건 |
| `a35dd14` | — | 기록 표의 검사 이름 뒤에 대문자(`X`)를 붙여도 기록 검사가 원래 이름으로 읽는다 | `audit-quality` | 초록이 맞다 — 검사 이름은 소문자라 어긋냄 쪽의 잘못이다. 다시 잴 때 소문자 꼬리를 쓴다(㉘ 묶음) |
| `8154399` | 204 | `_AWAITING` 에서 「열림」을 빼도 통과한다 — 고친 뒤에도 같다 | `audit-quality` | 초록 — 게이트는 고치지 않았다. `30ef34f` 196 줄과 같은 자리다 |
| `8154399` | 206 | 표 번호가 든 줄에 문서 이름을 같은 줄에 적은 것 | `audit-quality` | 초록이 맞다 — 대조군 |
| `8154399` | 210 | `echo \` 다음 줄의 명령 — 고친 뒤에도 같다 | `audit-internal` | 초록 — 의도한 경계(㉘ NC-210). `a35dd14` 210 줄과 같은 자리다 |
| `143a527` | — | 옛 전 · 후 줄과 같은 (커밋, NC) 의 다른 줄에서 검사 이름을 빼도 초록 검사가 통과한다 | `audit-quality` | **닫혔다** — 예외가 셋째 칸의 여는 글자까지 든다(「PR #39 Codex 리뷰 1 라운드의 고침」 묶음) |
| `143a527` | — | 진짜 `린트` 앞에 `echo` 만 하는 같은 이름의 `린트` 스텝을 두어도 스텝 검사가 통과한다 | `audit-quality` | **닫혔다** — `run` 스텝의 이름이 겹치면 빨갛다(같은 묶음) |
| `5d579d9` | — | 「대표 1명을 지정한다」 줄 | `audit-quality` | 초록이 맞다 — 다른 낱말의 끝인 「표」는 표 번호가 아니다(대조군) |
| `88a8ff1` | 213 | 머리 셋째 칸이 「결과」인 표의 **굵게 하지 않은** 초록 줄 | `audit-quality` | **닫혔다** — 기록 표가 아닌 표의 `없다` 칸을 굵게 여부 없이 본다(「감사 ㉙ 의 고침」 묶음의 213 줄) |
| `88a8ff1` | 214 | 셋째 칸을 검사 이름으로 열고 「통과했다」를 적은 초록 줄이 앞 초록을 닫고 기록 게이트의 기록을 채운다 | `audit-quality` | **닫혔다** — 빨강 칸에 고치기 전 결과가 함께 들면 빨갛다(「감사 ㉙ 의 고침」 묶음의 214 줄) |
| `88a8ff1` | 215 | 두 스키마 문서끼리의 번호 · 틀린 문서 이름 · 대장의 새 줄에 표 번호 게이트가 통과한다 | `audit-quality` | 초록 — 의도한 경계. 저장소 소유자가 막지 않고 「못 보는 부류」에 적기로 정했다(㉙ NC-215). 고친 뒤에도 초록(`4da615c`) |
| `88a8ff1` | — | `uses:` 로 선 검사 스텝 · 형제 잡에 스텝 검사가 통과한다 | `audit-quality` | 초록 — ㉙(`audit-quality`) OB-3. `uses` 스텝을 검사 스텝에서 뺀 것이 규칙인지 정해지는 날 다시 본다 |
| `88a8ff1` | 219 | 한 칸에 고치기 전 · 뒤를 적은 규칙 뒤의 새 줄(`e0159e2` 묶음)을 게이트가 물지 않는다 | `audit-internal` | **닫혔다** — 214 의 고침이 그 줄을 문다. 고치지 않는 옛 줄로 `_RED_WITH_A_PASS` 에 이름으로 들고, 빼면 빨강(「감사 ㉙ 의 고침」 묶음의 214 줄) |
| `4da615c` | 215 | 표 번호 게이트가 빼는 파일 안의 줄 · 틀린 문서 이름 — 고친 뒤에도 같다 | `audit-quality` | 초록 — 의도한 경계(㉙ NC-215). `88a8ff1` 215 줄과 같은 자리다 |
| `89712c1` | — | `_RED_WITH_A_PASS` 에 든 (커밋, NC) 의 다른 줄에 「— 통과했다」를 붙여도 초록 검사가 통과한다 | `audit-quality` | **닫혔다** — 목록이 셋째 칸의 여는 글자까지 든다(「PR #41 Codex 리뷰 1 라운드의 고침」 묶음) |
| `89712c1` | — | 빨강 칸에 「처음에는 없었다」로 전 · 후를 함께 적어도 초록 검사가 통과한다 | `audit-quality` | **닫혔다** — 전 표현에 「처음에는」 · 「첫 판」을 더했다(같은 묶음) |
| `757def1` | — | 대장에서 가장 큰 번호의 줄을 잃어도 줄 배치 검사가 통과한다 — 상한을 두 표에서 읽었다 | `audit-quality` | **닫혔다** — 상한을 「다음 번호」 줄에서 읽는다(「PR #45 Codex 리뷰 1 라운드의 고침」 묶음) |
| `757def1` | — | `README.md` 에 회차 절을 두어도 회차 게이트들이 통과한다 — 두 파일을 이어 읽는다 | `audit-quality` | **닫혔다** — `test_a_round_section_lives_in_the_record` 가 문다(같은 묶음) |
| `25676d4` | — | 회차 절을 `회차-기록.md` 끝에 둔다 | `audit-quality` | 초록이 맞다 — 대조군(「PR #45 Codex 리뷰 1 라운드의 고침」 묶음) |
| `c6baf9a` | — | 예외인 NC-163 줄에 「심각도 낮음」을 적는다 | `audit-quality` | 초록이 맞다 — 대조군(「심각도 낮음을 이슈로」 묶음) |
| `584f5c9` | — | 보통인 줄의 뒤 판정이 잔여를 「심각도 낮음」으로 든다 | `audit-quality` | 초록이 맞다 — 낮음 게이트는 원 지적만 본다(「PR #65 Codex 리뷰 1 라운드의 고침」 묶음) |
| `055fc4e` | — | 열린 줄의 원 지적에 「심각도: 낮음」(콜론 꼴)을 적어도 낮음 게이트가 통과한다 | `audit-quality` | **닫혔다** — `_LOW` 가 콜론 꼴을 받는다(「PR #65 Codex 리뷰 2 라운드의 고침」 묶음) |
| `5f6803a` | — | 열린 줄의 원 지적이 「심각도 낮음이 아니다」 · 「낮음 아님」이다 | `audit-quality` | 초록이 맞다 — 부정형은 낮음이 아니다(「PR #65 Codex 리뷰 3 라운드의 고침」 묶음) |
| `6001d28` | — | 두 NC 표의 머리 줄을 바꿔도 「아직」 표 게이트의 앵커가 통과한다 | `audit-quality` | 초록이 맞다 — 겨냥이 빗나간 어긋냄이다. 파서는 머리 줄이 아니라 절 이름으로 표를 찾고, 절 이름을 바꾸는 어긋냄은 같은 묶음에서 빨갛다 |
| `f2f39e3` | — | 원장 트리거의 로트 잠금만 `FOR UPDATE` 로 되돌려도 엇갈림 검사가 통과한다 | `audit-quality` | 초록이 맞다 — 겹친 방어. 반품 문서 트리거가 검사 줄을 먼저 잡아 같은 검사의 반품이 줄을 서므로 엇갈림 자체가 서지 않는다. 둘 다 되돌리면(같은 묶음의 7c) 빨갛다 |
| `f2f39e3` | — | 반품 문서 트리거의 검사 잠금만 빼도 엇갈림 검사가 통과한다 | `audit-quality` | 초록이 맞다 — 겹친 방어. `FOR NO KEY UPDATE` 는 외래키의 `KEY SHARE` 와 부딪치지 않아 교착이 나지 않는다. 둘 다 되돌리면 빨갛다 |
| `57a5bba` | — | 반품 쓰기 경로의 `_as_counted()` 만 `double` 로 바꿔도 잔량 검사가 통과한다 | `audit-quality` | 초록이 맞다 — 겹친 방어. 합이 `numeric` 이면 `double` 과의 비교에서 합 쪽 값이 이미 맞다. 합까지 바꾸면 빨갛다(`79d04b8` 묶음) |
| `79d04b8` | — | 반품 쓰기 경로의 `_as_counted()` 만 `double` 로 바꿔도 잔량 검사가 통과한다 — 수를 고친 뒤에도 같다 | `audit-quality` | 초록이 맞다 — 겹친 방어. `57a5bba` 줄과 같은 자리다 |
| `79d04b8` | — | 반품 쓰기 경로의 로트 잠금만 빼도 동시 반품 검사가 통과한다 | `audit-quality` | 초록이 맞다 — 겹친 방어. 검사와 로트가 하나씩 짝이라(`uq_lot_inspection`) 먼저 잡는 검사 잠금이 같은 로트의 반품을 줄 세운다. 둘 다 빼면 빨갛다. 로트를 검사 밖의 길로 줄이는 유형(폐기출고)이 서는 날 이 잠금이 홀로 선다 — 그 조각이 다시 잰다 |
| `49b7d14` | 228 | `_is_type` 이 불리언을 정수로 받아도 통과한다 | `audit-quality` | **닫혔다** — 「등가 어긋냄」은 틀린 판정이었다. 요청 `anyOf` 에 정수 갈래가 서는 자리에서 거짓 근거가 지나간다(감사 ㊶ 낮음-2 · #91). 그 입력의 검사가 문다(「감사 ㊶ 의 고침」 묶음) |

## ⑧ 의 고침 (`03b6c1f`)

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 65 | `992bb442d985` · `361ec789023c` · `e84fbec436c0` 의 `downgrade()` 에서 `DO $$ … RAISE EXCEPTION` 블록을 지웠다(각각 따로) | `test_downgrade_says_whose_judgements_would_vanish` · `…whose_measurements_would_vanish` · `…which_lots_would_lose_their_ledger` |
| 64 | `backend/.dockerignore` 를 지웠다 | `test_the_build_context_does_not_carry_the_secret_file` |
| 64 | `compose.yaml` 의 `"127.0.0.1:8000:8000"` 을 `"8000:8000"` 으로 | `test_every_published_port_is_bound_to_loopback` |
| 68 | `incoming.py` 의 `if not any(_measures(...)):` 를 `if False:` 로 | `test_a_material_group_with_nothing_to_measure_is_refused` |
| 72 | `incoming.py` 의 `if twice:` 를 `if False:` 로 | `test_measuring_the_same_item_twice_is_refused` |
| 71 | `incoming.py` 의 `if request.nonconformity_code is not None:` 를 `if False:` 로 | `test_a_reason_sent_with_an_out_of_spec_value_is_refused` |
| 74 | `schemas.py` 의 `_present` 에서 `if not value.strip(_BLANK):` 를 `if False:` 로 | `test_the_boundary_refuses_what_only_looks_empty` — **갈래 열둘 전부** |

## ⑧(`audit-contract`) 의 고침 (`72392cf`)

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 77 | `incoming.py` 의 `if request.received_date > date.today():` 를 `if False:` 로 | `test_a_delivery_that_has_not_arrived_is_refused` |
| 82 | `schemas.py` 의 `ConfigDict(extra="forbid")` 를 `extra="ignore"` 로 | `test_a_field_we_do_not_know_is_refused` |
| 78 | `app.py` 의 `@app.exception_handler(Exception)` 를 `ZeroDivisionError` 로 좁혔다 | `test_a_break_answers_with_json_and_says_nothing_about_the_inside` |
| 75 | `app.py` 의 거절 본문을 `[{"loc": …, "type": refused.code}]` 에서 `[str(refused)]` 로 | `test_both_kinds_of_422_have_the_same_shape` |
| 81 | `schemas.py` 의 `result` 에서 `json_schema_extra={"enum": …}` 를 뺐다 | `test_the_spec_says_which_version_and_which_judgements` |
| **79** | `app.py` 의 `version=API_VERSION` 을 뺐다 | **통과했다.** FastAPI 의 기본 판이 하필 고른 값(`0.1.0`)과 같아 「적었다」와 「안 적었다」가 밖에서 구별되지 않았다 — 판을 `0.1` 로 바꾸고 **기본값과 다른지**까지 보게 고친 뒤 같은 돌연변이가 빨개졌다 |

## ⑨ 의 고침 (`fc940e8`)

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 87 | `app.py` 의 `session_scope` 에서 `session.commit()` 을 지웠다 | `test_a_pass_is_actually_committed` — **그 전에는 294 개가 전부 초록이었다** |
| 88 | `_sessions()` 를 게으른 형태에서 **모듈 최상단**으로 되돌렸다 | `test_the_app_does_not_reach_for_the_default_database` · `test_a_pass_is_actually_committed` |
| 91 | `ck_lot_passed_after_arrival` 의 `>=` 를 `>` 로 | `test_a_lot_that_arrives_and_passes_on_the_same_day_stands` |
| 90 | `inspections` 에 `UNIQUE (supplier_id, item_id, supplier_lot_number)` 를 **더했다**(NC-67 의 결정을 뒤집는 변경) | `test_the_same_request_twice_makes_two_lots` · `test_a_split_delivery_of_the_same_supplier_lot_is_accepted`. **「둘째는 그날의 다음 일련을 받는다」는 통과했다** — 감사자가 예측한 그대로다 |
| 92 · 86 | `production.py` 의 문장을 「1단계에서는 표만 선다」로 되돌렸다 | `test_a_stage_that_closed_is_not_written_as_if_it_were_now` |
| 86 | 저장소 최상위에 `frontend/` 를 만들었다 | `test_there_is_still_no_screen` |

## 감사 ⑩ 의 고침 (`a98f40d`)

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 129 | `a7c14b3e9052` 의 `upgrade()` 에서 **조이기 전의 가드**(`판정이 도착보다 앞선 검사가 있다`)를 통째로 지웠다 | `test_upgrading_says_which_judgement_came_before_its_arrival` — 가드가 없으면 `ck_inspection_judged_after_arrival` 이 **제약 이름만** 들고 걸린다 |

**가드를 하나 세우려다 말았고, 그것을 탐침이 정했다.** 감사 ⑩ 이 낸 NC-129 는 두 갈래였는데 둘째(「검사를 가리키는데 도착일이 없는 로트」)는 **옛 줄로 설 수 없었다.** 앞 스키마에서 네 갈래를 실제로 심어 보았고 전부 막혔다 —

| 심어 본 줄 | 막은 것 |
|---|---|
| 공급사 로트의 도착일 비우기 | `ck_lot_supplied_has_received_date` |
| 그 로트를 자사로 바꾸기 | `ck_lot_origin_matches_type` |
| 자사 반제품 로트 세우기 | `ck_lot_warehouse` — 창고 코드가 없어서였고, 심고 다시 했다 |
| 자사 반제품 로트가 수입검사를 가리키기 | **`fk_lot_inspection_item`** — NC-118 이 세운 쌍 외래키가 사슬의 마지막 고리다 |

**닿지 않는 가드는 세우지 않는다.** 물지 않는 가드는 그 자리가 지켜지고 있다는 잘못된 안심을 주고, 그것을 무는 검사는 **통과하면서 아무것도 지키지 않는다.** 사슬을 리비전에 이름으로 적어 두었으므로, 관문 2 가 `ck_inspection_item_is_raw_material` 을 넓혀 둘째 고리를 끊는 날 그 자리가 드러난다.

## 감사 ⑪ 의 고침 (`5f9922c`)

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 132 | `## 감사 ⑩ 의 고침` 제목에서 커밋을 뗐다 | `test_a_mutation_bundle_says_which_commit_it_was_measured_on` |
| 132 | **이 파일을 통째로 지웠다** | 같은 검사 — 앵커가 물었다. 그 전까지 이 파일은 **지워도 초록**이었다(⑪ OB-3) |
| 132 | 파일은 두고 **고침 묶음만 전부 없앴다** | 같은 검사 — 둘째 앵커가 물었다(훑을 것이 있었는가) |

**전수 단언에 앵커를 함께 걸었다**(⑪ OB-1). 「어긋난 것이 없다」 꼴은 훑은 집합이
비면 그대로 통과하므로, **훑을 것이 있었다**는 것까지 같은 검사가 센다. 이 저장소에
이미 세 자리에 있던 관용구이고 네 자리에 없었다.

## 감사 ⑫ 의 고침 (`f520d26`)

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 135 | `app.py` 의 `@app.exception_handler(StarletteHTTPException)` 를 `ZeroDivisionError` 로 좁혔다 | `test_a_path_error_answers_in_the_same_shape` — 404·405 의 `detail` 이 다시 문자열이 됐다 |
| 134 | 라우트의 `responses={422: {"model": Refused}}` 를 뺐다 | `test_the_spec_lists_every_refusal_name` |
| 134 | `RefusalDetail.type` 을 `Refusal` 에서 `str` 로 되돌렸다 | 같은 검사 — 스펙에서 `Refusal` 컴포넌트가 통째로 사라진다 |

**둘째와 셋째가 같은 검사를 다른 이유로 물게 한다.** 하나는 **스펙이 그 모양을
가리키지 않는 것**이고 하나는 **가리키는데 이름 목록이 비는 것**이다 — 한 검사가
두 겹을 다 세는지 확인했다.

## 감사 ⑬ 의 고침 (`0d9a96d`)

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 145 | 미들웨어에서 `response.headers[_REQUEST_ID_HEADER] = request_id` 를 지웠다 | `test_every_answer_carries_an_id_that_names_the_request` · `test_an_id_the_caller_brought_is_not_replaced` |
| 145 | 받은 값의 모양 검사를 빼고 **그대로 되돌려 싣게** 했다 | `test_an_id_we_cannot_use_is_replaced_not_echoed` |
| 145 | 500 처리기의 `_log.exception` 을 `_log.debug` 로 낮췄다 | `test_a_break_leaves_a_log_line_that_names_the_request` |
| 145 | 500 처리기에서 헤더를 **다시 다는 줄**을 지웠다 | 같은 검사 |
| 147 | `docker-entrypoint.sh` 의 `set -euo pipefail` 을 지우고 `shellcheck` 를 돌렸다 | **없다 — 통과했다.** 그것이 NC-147 의 근거다 |

**통과한 줄이 이 묶음에서 가장 값지다.** 그 어긋냄이 없었으면 「`shellcheck` 가
`set -euo pipefail` 을 지킨다」가 근거로 남아 있었다 — 도구가 요구하지 않는
줄이다. **이 줄은 ⑬ 이 실제로 돌렸는데 여기 적히지 않아**(감사 ⑮ NC-156) 결과가
`ci.yml` 주석과 대장에만 남았고, `mutations.md` 만 읽는 사람에게 셸 검사는
**어긋내 본 적이 없는 검사**로 보였다. 규칙 ③ 이 요구하는 바로 그 줄이다.

**첫 어긋냄에서 500 검사만 통과했고 그것이 옳다.** `ServerErrorMiddleware` 가
사용자 미들웨어 **바깥**에 서므로 그 응답은 미들웨어를 지나오지 않고, 처리기가
따로 축을 단다 — 네 번째 어긋냄이 그 자리를 따로 문다. **두 자리를 한 검사가
겹쳐 세지 않는다.**

**그리고 이 검사가 실제로 결함을 하나 잡았다.** 처음 세웠을 때 500 에는 헤더가
붙지 않았다 — 하필 **축이 가장 필요한 응답**이다. 검사를 먼저 쓰지 않았으면
「달았다」로 끝났을 자리다.

## 감사 ⑮ 의 고침 (`b2bb637`)

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 153 | `## 감사 ⑬ 의 고침 (\`0d9a96d\`)` 을 `## 감사 ⑬ 가 돌린 어긋냄` 으로(해시도 함께 뗐다) | **고치기 전에는 없다 — 통과했다.** 고친 뒤 `test_a_mutation_bundle_says_which_commit_it_was_measured_on` |
| 155 | `backend/.dockerignore` 에 `migrations/` 를 한 줄 더했다 | **고치기 전에는 없다 — 364 개가 전부 통과했다.** 고친 뒤 `test_the_build_context_still_carries_what_the_image_needs_to_boot` |
| 155 | `chmod -x backend/docker-entrypoint.sh` | **고치기 전에는 없다 — `pytest` 도 `shellcheck` 도 통과했다.** 고친 뒤 `test_the_entrypoint_is_executable` |
| 154 | 저장소 루트에 `.sh` 파일을 하나 심고 `git ls-files '*.sh'` 와 `:(top)*.sh` 를 견줬다 | 검사가 아니라 **명령의 범위**를 쟀다 — 기본 경로명세가 그 파일을 놓쳤다 |

**셋 다 「고치기 전에는 통과, 고친 뒤에는 빨강」이다** — 어긋냄이 결함을 먼저
보이고 고침이 그것을 물게 한 순서다. 이 회차의 어긋냄은 감사자가 「돌려 봐야
확정된다」고 지목한 것을 그대로 돌린 것이고, 셋 다 감사자의 예측대로였다.

## 감사 ⑯ 의 고침 (`1e0a336`)

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 160 | `responses` 에서 404 선언을 뺐다 | `test_the_spec_declares_every_answer_that_actually_goes_out` · `test_the_spec_says_which_header_names_the_request` |
| 160 | 405 의 `Allow` 헤더 선언을 뺐다 | `test_the_spec_says_which_header_names_the_request` |
| 160 | `Transport` 열거에 이름(`ghost`)을 하나 더했다 | **없다 — 통과했다.** 양변이 같은 원천에서 나온다 |
| 160 | `http_error` 를 `path_error` 로 고쳤다 | **없다 — 통과했다.** 같은 이유. 다만 `/openapi.json` 이 함께 바뀌어 diff 에는 보인다 |
| 161 | 덮개에서 본문 금지 상태 코드 갈래를 지웠다 | `test_a_status_that_may_not_carry_a_body_does_not_get_one` |

**통과한 둘이 이 묶음의 값이다.** 스펙 쪽 열거는 pydantic 이 코드의 열거에서
만들므로 이름을 더하거나 고치면 **두 변이 함께 움직인다** — 이 검사가 무는 것은
**배선의 끊김**이지 이름의 변동이 아니다. NC-160 이 요구한 것(이름이 기계가 읽는
계약에 있을 것)은 충족되지만, 「이름이 바뀌면 검사가 문다」를 원하면 필요한 것은
**찍어 둔 스펙과의 대조**이고 그것은 아직 없다(감사 ⑯ OB-1). 두 검사의 독스트링이
이 사각을 적는다.

**어긋냄이 아니라 찍어서 잡은 것이 하나 더 있다** — 헤더를 201 에 선언하지 않은
자리다. 실제 응답에는 붙는데 선언에는 없어, **고침이 NC-160 의 모양을 한 겹
남겼다.** 검사를 고치고 선언을 채웠다.

## 감사 ⑰ 의 고침 (`5472330`)

**잰 트리가 둘이다.** 아래 넷 중 셋은 `bb0c2e5` 에서 쟀고, `hide_parameters`
를 떼는 어긋냄은 거기서 **통과**해 엔진 층 검사를 세운 뒤 `5472330` 에서 다시
쟀다. 묶음의 커밋은 **그 표가 지금 말하는 것이 참인 트리**를 적는다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 162 | 미들웨어에서 4xx 이상을 찍는 줄을 지웠다 | `test_a_refusal_leaves_a_line_that_names_the_request` |
| 162 | 그 줄의 레벨을 `warning` 에서 `info` 로 낮췄다 | 같은 검사 — 루트에 레벨이 없어 한 줄도 나오지 않는다 |
| 164 | `hide_parameters=True` 를 뗐다 | **처음에는 없었다 — 통과했다.** 처리기가 DB 오류의 말을 아예 옮기지 않아 API 쪽 검사가 막아 주었다. 엔진 층을 직접 무는 검사를 세운 뒤 `test_a_database_error_does_not_render_the_values_it_was_given` |
| 164 | DB 오류 갈래를 지우고 `exc_info=exc` 하나로 되돌렸다 | `test_a_break_does_not_carry_the_values_the_caller_sent` — `DETAIL: Failing row contains` 가 실린다 |

**셋째가 이 묶음의 값이다.** 고침이 두 겹인데 **검사는 한 겹만 물고 있었다** —
둘째 겹(처리기)이 첫째 겹(엔진)을 가려 주는 바람에, 첫째를 떼도 초록이었다.
「두 겹으로 막았다」가 「두 겹이 지켜진다」는 뜻이 아니다. 엔진 층을 직접 무는
검사를 따로 세웠다.

**넷째는 고침 중에 실제로 일어났다.** `hide_parameters` 만 걸고 검사를 돌렸더니
**빨갰다**: 끈 것은 SQLAlchemy 층이고 PostgreSQL 자신이 `DETAIL` 로 줄의 값을
되비춘다. **검사를 먼저 쓰지 않았으면 「껐다」로 닫혔을 자리**이고, 그 말은 이
저장소가 NC-145 에서 이미 한 번 적었다.

**그리고 새 검사가 다른 검사를 빨갛게 했다.** 엔진을 만들고 버리지 않아 풀의
연결이 나중에 수거되면서 `ResourceWarning` 을 냈고, pytest 는 그것을 **그때 돌던
남의 검사**의 실패로 올렸다 — 단독으로는 초록이고 전체에서만 빨간 자리다.
`engine.dispose()` 로 닫았다.

**돌연변이가 아니라 실측으로 확정한 것이 셋 더 있다**(회차 절에 있다) — 거절이
로그에 0 건인 것, 로트 0건에서 되돌리기가 멈추는 것, 예외 문자열에 요청 본문의
값이 실리는 것. 셋 다 앱을 띄우거나 실제로 되돌려 찍었다.

## 감사 ⑱ 의 고침 (`b701a19`)

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 142 | 회차별 W 표에서 `⑰` 행을 지웠다 | **첫 판에서는 없었다 — 통과했다.** 좁힌 뒤 `test_a_round_that_closed_leaves_a_line_in_the_round_table` |
| 142 | 회차별 W 표에서 `⑮` · `⑱` 행을 각각 지웠다 | 같은 검사 |
| 142 | 회차 절(`## 감사 ⑲ …`)만 더하고 표에 줄을 안 적었다 | 같은 검사 |

**첫째가 이 묶음의 값이다 — 게이트를 세우는 커밋에서 그 게이트가 아무것도
지키지 않을 뻔했다.** 첫 판은 「첫 칸이 회차 기호로 **시작하는**」 행을 셌는데,
「아직 아무도 보지 않은 것」 표에도 `⑰ 이 고친 자리(…)` 같은 행이 있어 **회차별
W 표에서 줄을 지워도 초록**이었다. 「첫 칸이 회차 **이름뿐인**」 행으로 좁혔다.

**어긋냄 없이 `## 감사 ⑱` 절을 쓰기 전에 `⑱` 행을 지우면 통과한다는 것도
확인했다** — 절이 없으면 셀 대상이 없기 때문이고, 그것이 이 게이트가 스스로
적어 둔 「못 보는 부류」의 셋째다.

## 감사 ⑲ 의 고침 (`9deb8a9`)

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 172 | `.gitignore` 를 `.env.*` 에서 `.env.local` 로 되돌렸다 | `test_the_two_secret_filters_say_the_same_thing` |
| 173 | 판정자 가드의 조건을 `IF false` 로 바꿨다 | `test_downgrade_counts_the_judgements_that_would_vanish` — **명단을 수로 바꾼 뒤에도 무는 힘이 그대로임을 이것이 센다** |
| 174 | 4xx 줄의 `%r` 을 `%s` 로 되돌렸다 | `test_a_path_the_caller_chose_does_not_shape_the_log_line` |

**돌연변이가 아니라 실측으로 가른 것이 넷 더 있다** — 넷 다 앱이나 DB 를 실제로
돌려 찍었고, 그중 하나는 **감사의 시나리오를 반박했다.**

| 무엇을 찍었나 | 답 |
|---|---|
| `backend/.env.prod` 를 만들고 `git check-ignore` | **0 건** — 이미지 필터에는 걸리는데 버전관리에는 안 걸렸다(NC-172 확정) |
| `RAISE EXCEPTION` 에 판정자를 실어 돌리고 PostgreSQL 서버 로그 | **로그 파일에 그대로 남았다**(NC-173 확정) |
| 경로에 `%0A` 를 넣고 앱 로그 | **위조된 독립된 줄이 서지 않았다** — uvicorn 이 CR·LF 를 뗀다(NC-174 의 시나리오 **반박**) |
| 같은 로거에 순수 파이썬으로 줄바꿈을 주었다 | **독립된 줄이 섰다** — 막는 것이 우리 코드가 아니라 서버 층이라는 뜻이고, `%00` 은 실제로 통과했다(NC-174 의 고침 **유지**) |

**마지막 둘이 이 묶음의 값이다.** 하나만 찍었으면 「재현 안 됨 → 반박」으로
닫혔을 자리인데, **반대 방향을 한 번 더 찍자 「오늘 안 새는 이유가 우리 것이
아니다」가 드러났다.** 어긋냄이 한쪽 방향만 보면 안 된다는 것을 ⑮ 이 적었고
(NC-153 · 155 · 156) 여기서는 **실측이 그랬다.**

**옛 검사 이름이 하나 바뀌었다** — `test_downgrade_says_whose_judgements_would_vanish`
가 `…_counts_the_judgements_…` 가 됐다(NC-173 이 「누구」를 지웠으므로). ⑧ 묶음이
드는 옛 이름은 **그 트리의 기록이라 소급해 고치지 않는다.**

## Codex 리뷰의 고침 (`d6b350c`)

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 148 | HTTP 예외 처리기에서 `headers=exc.headers` 를 뺐다 | `test_a_method_error_still_says_which_method_works` — 405 의 `Allow` 가 사라진다 |
| 149 | `_log.error(..., exc_info=exc)` 를 `_log.exception(...)` 으로 되돌렸다 | `test_a_break_leaves_the_cause_not_just_the_axis` — 로그에 `NoneType: None` 이 찍힌다 |

**둘째는 앞 커밋이 세운 검사가 놓친 자리다.** `…names_the_request` 는 로그에 **축이
있는지**만 물었고 **까닭이 실렸는지**는 묻지 않았다 — 그래서 `NoneType: None` 이
찍히는 동안에도 초록이었다. 단언을 넓히지 않고 **검사를 따로 세웠다**: 하나는 축을,
하나는 까닭을 문다.

## 아직 도구가 없다

여기 적힌 것은 **손으로 돌린 것**이다. 돌연변이 러너를 개발 의존성으로 들이는
쪽(NC-89 의 제안 ②)은 아직 하지 않았다 — 먼저 **기록의 자리**를 정하는 것이 싸고,
그 자리가 없으면 러너를 들여도 결과가 다시 저장소 밖에 남는다.

## Codex 리뷰의 고침 (`ebeef8a` 뒤)

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 104 | `app.py` 에서 커밋을 **의존성 뒤로 되돌렸다**(`yield` 다음) | `test_a_commit_that_fails_does_not_answer_201` — 커밋이 터졌는데 **201 이 나갔다.** 그것이 이 부적합의 모양 그대로다 |
| 103 | `incoming.py` 의 `_must_be_a_counted_reason(...)` 호출을 지웠다 | `test_a_measured_reason_cannot_be_sent_by_a_person` |
| 107 | `if counted_items:` 를 `if False:` 로 | `test_a_value_for_a_counted_item_is_refused` |
| 106 | `if not partner.is_active:` 를 `if False:` 로 | `test_an_inactive_supplier_cannot_deliver` |
| 105 | 로트 번호 길이 가드를 `if False:` 로 | `test_an_item_code_too_long_for_the_lot_number_is_refused` |
| 102 | 유효기간을 `request.received_date` 대신 **`judged_at.date()`** 에서 세게 되돌렸다 | `test_the_expiry_counts_from_the_day_it_arrived` · `test_material_that_already_expired_on_arrival_is_refused` |

## CodeRabbit 리뷰의 고침 (`e3b3eeb` 뒤)

넷 중 **하나만** 기계가 셀 수 있는 모양이었다. 나머지 셋(110 · 111 · 113)은 산문의
뜻이 갈린 자리라 게이트가 서지 않는다 — 그 셋이 못 세는 부류라는 것이
`test_prose.py` 머리말의 「이 게이트가 못 보는 부류」다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 112 | 대장의 NC-35 줄 끝에 **칸 하나를 도로 붙였다**(머리가 6 칸인데 7 칸) | `test_a_table_row_does_not_carry_a_cell_the_header_did_not_declare` — 줄 번호까지 가리켰다(`docs/audit/README.md:111`) |

## NC-109 의 고침 — `inspections.received_date` (`9c09a96` 뒤)

**하나가 통과했고 그것이 이 표의 값이다.** 데이터 단계를 「로트에서 옮긴다」에서
「판정일에서 센다」로 어긋냈는데 전부 초록이었다 — 픽스처의 로트 도착일과 판정일이
**같은 날**이라 두 구현이 같은 값을 냈다. 테스트가 그 자리를 지나가면서 아무것도
지키지 않던 자리이고, 도착일을 판정일에서 떼어 두고서야 물었다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 109 | `incoming.py` 에서 `received_date=request.received_date` 를 지웠다(검사 쪽) | `test_a_failed_judgement_still_remembers_when_the_material_arrived` 외 여럿 — 쌍 외래키가 합격 경로도 함께 무너뜨린다 |
| 109 | `fk_lot_inspection_received_date` 를 통째로 뺐다 | `test_a_pass_cannot_let_the_two_arrival_dates_drift` · `test_the_migration_builds_the_same_tables_as_the_models` |
| 109 | `ck_inspection_judged_after_arrival` 의 비교를 60 일 늦췄다 | `test_an_inspection_cannot_be_judged_before_the_material_arrived` · 대조 테스트 |
| 109 | 데이터 단계를 `l.received_date` 대신 `i.judged_at::date` 로 | **처음에는 통과했다.** 픽스처의 두 날짜를 떼어 둔 뒤 `test_the_data_step_moves_the_arrival_date_from_the_lot` 이 물었다 |
| 109 | 되돌림 가드의 `NOT EXISTS` 를 `FALSE AND NOT EXISTS` 로(아무것도 세지 않게) | `test_downgrade_says_whose_arrival_date_has_no_lot_to_fall_back_on` |
| 114 | `ck_lot_from_an_inspection_has_an_arrival_date` 를 항상 참으로(`OR TRUE`) | `test_an_own_lot_cannot_borrow_an_incoming_inspection` · 대조 테스트. **CHECK 를 걸기 전에 그 검사가 실제로 통과하는 것**(DID NOT RAISE)을 먼저 확인했다 — 구멍이 있다는 주장과 구멍이 있다는 사실은 다르다 |

## Codex 리뷰의 고침 — `931a400` 뒤

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 115 | `if attribute.inspection_item_code is None:` 을 `if False:` 로 | `test_a_reason_the_system_derives_cannot_be_sent_by_a_person` |
| 116 | 길이 가드를 접두를 재던 옛 식(`len(prefix) + 2`)으로 되돌렸다 | `test_a_serial_that_grew_a_digit_is_refused_by_name` — 긴 코드 갈래는 **그대로 통과한다**(같은 결과의 두 원인이라 한 갈래로는 갈리지 않는다) |
| 117 | `08d406fa7f3b` 의 데이터 단계를 `SELECT 1` 로 | `test_upgrading_a_database_that_already_has_a_ledger_line_does_not_stop` |

## CodeRabbit 리뷰의 고침 — `2fc40f3` 뒤

**검사가 아무것도 재지 않는 것을 한 번 더 겪었다.** 어긋난 짝을 만들려고 둘째
품목의 검사를 심었는데 **그 품목이 픽스처에 없어** 삽입이 빈 동작이 됐고, 원장
줄은 원래 검사를 그대로 가리켜 가드가 물 자리가 없었다. 가드가 옳은데 검사가
빨갛지 않아 **가드부터 의심하게 되는** 모양이다 — 품목을 함께 심고서야 물었다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 118 | 품목 대조 가드의 조건을 `WHERE FALSE` 로(아무것도 세지 않게) | `test_upgrading_stops_when_a_ledger_line_points_at_another_items_inspection` |

## Codex 리뷰의 고침 — `2fc40f3` 뒤

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 118(구조) | `fk_lot_inspection_item` 을 통째로 뺐다 | `test_a_lot_cannot_point_at_another_items_inspection` · 대조 테스트 |
| 119 | 역방향 가드의 `HAVING count(DISTINCT lot_id) > 1` 을 `HAVING FALSE` 로 | `test_upgrading_stops_when_two_lots_share_one_inspection` |
| 120 | `startswith(..., autoescape=True)` 를 `like(prefix + '%')` 로 되돌렸다 | `test_a_wildcard_in_the_item_code_does_not_reach_the_like` |
| 121 | `if attribute.inspection_item_code not in standards:` 를 `if False:` 로 | `test_a_reason_this_material_is_not_inspected_for_is_refused` |

## NC-122 의 고침 — `186207e` 뒤

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 122 | `applied_unit=standard.unit` 를 `None` 으로 | `test_the_measurement_pins_the_unit_the_number_meant` · 잠금 검사 |
| 122 | `fk_inspection_measurement_unit` 을 통째로 뺐다 | `test_a_standard_cannot_change_its_unit_while_a_measurement_cites_it` · 대조 테스트 |
| 122 | 리비전의 데이터 단계를 `SELECT 1` 로 | `test_the_data_step_moves_the_unit_from_the_standard` 외 하나 |
| 122 | 되돌림 가드의 값 대조를 `AND FALSE` 로(외래키에 기대게) | `test_downgrade_says_which_measurements_would_lose_their_unit` |

## NC-123 의 고침 — `fcb7570` 뒤

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 123 | `ck_inspection_standard_measured_has_a_unit` 의 식을 `TRUE` 로 | `test_a_standard_that_measures_must_say_in_what_unit` · 대조 테스트 |
| 123 | 시드의 `입도` 에서 단위를 지웠다 | **CHECK 가 심는 단계에서 거부해** 시드를 쓰는 검사가 전부 빨갛다 — 시드 쪽 검사는 그 위의 덧대기이고, 무는 것은 제약이다 |

## Codex 리뷰의 고침 — `94cbd51` 뒤

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 124 | `applied_unit` 을 널 허용으로 되돌렸다(모델과 리비전을 함께) | `test_a_measurement_cannot_be_written_without_its_unit` — **대조 테스트는 초록이다**(둘을 함께 어긋냈으므로). 구조가 갈렸는지가 아니라 **무엇을 막는지**를 재는 검사라야 무는 자리다 |
| 125 | `if _measures(standards[...]):` 를 `if False:` 로 | `test_a_counted_reason_whose_standard_measures_is_refused` |
| 125 | 시드에서 `IQ-FM` 이 `이물` 대신 `입도`(재는 항목)를 가리키게 했다 | `test_no_counted_reason_points_at_a_measured_standard` · `test_every_standard_has_a_reason_that_can_use_it` |

## NC-126 의 고침 — `9bad48b` 뒤

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 126 | 단위 없는 기준을 세는 가드의 조건을 `AND FALSE` 로(CHECK 가 먼저 걸리게) | `test_upgrading_says_which_standard_measures_without_a_unit` |

## NC-127 의 고침 — `3e2e703` 뒤

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 127 | `ck_inspection_standard_measured_has_a_unit` 의 식을 `TRUE` 로 | `test_a_standard_that_measures_must_say_in_what_unit` · 대조 테스트 |
| 127 | `ck_inspection_standard_unit_means_something` 의 식을 `TRUE` 로 | `test_a_unit_that_only_looks_like_one_is_refused` · `test_even_a_standard_that_only_counts_cannot_hold_a_hollow_unit` · 대조 테스트 |
| 127 | `fk_inspection_measurement_unit` 을 통째로 지웠다 | `test_a_measurement_unit_that_only_looks_like_one_has_nowhere_to_land` · 대조 테스트 |
| 127 | 빈 단위 기준을 세는 **올릴 때 가드**를 `SELECT 1` 로 | `test_upgrading_says_which_standard_holds_a_unit_that_only_looks_like_one` |

**여기서 하나가 거뒀다.** 측정 줄에도 `is_present("applied_unit")` 를 걸었다가 **지워도
대조 테스트만 빨개졌다** — 그 CHECK 를 물게 하려면 「빈 단위를 든 기준」이 있어야 하는데,
같은 고침이 그런 기준을 설 수 없게 만들었기 때문이다. **물게 할 수 없는 제약**은 같은
명제의 둘째 자리라 거두고, 외래키가 그것을 이 줄까지 나른다는 것을 검사로 적었다.


## 감사 ㉓ 의 고침 — `2ad2785`

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 179 | 「아직 아무도 보지 않은 것」의 `⑧ 셋이 고친 자리` 행에서 지운 줄 표시(`~~`)를 벗겼다 | `test_a_row_still_waiting_does_not_wait_on_a_closed_nc` |
| 179 | 같은 표의 `⑫ 가 고친 자리` 행에서 같은 것을 | `test_a_row_still_waiting_does_not_wait_on_a_closed_nc` |
| 179 | 같은 표의 `⑱ 이 고친 자리` 행에서 같은 것을 | `test_a_row_still_waiting_does_not_wait_on_a_closed_nc` |
| 179 | 부적합 대장에서 NC-176 의 상태를 「닫힘」으로(⑳ 행이 기다리는 번호가 닫힌다) | `test_a_row_still_waiting_does_not_wait_on_a_closed_nc` |

반대 방향도 쟀다 — 앞의 셋은 **표 쪽**을, 넷째는 **대장 쪽**을 어긋냈다. 게이트가 두 표를
함께 읽는다는 것이 둘 다 빨개져야 드러난다.

## 감사 ㉕ 가 돌린 어긋냄 (`6402ccb`)

감사자(읽기 전용)가 「이것을 돌리면 판정이 확정된다」로 적어 넘긴 것을 호출자가 돌렸다. 대장 ㉕ 절의
표와 같은 것이고, **기록의 자리는 여기다**(감사 ㉕ NC-189 — NC-156 의 잔여). 하나씩 돌리고 되돌렸다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 186 | `mutations.md` 끝에 커밋 없는 `###` 묶음(표 하나)을 붙였다 | **없다 — 통과했다** (`test_a_mutation_bundle_says_which_commit_it_was_measured_on`). 같은 것을 `## ` 로 쓰면 그 검사가 빨갛다 |
| 188 | 대장 회차별 W 표의 `⑦-b` 행을 지웠다 | **없다 — 통과했다** (`test_a_round_that_closed_leaves_a_line_in_the_round_table`). ⑦ 번호 대조표의 `⑦` 두 줄까지 지우면 빨갛다 — 가리는 것이 다른 표다 |
| 187 | 「아직 아무도 보지 않은 것」의 ⑪ 행에서 지운 줄 표시(`~~`)를 벗겼다 | **없다 — 통과했다** (`test_a_row_still_waiting_does_not_wait_on_a_closed_nc`) — 드는 132 · 133 이 둘 다 부분 닫힘이다 |
| 187 | 바꾸지 않고 돌렸다 — NC-157(고침)을 기다리는 줄이 표에 없다 | **없다 — 통과했다** (같은 검사) |
| 190 | `docker-entrypoint.sh` 의 `set -euo pipefail` 을 지웠다 | **없다 — 통과했다** — `tests/test_boundary.py` 전부와 `shellcheck` |
| 191 | 두 잠금의 `idna==3.20` 을 함께 `3.19` 로(해시는 그대로) | **없다 — `scripts/lock.sh --check` 가 exit 0.** 하나만 바꾸면 exit 1. 감사자가 적은 `3.10` 은 의존자의 `idna>=3.18` 을 어겨 둘 다 바꿔도 풀이가 깨졌다 |
| — | `_CLAUDE_MD_CEILING` 을 100 으로 | `test_claude_md_stays_short` |
| — | 대장 ㉔ 절의 「감사한 커밋」 줄을 지웠다 | `test_a_round_section_names_the_commit_it_audited` |
| — | `_NO_COMMIT_LINE` 에서 ⑲ 항목을 지웠다 | `test_a_round_section_names_the_commit_it_audited` |
| — | 대장 산문 사이에 `> ## 감사 ㉖ — 시험` 한 줄을 넣었다 | `test_a_round_section_names_the_commit_it_audited` — 「감사 머리는 줄 머리의 `## 감사 ` 로 쓴다」 |
| 157 | `_cells` 의 이스케이프 구분자 처리(`row.replace(...)`)를 뺐다 | `test_a_table_row_does_not_carry_a_cell_the_header_did_not_declare` |
| — | `ci.yml` 잠금 스텝 끝에 `\|\| true` 를 붙였다 | `test_the_image_and_ci_install_from_the_lock_and_check_it` |
| — | 잠금 스텝에 `continue-on-error: true` 를 더했다 | **없다 — 통과했다** (같은 검사) — ㉕ OB-2 |
| 179 | 기다리는 표 게이트가 닫힌 NC 를 넷째 칸으로 읽게 했다(`cells[4]` → `cells[3]`) | `test_a_row_still_waiting_does_not_wait_on_a_closed_nc` — 앵커 |
| 179 | 같은 게이트의 `_waiting_on` 이 빈 집합을 돌려주게 했다 | 같은 검사 — 다른 앵커 |

**통과한 줄 가운데 186 · 188 · 190 의 줄과 187 의 둘째 줄은 이 회차의 고침이 문다**(아래 묶음).
나머지는 **여전히 초록이다** — 187 의 첫 줄(부분 닫힘만 드는 줄)은 게이트의 「못 보는 부류」에,
191 의 줄은 `scripts/lock.sh` 머리의 「못 보는 것」에 적었고, `continue-on-error` 줄은 ㉕ OB-2 로 남았다.

## 감사 ㉕ 의 고침 (`4abd1b6`)

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 186 | `mutations.md` 끝에 커밋 없는 `###` 묶음을 붙였다 | `test_a_mutation_bundle_says_which_commit_it_was_measured_on` — 고치기 전에는 통과했다 |
| 186 | 파일 머리(제목 앞)에 표를 하나 두었다 | 같은 검사 |
| 186 | 옛 절(`감사 ㉓ 의 고침`) 밑에 둘째 표를 덧붙였다 | **없다 — 통과했다.** 그 절의 커밋을 빌린다 — 게이트의 「못 보는 부류」에 적었다 |
| 188 | 회차별 W 표의 `⑦-b` 행을 지웠다 | `test_a_round_that_closed_leaves_a_line_in_the_round_table` — 고치기 전에는 통과했다 |
| 187 | 「아직 아무도 보지 않은 것」의 ㉕ 행 첫 칸을 `186 ~ 190` 으로(191 이 아무 줄에도 없다) | `test_an_nc_waiting_for_a_reaudit_has_a_row_that_waits_for_it` |
| 187 | 기다리는 상태를 `("**없음",)` 으로(집합이 빈다) | 같은 검사 — 앵커 |
| 187 | ⑪ 행에서 지운 줄 표시를 벗겼다 | **없다 — 통과했다** (위 검사와 `test_a_row_still_waiting_does_not_wait_on_a_closed_nc`). 187 (i) — 「못 보는 부류」에 적었다 |
| 190 | `docker-entrypoint.sh` 의 `set -euo pipefail` 을 지웠다 | `test_the_entrypoint_stops_at_the_first_failure` — 고치기 전에는 통과했다 |
| 190 | 그 줄 앞에 명령(`cd /app`)을 하나 넣었다 | 같은 검사 |
| 189 | 이 파일의 표에서 `test_the_entrypoint_is_executable` 을 다른 이름으로 바꿨다 | `test_every_gate_has_a_record_of_turning_red` |
| 189 | `_GATE_FILES` 를 비웠다 | 같은 검사 — 앵커 |

## 감사 ㉖ 가 넘긴 물음 4 — 엔트리포인트 목록 대조 (`b62bb7b`)

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| — | `docker-entrypoint.sh` 목록에서 맨 아래 줄(`3c602ffaebc3`)을 지웠다 | `test_the_entrypoint_lists_the_whole_chain` |
| — | 목록의 첫 두 줄(`b41d7c8e5a92` · `a7c14b3e9052`)의 순서를 바꿨다 | 같은 검사 |
| — | `migrations/versions/` 에 head 위로 리비전 하나(`ffffffffffff`)를 더하고 목록은 그대로 뒀다 | 같은 검사 — 이 검사가 선 까닭인 모양 |
| — | `migrations/versions/` 에서 맨 아래 리비전 파일을 뺐다 | 같은 검사 — 사슬을 걷다가 멈춘다 |


## 감사 ㉗ 이 돌린 어긋냄 (`30ef34f`)

감사자 둘(`audit-quality` · `audit-internal`, 읽기 전용)이 「이것을 돌리면 판정이 확정된다」로 적어 넘긴 것을 호출자가
실제 PostgreSQL 16 위에서 하나씩 돌리고 되돌렸다. 대장 ㉗(`audit-internal`) 절의 표와 같은 것이다. 게이트 실행은
브리핑 보관본(`.claude/briefs/`)을 잠시 치우고 돌렸다(NC-202).

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 195 | 이 파일 끝에 커밋 없는 `###` 묶음을 붙이되 표를 앞 파이프 없이(`NC \| … \| …`) 썼다 | **없다 — 통과했다** (`test_a_mutation_bundle_says_which_commit_it_was_measured_on`) |
| 195 | 같은 표를 인용(`> \| … \|`) 안에 썼다 | **없다 — 통과했다** (같은 검사) |
| 195 | 같은 표를 줄 머리 파이프로 썼다(대조군) | `test_a_mutation_bundle_says_which_commit_it_was_measured_on` |
| 198 | ⑮ 묶음의 155 줄(`chmod -x`)에서 `test_the_entrypoint_is_executable` 을 다른 이름으로 바꿨다 | **없다 — 통과했다** (`test_every_gate_has_a_record_of_turning_red`) — ㉕ 의 고침 묶음 189 줄이 그 이름을 대신 든다 |
| 198 | 그 189 줄의 같은 이름도 함께 바꿨다(대조군) | `test_every_gate_has_a_record_of_turning_red` |
| 196 | `_AWAITING` 에서 「열림」을 뺐다 | **없다 — 통과했다** (`test_an_nc_waiting_for_a_reaudit_has_a_row_that_waits_for_it`) — 대장에 「열림」 줄이 없어 그 갈래를 무는 것이 없었다 |
| 196 | 대장 NC-192 의 상태를 굵은 「열림 — 저자 판정 대기」로 하고 「아직」 표 ㉖ 행 첫 칸에서 192 를 뺐다 | `test_an_nc_waiting_for_a_reaudit_has_a_row_that_waits_for_it` — 열림 갈래가 문다 |
| 196 | 같은 것을 굵게 하지 않고 썼다 | **없다 — 통과했다** (같은 검사) |
| 199 | `requirements-dev.txt` **하나만** `iniconfig` 2.3.0 → 2.0.0 으로, 해시는 실재 해시로 | **없다 — 새 가상환경의 `pip install --require-hashes` · `scripts/lock.sh --check` · `pytest` 전체가 통과했다** |
| — | `migrations/versions/` 에 `a7c14b3e9052` 를 부모로 하는 리비전 하나를 더해 head 를 둘로 만들었다 | `test_the_entrypoint_lists_the_whole_chain` — 「head 가 하나가 아니다」 |
| — | 거기에 두 head 를 합치는 merge 리비전(`down_revision` 이 튜플)을 더했다 | `test_the_entrypoint_lists_the_whole_chain` — 「리비전 줄을 읽지 못했다」 |
| — | 맨 아래 리비전(`3c602ffaebc3`) 파일을 뺐다 | `test_the_entrypoint_lists_the_whole_chain` — 단언이 아니라 `KeyError` |
| 197 | head 위에 리비전 하나를 더하고 엔트리포인트 목록 맨 위에 그 줄을 넣되 「사슬은 여덟이고」는 그대로 뒀다 | **없다 — 통과했다** (`test_the_entrypoint_lists_the_whole_chain`) |

**통과한 줄은 전부 여전히 초록이다** — 이 회차는 고치지 않았다. 각 줄의 NC 가 열림으로 든다.

## 감사 ㉗ 의 고침 (`0a92e57`)

저장소 소유자가 ㉗ 의 여덟을 추천대로 고치기로 정했다(2026-09-30). 고친 커밋 위에서 하나씩 돌리고 되돌렸다.
「고치기 전」의 결과는 위 ㉗ 묶음이다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 195 | 이 파일 끝에 커밋 없는 `###` 묶음을 붙이되 표를 앞 파이프 없이 썼다 | `test_a_mutation_bundle_says_which_commit_it_was_measured_on` — 고치기 전에는 통과했다 |
| 195 | 같은 표를 인용(`>`) 안에 썼다 | `test_a_mutation_bundle_says_which_commit_it_was_measured_on` — 고치기 전에는 통과했다 |
| 195 | 커밋 없는 제목 아래 울타리 코드에 `# 가짜 제목` 과 커밋 토막을 넣고 그 뒤에 표를 두었다 | `test_a_mutation_bundle_says_which_commit_it_was_measured_on` — 코드 안의 줄이 제목으로 읽히지 않는다 |
| 195 | 커밋 없는 Setext 제목(`시험 묶음` / `---`) 아래에 표를 두었다 | `test_a_mutation_bundle_says_which_commit_it_was_measured_on` — Setext 도 제목이라 앞 절의 커밋을 빌리지 않는다 |
| 195 | 같은 Setext 제목에 커밋을 적었다(대조군) | **없다 — 통과했다** (같은 검사) — 그래야 맞다 |
| 196 | 대장 NC-192 의 상태 칸을 `판정 대기` 로(굵게 하지 않고) | `test_every_nc_status_opens_with_a_word_the_ledger_defined` |
| 196 | 같은 칸을 `**판정 대기**` 로 | `test_every_nc_status_opens_with_a_word_the_ledger_defined` |
| 196 | 그 게이트가 NC 줄을 하나도 고르지 못하게(`isdigit()` → `== "x"`) | `test_every_nc_status_opens_with_a_word_the_ledger_defined` — 앵커 |
| 198 | ⑮ 묶음 155 줄의 셋째 칸에서 `test_the_entrypoint_is_executable` 을 다른 이름으로 | `test_every_gate_has_a_record_of_turning_red` — 고치기 전에는 189 줄이 대신 채워 통과했다 |
| 198 | ㉕ 의 고침 묶음 190 줄 둘에서 검사 이름을 셋째 칸에서 빼 둘째 칸에만 두었다 | `test_every_gate_has_a_record_of_turning_red` — 둘째 칸의 이름은 기록이 아니다 |
| 202 | `.claude/briefs/` 에 닫힌 단계를 현재형으로 가리키는 줄을 든 파일을 두었다 | **없다 — 통과했다** (`test_a_stage_that_closed_is_not_written_as_if_it_were_now`) — 무시된 파일은 보지 않는다. 고치기 전에는 빨갰다 |
| 202 | 같은 파일을 `docs/` 에 추적 안 된 채로 두었다 | `test_a_stage_that_closed_is_not_written_as_if_it_were_now` — 추적 안 된 새 파일은 여전히 본다 |
| 202 | `.claude/briefs/` 에 넘치는 표를 든 파일을 두었다 | **없다 — 통과했다** (`test_a_table_row_does_not_carry_a_cell_the_header_did_not_declare`) |
| 202 | 같은 파일을 `docs/` 에 추적 안 된 채로 두었다 | `test_a_table_row_does_not_carry_a_cell_the_header_did_not_declare` |

**통과한 줄은 전부 의도한 초록이다** — Setext 대조군과 무시된 파일 둘. 197 · 199 · 200 은 주석만 고쳐 어긋낼 검사가 없고,
201 은 규칙 절의 문장이다.

## 감사 ㉕ OB-1 · OB-2 의 고침 (`bbfb6e8`)

저장소 소유자가 둘 다 세우기로 정했다(2026-09-30). 세운 커밋 위에서 하나씩 돌리고 되돌렸다. OB 는 NC 가 아니라
첫 칸을 `—` 로 둔다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| — | `ci.yml` 의 `린트` 스텝에서 `run: ruff check .` 줄을 지웠다 | `test_every_check_step_is_still_there_and_can_still_fail` |
| — | `테스트` 스텝에 `continue-on-error: true` 를 더했다 | `test_every_check_step_is_still_there_and_can_still_fail` — ㉕ M6-d 에서는 통과했다 |
| — | `셸` 스텝에 `if: false` 를 더했다 | `test_every_check_step_is_still_there_and_can_still_fail` |
| — | `이미지` 스텝의 명령 끝에 `\|\| true` 를 붙였다 | `test_every_check_step_is_still_there_and_can_still_fail` |
| — | `codeql.yml` 의 잡에 `continue-on-error: true` 를 더했다 | `test_every_check_step_is_still_there_and_can_still_fail` |
| — | `_ci_steps` 가 스텝 이름을 읽지 못하게(`name:` → `nameX:`) | `test_every_check_step_is_still_there_and_can_still_fail` — 앵커 |
| — | `테스트` 스텝의 명령을 `pytest tests/test_api.py` 로 좁혔다 | **없다 — 통과했다** (`test_every_check_step_is_still_there_and_can_still_fail`) — 명령의 인자는 보지 않는다. 「아직 초록인 어긋냄」에 들었다 |
| — | 이 파일 끝에 NC `999` 의 초록 줄 하나를 든 묶음을 붙였다 | `test_a_mutation_that_stayed_green_is_closed_later_or_listed` |
| — | 거기에 같은 NC 의 빨강 줄을 뒤에 더했다(대조군) | **없다 — 통과했다** (`test_a_mutation_that_stayed_green_is_closed_later_or_listed`) — 뒤의 빨강으로 이어진다 |
| — | 「아직 초록인 어긋냄」에서 `1e0a336` · 160 줄을 지웠다 | `test_a_mutation_that_stayed_green_is_closed_later_or_listed` |
| — | 초록 줄을 하나도 고르지 못하게(`**없다` → `**없xx`) | `test_a_mutation_that_stayed_green_is_closed_later_or_listed` — 앵커 |
| — | 초록 절의 줄을 하나도 읽지 못하게 | `test_a_mutation_that_stayed_green_is_closed_later_or_listed` — 앵커 |

## PR #38 Codex 리뷰 1 라운드의 고침 (`7d45282`)

Codex 가 게이트 셋의 틈을 짚었다(라운드 점수 5 — 기존 한계 · 시끄러운 실패 1, 기존 한계 · 조용한 통과 2 · 2).
고친 커밋 위에서 하나씩 돌리고 되돌렸다. 고치기 전의 결과는 돌리지 않았다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 202 | 무시된 `.claude/worktrees/x/docs/` 에 `PRD-2단계.md` 를 두었다 | **없다 — 통과했다** (`test_a_stage_that_closed_is_not_written_as_if_it_were_now`) — 무시된 파일로 단계를 닫지 않는다 |
| 202 | 같은 파일을 `docs/PRD-2단계.md` 로 추적 안 된 채 두었다(대조군) | `test_a_stage_that_closed_is_not_written_as_if_it_were_now` — 2단계가 닫힌 것으로 읽혀 추적하는 산문이 걸린다 |
| 196 | 대장 NC-192 의 상태 칸을 닫지 않은 굵게(`**닫힘`)로 | `test_every_nc_status_opens_with_a_word_the_ledger_defined` |
| 198 | ⑮ 묶음 155 줄의 셋째 칸에서 `test_the_entrypoint_is_executable` 을 뺐다 | `test_every_gate_has_a_record_of_turning_red` |
| 198 | 거기에 머리가 기록 표가 아닌 표(`가 · 나 · 다`)의 셋째 칸에 그 이름을 두었다 | `test_every_gate_has_a_record_of_turning_red` — 기록 표가 아닌 표는 세지 않는다 |
| 198 | 대신 인용(`>`) 안의 기록 표에 그 이름을 두었다 | **없다 — 통과했다** (`test_every_gate_has_a_record_of_turning_red`) — 파서가 인용 안의 기록 표도 읽는다 |

## PR #38 Codex 리뷰 2 라운드의 고침 (`08eabbc`)

Codex 가 두 틈을 짚었다(라운드 점수 4 — 기존 한계 · 조용한 통과 2 · 2, 저장소에 그런 입력은 없었다). 고친 커밋
위에서 하나씩 돌리고 되돌렸다. 고치기 전의 결과는 돌리지 않았다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| — | 이 파일 끝에 NC `999` 의 초록 줄 하나를 든 기록 표를 인용(`>`) 안에 붙였다 | `test_a_mutation_that_stayed_green_is_closed_later_or_listed` |
| — | 같은 기록 표를 앞 파이프 없이 붙였다 | `test_a_mutation_that_stayed_green_is_closed_later_or_listed` |
| — | 초록 줄 뒤에 머리가 기록 표가 아닌 표(`가 · 나 · 다`)를 두고 첫 칸을 `999` 로 했다 | `test_a_mutation_that_stayed_green_is_closed_later_or_listed` — 설명 표의 수 칸은 빨강 줄이 아니다 |
| — | `ci.yml` 의 `backend` 잡에 `if: false` 를 더했다 | `test_every_check_step_is_still_there_and_can_still_fail` |

## PR #38 Codex 리뷰 3 라운드의 고침 (`ae2170f`)

Codex 가 넷을 짚었다(라운드 점수 7 — 기존 한계 · 조용한 통과 2 · 2 · 2, 시끄러운 실패 1). 고친 커밋 위에서 하나씩
돌리고 되돌렸다. 고치기 전의 결과는 돌리지 않았다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| — | `ci.yml` 의 `backend` 앞에 `린트` 스텝(`ruff check .`)을 든 잡을 더하고, `backend` 의 `린트` 스텝은 지웠다 | `test_every_check_step_is_still_there_and_can_still_fail` — 다른 잡의 스텝은 채우지 못한다 |
| — | `린트` 스텝을 `env: {OLD_COMMAND: "ruff check ."}` 과 `run: echo skipped` 로 바꿨다 | `test_every_check_step_is_still_there_and_can_still_fail` — 명령은 `run` 값에서만 찾는다 |
| — | 이 파일 끝에 셋째 칸이 `통과했다`(굵게도 검사 이름도 없이)인 기록 줄을 붙였다 | `test_a_mutation_that_stayed_green_is_closed_later_or_listed` — 빨강도 초록도 아닌 줄은 거절한다 |
| — | 대장 NC-1 줄의 「무엇」 칸에 `a \|\| b` 를 넣었다 | **없다 — 통과했다** (`test_every_nc_status_opens_with_a_word_the_ledger_defined`) — 상태 칸이 밀리지 않는다 |

## PR #38 Codex 리뷰 4 라운드의 고침 (`356e7e3`)

CI 스텝 파싱에 쏠림 신호가 섰다(3 · 4 라운드 지적 일곱 중 넷). 저장소 소유자가 `docs/리뷰-루프.md` 방안 A 로
정해 게이트가 `ci.yml` 을 PyYAML 로 읽는다. 앞 라운드의 어긋냄까지 이 커밋 위에서 다시 돌리고 되돌렸다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| — | `린트` 스텝의 `run` 줄을 지웠다 | `test_every_check_step_is_still_there_and_can_still_fail` |
| — | `테스트` 스텝에 `continue-on-error: true` 를 더했다 | `test_every_check_step_is_still_there_and_can_still_fail` |
| — | `셸` 스텝에 `if: false` 를 더했다 | `test_every_check_step_is_still_there_and_can_still_fail` |
| — | `이미지` 스텝의 명령 끝에 `\|\| true` 를 붙였다 | `test_every_check_step_is_still_there_and_can_still_fail` |
| — | `backend` 잡에 `if: false` 를 더했다 | `test_every_check_step_is_still_there_and_can_still_fail` |
| — | `backend` 앞에 `린트` 스텝을 든 잡을 더하고 `backend` 의 `린트` 는 지웠다 | `test_every_check_step_is_still_there_and_can_still_fail` |
| — | `린트` 스텝을 `env: {OLD_COMMAND: "ruff check ."}` 와 `run: echo skipped` 로 바꿨다 | `test_every_check_step_is_still_there_and_can_still_fail` |
| — | `codeql.yml` 의 잡에 `continue-on-error: true` 를 더했다 | `test_every_check_step_is_still_there_and_can_still_fail` |
| — | `린트` 스텝을 접힌 블록(`run: >` 아래 `ruff check` · `.` 두 줄)으로 썼다(대조군) | **없다 — 통과했다** (`test_every_check_step_is_still_there_and_can_still_fail`) — YAML 이 `ruff check .` 로 접는다 |
| — | `backend` 앞에 `if:` 가 걸린 배포 잡을 더했다(대조군) | **없다 — 통과했다** (`test_every_check_step_is_still_there_and_can_still_fail`) — 형제 잡의 조건은 보지 않는다 |

## PR #38 Codex 리뷰 5 라운드의 고침 (`45d9beb`)

CI 스텝 게이트에 쏠림 신호가 두 번째로 섰고(4 · 5 라운드), 저장소 소유자가 `docs/리뷰-루프.md` 방안 B 로 정했다 —
검사 명령은 `run` 의 실행 줄 맨 앞에 선다는 작성 규칙을 두고, `continue-on-error` 는 모든 워크플로를 YAML 로 읽는다.
하나씩 돌리고 되돌렸다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| — | `린트` 스텝을 `run: "# ruff check .` + 줄바꿈 + `echo skipped"` 로 바꿨다 | `test_every_check_step_is_still_there_and_can_still_fail` — 주석 줄은 명령이 아니다 |
| — | `린트` 스텝을 `run: echo ruff check .` 로 바꿨다 | `test_every_check_step_is_still_there_and_can_still_fail` — 명령은 줄 맨 앞에 선다 |
| — | `codeql.yml` 의 잡에 따옴표 키 `"continue-on-error": true` 를 더했다 | `test_every_check_step_is_still_there_and_can_still_fail` |
| — | `.github/workflows/extra.yaml`(확장자 `.yaml`)에 `continue-on-error: true` 잡을 두었다 | `test_every_check_step_is_still_there_and_can_still_fail` |
| — | `린트` 스텝의 `run` 줄을 지웠다 | `test_every_check_step_is_still_there_and_can_still_fail` |
| — | `린트` 스텝을 접힌 블록(`run: >` 아래 `ruff check` · `.`)으로 썼다(대조군) | **없다 — 통과했다** (`test_every_check_step_is_still_there_and_can_still_fail`) |

## 감사 ㉘ 이 돌린 어긋냄 (`a35dd14`)

감사자 둘(`audit-quality` · `audit-internal`, 읽기 전용)이 「이것을 돌리면 판정이 확정된다」로 적어 넘긴 것을 호출자가
실제 PostgreSQL 16 위에서 하나씩 돌리고 되돌렸다. 매번 `pytest` 전체이고 기준선은 387 passed 다 — 브리핑 보관본을
`.claude/briefs/` 에 둔 채 돌렸다(NC-202 가 닫혔다). 대장 ㉘(`audit-internal`) 절의 표와 같은 것이다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| — | ⑮ 묶음 155 줄 셋째 칸의 `test_the_entrypoint_is_executable` 뒤에 대문자 `X` 를 붙였다 | **없다 — 통과했다** (`test_every_gate_has_a_record_of_turning_red`) — 이름을 읽는 정규식이 대문자 앞에서 끊어 원래 이름으로 읽었다. 어긋냄이 아무것도 바꾸지 못했다 |
| — | ㉕ 가 돌린 묶음의 `test_claude_md_stays_short` 뒤에 대문자 `X` 를 붙였다 | **없다 — 통과했다** (같은 검사) — 같은 까닭 |
| 198 | ⑮ 묶음 155 줄 셋째 칸의 `test_the_entrypoint_is_executable` 을 `…_x` 로 바꿨다 | `test_every_gate_has_a_record_of_turning_red` |
| 203 | 파일 끝에 커밋 있는 `##` 묶음을 붙이고 기록 표 줄의 셋째 칸을 굵게 없이 「없다 — 통과했다 (`test_claude_md_stays_short`)」로 썼다 | **없다 — 통과했다** (`test_a_mutation_that_stayed_green_is_closed_later_or_listed`) |
| 203 | 같은 줄을 굵게(`**없다 — 통과했다**`) 썼다(대조군) | `test_a_mutation_that_stayed_green_is_closed_later_or_listed` |
| 203 | 그 굵은 줄 **뒤에** 같은 NC 의 굵게 없는 초록 줄을 더했다 | **없다 — 통과했다** (같은 검사) — 뒤의 줄이 앞의 초록을 닫은 것으로 읽혔다 |
| — | ㉕ 가 돌린 묶음의 `test_claude_md_stays_short` 를 `…_x` 로 바꿨다(대조군) | `test_every_gate_has_a_record_of_turning_red` |
| 203 | 거기에 굵게 없는 초록 줄의 묶음(셋째 칸에 `test_claude_md_stays_short`)을 더했다 | **없다 — 통과했다** (`test_every_gate_has_a_record_of_turning_red`) — 초록 줄이 기록을 채웠다 |
| 204 | `_AWAITING` 에서 「열림」을 뺐다 | **없다 — 통과했다** (`test_an_nc_waiting_for_a_reaudit_has_a_row_that_waits_for_it`) — ㉗ 과 같다 |
| 205 | 굵은 초록 줄의 묶음을 붙이되 표 머리 셋째 칸을 「결과」로 썼다 | **없다 — 통과했다** (`test_a_mutation_that_stayed_green_is_closed_later_or_listed`) |
| 205 | 「아직 초록인 어긋냄」 절과 `## ⑧` 사이에 커밋 없는 `###` 묶음(굵은 초록 줄)을 넣었다 | **없다 — 통과했다** (`test_a_mutation_bundle_says_which_commit_it_was_measured_on`) |
| 205 | 같은 블록을 파일 끝에 붙였다(대조군) | `test_a_mutation_bundle_says_which_commit_it_was_measured_on` · `test_a_mutation_that_stayed_green_is_closed_later_or_listed` |
| — | 파일 끝에 원시 HTML `<table>` 로 쓴 묶음(셋째 칸 `<strong>없다</strong>`, 커밋 없음)을 붙였다 | **없다 — 통과했다** (`test_a_mutation_bundle_says_which_commit_it_was_measured_on`) |
| — | `린트` 스텝을 `ruff check . --exit-zero` 로 | **없다 — 통과했다** (`test_every_check_step_is_still_there_and_can_still_fail`) |
| — | `린트` 스텝에 `working-directory: ../docs` 를 더했다 | **없다 — 통과했다** (같은 검사) |
| — | `의존성` 스텝 끝에 `\|\| pip install -r requirements-dev.in` 을 붙였다 | **없다 — 통과했다** (같은 검사) |
| — | `codeql.yml` 의 `analyze` 잡에 `if: false` 를 더했다 | **없다 — 통과했다** (같은 검사) |
| — | 대장 NC-196 행의 첫 칸을 `**196**` 로, 상태 칸을 `판정 대기` 로 바꿨다 | **없다 — 통과했다** (`test_every_nc_status_opens_with_a_word_the_ledger_defined`) |
| 206 | `test_write_path.py` 의 주석 「수불 원장(`stock_ledger_entries`)이 설 때는」을 「표 18 이 설 때는」으로 되돌렸다 | **없다 — 통과했다** (`pytest` 전체) |
| — | 스텝 검사의 `if "name" in step` 을 `"nameX"` 로 바꿨다 | `test_every_check_step_is_still_there_and_can_still_fail` — 「backend 잡에서 스텝을 찾지 못했다」. `bbfb6e8` 묶음의 앵커를 YAML 구현에서 다시 쟀다 |
| 210 | `린트` 스텝을 `run: \|` 아래 `echo \` 와 다음 줄 `ruff check .` 로 썼다 | **없다 — 통과했다** (`test_every_check_step_is_still_there_and_can_still_fail`) — 셸은 `echo` 만 돌린다 |

**통과한 줄은 전부 여전히 초록이다** — 이 회차는 고치지 않았다. 전부 「아직 초록인 어긋냄」에 든다 — 203 의 두 줄과 204 는 뒤에
같은 NC 의 빨강이 있거나 있는 것처럼 읽히지만, 그것이 곧 203 · 204 가 말하는 틈이라 색인에 따로 적었다.

## 감사 ㉘ 의 고침 (`8154399`)

저장소 소유자의 가름대로 고친 트리(`8154399`)에서 하나씩 돌리고 되돌렸다. 실제 PostgreSQL 16, 매번 `pytest` 전체. 그
트리에는 이 묶음이 아직 없어 기록 게이트가 새 게이트의 기록을 찾지 못해 빨갰다 — 아래 「빨개진 검사」는 **그 하나를 뺀**
빨강이다. 같은 어긋냄을 고치기 전(`a35dd14`)에 돌린 결과는 「감사 ㉘ 이 돌린 어긋냄」 묶음이다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 203 | 파일 끝에 커밋 있는 묶음을 붙이고 셋째 칸을 굵게 없이 「없다 — 통과했다 (`test_claude_md_stays_short`)」로 썼다 | `test_a_mutation_that_stayed_green_is_closed_later_or_listed` — 빨강도 초록도 아닌 줄 |
| 203 | 굵은 초록 줄 **뒤에** 같은 NC 의 굵게 없는 초록 줄을 더했다 | 같은 검사 — 뒤 줄이 앞 초록을 닫지 못한다 |
| 203 | ㉕ 가 돌린 묶음의 `test_claude_md_stays_short` 를 `…_x` 로 바꾸고 굵게 없는 초록 줄의 묶음을 더했다 | 같은 검사 |
| 205 | 굵은 초록 줄의 묶음을 붙이되 표 머리 셋째 칸을 「결과」로 썼다 | `test_a_mutation_that_stayed_green_is_closed_later_or_listed` — 기록 표가 아닌 표의 초록 줄 |
| 205 | 「아직 초록인 어긋냄」 절과 `## ⑧` 사이에 커밋 없는 `###` 묶음(굵은 초록 줄)을 넣었다 | `test_a_mutation_bundle_says_which_commit_it_was_measured_on` · `test_a_mutation_that_stayed_green_is_closed_later_or_listed` |
| 206 | `test_write_path.py` 의 주석 「수불 원장(`stock_ledger_entries`)이 설 때는」을 「표 18 이 설 때는」으로 되돌렸다 | `test_a_third_document_names_the_schema_document_with_a_table_number` |
| 206 | 같은 줄을 「`docs/schema-2단계.md` 의 표 18 이 설 때는」으로 썼다(대조군) | **없다 — 통과했다** (`test_a_third_document_names_the_schema_document_with_a_table_number`) — 같은 줄에 문서 이름이 있다 |
| 211 | `backend` 잡의 `린트` 앞에 이름 붙은 `run` 스텝(`새 검사`)을 더했다 | `test_every_check_step_is_still_there_and_can_still_fail` — 목록에 없다 |
| 211 | 같은 자리에 이름 없는 `run` 스텝을 더했다 | 같은 검사 |
| 203 | `_BEFORE_AND_AFTER` 에서 `("5472330", "164")` 를 뺐다 | `test_a_mutation_that_stayed_green_is_closed_later_or_listed` — 그 옛 줄이 빨강도 초록도 아닌 줄이 된다 |
| 204 | `_AWAITING` 에서 「열림」을 뺐다 | **없다 — 통과했다** (`test_an_nc_waiting_for_a_reaudit_has_a_row_that_waits_for_it`) — 게이트는 고치지 않았다. 색인의 `30ef34f` 196 줄이 든다 |
| 210 | `린트` 스텝을 `run: \|` 아래 `echo \` 와 다음 줄 `ruff check .` 로 썼다 | **없다 — 통과했다** (`test_every_check_step_is_still_there_and_can_still_fail`) — 의도한 경계다. 독스트링의 「못 보는 부류」에 들었다 |

**통과한 줄은 닫을 것이 아니다** — 206 은 대조군이고, 204 · 210 은 의도한 경계다. 셋 다 색인이 든다.

## 감사 ㉘ 의 고침 — 기록 게이트 (`e0159e2`)

「감사 ㉘ 의 고침」 묶음의 트리(`8154399`)에서는 기록 게이트가 이미 빨개 이 한 줄을 가를 수 없었다. 기록을 더한 트리에서
다시 쟀다. 실제 PostgreSQL 16, `pytest` 전체 — 기준선 388 passed.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 203 | ㉕ 가 돌린 묶음의 `test_claude_md_stays_short` 를 `…_x` 로 바꾸고, 그 이름을 든 **굵은** 초록 줄의 묶음을 더했다 | `test_every_gate_has_a_record_of_turning_red` — 초록 줄의 이름은 기록이 아니다(고치기 전에는 세었다 — ㉘(`audit-quality`) OB-2) |

## PR #39 Codex 리뷰 1 라운드 — 고치기 전 (`143a527`)

Codex 의 지적 셋을 저장소의 실제 파일에 넣어 재현했다(`docs/리뷰-루프.md`). 같은 입력을 `main`(`a35dd14`)에도 넣어
견줬다 — 첫째 · 셋째는 `main` 이 맞고 이 PR 이 틀린 **회귀**(5 · 5), 둘째는 `main` 도 똑같이 놓치는 **기존 한계 · 조용한
통과**(2)다. 라운드 점수 12. `test_prose.py` · `test_dependencies.py` 만 돌렸다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| — | `b701a19` 묶음 142 의 「같은 검사」 줄 하나를 「지웠다」로 바꿨다 — 같은 (커밋, NC) 의 옛 전 · 후 줄 곁 | **없다 — 통과했다** (`test_a_mutation_that_stayed_green_is_closed_later_or_listed`) — `main` 에서는 빨강 |
| — | `backend` 잡의 `린트` 앞에 `run: echo skipped` 인 `린트` 스텝을 하나 더 뒀다 | **없다 — 통과했다** (`test_every_check_step_is_still_there_and_can_still_fail`) — `main` 도 초록 |
| — | `docs/지나온-길.md` 에 「대표 1명을 지정한다.」 줄을 더했다 | `test_a_third_document_names_the_schema_document_with_a_table_number` — **거짓 양성**이다. `main` 에는 이 게이트가 없다 |

## PR #39 Codex 리뷰 1 라운드의 고침 (`5d579d9`)

같은 셋과 대조군 둘. 셋은 `test_prose.py` · `test_dependencies.py` 만, 대조군은 `pytest` 전체(실제 PostgreSQL 16)를 돌렸다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| — | `b701a19` 묶음 142 의 「같은 검사」 줄 하나를 「지웠다」로 바꿨다 | `test_a_mutation_that_stayed_green_is_closed_later_or_listed` — 빨강도 초록도 아닌 줄 |
| — | `린트` 앞에 `run: echo skipped` 인 `린트` 스텝을 하나 더 뒀다 | `test_every_check_step_is_still_there_and_can_still_fail` — 이름이 겹친다 |
| — | 「대표 1명을 지정한다.」 줄을 더했다 | **없다 — 통과했다** (`test_a_third_document_names_the_schema_document_with_a_table_number`) — 고친 대로다 |
| 206 | `test_write_path.py` 의 주석을 「표 18 이 설 때는」으로 되돌렸다(대조군 — 게이트가 느슨해지지 않았다) | `test_a_third_document_names_the_schema_document_with_a_table_number` |
| 203 | `_BEFORE_AND_AFTER` 에서 `("5472330", "164")` 를 뺐다(대조군) | `test_a_mutation_that_stayed_green_is_closed_later_or_listed` |

## 감사 ㉙ 가 돌린 어긋냄 (`88a8ff1`)

감사자 둘(`audit-quality` · `audit-internal`, 읽기 전용)이 「이것을 돌리면 판정이 확정된다」로 적어 넘긴 것을 호출자가
실제 PostgreSQL 16 위에서 하나씩 돌리고 되돌렸다. 매번 `pytest` 전체이고 기준선은 388 passed 다 — 브리핑 보관본을
`.claude/briefs/` 에 둔 채 돌렸다. 대장 ㉙(`audit-internal`) 절의 표와 같은 것이다. 검사 이름은 소문자 `_x` 로 어긋냈다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 213 | 파일 끝에 커밋 있는 묶음을 붙이고 머리 셋째 칸을 「결과」로, 줄의 셋째 칸을 굵게 없이 「없다 — 통과했다 (`test_claude_md_stays_short`)」로 썼다 | **없다 — 통과했다** (`test_a_mutation_that_stayed_green_is_closed_later_or_listed`) |
| — | 같은 묶음의 머리 셋째 칸만 「빨개진 검사」로 썼다(대조군) | `test_a_mutation_that_stayed_green_is_closed_later_or_listed` — 빨강도 초록도 아닌 줄 |
| 214 | 기록 표에 굵은 초록 줄을 두고, 그 **뒤에** 같은 NC 의 줄을 셋째 칸 「`test_claude_md_stays_short` — 통과했다」로 더했다 | **없다 — 통과했다** (같은 검사) — 뒤 줄이 빨강으로 읽혀 앞 초록을 닫았다 |
| — | 둘째 줄을 빼고 굵은 초록 줄만 두었다(대조군) | `test_a_mutation_that_stayed_green_is_closed_later_or_listed` — 색인에 없다 |
| 214 | ㉕ 가 돌린 묶음의 `test_claude_md_stays_short` 를 `…_x` 로 바꾸고, 끝에 셋째 칸 「`test_claude_md_stays_short` — 통과했다」인 줄의 묶음을 더했다 | **없다 — 통과했다** (`test_every_gate_has_a_record_of_turning_red`) — 초록 줄이 기록을 채웠다 |
| — | 이름만 `…_x` 로 바꿨다(대조군 — ㉘ 의 같은 줄을 다시 쟀다) | `test_every_gate_has_a_record_of_turning_red` |
| 215 | `docs/schema.md` 에 「원장은 표 18 을 본다.」를 더했다 | **없다 — 통과했다** (`test_a_third_document_names_the_schema_document_with_a_table_number`) — 번호의 주인은 통째로 빠진다 |
| 215 | `docs/지나온-길.md` 에 「`docs/schema.md` 의 표 18 이 설 때는 …」을 더했다 — 그 문서에 18 은 없다 | **없다 — 통과했다** (같은 검사) — 같은 줄에 문서 이름이 있다 |
| 215 | 대장 끝에 「표 18 이 설 때는 …」을 더했다 | **없다 — 통과했다** (같은 검사) — 대장은 통째로 빠진다 |
| — | `docs/지나온-길.md` 에 「표 18 이 설 때는 …」을 더했다(대조군) | `test_a_third_document_names_the_schema_document_with_a_table_number` |
| — | `backend` 잡의 `린트` 뒤에 `uses: astral-sh/ruff-action@v3` 인 `새 검사` 스텝을 더했다 | **없다 — 통과했다** (`test_every_check_step_is_still_there_and_can_still_fail`) |
| — | `ci.yml` 에 형제 잡 `extra`(`run: exit 1`)를 더했다 | **없다 — 통과했다** (같은 검사) |
| 217 | 머리가 `NC \| 무엇 \| 결과` 인 표에서 **둘째 칸**만 `**없다 — 통과했다**` 로 썼다 | `test_a_mutation_that_stayed_green_is_closed_later_or_listed` — 기록 표가 아닌 표의 초록. 독스트링의 「셋째 칸」보다 넓게 본다 |
| 216 | 「아직 초록인 어긋냄」 절의 색인 표 뒤(`## ⑧` 앞)에 커밋 없는 `###` 묶음을 넣었다 | `test_a_mutation_bundle_says_which_commit_it_was_measured_on` — 주석(「이 절을 뺀다」)이 아니라 코드가 맞다 |
| 218 | `4abd1b6` 묶음 186 줄의 셋째 칸을 「고치기 전에는 통과했다. 고친 뒤 `test_…`」로 바꿨다 | `test_a_mutation_that_stayed_green_is_closed_later_or_listed` — 빨강도 초록도 아닌 줄. 검사 이름으로 연 옛 줄은 `_BEFORE_AND_AFTER` 없이 빨강으로 세인다 |

**219 는 어긋내지 않고 잰 것이다** — `e0159e2` 묶음의 한 칸 전 · 후 줄을 그대로 두고 `pytest` 전체를 돌려 388 passed 였다.
게이트가 그 줄을 물지 않는다는 뜻이라 색인에 줄을 두었다. **통과한 줄은 전부 여전히 초록이다** — 이 회차는 고치지 않았다.
213 · 214 · 215 와 `—` 둘은 「아직 초록인 어긋냄」에 든다.

## 감사 ㉙ 의 고침 (`4da615c`)

저장소 소유자의 가름대로 고친 트리(`4da615c`)에서 하나씩 돌리고 되돌렸다. 실제 PostgreSQL 16, 매번 `pytest` 전체. 그
트리에는 이 묶음이 아직 없어 기록 게이트가 새 검사(`test_the_type_check_covers_every_gate_file`)의 기록을 찾지 못해
빨갰다 — 아래 「빨개진 검사」는 **그 하나를 뺀** 빨강이다. 같은 어긋냄을 고치기 전(`88a8ff1`)에 돌린 결과는 「감사 ㉙ 가
돌린 어긋냄」 묶음이다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 213 | 파일 끝에 커밋 있는 묶음을 붙이고 머리 셋째 칸을 「결과」로, 줄의 셋째 칸을 굵게 없이 「없다 — 통과했다 (`test_claude_md_stays_short`)」로 썼다 | `test_a_mutation_that_stayed_green_is_closed_later_or_listed` — 기록 표가 아닌 표의 초록 줄 |
| — | 같은 묶음의 머리 셋째 칸만 「빨개진 검사」로 썼다(대조군) | `test_a_mutation_that_stayed_green_is_closed_later_or_listed` — 빨강도 초록도 아닌 줄 |
| 214 | 기록 표에 굵은 초록 줄을 두고, 그 뒤에 같은 NC 의 줄을 셋째 칸 「`test_claude_md_stays_short` — 통과했다」로 더했다 | `test_a_mutation_that_stayed_green_is_closed_later_or_listed` — 빨강 칸에 전 · 후가 한 칸에 들었다 |
| 214 | ㉕ 가 돌린 묶음의 `test_claude_md_stays_short` 를 `…_x` 로 바꾸고, 끝에 셋째 칸 「`test_claude_md_stays_short` — 통과했다」인 줄의 묶음을 더했다 | 같은 검사 — 그 줄이 기록을 채우기 전에 초록 검사가 거절한다 |
| 214 | `_RED_WITH_A_PASS` 에서 `("4abd1b6", "186")` 을 뺐다 | `test_a_mutation_that_stayed_green_is_closed_later_or_listed` — 규칙 앞의 옛 줄도 목록에 없으면 문다 |
| 214 | `_RED_WITH_A_PASS` 의 `("e0159e2", "203")` 을 다른 NC 로 바꿨다(219 의 줄) | 같은 검사 — 규칙 바로 뒤의 줄을 이제 문다 |
| 215 | `docs/schema.md` 에 「원장은 표 18 을 본다.」를 더했다 | **없다 — 통과했다** (`test_a_third_document_names_the_schema_document_with_a_table_number`) — 의도한 경계다. 「못 보는 부류」에 들었다 |
| 215 | `docs/지나온-길.md` 에 「`docs/schema.md` 의 표 18 이 설 때는 …」을 더했다 | **없다 — 통과했다** (같은 검사) — 같은 줄의 문서 이름이 틀린 것. 「못 보는 부류」에 들었다 |
| 215 | 대장 끝에 「표 18 이 설 때는 …」을 더했다 | **없다 — 통과했다** (같은 검사) — 기록 둘은 통째로 빠진다. 「못 보는 부류」와 `docs/schema-2단계.md` 머리에 들었다 |
| — | `pyproject.toml` 의 `[tool.mypy] files` 에서 `tests/test_boundary.py` 를 뺐다 | `test_the_type_check_covers_every_gate_file` |
| — | `files` 를 다른 이름의 키로 바꿨다 — 인자 없는 `mypy` 가 무엇을 볼지 정해지지 않는다 | `test_the_type_check_covers_every_gate_file` |
| — | `타입체크` 스텝을 `run: mypy app migrations` 로 되돌렸다 — 인자가 `files` 를 덮는다 | `test_every_check_step_is_still_there_and_can_still_fail` — 명령이 `mypy` 한 낱말이 아니다 |

**215 의 초록 셋은 닫을 것이 아니다** — 소유자가 막지 않고 적는 쪽을 골랐다. 색인이 든다.

**`e0159e2` 묶음의 203 줄을 바로잡는다**(감사 ㉙ NC-219). 그 줄의 셋째 칸 괄호 「고치기 전에는 세었다」는 **돌린 결과가
아니라 읽어서 판단한 것**이다 — 고치기 전 트리(`a35dd14`)에서 굵은 초록 줄로 돌린 기록은 없고, ㉘ M1e 는 굵게 없는
줄이었다. 옛 줄은 소급해 고치지 않으므로 여기 적는다. 그 줄은 이제 초록 검사가 물고(위 214 의 넷째 줄),
`backend/tests/test_prose.py` 의 `_RED_WITH_A_PASS` 가 사유와 함께 이름으로 든다.

타입 검사를 넓힌 것(ADR 0007)은 `mypy` 로도 쟀다 — `[tool.mypy]` 의 cmark-gfm 덮어쓰기를 빼면 `import-untyped` 둘로
멈추고, 넣으면 34 개 파일에 이상이 없다. 이것은 CI 의 `타입체크` 스텝이 무는 자리라 위 기록 표에 넣지 않았다.

## PR #41 Codex 리뷰 1 라운드 — 고치기 전 (`89712c1`)

Codex 의 지적 둘을 저장소의 실제 파일에 넣어 재현했다(`docs/리뷰-루프.md`). 같은 입력을 `main`(`88a8ff1`)에도 넣어
견줬다 — 둘 다 `main` 도 똑같이 놓치는 **기존 한계 · 조용한 통과**(2 · 2)다. 저장소의 실제 줄에는 그런 입력이 없다.
라운드 점수 4. `test_prose.py` 만 돌렸다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| — | `bbfb6e8` 묶음에서 셋째 칸이 검사 이름뿐인 줄 하나에 「— 통과했다」를 붙였다 — 목록에 든 (커밋, NC) 의 다른 줄 | **없다 — 통과했다** (`test_a_mutation_that_stayed_green_is_closed_later_or_listed`) — `main` 도 초록 |
| — | 굵은 초록 줄 뒤에 같은 NC 의 줄을 셋째 칸 「`test_claude_md_stays_short` — 처음에는 없었다」로 더했다 | **없다 — 통과했다** (같은 검사) — `main` 도 초록 |

## PR #41 Codex 리뷰 1 라운드의 고침 (`b2f1995`)

같은 둘과 대조군 하나. `test_prose.py` 를 돌렸고, 고친 트리의 `pytest` 전체(실제 PostgreSQL 16)는 389 passed 다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| — | `bbfb6e8` 묶음의 검사 이름뿐인 줄 하나에 「— 통과했다」를 붙였다 | `test_a_mutation_that_stayed_green_is_closed_later_or_listed` — 목록이 여는 글자까지 견준다 |
| — | 같은 NC 의 줄을 셋째 칸 「`test_claude_md_stays_short` — 처음에는 없었다」로 더했다 | 같은 검사 — 빨강 칸에 전 · 후가 한 칸에 들었다 |
| 214 | `_RED_WITH_A_PASS` 에서 `("4abd1b6", "188")` 을 뺐다(대조군 — 게이트가 느슨해지지 않았다) | `test_a_mutation_that_stayed_green_is_closed_later_or_listed` |

## 대장 가르기 (`aa794d1`)

대장을 `README.md` 와 `회차-기록.md` 로 가른 트리(ADR 0010)에서 하나씩 넣고 되돌렸다. `test_prose.py` 만 돌렸다. 그
트리에는 이 묶음이 아직 없어 기록 게이트가 새 검사의 기록을 찾지 못해 빨갰다 — 아래 「빨개진 검사」는 **그 하나를 뺀**
빨강이다. 어긋냄 없이 돌린 대조군은 그 하나 말고 초록이다. 같은 트리의 `pytest` 전체(실제 PostgreSQL 16)도 그 하나 말고
초록이다(389 passed).

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| — | 닫힌 NC-1 줄을 `회차-기록.md` 에서 빼 `README.md` 표 끝에 두었다 | `test_an_nc_row_lives_in_the_table_its_status_names` |
| — | 열린 NC-213 줄을 `README.md` 에서 빼 「닫힌 부적합」 표 끝에 두었다 | `test_an_nc_row_lives_in_the_table_its_status_names` — 기다리는 표 게이트는 두 표를 함께 세므로 초록이다. 이 자리를 무는 것은 이 검사 하나다 |
| — | 「닫힌 부적합」에서 NC-100 줄을 지웠다 | `test_an_nc_row_lives_in_the_table_its_status_names` — 어디에도 없는 번호 |
| — | 「닫힌 부적합」의 NC-5 줄을 두 번 두었다 | `test_an_nc_row_lives_in_the_table_its_status_names` — 두 번 있는 번호 |
| — | `_NOT_IN_AN_NC_TABLE` 에서 21 을 뺐다 | `test_an_nc_row_lives_in_the_table_its_status_names` — 어디에도 없는 번호 |
| — | 「닫힌 부적합」의 NC-1 상태 칸 `**닫힘**` 을 굵게 없이 `닫힘` 으로 썼다 — 게이트가 `회차-기록.md` 의 표를 읽는가 | `test_every_nc_status_opens_with_a_word_the_ledger_defined` · `test_an_nc_row_lives_in_the_table_its_status_names` |
| — | `회차-기록.md` 의 「감사 ㉙(`audit-quality`)」 절에서 감사한 커밋 줄을 지웠다 | `test_a_round_section_names_the_commit_it_audited` |
| — | `회차-기록.md` 의 회차별 W 표(감사 ⑥ 절 안)에서 「㉙ 둘」 줄을 지웠다 | `test_a_round_that_closed_leaves_a_line_in_the_round_table` |
| — | `회차-기록.md` 「닫힌 부적합」 머리 아래에 들여쓴 울타리 블록을 두었다 | `test_a_round_section_names_the_commit_it_audited` — 대장이 지키는 모양을 두 파일 다 본다 |
| — | `README.md` 「아직 아무도 보지 않은 것」의 지운 줄 「㉘(`audit-quality`) 이 낸 자리(203 ~ 206)」를 되살렸다 — 닫힌 204 · 206 은 `회차-기록.md` 에 있다 | `test_a_row_still_waiting_does_not_wait_on_a_closed_nc` |
| — | 「㉙(`audit-quality`) 이 낸 자리(213 ~ 215)」의 첫 칸을 214 ~ 215 로 좁혔다 | `test_an_nc_waiting_for_a_reaudit_has_a_row_that_waits_for_it` |

## PR #45 Codex 리뷰 1 라운드 — 고치기 전 (`757def1`)

Codex 의 지적 둘을 저장소의 실제 파일에 넣어 재현했다(`docs/리뷰-루프.md`). 둘 다 이 PR 이 세운 게이트의 틈이고, `main` 에는
그 게이트가 없어 같은 입력을 똑같이 놓친다 — **기존 한계 · 조용한 통과**(2 · 2). 저장소의 실제 줄에는 그런 입력이 없다.
라운드 점수 4. `test_prose.py` 만 돌렸다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| — | `README.md` 「부적합 대장」에서 가장 큰 번호의 줄(NC-219)을 지웠다 — 상한이 함께 218 로 내려간다 | **없다 — 통과했다** (`test_an_nc_row_lives_in_the_table_its_status_names`) |
| — | `README.md` 끝에 「감사 ㉚」 절(감사한 커밋 줄까지)을 두고 회차별 W 표에 ㉚ 줄을 더했다 | **없다 — 통과했다** (`test_a_round_section_names_the_commit_it_audited` · `test_a_round_that_closed_leaves_a_line_in_the_round_table`) — 두 파일을 이어 읽는다 |

## PR #45 Codex 리뷰 1 라운드의 고침 (`25676d4`)

같은 둘과 그 곁의 셋. `test_prose.py` 만 돌렸다. 그 트리에는 이 묶음이 아직 없어 기록 게이트가 새 검사의 기록을 찾지 못해
빨갰다 — 아래 「빨개진 검사」는 그 하나를 뺀 빨강이다. 어긋냄 없이 돌린 대조군은 그 하나 말고 초록이다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| — | 「부적합 대장」에서 NC-219 줄을 지웠다 | `test_an_nc_row_lives_in_the_table_its_status_names` — 「다음 번호」(NC-220) 아래의 빈 번호 |
| — | NC-219 줄을 베껴 220 으로 더하고 「다음 번호」 줄은 그대로 두었다 | `test_an_nc_row_lives_in_the_table_its_status_names` · `test_an_nc_waiting_for_a_reaudit_has_a_row_that_waits_for_it` — 앞의 것은 다음 번호 이상인 번호, 뒤의 것은 그 줄을 기다리는 줄이 없다 |
| — | 「다음 번호」 줄의 굵게를 뺐다 | `test_an_nc_row_lives_in_the_table_its_status_names` — 다음 번호 줄이 하나가 아니다 |
| — | `README.md` 끝에 「감사 ㉚」 절을 두고 회차별 W 표에 ㉚ 줄을 더했다 | `test_a_round_section_lives_in_the_record` |
| — | 같은 절을 `회차-기록.md` 끝에 두고 W 표에 ㉚ 줄을 더했다(대조군 — 제자리다) | **없다 — 통과했다** (`test_a_round_section_lives_in_the_record`) — 초록이 맞다 |

## 심각도 낮음을 이슈로 (`c6baf9a`)

낮음을 이슈로 옮긴 트리(ADR 0011)에서 하나씩 넣고 되돌렸다. `test_prose.py` 만 돌렸다. 그 트리에는 이 묶음이 아직 없어
기록 게이트가 새 검사의 기록을 찾지 못해 빨갰다 — 아래 「빨개진 검사」는 그 하나를 뺀 빨강이다. 어긋냄 없이 돌린 대조군은
그 하나 말고 초록이다. 같은 트리의 `pytest` 전체(실제 PostgreSQL 16)도 그 하나 말고 초록이다(391 passed).

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| — | 열린 NC-4 줄의 끝 칸에 「심각도 낮음.」을 덧붙였다 | `test_a_low_nc_goes_to_an_issue` |
| — | 같은 글을 예외인 NC-163 줄에 덧붙였다(대조군 — 보통인 146 의 잔여) | **없다 — 통과했다** (`test_a_low_nc_goes_to_an_issue`) — 초록이 맞다 |
| — | `_LOW_KEPT_AS_NC` 의 163 을 열린 줄이 아닌 80 으로 바꿨다 | `test_a_low_nc_goes_to_an_issue` — 목록의 번호가 열린 줄이 아니다 |
| — | 옮긴 216 줄의 상태 `**이슈로 옮김 — #61**` 에서 이슈 번호를 뺐다 | `test_every_nc_status_opens_with_a_word_the_ledger_defined` |
| — | 옮긴 216 줄을 `README.md` 표 끝으로 되돌렸다 | `test_an_nc_row_lives_in_the_table_its_status_names` · `test_a_low_nc_goes_to_an_issue` — 원 지적이 「심각도 낮음」이다 |
| — | `_SETTLED` 에서 「이슈로 옮김」을 뺐다 | `test_an_nc_row_lives_in_the_table_its_status_names` — 옮긴 줄이 기록 쪽에 있을 수 없게 된다 |

## PR #65 Codex 리뷰 1 라운드 — 고치기 전 (`05c073c`)

Codex 의 셋째 지적(낮음 게이트가 줄 전체를 훑는다)을 저장소의 실제 줄에 넣어 재현했다. `main` 에는 그 게이트가 없다 —
**기존 한계 · 시끄러운 실패**(1). 나머지 둘(감사자 출력 형식 · 브리핑의 상한)은 산문이라 어긋낼 검사가 없다.
`test_prose.py` 만 돌렸다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| — | 보통인 NC-146 줄 끝에 뒤 판정 「· **㉚ 재감사** — 잔여 163 은 심각도 낮음이다」를 덧붙였다 | `test_a_low_nc_goes_to_an_issue` — 거짓 양성이다. 146 자신은 낮음이 아니다 |

## PR #65 Codex 리뷰 1 라운드의 고침 (`584f5c9`)

같은 줄과 곁의 둘. `test_prose.py` 만 돌렸다. 어긋냄 없이 돌린 대조군은 초록이고, 같은 트리의 `pytest` 전체(실제
PostgreSQL 16)도 초록이다(392 passed).

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| — | 보통인 NC-146 줄 끝에 뒤 판정 「· **㉚ 재감사** — 잔여 163 은 심각도 낮음이다」를 덧붙였다 | **없다 — 통과했다** (`test_a_low_nc_goes_to_an_issue`) — 초록이 맞다. 원 지적만 본다 |
| — | 열린 NC-4 의 「무엇」 칸(원 지적)에 「— 심각도 낮음」을 덧붙였다 | `test_a_low_nc_goes_to_an_issue` |
| — | 옮긴 216 줄을 `README.md` 표 끝으로 되돌렸다 — 원 지적의 「심각도 낮음」이 「제안:」 앞에 있다 | `test_a_low_nc_goes_to_an_issue` · `test_an_nc_row_lives_in_the_table_its_status_names` |

## PR #65 Codex 리뷰 2 라운드 — 고치기 전 (`055fc4e`)

Codex 의 둘째 지적(콜론 꼴)을 저장소의 실제 줄에 넣어 재현했다. `main` 에는 그 게이트가 없다 — **기존 한계 · 조용한
통과**(2). 첫째(브리핑 없는 감사)는 산문이라 어긋낼 검사가 없다(2). 라운드 점수 4. `test_prose.py` 만 돌렸다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| — | 열린 NC-4 의 「무엇」 칸에 감사자 출력 양식 그대로 「— 심각도: 낮음」을 덧붙였다 | **없다 — 통과했다** (`test_a_low_nc_goes_to_an_issue`) |

## PR #65 Codex 리뷰 2 라운드의 고침 (`6624251`)

같은 줄. `test_prose.py` 만 돌렸다. 어긋냄 없이 돌린 대조군은 초록이고, 같은 트리의 `pytest` 전체(실제 PostgreSQL 16)도
초록이다(392 passed).

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| — | 열린 NC-4 의 「무엇」 칸에 「— 심각도: 낮음」을 덧붙였다 | `test_a_low_nc_goes_to_an_issue` |

## PR #65 Codex 리뷰 3 라운드 — 고치기 전 (`7cc6786`)

Codex 의 둘째 지적(부정형)을 저장소의 실제 줄에 넣어 재현했다. `main` 에는 그 게이트가 없다 — **기존 한계 · 시끄러운
실패**(1). 나머지 둘(브리핑 검사기 · 이슈 본문)은 산문이라 어긋낼 검사가 없고, 방안 B 로 계약을 좁혀 처리했다(PR 본문).
`test_prose.py` 만 돌렸다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| — | 열린 NC-4 의 「무엇」 칸에 「— 심각도 낮음이 아니다」를 덧붙였다 | `test_a_low_nc_goes_to_an_issue` — 거짓 양성이다 |

## PR #65 Codex 리뷰 3 라운드의 고침 (`5f6803a`)

같은 줄과 곁의 둘. `test_prose.py` 만 돌렸다. 어긋냄 없이 돌린 대조군은 초록이고, 같은 트리의 `pytest` 전체(실제
PostgreSQL 16)도 초록이다(392 passed).

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| — | 열린 NC-4 의 「무엇」 칸에 「— 심각도 낮음이 아니다」를 덧붙였다 | **없다 — 통과했다** (`test_a_low_nc_goes_to_an_issue`) — 초록이 맞다 |
| — | 같은 자리에 「— 심각도: 낮음 아님」을 덧붙였다 | **없다 — 통과했다** (같은 검사) — 초록이 맞다 |
| — | 같은 자리에 「— 심각도: 낮음」을 덧붙였다(부정형을 빼면서 긍정형을 놓치지 않았는가) | `test_a_low_nc_goes_to_an_issue` |

**위 두 「고치기 전」 묶음의 분류를 바로잡는다**(PR #65 Codex 리뷰 4 라운드). 「PR #65 Codex 리뷰 1 라운드 — 고치기 전」과
「3 라운드 — 고치기 전」은 낮음 게이트의 거짓 양성을 **기존 한계 · 시끄러운 실패**(1)로 적었다. 같은 입력을 `main` 은
받아들이고(그 게이트가 없다) 이 PR 만 막으므로 `docs/리뷰-루프.md` 의 **회귀**(5)다 — 라운드 점수는 8 → 12, 5 → 9 다.

## 감사 ㉚ 이 돌린 어긋냄 (`e53b091`)

감사자는 읽기 전용이라 호출자가 돌렸다. 감사자가 코드로 읽어 낸 누출(NC-164 — `Exception` 처리기가
`ServerErrorMiddleware` 에 놓여 예외를 다시 던진다)을 **어긋냄 없이** 그대로 재현했다 — 기존 검사
`test_a_break_does_not_carry_the_values_the_caller_sent` 를 `raise_server_exceptions=True` 로만 바꿔 같은 트리에서
돌렸다(임시 파일, 지웠다). 다시 던진 `IntegrityError` 의 문자열에 판정자 이름과 `Failing row contains` 가 둘 다 들었다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 164 | 어긋내지 않았다 — 검사의 `TestClient` 만 `raise_server_exceptions=True` 로 바꿨다 | **없다 — 통과했다** (`test_a_break_does_not_carry_the_values_the_caller_sent` 의 원래 형태) — 누출이 있는데 초록이었다. 다시 던진 예외를 삼키고 `app.api` 로거만 본다 |

## 감사 ㉚ 의 고침 (`711e3a9`)

`app.py` 의 `DBAPIError` 처리기와 미들웨어의 4xx 좁힘, 그것을 무는 `test_api.py` 의 검사. 어긋낸 뒤 그 검사만 돌렸다.
어긋냄 없이 돌린 대조군은 초록이고, 같은 트리의 `pytest` 전체(실제 PostgreSQL 16)도 초록이다(392 passed).

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 164 | `app.py` 의 `@app.exception_handler(DBAPIError)` 줄을 주석으로 바꿨다(DB 오류가 다시 `Exception` 처리기로 간다) | `test_a_break_does_not_carry_the_values_the_caller_sent` — `IntegrityError` 가 앱 밖으로 나왔다 |
| 164 | 미들웨어의 `400 <= response.status_code < 500` 을 옛 `response.status_code >= 400` 으로 되돌렸다 | 같은 검사 — DB 500 이 「거절했다」 줄을 한 번 더 남겼다 |

## 감사 ㉛ 이 돌린 어긋냄 (`26e44ed`)

감사자는 읽기 전용이라 호출자가 돌렸다. 감사자가 코드로 읽어 낸 400(NC-220)을 **어긋냄 없이** 찍었다 — 임시 검사로
`b"\xff"` 를 `application/json` 으로 보내 상태 · 본문 · 스펙을 봤다(임시 파일, 지웠다). 400 · `loc:["path"]` 로 나갔고 스펙에
`"400"` 이 없었다. 같은 트리의 `test_api.py` 는 초록이었다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 220 | 어긋내지 않았다 — 실제로 나가는 400 이 선언에 없는 채로 돌렸다 | **없다 — 통과했다** (`test_the_spec_declares_every_answer_that_actually_goes_out` 의 원래 형태) — 그 검사는 400 을 일으키지 않았다 |

## 감사 ㉛ 의 고침 (`bb78260`)

`app.py` 의 400 선언과 덮개의 `loc`, 그것을 무는 `test_api.py` 의 검사 둘. 어긋낸 뒤 `test_api.py` 를 돌렸다. 어긋냄 없이 돌린
대조군은 초록이고, 같은 트리의 `pytest` 전체(실제 PostgreSQL 16)도 초록이다(393 passed).

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 220 | `responses` 에서 400 선언 줄을 지웠다 | `test_the_spec_declares_every_answer_that_actually_goes_out` · `test_the_spec_says_which_header_names_the_request` |
| 220 | 덮개의 `loc` 을 늘 `"path"` 로 되돌렸다 | `test_a_body_that_cannot_be_read_points_at_the_body` |

## ADR 0012 — 계약의 사진 (`ded3639`)

`docs/openapi.json` 과 `test_the_spec_matches_the_snapshot_in_the_repository`. 어긋낸 뒤 `test_api.py` 를 돌렸다. 어긋냄 없이 돌린
대조군은 초록이고, 같은 트리의 `pytest` 전체(실제 PostgreSQL 16)도 초록이다. 앞의 둘은 `1e0a336` 묶음에서 초록이던 그 어긋냄이다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 160 | `Transport` 의 `http_error` 를 `path_error` 로 고쳤다 | `test_the_spec_matches_the_snapshot_in_the_repository` · `test_a_body_that_cannot_be_read_points_at_the_body` |
| 160 | `Transport` 열거에 이름(`ghost`)을 하나 더했다 | `test_the_spec_matches_the_snapshot_in_the_repository` |
| — | 코드는 그대로 두고 `docs/openapi.json` 의 `http_error` 를 `path_error` 로 고쳤다 | `test_the_spec_matches_the_snapshot_in_the_repository` |

## 감사 ㉝ OB-1 의 고침 — 끝 슬래시 (`4da8f80`)

`app.py` 의 `redirect_slashes=False` 와 그것을 무는 `test_api.py` 의 검사 둘. 어긋낸 뒤 `test_api.py` 를 돌렸다. 어긋냄 없이 돌린
대조군은 초록이고, 같은 트리의 `pytest` 전체(실제 PostgreSQL 16)도 초록이다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| — | `FastAPI(...)` 의 `redirect_slashes=False` 줄을 지웠다(기본값 307 으로 돌아간다) | `test_a_trailing_slash_is_not_sent_elsewhere` · `test_the_spec_declares_every_answer_that_actually_goes_out` |

## 감사 ㉞ — 「아직」 표 게이트 둘의 앵커 (`6001d28`)

마지막 사슬이 닫혀 재감사를 기다리는 NC 가 0 이 되자 두 게이트가 앵커(「기다리는 것이 하나라도 있다」)에서 빨개졌다 — 옳은 상태를
틀렸다고 한 것이다. 앵커를 「파서가 표를 읽었다」로 바꾸고, 파서를 깨는 어긋냄으로 빨개지는 것을 봤다. `test_prose.py` 만 돌렸다.
어긋냄 없이 돌린 대조군은 초록이고, 같은 트리의 `pytest` 전체(실제 PostgreSQL 16)도 초록이다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| — | 「아직 아무도 보지 않은 것」 절의 「자리(」를 「곳(」으로 바꿨다(파서가 NC 번호를 못 읽는다) | `test_a_row_still_waiting_does_not_wait_on_a_closed_nc` |
| — | 두 NC 표의 머리 줄 `\| NC \| 무엇 \|` 을 `\| 번호 \| 무엇 \|` 으로 바꿨다 | **없다 — 통과했다** — 파서는 머리 줄이 아니라 절 이름으로 표를 찾는다. 겨냥이 빗나간 어긋냄이라 아래 줄로 다시 쟀다 |
| — | 두 NC 표의 절 머리(`## 부적합 대장` · 「닫힌 부적합」)를 다른 이름으로 바꿨다 | `test_an_nc_waiting_for_a_reaudit_has_a_row_that_waits_for_it` · `test_a_row_still_waiting_does_not_wait_on_a_closed_nc` 와 NC 표를 읽는 게이트 셋 |

## 3단계 조각 1 — 원장 트리거 (`f925faa`)

구매반품이 원장에 닿는 조각의 트리거 셋(`app/db/ledger_guards.py`)과 마이그레이션 `85d4ad8b3f1f`, 그리고 반품 줄의 짝
외래키. 하나씩 어긋낸 뒤 그것을 물어야 할 검사만 돌렸다(`tests/test_purchase_returns.py` · `tests/test_migrations.py`). 어긋냄
없이 돌린 대조군은 초록이고, 같은 트리의 `pytest` 전체(실제 PostgreSQL 16)도 초록이다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 70 | 원장 트리거가 로트 줄을 잠그지 않게 했다(`FOR UPDATE` 를 뺐다) | `test_two_returns_at_once_cannot_both_take_the_last_of_a_lot` |
| — | 반품 문서 트리거가 검사 줄을 잠그지 않게 했다 | `test_two_failed_returns_at_once_cannot_exceed_what_came` |
| 70 | 원장의 합을 `numeric` 이 아니라 `double precision` 으로 셌다 | **없다 — 통과했다** — 검사가 쓴 수(33.3 · 66.7 · 400)는 부동소수점 합이 공교롭게 0 보다 크게 남는다. 겨냥이 빗나간 검사라 수를 고쳐 아래 묶음에서 다시 쟀다 |
| 70 | 「입고 줄의 수량 = 로트 수량」 비교를 `FALSE` 로 바꿨다 | `test_a_receipt_carries_the_lots_quantity` |
| 70 | 원장 트리거의 고치기 · 지우기 거부를 껐다 | `test_a_ledger_line_is_never_rewritten` |
| 70 | 로트 수량 트리거를 걸지 않았다(모델 쪽 `install()` 에서 뺐다) | `test_a_lots_quantity_stays_once_the_ledger_has_spoken` |
| 70 | 잔량의 하한을 0 에서 −1,000,000 으로 내렸다 | `test_a_return_cannot_take_more_than_is_left` |
| — | 총량 영향을 셀 수 없는 유형의 거부를 껐다 | `test_a_type_whose_direction_is_unknown_is_not_counted` |
| — | 불합격분 반품 합의 상한을 받은 수량의 1000 배로 늘렸다 | `test_failed_returns_add_up_to_no_more_than_what_came` |
| — | 반품 문서 트리거의 고치기 · 지우기 거부를 껐다 | `test_a_return_document_is_never_rewritten` |
| — | 반품 문서 트리거가 셀 수 없는 수를 건너뛰지 않게 했다 | `test_a_return_sends_back_something_countable` — `nan` · `inf` 가 CHECK 이름이 아니라 「돌려보낸 합이」로 거부된다 |
| — | 마이그레이션에 굳힌 원장 함수의 메시지 한 글자(「있는 것보다」의 띄어쓰기)를 바꿨다 | `test_the_migration_builds_the_same_tables_as_the_models` |
| — | 마이그레이션이 로트 수량 트리거를 걸지 않게 했다 | `test_the_migration_builds_the_same_tables_as_the_models` |
| 70 | 올릴 때의 가드(입고 줄과 로트 수량이 갈린 로트)를 껐다 | `test_upgrading_stops_when_a_receipt_disagrees_with_its_lot` |
| — | 내릴 때의 가드 문턱을 반품 0 건에서 100 건으로 올렸다 | `test_downgrade_counts_the_returns_that_would_vanish` |
| — | 「구매반품출고」 설명 고침이 사람이 고친 글자도 덮게 했다 | `test_the_return_type_description_is_corrected_only_where_the_seed_left_it` — `edited-by-a-person` 쪽 |
| — | 반품 줄의 짝 외래키에서 수량을 뺐다(모델) | `test_a_return_line_says_what_its_document_says` — `quantity` 쪽 |

## 3단계 조각 1 — 빗나간 겨냥을 고친 뒤 (`e810965`)

위 묶음에서 초록이던 어긋냄 하나를, 부동소수점 합이 실제로 음수가 되는 수(0.1 · 0.3 · 499.6)로 고친 검사에 대고 다시
쟀다. 어긋냄 없이 돌린 대조군은 초록이다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 70 | 원장의 합을 `numeric` 이 아니라 `double precision` 으로 셌다 | `test_returns_can_empty_a_lot_to_the_last_gram` |

## 조각 1 리뷰 라운드 — Codex 리뷰 · 감사 ㉟ 의 고침 (`f2f39e3`)

이번 라운드가 더한 지킴(트리거 넷 · 쌍 외래키 · 사유의 단계 외래키 · 마이그레이션 가드)을 하나씩 어긋낸 뒤 그것을 물어야 할 검사만
돌렸다(`tests/test_purchase_returns.py` · `tests/test_migrations.py`). 어긋냄 없이 돌린 대조군은 초록이고, 같은 트리의 `pytest`
전체(실제 PostgreSQL 16)도 초록이다. 잠금은 둘 중 무엇이 교착을 막는지 가르려고 셋으로 나눠 쟀다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 222 | 반품 문서의 지연 트리거(문서 → 원장 줄)를 걸지 않았다 | `test_a_lot_return_cannot_stand_without_its_ledger_line` |
| 223 | 유형의 방향을 고정하는 트리거를 걸지 않았다 | `test_a_types_direction_is_fixed_once_the_ledger_uses_it` |
| 223 | 반품이 가리키는 검사를 고정하는 트리거를 걸지 않았다 | `test_a_returned_inspection_stays_as_it_was` — 다섯 칸 모두 |
| — | 반품 시각과 판정 시각의 비교를 껐다 | `test_nothing_goes_back_before_it_was_judged` |
| — | 반품 사유의 외래키를 공통코드로 되돌렸다(모델) | `test_a_lot_return_uses_a_reason_the_incoming_stage_knows` |
| 225 | 로트 · 검사 수량의 쌍 외래키를 뺐다(모델) | `test_a_lot_carries_its_inspections_quantity` · `test_an_inspection_that_made_a_lot_keeps_its_quantity` |
| — | 원장 트리거의 로트 잠금만 `FOR UPDATE` 로 되돌렸다(7a) | **없다 — 통과했다** — 겹친 방어. 반품 문서 트리거의 검사 잠금이 같은 검사의 반품을 줄 세워 엇갈림이 서지 않는다 |
| — | 반품 문서 트리거의 검사 잠금만 뺐다(7b) | **없다 — 통과했다** — 겹친 방어. `FOR NO KEY UPDATE` 가 외래키의 `KEY SHARE` 와 부딪치지 않는다 |
| — | 둘 다 처음 모양으로 되돌렸다 — 로트 `FOR UPDATE`, 검사 잠금 없음(7c) | `test_two_returns_written_document_first_do_not_deadlock` — 교착으로 둘째가 끊긴다 |
| 225 | 올릴 때의 가드(로트 수량 ≠ 검사 수량)를 껐다 | `test_upgrading_stops_when_a_lot_disagrees_with_its_inspection` |
| — | 마이그레이션이 유형 방향 고정 트리거를 걸지 않게 했다 | `test_the_migration_builds_the_same_tables_as_the_models` |


## 조각 1 리뷰 2 라운드 — Codex 리뷰의 고침 (`cab7fc7`)

2 라운드가 더한 지킴 넷을 하나씩 어긋낸 뒤 그것을 물어야 할 검사만 돌렸다(`tests/test_purchase_returns.py`). 어긋냄 없이 돌린
대조군은 초록이고, 같은 트리의 `pytest` 전체(실제 PostgreSQL 16)도 초록이다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| — | 재고 로트 반품의 입고 시각 비교를 껐다 | `test_nothing_goes_back_before_it_came_in` |
| 223 | 원장 트리거가 유형 속성 줄을 `FOR SHARE` 없이 읽게 했다 | `test_a_direction_change_waits_for_the_first_line_of_its_type` — 둘째의 방향 변경이 커밋되고 잔량이 510 이 된다 |
| — | `lot_id` 인덱스를 뺐다(모델) | `test_the_balance_is_looked_up_by_lot` |
| 223 | 검사 고정에서 불합격 사유를 뺐다 | `test_a_returned_inspection_stays_as_it_was` — `reason` 쪽만 |

## 조각 1 리뷰 3 라운드 — Codex 리뷰의 고침 (`0a48994`)

3 라운드가 더한 지킴 넷을 하나씩 어긋낸 뒤 그것을 물어야 할 검사만 돌렸다. 어긋냄 없이 돌린 대조군은 초록이고, 같은 트리의
`pytest` 전체(실제 PostgreSQL 16)도 초록이다. 내릴 때 잠금과 방향 가드의 검사는 고침보다 먼저 써서, 고치기 전의 코드에서
빨간 것을 봤다(재현).

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 223 | 검사 고정을 줄 통째에서 옛 칸 목록(수량 · 공급사 · 품목 · 시각 · 도착일)으로 되돌렸다 | `test_a_returned_inspection_stays_as_it_was` — `reason` · `supplier_lot` · `judged_by` 셋 |
| — | 반품 문서의 `inspection_id` 인덱스를 뺐다(모델) | `test_failed_returns_are_looked_up_by_inspection` |
| — | 올릴 때 원장 유형의 방향 가드를 껐다 | `test_upgrading_stops_when_a_ledger_type_runs_the_wrong_way` |
| — | 내릴 때 반품 표 잠금을 뺐다 | `test_downgrade_does_not_miss_a_return_still_being_written` — 가드가 0 을 보고 지나간 뒤 옛 CHECK 를 다시 세우다 터진다 |

## 조각 1 리뷰 4 라운드 — Codex 리뷰의 고침 (`9523f7f`)

4 라운드가 더한 지킴 셋을 하나씩 어긋낸 뒤 그것을 물어야 할 검사만 돌렸다. 어긋냄 없이 돌린 대조군은 초록이고, 같은 트리의
`pytest` 전체(실제 PostgreSQL 16)도 초록이다. 세 검사 모두 고침보다 먼저 써서, 고치기 전의 코드에서 빨간 것을 봤다(재현).

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| — | 잔량 트리거의 방향 비교(`codes.LEDGER_EFFECTS`)를 껐다 | `test_a_type_running_the_wrong_way_takes_no_line` — 증가 · 양방향 둘 다 |
| — | 잔량 트리거의 나가는 줄 시각 비교를 껐다 | `test_a_receipt_written_later_does_not_launder_an_earlier_return` — 문서 쪽 비교만 무는 `test_nothing_goes_back_before_it_came_in` 은 초록으로 남는다(겹친 방어가 아니라 입고 줄이 있을 때의 자리) |
| — | 올릴 때 방향 가드 앞의 `txn_type_attributes` 잠금을 뺐다 | `test_upgrading_does_not_check_a_direction_still_being_changed` — 올리기가 고쳐진 방향째 지나간다 |

## 3단계 조각 2 — 반품 쓰기 경로 (`57a5bba`)

쓰기 경로가 트리거보다 먼저 이름으로 막는 가드를 하나씩 어긋낸 뒤 `tests/test_return_path.py` 만 돌렸다. 어긋냄 없이 돌린
대조군은 초록이고, 같은 트리의 `pytest` 전체(실제 PostgreSQL 16)도 초록이다. 가드를 빼면 트리거나 제약이 같은 줄을 막으므로
데이터는 지켜지고, 빨개지는 까닭은 **이름 대신 `IntegrityError` 가 나서**다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| — | 불합격분 합의 가드를 껐다 | `test_failed_returns_do_not_add_up_past_what_came` · `test_two_failed_returns_at_once_leave_the_second_with_a_name` |
| — | 로트 잔량의 가드를 껐다 | `test_a_lot_can_go_back_in_pieces_down_to_nothing` · `test_a_lot_does_not_give_back_more_than_it_holds` · `test_a_refusal_leaves_nothing_behind` · `test_two_lot_returns_at_once_leave_the_second_with_a_name` |
| — | 견주는 수(`_as_counted()`)만 `double` 로 바꿨다 | **없다 — 통과했다** — 겹친 방어(위 「아직 초록인 어긋냄」). 그리고 그 트리의 잔량 검사가 고른 수(33.3 · 66.7)는 `double` 로도 0 이라, 셈 전체를 바꿔도 무는지 이 트리에서는 알 수 없었다 — `79d04b8` 이 수를 고쳤다 |
| — | 불합격 검사에 사유가 함께 오는 것을 막는 가드를 껐다 | `test_a_failed_return_does_not_say_why_twice` — `ck_purchase_return_reason_only_for_a_lot` 가 문다 |
| — | 재고 로트 반품에 사유가 없는 것을 막는 가드를 껐다 | `test_a_lot_return_says_why` — 다음 가드가 「관문에서 쓸 수 없는 사유」로 거절해 이름이 갈린다 |
| — | 정산 구분이 있는지 묻는 가드를 껐다 | `test_a_settle_type_nobody_defined_is_named` — `fk_purchase_return_settle_type` 가 문다 |
| — | 사유가 관문 1 의 규칙 표에 있는지 묻는 가드를 껐다 | `test_a_lot_return_uses_a_reason_the_incoming_gate_knows` — `fk_purchase_return_reason` 이 문다 |

## 조각 2 — 잔량 셈의 수를 고친 뒤 (`79d04b8`)

`57a5bba` 의 잔량 검사가 셈을 `double` 로 바꾸는 어긋냄을 물 수 없는 수였다. `double` 로 실제 음수가 되는 수(64.4 · 35.6 →
−7.1e-15)로 고친 뒤 셈과 잠금, 경계를 어긋냈다. 대조군과 같은 트리의 `pytest` 전체는 초록이다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| — | 잔량의 합과 견주는 수를 모두 `double` 로 셌다 | `test_a_lot_can_go_back_in_pieces_down_to_nothing` |
| — | 잔량의 합만 `double` 로 셌다 | `test_a_lot_can_go_back_in_pieces_down_to_nothing` |
| — | 견주는 수(`_as_counted()`)만 `double` 로 바꿨다 | **없다 — 통과했다** — 겹친 방어(위 「아직 초록인 어긋냄」) |
| — | 쓰기 경로의 검사 줄 잠금을 뺐다 | `test_two_failed_returns_at_once_leave_the_second_with_a_name` — 둘째가 트리거의 `IntegrityError` 를 받는다. 재고 로트 쪽은 로트 잠금이 받쳐 초록이다 |
| — | 쓰기 경로의 로트 줄 잠금만 뺐다 | **없다 — 통과했다** — 겹친 방어(위 「아직 초록인 어긋냄」) |
| — | 검사 줄 잠금과 로트 줄 잠금을 함께 뺐다 | `test_two_lot_returns_at_once_leave_the_second_with_a_name` — 둘째가 트리거의 `IntegrityError`(잔량 −100)를 받는다 |
| — | 경계에서 `inspection_id` 의 `integer` 상한을 뺐다 | `test_what_the_database_would_break_on_is_refused_at_the_boundary` — `inspection_id-2147483648` 이 500 |
| — | 경계에서 `quantity` 의 `> 0` 을 뺐다 | `test_what_the_database_would_break_on_is_refused_at_the_boundary` — `quantity-0.0` · `quantity--1.0` 이 500 |

같은 트리에서 경계의 `settle_type` 길이(10자)를 뺐을 때도 같은 검사가 빨갰는데 **다른 까닭이었다** — 보낸 긴 코드가 공통코드에
없어 「그런 정산 구분이 없다」(422, `loc` 이 `body`)가 났다. 경계가 막는 500 을 잰 것이 아니라서 빨강 줄로 세지 않고,
`08662f1` 이 실제로 있는 긴 코드로 고쳐 다시 쟀다.

## 조각 2 — 정산 구분의 길이를 고친 뒤 (`08662f1`)

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| — | 경계에서 `settle_type` 의 길이(10자)를 뺐다 | `test_what_the_database_would_break_on_is_refused_at_the_boundary` — 공통코드에 있는 12자 코드가 넣는 자리에서 500 |
| — | 재고 로트 반품에서 원장 줄을 넣지 않고 돌아오게 했다 | `test_a_201_means_the_commit_passed_the_deferred_check` — 커밋에서 지연 트리거가 물어 500 |
| — | 엔드포인트가 커밋 대신 `flush` 만 하게 했다 | `test_a_201_means_the_commit_passed_the_deferred_check` — 응답은 201 인데 다른 세션에서 문서가 보이지 않는다 |
| — | 반품 라우트의 422 를 검사의 `Refused` 로 선언했다 | `test_the_spec_lists_every_return_refusal_name` |
| — | 반품 라우트의 선언에서 400 을 뺐다 | `test_the_spec_declares_every_answer_that_actually_goes_out` — `/purchase-returns` 쪽만 |

## 조각 2 — 불합격분 합의 수를 더한 뒤 (`1851297`)

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| — | 불합격분 반품의 합과 견주는 수를 모두 `double` 로 셌다 | `test_failed_goods_can_go_back_in_pieces_up_to_all_of_it` — 0.1 + 2.7 + 0.2 가 3.0000000000000004 |
| — | 불합격분 반품의 합만 `double` 로 셌다 | `test_failed_goods_can_go_back_in_pieces_up_to_all_of_it` |

## 조각 2 리뷰 1 라운드 — Codex 리뷰의 고침 (`62d0030`)

더한 지킴 셋을 하나씩 어긋낸 뒤 그것을 물어야 할 검사만 돌렸다. 어긋냄 없이 돌린 대조군은 초록이고, 같은 트리의 `pytest`
전체(실제 PostgreSQL 16)도 초록이다. 검사는 모두 고침보다 먼저 써서, 고치기 전의 코드에서 빨간 것을 봤다(재현).

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| — | 꺼진 정산 구분의 거절을 껐다 | `test_a_retired_settle_type_is_named` |
| — | 꺼진 사유의 거절을 껐다 | `test_a_retired_reason_is_named` |
| — | 경계의 NUL 거절을 껐다 | `test_the_boundary_refuses_a_nul_the_database_cannot_hold` 둘 · `test_what_the_database_would_break_on_is_refused_at_the_boundary` 의 NUL 셋 — `nonconformity_code` 는 500 이 아니라 다른 까닭의 업무 거절(`loc` 가 `body`)로 빨갛다. 불합격 검사로 재는 자리라 사유가 경계를 지나면 그 거절이 먼저 문다 |

## 거절 본문의 문장 — CodeQL 경고의 고침 (`951c6a6`)

라우트가 싣는 문장을 상수(`"x"`)로 바꾼 뒤 `tests/test_api.py` · `tests/test_return_api.py` 를 돌렸다. 대조군과 같은 트리의
`pytest` 전체(실제 PostgreSQL 16)는 초록이다. 반품 쪽 단언은 이 커밋이 더했고, 그 앞에서는 같은 어긋냄이 반품 쪽에서 초록이었다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| — | 두 라우트가 `refused.message` 대신 상수를 싣게 했다 | `test_something_we_cannot_judge_comes_back_named` · `test_a_business_refusal_names_itself_in_the_same_shape` |

## 3단계 조각 3 — 재검사 스키마 (`1de458b`)

트리거와 CHECK 를 하나씩 어긋낸 뒤 `tests/test_retest.py` 를, 내릴 때의 가드는 `tests/test_migrations.py -k retest` 를
돌렸다. 어긋냄 없이 돌린 대조군과 같은 트리의 `pytest` 전체(실제 PostgreSQL 16)는 초록이다. 마지막 줄은 어긋냄이 아니라
처음 쓴 CHECK 그대로이고, 그 검사가 그 식에서 먼저 빨갛게 나와 식을 고쳤다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| — | 재검사 트리거에서 로트 잠금(`FOR NO KEY UPDATE`)을 뺐다 | `test_two_retests_at_once_do_not_both_find_the_lot_expired` · `test_a_retest_behind_a_failure_finds_the_lot_disposed` |
| — | 재검사 트리거를 `AFTER INSERT` 로 걸었다 | `test_a_passed_retest_renews_the_expiry_on_its_own_row` 를 비롯해 합격 재검사를 넣는 검사 전부 — 방금 넣은 갱신 만료일이 「가장 최근」으로 잡힌다 |
| — | 앞선 불합격 재검사를 묻지 않게 했다 | `test_a_lot_that_failed_its_retest_is_not_retested_again` · `test_a_failure_still_waiting_for_its_disposal_blocks_a_pass` · `test_a_retest_behind_a_failure_finds_the_lot_disposed` |
| — | 만료일이 NULL 인 분기를 껐다 | `test_a_lot_without_an_expiry_is_not_retested` |
| — | 만료의 경계를 `>=` 에서 `>` 로 바꿨다(만료일 당일을 만료로 셌다) | `test_a_lot_that_has_not_expired_is_not_retested` 의 `on-the-expiry-day` |
| — | 잔량 0 의 거절을 껐다 | `test_a_lot_with_nothing_left_is_not_retested` |
| — | 앞선 재검사보다 이른 판정의 거절을 껐다 | `test_a_retest_does_not_slip_in_before_an_earlier_one` |
| — | 원장 트리거에서 「폐기 줄은 잔량 전부」를 껐다 | `test_a_disposal_takes_the_whole_balance` |
| — | 단계가 바뀌는 것의 거절을 껐다 | `test_an_inspection_keeps_the_stage_it_came_in_with` |
| — | 재검사 줄을 고치는 것의 거절을 껐다 | `test_a_retest_is_never_rewritten` 셋 |
| — | 재검사 줄을 지우는 것의 거절을 껐다 | `test_a_retest_is_never_erased` |
| — | 로트 만료일의 고정을 껐다 | `test_a_lots_expiry_stays_as_labelled` 셋 |
| — | 떨어진 재검사의 폐기 줄을 커밋 때 묻지 않게 했다 | `test_a_failed_retest_cannot_stand_without_its_disposal` |
| — | 폐기 줄의 판정 CHECK 를 한 식(`(id IS NULL AND result IS NULL) OR (id IS NOT NULL AND result = '불합격')`)으로 썼다 — 처음 쓴 모양이다 | `test_a_disposal_carries_the_failure_it_follows` — 판정이 빌 때 `NULL = '불합격'` 이 NULL 이라 CHECK 가 그 줄을 받았다 |
| — | 내릴 때 세기 전의 `LOCK TABLE inspections` 를 뺐다 | `test_downgrade_does_not_miss_a_retest_still_being_written` |
| — | 내릴 때의 재검사 수 가드를 껐다 | `test_downgrade_counts_the_retests_that_would_vanish` · `test_downgrade_does_not_miss_a_retest_still_being_written` |

## 3단계 조각 4 — 재검사 쓰기 경로 (`330e335`)

쓰기 경로(`app/services/retests.py`)의 지킴을 하나씩 어긋낸 뒤 `tests/test_retest_path.py` · `tests/test_retest_api.py` 를
돌렸다. 어긋냄 없이 돌린 대조군과 같은 트리의 `pytest` 전체(실제 PostgreSQL 16)는 초록이다. 잰 트리와 이 커밋은 테스트
독스트링 한 줄의 줄바꿈만 다르다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| — | 로트 줄의 잠금(`FOR NO KEY UPDATE`)을 뺐다 | `test_two_retests_at_once_the_second_is_named` 둘 — 둘째가 이름 대신 트리거의 거절을 받는다 |
| — | 만료의 경계를 `>=` 에서 `>` 로 바꿨다 | `test_a_lot_that_expires_today_is_still_in_date` · `test_the_write_path_and_the_trigger_draw_the_same_line` 의 `expires-today` · `test_a_business_refusal_names_itself_in_the_same_shape`(API) |
| — | 앞선 불합격 재검사를 묻지 않게 했다 | `test_a_lot_that_failed_is_not_retested_again` · `test_two_retests_at_once_the_second_is_named` 의 `behind-a-failure` |
| — | 설정기간이 없을 때의 거절을 껐다 | `test_a_pass_without_a_shelf_life_is_named` |
| — | 새 만료일을 판정일이 아니라 옛 만료일에서 셌다 | `test_a_pass_renews_the_expiry_from_the_day_it_was_judged` · `test_a_pass_comes_back_with_its_new_expiry` |
| — | 폐기 줄의 양을 잔량이 아니라 로트 수량으로 냈다 | `test_a_failure_throws_away_everything_left` · `test_a_failure_whose_balance_does_not_add_up_in_binary_still_empties_the_lot` |
| — | 잔량을 `numeric` 이 아니라 `double` 로 셌다 | `test_a_failure_whose_balance_does_not_add_up_in_binary_still_empties_the_lot` — 처음 고른 수(33.3 · 0.1)에서는 초록이라 수를 33.3 · 66.6 으로 바꿔 다시 쟀다 |
| — | 재지 않는 재검사의 거절을 껐다 | `test_nothing_to_measure_again_is_named` |
| — | 경시변화가 아닌 항목의 거절을 껐다 | `test_measurements_that_do_not_fit_the_retest_are_named` 의 `not-time-variant` |
| — | 기준을 경시변화로 거르지 않았다 | `test_retest_path.py` · `test_retest_api.py` 의 검사 스물넷 |
| — | 잔량 0 의 거절을 껐다 | `test_a_lot_with_nothing_left_is_named` |
| — | 만료일 없음의 거절을 껐다 | `test_a_lot_without_an_expiry_is_named` |

## 3단계 조각 4 — 반품이 재검사를 가리킬 때의 이름 (`5f0a50e`, 감사 ㊴)

반품 쓰기 경로(`app/services/returns.py`)가 재검사의 id 를 `inspection_is_not_incoming` 으로 거절하는 분기를
어긋낸 뒤 `tests/test_retest_path.py` 를 돌렸다. 어긋냄 없이 돌린 대조군은 초록이다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| — | 단계를 묻는 분기를 껐다(`if False:`) | `test_the_return_path_names_a_retest_it_cannot_take` — 문서의 외래키(`fk_purchase_return_inspection_stage`)가 이름 대신 막는다 |

## 이슈 #73 — 꺼진 사유 코드 (`f610cb7`)

검사 · 재검사 쓰기 경로의 `is_active` 거절을 하나씩 어긋낸 뒤 `tests/test_write_path.py` · `tests/test_retest_path.py` ·
`tests/test_api.py` 를 돌렸다. 어긋냄 없이 돌린 대조군과 같은 트리의 `pytest` 전체(실제 PostgreSQL 16)는 초록이다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| — | `must_be_a_reason_a_person_inspects` 의 꺼진 사유 분기를 껐다(`if False:`) | `test_a_retired_reason_cannot_be_sent_by_a_person` · `test_a_retired_reason_a_person_wrote_is_named` |
| — | `RetestRefusal` 에서 `REASON_IS_NOT_ACTIVE` 를 뺐다 | `test_the_names_shared_with_the_inspection_path_mean_the_same` · `test_a_retired_reason_a_person_wrote_is_named` · `test_the_spec_matches_the_snapshot_in_the_repository` |

## 이슈 #73 — 측정값이 고르는 사유 (`350b553`, PR #81 Codex 리뷰)

`reason_for` 가 켜진 사유만 고르는 것을 어긋낸 뒤 `tests/test_write_path.py` · `tests/test_retest_path.py` 를 돌렸다. 어긋냄
없이 돌린 대조군과 같은 트리의 `pytest` 전체(실제 PostgreSQL 16)는 초록이다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| — | 켜졌는지 거르지 않고 첫 사유를 골랐다(`if active` 를 뺐다) | `test_a_deviation_whose_reason_was_retired_is_refused` · `test_a_deviation_whose_reason_was_retired_is_named` |

## 3단계 읽는 조각 A — 현장 시계 (`74b06d9`, ADR 0019)

`app/core/clock.py` · `app/services/site_clock.py` 와 쓰기 경로 셋을 하나씩 어긋낸 뒤 `tests/test_site_clock.py` ·
`tests/test_retest_path.py` 를 돌렸다. 어긋냄 없이 돌린 대조군과 같은 트리의 `pytest` 전체(실제 PostgreSQL 16)는 초록이다.
시간대를 보는 검사는 UTC 와 14 · 12 시간 떨어진 고정 오프셋 시간대로 잰다 — 컨테이너(UTC)와 현장이 같은 시간대면
「컨테이너 시각을 쓴다」는 회귀가 보이지 않고, 서울로만 재면 하루의 몇 시간에만 빨개진다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| — | `clock.now()` 가 컨테이너 시각을 냈다 | `test_now_is_the_site_wall_clock` · `test_a_clock_nobody_set_does_not_tell_the_time` 둘 |
| — | 시간대가 비었을 때의 분기를 껐다 | `test_a_clock_nobody_set_does_not_tell_the_time` 의 `missing` — 예외만 보던 검사로는 빨개지지 않아(빈 이름도 「모르는 시간대」로 멈춘다) 메시지까지 보게 고친 뒤 다시 쟀다 |
| — | 오프셋 전환을 묻지 않았다 | `test_a_zone_whose_wall_clock_turns_back_is_refused` · `test_the_app_does_not_start_on_a_clock_it_cannot_trust` 의 `turns-back` |
| — | 저장된 미래 시각을 묻지 않았다 | `test_a_stamp_later_than_the_site_now_stops_the_clock` |
| — | 앱에서 lifespan 을 뺐다 | `test_the_app_does_not_start_on_a_clock_it_cannot_trust` 둘 |
| — | 검사의 도착일 경계를 `date.today()` 로 되돌렸다 | `test_the_gate_draws_today_on_the_site_calendar` — 서울로만 재는 검사로는 빨개지지 않아(서울과 UTC 는 하루의 몇 시간에만 날짜가 갈린다) 두 시간대로 재는 검사를 더한 뒤 다시 쟀다 |
| — | 검사의 판정 시각을 `datetime.now()` 로 되돌렸다 | `test_the_write_paths_stamp_the_site_wall_clock` · `test_the_gate_draws_today_on_the_site_calendar` · `test_a_stamp_later_than_the_site_now_stops_the_clock` |
| — | 반품 시각을 `datetime.now()` 로 되돌렸다 | `test_the_write_paths_stamp_the_site_wall_clock` |
| — | 재검사의 판정 시각을 `datetime.now()` 로 되돌렸다 | `test_a_retest_is_judged_on_the_site_wall_clock` 를 비롯한 `test_retest_path.py` 서른둘 |

## 3단계 읽는 조각 B1 — 로트 읽기 (`5a4c237`, ADR 0020)

`app/services/lots.py` · `app/api/cursor.py` · `GET /lots` 를 하나씩 어긋낸 뒤 `tests/test_lot_api.py` 를 돌렸다. 어긋냄 없이 돌린
대조군과 같은 트리의 `pytest` 전체(실제 PostgreSQL 16)는 초록이다. 잰 트리와 이 커밋은 독스트링 몇 줄만 다르다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| — | 만료의 경계를 `<` 에서 `<=` 로 바꿨다(만료일 당일을 기다리게 했다) | `test_the_wait_starts_where_the_retest_path_draws_the_line` 의 `expires-today` · `test_the_waiting_list_holds_only_the_lots_that_wait` |
| — | 잔량 조건을 뺐다 | `test_a_lot_sent_back_whole_does_not_wait` · `test_a_failed_retest_empties_the_lot_and_ends_the_wait` — 처음 쓴 검사로는 빨개지지 않아(떨어진 재검사 조건이 같은 로트를 덮었다) 반품으로 비운 로트를 더한 뒤 다시 쟀다 |
| — | 지금 만료일을 가장 이른 합격 재검사의 것으로 골랐다 | `test_the_current_expiry_is_the_latest_passed_retests` — 처음 쓴 검사로는 빨개지지 않아 합격 재검사 둘을 둔 검사를 더한 뒤 다시 쟀다 |
| — | 지금 만료일을 라벨의 것으로만 냈다 | `test_a_passed_retest_renews_the_current_expiry_but_not_the_label` |
| — | 커서 다음을 `>` 대신 `>=` 로 읽었다 | `test_paging_through_the_list_neither_repeats_nor_skips` |
| — | 다음 쪽이 있는지를 `>=` 로 셌다 | `test_the_waiting_list_holds_only_the_lots_that_wait` — 처음 쓴 검사로는 빨개지지 않아 상한과 꼭 맞는 쪽의 커서를 보는 줄을 더한 뒤 다시 쟀다 |
| — | 커서의 거름과 요청의 거름을 견주지 않았다 | `test_a_cursor_this_list_did_not_issue_is_named` 의 `another-list` |
| — | 현장의 오늘을 하루 밀었다 | `test_a_passed_retest_renews_the_current_expiry_but_not_the_label` |

## 3단계 읽는 조각 B1 — ASCII 밖의 커서 (`d54ee4a`, PR #83 Codex 리뷰)

`app/api/cursor.py` 가 잡는 예외를 좁힌 뒤 `tests/test_lot_api.py` 를 돌렸다. 어긋냄 없이 돌린 대조군은 초록이다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| — | `ValueError` 대신 `JSONDecodeError` · `UnicodeDecodeError` 만 잡았다 | `test_a_cursor_this_list_did_not_issue_is_named` 의 `not-ascii` |

## 3단계 읽는 조각 B1 — 내준 그대로의 커서 (`2bc0f80`, PR #83 Codex 리뷰 2 라운드)

`app/api/cursor.py` 의 두 거절을 하나씩 껐다. 어긋냄 없이 돌린 대조군과 같은 트리의 `pytest` 전체(실제 PostgreSQL 16)는 초록이다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| — | 읽은 커서를 다시 내어 견주지 않았다 | `test_a_cursor_this_list_did_not_issue_is_named` 의 `a-stray-dollar` · `a-stray-dot` · `not-as-issued` — 끼운 글자가 하나일 때는 패딩이 어긋나 우연히 거절됐다. 넷을 끼워 디코더가 받는 모양으로 다시 쟀다 |
| — | id 의 위 끝(`integer`)을 묻지 않았다 | `test_a_cursor_this_list_did_not_issue_is_named` 의 `beyond-integer` |

## 3단계 읽는 조각 B1 — 경로마다 가른 거절 이름 (`8a47ece`, PR #83 Codex 리뷰 3 라운드)

`app/api/app.py` · `app/api/schemas.py` 의 선언을 하나씩 되돌렸다. 어긋냄 없이 돌린 대조군과 같은 트리의 `pytest` 전체(실제 PostgreSQL 16)는 초록이다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| — | 로트 하나의 422 에 목록의 본문(`LotListRefused`)을 실었다 | `test_the_spec_declares_what_the_read_paths_answer` |
| — | 목록 경로에도 업무의 404 를 선언했다 | `test_the_spec_declares_what_the_read_paths_answer` |
| — | 목록의 이름에 `unknown_lot` 을 더했다 | `test_the_spec_declares_what_the_read_paths_answer` |
| — | 로트 하나의 이름에 `cursor_is_not_readable` 을 더했다 | `test_the_spec_declares_what_the_read_paths_answer` |
| — | 스펙 산문을 「400 · 404 · 405 · 500 은 라우트 밖의 일이다」로 되돌렸다 | `test_the_spec_declares_what_the_read_paths_answer` |

## 3단계 읽는 조각 B2 — 계약의 호환 판정 (`c23b31d`, ADR 0018)

`app/api/compat.py` 의 가름을 하나씩 어긋낸 뒤 `tests/test_contract_judgment.py` 를 돌렸다. 마지막 넷은 판정 테스트 자체를 실제 스펙으로 돌린 것이다 — 기준을 이 PR 의 첫 커밋(`c23cdb1`, 판 `1.0`)으로 주고 코드를 어긋냈다. 어긋냄 없이 돌린 대조군과 같은 트리의 `pytest` 전체(실제 PostgreSQL 16)는 초록이다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| — | 옛 판의 앞자리가 0 이어도 창이 열려 있던 것으로 보지 않았다 | `test_a_window_that_was_open_takes_anything` · `test_the_version_moves_as_far_as_the_contract_moved`(기준 `origin/main` 이 `0.1` 이다) |
| — | 깨는 변경에도 판이 (앞자리, 뒷자리) 순서로 오르기만 하면 받았다 | `test_the_judgment_asks_for_as_far_as_the_contract_moved` 의 `*-breaks` 여섯 · `test_a_renamed_name_breaks` · `test_a_name_declared_breaking_moves_the_first_place` · `test_an_answer_bound_moves_the_other_way` |
| — | 계약이 그대로인데 판이 움직인 것을 받았다 | `test_the_judgment_asks_for_as_far_as_the_contract_moved` 의 `prose-is-not-the-contract` |
| — | 기존 경로에 새로 나가는 이름을 선언 없이 넓히는 변경으로 셌다 | `test_a_new_name_on_an_old_path_needs_the_authors_word` 외 넷 |
| — | 넓히는 변경이라는 선언의 근거를 옛 사진과 견주지 않았다 | `test_a_name_declared_widening_must_point_at_an_input_the_old_schema_did_not_take` · `test_a_new_enum_value_in_the_request_is_a_reason_for_a_new_name` |
| — | 경계의 변화를 요청 · 응답 가리지 않고 요청처럼 셌다 | `test_an_answer_bound_moves_the_other_way` — 처음 쓴 검사로는 빨개지지 않아(응답의 경계를 움직이는 경우가 없었다) 그 검사를 더한 뒤 다시 쟀다 |
| — | 요청의 칸이 필수가 되는 것을 넓히는 변경으로 셌다 | `test_the_judgment_asks_for_as_far_as_the_contract_moved` 의 `a-required-request-field-breaks` |
| — | 새 상태 코드를 넓히는 변경으로 셌다 | `test_the_judgment_asks_for_as_far_as_the_contract_moved` 의 `a-new-status-breaks` |
| — | 선언을 지금 판의 키만이 아니라 모든 판의 키에서 읽었다 | `test_a_declaration_of_another_version_is_not_read` |
| — | 글(`description` 등)을 계약으로 셌다 | `test_the_judgment_asks_for_as_far_as_the_contract_moved` 의 `prose-is-not-the-contract` |
| — | 계약을 그대로 두고 `API_VERSION` 만 `1.1` 로 올렸다 | `test_the_version_moves_as_far_as_the_contract_moved` |
| — | `unknown_lot` 을 `lot_is_unknown` 으로 바꿨다 | `test_the_version_moves_as_far_as_the_contract_moved` — 선언이 없다는 것과 깨는 변경에 앞자리가 오르지 않았다는 것 둘을 낸다 |
| — | 기준을 없는 리비전으로 주었다 | `test_the_version_moves_as_far_as_the_contract_moved` — 건너뛰지 않고 실패한다 |

## 3단계 읽는 조각 B2 — 가르지 않는 칸 · `$ref` 옆 제약 · 로컬 기준 (`a5232ec`, PR #84 Codex 리뷰 1 라운드)

`app/api/compat.py` 의 고침을 하나씩 되돌린 뒤 `tests/test_contract_judgment.py` 를 돌렸다. 마지막 줄은 원격이 `up` 이라는 이름인 클론(로컬 `main` 은 `0947f09`)에서 `ERP_CONTRACT_BASELINE` 없이 판정 테스트를 돌린 것이다. 어긋냄 없이 돌린 대조군과 같은 트리의 `pytest` 전체(실제 PostgreSQL 16)는 초록이다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| — | 경로의 나머지 칸(`operationId` · `security` …)을 견주지 않았다 | `test_the_judgment_asks_for_as_far_as_the_contract_moved` 의 `security-on-a-path-breaks` · `a-renamed-operation-breaks` · `test_security_for_every_path_and_its_schemes_are_each_seen` |
| — | 경로 밖의 칸(`securitySchemes` 등)을 견주지 않았다 | `test_security_for_every_path_and_its_schemes_are_each_seen` — 처음 쓴 검사로는 빨개지지 않아(머리의 `security` 와 함께 바꿔 하나만 보아도 빨갰다) 둘을 따로 어긋내는 검사를 더한 뒤 다시 쟀다 |
| — | 스펙 머리의 `security` 를 경로에 물려주지 않았다 | `test_security_for_every_path_and_its_schemes_are_each_seen` — 같은 까닭으로 같은 검사를 더한 뒤 다시 쟀다 |
| — | `$ref` 옆의 제약을 버렸다 | `test_the_judgment_asks_for_as_far_as_the_contract_moved` 의 `a-bound-beside-a-ref-is-seen` |
| — | 경로 머리의 인자를 견주지 않았다 | `test_the_judgment_asks_for_as_far_as_the_contract_moved` 의 `a-required-path-input-breaks` |
| — | 로컬 기준을 `origin/main` 하나로 되돌렸다 | `test_the_version_moves_as_far_as_the_contract_moved` — 원격 이름이 다른 클론에서 기준을 읽지 못한다 |

## 3단계 읽는 조각 B2 — 판정이 아는 모양 (`0e8c991`, PR #84 Codex 리뷰 2 라운드 · ADR 0021)

`app/api/compat.py` 의 거절과 고침을 하나씩 껐다. 껐을 때 `tests/test_contract_judgment.py` 에서 빨개진 검사를 적었다. 어긋냄 없이 돌린 대조군과 같은 트리의 `pytest` 전체(실제 PostgreSQL 16)는 초록이다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| — | 판정이 모양을 묻지 않고 견줬다 | `test_a_shape_the_judgment_does_not_know_is_refused` 의 `a-schema-that-holds-itself` |
| — | 모르는 칸을 거절하지 않았다 | `test_a_shape_the_judgment_does_not_know_is_refused` 의 여덟(`security-*` · `an-input-on-the-path-item` · `one-of` · `const` · `a-path-item-ref` · `encoding`) |
| — | `$ref` 옆의 칸을 거절하지 않았다 | `test_a_shape_the_judgment_does_not_know_is_refused` 의 `a-bound-beside-a-ref` — 처음 쓴 검사로는 빨개지지 않아(옆에 둔 `maxProperties` 가 모르는 키라 따로 걸렸다) 아는 키(`maxLength`)로 바꾼 뒤 다시 쟀다 |
| — | 제 자신을 가리키는 `$ref` 를 거절하지 않았다 | `test_a_shape_the_judgment_does_not_know_is_refused` 의 `a-schema-that-holds-itself` |
| — | 모르는 칸을 받는 요청 객체를 거절하지 않았다 | `test_a_shape_the_judgment_does_not_know_is_refused` 의 `a-request-object-that-takes-any-field` |
| — | 모르는 미디어 타입을 거절하지 않았다 | `test_a_shape_the_judgment_does_not_know_is_refused` 의 `a-form-body` |
| — | 포함 · 배제 경계의 쌍을 견주지 않았다 | `test_an_inclusive_and_an_exclusive_bound_are_one_constraint` · `test_the_judgment_asks_for_as_far_as_the_contract_moved` 의 `a-looser-request-bound-widens` · `a-tighter-request-bound-breaks` |
| — | 값을 파이썬의 `==` 로 견줬다 | `test_a_boolean_is_not_a_number` |
| — | `operationId` 를 견주지 않았다 | `test_the_judgment_asks_for_as_far_as_the_contract_moved` 의 `a-renamed-operation-breaks` |

## 3단계 읽는 조각 B2 — 없던 anyOf · 근거 값의 제약 · 헤더 대소문자 (`ad7ff81`, PR #84 Codex 리뷰 3 라운드)

`app/api/compat.py` 의 고침을 하나씩 되돌린 뒤 `tests/test_contract_judgment.py` 를 돌렸다. 어긋냄 없이 돌린 대조군과 같은 트리의 `pytest` 전체(실제 PostgreSQL 16)는 초록이다. 같은 커밋이 고친 CI 의 기준(머지 커밋의 첫 부모)은 로컬에서 어긋낼 수 없다 — CI 실행 로그의 「계약의 기준」 스텝이 받은 커밋이 그것을 보인다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| — | 없던 `anyOf` 를 갈래 0 으로 읽었다 | `test_an_any_of_that_was_not_there_was_no_constraint` |
| — | 응답 헤더 이름을 철자대로 견줬다 | `test_a_header_name_is_the_same_in_any_case` |
| — | 근거 값의 길이를 묻지 않았다 | `test_a_reason_must_be_a_value_the_new_schema_takes_whole` |

## 3단계 읽는 조각 B2 — 한 칸 더 좁힌 모양 (`d58c9f3`, PR #84 Codex 리뷰 4 라운드)

`app/api/compat.py` 의 거절을 하나씩 껐다. 껐을 때 `tests/test_contract_judgment.py` 에서 빨개진 검사를 적었다. 어긋냄 없이 돌린 대조군과 같은 트리의 `pytest` 전체(실제 PostgreSQL 16)는 초록이다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| — | 문자열이 아닌 열거 값을 받았다 | `test_a_shape_the_judgment_does_not_know_is_refused` 의 `an-enum-of-numbers` |
| — | 헤더 인자를 받았다 | `test_a_shape_the_judgment_does_not_know_is_refused` 의 `a-header-input` |
| — | 같은 경로 · 이름의 선언 둘을 받았다 | `test_two_declarations_of_one_name_are_refused` |
| — | 배열을 근거의 값으로 받았다 | `test_a_reason_value_is_a_scalar` |

## 3단계 읽는 조각 B2 — 처음 서는 이름 목록 · anyOf 옆 제약 (`f6dde51`, PR #84 Codex 리뷰 5 라운드)

`app/api/compat.py` 의 고침을 하나씩 되돌린 뒤 `tests/test_contract_judgment.py` 를 돌렸다. 어긋냄 없이 돌린 대조군과 같은 트리의 `pytest` 전체(실제 PostgreSQL 16)는 초록이다. 3 라운드의 「없던 `anyOf`」 검사는 `anyOf` 옆 제약을 거절하게 되며 제약이 없던 스키마 위로 옮겼고, 같은 어긋냄으로 다시 쟀다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| — | 처음 서는 `x-known-values` 를 통째로 깨는 변경으로 셌다 | `test_the_first_known_name_is_an_addition_like_any_other` |
| — | `anyOf` 옆의 제약을 받았다 | `test_a_shape_the_judgment_does_not_know_is_refused` 의 `a-constraint-beside-any-of` |
| — | 없던 `anyOf` 를 갈래 0 으로 읽었다 | `test_an_any_of_that_was_not_there_was_no_constraint` |

## 3단계 읽는 조각 B2 — 닫힌 응답 객체 · 형식이 붙은 근거 (`249e57b`, PR #84 Codex 리뷰 7 라운드)

`app/api/compat.py` 의 거절을 하나씩 껐다. 껐을 때 `tests/test_contract_judgment.py` 에서 빨개진 검사를 적었다. 어긋냄 없이 돌린 대조군과 같은 트리의 `pytest` 전체(실제 PostgreSQL 16)는 초록이다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| — | 응답 객체의 `additionalProperties` 를 받았다 | `test_a_shape_the_judgment_does_not_know_is_refused` 의 `a-closed-answer-object` |
| — | 형식이 붙은 칸의 값을 근거로 받았다 | `test_a_formatted_value_is_not_a_reason` |

## 3단계 읽는 조각 B2 — 갈래를 지나는 근거 · 요청의 열린 이름 (`6e71697`, PR #84 Codex 리뷰 8 라운드)

`app/api/compat.py` 의 고침을 하나씩 되돌린 뒤 `tests/test_contract_judgment.py` 를 돌렸다. 어긋냄 없이 돌린 대조군과 같은 트리의 `pytest` 전체(실제 PostgreSQL 16)는 초록이다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| — | 요청의 `x-known-values` 를 받았다 | `test_a_request_with_known_values_is_refused` |
| — | 근거의 자리가 갈래를 지나도 그 까닭을 내지 않았다 | `test_a_reason_that_crosses_branches_is_refused` — 처음 쓴 검사로는 빨개지지 않아(다른 까닭으로 빨갰고, 확인한 낱말이 경로 이름에도 들어 있었다) 그 까닭의 문구를 보게 고친 뒤 다시 쟀다 |
| — | 근거의 자리를 첫 갈래로 내려가 찾았다 | `test_a_reason_that_crosses_branches_is_refused` |

## 3단계 읽는 조각 B2 — 겹치는 경로 · 값 없는 근거 (`979930d`, PR #84 Codex 리뷰 9 라운드)

`app/api/compat.py` 의 고침을 하나씩 되돌린 뒤 `tests/test_contract_judgment.py` 를 돌렸다. 어긋냄 없이 돌린 대조군과 같은 트리의 `pytest` 전체(실제 PostgreSQL 16)는 초록이다. 같은 커밋이 고친 CI 의 취소 규칙(`main` 은 취소하지 않는다)은 로컬에서 어긋낼 수 없다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| — | 기존 경로의 틀과 겹치는 새 경로를 넓히는 변경으로 셌다 | `test_a_new_path_over_an_old_template_breaks` 의 둘 |
| — | 값 없이 칸만 든 근거를 받았다 | `test_a_reason_names_a_value` |

## 3단계 읽는 조각 B2 — 겹치는 경로 틀 · 같은 operationId · 이름 목록의 모양 (`89e357e`, PR #84 Codex 리뷰 10 라운드)

`app/api/compat.py` 의 거절을 하나씩 껐다. 껐을 때 `tests/test_contract_judgment.py` 에서 빨개진 검사를 적었다. 어긋냄 없이 돌린 대조군과 같은 트리의 `pytest` 전체(실제 PostgreSQL 16)는 초록이다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| — | 같은 메서드에 겹치는 경로 틀을 받았다 | `test_overlapping_path_templates_are_refused` 의 둘 |
| — | 같은 `operationId` 둘을 받았다 | `test_an_operation_id_is_used_once` |
| — | 문자열인 `x-known-values` 를 받았다 | `test_known_values_are_a_list_of_strings` |

## 감사 ㊵ 의 고침 — 옛 서버가 무시하던 근거 · 목록 한 줄에 검사 하나 (`49b7d14`, 감사 NC-227 · 228)

`app/api/compat.py` 의 분기를 하나씩 어긋낸 뒤 `tests/test_contract_judgment.py` 를 돌렸다. 어긋냄 없이 돌린 대조군과 같은 트리의 `pytest` 전체(실제 PostgreSQL 16)는 초록이다. NC-228 의 어긋냄은 감사자가 든 분기 가운데 판이 덜 오르는 방향을 골랐다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 227 | 옛 경로에 없던 쿼리 인자를 근거로 받았다 | `test_an_input_the_old_server_ignored_is_not_a_reason` |
| 227 | 본문이 없던 경로의 본문을 근거로 받았다 | `test_an_input_the_old_server_ignored_is_not_a_reason` |
| 228 | 스펙 형식의 판(`openapi`)이 바뀌어도 세지 않았다 | `test_each_line_of_the_list_moves_the_version` 의 `the-spec-format-moves` |
| 228 | 요청에 선 필수 인자를 넓히는 변경으로 셌다 | `test_each_line_of_the_list_moves_the_version` 의 `a-required-input-comes` |
| 228 | 사라진 인자를 넓히는 변경으로 셌다 | `test_each_line_of_the_list_moves_the_version` 의 `an-input-goes` |
| 228 | 상태 코드가 서거나 사라져도 세지 않았다 | `test_the_judgment_asks_for_as_far_as_the_contract_moved` 의 `a-new-status-breaks` |
| 228 | 사라진 요청 본문을 넓히는 변경으로 셌다 | `test_each_line_of_the_list_moves_the_version` 의 `a-body-goes` |
| 228 | 필수로 선 요청 본문을 넓히는 변경으로 셌다 | `test_each_line_of_the_list_moves_the_version` 의 `a-required-body-comes` |
| 228 | 인자가 필수가 되는 것을 넓히는 변경으로 셌다 | `test_each_line_of_the_list_moves_the_version` 의 `an-input-becomes-required` |
| 228 | 응답 헤더 · 미디어 타입이 사라져도 세지 않았다 | `test_each_line_of_the_list_moves_the_version` 의 `an-answer-header-goes` |
| 228 | 사라진 칸을 넓히는 변경으로 셌다 | `test_each_line_of_the_list_moves_the_version` 의 `an-answer-field-goes` |
| 228 | 요청의 `anyOf` 가 다 사라지는 것을 깨는 변경으로 셌다 | `test_each_line_of_the_list_moves_the_version` 의 `request-branches-go` |
| 228 | 요청 열거에서 빠진 값을 넓히는 변경으로 셌다 | `test_each_line_of_the_list_moves_the_version` 의 `a-request-value-goes` |
| 228 | 요청에 새로 선 경계를 넓히는 변경으로 셌다 | `test_each_line_of_the_list_moves_the_version` 의 `a-request-bound-comes` |
| 228 | 포함 · 배제 쌍의 경계가 사라지는 것(`after is None`)을 깨는 변경으로 셌다 | **없다 — 통과했다** |
| 228 | 같은 어긋냄 — 위 끝이 사라지는 줄을 매개변수에 더한 뒤 | `test_each_line_of_the_list_moves_the_version` 의 `a-request-upper-end-goes` |
| 228 | 깨는 변경 선언에 든 근거(`"because"`)를 받았다 | `test_a_breaking_declaration_carries_no_reason` |
| 228 | 인자 이름이 없는 짧은 근거 자리를 받았다 | `test_a_reason_the_new_schema_does_not_take_is_refused` 의 `a-place-without-a-name` |
| 228 | 근거의 값을 새 스키마의 수 경계와 견주지 않았다 | `test_a_name_declared_widening_must_point_at_an_input_the_old_schema_did_not_take` |
| 228 | `_is_type` 이 불리언을 정수로 받았다 | **없다 — 통과했다** — 등가 어긋냄이다. 불리언은 수 경계를 건너뛰므로 옛 정수 칸도 `True` 를 받아 「받던 요청」으로 같은 답이 난다(`test_a_boolean_is_not_a_reason_for_an_integer` 독스트링) |
| — | `_same` 을 파이썬의 `==` 로 되돌렸다(감사 ㊵ 낮음-2) | `test_a_default_that_turns_from_false_to_zero_moves` |

**앞 묶음의 줄이 든 검사 가운데 지금은 없는 것**(감사 ㊵ 낮음-2). 옛 줄은 소급해 고치지 않고 여기 적는다 —
그 줄의 「빨개진 검사」는 그 커밋에서 참이었고, 뒤의 커밋이 검사를 걷었다.

- `test_security_for_every_path_and_its_schemes` · `security-on-a-path-breaks` · `a-bound-beside-a-ref-is-seen` ·
  `a-required-path-input-breaks` — `7207002`(ADR 0021)가 걷었다. 그 모양은 이제 견주지 않고
  `test_a_shape_the_judgment_does_not_know_is_refused` 가 거절을 문다
- `test_a_boolean_is_not_a_number` — `d58c9f3` 가 걷었다(열거를 문자열로 좁혀 수 열거를 거절한다). 그 뒤
  `_same` 을 무는 검사가 없었다 — 위 표의 마지막 줄이 다시 세웠다
- `test_a_new_path_over_an_old_template_breaks` — `89e357e` 가 걷었다. 겹치는 틀은 이제
  `test_overlapping_path_templates_are_refused` 가 거절로 문다

## 감사 ㊶ 의 고침 — 갈래 수 · 선다 · 풀린다 줄 · 불리언 가지 (`9e2358d`, 감사 NC-229 · 228)

`app/api/compat.py` 의 분기를 하나씩 어긋낸 뒤 `tests/test_contract_judgment.py` 를 돌렸다. 어긋냄 없이 돌린 대조군과 같은 트리의 `pytest` 전체(실제 PostgreSQL 16)는 초록이다. NC-229 는 `test_each_line_of_the_list_moves_the_version` 에 매개변수 줄을 더해 고쳤다 — 단언과 `compat.py` 는 그대로이고, 줄을 짓는 준비 코드를 새로 더했다. 어긋냄마다 빨개진 줄은 그 어긋냄이 겨눈 매개변수 하나뿐이었다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 229 | 응답 본문의 미디어 타입이 서는 것을 넓히는 변경으로 셌다 | `test_each_line_of_the_list_moves_the_version` 의 `an-answer-media-comes` |
| 229 | 응답 헤더가 서는 것을 깨는 변경으로 셌다 | `test_each_line_of_the_list_moves_the_version` 의 `an-answer-header-comes` |
| 229 | `anyOf` 에 갈래가 서는 것을 응답에서도 넓히는 변경으로 셌다 | `test_each_line_of_the_list_moves_the_version` 의 `an-answer-branch-comes` |
| 229 | `anyOf` 에 갈래가 서는 것을 요청에서도 깨는 변경으로 셌다 | `test_each_line_of_the_list_moves_the_version` 의 `a-request-branch-comes` |
| 229 | `anyOf` 에서 갈래가 빠지는 것을 요청에서도 넓히는 변경으로 셌다 | `test_each_line_of_the_list_moves_the_version` 의 `a-request-branch-goes` |
| 229 | `anyOf` 에서 갈래가 빠지는 것을 응답에서도 깨는 변경으로 셌다 | `test_each_line_of_the_list_moves_the_version` 의 `an-answer-branch-goes` |
| 229 | 응답 칸이 필수가 되는 것을 깨는 변경으로 셌다 | `test_each_line_of_the_list_moves_the_version` 의 `an-answer-field-is-required` |
| 229 | 요청 칸의 필수가 풀리는 것을 깨는 변경으로 셌다 | `test_each_line_of_the_list_moves_the_version` 의 `a-request-field-is-let-go` |
| 229 | 필수 아닌 인자가 서는 것을 깨는 변경으로 셌다 | `test_each_line_of_the_list_moves_the_version` 의 `an-optional-input-comes` |
| 228 | `_is_type` 이 불리언을 정수로 받았다(「감사 ㊵ 의 고침」 묶음의 초록 줄과 같은 어긋냄) | `test_a_boolean_is_not_a_reason_where_an_integer_branch_comes` |

## 감사 ㊶ 의 고침 — 불리언 근거를 본문에서 잰다 (`a9df507`, PR #92 Codex 리뷰)

위 묶음의 불리언 검사는 쿼리 인자에서 쟀는데, 쿼리 값은 언제나 문자열로 와 옛 `str` 인자가 `?mode=1` 도 받는다 — 검사가
거짓 근거(`1`)를 맞는 예로 못박았다. 같은 검사를 본문 칸으로 옮겨 다시 쟀다. 어긋냄 없이 돌린 대조군은 초록이다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 228 | `_is_type` 이 불리언을 정수로 받았다 | `test_a_boolean_is_not_a_reason_where_an_integer_branch_comes` |
