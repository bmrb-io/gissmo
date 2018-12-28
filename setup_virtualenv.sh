#!/bin/bash
python -m virtualenv env
source ./env/bin/activate
export PATH="${PATH}:/usr/pgsql-9.2/bin/"
pip install -r requirements.txt