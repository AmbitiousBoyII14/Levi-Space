# ============================================================
# DISPLAY.PY (payload feature module)
# PROVIDES: _hero_forced_pick, _hero_live_objects, _striker_call_log, _striker_scene_gate, _install_striker_scene_wraps, _striker_scene_watcher, _striker_native_combat_owned, _herofx_note, _install_striker_effects_class, _install_striker_effects, _striker_effects_watcher, _install_hsp_force, _install_ghsp_class, _install_arm_force, ... +43 more | _HEROFX_SPECS, _ARM_SPECS, _MDL_SPECS, _MDL_FIELDS, BODY_SPECS, LOADER_SPECS, HALL_SPECS
# REQUIRES: shared namespace (config/names/main/game_api/catalog);
#           game modules imported inline, verified against the dumps.
# Feature module - see REWRITE_PLAN.md S1.
# ============================================================
"""Hero display chain: hero_skin_proto resolution, HallShowModel/Doll load wraps, twin-dissolve cosmetics (v2.124), display-sync drop snapshots."""

# #======================================================================
# //  DISPLAY.PY
# //
# //  This file is for: DISPLAY: the hero pick, the hand models / FPS arms (OnReloadHandModel, AddHandPrimitives), the ZLSKIN arm-clothes, the hall/combat dolls.
# //
# //  Part of the split TREACKY BS payload (v2.112).  The runtime
# //  file payload/skins_payload.py is GENERATED: run
# //  tools/build_payload.py after editing these modules.
# #======================================================================
def _hero_forced_pick():
    """True when at least one hero has a striker index selected."""
    try:
        for hid in list(HERO.keys()):
            if _safe_int(sync_attrs.get('iHeroSkin_%d' % hid, 0), 0) > 0:
                return True
    except Exception:
        pass
    return False


# counters the IDS dump prints; with the BSB block nothing increments
# them (it has no read instrumentation) - they stay at zero, honestly.
_hero_stats2 = {'desc_reads': 0, 'desc_forced': 0,
                'arm_reads': 0, 'arm_forced': 0,
                'proto_reads': 0, 'proto_forced': 0}

_fx_seed_logged = {}     # weapon-FX seed log counter per skin id (shared)

_hero_gc_cache = {'at': 0.0, 'objs': []}


def _hero_live_objects():
    """Live dolls/models, found by a bounded heap walk.

    The v7.30 block recorded these for free from its descriptor hooks;
    the ORIGINAL BSB block has no instrumentation, so this scans the
    heap instead - throttled to one walk per 5 s (the v6.1 lesson: an
    unthrottled gc walk blocked the game thread ~1 s). Consumers: the
    emote replay (which adds its own gc pass on top), the IDS dump,
    the menu Equip nudge and the apply loop's change detector."""
    import gc as _gc
    now = time.time()
    if now - _hero_gc_cache['at'] < 5.0:
        return list(_hero_gc_cache['objs'])
    out = []
    seen = set()
    try:
        for obj in _gc.get_objects():
            t = type(obj)
            if t in seen:
                continue
            seen.add(t)
            if _hero_kind(obj) is None:
                continue
            out.append(obj)
    except Exception:
        pass
    _hero_gc_cache['at'] = now
    _hero_gc_cache['objs'] = out
    return list(out)


# ============================================================
# v7.30R19: STRIKER PER-SCENE BUTTONS + "show in lobby"
# ============================================================
# The BSB block above stays byte-verbatim. The scene buttons work
# through the _SyncAttrsDict: every hook of the original block asks
# sync_attrs for 'bHeroSkinHack' before forcing, and the answer now
# depends on the scene:
#   Striker (lobby)  - hall shows/loads (the default state)
#   Striker (emote)  - while an emote plays and ~10 s after (the
#                      Clear/Cue re-assert window)
#   Striker (match)  - in a match (also covers execution animations)
# All default ON = exactly the single original switch.
_striker_emote_until = [0.0]
_striker_hall_models = []          # weakrefs of live HallShowModel
_striker_last_refresh = [0.0]
# v7.30R20: proof counters. The R19 device log could not answer "did the
# game ever call Load/Reload/Clear/Cue after boot?" - the hall model is
# usually loaded BEFORE injection, which is exactly why the R19 refresh
# (registry-only) sat empty all session and the lobby skin never applied.
_striker_calls = {}
_striker_calls_logged = {}
# v7.30R20: refresh bookkeeping - retry until ONE model actually re-shows.
_striker_refresh_ok = [False]
_striker_refresh_tries = [0]
_striker_hall_entry_at = [0.0]
_striker_postshow_logged = [False]   # v7.30R22: post-show errors, once


def _striker_call_log(meth, obj):
    try:
        _striker_calls[meth] = _striker_calls.get(meth, 0) + 1
        n = _striker_calls[meth]
        if n <= 3:
            owner = getattr(obj, 'owner', None)
            hid = None
            try:
                hid = owner.GetHeroId() if hasattr(owner, 'GetHeroId') else None
            except Exception:
                hid = None
            _plog('[HERO-SCENE] game call HallShowModel.%s #%d hero=%r'
                  % (meth, n, hid))
    except Exception:
        pass


def _striker_scene_gate():
    """True when the striker hack may force in the CURRENT context."""
    try:
        if _hero_in_match():
            return bool(sync_attrs.get('bStrikerMatch', True))
    except Exception:
        pass
    try:
        if time.time() < _striker_emote_until[0]:
            return bool(sync_attrs.get('bStrikerEmote', True))
    except Exception:
        pass
    try:
        return bool(sync_attrs.get('bStrikerLobby', True))
    except Exception:
        pass
    return True


def _install_striker_scene_wraps():
    """Record live hall show models + emote cues. Call-through only - the
    forcing decision stays inside the ORIGINAL block (via the gated
    flag), these wraps only observe so we know WHO to re-show.
    v7.30R23: the wraps now cover BOTH show-model classes - the
    previewer/card models are HallShowModel, but the HOME LOBBY model
    is a HallDollShowModel (proven by the R22 device log's emote dump:
    live 'HallDollShowModel mod=gclient.gamesystem.entities.hall_doll'
    alongside the previewer's HallShowModel calls). R21/R22 only ever
    wrapped HallShowModel, so the home lobby model was never recorded,
    never data-forced and never repainted."""
    found = []
    try:
        import weakref
        _targets = []
        try:
            from gclient.gamesystem.models.hall_show_model import \
                HallShowModel as _HSM1
            _targets.append(_HSM1)
        except Exception:
            pass
        try:
            _hd = sys.modules.get('gclient.gamesystem.entities.hall_doll')
            if _hd is None:
                _hd = __import__(
                    'gclient.gamesystem.entities.hall_doll',
                    globals(), locals(), ['HallDollShowModel'], 0)
            _hdsm = getattr(_hd, 'HallDollShowModel', None)
            if isinstance(_hdsm, type):
                _targets.append(_hdsm)
        except Exception:
            pass
        for _HSM in _targets:
            _pfx = getattr(_HSM, '__name__', 'HallShowModel')
            for meth in ('Load', 'Reload', 'ClearHeroSkinInfo',
                         'CueChangeHeroSkin'):
                prev = _HSM.__dict__.get(meth)
                if not callable(prev) or getattr(prev, '_treacky_ssg',
                                                 False):
                    continue

                def _wrap(_prev, _m):
                    def wrapper(self, *a, **k):
                        try:
                            _game_mark_thread()
                            _game_pump()
                        except Exception:
                            pass
                        try:
                            _striker_call_log(_m, self)
                            if _m in ('ClearHeroSkinInfo',
                                      'CueChangeHeroSkin'):
                                try:
                                    _striker_native_intro_cancelled(self)
                                except Exception:
                                    pass
                                # v8.06: in the hall the emote model is
                                # being torn down - open only a SHORT
                                # no-paint window so the skin returns
                                # quickly, and re-arm the one-shot so
                                # it actually does. In a match keep the
                                # classic 10s TPS window.
                                if _hero_in_match():
                                    _striker_emote_until[0] = \
                                        time.time() + 10.0
                                elif _m == 'CueChangeHeroSkin':
                                    # v8.18: only the game's own
                                    # skin-CHANGE cue re-arms the
                                    # active paint. A plain
                                    # ClearHeroSkinInfo is the game's
                                    # ordinary teardown/rebuild (2-3
                                    # per weapon change on the v8.17
                                    # log) - the rebuild reads the
                                    # forced state through the
                                    # wrapped getters on its own, and
                                    # re-arming here fought it:
                                    # apply, unapply, apply, unapply.
                                    _striker_emote_until[0] = 0.0
                                    _striker_invalidate_skin_caches(
                                        'teardown', targets=[self])
                                    paint_once_key[0] = None
                                    # v8.11: the re-paint that follows
                                    # the emote teardown must NOT
                                    # replay the entrance animation
                                    emote_rearm[0] = True
                                    # v8.14: ...and it must not be
                                    # delayed by the same-pick show
                                    # dedup either
                                    try:
                                        _striker_owner_last.clear()
                                        _striker_owner_sig.clear()
                                    except Exception:
                                        pass
                                    # re-arm the retry burst so the
                                    # apply loop actually re-paints
                                    try:
                                        _striker_refresh_tries[0] = 0
                                        _striker_refresh_ok[0] = False
                                    except Exception:
                                        pass
                                else:
                                    # v8.18/19: a plain hall Clear is
                                    # the game wiping the shown skin
                                    # (weapon change, scene churn) -
                                    # do NOT re-arm a paint burst (the
                                    # v8.17 apply/unapply fight), but
                                    # DO drop the per-doll "already
                                    # showing" bookkeeping: it is
                                    # stale now, and keeping it is how
                                    # v8.18 lost the skin entirely.
                                    # The next Load dispatch or retry
                                    # pass may re-show each doll once.
                                    _striker_emote_until[0] = 0.0
                                    _striker_invalidate_skin_caches(
                                        'teardown', targets=[self])
                                    try:
                                        _striker_owner_sig.clear()
                                    except Exception:
                                        pass
                            alive = [w for w in _striker_hall_models
                                     if w() is not None and w() is not self]
                            alive.append(weakref.ref(self))
                            del _striker_hall_models[:]
                            _striker_hall_models.extend(alive[:8])
                        except Exception:
                            pass
                        # v7.30R21: the R20 device log proved the current
                        # HallShowModel has NO ShowHeroSkinModel (the refresh
                        # found live models, hero ids resolved through
                        # owner.GetHeroId, yet showed=0 all session) - so the
                        # original block's own re-show after Clear/Cue no-ops
                        # on this game version. Belt and suspenders, all
                        # guarded so the game's call can never break:
                        #   1. observe the native Load/Reload bundle intact,
                        #   2. let the chain run (block wrapper + original),
                        #   3. show the complete pick on the OWNER DOLL after -
                        #      the doll's ShowHeroSkinModel is the channel
                        #      that actually repaints the lobby model.
                        try:
                            # Observe the native bundle, never rewrite only
                            # its model_id/id while leaving resource and
                            # additional-model paths stale.  The complete
                            # selected lobby row is shown after native Load.
                            if _m in ('Load', 'Reload'):
                                _owner0 = getattr(self, 'owner', None)
                                _hid0 = None
                                try:
                                    _hid0 = _owner0.GetHeroId() \
                                        if _owner0 is not None else None
                                except Exception:
                                    _hid0 = None
                                if not _hid0:
                                    _hid0 = _hero_id_deep(self)
                                if not _hid0 and a:
                                    _hid0 = _hero_proto_get(
                                        a[0], 'hero_id', None)
                                if _hid0:
                                    self._treacky_hero_hint = _hid0
                        except Exception:
                            pass
                        _res = None
                        try:
                            _res = _prev(self, *a, **k)
                        except Exception:
                            raise
                        try:
                            # v8.19: the v8.18 "trust the passive
                            # getters, mark the paint done" bet LOST
                            # on device - the home lobby doll does
                            # NOT get our skin from the game's own
                            # rebuild; the striker vanished from the
                            # lobby entirely. The v8.05 dispatch is
                            # back: the game just (re)built a hall
                            # model -> schedule the ONE-SHOT paint.
                            # The flicker protection is NOT here - it
                            # is the never-rule in _striker_show_on_
                            # doll: a doll object already showing the
                            # current (pick, hero) is skipped, so the
                            # repeated Load/Reload/Clear cycles of a
                            # weapon change cost at most ONE re-show
                            # per NEW doll object, with the intro
                            # suppressed and the weapon hold restored
                            # right after.
                            if _m in ('Load', 'Reload') \
                                    and not (sync_attrs.get(
                                        'bStrikerRepaint', False)
                                        or paint_once_active[0]):
                                # (once-path only: in R23 repaint mode
                                # the legacy post-call re-show already
                                # handles it - v8.02 semantics)
                                # v8.06: NEVER paint on the game thread
                                # - the v8.05 log stalled it up to 76s
                                # (the paint walk waits on model loads).
                                # Defer to a short-lived thread; the
                                # pending flag keeps one in flight.
                                try:
                                    if not dispatch_pending[0]:
                                        dispatch_pending[0] = True
                                        _herofx_note(
                                            'v8-dispatch',
                                            '[V8] game %s -> one-shot '
                                            'paint scheduled' % _m)

                                        def _defer(_src):
                                            try:
                                                time.sleep(0.15)
                                                _rfn = globals().get(
                                                    '_striker_lobby_refresh'
                                                )
                                                if callable(_rfn):
                                                    _rfn(_src)
                                            except Exception:
                                                pass
                                            finally:
                                                dispatch_pending[0] \
                                                    = False
                                        threading.Thread(
                                            target=_defer,
                                            args=('game-%s'
                                                  % _m.lower(),),
                                            daemon=True).start()
                                except Exception:
                                    pass
                            # v8.35: the v8.18 idle-pose nudge after
                            # the game's Load/Reload is REMOVED - the
                            # user report is explicit: the striker
                            # stands in the SKIN pose instead of holding
                            # the gun, and Zelewin's channel (game
                            # re-dress only, no pose calls) held the gun
                            # fine. The game restores its own hold.
                            _owner = getattr(self, 'owner', None)
                            if _owner is not None:
                                _gfp2 = globals().get(
                                    '_get_forced_skin_proto')
                                _ohid = None
                                try:
                                    _ohid = _owner.GetHeroId()
                                except Exception:
                                    _ohid = None
                                if not _ohid:
                                    # v7.30R23: the home lobby doll has no
                                    # GetHeroId - fall back to the model's
                                    # own hero (hint stashed at Load time).
                                    _ohid = _hero_id_deep(self)
                                if (_gfp2 is not None and callable(_gfp2)
                                        and _ohid):
                                    _oproto = _gfp2(_ohid)
                                    if _oproto is not None:
                                        # v7.30R22 (restored in v8.19):
                                        # re-show the pick on the OWNER
                                        # DOLL - on device this is the
                                        # channel that actually paints
                                        # the home lobby model (the
                                        # v8.18 removal is why the
                                        # striker left the lobby).
                                        # v8.19 makes it safe: the
                                        # never-rule in _striker_show_
                                        # on_doll skips a doll already
                                        # showing the current (pick,
                                        # hero), so this fires at most
                                        # once per NEW doll object.
                                        _striker_show_on_doll(_owner,
                                                              _oproto)
                        except Exception as _re:
                            try:
                                if not _striker_postshow_logged[0]:
                                    _striker_postshow_logged[0] = True
                                    _plog('[HERO-SCENE] post-show error '
                                          '(logged once) %r' % (_re,))
                            except Exception:
                                pass
                        return _res
                    wrapper._treacky_ssg = True
                    return wrapper

                setattr(_HSM, meth, _wrap(prev, meth))
                found.append('%s.%s' % (_pfx, meth))
    except Exception:
        pass
    # real emote cues from the emote components - this only marks the
    # scene context (independent of the emote FEATURE's own gates)
    for mod_name, cls_name, meths in (
            ('gclient.gamesystem.models.hall_emote_model_component',
             'EmoteModelComponent',
             ('CueEmoteBegin', 'CueStartShowEmoteModel', 'PlayEmoteAnim')),
            ('gclient.gamesystem.models.hall_model_component',
             'HallModelComponent', ('PlayEmoteAnim', 'ShowEmoteModel'))):
        try:
            mod = sys.modules.get(mod_name)
            if mod is None:
                try:
                    mod = __import__(mod_name, globals(), locals(),
                                     ['x'], 0)
                except Exception:
                    continue
            cls = getattr(mod, cls_name, None)
            if not isinstance(cls, type):
                continue
            for meth in meths:
                prev = cls.__dict__.get(meth)
                if (not callable(prev)
                        or getattr(prev, '_treacky_emc', False)):
                    continue

                def _ewrap(_prev):
                    def wrapper(self, *a, **k):
                        _striker_emote_until[0] = time.time() + 10.0
                        _striker_invalidate_skin_caches('emote-start')
                        return _prev(self, *a, **k)
                    wrapper._treacky_emc = True
                    return wrapper

                setattr(cls, meth, _ewrap(prev))
                found.append('%s.%s' % (cls_name, meth))
        except Exception:
            continue
    return found


