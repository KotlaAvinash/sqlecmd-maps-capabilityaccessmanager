"""Synthetic Capability Access Manager databases with a known answer key.

All values are invented (S-1-5-21-0-0-0-100x SIDs, C:\\Example\\ paths, Example.* package
families). The schema is written from the column names the maps read; no real database is used.
"""
import os
import sqlite3
from datetime import datetime, timedelta, timezone

EPOCH_1601 = datetime(1601, 1, 1, tzinfo=timezone.utc)


def text(v):
    """How a value appears in SQLECmd's CSV (and in the emulator)."""
    if v is None:
        return ''
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


M_CAM = 'Windows_CapabilityAccessManager.smap'
M_CONS = 'Windows_CapabilityConsentStorage.smap'
LOOKUPS = ['Capabilities', 'PackageFamilyNames', 'BinaryFullPaths', 'Users', 'FileIDs', 'ProgramIDs',
           'AppNames', 'ServiceNames', 'AccessGUIDs']

CAM_DDL = ''.join(f'CREATE TABLE {t}(ID INTEGER PRIMARY KEY, StringValue TEXT UNIQUE);' for t in LOOKUPS) + '''
CREATE TABLE PackagedUsageHistory(ID INTEGER PRIMARY KEY, Capability INTEGER, PackageFamilyName INTEGER, UserSid INTEGER,
  AccessGUID INTEGER, LastUsedTimeStart INTEGER, LastUsedTimeStop INTEGER, AccessBlocked INTEGER, Label INTEGER, AppName INTEGER);
CREATE TABLE NonPackagedUsageHistory(ID INTEGER PRIMARY KEY, Capability INTEGER, FileID INTEGER, ProgramID INTEGER,
  BinaryFullPath INTEGER, UserSid INTEGER, AccessGUID INTEGER, LastUsedTimeStart INTEGER, LastUsedTimeStop INTEGER,
  AccessBlocked INTEGER, Label INTEGER, AppName INTEGER, ServiceName INTEGER);
CREATE TABLE NonPackagedIdentityRelationship(ID INTEGER PRIMARY KEY, BinaryFullPath INTEGER, FileID INTEGER,
  ProgramID INTEGER, LastObservedTime INTEGER);
CREATE TABLE NonPackagedGlobalPromptHistory(ID INTEGER PRIMARY KEY, Capability INTEGER, FileID INTEGER, ProgramID INTEGER,
  UserSid INTEGER, ShownTime INTEGER);
CREATE TABLE PackagedGlobalPromptHistory(ID INTEGER PRIMARY KEY, Capability INTEGER, PackageFamilyName INTEGER, UserSid INTEGER);
'''

CONS_DDL = '''
CREATE TABLE SystemGlobal(Capability TEXT, Value INTEGER);
CREATE TABLE UserGlobal(Capability TEXT, User TEXT, Value INTEGER);
CREATE TABLE ClassicGlobal(Capability TEXT, User TEXT, Value INTEGER);
CREATE TABLE App(Capability TEXT, User TEXT, PackageFamily TEXT, Value INTEGER);
CREATE TABLE UserGlobalWithConsentID(Capability TEXT, User TEXT, ConsentID TEXT, Value INTEGER);
CREATE TABLE ClassicGlobalWithConsentID(Capability TEXT, User TEXT, ConsentID TEXT, Value INTEGER);
CREATE TABLE AppWithConsentID(Capability TEXT, User TEXT, PackageFamily TEXT, ConsentID TEXT, Value INTEGER);
CREATE TABLE ShowGlobalPrompts(Capability TEXT, User TEXT, Value INTEGER);
CREATE TABLE MigratedUsers(User TEXT, Value INTEGER);
'''

BASE = datetime(2025, 2, 3, 4, 5, 6, tzinfo=timezone.utc)


def ft(dt, ticks=0):
    return int((dt - EPOCH_1601).total_seconds()) * 10_000_000 + ticks


