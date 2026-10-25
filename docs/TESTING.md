# How the Capability Access Manager maps were tested

Everything in this repository was tested on **synthetic data only**. The maps were also checked against a real Windows 11 system's CAM databases, but no value, count or identifier from that system is published here. Only the method and the pass/fail outcome are.

## 1. Answer-key tests (`tests/run_tests.py`)

`tests/fixtures.py` builds both databases from invented values (`S-1-5-21-0-0-0-100x` SIDs, `C:\Example\` paths, `Example.*` package families). It also computes the expected output **in Python, independently of the maps' SQL**.

Each scenario runs through two engines:
- an emulator of SQLECmd's rules (string-equal IdentifyValue)
- the real SQLECmd.exe

| Scenario | What it proves |
|---|---|
| cam | Each database matches exactly its own map. All 8 queries equal the answer key: rows, exact column set and sort order. Covered cases: unresolved lookup IDs, FileID 0, still-running uses (stop 0), stop-before-start, start 0, and the Allow / Deny / Prompt decode with its DecodeChecked flag |
| cam-negatives | Lookup tables on their own, and a consent-like database with missing tables. Neither matches |
| cross-match | With all upstream SQLECmd maps loaded, each synthetic database matches exactly one map |

When the real SQLECmd is used, every CSV row is also checked:
- it has exactly the header's field count;
- its `SourceFile` cell holds the database path.

Deliberate breakages make the suite fail:
- a swapped consent decode
- FileID 0 allowed to link prompts and identities

## 2. Real-data validation (results only)

On a real Windows 11 system, the maps ran through SQLECmd on **copies** of the CAM databases. The originals were hashed before and after, and were unchanged.

- **Independent query run:** every query's output was compared cell by cell with an independent Python `sqlite3` run of the same SQL. 0 mismatched cells.
- **Independent tool:** rows match the WinWitness parser.
- **Consent decode:** checked against the live ConsentStore registry for the scopes marked `DecodeChecked = Yes`.
- **Alignment:** every CSV row is aligned with its header.

## 3. Stress and performance (`tests/stress.py`, synthetic)

| Input | Result with the real SQLECmd |
|---|---|
| 200,000 packaged + 200,000 desktop usage rows, 50,000 identities, 50,000 prompts | All rows out; about 8 s; about 510 MB peak memory |

In an earlier draft, the related-table counts and first/last times were per-row subqueries, which were quadratic: 71 s for the identity query at only 20,000 rows. They were rewritten as pre-grouped joins. Comparing the old and new queries on 300 random synthetic databases gave identical rows.

## 4. Independent review

Two review rounds by independent reviewers (correctness, robustness, privacy) produced the fixes above, and the final round verified every fix. A privacy audit scanned every file and the full git history against all values extracted from the real test databases and the test machine, and found none.