_striker_wraps_logged = [False]


def _striker_scene_watcher():
    """The emote component classes load late - retry (cheap, idempotent)
    forever; already-wrapped methods are skipped by their markers."""
    _probed = [False]
    while True:
        try:
            found = _install_striker_scene_wraps()
            if found and not _striker_wraps_logged[0]:
                _striker_wraps_logged[0] = True
                _plog('[HERO-SCENE] wraps installed %r' % (found,))
            if not _probed[0]:
                _probed[0] = True
                # v7.30R20 boot probe: is the ORIGINAL block's forcing
                # layer actually installed? hero_skin_proto.fget should
                # be the block's _getter on the doll classes - if it is
                # anything else the block's install failed and that is
                # the skin regression, visible in the next device log.
                try:
                    names = {}
                    try:
                        _hd = __import__('gclient.gamesystem.entities.hall_doll',
                                         globals(), locals(), ['Doll'], 0)
                        for _cn in ('Doll', 'DollLike', 'CalculationDoll',
                                    'BigHeadCalculationDoll'):
                            _c = getattr(_hd, _cn, None)
                            if _c is None:
                                continue
                            _p = _c.__dict__.get('hero_skin_proto')
                            names[_cn] = getattr(getattr(_p, 'fget', None),
                                                 '__name__', None)
                    except Exception as _ie:
                        names['import'] = repr(_ie)
                    from gclient.gamesystem.models.hall_show_model import \
                        HallShowModel as _HSMp
                    _fg = None
                    try:
                        _fg = getattr(_HSMp.__dict__.get('hero_skin_proto'),
                                      'fget', None)
                    except Exception:
                        pass
                    _plog('[HERO-SCENE] block probe HallShowModel.fget=%r '
                          'doll_fgets=%r' %
                          (getattr(_fg, '__name__', None), names))
                except Exception as _pe:
                    _plog('[HERO-SCENE] block probe failed %r' % (_pe,))
        except Exception:
            pass
        try:
            time.sleep(10.0)
        except Exception:
            return


try:
    threading.Thread(target=_striker_scene_watcher, daemon=True).start()
except Exception:
    pass


# ============================================================
# v7.30R20: STRIKER IN-MATCH SKIN + EFFECTS (the DSID layer)
# ============================================================


def _striker_native_combat_owned():
    """True when the native Striker state/consumer layer owns combat.

    The pre-native combat wrappers below were best-effort visual workarounds.
    Once native equip/readback is enabled they must not replace execution,
    Nova-form, low-level, or hand-model state a second time.  Lookup is dynamic
    because the native installer is defined later in this payload.
    """
    try:
        gate = globals().get('category_enabled')
        return bool(callable(gate) and gate('striker'))
    except Exception:
        return False
# Device rounds R11-R13 proved this one getter's forced answer is what
# raises the striker skin AND its effects in a match (R12 passive = no
# effects, v7.7 raw = effects). R18 shipped it as a test button; R19
# removed the whole layer and the device test came back "effects only
# in lobby, nothing in gameplay". R20 restores it with NO button: it is
# armed whenever the striker master switch says the current scene may
# force (in a match that is the bStrikerMatch button via the gated
# flag), and it only ever answers when the game asks about NO specific
# item - specific-item queries stay honest. The BSB block itself stays
# byte-verbatim; this is an add-on layer around Player-prefixed
# avatars, exactly as it was in R18.
_HEROFX_SPECS = (
    ('gclient.framework.entities.avatar', 'PlayerAvatar'),
    ('gclient.gameplay.logic_base.entities.combat_avatar', 'CombatAvatar'),
    ('gclient.gameplay.logic_base.entities.combat_avatar',
     'PlayerCombatAvatar'),
    ('gclient.gameplay.logic_shootingrange.combat_avatar_shootingrange',
     'PlayerCombatAvatarShootingRange'),
    ('gclient.gameplay.logic_shootingrange.combat_avatar_shootingrange',
     'RobotCombatAvatarShootingRange'),
)
_herofx_notes = {}


def _herofx_note(tag, text):
    try:
        n = _herofx_notes.get(tag, 0) + 1
        _herofx_notes[tag] = n
        if n <= 3 or n % 50 == 0:
            _plog('[HERO-FX] %s (#%d)' % (text, n))
    except Exception:
        pass


def _install_striker_effects_class(cls, found=None):
    """Wrap GetDisplayHeroSkinItemId (the DSID getter) on ONE class."""
    try:
        cls_name = cls.__name__
    except Exception:
        return
    prev = cls.__dict__.get('GetDisplayHeroSkinItemId')
    if not callable(prev) or getattr(prev, '_treacky_dsid', False):
        return
    label = '%s.GetDisplayHeroSkinItemId' % cls_name

    def _make_dsid(_prev, _label):
        # v7.30R27: signature-transparent (same crash class the R26 log
        # caught on ghsp - never pad positional args on passthrough).
        def wrapper(self, *a, **k):
            try:
                skin_item_id = k.get('skin_item_id', None)
                if len(a) > 0 and skin_item_id is None:
                    skin_item_id = a[0]
                if (sync_attrs.get('bHeroSkinHack', False)
                        and not _striker_native_combat_owned()
                        and _hero_scene_stable() == 'match'
                        and type(self).__name__.startswith('Player')):
                    gf = globals().get('_get_forced_skin')
                    hid = _hero_id_deep(self)
                    forced = gf(hid) if (hid and callable(gf)) else None
                    if forced and not _safe_int(skin_item_id, 0):
                        _herofx_note(_label,
                                     '%s -> %s (match)' % (_label, forced))
                        return forced
            except Exception:
                pass
            return _prev(self, *a, **k)
        wrapper._treacky_dsid = True
        return wrapper

    try:
        setattr(cls, 'GetDisplayHeroSkinItemId',
                _make_dsid(prev, label))
        if found is not None:
            found.append(label)
    except Exception:
        pass


def _install_striker_effects():
    found = []
    for mod_name, cls_name in _HEROFX_SPECS:
        mod = sys.modules.get(mod_name)
        if mod is None:
            try:
                mod = __import__(mod_name, globals(), locals(), ['x'], 0)
            except Exception:
                mod = None
        cls = getattr(mod, cls_name, None) if mod is not None else None
        if isinstance(cls, type):
            _install_striker_effects_class(cls, found)
    return found


_herofx_tries = [0]


def _striker_effects_watcher():
    """Avatar classes load at different times - retry (cheap, idempotent)
    until the getter is wrapped on at least two of them."""
    while True:
        try:
            found = _install_striker_effects()
            _herofx_tries[0] += 1
            if found:
                _herofx_note('install',
                             'striker in-match layer wrapped %r (try %d)'
                             % (found, _herofx_tries[0]))
                if len(found) >= 2:
                    return
            if _herofx_tries[0] >= 360:   # ~1 h of 10 s retries
                return
        except Exception:
            pass
        try:
            time.sleep(10.0)
        except Exception:
            return


try:
    threading.Thread(target=_striker_effects_watcher, daemon=True).start()
except Exception:
    pass


# ============================================================
twin_honest_until = [0.0]   # v8.10: Nova twin build window -
                                # hero_skin_proto answers honest


# v7.30R21: IN-MATCH SKIN CHANNEL (cached_property hero_skin_proto)
# ============================================================
# The original block only hooks hero_skin_proto when it is a plain
# property. On the current game the match avatar's hero_skin_proto is
# a cached_property - the block's own installer skips it (by design of
# the zip it came from), so in a match the game kept reading the REAL
# skin: effects arrived (the DSID layer) but the model never changed.
# This add-on wraps the cached_property's function the same way the
# block wraps plain properties: gate on (the scene-gated flag), resolve
# the hero, return the forced proto. The block stays byte-verbatim.
def _install_hsp_force(cls, found=None, local_only=False):
    try:
        cp = cls.__dict__.get('hero_skin_proto')
        if cp is None or isinstance(cp, property):
            return False                # absent, or block already handles
        f = getattr(cp, 'func', None) or getattr(cp, 'fget', None)
        if not callable(f) or getattr(f, '_treacky_hspf', False):
            return False
        if getattr(cp, '_treacky_hspf', False):
            return False

        def _forced(self, _f=f, _lo=local_only):
            result = _f(self)
            try:
                # Native GetHeroSkinProto is the single combat resolver.  The
                # official cached_property delegates there; forcing the cached
                # result here would bypass execution/form transitions.
                if (_lo and _striker_native_combat_owned()
                        and _hero_scene_stable() == 'match'):
                    return result
                if (not _lo and _striker_native_combat_owned()
                        and not _striker_native_local_display(self)):
                    return result
                # v2.104: key on the EQUIPPED ITEM (the resolver returns
                # None when nothing is picked), never the bHeroSkinHack
                # toggle - the r112 law.  The _lo/local/twin rails below
                # stay byte-for-byte.
                if True:
                    # v7.30R22: in a match, combat avatars force ONLY for
                    # the local player - enemy avatars that share a hero
                    # with one of our picks keep their real skin. In the
                    # hall there are no combat avatars, so hero-id
                    # forcing stays fine there.
                    if (_lo and _hero_scene_stable() == 'match'
                            and not _striker_is_local(self)):
                        return result
                    # v8.10: the Nova twin skill builds its model from
                    # the avatar's skin state - keep the property
                    # HONEST during the twin build (the striker skill
                    # must stay the skill visual, not the skin).
                    try:
                        if _lo and time.time() < twin_honest_until[0]:
                            return result
                    except Exception:
                        pass
                    hid = None
                    if hasattr(self, 'GetHeroId'):
                        hid = self.GetHeroId()
                    elif hasattr(self, 'hero_id'):
                        hid = self.hero_id
                    if hid:
                        resolver = globals().get(
                            '_get_forced_hero_skin_proto')
                        if callable(resolver):
                            fp = resolver(hid)
                            if fp is not None:
                                _herofx_note(
                                    'hero_skin_proto',
                                    'hero_skin_proto -> authentic hero row')
                                return fp
            except Exception:
                pass
            return result
        _forced.__name__ = getattr(f, '__name__', 'hero_skin_proto')
        _forced._treacky_hspf = True
        CP = type(cp)
        new_cp = CP(_forced)
        try:
            new_cp._treacky_hspf = True
        except Exception:
            pass
        setattr(cls, 'hero_skin_proto', new_cp)
        if found is not None:
            found.append(cls.__name__)
        return True
    except Exception:
        return False


def _install_ghsp_class(cls, found=None):
    """v7.30R22: wrap GetHeroSkinProto on the COMBAT avatar classes.
    The original block hooks it on PlayerAvatar only - on the current
    game the match avatar is a PlayerCombatAvatar, so the match model
    channel the block was built for never fires. Same semantics as the
    block's hook, but LOCAL-ONLY in a match (enemies keep their real
    skins) and only when the game asks about no specific item."""
    try:
        cls_name = cls.__name__
    except Exception:
        return
    prev = cls.__dict__.get('GetHeroSkinProto')
    if not callable(prev) or getattr(prev, '_treacky_ghsp', False):
        return
    label = '%s.GetHeroSkinProto' % cls_name

    def _make_ghsp(_prev, _label):
        # v7.30R27: SIGNATURE-TRANSPARENT. The R26 device log caught the
        # real crash: the game calls GetHeroSkinProto() with ZERO args
        # (cimp_model._on_set_arm_clothes), and this wrapper used to
        # repack the call as _prev(self, None, None) - 3 positional args
        # into 1-arg CombatAvatarMember.GetHeroSkinProto -> TypeError
        # inside the game's on_setattr -> the vault / avatar-card CRASH
        # (64 hits in one log, also the lag). Passthrough now forwards
        # the EXACT args, always.
        def wrapper(self, *a, **k):
            try:
                # v7.30R27: any live PlayerAvatar passing through here
                # is the equip-by-game trigger (the R26 trigger methods
                # were never called by this game).
                try:
                    if callable(getattr(self, 'ArmHeroSkin', None)):
                        _avatar_note_seen(self)
                except Exception:
                    pass
                hero_id = k.get('hero_id', None)
                skin_item_id = k.get('skin_item_id', None)
                if len(a) > 0 and hero_id is None:
                    hero_id = a[0]
                if len(a) > 1 and skin_item_id is None:
                    skin_item_id = a[1]
                if (sync_attrs.get('bHeroSkinHack', False)
                        and not _striker_native_combat_owned()
                        and not _safe_int(skin_item_id, 0)
                        and _hero_scene_stable() == 'match'
                        and _striker_is_local(self)):
                    if not hero_id:
                        if hasattr(self, 'GetHeroId'):
                            hero_id = self.GetHeroId()
                        elif hasattr(self, 'hero_id'):
                            hero_id = self.hero_id
                    if hero_id:
                        resolver = globals().get(
                            '_get_forced_hero_skin_proto')
                        if callable(resolver):
                            fp = resolver(hero_id)
                            if fp is not None:
                                _herofx_note(
                                    _label,
                                    '%s -> authentic hero row (match, local)'
                                    % _label)
                                return fp
            except Exception:
                pass
            return _prev(self, *a, **k)
        wrapper._treacky_ghsp = True
        return wrapper

    try:
        setattr(cls, 'GetHeroSkinProto', _make_ghsp(prev, label))
        if found is not None:
            found.append(label)
    except Exception:
        pass


# v7.30R23: the classic per-hero equip getters - the original block's
# PlayerAvatar channel never fires on this game version (R22 device
# log: block hook counters all zero for a whole session), and
# GetHeroSkinProto on the combat avatar fires only ~3x per match, so
# it is not the model driver either. These are the remaining known
# per-hero channels the match model can be built from.
_ARM_SPECS = (
    ('GetCurArmSkinItemId', 'id'),
    ('GetActualArmSkinItemId', 'id'),
    ('GetCurArmHeroSkinProto', 'proto'),
    ('GetActualArmHeroSkinProto', 'proto'),
    ('GetModelUnitID', 'unit'),
)


