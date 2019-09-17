#!/bin/bash

THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"

GITDIFF=$(git rev-list HEAD...private/master --count)

if [ "$GITDIFF" != "0" ]; then
  cd "$THIS_DIR"
  git pull private master
  ./rebuild_docker.sh
fi
