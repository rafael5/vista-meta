# vista-meta Makefile — lean v1 (spec §8, ADR-032)
# RUNS ON: host
# Default target: help

include .env

IMAGE     := vista-meta
RPC_PORT  ?= 9430          # RPC Broker host port; overridable in .env
VLINK_PORT ?= 8001         # VistALink host port; overridable in .env
CONTAINER := vista-vehu
VOLUME    := vehu-globals
COMPOSE   := docker/compose.yml
PROJECT   := vista-vehu
BUILD_DATE := $(shell date +%F)
DOCKER    := docker

# Single source of truth for the container is docker/compose.yml. Lifecycle
# targets shell out to `docker compose`; one-off targets (exec/cp/logs)
# still use plain docker by container name for terseness. The --env-file
# pin makes compose pick up .env overrides (e.g. RPC_PORT) even though
# compose.yml lives one level down (compose's default lookup is next to
# the compose file, which would miss our .env at repo root).
COMPOSE_CMD := $(DOCKER) compose --env-file .env -f $(COMPOSE) -p $(PROJECT)

.DEFAULT_GOAL := help

# ── Lifecycle ─────────────────────────────────────────────────────────

.PHONY: build
build: ## Build the Docker image
	$(DOCKER) build \
		-f docker/Dockerfile \
		--build-arg BUILD_DATE=$(BUILD_DATE) \
		-t $(IMAGE):latest \
		-t $(IMAGE):$(BUILD_DATE) \
		docker/

.PHONY: run
run: ## Start the container via docker compose (creates volume on first run)
	$(COMPOSE_CMD) up -d

.PHONY: stop
stop: ## Stop the container gracefully (keeps container + volume)
	$(COMPOSE_CMD) stop 2>/dev/null || true

.PHONY: restart
restart: ## Restart the container (in-place)
	$(COMPOSE_CMD) restart

.PHONY: rm
rm: ## Stop + remove the container (keeps volume and image)
	$(COMPOSE_CMD) down --remove-orphans 2>/dev/null || true

.PHONY: clean
clean: ## Remove container + volume + image (DESTRUCTIVE — prompts; FORCE=1 skips prompt)
	@echo "This will destroy the container, named volume (globals), and image."
	@echo "Snapshots in snapshots/ are not affected."
	@if [ "$(FORCE)" != "1" ]; then \
		read -p "Are you sure? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1; \
	fi
	$(COMPOSE_CMD) down -v --remove-orphans 2>/dev/null || true
	$(DOCKER) rmi $(IMAGE):latest $(IMAGE):$(BUILD_DATE) 2>/dev/null || true

.PHONY: reset
reset: ## Recreate container from current image (preserves volume + image; ~30s)
	@echo "==> reset: down → up → wait → doctor"
	@$(MAKE) -s rm
	@$(MAKE) -s run
	@$(MAKE) -s wait-healthy
	@$(MAKE) -s doctor || true
	@echo "==> reset complete"

.PHONY: rebuild
rebuild: ## Rebuild image + recreate container (preserves volume; longer)
	@echo "==> rebuild: down → build → up → wait → doctor"
	@$(MAKE) -s rm
	@$(MAKE) -s build
	@$(MAKE) -s run
	@$(MAKE) -s wait-healthy
	@$(MAKE) -s doctor || true
	@echo "==> rebuild complete"

.PHONY: nuke
nuke: ## Full teardown + rebuild (DESTROYS VOLUME — bake re-runs from scratch)
	@echo "==> nuke: clean (FORCE) → build → up → wait → doctor"
	@$(MAKE) -s clean FORCE=1
	@$(MAKE) -s build
	@$(MAKE) -s run
	@$(MAKE) -s wait-healthy
	@$(MAKE) -s doctor || true
	@echo "==> nuke complete"

.PHONY: wait-healthy
wait-healthy: ## Block until container healthcheck resolves (120s timeout — covers Dockerfile's 60s start-period)
	@echo -n "waiting for healthy"; \
	for i in $$(seq 1 60); do \
		status=$$($(DOCKER) inspect $(CONTAINER) --format '{{.State.Health.Status}}' 2>/dev/null || echo missing); \
		case "$$status" in \
			healthy) echo " — ok"; exit 0 ;; \
			unhealthy) echo " — UNHEALTHY (continuing — see \`make logs\`)"; exit 0 ;; \
			missing) echo " — container not found"; exit 1 ;; \
			*) echo -n "."; sleep 2 ;; \
		esac; \
	done; \
	echo " — timeout (still $$status — see \`make logs\`)"; exit 0

# ── Interactive ───────────────────────────────────────────────────────