def _install_arm_force(cls, found=None):
    """v7.30R23: wrap the equip/model getters on ONE combat class.
    Match + LOCAL avatar only (enemies, robots and the hall stay on
    their real answers)."""
    try:
        cls_name = cls.__name__
    except Exception:
        return
    for meth, kind in _ARM_SPECS:
        try:
            prev = cls.__dict__.get(meth)
            if not callable(prev) or getattr(prev, '_treacky_armf', False) \
                    or getattr(prev, '_skhk', False):
                continue
            label = '%s.%s' % (cls_name, meth)

            def _make_arm(_prev, _label, _kind):
                def wrapper(self, *a, **k):
                    try:
                        if (sync_attrs.get('bHeroSkinHack', False)
                                and not _striker_native_combat_owned()
                                and _hero_scene_stable() == 'match'
                                and _striker_is_local(self)):
                            gf = globals().get('_get_forced_skin')
                            gfp = globals().get('_get_forced_skin_proto')
                            ghp = globals().get(
                                '_get_forced_hero_skin_proto')
                            hid = None
                            if a:
                                try:
                                    hid = _safe_int(a[0], 0) or None
                                except Exception:
                                    hid = None
                            if not hid:
                                hid = _hero_id_deep(self)
                            forced = gf(hid) if (hid and callable(gf)) \
                                else None
                            if forced:
                                if _kind == 'id':
                                    _herofx_note(_label,
                                                 '%s -> %s (match, local)'
                                                 % (_label, forced))
                                    return forced
                                if _kind == 'proto':
                                    fp = ghp(hid) if callable(ghp) else None
                                    if fp is not None:
                                        _herofx_note(
                                            _label,
                                            '%s -> authentic hero row '
                                            '(match, local)' % (_label,))
                                        return fp
                                fp = gfp(hid) if callable(gfp) else None
                                if _kind == 'unit':
                                    mid = _hero_proto_get(
                                        fp, 'model_id', None) \
                                        if fp is not None else None
                                    if mid:
                                        _herofx_note(_label,
                                                     '%s -> %s (match, '
                                                     'local)'
                                                     % (_label, mid))
                                        return mid
                    except Exception:
                        pass
                    return _prev(self, *a, **k)
                wrapper._treacky_armf = True
                wrapper._treacky_orig = _prev
                return wrapper

            setattr(cls, meth, _make_arm(prev, label, kind))
            if found is not None:
                found.append(label)
        except Exception:
            continue


# v7.30R24: the R23 device log's match probe named the combat avatar's
# REAL model pipeline: InitAvatarModel / OnLoadModel / OnReloadModel /
# OnReloadPlayerModel / CacheModel / ShowModel / GetModelData /
# GetReplaceModelID (RobotCombatAvatarShootingRange exposes exactly
# InitAvatarModel -> OnLoadModel -> ShowModel). Map the equipped skin's
# model fields onto our pick's fields everywhere in that pipeline -
# match + LOCAL avatar only.
_MDL_SPECS = ('InitAvatarModel', 'OnLoadModel', 'OnReloadModel',
              'OnReloadPlayerModel', 'CacheModel', 'ShowModel',
              'GetModelData', 'GetReplaceModelID')
_MDL_FIELDS = ('model_id', 'fps_model_id', 'model_id_alb')
# v8.06: the v8.05 log recomputed the map on EVERY pipeline call
# (the getters hit #50/#100) - the resolution chain reads data tables
# and the avatar, which during match loading stalled the game thread
# for up to 76s. Cache per (hero, pick sig, real skin, avatar).
mdlmap_cache = {}


def _striker_model_map(self):
    """real-skin model field -> forced model field for this avatar."""
    try:
        gfp = globals().get('_get_forced_skin_proto')
        if not callable(gfp):
            return None
        hid = _hero_id_deep(self)
        if not hid:
            return None
        forced = gfp(hid)
        if forced is None:
            return None
        real_id = None
        for meth in ('GetActualSkinItemId', '_GetActualHeroSkinItemId',
                     'GetCurArmSkinItemId'):
            try:
                fn = getattr(self, meth, None)
                if callable(fn):
                    # our own wraps answer the FORCED id - read through
                    # to the ORIGINAL so the map stays real -> forced
                    orig = getattr(fn, '_treacky_orig', None)
                    if callable(orig):
                        v = orig(self)
                    elif any(getattr(fn, _mk, False) for _mk in
                             ('_treacky_armf', '_treacky_ghsp',
                              '_treacky_avsk')):
                        continue
                    else:
                        v = fn()
                    if v:
                        real_id = v
                        break
            except Exception:
                continue
        _ck = (hid, _hero_apply_sig[0], real_id, id(self))
        _ce = mdlmap_cache.get(_ck)
        if _ce is not None and time.time() - _ce[0] < 10.0:
            return _ce[1]
        mapping = {}
        if real_id:
            try:
                import gclient.data.lobby_item_data as _lid
                real = _lid.data.get(real_id)
            except Exception:
                real = None
            if real is not None:
                for f in _MDL_FIELDS:
                    rv = _hero_proto_get(real, f, None)
                    fv = _hero_proto_get(forced, f, None)
                    if rv and fv and rv != fv:
                        mapping[rv] = fv
        if not mapping:
            # v8.05: NO real skin armed - the server can revert the
            # equip between sessions (the v8.04 device log proved it:
            # every Load came back model_id=None, the local match
            # avatar built the DEFAULT model and the R24 base lookup
            # found nothing because the hero tables carry no model
            # fields). Resolve the hero's DEFAULT model from every
            # source we have and map each to the pick's counterpart.
            base_by_field = {}
            # (a) the hero's default item proto (hero_item_id)
            try:
                mod = sys.modules.get('gclient.data.hero_data')
                data = getattr(mod, 'data', None)
                hp2 = data.get(hid) if hasattr(data, 'get') else None
                hitem = _hero_proto_get(hp2, 'hero_item_id', None)
                if hitem:
                    import gclient.data.lobby_item_data as _lid2
                    dp = _lid2.data.get(hitem)
                    for f in _MDL_FIELDS:
                        v = _hero_proto_get(dp, f, None)
                        if v:
                            base_by_field.setdefault(f, set()).add(v)
            except Exception:
                pass
            # (b) the avatar's own current model (what it actually
            # loaded while the arm state was empty). NOTE: in a match
            # these properties may already answer the FORCED model
            # (v8.06 unit-model force) - same-value maps are filtered.
            try:
                v = _safe_int(getattr(self, 'unit_model_id', None), 0)
                if v:
                    base_by_field.setdefault('model_id',
                                             set()).add(v)
            except Exception:
                pass
            try:
                v = _safe_int(getattr(self, 'hand_model_id', None), 0)
                if v:
                    base_by_field.setdefault('fps_model_id',
                                             set()).add(v)
            except Exception:
                pass
            # (c) the avatar's default skin proto (read through the
            # wrapper to the ORIGINAL - our wraps answer the pick)
            try:
                fn = getattr(self, 'GetHeroSkinProto', None)
                orig = getattr(fn, '_treacky_orig', None) \
                    if callable(fn) else None
                if callable(orig):
                    dp = orig(self)
                    for f in _MDL_FIELDS:
                        v = _hero_proto_get(dp, f, None)
                        if v:
                            base_by_field.setdefault(f, set()).add(v)
            except Exception:
                pass
            # (d) the R24 hero-table lookup (kept - harmless)
            base = _striker_hero_base_model(hid)
            if base:
                base_by_field.setdefault('model_id', set()).add(base)
            # field-to-field: default.model_id -> pick.model_id,
            # default.fps -> pick.fps (never cross-field).
            for f, bvs in base_by_field.items():
                fv = _hero_proto_get(forced, f, None)
                for bv in bvs:
                    if bv and fv and bv != fv:
                        mapping[bv] = fv
        try:
            if len(mdlmap_cache) > 8:
                mdlmap_cache.clear()
            mdlmap_cache[_ck] = (time.time(), mapping or None)
        except Exception:
            pass
        return mapping or None
    except Exception:
        return None


def _striker_hero_base_model(hero_id):
    """The hero's default model id from the hero data tables."""
    try:
        for mod_name in ('gclient.data.hero_data',
                         'gclient.data.hero_skin_data'):
            mod = sys.modules.get(mod_name)
            if mod is None:
                continue
            data = getattr(mod, 'data', None)
            if not hasattr(data, 'get'):
                continue
            hp = data.get(hero_id)
            for f in ('model_id', 'base_model_id', 'hero_model_id'):
                v = _hero_proto_get(hp, f, None)
                if v:
                    return v
    except Exception:
        pass
    return None


def _install_model_force(cls, found=None):
    """v7.30R24: wrap the avatar model pipeline on ONE combat class.
    Any model-id argument (or dict field) that belongs to the avatar's
    REAL equipped skin is swapped for our pick's counterpart."""
    try:
        cls_name = cls.__name__
    except Exception:
        return
    for meth in _MDL_SPECS:
        try:
            prev = cls.__dict__.get(meth)
            if not callable(prev) or getattr(prev, '_treacky_mdlf', False):
                continue
            label = '%s.%s' % (cls_name, meth)
            is_get = meth in ('GetModelData', 'GetReplaceModelID')

            def _make_mdl(_prev, _label, _get):
                def wrapper(self, *a, **k):
                    try:
                        # v7.30R27: bStrikerTPS extends the model force
                        # past the match into the emote window (emote =
                        # TPS camera; the third-person model the user
                        # actually SEES is built there).
                        _tps = False
                        if sync_attrs.get('bStrikerTPS', False):
                            try:
                                _tps = time.time() < _striker_emote_until[0]
                            except Exception:
                                _tps = False
                        if (sync_attrs.get('bHeroSkinHack', False)
                                and not _striker_native_combat_owned()
                                and (_hero_scene_stable() == 'match'
                                     or _tps)
                                and _striker_is_local(self)):
                            mapping = _striker_model_map(self)
                            # v8.05: visibility - which pipeline
                            # methods fire for the LOCAL avatar in a
                            # match and what map they got (capped per
                            # label). If the skin still fails to show
                            # in match, this line names the channel.
                            _herofx_note(
                                _label + ':pipe', '%s (match, local) %s'
                                % (_label,
                                   ('map=%r' % (sorted(
                                       mapping.items())[:3],))
                                   if mapping else 'nomap'))
                            if mapping:
                                if _get:
                                    res = _prev(self, *a, **k)
                                    rv = res if isinstance(res, int) \
                                        else None
                                    if rv is None and hasattr(res, 'get'):
                                        rv = _hero_proto_get(res,
                                                             'model_id',
                                                             None)
                                    if rv in mapping:
                                        _herofx_note(
                                            _label, '%s -> %s (match, '
                                            'local)' % (_label, mapping[rv]))
                                        if isinstance(res, int):
                                            return mapping[rv]
                                        try:
                                            res['model_id'] = mapping[rv]
                                        except Exception:
                                            pass
                                        return res
                                    if not rv and mapping:
                                        # v8.06: the game asked for a
                                        # replace/model id and has NONE
                                        # (no real skin armed) - answer
                                        # the pick's model, exactly what
                                        # a real equipped skin would do.
                                        try:
                                            _hid0 = _hero_id_deep(self)
                                            _gfp0 = globals().get(
                                                '_get_forced_skin_proto')
                                            _fp0 = _gfp0(_hid0) \
                                                if (_hid0 and callable(
                                                    _gfp0)) else None
                                            fv = _hero_proto_get(
                                                _fp0, 'model_id', None)
                                        except Exception:
                                            fv = None
                                        if fv:
                                            _herofx_note(
                                                _label, '%s empty -> %s '
                                                '(match, local fill)'
                                                % (_label, fv))
                                            if isinstance(res, int):
                                                return fv
                                            try:
                                                res['model_id'] = fv
                                            except Exception:
                                                pass
                                        return res
                                    if rv:
                                        # v8.10: the v8.09 unmapped
                                        # fill is REVERTED - it broke
                                        # the Nova twin striker skill
                                        # (the game asks GetReplace-
                                        # ModelID for the TWIN's model
                                        # too; answering the pick's
                                        # skin made the skill visual
                                        # become the skin). Unmapped
                                        # answers stay honest; the TPS
                                        # emote body is handled at the
                                        # hero_skin_proto property now
                                        # (the original mod's channel).
                                        _herofx_note(
                                            _label + ':seen',
                                            '%s res=%r unmapped' % (_label,
                                                                    rv))
                                    return res
                                na = list(a)
                                for i, av in enumerate(na):
                                    if isinstance(av, int) and av in mapping:
                                        _herofx_note(
                                            _label, '%s arg %s -> %s '
                                            '(match, local)'
                                            % (_label, av, mapping[av]))
                                        na[i] = mapping[av]
                                    elif hasattr(av, 'get') and \
                                            hasattr(av, '__setitem__'):
                                        mv = _hero_proto_get(av, 'model_id',
                                                              None)
                                        if mv in mapping:
                                            try:
                                                av['model_id'] = mapping[mv]
                                            except Exception:
                                                pass
                                a = na
                    except Exception:
                        pass
                    return _prev(self, *a, **k)
                wrapper._treacky_mdlf = True
                return wrapper

            setattr(cls, meth, _make_mdl(prev, label, is_get))
            if found is not None:
                found.append(label)
        except Exception:
            continue


def hand_model_vetoed():
    """v2.95: never veto an EQUIPPED skin.  The game picker's native
    ArmHeroSkin flow (the CUNLOCK striker categories) equips skins with
    the legacy bHeroSkinHack switch OFF - the old rule starved exactly
    those equips ('hand_model_id -> None' across the debug-10 log).  The
    per-hero chain downstream still requires an actual equipped pick and
    passes through to the game's own answer otherwise."""
    return False


def hand_model_for(self):
    """The authorised fps_model_id for this avatar's hands, or None.

    v10.12.2-lagfix-r1.  Why this exists:

    Every striker skin row carries TWO model ids (device log,
    HERO_SKIN_INFO count=556):

        3001130351  ZERO - Levi: Battle-Hardened
                    model_id=511300332      <- third-person body / doll
                    fps_model_id=511300331  <- FIRST-PERSON ARMS

    The hands the player sees in a match are built from fps_model_id, not
    model_id.  The old layer that forced hand_model_id
    (_install_unit_model_force) bails out on
    ``not _striker_native_combat_owned()`` - i.e. the moment the striker
    category is switched on (which is the default), the hands are left
    entirely to the native layer.  The native layer, in the r1 session, never
    ran a single body/hands refresh: the whole sky-r1 log has ZERO
    'striker-combat-show' lines, while the equip itself did happen
    ('RPC=ArmHeroSkin item=3001150050').  Net effect on device: every striker
    skin shows its body but the arms keep the default mesh - because only
    model_id was ever honoured and fps_model_id was never applied by anything.

    So: answer the pick's fps_model_id for the LOCAL avatar in a match, read
    from the same authentic tables the game uses
    (lobby_item_data -> fps_model_id).  Enemies and other players are never
    touched.
    """
    try:
        if hand_model_vetoed():
            return None
        if _hero_scene_stable() != 'match':
            return None
        if not _striker_is_local(self):
            return None
        hid = _hero_id_deep(self)
        if not hid:
            return None
        gfp = globals().get('_get_forced_skin_proto')
        fp = gfp(hid) if callable(gfp) else None
        if fp is None:
            return None
        value = _hero_proto_get(fp, 'fps_model_id', None)
        value = _safe_int(value, 0)
        return value or None
    except Exception:
        return None


