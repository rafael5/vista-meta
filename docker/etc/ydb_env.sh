#!/bin/bash
# YottaDB + VistA environment for interactive shells and service wrappers.
# __YDB_DIST__ is replaced at Docker build time (see Dockerfile layer 4).
#
# RUNS IN: container. Sourced by:
#   - /etc/profile.d/ (interactive SSH sessions)
#   - entrypoint.sh (service startup)
#   - ydb-run wrapper (xinetd-spawned M processes)
#
# This is the RUNTIME source of truth for YDB env vars. The Dockerfile
# also sets these as ENV directives for build-time RUN commands.
# Spec: docs/vista-meta-spec-v0.4.md § 7

export ydb_dist="__YDB_DIST__"
export ydb_gbldir="/home/vehu/g/mumps.gld"
export ydb_chset="M"
export ydb_log="/home/vehu/export/logs/ydb"
export ydb_tmp="/tmp/ydb"
# BL-009: parenthesized source(object) $ZRO syntax broken in YDB r2.02.
# Use flat directory entries instead. Object dirs listed before source
# dirs so pre-compiled .o files are found first.
export ydb_routines="/home/vehu/dev/o /home/vehu/dev/r /opt/VistA-M/o /opt/VistA-M/r $ydb_dist/libyottadbutil.so"
export LD_LIBRARY_PATH="$ydb_dist${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PATH="$PATH:$ydb_dist"
