#!/usr/bin/env bash

sudo docker stop gissmo_ml
sudo docker rm gissmo_ml

if [[ $# -eq 0 ]]; then
  if ! sudo docker build -t gissmo_ml .; then
    echo "Docker build failed."
    exit 2
  fi
fi

#-v /websites/webapi/configuration.json:/opt/wsgi/configuration.json
sudo docker run -d --name gissmo_ml -p 9000:9000 -p 9001:9001 --restart=always  gissmo_ml