def _install_hand_model_native(cls, found=None):
    """Additive fps_model_id layer for the local player's hands only.

    Deliberately INDEPENDENT of _striker_native_combat_owned(): that gate
    exists so two layers never fight over the same property, and the native
    layer demonstrably does not write hand_model_id at all.  This one only
    ever ANSWERS a different value than the original would (it never stores
    anything), and it always reports itself in the log so the next device log
    can confirm the channel rather than us guessing again.
    """
    try:
        cls_name = cls.__name__
    except Exception:
        return
    attr = 'hand_model_id'
    try:
        prev = cls.__dict__.get(attr)
        if isinstance(prev, property):
            fget = getattr(prev, 'fget', None)
            if not callable(fget) or getattr(fget, '_treacky_hmn', False):
                return

            def _fg_w(self):
                forced = hand_model_for(self)
                if forced:
                    try:
                        _herofx_note('%s.%s' % (cls_name, attr),
                                     '%s -> %s (match, local hands, '
                                     'fps_model_id)' % (attr, forced))
                    except Exception:
                        pass
                    return forced
                return fget(self)
            _fg_w._treacky_hmn = True
            setattr(cls, attr, property(_fg_w, prev.fset, prev.fdel,
                                        prev.__doc__))
            if found is not None:
                found.append('%s.%s' % (cls_name, attr))
        elif prev is not None and callable(getattr(prev, 'func', None)):
            f = prev.func
            if getattr(f, '_treacky_hmn', False):
                return

            def _f_w(self):
                forced = hand_model_for(self)
                if forced:
                    try:
                        _herofx_note('%s.%s' % (cls_name, attr),
                                     '%s -> %s (match, local hands, '
                                     'fps_model_id)' % (attr, forced))
                    except Exception:
                        pass
                    return forced
                return f(self)
            _f_w._treacky_hmn = True
            try:
                ncp = type(prev)(_f_w)
            except Exception:
                return
            setattr(cls, attr, ncp)
            if found is not None:
                found.append('%s.%s' % (cls_name, attr))
    except Exception:
        return


def _install_unit_model_force(cls, found=None):
    """v8.06: the v8.05 device log proved the match model pipeline
    carries NO mappable ids - InitAvatarModel/ShowModel/GetModelData/
    GetReplaceModelID fired with a live map and ZERO swaps. The ids
    live in the avatar's unit_model_id / hand_model_id properties.
    Force those on the LOCAL avatar in a match (enemies stay real)."""
    try:
        cls_name = cls.__name__
    except Exception:
        return
    for attr, field in (('unit_model_id', 'model_id'),
                        ('hand_model_id', 'fps_model_id')):
        try:
            prev = cls.__dict__.get(attr)
            if isinstance(prev, property):
                fget = getattr(prev, 'fget', None)
                if not callable(fget) \
                        or getattr(fget, '_treacky_umf', False):
                    continue

                def _mk_prop(_prev, _fget, _label, _field):
                    def fget_w(self):
                        try:
                            if (sync_attrs.get('bHeroSkinHack', False)
                                    and not _striker_native_combat_owned()
                                    and _hero_scene_stable() == 'match'
                                    and _striker_is_local(self)):
                                hid = _hero_id_deep(self)
                                gfp = globals().get(
                                    '_get_forced_skin_proto')
                                fp = gfp(hid) if (hid and callable(gfp)) \
                                    else None
                                if fp is not None:
                                    v = _hero_proto_get(fp, _field, None)
                                    if v:
                                        _herofx_note(
                                            _label, '%s -> %s (match, '
                                            'local unit model)'
                                            % (_label, v))
                                        return v
                        except Exception:
                            pass
                        try:
                            return _fget(self)
                        except Exception:
                            return None
                    fget_w._treacky_umf = True
                    return fget_w
                _fg = _mk_prop(prev, fget, '%s.%s' % (cls_name, attr),
                               field)
                setattr(cls, attr, property(_fg, prev.fset, prev.fdel,
                                            prev.__doc__))
                if found is not None:
                    found.append('%s.%s' % (cls_name, attr))
            elif prev is not None and callable(getattr(prev, 'func',
                                                       None)):
                # cached_property variant (like hero_skin_proto)
                f = prev.func
                if getattr(f, '_treacky_umf', False):
                    continue

                def _mk_cp(_prev, _f, _label, _field):
                    def f_w(self):
                        try:
                            if (sync_attrs.get('bHeroSkinHack', False)
                                    and not _striker_native_combat_owned()
                                    and _hero_scene_stable() == 'match'
                                    and _striker_is_local(self)):
                                hid = _hero_id_deep(self)
                                gfp = globals().get(
                                    '_get_forced_skin_proto')
                                fp = gfp(hid) if (hid and callable(gfp)) \
                                    else None
                                if fp is not None:
                                    v = _hero_proto_get(fp, _field, None)
                                    if v:
                                        _herofx_note(
                                            _label, '%s -> %s (match, '
                                            'local unit model)'
                                            % (_label, v))
                                        return v
                        except Exception:
                            pass
                        return _f(self)
                    f_w._treacky_umf = True
                    return f_w
                CP = type(prev)
                _fw = _mk_cp(prev, f, '%s.%s' % (cls_name, attr), field)
                try:
                    ncp = CP(_fw)
                except Exception:
                    continue
                setattr(cls, attr, ncp)
                if found is not None:
                    found.append('%s.%s' % (cls_name, attr))
        except Exception:
            continue




# ============================================================
# FPSARMS v1: the first-person hands rebuild (the arm-clothes
# dispatch).  The FPS hands are rebuilt ONLY when arm_clothes
# changes through the entity dispatch: engine sets avatar.arm_clothes
# -> CombatAvatar.on_setattr('arm_clothes', old, new) ->
# _on_set_arm_clothes(old) -> hand-model reload (AddHandPrimitives
# with fps_model_id).  Map writes mutate in place and plain attribute
# writes bypass on_setattr - both were silent no-ops.  This block
# merges slot 300 = the equipped Suit item via _zle_arm_clothes (the
# other slots kept) and FIRES the dispatch through whichever entry
# this engine build exposes, stopping at the first that runs.
# ============================================================
_fpsarms_state = {'resolve': {}, 'hmf': {}, 'notes': set()}


def _fpsarms_note(key, msg):
    try:
        if key not in _fpsarms_state['notes']:
            _fpsarms_state['notes'].add(key)
            _plog(msg)
    except Exception:
        pass


def _fpsarms_resolve(hero_id):
    """(item_id, source) for this hero: GAME STATE first, then the pick."""
    item = 0
    source = 'none'
    try:
        _native = globals().get('striker_legacy_skin')
        if callable(_native):
            item = _v109_int(_native(hero_id), 0)
            if item:
                source = 'game-state'
        if not item:
            _gfs = globals().get('_get_forced_skin')
            if callable(_gfs):
                item = _v109_int(_gfs(hero_id), 0)
                if item:
                    source = 'pick'
    except Exception:
        pass
    try:
        _seen = _fpsarms_state['resolve']
        if _seen.get(hero_id, 0) < 2:
            _seen[hero_id] = _seen.get(hero_id, 0) + 1
            _plog('[FPSARMS] resolve hero=%s item=%s source=%s'
                  % (hero_id, item, source))
    except Exception:
        pass
    return item, source


def _fpsarms_refresh(owner, hero_id, item_id):
    """Rebuild the local combat avatar's FPS hands from the equipped Suit.

    Gates: bHeroSkinHack + scene 'match' (training included) + a Suit
    item (sub_type 300) + a local combat avatar + hero match.  A gate
    that SAYS NO logs one line and stands down; a gate that ERRORS fails
    OPEN with one log (never silently drop a legit equip).
    """
    try:
        if not item_id and not sync_attrs.get('bHeroSkinHack', False):
            return
        scene = _hero_scene_stable()
        if scene != 'match':
            _fpsarms_note('skip-scene',
                          '[FPSARMS] skip scene=%s (correctly did nothing)'
                          % (scene,))
            return
        info = (globals().get('HERO_SKIN_INFO') or {}).get(item_id) or {}
        if _v109_int(info.get('sub_type', 0), 0) != 300:
            _fpsarms_note('skip-suit',
                          '[FPSARMS] skip not a Suit item=%s' % (item_id,))
            return
        _get_local = globals().get('_local_combat_avatar')
        cav = _get_local() if callable(_get_local) else None
        if cav is None:
            _fpsarms_note('skip-cav',
                          '[FPSARMS] skip no local combat avatar')
            return
        try:
            cav_hero = _v109_int(_hero_id_deep(cav), 0)
        except Exception:
            cav_hero = 0
        if cav_hero and hero_id and cav_hero != hero_id:
            _fpsarms_note('skip-hero',
                          '[FPSARMS] skip hero-mismatch cav=%s hero=%s'
                          % (cav_hero, hero_id))
            return
        # LAW 2: drop the stale cached_property instance-dict entries.
        try:
            _dict = cav.__dict__
            _dict.pop('hero_skin_proto', None)
            _dict.pop('skin_proto', None)
        except Exception:
            pass
        old = getattr(cav, 'arm_clothes', None)
        _acfn = globals().get('_zle_arm_clothes')
        merged = _acfn(item_id, old) if callable(_acfn) else (None, 0)
        if not merged or merged[0] is None:
            _fpsarms_note('skip-ac',
                          '[FPSARMS] skip CArmClothes merge failed item=%s'
                          % (item_id,))
            return
        new = merged[0]
        try:
            cav.arm_clothes = new
        except Exception:
            pass
        via = 'NOTHING'
        for name, args in (
                ('on_setattr', ('arm_clothes', old, new)),
                ('_on_set_arm_clothes', (old,)),
                ('_callComponents', ('_on_set_arm_clothes', old))):
            try:
                fn = getattr(cav, name, None)
                if not callable(fn):
                    continue
                fn(*args)
                via = name
                break
            except Exception:
                continue
        # v2.95: the menu picker's FPS METHOD - the hand-model reload.
        # The picker fires it directly after an equip; always fire it here
        # too (it is what rebuilds the first-person hands from
        # fps_model_id via AddHandPrimitives).
        fps = 'NOTHING'
        for name, args in (
                ('OnReloadHandModel', ()),
                ('_callComponents', ('OnReloadHandModel',))):
            try:
                fn = getattr(cav, name, None)
                if not callable(fn):
                    continue
                fn(*args)
                fps = name
                break
            except Exception:
                continue
        _plog('[FPSARMS] arm-clothes refresh hero=%s item=%s via %s '
              'fps=%s (kept %s arm_clothes slots)'
              % (hero_id, item_id, via, fps, merged[1]))
    except Exception as _e:
        _plog('[FPSARMS] refresh error %r' % (_e,))


# logging shim on the Eclipse author's fps_model_id answer - separates
# "wrong skin resolved" from "right skin, no rebuild" in the next log.
try:
    _hmf_orig = hand_model_for

    def hand_model_for(self):
        _val = _hmf_orig(self)
        try:
            # v2.95: hand_model_id is a hot property - resolve ONLY when
            # the log cap still allows a line (the per-read resolve was
            # measurable game-thread cost).
            _seen = _fpsarms_state['hmf']
            _key = type(self).__name__
            if _seen.get(_key, 0) < 3:
                _seen[_key] = _seen.get(_key, 0) + 1
                _hid = _hero_id_deep(self)
                _item, _src = _fpsarms_resolve(_hid) if _hid else (0, 'none')
                _plog('[FPSARMS] hand_model_id -> %s (item=%s source=%s)'
                      % (_val, _item, _src))
        except Exception:
            pass
        return _val
    hand_model_for._fpsarms_shim = True
except Exception:
    pass


# v7.30R24: game-native EQUIP. The R23 probe showed PlayerAvatar has the
# game's own Arm* methods (ArmHeroSkin, ArmGunSkin, ArmGunGuise, ...).
# When the game arms a hero/gun with the real skin, substitute our pick
# so the skin flows through the game's own arming pipeline - the
# "equip by game, not by menu" channel. Menu systems stay untouched.
def _install_armstar_force(cls, found=None):
    try:
        cls_name = cls.__name__
    except Exception:
        return
    for meth in ('ArmHeroSkin', 'ArmGunSkin', 'ArmGunGuise'):
        try:
            prev = cls.__dict__.get(meth)
            if not callable(prev) or getattr(prev, '_treacky_arms', False):
                continue
            label = '%s.%s' % (cls_name, meth)

            def _make_arms(_prev, _label, _meth):
                def wrapper(self, *a, **k):
                    _arm_mark = False
                    _arm_hid = None
                    _arm_forced = None
                    _arm_change_hid = None
                    try:
                        na = list(a)
                        if _meth == 'ArmHeroSkin':
                            _native_gate = globals().get('native_arm_takeover')
                            _native_block = (callable(_native_gate)
                                             and _native_gate('striker'))
                            if (sync_attrs.get('bHeroSkinHack', False)
                                    and _striker_scene_gate()
                                    and not _native_block):
                                hid = None
                                for av in na:
                                    if isinstance(av, int) and av > 100:
                                        hid = av
                                        break
                                if not hid:
                                    hid = _hero_id_deep(self)
                                # v8.13: striker SWAP detection. The
                                # sig holds every hero's pick, so it
                                # does NOT change on Ethan -> Nova.
                                # v10.8: remember the requested hero here,
                                # but invalidate/repaint only AFTER the
                                # native arm returns.  The v10.7 pre-native
                                # repaint could re-show the old operator.
                                if hid:
                                    _arm_change_hid = hid
                                gf = globals().get('_get_forced_skin')
                                forced = gf(hid) if (hid and callable(gf)) \
                                    else None
                                # v2.107: a genuine carried striker item
                                # IS the user's equip - accept it and
                                # advance the saved pick (the r112 law:
                                # 'as long as the skin is equipped it
                                # should show').  Only a default/foreign
                                # re-arm gets re-skinned with the forced
                                # pick - never swap a real equip back to
                                # the stale saved skin (the saver bug).
                                _c2107 = None
                                _ci2107 = None
                                for i, av in enumerate(na):
                                    if isinstance(av, int) and i > 0 \
                                            and av != hid:
                                        _c2107 = av
                                        _ci2107 = i
                                        break
                                _cok2107 = True
                                if _c2107:
                                    try:
                                        _cat2107 = (globals().get(
                                            '_v109_category')
                                            or (lambda _x: None))(_c2107)
                                        if _cat2107 is not None \
                                                and _cat2107 != 'striker':
                                            _cok2107 = False
                                    except Exception:
                                        pass
                                if _c2107 and _cok2107:
                                    if hid:
                                        try:
                                            _rem2107 = globals().get(
                                                'cosmetic_remember_pick')
                                            if callable(_rem2107):
                                                _rem2107('ArmHeroSkin',
                                                         hid, _c2107,
                                                         persist=True)
                                        except Exception:
                                            pass
                                elif forced and _ci2107 is not None:
                                    na[_ci2107] = forced
                                    _herofx_note(_label,
                                                 '%s -> %s (equip by game)'
                                                 % (_label, forced))
                                    # Commit only after the original native
                                    # method returns successfully below.
                                    _arm_mark = True
                                    _arm_hid = hid
                                    _arm_forced = forced
                        else:
                            _native_gate = globals().get('native_arm_takeover')
                            _native_block = (callable(_native_gate)
                                             and _native_gate('weapon'))
                            wfx = (globals().get('_weaponfx_forced_for')
                                   if not _native_block else None)
                            if callable(wfx):
                                gun = None
                                for av in na:
                                    if isinstance(av, int):
                                        gun = av
                                        break
                                if gun:
                                    forced = wfx(gun)
                                    if forced:
                                        for i, av in enumerate(na):
                                            if isinstance(av, int) and i > 0\
                                                    and av != gun:
                                                na[i] = forced
                                                break
                                        _herofx_note(
                                            _label, '%s gun %s -> %s '
                                            '(equip by game)'
                                            % (_label, gun, forced))
                        a = na
                    except Exception:
                        pass
                    _arm_result = _prev(self, *a, **k)
                    if _arm_mark and _arm_result is not False:
                        try:
                            if _hero_apply_sig[0]:
                                _avatar_equip_sig[0] = _hero_apply_sig[0]
                                _avatar_equip_aid[0] = id(self)
                                _target_state = globals().get(
                                    'hero_equip_target')
                                if _target_state is not None:
                                    _target_state[0] = _arm_forced
                        except Exception:
                            pass
                    if _arm_change_hid and _arm_result is not False:
                        try:
                            on_hero_change(
                                _arm_change_hid, 'ArmHeroSkin')
                        except Exception:
                            pass
                    return _arm_result
                wrapper._treacky_arms = True
                return wrapper

            setattr(cls, meth, _make_arms(prev, label, meth))
            if found is not None:
                found.append(label)
        except Exception:
            continue


