# Automated File Organizer

A small, dependency-free CLI tool that tidies a folder by moving every file into a sub-folder based on its extension (`images/`, `documents/`, `videos/`, `audio/`, `archives/`, `code/`, `others/`).

It **never overwrites** an existing file. If `images/photo.jpg` already exists, the incoming `photo.jpg` becomes `images/photo_1.jpg` (then `_2`, `_3`, ...).

Only the Python standard library is used (`os`, `shutil`, `pathlib`, `argparse`, `logging`, plus a few helpers). Requires **Python 3.8+**.

## Features

- Extension-to-folder mapping lives in one dictionary (`EXTENSION_MAP`) at the top of `organizer.py`.
- Conflict-safe: numeric suffix (`photo_1.jpg`) or timestamp suffix (`--on-conflict timestamp`).
- `--dry-run` previews every move without touching a single file.
- Logs every action to `organizer.log`; the console shows a short summary (add `-v` to see every move).
- Never crashes with a traceback. Handled gracefully: non-existent path, path that is a file, permission errors, empty folders, files with no extension, hidden files, symlinks, duplicate names, and Ctrl+C.
- Meaningful exit codes for scripting and schedulers.

## Files

| File | Purpose |
|------|---------|
| `organizer.py` | The tool |
| `make_sandbox.py` | Creates a throw-away temp folder full of sample files (including a duplicate name) |
| `test_organizer.py` | Automated tests (all run in temporary folders) |

## Usage

```bash
python organizer.py TARGET_DIR [options]
```

| Option | Description |
|--------|-------------|
| `-n`, `--dry-run` | Preview all moves; no file is moved, no folder is created |
| `-v`, `--verbose` | Show every move on the console (they are always written to the log file) |
| `--include-hidden` | Also organize hidden files (skipped by default) |
| `--on-conflict {number,timestamp}` | How to rename on a name clash (default: `number`) |
| `--log-file PATH` | Log file location (default: `./organizer.log`) |

### Example commands

```bash
# Always preview first
python organizer.py ~/Downloads --dry-run

# Organize, showing every move
python organizer.py ~/Downloads -v

# Use timestamps instead of numbers on conflicts
python organizer.py ~/Downloads --on-conflict timestamp

# Include hidden files, custom log location
python organizer.py ~/Downloads --include-hidden --log-file ~/logs/organizer.log

# Windows
python organizer.py "C:\Users\me\Downloads" --dry-run
```

### Exit codes

| Code | Meaning |
|------|---------|
| `0` | Finished without errors |
| `1` | Finished, but at least one file failed (e.g. permission denied) |
| `2` | Invalid target path |
| `130` | Interrupted with Ctrl+C |

## Example output

Normal run (short console summary; details go to `organizer.log`):

```
--------------------------------------------
Summary for /home/me/Downloads
  Moved:      11 (renamed on conflict: 1)
  Skipped:    1 (failed: 0)
```

Dry run with `-v` (nothing is changed):

```
[DRY-RUN] SKIPPED <sandbox>/.hidden_config (hidden file)
[DRY-RUN] MOVED archive.tar.gz | <sandbox>/archive.tar.gz -> <sandbox>/archives/archive.tar.gz
[DRY-RUN] MOVED notes.txt | <sandbox>/notes.txt -> <sandbox>/documents/notes.txt
[DRY-RUN] MOVED+RENAMED photo.jpg -> photo_1.jpg | <sandbox>/photo.jpg -> <sandbox>/images/photo_1.jpg
[DRY-RUN] MOVED report.pdf | <sandbox>/report.pdf -> <sandbox>/documents/report.pdf
...
--------------------------------------------
[DRY-RUN] Summary for <sandbox>
  Would move: 11 (renamed on conflict: 1)
  Skipped:    1 (failed: 0)
```

Invalid path:

```
$ python organizer.py /no/such/dir
ERROR: Target path does not exist: /no/such/dir
$ echo $?
2
```

Each log line records filename, source path and destination path, for example:

```
2026-10-20 12:38:30,669 | INFO     | MOVED+RENAMED photo.jpg -> photo_1.jpg | /data/photo.jpg -> /data/images/photo_1.jpg
```

## How edge cases are handled

