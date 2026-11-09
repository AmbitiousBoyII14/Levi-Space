# ============================================================
# UNLOCKS.PY (payload feature module)
# PROVIDES: _unlock_should_force, _install_unlock_hooks, _emote_hook_ok, _install_emote_unlock_hooks, _install_hall_item_emote_unlock, _unlock_dump, exec_gate, apply_exec_skin, purge_skin_proto_cache, twin_honest_required, _install_v810_twin_hook, _install_v810_camera_hook, _install_v810_anim_check_hook, is_catalog_emote, ... +94 more | _EMOTE_HOOK_TOKENS, _EMOTE_HOOK_SKIP, MERGED_DAGGER_ROWS, DAGGER_ROWS, _COSM_CACHE, _COSM_PREFIX, _ZLU_PROTO_TABLES, UDP_EXEC_PORT, EXEC_PKG, EXEC_PROTO, ...
# REQUIRES: shared namespace (config/names/main/game_api/catalog);
#           game modules imported inline, verified against the dumps.
# ABI: _get_forced_skin = get_forced_skin stays LAST.
# ============================================================
"""Unlockers + forced-skin resolution: the v8.42 forced-skin/hero selection core (_v842_* family), vault/avatar/banner/emote unlockers, native unlock-equip bridge."""

# #======================================================================
# //  UNLOCKS.PY
# //
# //  This file is for: UNLOCKS: the vault ownership force (IHallItems.HasItemByItemId), the v832/v839 hall-item hooks, the unlock gates - the melee, striker, emote, Collection + Consumable families.
# //
# //  Part of the split TREACKY BS payload (v2.112).  The runtime
# //  file payload/skins_payload.py is GENERATED: run
# //  tools/build_payload.py after editing these modules.
# #======================================================================
def _unlock_should_force(gate):
    if not gate:
        return False
    # v8.33: "Unlock items" is REMOVED by user request - a stale
    # bUnlockAll=True from an old config must not force anything.
    # v7.22: "Unlock emotes" now behaves like "unlock everything" - the
    # point is the game's own vault/collection letting you pick emotes
    # there, not our menu forcing one. Every ownership predicate opens.
    if sync_attrs.get('bUnlockEmotes', False):
        return True
    return bool(sync_attrs.get(gate, False))


def _install_unlock_hooks(verbose=True):
    """Wrap the client's own ownership predicates - only while a switch is on."""
    if not _unlock_enabled():
        return []          # nothing is touched while the feature is off
    found = []
    refused = []
    for mod_name, mod in list(sys.modules.items()):
        if not mod_name.startswith('gclient') or mod is None:
            continue
        short = mod_name.rsplit('.', 1)[-1].lower()
        if not any(h in short for h in _UNLOCK_MODULE_HINT):
            continue
        for attr in dir(mod):
            if not _unlock_gate(attr):
                continue
            fn = getattr(mod, attr, None)
            if isinstance(fn, type) or not callable(fn):
                refused.append('%s.%s(not a function)' % (short, attr))
                continue
            if getattr(fn, '_treacky_unlock', False):
                found.append('%s.%s' % (short, attr))
                continue
            try:
                sig = inspect.signature(fn)
                n = len([p for p in sig.parameters.values()
                         if p.default is p.empty and
                         p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)])
                if n > 2:
                    refused.append('%s.%s(arity %d)' % (short, attr, n))
                    continue
            except Exception:
                refused.append('%s.%s(no signature)' % (short, attr))
                continue

            def _make(_prev, _key, _label):
                def wrapper(*a, **k):
                    if _unlock_should_force(_key):
                        return True
                    return _prev(*a, **k)
                wrapper._treacky_unlock = True
                wrapper._label = _label
                return wrapper
            label = '%s.%s' % (short, attr)
            key = _unlock_gate(attr)
            try:
                setattr(mod, attr, _make(fn, key, label))
                found.append('%s [%s]' % (label, key))
            except Exception as e:
                refused.append('%s(%r)' % (label, e))
    # v7.25: the v7.24 device log proved the vault's emote/warehouse
    # logic lives as CLASS METHODS (warehouse_hero_model_ctrl.* etc.) -
    # the module-level pass above can never see them. Same endings, now
    # on classes inside hint modules; wrapped on the class itself so
    # every instance answers, with the descriptor type preserved.
    try:
        for mod_name, mod in list(sys.modules.items()):
            if not mod_name.startswith('gclient') or mod is None:
                continue
            short = mod_name.rsplit('.', 1)[-1].lower()
            if not any(h in short for h in _UNLOCK_MODULE_HINT):
                continue
            for attr in dir(mod):
                cls = getattr(mod, attr, None)
                if not isinstance(cls, type):
                    continue
                for meth in dir(cls):
                    key = _unlock_gate(meth)
                    if not key:
                        continue
                    try:
                        static = inspect.getattr_static(cls, meth)
                    except Exception:
                        continue
                    if getattr(static, '_treacky_unlock', False):
                        found.append('%s.%s.%s' % (short, attr, meth))
                        continue
                    prev = static.__func__ if isinstance(
                        static, (staticmethod, classmethod)) else static
                    if not callable(prev) or isinstance(prev, type):
                        continue
                    try:
                        sig = inspect.signature(prev)
                        n = len([p2 for p2 in sig.parameters.values()
                                 if p2.default is p2.empty and
                                 p2.kind in (p2.POSITIONAL_ONLY,
                                             p2.POSITIONAL_OR_KEYWORD)])
                        if n > 3:
                            continue
                    except Exception:
                        continue

                    def _mkc(_prev, _key, _label):
                        def cwrapper(*a, **k):
                            if _unlock_should_force(_key):
                                return True
                            return _prev(*a, **k)
                        cwrapper._treacky_unlock = True
                        cwrapper._label = _label
                        return cwrapper
                    label = '%s.%s.%s' % (short, attr, meth)
                    try:
                        cw = _mkc(prev, key, label)
                        if isinstance(static, staticmethod):
                            setattr(cls, meth, staticmethod(cw))
                        elif isinstance(static, classmethod):
                            setattr(cls, meth, classmethod(cw))
                        else:
                            setattr(cls, meth, cw)
                        found.append('%s [%s]' % (label, key))
                    except Exception:
                        pass
    except Exception:
        pass
    _UNLOCK_HOOKED[:] = found
    _UNLOCK_REFUSED[:] = refused
    # v7.23: every callable with 'emote' in its name that the scan saw but
    # did not hook - this is how the vault's emote list check gets found
    # instead of guessed.
    emote_raw = []
    bag_cands = []
    _PRI = ('own', 'unlock', 'canuse', 'can_use', 'free', 'valid',
            'available', 'lock')

    def _emname(nm):
        return 'emote' in str(nm).lower().replace('remote', '')

    try:
        for mod_name, mod in list(sys.modules.items()):
            if not mod_name.startswith('gclient') or mod is None:
                continue
            short = mod_name.rsplit('.', 1)[-1].lower()
            emote_mod = ('emote' in short or 'vault' in short
                         or 'warehouse' in short or 'wardrobe' in short
                         or 'collection' in short)
            bag_mod = any(t in short for t in
                          ('bag', 'inventory', 'item', 'warehouse',
                           'vault', 'collection'))
            if not emote_mod and not bag_mod:
                continue
            for attr in dir(mod):
                fn = getattr(mod, attr, None)
                if isinstance(fn, type):
                    try:
                        meths = [m for m in dir(fn)
                                 if callable(getattr(fn, m, None))]
                    except Exception:
                        meths = []
                    for meth in meths:
                        ml = meth.lower()
                        if _emname(meth):
                            # ownership-looking names go FIRST - the v7.24
                            # 40-cap drowned them in Play/Show noise.
                            pri = 0 if any(t in ml for t in _PRI) else 1
                            emote_raw.append(
                                (pri, '%s.%s.%s' % (short, attr, meth)))
                        elif bag_mod and any(t in ml for t in
                                             ('own', 'unlock', 'count',
                                              'num')):
                            if len(bag_cands) < 40:
                                bag_cands.append('%s.%s.%s'
                                                 % (short, attr, meth))
                elif callable(fn) and not isinstance(fn, type):
                    low = attr.lower()
                    if emote_mod and _emname(attr):
                        emote_raw.append((1, '%s.%s' % (short, attr)))
                    elif bag_mod and any(t in low for t in
                                         ('count', 'num', 'own', 'has')):
                        if len(bag_cands) < 40:
                            bag_cands.append('%s.%s' % (short, attr))
    except Exception:
        pass
    emote_raw.sort(key=lambda x: x[0])
    emote_cands = [n for _, n in emote_raw]
    sig = tuple(sorted(found))
    if verbose and sig != _UNLOCK_SIG[0]:
        _UNLOCK_SIG[0] = sig
        _plog('[UNLOCK] predicates hooked=%d %r refused=%d %r'
              % (len(found), found[:10], len(refused), refused[:8]))
        _plog('[EMOTE-CAND] methods+modules=%d %r'
              % (len(emote_cands), emote_cands[:80]))
        if bag_cands:
            _plog('[BAG-CAND] count-style apis=%d %r'
                  % (len(bag_cands), bag_cands[:24]))
    return found


# v7.24: the vault emote unlock, take two. The module-level predicate
# scan never finds the vault's emote check because it lives as a method
# on a UI class (emote_comp.EmoteWheelComp & friends). Scan hint modules
# for emote-named METHODS too and wrap them while Unlock emotes is on.
_emote_hooks_last = [None]
# v7.25: tightened after the v7.24 device log - 'check' wrapped
# CheckEmoteCollision/CheckTalentRemoteShotDamageUp ("REMote" contains
# "emote"!), and 'has'/'active' added nothing. Ownership-ish only.
_EMOTE_HOOK_TOKENS = ('own', 'unlock', 'canuse', 'can_use',
                      'free', 'valid', 'available', 'purchased',
                      'bought', 'enable')
_EMOTE_HOOK_SKIP = ('get', 'load', 'query', 'fetch', 'list', 'find',
                    'dump', 'log', 'send', 'add', 'remove', 'del',
                    'play', 'show', 'anim')


def _emote_hook_ok(name):
    low = str(name).lstrip('_').lower()
    # v7.25: 'remote' contains 'emote'; strip it first or
    # CheckTalentRemoteShotDamageUp gets forced True in matches.
    if 'emote' not in low.replace('remote', ''):
        return False
    if low.startswith(_EMOTE_HOOK_SKIP):
        return False
    if any(b in low for b in _UNLOCK_BLOCK):
        return False
    if any(b in low for b in ('collision', 'timer', 'tick', 'talent',
                              'prompt', 'wallcheck', 'attach')):
        return False
    return any(t in low for t in _EMOTE_HOOK_TOKENS)


def _install_emote_unlock_hooks():
    """v7.24: wrap every emote-named ownership predicate - module level
    AND class methods - so the game's own vault marks emotes as owned.
    (Not _install_emote_hooks - that one is the v6 emote APPLY installer.)"""
    if not _unlock_enabled():
        return []

    def _arity(fn, cap=3):
        try:
            sig = inspect.signature(fn)
            return len([p for p in sig.parameters.values()
                        if p.default is p.empty and
                        p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)])
        except Exception:
            return cap + 1

    wrapped = []

    def _wrap(owner, name, prev, label):
        def wrapper(*a, **k):
            if True:  # v2.113: per-item fine gates below
                return True
            return prev(*a, **k)
        wrapper._treacky_unlock = True
        wrapper._label = label
        try:
            # keep the descriptor type: a staticmethod replaced by a
            # plain function would gain a phantom self when called via
            # an instance.
            static = None
            try:
                static = inspect.getattr_static(owner, name)
            except Exception:
                pass
            if isinstance(static, staticmethod):
                setattr(owner, name, staticmethod(wrapper))
            elif isinstance(static, classmethod):
                setattr(owner, name, classmethod(wrapper))
            else:
                setattr(owner, name, wrapper)
            wrapped.append(label)
        except Exception:
            pass

    try:
        for mod_name, mod in list(sys.modules.items()):
            if not mod_name.startswith('gclient') or mod is None:
                continue
            short = mod_name.rsplit('.', 1)[-1].lower()
            if not any(h in short for h in _UNLOCK_MODULE_HINT):
                continue
            for attr in dir(mod):
                fn = getattr(mod, attr, None)
                if isinstance(fn, type):
                    for meth in dir(fn):
                        if not _emote_hook_ok(meth):
                            continue
                        # (v7.26 tracer shares this loop shape below)
                        try:
                            mf = getattr(fn, meth, None)
                        except Exception:
                            continue
                        if (not callable(mf) or isinstance(mf, type)
                                or getattr(mf, '_treacky_unlock', False)):
                            continue
                        if _arity(mf) > 3:
                            continue
                        _wrap(fn, meth, mf,
                              '%s.%s.%s' % (short, attr, meth))
                elif (callable(fn) and not isinstance(fn, type)
                        and _emote_hook_ok(attr)
                        and not getattr(fn, '_treacky_unlock', False)
                        and _arity(fn) <= 3):
                    _wrap(mod, attr, fn, '%s.%s' % (short, attr))
    except Exception:
        pass
    return wrapped


# v7.28: the v7.26 tracer is RETIRED - it found the vault's emote
# ownership source on device ([EMOTE-CALL] cimp_hall_item.IHallItems.
# HasItemByItemId / _HasItemById / ItemCountByItemId) and wrapping 513
# callables "just to watch" is needless risk on match classes. The
# by-ID plan now runs for real, directly on that source.
_hall_item_done = [False]


def _install_hall_item_emote_unlock():
    """v7.28: the vault emote unlock, direct hit. While Unlock emotes is
    on, emote-range item ids (604...) answer OWNED from the game's own
    hall-item store - the vault emote list populates from it."""
    if not _unlock_enabled() or _hall_item_done[0]:
        return 0
    n = 0
    try:
        for mod_name, mod in list(sys.modules.items()):
            if not mod_name.startswith('gclient') or mod is None:
                continue
            if mod_name.rsplit('.', 1)[-1] != 'cimp_hall_item':
                continue
            cls = getattr(mod, 'IHallItems', None)
            if not isinstance(cls, type):
                continue
            for meth, kind in (('HasItemByItemId', 'bool'),
                               ('_HasItemById', 'bool'),
                               ('ItemCountByItemId', 'count')):
                try:
                    static = inspect.getattr_static(cls, meth)
                except Exception:
                    continue
                if getattr(static, '_treacky_unlock', False):
                    continue
                prev = static.__func__ if isinstance(
                    static, (staticmethod, classmethod)) else static
                if not callable(prev):
                    continue

                def _mk(_prev, _kind, _label):
                    def iwrapper(*a, **k):
                        if True:  # v2.113: per-item fine gates below
                            for _x in a:
                                if (isinstance(_x, int)
                                        and should_unlock(_x)):
                                    if _kind == 'count':
                                        try:
                                            _r = _prev(*a, **k)
                                            if isinstance(_r, int) and _r > 0:
                                                return _r
                                        except Exception:
                                            pass
                                        return 1
                                    return True
                        return _prev(*a, **k)
                    iwrapper._treacky_unlock = True
                    iwrapper._label = _label
                    return iwrapper
                try:
                    w = _mk(prev, kind, 'IHallItems.%s' % meth)
                    if isinstance(static, staticmethod):
                        setattr(cls, meth, staticmethod(w))
                    elif isinstance(static, classmethod):
                        setattr(cls, meth, classmethod(w))
                    else:
                        setattr(cls, meth, w)
                    n += 1
                except Exception:
                    pass
            break
    except Exception:
        pass
    if n:
        _hall_item_done[0] = True
        _plog('[EMOTE-OWN] IHallItems wrapped=%d - vault emote ownership '
              'forced while Unlock emotes is on' % n)
    return n


def _unlock_dump():
    # v8.02: unlock is REMOVED (R27). This dump was the last living
    # piece of it - a full gclient module scan (0.5-1.3 s of frozen UI
    # per pass) that also made the log claim unlock gates were on.
    return []


# names the tick uses
_emote_gate = _ea_gate
_emote_forced = _get_forced_emote


# ============================================================
# v8.10: THE ORIGINAL v7.30 TPS-EMOTE SKIN CHANNEL, PORTED
# ============================================================
# The v8.09 device log proved the third-person body the player SEES
# during gameplay emotes / sprays (the TPS camera view) is NOT built
# from our wrapped getters (they all fired, the body stayed default):
# CombatAvatar.hero_skin_proto and PlayerCombatAvatar.hero_skin_proto
# are cached_property descriptors and the game builds the TPS body
# from THAT. The original BSB mod hooked this property on every
# avatar/doll class (its "hero_skin_proto v2" block) - that is the
# code the user means by "go to 7.30 original and take the TPS emote
# code". Ported with harder gates: LOCAL avatar only, MATCH only, and
# only while an emote/TPS window is open - so the Nova twin skill
# (no emote, no TPS camera) and enemy avatars stay honest.

purge_at = [0.0]      # v8.11: the purge walks the whole heap -
                            # never more than one per 5 s (the v8.10
                            # device log: ~1.2 s stalls per emote press)


exec_skin_at = {}       # per-class cooldown for the exec-skin
                              # apply
exec_skin_done = set()  # skin ids WE armed via the pipeline
exec_tick_at = [0.0]    # _esp_aim_tick throttle (one try per 2 s)
exec_walk_at = [0.0]    # last-resort heap walk throttle (30 s)
exec_diag_at = [0.0]    # sampled gate diagnostics (30 s)


def exec_gate(reason):
    """Sampled (once per 30 s) note of WHY the exec-skin apply is not
    running. The v8.11 device log had ZERO [V811] lines and no way to
    tell which gate blocked - this makes the next log say it."""
    try:
        now = time.time()
        if now - exec_diag_at[0] < 30.0:
            return None
        exec_diag_at[0] = now
        _plog('[V812] exec-skin gate: %s' % (reason,))
    except Exception:
        pass
    return None


