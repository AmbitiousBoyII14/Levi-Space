# ============================================================
# WEAPON.PY (payload feature module)
# PROVIDES: dlc_api_probe, dlcmgr, dlc_download_now, dlc_match_skip, dlc_worker, dlc_enqueue, try_dlc_download, dlc_preflight, server_arm, try_dlc_call, maybe_download_melee, _reg_live, _striker_doll_note, ctrl_note, ... +27 more | DLC_SPACING, ARMED, _WEAPONFX_IDENTITY_FIELDS, _FX_CASE_KEYS
# REQUIRES: shared namespace (config/names/main/game_api/catalog);
#           game modules imported inline, verified against the dumps.
# Feature module - see REWRITE_PLAN.md S1.
# ============================================================
"""Weapon-case skin application + effect pipeline: forced-skin apply core, EquipCaseFactory wraps, ballistic/hit FX hooks, DLC download queue that feeds missing skin rows."""

# #======================================================================
# //  WEAPON.PY
# //
# //  This file is for: WEAPON / DLC: the download queue + AutoDownloadItem fetches (melee-anywhere, others lobby-only), the weapon-case skin apply (ChangeWeaponSkin/ChangeWeaponGuise chain), the WEAPONFX rebuild pump, the ballistic/hit effect hooks.
# //
# //  Part of the split TREACKY BS payload (v2.112).  The runtime
# //  file payload/skins_payload.py is GENERATED: run
# //  tools/build_payload.py after editing these modules.
# #======================================================================
def dlc_api_probe():
    """v8.15: the melee models need the game DLC download before
    they render (the per-item download ask). The v8.14 probe found
    the modules; this logs the real signatures + method names once
    so the next device log shows the exact call shape."""
    if dlc_probed[0]:
        return
    dlc_probed[0] = True
    try:
        out = []
        for _mod_name in ('gclient.framework.util.downloader',
                          'gclient.framework.util.'
                          'dlc_download_request'):
            _mod = sys.modules.get(_mod_name)
            if _mod is None:
                continue
            for _attr in ('DownloadableContentManager',
                          'DownloadContent', 'DlcDownloadRequest',
                          'DLCTask', 'Singleton'):
                _obj = getattr(_mod, _attr, None)
                if _obj is None:
                    continue
                try:
                    _sig = str(inspect.signature(
                        _obj.__init__ if isinstance(_obj, type)
                        else _obj))
                except Exception:
                    _sig = '?'
                out.append('%s.%s%s'
                           % (_mod_name.rsplit('.', 1)[-1],
                              _attr, _sig))
                if isinstance(_obj, type):
                    try:
                        out.append('  %s.methods=%r'
                                   % (_attr, sorted(
                                       _m for _m in dir(_obj)
                                       if not _m.startswith('_')
                                       and callable(getattr(
                                           _obj, _m, None)))[:40]))
                    except Exception:
                        pass
        if out:
            _plog('[V815] dlc probe %r' % (out[:24],))
    except Exception:
        pass


dlc2_tried = set()


def dlcmgr():
    """v8.16: the probe showed DownloadableContentManager has a
    classmethod instance() (plus init/Destroy on the Singleton
    base)."""
    try:
        _mod = sys.modules.get(
            'gclient.framework.util.downloader')
        _mgr = getattr(_mod, 'DownloadableContentManager',
                       None) if _mod else None
        if isinstance(_mgr, type):
            _inst = getattr(_mgr, 'instance', None)
            if callable(_inst):
                return _inst()
    except Exception:
        pass
    return None


def dlc_download_now(item_id, dlc_ids=None):
    """v8.16: per-item download with the REAL API shapes the v8.15
    probe logged: manager AutoDownloadItem(item) /
    AutoBatchDownloadByLobbyItems([items]),
    DlcDownloadRequest.instance().RequestDlc([dlc], None, dlc),
    DLCTask(dlc_ids, callback, key). Item-level first (that is
    the game's own 'download this item' path - the per-item
    replacement for the 'download all resources' prompt), then
    the batch, then the raw dlc ids. Each shape tried once per
    item, fully guarded, results logged.
    v8.20: this is now the WORKER body - callers go through
    try_dlc_download, which serializes items onto the
    staggered queue below instead of firing them all at once."""
    out = []
    try:
        mgr = dlcmgr()
        if mgr is None:
            out.append('no manager')
            return out
        _item_ok = False
        for meth, args in (
            ('AutoDownloadItem', (item_id,)),
            ('AutoBatchDownloadByLobbyItems', ([item_id],)),
        ):
            try:
                fn = getattr(mgr, meth, None)
                if not callable(fn):
                    continue
                fn(*args)
                out.append('%s ok' % (meth,))
                _item_ok = True
                break
            except Exception as _e:
                out.append('%s=%r' % (meth, _e,))
        if _item_ok:
            # the item download implies its dlc pack - asking again
            # would be a redundant second download.
            if out:
                _plog('[V816] dlc download item=%s -> %r'
                      % (item_id, out))
            return out
        req_mod = sys.modules.get(
            'gclient.framework.util.dlc_download_request')
        _req_cls = getattr(req_mod, 'DlcDownloadRequest',
                           None) if req_mod else None
        if isinstance(_req_cls, type):
            try:
                _ri = getattr(_req_cls, 'instance', None)
                _req = _ri() if callable(_ri) else None
                _rf = getattr(_req, 'RequestDlc', None)
                if callable(_rf):
                    for _dlc in (dlc_ids or ())[:3]:
                        try:
                            _rf([_dlc], None, _dlc)
                            out.append('RequestDlc(%s) ok' % (_dlc,))
                        except Exception as _e:
                            out.append('RequestDlc(%s)=%r'
                                       % (_dlc, _e,))
            except Exception as _e:
                out.append('req=%r' % (_e,))
        if out:
            _plog('[V816] dlc download item=%s dlc=%r -> %r'
                  % (item_id, list(dlc_ids or ())[:3], out))
    except Exception as _e:
        out.append('guard=%r' % (_e,))
    return out


# v8.20: THE DLC STAGGER QUEUE. The v8.19 device log showed the
# hall-entry storm: every forced skin fired its AutoDownloadItem
# in the same frame (items 41100010, 141199002, 6040000500,
# 221100008, ...) and the downloads fought for the same threads -
# that is the "small lag on FIRST lobby entry" and a growing
# chunk of the match-entry stall (49.89s v8.16 -> 73.71s v8.19).
# One worker, one item at a time, 0.45s apart, deduped by the
# existing dlc2_tried set. A ~10-item burst now spreads
# over ~4.5s of background time instead of one frozen frame.
dlc_queue = []
dlc_lock = threading.Lock()
dlc_worker_started = [False]
DLC_SPACING = 0.45


# v10.12.2-lagfix-r1: in a MATCH the only job this queue exists for is
# making an injected item's assets resident, and the game loads whatever
# weapon the player actually holds on its own.  Firing AutoDownloadItem
# between ticks while the player is picking a gun up only competes for the
# same resource requests - the r1 log shows it firing on every single
# pickup ('dlc queue item=550040055 waited=0.41s ... AutoDownloadItem ok',
# then 5100390134, 510010117, 5100380147 - one per weapon swap).  Drop the
# job instead of queueing it there; the lobby path (where resource
# availability actually decides whether a list/preview renders) is unchanged.
def dlc_match_skip(item_id):
    # v2.103: NEVER skip.  The 'game owns weapon resource load
    # in-match' assumption is disproven by the round-120 log: the
    # UZI skin item 5100140206 was match-skipped here, the game
    # never fetched the unowned skin's resources, and every later
    # case rebuild blocked the game thread 28-65s on the synchronous
    # resource load ('[STALL] game thread blocked 65.51s' after each
    # equip=72 Modify/loadout InitWeapon).  The staggered worker
    # queue keeps the download gentle; a background fetch beats a
    # frozen game thread.
    return False


def dlc_worker():
    while True:
        try:
            time.sleep(DLC_SPACING)
            with dlc_lock:
                if not dlc_queue:
                    _job = None
                else:
                    _job = dlc_queue.pop(0)
            if _job is None:
                continue
            _item, _dlcs, _queued_at = _job
            _waited = time.time() - _queued_at
            try:
                _res = dlc_download_now(_item, _dlcs)
            except Exception:
                _res = ['worker-guard']
            with dlc_lock:
                _depth = len(dlc_queue)
            _plog('[V820] dlc queue item=%s waited=%.2fs '
                  'depth=%d res=%r'
                  % (_item, _waited, _depth, _res[:2]))
        except Exception:
            time.sleep(1.0)


def dlc_enqueue(item_id, dlc_ids, front=False):
    try:
        with dlc_lock:
            _job3 = (item_id, list(dlc_ids or ()),
                     time.time())
            if front:
                dlc_queue.insert(0, _job3)
            else:
                dlc_queue.append(_job3)
            _depth = len(dlc_queue)
        if not dlc_worker_started[0]:
            dlc_worker_started[0] = True
            threading.Thread(target=dlc_worker,
                             daemon=True).start()
        return _depth
    except Exception:
        return -1


