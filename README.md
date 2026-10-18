# SQLECmd maps: Windows Capability Access Manager

Two [SQLECmd](https://github.com/EricZimmerman/SQLECmd) maps for the Windows 11 Capability Access Manager (CAM) databases: which apps used the camera, microphone, location and other capabilities, when, and what the user allowed or denied. SQLECmd has no CAM map today. Both maps are tested against synthetic databases with a known answer key, on both an emulator of SQLECmd's matching rules and the real SQLECmd.

## Why these maps exist

On Windows 11, capability usage history is stored in `CapabilityAccessManager.db`, and the Allow / Deny / Prompt decisions in `CapabilityConsentStorage.db`. Registry-only parsers, which read the ConsentStore keys, see only the *last* use per app. The database keeps the history.

## The maps

| Map | Database | What you get |
|---|---|---|
| `Windows_CapabilityAccessManager.smap` | `CapabilityAccessManager.db` | Packaged (Store) and desktop app usage history: start, stop and duration, capability, user SID, binary path, FileID / SHA-1. Also binary identities and capability prompts |
| `Windows_CapabilityConsentStorage.smap` | `CapabilityConsentStorage.db` | Allow / Deny / Prompt decisions per capability, user, app, device and site, plus prompt and migrated-user settings |

Location: `C:\ProgramData\Microsoft\Windows\CapabilityAccessManager\` (set by `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\CapabilityUsageHistory\DatabaseRoot`).

## Use

1. Copy the `.smap` files into SQLECmd's `Maps` folder, or point `--maps` at this repo's `maps` folder.
2. **Work on copies.** Opening the database read-write can checkpoint the `-wal`, and that destroys deleted usage rows in pages past the logical end of the file. SQLECmd also writes `-shm`/`-wal` files beside its input. Collect each `.db` with its `-wal` and `-shm`, because the most recent usage rows can be in the `-wal` only.
3. Run it:
   ```
   SQLECmd.exe -d <copied folder> --hunt --maps <maps folder> --csv <out>\csv
   ```

## Design rules the maps follow

- **A map only matches the right database.** Every IdentifyQuery checks the exact columns the queries read, and that those tables are real tables (a planted view does not match).
- **Nothing is dropped or guessed.**
  - Lookup IDs are resolved with LEFT JOINs.
  - A purged lookup value shows as `Unresolved ID n`, never guessed.
  - A FileID of 0 is never used to link usage, identity and prompt rows.
- **Times are never invented.**
  - FILETIME is shown to the millisecond, truncated rather than rounded.
  - 0, text and out-of-range values give an empty time.
  - The `*Raw` columns keep the stored value as text.
- **Unchecked decodes are labelled.** The Allow / Deny / Prompt decode was checked against the live registry for SystemGlobal, UserGlobal and App. The other scopes are marked `DecodeChecked = No`.
- **Fast on large databases.** Related-table counts and first/last times are grouped once and joined. In a stress test, 200,000 + 200,000 usage rows, 50,000 identities and 50,000 prompts went through SQLECmd in about 8 s.

## SQLECmd behaviours to know (not fixable in a map)

- It writes `-shm`/`-wal` files beside its input, so run it on copies.
- It skips a database that is locked, or held open by another process, and still exits with code 0. On a live system, collect copies first.
- It ignores a `-wal` whose header doesn't match the database, without warning.
- It has no query timeout.
- It converts a value whose stored type differs from the column's declared type: text in an INTEGER column becomes 0 or its leading number. The `*Raw` columns are cast to text so the stored value survives.
- Open the CSVs as text or in Timeline Explorer, not by double-clicking them into Excel.

## Limitations

- Tested against one current Windows 11 build (October 2026).
- **Older builds:** the maps require the full current table and column set. A database from an older build that lacks any of them (for example `ServiceName` or the `*WithConsentID` tables) is skipped by SQLECmd with no warning.
- **Columns not read yet:** `NonPackagedGlobalPromptHistory.BinaryName` and the newer `Context` column. Prompt rows that have no identity row therefore show only the FileID hash, not a binary path.
- **Duration:** `DurationSeconds` is stop minus start. For screen capture this can be a fixed hold time rather than the real length of the capture.
- **Usage history is pruned,** by age and by count (`ExpirationPolicyInDays` and `MaximumSizeOnWrite` under the registry key above). A missing row is not proof that nothing happened, and the newest use can also be in the ConsentStore registry, so check both.

## Tests

See [docs/TESTING.md](docs/TESTING.md). To run them:

```
pip install pyyaml yamllint
yamllint -c .yamllint maps
python tests/run_tests.py                                         # emulator, synthetic data
python tests/run_tests.py --sqlecmd C:\Tools\SQLECmd.exe           # plus the real SQLECmd
python tests/stress.py C:\Tools\SQLECmd.exe                        # large synthetic database
```

## Related

- Phone Link maps (and a relations viewer) are a separate repo: [phone-link-forensics](https://github.com/whitedevil1026/phone-link-forensics).
- For carving deleted CAM rows and WAL slack, see [CAMtool](https://github.com/whitedevil1026/CAMtool).

## Credits

Background: the *CapabilityAccessManager.db Deep Dive* series by cyber.sundae.dfir, and the Amcache FileId/SHA-1 note by NVISO. MIT licence.