def apply_exec_skin():
    """v8.11: THE v7.30R6 'striker FPS code', ported. The game's own
    EXECUTE-SKIN pipeline (finishers run in FPS with full controls) is
    the game's FPS-safe mid-match skin swap:

        _PrepareExecuteSkinSwitch -> CueChangeExecuteHeroSkin ->
        _TryApplyExecuteSkin(skin_item_id) -> _OnExecuteSkinReloaded

    Calling the apply primitive with the picked skin's ITEM id arms the
    skin through the GAME'S OWN model state - the FPS view AND the TPS
    emote/spray body are built from it (not emote-based, exactly the
    R6 behavior the user described). All the R6/v7.20 brakes: LOCAL
    Player*CombatAvatar only, scene settled >= 10 s, never during the
    game's own skin reload, 12 s per-class cooldown, sticky skip, and
    a one-shot restore when the pick turns off."""
    try:
        if not sync_attrs.get('bHeroSkinHack', False):
            return None
        if _hero_scene_stable() != 'match':
            return None
        # Native execution selection uses GetCurArmExecutionItemId and the
        # official _Prepare/Cue/_Restore state machine.  This legacy driver
        # used _TryApplyExecuteSkin as a general FPS repaint workaround and
        # can overwrite an execution's own forced skin between native cues.
        if _striker_native_combat_owned():
            return 'native-official'
        try:
            if time.time() - _scene_at[0] < 10.0:
                return exec_gate('settling') or 'settling'
        except Exception:
            return exec_gate('scene-clock')
        av = None
        try:
            av = _local_combat_avatar()
        except Exception:
            av = None
        if av is None:
            try:
                _sp = getattr(Space, '_instance', None)
                _ow = getattr(_sp, 'owner', None) if _sp else None
                av = getattr(_ow, 'combat_avatar', None) if _ow else None
            except Exception:
                av = None
        if av is None:
            # last resort, R6's own scan: bounded heap walk for a
            # local Player*CombatAvatar. Throttled to one walk per
            # 30 s (a full walk costs ~0.4-1.2 s - never per tick).
            try:
                now2 = time.time()
                if now2 - exec_walk_at[0] >= 30.0:
                    exec_walk_at[0] = now2
                    import gc as _gc
                    for obj in _gc.get_objects():
                        cn2 = type(obj).__name__
                        if ('CombatAvatar' not in cn2 or 'Robot' in cn2
                                or 'Replay' in cn2
                                or not cn2.startswith('Player')):
                            continue
                        if _striker_is_local(obj):
                            av = obj
                            break
            except Exception:
                av = None
        if av is None:
            return exec_gate('no-local-avatar')
        cn = type(av).__name__
        if ('CombatAvatar' not in cn or 'Robot' in cn
                or 'Replay' in cn or not cn.startswith('Player')):
            return exec_gate('avatar-type:%s' % (cn,))
        if not _striker_is_local(av):
            return exec_gate('not-local')
        hid = _hero_id_deep(av)
        if not hid:
            return exec_gate('no-hero-id')
        gfs = globals().get('_get_forced_skin')
        sid = gfs(hid) if callable(gfs) else None
        if not sid:
            # pick off: restore the exec skin WE applied, once
            try:
                worn = getattr(av, '_execute_force_skin_item_id', None)
                if worn in exec_skin_done:
                    m = getattr(av, '_RestoreExecuteForceSkin', None)
                    if callable(m):
                        r = m()
                        _plog('[V812] _RestoreExecuteForceSkin -> %r'
                              % (r,))
                        exec_skin_done.discard(worn)
            except Exception:
                pass
            return None
        try:
            if getattr(av, '_execute_skin_reload_in_progress', False):
                return 'busy'
        except Exception:
            pass
        try:
            if getattr(av, '_execute_force_skin_item_id', None) == sid:
                return 'sticky'
        except Exception:
            pass
        if time.time() - exec_skin_at.get(cn, 0.0) < 12.0:
            return 'cooldown'
        m = getattr(av, '_TryApplyExecuteSkin', None)
        if not callable(m):
            _herofx_note('exec-missing',
                         '_TryApplyExecuteSkin missing on %s' % (cn,))
            return None
        exec_skin_at[cn] = time.time()
        try:
            r = m(sid)
        except Exception as e:
            _plog('[V812] _TryApplyExecuteSkin(%r) on %s RAISED %r'
                  % (sid, cn, e))
            return 'error'
        exec_skin_done.add(sid)
        _plog('[V812] _TryApplyExecuteSkin(%r) on %s -> %r'
              % (sid, cn, r))
        return 'exec-skin'
    except Exception as e:
        try:
            _plog('[V812] exec-skin error=%r' % (e,))
        except Exception:
            pass
        return None


def purge_skin_proto_cache():
    """v8.10: THE fix for the TPS emote body. The real cached_property
    caches hero_skin_proto in each instance's __dict__ on first read -
    and an instance-dict entry SHADOWS the (non-data) descriptor, so
    values read before our wrap installed (or before an emote/TPS
    window opened) stick forever and the wrapper never runs again.
    Walk the heap ourselves and pop the cached attribute from EVERY
    object that holds one (_hero_live_objects dedups by TYPE - one
    instance per class - and would miss the local avatar). Bounded,
    event-driven (emote press / TPS camera / twin build / addon
    install), never per-frame."""
    try:
        import gc as _gc
        import time as _t
        if _t.time() - purge_at[0] < 5.0:
            return
        purge_at[0] = _t.time()
        n = 0
        for obj in _gc.get_objects():
            try:
                d = getattr(obj, '__dict__', None)
                if d is None or 'hero_skin_proto' not in d:
                    continue
                del d['hero_skin_proto']
                n += 1
                if n >= 200:
                    break
            except Exception:
                continue
        if n:
            _herofx_note('hsp-purge',
                         'hero_skin_proto cache purged n=%d' % (n,))
    except Exception:
        pass


def twin_honest_required(owner):
    """Keep the legacy genuine-twin window out of native EVO form switches.

    v8.10 forced four seconds of genuine skin around every NovaTwin method.
    The recovered official methods are also the EVO Striker form-switch path;
    applying that blanket window to an authenticated injected selection hides
    its maximum model/effects and can visibly restore the default.  Genuine or
    unresolved state retains the old behavior byte-for-byte in effect.
    """
    try:
        resolver = globals().get('striker_legacy_skin')
        if not callable(resolver):
            return True
        hero_reader = globals().get('_hero_id_deep')
        hero_id = (_safe_int(hero_reader(owner), 0)
                   if callable(hero_reader) else
                   _safe_int(getattr(owner, 'hero_id', 0), 0))
        if hero_id and _safe_int(resolver(hero_id), 0):
            return False
    except Exception:
        pass
    return True


def _install_v810_twin_hook():
    """v8.10/v10.12.0: preserve genuine twin behavior, but never replace an
    authenticated native EVO form-switch appearance with the default skin."""
    installed = []
    for mod_name, cls_names in (
            ('gclient.gameplay.logic_base.entities.combat_avatar',
             ('CombatAvatar', 'PlayerCombatAvatar')),
            ('gclient.gameplay.logic_shootingrange.'
             'combat_avatar_shootingrange',
             ('PlayerCombatAvatarShootingRange',))):
        try:
            mod = _ea_import(mod_name)
            if mod is None:
                continue
            for cn in cls_names:
                cls = getattr(mod, cn, None)
                if not isinstance(cls, type):
                    continue
                for meth in ('RequestNovaTwinSkinTransform',
                             'TryPlayNovaTwinSkinTransform',
                             'PlayerInput_OnNovaTwinSkinTransform',
                             'RefreshNovaTwinSkinAppearance',
                             'EnterNovaTwinSkinEmote'):
                    fn = cls.__dict__.get(meth)
                    if fn is None:
                        fn = getattr(cls, meth, None)
                    if not callable(fn) or getattr(
                            fn, '_v810_twin', False):
                        continue

                    def _make(_f, _cn=cn, _mn=meth):
                        def wrapper(self, *a, **k):
                            try:
                                if twin_honest_required(self):
                                    twin_honest_until[0] = max(
                                        twin_honest_until[0],
                                        time.time() + 4.0)
                                    _herofx_note(
                                        'twin:%s.%s' % (_cn, _mn),
                                        'genuine nova twin build -> skin state '
                                        'honest window (+4s)')
                                else:
                                    # A previous genuine window must not leak
                                    # into this newer injected EVO transition.
                                    twin_honest_until[0] = 0.0
                                    _herofx_note(
                                        'twin:%s.%s:native-evo' % (_cn, _mn),
                                        'native EVO form switch keeps the '
                                        'authenticated actual Striker skin')
                            except Exception:
                                pass
                            return _f(self, *a, **k)
                        wrapper._v810_twin = True
                        return wrapper
                    setattr(cls, meth, _make(fn))
                    installed.append('%s.%s' % (cn, meth))
        except Exception:
            continue
    return installed


def _install_v810_camera_hook():
    """v8.10: SwitchToEmoteCamera(value, need_blender=True,
    camera_id=19) - the TPS camera switch the game makes for gameplay
    emotes AND sprays/stickers. Opening on it (instead of only on our
    emote rewrite) covers honest emote plays and sprays too; the Nova
    twin never switches the camera, so its model asks stay honest."""
    installed = []
    for mod_name, cls_names in (
            ('gclient.gameplay.logic_base.entities.combat_avatar',
             ('CombatAvatar', 'PlayerCombatAvatar')),
            ('gclient.gameplay.logic_shootingrange.'
             'combat_avatar_shootingrange',
             ('PlayerCombatAvatarShootingRange',
              'RobotCombatAvatarShootingRange')),
            ('gclient.gamesystem.entities.hall_doll',
             ('Doll', 'DollLike', 'CalculationDoll',
              'BigHeadCalculationDoll')),
            ('gclient.gamesystem.models.hall_show_model',
             ('HallShowModel', 'BigHeadCalculationShowModel'))):
        try:
            mod = _ea_import(mod_name)
            if mod is None:
                continue
            for cn in cls_names:
                cls = getattr(mod, cn, None)
                if not isinstance(cls, type):
                    continue
                fn = cls.__dict__.get('SwitchToEmoteCamera')
                if fn is None:
                    fn = getattr(cls, 'SwitchToEmoteCamera', None)
                if not callable(fn) or getattr(fn, '_v810_cam', False):
                    continue

                def _make(_f, _cn=cn):
                    def wrapper(self, value=None, *a, **k):
                        _on = bool(value) or bool(k.get('value'))
                        result = _f(self, value, *a, **k)
                        try:
                            if _on:
                                _striker_emote_until[0] = max(
                                    _striker_emote_until[0],
                                    time.time() + 15.0)
                                _striker_invalidate_skin_caches('emote-start')
                                _herofx_note(
                                    'cam:%s' % (_cn,),
                                    'SwitchToEmoteCamera on -> emote '
                                    'skin window (+15s)')
                            else:
                                _striker_rearm_after_emote('camera-off')
                        except Exception:
                            pass
                        return result
                    wrapper._v810_cam = True
                    wrapper._treacky_orig = _f
                    return wrapper
                setattr(cls, 'SwitchToEmoteCamera', _make(fn))
                installed.append('%s.SwitchToEmoteCamera' % (cn,))
        except Exception:
            continue
    return installed


def _install_v810_anim_check_hook():
    """Observe CheckPlayHeroSkinAnim without changing its answer.

    The native CheckPlayHeroSkinAnim -> CueIntroEnd ->
    _SwitchSkinIntroEndToIdle chain owns intro/idle state.  This hook is
    diagnostics only; it must never globally return False.
    """
    installed = []
    for mod_name, cls_names in (
            ('gclient.gamesystem.entities.hall_doll',
             ('Doll', 'DollLike', 'CalculationDoll',
              'BigHeadCalculationDoll')),
            ('gclient.gamesystem.models.hall_show_model',
             ('HallShowModel', 'BigHeadCalculationShowModel'))):
        try:
            mod = _ea_import(mod_name)
            if mod is None:
                continue
            for cn in cls_names:
                cls = getattr(mod, cn, None)
                if not isinstance(cls, type):
                    continue
                fn = cls.__dict__.get('CheckPlayHeroSkinAnim')
                if fn is None:
                    fn = getattr(cls, 'CheckPlayHeroSkinAnim', None)
                if not callable(fn) or getattr(fn, '_v810_cpa', False):
                    continue

                def _make(_f, _cn=cn):
                    def wrapper(self, *a, **k):
                        res = _f(self, *a, **k)
                        try:
                            _herofx_note(
                                'cpa-native:%s' % (_cn,),
                                'CheckPlayHeroSkinAnim native res=%r '
                                'a=%r' % (res, a[:2]))
                        except Exception:
                            pass
                        return res
                    wrapper._v810_cpa = True
                    wrapper._treacky_orig = _f
                    return wrapper
                setattr(cls, 'CheckPlayHeroSkinAnim', _make(fn))
                installed.append('%s.CheckPlayHeroSkinAnim' % (cn,))
        except Exception:
            continue
    return installed


# v8.20: EMOTE VAULT UNLOCK
# ============================================================
# The runtime dump shows the ownership gate the vault/wheel UI asks
# before an emote is listed or selectable:
#   gshare.ihall_item.IHallItems.HasItemByItemId            (bool)
#   gclient...avatarmembers.PlayerAvatarMember.
#       HasItemByItemIdIncludeTimeLimit
# The payload already knows the FULL emote catalog (EMOTE_INFO -
# the same 581-item set the menu's E| lines come from). While the
# emote hack is on, both checks answer True for every catalog
# emote id - the vault panel and the wheel then list and accept
# them all. Local-only: nothing is written to any server table,
# and every other item kind keeps the game's own answer.
owned_wrapped = set()
owned_log_n = [0]
owned_refreshed = [False]


def is_catalog_emote(value):
    try:
        iid = _safe_int(value, 0)
        if iid and iid in (globals().get('EMOTE_INFO') or {}):
            return True
    except Exception:
        pass
    return False


def legacy_emote_active():
    """Legacy bool-only ownership yields to real native emote objects."""
    try:
        if not sync_attrs.get('bEmoteHack', False):
            return False
        native_gate = globals().get('category_enabled')
        if callable(native_gate) and native_gate('emote'):
            return False
        return True
    except Exception:
        return False


def wrap_owned(cls, meth, label):
    try:
        key = (id(cls), meth)
        if key in owned_wrapped:
            return False
        orig = cls.__dict__.get(meth) or getattr(cls, meth, None)
        if not callable(orig):
            return False

        def _v820_owned(self, item_id, *a, **k):
            try:
                if legacy_emote_active() \
                        and is_catalog_emote(item_id):
                    if owned_log_n[0] < 6:
                        owned_log_n[0] += 1
                        _plog('[V820] emote owned %s item=%s -> True'
                              % (label, item_id))
                    return True
            except Exception:
                pass
            return orig(self, item_id, *a, **k)
        _v820_owned._treacky_v820_owned = True
        setattr(cls, meth, _v820_owned)
        owned_wrapped.add(key)
        return True
    except Exception:
        return False


def install_emote_ownership():
    n = 0
    try:
        for _mod_name in ('gshare.ihall_item',
                          'gclient.gamesystem.entities.avatarmembers.'
                          'cimp_backpack'):
            try:
                _mod = sys.modules.get(_mod_name)
                if _mod is None:
                    _mod = __import__(_mod_name, globals(),
                                      locals(), ['IHallItems'], 0)
                _cls = getattr(_mod, 'IHallItems', None)
                if isinstance(_cls, type) \
                        and hasattr(_cls, 'HasItemByItemId'):
                    if wrap_owned(_cls, 'HasItemByItemId',
                                        'IHallItems'):
                        n += 1
            except Exception:
                pass
        try:
            _pm = sys.modules.get(
                'gclient.gamesystem.entities.avatarmembers.'
                'cimp_backpack') or sys.modules.get(
                'gclient.gamesystem.entities.avatarmembers')
            if _pm is None:
                _pm = __import__(
                    'gclient.gamesystem.entities.avatarmembers',
                    globals(), locals(),
                    ['PlayerAvatarMember'], 0)
            _pcls = getattr(_pm, 'PlayerAvatarMember', None)
            if isinstance(_pcls, type) \
                    and hasattr(_pcls,
                                'HasItemByItemIdIncludeTimeLimit'):
                if wrap_owned(
                        _pcls, 'HasItemByItemIdIncludeTimeLimit',
                        'PlayerAvatarMember'):
                    n += 1
        except Exception:
            pass
        if n:
            _plog('[V820] emote ownership hooks installed=%d '
                  'catalog=%d'
                  % (n, len(globals().get('EMOTE_INFO') or {})))
            # one refresh so an already-open vault/wheel re-queries
            try:
                if not owned_refreshed[0] \
                        and legacy_emote_active():
                    owned_refreshed[0] = True
                    threading.Thread(
                        target=refresh_emote_panels,
                        daemon=True).start()
            except Exception:
                pass
    except Exception:
        pass
    return n


def refresh_emote_panels():
    try:
        time.sleep(0.5)
        import gc as _gc
        _done = []
        _seen = 0
        for obj in _gc.get_objects():
            try:
                _cn = type(obj).__name__
                if _cn not in ('PanelEmote', 'PanelExtraEmote',
                               'EmoteWheelComp', 'EmoteWheelCompInHall'):
                    continue
                _seen += 1
                if _seen > 6:
                    break
                for _meth in ('RefreshEmoteSlots', 'RefreshAll'):
                    _fn = getattr(obj, _meth, None)
                    if callable(_fn):
                        try:
                            _fn()
                            _done.append('%s.%s' % (_cn, _meth))
                            break
                        except Exception:
                            continue
            except Exception:
                continue
        if _done:
            _plog('[V820] emote panels refreshed %r' % (_done[:6],))
    except Exception:
        pass


def _install_v810_hooks(verbose=False):
    out = []
    try:
        out.extend(_install_v810_camera_hook())
        out.extend(_install_v810_twin_hook())
        out.extend(_install_v810_anim_check_hook())
        try:
            install_racer_shield()
        except Exception:
            pass
        # v8.20: the emote vault ownership hooks (idempotent, lazy -
        # gshare/avatarmembers load late like everything else).
        try:
            install_emote_ownership()
        except Exception:
            pass
        if verbose and out:
            _plog('[V810] hooks installed=%d %r' % (len(out), out))
    except Exception as _e:
        try:
            _plog('[V810] hooks error=%r' % (_e,))
        except Exception:
            pass
    return out


try:
    _ea_build_catalog()
    _install_emote_hooks(verbose=True)
    _install_v810_hooks(verbose=True)
    threading.Thread(target=_ea_loop, args=(_loop_gen('emotes'),),
                     daemon=True).start()
except Exception as _ea_err:
    _plog("[EMOTE] init failed: %r" % (_ea_err,))