# Keep the ordinary equipped skin id aligned with the pick.  The native
# GetSkinStartAnim* getters are deliberately NOT wrapped: they drive the
# authentic intro cue, its attachments/effects, and the completion-to-idle
# transition.  Returning 0/None here was global animation suppression.
def _install_doll_state_force(cls, found=None):
    try:
        cls_name = cls.__name__
    except Exception:
        return
    meth = 'GetActualSkinItemId'
    try:
        prev = cls.__dict__.get(meth)
        if not callable(prev) or getattr(prev, '_treacky_dstate', False):
            return
        label = '%s.%s' % (cls_name, meth)

        def wrapper(self, *a, **k):
            try:
                # v2.104: key on the EQUIPPED ITEM, never bHeroSkinHack
                # (the r112 law), and admit the local display in a match
                # (the after-match MVP lineup renders while the scene is
                # still 'match').  Non-local dolls still fail closed via
                # _striker_native_local_display / _striker_scene_gate.
                if ((not _hero_in_match()
                     or _striker_native_local_display(self))
                        and (not _striker_native_combat_owned()
                             or _striker_native_local_display(self))
                        and _striker_scene_gate()):
                    hid = None
                    try:
                        hid = self.GetHeroId()
                    except Exception:
                        hid = None
                    if not hid:
                        hid = _hero_id_deep(self)
                    gf = globals().get('_get_forced_skin')
                    forced = gf(hid) if (hid and callable(gf)) else None
                    if forced:
                        _herofx_note(label, '%s -> %s (doll state)'
                                     % (label, forced))
                        return forced
            except Exception:
                pass
            return prev(self, *a, **k)
        wrapper._treacky_dstate = True
        wrapper._treacky_orig = prev
        setattr(cls, meth, wrapper)
        if found is not None:
            found.append(label)
    except Exception:
        pass


# v7.30R25: the combat avatar's OWN equipped-skin getter. The R23 probe
# showed CombatAvatar._GetActualHeroSkinItemId - the model build can
# read the avatar's actual skin through it. Match + LOCAL only.
def _install_avskin_force(cls, found=None):
    try:
        cls_name = cls.__name__
    except Exception:
        return
    for meth in ('_GetActualHeroSkinItemId', 'GetActualSkinItemId'):
        try:
            prev = cls.__dict__.get(meth)
            if not callable(prev) or getattr(prev, '_treacky_avsk',
                                             False):
                continue
            label = '%s.%s' % (cls_name, meth)

            def _make_avsk(_prev, _label):
                def wrapper(self, *a, **k):
                    try:
                        if (sync_attrs.get('bHeroSkinHack', False)
                                and not _striker_native_combat_owned()
                                and _hero_scene_stable() == 'match'
                                and _striker_is_local(self)):
                            hid = None
                            if a:
                                try:
                                    hid = _safe_int(a[0], 0) or None
                                except Exception:
                                    hid = None
                            if not hid:
                                hid = _hero_id_deep(self)
                            if hid:
                                gf = globals().get('_get_forced_skin')
                                forced = gf(hid) if (hid and callable(gf)) \
                                    else None
                                if forced:
                                    _herofx_note(
                                        _label, '%s -> %s (match, local '
                                        'skin state)' % (_label, forced))
                                    return forced
                    except Exception:
                        pass
                    return _prev(self, *a, **k)
                wrapper._treacky_avsk = True
                wrapper._treacky_orig = _prev
                return wrapper

            setattr(cls, meth, _make_avsk(prev, label))
            if found is not None:
                found.append(label)
        except Exception:
            continue


# v7.30R26: EQUIP BY GAME. R25 device evidence: nothing we force on
# the READ side moves the visible model - the doll state getters were
# never even called in the lobby, and the avatar state getters
# answered our pick 3x in match with no model change. The one channel
# that demonstrably moves the model EVERYWHERE (lobby doll, match
# avatar, vault, cards) is the game's OWN equip verb -
# PlayerAvatar.ArmHeroSkin - the same call the vault / hero-window UI
# makes when the player equips a skin. We call it ourselves now:
# lobby contexts only (never mid-match), once per pick signature and
# once per avatar instance, deferred 0.5 s on its own thread so it
# can never re-enter the frame that triggered it. Signature, call
# shape and result are logged so R27 can be surgical if it fails.
_avatar_equip_sig = [None]              # last sig we equipped
_avatar_seen_log_n = [0]                # v8.02: capture diagnostics
skip_notes = set()                  # v8.02: equip skip reasons
_avatar_equip_aid = [None]              # id(avatar) we equipped on
_avatar_equip_busy = [False]
_avatar_equip_probed = [False]          # ArmHeroSkin signature logged
_avatar_show_probed = {}                # trigger method -> return logged
_avatar_seen_ref = None                 # weakref -> last PlayerAvatar seen


def skip_note(reason):
    """v8.02: one-shot log for every silent skip in the equip path -
    the v8.01 device log could not tell 'no avatar seen' from 'seen but
    skipped', which is exactly what we need to know next time."""
    try:
        if reason in skip_notes:
            return
        skip_notes.add(reason)
        _plog('[V8] equip skipped: %s' % (reason,))
    except Exception:
        pass


def _avatar_note_seen(avatar):
    """v7.30R27: the ghsp wrapper hands us every live avatar that owns
    an ArmHeroSkin verb (= PlayerAvatar, the local player). Remember it
    (weakref) and try the equip-by-game call - _avatar_try_equip gates
    itself (hall only, once per pick sig + avatar instance)."""
    global _avatar_seen_ref
    try:
        if avatar is None:
            return
        try:
            _avatar_seen_ref = weakref.ref(avatar)
        except Exception:
            _avatar_seen_ref = None
        try:
            if _avatar_seen_log_n[0] < 5:
                _avatar_seen_log_n[0] += 1
                _plog('[V8] avatar seen %s id=0x%x'
                      % (type(avatar).__name__, id(avatar)))
        except Exception:
            pass
        _avatar_try_equip(avatar)
    except Exception:
        pass




def _install_avatar_equip_force(cls, found=None):
    """v7.30R26: trigger surface for the equip-by-game call. Wraps the
    PlayerAvatar read verbs the game hits when it builds the player's
    show model (cards / lobby / vault). v8.08: the armed-gun-skin
    getters are NOT wrapped - forcing them fed gun-skin ids into the
    game's hero-skin flow and the skin-choose screen said LOCKED
    (v8.07 device log: hero_choose_comp.OnChoose -> CallServerOld got
    a None proto). The wraps hand the live avatar instance to
    _avatar_try_equip and (once) log the answer shape."""
    try:
        if cls.__name__ != 'PlayerAvatar':
            return
    except Exception:
        return
    for meth in ('OnGetPlayerShowModel', 'GetAvatarModelShowInfo'):
        try:
            prev = getattr(cls, meth, None)
            if not callable(prev) or getattr(prev, '_treacky_gequip',
                                             False):
                continue
            label = 'PlayerAvatar.%s' % (meth,)

            def _make_gequip(_prev, _label, _meth):
                def wrapper(self, *a, **k):
                    rr = _prev(self, *a, **k)
                    try:
                        if _meth not in _avatar_show_probed:
                            _avatar_show_probed[_meth] = True
                            try:
                                _plog('[HERO-SCENE] %s -> %s'
                                      % (_label, repr(rr)[:200]))
                            except Exception:
                                pass
                        _avatar_try_equip(self)
                    except Exception:
                        pass
                    return rr
                wrapper._treacky_gequip = True
                # v8.07: probe_skin_fields reads the REAL code
                # object through _treacky_orig - without this the
                # data-write field probe found nothing (test DW1).
                wrapper._treacky_orig = _prev
                return wrapper

            setattr(cls, meth, _make_gequip(prev, label, meth))
            if found is not None:
                found.append(label)
        except Exception:
            continue


# v7.30R24: game-native EMOTE - when the user plays ANY emote (wheel in
# the lobby, wheel in match), the armed emote becomes OUR pick, through
# the game's own emote pipeline. The menu replay/feed stay untouched.
def _install_native_emote_force():
    found = []
    # hall: the proto the show model resolves for the armed emote
    try:
        _emc = sys.modules.get(
            'gclient.gamesystem.models.hall_emote_model_component')
        if _emc is None:
            _emc = __import__(
                'gclient.gamesystem.models.hall_emote_model_component',
                globals(), locals(), ['EmoteModelComponent'], 0)
        _cls = getattr(_emc, 'EmoteModelComponent', None)
        prev = _cls.__dict__.get('GetEmoteProto') \
            if isinstance(_cls, type) else None
        if callable(prev) and not getattr(prev, '_treacky_nem', False):
            def _make_nem(_prev):
                def wrapper(self, *a, **k):
                    try:
                        # v8.09: the auto-apply is REMOVED - the game
                        # asks GetEmoteProto at every hall re-entry and
                        # the forced answer was the "it auto plays emote
                        # when I get back to the lobby" report. Emotes
                        # apply through the user's own plays (the
                        # swap/anim/entry rewrites) and the menu
                        # replay. The wrap stays for the repair below.
                        pass
                    except Exception:
                        pass
                    # v8.09: the game's own GetEmoteProto raises on
                    # models without emote_item_id armed (the v8.07
                    # dump: HallDollShowModel). Fill 0 (= no emote) and
                    # retry - honest answer, no traceback.
                    try:
                        return _prev(self, *a, **k)
                    except AttributeError as _ae:
                        if 'emote_item_id' in str(_ae):
                            try:
                                self.emote_item_id = 0
                            except Exception:
                                pass
                            return _prev(self, *a, **k)
                        raise
                wrapper._treacky_nem = True
                return wrapper
            setattr(_cls, 'GetEmoteProto', _make_nem(prev))
            found.append('EmoteModelComponent.GetEmoteProto')
    except Exception:
        pass
    # match/shooting range: the emote that begins + its model info
    try:
        _cav = sys.modules.get(
            'gclient.gameplay.logic_base.entities.combat_avatar')
        if _cav is not None:
            for cls_name in ('PlayerCombatAvatar', 'CombatAvatar'):
                _cls = getattr(_cav, cls_name, None)
                if not isinstance(_cls, type):
                    continue
                for meth in ('BeginEmoteState', 'GetEmoteModelInfo'):
                    try:
                        prev = _cls.__dict__.get(meth)
                        if not callable(prev) or getattr(
                                prev, '_treacky_nem', False):
                            continue
                        label = '%s.%s' % (cls_name, meth)

                        def _make_nem2(_prev, _label):
                            def wrapper(self, *a, **k):
                                try:
                                    # v8.08: the rewrite is back for
                                    # the LOCAL avatar everywhere -
                                    # see _emote_wrap for the freeze
                                    # re-analysis (the real cause was
                                    # the game's own GetEmoteModelInfo
                                    # raise, repaired below).
                                    if (sync_attrs.get('bEmoteHack', False)
                                            and _safe_int(sync_attrs.get(
                                                'iEmoteSel', 0), 0) > 0):
                                        if _striker_is_local(self):
                                            fe = globals().get(
                                                '_get_forced_emote')
                                            item = (fe() if callable(fe)
                                                    else None)
                                            if item:
                                                na = list(a)
                                                for i, av in enumerate(na):
                                                    if isinstance(av, int):
                                                        na[i] = item
                                                        break
                                                _herofx_note(
                                                    _label,
                                                    '%s -> %s (native '
                                                    'emote)' % (_label,
                                                                item))
                                                a = na
                                        else:
                                            _ea_seen(_label,
                                                     _ea_arg_id(a, k))
                                except Exception:
                                    pass
                                # v8.08: the v8.07 emote dump PROVED
                                # the real implementation raises
                                # AttributeError (is_hall_emote) on
                                # match/range avatars - the emote state
                                # entered, the model info never came,
                                # the striker was stuck ('emote TPS
                                # not working', and the v8.03
                                # 'freeze'). Fill the missing attr and
                                # retry.
                                try:
                                    return _prev(self, *a, **k)
                                except AttributeError as _ae:
                                    if 'is_hall_emote' in str(_ae):
                                        try:
                                            self.is_hall_emote = False
                                        except Exception:
                                            pass
                                        return _prev(self, *a, **k)
                                    if '_space' in str(_ae):
                                        # v8.16: the EVA-01 refusal on
                                        # the v8.15 device -
                                        # PlayerCombatAvatarShooting-
                                        # Range has no _space at
                                        # cimp_emote.py:531. Heal it
                                        # with the live Space and
                                        # retry once.
                                        _sp16 = space_instance()
                                        if _sp16 is not None:
                                            try:
                                                self._space = _sp16
                                            except Exception:
                                                pass
                                            _plog('[V816] healed '
                                                  'missing _space '
                                                  '(%s)' % (_label,))
                                            return _prev(self, *a, **k)
                                    raise
                                except TypeError as _te15:
                                    if 'cannot unpack' in str(_te15):
                                        _plog('[V815] %s unpack '
                                              'guarded: %r'
                                              % (_label, _te15))
                                        return None
                                    raise
                            wrapper._treacky_nem = True
                            return wrapper
                        setattr(_cls, meth, _make_nem2(prev, label))
                        found.append(label)
                    except Exception:
                        continue
    except Exception:
        pass
    return found


def _install_v815_arrow_guard():
    """v8.15: arrow.LoadModelSkin raised KeyError 46x on the v8.14
    device (template rows without gun_skin_part_mat_list). The row
    heal above prevents the known key; this guard makes ANY
    missing-key or unpack failure in the arrow model-skin path
    non-fatal (log + honest skip) instead of killing the process.
    Idempotent."""
    found = []
    try:
        _mod = sys.modules.get(
            'gclient.gameplay.logic_base.entities.arrow')
        if _mod is None:
            return found

        def _make_guard(_prev, _label):
            def _guarded(*a, **k):
                try:
                    return _prev(*a, **k)
                except KeyError as _ke:
                    _plog('[V815] %s KeyError guarded: %r'
                          % (_label, _ke))
                    return None
                except TypeError as _te:
                    if 'cannot unpack' in str(_te):
                        _plog('[V815] %s unpack guarded: %r'
                              % (_label, _te))
                        return None
                    raise
            _guarded._treacky_v815 = True
            _guarded._treacky_orig = _prev
            return _guarded

        for _attr in ('LoadModelSkin', 'OnMissileModelLoad'):
            try:
                _fn = getattr(_mod, _attr, None)
                if callable(_fn) \
                        and not getattr(_fn, '_treacky_v815', False):
                    setattr(_mod, _attr,
                            _make_guard(_fn, 'arrow.%s' % (_attr,)))
                    found.append('arrow.%s' % (_attr,))
            except Exception:
                pass
        for _cname, _cls in list(vars(_mod).items()):
            if not isinstance(_cls, type):
                continue
            for _m in ('LoadModelSkin', 'OnMissileModelLoad'):
                try:
                    _prev = _cls.__dict__.get(_m)
                    if not callable(_prev) or getattr(
                            _prev, '_treacky_v815', False):
                        continue
                    setattr(_cls, _m,
                            _make_guard(_prev,
                                        'arrow.%s.%s' % (_cname, _m)))
                    found.append('arrow.%s.%s' % (_cname, _m))
                except Exception:
                    continue
    except Exception:
        pass
    return found


