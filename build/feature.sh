#!/usr/bin/env bash
set -euo pipefail

# Feature work happens in its own worktree, so a hotfix on master never has to wait for it.
#   build/feature.sh new NAME      branch NAME off master in ../boredroom-NAME
#   build/feature.sh list          every feature: how far ahead/behind master, uncommitted, on stage
#   build/feature.sh stage NAME    put NAME on stage (build/deploy.sh stage, from its worktree)
#   build/feature.sh rebase [NAME] replay NAME (default: every feature) onto master
#   build/feature.sh land NAME     fast-forward master to NAME, ready for promote
#   build/feature.sh done NAME     remove NAME's worktree and branch, once it's on master
#
# The main checkout (the repo's first worktree) stays on master: hotfixes are made and
# committed there, go to stage, then promote. promote rebases every feature afterwards.

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
MAIN="$(git -C "$ROOT" worktree list --porcelain | sed -n '1s/^worktree //p')"
g() { git -C "$MAIN" "$@"; }
tree() { echo "$(dirname "$MAIN")/boredroom-$1"; }
need() {
  [[ -n "${1:-}" ]] || { sed -n '4,10p' "$0" >&2; exit 1; }
  g show-ref -q --verify "refs/heads/$1" || { echo "no feature called $1; see: build/feature.sh list" >&2; exit 1; }
}
# feature branches: every worktree's branch except master
features() { g worktree list --porcelain | sed -n 's|^branch refs/heads/||p' | grep -vx master || true; }
where() { g worktree list --porcelain | awk -v b="refs/heads/$1" '/^worktree /{w=substr($0,10)} $0=="branch "b{print w}'; }

rebase_one() {
  local name=$1 w; w=$(where "$name")
  [[ -n "$w" ]] || { echo "$name has no worktree; skipped"; return; }
  if g merge-base --is-ancestor master "$name"; then echo "$name: already on master's latest"; return; fi
  if git -C "$w" rebase --autostash master >/dev/null 2>&1; then
    echo "$name: rebased onto master ($(g rev-parse --short master))"
  else
    git -C "$w" rebase --abort >/dev/null 2>&1 || true
    echo "$name: conflicts with master; left as it was. rebase it by hand: cd $w && git rebase --autostash master" >&2
    return 1
  fi
}

CMD="${1:-}"; shift || true
case "$CMD" in
  new)
    name="${1:?name the feature: build/feature.sh new NAME}"
    [[ "$name" =~ ^[a-z0-9][a-z0-9-]*$ ]] || { echo "use lowercase letters, digits and dashes" >&2; exit 1; }
    w=$(tree "$name")
    g worktree add -q -b "$name" "$w" master
    # private and untracked material stays in the main checkout; the feature sees it through links
    ln -s "$MAIN/research" "$w/research"
    [[ -d "$MAIN/web/node_modules" ]] && (cd "$w/web" && npm ci --prefer-offline --no-audit --no-fund --silent)
    echo "feature $name is at $w. put it on stage with: build/feature.sh stage $name" ;;
  list)
    read -r sb sc sd < <(docker inspect -f '{{index .Config.Labels "boredroom.branch"}} {{index .Config.Labels "boredroom.commit"}} {{index .Config.Labels "boredroom.dirty"}}' boredroom:stage 2>/dev/null) || true
    if [[ "${sc:-}" =~ ^[0-9a-f]{40}$ ]]; then echo "stage runs ${sb:-a detached HEAD} at ${sc:0:7}$([[ "${sd:-}" == 1 ]] && echo ', with uncommitted changes')"
    else echo "stage runs an image from before builds were labelled"; fi
    for f in $(features); do
      w=$(where "$f"); read -r behind ahead < <(g rev-list --left-right --count "master...$f")
      dirty=$([[ -n "$(git -C "$w" status --porcelain)" ]] && echo ", uncommitted changes" || true)
      printf '  %-16s %d ahead, %d behind master%s  %s\n' "$f" "$ahead" "$behind" "$dirty" "$w"
    done ;;
  stage)
    need "${1:-}"; w=$(where "$1")
    [[ -n "$w" ]] || { echo "$1 has no worktree" >&2; exit 1; }
    "$w/build/deploy.sh" stage ;;
  rebase)
    if [[ -n "${1:-}" ]]; then need "$1"; rebase_one "$1"
    else rc=0; for f in $(features); do rebase_one "$f" || rc=1; done; exit $rc; fi ;;
  land)
    need "${1:-}"; name=$1; w=$(where "$name")
    [[ "$(g branch --show-current)" == master && -z "$(g status --porcelain)" ]] ||
      { echo "the main checkout ($MAIN) has to be on master with nothing uncommitted" >&2; exit 1; }
    [[ -z "$(git -C "$w" status --porcelain)" ]] || { echo "$name has uncommitted changes; commit them first" >&2; exit 1; }
    g merge-base --is-ancestor master "$name" || { echo "$name is behind master; run: build/feature.sh rebase $name" >&2; exit 1; }
    g merge -q --ff-only "$name"
    echo "master is now $name ($(g rev-parse --short master))."
    s=$(docker inspect -f '{{index .Config.Labels "boredroom.commit"}}' boredroom:stage 2>/dev/null) || true
    if [[ "$s" == "$(g rev-parse master)" ]]; then echo "stage already runs exactly this: build/deploy.sh promote"
    else echo "stage runs something else: build/feature.sh stage $name, check it, then build/deploy.sh promote"; fi ;;
  done)
    need "${1:-}"; name=$1; w=$(where "$name")
    g merge-base --is-ancestor "$name" master || { echo "$name isn't on master yet (land it first); nothing removed" >&2; exit 1; }
    if [[ -n "$w" ]]; then
      [[ -z "$(git -C "$w" status --porcelain)" ]] || { echo "$w has uncommitted changes; nothing removed" >&2; exit 1; }
      rm -f "$w/research"
      g worktree remove "$w"
    fi
    g branch -q -d "$name" && echo "removed $name" ;;
  *)
    sed -n '4,13p' "$0"; exit 1 ;;
esac
