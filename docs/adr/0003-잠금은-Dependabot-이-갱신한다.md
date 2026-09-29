# ADR 0003 — 의존성 잠금은 Dependabot 이 매주 갱신한다

- 상태: 채택
- 날짜: 2026-09-29
- 정한 사람: 저장소 소유자

## 맥락

ADR 0002 로 하위 의존성까지 해시로 잠갔다. 그 전에는 설치할 때마다 하위 의존성의 최신판이
와서 보안 패치도 저절로 따라왔다(같은 성질이 starlette 사고를 냈다). 이제는 누군가 잠금을
다시 만들기 전까지 그대로 멈춘다.

## 대안

- **가) Dependabot.** 매주 잠금을 다시 만든 PR 을 연다. PR 이 주기적으로 쌓인다.
- **나) 주기적 수동 갱신.** 조각이 설 때마다 `pip-compile --upgrade` 를 돌린다. 사람이
  기억해야 한다 — 이 저장소가 거듭 적은 「사람이 매번 기억해야 하는 검사는 바쁠 때
  건너뛴다」의 그 모양이다.

## 결정

**가).** `.github/dependabot.yml` — pip · `/backend` · 매주. 부 · 수 버전은 한 PR 로 묶고,
주 버전은 따로 연다.

## 결과

- **파일 이름을 pip-tools 관례로 바꿨다** — 입력은 `requirements{,-dev}.in`, 잠금은
  `requirements{,-dev}.txt`. Dependabot 은 이 관례로만 pip-compile 잠금을 알아본다
  (dependabot-core 의 `PipCompileFileMatcher` 를 읽어 확인했다).
- 개발 입력이 런타임 잠금을 `-c requirements.txt` **줄**로 받는다. Dependabot 이 잠금 머리의
  `--constraint` 옵션을 옮겨 싣지 않기 때문이다.
- 갱신 PR 도 같은 CI 를 탄다. 입력과 잠금 · 두 잠금이 갈리면 떨어진다.
- **이 결정 밖:** 취약점이 공지된 날 바로 여는 PR(security updates)은 저장소 설정이다.
- **확인하지 못한 것:** Dependabot 이 `-c` 로 이은 두 잠금을 한 PR 에서 함께 올리는가.
  못 올리면 CI 의 「잠금」 스텝(ADR 0004)이 그 PR 에서 떨어진다 — 조용히 통과하지는
  않는다. 첫 갱신 PR 이 답한다.