# ============================================================
# v5.9: make the Equip buttons actually do something
# ============================================================
# _process_equip_nonces() was only ever reached from on_space_tick() - the
# in-match Space tick. In the LOBBY there is no space, so the hero nonce and
# the emote selection were never read: your config shows iHeroEquipNonce 23
# (you pressed Equip, the menu bumped it) and the payload logged nothing at
# all, because nothing was listening. This is why "Equip" did nothing even
# with every hook installed.
_hero_probe_done = [False]
_emote_probe_done = [False]
_hero_last_push = [None, 0.0]
_hero_apply_sig = [None]


def _hero_probe():
    """One-shot report of what the lobby actually exposes.

    The striker block cannot log (it is the zip's code, unmodified), so this
    says which of the paths it hooks can ever fire on this build.
    """
    if _hero_probe_done[0]:
        return
    _hero_probe_done[0] = True
    info = []
    try:
        probes = (('Doll', Doll), ('DollLike', DollLike),
                  ('CalculationDoll', CalculationDoll),
                  ('HallShowModel', HallShowModel))
    except Exception as e:
        _plog('[HERO] probe: classes missing=%r' % (e,))
        return
    for name, cls in probes:
        try:
            has_id = callable(getattr(cls, 'GetHeroId', None))
            desc = None
            for base in getattr(cls, '__mro__', (cls,)):
                if 'hero_skin_proto' in base.__dict__:
                    desc = type(base.__dict__['hero_skin_proto']).__name__
                    break
            info.append('%s:GetHeroId=%s,hero_skin_proto=%s'
                        % (name, has_id, desc or 'none'))
        except Exception as e:
            info.append('%s:%r' % (name, e))
    try:
        live = _hero_live_objects()
        info.append('live=%d' % len(live))
        for obj in live[:4]:
            hid = None
            try:
                fn = getattr(obj, 'GetHeroId', None)
                hid = fn() if callable(fn) else None
            except Exception:
                hid = None
            deep = _hero_id_deep(obj)
            proto_hid = None
            for meth in ('GetCurArmHeroSkinProto', 'GetActualArmHeroSkinProto'):
                try:
                    fn = getattr(obj, meth, None)
                    if callable(fn):
                        proto_hid = _hero_proto_get(fn(), 'hero_id')
                        if proto_hid:
                            break
                except Exception:
                    pass
            cur = None
            try:
                cur = _hero_proto_get(obj.hero_skin_proto, 'hero_id')
            except Exception:
                cur = None
            forced = None
            try:
                forced = _get_forced_skin(deep) if deep else None
            except Exception:
                forced = None
            info.append('%s:GetHeroId=%r deep=%r arm_proto_hero=%r '
                        'cached_proto_hero=%r forced=%r'
                        % (type(obj).__name__, hid, deep, proto_hid, cur, forced))
    except Exception as e:
        info.append('live error=%r' % (e,))
    _plog('[HERO] probe %s' % (' | '.join(info),))


# ============================================================
# v8.42-striker-melee: late catalog, explicit equip, and merged rows
# ============================================================
# This block is deliberately sys.modules-only.  The lobby object walk stays
# in the established background collector; only the short native call blocks
# below cross to the game-thread pump.

MERGED_DAGGER_ROWS = frozenset((97, 107, 141))
DAGGER_ROWS = frozenset((33, 97, 107, 141))


def _v842_int(value, default=0):
    try:
        return _safe_int(value, default)
    except Exception:
        return default


def weapon_row(equip_id):
    """Return (display row, row) for both real and merged melee catalogs."""
    equip_id = _v842_int(equip_id, 0)
    if not equip_id:
        return 0, None
    try:
        row = WEP.get(equip_id)
        if row:
            return equip_id, row
    except Exception:
        pass
    try:
        row = (globals().get('WEP_MERGED_DISPLAY') or {}).get(equip_id)
        if row:
            return equip_id, row
    except Exception:
        pass
    return equip_id, None


def melee_source_row():
    """Resolve the display row most recently equipped on actual Dagger 33.

    New menus write iSkinMeleeSource.  The fallback keeps old configs useful:
    if exactly one merged row has a selection and ordinary Dagger has none,
    that row is the only unambiguous legacy choice.  An explicit source always
    wins, including source=97 with index zero (Default).
    """
    try:
        source = _v842_int(sync_attrs.get('iSkinMeleeSource', 0), 0)
        if source in DAGGER_ROWS:
            return source
        candidates = []
        for row_id in (33, 97, 107, 141):
            _rid, row = weapon_row(row_id)
            if not row:
                continue
            idx = _v842_int(sync_attrs.get('iSkin_%s' % row_id, 0), 0)
            if 0 < idx <= len(row) - 1:
                candidates.append(row_id)
        if 33 in candidates:
            return 33
        if len(candidates) == 1:
            return candidates[0]
    except Exception:
        pass
    return 33


def selected_weapon_skin(equip_id):
    equip_id = _v842_int(equip_id, 0)
    if not equip_id:
        return None
    row_id = melee_source_row() if equip_id == 33 else equip_id
    _rid, row = weapon_row(row_id)
    if not row:
        return None
    try:
        idx = _v842_int(sync_attrs.get('iSkin_%s' % row_id, 0), 0)
        skins = list(row[1:])
        if 0 < idx <= len(skins):
            return skins[idx - 1]
    except Exception:
        pass
    return None


# All weapon consumers, including the factory and Doll/showroom hooks, use
# this one resolver.  In particular actual equip 33 can resolve display 97.
def get_forced_weapon_skin(equip_id):
    # A native Vault melee owns its authentic CItem/case lifecycle.  The old
    # menu painter must yield everywhere (create, setter hooks, current-weapon
    # pump and rebuild enforcement), not only at EquipCaseFactory.Create.
    # Native gun behavior is unchanged in a match; its takeover gate remains
    # scene-scoped exactly as defined by native_arm_takeover.
    native_gate = globals().get('native_equip_takeover')
    try:
        if callable(native_gate) and native_gate(equip_id):
            return None
    except Exception:
        pass
    return selected_weapon_skin(equip_id)


_get_forced_weapon_skin = get_forced_weapon_skin


def has_weapon_row(equip_id):
    return weapon_row(equip_id)[1] is not None


# ---------------------------------------------------------------------------
# Hero catalog recovery / stable indices
# ---------------------------------------------------------------------------
_hero_catalog_state = {
    'sig': None, 'built': False, 'complete': False,
    'next_retry': 0.0, 'last': None, 'sizes': None, 'table_ids': None,
}
# Native config sync is one-way.  Keep the selected skin ID when a catalog
# remap cannot be written back to the native integer index.
_hero_selection_override = {}


def get_forced_skin(hero_id):
    hid = _v842_int(hero_id, 0)
    if not hid:
        return None
    # v10.12.0: once the native Unlock All equip has completed, every legacy
    # hall/emote/MVP/combat consumer must resolve the SAME actual item as the
    # native path (including maximum evolution and explicit lower appearances).
    # Before that equip, or for genuine/default state, retain the stable menu
    # selection below.  The runtime lookup avoids a definition-order dependency.
    try:
        native_resolver = globals().get('striker_legacy_skin')
        native_item = (_v842_int(native_resolver(hid), 0)
                       if callable(native_resolver) else 0)
        if native_item:
            return native_item
    except Exception:
        pass
    try:
        entries = (HERO.get(hid) or HERO.get(str(hid)) or [])
        ids = list(entries[1:])
        key = 'iHeroSkin_%s' % hid
        raw_idx = _v842_int(dict.get(sync_attrs, key, 0), 0)
        override = _hero_selection_override.get(hid)
        if override:
            if raw_idx in (override['old_idx'], override['new_idx']):
                # A removed selection is an honest Default, never the next
                # row which happens to inherit its old numeric index.
                return (override['skin_id']
                        if override['skin_id'] in ids else None)
            # A different native index is a new user selection.  The explicit
            # nonce path also clears this map before resolving the new pick.
            _hero_selection_override.pop(hid, None)
        if 0 < raw_idx <= len(ids):
            return ids[raw_idx - 1]
    except Exception:
        pass
    return None


_get_forced_skin = get_forced_skin


def _v842_items(table):
    try:
        return list(table.items()) if table is not None else []
    except Exception:
        return []


def _v842_field(proto, key, default=None):
    try:
        getter = globals().get('_hero_proto_get')
        if callable(getter):
            return getter(proto, key, default)
    except Exception:
        pass
    try:
        if isinstance(proto, dict):
            return proto.get(key, default)
        value = getattr(proto, key, default)
        return value() if callable(value) else value
    except Exception:
        return default


def model_ready(proto):
    # Keep the established stub guard, but accept every model field used by
    # the supported hall/match paths rather than dropping FPS-only rows.
    for key in ('model_id', 'fps_model_id', 'model_id_alb'):
        if _v842_int(_v842_field(proto, key, 0), 0):
            return True
    return False


def refresh_hero_catalog(reason='retry'):
    """Rebuild after delayed data loads without reshuffling saved skin IDs."""
    global HERO, HERO_SKIN_INFO, hd, lid
    st = _hero_catalog_state
    now = time.time()
    try:
        hm = sys.modules.get('gclient.data.hero_data')
        lm = sys.modules.get('gclient.data.lobby_item_data')
        if hm is None:
            hm = sys.modules.get('gclient.data.hero_template_data')
        if lm is None:
            lm = sys.modules.get('gclient.data.lobby_item_template_data')
        if hm is not None:
            hd = hm
        if lm is not None:
            lid = lm
        hdata = getattr(hd, 'data', None) if 'hd' in globals() else None
        ldata = getattr(lid, 'data', None) if 'lid' in globals() else None
        if hdata is None and ldata is None:
            st['next_retry'] = now + 5.0
            return False
        sig = (len(hdata or {}), len(ldata or {}))
        table_ids = (id(hdata), id(ldata))
        previous_sizes = st.get('sizes')
        if (st.get('table_ids') == table_ids and previous_sizes
                and (sig[0] < previous_sizes[0]
                     or sig[1] < previous_sizes[1])):
            # Live game tables can be cleared/refilled in place during a
            # scene/data reload.  Never erase a good catalog against that
            # transient subset; a replacement table object is authoritative.
            st['sig'] = sig
            st['complete'] = False
            st['next_retry'] = now + 5.0
            return False
        if (st['built'] and st['sig'] == sig
                and st.get('table_ids') == table_ids
                and (st['complete'] or now < st['next_retry'])):
            return False
        if (st['sig'] == sig and st.get('table_ids') == table_ids
                and now < st['next_retry']):
            return False
        # An item table without its hero table is still a cold/partial load.
        # Do not erase a previously usable catalog in that state.
        if not hdata:
            st['sig'] = sig
            st['next_retry'] = now + 5.0
            return False

        old_hero = globals().get('HERO') or {}
        old_info = globals().get('HERO_SKIN_INFO') or {}
        old_selection = {}
        for hero_id, entries in _v842_items(old_hero):
            try:
                hid = _v842_int(hero_id, 0)
                old_ids = list(entries[1:])
                key = 'iHeroSkin_%s' % hid
                idx = _v842_int(dict.get(sync_attrs, key, 0), 0)
                if not hid or idx <= 0:
                    if hid:
                        _hero_selection_override.pop(hid, None)
                    continue
                override = _hero_selection_override.get(hid)
                if override and idx in (override['old_idx'], override['new_idx']):
                    # Read the effective ID, not the neighbor now occupying
                    # the stale native index after an earlier remap.
                    old_iid = override['skin_id']
                elif idx <= len(old_ids):
                    old_iid = old_ids[idx - 1]
                else:
                    old_iid = None
                if old_iid:
                    old_selection[hid] = (idx, old_iid)
                else:
                    _hero_selection_override.pop(hid, None)
            except Exception:
                continue

        new_hero = {}
        hero_rows = {}
        for hero_id, proto in _v842_items(hdata):
            hid = _v842_int(hero_id, 0)
            if not hid:
                continue
            hero_rows[hid] = proto
            name = _v842_field(proto, 'hero_name', None)
            if name is None:
                name = str(hid)
            new_hero[hid] = [name]

        new_info = {}
        source_order = {}
        for item_id, proto in _v842_items(ldata):
            try:
                iid = _v842_int(item_id, 0)
                hid = _v842_int(_v842_field(proto, 'hero_id', 0), 0)
                if not iid or not hid or hid not in new_hero:
                    continue
                sub_type = _v842_int(_v842_field(proto, 'sub_type', 0), 0)
                short_desc = _v842_field(proto, 'short_desc', None)
                hero_skin_id = _v842_field(proto, 'hero_skin_id', None)
                is_skin = (sub_type == 300 or short_desc == 'Striker'
                           or hero_skin_id is not None)
                if not is_skin or not model_ready(proto):
                    continue
                default_item = _v842_int(
                    _v842_field(hero_rows.get(hid), 'hero_item_id', 0), 0)
                if default_item and iid == default_item:
                    continue
                if iid in new_info:
                    continue
                new_info[iid] = proto
                source_order.setdefault(hid, []).append(iid)
            except Exception:
                continue

        # Preserve every old position that still exists; append newly arrived
        # rows in game-table order.  This is what makes index remapping safe.
        for hid, source_ids in source_order.items():
            source_set = set(source_ids)
            old_entries = old_hero.get(hid, [])
            old_ids = list(old_entries[1:]) if old_entries else []
            ordered = [iid for iid in old_ids if iid in source_set]
            ordered_set = set(ordered)
            ordered.extend(iid for iid in source_ids if iid not in ordered_set)
            new_hero[hid].extend(ordered)

        # Native config sync is C++ -> Python only.  Do not pretend that a
        # Python-side index write updates the menu's saved integer.  Instead
        # retain the selected skin ID and let get_forced_skin resolve
        # both the old native index and the new catalog index.  An explicit
        # equip nonce clears this override before a new pick is resolved.
        for hid, (old_idx, old_iid) in old_selection.items():
            try:
                key = 'iHeroSkin_%s' % hid
                raw_idx = _v842_int(dict.get(sync_attrs, key, 0), 0)
                if raw_idx != old_idx:
                    _hero_selection_override.pop(hid, None)
                    continue
                ids = new_hero.get(hid, [])[1:]
                new_idx = ids.index(old_iid) + 1 if old_iid in ids else 0
                if new_idx == old_idx and old_iid in ids:
                    _hero_selection_override.pop(hid, None)
                else:
                    _hero_selection_override[hid] = {
                        'old_idx': old_idx, 'new_idx': new_idx,
                        'skin_id': old_iid,
                    }
            except Exception:
                continue

        changed = (dict(old_hero) != new_hero
                   or set(old_info) != set(new_info))
        HERO = new_hero
        HERO_SKIN_INFO = new_info
        st.update({'sig': sig, 'built': True, 'complete': bool(new_info),
                   'next_retry': now + (30.0 if new_info else 5.0),
                   'sizes': sig, 'table_ids': table_ids,
                   'last': (reason, len(new_hero), len(new_info))})
        builder = (globals().get('_build_hero_info_lines')
                   or globals().get('_build_hero_info_lines_r21'))
        if callable(builder):
            text = builder()
            if isinstance(text, (list, tuple)):
                text = '\n'.join(str(x) for x in text)
            text = str(text)
            if not text.endswith('\n'):
                text += '\n'
            old_text = _hero_lines_cache[0]
            _hero_lines_cache[0] = text
            if changed or old_text != text:
                _hero_udp_last[0] = None
                _write_udp_hero(text)
        if changed:
            _plog('[V842] hero catalog refresh reason=%s heroes=%d skins=%d'
                  % (reason, len(new_hero), len(new_info)))
        return changed
    except Exception as exc:
        st['next_retry'] = now + 5.0
        try:
            _plog('[V842] hero catalog refresh deferred: %r' % (exc,))
        except Exception:
            pass
        return False


def _v842_hero_text():
    builder = (globals().get('_build_hero_info_lines')
               or globals().get('_build_hero_info_lines_r21'))
    if not callable(builder):
        return 'END\n'
    text = builder()
    if isinstance(text, (list, tuple)):
        text = '\n'.join(str(x) for x in text)
    text = str(text)
    return text if text.endswith('\n') else text + '\n'


# Replace the old sender, whose list-only join corrupted the sanitized string
# builder on every periodic feed.  No character-wise joins, no import storm.
def send_hero_info():
    try:
        refresh_hero_catalog('feed')
        text = _v842_hero_text()
        _hero_lines_cache[0] = text
        _write_udp_hero(text)
    except Exception as exc:
        try:
            _plog('[V842] hero feed deferred: %r' % (exc,))
        except Exception:
            pass


_send_hero_info = send_hero_info


# ---------------------------------------------------------------------------
# Game-thread completion helper and latest-show coalescing
# ---------------------------------------------------------------------------
show_latest = {}


def safe_game_thread():
    try:
        if _game_on_game_thread():
            return True
    except Exception:
        pass
    # Host tests and the early boot path have no established tid yet.  Keep
    # their historical inline-main behavior; real worker threads still queue.
    try:
        return (_GAME_TID[0] is None
                and threading.current_thread() is threading.main_thread())
    except Exception:
        return False


def game_call_sync(name, fn, timeout=4.0):
    if safe_game_thread():
        try:
            return True, fn()
        except Exception:
            return False, None
    done = threading.Event()
    result = [None]
    failed = [False]

    def action():
        try:
            result[0] = fn()
        except Exception as exc:
            failed[0] = True
            try:
                _plog('[V842] queued call %s failed: %r' % (name, exc))
            except Exception:
                pass
        finally:
            done.set()

    try:
        if not _game_post(name, action):
            return False, None
    except Exception:
        return False, None
    if not done.wait(timeout):
        return False, None
    if failed[0]:
        return False, None
    return True, result[0]


def show_dispatch(kind, obj, fn, failure, selection=None):
    key = (kind, id(obj))
    token = object()
    show_latest[key] = token
    try:
        generation = (_hero_apply_sig[0], paint_hero[0], id(selection))
    except Exception:
        generation = None

    def action():
        if show_latest.get(key) is not token:
            return failure
        if generation is not None:
            try:
                if generation != (_hero_apply_sig[0], paint_hero[0],
                                  id(selection)):
                    return failure
            except Exception:
                pass
        try:
            return fn()
        finally:
            if show_latest.get(key) is token:
                show_latest.pop(key, None)

    name = 'hero-show-%s-%x' % (kind, id(obj))
    if safe_game_thread():
        try:
            return action()
        except Exception:
            return failure
    ok, value = game_call_sync(name, action)
    if not ok and show_latest.get(key) is token:
        # Cancel an action which has not started.  A late queue drain must not
        # paint an old pick or write its painted signature after a timeout.
        show_latest.pop(key, None)
    return value if ok else failure


