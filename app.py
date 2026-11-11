"""ChurchRadio Studio: starts the window (mainwindow.py), where a service recording is dropped to
make the broadcast MP3.

With --build it makes the broadcast with no window instead (cli.py), for Task Scheduler.
--selftest loads the speech models and --uitest makes every window once (for the release build)."""
import multiprocessing
import sys

import audio
import builder
import cli
import paths
import prelude


def _selftest():
    """--selftest: only load the speech models (base.en + small.en) and exit. No window.

    For each model it prints the on-disk state *before* loading (the smoke test asserts on this)
    and then whether it loaded:
      "model base.en: PRESENT before load"   -> "model base.en: loaded from <path>"
      "model base.en: MISSING before load"   -> "model base.en: downloaded to <path> (first run only)"
    """
    models_folder = ""
    try:
        models_folder = builder.load_config().get("models_folder", "")
    except (OSError, ValueError):
        models_folder = ""

    root = prelude._models_dir(models_folder)
    print(f"selftest: {paths.APP_NAME} version {paths.version()}")
    print(f"selftest: program dir = {paths.program_dir()}")
    print(f"selftest: data dir = {builder.data_dir()}")
    try:
        print(f"selftest: ffmpeg = {audio.find_tool('ffmpeg')}")
        print(f"selftest: ffprobe = {audio.find_tool('ffprobe')}")
    except RuntimeError as e:
        print(f"selftest: ffmpeg NOT FOUND ({e})")
    print(f"selftest: models folder = {root}")
    ok = True
    for name in (prelude.MODEL_NAME, prelude.END_MODEL_NAME):
        # Check the on-disk state BEFORE loading: this is what the smoke test asserts on.
        before = prelude._model_ready(root, name)
        print(f"selftest: model {name}: {'PRESENT' if before else 'MISSING'} before load")
        try:
            prelude._get_model(models_folder, name)
            # Now it loaded. Report the true outcome (the before-check already proved
            # whether it had to download). For "loaded from" print the real model
            # directory (_model_path found it, e.g. the faster-whisper snapshot folder),
            # not a guessed <root>/<name> that may not exist.
            if before:
                real = prelude._model_path(root, name)
                print(f"selftest: model {name}: loaded from {real if real else root}")
            else:
                print(f"selftest: model {name}: downloaded to {root} (first run only)")
        except Exception as e:  # noqa: BLE001
            ok = False
            print(f"selftest: model {name}: FAILED to load ({e})")
    print("selftest: OK" if ok else "selftest: FAILED")
    sys.exit(0 if ok else 1)


def main():
    # Python starts helper processes by running this program again (on macOS, the "resource
    # tracker" when the speech models are downloaded). In the packaged app, freeze_support() makes
    # such a run do the helper's job and exit. Without it the helper opened a second app window,
    # took its arguments for a recording to build, and hung.
    multiprocessing.freeze_support()
    builder.ensure_user_files()
    if cli.build_args(sys.argv[1:]):  # --build: no window, for Task Scheduler
        sys.exit(cli.main(sys.argv[1:]))
    if "--selftest" in sys.argv:
        _selftest()
        return
    # The window parts (Qt) are loaded only now: --build and --selftest run without them, also on
    # a computer with no screen.
    import mainwindow
    if "--uitest" in sys.argv:
        try:
            mainwindow.uitest()
        except Exception as e:  # noqa: BLE001
            print(f"uitest: FAILED ({type(e).__name__}: {e})")
            sys.exit(1)
        return
    sys.exit(mainwindow.run(sys.argv))


if __name__ == "__main__":
    main()