def _install_v815_mall_guard():
    """v8.15: the mall hero-window floor comp crashed twice on the
    v8.14 device - AttributeError(item_id) inside GetFloorProto via
    LeftSkinV6Intro. Heal item_id = 0 and retry (the pattern that
    fixed emote_item_id and is_hall_emote). Idempotent."""
    found = []
    try:
        _mod = sys.modules.get(
            'gclient.gamesystem.uihall.uihero.'
            'hero_window_model_comp')
        if _mod is None:
            return found
        for _cname, _cls in list(vars(_mod).items()):
            if not isinstance(_cls, type):
                continue
            _prev = _cls.__dict__.get('GetFloorProto')
            if not callable(_prev) or getattr(
                    _prev, '_treacky_v815', False):
                continue

            def _make_gp(_prev2, _label):
                def _gp(self, *a, **k):
                    try:
                        return _prev2(self, *a, **k)
                    except AttributeError as _ae:
                        if 'item_id' in str(_ae):
                            try:
                                self.item_id = 0
                            except Exception:
                                pass
                            try:
                                return _prev2(self, *a, **k)
                            except Exception as _e2:
                                _plog('[V815] %s guarded: %r'
                                      % (_label, _e2))
                                return None
                        raise
                _gp._treacky_v815 = True
                _gp._treacky_orig = _prev2
                return _gp

            setattr(_cls, 'GetFloorProto',
                    _make_gp(_prev,
                             '%s.GetFloorProto' % (_cname,)))
            found.append('%s.GetFloorProto' % (_cname,))
    except Exception:
        pass
    return found


hp_probed = [False]


def _is_wrapped_fn(f):
    """v8.32: TRUE for ANY of our wrapper families. The v8.31 device
    log (nexora_debug-5) proved the v8.16 guard and the v8.22 weapon
    add re-wrapped each other EVERY 10 s watcher pass (each installer
    only recognised its own marker) until the call chain passed the
    recursion limit - RecursionError killed the hall weapon adds
    (striker skins gone) and every call walked hundreds of layers
    (the lag). Every wrap site must check this, not its own marker."""
    try:
        return bool(getattr(f, '_treacky_wrap', False)
                    or getattr(f, '_treacky_v816', False)
                    or getattr(f, '_treacky_v822', False))
    except Exception:
        return False


def _install_v816_profile_guard():
    """v8.16: the profile page crashed on the v8.15 device -
    WeaponModel.base_graph_id missing inside
    hall_model_component.AddWeaponByEquipId (RefreshPersonalHomepa-
    geModel -> AddWeaponByEquipId:162 -> hall:818). Guard the hall
    component AND the homepage comps so a missing attr logs +
    skips instead of killing the profile; probe the homepage comp
    APIs so the next log shows the striker-skin channel for the
    profile / post-match screens. Idempotent."""
    found = []

    def _mk_guard(_prev, _label):
        def _g(*a, **k):
            try:
                return _prev(*a, **k)
            except AttributeError as _ae:
                _plog('[V816] %s guarded: %r' % (_label, _ae))
                return None
            except TypeError as _te:
                if 'cannot unpack' in str(_te):
                    _plog('[V816] %s unpack guarded: %r'
                          % (_label, _te))
                    return None
                raise
        _g._treacky_v816 = True
        _g._treacky_wrap = True      # v8.32: shared - see _is_wrapped_fn
        _g._treacky_orig = _prev
        return _g

    try:
        _mod = sys.modules.get(
            'gclient.gamesystem.models.hall_model_component')
        if _mod is not None:
            for _attr in ('AddWeaponByEquipId',):
                try:
                    _fn = getattr(_mod, _attr, None)
                    if callable(_fn) and not _is_wrapped_fn(_fn):
                        setattr(_mod, _attr, _mk_guard(
                            _fn, 'hall_model_component.%s'
                            % (_attr,)))
                        found.append(
                            'hall_model_component.%s' % (_attr,))
                except Exception:
                    pass
            for _cname, _cls in list(vars(_mod).items()):
                if not isinstance(_cls, type):
                    continue
                _prev = _cls.__dict__.get('AddWeaponByEquipId')
                if callable(_prev) and not _is_wrapped_fn(_prev):
                    setattr(_cls, 'AddWeaponByEquipId',
                            _mk_guard(
                                _prev,
                                '%s.AddWeaponByEquipId' % (_cname,)))
                    found.append(
                        '%s.AddWeaponByEquipId' % (_cname,))
    except Exception:
        pass
    try:
        _hp = sys.modules.get(
            'gclient.gamesystem.uihall.ui_personal_homepage_v2.'
            'components.personal_homepage_model_comp')
        if _hp is not None:
            for _cname, _cls in list(vars(_hp).items()):
                if not isinstance(_cls, type):
                    continue
                for _m in ('AddWeaponByEquipId',
                           'RefreshPersonalHomepageWeapon',
                           'RefreshPersonalHomepageModel',
                           '__refresh_node_component__'):
                    try:
                        _prev = _cls.__dict__.get(_m)
                        if not callable(_prev) \
                                or _is_wrapped_fn(_prev):
                            continue
                        setattr(_cls, _m, _mk_guard(
                            _prev, 'homepage.%s.%s'
                            % (_cname, _m)))
                        found.append('homepage.%s.%s'
                                     % (_cname, _m))
                    except Exception:
                        continue
            if not hp_probed[0]:
                hp_probed[0] = True
                for _cname, _cls in list(vars(_hp).items()):
                    if isinstance(_cls, type):
                        _names = sorted(
                            _m for _m in _cls.__dict__
                            if isinstance(_m, str))
                        if _names:
                            _plog('[V816] homepage probe %s apis=%d '
                                  '%r' % (_cname, len(_names),
                                          _names[:60]))
    except Exception:
        pass
    return found


# ============================================================
# v8.18: THE PROFILE / SHOWROOM WEAPON
# ============================================================
# The profile page builds its display weapon from the player's REAL
# equip state (HeroSelectModelCtrl.AddWeaponByEquipId /
# CreateWeaponCaseByItemProto) - our forced pick is not in that
# state, so the profile showed the default weapon ('melee not show
# on profile'). Wrap the builders: log their real call shapes
# (bounded, so a miss shows in the next device log), then run the
# full proven WEAPONFX apply chain on the case they built.
pw_seen = set()
# v8.19: the v8.18 device log showed HeroSelectModelCtrl.AddWeaponBy-
# EquipId firing constantly in the LOBBY (hero-select scene) with a
# fresh case each time - the profile wrap re-ran the full apply chain
# per call = duplicate work on top of the equip flow + model refresh
# storms (the lobby lag). Cooldown per (ctrl, equip): one apply per
# 60 s; and a case that already carries our pick is skipped outright.
pw_cool = {}


# ============================================================
# v8.22: THE SHOWROOM / PROFILE WEAPON CHANNELS
# ============================================================
# The v8.20 session-1 device log PROVED the profile/showroom builds
# its display weapon through HeroSelectModelCtrl.AddWeaponByEquipId
# (a=(33, 0, 101) - equip, skin_id=0, guise: the REAL equip state,
# which has no skin) - a class the R26 Doll hooks never covered, so
# the profile striker showed the DEFAULT weapon whatever the menu
# pick. The v8.18 answer (wrap + re-run the whole apply chain on the
# built case) caused re-apply spam and half-built cases; the v8.22
# answer is the R26 way: substitute the picked skin into the CALL
# ARGUMENTS and let the game's own builder run - plus the
# AddWeaponByEquipIdForHeroSkin sibling, which every showroom
# controller (and Doll) exposes and which is the channel a showing
# hero skin uses for its weapon.
sr_log = set()


def wrap_add_weapon(prev, cls_name, meth):
    def _add(self, *args, **kwargs):
        try:
            _striker_doll_note(self)
            ctrl_note(self)
        except Exception:
            pass
        _sub = None
        try:
            _equip = args[0] if args else kwargs.get('equip_id')
            if (sync_attrs.get('bSkinHack')
                    and _equip is not None and has_weapon_row(_equip)):
                new_skin = _get_forced_weapon_skin(_equip)
                if new_skin is not None:
                    _a = list(args)
                    if len(_a) >= 3 and _a[2] is not None:
                        _sub = 'guise'
                        _a[2] = new_skin
                    elif len(_a) >= 2:
                        _sub = 'skin'
                        _a[1] = new_skin      # v8.23: even when None
                    elif kwargs.get('guise_id') is not None:
                        _sub = 'guise-kw'
                        kwargs['guise_id'] = new_skin
                    else:
                        _sub = 'skin-kw'
                        kwargs['skin_id'] = new_skin   # v8.23: slotless
                    args = tuple(_a)
        except Exception:
            _sub = None
        try:
            _k = (cls_name, meth, args, tuple(sorted(kwargs)))
            if len(sr_log) < 12 and _k not in sr_log:
                sr_log.add(_k)
                _plog('[V822] %s.%s a=%r k=%r sub=%s'
                      % (cls_name, meth, args, kwargs, _sub))
        except Exception:
            pass
        try:
            return prev(self, *args, **kwargs)
        except AttributeError as _ae:
            # v8.16 guard semantics: the game's own adds can raise
            # AttributeError internally (the 'attached_weapon_case'
            # class of missing-attr failures seen live in the v8.20
            # log) - absorb it, never crash the caller.
            try:
                _k2 = (cls_name, meth, 'guarded')
                if len(sr_log) < 24 and _k2 not in sr_log:
                    sr_log.add(_k2)
                    _plog('[V822] %s.%s guarded: %r'
                          % (cls_name, meth, _ae))
            except Exception:
                pass
            return None
    _add._treacky_v822 = True
    _add._treacky_wrap = True       # v8.32: shared - see _is_wrapped_fn
    return _add


def install_showroom_weapon(cls, found):
    """Wrap AddWeaponByEquipId / AddWeaponByEquipIdForHeroSkin on a
    showroom controller with the R26 argument gate. Idempotent (the
    _treacky_v822 marker); inherited methods are wrapped at the class
    that defines them, never shadow-duplicated."""
    n0 = len(found)
    try:
        if not isinstance(cls, type):
            return found[n0:]
        for meth in ('AddWeaponByEquipId',
                     'AddWeaponByEquipIdForHeroSkin'):
            try:
                prev = cls.__dict__.get(meth)
                if not callable(prev):
                    continue
                if _is_wrapped_fn(prev):
                    continue
                # NOTE: if the v8.16 error guard already wrapped this
                # method, `prev` IS the guard - we wrap AROUND it, so
                # its AttributeError absorption stays in the chain
                # under our substitution.
                setattr(cls, meth,
                        wrap_add_weapon(prev,
                                              cls.__name__, meth))
                found.append('%s.%s' % (cls.__name__, meth))
            except Exception:
                continue
    except Exception:
        pass
    return found[n0:]


# ============================================================
# v8.37: HeroSkin.cpp contribution by @Zelewin, dump-audited and
# folded into the existing striker core (not executed as a second
# payload). Only channels missing from v8.36 are added here:
#   * ModelHeroAttachComp body-attach proto; idle/intro stay native;
#   * AvatarModel.LoadById, using the PROVEN real->forced model map;
#   * HeroSkinModelComponent primitive/effect reload resources.
# No extra thread, FIFO, catalog or transport. Every lookup uses
# sys.modules (the v8.31 boot-storm law), every wrapper is idempotent
# and signature-transparent, match forcing is LOCAL-only, and the
# Nova twin honesty window stays authoritative.
# ============================================================
BODY_SPECS = (
    ('gclient.gameplay.logic_base.comps.model_hero_attach_comp',
     'ModelHeroAttachComp'),
    ('gclient.gameplay.logic_base.models.avatar_model',
     'ModelHeroAttachComp'),
)
LOADER_SPECS = (
    ('gclient.gameplay.logic_base.models.avatar_model', 'AvatarModel'),
    ('gclient.gameplay.logic_base.entities.combatavatarmembers.cimp_model',
     'AvatarModel'),
)
HALL_SPECS = (
    ('gclient.gamesystem.models.hall_hero_skin_model_component',
     'HeroSkinModelComponent'),
    ('gclient.gamesystem.models.hall_show_model',
     'HeroSkinModelComponent'),
)
note_seen = set()


def _v837_note(tag, text):
    try:
        key = (tag, text)
        if key in note_seen or len(note_seen) >= 32:
            return
        note_seen.add(key)
        _plog('[V837] %s %s' % (tag, text))
    except Exception:
        pass


def _v837_local_avatar(obj):
    """Bounded owner/member walk; never a gc walk. Return the object in
    that chain which the existing local-player predicate accepts."""
    try:
        queue = [obj]
        seen = set()
        steps = 0
        while queue and steps < 16:
            cur = queue.pop(0)
            steps += 1
            if cur is None or id(cur) in seen:
                continue
            seen.add(id(cur))
            if _striker_is_local(cur):
                return cur
            for attr in ('owner', 'entity', 'combat_avatar', 'avatar',
                         'parent', 'master', 'follow_entity', 'ctrl_entity',
                         'bind_entity', 'source_avatar'):
                try:
                    nxt = getattr(cur, attr, None)
                except Exception:
                    continue
                if nxt is not None and id(nxt) not in seen:
                    queue.append(nxt)
    except Exception:
        pass
    return None


def match_pick(obj):
    """(local avatar, hero, skin id, authentic hero_skin_data row) or None. The
    contribution's ungated combat hooks are deliberately not used."""
    try:
        if not sync_attrs.get('bHeroSkinHack', False):
            return None
        # Native execution/Nova/model state is authoritative.  This older
        # real->forced resource mapper must not replace those stage resources.
        if _striker_native_combat_owned():
            return None
        if _hero_scene_stable() != 'match':
            return None
        if time.time() < twin_honest_until[0]:
            return None
        av = _v837_local_avatar(obj)
        if av is None:
            return None
        hid = _hero_id_deep(av)
        if not hid:
            return None
        sid = _get_forced_skin(hid)
        proto = _get_forced_hero_skin_proto(hid)
        if sid and proto is not None:
            return av, hid, sid, proto
    except Exception:
        pass
    return None


def hall_pick(obj):
    try:
        if not sync_attrs.get('bHeroSkinHack', False):
            return None
        if (_striker_native_combat_owned()
                and not _striker_native_local_display(obj)):
            return None
        if _hero_scene_stable() != 'hall':
            return None
        hid = _hero_id_deep(obj)
        if not hid:
            for attr in ('owner', 'model_owner', 'ctrl'):
                try:
                    hid = _hero_id_deep(getattr(obj, attr, None))
                except Exception:
                    hid = None
                if hid:
                    break
        if not hid:
            return None
        sid = _get_forced_skin(hid)
        proto = _get_forced_skin_proto(hid)
        if sid and proto is not None:
            return hid, sid, proto
    except Exception:
        pass
    return None


def wrap_body_getter(cls, meth, kind, found):
    try:
        prev = cls.__dict__.get(meth)
        if not callable(prev) or getattr(prev, '_treacky_v837', False):
            return

        def wrapper(self, *args, **kwargs):
            # Native animation selection is cue-driven.  In particular the
            # authentic fields are jetpack_skin_idleanim and
            # jetpack_skin_intro_idleanim; substituting lobby-item fields
            # here breaks CueIntroEnd -> _SwitchSkinIntroEndToIdle.
            result = prev(self, *args, **kwargs)
            if kind != 'proto':
                return result
            try:
                pick = match_pick(self)
                if pick is not None:
                    _av, _hid, sid, proto = pick
                    _v837_note('body-proto',
                               '%s -> authentic hero row %s (match, local)'
                               % (meth, sid))
                    return proto
            except Exception:
                pass
            return result
        wrapper._treacky_v837 = True
        wrapper._treacky_wrap = True
        wrapper._treacky_orig = prev
        setattr(cls, meth, wrapper)
        found.append('%s.%s' % (cls.__name__, meth))
    except Exception:
        pass


