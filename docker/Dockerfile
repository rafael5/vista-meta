# vista-meta — VEHU on YottaDB analytics sandbox
# Spec: docs/vista-meta-spec-v0.4.md § 4
# Single-stage build (ADR-020) on Ubuntu 24.04 (ADR-003)
#
# RUNS ON: host (docker build)
# BUILD CONTEXT: docker/ directory only
# BUILD: make build  (or: docker build -f docker/Dockerfile docker/)
#
# Build args:
#   YDB_VERSION    — YottaDB version to install (default: r2.02)
#   VEHU_M_URL     — URL to VEHU-M zip archive
#   VEHU_UID       — UID for the vehu user (default: 1001)
#   VEHU_PASSWORD  — password for vehu SSH login (default: vehu)
#   BUILD_DATE     — image label for tagging

FROM ubuntu:24.04

# Ubuntu's /bin/sh is dash, which lacks `source` and bash arrays.
# All RUN commands in this file use bash features.
SHELL ["/bin/bash", "-c"]

ARG YDB_VERSION=r2.02
ARG VEHU_M_URL=https://github.com/WorldVistA/VistA-VEHU-M/archive/master.zip
ARG VEHU_UID=1001
ARG VEHU_PASSWORD=vehu
ARG BUILD_DATE

LABEL maintainer="rmrich5@gmail.com"
LABEL description="vista-meta: VEHU on YottaDB analytics sandbox"
LABEL build.date="${BUILD_DATE}"

# ── Layer 2: OS dependencies ─────────────────────────────────────────
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl wget unzip sudo openssh-server xinetd tini git \
        python3 python3-pip python3-venv \
        build-essential cmake pkg-config file \
        bison flex nodejs \
        ca-certificates locales \
        libelf-dev libicu-dev libconfig-dev libreadline-dev libssl-dev \
        libsodium-dev libcurl4-openssl-dev \
        ranger micro tree btop ncdu less jq \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /run/sshd /tmp/ydb

# ── Layer 3: User setup ──────────────────────────────────────────────
RUN groupadd -g ${VEHU_UID} vehu \
    && useradd -m -u ${VEHU_UID} -g vehu -s /bin/bash vehu \
    && echo "vehu:${VEHU_PASSWORD}" | chpasswd \
    && usermod -aG sudo vehu \
    && echo "vehu ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/vehu \
    && chmod 0440 /etc/sudoers.d/vehu \
    && mkdir -p /home/vehu/dev/r /home/vehu/dev/o \
                /home/vehu/scripts \
                /home/vehu/export/logs/ydb \
                /home/vehu/g \
    && chown -R vehu:vehu /home/vehu

# ── Layer 4: YottaDB install ─────────────────────────────────────────
# ADR-004: ydbinstall.sh with pinned version
# ADR-005: ASCII only (no --utf8)
# Installs: YDB core + YDB Web Server (--webserver) + Octo SQL (--octo)
RUN mkdir -p /tmp/ydb-install && cd /tmp/ydb-install \
    && wget -q https://gitlab.com/YottaDB/DB/YDB/-/raw/master/sr_unix/ydbinstall.sh \
    && chmod +x ydbinstall.sh \
    && ./ydbinstall.sh \
        --installdir /usr/local/lib/yottadb/${YDB_VERSION} \
        --webserver --octo \
        --force-install \
        ${YDB_VERSION} \
    && rm -rf /tmp/ydb-install

# YDB environment — build-time ENVs
ENV ydb_dist=/usr/local/lib/yottadb/${YDB_VERSION}
ENV ydb_gbldir=/home/vehu/g/mumps.gld
ENV ydb_chset=M
ENV ydb_log=/home/vehu/export/logs/ydb
ENV ydb_tmp=/tmp/ydb
ENV LD_LIBRARY_PATH=$ydb_dist
ENV PATH=$PATH:$ydb_dist

# Profile script for interactive shells + service wrappers
COPY etc/ydb_env.sh /etc/profile.d/ydb_env.sh
RUN sed -i "s|__YDB_DIST__|/usr/local/lib/yottadb/${YDB_VERSION}|g" \
        /etc/profile.d/ydb_env.sh \
    && chmod +x /etc/profile.d/ydb_env.sh

# Wrapper for xinetd services: xinetd can't expand env vars or source
# profile scripts, so this 3-line shim sources the YDB env then exec's
# mumps with whatever args xinetd passes (e.g., -run XWBTCPM).
RUN printf '#!/bin/bash\nsource /etc/profile.d/ydb_env.sh\nexec $ydb_dist/mumps "$@"\n' \
        > /usr/local/bin/ydb-run \
    && chmod +x /usr/local/bin/ydb-run