.PHONY: shell
shell: ## SSH into the container as vehu
	ssh -p 2222 -o StrictHostKeyChecking=no vehu@127.0.0.1

.PHONY: mumps
mumps: ## Open a YottaDB/MUMPS prompt inside the container
	$(DOCKER) exec -it -u vehu $(CONTAINER) bash -lc '$$ydb_dist/mumps -direct'

.PHONY: python
python: ## Open a Python shell inside the container
	$(DOCKER) exec -it -u vehu $(CONTAINER) python3

.PHONY: logs
logs: ## Tail container logs (entrypoint output)
	$(DOCKER) logs -f $(CONTAINER)

.PHONY: bake-log
bake-log: ## Show the latest bake log
	@ls -t vista/export/logs/bake-*.log 2>/dev/null | head -1 | xargs cat 2>/dev/null \
		|| echo "No bake logs found"

# ── Bake ──────────────────────────────────────────────────────────────

.PHONY: bake
bake: ## Run bake.sh --all inside the container
	$(DOCKER) exec -u vehu $(CONTAINER) bash -lc '/usr/local/bin/bake.sh --all'

.PHONY: bake-xindex
bake-xindex: ## Run XINDEX baseline only
	$(DOCKER) exec -u vehu $(CONTAINER) bash -lc '/usr/local/bin/bake.sh --xindex'

.PHONY: bake-dd-text
bake-dd-text: ## Run DD exporter A (FileMan text)
	$(DOCKER) exec -u vehu $(CONTAINER) bash -lc '/usr/local/bin/bake.sh --only=dd-text'

.PHONY: bake-dd-fmql
bake-dd-fmql: ## Run DD exporter B (FMQL)
	$(DOCKER) exec -u vehu $(CONTAINER) bash -lc '/usr/local/bin/bake.sh --only=dd-fmql'

.PHONY: bake-dd-template
bake-dd-template: ## Run DD exporter D (Print Templates)
	$(DOCKER) exec -u vehu $(CONTAINER) bash -lc '/usr/local/bin/bake.sh --only=dd-template'

.PHONY: wait-for-bake
wait-for-bake: ## Poll sentinel until bake completes (progress dots)
	@echo -n "[wait-for-bake] "
	@while true; do \
		if [ ! -f vista/export/.vista-meta-initialized ]; then \
			echo -n "."; sleep 30; continue; \
		fi; \
		if $(DOCKER) exec $(CONTAINER) jq -e \
			'.phases | to_entries[] | select(.value.status == "pending")' \
			/home/vehu/export/.vista-meta-initialized >/dev/null 2>&1; then \
			echo -n "."; sleep 30; \
		else \
			echo " done"; \
			$(DOCKER) exec $(CONTAINER) jq '.phases | to_entries[] | "\(.key): \(.value.status)"' \
				/home/vehu/export/.vista-meta-initialized 2>/dev/null; \
			break; \
		fi; \
	done

# ── Snapshot ──────────────────────────────────────────────────────────

.PHONY: snapshot-globals
snapshot-globals: ## Snapshot the globals volume (auto-prune to last 5)
	@mkdir -p snapshots
	$(DOCKER) run --rm -v $(VOLUME):/data -v $(PWD)/snapshots:/snapshots \
		alpine tar czf /snapshots/globals-$$(date +%F-%H%M%S).tar.gz -C /data .
	@echo "Snapshot saved. Pruning to last 5..."
	@ls -t snapshots/globals-*.tar.gz 2>/dev/null | tail -n +6 | xargs rm -f 2>/dev/null || true
	@ls -lh snapshots/globals-*.tar.gz

.PHONY: restore-globals
restore-globals: ## Restore globals from snapshot (SNAPSHOT=path/to/file.tar.gz)
	@[ -n "$(SNAPSHOT)" ] || { echo "Usage: make restore-globals SNAPSHOT=snapshots/globals-YYYY-MM-DD.tar.gz"; exit 1; }
	@[ -f "$(SNAPSHOT)" ] || { echo "File not found: $(SNAPSHOT)"; exit 1; }
	@echo "This will replace ALL globals with the snapshot contents."
	@read -p "Are you sure? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	$(DOCKER) run --rm -v $(VOLUME):/data -v $(PWD)/$(SNAPSHOT):/snapshot.tar.gz \
		alpine sh -c 'rm -rf /data/* && tar xzf /snapshot.tar.gz -C /data'

# ── Host sync ─────────────────────────────────────────────────────────

