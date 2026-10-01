# ADR 0008 — 프로젝트 보드는 Actions 가 다룬다 — 클라우드 세션은 실행만 건다

- 상태: 채택
- 날짜: 2026-09-30
- 정한 사람: 저장소 소유자

## 맥락

이 저장소의 작업은 전부 Claude Code 클라우드 세션에서 한다. 할 일을 GitHub Projects 보드로 보기로 했는데,
클라우드 세션은 보드를 다룰 수 없다 — 실제로 쟀다(2026-09-30):

- GraphQL(`api.github.com/graphql`)은 403 이다 — 「GitHub GraphQL is not available from Claude Code sessions」.
  Projects v2 는 GraphQL 에만 있다
- REST 의 `users/pdw96/projectsV2` 도 403 이다 — 「sessions are bound to their configured repositories」
- 토큰을 바꿔 넣어도 같다. 가짜 토큰으로도 저장소 경로는 200, 막힌 경로는 403 이었다 — 프록시가 경로로 막고
  인증을 자기 것으로 붙인다

Claude Code 문서(Configure cloud environments 의 「GitHub proxy」)가 같은 것을 적는다 — 이 제한은 넣은 자격증명과
상관없이 걸리고, GraphQL 에만 있는 API(Projects v2)에는 프록시를 거쳐 닿을 수 없다.

## 대안

- **가) Actions 가 중계한다.** 저장소에 워크플로를 두고, 세션은 그 실행만 건다(저장소 범위라 통과한다). 보드는
  GitHub 의 러너가 사람의 토큰으로 다룬다
- **나) 보드의 기본 워크플로만 쓴다.** 라벨로 자동 추가 · 닫히면 Done. 토큰도 코드도 없지만 상태를 세션이 옮길 수 없다
- **다) Remote Control.** Claude Code 를 사람의 PC 에서 돌리고 클라우드 화면으로 조종한다. 실행이 로컬이라
  「전부 클라우드」가 깨지고 PC 가 켜져 있어야 한다
- **라) 자체 호스팅 환경.** Team · Enterprise 요금제의 공개 베타이고 러너 서버를 운영해야 한다

## 결정

**가).** `.github/workflows/project-board.yml` 이 수동 실행(`workflow_dispatch`)으로 「이슈 N 을 보드에 넣고
Status 를 X 로」를 받아 `gh project` 로 처리한다. 나)의 기본 워크플로는 함께 써도 된다 — 겹치지 않는다(자동 추가는
보드가, 상태 이동은 이 워크플로가).

토큰은 **클래식 개인 토큰의 `project` 범위 하나**이고, 저장소 시크릿이 아니라 **환경 `project-board` 의 시크릿**이다.
그 환경의 배포 브랜치는 `main` 하나다. 수동 실행은 아무 브랜치의 워크플로 판으로도 걸 수 있어(`--ref`), 저장소
시크릿이면 리뷰 안 된 브랜치의 코드가 토큰을 받는다(PR #42 Codex 리뷰). 환경 시크릿은 그 환경을 쓰는 잡에만, 환경의
규칙을 통과한 뒤에만 주어진다 — 그 규칙은 워크플로 글자가 아니라 저장소 설정이 건다. 세분화 토큰은 사용자 소유 Projects 에 쓸 수 없다(GitHub 문서
「Managing your personal access tokens」의 제한 목록). 이 저장소가 공개라 `repo` 범위는 필요 없다.

## 결과

- 소유자가 한 번 준비한다 — 보드, 환경 `project-board`(배포 브랜치 `main`)와 그 시크릿 `PROJECT_TOKEN`, 변수
  `PROJECT_NUMBER`. 절차는 워크플로 머리가 든다. 저장소 수준에 같은 이름의 시크릿을 남기지 않는다 — 남기면 다른
  브랜치의 판이 그것을 받는다
- Status 를 옮길 때는 값을 먼저 확인하고 카드를 넣는다 — 틀린 값이면 보드를 바꾸지 않고 멈춘다
- 토큰은 만료가 있다. 만료되면 워크플로가 빨갛게 멈춘다 — 조용히 건너뛰지 않는다
- 워크플로는 저장소 토큰을 쓰지 않는다(`permissions: {}`). 입력은 환경변수로만 셸에 넘긴다(스크립트 주입)
- `project` 범위는 소유자의 **모든** 사용자 소유 보드에 쓸 수 있다 — 이 저장소의 보드만으로 좁힐 길이 없다(세분화
  토큰을 못 쓰는 까닭과 같다). 그 토큰은 이 저장소의 환경 `project-board` 시크릿에만 둔다
- `gh project field-list` 의 출력 모양은 첫 실제 실행에서 확인한다 — 세션에서는 GraphQL 이 막혀 미리 돌려 볼 수 없다
