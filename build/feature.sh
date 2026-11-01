#!/usr/bin/env bash
set -euo pipefail

# Every change, hotfixes included, is a feature: a branch cut from master in its own worktree.
#   build/feature.sh new NAME      cut NAME from master into ../boredroom-NAME
#   build/feature.sh stage NAME    rebase NAME onto master, then put it on stage
#   build/feature.sh list          every feature: ahead/behind master, uncommitted work, what stage runs
#   build/feature.sh rebase [NAME] replay NAME (default: every feature) onto master; any time
#   build/feature.sh promote NAME  NAME is on stage and approved: merge it into master, put master
#                                  on production and stage, rebase the other features
#   build/feature.sh done NAME     remove NAME's worktree and branch, once it's in master
#
# The main checkout (the repo's first worktree) stays on master, untouched by hand: master
# only moves when a feature is promoted, and production only runs master.

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
MAIN="$(git -C "$ROOT" worktree list --porcelain | sed -n '1s/^worktree //p')"
g() { git -C "$MAIN" "$@"; }
need() {
  [[ -n "${1:-}" ]] || { sed -n '4,11p' "$0" >&2; exit 1; }
  [[ "$1" != master ]] || { echo "master isn't a feature" >&2; exit 1; }
  g show-ref -q --verify "refs/heads/$1" || { echo "no feature called $1; see: build/feature.sh list" >&2; exit 1; }
}
features() { g worktree list --porcelain | sed -n 's|^branch refs/heads/||p' | grep -vx master || true; }
where() { g worktree list --porcelain | awk -v b="refs/heads/$1" '/^worktree /{w=substr($0,10)} $0=="branch "b{print w}'; }
clean() { [[ -z "$(git -C "$1" status --porcelain)" ]]; }
stage_label() { docker inspect -f "{{index .Config.Labels \"boredroom.$1\"}}" boredroom:stage 2>/dev/null | sed 's/^<no value>$//' || true; }

rebase_one() {
  local name=$1 w; w=$(where "$name")
  [[ -n "$w" ]] || { echo "$name has no worktree; skipped"; return; }
  if g merge-base --is-ancestor master "$name"; then echo "$name: already on master ($(g rev-parse --short master))"; return; fi
  if git -C "$w" rebase --autostash master >/dev/null 2>&1; then
    echo "$name: rebased onto master ($(g rev-parse --short master))"
  else
    git -C "$w" rebase --abort >/dev/null 2>&1 || true
    echo "$name: conflicts with master, left as it was. by hand: cd $w && git rebase --autostash master" >&2
    return 1
  fi
}

CMD="${1:-}"; shift || true
case "$CMD" in
  new)
    name="${1:?name the feature: build/feature.sh new NAME}"
    [[ "$name" =~ ^[a-z0-9][a-z0-9-]*$ && "$name" != master ]] || { echo "use lowercase letters, digits and dashes" >&2; exit 1; }
    w="$(dirname "$MAIN")/boredroom-$name"
    g worktree add -q -b "$name" "$w" master
    # private and untracked material stays in the main checkout; the feature sees it through links
    ln -s "$MAIN/research" "$w/research"
    [[ -d "$MAIN/web/node_modules" ]] && (cd "$w/web" && npm ci --prefer-offline --no-audit --no-fund --silent)
    echo "feature $name is at $w, cut from master ($(g rev-parse --short master)). stage it: build/feature.sh stage $name" ;;
  list)
    sb=$(stage_label branch); sc=$(stage_label commit)
    if [[ "$sc" =~ ^[0-9a-f]{40}$ ]]; then echo "stage runs ${sb:-a detached HEAD} at ${sc:0:7}$([[ "$(stage_label dirty)" == 1 ]] && echo ', with uncommitted changes')"
    else echo "stage runs an image from before builds were labelled"; fi
    echo "master is at $(g rev-parse --short master)"
    for f in $(features); do
      w=$(where "$f"); read -r behind ahead < <(g rev-list --left-right --count "master...$f")
      printf '  %-16s %d ahead, %d behind master%s  %s\n' "$f" "$ahead" "$behind" "$(clean "$w" || echo ', uncommitted changes')" "$w"
    done ;;
  stage)
    need "${1:-}"; w=$(where "$1")
    [[ -n "$w" ]] || { echo "$1 has no worktree" >&2; exit 1; }
    rebase_one "$1"
    "$w/build/deploy.sh" stage ;;
  rebase)
    if [[ -n "${1:-}" ]]; then need "$1"; rebase_one "$1"
    else rc=0; for f in $(features); do rebase_one "$f" || rc=1; done; exit $rc; fi ;;
  promote)
    need "${1:-}"; name=$1; w=$(where "$name"); head=$(g rev-parse "$name")
    [[ "$(g branch --show-current)" == master ]] && clean "$MAIN" ||
      { echo "the main checkout ($MAIN) has to be on master with nothing uncommitted" >&2; exit 1; }
    clean "$w" || { echo "$name has uncommitted changes: commit them, stage them, get them approved" >&2; exit 1; }
    g merge-base --is-ancestor master "$name" || { echo "$name isn't rebased onto master: build/feature.sh stage $name, check it again" >&2; exit 1; }
    # what's approved is what's on stage: the branch's last commit, built with nothing uncommitted
    [[ "$(stage_label branch)" == "$name" && "$(stage_label commit)" == "$head" && "$(stage_label dirty)" == 0 ]] ||
      { echo "stage isn't running $name at ${head:0:7} (committed). build/feature.sh stage $name, get it approved, then promote" >&2; exit 1; }
    g merge -q --ff-only "$name"
    echo "master is now $name (${head:0:7}). push it: git -C $MAIN push"
    "$MAIN/build/deploy.sh" master
    for f in $(features); do [[ "$f" == "$name" ]] || rebase_one "$f" || true; done
    echo "$name is in master; when you're done with it: build/feature.sh done $name" ;;
  done)
    need "${1:-}"; name=$1; w=$(where "$name")
    g merge-base --is-ancestor "$name" master || { echo "$name isn't in master yet (promote it first); nothing removed" >&2; exit 1; }
    if [[ -n "$w" ]]; then
      clean "$w" || { echo "$w has uncommitted changes; nothing removed" >&2; exit 1; }
      rm -f "$w/research"
      g worktree remove "$w"
    fi
    g branch -q -d "$name" && echo "removed $name" ;;
  *)
    sed -n '4,14p' "$0"; exit 1 ;;
esac
