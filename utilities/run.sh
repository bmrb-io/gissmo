#!/bin/bash
source ./env/bin/activate
export FLASK_APP=gissmo.py
export FLASK_DEBUG=1
flask run --host=0.0.0.0 --port 8001