# Keep the established gate/dedup implementation, but execute its short native
# call section on the game thread.  Scene collection remains in the caller.
doll_show_direct = globals().get('_striker_show_on_doll')
if callable(doll_show_direct):
    def striker_show_on_doll(obj, proto, sticky=False):
        return show_dispatch(
            'doll', obj,
            lambda: doll_show_direct(obj, proto, sticky=sticky), False,
            selection=proto)
    _striker_show_on_doll = striker_show_on_doll

proto_show_direct = globals().get('_striker_show_proto')
if callable(proto_show_direct):
    def striker_show_proto(hsm, proto, sticky=False):
        return show_dispatch(
            'proto', hsm,
            lambda: proto_show_direct(hsm, proto, sticky=sticky), None,
            selection=proto)
    _striker_show_proto = striker_show_proto


# ---------------------------------------------------------------------------
# Explicit Striker Equip/Default requests
# ---------------------------------------------------------------------------
_hero_menu_request = [None]       # (nonce, hero_id), survives no-avatar boot
_hero_menu_last_try = [0.0]
hero_equip_latest = [None]
hero_equip_target = [None]


def current_hero_sig():
    try:
        return tuple(sorted(
            (key, value) for key, value in sync_attrs.items()
            if str(key).startswith('iHeroSkin_')
            and _v842_int(value, 0) > 0))
    except Exception:
        return ()


def default_hero_item(hero_id):
    """Use the game's real default item; never invent a skin namespace."""
    hero_id = _v842_int(hero_id, 0)
    if not hero_id:
        return 0
    try:
        data = getattr(hd, 'data', {}) if 'hd' in globals() else {}
        proto = data.get(hero_id, {})
        for key in ('hero_item_id', 'default_hero_skin_item_id',
                    'default_hero_skin_id'):
            value = _v842_int(_v842_field(proto, key, 0), 0)
            if not value:
                continue
            if key == 'hero_item_id':
                return value
            try:
                lobby = getattr(lid, 'data', {}) if 'lid' in globals() else {}
                if value in lobby or value in (HERO_SKIN_INFO or {}):
                    return value
            except Exception:
                pass
    except Exception:
        pass
    return 0


def pending_for(hero_id):
    pending = _hero_menu_request[0]
    if not pending:
        return None
    _nonce, requested_hero = pending
    if requested_hero and hero_id and requested_hero != hero_id:
        return None
    return pending


def avatar_try_equip(avatar, force=False, restore_default=False,
                           hero_id=None, request_nonce=None):
    """Queue the real ArmHeroSkin call; never run it on a worker thread."""
    try:
        if avatar is None or not sync_attrs.get('bHeroSkinHack', False):
            return False
        if _hero_in_match():
            return False
        hid = _v842_int(hero_id, 0)
        actual_hid = None
        try:
            actual_hid = _hero_id_deep(avatar)
        except Exception:
            pass
        pending_before = _hero_menu_request[0]
        if (pending_before and pending_before[1] and actual_hid
                and pending_before[1] != actual_hid
                and (request_nonce is None
                     or pending_before[0] == request_nonce)):
            # The player swapped heroes before the old queued request landed.
            # Do not let that stale request suppress the new hero forever.
            _hero_menu_request[0] = None
        if hid and actual_hid and hid != actual_hid:
            return False
        hid = hid or actual_hid
        if not hid:
            return False

        pending = pending_for(hid)
        if pending and request_nonce is None:
            request_nonce = pending[0]
            force = True
            restore_default = True
        if not force and pending:
            # The explicit menu request wins over passive getter callbacks.
            return False

        if request_nonce is not None:
            # An explicit menu action supersedes a catalog-remap override.
            _hero_selection_override.pop(hid, None)
        gf = globals().get('_get_forced_skin')
        if not callable(gf):
            return False
        forced = gf(hid)
        target = forced
        if not target and (restore_default or pending):
            target = default_hero_item(hid)
        if not target:
            # Never acknowledge an unverified zero-ID reset.  The hero table's
            # real default item may arrive on the next cold-catalog retry.
            return False

        sig = current_hero_sig() if force else _hero_apply_sig[0]
        aid = id(avatar)
        key = (sig, aid, hid, target, request_nonce)
        if (not force and _avatar_equip_sig[0] == sig
                and _avatar_equip_aid[0] == aid
                and hero_equip_target[0] in (None, target)):
            return False
        if _avatar_equip_busy[0]:
            if not force or hero_equip_latest[0] == key:
                return False
        hero_equip_latest[0] = key

        def _run():
            _avatar_equip_busy[0] = True
            try:
                if hero_equip_latest[0] != key:
                    return
                try:
                    data_write(avatar)
                except Exception:
                    pass
                arm = getattr(avatar, 'ArmHeroSkin', None)
                if not callable(arm):
                    _plog('[V842] ArmHeroSkin unavailable for hero=%r' % (hid,))
                    return
                equipped = False
                for shape, args, kwargs in (
                        ('(hero_id, skin_item_id)', (hid, target), {}),
                        ('(skin_item_id=)', (), {'skin_item_id': target}),
                        ('(item_id=)', (), {'item_id': target}),
                        ('(skin_id,)', (target,), {})):
                    try:
                        result = arm(*args, **kwargs)
                        _plog('[V842] ArmHeroSkin%s hero=%r target=%r -> %r'
                              % (shape, hid, target, result))
                        if result is False:
                            # The established native success result is None;
                            # an explicit False is a rejected equip, not an
                            # acknowledgement that should suppress retries.
                            break
                        equipped = True
                        break
                    except TypeError:
                        continue
                    except Exception as exc:
                        _plog('[V842] ArmHeroSkin%s error=%r' % (shape, exc))
                        break
                if equipped and hero_equip_latest[0] == key:
                    _avatar_equip_sig[0] = sig
                    _avatar_equip_aid[0] = aid
                    hero_equip_target[0] = target
                    if request_nonce is not None:
                        pending_now = _hero_menu_request[0]
                        if pending_now and pending_now[0] == request_nonce:
                            _hero_menu_request[0] = None
            except Exception as exc:
                try:
                    _plog('[V842] queued hero equip error=%r' % (exc,))
                except Exception:
                    pass
            finally:
                _avatar_equip_busy[0] = False

        # _game_post coalesces this name, so a rapid pick burst executes only
        # the newest request.  The request is acknowledged inside _run, not
        # when it is merely queued.
        return bool(_game_post('hero-equip', _run))
    except Exception as exc:
        try:
            _plog('[V842] hero equip request error=%r' % (exc,))
        except Exception:
            pass
        return False


_avatar_try_equip = avatar_try_equip


_v842_base_process_nonces = globals().get('_process_equip_nonces')
if callable(_v842_base_process_nonces):
    def process_equip_nonces(reason='tick'):
        processed = False
        try:
            processed = bool(_v842_base_process_nonces(reason))
        except Exception:
            pass
        try:
            nonce = _v842_int(sync_attrs.get('iHeroEquipNonce', 0), 0)
            changed = nonce != _hero_equip_nonce_seen[0]
            if changed:
                _hero_equip_nonce_seen[0] = nonce
                hid = _v842_int(sync_attrs.get('iRecentStrikerHero', 0), 0)
                if hid:
                    _hero_selection_override.pop(hid, None)
                _striker_invalidate_skin_caches('equip')
                _striker_refresh_tries[0] = 0
                _striker_refresh_ok[0] = False
                _hero_menu_request[0] = (nonce, hid)
                _hero_menu_last_try[0] = 0.0
                _plog('[V842] Striker equip nonce=%d hero=%r' % (nonce, hid))
            pending = _hero_menu_request[0]
            now = time.time()
            if pending and (changed or now - _hero_menu_last_try[0] >= 3.0):
                avatar = None
                try:
                    avatar = _avatar_seen_ref() if _avatar_seen_ref else None
                except Exception:
                    avatar = None
                if avatar is not None:
                    _hero_menu_last_try[0] = now
                    _avatar_try_equip(
                        avatar, force=True, restore_default=True,
                        hero_id=pending[1], request_nonce=pending[0])
                processed = True
        except Exception as exc:
            try:
                _plog('[V842] Striker nonce error=%r' % (exc,))
            except Exception:
                pass
        return processed
    _process_equip_nonces = process_equip_nonces


def _v842_tick():
    # Called by the established 1.5 s worker.  The function is cheap when the
    # data signature is unchanged and performs no game imports or heap walks.
    refresh_hero_catalog('apply')


def _treacky_apply_loop(gen=0):
    while _loop_alive('apply', gen):
        try:
            _v842_tick()
        except Exception:
            pass
        # v7.21: one-shot diagnostics + scope catalog, threaded so the
        # lobby push below is never delayed by them.
        try:
            _now_bp = time.time()
            _bscene = _hero_scene_stable()
            # v7.23: v7.22's boot probe ran before ANY combat module
            # existed ("no bullet/tracer/killfeed modules loaded yet").
            # On match entry schedule ONE re-run ~20 s in - combat
            # classes exist by then and 20 s keeps the dump out of the
            # fragile first seconds of a scene change.
            if _bscene == 'match' and _bullet_probe_scene[0] != 'match':
                _bullet_probe_scene[0] = 'match'
                _bullet_probe_re_at[0] = _now_bp + 20.0
            elif _bscene != 'match' and _bullet_probe_scene[0] != _bscene:
                _bullet_probe_scene[0] = _bscene
            if not _bullet_probe_started[0]:
                _bullet_probe_started[0] = True
                # NOTE: _bullet_probe_done belongs to the probe itself -
                # v7.21 set it BEFORE the thread ran, so the probe's own
                # first check saw "done" and returned instantly. That is
                # why no [TRACER-PROBE] line ever appeared.
                if _V841PERF_AUTO_DIAGNOSTICS and _debug_log_on():
                    threading.Thread(target=_bullet_kill_probe,
                                     daemon=True).start()
            elif (_bullet_probe_re_at[0]
                  and _now_bp >= _bullet_probe_re_at[0]
                  and _V841PERF_AUTO_DIAGNOSTICS and _debug_log_on()):
                _bullet_probe_re_at[0] = 0.0
                _bullet_probe_done[0] = False
                _plog('[TRACER-PROBE] match entry - re-running now that '
                      'combat modules are loaded')
                threading.Thread(target=_bullet_kill_probe,
                                 daemon=True).start()
        except Exception:
            pass
        try:
            if not _optic_catalog_done[0] and (WEP_SKIN_INFO or WEP):
                _optic_catalog_done[0] = True
                threading.Thread(target=_harvest_optics,
                                 daemon=True).start()
        except Exception:
            pass
        try:
            fn = globals().get('_process_equip_nonces')
            if callable(fn):
                fn('lobby')
        except Exception as e:
            _plog('[APPLY] loop error=%r' % (e,))
        # v6.1: don't wait for the Equip button. If a striker is selected and
        # the switch is on, keep the lobby model showing it.
        try:
            if _ea_gate() and not _emote_probe_done[0]:
                _emote_probe_done[0] = True
                # v7.17: the heap scan can run for over a minute - never
                # let it starve this loop (the lobby push lives here).
                threading.Thread(target=_emote_probe,
                                 daemon=True).start()
            # v7.30R19: "show in lobby" - when a pick CHANGES, re-show
            # the live hall models through their own ShowHeroSkinModel
            # (the same call the original block makes after Clear/Cue).
            # v7.30R20: the R19 trigger only fired on a pick CHANGE -
            # but the picks arrive seconds after boot (from the saved
            # menu config), the refresh then found an EMPTY registry
            # (the lobby model loads before injection) and NOTHING ever
            # retried. Now: retry every 3 s in the hall until ONE model
            # has actually re-shown (max 15 tries per hall entry), and
            # every return to the hall (after a match) resets the
            # retries so the fresh lobby model gets its pick too.
            try:
                if (sync_attrs.get('bHeroSkinHack', False)
                        and not _hero_in_match()):
                    # hall-entry edge: arm a refresh burst
                    if _striker_hall_entry_at[0] <= 0.0:
                        _striker_hall_entry_at[0] = now = time.time()
                        _striker_refresh_tries[0] = 0
                        _striker_refresh_ok[0] = False
                        _striker_last_refresh[0] = 0.0
                    sig = tuple(sorted(
                        (k, v) for k, v in sync_attrs.items()
                        if str(k).startswith('iHeroSkin_')
                        and _safe_int(v, 0) > 0))
                    now = time.time()
                    sig_changed = sig != _hero_apply_sig[0]
                    if sig_changed:
                        _hero_apply_sig[0] = sig
                        _striker_invalidate_skin_caches('selection')
                        _striker_refresh_ok[0] = False
                        _striker_refresh_tries[0] = 0
                        _striker_last_refresh[0] = 0.0
                    # v8.18: the 10 s maintenance cadence is RETIRED -
                    # every maintenance re-show was a full model
                    # rebuild (weapon drop + pose reset), i.e. one
                    # visible glitch per pass in a long lobby stay
                    # (the 'apply, unapply, apply...' report). The
                    # passive state force + the game's own Load keep
                    # the skin on; the active retry burst only exists
                    # to land a NEW pick, six 3 s tries are plenty.
                    # v8.19: ten tries - the v8.18 device log showed
                    # slow scene entries where the dolls only appear
                    # late; the never-rule makes extra tries free.
                    # optimized1: two quick attempts cover normal slow loads;
                    # later passes are spaced out instead of repeatedly walking/
                    # showing when prior attempts painted nothing. Native Load,
                    # controller, pick, and scene triggers remain intact.
                    _interval = 3.0 if _striker_refresh_tries[0] < 2 else 8.0
                    _may = _striker_refresh_tries[0] < 10
                    if (_may
                            and (sig_changed
                                 or now - _striker_last_refresh[0] >= _interval)):
                        _striker_refresh_tries[0] += 1
                        n = _striker_lobby_refresh(
                            'pick' if sig_changed else 'retry%d'
                            % _striker_refresh_tries[0])
                        # Start the interval AFTER the pass. The old start-time
                        # stamp expired during a multi-second pass and allowed
                        # another expensive retry on the very next worker tick.
                        _striker_last_refresh[0] = time.time()
                        if n:
                            if not _striker_refresh_ok[0]:
                                _plog('[HERO-SCENE] lobby refresh '
                                      're-show=%d' % (n,))
                            _striker_refresh_ok[0] = True
                else:
                    # left the hall (match / elsewhere): re-arm the
                    # next hall entry
                    _striker_hall_entry_at[0] = 0.0
            except Exception:
                pass
        except Exception as e:
            _plog('[HERO] auto-apply error=%r' % (e,))
        try:
            time.sleep(1.5)
        except Exception:
            return


# v7.30R18: the hero-compat boot step is REMOVED. No proto conversion,
# no resend - the original block builds its own catalog (real protos
# straight from lid.data) and its own 2 s feed loop feeds the menu.
# Exactly as the original shipped.

_plog('[BOOT] step: apply-loop')
try:
    threading.Thread(target=_treacky_apply_loop, args=(_loop_gen('apply'),),
                     daemon=True).start()
    _plog('[APPLY] lobby apply loop started (1.5 s)')
except Exception as _al_err:
    _plog('[APPLY] loop start failed: %r' % (_al_err,))

_plog("[PAYLOAD] %s ready utc=%s" % (PAYLOAD_BUILD, _utc_stamp()))


# ============================================================
# v7.5: FEED SUPERVISOR
# ============================================================
# The menu showed "50003 bound, 0 packets" and every list sat on
# "scanning..." - the payload's sender threads were dead. This loop keeps
# the two catalogs flowing no matter what happened to them, and writes one
# status line per pass so the log always shows the state of every feed.
def _treacky_feed_supervisor():
    last = {'hero': -1, 'emote': -1, 'stuck': 0}
    stall_sampled = False
    while True:
        time.sleep(15.0)
        try:
            # hero catalog: send it ourselves - a complete refresh each time
            try:
                fn = globals().get('_send_hero_info')
                if callable(fn):
                    fn()
            except Exception as e:
                _plog('[FEED] hero send failed: %r' % (e,))
            # weapon catalog: only when it is actually built and non-empty
            try:
                if _weapon_catalog_ready[0] and WEP:
                    build = globals().get('_build_skin_info_lines')
                    if callable(build):
                        _write_udp_chunked(_write_udp_skin, build())
            except Exception as e:
                _plog('[FEED] weapon send failed: %r' % (e,))
            try:
                hs = _hero_stats.get('sent', 0)
                es = _emote_stats.get('sent', 0)
                moved = (hs != last['hero']) or (es != last['emote'])
                if not moved:
                    last['stuck'] += 1
                else:
                    last['stuck'] = 0
                    stall_sampled = False
                last['hero'] = hs
                last['emote'] = es
                # v8.20: STALL PROFILER. The match-entry stall grew
                # every round (49.89s v8.16 -> 73.71s v8.19) and the
                # counters never said WHY. The first time a stall
                # episode reaches 2, sample every thread's stack once
                # (bounded, 10 frames, main thread first) - the frame
                # names name the culprit directly.
                if last['stuck'] >= 2 and not stall_sampled:
                    stall_sampled = True
                    try:
                        frames = sys._current_frames()
                        lines = []
                        for _tid in sorted(frames,
                                           key=lambda t: t
                                           != threading.main_thread()
                                           .ident):
                            frm = frames.get(_tid)
                            if frm is None:
                                continue
                            hops = []
                            f = frm
                            for _ in range(10):
                                try:
                                    hops.append('%s:%s'
                                                % (f.f_code
                                                   .co_name,
                                                   f.f_code
                                                   .co_filename
                                                   .rsplit('/', 1)
                                                   [-1]))
                                    f = f.f_back
                                except Exception:
                                    break
                            if hops:
                                lines.append('  t%s %s'
                                             % (_tid, ' <- '
                                                .join(hops[:6])))
                        if lines:
                            _plog('[V820] stall sample stuck=%d '
                                  'threads=%d\n%s'
                                  % (last['stuck'], len(lines),
                                     '\n'.join(lines[:12])))
                    except Exception as _se:
                        _plog('[V820] stall sample failed: %r'
                              % (_se,))
                # v7.30R3: esp_rx = bound/pkts/fail/ents/drawn from the C++
                # receiver - the cold-start bind race is visible now.
                _plog('[FEED] weapon_ready=%s WEP=%d hero_sent=%d emote_sent=%d '
                      'esp_frame=%d stuck=%d esp_rx=%s/%s/%s/%s/%s'
                      % (_weapon_catalog_ready[0], len(WEP), hs, es,
                         _esp_frame_count[0], last['stuck'],
                         sync_attrs.get('iEspRxInit', -1),
                         sync_attrs.get('iEspRx', -1),
                         sync_attrs.get('iEspRxFail', -1),
                         sync_attrs.get('iEspRxEnts', -1),
                         sync_attrs.get('iEspRxDrawn', -1)))
            except Exception as e:
                _plog('[FEED] status failed: %r' % (e,))
        except Exception:
            pass


