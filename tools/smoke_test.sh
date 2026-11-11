#!/bin/bash
# Smoke test of an installed ChurchRadio Studio on Linux or macOS (run by release.yml).
#
#   tools/smoke_test.sh PROGRAM FFMPEG_DIR DATA_DIR MODELS_DIR VERSION
#
# PROGRAM     the installed program to run
# FFMPEG_DIR  the folder of the ffmpeg installed with it (the app must use that one)
# DATA_DIR    where the app must keep the user's settings
# MODELS_DIR  where the speech models must download to (once)
# VERSION     the version the app must report
#
# The same checks as the Windows job: --selftest twice (the models download once, then load from
# disk), then headless builds with --build: a broadcast is made, a second run finds nothing to do,
# a bad --date fails with exit code 1, and no lock is left behind.
set -euo pipefail

PROGRAM=$1 FFMPEG_DIR=$2 DATA_DIR=$3 MODELS_DIR=$4 VERSION=$5
fail() { echo "SMOKE TEST FAILED: $*" >&2; exit 1; }
has() { grep -qF -- "$2" <<<"$1" || fail "$3 (expected: $2)"; }
# limit SECONDS PROGRAM ARGS...: run with a time limit, so a hang fails the test instead of the job
# waiting for hours. The program runs in its own process group and the whole group is stopped,
# so a helper process it started cannot keep the output open. perl, because macOS has no
# `timeout`. Exit code 142 = time limit hit, else the program's own exit code.
limit() {
    perl -e '
        my $secs = shift;
        my $pid = fork() // die "fork: $!";
        if ($pid == 0) { setpgrp(0, 0); exec @ARGV or die "cannot run $ARGV[0]: $!"; }
        local $SIG{ALRM} = sub { kill "TERM", -$pid; sleep 5; kill "KILL", -$pid; waitpid($pid, 0); exit 142; };
        alarm $secs;
        waitpid($pid, 0);
        alarm 0;
        exit($? & 127 ? 128 + ($? & 127) : $? >> 8);
    ' "$@"
}
work=$(mktemp -d)
# selftest N: run --selftest (up to 25 minutes: the first run downloads the models), show its
# output as it comes, and put it in $out.
selftest() {
    local log="$work/selftest-$1.log" code=0
    limit 1500 "$PROGRAM" --selftest 2>&1 | tee "$log" || code=${PIPESTATUS[0]}
    out=$(cat "$log")
    [ "$code" -ne 142 ] || fail "selftest run $1 did not finish in 25 minutes (it hangs)"
    [ "$code" -eq 0 ] || fail "selftest run $1 failed (exit $code)"
}

[ -x "$PROGRAM" ] || fail "program not found: $PROGRAM"
[ -x "$FFMPEG_DIR/ffmpeg" ] && [ -x "$FFMPEG_DIR/ffprobe" ] || fail "ffmpeg was not installed in $FFMPEG_DIR"

echo "=== Selftest run 1 (first start: models download once) ==="
selftest 1
has "$out" "selftest: OK" "selftest run 1 failed"
has "$out" "version $VERSION" "the app does not know its version"
has "$out" "ffmpeg = $FFMPEG_DIR/ffmpeg" "the app did not use the ffmpeg installed with it"
has "$out" "data dir = $DATA_DIR" "the app does not keep its files in the right folder"
has "$out" "models folder = $MODELS_DIR" "the models folder is not the expected one"
[ -f "$DATA_DIR/config.json" ] || fail "config.json was not created in $DATA_DIR"
for m in base.en small.en; do
    find "$MODELS_DIR/models--Systran--faster-whisper-$m" -name model.bin 2>/dev/null | grep -q . \
        || fail "$m did not download to $MODELS_DIR"
done

echo "=== Selftest run 2 (models already on disk) ==="
selftest 2
has "$out" "PRESENT before load" "run 2 would download the models again"
grep -q "MISSING before load" <<<"$out" && fail "run 2 would download the models again"

echo "=== Headless build (--build, as cron or launchd runs it) ==="
rec="$work/recordings" outdir="$work/out"
mkdir -p "$rec" "$outdir"
# A 2-minute test recording with the date in its name. It has no speech, so the start and end
# are not found and nothing is cut, but the speech models are loaded and searched.
"$FFMPEG_DIR/ffmpeg" -v error -y -f lavfi -i "sine=frequency=440:duration=120" -ac 2 \
    "$rec/BLCTrad11.15.2026 08-10.wav"
python3 - "$DATA_DIR/config.json" "$outdir" <<'PY'
import json, sys
path, out = sys.argv[1], sys.argv[2]
with open(path, encoding="utf-8") as fh:
    cfg = json.load(fh)
cfg.update(setup_done=True, output_folder=out, broadcast_name="Headless Test")
with open(path, "w", encoding="utf-8") as fh:
    json.dump(cfg, fh, indent=2)
PY

build() {  # build ARGS... -> sets CODE and LOG
    local log="$work/build-$RANDOM.log"
    set +e
    limit 900 "$PROGRAM" --build "$rec" --log "$log" "$@" >/dev/null 2>&1
    CODE=$?
    [ "$CODE" -ne 142 ] || fail "the headless build did not finish in 15 minutes (it hangs)"
    set -e
    LOG=$(cat "$log" 2>/dev/null || echo "(no log written)")
    echo "$LOG"
}
build --settle 0
[ "$CODE" -eq 0 ] || fail "headless build failed (exit $CODE)"
[ -f "$outdir/Headless Test 2026-11-15.mp3" ] || fail "headless build did not save the MP3"
has "$LOG" "Saved:" "the headless log does not say where the MP3 was saved"
build --settle 0
[ "$CODE" -eq 0 ] && grep -q "already made" <<<"$LOG" || fail "a second run should find nothing to do"
build --settle 0 --date 15/11/2026
[ "$CODE" -eq 1 ] || fail "a bad --date should end with exit code 1, not $CODE"
[ ! -e "$DATA_DIR/build.lock" ] || fail "the headless build left its lock behind"
rm -rf "$work"

echo "Smoke test PASS: ffmpeg found, files in $DATA_DIR, models downloaded once, headless build works."
