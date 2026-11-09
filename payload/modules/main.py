# ============================================================
# MAIN.PY
# PROVIDES: _plog/log_line, DIAG_PATH, _ALREADY_LOADED, UDP transport
#           (_init_udp/_esp_udp_open/_write_udp_esp/_write_udp_skin/
#           _write_udp_chunked), _read_udp_thread, crash capture,
#           _split_report_once, _create_diag_once, _weaponfx_probe_skin,
#           _log_rotate_if_big, _one_file_open, _thread_excepthook
# REQUIRES: config.sync_attrs, json/socket/threading (stdlib)
# ABI: _read_udp_thread name is frozen (native docs); UDP 50000 in,
#      50001/50002/50003 out.
# ============================================================
"""Boot, logging, crash capture and UDP transport.

Runs its boot (UDP sockets + receiver thread) at concat-exec time exactly
where the old core.py did - before the catalog build - so timing matches
the proven behaviour. Feature modules may call _plog from their own exec.
"""

# #======================================================================
# //  CORE.PY
# //
# //  This file is for: CORE INFRASTRUCTURE: imports, logging, config sync (UDP 50000), the hook framework, module loaders, the re-exec guard, diagnostics.
# //
# //  Part of the split TREACKY BS payload (v2.112).  The runtime
# //  file payload/skins_payload.py is GENERATED: run
# //  tools/build_payload.py after editing these modules.
# #======================================================================
# #======================================================================
# //  CORE.PY
# //
# //  This file is for: CORE INFRASTRUCTURE: imports, logging, config sync (UDP 50000), the hook framework, module loaders, the re-exec guard, diagnostics.
# //
# //  Part of the split TREACKY BS payload (v2.112).  The runtime
# //  file payload/skins_payload.py is GENERATED: run
# //  tools/build_payload.py after editing these modules.
# #======================================================================
# ============================================================
# TREACKY BS PAYLOAD v2.7  (@TreackyModz / Blood Strike / Messiah)
# Test build: weapon skins + Striker skins + kill effects only (ESP/Aimbot removed).
# Forced skins are CLIENT-VISUAL: they change what renders on
# this device. They do not grant server-side ownership and
# other players keep seeing the real (owned) skins.
# ============================================================
import os, json, re, threading, functools, sys, inspect, time, socket, math, random
_V841PERF_AUTO_DIAGNOSTICS = False
import weakref  # ESP tick registration keeps weakrefs to Spaces

# ---- re-exec sentinel: sockets/threads start once; HOOK v2 is idempotent
_ALREADY_LOADED = getattr(sys, '_skins_only_v2_loaded', False)
sys._skins_only_v2_loaded = True

# v7.1: ONE file for everything. skin_diag.txt and nexora_debug.txt were two
# halves of the same story and had to be read side by side; the hero-catalog
# file was a third. All of it now lands here.
DIAG_PATH = "/storage/emulated/0/Levi/levi_debug.txt"
# v2.121: one-time move of the old /Nexora data dir -> /Levi (user rename)
try:
    if not os.path.isdir("/storage/emulated/0/Levi") and os.path.isdir("/storage/emulated/0/Nexora"):
        os.rename("/storage/emulated/0/Nexora", "/storage/emulated/0/Levi")
except Exception:
    pass
LOG_MAX_BYTES = 3 * 1024 * 1024
_log_state = {'size': -1, 'rotated': 0}


# ============================================================

def _log_rotate_if_big():
    """Keep the file readable: over 3 MB it is cut to its last 400 KB."""
    try:
        size = os.path.getsize(DIAG_PATH)
    except Exception:
        return
    if size < LOG_MAX_BYTES:
        return
    try:
        with open(DIAG_PATH, "r", errors="replace") as f:
            try:
                f.seek(-400 * 1024, os.SEEK_END)
            except Exception:
                pass
            tail = f.read()
        with open(DIAG_PATH, "w") as f:
            f.write("==== log rotated at %s (previous %d bytes cut) ====\n"
                    % (time.strftime("%Y-%m-%d %H:%M:%S"), size))
            f.write(tail)
        _log_state['rotated'] += 1
    except Exception:
        pass


# v7.1: the vendored hero block and a few older call sites still open their own
# file names. They are redirected here instead of being edited - that block has
# to stay byte identical to the zip. Anything that is not one of those exact
# names goes straight through.
import builtins as _bi
_real_open = _bi.open


def _one_file_open(path, *a, **k):
    try:
        if isinstance(path, str) and path.endswith(
                ('nexora_herobuild_debug.txt', 'skin_diag.txt')):
            path = DIAG_PATH
    except Exception:
        pass
    return _real_open(path, *a, **k)


try:
    _bi.open = _one_file_open
except Exception:
    pass