def try_dlc_download(item_id, dlc_ids=None, front=False):
    """v8.20: the entry point - dedupes exactly like v8.16 did
    (the dlc2_tried set), then hands the item to the
    staggered background queue instead of downloading inline.
    The download still happens, just not all at once."""
    try:
        item_id = _safe_int(item_id, 0)
        if not item_id:
            return []
        # v2.110: the download gate - melee anywhere, striker in
        # the LOBBY only (the saved suits must prefetch before a
        # match or the FPS-arms build blocks 80+s on the fetch -
        # the two 83s stalls in round-127), NEVER guns/other (the
        # in-match gun downloads churned the queue and every gun
        # pickup stuttered - the user's rule: the download-cloud
        # is for melees, 'keep it melee sided, not guns too').
        # Unknown rows (the subtype enum still loading) are
        # blocked inside the gun-skin lobby-id range so a lazy
        # catalog can never leak a gun fetch.
        try:
            _cat2110 = (globals().get('_v109_category')
                        or (lambda _x: None))(item_id)
            if _cat2110 == 'striker':
                _him2110 = globals().get('_hero_in_match')
                if callable(_him2110) and _him2110():
                    return ['melee-only']
            elif _cat2110 != 'melee':
                if _cat2110 == 'weapon':
                    # v2.111: gun-skin resources fetch OUTSIDE a match
                    # only (lobby loadout preview / vault pick / login
                    # prefetch).  In-match fetches were the pickup lag;
                    # banning them entirely made the gun model builds
                    # stall 28-62s on the game's own fetch instead.
                    _him2111 = globals().get('_hero_in_match')
                    if callable(_him2111) and _him2111():
                        return ['melee-only']
                elif _cat2110 in ('emote', 'collection',
                        'consumable', 'profile', 'other'):
                        # v2.112: anim/companion bundles (the first-kill
                        # freeze) fetch anywhere - small and one-shot.
                        # The other cosmetic families fetch outside matches
                        # only (same rule as guns).
                        if _cat2110 != 'emote':
                            _him2112 = globals().get('_hero_in_match')
                            if callable(_him2112) and _him2112():
                                return ['melee-only']
                elif _cat2110 is not None:
                    return ['melee-only']
                elif 510000000 <= item_id <= 559999999:
                    return ['melee-only']
        except Exception:
            pass
        key = (item_id, tuple(dlc_ids or ()))
        if key in dlc2_tried:
            return []
        if dlc_match_skip(item_id):
            dlc2_tried.add(key)
            return ['match-skip']
        dlc2_tried.add(key)
        _depth = dlc_enqueue(item_id, dlc_ids,
                                    front=front)
        if _depth >= 0:
            _plog('[V820] dlc queued item=%s depth=%d'
                  % (item_id, _depth))
            return ['queued']
        # queue broken - fall back to the inline download
        return dlc_download_now(item_id, dlc_ids)
    except Exception:
        return []


def dlc_preflight(item_id, template_id, dlc_ids=None):
    """True = proceed with the model build.  False = the item's DLC
    bundles are explicitly missing: the download request is out and
    the caller must skip this build (the loader would block the game
    thread on the fetch).  Every unknown state proceeds (fail-open).
    """
    try:
        mgr = None
        try:
            _gm = globals().get('dlcmgr')
            mgr = _gm() if callable(_gm) else None
        except Exception:
            mgr = None
        check = getattr(mgr, 'CheckDlcExists', None)
        if not callable(check):
            return True
        ids = []
        try:
            ids.extend([d for d in (dlc_ids or ()) if d])
        except Exception:
            pass
        if not ids and template_id:
            try:
                _srg = globals().get('skin_raw_get')
                if callable(_srg):
                    ids.extend([d for d in (_srg(template_id,
                                                 'dlc_ids') or ())
                                if d])
            except Exception:
                pass
        init = getattr(mgr, 'InitGuiseDlcId', None)
        if callable(init) and template_id:
            try:
                _d = init(template_id)
                if _d:
                    ids.append(_d)
            except Exception:
                pass
        if not ids:
            return True
        for _d in ids:
            try:
                if not check(_d):
                    try:
                        _dl = globals().get('try_dlc_download')
                        if callable(_dl) and item_id:
                            _dl(item_id, [])
                    except Exception:
                        pass
                    return False
            except Exception:
                return True
        return True
    except Exception:
        return True


ARMED = set()


def server_arm(owner, hero_id, item_id):
    """v2.109: fire the game's own ArmHeroSkin verb so the SERVER
    records the equip (other players render the server state).
    Direct and instrumented - the v7-era _avatar_try_equip chain
    logged zero memos on device (round-126) so its gates stayed
    dark.  Off the game frame, deduped per (avatar, hero, item),
    every attempt logged as [SVR-ARM]."""
    # v2.111: ArmHeroSkin is a LOCAL setter (the friend-side
    # verdict is proven: every call returned None and nothing
    # changed for the friend).  The calls still re-arm the hero
    # and rebuild the weapon cases - debug-10 saw 73 of them and
    # the melee visual repair fought every rebuild ("state never
    # settles" -> the melee went invisible).  Never call this.
    return None
    try:
        hero_id = _safe_int(hero_id, 0)
        item_id = _safe_int(item_id, 0)
        if not hero_id or not item_id or owner is None:
            return
        key = (id(owner), hero_id, item_id)
        if key in ARMED:
            return
        ARMED.add(key)
    except Exception:
        return

    def _run():
        try:
            time.sleep(0.5)
            arm = getattr(owner, 'ArmHeroSkin', None)
            if not callable(arm):
                _plog('[SVR-ARM] ArmHeroSkin missing on %s'
                      % type(owner).__name__)
                return
            for _shape, _args, _kw in (
                    ('(hero_id, item_id)', (hero_id, item_id), {}),
                    ('(item_id=)', (), {'skin_item_id': item_id}),
                    ('(item_id,)', (item_id,), {}),
                    ('(item_id, 0)', (item_id, 0), {})):
                try:
                    rr = arm(*_args, **_kw)
                    _plog('[SVR-ARM] ArmHeroSkin%s -> %r [shape %s]'
                          % (_shape, rr, _shape))
                    return
                except TypeError:
                    continue
                except Exception as _ae:
                    _plog('[SVR-ARM] ArmHeroSkin%s err %r'
                          % (_shape, _ae))
                    return
            _plog('[SVR-ARM] no shape fit hero=%s item=%s'
                  % (hero_id, item_id))
        except Exception as _e:
            _plog('[SVR-ARM] guarded %r' % (_e,))
    try:
        threading.Thread(target=_run, daemon=True).start()
    except Exception:
        pass


def try_dlc_call(dlc_id):
    """Guarded best-effort per-item download: the module-level
    DownloadContent entry point, else a download-named method on
    the manager singleton. Everything is wrapped and reported; the
    probe above tells the next log whether the shape was right."""
    tries = []
    _fn_ok = False
    try:
        _mod = sys.modules.get(
            'gclient.framework.util.downloader')
        if _mod is not None:
            _fn = getattr(_mod, 'DownloadContent', None)
            if callable(_fn) and not isinstance(_fn, type):
                _nreq = 1
                try:
                    _sig = inspect.signature(_fn)
                    _nreq = len([
                        p for p in _sig.parameters.values()
                        if p.default is inspect.Parameter.empty
                        and p.kind in (
                            inspect.Parameter.POSITIONAL_ONLY,
                            inspect.Parameter.POSITIONAL_OR_KEYWORD)])
                except Exception:
                    pass
                if _nreq <= 1:
                    try:
                        if _nreq == 0:
                            _fn()
                        else:
                            _fn(dlc_id)
                        tries.append('DownloadContent ok')
                        _fn_ok = True
                    except Exception as _e:
                        tries.append('DownloadContent=%r' % (_e,))
            _mgr = getattr(_mod, 'DownloadableContentManager',
                           None)
            if isinstance(_mgr, type) and not _fn_ok:
                _inst = None
                for _acc in ('instance', 'Instance',
                             'GetInstance', 'GetInstancePtr'):
                    try:
                        _f = getattr(_mgr, _acc, None)
                        if callable(_f):
                            _cand = _f()
                            if _cand is not None:
                                _inst = _cand
                                tries.append('inst via %s' % (_acc,))
                                break
                    except Exception:
                        continue
                if _inst is None:
                    try:
                        _sing = getattr(_mod, 'Singleton', None)
                        if callable(_sing) \
                                and not isinstance(_sing, type):
                            _cand = _sing()
                            if _cand is not None:
                                _inst = _cand
                                tries.append('inst via Singleton()')
                    except Exception:
                        pass
                if _inst is not None:
                    for _mname in sorted(dir(_inst)):
                        if _mname.startswith('_') \
                                or 'download' not in _mname.lower():
                            continue
                        _mf = getattr(_inst, _mname, None)
                        if not callable(_mf):
                            continue
                        _nreq2 = 1
                        _npar2 = 1
                        try:
                            _sig2 = inspect.signature(_mf)
                            _params2 = [
                                p for p in _sig2.parameters.values()
                                if p.kind in (
                                    inspect.Parameter.POSITIONAL_ONLY,
                                    inspect.Parameter.
                                    POSITIONAL_OR_KEYWORD)]
                            _npar2 = len(_params2)
                            _nreq2 = len([
                                p for p in _params2
                                if p.default is
                                inspect.Parameter.empty])
                        except Exception:
                            pass
                        if _nreq2 > 1 or _npar2 > 2:
                            continue
                        try:
                            _mf(dlc_id)
                            tries.append('%s(%s) ok'
                                          % (_mname, dlc_id))
                        except Exception as _e:
                            tries.append('%s=%r' % (_mname, _e,))
                        break
    except Exception as _e:
        tries.append('guard=%r' % (_e,))
    if not tries:
        tries.append('no entry point found')
    return tries


def maybe_download_melee(equip_id, skin_id):
    """v8.15: best-effort per-item DLC download for a forced MELEE
    skin. The skin template row carries dlc_id / dlc_pack_ids (the
    v8.14 FXROW proved the fields exist). Only the ids the game
    itself associates with the skin are ever requested, each once,
    fully guarded and logged."""
    try:
        if not equip_id or not skin_id:
            return
        _melee_ids = globals().get('WEP_MELEE_IDS') or {}
        if equip_id not in _melee_ids:
            return
        _row = None
        for _mod_name in ('gclient.data.gun_skin_template_data',
                          'gclient.data.gun_skin_template_base_data'):
            _mod = sys.modules.get(_mod_name)
            if _mod is None:
                continue
            _row = _data_get(getattr(_mod, 'data', None),
                             skin_id, None)
            if _row is not None:
                break
        if _row is None:
            return
        _dlc_ids = []
        for _f in ('dlc_id', 'dlc_pack_ids'):
            _v = _proto_get(_row, _f, None)
            if _v is None:
                continue
            if isinstance(_v, (list, tuple)):
                _dlc_ids.extend(_safe_int(_x, 0) for _x in _v)
            else:
                _iv = _safe_int(_v, 0)
                if _iv:
                    _dlc_ids.append(_iv)
        _dlc_ids = [d for d in _dlc_ids if d]
        if not _dlc_ids:
            if ('nodlc', skin_id) not in dlc_tried:
                dlc_tried.add(('nodlc', skin_id))
                _plog('[V815] melee skin=%s carries no dlc ids on '
                      'its row' % (skin_id,))
            return
        dlc_api_probe()
        for _dlc in _dlc_ids[:3]:
            if ('dlc', _dlc) in dlc_tried:
                continue
            dlc_tried.add(('dlc', _dlc))
            _res = try_dlc_call(_dlc)
            _plog('[V815] melee dlc attempt skin=%s dlc=%s -> %r'
                  % (skin_id, _dlc, _res))
    except Exception:
        pass