.PHONY: sync-routines
sync-routines: ## Copy /opt/VistA-M/Packages/ from container to vista/vista-m-host/ (ADR-045)
	@$(DOCKER) ps --format '{{.Names}}' | grep -q '^$(CONTAINER)$$' || \
		{ echo "Container '$(CONTAINER)' is not running. Run 'make run' first."; exit 1; }
	@echo "Syncing VistA-M routines from container..."
	@rm -rf vista/vista-m-host
	@mkdir -p vista/vista-m-host
	$(DOCKER) cp $(CONTAINER):/opt/VistA-M/Packages vista/vista-m-host/Packages
	$(DOCKER) cp $(CONTAINER):/opt/VistA-M/r/MANIFEST.tsv vista/vista-m-host/MANIFEST.tsv
	@# R4: %-routine census sources — ZTMGRSET set in o/ plus r/ strays.
	@# Boundary: these two VistA dirs ONLY, never $$ydb_dist (F10).
	@mkdir -p vista/vista-m-host/PercentRoutines
	@printf 'routine\tsource\n' > vista/vista-m-host/PercentRoutines/MANIFEST.tsv
	@$(DOCKER) exec $(CONTAINER) bash -c \
		'ls /opt/VistA-M/o/_*.m /opt/VistA-M/r/_*.m 2>/dev/null' | \
	while read -r src; do \
		$(DOCKER) cp "$(CONTAINER):$$src" vista/vista-m-host/PercentRoutines/; \
		printf '%%%s\t%s\n' "$$(basename $$src .m | cut -c2-)" "$$src" \
			>> vista/vista-m-host/PercentRoutines/MANIFEST.tsv; \
	done
	@echo "---"
	@echo "Packages:  $$(ls vista/vista-m-host/Packages | wc -l)"
	@echo "Routines:  $$(find vista/vista-m-host/Packages -path '*/Routines/*.m' | wc -l)"
	@echo "%-routines: $$(( $$(wc -l < vista/vista-m-host/PercentRoutines/MANIFEST.tsv) - 1 ))"
	@echo "MANIFEST:  $$(( $$(wc -l < vista/vista-m-host/MANIFEST.tsv) - 1 )) entries"
	@echo "Size:      $$(du -sh vista/vista-m-host/Packages | cut -f1)"

.PHONY: inventory
inventory: ## Build routines.tsv + packages.tsv from vista-m-host snapshot (ADR-045)
	@[ -f vista/vista-m-host/MANIFEST.tsv ] || \
		{ echo "No snapshot found. Run 'make sync-routines' first."; exit 1; }
	/usr/bin/python3 host/scripts/build_routine_inventory.py

.PHONY: package-data
package-data: ## Inventory Globals/*.zwr exports → package-data.tsv (ADR-045)
	@[ -d vista/vista-m-host/Packages ] || \
		{ echo "No snapshot found. Run 'make sync-routines' first."; exit 1; }
	/usr/bin/python3 host/scripts/build_package_data_inventory.py

.PHONY: package-piks
package-piks: ## Join package-data × files.tsv → per-package PIKS distribution (ADR-045)
	@[ -f vista/export/code-model/package-data.tsv ] || \
		{ echo "Run 'make package-data' first."; exit 1; }
	@[ -f vista/export/data-model/files.tsv ] || \
		{ echo "files.tsv missing (from PIKS work)."; exit 1; }
	/usr/bin/python3 host/scripts/build_package_piks_summary.py

.PHONY: routine-globals
routine-globals: ## Scan each routine for subscripted ^GLOBAL refs (ADR-045 Phase 3a)
	@[ -f vista/vista-m-host/MANIFEST.tsv ] || \
		{ echo "Run 'make sync-routines' first."; exit 1; }
	/usr/bin/python3 host/scripts/build_routine_globals.py

.PHONY: routine-calls
routine-calls: ## Scan each routine for DO/GOTO/JOB and $$ calls → routine-calls.tsv (ADR-045 Phase 5)
	@[ -f vista/vista-m-host/MANIFEST.tsv ] || \
		{ echo "Run 'make sync-routines' first."; exit 1; }
	/usr/bin/python3 host/scripts/build_routine_calls.py

.PHONY: protocol-calls
protocol-calls: ## Scan protocol ENTRY/EXIT ACTION for routine calls (ADR-045 Phase 5b)
	@[ -f vista/export/code-model/protocols.tsv ] || \
		{ echo "Run 'make dump-file-101' first."; exit 1; }
	/usr/bin/python3 host/scripts/build_protocol_calls.py

.PHONY: package-manifest
package-manifest: ## Join everything into per-package manifest (ADR-045 Phase 6a)
	@for f in packages.tsv routines.tsv package-piks-summary.tsv rpcs.tsv \
	          options.tsv routine-globals.tsv routine-calls.tsv; do \
		[ -f vista/export/code-model/$$f ] || \
			{ echo "Missing: vista/export/code-model/$$f"; exit 1; }; \
	done
	/usr/bin/python3 host/scripts/build_package_manifest.py