# v7.5: a sender thread that dies takes its feed with it and the menu sits on
# "scanning..." forever with no evidence. Every unhandled thread exception is
# logged with its name and traceback instead.
def _thread_excepthook(args):
    try:
        import traceback
        _plog('[THREAD-DIED] %s: %s\n%s'
              % (getattr(args.thread, 'name', '?'), args.exc,
                 '\n'.join('    ' + l for l in
                           traceback.format_exception(args.exc_type, args.exc,
                                                      args.exc_tb)[:12])))
    except Exception:
        pass


try:
    threading.excepthook = _thread_excepthook
except Exception:
    pass


def _plog(msg):
    try:
        os.makedirs("/storage/emulated/0/Levi", exist_ok=True)
        _log_rotate_if_big()
        with open(DIAG_PATH, "a") as f:
            f.write(str(msg) + "\n")
    except Exception:
        pass

# ============================================================
# v10.12.2-split-r1: THE PAYLOAD IS BUILT FROM C++ PARTS NOW
#
# srcpy.cpp (the combiner / "python.cpp") joins srcpy_core +
# srcpy_emot (emot.cpp) + srcpy_tail into the script you are reading.
# Before executing, main.cpp writes a composition report next to the
# diag log. We echo it here so ONE log answers "which parts are in
# this build" - without it, a missing part shows up as a Python
# syntax error with no indication of which one vanished.
#
# The report is written by the native side, so this cannot fail the
# payload: any problem here is caught and ignored.
def _split_report_once():
    try:
        path = '/storage/emulated/0/Levi/srcpy_parts.txt'
        if not os.path.isfile(path):
            _plog('[SRCPY] composition report missing (native side did not '
                  'write it) - payload still executed')
            return
        with open(path, 'r', errors='replace') as f:
            line = f.readline().strip()
        if line:
            _plog('[SRCPY] %s' % (line,))
    except Exception:
        pass


try:
    _split_report_once()
except Exception:
    pass

_plog('[BOOT] exec start (already_loaded=%s) utc=%s build=2.126/vc226'
      % (_ALREADY_LOADED, time.strftime('%Y-%m-%d %H:%M:%S')))

# v7.30R26: CRASH CAPTURE. The R25 device log ended silently at the
# vault / avatar-card crashes - nothing of the actual error reached
# our diag file. Chain-safe hooks now write every UNCAUGHT Python
# error (and native faults, when faulthandler exists) to the diag
# file before the process dies, then hand over to the previous hook
# so game behavior is unchanged.
try:
    _crash_prev_hook = sys.excepthook

    _crash_benign_count = [0]

    def _treacky_excepthook(tp, val, tb):
        try:
            # v2.124: the [asiocore] "create entity ... before player
            # avatar!!" ordering RuntimeErrors are engine noise seen 46x per
            # run. Count them in one line so REAL crashes stand out.
            if (tp is RuntimeError
                    and str(val).startswith('[asiocore] create entity:')
                    and str(val).endswith('before player avatar!!')):
                _crash_benign_count[0] += 1
                if (_crash_benign_count[0] == 1
                        or _crash_benign_count[0] % 25 == 0):
                    _plog('[CRASH-BENIGN] asio create-entity ordering x%d '
                          '(suppressed)' % _crash_benign_count[0])
                return
            _plog('[CRASH] uncaught %s: %r' % (getattr(tp, '__name__', tp),
                                               val))
            try:
                import traceback as _tbc
                _plog('[CRASH] ' + ''.join(
                    _tbc.format_exception(tp, val, tb))[-4000:])
            except Exception:
                pass
        except Exception:
            pass
        try:
            _crash_prev_hook(tp, val, tb)
        except Exception:
            pass

    sys.excepthook = _treacky_excepthook
except Exception:
    pass
try:
    _crash_prev_thook = threading.excepthook

    def _treacky_thread_excepthook(args):
        try:
            _tn = getattr(getattr(args, 'thread', None), 'name', '?')
            _tp = getattr(args, 'exc_type', None)
            _vl = getattr(args, 'exc_value', None)
            _plog('[CRASH] thread %s uncaught %s: %r'
                  % (_tn, getattr(_tp, '__name__', _tp), _vl))
            try:
                import traceback as _tbc
                _plog('[CRASH] ' + ''.join(
                    _tbc.format_exception(_tp, _vl,
                                          getattr(args, 'exc_traceback',
                                                  None)))[-4000:])
            except Exception:
                pass
        except Exception:
            pass
        try:
            _crash_prev_thook(args)
        except Exception:
            pass

    threading.excepthook = _treacky_thread_excepthook
except Exception:
    pass
try:
    import faulthandler as _fhmod
    _crash_fh_file = open(DIAG_PATH, 'a')
    _fhmod.enable(file=_crash_fh_file, all_threads=True)
    _plog('[BOOT] crash-capture on (faulthandler)')