# ============================================================
# v8.21: THE v7.30 WEAPON-SKIN RESTORE.
# Deleted here (owner directive, v8.20 log evidence): the v8.18
# melee guise retry (failed on MeleeCase.is_in_combat - the heal
# never ran on the retried case), the v8.18 profile-weapon apply
# wraps, and the v8.20 GetActualSkinItemId "resolver" (WRONG
# METHOD: the v8.20 log proved it resolves the HERO skin - zero
# overrides all session; the v8.17 showroom wrap already owns it
# for hero skins). The apply core below is the original v7.30R26
# body, verbatim.


profile_painted = {}
# v8.21: (timestamp, [ctrl objects]) - filled by _striker_live_dolls'
# single walk, consumed by profile_paint so a paint pass pays
# for ONE gc walk instead of two.
ctrl_stash = [(0.0, [])]
# v8.22: live-object REGISTRIES. The v8.21 device log showed every
# paint pass paying 2-3 FULL gc walks (~300k objects each, 2.3-9.6 s
# per pass, the retry burst re-running them every 3 s) just to
# rediscover the same few dolls/controllers. The registers are filled
# for free by the hooks that already touch these objects (weapon
# adds, shows, model owners); the gc walk stays as the cold-start
# fallback when a register is empty.
_striker_doll_reg = []      # weakrefs: live Doll-family objects
ctrl_reg = []         # weakrefs: HeroSelectModelCtrl /
                            # PersonalHomepageModelCtrl
# v8.22 walk markers: a register warmed this scene is authoritative
# (no walk); an EMPTY register re-walks on the retry cadence but at
# most once per 5 s (the v8.21 log: retry bursts re-walked ~300k
# objects every 3 s while nothing was live yet); a scene change
# re-walks once so the new scene's un-noted objects are caught.
_striker_doll_walk_at = [0.0]
_striker_doll_walk_scene = [None]
ctrl_walk_scene = [None]


def _reg_live(reg, bound=64):
    """Live objects from a weakref register; dead refs pruned."""
    out = []
    dead = []
    try:
        for w in reg:
            try:
                o = w() if callable(w) else w
            except Exception:
                o = None
            if o is None:
                dead.append(w)
            else:
                out.append(o)
        for w in dead:
            try:
                reg.remove(w)
            except Exception:
                pass
    except Exception:
        pass
    return out[:bound]


def _striker_doll_note(obj):
    """v8.22: remember a live Doll-family object (deduped, capped)."""
    try:
        if obj is None:
            return
        if type(obj).__name__ not in ('Doll', 'DollLike',
                                      'CalculationDoll',
                                      'BigHeadCalculationDoll'):
            return
        for w in _striker_doll_reg:
            try:
                if w() is obj:
                    return
            except Exception:
                pass
        import weakref as _wr
        _striker_doll_reg.append(_wr.ref(obj))
        if len(_striker_doll_reg) > 64:
            del _striker_doll_reg[:-64]
    except Exception:
        pass


def ctrl_note(obj):
    """v8.22: remember a live profile controller (deduped, capped).
    v8.34: the one-shot-paint trigger now fires for EVERY weapon
    build through a known ctrl too - the game REUSES the ctrl object
    when the profile page reopens, so the v8.33 first-note-only
    trigger went silent after the first open."""
    try:
        if obj is None:
            return
        if type(obj).__name__ not in ('HeroSelectModelCtrl',
                                      'PersonalHomepageModelCtrl'):
            return
        _known834 = False
        for w in ctrl_reg:
            try:
                if w() is obj:
                    _known834 = True
                    break
            except Exception:
                pass
        if not _known834:
            import weakref as _wr
            ctrl_reg.append(_wr.ref(obj))
            if len(ctrl_reg) > 32:
                del ctrl_reg[:-32]
        # v8.33: a NEW controller coming alive IS the profile page
        # opening (or the showroom) - the game builds its weapon via
        # AddWeaponByEquipId and that call is what noted this object.
        # The paint passes had NO trigger on profile-open, so the
        # profile always showed the default striker. Schedule the
        # one-shot paint exactly like the game's Load hook does
        # (deferred thread - never paint on the game thread, v8.06).
        try:
            if (not dispatch_pending[0]
                    and not paint_once_active[0]
                    and sync_attrs.get('bHeroSkinHack', False)):
                dispatch_pending[0] = True
                _herofx_note(
                    'v8-dispatch',
                    '[V8] ctrl alive -> one-shot paint scheduled')

                def _defer_ctrl(_src='ctrl-alive'):
                    try:
                        time.sleep(0.35)
                        _rfn = globals().get('_striker_lobby_refresh')
                        if callable(_rfn):
                            _rfn(_src)
                    except Exception:
                        pass
                    finally:
                        dispatch_pending[0] = False
                threading.Thread(target=_defer_ctrl,
                                 daemon=True).start()
        except Exception:
            pass
    except Exception:
        pass


def display_objects(bound=8):
    """v8.29: profile controllers come from the shared one-sweep
    collector; the separate walk was one of the three lobby stalls."""
    try:
        _h, _d, ctrls = _striker_collect_scene_objects()
        if ctrls:
            return ctrls[:bound]
    except Exception:
        pass
    return _reg_live(ctrl_reg, bound)


def profile_paint():
    """v8.20: the PROFILE page striker. The personal-homepage model
    controller is a HeroSelectModelCtrl with the SAME
    ShowHeroSkinModel channel the lobby doll paint drives - it was
    simply never in the paint walk. Paint it exactly like a doll
    (sticky, throttled, bounded to 2 per pass)."""
    n = 0
    try:
        gf = globals().get('_get_forced_skin_proto')
        if not callable(gf):
            return 0
        if not (sync_attrs.get('bHeroSkinHack', False)):
            return 0
        _show = globals().get('_striker_show_on_doll')
        if not callable(_show):
            return 0
        # v8.22: REGISTER first (the showroom weapon hooks note the
        # controllers exactly when they are alive and displaying),
        # the v8.21 stash from the doll walk rides along when fresh,
        # and ONE bounded walk per scene entry catches controllers
        # our hooks never touched (cold start / pre-injection) - the
        # retry burst NEVER walks.
        _objs = []
        try:
            _skey = _scene_at[0]
        except Exception:
            _skey = None
        try:
            _objs = list(_reg_live(ctrl_reg))
        except Exception:
            _objs = []
        try:
            _ts, _st = ctrl_stash[0]
            if time.time() - _ts < 2.0:
                for _c in _st:
                    ctrl_note(_c)
        except Exception:
            pass
        if ctrl_walk_scene[0] != _skey:
            ctrl_walk_scene[0] = _skey
            # v8.23: a FRESH NON-EMPTY stash means the doll walk just
            # ran and found the controllers - skip this scene-entry
            # walk (a fresh-but-EMPTY stash still walks: nothing was
            # found and the ctrls may predate our hooks).
            _stash_ok = False
            try:
                _ts2, _st2 = ctrl_stash[0]
                if time.time() - _ts2 < 2.0 and _st2:
                    _stash_ok = True
            except Exception:
                pass
            if not _stash_ok:
                try:
                    for _c in display_objects():
                        ctrl_note(_c)
                    _objs = list(_reg_live(ctrl_reg)) or _objs
                except Exception:
                    pass
        if not _objs:
            try:
                _ts, _st = ctrl_stash[0]
                if time.time() - _ts < 2.0:
                    _objs = list(_st)
            except Exception:
                _objs = []
        for obj in _objs:
            if type(obj).__name__ not in ('HeroSelectModelCtrl',
                                          'PersonalHomepageModelCtrl'):
                continue
            try:
                ctrl_note(obj)
            except Exception:
                pass
            key = id(obj)
            if profile_painted.get(key) \
                    == (_hero_apply_sig[0], paint_hero[0]):
                continue
            try:
                hid = obj.GetHeroId()
            except Exception:
                hid = None
            if not hid:
                hid = globals().get('_hero_id_deep')(obj) \
                    if callable(globals().get('_hero_id_deep')) \
                    else None
            # v8.34: the profile ctrl carries NO hero id of its own -
            # the profile page shows the CURRENT striker by definition
            # (the v8.33 log: homepage ctrl noted + weapon built, but
            # hid=None -> proto=None -> never painted).
            if not hid:
                hid = paint_hero[0] or None
            # v8.34: PersonalHomepageModelCtrl has no ShowModel of its
            # own - resolve the doll/model it drives (one attribute
            # level, bounded) and paint THAT.
            _tgt = obj
            try:
                if not callable(getattr(obj, 'ShowHeroSkinModel', None)) \
                        and not callable(getattr(obj, 'ShowDisplayModel',
                                                 None)):
                    for _an, _av in list(vars(obj).items())[:12]:
                        try:
                            if callable(getattr(_av, 'ShowHeroSkinModel',
                                                None)) \
                                    or callable(getattr(
                                        _av, 'ShowDisplayModel', None)):
                                _tgt = _av
                                _herofx_note(
                                    'v834-profile',
                                    '[V834] profile target via ctrl '
                                    'attr %r' % (_an,))
                                break
                        except Exception:
                            continue
            except Exception:
                pass
            proto = gf(hid) if hid else None
            if proto and _show(_tgt, proto, sticky=True):
                profile_painted[key] = \
                    (_hero_apply_sig[0], paint_hero[0])
                n += 1
                if n >= 2:
                    break
        if len(profile_painted) > 32:
            try:
                profile_painted.clear()
            except Exception:
                pass
    except Exception:
        pass
    return n