.PHONY: routines-comprehensive
routines-comprehensive: ## Per-routine comprehensive view joining all signals (ADR-045 Phase 6b)
	@for f in routines.tsv vista-file-9-8.tsv rpcs.tsv options.tsv \
	          routine-calls.tsv routine-globals.tsv; do \
		[ -f vista/export/code-model/$$f ] || \
			{ echo "Missing: vista/export/code-model/$$f"; exit 1; }; \
	done
	/usr/bin/python3 host/scripts/build_routines_comprehensive.py

.PHONY: package-edge-matrix
package-edge-matrix: ## Package-to-package call edge matrix (ADR-045 Phase 6c)
	@[ -f vista/export/code-model/routines.tsv ] || \
		{ echo "Missing routines.tsv"; exit 1; }
	@[ -f vista/export/code-model/routine-calls.tsv ] || \
		{ echo "Missing routine-calls.tsv"; exit 1; }
	/usr/bin/python3 host/scripts/build_package_edge_matrix.py

.PHONY: package-namespace
package-namespace: ## Per-package namespace + VDL app_code from host/vendor/Packages.csv (P3/P4)
	@[ -f vista/export/code-model/packages.tsv ] || \
		{ echo "Run 'make inventory' first."; exit 1; }
	@[ -f host/vendor/Packages.csv ] || { echo "Missing host/vendor/Packages.csv"; exit 1; }
	/usr/bin/python3 host/scripts/build_package_namespace.py

.PHONY: augment-registries
augment-registries: ## (retired) package columns now land via normalize-dumps
	@echo "Retired: augmentation is part of 'make normalize-dumps' (V1)."
	@exit 1

.PHONY: normalize-dumps
normalize-dumps: ## Normalize raw M dumps -> schema_v1 finals (V1.4)
	@[ -f vista/export/raw/files.tsv ] || \
		{ echo "No raw dumps. Run the dump-* targets first."; exit 1; }
	@[ -f vista/export/code-model/routines.tsv ] || \
		{ echo "Run 'make inventory' first."; exit 1; }
	/usr/bin/python3 host/scripts/normalize_dumps.py

.PHONY: capture-extraction
capture-extraction: ## Capture R3 engine identity/state sidecar (V1.6)
	/usr/bin/python3 host/scripts/capture_extraction.py $(CONTAINER)

.PHONY: finals-owner
finals-owner: ## Reclaim finals dirs for the host (pre-V1 entrypoints chown them to vehu)
	$(DOCKER) exec -u root $(CONTAINER) sh -c 'mkdir -p /home/vehu/export/meta && \
		chown -R 1000:1000 /home/vehu/export/data-model \
		/home/vehu/export/code-model /home/vehu/export/meta'

.PHONY: column-manifest
column-manifest: ## Emit + verify the typed column manifest (V3/R1)
	/usr/bin/python3 host/scripts/build_column_manifest.py
	/usr/bin/python3 host/scripts/build_column_manifest.py --check

.PHONY: fidelity
fidelity: ## Emit + verify the fidelity declarations (V4/R2+F9)
	/usr/bin/python3 host/scripts/build_fidelity.py
	/usr/bin/python3 host/scripts/build_fidelity.py --check

.PHONY: validate
validate: ## Validate the emitted tree against the full v1 contract (V6)
	/usr/bin/python3 host/scripts/validate_export.py

.PHONY: content-hash
content-hash: ## Print the V5 data fingerprint (24 TSVs, normative recipe)
	/usr/bin/python3 host/scripts/content_hash.py

.PHONY: release
release: ## Assemble the data-v1 release assets into dist/ (V7; no publish)
	/usr/bin/python3 host/scripts/build_release.py

.PHONY: release-publish
release-publish: ## Assemble + publish the data-v1 GitHub Release (V7)
	/usr/bin/python3 host/scripts/build_release.py --publish

.PHONY: emit-all
emit-all: ## Single-run emission of all 24 finals from one engine state (F7)
	@$(DOCKER) ps --format '{{.Names}}' | grep -q '^$(CONTAINER)$$' || \
		{ echo "Container '$(CONTAINER)' is not running. Run 'make run' first."; exit 1; }
	$(MAKE) finals-owner
	$(MAKE) sync-routines
	$(MAKE) dump-files dump-piks dump-field-piks
	$(MAKE) dump-file-9-8 dump-file-8994 dump-file-19 dump-file-101
	$(MAKE) xindex
	$(MAKE) capture-extraction
	$(MAKE) inventory
	$(MAKE) normalize-dumps
	$(MAKE) routine-globals routine-calls protocol-calls
	$(MAKE) package-data package-piks package-namespace
	$(MAKE) package-manifest routines-comprehensive package-edge-matrix
	$(MAKE) validate-xindex
	$(MAKE) column-manifest
	$(MAKE) fidelity
	$(MAKE) validate
	@echo "emit-all complete: 24 finals + typed manifest + fidelity from one extraction, validated."