try:
    threading.Thread(target=_treacky_feed_supervisor, daemon=True,
                     name='feed-supervisor').start()
    _plog('[BOOT] feed supervisor started')
except Exception as _fs_err:
    _plog('[BOOT] feed supervisor failed: %r' % (_fs_err,))

_plog('[BOOT] module exec complete')

# ============================================================
# EXECUTIONS  --  port 50007, `H|hero_id|hero_name` +
#                 `X|hero_id|idx|item_id|name` + BEGIN/END
# ============================================================
# v8.24: executions are BACK (they lived in v5.x and were dropped in the
# v6.1 emote rewrite). Data source is the game's own
# gclient.data.hero_execution_data (per-hero groups) resolved through
# lobby_item_data - built by @Zelewin's package builder with HIS field
# names exactly first and our dump-evidenced names as fallback:
#   item id : execution_item_id, lobby_item_id, item_id, id
#   item nm : name, en_name, english_name, name_en, skin_name
#   hero nm : hero_name, name, en_name, english_name, name_en
#   anim    : anims, anim, animation, esm, graph
# The first row's REAL keys are logged once ([EXEC] probe ...) so the next
# device log tells us the truth if every guess missed. Keys are looked up
# int-first (the payload's proven pattern - these tables are int-keyed).
# Selection: the menu sends iExec_<hero_id> (1-based idx into that hero's
# list) + master switch bExecHack. Apply: v5.7-style overrides of the
# execution proto/id getters on the doll / show-model / avatar classes,
# keyed by the object's own hero id via _hero_id_deep.
# ============================================================


# ============================================================
# v8.28: ZELEWIN'S LOBBY HERO-SKIN CODE (@Zelewin, hall only)
# ============================================================
# Integrated as instructed: "Lobby only - in-game use the current we
# made." What is NEW from his snippet (his ShowHeroSkinModel rewrite was
# already covered by our existing wrap of the same argument, so it is
# NOT re-added - no double wrap):
#   1) SetArmClothes / ChangeArmClothes on the hall_doll classes ->
#      arm_clothes replaced by CArmClothes({300: sid}) - his import
#      path and his slot literal, first try; on import failure we log
#      once and pass the original through.
#   2) SkinStartAnimPlayer._GetHeroSkinProto -> the item_proto swapped
#      for the forced hero proto (his snippet's `returns` syntax error
#      fixed to `return`).
# Scene gate: hall only. In a match this whole block stands down and
# the v7.30/v8-core in-match machinery (device-proven) keeps running.
_zle_installed = [False]  # compatibility/diagnostic aggregate
_zle_install_state = {'arm': False, 'skin_start_anim': False}
_zle_notes = set()
_zle_applies = [0]


def _zle_log(msg):
    try:
        if msg not in _zle_notes:
            _zle_notes.add(msg)
            _plog('[ZLSKIN] %s' % (msg,))
    except Exception:
        pass


def _zle_scene_is_hall():
    try:
        s = None
        f = globals().get('_hero_scene_stable')
        if callable(f):
            s = f()
        if not s:
            g = globals().get('_scene_from_space')
            if callable(g):
                s = g()
        return s == 'hall'
    except Exception:
        return False


def _zle_forced_for(hero_id):
    """(sid, proto) for this hero, lobby-gated, or (None, None)."""
    try:
        if not sync_attrs.get('bHeroSkinHack', False):
            # v2.97: the lobby show-skin code - the game picker equips
            # through the native ArmHeroSkin flow with the legacy switch
            # OFF, so the doll reverted to default without the in-game
            # confirm.  An equipped skin must show in the lobby.
            _gfs = globals().get('_get_forced_skin')
            _has = False
            try:
                _has = bool(_gfs(hero_id)) if callable(_gfs) else False
            except Exception:
                _has = False
            if not _has:
                return None, None
        if not _zle_scene_is_hall():
            return None, None
        if not hero_id:
            return None, None
        gf = globals().get('_get_forced_skin')
        gfp = globals().get('_get_forced_skin_proto')
        sid = gf(hero_id) if callable(gf) else None
        proto = gfp(hero_id) if callable(gfp) else None
        return sid, proto
    except Exception:
        return None, None


_zle_arm_types = set()


def _zle_arm_clothes(sid, existing=None):
    """Zelewin's shape - CArmClothes with slot 300 = sid - but v8.29+
    KEEPS the other slots of the incoming arm_clothes: the v8.28 full
    replacement wiped the doll's remaining outfit slots (weapon-display
    fallout). v8.30: the incoming slots are read through whatever the
    real object offers (keys()/items()/int __dict__ keys/plain dict) -
    the v2.2 log's "kept -1 slots" meant the old .m introspection never
    matched, not that the merge failed. Returns (CArmClothes, kept)."""
    try:
        from gclient.gameplay.logic_base.entities.combatavatarmembers.cimp_model import CArmClothes
        merged = {}
        try:
            if existing is not None:
                try:
                    _zle_arm_types.add(type(existing).__name__)
                except Exception:
                    pass
                if callable(getattr(existing, 'keys', None)):
                    for _k in list(existing.keys()):
                        try:
                            merged[_k] = existing[_k]
                        except Exception:
                            pass
                elif callable(getattr(existing, 'items', None)):
                    for _k, _v in existing.items():
                        merged[_k] = _v
                elif hasattr(existing, '__dict__'):
                    for _k, _v in vars(existing).items():
                        if isinstance(_k, int):
                            merged[_k] = _v
                elif isinstance(existing, dict):
                    merged.update(existing)
        except Exception:
            pass
        kept = len([_k for _k in merged if _k != 300])
        merged[300] = sid
        return CArmClothes(merged), kept
    except Exception as _e:
        _zle_log('CArmClothes import failed: %r' % (_e,))
        return None, 0


def _zle_install_skin_start_anim(done=None):
    """Install the late SkinStartAnimPlayer channel independently of arms."""
    if _zle_install_state.get('skin_start_anim'):
        return False
    try:
        player_cls = None
        modules = []
        exact = sys.modules.get(
            'gclient.gamesystem.uihall.uihero.skin_start_anim_player')
        if exact is not None:
            modules.append(exact)
        else:
            # Bounded fallback for vendor builds that suffix the module;
            # never dir() every loaded game module on a worker thread.
            for module_name, mod in list(sys.modules.items()):
                if (mod is not None
                        and module_name.endswith('.skin_start_anim_player')):
                    modules.append(mod)
                    break
        for mod in modules:
            candidate = getattr(mod, 'SkinStartAnimPlayer', None)
            if (isinstance(candidate, type)
                    and callable(getattr(
                        candidate, '_GetHeroSkinProto', None))):
                player_cls = candidate
                break
        if player_cls is None:
            _zle_log('SkinStartAnimPlayer not found yet (retry scheduled)')
            return False
        fn = vars(player_cls).get('_GetHeroSkinProto')
        if (getattr(fn, '_zle_wrap', False)
                or '_orig__GetHeroSkinProto' in vars(player_cls)):
            _zle_install_state['skin_start_anim'] = True
            return False
        if not callable(fn):
            return False

        def _make_proto(orig_fn):
            def _w(self, item_proto, *args, **kwargs):
                try:
                    if sync_attrs.get('bHeroSkinHack', False):
                        hero_id = None
                        try:
                            if hasattr(item_proto, 'get'):
                                hero_id = item_proto.get('hero_id')
                            elif item_proto is not None:
                                hero_id = getattr(item_proto, 'hero_id', None)
                        except Exception:
                            hero_id = None
                        # This native method accepts a LOBBY item and performs
                        # its own hero_skin_data lookup.  Keep that contract;
                        # do not pass the already-resolved hero row here.
                        _sid, proto = _zle_forced_for(hero_id)
                        if proto is not None:
                            item_proto = proto
                except Exception:
                    pass
                return orig_fn(self, item_proto, *args, **kwargs)
            _w._zle_wrap = True
            _w._treacky_orig = orig_fn
            return _w

        setattr(player_cls, '_orig__GetHeroSkinProto', fn)
        setattr(player_cls, '_GetHeroSkinProto', _make_proto(fn))
        _zle_install_state['skin_start_anim'] = True
        if done is not None:
            done.append('SkinStartAnimPlayer._GetHeroSkinProto')
        _zle_log('SkinStartAnimPlayer installed independently')
        return True
    except Exception as exc:
        _zle_log('SkinStartAnimPlayer hook failed: %r' % (exc,))
        return False


def _zle_install():
    done = []
    arm_seen = False
    # ---- 1) his hall_doll arm-clothes wraps ------------------------
    # v8.31: sys.modules ONLY (the v2.3 boot-storm lesson - never
    # import game modules from our own threads). The Timer(30) retry
    # keeps calling this until the game itself loads hall_doll.
    try:
        _hd = sys.modules.get('gclient.gamesystem.entities.hall_doll')
        for _cls_name in (dir(_hd) if _hd is not None else ()):
            try:
                _cls = getattr(_hd, _cls_name)
                if not isinstance(_cls, type):
                    continue
                # v8.29: Doll-family ONLY. v8.28 also wrapped
                # DollModelComponent / HallModelComponent - the
                # weapon-display components - which is part of the
                # weapon-skin fallout in the v8.28 device report.
                if _cls_name not in ('Doll', 'DollLike', 'CalculationDoll',
                                     'BigHeadCalculationDoll'):
                    continue
                for _m in ('SetArmClothes', 'ChangeArmClothes'):
                    _fn = getattr(_cls, _m, None)
                    if not callable(_fn):
                        continue
                    if (getattr(_fn, '_zle_wrap', False)
                            or ('_orig_' + _m) in vars(_cls)):
                        arm_seen = True
                        continue

                    def _make_arm(orig_fn, label):
                        def _w(self, arm_clothes, *a, **k):
                            try:
                                # v8.34: the game's own re-dress IS the
                                # lobby rebuild signal (post-match the
                                # game calls SetArmClothes but never
                                # Load/Reload again - the v8.33 log had
                                # every retry showed=0 while this very
                                # call carried our merged pick).
                                # Register the doll so the retry passes
                                # find it WITHOUT a heap walk.
                                try:
                                    _striker_doll_note(self)
                                except Exception:
                                    pass
                                # v8.35: FRESH hero first. The v8.34 log
                                # caught the stale-hint clobber: right
                                # after a striker swap the game equipped
                                # the NEW hero's pick itself
                                # (ArmHeroSkin -> 3001240014) and our
                                # merge overwrote slot 300 with the OLD
                                # hero's pick - _hero_id_deep let the
                                # stale _treacky_hero_hint (101) win
                                # over the doll's own fresh GetHeroId.
                                hid = None
                                try:
                                    _gh = getattr(self, 'GetHeroId', None)
                                    if callable(_gh):
                                        hid = _gh()
                                except Exception:
                                    hid = None
                                if not hid:
                                    hid = paint_hero[0] or None
                                # v8.35: during the swap window a doll
                                # may still report the OLD hero - merging
                                # then clobbers the game's own equip of
                                # the new striker's skin. Stand down and
                                # let the game's dress stand.
                                try:
                                    if (hid and paint_hero[0]
                                            and hid != paint_hero[0]
                                            and time.time()
                                            < swap_gate_until[0]):
                                        hid = None
                                except Exception:
                                    pass
                                sid, _proto = _zle_forced_for(hid)
                                if sid:
                                    # A slot-300 arm merge is only a dress;
                                    # it is NOT proof that the native hero
                                    # body, intro, attachments and effects
                                    # were built. v10.6 logged show-false=1
                                    # after this path had written the full
                                    # paint signature, suppressing the one
                                    # authentic ShowHeroSkinModel required
                                    # after the scene returned. Keep the doll
                                    # registered, but let the next pass show
                                    # it once; a successful full show writes
                                    # the signature and stops later retries.
                                    try:
                                        _cur = None
                                        if callable(getattr(arm_clothes, 'get', None)):
                                            _cur = arm_clothes.get(300)
                                        elif isinstance(arm_clothes, dict):
                                            _cur = arm_clothes.get(300)
                                        if _cur == sid:
                                            # already our pick: no rebuild
                                            return orig_fn(self, arm_clothes, *a, **k)
                                    except Exception:
                                        pass
                                    # v2.105: request the arm-skin
                                    # resources before the rebuild.
                                    try:
                                        if sid:
                                            _dl2105b = globals().get(
                                                'try_dlc_download')
                                            if callable(_dl2105b):
                                                _dl2105b(sid, [])
                                    except Exception:
                                        pass
                                    ac, kept = _zle_arm_clothes(sid, arm_clothes)
                                    if ac is not None:
                                        arm_clothes = ac
                                        if _zle_applies[0] < 6:
                                            _zle_applies[0] += 1
                                            _zle_log('%s -> CArmClothes(300:%s, kept %d slots, in=%s) (#%d)'
                                                     % (label, sid, kept,
                                                        '/'.join(sorted(_zle_arm_types)) or '?',
                                                        _zle_applies[0]))
                            except Exception:
                                pass
                            return orig_fn(self, arm_clothes, *a, **k)
                        _w._zle_wrap = True
                        return _w

                    setattr(_cls, '_orig_' + _m, _fn)
                    setattr(_cls, _m, _make_arm(_fn, '%s.%s' % (_cls_name, _m)))
                    arm_seen = True
                    done.append('%s.%s' % (_cls_name, _m))
            except Exception:
                continue
    except Exception as _e:
        _zle_log('hall_doll scan failed: %r' % (_e,))

    # ---- 2) late native intro resolver, tracked independently --------
    _zle_install_skin_start_anim(done)
    if arm_seen:
        _zle_install_state['arm'] = True
    _zle_installed[0] = bool(_zle_install_state['arm']
                             and _zle_install_state['skin_start_anim'])
    if done:
        _zle_log('installed (lobby-only): %r state=%r'
                 % (done, _zle_install_state))


try:
    _zle_install()
except Exception as _zle_boot_err:
    _zle_log('boot failed: %r' % (_zle_boot_err,))
try:
    _zle_timer = threading.Timer(30.0, _zle_install)
    _zle_timer.daemon = True
    _zle_timer.start()
except Exception:
    pass



# ============================================================
# v8.29: ZELEWIN'S IHallItems OWNERSHIP UNLOCK (@Zelewin)
# ============================================================
# Replaces the removed Emotes/Executions unlock features: while the
# "Unlock items" switch is ON, the game's own hall-item store answers
# OWNED for skin items - the vault/collection and the game's native
# equip flows then do all the work. His method set, his sub_type tuple
# and his _orig_ guard names, as sent. The wrap keeps his logic but
# resolves the raw function first (staticmethod/classmethod-safe, the
# same pattern the old emote-own wrap used in this game).
_COSM_CACHE = {}
_COSM_PREFIX = ('11', '12', '13', '14', '15', '16', '17', '20', '30', '31',
                '51', '52', '53', '54', '55', '60', '61', '62')


def _is_skin_item(item_id):
    return True


def _unlock_active():
    try:
        # The scoped native cosmetic candidate must not resurrect the retired
        # broad ownership predicate through a stale bUnlockAll saved setting.
        if globals().get('EMOTE_ONLY', False):
            return False
        return bool(sync_attrs.get('bUnlockAll', False))
    except Exception:
        return False


_zlunlock_notes = set()


def _zlunlock_log(msg):
    try:
        if msg not in _zlunlock_notes:
            _zlunlock_notes.add(msg)
            _plog('[ZLUNLOCK] %s' % (msg,))
    except Exception:
        pass


def _zlu_sig(meth, a):
    parts = []
    for _x in a[:5]:
        if isinstance(_x, bool):
            parts.append('b')
        elif isinstance(_x, int):
            parts.append(str(_x))
        else:
            try:
                parts.append(type(_x).__name__)
            except Exception:
                parts.append('?')
    return '%s(%s)' % (meth, ','.join(parts))


def _zlu_res(r):
    try:
        if r is None:
            return 'None'
        if isinstance(r, (list, tuple, set)):
            return 'len=%d' % len(r)
        if isinstance(r, dict):
            return 'dict(%d)' % len(r)
        return type(r).__name__
    except Exception:
        return '?'


_zlu_calls = {}
_zlu_subtypes = {}


def _zlu_note(meth, a, extra=''):
    """v8.30: bounded distinct-call logging - the v2.2 vault report
    ("weapons ain't showing, pistols/melees did, nothing equips")
    could not be diagnosed because the wraps were silent. First 60
    distinct (method, int args) per method land as [ZLU-CALL] lines."""
    try:
        seen = _zlu_calls.get(meth)
        if seen is None:
            seen = _zlu_calls[meth] = set()
        if len(seen) < 60:
            sig = _zlu_sig(meth, a)
            if sig not in seen:
                seen.add(sig)
                _plog('[ZLU-CALL] %s%s' % (sig, extra))
        for _x in a:
            if isinstance(_x, int) and not isinstance(_x, bool) \
                    and 0 < _x < 10000:
                st = _zlu_subtypes.get(meth)
                if st is None:
                    st = _zlu_subtypes[meth] = set()
                if _x not in st and len(st) < 60:
                    st.add(_x)
                    _plog('[ZLU-SUB] %s sub_type=%d' % (meth, _x))
                break
    except Exception:
        pass