| Situation | Behavior |
|-----------|----------|
| Name already exists at destination | Incoming file is renamed (`photo_1.jpg`); the existing file is never touched |
| Several clashes | `_1`, `_2`, `_3` ... the first free number is used |
| `PermissionError` / other `OSError` | Logged as an error, file counted as skipped and left in place, run continues, exit code `1` |
| Empty folder / no files | Prints "Nothing to organize", exit code `0` |
| Target missing or not a directory | Clear error message, exit code `2` |
| No extension (e.g. `Makefile`) or unknown extension | Goes to `others/` |
| Hidden files (`.env`, Windows hidden attribute) | Skipped unless `--include-hidden` |
| Symbolic links | Skipped (never followed or moved) |
| Sub-folders | Left alone; the tool is non-recursive |
| Upper-case extensions (`PHOTO.JPG`) | Matched case-insensitively |
| `organizer.log` / `organizer.py` inside the target | Ignored, never moved |
| Log file cannot be opened | Warning, continues with console only |

Note: only the last extension is used, so `archive.tar.gz` is classified as `.gz` (archives).

## Safe testing with a temporary folder

Nothing here touches your real files.

**Option A: automated tests**

```bash
python -m unittest -v test_organizer
```

The tests build a temporary folder, including an existing `images/photo.jpg` that clashes with an incoming `photo.jpg`, and verify that the original is never overwritten, dry-run changes nothing, hidden/no-extension files behave, and bad paths return exit code 2. (The permission test is skipped automatically when running as root or on Windows.)

**Option B: try it by hand**

```bash
python make_sandbox.py
# Sandbox created: /tmp/organizer_sandbox_abc123

python organizer.py /tmp/organizer_sandbox_abc123 --dry-run -v
python organizer.py /tmp/organizer_sandbox_abc123 -v
```

The sandbox contains `photo.jpg` (clashing with `images/photo.jpg`, whose content is `ORIGINAL`), `UPPER.JPG`, `Makefile`, `archive.tar.gz`, a hidden file, and an empty folder. After the real run, check that `images/photo.jpg` still contains `ORIGINAL` and that the incoming file is `images/photo_1.jpg`. Run `make_sandbox.py` again for a fresh sandbox and delete old ones when done (the command to do so is printed).

Manual duplicate test: after a run, create a new `photo.jpg` in the sandbox and run again. It becomes `photo_2.jpg`.

## Scheduling

Tip: run with `--dry-run` manually first, and always use **absolute paths** (schedulers start in a different working directory, so also pass `--log-file` with an absolute path).

### Linux / macOS (cron)

1. Find your Python path: `which python3` (e.g. `/usr/bin/python3`).
2. Open your crontab: `crontab -e`
3. Add a line, for example to run every day at 02:00:

```cron
0 2 * * * /usr/bin/python3 /home/me/tools/organizer.py /home/me/Downloads --log-file /home/me/logs/organizer.log >> /home/me/logs/cron.out 2>&1
```

Cron schedule format: `minute hour day-of-month month day-of-week`. Other examples:

```cron
*/30 * * * *  ...   # every 30 minutes
0 9 * * 1     ...   # Mondays at 09:00
@reboot       ...   # at startup
```

Notes:
- Create the log folder first (`mkdir -p /home/me/logs`).
- On macOS, cron may need Full Disk Access (System Settings -> Privacy & Security) to touch folders like Downloads or Desktop. `launchd` is the native alternative.
- List jobs with `crontab -l`; check `cron.out` and `organizer.log` if nothing happens.

### Windows (Task Scheduler)

**Command line (run in an elevated or normal Command Prompt):**

```bat
schtasks /Create /SC DAILY /ST 02:00 /TN "FileOrganizer" /TR "\"C:\Python312\python.exe\" \"C:\tools\organizer.py\" \"C:\Users\me\Downloads\" --log-file \"C:\tools\organizer.log\""
```

Run it now to test: `schtasks /Run /TN "FileOrganizer"`. Remove it: `schtasks /Delete /TN "FileOrganizer" /F`.

**Using the GUI:**

1. Open **Task Scheduler** -> **Create Basic Task...** and name it `FileOrganizer`.
2. Choose a trigger (Daily, Weekly, At log on...) and set the time.
3. Action: **Start a program**.
   - Program/script: `C:\Python312\python.exe` (find yours with `where python`)
   - Add arguments: `"C:\tools\organizer.py" "C:\Users\me\Downloads" --log-file "C:\tools\organizer.log"`
   - Start in: `C:\tools`
4. Finish, then right-click the task -> **Run** to test, and check `organizer.log`.

## Limitations

- Non-recursive by design: only files directly inside the target folder are organized.
- The "does it exist?" check and the move are two steps, so a file created by another program in that tiny window could in theory still be replaced. This is not a concern for normal use.
- Moving to a different drive/filesystem copies then deletes (standard `shutil.move` behavior).