# ── Layer 5: VEHU-M fetch ────────────────────────────────────────────
# BL-010: VEHU-M archive lacks % routines — installed via ZTMGRSET in layer 7.
RUN mkdir -p /opt/VistA-M \
    && curl -fSsL "${VEHU_M_URL}" -o /tmp/vehu-m.zip \
    && cd /tmp && unzip -q vehu-m.zip \
    && cp -a VistA-VEHU-M-*/Packages /opt/VistA-M/ \
    && rm -rf /tmp/vehu-m.zip /tmp/VistA-VEHU-M-*

# ── Layer 6: Symlink farm + GDE ──────────────────────────────────────
# ADR-029: symlink farm for flat routine namespace
# ADR-030: single DEFAULT region → one mumps.dat
# BL-009: YDB $ZRO cannot follow symlinks — use hard copies instead.
# This increases layer size (~100MB) but ensures routine resolution works.
RUN set -e \
    && mkdir -p /opt/VistA-M/r /opt/VistA-M/o \
    && printf 'routine\tpackage\tsource\n' > /opt/VistA-M/r/MANIFEST.tsv \
    && find /opt/VistA-M/Packages -path '*/Routines/*.m' | sort | while read -r src; do \
        routine=$(basename "$src"); \
        pkg=$(echo "$src" | sed 's|.*/Packages/\([^/]*\)/.*|\1|'); \
        target="/opt/VistA-M/r/$routine"; \
        if [ -e "$target" ]; then \
            echo "FATAL: duplicate routine: $routine" >&2; \
            echo "  existing: $target" >&2; \
            echo "  conflict: $src" >&2; \
            exit 1; \
        fi; \
        cp "$src" "$target"; \
        printf '%s\t%s\t%s\n' "${routine%.m}" "$pkg" "$src" \
            >> /opt/VistA-M/r/MANIFEST.tsv; \
    done \
    && echo "Routine farm: $(( $(wc -l < /opt/VistA-M/r/MANIFEST.tsv) - 1 )) routines" \
    && printf '%s\n' \
        'change -segment DEFAULT -file=/home/vehu/g/mumps.dat' \
        'change -region DEFAULT -record_size=1048576 -key_size=1019 -null_subscripts=always' \
        'exit' \
        | $ydb_dist/mumps -r GDE \
    && chown -R vehu:vehu /home/vehu/g /opt/VistA-M/o \
    && su -s /bin/bash vehu -c "source /etc/profile.d/ydb_env.sh && mupip create"

# ── Layer 7: VEHU-M import (expensive: ~5-15 min) ────────────────────
# Import globals from ZWR files, then compile routines to object code.
# ADR-006: skip bootstrap — VEHU-M already has demo users + patients.
USER vehu
WORKDIR /home/vehu
# Build-time ZRO: object dir first, then source dir (BL-009: no parenthesized syntax)
ENV ydb_routines="/opt/VistA-M/o /opt/VistA-M/r $ydb_dist/libyottadbutil.so"

RUN set -e \
    && echo "=== Importing globals ===" \
    && find /opt/VistA-M/Packages -name '*.zwr' | sort | while read -r f; do \
        ln -sf "$f" /tmp/_load.zwr \
        && $ydb_dist/mupip load -ignorechset /tmp/_load.zwr 2>&1 \
            || echo "WARN: failed to load $f"; \
    done \
    && rm -f /tmp/_load.zwr \
    && echo "=== Compiling routines → /opt/VistA-M/o/ ===" \
    && cd /opt/VistA-M/o \
    && find /opt/VistA-M/r -name '*.m' -print0 \
        | xargs -0 -n 200 $ydb_dist/mumps 2>&1 || true \
    && echo "Compiled $(ls -1 /opt/VistA-M/o/*.o 2>/dev/null | wc -l) object files" \
    && echo "=== Installing percent routines via ZTMGRSET ===" \
    && $ydb_dist/mumps -run %XCMD \
        'S ZTMODE=0,ZTOS=8,U="^",SCR="I 1" D @ZTOS^ZTMGRSET,TM^ZTMGRSET,ETRAP^ZTMGRSET,DEV^ZTMGRSET,OTHER^ZTMGRSET' \
        2>&1 || true \
    && echo "=== Installing FileMan percent routines (DT, DTC, RCR) ===" \
    && $ydb_dist/mumps -run %XCMD \
        'S U="^",ZTOS=8,SCR="I 1",%S="DIDT^DIDTC^DIRCR",%D="%DT^%DTC^%RCR" D MOVE^ZTMGRSET' \
        2>&1 || true \
    && echo "Percent routines: $(ls -1 /opt/VistA-M/o/_*.o 2>/dev/null | wc -l) installed"

