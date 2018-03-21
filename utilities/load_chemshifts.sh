#!/bin/sh

psql -U web -d gissmo < load_chemshifts.sql