def _apply_weapon_case_skin_core(case, equip_id, forced_skin, reason='apply', force=False):
    apply_t0 = time.time()
    if case is None or not forced_skin or not sync_attrs.get('bSkinHack', False):
        return False
    equip_id = _safe_int(equip_id, 0)
    if not equip_id:
        try:
            equip_id = _safe_int(getattr(case, 'equip_id', 0) or getattr(case, 'weapon_id', 0), 0)
        except Exception:
            equip_id = 0
    apply_key = (id(case), equip_id, forced_skin)
    if not force and _weaponfx_applied.get(id(case)) == (equip_id, forced_skin):
        return True

    skin_info = WEP_SKIN_INFO.get(forced_skin) or {}
    item_id = SKIN_TO_ITEM.get(forced_skin) or skin_info.get('lobby_item_id') or forced_skin
    # v2.109: the v2.107 preflight skip is gone - with downloads
    # melee-only it would block gun skins forever (missing bundles
    # that are never fetched).  The game's own loader fetches on
    # demand as it always did.
    optic_id = _resolve_skin_optic_id(equip_id, forced_skin, item_id, case)
    called = []
    errors = []

    # Distinct ID namespaces: template/guise template vs lobby item.
    for attr_name, attr_val in (
        ('_selected_skin_id', forced_skin),
        ('_treacky_skin_template_id', forced_skin),
        ('_treacky_skin_item_id', item_id),
        ('skin_id', forced_skin),
        ('guise_id', forced_skin),
        ('guise_template_id', forced_skin),
        ('skin_template_id', forced_skin),
        ('guise_item_id', item_id),
        ('skin_item_id', item_id),
        ('skin_optic_id', optic_id),
        ('show_guise_bullet_trace', True),
        ('show_guise_hit_effect', True),
        ('show_hit_effect', True),
        ('upgrade_level', 10),
    ):
        _set_case_attr(case, attr_name, attr_val)

    # Mirror every captured effect-like template field onto the case.
    # Ballistic/hit code reads several of these from the active case.
    try:
        for _key, _value in (skin_info.get('raw_effect_fields') or {}).items():
            _set_case_attr(case, str(_key), _value)
        for _key in (
            'effect_id', 'effect_path', 'optic_b_fx', 'optic_b_fx_path',
            'kill_mat', 'team_kill_mat', 'kill_mat_start_time',
            'team_kill_mat_start_time', 'kill_team_extra_model_id',
            'kill_team_extra_hexie_model_id', 'kill_tip_icon_replace',
            'fps_tracer_bullet_id', 'fps_adstracer_bullet_id',
            'tps_tracer_bullet_id', 'fps_simple_tracer_bullet_id',
            'extra_ballistic_tracer_bullet_id',
        ):
            if skin_info.get(_key) is not None:
                _set_case_attr(case, _key, skin_info.get(_key))
    except Exception:
        pass

    _call_case_method(case, 'ClearGuiseItemCache', called=called, errors=errors)

    # Real WeaponCase signature from device diag:
    # ChangeWeaponSkin(skin_id, data_changed=True, force_refresh=False).
    # v2.6 left force_refresh=False, so tracer/scope/hit data stayed on
    # the previously created case. Force the refresh explicitly.
    _change_skin_done = False
    try:
        _change_fn = getattr(case, 'ChangeWeaponSkin', None)
        if callable(_change_fn):
            try:
                _params = inspect.signature(_change_fn).parameters
            except Exception:
                _params = {}
            if 'force_refresh' in _params:
                _change_skin_done = _call_case_method(
                    case, 'ChangeWeaponSkin', (forced_skin,),
                    {'data_changed': True, 'force_refresh': True}, called, errors)
            if not _change_skin_done:
                _change_skin_done = _call_case_method(case, 'ChangeWeaponSkin', (forced_skin,), called=called, errors=errors)
    except Exception:
        pass
    if not _change_skin_done:
        _call_case_method(case, 'ChangeWeaponSkin', (forced_skin, True), called=called, errors=errors)

    # Guise change: prefer the mapped lobby item for guise_item_id.
    if hasattr(case, 'ChangeWeaponGuise'):
        done = _call_case_method(
            case, 'ChangeWeaponGuise', (forced_skin,),
            {'guise_item_id': item_id}, called, errors)
        if not done:
            _call_case_method(case, 'ChangeWeaponGuise', (forced_skin,), called=called, errors=errors)

    if optic_id:
        for method_name in ('ChangeWeaponOpticReticle', 'ChangeOpticReticle', 'SetOpticReticle', 'RefreshOpticReticle'):
            if _call_case_method(case, method_name, (optic_id,), called=called, errors=errors):
                break

    # Real WeaponGuiseComponent / WeaponSkinComponent methods from the
    # game stubs, plus the legacy names as harmless fallbacks.
    _call_case_method(case, 'InitGuiseIllusion', called=called, errors=errors)
    if not _call_case_method(case, 'WeaponBodyIllusion', (True,), called=called, errors=errors):
        _call_case_method(case, 'WeaponBodyIllusion', (False,), called=called, errors=errors)
    _call_case_method(case, 'RefreshIllusionEffect', called=called, errors=errors)
    _call_case_method(case, 'ShowWeaponBodyEffectVisible', (True,), called=called, errors=errors)
    _call_case_method(case, 'ShowWeaponAdsSfxVisible', (True,), called=called, errors=errors)
    if not _call_case_method(case, 'LoadModelSkin', (forced_skin,), {'is_init': False, 'start_load': True}, called, errors):
        _call_case_method(case, 'LoadModelSkin', (forced_skin,), called=called, errors=errors)
    _call_case_method(case, 'RefreshModelSkin', called=called, errors=errors)
    _call_case_method(case, 'PostprocessPerformance', called=called, errors=errors)
    _call_case_method(case, 'PostprocessMeleePerformance', called=called, errors=errors)
    # Device diag: RefreshFireSfxId(guise_template_data, guise_item_id).
    try:
        _template_record = None
        _get_skin_data_fn = globals().get('_get_skin_data')
        if callable(_get_skin_data_fn):
            _template_record, _feature_record = _get_skin_data_fn(forced_skin)
        if _template_record is None:
            _gst_mod = _import_module('gclient.data.gun_skin_template_data')
            _template_record = _data_get(getattr(_gst_mod, 'data', None), forced_skin, None)
        if _template_record is not None:
            _call_case_method(case, 'RefreshFireSfxId', (_template_record, item_id), called=called, errors=errors)
    except Exception as _e:
        errors.append('RefreshFireSfxId(resolve)=%r' % (_e,))
    for method_name in (
        'RefreshGuiseEffect', 'RefreshGuise3PEffectInCombat',
        'RefreshRacerForChangeGuise',
        'RefreshFireSfxIdForGunPart', 'RefreshKillCounterForChangeGuise',
    ):
        _call_case_method(case, method_name, called=called, errors=errors)

    _weaponfx_applied[id(case)] = (equip_id, forced_skin)
    _weaponfx_log_once(
        ('apply', equip_id, forced_skin),
        '[WEAPONFX] apply ms=%.0f reason=%s equip=%s skin=%s item=%s optic=%r '
        'tracer=%r ads_tracer=%r kill_mat=%r raw_keys=%r called=%r errors=%r'
        % (1000.0 * (time.time() - apply_t0), reason, equip_id, forced_skin, item_id, optic_id,
           skin_info.get('fps_tracer_bullet_id'),
           skin_info.get('fps_adstracer_bullet_id'),
           skin_info.get('kill_mat'),
           sorted((skin_info.get('raw_effect_fields') or {}).keys())[:24],
           called, errors[:6]))
    return True


# ---- v4.7 gate instrumentation (behaviour-preserving) -------------------
# The v4.2 body above stays byte-identical on purpose: this wrapper only
# reports WHY it is about to bail, then delegates unchanged.


def _weaponfx_skip(reason, equip_id=None, forced_skin=None):
    # A silent False here is why "nothing happens" was impossible to see in
    # the field: the whole apply chain (ChangeWeaponSkin, ChangeWeaponGuise,
    # LoadModelSkin, illusion refresh, optic reticle) is skipped before it
    # starts. Log each distinct reason once so the next log names it.
    _key = (reason, str(equip_id), str(forced_skin))
    if _key in _weaponfx_skip_seen:
        return
    _weaponfx_skip_seen.add(_key)
    _plog('[WEAPONFX] SKIP reason=%s equip=%r skin=%r bSkinHack=%r bForceFX=%r'
          % (reason, equip_id, forced_skin,
             sync_attrs.get('bSkinHack'), sync_attrs.get('bForceFX')))


_weaponfx_skip_seen = set()


# ============================================================
# v6.8: KEEP THE GUN SKIN ON THE WEAPON
# ============================================================
# The equip path only writes the skin onto the WeaponCase object that exists at
# that moment. Leave the vault and the game builds new cases from the server's
# real loadout, so the skin and the camo vanished - exactly what you saw.
# Every case we touch is remembered (weakref) and the pump re-forces it when the
# game rebuilt it. The marker _treacky_skin_template_id is the tell: if it is
# gone or different, this case is new and has to be pushed again.
_weaponfx_cases = []
_weaponfx_enforce_at = [0.0]
_weaponfx_enforce_stat = {'applied': 0, 'cases': 0, 'last': None}

# Reference1 Modify repair: compare against what the authentic case actually
# contained after our apply, not a guessed list of fields that must all differ.
# Snapshots are weak-keyed by the remembered case identity, bounded, and read
# only by the existing lobby-only enforce pass (once per 2.5 seconds).
_weaponfx_identity_snapshots = {}
_WEAPONFX_IDENTITY_FIELDS = (
    'skin_id', 'guise_id', 'skin_template_id', 'guise_template_id',
    'skin_item_id', 'guise_item_id', '_selected_skin_id', 'skin_optic_id',
)


def _weaponfx_identity_value(case, name):
    try:
        raw = getattr(case, name, None)
    except Exception:
        return None
    if raw is None or isinstance(raw, (bool, int, float, str)):
        return raw
    try:
        return repr(raw)[:96]
    except Exception:
        return '<unrepresentable>'


def _weaponfx_capture_identity(case, forced):
    try:
        if case is None or not forced:
            return
        values = []
        for name in _WEAPONFX_IDENTITY_FIELDS:
            value = _weaponfx_identity_value(case, name)
            if value is not None:
                values.append((name, value))
        if not values:
            return
        if len(_weaponfx_identity_snapshots) >= 64:
            for key in list(_weaponfx_identity_snapshots)[:16]:
                _weaponfx_identity_snapshots.pop(key, None)
        _weaponfx_identity_snapshots[id(case)] = (
            weakref.ref(case), forced, tuple(values))
    except Exception:
        pass