.PHONY: dump-files dump-piks dump-field-piks
.PHONY: raw-dir
raw-dir: ## Ensure the container-writable raw dump dir exists
	$(DOCKER) exec -u vehu $(CONTAINER) mkdir -p /home/vehu/export/raw

dump-files: raw-dir ## Dump FileMan inventory via VMFILES → raw/files.tsv
	$(DOCKER) exec -u vehu $(CONTAINER) bash -lc 'echo "D RUN^VMFILES" | $$ydb_dist/mumps -direct'

dump-piks: raw-dir ## Run PIKS classifier via VMPIKS → raw/piks.tsv
	$(DOCKER) exec -u vehu $(CONTAINER) bash -lc 'echo "D RUN^VMPIKS" | $$ydb_dist/mumps -direct'

dump-field-piks: raw-dir ## Field-level PIKS via VMFPIKS → raw/field-piks.tsv
	$(DOCKER) exec -u vehu $(CONTAINER) bash -lc 'echo "D RUN^VMFPIKS" | $$ydb_dist/mumps -direct'

.PHONY: dump-file-9-8
dump-file-9-8: raw-dir ## Dump File 9.8 (ROUTINE) via VMDUMP98 → raw/ (ADR-045 Phase 4a)
	$(DOCKER) exec -u vehu $(CONTAINER) bash -lc 'echo "D RUN^VMDUMP98 H" | $$ydb_dist/mumps -direct'
	$(DOCKER) cp $(CONTAINER):/tmp/vista-file-9-8.tsv vista/export/raw/vista-file-9-8.tsv
	$(DOCKER) exec -u vehu $(CONTAINER) rm -f /tmp/vista-file-9-8.tsv
	@echo "Written: vista/export/raw/vista-file-9-8.tsv"
	@wc -l vista/export/raw/vista-file-9-8.tsv

.PHONY: dump-file-8994
dump-file-8994: raw-dir ## Dump File 8994 (REMOTE PROCEDURE) via VMDUMP8994 → rpcs.tsv (ADR-045 Phase 4b)
	$(DOCKER) exec -u vehu $(CONTAINER) bash -lc 'echo "D RUN^VMDUMP8994 H" | $$ydb_dist/mumps -direct'
	$(DOCKER) cp $(CONTAINER):/tmp/rpcs.tsv vista/export/raw/rpcs.tsv
	$(DOCKER) exec -u vehu $(CONTAINER) rm -f /tmp/rpcs.tsv
	@echo "Written: vista/export/raw/rpcs.tsv"
	@wc -l vista/export/raw/rpcs.tsv

.PHONY: dump-file-19
dump-file-19: raw-dir ## Dump File 19 (OPTION) via VMDUMP19 → options.tsv (ADR-045 Phase 4c)
	$(DOCKER) exec -u vehu $(CONTAINER) bash -lc 'echo "D RUN^VMDUMP19 H" | $$ydb_dist/mumps -direct'
	$(DOCKER) cp $(CONTAINER):/tmp/options.tsv vista/export/raw/options.tsv
	$(DOCKER) exec -u vehu $(CONTAINER) rm -f /tmp/options.tsv
	@echo "Written: vista/export/raw/options.tsv"
	@wc -l vista/export/raw/options.tsv

.PHONY: dump-file-101
dump-file-101: raw-dir ## Dump File 101 (PROTOCOL) via VMDUMP101 → protocols.tsv (ADR-045 Phase 4d)
	$(DOCKER) exec -u vehu $(CONTAINER) bash -lc 'echo "D RUN^VMDUMP101 H" | $$ydb_dist/mumps -direct'
	$(DOCKER) cp $(CONTAINER):/tmp/protocols.tsv vista/export/raw/protocols.tsv
	$(DOCKER) exec -u vehu $(CONTAINER) rm -f /tmp/protocols.tsv
	@echo "Written: vista/export/raw/protocols.tsv"
	@wc -l vista/export/raw/protocols.tsv

.PHONY: xindex
xindex: raw-dir ## Run XINDEX on full corpus via VMXIDX → xindex-{routines,errors,xrefs,tags}.tsv
	$(DOCKER) exec -u vehu $(CONTAINER) bash -lc 'echo "D ALL^VMXIDX H" | $$ydb_dist/mumps -direct' | tail -5
	@for f in routines errors xrefs tags; do \
		$(DOCKER) cp $(CONTAINER):/tmp/xindex-$$f.tsv vista/export/raw/xindex-$$f.tsv; \
		$(DOCKER) exec -u vehu $(CONTAINER) rm -f /tmp/xindex-$$f.tsv; \
	done
	@wc -l vista/export/raw/xindex-*.tsv