def _zlu_scan():
    """v8.30: one-shot class scan of cimp_hall_item - the rt16 dump
    shows IHallParts/IHallSlots/IItemIdDict siblings live there too;
    log their predicate/getter surface so the next wrap round targets
    the right class."""
    try:
        _chi = sys.modules.get(
            'gclient.gamesystem.entities.avatarmembers.cimp_hall_item')
        names = []
        for _cn in dir(_chi):
            _co = getattr(_chi, _cn, None)
            if not isinstance(_co, type):
                continue
            _ms = [m for m in dir(_co)
                   if m.startswith(('Has', 'Get', 'Item', 'Iter', '_Has'))
                   and callable(getattr(_co, m, None))]
            if _ms:
                names.append('%s:[%s]' % (_cn, ','.join(_ms)))
        if names:
            _plog('[ZLU-SCAN] %s' % (' | '.join(names)[:1500],))
    except Exception as _e:
        _plog('[ZLU-SCAN] failed %r' % (_e,))



class _ZLVal(int):
    """An int that survives being CALLED like a method - the rt16 dump
    lists the IHallItem fields as methods, but property-style reads
    must work too. _ZLVal(5) == 5, _ZLVal(5)() == 5."""
    def __call__(self):
        return int(self)


class _ZLNullProto(object):
    """v8.32: stand-in when no real data row was found for a faked
    item. The v8.31 device log crashed the vault DIY panel
    (gun_diy_ui_component.RefreshItem:657) with "'NoneType' object
    has no attribute 'get'" - item_proto was a bare None. This
    answers .get()/.keys()/[] like an EMPTY row so game reads degrade
    to defaults instead of AttributeError."""
    def get(self, k, d=None):
        return d

    def keys(self):
        return ()

    def __contains__(self, k):
        return False

    def __getitem__(self, k):
        raise KeyError(k)

    def __bool__(self):
        return True

    def __getattr__(self, name):
        raise AttributeError(name)


_ZLU_PROTO_TABLES = (
    'gclient.data.lobby_item_data',
    'gclient.data.lobby_gun_skin_item_data',
    'gclient.data.gun_skin_item_data',
)


def _zlu_lookup_proto(item_id):
    """v8.32: find the REAL data row for a faked item id - try every
    plausible item table (module dict / .data / int + str keys)."""
    for _tname in _ZLU_PROTO_TABLES:
        try:
            _tm = sys.modules.get(_tname)
            if _tm is None:
                continue
            for _acc in (lambda m: m[item_id],
                         lambda m: m.data[item_id],
                         lambda m: m.data.get(item_id),
                         lambda m: m.data.get(str(item_id))):
                try:
                    _v = _acc(_tm)
                    if _v is not None:
                        return _v, _tname.rsplit('.', 1)[-1]
                except Exception:
                    continue
        except Exception:
            continue
    return None, 'none'


def _zl_cmp_key(other):
    try:
        return (_safe_int(getattr(other, 'quality', 0), 0),
                _safe_int(getattr(other, 'item_id', 0)
                          or getattr(other, 'id', 0), 0))
    except Exception:
        return (0, 0)


class _ZLFakeItem(object):
    """v8.31: a duck-typed IHallItem for an item the player does not
    own. Known accessors (rt16 dump) get owned/permanent values as
    _ZLVal; anything unknown falls through __getattr__ to a permissive
    _ZLVal(0) so game reads never AttributeError.
    v8.32: the real data row is looked up in THREE item tables and
    item_proto is never None (_ZLNullProto if the row was not found);
    unknown attribute reads proxy to the real row FIRST - the v8.31
    vault DIY crash proved the game reads fields our name-guess list
    never covered."""
    def _zl_key(self):
        try:
            return (_safe_int(getattr(self, 'quality', 0), 0),
                    _safe_int(getattr(self, 'item_id', 0), 0))
        except Exception:
            return (0, 0)

    def __lt__(self, other):
        try:
            return self._zl_key() < _zl_cmp_key(other)
        except Exception:
            return False

    def __le__(self, other):
        try:
            return self._zl_key() <= _zl_cmp_key(other)
        except Exception:
            return False

    def __gt__(self, other):
        try:
            return self._zl_key() > _zl_cmp_key(other)
        except Exception:
            return False

    def __ge__(self, other):
        try:
            return self._zl_key() >= _zl_cmp_key(other)
        except Exception:
            return False

    def __eq__(self, other):
        try:
            return self._zl_key() == _zl_cmp_key(other)
        except Exception:
            return False

    def __ne__(self, other):
        try:
            return self._zl_key() != _zl_cmp_key(other)
        except Exception:
            return True

    def __hash__(self):
        try:
            return hash(self._zl_key())
        except Exception:
            return 0

    def __init__(self, item_id):
        self.item_id = item_id
        self.guid = 'zl%d' % (item_id,)
        proto, proto_src = _zlu_lookup_proto(item_id)
        self.item_proto = proto if proto is not None else _ZLNullProto()
        self._zl_proto_src = proto_src
        try:
            _st = self._pf(('sub_type', 'detail_sub_type'), 0)
            _gun = self._pf(('gun_id', 'equip_id', 'weapon_id'), 0)
            _sk = self._pf(('skin_id', 'gun_skin_id',
                            'skin_template_id', 'template_id',
                            'item_id'), item_id)
            _eq = self._pf(('equip_id', 'gun_id'), 0)
            _ml = self._pf(('melee_id',), 0)
            _q = self._pf(('quality', 'rarity'), 0)
        except Exception:
            _st, _gun, _sk, _eq, _ml, _q = 0, 0, item_id, 0, 0, 0
        self.sub_type = _ZLVal(_st)
        self.gun_id = _ZLVal(_gun)
        self.skin_id = _ZLVal(_sk)
        self.equip_id = _ZLVal(_eq)
        self.melee_id = _ZLVal(_ml)
        self.guise_id = _ZLVal(self._pf(('guise_id',), 0))
        self.hangings_id = _ZLVal(0)
        self.reticle_id = _ZLVal(0)
        self.reticle_template_id = _ZLVal(0)
        self.skin_optic_id = _ZLVal(0)
        self.skin_optic_part_id = _ZLVal(0)
        self.quality = _ZLVal(_q)
        self.mall_id = _ZLVal(0)
        self.begin_time = _ZLVal(0)
        self.bind_qualifying_expire_time = _ZLVal(0)
        self.expired = _ZLVal(0)          # falsy, callable -> 0
        self.bind_qualifying_expired = _ZLVal(0)
        self.is_experience_item = _ZLVal(0)
        self.is_bind_qualifying = _ZLVal(0)
        self.can_disassemble = _ZLVal(0)
        self.can_pileup = _ZLVal(1)       # truthy, callable -> 1
        self.can_reuse = _ZLVal(1)
        self.is_permanent = _ZLVal(1)
        self.is_begin = _ZLVal(1)

    def _pf(self, names, default):
        p = self.item_proto
        if p is None:
            return default
        for nm in names:
            try:
                v = getattr(p, nm, None)
                if v is None and callable(getattr(p, 'get', None)):
                    v = p.get(nm)
                if v is not None:
                    return v
            except Exception:
                continue
        return default

    def __getattr__(self, name):
        if name.startswith('__'):
            raise AttributeError(name)
        # v8.32: unknown reads go to the REAL data row first - the
        # game's DIY panel reads fields our name-guess list never
        # covered; the real row answers them with real values.
        try:
            p = self.__dict__.get('item_proto')
            if p is not None and not isinstance(p, _ZLNullProto):
                v = getattr(p, name, None)
                if v is None and callable(getattr(p, 'get', None)):
                    v = p.get(name)
                if v is not None:
                    return v
        except Exception:
            pass
        return _ZLVal(0)

    def __bool__(self):
        return True

    def __str__(self):
        return 'IHallItem<zl %d>' % (self.item_id,)

    def get_time(self):
        return 0

    def AddUseDay(self, *a, **k):
        return None

    def AddUseTime(self, *a, **k):
        return None

    def DecUseTime(self, *a, **k):
        return None

    def InExpireTimeWarningPeriod(self, *a, **k):
        return False

    def IsExpireTimeWarningItem(self, *a, **k):
        return False

    def Pack(self, *a, **k):
        return ''

    @property
    def mall_proto(self):
        return None


_zlu_fakes = {}
_zlu_fake_by_id = {}
_zlu_fake_ids = set()


def _zlu_fake_note(iid, proto_src='', row=''):
    try:
        if iid not in _zlu_fake_ids and len(_zlu_fake_ids) < 20:
            _zlu_fake_ids.add(iid)
            _plog('[ZLU-FAKE] GetItemByItemId(%d) -> fake owned item '
                  'proto=%s %s' % (iid, proto_src or 'none', row or ''))
    except Exception:
        pass


def _zl_fake_row_desc(it):
    """v8.32: one-line evidence - which table answered and which
    field names the real row carries (so a still-broken DIY panel
    can be mapped exactly from the next log)."""
    try:
        p = it.__dict__.get('item_proto')
        if p is None or isinstance(p, _ZLNullProto):
            return 'row=MISSING'
        if callable(getattr(p, 'keys', None)):
            ks = list(p.keys())
            if ks:
                return 'row=%r' % (ks[:18],)
        return 'row=%s' % (type(p).__name__,)
    except Exception:
        return 'row=?' 


def _install_hall_item_hooks():
    """v8.33: REMOVED by user request - the IHallItems unlock-all
    feature (predicate overrides + owned-item fakes) is gone. This is
    now a permanent no-op; nothing wraps cimp_hall_item anymore.
    (The v8.30/v8.31 implementation follows for the record only.)"""
    return 0


def _install_hall_item_hooks_v832():
    """Zelewin's IHallItems ownership wraps. Idempotent via his
    _orig_ guards; the wrappers check the switch on every call, so
    installing early (gate off) is harmless. v8.30: (a) the
    HasItemsByDetailSubType override now covers ANY plausible sub_type
    (int 1..9999) while the switch is on - his tuple (300, 623, 614,
    602-607) had no weapon-skin sub_types, so the vault's weapon tab
    stayed locked on v2.2; (b) the GETTERS (Get/GetItemByItemId/
    GetItemsByDetailSubType/...) are wrapped LOG-ONLY - passthrough +
    [ZLU-CALL] - because the rt16 dump shows the lists/equips read
    those, not the predicates."""
    # v8.31: sys.modules ONLY - importing game modules from our own
    # threads raced the game's boot imports through its custom
    # importer and corrupted it for the whole session (the v2.3 boot
    # storm). The game loads this module itself; we wrap what is
    # already loaded.
    try:
        _chi = sys.modules.get(
            'gclient.gamesystem.entities.avatarmembers.cimp_hall_item')
        if _chi is None:
            return 0
    except Exception:
        return 0

    installed = 0
    try:
        cls = _chi.IHallItems
    except Exception:
        return 0

    # (method, his guard attr, override kind)
    _targets = (
        ('_HasItemById', '_orig__HasItemById', 'bool'),
        ('HasItemByItemId', '_orig_HasItemByItemId', 'bool'),
        ('ItemCountByItemId', '_orig_ItemCountByItemId', 'count'),
        ('HasItemsByDetailSubType', '_orig_HasItemsByDetailSubType', 'sub'),
    )

    def _mk(_prev, _kind, _label):
        def iwrapper(*a, **kw):
            try:
                _zlu_note(_label, a,
                          ' gate=ON' if _unlock_active() else ' gate=off')
            except Exception:
                pass
            try:
                if _unlock_active():
                    if _kind == 'sub':
                        for _x in a:
                            if (isinstance(_x, int)
                                    and not isinstance(_x, bool)
                                    and 0 < _x < 10000):
                                # v8.30: any plausible detail sub_type
                                # answers owned - his tuple had no
                                # weapon-skin sub_types.
                                return True
                    else:
                        for _x in a:
                            if isinstance(_x, int) \
                                    and not isinstance(_x, bool):
                                if _is_skin_item(_x):
                                    return 1 if _kind == 'count' else True
                                break
            except Exception:
                pass
            return _prev(*a, **kw)
        iwrapper._zlunlock = True
        iwrapper._label = _label
        return iwrapper

    # ---- his four predicates (override + logging) ----------------------
    try:
        for meth, guard, kind in _targets:
            try:
                if not hasattr(cls, meth) or hasattr(cls, guard):
                    continue
                static = inspect.getattr_static(cls, meth)
                if getattr(static, '_zlunlock', False):
                    continue
                prev = static.__func__ if isinstance(
                    static, (staticmethod, classmethod)) else static
                if not callable(prev):
                    continue
                setattr(cls, guard, prev)
                w = _mk(prev, kind, 'IHallItems.%s' % meth)
                if isinstance(static, staticmethod):
                    setattr(cls, meth, staticmethod(w))
                elif isinstance(static, classmethod):
                    setattr(cls, meth, classmethod(w))
                else:
                    setattr(cls, meth, w)
                installed += 1
            except Exception:
                continue
    except Exception:
        pass

    # ---- the getters (LOG-ONLY passthrough - the list/equip drivers) ---
    _getters = ('Get', 'GetItemByGuid', 'GetItemByItemId',
                'GetItemByMeleeGuiseId', 'GetItemsByDetailSubType',
                'GetItemsByDetailSubTypeList', 'GetItemsBySubType',
                'GetUpgradeItemInfo', 'IterItemsByDetailSubType')

    def _mk_get(_prev, _label):
        def gwrapper(*a, **kw):
            r = _prev(*a, **kw)
            try:
                _zlu_note(_label, a, ' -> %s' % _zlu_res(r))
            except Exception:
                pass
            # v8.31: the [ZLU-CALL] evidence - the weapon tab asks
            # GetItemByItemId(id) for every gun skin and gets len=0.
            # While the switch is ON, an EMPTY answer for a skin item
            # returns one duck-typed fake owned item; guid lookups
            # check the fake map first.
            try:
                if _unlock_active():
                    if _label.endswith('GetItemByItemId'):
                        _iid = None
                        for _x in a:
                            if isinstance(_x, int) \
                                    and not isinstance(_x, bool):
                                _iid = _x
                                break
                        if _iid is not None and _is_skin_item(_iid) and not r:
                            _it = _zlu_fake_by_id.get(_iid)
                            if _it is None:
                                _it = _ZLFakeItem(_iid)
                                _zlu_fake_by_id[_iid] = _it
                                _zlu_fakes[_it.guid] = _it
                                _zlu_fake_note(
                                    _iid,
                                    getattr(_it, '_zl_proto_src', ''),
                                    _zl_fake_row_desc(_it))
                            return [_it]
                    elif _label.endswith('.Get') or _label.endswith('GetItemByGuid'):
                        for _x in a:
                            if isinstance(_x, str):
                                _it = _zlu_fakes.get(_x)
                                if _it is not None:
                                    return _it
                                break
            except Exception:
                pass
            return r
        gwrapper._zlunlock = True
        gwrapper._label = _label
        return gwrapper

    try:
        for meth in _getters:
            try:
                if not hasattr(cls, meth) or hasattr(cls, '_origz_' + meth):
                    continue
                static = inspect.getattr_static(cls, meth)
                if getattr(static, '_zlunlock', False):
                    continue
                prev = static.__func__ if isinstance(
                    static, (staticmethod, classmethod)) else static
                if not callable(prev):
                    continue
                setattr(cls, '_origz_' + meth, prev)
                w = _mk_get(prev, 'IHallItems.%s' % meth)
                if isinstance(static, staticmethod):
                    setattr(cls, meth, staticmethod(w))
                elif isinstance(static, classmethod):
                    setattr(cls, meth, classmethod(w))
                else:
                    setattr(cls, meth, w)
                installed += 1
            except Exception:
                continue
    except Exception:
        pass

    if installed:
        _zlunlock_log('IHallItems wrapped=%d (4 predicates + getters, '
                      'gate: Unlock items switch)' % installed)
        try:
            _zlu_scan()
        except Exception:
            pass
    return installed


def _zlunlock_loop():
    """v8.33: REMOVED with the unlock-all feature - exits at once."""
    return


def _zlunlock_loop_v832():
    """v8.31: NEVER import here. Sleep out the boot storm (30 s), then
    watch sys.modules every 5 s; when the game itself has loaded
    cimp_hall_item, wrap the already-loaded class."""
    time.sleep(30.0)
    _seen = False
    while True:
        try:
            _mod = sys.modules.get(
                'gclient.gamesystem.entities.avatarmembers.cimp_hall_item')
            if _mod is not None:
                if not _seen:
                    _seen = True
                    _plog('[ZLUNLOCK] cimp_hall_item loaded by the game - '
                          'wrapping (no imports from our threads)')
                if _install_hall_item_hooks():
                    return
        except Exception:
            pass
        time.sleep(5.0)


try:
    threading.Thread(target=_zlunlock_loop, daemon=True).start()
except Exception:
    pass


UDP_EXEC_PORT = 50007
_exec_sock = [None]
_exec_stats = {'sent': 0, 'bytes': 0, 'errors': 0, 'last_error': None}

EXEC_PKG = {}      # hero_id(int) -> {'name': str, 'skins': [{idx,id,name,anim}]}
EXEC_PROTO = {}    # item_id(int) -> lobby item proto (for the proto hooks)
_exec_probe_done = [False]
_exec_probe_rows_done = [False]

_EXEC_ID_FIELDS = ('execution_item_id', 'lobby_item_id', 'item_id', 'id')
_EXEC_NAME_FIELDS = ('name', 'en_name', 'english_name', 'name_en', 'skin_name')
_EXEC_HNAME_FIELDS = ('hero_name', 'name', 'en_name', 'english_name', 'name_en')
_EXEC_ANIM_FIELDS = ('anims', 'anim', 'animation', 'esm', 'graph')


def _exec_plog(msg):
    try:
        _plog('[EXEC] %s' % (msg,))
    except Exception:
        pass


def _exec_is_mapping(v):
    """v8.27: the game's tables/rows are taggeddict objects, NOT dict
    subclasses - the v8.26 log proved it (probe item row type=
    taggeddict). Duck-type instead: has .keys() and .get()."""
    if isinstance(v, dict):
        return True
    try:
        return (callable(v.keys) and callable(v.get)
                and not isinstance(v, (str, bytes, list, tuple, set)))
    except Exception:
        return False


def _exec_first(info, fields):
    if not _exec_is_mapping(info):
        return None
    for f in fields:
        try:
            v = info.get(f)
        except Exception:
            v = None
        if v:
            return v
    return None


def _exec_data_get(data, key):
    """int-first, str-fallback lookup (these tables are int-keyed).
    v8.27: taggeddict-safe membership test."""
    if not _exec_is_mapping(data):
        return None
    for k in (key, str(key)):
        try:
            if k in data:
                return data[k]
        except Exception:
            pass
    return None