def _weaponfx_lobby_snapshot_drift(case, forced):
    try:
        entry = _weaponfx_identity_snapshots.get(id(case))
        if not entry:
            return ()
        ref, snapshot_forced, values = entry
        if ref() is not case or snapshot_forced != forced:
            return ()
        drift = []
        for name, before in values:
            after = _weaponfx_identity_value(case, name)
            if after != before:
                drift.append('%s:%r>%r' % (name, before, after))
        return tuple(drift)
    except Exception:
        return ()


def _weaponfx_remember(case, wid=0):
    """Keep (weakref, wid) - the case itself does not always expose its wid."""
    try:
        if case is None:
            return
        wid = _safe_int(wid, 0) or _weapon_case_wid(case)
        for ref, w in _weaponfx_cases:
            if ref() is case:
                if wid and not w:
                    _weaponfx_cases[_weaponfx_cases.index((ref, w))] = (ref, wid)
                return
        _weaponfx_cases.append((weakref.ref(case), wid))
        del _weaponfx_cases[:-24]
    except Exception:
        pass


def _weapon_case_wid(case):
    for attr in ('equip_id', 'weapon_id', 'wid', 'gun_id'):
        try:
            v = getattr(case, attr, None)
            v = _safe_int(v, 0)
            if v:
                return v
        except Exception:
            continue
    return 0


def _weaponfx_forced_for(wid):
    try:
        if not sync_attrs.get('bSkinHack', False):
            return None
        return _get_forced_weapon_skin(wid)
    except Exception:
        pass
    return None


killnum_shield_state = {'done': False, 'count': 0}


def install_killnum_shield():
    # v2.124: the kill-counter refresh (RefreshKillCounterForChangeGuise)
    # can reach hand_model_extra_attach_comp.CheckKillNumModel -> ShowModel
    # before the kill-num extra-attach model exists; the game then dies on
    # "'NoneType' object has no attribute 'Hardpoint'" (levi_debug-2.txt:1066).
    # Shield CheckKillNumModel: the game's own _callComponents already treats
    # the error as absorbed, but faulthandler logs it as a real crash and the
    # model never attaches. Catch it here, log bounded, and let the next
    # model-ready pass re-run it.
    if killnum_shield_state['done']:
        return True
    mod = sys.modules.get(
        'gclient.gameplay.logic_base.models.hand_model_extra_attach_comp')
    if mod is None:
        try:
            mod = __import__(
                'gclient.gameplay.logic_base.models.hand_model_extra_attach_comp',
                globals(), locals(), ['x'], 0)
        except Exception:
            return False
    for _name24 in dir(mod):
        try:
            cls = getattr(mod, _name24)
        except Exception:
            continue
        if not isinstance(cls, type):
            continue
        prev = cls.__dict__.get('CheckKillNumModel')
        if not callable(prev) or getattr(prev, '_treacky_killnum24', False):
            continue

        def _make(_prev):
            def wrapper(self, *a, **k):
                try:
                    return _prev(self, *a, **k)
                except AttributeError:
                    killnum_shield_state['count'] += 1
                    if (killnum_shield_state['count'] == 1
                            or killnum_shield_state['count'] % 25 == 0):
                        _plog('[SHIELD] killnum CheckKillNumModel absorbed '
                              'AttributeError x%d (model not built yet)'
                              % killnum_shield_state['count'])
                    return None
            wrapper._treacky_killnum24 = True
            return wrapper

        try:
            setattr(cls, 'CheckKillNumModel', _make(prev))
            _plog('[SHIELD] killnum installed on %s.%s'
                  % (_name24, 'CheckKillNumModel'))
            killnum_shield_state['done'] = True
        except Exception:
            pass
    return killnum_shield_state['done']


# ---------------------------------------------------------------- weapon_case
# v6.9: the case objects the game builds on its own never reached our hooks, so
# the skin we wrote onto the old case was simply gone after leaving the vault.
# These wrap the case's OWN setters - whatever path the game uses to put a skin
# on a weapon ends in one of them, and the argument is rewritten to the one you
# picked. Additive: the original still runs, with our skin instead of theirs.
_weapon_case_hooked = []


def _install_weapon_case_hooks(verbose=True):
    mod = sys.modules.get('gclient.gameplay.logic_base.equips.weapon_case')
    if mod is None:
        try:
            mod = __import__('gclient.gameplay.logic_base.equips.weapon_case',
                             globals(), locals(), ['x'], 0)
        except Exception as e:
            if verbose:
                _plog('[WEAPONFX] weapon_case import failed: %r' % (e,))
            return []
    done = []
    for cls_name in ('WeaponCase', 'WeaponCaseBase'):
        cls = getattr(mod, cls_name, None)
        if not isinstance(cls, type):
            continue
        for meth in ('ChangeWeaponSkin', 'ChangeWeaponGuise', 'LoadModelSkin',
                     'ChangeWeaponSkinId', 'InitGuiseIllusion'):
            prev = cls.__dict__.get(meth)
            if not callable(prev) or getattr(prev, '_treacky_case', False):
                if prev is not None and getattr(prev, '_treacky_case', False):
                    done.append('%s.%s' % (cls_name, meth))
                continue

            def _make(_prev, _label):
                def wrapper(self, *a, **k):
                    try:
                        wid = _weapon_case_wid(self)
                        forced = _weaponfx_forced_for(wid)
                        if forced and a and isinstance(a[0], int):
                            if _safe_int(a[0], 0) != forced:
                                a = (forced,) + tuple(a[1:])
                                _weapon_note('%s forced' % _label)
                            _weaponfx_remember(self, wid)
                    except Exception:
                        pass
                    return _prev(self, *a, **k)
                wrapper._treacky_case = True
                return wrapper
            try:
                setattr(cls, meth, _make(prev, '%s.%s' % (cls_name, meth)))
                done.append('%s.%s' % (cls_name, meth))
            except Exception:
                continue
    if verbose and done:
        _plog('[WEAPONFX] weapon_case hooks %r' % (done,))
    _weapon_case_hooked[:] = done
    return done


_weapon_notes = set()


def _weapon_note(msg):
    if msg in _weapon_notes:
        return
    _weapon_notes.add(msg)
    _plog('[WEAPONFX] %s' % (msg,))


try:
    _install_weapon_case_hooks()
except Exception as _wch_err:
    _plog('[WEAPONFX] weapon_case hooks failed: %r' % (_wch_err,))


# v8.26: Zelewin's optic lead - WeaponBody.GetSkinOpticIdByOpticItemId.
# PROBE ONLY: log the first calls (args + the game's own return) so the
# next log shows the optic id space. No substitution yet.
_optic_probe_seen = {}
_optic_probe_found = [False]


def _install_weaponbody_optic_probe():
    if not _V841PERF_AUTO_DIAGNOSTICS:
        return []
    if _optic_probe_found[0]:
        return []
    found = []
    try:
        for _mn, _mod in list(sys.modules.items()):
            if _mod is None or not _mn.startswith(('gclient.', 'gshare.')):
                continue
            try:
                _clses = [c for c in vars(_mod).values()
                          if isinstance(c, type) and c.__name__ == 'WeaponBody']
            except Exception:
                continue
            for _cls in _clses:
                _f = vars(_cls).get('GetSkinOpticIdByOpticItemId')
                if _f is None or getattr(_f, '_treacky_obprobe', False):
                    continue

                def _make_ob(o, label):
                    def _w(self, *a, **k):
                        r = o(self, *a, **k)
                        try:
                            n = _optic_probe_seen.get(label, 0)
                            if n < 5:
                                _optic_probe_seen[label] = n + 1
                                _plog('[OPTIC-PROBE] %s a=%r -> %r'
                                      % (label, [repr(x)[:60] for x in a],
                                         repr(r)[:80]))
                        except Exception:
                            pass
                        return r
                    _w._treacky_obprobe = True
                    return _w

                _lbl = '%s.WeaponBody' % _mn
                setattr(_cls, 'GetSkinOpticIdByOpticItemId',
                        _make_ob(_f, _lbl))
                found.append(_lbl)
    except Exception as _e:
        _plog('[OPTIC-PROBE] install failed: %r' % (_e,))
    if found:
        _optic_probe_found[0] = True
        _plog('[OPTIC-PROBE] WeaponBody probed: %r' % (found,))
    return found


try:
    _install_weaponbody_optic_probe()
except Exception as _obp_err:
    _plog('[OPTIC-PROBE] boot failed: %r' % (_obp_err,))
try:
    _obp_timer = threading.Timer(30.0, _install_weaponbody_optic_probe)
    _obp_timer.daemon = True
    _obp_timer.start()
except Exception:
    pass


def _weaponfx_lobby_identity_reset(case, forced):
    """Detect a lobby/Modify reset hidden by our still-valid marker.

    The attachment preview can rewrite the real skin fields without clearing
    _treacky_skin_template_id.  Return True only when at least one authentic
    identity field is readable and every readable identity differs from the
    selected template.  Missing/unreadable fields preserve the old skip.
    """
    try:
        if getattr(case, '_treacky_skin_template_id', None) != forced:
            return False
        seen = False
        for name in ('skin_id', 'guise_id', 'skin_template_id',
                     'guise_template_id'):
            raw = getattr(case, name, None)
            if raw is None:
                continue
            seen = True
            if _safe_int(raw, 0) == _safe_int(forced, 0):
                return False
        return seen
    except Exception:
        return False


