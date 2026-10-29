# Copy a Drive or Folder onto .220 (rsync modules)

Copies a folder from an external drive, or anything else on a Mac, onto the TrueNAS at 192.168.3.220. The Mac sends the files, and .220 receives them through one of its rsync modules.

**You need:**
- a Mac on the lab network (192.168.3.x) whose IP is in the module's Hosts Allow;
- GNU rsync from Homebrew at `/opt/homebrew/bin/rsync` (macOS's own `rsync` won't do);
- tmux.

The full procedure, with the reasons behind each step, is in `rsync_module_ingest_to_truenas.md`. The `ingest-to-220` script runs these same steps with the checks built in.

**Modules on .220:**

| Module | Use for | Path |
|---|---|---|
| `jpca_av_files` | JPCA AV files | fixed: don't change it |
| `dpx_files_from_drives` | DPX files from drives | fixed: don't change it |
| `large_upload` | anything else | set it for each job |

---

## 1. On .220: switch the module on

Choose the module for this job from the table above. In the TrueNAS web UI, go to **Services → Rsync → Rsync Module** and click the pencil next to it.

1. **Path:** check that it's where you want the files. The copy lands in `<Path>/<your folder name>/`.
   - `jpca_av_files` and `dpx_files_from_drives` keep their paths. If the path isn't right for your files, you've picked the wrong module.
   - Only `large_upload` gets its Path changed for a job.
2. **Hosts Allow:** check that it includes this Mac's IP.
3. Tick **Enabled**, then **Save**.

If the Rsync service is off, turn it on under **Services**.

---

## 2. On the Mac: start tmux

tmux keeps the copy running if you close Terminal or step away. It doesn't keep the Mac awake; step 6 uses `caffeinate` for that.

```
tmux new -s ingest
```

You're now inside a tmux session named `ingest`. It looks like a normal Terminal window. Do all the Terminal commands from steps 3 to 9 in it; the later steps use the settings from step 3.

If you get `duplicate session: ingest`, a session with that name is already open. Go back into it with `tmux attach -t ingest`, or use another name.

The **tmux quick guide** at the end covers leaving the session, coming back, scrolling, and checking on a copy.

---

## 3. Set the source and module

Paste these one at a time. Only the first two need editing. Don't put a slash at the end of `SRC`.

```
SRC="/Volumes/<drive>/<folder>"
```

```
MODULE="<module>"
```

```
EXCL=(--exclude='.DS_Store' --exclude='._*' --exclude='.Spotlight-V100' --exclude='.Trashes' --exclude='.TemporaryItems' --exclude='.fseventsd')
```

```
LABEL=$(printf '%s-%s' "$(basename "$(dirname "$SRC")")" "$(basename "$SRC")" | tr -c 'A-Za-z0-9_-' '-')
```

```
STAMP=$(date +%Y%m%d-%H%M%S); mkdir -p ~/rsync_logs; ls "$SRC" | head
```

`MODULE` is the module you chose in step 1, for example `MODULE="dpx_files_from_drives"`. The last command should list your files. To copy a whole drive, use `SRC="/Volumes/<drive>"`; it lands in `<Path>/<drive name>/`.

---

## 4. Check that .220 answers

```
/opt/homebrew/bin/rsync rsync://192.168.3.220/
```

Your module should be in the list.
- **Timeout:** this Mac isn't on the lab network.
- **Connection refused:** the Rsync service is off.
- **Your module isn't in the list:** it isn't Enabled.

---

## 5. Dry run (copies nothing)

```
/opt/homebrew/bin/rsync -rlt -W -h -v -i -n --stats "${EXCL[@]}" "$SRC" "rsync://192.168.3.220/$MODULE/" 2>&1 | tee "$HOME/rsync_logs/$STAMP-DRYRUN-$LABEL-to-$MODULE.log"
```

At the end, check that:
- there are no `rsync error` lines;
- `Number of regular files transferred` and `Total transferred file size` are what you expect.

Then check that nothing already in the module would be replaced. This should print nothing:

```
grep '^<f' "$HOME/rsync_logs/$STAMP-DRYRUN-$LABEL-to-$MODULE.log" | grep -v '^<f+++++++++'
```

`<f+++++++++` is a new file. Any other `<f` line means a file with that name is already in the module and differs. Find out why before going on.

---

## 6. Live run

```
caffeinate -i /opt/homebrew/bin/rsync -rlt -W -h -v -i --stats --info=progress2 --ignore-existing "${EXCL[@]}" --log-file="$HOME/rsync_logs/$STAMP-LIVE-$LABEL-to-$MODULE.log" "$SRC" "rsync://192.168.3.220/$MODULE/"; echo "Exit code: $?"
```

`caffeinate -i` stops the Mac from going to sleep on its own while rsync runs. It doesn't stop someone choosing Sleep or shutting the Mac down.

Once the first files are moving, you can detach (`Ctrl-b`, release, `d`) and come back later with `tmux attach -t ingest`. It's finished when you see the `--stats` summary and `Exit code: 0`. `Number of regular files transferred` should match the dry run.

If it stopped partway, run the same command again in the same tmux window (the step 3 settings are still there). Files that finished are skipped.

---

## 7. Verify

This should print nothing:

```
/opt/homebrew/bin/rsync -rltni "${EXCL[@]}" "$SRC" "rsync://192.168.3.220/$MODULE/"
```

---

## 8. On .220: switch the module off

In the TrueNAS web UI, open your module, untick **Enabled**, and **Save**. Stop the Rsync service too if nothing else needs it. Then check from the Mac:

```
/opt/homebrew/bin/rsync rsync://192.168.3.220/
```

Your module should be gone from the list. If you stopped the service, you'll get "Connection refused" instead.

---

## 9. Copy the two log files to .220

This copies only the logs, not your files. The DRYRUN and LIVE logs from this job go from `~/rsync_logs` on the Mac into the `rsync_logs` folder on .220, where the other transfer logs are kept.

```
scp "$HOME/rsync_logs/$STAMP-"* root@192.168.3.220:/mnt/ssd_raid/ssd_raid/_rsync_admin/rsync_logs/
```

It logs in to .220 as root over ssh, so expect a password prompt unless this Mac has an ssh key set up for it. The logs stay on the Mac as well.

Then close the tmux session:

```
exit
```

---

## tmux quick guide

| To | Do this |
|---|---|
| Start a session | `tmux new -s ingest` |
| Leave it running and get your Terminal back (detach) | Press `Ctrl-b`, release **both** keys, then press `d` |
| See which sessions are open | `tmux ls` |
| Go back into a session (reattach) | `tmux attach -t ingest` |
| Scroll back through the output | `Ctrl-b`, release, `[`; then use the arrow keys or Page Up/Down. Press `q` to stop scrolling. |
| Close a session once its copy has finished | `exit` inside it, or `tmux kill-session -t ingest` from outside |

**Detaching:** release `Ctrl-b` fully before pressing `d`. Pressed together, they send `Ctrl-d` instead, which doesn't detach.

**While a copy is running inside tmux:**
- Don't press `Ctrl-c`. It stops rsync. Running the same command again resumes, but there's no reason to stop it.
- Don't type `exit` or other commands. Anything you type waits and runs as soon as rsync finishes, so a typed `exit` would close the session before you see the result.
- Closing the Terminal window is fine; the session keeps running. Logging out of the Mac or restarting it ends the session and stops the copy.

**When you come back:** `tmux ls` shows whether the `ingest` session is still open. A finished copy leaves it open at a prompt, so an open session doesn't mean the copy is still running. Reattach and look for `Exit code:`.

**Checking on a copy without reattaching:** the LIVE log grows as files arrive, and it ends with the `--stats` summary when the copy is done.

```
tail -5 ~/rsync_logs/*-LIVE-*.log
```

If you've run several jobs, this shows the end of each LIVE log; the newest has the latest timestamp in its name.