def wrap_model_loadbyid(cls, found):
    try:
        # LoadById is inherited from SimpleModel on the dump's AvatarModel;
        # getattr is intentional here. The marker prevents double wraps when
        # the same class is exported through cimp_model and avatar_model.
        prev = getattr(cls, 'LoadById', None)
        if not callable(prev) or getattr(prev, '_treacky_v837', False):
            return

        def wrapper(self, *args, **kwargs):
            try:
                old = args[0] if args else kwargs.get('model_id', None)
                if isinstance(old, int):
                    pick = match_pick(self)
                    if pick is not None:
                        # Never invent a replacement for an unmapped id: that
                        # was the v8.09 Nova-twin bug. Only the existing,
                        # cached real-skin -> forced-skin mapping is used.
                        mapping = _striker_model_map(pick[0])
                        new = mapping.get(old) if mapping else None
                        if new and new != old:
                            if args:
                                args = (new,) + args[1:]
                            else:
                                kwargs['model_id'] = new
                            _v837_note('LoadById', '%s -> %s (match, local)'
                                       % (old, new))
            except Exception:
                pass
            return prev(self, *args, **kwargs)
        wrapper._treacky_v837 = True
        wrapper._treacky_wrap = True
        wrapper._treacky_orig = prev
        setattr(cls, 'LoadById', wrapper)
        found.append('%s.LoadById' % cls.__name__)
    except Exception:
        pass


def wrap_hall_reload(cls, found):
    meth = 'ReloadHeroSkinPrimitivesAndEffects'
    try:
        prev = cls.__dict__.get(meth)
        if not callable(prev) or getattr(prev, '_treacky_v837', False):
            return

        def wrapper(self, *args, **kwargs):
            try:
                pick = hall_pick(self)
                if pick is not None:
                    _hid, sid, proto = pick
                    mid = _hero_proto_get(proto, 'model_id', None)
                    paths = _hero_proto_get(proto, 'model_resource_paths',
                                            None)
                    # Model id and resource paths are one atomic contract.
                    # Substitute both from the SAME lobby row, or leave the
                    # native call completely untouched.  Never combine a new
                    # model id with stale companion paths.
                    if mid and paths:
                        args = list(args)
                        if len(args) >= 2:
                            args[0] = mid
                            args[1] = paths
                        elif len(args) == 1:
                            args[0] = mid
                            kwargs['model_resource_paths'] = paths
                        else:
                            kwargs['model_unit_id'] = mid
                            kwargs['model_resource_paths'] = paths
                        args = tuple(args)
                        _v837_note(
                            'hall-reload',
                            'skin=%s atomic model/resources=%s'
                            % (sid, mid))
            except Exception:
                pass
            return prev(self, *args, **kwargs)
        wrapper._treacky_v837 = True
        wrapper._treacky_wrap = True
        wrapper._treacky_orig = prev
        setattr(cls, meth, wrapper)
        found.append('%s.%s' % (cls.__name__, meth))
    except Exception:
        pass


def install_hero_skin_contribution():
    """Called by the EXISTING 10 s idempotent striker watcher. No game
    imports and no additional worker are introduced by this contribution."""
    found = []
    for mod_name, cls_name in BODY_SPECS:
        try:
            mod = sys.modules.get(mod_name)
            cls = getattr(mod, cls_name, None) if mod is not None else None
            if not isinstance(cls, type):
                continue
            for meth, kind in (
                    ('GetBodyAttachModelHeroSkinProto', 'proto'),
                    ('GetBodyAttachModelSkinIdleAnim', 'idle'),
                    ('GetBodyAttachModelSkinIntroIdleAnim', 'intro')):
                wrap_body_getter(cls, meth, kind, found)
        except Exception:
            continue
    for mod_name, cls_name in LOADER_SPECS:
        try:
            mod = sys.modules.get(mod_name)
            cls = getattr(mod, cls_name, None) if mod is not None else None
            if isinstance(cls, type):
                wrap_model_loadbyid(cls, found)
        except Exception:
            continue
    for mod_name, cls_name in HALL_SPECS:
        try:
            mod = sys.modules.get(mod_name)
            cls = getattr(mod, cls_name, None) if mod is not None else None
            if isinstance(cls, type):
                wrap_hall_reload(cls, found)
        except Exception:
            continue
    if found:
        _v837_note('install', 'wrapped %r' % (found,))
    return found


# ============================================================
# v8.38: owner-supplied PlayerAvatar arm-skin getter snippet.
# The existing _treacky_armf layer owns MATCH + LOCAL forcing. This
# complementary _skhk layer covers HALL / PROFILE only, so it does not
# stack a second match force. It uses the payload's real _get_forced_skin
# (the snippet's _get_forced_hero_skin name does not exist here).
# ============================================================
arm_log = set()


def arm_note(meth, forced):
    try:
        if meth in arm_log or len(arm_log) >= 8:
            return
        arm_log.add(meth)
        _plog('[V838] PlayerAvatar.%s -> %s (hall)' % (meth, forced))
    except Exception:
        pass


def wrap_avatar_getter(cls, nm, found):
    try:
        orig = getattr(cls, nm, None)
        if not callable(orig) or getattr(orig, '_skhk', False):
            return

        def _w(self, *args, **kwargs):
            try:
                if (sync_attrs.get('bHeroSkinHack', False)
                        and _hero_scene_stable() == 'hall'):
                    hero_id = kwargs.get('hero_id', None)
                    if args:
                        hero_id = args[0]
                    if not hero_id:
                        hero_id = _hero_id_deep(self)
                    forced = _get_forced_skin(hero_id) if hero_id else None
                    if forced:
                        arm_note(nm, forced)
                        return forced
            except Exception:
                pass
            # Exact signature passthrough: no artificial hero_id argument
            # (the R26 zero-arg crash class), including feature-off/no-pick.
            return orig(self, *args, **kwargs)
        _w._skhk = True                 # owner snippet's marker, preserved
        _w._treacky_v838 = True
        _w._treacky_wrap = True
        _w._treacky_orig = orig
        setattr(cls, nm, _w)
        found.append('%s.%s' % (cls.__name__, nm))
    except Exception:
        pass


def install_avatar_arm_getters():
    """Install through the existing watcher; no game import/new thread."""
    found = []
    try:
        mod = sys.modules.get('gclient.framework.entities.avatar')
        cls = getattr(mod, 'PlayerAvatar', None) if mod is not None else None
        if not isinstance(cls, type):
            return found
        for nm in ('GetCurArmSkinItemId', 'GetActualArmSkinItemId'):
            wrap_avatar_getter(cls, nm, found)
    except Exception:
        pass
    return found

def _install_striker_skin_addon():
    """Wrap hero_skin_proto cached_propertys + GetHeroSkinProto + the
    equip/model getters + the model pipeline + the game's own Arm*
    equips on the avatar classes the block skips. Idempotent; returns
    what was wrapped this pass."""
    found = []
    for mod_name, cls_name in _HEROFX_SPECS:
        try:
            mod = sys.modules.get(mod_name)
            if mod is None:
                continue
            cls = getattr(mod, cls_name, None)
            if isinstance(cls, type):
                _install_hsp_force(cls, found, local_only=True)
                _install_ghsp_class(cls, found)
                _install_arm_force(cls, found)
                _install_model_force(cls, found)
                _install_unit_model_force(cls, found)
                # v10.12.2-lagfix-r1: the FIRST-PERSON hands channel.
                # unit_model_id/model_id is the body; the arms in a match
                # come from fps_model_id, which nothing applied while the
                # native striker layer owned combat. Installed here so it
                # covers the same avatar classes.
                _install_hand_model_native(cls, found)
                _install_armstar_force(cls, found)
                _install_avskin_force(cls, found)
                _install_avatar_equip_force(cls, found)
        except Exception:
            continue
    for cls_name in ('Doll', 'DollLike', 'CalculationDoll',
                     'BigHeadCalculationDoll'):
        try:
            _hd = sys.modules.get('gclient.gamesystem.entities.hall_doll')
            cls = getattr(_hd, cls_name, None) if _hd is not None else None
            if isinstance(cls, type):
                _install_hsp_force(cls, found, local_only=False)
                _install_doll_state_force(cls, found)
        except Exception:
            continue
    # v8.17: the PROFILE / after-match screen renders through
    # HeroSelectModelCtrl (showroom_component) - the v8.16 probe
    # showed it reads the same hero_skin_proto the lobby dolls
    # use, plus ShowHeroSkinModel / GetModelUnitID / AddWeaponByE-
    # quipId. Wrap it exactly like the lobby dolls (always-on:
    # the profile shows the LOCAL player). The module loads when
    # the profile first opens - the 10 s watcher picks it up.
    try:
        _sr = sys.modules.get(
            'gclient.framework.commoncomps.showroom_component')
        _srcls = getattr(_sr, 'HeroSelectModelCtrl', None) \
            if _sr is not None else None
        if isinstance(_srcls, type):
            _n17 = len(found)
            _install_hsp_force(_srcls, found, local_only=False)
            _install_ghsp_class(_srcls, found)
            _install_arm_force(_srcls, found)
            _install_model_force(_srcls, found)
            _install_unit_model_force(_srcls, found)
            _install_armstar_force(_srcls, found)
            _install_avskin_force(_srcls, found)
            _install_avatar_equip_force(_srcls, found)
            _n22 = len(found)
            install_showroom_weapon(_srcls, found)
            # HallModelComponent covers every showroom controller that
            # inherits the adds (ShowRoomHeroModelCtrl,
            # BillboardShowRoomHeroModelCtrl, WarehouseHeroModelCtrl...)
            _hmc = getattr(_sr, 'HallModelComponent', None) \
                if _sr is not None else None
            if isinstance(_hmc, type):
                install_showroom_weapon(_hmc, found)
            if len(found) > _n22:
                _plog('[V822] showroom weapon wrapped: %r'
                      % (found[_n22:],))
            if len(found) > _n17:
                _plog('[V817] showroom wrapped: %r'
                      % (found[_n17:],))
    except Exception:
        pass
    # v8.22: the personal-homepage model controller (its own
    # AddWeaponByEquipId, seen live in the v8.20 log) - same R26
    # argument gate as the showroom controllers.
    try:
        _hp2 = sys.modules.get(
            'gclient.gamesystem.uihall.ui_personal_homepage_v2.'
            'components.personal_homepage_model_comp')
        if _hp2 is not None:
            for _cname in ('PersonalHomepageModelCtrl',):
                _c2 = getattr(_hp2, _cname, None)
                if isinstance(_c2, type):
                    _n22b = len(found)
                    install_showroom_weapon(_c2, found)
                    if len(found) > _n22b:
                        _plog('[V822] homepage weapon wrapped: %r'
                              % (found[_n22b:],))
    except Exception:
        pass
    try:
        found.extend(_install_native_emote_force())
    except Exception:
        pass
    # v8.15: crash guards for the arrow loader + the mall floor
    # comp (both proved fatal on the v8.14 device).
    try:
        found.extend(_install_v815_arrow_guard())
    except Exception:
        pass
    try:
        found.extend(_install_v815_mall_guard())
    except Exception:
        pass
    try:
        found.extend(_install_v816_profile_guard())
    except Exception:
        pass
    # v8.37: the audited HeroSkin.cpp channels ride THIS watcher.
    try:
        found.extend(install_hero_skin_contribution())
    except Exception:
        pass
    # v8.38: complementary hall-only PlayerAvatar arm getters (_skhk).
    try:
        found.extend(install_avatar_arm_getters())
    except Exception:
        pass
    # v8.10: instances that read hero_skin_proto BEFORE this wrap
    # installed hold the honest value in their __dict__ cache - the
    # real cached_property never calls the wrapper again. Purge once
    # per pass that wrapped something, so the next read recomputes.
    try:
        if found:
            purge_skin_proto_cache()
    except Exception:
        pass
    return found


_striker_skin_addon_logged = [False]
_striker_match_probed = [False]
_striker_hall_probed = [False]


def _striker_hall_probe():
    """v7.30R24: ONE-SHOT, names only, watcher thread - the hall-side
    twin of the match probe. The home lobby model (HallDollShowModel)
    and its Doll still show no hero id and no paintable method on
    device; this line in the next log lists exactly which skin/model
    apis those classes (plus the hall space owner + the skin manager)
    actually have, so the lobby fix can target the real method."""
    try:
        import re as _re
        rx = _re.compile('skin|model|hero|guise|appear|shape|show|change',
                         _re.I)
        targets = []
        for mod_name, cls_name in (
                ('gclient.gamesystem.entities.hall_doll',
                 'HallDollShowModel'),
                ('gclient.gamesystem.entities.hall_doll', 'Doll'),
                ('gclient.gamesystem.uihall.warehouse_hero_model_ctrl',
                 'HallModelComponent'),
                ('gclient.gamesystem.uiskin.hero_skin_manager',
                 'HeroSkinManager'),
                ('gclient.gameplay.logic_base.entities.hero_avatar',
                 'HeroAvatar')):
            try:
                mod = sys.modules.get(mod_name)
                cls = getattr(mod, cls_name, None) if mod is not None \
                    else None
                if isinstance(cls, type):
                    targets.append((mod_name, cls_name, cls))
            except Exception:
                continue
        for mod_name, cls_name, cls in targets:
            try:
                names = sorted(m for m in cls.__dict__
                               if isinstance(m, str) and rx.search(m))
                if names:
                    _plog('[HERO-FX] hall-probe %s.%s apis=%d %r'
                          % (mod_name.rsplit('.', 1)[-1], cls_name,
                             len(names), names[:100]))
            except Exception:
                continue
        # v7.30R25: exact signatures of the lobby-model candidates, so
        # the next fix can CALL them instead of guessing
        try:
            _hd2 = sys.modules.get('gclient.gamesystem.entities.hall_doll')
            _doll = getattr(_hd2, 'Doll', None) if _hd2 is not None \
                else None
            if isinstance(_doll, type):
                sigs = []
                for m in ('GetActualSkinItemId',
                          'GetSkinStartAnimSkinItemId',
                          'GetSkinStartAnimSkinInfo', 'SetIsShowHeroSkin',
                          'CacheModel', 'ShowDisplayModel',
                          'ShowHeroSkinModel', 'GetModelUnitID',
                          'OnHallShowModelLoaded', 'ChangeArmClothes'):
                    try:
                        fn = _doll.__dict__.get(m)
                        if callable(fn):
                            sigs.append('%s%s' % (m, inspect.signature(fn)))
                    except Exception:
                        continue
                if sigs:
                    _plog('[HERO-FX] hall-probe Doll signatures: %r'
                          % (sigs,))
        except Exception:
            pass
        # what fields do the hero tables carry (base model ids?)
        try:
            for dn in ('gclient.data.hero_data',
                       'gclient.data.hero_skin_data'):
                dm = sys.modules.get(dn)
                if dm is None:
                    continue
                dd = getattr(dm, 'data', None)
                if hasattr(dd, 'keys') and len(dd):
                    k0 = list(dd.keys())[0]
                    row = dd.get(k0)
                    _plog('[HERO-FX] hall-probe %s keys=%r'
                          % (dn.rsplit('.', 1)[-1],
                             list(row.keys())[:40]
                             if hasattr(row, 'keys') else type(row).__name__))
        except Exception:
            pass
        try:
            sp = getattr(Space, '_instance', None)
            sp_owner = getattr(sp, 'owner', None)
            if sp_owner is not None:
                _plog('[HERO-FX] hall-probe space owner is %s.%r'
                      % (type(sp_owner).__module__.rsplit('.', 1)[-1],
                         type(sp_owner).__name__))
        except Exception:
            pass
    except Exception:
        pass


