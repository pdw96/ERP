# ADR 0006 — 잠금 도구의 click 을 묶지 않는다 — 머리의 오표시는 lock.sh 가 지운다

- 상태: 채택
- 날짜: 2026-09-29
- 정한 사람: 저장소 소유자

## 맥락

ADR 0004 는 잠금 도구(`requirements-tools.in`)에 `click<8.2` 를 두었다. click 8.2 이상에서
pip-compile(7.6.1)이 잠금 머리의 명령 줄에 `--no-index` 를 잘못 찍기 때문이다 — 그 명령을
그대로 따라 치면 인덱스 없이 돌아 실패한다.

Dependabot 의 첫 묶음 PR(ERP#25)이 그 범위를 `click<8.6` 으로 넓혔다. 묶어 두면 매주 같은 PR 이
온다.

그 머리 줄을 읽는 것은 사람뿐이다. `lock.sh --check` 는 버전만 견주고, Dependabot 이 잠금에서
옵션을 읽을 때 보는 것(`--hash` · `--strip-extras` · `--pre` 등)에 `--no-index` 는 없다
(dependabot-core 의 `pip_compile_options_from_compiled_file`).

## 대안

- **가) 묶지 않는다.** 머리의 오표시는 `lock.sh` 가 만든 직후 지운다.
- **나) `dependabot.yml` 에서 click 을 무시한다.** 무시는 「디렉터리 + 이름」으로만 걸 수 있어,
  런타임 · 개발 잠금의 click(uvicorn 이 끌어온다)까지 갱신이 멈춘다 — ADR 0003 을 세운 이유와
  부딪힌다.
- **다) 묶은 채 둔다.** 매주 같은 PR 을 사람이 닫는다.

## 결정

**가).** `requirements-tools.in` 에서 click 을 뺐다. `scripts/lock.sh` 가 잠금을 쓸 때마다 머리의
`#    pip-compile` 줄에서 `--no-index` 를 지운다.

## 결과

- click 8.5 로 도는 도구 환경에서 만든 잠금이 click 8.1 로 만든 것과 바이트 단위로 같다 — 지우는
  줄을 빼면 `--no-index` 가 찍히는 것도 확인했다.
- **pip-tools 가 그 버그를 고치면** 지우는 줄은 아무것도 바꾸지 않는다. 남겨 두어도 해가 없다.
- **Dependabot 이 만든 잠금**의 머리는 Dependabot 의 도구가 쓴다 — 그 줄에 무엇이 찍히든 견주기는
  버전만 본다.