def _weaponfx_enforce(reason='pump'):
    """Re-apply the chosen skin to every live case the game rebuilt."""
    now = time.time()
    # PERF: the old code ran the racer module/class scan and scene detection
    # BEFORE this throttle, so a per-frame pump repeated them every frame.
    if now - _weaponfx_enforce_at[0] < 2.5:
        return 0
    _weaponfx_enforce_at[0] = now
    # v8.10: lazy racer shield retry, now at the intended 2.5 s cadence.
    try:
        install_racer_shield()
    except Exception:
        pass
    try:
        install_killnum_shield()
    except Exception:
        pass
    # v7.30R20: match-entry blackout. The R19 device log shows the game
    # thread blocked 14-33 s at every match entry with the pump firing
    # on the first tick after the block - re-applying weapon-case fields
    # while the map is still loading both adds work to the load window
    # and races half-built cases. Let the scene settle for 8 s first;
    # after that ONE pass puts the skin back (the "apply once" the user
    # asked for), and the scan itself drops to one per 2.5 s.
    # Pairicon6: reuse this ONE scene query for the lobby-only deeper check.
    # In-match shooting/pickup keeps the established marker-only fast path.
    check_lobby_identity = False
    try:
        in_match = bool(_hero_in_match())
        check_lobby_identity = not in_match
        if in_match and now - _scene_at[0] < 12.0:
            return 0
    except Exception:
        # Unknown scene state fails closed for the new deeper check only.
        check_lobby_identity = False
    # v2.125: shoot-lag fix - the pump re-ran the whole skin pipeline on
    # every rebuilt case (kills/shot churn rebuild cases). At most one
    # enforce pass per 2s for pump reasons; equip reasons stay instant.
    if reason == 'pump':
        _pass25 = _weaponfx_enforce_stat.get('pass_at', 0.0)
        if now - _pass25 < 2.0:
            return 0
    _weaponfx_enforce_stat['pass_at'] = now
    applied = 0
    live = 0
    # v2.124: budget the re-apply work per pass. Each _apply_weapon_case_skin
    # runs the full native skin pipeline (11+ refresh calls); several rebuilt
    # cases in one tick is exactly the shoot-lag signature. At most 3 applies
    # per pass; the remainder resumes on the next pump (~0.5s later).
    budget24 = 3
    carried24 = 0
    for item in list(_weaponfx_cases):
        try:
            ref, stored_wid = item
        except Exception:
            ref, stored_wid = item, 0
        try:
            case = ref()
        except Exception:
            case = None
        if case is None:
            try:
                _weaponfx_cases.remove(item)
            except Exception:
                pass
            continue
        live += 1
        wid = stored_wid or _weapon_case_wid(case)
        forced = _weaponfx_forced_for(wid)
        if not forced:
            continue
        try:
            have = getattr(case, '_treacky_skin_template_id', None)
        except Exception:
            have = None
        if have == forced:
            drift = (_weaponfx_lobby_snapshot_drift(case, forced)
                     if check_lobby_identity else ())
            lobby_reset = (check_lobby_identity and
                           (bool(drift) or
                            _weaponfx_lobby_identity_reset(case, forced)))
            if not lobby_reset:
                continue
            _weaponfx_log_once(
                ('lobby-identity-reset', wid, forced, drift),
                '[WEAPONFX] lobby identity reset wid=%s skin=%s drift=%s; '
                'forcing Modify repair' % (wid, forced, repr(drift)))
        if budget24 <= 0:
            carried24 += 1
            continue
        try:
            _apply_weapon_case_skin(case, wid, forced, 'enforce:%s' % reason, force=True)
            applied += 1
            budget24 -= 1
        except Exception as e:
            _plog('[WEAPONFX] enforce error wid=%d %r' % (wid, e))
    if carried24:
        # Resume the remaining cases on the next pump tick instead of this
        # one: release both throttles so the continuation runs ~0.5s later.
        _weaponfx_enforce_at[0] = now - 2.1
        _weaponfx_enforce_stat['pass_at'] = now - 1.55
        _weaponfx_enforce_stat['carried'] = carried24
    if applied:
        _weaponfx_enforce_stat['applied'] += applied
        _weaponfx_enforce_stat['last'] = reason
        _plog('[WEAPONFX] re-applied the skin to %d rebuilt case(s) (%s)'
              % (applied, reason))
    _weaponfx_enforce_stat['cases'] = live
    return applied


def _apply_weapon_case_skin(case, equip_id, forced_skin, reason='apply', force=False):
    # v6.8: keep a handle on every case we force, so the pump can put the skin
    # back when the game rebuilds the weapon (leaving the vault). This lives in
    # the wrapper, never in _apply_weapon_case_skin_core - that block is the
    # vendored weapon pipeline and must stay byte identical.
    _weaponfx_remember(case, equip_id)
    skip = False
    if case is None:
        _weaponfx_skip('case is None', equip_id, forced_skin); skip = True
    elif not forced_skin:
        _weaponfx_skip('no skin selected for this weapon', equip_id, forced_skin); skip = True
    elif not sync_attrs.get('bSkinHack', False):
        _weaponfx_skip('bSkinHack is OFF', equip_id, forced_skin); skip = True
    # v5.0 WEAPON FX - no separate toggle. Same gate and same
    # unconditional style as the kill-animation fix:
    #   seed the skin row BEFORE the core applies it,
    #   mirror onto the case AFTER the case exists.
    if not skip:
        # v8.21: these used to live inside the v8.x core; the core is
        # the restored v7.30R26 body now, so the side utilities moved
        # here - the mat-list heal (v8.15, LoadModelSkin reads those
        # fields) and the per-item DLC prefetch (v8.16, gun + melee -
        # goes through the staggered queue since v8.20).
        try:
            heal_skin_row(forced_skin)
        except Exception:
            pass
        try:
            _item16 = SKIN_TO_ITEM.get(forced_skin) \
                or (WEP_SKIN_INFO.get(forced_skin) or {}).get(
                    'lobby_item_id') or forced_skin
            _dlc16 = []
            for _mod16 in ('gclient.data.gun_skin_template_data',
                           'gclient.data.gun_skin_template_base_data'):
                _m16 = sys.modules.get(_mod16)
                if _m16 is None:
                    continue
                _row16 = _data_get(getattr(_m16, 'data', None),
                                   forced_skin, None)
                if _row16 is not None:
                    for _f16 in ('dlc_id', 'dlc_pack_ids'):
                        _v16 = _proto_get(_row16, _f16, None)
                        if _v16 is None:
                            continue
                        if isinstance(_v16, (list, tuple)):
                            _dlc16.extend(_safe_int(_x, 0)
                                          for _x in _v16)
                        else:
                            _iv16 = _safe_int(_v16, 0)
                            if _iv16:
                                _dlc16.append(_iv16)
                    break
            try_dlc_download(_item16, [d for d in _dlc16 if d])
        except Exception:
            pass
        try:
            _fx_seed_row(forced_skin)
        except Exception as e:
            _plog('[FX] seed error=%r' % (e,))
        # BEFORE: the core calls ChangeWeaponSkin / ChangeWeaponGuise /
        # RefreshFireSfxId / RefreshGuiseEffect, and those read the case
        # fields. Mirroring only afterwards meant the game's own refresh
        # ran with the old (empty) values and cached them.
        try:
            _fx_mirror_case(case, forced_skin)
        except Exception as e:
            _plog('[FX] pre-mirror error=%r' % (e,))
    result = _apply_weapon_case_skin_core(case, equip_id, forced_skin, reason, force)
    if not skip:
        # AFTER: whatever the refresh chain clobbered goes straight back.
        try:
            _fx_mirror_case(case, forced_skin)
        except Exception as e:
            _plog('[FX] mirror error=%r' % (e,))
        try:
            _fx_remember_state(case, forced_skin)
        except Exception:
            pass
        if result:
            _weaponfx_capture_identity(case, forced_skin)
    # v7.25: the Skins-tab scope picker is gone ("Forget abt it") -
    # the skin's OWN optic still rides the core, untouched.
    return result

def _current_weapon_cases(ca):
    cases = []
    def _add(value):
        if value is not None and not any(value is old for old in cases):
            cases.append(value)
    if ca is None:
        return cases
    weapon = None
    guid = None
    try:
        weapon = ca.GetCurWeapon()
        guid = getattr(weapon, 'guid', None)
    except Exception:
        pass
    if guid and hasattr(ca, 'GetWeaponCase'):
        for is_fps in (True, False):
            try:
                _add(ca.GetWeaponCase(guid, is_fps_weapon=is_fps))
            except TypeError:
                try:
                    _add(ca.GetWeaponCase(guid, is_fps))
                except Exception:
                    pass
            except Exception:
                pass
        if not cases:
            try:
                _add(ca.GetWeaponCase(guid))
            except Exception:
                pass
    for method_name in ('GetCurWeaponCase', 'GetCurrentWeaponCase'):
        fn = getattr(ca, method_name, None)
        if callable(fn):
            for is_fps in (True, False):
                try:
                    _add(fn(is_fps_weapon=is_fps))
                except TypeError:
                    try:
                        _add(fn(is_fps))
                    except Exception:
                        pass
                except Exception:
                    pass
    return cases


_weaponfx_current_signature = [None]



def _apply_current_weapon_skin_effects(reason='tick', force_check=False, force_apply=False):
    if not sync_attrs.get('bSkinHack', False):
        return False
    _weaponfx_tick[0] += 1
    if not force_check and (_weaponfx_tick[0] % 15) != 0:
        return False
    ca = None
    get_local = globals().get('_local_combat_avatar')
    if callable(get_local):
        try:
            ca = get_local()
        except Exception:
            ca = None
    if ca is None:
        try:
            sp = getattr(Space, '_instance', None)
            owner = getattr(sp, 'owner', None) if sp else None
            ca = getattr(owner, 'combat_avatar', None) if owner else None
        except Exception:
            ca = None
    if ca is None:
        return False
    try:
        weapon = ca.GetCurWeapon()
    except Exception:
        weapon = None
    equip_id = 0
    if weapon is not None:
        equip_id = _safe_int(getattr(weapon, 'equip_id', 0) or getattr(weapon, 'weapon_id', 0), 0)
    if not equip_id:
        return False
    forced = _get_forced_weapon_skin(equip_id)
    if not forced:
        _weaponfx_current_signature[0] = None
        return False
    weapon_guid = getattr(weapon, 'guid', None)
    signature = (id(ca), str(weapon_guid), equip_id, forced, bool(sync_attrs.get('bSkinHack', False)))
    if not force_apply and signature == _weaponfx_current_signature[0]:
        # v5.1: do NOT trust the signature alone. The game re-creates the
        # weapon case and re-runs its refresh chain, which wipes the fields
        # we mirrored. v5.0 returned True here forever after the first
        # apply, so a wipe was never corrected - the "works, stops, works
        # again" flicker. Now the signature only skips the work while the
        # fields are still in place.
        if _fx_state_is_healthy(forced):
            return True
        # Re-apply the whole chain, but never faster than every 2 s.
        try:
            _now = time.time()
            if (_now - _fx_last_force[0]) < 2.0:
                return True
            _fx_last_force[0] = _now
        except Exception:
            pass
        force_apply = True
    applied = False
    for case in _current_weapon_cases(ca):
        applied = _apply_weapon_case_skin(case, equip_id, forced, reason, force=force_apply) or applied
    if applied:
        _weaponfx_current_signature[0] = signature
    return applied