def _striker_match_probe():
    """v7.30R23: ONE-SHOT per session, NAMES ONLY, runs on our watcher
    thread (never the game thread, no object walks, no calls into the
    game - a filtered dir() of the combat classes plus the local
    avatar's type). The R22 device log proved the match model driver
    is none of the channels we hooked so far (block counters zero,
    GetHeroSkinProto 3x/match) - this line in the next log tells us
    which skin/model apis the combat avatar ACTUALLY has, so the next
    fix targets the real driver instead of guessing."""
    try:
        import re as _re
        rx = _re.compile('skin|model|hero|guise|appear|shape', _re.I)
        for mod_name, cls_name in _HEROFX_SPECS:
            try:
                mod = sys.modules.get(mod_name)
                cls = getattr(mod, cls_name, None) if mod is not None \
                    else None
                if not isinstance(cls, type):
                    continue
                names = sorted(m for m in cls.__dict__
                               if isinstance(m, str) and rx.search(m))
                if names:
                    _plog('[HERO-FX] match-probe %s.%s apis=%d %r'
                          % (mod_name.rsplit('.', 1)[-1], cls_name,
                             len(names), names[:140]))
            except Exception:
                continue
        try:
            la = globals().get('_local_combat_avatar')
            local = la() if callable(la) else None
            if local is not None:
                _plog('[HERO-FX] match-probe local avatar is %s.%r'
                      % (type(local).__module__.rsplit('.', 1)[-1],
                         type(local).__name__))
        except Exception:
            pass
    except Exception:
        pass


def _striker_skin_addon_watcher():
    """Avatar classes load at different times - retry (cheap, idempotent)
    until the wrapped property is in place, then keep checking slowly."""
    while True:
        try:
            found = _install_striker_skin_addon()
            try:
                lifecycle = globals().get('install_lifecycle')
                if callable(lifecycle):
                    found.extend(lifecycle())
            except Exception:
                pass
            try:
                zle_install = globals().get('_zle_install')
                if callable(zle_install):
                    zle_install()
            except Exception:
                pass
            if found and not _striker_skin_addon_logged[0]:
                _striker_skin_addon_logged[0] = True
                _plog('[HERO-SCENE] in-match skin channel wrapped %r'
                      % (found,))
            if not _striker_match_probed[0]:
                try:
                    if _hero_scene_stable() == 'match':
                        _striker_match_probed[0] = True
                        _striker_match_probe()
                except Exception:
                    pass
            if not _striker_hall_probed[0]:
                try:
                    if _hero_scene_stable() == 'hall':
                        _striker_hall_probed[0] = True
                        _striker_hall_probe()
                except Exception:
                    pass
        except Exception:
            pass
        try:
            time.sleep(10.0)
        except Exception:
            return


try:
    threading.Thread(target=_striker_skin_addon_watcher, daemon=True).start()
except Exception:
    pass


# ============================================================
# v7.30R21: MENU NAME SANITIZER (the "JSON format" striker names)
# ============================================================
# The R20 device log proved the game's skin protos are taggeddicts, not
# dict instances. The block's own feed builder falls back to
# str(skin_proto) for anything that is not a dict - which puts the
# whole dict repr into the menu's skin list ("written in JSON format").
# The block itself stays byte-verbatim; instead its builder global is
# REPLACED here with a name-safe version. The block's own 2 s sender
# loop looks the function up by name, so it serves the sanitized feed.
def _hero_feed_clean_name(raw, fallback):
    if raw is None:
        return fallback
    name = raw
    if not isinstance(name, str):
        try:
            name = str(name)
        except Exception:
            name = ''
    try:
        name = name.strip()
    except Exception:
        name = ''
    if (not name or name in ('None', 'True', 'False')
            or '{' in name or '[' in name or '}' in name
            or "='" in name or '"' in name
            or len(name) > 64):
        return fallback
    return name


def _build_hero_info_lines_r21():
    """Name-safe replacement for the block's feed builder (same rows,
    same order, same END - only the name extraction differs)."""
    try:
        HERO_G = globals().get('HERO') or {}
        HSI_G = globals().get('HERO_SKIN_INFO') or {}
        hd_mod = sys.modules.get('gclient.data.hero_data')
        hd_data = getattr(hd_mod, 'data', None) or {}
        lines = []
        for hero_id, entries in list(HERO_G.items()):
            hero_name = None
            try:
                hero_name = _hero_proto_get(hd_data.get(hero_id),
                                            'hero_name', None)
            except Exception:
                hero_name = None
            if not hero_name and entries:
                hero_name = entries[0]
            hero_name = _hero_feed_clean_name(hero_name,
                                              'Hero_%s' % hero_id)
            lines.append('H|%s|%s' % (hero_id, hero_name))
            for idx, skin_id in enumerate(entries[1:], start=1):
                skin_proto = HSI_G.get(skin_id)
                skin_name = None
                try:
                    skin_name = _hero_proto_get(skin_proto, 'name', None)
                except Exception:
                    skin_name = None
                skin_name = _hero_feed_clean_name(skin_name,
                                                  'Skin_%s' % skin_id)
                lines.append('K|%s|%s|%s' % (hero_id, idx, skin_name))
        lines.append('END')
        return '\n'.join(lines)
    except Exception as _nbe:
        try:
            _plog('[HEROFEED] sanitizer error %r' % (_nbe,))
        except Exception:
            pass
        try:
            return _bsb_build_hero_info_lines_backup()
        except Exception:
            return 'END'


try:
    _bsb_build_hero_info_lines_backup = globals().get(
        '_build_hero_info_lines')
    if callable(_bsb_build_hero_info_lines_backup):
        _build_hero_info_lines = _build_hero_info_lines_r21
        _plog('[HEROFEED] name sanitizer installed '
              '(taggeddict protos -> clean menu names)')
    else:
        _bsb_build_hero_info_lines_backup = None
except Exception:
    _bsb_build_hero_info_lines_backup = None


def _striker_collect_scene_objects(force=False):
    """v8.29: ONE guarded heap sweep per scene for halls + dolls +
    profile controllers. The v8.26-v8.28 device logs showed the three
    SEPARATE walks behind every paint pass costing 2.5-5.75 s (the
    lobby lag). Register-first: steady state never walks; an empty sweep
    retries at most every 5 s; a background thread never walks during
    the 2 s scene-settle window. Per-OBJECT dedup (id()), bounded
    12/64/32, early break when all caps are full."""
    try:
        scene_key = _scene_at[0]
    except Exception:
        scene_key = None
    now = time.time()
    try:
        hall_live = _reg_live(_striker_hall_models, 12)
        doll_live = _reg_live(_striker_doll_reg, 64)
        ctrl_live = _reg_live(ctrl_reg, 32)
    except Exception:
        hall_live, doll_live, ctrl_live = [], [], []
    try:
        same_scene = (_striker_doll_walk_scene[0] == scene_key)
        age = now - _striker_doll_walk_at[0]
        if not force and same_scene:
            if hall_live or doll_live or ctrl_live:
                return hall_live, doll_live, ctrl_live
            if age < 5.0:
                return hall_live, doll_live, ctrl_live
    except Exception:
        pass
    try:
        if (threading.current_thread() is not threading.main_thread()
                and (now - _scene_at[0]) < 2.0):
            return hall_live, doll_live, ctrl_live
    except Exception:
        pass
    try:
        # v8.33: hall machinery ONLY - never sweep the match/loading
        # heap. The v8.32 device log had paint passes of 20-46 s when
        # the walk ran during scene transitions (those heaps are the
        # biggest); in-match the registers are all we need anyway.
        try:
            if _hero_scene_stable() != 'hall':
                return hall_live, doll_live, ctrl_live
        except Exception:
            pass
        import gc as _gc
        hall_names = ('HallShowModel', 'HallDollShowModel')
        doll_names = ('Doll', 'DollLike', 'CalculationDoll',
                      'BigHeadCalculationDoll')
        ctrl_names = ('HeroSelectModelCtrl', 'PersonalHomepageModelCtrl')
        hall_classes = []
        doll_classes = []
        try:
            _hm = sys.modules.get('gclient.gamesystem.models.hall_show_model')
            if _hm is None:
                _hm = __import__('gclient.gamesystem.models.hall_show_model',
                                 globals(), locals(), ['HallShowModel'], 0)
            _c = getattr(_hm, 'HallShowModel', None)
            if isinstance(_c, type):
                hall_classes.append(_c)
        except Exception:
            pass
        try:
            _hd = sys.modules.get('gclient.gamesystem.entities.hall_doll')
            if _hd is None:
                _hd = __import__('gclient.gamesystem.entities.hall_doll',
                                 globals(), locals(),
                                 ['Doll', 'HallDollShowModel'], 0)
            _c = getattr(_hd, 'HallDollShowModel', None)
            if isinstance(_c, type):
                hall_classes.append(_c)
            for _name in doll_names:
                _c = getattr(_hd, _name, None)
                if isinstance(_c, type):
                    doll_classes.append(_c)
        except Exception:
            pass
        halls, dolls, ctrls = [], [], []
        hall_seen, doll_seen, ctrl_seen = set(), set(), set()
        # v8.34: TYPE-SET PREFILTER. The v8.33 walk hit its own 4 s
        # deadline on EVERY run (87k-290k of ~500k objects scanned) -
        # every object paid for type().__name__, id() and three tuple
        # membership scans, so it could never finish, every paint pass
        # carried a ~4 s walk (the "lil lag"), and the partial sweep
        # missed the real lobby doll. Now each object costs ONE set
        # lookup and only matches pay for id()/dedup. Exact classes
        # only - the registers, the Load/Reload wraps and the v8.34
        # ZLSKIN re-dress note cover anything the exact set misses.
        # Ctrls resolve from sys.modules ONLY (the no-import law).
        _hall_set = set(hall_classes)
        _doll_set = set(doll_classes)
        _ctrl_set = set()
        try:
            _pm = sys.modules.get(
                'gclient.gamesystem.uihall.ui_personal_homepage_v2.'
                'components.personal_homepage_model_comp')
            _c = getattr(_pm, 'PersonalHomepageModelCtrl', None)
            if isinstance(_c, type):
                _ctrl_set.add(_c)
        except Exception:
            pass
        try:
            _sm = sys.modules.get(
                'gclient.framework.commoncomps.showroom_component')
            _c = getattr(_sm, 'HeroSelectModelCtrl', None)
            if isinstance(_c, type):
                _ctrl_set.add(_c)
        except Exception:
            pass
        _walk_want = _hall_set | _doll_set | _ctrl_set
        # v8.33 (kept): SLICED (GIL released periodically) and hard
        # deadline-capped at 4 s.
        _walk_deadline = time.time() + 4.0
        _walk_t0 = time.time()
        _scanned = 0
        _capped = False
        for obj in _gc.get_objects():
            _scanned += 1
            if not (_scanned & 2047):
                try:
                    time.sleep(0.0005)
                except Exception:
                    pass
                if time.time() > _walk_deadline:
                    _capped = True
                    break
            if type(obj) not in _walk_want:
                continue
            try:
                oid = id(obj)
                _t = type(obj)
                if _t in _hall_set:
                    if oid not in hall_seen and len(halls) < 12:
                        halls.append(obj)
                        hall_seen.add(oid)
                elif _t in _doll_set:
                    if oid not in doll_seen and len(dolls) < 64:
                        dolls.append(obj)
                        doll_seen.add(oid)
                else:
                    if oid not in ctrl_seen and len(ctrls) < 32:
                        ctrls.append(obj)
                        ctrl_seen.add(oid)
                if (len(halls) >= 12 and len(dolls) >= 64
                        and len(ctrls) >= 32):
                    break
            except Exception:
                continue
        try:
            _plog('[V834] scene walk %s in %.2fs (scanned=%d objs, '
                  'halls=%d dolls=%d ctrls=%d)'
                  % ('capped' if _capped else 'done',
                     time.time() - _walk_t0, _scanned, len(halls),
                     len(dolls), len(ctrls)))
        except Exception:
            pass
        try:
            del _striker_hall_models[:]
            for obj in halls:
                try:
                    _striker_hall_models.append(weakref.ref(obj))
                except Exception:
                    pass
        except Exception:
            pass
        for obj in dolls:
            try:
                _striker_doll_note(obj)
            except Exception:
                pass
        for obj in ctrls:
            try:
                ctrl_note(obj)
            except Exception:
                pass
        try:
            ctrl_stash[0] = (time.time(), ctrls[:])
            _striker_doll_walk_at[0] = time.time()
            _striker_doll_walk_scene[0] = scene_key
        except Exception:
            pass
        return halls, dolls, ctrls
    except Exception as _walk_err:
        try:
            _plog('[V829] combined scene walk failed: %r' % (_walk_err,))
        except Exception:
            pass
        return hall_live, doll_live, ctrl_live


def _striker_live_hall_models():
    """v8.29: halls come from the shared one-sweep collector - the three
    separate ~2 s heap walks per paint pass were the lobby lag in the
    v8.26-v8.28 device logs."""
    try:
        halls, _dolls, _ctrls = _striker_collect_scene_objects()
        if halls:
            return halls
    except Exception:
        pass
    return _reg_live(_striker_hall_models, 12)


# #======================================================================
# //  STRIKER.PY
# //
# //  This file is for: STRIKER: the local-player auth, the hero-skin doll display, the emote-class hooks, the exec gate, the auto-debug tick.
# //
# //  Part of the split TREACKY BS payload (v2.112).  The runtime
# //  file payload/skins_payload.py is GENERATED: run
# //  tools/build_payload.py after editing these modules.
# #======================================================================


# ============================================================
# v2.124: twin-dissolve hooks (moved from core.py in the rewrite).
# Hosted here until the display rewrite absorbs the HallShowModel/
# Doll display chain into one module.
# ============================================================
# v2.124: twin-dissolve hooks (evo-after-inspect). The dump proves
# HallShowModel.StartTwinDissolve(material_path, target_model_id,
# target_skin_item_id, duration) + CueExecuteTwinDissolve drive the
# skin-transform swap; the payload never touched them. Wrap both: pass the
# game's own calls through, log bounded evidence, and when the game offers NO
# target skin while the user has a forced skin for the same model, offer it as
# the dissolve target (the transform must land on the FORCED skin).
twin_state = {'done': False, 'logged': 0, 'rewritten': 0}


def install_twin_hooks():
    if twin_state['done']:
        return True
    mod = sys.modules.get('gclient.gamesystem.models.hall_show_model')
    if mod is None:
        try:
            mod = __import__('gclient.gamesystem.models.hall_show_model',
                             globals(), locals(), ['x'], 0)
        except Exception:
            return False
    cls = getattr(mod, 'HallShowModel', None)
    if not isinstance(cls, type):
        return False
    done = []
    for mname, slot in (('StartTwinDissolve', 2), ('CueExecuteTwinDissolve', 0)):
        prev = cls.__dict__.get(mname)
        if not callable(prev) or getattr(prev, '_treacky_twin24', False):
            continue

        def _make(_prev, _name, _slot):
            def wrapper(self, *a, **k):
                try:
                    twin_state['logged'] += 1
                    if (twin_state['logged'] <= 8
                            or twin_state['logged'] % 50 == 0):
                        _plog('[TWIN24] %s args=%r kwargs=%r'
                              % (_name, a[:4], dict(list(k.items())[:4])))
                    if _name == 'StartTwinDissolve':
                        cur = 0
                        try:
                            if len(a) > _slot:
                                cur = _safe_int(a[_slot], 0)
                            elif 'target_skin_item_id' in k:
                                cur = _safe_int(k.get('target_skin_item_id'), 0)
                        except Exception:
                            cur = 0
                        if not cur:
                            forced = 0
                            try:
                                _sv24 = (globals().get('MELEE_SAVED')
                                         or {})
                                forced = _safe_int(_sv24.get('item_id'), 0)
                            except Exception:
                                forced = 0
                            if forced:
                                if len(a) > _slot:
                                    a = (a[:_slot] + (forced,)
                                         + a[_slot + 1:])
                                else:
                                    k['target_skin_item_id'] = forced
                                twin_state['rewritten'] += 1
                                _plog('[TWIN24] offered forced item=%d as '
                                      'dissolve target' % forced)
                except Exception:
                    pass
                return _prev(self, *a, **k)
            wrapper._treacky_twin24 = True
            return wrapper

        try:
            setattr(cls, mname, _make(prev, mname, slot))
            done.append(mname)
        except Exception:
            pass
    if done:
        _plog('[TWIN24] hooks installed=%r' % (done,))
        twin_state['done'] = True
    return twin_state['done']


