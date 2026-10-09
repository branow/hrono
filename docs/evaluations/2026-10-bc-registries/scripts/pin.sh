#!/bin/sh
# Point each mirror's main branch at the last first-parent commit of its
# upstream default branch before DATE. hrono's git source fetches the mirror's
# HEAD, so this is how the eval replays history without a ref option in hrono.
# usage: pin.sh 2024-10-01 [repo...]
set -eu
date="$1"; shift
root="$(cd "$(dirname "$0")/.." && pwd)"
repos="${*:-lear sbc-auth sbc-pay business-filings-ui}"
for repo in $repos; do
  up="$root/upstream/$repo"
  mirror="$root/mirror/$repo.git"
  branch="$(git -C "$up" symbolic-ref --short refs/remotes/origin/HEAD | sed 's|^origin/||')"
  sha="$(git -C "$up" rev-list -1 --first-parent --before="$date" "origin/$branch")"
  if [ ! -d "$mirror" ]; then
    git init -q --bare -b main "$mirror"
  fi
  git -C "$up" push -q --force "$mirror" "$sha:refs/heads/main"
  echo "$repo $(git -C "$up" log -1 --format='%h %cs' "$sha")"
done
