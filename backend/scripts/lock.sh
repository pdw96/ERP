#!/usr/bin/env bash
# **잠금을 다시 만든다 — 또는 다시 만들어 지금 잠금과 견준다**(ERP#22).
#
#     scripts/lock.sh            입력(.in)을 고친 뒤. 잠금(.txt) 셋을 해시까지 다시 쓴다
#     scripts/lock.sh --check    CI 의 「잠금」 스텝. 아무것도 쓰지 않고 갈린 것을 보인다
#
# 도구는 `requirements-tools.txt` 로 따로 깐 pip-compile 이다 — `LOCK_PIP_COMPILE` 로 가리킨다.
# **이름이 `PIP_` 로 시작하면 안 된다** — pip 이 그 환경변수를 자기 옵션(`PIP_COMPILE` 는
# `--compile`)으로 읽어 깨진다. 실제로 그렇게 깨졌다.
#
# **견주기는 버전만 본다. 해시는 보지 않는다.** 같은 버전에 새 휠이 올라오면 해시 목록이
# 늘어, 이 저장소가 아무것도 바꾸지 않은 PR 이 빨개진다. 해시는 설치(`--require-hashes`)가
# 문다.
#
# **이 스크립트가 못 보는 것**(W-6 ③): 처음부터 엉뚱한 패키지를 고른 것 — 입력이 부르면
# 충실히 다시 만든다. 그리고 PyPI 가 그 버전을 내리면(yank) 다시 만들기가 달리 풀릴 수 있다.
set -euo pipefail
cd "$(dirname "$0")/.."

LOCK_PIP_COMPILE="${LOCK_PIP_COMPILE:-pip-compile}"
# 순서가 뜻을 갖는다 — 개발 입력이 런타임 잠금을 `-c` 로 받으므로 런타임이 먼저다.
INPUTS=(requirements.in requirements-dev.in requirements-tools.in)

lock_all() {
  local src
  for src in "${INPUTS[@]}"; do
    "$LOCK_PIP_COMPILE" --quiet --allow-unsafe --strip-extras "$@" \
      --output-file="${src%.in}.txt" "$src"
    # click 8.2 이상에서 pip-compile 이 머리의 명령 줄에 `--no-index` 를 잘못 찍는다(ADR 0006).
    # 그 줄은 사람이 읽는 주석이라 지운다 — 버그가 고쳐지면 아무것도 바꾸지 않는다.
    sed -i -E '/^#    pip-compile /s/ --no-index//' "${src%.in}.txt"
  done
}

pins() {
  grep -oE '^[A-Za-z0-9][A-Za-z0-9._-]*==[^ ]+' "$1" | sort
}

if [[ "${1:-}" != "--check" ]]; then
  lock_all --generate-hashes
  exit 0
fi

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
cp requirements*.in requirements*.txt "$work"/
# 지금 잠금을 옮겨 두고 그 위에 다시 만든다 — pip-compile 은 출력 파일에 있는 버전을
# 먼저 고르므로, 입력이 그대로면 버전도 그대로 나온다. 새 파일로 풀면 그날의 최신판이
# 와서 아무것도 안 바꾼 PR 이 갈린다.
(cd "$work" && lock_all)

drift=0
for src in "${INPUTS[@]}"; do
  lock="${src%.in}.txt"
  if ! diff -u --label "$lock (저장소)" --label "$lock (다시 만든 것)" \
    <(pins "$lock") <(pins "$work/$lock"); then
    drift=1
  fi
done
if ((drift)); then
  echo "잠금이 입력에서 다시 나오지 않는다 — backend/ 에서 scripts/lock.sh 를 돌려 다시 만든다" >&2
  exit 1
fi