USER root

# ── Layer 8: Octo DDL mapping ────────────────────────────────────────
# Octo binary was installed in layer 4. YDBOctoVistA is a separate project
# that generates DDL from FileMan's SQLI tables. Fetch it, compile, then
# run MAPALL with DUZ set so FileMan utilities work.
# DUZ=.5 = Postmaster user; DIQUIET=1 = suppress FileMan prompts;
# DUZ(0)="@" = programmer access; DT^DICRW = initialize FileMan date vars.
RUN mkdir -p /opt/VistA-M/ddl \
    && curl -fSsL https://gitlab.com/YottaDB/DBMS/YDBOctoVistA/-/raw/master/_YDBOCTOVISTAM.m \
        -o /opt/VistA-M/r/_YDBOCTOVISTAM.m \
    && cd /opt/VistA-M/o && $ydb_dist/mumps /opt/VistA-M/r/_YDBOCTOVISTAM.m \
    && su -s /bin/bash vehu -c "\
        source /etc/profile.d/ydb_env.sh \
        && \$ydb_dist/mumps -r %XCMD \
            'S DUZ=.5,DIQUIET=1,DUZ(0)=\"@\" D DT^DICRW,MAPALL^%YDBOCTOVISTAM(\"/opt/VistA-M/ddl/vista.sql\")' \
    " || echo "WARN: Octo MAPALL failed — DDL generation may need manual run"

# ── Layer 9: M-Unit install ──────────────────────────────────────────
# ADR-015: ChristopherEdwards/M-Unit via cmake (YDB plugin)
RUN git clone --depth 1 https://github.com/ChristopherEdwards/M-Unit.git /tmp/m-unit \
    && cd /tmp/m-unit \
    && mkdir build && cd build \
    && cmake -DYDB_DIST=$ydb_dist .. \
    && make -j"$(nproc)" \
    && make install \
    && rm -rf /tmp/m-unit

# ── Layer 10: YDBGUI install ─────────────────────────────────────────
# YDB Web Server was installed in layer 4 (--webserver).
# YDBGUI provides the Angular frontend served by it.
# cmake auto-fetches missing plugin deps (YDB-Web-Server, YDBCurl, YDBPosix).
RUN git clone --depth 1 https://gitlab.com/YottaDB/UI/YDBGUI.git /tmp/ydbgui \
    && cd /tmp/ydbgui \
    && mkdir build && cd build \
    && cmake -DYDB_DIST=$ydb_dist .. \
    && make -j"$(nproc)" \
    && make install \
    && rm -rf /tmp/ydbgui

# ── Layer 11: FMQL install ───────────────────────────────────────────
# ADR-016: FMQL as one of three DD exporter baselines
RUN git clone --depth 1 https://github.com/caregraf/FMQL.git /tmp/fmql \
    && cp /tmp/fmql/MUMPS/*.m /opt/VistA-M/r/ \
    && cd /opt/VistA-M/o \
    && $ydb_dist/mumps /opt/VistA-M/r/CG*.m 2>&1 || true \
    && rm -rf /tmp/fmql

# ── Layer 12: Python tooling ─────────────────────────────────────────
# ADR-014: baked Python tooling for analytics scripting
# --break-system-packages: no venv inside the container; these are system tools
RUN pip3 install --no-cache-dir --break-system-packages \
        yottadb click pyyaml requests

# ── Layer 13: Service configs ────────────────────────────────────────
COPY etc/xinetd.d/xwb   /etc/xinetd.d/xwb
COPY etc/xinetd.d/vlink  /etc/xinetd.d/vlink
COPY etc/sshd_config     /etc/ssh/sshd_config

# ── Layer 14: Entrypoint + bake + healthcheck ────────────────────────
COPY entrypoint.sh   /usr/local/bin/entrypoint.sh
COPY bake.sh         /usr/local/bin/bake.sh
COPY healthcheck.sh  /usr/local/bin/healthcheck.sh
RUN chmod +x /usr/local/bin/entrypoint.sh /usr/local/bin/bake.sh /usr/local/bin/healthcheck.sh

# ── Layer 15: Metadata ───────────────────────────────────────────────
# Runtime ZRO: dev dirs first (shadow VEHU), then VEHU, then YDB libs (ADR-012)
# BL-009: flat dirs, no parenthesized source(object) syntax
ENV ydb_routines="/home/vehu/dev/o /home/vehu/dev/r /opt/VistA-M/o /opt/VistA-M/r $ydb_dist/libyottadbutil.so"

EXPOSE 22 9430 8001 1338 8089

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD ["/usr/local/bin/healthcheck.sh"]

ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/entrypoint.sh"]
