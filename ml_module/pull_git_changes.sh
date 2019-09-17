#!/bin/bash

THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$THIS_DIR" || exit 1

git fetch private
GITDIFF=$(git rev-list HEAD...private/master --count)

if [ "$GITDIFF" != "0" ]; then
  git pull private master
  ./rebuild_docker.sh
fi