def _exec_build_catalog():
    """v8.25: TWO sources, both probed, nothing silent.

    The v8.24 device log (nexora_debug 2026-10-28) proved:
      - hero_execution_data has 18 entries (one per hero) whose values are
        NOT dict-of-dicts (the v8.24 probe never fired) - parse adaptively.
      - 'execution_item_id' IS a real field name, but on WEAPON-SKIN rows
        (gun_skin_template_data), not on hero groups.
      - the emote catalog works by NAME-PREFIX scan of lobby_item_data
        ('Emote - ...', 274 items) - mirror that for executions.

    Source A: hero_execution_data, adaptive shape (flat row /
              dict-of-dicts / dict-of-scalars / list / bare item id).
    Source B: lobby_item_data name scan - 'Execution - '/'Exec - ' prefix,
              'execut'/'finish' substring (v5.7 rule), sub_type in (5, 4)
              (v5.7 subtypes). Grouped under hero 0 = 'All Heroes'.
    """
    EXEC_PKG.clear()
    EXEC_PROTO.clear()
    try:
        import gclient.data.lobby_item_data as lid
        import gclient.data.hero_data as hd
    except Exception as e:
        _exec_plog('import failed: %r' % (e,))
        return False
    lid_data = getattr(lid, 'data', None) or {}
    hd_data = getattr(hd, 'data', None) or {}

    def _hero_name_of(hid):
        hp = _exec_data_get(hd_data, hid)
        nm = _exec_first(hp, _EXEC_HNAME_FIELDS) if isinstance(hp, dict) else None
        return str(nm) if nm else ('Hero %s' % (hid,))

    # ---------- source A: hero_execution_data, adaptive ----------
    src_a = 0
    try:
        import gclient.data.hero_execution_data as hed
        hed_data = getattr(hed, 'data', None) or {}
        if hed_data and not _exec_probe_done[0]:
            _exec_probe_done[0] = True
            try:
                k0 = next(iter(hed_data))
                g0 = hed_data[k0]
                _exec_plog('probe table hero_key=%r group_type=%s group_repr=%s'
                           % (k0, type(g0).__name__, repr(g0)[:300]))
            except Exception:
                pass
        for hero_key, group in hed_data.items():
            hero_id = _safe_int(hero_key, 0)
            rows = []
            if _exec_is_mapping(group):                  # v8.27: taggeddict-safe
                if _exec_first(group, _EXEC_ID_FIELDS):
                    rows = [group]                       # flat row = the hero's execution
                else:
                    for _sub, val in group.items():
                        if _exec_is_mapping(val):        # v8.27: taggeddict rows
                            rows.append(val)
                        else:
                            iid = _safe_int(val, 0)      # dict-of-scalars: sub -> item id
                            if iid:
                                rows.append({'execution_item_id': iid})
            elif isinstance(group, (list, tuple)):
                for val in group:
                    if _exec_is_mapping(val):
                        rows.append(val)
                    else:
                        iid = _safe_int(val, 0)
                        if iid:
                            rows.append({'execution_item_id': iid})
            else:
                iid = _safe_int(group, 0)                # bare item id
                if iid:
                    rows = [{'execution_item_id': iid}]
            pkg = EXEC_PKG.setdefault(hero_id,
                                      {'name': _hero_name_of(hero_id), 'skins': []})
            for info in rows:
                if (not _exec_probe_rows_done[0] and _exec_is_mapping(info)
                        and len(list(info.keys())) > 1):
                    _exec_probe_rows_done[0] = True
                    try:
                        _exec_plog('probe row keys=%r sample=%r'
                                   % (sorted(info.keys()),
                                      dict(list(info.items())[:6])))
                    except Exception:
                        pass
                iid = _safe_int(_exec_first(info, _EXEC_ID_FIELDS), 0)
                if not iid:
                    continue
                lobby = _exec_data_get(lid_data, iid)
                nm = (_exec_first(lobby, _EXEC_NAME_FIELDS)
                      if _exec_is_mapping(lobby) else None) or str(iid)
                if _exec_is_mapping(lobby):
                    EXEC_PROTO.setdefault(iid, lobby)
                anim = _exec_first(info, _EXEC_ANIM_FIELDS) or ''
                if isinstance(anim, (list, tuple)):
                    anim = anim[0] if anim else ''
                pkg['skins'].append({'idx': 0, 'id': iid,
                                     'name': str(nm), 'anim': str(anim)})
                src_a += 1
        for hid in list(EXEC_PKG.keys()):                # drop empty groups
            if not EXEC_PKG[hid]['skins']:
                del EXEC_PKG[hid]
            else:
                for i, sk in enumerate(EXEC_PKG[hid]['skins'], start=1):
                    sk['idx'] = i
        if src_a:
            _exec_plog('source A (hero_execution_data): %d executions over %d heroes'
                       % (src_a, len(EXEC_PKG)))
        else:
            _exec_plog('source A (hero_execution_data): 0 - see probe table above')
    except Exception as e:
        _exec_plog('source A error: %r' % (e,))

    # ---------- source B: lobby name scan (the proven emote method) ----------
    src_b = 0
    try:
        pkg0 = EXEC_PKG.setdefault(0, {'name': 'All Heroes', 'skins': []})
        rule_counts = {'prefix': 0, 'substr': 0, 'subtype': 0}
        sample = []
        for item_id, proto in lid_data.items():
            name = _hero_proto_get(proto, 'name') or _hero_proto_get(proto, 'short_desc')
            nm = str(name or '').strip()
            sub = _safe_int(_hero_proto_get(proto, 'sub_type'), -1)
            hit = None
            if nm.startswith('Execution - ') or nm.startswith('Exec - '):
                hit = 'prefix'
            elif 'execut' in nm.lower() or 'finish' in nm.lower():
                hit = 'substr'
            elif sub in (5, 4):
                hit = 'subtype'
            if hit is None:
                continue
            rule_counts[hit] = rule_counts.get(hit, 0) + 1
            if item_id in EXEC_PROTO:
                continue                                  # already from source A
            EXEC_PROTO.setdefault(item_id, proto)
            pkg0['skins'].append({'idx': 0, 'id': item_id,
                                  'name': nm or str(item_id), 'anim': ''})
            src_b += 1
            if len(sample) < 4:
                sample.append((item_id, nm, sub))
        if src_b:
            _exec_plog('source B (lobby scan): %d items rules=%r sample=%r'
                       % (src_b, rule_counts, sample))
        else:
            _exec_plog('source B (lobby scan): 0 - no Execution-named items'
                       ' and no sub_type 5/4 rows')
    except Exception as e:
        _exec_plog('source B error: %r' % (e,))

    # v8.26: probe ONE catalog item row - the lobby rows may carry the
    # graph/anim linkage the play-side substitution needs.
    try:
        _pr_id, _pr = next(iter(EXEC_PROTO.items()))
        if _exec_is_mapping(_pr):                        # v8.27: taggeddict-safe
            _keys = sorted(_pr.keys())
            _sample = dict((k, str(_pr[k])[:60]) for k in _keys[:14])
        else:
            _keys = [a for a in dir(_pr) if not a.startswith('__')][:40]
            _sample = dict((a, str(getattr(_pr, a, ''))[:60]) for a in _keys[:14])
        _exec_plog('probe item row id=%s type=%s keys=%r sample=%r'
                   % (_pr_id, type(_pr).__name__, _keys, _sample))
    except Exception as _pre:
        _exec_plog('probe item row failed: %r' % (_pre,))

    if 0 in EXEC_PKG:                                     # number hero-0 skins
        for i, sk in enumerate(EXEC_PKG[0]['skins'], start=1):
            sk['idx'] = i
        if not EXEC_PKG[0]['skins']:
            del EXEC_PKG[0]

    total = sum(len(v['skins']) for v in EXEC_PKG.values())
    if not EXEC_PKG:
        _exec_plog('catalog EMPTY: both sources failed - see probes above')
    else:
        _exec_plog('catalog heroes=%d executions=%d (A=%d B=%d) sample=%r'
                   % (len(EXEC_PKG), total, src_a, src_b,
                      [(h, v['name'], len(v['skins']))
                       for h, v in list(EXEC_PKG.items())[:5]]))
    return bool(EXEC_PKG)


def _write_udp_exec(data):
    if _exec_sock[0] is None:
        try:
            import socket as _s
            _exec_sock[0] = _s.socket(_s.AF_INET, _s.SOCK_DGRAM)
            _exec_sock[0].setsockopt(_s.SOL_SOCKET, _s.SO_REUSEADDR, 1)
            try:
                _exec_sock[0].setsockopt(_s.SOL_SOCKET, _s.SO_SNDBUF, 2 * 1024 * 1024)
            except Exception:
                pass
        except Exception as _ee:
            _exec_sock[0] = False
            _exec_plog('UDP socket failed: %r' % (_ee,))
    if not _exec_sock[0]:
        return
    try:
        if isinstance(data, str):
            data = data.encode('utf-8')
        _exec_sock[0].sendto(data, ("127.0.0.1", UDP_EXEC_PORT))
        _exec_stats['bytes'] += len(data)
    except Exception as _ee:
        _exec_stats['errors'] += 1
        if _exec_stats['last_error'] != repr(_ee):
            _exec_stats['last_error'] = repr(_ee)
            _exec_plog('UDP send error: %r' % (_ee,))
        _exec_sock[0] = None


def _exec_send():
    lines = ['BEGIN']
    for hero_id, pkg in EXEC_PKG.items():
        hname = str(pkg['name']).replace('|', ' ').replace('\n', ' ')
        lines.append('H|%d|%s' % (hero_id, hname))
        for sk in pkg['skins']:
            nm = str(sk['name']).replace('|', ' ').replace('\n', ' ')
            lines.append('X|%d|%d|%d|%s' % (hero_id, sk['idx'], sk['id'], nm))
    lines.append('END')
    data = ('\n'.join(lines) + '\n').encode('utf-8')
    start = 0
    while start < len(data):
        _write_udp_exec(data[start:start + 60000])
        start += 60000
    _exec_stats['sent'] += 1


def _exec_gate():
    # v8.29: REMOVED by user request - the Executions tab and its force
    # are gone. Hard-off passthrough, stale bExecHack values ignored.
    return False
    return bool(sync_attrs.get('bExecHack', False))


def _exec_sel_ids():
    """hero_id -> selected item_id (only heroes with a live pick)."""
    out = {}
    for hero_id, pkg in EXEC_PKG.items():
        idx = _safe_int(sync_attrs.get('iExec_%d' % (hero_id,), 0), 0)
        if 0 < idx <= len(pkg['skins']):
            out[hero_id] = pkg['skins'][idx - 1]['id']
    return out


def _exec_forced_for(hero_id):
    if not _exec_gate():
        return None
    ids = _exec_sel_ids()
    if hero_id in ids and hero_id != 0:
        return ids[hero_id]
    if 0 in ids:           # the 'All Heroes' pick applies to every hero
        return ids[0]
    if len(ids) == 1:      # object's hero unknown - the single live pick
        return list(ids.values())[0]
    return None


def _exec_forced_proto_for(hero_id):
    sid = _exec_forced_for(hero_id)
    return EXEC_PROTO.get(sid) if sid else None


_EXEC_PROPS = ('execution_proto', 'cur_execution_proto', 'execution_item_proto')


def _exec_hook_property(cls, prop_name):
    orig_prop = None
    for base in getattr(cls, '__mro__', [cls]):
        found = base.__dict__.get(prop_name)
        if isinstance(found, property):
            orig_prop = found
            break
    if orig_prop is None or orig_prop.fget is None:
        return False
    orig_get = orig_prop.fget

    def _getter(self):
        result = orig_get(self)
        try:
            if _exec_gate():
                hid = _hero_id_deep(self)
                forced = _exec_forced_proto_for(hid) if hid else None
                if forced is not None:
                    return forced
        except Exception:
            pass
        return result

    setattr(cls, prop_name, property(_getter))
    return True


def _exec_candidate_classes():
    out = []
    try:
        import gclient.gamesystem.entities.hall_doll as _hd
        for n in ('Doll', 'DollLike', 'CalculationDoll', 'BigHeadCalculationDoll'):
            c = getattr(_hd, n, None)
            if c is not None:
                out.append(('hall_doll.' + n, c))
    except Exception:
        pass
    try:
        import gclient.gamesystem.models.hall_show_model as _hsm
        c = getattr(_hsm, 'HallShowModel', None)
        if c is not None:
            out.append(('HallShowModel', c))
    except Exception:
        pass
    for mod_name in ('gclient.gameplay.logic_base.entities.combat_avatar',
                     'gclient.gameplay.logic_gun_fight.combat_avatar_gun_fight',
                     'gclient.framework.entities.avatar'):
        try:
            mod = sys.modules.get(mod_name) or __import__(mod_name, fromlist=['x'])
        except Exception:
            continue
        for n in dir(mod):
            low = n.lower()
            if 'avatar' in low or 'hero' in low or 'execution' in low:
                c = getattr(mod, n)
                if isinstance(c, type):
                    out.append(('%s.%s' % (mod_name.split('.')[-1], n), c))
    return out


# ============================================================
# v8.26: THE PLAY-SIDE ENTRY POINTS
# ============================================================
# The v8.25 device log proved the id getters are NEVER queried (hook
# counters desc/arm/proto reads all 0) - the game CHOOSES the execution
# by SETTING ids and LOADING graphs. These wraps (a) probe the first
# calls per method (bounded, evidence for the next round), (b) swap any
# execution-item id argument (in EXEC_PROTO or the 605xxxxxxx space)
# for the picked one. Never force returns here - only arguments.
_EXEC_PLAY_METHODS = (
    'PlayExecuteAnim', 'ShowExecuteModel', 'ShowExecutedModel',
    'LoadBodyAttachExecutionGraph', 'LoadBodyAttachExecutionGraphs',
    'PopExecuteGraph', 'SwitchExecuteSkin', 'PrepareExecuteSkinSwitch',
    'CommitPreparedExecuteSkinSwitch', '_on_set_execution_id',
    'ExecuteCreateThirdPersonModel', 'CheckPreloadExecuteThirdModel',
    'CueChangeExecuteHeroSkin', 'CueExecuteThirdModel',
    'CueExecuteShowModel', 'CueExecuteHideModel',
    '_GetExecuteSkinSwitchItemIds', '_GetExecuteStartSkinItemId',
    '_TryApplyExecuteSkin', '_TryApplyExecuteForceSkin',
)
_exec_play_seen = {}
_exec_sub_notes = set()


def _exec_is_item_id(v):
    try:
        if isinstance(v, bool) or not isinstance(v, int):
            return False
        if v in EXEC_PROTO:
            return True
        return 6050000000 <= v <= 6059999999
    except Exception:
        return False


def _exec_graph_for(item_id):
    proto = EXEC_PROTO.get(item_id)
    if not proto:
        return None
    for f in ('execution_graph_path', 'graph_path', 'graph', 'esm'):
        v = _hero_proto_get(proto, f)
        if v and isinstance(v, str) and ('.graph' in v or 'Execution' in v):
            return v
    return None


def _exec_make_play(original, label):
    def wrapper(self, *a, **k):
        try:
            n = _exec_play_seen.get(label, 0)
            if n < 3:
                _exec_play_seen[label] = n + 1
                _exec_plog('call %s a=%r k=%r gate=%s'
                           % (label, [repr(x)[:90] for x in a],
                              sorted(k), _exec_gate()))
            forced = None
            if _exec_gate():
                try:
                    hid = _hero_id_deep(self)
                except Exception:
                    hid = None
                forced = _exec_forced_for(hid) if hid else None
                if not forced:
                    forced = _exec_forced_for(0)     # the All Heroes pick
            if forced:
                na = []
                ch = []
                for i, v in enumerate(a):
                    nv = v
                    if _exec_is_item_id(v):
                        nv = forced
                        ch.append((i, v, nv))
                    elif (isinstance(v, str)
                          and ('Execution/' in v or v.endswith('.graph'))):
                        g = _exec_graph_for(forced)
                        if g:
                            nv = g
                            ch.append((i, v[:44], g[:44]))
                    na.append(nv)
                for kk, vv in list(k.items()):
                    if _exec_is_item_id(vv):
                        k[kk] = forced
                        ch.append((kk, vv, forced))
                if ch:
                    note = '%s sub=%r' % (label, ch[:3])
                    if note not in _exec_sub_notes:
                        _exec_sub_notes.add(note)
                        _exec_plog('substituted ' + note)
                a = tuple(na)
        except Exception as _pe:
            try:
                if '_exec_play_err' not in _exec_sub_notes:
                    _exec_sub_notes.add('_exec_play_err')
                    _exec_plog('play wrap error: %r' % (_pe,))
            except Exception:
                pass
        return original(self, *a, **k)
    wrapper._treacky_exec = True
    return wrapper


def _install_exec_hooks(verbose=False):
    installed = []
    cands = _exec_candidate_classes()
    if verbose:
        named = {}
        for cname, cls in cands:
            try:
                nm = [a for a in dir(cls) if 'execut' in a.lower()]
            except Exception:
                nm = []
            if nm:
                named[cname] = nm[:12]
        _exec_plog('candidates with execution members: %r' % (named,))
    for cname, cls in cands:
        for prop in _EXEC_PROPS:
            try:
                if _exec_hook_property(cls, prop):
                    installed.append('%s.%s' % (cname, prop))
            except Exception:
                pass
        try:
            for attr in list(getattr(cls, '__dict__', {}).keys()):
                low = attr.lower()
                if ('execut' not in low or not low.endswith('id')
                        or attr.startswith('_treacky_exec_orig')):
                    # v8.26: the saved-original slots must never re-wrap
                    # (the v8.25 match-probe dump showed a double wrap)
                    continue
                fn = cls.__dict__.get(attr)
                if not callable(fn) or getattr(fn, '_treacky_exec', False):
                    continue

                def make(original):
                    def wrapper(self, *a, **k):
                        if _exec_gate():
                            hid = _hero_id_deep(self)
                            forced = _exec_forced_for(hid) if hid else None
                            if forced:
                                return forced
                        return original(self, *a, **k)
                    wrapper._treacky_exec = True
                    return wrapper

                try:
                    setattr(cls, '_treacky_exec_orig_' + attr, fn)
                    setattr(cls, attr, make(fn))
                    installed.append('%s.%s' % (cname, attr))
                except Exception:
                    pass
        except Exception:
            pass
    # v8.26: the play-side pass - probe + argument substitution
    for cname, cls in cands:
        try:
            for meth in _EXEC_PLAY_METHODS:
                fn = cls.__dict__.get(meth)
                if not callable(fn) or getattr(fn, '_treacky_exec', False):
                    continue
                setattr(cls, meth,
                        _exec_make_play(fn, '%s.%s' % (cname, meth)))
                installed.append('%s.%s' % (cname, meth))
        except Exception:
            pass
    if installed or verbose:
        _exec_plog('hooks installed=%r' % (installed,))
    return installed