.PHONY: validate-xindex
validate-xindex: ## Validate our regex extractions against XINDEX (ADR-045 post-Phase-6)
	@for f in routines.tsv routine-calls.tsv xindex-routines.tsv xindex-xrefs.tsv; do \
		[ -f vista/export/code-model/$$f ] || \
			{ echo "Missing: vista/export/code-model/$$f"; exit 1; }; \
	done
	/usr/bin/python3 host/scripts/validate_against_xindex.py

# ── Decomposed-on-disk patch workflow (Tier 2 #7) ─────────────────────
# Requires the `v-pkg` CLI on $PATH (~/vista-forge/v-pkg — the Go successor
# of the retired py-kids-vc; same verbs and argument shapes).

PATCHES_DIR := patches

.PHONY: patch-new
patch-new: ## Scaffold a new patch tree: NAME=MYPKG_1_0_1001
	@[ -n "$(NAME)" ] || { echo "Usage: make patch-new NAME=MYPKG_1_0_1001"; exit 1; }
	@for d in routines files options protocols rpcs keys hooks; do \
		mkdir -p "$(PATCHES_DIR)/$(NAME)/$$d"; \
	done
	@printf 'Patch %s\n\nDescribe the patch, its purpose, and reversibility here.\n' \
		"$(NAME)" > $(PATCHES_DIR)/$(NAME)/README.md
	@echo "Created $(PATCHES_DIR)/$(NAME)/"
	@find $(PATCHES_DIR)/$(NAME) -maxdepth 2 | sort

.PHONY: patch-decompose
patch-decompose: ## Decompose a .KID into on-disk form: KID=path/to/patch.KID
	@[ -n "$(KID)" ] || { echo "Usage: make patch-decompose KID=path/to/patch.KID"; exit 1; }
	@mkdir -p $(PATCHES_DIR)
	@name=$$(basename "$(KID)" | sed -E 's/\.[Kk][Ii][Dd][Ss]?$$//'); \
		dst=$(PATCHES_DIR)/$$name; \
		v-pkg decompose "$(KID)" "$$dst" && \
		echo "Decomposed -> $$dst"

.PHONY: patch-assemble
patch-assemble: ## Assemble an on-disk patch tree into a .KID: DIR=patches/NAME
	@[ -n "$(DIR)" ] || { echo "Usage: make patch-assemble DIR=patches/MYPKG_1_0_1001"; exit 1; }
	@name=$$(basename "$(DIR)"); \
		out=$(PATCHES_DIR)/$$name.KID; \
		v-pkg assemble "$(DIR)" "$$out" && \
		echo "Assembled -> $$out"

.PHONY: patch-roundtrip
patch-roundtrip: ## Round-trip a .KID (decompose + re-assemble + diff): KID=path
	@[ -n "$(KID)" ] || { echo "Usage: make patch-roundtrip KID=path/to/patch.KID"; exit 1; }
	@v-pkg roundtrip "$(KID)"

# ── More developer tools (Tier 2 #5, #6, #8) ──────────────────────────

.PHONY: fmt
fmt: ## Format .m files in-place: FILES="path1 path2" or FILES=vista/dev-r
	@[ -n "$(FILES)" ] || { echo "Usage: make fmt FILES=\"vista/dev-r PATH2\""; exit 1; }
	@/usr/bin/python3 host/scripts/mfmt.py $(FILES)

.PHONY: fmt-check
fmt-check: ## Report files that would be reformatted: FILES="..."
	@[ -n "$(FILES)" ] || { echo "Usage: make fmt-check FILES=\"vista/dev-r PATH2\""; exit 1; }
	@/usr/bin/python3 host/scripts/mfmt.py --check $(FILES)

.PHONY: new-test
new-test: ## Generate an M-Unit test skeleton: ROUTINE=PSOVCC1 [OUT=path]
	@[ -n "$(ROUTINE)" ] || { echo "Usage: make new-test ROUTINE=PSOVCC1 [OUT=TPSOVCC1.m]"; exit 1; }
	@/usr/bin/python3 host/scripts/vista_meta_cli.py new-test "$(ROUTINE)" \
		$(if $(OUT),-o $(OUT),)

.PHONY: lint
lint: ## Doc-comment lint for public tags: FILES="..."
	@[ -n "$(FILES)" ] || { echo "Usage: make lint FILES=\"vista/dev-r PATH2\""; exit 1; }
	@/usr/bin/python3 host/scripts/vista_meta_cli.py lint $(FILES)

