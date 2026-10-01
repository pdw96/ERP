# ADR 0009 — 보드 토큰에 `read:org` · `read:discussion` 을 더한다 (ADR 0008 의 토큰 범위를 대체)

- 상태: 채택
- 날짜: 2026-10-01
- 정한 사람: 저장소 소유자

## 맥락

ADR 0008 은 보드 토큰(`PROJECT_TOKEN`, 클래식 개인 토큰)의 범위를 **`project` 하나**로 정했다. 그 범위로
첫 실제 실행(이슈 #43, run 36798314731)이 `gh project view` 에서 멈췄다 — 실행 로그의 말은 `unknown owner type`
하나였다(저장소 소유자가 Actions 화면에서 읽었다. 클라우드 세션은 실행 로그를 내려받을 수 없다).

`gh project --owner` 는 소유자가 사용자인지 조직인지 먼저 가리는데, `project` 범위만으로는 그 조회가 실패하고
모든 실패가 같은 말(`unknown owner type`)로 나온다. 같은 일을 겪은 다른 저장소들이 필요한 범위로 `read:org` ·
`read:discussion` 을 든다(cli/cli#8885, luketmoss/thrive#206, Elhan-Salaji/Media-Tracker#114).

## 대안

- **가) 토큰에 `read:org` · `read:discussion` 을 더한다.** 둘 다 읽기 전용이다. 토큰 값은 그대로라 시크릿을
  다시 넣지 않는다
- **나) 워크플로가 `gh project` 대신 GraphQL 을 직접 부른다.** 노드 ID 로 부르면 소유자 조회가 없어 `project`
  하나로 된다(mtharrison/edgewise#23). 코드가 커지고, 토큰이 `main` 실행에만 가므로(ADR 0008) 고칠 때마다
  머지해야 시험할 수 있다

## 결정

**가).** 범위는 `project` · `read:org` · `read:discussion` 이다. `repo` 는 여전히 필요 없다(공개 저장소).

## 결과

범위를 더한 뒤 같은 이슈 #43 으로 `main` 에서 쟀다(2026-10-01):

| 시험 | 실행 | 결과 |
|---|---|---|
| 없는 Status 값 | 36799270759 | 빨강 — 「Status 칸에 … 없다 — 보드는 바꾸지 않았다」(ADR 0008 의 순서대로 보드는 건드리지 않았다) |
| 넣기만 | 36799302911 | 초록 |
| 같은 이슈를 다시 넣고 `In Progress` 로 | 36799370457 | 초록 — 이미 있는 카드에 `item-add` 가 실패하지 않는다. PR #42 Codex 리뷰가 보류로 남긴 지적이 반박됐다. `field-list` 의 출력 모양도 워크플로의 가정과 같다 |
| `main` 이 아닌 브랜치로 | 36799409922 | 거절 — 「Branch … is not allowed to deploy to project-board due to environment protection rules」. 단계가 하나도 돌지 않았다 |

`read:org` 는 소유자가 속한 조직의 소속 · 팀을, `read:discussion` 은 팀 토론을 읽을 수 있다 — 쓰기는 없다. 그 토큰은
여전히 환경 `project-board` 의 시크릿에만 둔다(ADR 0008).