except Exception as _fhe:
    try:
        _plog('[BOOT] crash-capture partial (no faulthandler: %r)' % (_fhe,))
    except Exception:
        pass


_create_diag_done = [False]
_create_diag_wids = set()
_create_sig_logged = [False]

def _create_diag_once(wid, args, kwargs):
    # Evidence for the EquipCaseFactory.Create positional layout: the v2.7.2
    # device log showed (doll, guid, wid, <a>, <b>) with the skin id moving
    # between slot 3 and slot 4 depending on the weapon, so instead of
    # assuming an index we now report every call's layout plus, once, the
    # real function signature, and mark which slot holds a known skin id.
    global _create_sig_logged
    if not _create_sig_logged[0]:
        _create_sig_logged[0] = True
        try:
            _plog("[EQUIP-SIG] EquipCaseFactory.Create=%r"
                  % (inspect.signature(EquipCaseFactory._Create),))
        except Exception as _sig_err:
            _plog("[EQUIP-SIG] signature unavailable err=%r" % (_sig_err,))
        try:
            _wcm = sys.modules.get('gclient.gameplay.logic_base.equips.weapon_case')
            _wc = getattr(_wcm, 'WeaponCase', None)
            if _wc is not None:
                _plog("[EQUIP-SIG] WeaponCase.ChangeWeaponSkin=%r"
                      % (inspect.signature(_wc._ChangeWeaponSkin),))
            else:
                _plog("[EQUIP-SIG] WeaponCase module not loaded yet")
        except Exception as _sig_err2:
            _plog("[EQUIP-SIG] ChangeWeaponSkin signature err=%r" % (_sig_err2,))
    if wid in _create_diag_wids or len(_create_diag_wids) >= 6:
        return
    _create_diag_wids.add(wid)
    try:
        skins = set()
        try:
            _row = weapon_row(wid)[1] or []
            skins = set(_safe_int(x, 0) for x in _row[1:])
        except Exception:
            pass
        slots = []
        for idx, val in enumerate(args):
            iv = _safe_int(val, None)
            mark = ''
            if iv is not None and iv in skins:
                mark = ' <== KNOWN SKIN ID'
            elif iv == 0:
                mark = ' (0)'
            slots.append('arg%d=%r%s' % (idx, val, mark))
        _plog("[CREATE] wid=%r nargs=%d %s kwargs=%r"
              % (wid, len(args), ' '.join(slots), list(kwargs.keys())))
    except Exception:
        pass
    # v4.7: dump the tables for the skin the menu actually selected. The
    # v2.7.2 log only ever probed gun_skin_template_data[171100013] - the
    # default *template* row - whose FX fields are all None by design.
    try:
        _selected = _get_forced_weapon_skin(wid)
        _idx = _safe_int(sync_attrs.get('iSkin_%s' % (wid,), 0), 0)
        if _selected:
            _weaponfx_probe_skin(_selected, wid, 'menu-selected')
        else:
            _plog('[EQUIP-PROBE] wid=%r no skin selected (iSkin=%r)' % (wid, _idx))
    except Exception as _pe:
        _plog('[EQUIP-PROBE] error=%r' % (_pe,))


def _weaponfx_probe_skin(skin_id, equip_id=None, reason=''):
    """Dump every FX-bearing table for one skin id. v2.7.2 only ever probed
    gun_skin_template_data (the *template* row, all FX fields None) - the
    kill effect / tracer / kill_mat live on the equip + item rows, which
    were never looked at. This prints them all so the next device log is
    conclusive instead of another guess."""
    if not _V841PERF_AUTO_DIAGNOSTICS:
        return
    try:
        skin_id = _safe_int(skin_id, 0)
    except Exception:
        return
    if not skin_id:
        return
    key = (skin_id, reason)
    if key in _weaponfx_probes_done:
        return
    _weaponfx_probes_done.add(key)
    _plog('[EQUIP-PROBE] ---- skin=%r equip=%r reason=%s' % (skin_id, equip_id, reason))
    for module_name in (
        'gclient.data.gun_skin_template_data',
        'gclient.data.gun_skin_equip_data',
        'gclient.data.gun_skin_item_data',
        'gclient.data.gun_skin_base_data',
        'gclient.data.gun_skin_template_base_data',
        'gclient.data.equip_data',
        'gclient.data.lobby_item_data',
        'gclient.data.lobby_gun_skin_item_data',
    ):
        try:
            mod = sys.modules.get(module_name) or _import_module(module_name)
            data = getattr(mod, 'data', None)
            row = None
            try:
                row = data[skin_id]
            except Exception:
                row = None
            if row is None:
                _plog('[EQUIP-PROBE] %s[%r]=<absent>' % (module_name, skin_id))
                continue
            try:
                row = dict(_data_items(row)) if not isinstance(row, dict) else dict(row)
            except Exception:
                row = {'repr': repr(row)[:400]}
            interesting = {}
            for k, v in row.items():
                kl = str(k).lower()
                if any(t in kl for t in ('effect', 'kill', 'tracer', 'trace', 'hit',
                                         'mat', 'model', 'replace', 'anim', 'pose',
                                         'fx', 'sfx', 'optic', 'bullet')):
                    interesting[str(k)] = v
            _plog('[EQUIP-PROBE] %s[%r] fields=%d fx_fields=%r'
                  % (module_name, skin_id, len(row), interesting))
            if module_name.endswith('gun_skin_equip_data') or module_name.endswith('equip_data'):
                _plog('[EQUIP-PROBE] %s[%r] full=%r' % (module_name, skin_id, row))
        except Exception as _e:
            _plog('[EQUIP-PROBE] %s error=%r' % (module_name, _e))
    _plog('[EQUIP-PROBE] ---- end skin=%r' % (skin_id,))