def _selected_skin_for_caster(caster):
    try:
        get_local = globals().get('_local_combat_avatar')
        local = get_local() if callable(get_local) else None
        if local is not None and caster is not None:
            if caster is not local:
                local_id = getattr(local, 'id', None)
                caster_id = getattr(caster, 'id', None)
                if local_id is None or caster_id != local_id:
                    return 0
        ca = local or caster
        weapon = ca.GetCurWeapon() if ca is not None else None
        equip_id = _safe_int(
            getattr(weapon, 'equip_id', 0) or getattr(weapon, 'weapon_id', 0), 0) if weapon else 0
        return _get_forced_weapon_skin(equip_id) or 0
    except Exception:
        return 0

def _selected_hit_effect_id(skin_id, material_type=None):
    info = WEP_SKIN_INFO.get(skin_id) or {}
    for key in (
        # Real gun_skin_template_data field exposed by FXROW-REAL on device.
        # Log 9 proves this is normally a material -> effect mapping, not a
        # scalar.  Select the actual hit material; never int() the dictionary.
        'skin_hit_object_effect_id',
        'hit_effect_id', 'hit_fx_id', 'skin_hit_effect_id',
        'extra_effect_id', 'hit_effect', 'hit_fx',
    ):
        value = _skin_raw_field(info, key)
        entries = _data_items(value) if key == 'skin_hit_object_effect_id' else []
        # Log 10 proves the real map reaches the live case while the reduced
        # WEP_SKIN_INFO/raw mirror can still omit it.  Read the SAME selected
        # skin's authentic row as the already-proven mirror does.  No donor,
        # global scan, fabricated value, or other skin namespace is involved.
        if ((key == 'skin_hit_object_effect_id' and not entries)
                or (key != 'skin_hit_object_effect_id' and value is None)):
            for module_name in FX_SOURCE_MODULES:
                row = _fx_row(module_name, skin_id)
                if row is None:
                    continue
                row_value = _proto_get(row, key, None)
                if key == 'skin_hit_object_effect_id':
                    row_entries = _data_items(row_value)
                    if row_entries:
                        value, entries = row_value, row_entries
                        break
                elif row_value is not None:
                    value = row_value
                    break
        if key == 'skin_hit_object_effect_id':
            if entries:
                wanted = (_safe_int(material_type, None)
                          if material_type is not None else None)
                default_1001 = None
                default_0 = None
                for raw_material, raw_effect in entries:
                    material = _safe_int(raw_material, None)
                    effect = _safe_int(raw_effect, 0)
                    if wanted is not None and material == wanted:
                        # An authentic zero also wins: it means no effect for
                        # this material, not permission to use another row.
                        return effect
                    if material == 1001:
                        default_1001 = effect
                    elif material == 0:
                        default_0 = effect
                if default_1001 is not None:
                    return default_1001
                if default_0 is not None:
                    return default_0
                # No authentic material/default entry: retain legacy fallback.
                continue
        ivalue = _safe_int(value, 0)
        if ivalue:
            return ivalue
    return 0

# ============================================================
# v5.3: tracer targeting
# ============================================================
# The dump of gshare.effect_util.PlayBallisticEffect is stubbed, so the way
# it reaches the tracer cannot be read out of the file - only its constant
# table is intact, and that says 'weapon_case' comes first and the
# fps_/tps_/extra_ tracer ids are read after it. Two shots (v5.1, v5.2) of
# writing to a single guessed location were not enough, so instead of
# guessing again we now write to EVERY plausible carrier and log the shape
# of the object once, so the next log ends the guessing.
_FX_CASE_KEYS = ('weapon_case', 'weaponCase', 'case', 'equip_case', 'equipCase')


def _fx_looks_like_case(obj):
    """A weapon case is anything that carries a skin id or tracer fields."""
    if obj is None or isinstance(obj, (str, bytes, int, float, bool, dict, list, tuple)):
        return False
    cls_name = obj.__class__.__name__.lower()
    if 'case' in cls_name or 'weapon' in cls_name or 'skin' in cls_name:
        return True
    for attr in ('skin_id', 'cur_skin_id', 'guise_id', 'fps_tracer_bullet_id',
                 'change_weapon_skin', 'ChangeWeaponSkin'):
        try:
            if getattr(obj, attr, None) is not None:
                return True
        except Exception:
            continue
    return False


def _fx_find_cases(root, depth=0, seen=None, out=None):
    """Collect every object inside the effect that could be the weapon case."""
    if out is None:
        out = []
    if seen is None:
        seen = set()
    if root is None or depth > 2 or id(root) in seen:
        return out
    seen.add(id(root))
    if _fx_looks_like_case(root):
        out.append(root)
    for getter in ('items',):
        try:
            if hasattr(root, getter):
                for k, v in list(root.items()):
                    if isinstance(k, str) and k in _FX_CASE_KEYS and v is not None:
                        out.append(v)
                    _fx_find_cases(v, depth + 1, seen, out)
                return out
        except Exception:
            pass
    try:
        for attr in ('weapon_case', 'weaponCase', 'case', 'equip_case'):
            v = getattr(root, attr, None)
            if v is not None:
                out.append(v)
    except Exception:
        pass
    return out


def _fx_dump_effect_once(skin_id, ballistic_effect, key, tracer):
    """One structured dump per skin: tells us exactly what the game handed
    the effect player, and where our value landed."""
    if (not _V841PERF_AUTO_DIAGNOSTICS
            or ('fx-shape', skin_id) in _weaponfx_logged):
        return
    try:
        shape = {}
        for k in _mapping_keys(ballistic_effect)[:24]:
            try:
                v = _mapping_get(ballistic_effect, k, None)
            except Exception:
                v = None
            shape[k] = type(v).__name__
        cases = _fx_find_cases(ballistic_effect)
        case_info = []
        for c in cases[:3]:
            try:
                attrs = [a for a in dir(c) if 'tracer' in a.lower() or 'skin' in a.lower()][:8]
            except Exception:
                attrs = []
            case_info.append('%s tracer_now=%r' % (c.__class__.__name__, _mapping_get(c, key, None)))
        _weaponfx_log_once(
            ('fx-shape', skin_id),
            '[FX] effect shape skin=%s key=%s tracer=%r keys=%r cases=%r'
            % (skin_id, key, tracer, shape, case_info))
    except Exception as e:
        _plog('[FX] shape dump error=%r' % (e,))