# ── Developer workflow (vista-developers-guide.md §Tier 1) ───────────

.PHONY: install-hooks
install-hooks: ## Install hooks/pre-commit as .git/hooks/pre-commit (symlink)
	@mkdir -p .git/hooks
	@chmod +x hooks/pre-commit
	@ln -sf ../../hooks/pre-commit .git/hooks/pre-commit
	@echo "Installed. Next commit runs $(PWD)/hooks/pre-commit"

.PHONY: pkg
pkg: ## Package overview: NAME="Outpatient Pharmacy" or NAME=PSO
	@[ -n "$(NAME)" ] || { echo "Usage: make pkg NAME=\"Outpatient Pharmacy\""; exit 1; }
	@/usr/bin/python3 host/scripts/vista_meta_cli.py pkg "$(NAME)"

.PHONY: context
context: ## Context pack for AI: NAME=... [SOURCE=1] [BYTES=200000]
	@[ -n "$(NAME)" ] || { echo "Usage: make context NAME=\"Outpatient Pharmacy\" [SOURCE=1]"; exit 1; }
	@/usr/bin/python3 host/scripts/vista_meta_cli.py context "$(NAME)" \
		$(if $(SOURCE),--with-source,) \
		$(if $(BYTES),--bytes $(BYTES),)

.PHONY: doctor
doctor: ## Environment health check (TSVs, hook, container, round-trip)
	@/usr/bin/python3 host/scripts/vista_meta_cli.py doctor

.PHONY: search
search: ## Annotated corpus grep: PATTERN=... [PACKAGE=...] [TAGS=1]
	@[ -n "$(PATTERN)" ] || { echo "Usage: make search PATTERN=regex [PACKAGE=PSO] [TAGS=1]"; exit 1; }
	@/usr/bin/python3 host/scripts/vista_meta_cli.py search "$(PATTERN)" \
		$(if $(PACKAGE),--package "$(PACKAGE)",) \
		$(if $(TAGS),--tags-only,)

.PHONY: file
file: ## FileMan file overview: N=<file number> [FIELDS=N]
	@[ -n "$(N)" ] || { echo "Usage: make file N=2 [FIELDS=20]"; exit 1; }
	@/usr/bin/python3 host/scripts/vista_meta_cli.py file "$(N)" \
		$(if $(FIELDS),--fields $(FIELDS),)

.PHONY: xindex-file
xindex-file: ## Run XINDEX in the container on a host .m: FILE=path/to/R.m
	@[ -n "$(FILE)" ] || { echo "Usage: make xindex-file FILE=/tmp/MYNEW.m"; exit 1; }
	@/usr/bin/python3 host/scripts/vista_meta_cli.py xindex "$(FILE)"

# ── Verify ────────────────────────────────────────────────────────────

.PHONY: smoke
smoke: ## Run post-build smoke tests
	@bash tests/smoke/smoke.sh

# ── Docs ──────────────────────────────────────────────────────────────

.PHONY: docs-check
docs-check: ## Fail on dead docs links or dead '# Spec:'/'# Plan:' code citations
	@python3 host/scripts/docs_check.py