def ft_ms(v):
    """Oracle: FILETIME -> 'YYYY-MM-DD HH:MM:SS.mmm', truncated; empty for 0 or less."""
    if v is None or v <= 0:
        return ''
    return (EPOCH_1601 + timedelta(seconds=v // 10_000_000)).strftime('%Y-%m-%d %H:%M:%S') + f'.{(v // 10_000) % 1000:03d}'


def build_cam(folder):
    os.makedirs(folder, exist_ok=True)
    con = sqlite3.connect(os.path.join(folder, 'CapabilityAccessManager.db'))
    con.executescript(CAM_DDL)
    look = {
        'Capabilities': ['webcam', 'microphone', 'location'],
        'PackageFamilyNames': ['Example.Camera_abc123', 'Example.Notes_def456'],
        'BinaryFullPaths': ['C:\\Example\\a.exe', 'C:\\Example\\b.exe'],
        'Users': ['S-1-5-21-0-0-0-1001', 'S-1-5-21-0-0-0-1002'],
        'FileIDs': ['0000' + 'ab' * 20, 'not-a-fileid'],
        'ProgramIDs': ['0000example'],
        'AppNames': ['Example App'],
        'ServiceNames': ['ExampleSvc'],
        'AccessGUIDs': ['{00000000-0000-0000-0000-000000000001}'],
    }
    for t, vals in look.items():
        con.executemany(f'INSERT INTO {t} VALUES(?,?)', list(enumerate(vals, start=1)))

    def lk(t, i):
        if i is None:
            return ''
        if i == 0:
            return ''
        vals = look[t]
        return vals[i - 1] if 1 <= i <= len(vals) else f'Unresolved ID {i}'

    exp = {}
    # Packaged usage: normal, still-running (stop 0), unresolved lookups, start 0, blocked, stop < start
    p = [(1, 1, 1, 1, 1, ft(BASE, 1_234_567), ft(BASE + timedelta(seconds=5), 2_345_678), 0, 2, 1),
         (2, 2, 2, 2, 0, ft(BASE, 9_999_999), 0, 1, 0, 0),
         (3, 9, 7, 8, 5, ft(BASE, 0), ft(BASE, 0), 7, 0, 4),
         (4, 1, 1, 1, 1, 0, ft(BASE), 0, 0, 1),
         (5, 3, 1, 2, 1, ft(BASE + timedelta(hours=1)), ft(BASE), 0, 0, 1)]
    con.executemany('INSERT INTO PackagedUsageHistory VALUES(?,?,?,?,?,?,?,?,?,?)', p)
    p = sorted(p, key=lambda r: (r[5], r[0]))
    exp[(M_CAM, 'PackagedUsageHistory')] = {'blobs': {}, 'ordered': True, 'rows': [{
        'ID': text(r[0]), 'LastUsedTimeStartUTC': ft_ms(r[5]), 'LastUsedTimeStopUTC': ft_ms(r[6]),
        'DurationSeconds': text(round((r[6] - r[5]) / 1e7, 3)) if r[5] > 0 and r[6] > 0 and r[6] >= r[5] else '',
        'Capability': lk('Capabilities', r[1]), 'AppName': lk('AppNames', r[9]),
        'PackageFamilyName': lk('PackageFamilyNames', r[2]), 'UserSid': lk('Users', r[3]),
        'AccessBlocked': {0: 'No', 1: 'Yes'}.get(r[7], text(r[7])), 'AccessGUID': lk('AccessGUIDs', r[4]),
        'Label': text(r[8]), 'LastUsedTimeStartRaw': text(r[5]), 'LastUsedTimeStopRaw': text(r[6])} for r in p]}

    ident = [(1, 1, 1, 1, ft(BASE - timedelta(days=30), 5_550_000)), (2, 1, 1, 1, ft(BASE - timedelta(days=10))),
             (3, 2, 2, 1, 0), (4, 1, 0, 1, ft(BASE - timedelta(days=50))), (5, 7, 2, 1, ft(BASE - timedelta(days=60)))]
    con.executemany('INSERT INTO NonPackagedIdentityRelationship VALUES(?,?,?,?,?)', ident)
    prompts = [(1, 3, 1, 1, 1, ft(BASE - timedelta(days=29), 120_000)), (2, 3, 1, 1, 2, ft(BASE - timedelta(days=5))),
               (3, 3, 2, 1, 1, 0), (4, 3, 9, 0, 9, ft(BASE)), (5, 3, 0, 0, 1, ft(BASE - timedelta(days=1)))]
    con.executemany('INSERT INTO NonPackagedGlobalPromptHistory VALUES(?,?,?,?,?,?)', prompts)
    n = [(1, 1, 1, 1, 1, 1, 1, ft(BASE, 4_444_444), ft(BASE + timedelta(seconds=90), 1), 0, 2, 1, 1),
         (2, 2, 2, 1, 2, 2, 0, ft(BASE + timedelta(minutes=3)), 0, 1, 0, 0, 0),
         (3, 8, 8, 8, 8, 8, 8, ft(BASE + timedelta(minutes=4)), ft(BASE + timedelta(minutes=5)), 0, 0, 8, 8)]
    con.executemany('INSERT INTO NonPackagedUsageHistory VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)', n)

    def sha1(fid_index):
        v = lk('FileIDs', fid_index)
        return v[4:] if len(v) == 44 and v.startswith('0000') else ''

    def first_obs(fid, bfp):
        ts = [r[4] for r in ident if r[2] == fid and r[1] == bfp and r[4] > 0 and fid != 0]
        return ft_ms(min(ts)) if ts else ''

    exp[(M_CAM, 'NonPackagedUsageHistory')] = {'blobs': {}, 'rows': [{
        'ID': text(r[0]), 'LastUsedTimeStartUTC': ft_ms(r[7]), 'LastUsedTimeStopUTC': ft_ms(r[8]),
        'DurationSeconds': text(round((r[8] - r[7]) / 1e7, 3)) if r[7] > 0 and r[8] > 0 and r[8] >= r[7] else '',
        'Capability': lk('Capabilities', r[1]), 'AppName': lk('AppNames', r[11]),
        'BinaryFullPath': lk('BinaryFullPaths', r[4]), 'FileID': lk('FileIDs', r[2]), 'FileIDSHA1': sha1(r[2]),
        'ProgramID': lk('ProgramIDs', r[3]), 'UserSid': lk('Users', r[5]), 'ServiceName': lk('ServiceNames', r[12]),
        'AccessBlocked': {0: 'No', 1: 'Yes'}.get(r[9], text(r[9])), 'AccessGUID': lk('AccessGUIDs', r[6]),
        'Label': text(r[10]), 'IdentityLastObservedTimeUTC': first_obs(r[2], r[4]),
        'LastUsedTimeStartRaw': text(r[7]), 'LastUsedTimeStopRaw': text(r[8])} for r in n]}

    exp[(M_CAM, 'NonPackagedIdentityRelationship')] = {'blobs': {}, 'rows': [{
        'ID': text(r[0]), 'LastObservedTimeUTC': ft_ms(r[4]), 'BinaryFullPath': lk('BinaryFullPaths', r[1]),
        'FileID': lk('FileIDs', r[2]), 'FileIDSHA1': sha1(r[2]), 'ProgramID': lk('ProgramIDs', r[3]),
        'UsageRows': text(sum(1 for u in n if u[2] == r[2] and u[4] == r[1])),
        'PromptRows': text(sum(1 for g in prompts if g[2] == r[2] and r[2] != 0)),
        'FirstPromptShownTimeUTC': ft_ms(min([g[5] for g in prompts if g[2] == r[2] and g[5] > 0 and r[2] != 0], default=0)),
        'LastObservedTimeRaw': text(r[4])} for r in ident]}

    def ident_paths(fid):
        if fid == 0:
            return ''
        paths = [lk('BinaryFullPaths', r[1]) for r in ident if r[2] == fid]
        return ' | '.join(sorted(paths))

    exp[(M_CAM, 'NonPackagedGlobalPromptHistory')] = {'blobs': {}, 'list_cols': ['IdentityBinaryFullPath'], 'rows': [{
        'ID': text(g[0]), 'ShownTimeUTC': ft_ms(g[5]), 'Capability': lk('Capabilities', g[1]),
        'IdentityBinaryFullPath': ' | '.join(sorted(ident_paths(g[2]).split(' | '))) if ident_paths(g[2]) else '', 'FileID': lk('FileIDs', g[2]), 'FileIDSHA1': sha1(g[2]),
        'ProgramID': lk('ProgramIDs', g[3]), 'UserSid': lk('Users', g[4]), 'ShownTimeRaw': text(g[5])} for g in prompts]}

    pp = [(1, 3, 1, 1), (2, 3, 0, 9)]
    con.executemany('INSERT INTO PackagedGlobalPromptHistory VALUES(?,?,?,?)', pp)
    exp[(M_CAM, 'PackagedGlobalPromptHistory')] = {'blobs': {}, 'rows': [{
        'ID': text(g[0]), 'Capability': lk('Capabilities', g[1]), 'PackageFamilyName': lk('PackageFamilyNames', g[2]),
        'UserSid': lk('Users', g[3])} for g in pp]}
    con.commit()
    con.close()

    con = sqlite3.connect(os.path.join(folder, 'CapabilityConsentStorage.db'))
    con.executescript(CONS_DDL)
    u1, u2 = 'S-1-5-21-0-0-0-1001', 'S-1-5-21-0-0-0-1002'
    dec = {'Allow': 1, 'Deny': 2, 'Prompt': 3}
    rows = [('SystemGlobal', 'Machine-wide default', 'webcam', None, None, None, 1),
            ('UserGlobal', 'Per-user switch for the capability', 'webcam', u1, None, None, 2),
            ('ClassicGlobal', 'Per-user switch for desktop apps', 'microphone', u1, None, None, 3),
            ('App', 'Per-user decision for one app', 'location', u2, 'Example.Camera_abc123', None, 1),
            ('UserGlobalWithConsentID', 'Per-user decision for one device or site', 'bluetooth', u1, None, 'BluetoothLE#BluetoothLE00:00:00:00:00:00-00:00:00:00:00:01', 3),
            ('ClassicGlobalWithConsentID', 'Per-user decision for one device or site, desktop apps', 'passkeys', u2, None, 'example.com', 2),
            ('AppWithConsentID', 'Per-user decision for one device or site, one app', 'bluetooth', u2, 'Example.Notes_def456', 'example.org', 7)]
    for scope, _, cap, user, pf, cid, v in rows:
        cols = {'SystemGlobal': (cap, v), 'UserGlobal': (cap, user, v), 'ClassicGlobal': (cap, user, v),
                'App': (cap, user, pf, v), 'UserGlobalWithConsentID': (cap, user, cid, v),
                'ClassicGlobalWithConsentID': (cap, user, cid, v), 'AppWithConsentID': (cap, user, pf, cid, v)}[scope]
        con.execute(f'INSERT INTO {scope} VALUES({",".join("?" * len(cols))})', cols)
    inv = {v: k for k, v in dec.items()}
    exp[(M_CONS, 'ConsentDecisions')] = {'blobs': {}, 'rows': [{
        'Scope': s, 'ScopeDescription': d, 'Capability': c, 'UserSid': text(u), 'PackageFamily': text(pf),
        'ConsentID': text(cid), 'Decision': inv.get(v, 'Unknown'),
        'DecodeChecked': 'Yes' if s in ('SystemGlobal', 'UserGlobal', 'App') else 'No',
        'ValueRaw': text(v)} for s, d, c, u, pf, cid, v in rows]}
    con.executemany('INSERT INTO ShowGlobalPrompts VALUES(?,?,?)', [('location', u1, 1), ('location', u2, 0)])
    exp[(M_CONS, 'ConsentShowGlobalPrompts')] = {'blobs': {}, 'rows': [
        {'Capability': 'location', 'UserSid': u1, 'ValueRaw': '1'}, {'Capability': 'location', 'UserSid': u2, 'ValueRaw': '0'}]}
    con.executemany('INSERT INTO MigratedUsers VALUES(?,?)', [(u1, 1), (u2, 1)])
    exp[(M_CONS, 'ConsentMigratedUsers')] = {'blobs': {}, 'rows': [
        {'UserSid': u1, 'ValueRaw': '1'}, {'UserSid': u2, 'ValueRaw': '1'}]}
    con.commit()
    con.close()
    return exp


def build_cam_negatives(folder):
    """Lookup tables alone, or a consent-like DB missing tables, must not match."""
    os.makedirs(folder, exist_ok=True)
    con = sqlite3.connect(os.path.join(folder, 'lookups_only.db'))
    con.executescript(''.join(f'CREATE TABLE {t}(ID INTEGER PRIMARY KEY, StringValue TEXT);' for t in LOOKUPS))
    con.close()
    con = sqlite3.connect(os.path.join(folder, 'consent_partial.db'))
    con.executescript('CREATE TABLE SystemGlobal(Capability TEXT, Value INTEGER); CREATE TABLE App(Capability TEXT, User TEXT, PackageFamily TEXT, Value INTEGER);')
    con.close()
    return {}


def build_cam_stress(folder, usage=200_000, identities=50_000, prompts=50_000):
    os.makedirs(folder, exist_ok=True)
    con = sqlite3.connect(os.path.join(folder, 'CapabilityAccessManager.db'))
    con.executescript(CAM_DDL)
    for t in LOOKUPS:
        con.executemany(f'INSERT INTO {t} VALUES(?,?)', ((i, f'{t}-{i}') for i in range(1, identities + 1)))
    t0 = ft(BASE)
    con.executemany('INSERT INTO NonPackagedIdentityRelationship VALUES(?,?,?,?,?)',
                    ((i, i, i, i, t0 - i) for i in range(1, identities + 1)))
    con.executemany('INSERT INTO NonPackagedGlobalPromptHistory VALUES(?,?,?,?,?,?)',
                    ((i, 1, i, i, 1, t0 + i) for i in range(1, prompts + 1)))
    con.executemany('INSERT INTO NonPackagedUsageHistory VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    ((i, 1, i % identities + 1, 1, i % identities + 1, 1, 1, t0 + i * 10_000_000,
                      t0 + i * 10_000_000 + 50_000_000, 0, 0, 1, 1) for i in range(1, usage + 1)))
    con.executemany('INSERT INTO PackagedUsageHistory VALUES(?,?,?,?,?,?,?,?,?,?)',
                    ((i, 1, 1, 1, 1, t0 + i, t0 + i + 1, 0, 0, 1) for i in range(1, usage + 1)))
    con.commit()
    con.close()
    return {'usage': usage, 'identities': identities, 'prompts': prompts}