def _install_effect_util_hooks():
    if _weaponfx_effect_hooks_installed[0]:
        return True
    _weaponfx_effect_hook_attempts[0] += 1
    attempt = _weaponfx_effect_hook_attempts[0]
    try:
        effect_util = _import_module('gshare.effect_util')
    except Exception as e:
        if attempt == 1 or attempt % 20 == 0:
            _plog('[WEAPONFX] effect_util import deferred attempt=%d error=%r' % (attempt, e))
        return False

    originals = {}
    for name in ('PlayBallisticEffect', 'WrapperHitEffectResult', 'PlayHitEffect', 'ConfigBallisticEffect'):
        fn = getattr(effect_util, name, None)
        if callable(fn) and not getattr(fn, '_treacky_weaponfx', False):
            originals[name] = fn
    if not originals:
        _weaponfx_effect_hooks_installed[0] = True
        return True

    def _inject_selected_tracer(caster, ballistic_effect, simple_version=False, ads_override=None):
        skin_id = _selected_skin_for_caster(caster)
        if not skin_id or not sync_attrs.get('bSkinHack', False):
            return 0
        info = WEP_SKIN_INFO.get(skin_id) or {}
        is_ads = (bool(ads_override) if ads_override is not None else
                  bool(getattr(caster, 'is_ads', False) or
                       getattr(caster, 'is_real_ads', False)))
        if simple_version:
            key = 'fps_simple_adstracer_bullet_id' if is_ads else 'fps_simple_tracer_bullet_id'
        else:
            key = 'fps_adstracer_bullet_id' if is_ads else 'fps_tracer_bullet_id'
        tracer = info.get(key) or _skin_raw_field(info, key)
        if not tracer:
            # Keep the ADS family when a simple ADS row is absent.  The
            # old non-ADS-first fallback silently drew the wrong tracer.
            if is_ads:
                fallbacks = ('fps_adstracer_bullet_id',
                             'fps_tracer_bullet_id',
                             'extra_ballistic_tracer_bullet_id',
                             'tps_tracer_bullet_id')
            else:
                fallbacks = ('fps_tracer_bullet_id',
                             'fps_adstracer_bullet_id',
                             'extra_ballistic_tracer_bullet_id',
                             'tps_tracer_bullet_id')
            for fallback in fallbacks:
                tracer = info.get(fallback) or _skin_raw_field(info, fallback)
                if tracer:
                    break
        _case_count = 0
        _case_values = []
        if tracer and ballistic_effect is not None:
            _mapping_set(ballistic_effect, key, tracer)
            _mapping_set(ballistic_effect, 'skin_effect_id', tracer)
            if _mapping_get(ballistic_effect, 'effect_id', None) is not None:
                _mapping_set(ballistic_effect, 'effect_id', tracer)
            # ------------------------------------------------------------
            # v5.1 THE TRACER FIX.
            #
            # gshare.effect_util.PlayBallisticEffect resolves the tracer
            # from the WEAPON CASE carried inside the effect dict, not from
            # the dict itself - its constants start with 'weapon_case' and
            # then 'fps_tracer_bullet_id' / 'fps_adstracer_bullet_id' /
            # 'fps_simple_*' / 'extra_ballistic_tracer_bullet_id'. v5.0
            # (and the original) only wrote the top-level dict, so the shot
            # still had no tracer to draw.
            # ------------------------------------------------------------
            try:
                _cases = _fx_find_cases(ballistic_effect)
                if not _cases:
                    # Device-shaped PlayBallisticEffect dictionaries can
                    # contain no weapon_case.  Use the real current case
                    # instead of assuming the host-test shape.
                    _case_owner = caster
                    if _case_owner is None:
                        try:
                            _get_local = globals().get('_local_combat_avatar')
                            _case_owner = (_get_local()
                                           if callable(_get_local) else None)
                        except Exception:
                            _case_owner = None
                    try:
                        _weapon = (_case_owner.GetCurWeapon()
                                   if _case_owner is not None else None)
                        _guid = getattr(_weapon, 'guid', None)
                        if _guid and hasattr(_case_owner, 'GetWeaponCase'):
                            _one_case = _case_owner.GetWeaponCase(_guid)
                            if _one_case is not None:
                                _cases.append(_one_case)
                    except Exception:
                        pass
                    if not _cases:
                        _cases = _current_weapon_cases(_case_owner)
                _case_count = len(_cases)
                for _wc in _cases:
                    _mapping_set(_wc, key, tracer)
                    for _alt in ('fps_tracer_bullet_id', 'fps_adstracer_bullet_id',
                                 'fps_simple_tracer_bullet_id',
                                 'fps_simple_adstracer_bullet_id',
                                 'extra_ballistic_tracer_bullet_id'):
                        _val = info.get(_alt) or _skin_raw_field(info, _alt)
                        if _val:
                            _mapping_set(_wc, _alt, _val)
                    _mapping_set(_wc, 'show_guise_bullet_trace', True)
                _case_values = [_mapping_get(_wc, key, None)
                                for _wc in _cases[:3]]
                _fx_dump_effect_once(skin_id, ballistic_effect, key, tracer)
            except Exception as _wc_err:
                _weaponfx_log_once(('ballistic-wc-err', repr(_wc_err)),
                                   '[FX] weapon_case tracer error=%r' % (_wc_err,))
        if ('ballistic', skin_id, key) not in _weaponfx_logged:
            _weaponfx_log_once(
                ('ballistic', skin_id, key),
                '[WEAPONFX] ballistic inject skin=%s simple=%r ads=%s key=%s tracer=%r effect_keys=%r cases=%d case_values=%r'
                % (skin_id, simple_version, is_ads, key, tracer,
                   _mapping_keys(ballistic_effect), _case_count, _case_values))
        return tracer or 0

    ballistic_slow = [0]

    def PlayBallisticEffect(caster, spell_id, ballistic_effect, simple_version, *args, **kwargs):
        _bt0 = time.time()
        try:
            _inject_selected_tracer(caster, ballistic_effect, simple_version)
        except Exception as e:
            _weaponfx_log_once(('ballistic-error', repr(e)), '[WEAPONFX] ballistic hook error=%r' % (e,))
        try:
            _bdt = time.time() - _bt0
            if _bdt > 0.05 and ballistic_slow[0] < 5:
                ballistic_slow[0] += 1
                _plog('[V826] PlayBallisticEffect took %.0f ms (#%d)'
                      % (_bdt * 1000.0, ballistic_slow[0]))
        except Exception:
            pass
        return originals['PlayBallisticEffect'](caster, spell_id, ballistic_effect, simple_version, *args, **kwargs)

    def WrapperHitEffectResult(target, hit_pos, hit_normal, hit_material_type, hit_dir, caster, weapon_id, effect_id=0, extra_effect_id=None, heirloom_color=None, *args, **kwargs):
        try:
            skin_id = _selected_skin_for_caster(caster)
            if skin_id and sync_attrs.get('bSkinHack', False):
                hit_id = _selected_hit_effect_id(skin_id, hit_material_type)
                if hit_id and not extra_effect_id:
                    extra_effect_id = hit_id
                _weaponfx_log_once(
                    ('hitwrap', skin_id, _safe_int(hit_material_type, -1)),
                    '[WEAPONFX] hit wrapper skin=%s weapon=%r material=%r '
                    'hit_id=%r effect=%r extra=%r'
                    % (skin_id, weapon_id, hit_material_type, hit_id,
                       effect_id, extra_effect_id))
        except Exception as e:
            _weaponfx_log_once(('hitwrap-error', repr(e)), '[WEAPONFX] hit wrapper error=%r' % (e,))
        return originals['WrapperHitEffectResult'](
            target, hit_pos, hit_normal, hit_material_type, hit_dir, caster,
            weapon_id, effect_id, extra_effect_id, heirloom_color, *args, **kwargs)

    def PlayHitEffect(caster, spell_id, hit_effect, is_immune=False, heirloom_color=None, *args, **kwargs):
        try:
            skin_id = _selected_skin_for_caster(caster)
            if skin_id and sync_attrs.get('bSkinHack', False):
                material_type = _mapping_get(hit_effect, 'hit_material_type', None)
                hit_id = _selected_hit_effect_id(skin_id, material_type)
                if hit_id:
                    if not _mapping_get(hit_effect, 'hit_effect_id', None):
                        _mapping_set(hit_effect, 'hit_effect_id', hit_id)
                    _mapping_set(hit_effect, 'show_hit_effect', True)
                _weaponfx_log_once(
                    ('playhit', skin_id, _safe_int(material_type, -1)),
                    '[WEAPONFX] PlayHitEffect skin=%s material=%r hit_id=%r '
                    'hit_keys=%r'
                    % (skin_id, material_type, hit_id, _mapping_keys(hit_effect)))
        except Exception as e:
            _weaponfx_log_once(('playhit-error', repr(e)), '[WEAPONFX] PlayHitEffect hook error=%r' % (e,))
        return originals['PlayHitEffect'](caster, spell_id, hit_effect, is_immune, heirloom_color, *args, **kwargs)

    def ConfigBallisticEffect(ballistic_effect_id, is_ads, bullet_speed, hit_dis, *args, **kwargs):
        try:
            if sync_attrs.get('bSkinHack', False):
                caster = None
                frame = inspect.currentframe()
                try:
                    caller = frame.f_back if frame is not None else None
                    locals_map = caller.f_locals if caller is not None else {}
                    caster = locals_map.get('caster') or locals_map.get('self')
                    _weaponfx_log_once(
                        'config-ballistic-first',
                        '[WEAPONFX] ConfigBallisticEffect first id=%r ads=%r caller=%s locals=%r'
                        % (ballistic_effect_id, is_ads,
                           caller.f_code.co_name if caller is not None else '?',
                           [k for k in list(locals_map.keys())[:24]]))
                finally:
                    del frame
                skin_id = _selected_skin_for_caster(caster)
                if skin_id:
                    info = WEP_SKIN_INFO.get(skin_id) or {}
                    key = 'fps_adstracer_bullet_id' if is_ads else 'fps_tracer_bullet_id'
                    tracer = info.get(key) or _skin_raw_field(info, key) or info.get('fps_tracer_bullet_id')
                    if tracer:
                        _weaponfx_log_once(
                            ('config-ballistic', skin_id, key),
                            '[WEAPONFX] ConfigBallisticEffect replace skin=%s %r -> %r ads=%s'
                            % (skin_id, ballistic_effect_id, tracer, is_ads))
                        ballistic_effect_id = tracer
        except Exception as e:
            _weaponfx_log_once(('config-ballistic-error', repr(e)), '[WEAPONFX] ConfigBallisticEffect hook error=%r' % (e,))
        _cfg_result = originals['ConfigBallisticEffect'](
            ballistic_effect_id, is_ads, bullet_speed, hit_dis, *args, **kwargs)
        # v5.3 addition (the v4.2 id swap above is untouched): that swap only
        # reaches effects the game builds from the id. Whatever dict it does
        # build is what PlayBallisticEffect receives, so paint that too.
        try:
            if sync_attrs.get('bSkinHack', False) and isinstance(_cfg_result, dict):
                # ConfigBallisticEffect has an ADS argument but no simple
                # argument.  Preserve those as separate states; the old
                # `not is_ads` call mixed them and lost ADS with no caster.
                _inject_selected_tracer(None, _cfg_result, False, is_ads)
        except Exception as _ce:
            _weaponfx_log_once(('cfg-err', repr(_ce)), '[FX] config inject error=%r' % (_ce,))
        return _cfg_result

    wrappers = {
        'PlayBallisticEffect': PlayBallisticEffect,
        'ConfigBallisticEffect': ConfigBallisticEffect,
        'WrapperHitEffectResult': WrapperHitEffectResult,
        'PlayHitEffect': PlayHitEffect,
    }
    patched_modules = []
    for name, original in originals.items():
        wrapper = wrappers[name]
        wrapper._treacky_weaponfx = True
        try:
            setattr(effect_util, '_treacky_orig_' + name, original)
            setattr(effect_util, name, wrapper)
            patched_modules.append('gshare.effect_util.' + name)
        except Exception:
            pass
        # Callers that did `from gshare.effect_util import X` keep their
        # own module-global reference; patch identical references too.
        try:
            for mod_name, mod in list(sys.modules.items()):
                if mod is None or mod is effect_util:
                    continue
                _mod_lower = str(mod_name).lower()
                if not any(token in _mod_lower for token in ('combat', 'effect', 'spell', 'weapon')):
                    continue
                try:
                    if getattr(mod, name, None) is original:
                        setattr(mod, name, wrapper)
                        patched_modules.append(str(mod_name) + '.' + name)
                except Exception:
                    pass
        except Exception:
            pass

    _weaponfx_effect_hooks_installed[0] = True
    _plog('[WEAPONFX] effect_util hooks installed attempt=%d patched=%r' % (attempt, patched_modules[:16]))
    return True


_skinsel = {}

def _load_skinsel():
    global _skinsel
    _skinsel = {}
    for key, value in sync_attrs.items():
        if key.startswith('iSkin_'):
            equip_id = key.replace('iSkin_', '')
            if value > 0:
                _skinsel[str(equip_id)] = value

def _pick_wep_skin(equip_id):
    try:
        _load_skinsel()
        sel = _skinsel.get(str(int(equip_id)))
        if sel:
            return sel
        return None
    except:
        return None



# #======================================================================
# //  EQUIP.PY
# //
# //  This file is for: EQUIP PLUMBING: the forced-skin resolver (get_forced_skin rebind STAYS LAST), the equip nonces, the equip signature probes.
# //
# //  Part of the split TREACKY BS payload (v2.112).  The runtime
# //  file payload/skins_payload.py is GENERATED: run
# //  tools/build_payload.py after editing these modules.
# #======================================================================