_weaponfx_probes_done = set()

# ============================================================
# UDP: 50000 C++ -> Python (config) / 50001 ESP entities
#      50002 weapon catalog / 50003 hero catalog.
# ============================================================
UDP_CONFIG_PORT = 50000
UDP_ESP_PORT    = 50001   # ESP: Python -> C++ entity feed (sync_entities.h)
UDP_SKIN_PORT   = 50002
UDP_IDS_PORT    = 50006   # v7.30R6: live ID-scan status -> menu line

_recv_sock = None
_esp_sock = None
_skin_sock = None
_udp_initialized = False

def _init_udp():
    global _recv_sock, _skin_sock, _udp_initialized
    if _udp_initialized:
        return
    try:
        _recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        _recv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 2 * 1024 * 1024)
        _recv_sock.bind(("127.0.0.1", UDP_CONFIG_PORT))
        _recv_sock.settimeout(0.25)
        _skin_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        _skin_sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 2 * 1024 * 1024)
        _skin_sock.settimeout(0.25)
        _udp_initialized = True
    except Exception as e:
        _plog("[UDP] init error: %r" % (e,))

def _esp_udp_open():
    """Lazily open the ESP-only socket. Kept OUT of _init_udp so that
    _init_udp stays byte-identical to the SRC you uploaded."""
    global _esp_sock
    if _esp_sock is not None:
        return True
    try:
        _esp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        _esp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 2 * 1024 * 1024)
        _esp_sock.settimeout(0.25)
        return True
    except Exception as e:
        _esp_sock = None
        _plog("[UDP] esp socket error: %r" % (e,))
        return False

def _write_udp_esp(data):
    # ESP entity feed to sync_entities.h (C++ reader on 50001).
    if not _esp_udp_open():
        return
    try:
        if isinstance(data, str):
            data = data.encode('utf-8')
        _esp_sock.sendto(data, ("127.0.0.1", UDP_ESP_PORT))
    except Exception:
        pass

def _write_udp_skin(data):
    if not _udp_initialized:
        _init_udp()
    try:
        if isinstance(data, str):
            data = data.encode('utf-8')
        _skin_sock.sendto(data, ("127.0.0.1", UDP_SKIN_PORT))
    except Exception:
        pass


def _write_udp_chunked(write_fn, text, max_bytes=8192):
    # v2.3: the whole catalog can exceed one safe UDP datagram. The C++
    # receiver is a line accumulator, so send complete-line chunks only.
    # A 1ms gap avoids bursting past the receiver's socket buffer.
    try:
        raw = text.encode('utf-8', 'replace') if isinstance(text, str) else bytes(text)
        if len(raw) <= max_bytes:
            write_fn(raw)
            return
        start = 0
        while start < len(raw):
            end = min(len(raw), start + max_bytes)
            if end < len(raw):
                nl = raw.rfind(b'\n', start, end)
                if nl > start:
                    end = nl + 1
            write_fn(raw[start:end])
            start = end
            if start < len(raw):
                try:
                    time.sleep(0.001)
                except Exception:
                    pass
    except Exception:
        pass


def _read_udp_thread():
    if not _udp_initialized:
        _init_udp()
    while True:
        try:
            data, _addr = _recv_sock.recvfrom(65536)
            if data:
                parsed = json.loads(data.decode('utf-8'))
                if isinstance(parsed, dict):
                    sync_attrs.update(parsed)
                    # v7.30R17: mirror REMOVED - the ORIGINAL BSB block
                    # reads bHeroSkinHack live on every hook call, so the
                    # menu toggle is a REAL on/off again (default on).
                    fn = globals().get('_load_skinsel')
                    if fn:
                        try: fn()
                        except Exception: pass
        except socket.timeout:
            pass
        except Exception:
            pass

if not _ALREADY_LOADED:
    _init_udp()
    threading.Thread(target=_read_udp_thread, daemon=True).start()