.PHONY: adr-new
adr-new: ## Create a new ADR (TITLE="decision title")
	@[ -n "$(TITLE)" ] || { echo "Usage: make adr-new TITLE=\"My Decision\""; exit 1; }
	@NEXT=$$(ls docs/adr/*.md 2>/dev/null | grep -oP '\d+' | sort -n | tail -1); \
	NEXT=$$(printf "%03d" $$(( NEXT + 1 ))); \
	SLUG=$$(echo "$(TITLE)" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | tr -cd 'a-z0-9-'); \
	FILE="docs/adr/$${NEXT}-$${SLUG}.md"; \
	printf "# ADR-$${NEXT}: $(TITLE)\n\nDate: $$(date +%F)\nStatus: Proposed\n\n## Context\n\n## Decision\n\n## Consequences\n\n## Alternatives considered\n" > "$$FILE"; \
	echo "Created $$FILE"

# ── Client contract (sibling M projects share this Vista) ────────────
# Publishes connection info to ~/data/vista-meta/conn.env so other
# projects (m-cli, m-tools, m-stdlib, ...) can talk to this container
# as a remote engine without knowing about Docker. Each client owns
# its own seed-vista.sh / unseed-vista.sh under scripts/, namespaced
# by routine prefix and ^XTMP key so the shared volume can be
# destroyed and rebuilt at any time.

CONN_DIR  := $(HOME)/data/vista-meta
CONN_FILE := $(CONN_DIR)/conn.env
PROJECTS_DIR := $(HOME)/projects

.PHONY: write-conn
write-conn: ## Publish connection contract for client M projects
	@mkdir -p $(CONN_DIR)
	@printf '%s\n' \
	  '# Auto-generated by vista-meta. Source this in client Makefiles/tests.' \
	  '# Last written: $(shell date -Iseconds)' \
	  'VISTA_HOST=127.0.0.1' \
	  'VISTA_SSH_PORT=2222' \
	  'VISTA_SSH_USER=vehu' \
	  'VISTA_HTTP_RPC_PORT=$(RPC_PORT)' \
	  'VISTA_HTTP_FMQL_PORT=$(VLINK_PORT)' \
	  'VISTA_HTTP_ROCTO_PORT=1338' \
	  'VISTA_HTTP_YDBGUI_PORT=8089' \
	  'VISTA_CONTAINER=$(CONTAINER)' \
	  'VISTA_IMAGE=$(IMAGE)' \
	  > $(CONN_FILE)
	@echo "wrote $(CONN_FILE)"

# Hook contract refresh into run so it always reflects current ports.
run: write-conn

# ── SSH key provisioning ─────────────────────────────────────────────
# Sibling projects (m-cli, m-tools, m-stdlib) SSH into vehu with
# BatchMode=yes, which forbids password prompts. We collect the host
# user's public keys at `make run` time, write them to a gitignored
# file, and bind-mount it into the container. The entrypoint installs
# it as ~vehu/.ssh/authorized_keys. New keys → next `make run` picks
# them up; for live containers use `make install-ssh-keys`.

HOST_PUB_KEYS := $(wildcard $(HOME)/.ssh/*.pub)
AUTH_KEYS     := docker/etc/authorized_keys

.PHONY: ssh-keys
ssh-keys: $(AUTH_KEYS) ## Refresh docker/etc/authorized_keys from $HOME/.ssh/*.pub

$(AUTH_KEYS): $(HOST_PUB_KEYS)
	@[ -n "$(HOST_PUB_KEYS)" ] || { \
	    echo "No public keys found in $(HOME)/.ssh/. Run 'ssh-keygen' first."; \
	    exit 1; }
	@cat $(HOST_PUB_KEYS) > $@
	@echo "wrote $@ ($$(wc -l < $@) key(s) from $(words $(HOST_PUB_KEYS)) file(s))"

.PHONY: install-ssh-keys
install-ssh-keys: ssh-keys ## Push authorized_keys into a running container without restart
	@$(DOCKER) ps --format '{{.Names}}' | grep -q '^$(CONTAINER)$$' || \
	    { echo "container '$(CONTAINER)' not running"; exit 1; }
	$(DOCKER) cp $(AUTH_KEYS) $(CONTAINER):/etc/vehu_authorized_keys
	$(DOCKER) exec -u root $(CONTAINER) bash -c '\
	    install -d -m 700 -o vehu -g vehu /home/vehu/.ssh && \
	    install -m 600 -o vehu -g vehu \
	        /etc/vehu_authorized_keys /home/vehu/.ssh/authorized_keys'
	@echo "installed authorized_keys into running $(CONTAINER)"

# Ensure the file exists before `docker run` tries to bind-mount it.
run: ssh-keys

.PHONY: reseed-all
reseed-all: ## Run every sibling project's scripts/seed-vista.sh
	@$(DOCKER) ps --format '{{.Names}}' | grep -q '^$(CONTAINER)$$' || \
		{ echo "container '$(CONTAINER)' not running — run 'make run' first"; exit 1; }
	@for d in $(PROJECTS_DIR)/*/; do \
	    name=$$(basename $$d); \
	    [ "$$name" = "vista-meta" ] && continue; \
	    [ "$$name" = "vista-vehu" ] && continue; \
	    [ "$$name" = "archive" ] && continue; \
	    seed="$${d}scripts/seed-vista.sh"; \
	    [ -x "$$seed" ] || continue; \
	    echo "── seeding $$name ──"; \
	    ( cd "$$d" && "$$seed" ) || echo "  ! $$name seed failed (continuing)"; \
	done
	@echo "reseed-all complete"

.PHONY: unseed-all
unseed-all: ## Run every sibling project's scripts/unseed-vista.sh
	@for d in $(PROJECTS_DIR)/*/; do \
	    name=$$(basename $$d); \
	    [ "$$name" = "vista-meta" ] && continue; \
	    unseed="$${d}scripts/unseed-vista.sh"; \
	    [ -x "$$unseed" ] || continue; \
	    echo "── unseeding $$name ──"; \
	    ( cd "$$d" && "$$unseed" ) || true; \
	done

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' Makefile | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