def _exec_loop(gen=None):
    installed = []
    while True:
        try:
            if not EXEC_PKG:
                _exec_build_catalog()
            if EXEC_PKG:
                if not installed:
                    installed = _install_exec_hooks(verbose=True)
                _exec_send()
        except Exception as e:
            _exec_plog('loop error: %r' % (e,))
        time.sleep(5.0)


try:
    _exec_build_catalog()
    if not _ALREADY_LOADED:
        threading.Thread(target=_exec_loop, daemon=True).start()
except Exception as _exec_err:
    _exec_plog('init failed: %r' % (_exec_err,))

_plog('[BOOT] exec module v8.31 ready')
# ============================================================
# v8.39: MELEE-ONLY VAULT ACCESS + FAVORITE ANIMATION RECOVERY
#        + REAL SELECTED-SKIN UPGRADE LEVEL
# ============================================================
# Evidence (rt16, 2026-10-24):
#   * IHallItems.GetItemByItemId / HasItemByItemId / ItemCountByItemId
#     are the native owned-item reads used by the vault equip flow.
#   * VAULT_ITEMS places every melee base/skin in the 2xxxxxxxxxx
#     lobby-item namespace; Dagger's real base row is 2010000010.
#   * HallModelManager._OnSkinStartAnimDisplayEnd is the native display
#     animation completion callback; RefreshOnUpdateFavoriteBackpack is
#     the matching lobby rebuild entry point.
#   * GunUpgradeDataMgr.GetCurItemLevel / GetMaxLevel /
#     ItemId2BaseLevelItem own the real per-item upgrade state.  The
#     KILL_UI and DYNAMIC_KULL_UI features are configuration-driven.
#
# Scope / safety:
#   * The removed broad unlock installer remains a no-op.  These wraps
#     answer only for real melee lobby rows and only with bSkinHack ON.
#   * No list/sub_type unlock, no gun/emote/execution ownership changes.
#   * The favorite refresh runs AFTER the game's own end callback.
#   * Max level is read from the game for each selected item; there is
#     no hard-coded level and no blanket "every feature = True" hook.
#   * All game modules come from sys.modules.  No RPC/server calls, no
#     imports or gc walks in the retry thread.
DAGGER_BASE_ITEM = 2010000010
MELEE_ITEM_MIN = 2000000000
MELEE_ITEM_MAX = 2999999999

_v839_log_seen = {}
melee_proto_cache = {}
sel_cache = {'at': 0.0, 'ids': set()}
base_cache = {}
level_busy = set()
favorite_busy = set()


def _v839_log(key, msg, limit=3):
    """Bounded, distinct evidence lines; never per-frame spam."""
    try:
        n = _v839_log_seen.get(key, 0)
        if n >= limit:
            return
        if len(_v839_log_seen) >= 180 and key not in _v839_log_seen:
            return
        _v839_log_seen[key] = n + 1
        _plog('[V839] %s' % (msg,))
    except Exception:
        pass


def _v839_wrap_method(cls, meth, factory):
    """Install one descriptor-preserving, idempotent method wrapper."""
    guard = '_orig_v839_' + meth
    try:
        if guard in vars(cls):
            return False
        static = inspect.getattr_static(cls, meth)
        if getattr(static, '_v839_wrap', False):
            return False
        prev = (static.__func__ if isinstance(
            static, (staticmethod, classmethod)) else static)
        if not callable(prev):
            return False
        wrapper = factory(prev)
        wrapper._v839_wrap = True
        setattr(cls, guard, prev)
        try:
            if isinstance(static, staticmethod):
                setattr(cls, meth, staticmethod(wrapper))
            elif isinstance(static, classmethod):
                setattr(cls, meth, classmethod(wrapper))
            else:
                setattr(cls, meth, wrapper)
        except Exception:
            try:
                delattr(cls, guard)
            except Exception:
                pass
            return False
        return True
    except Exception:
        return False


def item_arg(a, k):
    """First real lobby/template-sized int, ignoring self and enums."""
    try:
        for x in tuple(a) + tuple(k.values()):
            if (isinstance(x, int) and not isinstance(x, bool)
                    and 1000000 <= x <= 9999999999):
                return x
    except Exception:
        pass
    return None


def call_sig(a):
    out = []
    try:
        for x in tuple(a)[:5]:
            if isinstance(x, bool):
                out.append('bool')
            elif isinstance(x, int):
                out.append(str(x))
            elif isinstance(x, str):
                # Feature names are real runtime values; logging only "str"
                # hid which kill/tracer gate the game actually queried.
                out.append(repr(x if len(x) <= 80 else x[:77] + '...'))
            else:
                out.append(type(x).__name__)
    except Exception:
        pass
    return ','.join(out)


def melee_active():
    try:
        return bool(sync_attrs.get('bSkinHack', False))
    except Exception:
        return False


def legacy_melee_active():
    """Old fake melee rows must not compete with native unlocked IHallItems."""
    try:
        if not melee_active():
            return False
        native = globals().get('category_enabled')
        return not bool(callable(native) and native('melee'))
    except Exception:
        return False


def _v841m2_native_melee_active():
    """True when native melee owns the UI; legacy wrappers must pass through."""
    try:
        native = globals().get('category_enabled')
        return bool(callable(native) and native('melee'))
    except Exception:
        return False


def is_melee_item_id(item_id):
    """Real melee row: actual catalog first, legacy 2xxx namespace second."""
    try:
        # melee2: some authentic melee rows live outside the 2xxx range.
        catalog_check = globals().get('_v841m2_is_catalog_melee_item')
        if callable(catalog_check) and catalog_check(item_id):
            return True
        if (isinstance(item_id, bool) or not isinstance(item_id, int)
                or not (MELEE_ITEM_MIN <= item_id
                        <= MELEE_ITEM_MAX)):
            return False
        if item_id in melee_proto_cache:
            return melee_proto_cache[item_id]
        proto, source = _zlu_lookup_proto(item_id)
        ok = proto is not None
        # A missing module during boot is NOT a permanent negative answer.
        # Cache only positive real-row evidence; retry absent rows later.
        if ok and len(melee_proto_cache) < 512:
            melee_proto_cache[item_id] = True
        _v839_log(('melee-proto', item_id, ok),
                  'melee item=%d real_proto=%s source=%s'
                  % (item_id, ok, source), 1)
        return ok
    except Exception:
        return False


def melee_fake(item_id):
    try:
        if not legacy_melee_active():
            return None
        old = _zlu_fake_by_id.get(item_id)
        if old is not None:
            return old
        if not is_melee_item_id(item_id):
            return None
        item = _ZLFakeItem(item_id)
        # Never manufacture an empty/unknown row for the native UI.
        if isinstance(getattr(item, 'item_proto', None), _ZLNullProto):
            return None
        _zlu_fake_by_id[item_id] = item
        _zlu_fakes[item.guid] = item
        _v839_log(('melee-fake', item_id),
                  'native melee equip owned item=%d guid=%s proto=%s %s'
                  % (item_id, item.guid,
                     getattr(item, '_zl_proto_src', 'none'),
                     _zl_fake_row_desc(item)), 1)
        return item
    except Exception as e:
        _v839_log(('melee-fake-error', item_id, repr(e)),
                  'melee fake item=%d failed: %r' % (item_id, e), 1)
        return None


def melee_fake_for_guid(value):
    """A fake GUID is in scope only when its item is independently melee."""
    try:
        if not isinstance(value, str):
            return None
        item = _zlu_fakes.get(value)
        if item is not None and is_melee_item_id(
                getattr(item, 'item_id', 0)):
            return item
    except Exception:
        pass
    return None


# v8.40: owner-supplied IHallItems snippet, adapted to the scoped melee law.
#
# Kept from the snippet: original-call-first predicates, exact *a/**kw
# forwarding, _HasItemById / HasItemByItemId / ItemCountByItemId coverage,
# and HasItemsByDetailSubType coverage.
#
# Adapted: the snippet's _is_skin_item() == True and its unrelated subtype
# tuple are NOT an unlock here. The established is_melee_item_id()
# check requires a real melee lobby row. The subtype method is a bounded
# passthrough probe until a device log proves a melee detail subtype.


def melee_predicate_factory(prev, kind):
    def wrapper(*a, **k):
        scoped = False
        item_id = None
        try:
            if legacy_melee_active():
                item_id = item_arg(a, k)
                fake_guid = any(melee_fake_for_guid(x) is not None
                                for x in tuple(a) + tuple(k.values()))
                scoped = ((item_id is not None
                           and is_melee_item_id(item_id)) or fake_guid)
        except Exception:
            scoped = False

        # Owner-snippet shape: the original sees the exact call first.
        # A scoped unowned-row exception degrades to the owned answer;
        # every non-scoped exception keeps the game's original behavior.
        try:
            result = prev(*a, **k)
        except Exception:
            if not scoped:
                raise
            result = None
        try:
            if scoped:
                _v839_log(('melee-predicate', kind, item_id),
                          '%s item=%s original=%r -> scoped owned answer'
                          % (kind, item_id, result), 1)
                return 1 if kind == 'count' else True
        except Exception:
            pass
        return result
    return wrapper


def subtype_probe_factory(prev):
    """Owner snippet's fourth hook, EVIDENCE-ONLY: never forces True."""
    def wrapper(*a, **k):
        result = prev(*a, **k)
        try:
            sub_type = None
            for x in tuple(a) + tuple(k.values()):
                if (isinstance(x, int) and not isinstance(x, bool)
                        and 0 < x < 1000000):
                    sub_type = x
                    break
            _v839_log(('melee-subtype-probe', sub_type, repr(result)),
                      'HasItemsByDetailSubType(%s) original=%r '
                      '(owner probe; passthrough)' % (sub_type, result), 1)
        except Exception:
            pass
        return result
    return wrapper

def melee_get_item_factory(prev):
    def wrapper(*a, **k):
        item_id = item_arg(a, k)
        scoped = False
        try:
            scoped = (legacy_melee_active() and item_id is not None
                      and is_melee_item_id(item_id))
        except Exception:
            scoped = False
        if not scoped:
            return prev(*a, **k)
        try:
            result = prev(*a, **k)
        except Exception:
            # Some unowned rows raise instead of returning an empty list.
            result = None
        try:
            if result:
                return result
            item = melee_fake(item_id)
            if item is not None:
                return [item]
        except Exception:
            pass
        return result
    return wrapper


def melee_guid_factory(prev):
    def wrapper(*a, **k):
        try:
            if legacy_melee_active():
                for x in tuple(a) + tuple(k.values()):
                    item = melee_fake_for_guid(x)
                    if item is not None:
                        return item
        except Exception:
            pass
        return prev(*a, **k)
    return wrapper


def install_melee_access():
    mod = sys.modules.get(
        'gclient.gamesystem.entities.avatarmembers.cimp_hall_item')
    cls = getattr(mod, 'IHallItems', None) if mod is not None else None
    if cls is None:
        return 0
    done = 0
    for meth, kind in (('_HasItemById', 'bool'),
                       ('HasItemByItemId', 'bool'),
                       ('ItemCountByItemId', 'count')):
        done += bool(_v839_wrap_method(
            cls, meth,
            lambda prev, kind=kind: melee_predicate_factory(
                prev, kind)))
    done += bool(_v839_wrap_method(
        cls, 'GetItemByItemId', melee_get_item_factory))
    done += bool(_v839_wrap_method(
        cls, 'HasItemsByDetailSubType', subtype_probe_factory))
    for meth in ('Get', 'GetItemByGuid'):
        done += bool(_v839_wrap_method(
            cls, meth, melee_guid_factory))
    if done:
        _v839_log('melee-installed',
                  'melee-only IHallItems wrappers=%d DaggerBase=%d; '
                  'sub_type/list/gun ownership untouched'
                  % (done, DAGGER_BASE_ITEM), 1)
    return done


# ---------------------------------------------------------- favorite weapon
def favorite_end_factory(prev):
    def wrapper(*a, **k):
        result = prev(*a, **k)
        manager = a[0] if a else None
        try:
            if not melee_active() or manager is None:
                return result
            if not _zle_scene_is_hall():
                return result
            key = id(manager)
            if key in favorite_busy:
                return result
            refresh = getattr(manager, 'RefreshOnUpdateFavoriteBackpack', None)
            if not callable(refresh):
                _v839_log('favorite-refresh-missing',
                          'display ended but favorite refresh is missing', 1)
                return result
            favorite_busy.add(key)
            try:
                refresh()
                _v839_log('favorite-refreshed',
                          'display animation end -> native favorite backpack '
                          'refresh', 3)
            finally:
                favorite_busy.discard(key)
        except Exception as e:
            _v839_log(('favorite-refresh-error', repr(e)),
                      'favorite refresh absorbed: %r' % (e,), 2)
        return result
    return wrapper


def install_favorite_recovery():
    mod = sys.modules.get('gclient.framework.entities.hall_space')
    cls = getattr(mod, 'HallModelManager', None) if mod is not None else None
    if cls is None:
        return 0
    done = bool(_v839_wrap_method(
        cls, '_OnSkinStartAnimDisplayEnd', favorite_end_factory))
    if done:
        _v839_log('favorite-installed',
                  'native display-end favorite recovery installed', 1)
    return int(done)


# ---------------------------------------------------------- real max level
def selected_weapon_items():
    """Current menu picks as REAL lobby item ids (not 1-based indexes)."""
    try:
        if not melee_active():
            return set()
        now = time.time()
        if now - sel_cache['at'] < 0.20:
            return set(sel_cache['ids'])
        found = set()
        _rows = list(WEP.items())
        _rows += list((globals().get('WEP_MERGED_DISPLAY') or {}).items())
        for equip_id, row in _rows:
            try:
                skins = list(row[1:])
                idx = _safe_int(sync_attrs.get('iSkin_%s' % equip_id, 0), 0)
                if not (0 < idx <= len(skins)):
                    continue
                template_id = skins[idx - 1]
                item_id = SKIN_TO_ITEM.get(template_id)
                if isinstance(item_id, int) and item_id > 0:
                    found.add(item_id)
                else:
                    _v839_log(('max-no-item-map', template_id),
                              'selected skin=%s has no lobby-item mapping; '
                              'level left honest' % template_id, 1)
            except Exception:
                continue
        sel_cache['at'] = now
        sel_cache['ids'] = set(found)
        return found
    except Exception:
        return set()


def manager_for_call(cls, a):
    try:
        for x in tuple(a):
            if callable(getattr(x, 'GetMaxLevel', None)):
                return x
        instance = getattr(cls, '_instance', None)
        if instance is not None:
            return instance
    except Exception:
        pass
    return cls


def _v839_base_item(manager, item_id):
    key = (id(manager), item_id)
    try:
        if key in base_cache:
            return base_cache[key]
        fn = getattr(manager, 'ItemId2BaseLevelItem', None)
        if not callable(fn):
            return None
        base = fn(item_id)
        if isinstance(base, int) and not isinstance(base, bool) and base > 0:
            if len(base_cache) < 512:
                base_cache[key] = base
            return base
    except Exception:
        pass
    return None


def is_selected_upgrade_item(manager, item_id):
    try:
        selected = selected_weapon_items()
        if item_id in selected:
            return True
        base = _v839_base_item(manager, item_id)
        if not base:
            return False
        for selected_id in selected:
            if base == selected_id:
                return True
            if base == _v839_base_item(manager, selected_id):
                return True
    except Exception:
        pass
    return False


def real_max_level(manager, item_id):
    key = (id(manager), item_id)
    if key in level_busy:
        return None
    fn = getattr(manager, 'GetMaxLevel', None)
    if not callable(fn):
        return None
    level_busy.add(key)
    try:
        value = fn(item_id)
        if (isinstance(value, int) and not isinstance(value, bool)
                and value > 0):
            return value
    except Exception as e:
        _v839_log(('max-error', item_id, repr(e)),
                  'GetMaxLevel item=%d failed: %r' % (item_id, e), 1)
    finally:
        level_busy.discard(key)
    return None


level_cache = {'sig': None, 'ids': set(), 'unmapped': 0}


def gun_upgrade_items():
    """Every included GUN skin with a real lobby-item mapping; never melee."""
    try:
        gun_equips = globals().get('WEP_GUN_IDS') or {}
        melee_equips = globals().get('WEP_MELEE_IDS') or {}
        signature = (len(WEP), sum(len(row) for row in WEP.values()),
                     len(SKIN_TO_ITEM), len(gun_equips))
        if level_cache['sig'] == signature:
            return level_cache['ids']
        found = set()
        unmapped = 0
        for equip_id, row in WEP.items():
            if equip_id not in gun_equips or equip_id in melee_equips:
                continue
            for template_id in list(row)[1:]:
                item_id = SKIN_TO_ITEM.get(template_id)
                if item_id is None:
                    item_id = (WEP_SKIN_INFO.get(template_id) or {}).get(
                        'lobby_item_id')
                if (isinstance(item_id, int)
                        and not isinstance(item_id, bool) and item_id > 0):
                    found.add(item_id)
                else:
                    unmapped += 1
        level_cache.update({
            'sig': signature, 'ids': found, 'unmapped': unmapped})
        _v839_log('all-gun-max-scope',
                  'all-gun max scope mapped=%d unmapped=%d'
                  % (len(found), unmapped), 1)
        return found
    except Exception:
        return set()


# #======================================================================
# //  KILLS.PY
# //
# //  This file is for: KILL CONFIG: the v841 kill-anim selection + kill-config cache + the PlayKillAnim/OnShowKillHudAnim front factories (the kill-anim companion prefetch lives here).
# //
# //  Part of the split TREACKY BS payload (v2.112).  The runtime
# //  file payload/skins_payload.py is GENERATED: run
# //  tools/build_payload.py after editing these modules.
# #======================================================================
