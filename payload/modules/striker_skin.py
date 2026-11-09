# ============================================================
# STRIKER_SKIN.PY (payload feature module)
# PROVIDES: _striker_is_local, idle_weapon_pose, _striker_native_flag, _striker_native_load_state, _striker_model_ready_for_show, _striker_refresh_native_weapon, _striker_reconcile_native_intro, _striker_native_intro_cancelled, _striker_after_native_model_load, _striker_show_on_doll, _striker_show_proto, _striker_live_dolls, _striker_lifecycle_log, _striker_cache_targets, ... +67 more | EMOTE, EMOTE_PLAIN, EMOTE_INFO, _EMOTE_SUBTYPES, _EMOTE_CLASS_NAMES, _EMOTE_TARGET_METHODS, _EA_SPECS, _EMOTE_HOOKED, _EMOTE_MODEL_ATTRS, DEBUG_PATH, ...
# REQUIRES: shared namespace (config/names/main/game_api/catalog);
#           game modules imported inline, verified against the dumps.
# Feature module - see REWRITE_PLAN.md S1.
# ============================================================
"""Striker/hero-skin feature: per-scene gating (match/emote/lobby), pick flow, repaint state (retired toggle honoured off)."""

# #======================================================================
# //  STRIKER.PY
# //
# //  This file is for: STRIKER: the local-player auth, the hero-skin doll display, the emote-class hooks, the exec gate, the auto-debug tick.
# //
# //  Part of the split TREACKY BS payload (v2.112).  The runtime
# //  file payload/skins_payload.py is GENERATED: run
# //  tools/build_payload.py after editing these modules.
# #======================================================================
def _striker_is_local(avatar):
    """True when `avatar` IS the local player's combat avatar. Used by
    the in-match add-ons so hero-id forcing never repaints ENEMY
    avatars that share a hero with one of our picks."""
    try:
        if avatar is None:
            return False
        la = globals().get('_local_combat_avatar')
        local = la() if callable(la) else None
        if local is None:
            sp = getattr(Space, '_instance', None)
            owner = getattr(sp, 'owner', None) if sp else None
            local = getattr(owner, 'combat_avatar', None) if owner else None
        if local is None:
            return False
        if avatar is local:
            return True
        for attr in ('id', 'entity_id', 'guid', 'entityid'):
            a = getattr(avatar, attr, None)
            l = getattr(local, attr, None)
            # Empty/default entity fields are not identity evidence.  In
            # particular, two different avatars with guid/entity_id=0 must
            # not both become "local" after their real IDs differ.
            if (a is not None and a == l
                    and a not in (0, '', '0', b'')):
                return True
        # v8.07: during emotes the game can show a third-person/TPS
        # avatar separate from the main combat avatar. If it links back
        # to the local avatar it is ours - force it too (v8.06 report:
        # 'skin don't show in TPS').
        for attr in ('owner', 'parent', 'master', 'follow_entity',
                     'ctrl_entity', 'bind_entity', 'source_avatar'):
            try:
                if getattr(avatar, attr, None) is local:
                    return True
            except Exception:
                pass
        return False
    except Exception:
        return False


# v7.30R22: the R21 device log showed the owner re-show recursing
# through the game's own pipeline (Doll.ShowHeroSkinModel -> ...
# -> HallShowModel.Reload -> our post-show -> ShowHeroSkinModel -> ...)
# and dying in RecursionError ~66 times per session - each one a full
# ~1000-frame unwind, which is exactly the "extreme lag as the skin is
# about to show". Every show now goes through ONE guarded, throttled
# entry point.
_striker_show_busy = [False]          # re-entrancy guard
_striker_owner_last = {}              # id(target) -> last show time
_striker_owner_sig = {}               # id(target) -> (selection, hero)
_striker_intro_done = {}              # id(target) -> native-completed generation
_striker_intro_active = {}            # id(target) -> in-flight generation
# v7.30R26: the R25 remount (SetIsShowHeroSkin(True) after paint) is
# REMOVED - it never moved the visible model, and it fired twice on
# PersonalHomepageModelCtrl right before the vault / avatar-card
# crashes (R25 device log). Never call SetIsShowHeroSkin ourselves.


def idle_weapon_pose(doll):
    """v8.18: put the weapon back in the doll's hands after a hero
    skin show. The show resets the doll into the skin start pose and
    detaches the held weapon (the 'it does the striker skin pause
    instead of holding the weapon' report) - the game's own idle
    weapon pose refresher is exactly this lever (Doll api surface:
    _TryRefreshHeroSkinIdleWeaponPose / RefreshWeaponModelAttach).
    Safe to call extra times; every call is guarded."""
    try:
        for _meth in ('_TryRefreshHeroSkinIdleWeaponPose',
                      'RefreshWeaponModelAttach'):
            try:
                _fn = getattr(doll, _meth, None)
                if callable(_fn):
                    _fn()
                    return _meth
            except Exception:
                continue
    except Exception:
        pass
    return None


def _striker_native_flag(obj, name):
    """Read a native animation flag without inventing a default state."""
    try:
        candidates = (obj, getattr(obj, 'model', None),
                      getattr(obj, 'owner', None),
                      getattr(obj, 'model_owner', None))
    except Exception:
        candidates = (obj,)
    seen = set()
    for target in candidates:
        try:
            if target is None or id(target) in seen:
                continue
            seen.add(id(target))
            value = getattr(target, name, None)
            if value is not None and not callable(value):
                return bool(value)
        except Exception:
            continue
    return None


def _striker_native_load_state(obj):
    """True/False only when the native model exposes its real load state."""
    try:
        candidates = (getattr(obj, 'model', None), obj)
    except Exception:
        candidates = (obj,)
    seen = set()
    for model in candidates:
        try:
            if model is None or id(model) in seen:
                continue
            seen.add(id(model))
            value = getattr(model, 'is_loaded', None)
            if value is None:
                continue
            if callable(value):
                value = value()
            if value is not None:
                return bool(value)
        except Exception:
            continue
    return None


def _striker_model_ready_for_show(obj):
    """Do not add a Striker load to a partially initialized BaseModel.

    The v10.7 device trace entered native HallDollShowModel.Load without
    load_tasks/warmingup_hidden_reason.  Those fields belong to the native
    constructors; filling them here would hide the broken lifecycle.  Defer
    only our repaint and let the game's own initialization/rebuild proceed.
    """
    try:
        candidates = (obj, getattr(obj, 'model', None))
    except Exception:
        candidates = (obj,)
    seen = set()
    for model in candidates:
        try:
            if model is None or id(model) in seen:
                continue
            seen.add(id(model))
            if getattr(model, '_is_destroyed', False) is True:
                return False
            if not (callable(getattr(model, 'Load', None))
                    and callable(getattr(model, 'AddLoadTask', None))):
                continue
            missing = []
            for field in ('load_tasks', 'warmingup_hidden_reason'):
                try:
                    getattr(model, field)
                except Exception:
                    missing.append(field)
            if missing:
                try:
                    _striker_lifecycle_log(
                        'model-unready:%x' % id(model),
                        'native model initialization pending; repaint '
                        'deferred fields=%r' % (missing,))
                except Exception:
                    pass
                return False
        except Exception:
            continue
    return True


def _striker_refresh_native_weapon(obj, completed=False):
    """Request the game's own attached-weapon refresh, never a forced pose.

    `completed` is used only by a real native intro-end observer.  It allows
    that authoritative cue to win over a stale playing flag; speculative
    state/load recovery remains gated by the native flags.
    """
    try:
        if not sync_attrs.get('bHeroSkinHack', False):
            return False
    except Exception:
        return False
    try:
        candidates = (obj, getattr(obj, 'owner', None),
                      getattr(obj, 'model_owner', None),
                      getattr(obj, '_skin_start_anim_npc', None),
                      getattr(obj, 'main_npc', None))
    except Exception:
        candidates = (obj,)
    seen = set()
    for target in candidates:
        try:
            if target is None or id(target) in seen:
                continue
            seen.add(id(target))
            refresh = getattr(target, 'CheckRefreshAttachedWeapon', None)
            if not callable(refresh):
                continue
            if not completed and (
                    _striker_native_flag(
                        target, 'is_play_hero_skin_anim') is True
                    or _striker_native_flag(
                        target, 'hero_skin_first_load_pending') is True
                    or _striker_native_flag(
                        target, '_skin_intro_pending_play') is True):
                continue
            if not _striker_model_ready_for_show(target):
                continue
            if _striker_native_load_state(target) is False:
                continue
            refresh()
            _striker_lifecycle_log(
                'native-weapon:%x' % id(target),
                'native idle/load -> CheckRefreshAttachedWeapon requested')
            return True
        except Exception:
            continue
    return False


def _striker_reconcile_native_intro(obj, generation=None):
    """Reconcile from native flags when an intro ends without my observer.

    A completion cue remains authoritative.  This path covers native skins
    with no intro and interrupted/cancelled intros: loaded + not playing is
    an observed native idle state, not a timer or a fabricated completion.
    """
    try:
        if generation is None:
            generation = (_hero_apply_sig[0], paint_hero[0])
        key = id(obj)
        if (_striker_intro_active.get(key) != generation
                and _striker_intro_done.get(key) != generation
                and _striker_owner_sig.get(key) != generation):
            return False
        playing = _striker_native_flag(obj, 'is_play_hero_skin_anim')
        idle = _striker_native_flag(obj, 'is_play_hero_skin_anim_idle')
        pending = (_striker_native_flag(
            obj, 'hero_skin_first_load_pending') is True
            or _striker_native_flag(obj, '_skin_intro_pending_play') is True)
        if playing is True or pending:
            if _striker_owner_sig.get(key) == generation:
                _striker_intro_active[key] = generation
            return False
        loaded = _striker_native_load_state(obj)
        if idle is True or (playing is False and loaded is True):
            _striker_intro_done[key] = generation
            _striker_intro_active.pop(key, None)
            _striker_lifecycle_log(
                'native-state-idle:%x' % key,
                'native state is idle; intro tracking reconciled')
            return True
    except Exception:
        pass
    return False


def _striker_native_intro_cancelled(obj):
    """Drop only my bookkeeping after the game's real cancel/clear call."""
    marked = 0
    try:
        candidates = (obj, getattr(obj, 'owner', None),
                      getattr(obj, 'model_owner', None))
    except Exception:
        candidates = (obj,)
    seen = set()
    for target in candidates:
        try:
            if target is None or id(target) in seen:
                continue
            seen.add(id(target))
            key = id(target)
            existed = (key in _striker_intro_active
                       or key in _striker_intro_done
                       or key in _striker_owner_sig)
            _striker_intro_active.pop(key, None)
            _striker_intro_done.pop(key, None)
            _striker_owner_sig.pop(key, None)
            if existed:
                marked += 1
        except Exception:
            continue
    if marked:
        _striker_lifecycle_log(
            'native-cancel:%x' % id(obj),
            'native intro cancel/clear -> stale tracking dropped')
    return marked


def _striker_after_native_model_load(obj):
    """Use native load completion to reconcile idle and refresh the weapon."""
    try:
        generation = (_hero_apply_sig[0], paint_hero[0])
        key = id(obj)
        if (_striker_intro_active.get(key) != generation
                and _striker_intro_done.get(key) != generation
                and _striker_owner_sig.get(key) != generation):
            return False
        if _striker_reconcile_native_intro(obj, generation):
            return _striker_refresh_native_weapon(obj)
        if (_striker_intro_done.get(key) == generation
                and key not in _striker_intro_active):
            return _striker_refresh_native_weapon(obj)
    except Exception:
        pass
    return False


def _striker_show_on_doll(obj, proto, sticky=False):
    """Show `proto` on a doll/owner: re-entrancy guarded (a show that
    re-enters the hall pipeline is skipped instead of recursing) and
    throttled per target (max one show per 2 s).
    v7.30R24 `sticky`: maintenance refreshes pass sticky=True - a
    target already painted with the CURRENT pick signature is skipped,
    so the 10 s maintenance pass never re-triggers the model's entrance
    animation (the R23 device log showed the previewer/card dolls
    re-shown every ~6 s = "keeps playing the entrance animation again
    and again"). Game-initiated post-shows stay sticky=False so a real
    skin change still gets re-forced."""
    try:
        if _striker_show_busy[0] or obj is None or proto is None:
            return False
        # A native pick is local-only.  The old hall/profile painter otherwise
        # repaints every same-hero doll found by its scene walk, including
        # teammates and another player's result/profile model.
        if (_striker_native_combat_owned()
                and not _striker_native_local_display(obj)):
            return False
        try:
            _striker_doll_note(obj)
            ctrl_note(obj)
        except Exception:
            pass
        # v8.02: paint is OFF unless the R23-mode toggle is on. The
        # v8.01 device log crashed at plain lobby entry with NO equip
        # fired: the game's own Load/Reload met our armed forces (model
        # ids, show channels, paint) = lag + native segfault. Default
        # is total stand-down; the equip verb is the one and only
        # writer and the game builds from its own equipped state.
        try:
            if not (sync_attrs.get('bHeroSkinHack', False)
                    and (sync_attrs.get('bStrikerRepaint', False)
                         or paint_once_active[0])):
                return False
        except Exception:
            pass
        key = id(obj)
        # v8.34: id()-keyed bookkeeping is validated with a weakref.
        # The game rebuilds lobby objects and a NEW object can reuse a
        # DEAD one's id(); a stale "already painted with this sig"
        # entry then silently skipped the new doll forever.
        try:
            import weakref as _wr834
            _wref_map = globals().setdefault('_striker_owner_wref', {})
            _w834 = _wref_map.get(key)
            if _w834 is None:
                if (key in _striker_owner_sig
                        or key in _striker_owner_last
                        or key in _striker_intro_done
                        or key in _striker_intro_active):
                    _striker_owner_sig.pop(key, None)
                    _striker_owner_last.pop(key, None)
                    _striker_intro_done.pop(key, None)
                    _striker_intro_active.pop(key, None)
            elif _w834() is not obj:
                _striker_owner_sig.pop(key, None)
                _striker_owner_last.pop(key, None)
                _striker_intro_done.pop(key, None)
                _striker_intro_active.pop(key, None)
                _wref_map.pop(key, None)
        except Exception:
            pass
        if sticky:
            try:
                # v7.30R27: "Lobby repaint (R23 mode)" toggle. R23
                # re-painted every maintenance pass - that is the mode
                # in which the skin actually SHOWED on the lobby /
                # previewer dolls (with the entrance anim replaying,
                # which R24's sticky skip removed along with the show).
                # Default OFF = R24+ behavior; ON = repaint every pass.
                if (not sync_attrs.get('bStrikerRepaint', False)
                        and _striker_owner_sig.get(key)
                        == (_hero_apply_sig[0], paint_hero[0])):
                    return False
            except Exception:
                pass
        now = time.time()
        try:
            # v8.18: same pick + same hero + SAME doll object => NEVER
            # re-show. The v8.14 45 s cadence still re-showed the
            # doll once a minute - and every show is a full model
            # rebuild (weapon drop + pose reset = one visible
            # glitch). A doll the game rebuilt is a NEW object (a new
            # key), a new pick changes the sig, and a hero swap
            # changes the hero - all three still show immediately.
            if _striker_owner_sig.get(key) \
                    == (_hero_apply_sig[0], paint_hero[0]):
                return False
        except Exception:
            pass
        try:
            # v8.14 (kept): a DIFFERENT pick on the same doll still
            # needs a small settle window so a pick burst does not
            # stack rebuilds.
            if now - _striker_owner_last.get(key, 0.0) < 1.5:
                return False
        except Exception:
            pass
        if max(len(_striker_owner_last), len(_striker_owner_sig),
               len(_striker_intro_done), len(_striker_intro_active)) > 64:
            try:
                _striker_owner_last.clear()
                _striker_owner_sig.clear()
                _striker_intro_done.clear()
                _striker_intro_active.clear()
                _wref_map834 = globals().get('_striker_owner_wref')
                if _wref_map834 is not None:
                    _wref_map834.clear()
            except Exception:
                pass
        # v8.35: the "painted" sig is written only AFTER a
        # successful show (the post-show write below). The v8.34 log
        # showed the pre-write poisoning the cache: a show that raised
        # (doll mid-rebuild at boot) still recorded "painted with this
        # sig" and every later pass skipped the doll forever
        # (show-false=1 on all eight retries).
        # v10.8: do not enter native Load with a partially initialized
        # model, and do not throttle the later valid retry for this defer.
        if not _striker_model_ready_for_show(obj):
            return False
        _striker_owner_last[key] = now
        try:
            import weakref as _wr834
            globals().setdefault(
                '_striker_owner_wref', {})[key] = _wr834.ref(obj)
        except Exception:
            pass
        # v8.09: the v8.07 display-channel experiment is REVERTED -
        # the v8.08 device log proved ShowDisplayModel paints "n=1" in
        # the log but never applies the skin visibly ("skin doesn't
        # show on lobby"). Intro/idle intent is passed to the native
        # skin-show channel below; animation setup itself is never dropped.
        m = getattr(obj, 'ShowHeroSkinModel', None)
        native_show = callable(m)
        if not native_show:
            # v7.30R23: some doll classes only expose ShowDisplayModel
            # (the block substitutes the proto on BOTH channels anyway)
            m = getattr(obj, 'ShowDisplayModel', None)
        if not callable(m):
            return False
        generation = (_hero_apply_sig[0], paint_hero[0])
        # If the native intro ended without reaching one of our observers,
        # use its real flags/load state before deciding to defer forever.
        _striker_reconcile_native_intro(obj, generation)
        # A fresh target uses the native default intro. Intentional
        # non-fresh repaints (scene return/emote recovery) may ask for the
        # native idle phase only after the native intro has completed.
        # v10.6 device evidence showed an in-flight intro being interrupted
        # by is_idle=True on a later retry; that retry also fabricated an
        # intro-done record without receiving a native completion.
        intro_active = _striker_intro_active.get(key) == generation
        if intro_active and _striker_intro_done.get(key) != generation:
            _striker_lifecycle_log(
                'defer-intro:%x' % key,
                'native intro in flight; idle repaint deferred')
            # The desired native intro is already running. Count this target
            # as satisfied so bounded retries do not keep rebuilding it, but
            # leave intro_done untouched until a real native idle/end cue.
            return True
        native_idle = (bool(skip_intro[0])
                       or _striker_intro_done.get(key) == generation)
        _striker_show_busy[0] = True
        try:
            if native_show and native_idle:
                m(proto, is_idle=True)
                _striker_intro_active.pop(key, None)
            else:
                if native_show:
                    _striker_intro_active[key] = generation
                    _striker_intro_done.pop(key, None)
                m(proto)
            _striker_owner_sig[key] = generation
            # Native flags decide whether an intro actually started or has
            # already reached idle.  An is_idle request alone is not proof
            # of completion.  Weapon restoration uses the game's own attach
            # refresh once native state/load says it is safe.
            _striker_reconcile_native_intro(obj, generation)
            if _striker_intro_done.get(key) == generation:
                _striker_refresh_native_weapon(obj)
            try:
                try:
                    _shown_hero = obj.GetHeroId()
                except Exception:
                    _shown_hero = _hero_id_deep(obj)
                _shown_item = _hero_proto_get(proto, 'id', None)
                _striker_lifecycle_log(
                    'show:%x:%r:%r' % (key, _shown_hero, _shown_item),
                    'native show hero=%r item=%r idle=%r playing=%r '
                    'pending=%r loaded=%r'
                    % (_shown_hero, _shown_item, native_idle,
                       _striker_native_flag(obj, 'is_play_hero_skin_anim'),
                       _striker_native_flag(
                           obj, 'hero_skin_first_load_pending'),
                       _striker_native_load_state(obj)))
            except Exception:
                pass
            # v8.18: the show rebuilt the model - put the weapon back
            # in the doll's hands right away instead of waiting for
            # the game's slow re-attach (the gameplay-roundtrip
            # recovery the user had to do by hand).
            # v8.35: the post-show idle-pose call is REMOVED (see
            # the Load/Reload site) - it was the "skin pose" the user
            # reported; the game restores its own hold after a show.
            return True
        except Exception:
            if not native_idle:
                _striker_intro_active.pop(key, None)
            raise
        finally:
            _striker_show_busy[0] = False
    except Exception:
        return False


def _striker_show_proto(hsm, proto, sticky=False):
    """Show `proto` on one hall model through whatever channel this game
    version actually has. v7.30R21: the R20 device log proved the
    current HallShowModel has NO ShowHeroSkinModel of its own (live
    models found, hero ids resolved, showed=0 every retry) - the method
    lives on the OWNER DOLL. Try the HSM first (the original BSB path,
    older game versions), then the owner doll, then any live doll."""
    # v8.09: display-channel experiment reverted (see
    # _striker_show_on_doll) - the hsm skin show is the channel that
    # actually applies the skin.
    try:
        if (hsm is not None
                and _striker_show_on_doll(hsm, proto, sticky=sticky)):
            return 'hsm'
    except Exception:
        pass
    try:
        owner = getattr(hsm, 'owner', None)
        if owner is not None and _striker_show_on_doll(owner, proto,
                                                       sticky=sticky):
            return 'owner'
    except Exception:
        pass
    return None


def _striker_live_dolls():
    """v8.29: dolls come from the shared one-sweep collector - ONE heap
    pass per scene instead of three separate walks (halls + dolls +
    profile ctrls) that cost 2.5-5.75 s per paint pass on device."""
    try:
        _halls, dolls, _ctrls = _striker_collect_scene_objects()
        if dolls:
            return dolls
    except Exception:
        pass
    return _reg_live(_striker_doll_reg, 64)


# v8.30 REGRESSION FIX: this init block was swallowed by the v8.29
# _striker_live_dolls replacement (the module-level statements that sat
# between the old body and the next def went with it) - the v2.2 device
# log showed "[HERO-SCENE] post-show error NameError(
# 'paint_once_active')" and the once-paint latch ran dead.
# Restored verbatim from v8.28:
paint_once_key = [None]
paint_once_active = [False]
skip_intro = [False]        # per-pass native is_idle intent only
last_paint_sig = [None]     # retained for existing diagnostics
last_paint_identity = [None]  # (selection signature, hero), not sig alone
emote_rearm = [False]       # v8.11: the paint after an emote
                                # teardown (Clear/Cue re-arm) is a
                                # RE-paint - no entrance anim
paint_hero = [0]            # v8.13: the hero the last paint was
                                # for. A lobby striker SWAP (Ethan ->
                                # Nova) keeps the same pick sig, so
                                # without the hero in the paint-once
                                # key the old hero's doll + anim stayed
                                # on screen.
swap_gate_until = [0.0]     # v8.14: for ~30 s after a swap only
                                # the NEW hero's doll is painted (the
                                # old striker's doll was still live and
                                # got re-shown = mixed animations)


_striker_lifecycle_notes = set()


def _striker_lifecycle_log(key, text):
    try:
        if key in _striker_lifecycle_notes:
            return
        if len(_striker_lifecycle_notes) >= 32:
            _striker_lifecycle_notes.clear()
        _striker_lifecycle_notes.add(key)
        _plog('[STRIKER] %s' % text)
    except Exception:
        pass


def _striker_cache_targets(extra=None):
    """Bounded live targets only; never walk gc on a selection event."""
    out = []
    seen = set()

    def add(obj):
        try:
            if obj is not None and id(obj) not in seen:
                seen.add(id(obj))
                out.append(obj)
        except Exception:
            pass

    try:
        if extra is not None:
            if isinstance(extra, (list, tuple, set)):
                for obj in list(extra)[:16]:
                    add(obj)
            else:
                add(extra)
        av = _avatar_seen_ref() if _avatar_seen_ref else None
        add(av)
        add(_local_combat_avatar())
        for reg, bound in ((_striker_doll_reg, 64),
                           (ctrl_reg, 32)):
            for obj in _reg_live(reg, bound):
                add(obj)
        for ref in list(_striker_hall_models)[:8]:
            try:
                obj = ref() if callable(ref) else ref
            except Exception:
                obj = None
            add(obj)
            add(getattr(obj, 'owner', None) if obj is not None else None)
    except Exception:
        pass
    return out


def _striker_invalidate_skin_caches(reason='selection', targets=None):
    """Event-driven invalidation of native cached_property/instance state.

    Selection, operator and teardown events are already rare.  Clearing only
    known live objects avoids the old periodic full-heap purge and ensures a
    newly loaded target cannot inherit the previous selection's hero row.
    """
    cleared = 0
    objects = _striker_cache_targets(targets)
    try:
        for obj in objects:
            key = id(obj)
            try:
                d = getattr(obj, '__dict__', None)
                if d is not None and 'hero_skin_proto' in d:
                    del d['hero_skin_proto']
                    cleared += 1
            except Exception:
                pass
            _striker_owner_sig.pop(key, None)
            _striker_intro_done.pop(key, None)
            _striker_intro_active.pop(key, None)
        if reason in ('selection', 'equip', 'default', 'hero-change',
                      'operator', 'teardown'):
            paint_once_key[0] = None
        _striker_lifecycle_log(
            'cache:' + reason,
            'cache invalidate reason=%s targets=%d native_rows=%d'
            % (reason, len(objects), cleared))
    except Exception:
        pass
    return cleared


def _striker_rearm_after_emote(reason='emote-end'):
    """Native completion, not a timer, releases the emote paint window."""
    try:
        if not _striker_emote_until[0]:
            return False
        _striker_emote_until[0] = 0.0
        emote_rearm[0] = True
        paint_once_key[0] = None
        _striker_refresh_tries[0] = 0
        _striker_refresh_ok[0] = False
        _striker_invalidate_skin_caches(reason)
        _striker_lifecycle_log('rearm:' + reason,
                               'native completion -> idle repaint (%s)'
                               % reason)
        return True
    except Exception:
        return False


def _striker_native_idle_observed(obj):
    """Record native _SwitchSkinIntroEndToIdle; never synthesize the cue."""
    try:
        generation = (_hero_apply_sig[0], paint_hero[0])
        marked = 0
        weapon_requests = 0
        for target in (obj, getattr(obj, 'owner', None),
                       getattr(obj, 'model_owner', None),
                       getattr(obj, '_skin_start_anim_npc', None),
                       getattr(obj, 'main_npc', None)):
            if target is None:
                continue
            key = id(target)
            if (_striker_intro_active.get(key) == generation
                    or _striker_owner_sig.get(key) == generation):
                _striker_intro_done[key] = generation
                _striker_intro_active.pop(key, None)
                marked += 1
                if _striker_refresh_native_weapon(target, completed=True):
                    weapon_requests += 1
        if marked:
            _striker_lifecycle_log(
                'native-idle:%x' % id(obj),
                'native intro completion -> idle targets=%d '
                'weapon_refresh=%d' % (marked, weapon_requests))
    except Exception:
        pass


def install_lifecycle():
    """Late, idempotent native intro/emote completion observers."""
    found = []
    specs = (
        ('gclient.gamesystem.models.hall_model_component',
         'HallModelComponent',
         (('OnPlayEmoteEnd', 'emote'),
          ('ClearPoseOnEmoteEnd', 'emote'),
          ('OnHallShowModelLoaded', 'model-load'),
          ('ClearHeroSkinPose', 'intro-cancel'))),
        ('gclient.gamesystem.entities.hall_doll', 'Doll',
         (('ClearPoseOnEmoteEnd', 'emote'),
          ('SetHeroSkinAnimIdle', 'intro'))),
        ('gclient.gamesystem.models.hall_hero_skin_model_component',
         'HeroSkinModelComponent',
         (('_SwitchSkinIntroEndToIdle', 'intro'),
          ('CancelHeroSkinAnim', 'intro-cancel'))),
        ('gclient.framework.entities.hall_space', 'HallModelManager',
         (('_OnSkinStartAnimDisplayEnd', 'intro'),)),
    )
    for mod_name, cls_name, methods in specs:
        try:
            mod = sys.modules.get(mod_name)
            cls = getattr(mod, cls_name, None) if mod is not None else None
            if not isinstance(cls, type):
                continue
            for meth, kind in methods:
                prev = cls.__dict__.get(meth)
                if (not callable(prev)
                        or getattr(prev, '_treacky_v106', False)):
                    continue

                def _make(_prev, _kind, _label):
                    def wrapper(self, *args, **kwargs):
                        result = _prev(self, *args, **kwargs)
                        try:
                            if _kind == 'intro':
                                _striker_native_idle_observed(self)
                            elif _kind == 'model-load':
                                _striker_after_native_model_load(self)
                            elif _kind == 'intro-cancel':
                                _striker_native_intro_cancelled(self)
                            else:
                                _striker_rearm_after_emote(
                                    'native:' + _label)
                        except Exception:
                            pass
                        return result
                    wrapper._treacky_v106 = True
                    wrapper._treacky_wrap = True
                    wrapper._treacky_orig = _prev
                    return wrapper

                setattr(cls, meth, _make(prev, kind,
                                         '%s.%s' % (cls_name, meth)))
                found.append('%s.%s' % (cls_name, meth))
        except Exception:
            continue
    return found


def on_hero_change(hid, source):
    """v8.14: ONE handler for a lobby striker swap, fed by BOTH verbs:
    PlayerAvatar._on_set_hero_id (the one the striker-select UI
    actually uses - the v8.13 ArmHeroSkin hook never fired on swaps)
    and ArmHeroSkin. Resets the paint, clears the intro re-arm (the
    new hero plays its entrance once), prunes the OLD hero's stale
    models so the refresh stops re-showing them, and nudges a
    refresh."""
    try:
        if not hid or hid == paint_hero[0]:
            return
        _plog('[V814] hero swap %s -> %s (%s)'
              % (paint_hero[0], hid, source))
        paint_hero[0] = hid
        paint_once_key[0] = None
        emote_rearm[0] = False
        skip_intro[0] = False
        _striker_invalidate_skin_caches('hero-change')
        swap_gate_until[0] = time.time() + 30.0
        try:
            _striker_owner_last.clear()
        except Exception:
            pass
        # stale models of the OLD hero: stop their skin anim via the
        # game's own clear and drop them from the registry.
        _pruned = 0
        try:
            for w in list(_striker_hall_models):
                hsm = None
                try:
                    hsm = w() if callable(w) else w
                except Exception:
                    hsm = None
                if hsm is None:
                    continue
                _h = None
                try:
                    _h = hsm.GetHeroId()
                except Exception:
                    _h = None
                if not _h:
                    _h = _hero_id_deep(hsm)
                if _h and _h != hid:
                    try:
                        hsm.ClearHeroSkinInfo()
                    except Exception:
                        pass
                    try:
                        _striker_hall_models.remove(w)
                    except Exception:
                        pass
                    _pruned += 1
        except Exception:
            pass
        if _pruned:
            _plog('[V814] pruned %d stale model(s) of the old hero'
                  % (_pruned,))
            # the prune's ClearHeroSkinInfo calls re-arm the intro
            # skip (the Clear wrap) - undo that: the NEW hero must
            # play its entrance animation once.
            try:
                emote_rearm[0] = False
                paint_once_key[0] = None
            except Exception:
                pass
        try:
            _lref = globals().get('_striker_lobby_refresh')
            if callable(_lref):
                _lref('hero-swap')
        except Exception:
            pass
    except Exception:
        pass
dispatch_pending = [False]  # v8.06: one deferred dispatch max
                             # (v8.18: the game-load dispatch itself is
                             # retired - the game's own Load already
                             # shows the forced pick; the flag stays
                             # for any future deferred channel)


def _striker_lobby_refresh(source='pick'):
    """v7.30R21: "show in lobby". The R20 version called
    ShowHeroSkinModel on the HallShowModel itself and the device proved
    that method does not exist there (showed=0 with live models found).
    Now every channel is tried - HSM, owner doll, gc dolls - and the
    path that worked is logged. Every attempt is logged."""
    if _hero_in_match():
        return 0
    if not sync_attrs.get('bStrikerLobby', True):
        return 0
    if not sync_attrs.get('bHeroSkinHack', False):
        return 0

    # v8.04: the R23 force mode is retired (v8.03) but the lobby paint
    # lives on as a ONE-SHOT per (skin pick, emote pick, scene entry).
    # Paint once -> the skin shows with its entrance animation once,
    # the game reloads once and re-asks GetEmoteProto (the emote
    # applies once) -> then everything stands down. No loop, no crash
    # (the v8.02 log looped because the R23 retry pass re-painted
    # forever; the v8.03 log showed nothing because the paint was
    # retired with the toggle).
    if paint_once_active[0]:
        # v8.04: a once-paint is already in flight - stand down and
        # let it finish. (Sending the concurrent caller to the body
        # here would double-paint - the exact pile-up v8.02 died of.)
        return 0
    if not sync_attrs.get('bStrikerRepaint', False):
        # v8.06: never paint over a playing emote (the v8.05 log:
        # picking an emote re-armed the paint, the instant dispatch
        # fired and killed the emote model). The key is NOT consumed;
        # the apply loop retries once the window closes.
        try:
            if time.time() < _striker_emote_until[0]:
                return 0
        except Exception:
            pass
        return paint_once(source)
    return _striker_lobby_refresh_body(source)


def paint_once(source='pick'):
    """v8.04: ONE paint pass per (skin pick, emote pick, scene entry).
    Retries (via the apply loop, every 3s while a hall is live) until
    the first successful pass, then the key is marked done - nothing
    paints again until the skin pick, the emote pick or the scene
    changes."""
    try:
        sig = _hero_apply_sig[0]
        if not sig:
            return 0
        try:
            emt = _get_forced_emote()
        except Exception:
            emt = None
        key = (sig, _scene_at[0], paint_hero[0])
        if paint_once_key[0] == key:
            return 0
        if paint_once_active[0]:
            return 0     # single flight: one pass in flight is enough
        # v8.06: the entrance animation plays only on a FRESH pick -
        # scene re-entries and post-emote re-paints skip it (the user
        # asked for exactly this: "everytime I comeback from gameplay
        # it does animation").
        identity = (sig, paint_hero[0])
        if identity != last_paint_identity[0]:
            emote_rearm[0] = False   # new selection OR hero = fresh
        fresh = (identity != last_paint_identity[0]
                 and not emote_rearm[0])
        paint_once_active[0] = True
        skip_intro[0] = not fresh
        _v820_t0 = time.time()
        try:
            n = _striker_lobby_refresh_body(source)
        finally:
            paint_once_active[0] = False
            skip_intro[0] = False
            # v8.20: swap-latency telemetry - the user reports the
            # lobby striker swap "taking forever"; this names the
            # actual cost of each paint pass.
            try:
                _dt = time.time() - _v820_t0
                if _dt > 1.0:
                    _plog('[V820] paint pass took %.2fs (n=%d) - '
                          'slow' % (_dt, n))
            except Exception:
                pass
        if n:
            paint_once_key[0] = key
            last_paint_sig[0] = sig
            last_paint_identity[0] = identity
            emote_rearm[0] = False
            _striker_emote_until[0] = 0.0
            _plog('[V8] lobby paint once (sig=%r emote=%r%s) n=%d'
                  % (sig, emt, '' if fresh else ' intro=skip', n))
        return n
    except Exception:
        return 0


def _striker_lobby_refresh_body(source):
    """The hall-object walk + paint pass (R23 body; one-shot body)."""
    gf = globals().get('_get_forced_skin_proto')
    if not callable(gf):
        return 0
    models = _striker_live_hall_models()
    n = 0
    paths = []
    owner_map = {}
    for hsm in models:
        try:
            owner = getattr(hsm, 'owner', None)
            if owner is not None:
                try:
                    _striker_doll_note(owner)
                except Exception:
                    pass
            hid = None
            if owner is not None and hasattr(owner, 'GetHeroId'):
                hid = owner.GetHeroId()
            if not hid:
                hid = _hero_id_deep(hsm)
            if not hid and paint_hero[0] and len(models) <= 2:
                # v8.33: the BOOT lobby model has no hero hint yet -
                # the game's first HallShowModel.Load fired before our
                # wrap existed (that is why the lobby only painted
                # after a match). With a small hall population the
                # unlabelled model IS the current striker.
                hid = paint_hero[0]
            if hid and owner is not None:
                # v7.30R23: dolls without their own GetHeroId can still
                # be matched to a hero through the model that owns them.
                owner_map[id(owner)] = hid
            # v10.8: apply the same swap gate to the model path that the
            # doll path below already had.  A gc sweep can rediscover the
            # old operator just after the prune; repainting it here fights
            # the native ArmHeroSkin switch and leaves the old body/intro
            # lifecycle on screen.
            try:
                if (time.time() < swap_gate_until[0]
                        and hid and paint_hero[0]
                        and hid != paint_hero[0]):
                    continue
            except Exception:
                pass
            proto = gf(hid) if hid else None
            if proto:
                how = _striker_show_proto(hsm, proto, sticky=True)
                if how:
                    n += 1
                    paths.append(how)
        except Exception:
            pass
    # v7.30R22: the doll pass ALWAYS runs now. R21 stopped after the
    # first owner-path success - and that success was usually a
    # previewer/card model, so the HOME lobby doll never got painted.
    # Never-painted dolls go FIRST (the lobby doll is one we have not
    # painted yet), and at most 3 paints per pass - each paint is a
    # real model show, and paint bursts were the R21 lag lesson. The
    # rest rotate in on later passes.
    _gc_dolls_n = 0
    try:
        # v8.07: the v8.06 device log segfaulted HERE, on the apply
        # loop's daemon thread - the gc walk hit Doll objects while the
        # MAIN thread was destroying them (hall re-entry). A gc walk on
        # the main thread is safe (same thread as the teardown); on a
        # background thread it must wait until the scene has settled -
        # the retry passes (3 s) pick it up once it has.
        try:
            _scene_age_ok = True
            if threading.current_thread() is not threading.main_thread():
                _scene_age_ok = (time.time() - _scene_at[0]) >= 2.0
        except Exception:
            _scene_age_ok = True
        dolls = _striker_live_dolls() if _scene_age_ok else []
        _gc_dolls_n = len(dolls)
        _fresh = [d for d in dolls if id(d) not in _striker_owner_last]
        _stale = [d for d in dolls if id(d) in _striker_owner_last]
        _dp = _nhid = _nproto = _nshow = 0
        for doll in _fresh + _stale:
            hid = None
            try:
                hid = doll.GetHeroId()
            except Exception:
                hid = None
            if not hid:
                hid = _hero_id_deep(doll)
            if not hid:
                # v7.30R23: hero via the model that owns this doll
                hid = owner_map.get(id(doll))
            if not hid and paint_hero[0] and len(dolls) <= 2:
                # v8.33: boot-lobby fallback - see the model loop.
                hid = paint_hero[0]
            if not hid:
                _nhid += 1
            # v8.14: right after a swap, only the NEW hero's doll
            # is painted - the old striker's doll was still live and
            # got re-shown with its own skin = the "mixed strikers"
            # animation bug. After the window, preview dolls of other
            # heroes paint again as before.
            try:
                if (time.time() < swap_gate_until[0]
                        and hid and paint_hero[0]
                        and hid != paint_hero[0]):
                    continue
            except Exception:
                pass
            proto = gf(hid) if hid else None
            if hid and not proto:
                _nproto += 1
            if proto and _striker_show_on_doll(doll, proto, sticky=True):
                n += 1
                paths.append('doll-gc')
                _dp += 1
                if _dp >= 3:
                    break
            elif proto:
                _nshow += 1
        # v8.34: when the doll pass painted NOTHING, say why - the
        # v8.33 log ended five retries at showed=0 with no clue.
        if _dp == 0 and dolls:
            try:
                _plog('[V834] doll pass painted=0: no-hid=%d '
                      'no-proto=%d show-false=%d (dolls=%d)'
                      % (_nhid, _nproto, _nshow, len(dolls)))
            except Exception:
                pass
    except Exception:
        pass
    try:
        _plog('[HERO-SCENE] lobby refresh source=%s live=%d showed=%d '
              'paths=%r registry=%d dolls=%d'
              % (source, len(models), n, paths[:4],
                 len(_striker_hall_models), _gc_dolls_n))
    except Exception:
        pass
    # v8.20: the PROFILE page's model controller paints with the
    # same ShowHeroSkinModel channel - it just was never in the
    # walk. Bounded, sticky, throttled inside _striker_show_on_doll.
    try:
        _pp = profile_paint()
        if _pp:
            n += _pp
            paths.append('profile')
    except Exception:
        pass
    return n


# EMOTES  --  port 50005, `E|idx|item_id|name` + `END`
# ============================================================
# v6.1: EXECUTIONS ARE GONE. No catalog, no hooks, no protocol field, no
# menu row, no `iExecSel`. Nothing in this build knows what an execution is.
#
# Everything below is built on the class/method map in the BS_skin reference
# dump (dump_analysis.txt), not on guessed names:
#   gclient.gamesystem.entities.hall_doll .... Doll / DollLike /
#        CalculationDoll / BigHeadCalculationDoll
#        -> ShowEmoteModel(item_proto, emote_loop=..) , ClearEmoteModel() ,
#           PlayEmoteAnim(interrupt=True)
#   gclient.gamesystem.models.hall_show_model . HallShowModel
#        -> GetEmoteProto() , SetEmoteAnimInfo(item_id, graph_file, emote_id,
#           loop=True, ..) , ClearEmoteInfo(smooth=False) ,
#           CancelEmoteAnim(smooth=False) , CueShowEmoteModel()
#   gclient.gamesystem.models.hall_model_component . HallModelComponent
#        -> ShowEmoteModel(item_proto, emote_loop=True, ..)
#   gclient.gameplay.logic_base.entities.combat_avatar . CombatAvatar /
#        PlayerCombatAvatar -> EnterEmoteState(item_id, follow_avatar='',
#        is_hall_emote=False) , EnterHallEmoteState(item_id, follow_avatar='')
#
# WHY v6.0 STILL PLAYED THE SAME EMOTE
# The old layer only rewrote values the game reads *while it is starting* an
# emote. Once the doll is looping emote A, changing iEmoteSel changes nothing:
# nobody calls ShowEmoteModel again, so the same clip keeps playing. Swapping
# GetEmoteProto/SetEmoteAnimInfo silently did nothing because the trigger had
# already happened. v6.1 therefore does what the game does when the player
# picks a different emote: tear the current emote down on the LIVE objects and
# start the forced one again. The live objects are found by a gc scan, because
# the recorder only ever sees objects that call a wrapped method *after* the
# payload was injected - the hall doll is normally built before that, which is
# why the v6.0 log said targets=0 forever.
# ============================================================

EMOTE = {}          # item_id -> the game's own proto (what the model wants)
EMOTE_PLAIN = {}    # item_id -> plain dict copy (menu/name lookups only)
EMOTE_INFO = {}

_EMOTE_SUBTYPES = (8, 604)

_EMOTE_CLASS_NAMES = (
    ('gclient.gamesystem.entities.hall_doll', 'Doll'),
    ('gclient.gamesystem.entities.hall_doll', 'DollLike'),
    ('gclient.gamesystem.entities.hall_doll', 'CalculationDoll'),
    ('gclient.gamesystem.entities.hall_doll', 'BigHeadCalculationDoll'),
    ('gclient.gamesystem.models.hall_model_component', 'HallModelComponent'),
    ('gclient.gamesystem.models.hall_show_model', 'HallShowModel'),
    ('gclient.gamesystem.models.hall_show_model', 'BigHeadCalculationShowModel'),
    ('gclient.gameplay.logic_base.entities.combat_avatar', 'CombatAvatar'),
    ('gclient.gameplay.logic_base.entities.combat_avatar', 'PlayerCombatAvatar'),
)

_emote_classes_cache = []
_emote_live_cache = {'at': 0.0, 'objs': []}
_emote_replay_seen = [-1]
_emote_replay_stats = {'targets': 0, 'done': [], 'errors': [], 'misses': 0}


def _ea_import(module_name):
    """importlib-free resolver, same shape as the rest of the payload."""
    mod = sys.modules.get(module_name)
    if mod is not None:
        return mod
    try:
        return __import__(module_name, globals(), locals(), ['__name__'], 0)
    except Exception:
        return None


def _emote_classes():
    out = []
    for mod_name, cls_name in _EMOTE_CLASS_NAMES:
        mod = _ea_import(mod_name)
        cls = getattr(mod, cls_name, None) if mod is not None else None
        if isinstance(cls, type) and cls not in out:
            out.append(cls)
    if out:
        _emote_classes_cache[:] = out
    return list(_emote_classes_cache)


def _emote_is_emote_name(item_proto):
    # v8.16: the user asked for the picker to keep ONLY real
    # emotes. The v8.15 device log had WEAPON SKINS in the wheel
    # (idx 216 = 'M1887 - Phantom Dance (Limited Time)' matched
    # the old 'dance' substring rule). The game names every real
    # emote item 'Emote - ...' - strict prefix, nothing else.
    name = _hero_proto_get(item_proto, 'name')
    if name is None:
        name = _hero_proto_get(item_proto, 'short_desc')
    try:
        nm = str(name or '').strip()
    except Exception:
        return False
    return nm.startswith('Emote - ')


def _ea_build_catalog():
    try:
        import gclient.data.lobby_item_data as lid
    except Exception as e:
        _plog("[EMOTE] import failed: %r" % (e,))
        return False
    EMOTE.clear(); EMOTE_INFO.clear(); EMOTE_PLAIN.clear()
    sample = []
    try:
        for item_id, item_proto in lid.data.items():
            if not _emote_is_emote_name(item_proto):
                continue
            name = (_hero_proto_get(item_proto, 'name') or
                    _hero_proto_get(item_proto, 'short_desc') or str(item_id))
            name = str(name)
            # v6.2: hand the GAME's own proto back to the model, not a copy.
            # dict(item_proto) lost the taggeddict behaviour and any lazily
            # resolved fields, which is why a few emotes (Emote - Throne and
            # friends, the ones with attach models) refused to play while the
            # plain dances worked.
            EMOTE[item_id] = item_proto
            try:
                EMOTE_PLAIN[item_id] = dict(item_proto)
            except Exception:
                EMOTE_PLAIN[item_id] = item_proto
            EMOTE_INFO[item_id] = name
            if len(sample) < 4:
                sample.append((item_id, name, _hero_proto_keys(item_proto, 8)))
    except Exception as e:
        _plog("[EMOTE] catalog error: %r" % (e,))
    _plog("[EMOTE] catalog emotes=%d lines=%d bytes=%d"
          % (len(EMOTE), len(EMOTE_INFO) + 2, len(_ea_lines())))
    return bool(EMOTE)


def _ea_lines():
    lines = ["BEGIN"]
    for idx, (item_id, name) in enumerate(EMOTE_INFO.items(), start=1):
        nm = str(name).replace("|", "/").replace("\n", " ").strip()
        lines.append("E|%d|%d|%s" % (idx, item_id, nm))
    lines.append("END")
    return "\n".join(lines) + "\n"


_ea_last_sig = [None]


def _ea_send():
    try:
        if not EMOTE_INFO:
            return
        # v7.30: the emote catalog is ~1.5 MB of UDP per send and went
        # out on every 5 s loop pass, match included. On change only,
        # never mid-match.
        if _hero_scene_stable() == 'match':
            return
        payload = _ea_lines()
        h = hash(payload)
        if h == _ea_last_sig[0]:
            return
        _ea_last_sig[0] = h
        _write_udp_chunked(_write_udp_emote, payload)
    except Exception as e:
        _plog("[EMOTE] send error=%r" % (e,))


def _ea_gate():
    """v8.29: REMOVED by user request - the Emotes tab and its force are
    gone (Zelewin's IHallItems ownership unlock replaces the whole
    idea). Hard-off: every emote-force path is a passthrough now, even
    if a stale bEmoteHack value arrives from an old config."""
    return False


def _emote_ids():
    return list(EMOTE_INFO.keys())


def _get_forced_emote():
    idx = _safe_int(sync_attrs.get('iEmoteSel', 0), 0)
    ids = _emote_ids()
    if ids and 0 < idx <= len(ids):
        return ids[idx - 1]
    return None


def _get_forced_emote_proto():
    item_id = _get_forced_emote()
    if item_id is None:
        return None
    proto = EMOTE.get(item_id)
    if proto is None:
        try:
            import gclient.data.lobby_item_data as lid
            proto = lid.data.get(item_id)
        except Exception:
            proto = None
    return proto


def _get_forced_emote_name():
    item_id = _get_forced_emote()
    if item_id is None:
        return None
    return EMOTE_INFO.get(item_id)


# ---- live objects -----------------------------------------------------------
_EMOTE_TARGET_METHODS = ('EnterHallEmoteState', 'EnterEmoteState',
                          'ShowEmoteModel', 'GetEmoteProto',
                          'SetEmoteAnimInfo', 'PlayEmoteAnim')
_emote_type_verdict = {}


_emote_live_refs = []
_emote_scan_at = [0.0]
_emote_scan_state = {'it': None, 'objs': [], 'seen': set(), 'at': 0.0,
                     'done_ok': False, 'ever_done': False}


def _emote_watch(obj):
    try:
        for ref in _emote_live_refs:
            if ref() is obj:
                return
        _emote_live_refs.append(weakref.ref(obj))
        if len(_emote_live_refs) > 128:
            del _emote_live_refs[:64]
    except Exception:
        pass


def _emote_live_objects(force=False):
    """Every live object that can play an emote.

    v6.2 walked the whole heap with gc.get_objects() to find them, and the
    device log shows what that costs:
        [STALL] game thread blocked 0.96s
    On a phone that is the app being killed. The list is built for free now:
    the emote hooks and the hero_skin_proto descriptor record every object the
    GAME touches. A heap scan is only a last resort, at most once every 20 s.
    """
    out = []
    for ref in list(_emote_live_refs):
        try:
            obj = ref()
        except Exception:
            obj = None
        if obj is None:
            _emote_live_refs.remove(ref)
        else:
            out.append(obj)
    if out:
        return out
    now = time.time()
    # v6.5: `force=True` used to run a FULL gc.get_objects() walk right here,
    # on the game thread, at the exact moment the menu applied an emote. The
    # 6.4 log dies on the line before the replay report - inside this walk.
    # A heap scan now never blocks: it runs in slices from _emote_scan_step(),
    # a few thousand objects per frame, and the answer is cached for 60 s.
    if _emote_live_cache['objs'] and now - _emote_live_cache['at'] < 60.0:
        return list(_emote_live_cache['objs'])
    _emote_scan_step(2500, force=True)
    return list(_emote_live_cache['objs'])


def _emote_scan_step(budget=2500, force=False):
    """Continue the heap scan for at most `budget` objects. Never blocks.

    Returns True while a scan is still in progress.
    """
    st = _emote_scan_state
    try:
        import gc as _gc
    except Exception:
        return False
    try:
        # v7.30R11: the scan exists to find replay targets for a SELECTED
        # emote. With the emote hack off or nothing selected it can only
        # burn game-thread slices for matches=0 - which is exactly what
        # happened on device: a 161 s scan ran straight through a training
        # ground entry, the game thread stalled 36 s behind it and the
        # client crashed. It also must DIE the moment a match starts.
        _perf_ea_gate = globals().get('_ea_gate')
        if not callable(_perf_ea_gate) or not _perf_ea_gate() \
                or _safe_int(sync_attrs.get('iEmoteSel', 0), 0) <= 0:
            if st['it'] is not None:
                st['it'] = None
                _plog('[EMOTE] heap scan aborted (no emote selected - '
                      'nothing to find)')
            return False
        if _hero_in_match():
            if st['it'] is not None:
                st['it'] = None
                _plog('[EMOTE] heap scan aborted (match started)')
            return False
    except Exception:
        pass
    if st['it'] is None:
        # v7.4: a completed scan is ENOUGH. The old 5-minute backoff re-walked
        # the whole heap over and over (15-60 s per cycle, forever) whenever it
        # ended with 0 matches - the device sat "scanning" constantly. Now the
        # scan runs once per session; only an explicit replay request may start
        # another, at most every 10 minutes.
        if _emote_live_refs and not force:
            return False
        if st['ever_done']:
            if not force or time.time() - st['at'] < 600.0:
                return False
        elif time.time() - st['at'] < 300.0 and st['done_ok']:
            return False
        st['it'] = iter(_gc.get_objects())
        st['objs'] = []
        st['seen'] = set()
        st['at'] = time.time()
        _plog('[EMOTE] heap scan started (sliced, %d objs/frame)' % (budget,))
    taken = 0
    try:
        for _ in range(budget):
            obj = next(st['it'])
            t = type(obj)
            verdict = _emote_type_verdict.get(t)
            if verdict is None:
                verdict = False
                for meth in _EMOTE_TARGET_METHODS:
                    if callable(getattr(t, meth, None)):
                        verdict = True
                        break
                _emote_type_verdict[t] = verdict
            if verdict and id(obj) not in st['seen']:
                st['seen'].add(id(obj))
                st['objs'].append(obj)
                taken += 1
    except StopIteration:
        st['it'] = None
        st['done_ok'] = True
        st['ever_done'] = True
        for obj in st['objs']:
            _emote_watch(obj)
        if st['objs']:
            _emote_live_cache['objs'] = st['objs'][:64]
            _emote_live_cache['at'] = time.time()
        _plog('[EMOTE] heap scan done in %.2fs matches=%d'
              % (time.time() - st['at'], len(st['objs'])))
        return False
    except Exception as e:
        st['it'] = None
        _plog('[EMOTE] heap scan error=%r' % (e,))
        return False
    return True


def _emote_scan_legacy(now):
    objs = []
    seen = set()

    def _take(o):
        if id(o) in seen:
            return
        seen.add(id(o))
        objs.append(o)

    for obj in _hero_live_objects():
        _take(obj)
    try:
        import gc as _gc
        for obj in _gc.get_objects():
            t = type(obj)
            verdict = _emote_type_verdict.get(t)
            if verdict is None:
                verdict = False
                for meth in _EMOTE_TARGET_METHODS:
                    if callable(getattr(t, meth, None)):
                        verdict = True
                        break
                _emote_type_verdict[t] = verdict
            if verdict:
                _take(obj)
    except Exception as e:
        _plog('[EMOTE] gc scan error=%r' % (e,))
    for obj in objs:
        _emote_watch(obj)
    if objs:
        _emote_live_cache['objs'] = objs[:64]
        _emote_live_cache['at'] = now
    return list(_emote_live_cache['objs'])


def _emote_call(obj, name, args=(), kwargs=None):
    fn = getattr(obj, name, None)
    if not callable(fn):
        return False
    try:
        fn(*args, **(kwargs or {}))
        return True
    except Exception:
        return False


# ---- hooks ------------------------------------------------------------------
# Emote-only. Each entry: (module, class, attr, mode)
_EA_SPECS = (
    ('gclient.gamesystem.models.hall_show_model', 'HallShowModel',
     'GetEmoteProto',            'proto'),
    ('gclient.gamesystem.models.hall_show_model', 'BigHeadCalculationShowModel',
     'GetEmoteProto',            'proto'),
    ('gclient.gamesystem.models.hall_show_model', 'HallShowModel',
     'SetEmoteAnimInfo',         'anim'),
    ('gclient.gamesystem.models.hall_show_model', 'BigHeadCalculationShowModel',
     'SetEmoteAnimInfo',         'anim'),
    ('gclient.gamesystem.entities.hall_doll', 'Doll',
     'ShowEmoteModel',           'swap'),
    ('gclient.gamesystem.entities.hall_doll', 'DollLike',
     'ShowEmoteModel',           'swap'),
    ('gclient.gamesystem.entities.hall_doll', 'CalculationDoll',
     'ShowEmoteModel',           'swap'),
    ('gclient.gamesystem.entities.hall_doll', 'BigHeadCalculationDoll',
     'ShowEmoteModel',           'swap'),
    ('gclient.gamesystem.models.hall_model_component', 'HallModelComponent',
     'ShowEmoteModel',           'swap'),
    ('gclient.gamesystem.entities.hall_doll', 'Doll',
     'PlayEmoteAnim',            'watch'),
    ('gclient.gamesystem.entities.hall_doll', 'CalculationDoll',
     'PlayEmoteAnim',            'watch'),
    ('gclient.gamesystem.models.hall_show_model', 'HallShowModel',
     'PlayEmoteAnim',            'watch'),
    ('gclient.gameplay.logic_base.entities.combat_avatar', 'CombatAvatar',
     'EnterEmoteState',          'entry'),
    ('gclient.gameplay.logic_base.entities.combat_avatar', 'PlayerCombatAvatar',
     'EnterEmoteState',          'entry'),
    ('gclient.gameplay.logic_base.entities.combat_avatar', 'CombatAvatar',
     'EnterHallEmoteState',      'entry'),
    ('gclient.gameplay.logic_base.entities.combat_avatar', 'PlayerCombatAvatar',
     'EnterHallEmoteState',      'entry'),
    ('gclient.gameplay.logic_base.entities.combat_avatar', 'CombatAvatar',
     'CheckCanUseEmote',         'allow'),
    ('gclient.gameplay.logic_base.entities.combat_avatar', 'PlayerCombatAvatar',
     'CheckCanUseEmote',         'allow'),
)

_EMOTE_HOOKED = []

_ea_once_key = [None]


def _ea_arg_id(args, kwargs):
    """v8.07: the emote item id the game passed (first int arg, or the
    id of a proto arg)."""
    try:
        for a in list(args) + list(kwargs.values()):
            if isinstance(a, int) and not isinstance(a, bool):
                return a
            if hasattr(a, 'get'):
                rid = _proto_get(a, 'id', None)
                if isinstance(rid, int):
                    return rid
    except Exception:
        pass
    return None


def _ea_seen(label, aid):
    """v8.07: one note per (wrapper, emote id) - the next device log
    must show what the game ACTUALLY passes when an emote is pressed
    in a match."""
    try:
        _herofx_note('ea-seen:%s:%s' % (label, aid),
                     '[EMOTE] seen %s id=%s' % (label, aid))
    except Exception:
        pass


def _ea_once_ok(label):
    """v8.03: the hall emote applies ONCE per (emote pick, scene
    entry). The v8.02 device log: every model rebuild asked
    GetEmoteProto again, we re-applied our emote each time, the lobby
    doll replayed its animation on every reload - the third replay
    segfaulted the engine. One ask forces; the rest answer honest
    until the pick changes or the scene is re-entered. The scene
    generation is _scene_at - the shared scene-change timestamp the
    background loops keep fresh, so a hall -> match -> hall round trip
    re-arms even though nobody asks GetEmoteProto while in the match.
    Any error here falls through to the wrapper's handler = honest."""
    _hero_scene_stable()
    key = (_get_forced_emote(), _scene_at[0], label)
    if _ea_once_key[0] == key:
        return False
    _ea_once_key[0] = key
    return True


def _emote_wrap(mode, original, label):
    def wrapper(self, *args, **kwargs):
        try:
            _game_mark_thread()
            _game_pump()
        except Exception:
            pass
        try:
            _emote_watch(self)
        except Exception:
            pass
        try:
            if _ea_gate():
                if mode == 'proto':
                    # v8.09: the auto-apply is REMOVED. The v8.03
                    # one-shot answered our emote proto on every model
                    # rebuild - which is exactly the "it auto plays
                    # emote when I get back to the lobby" report (the
                    # game asks GetEmoteProto at every hall re-entry).
                    # Emotes now show when the USER plays them (the
                    # swap/anim/entry rewrites + the menu replay).
                    pass
                elif mode == 'swap':
                    # v8.09: hall = rewrite (the v8.03-07 behavior -
                    # dolls have no local identity and the lobby wheel
                    # emote is forced through these writes); match =
                    # LOCAL avatar only (enemies keep their emotes).
                    if not _hero_in_match() or _striker_is_local(self):
                        forced = _get_forced_emote_proto()
                        if forced is not None:
                            if args:
                                args = (forced,) + tuple(args[1:])
                            else:
                                kwargs['item_proto'] = forced
                            _emote_note(label)
                    else:
                        _ea_seen(label, _ea_arg_id(args, kwargs))
                elif mode == 'entry':
                    if not _hero_in_match() or _striker_is_local(self):
                        forced = _get_forced_emote()
                        if forced is not None:
                            # v8.15: never inject an emote whose model
                            # info the game cannot build (the v8.14
                            # Throne crash - see the helper).
                            if emote_info_ok(self, forced):
                                if args:
                                    args = (forced,) + tuple(args[1:])
                                else:
                                    kwargs['item_id'] = forced
                                _emote_note(label)
                            else:
                                _plog('[V815] entry force skipped (no '
                                      'model info): %s' % (forced,))
                    else:
                        _ea_seen(label, _ea_arg_id(args, kwargs))
                elif mode == 'anim':
                    # A hero-skin item id on SetEmoteAnimInfo is the native
                    # skin-animation channel, not an emote.  Always preserve
                    # the native call and its result; intro freshness is
                    # decided by ShowHeroSkinModel(is_idle=...), never by
                    # dropping this animation setup.
                    try:
                        _aid = _ea_arg_id(args, kwargs)
                        if (_aid is not None and 3000000000 <= _aid
                                < 4000000000):
                            return original(self, *args, **kwargs)
                    except Exception:
                        pass
                    if not _hero_in_match() or _striker_is_local(self):
                        forced = _get_forced_emote()
                        if forced is not None and args:
                            args = (forced,) + tuple(args[1:])
                            _emote_note(label)
                    else:
                        _ea_seen(label, _ea_arg_id(args, kwargs))
                elif mode == 'allow':
                    if _hero_in_match():
                        # v8.07: in a match, bypass the permission
                        # check ONLY for our own forced emote. The
                        # v8.03- unconditional True may have been
                        # breaking the OWNED wheel emotes in gameplay
                        # ('emotes don't work in gameplay').
                        _forced_ea = _get_forced_emote()
                        if (_forced_ea is not None
                                and _ea_arg_id(args, kwargs)
                                == _forced_ea):
                            _emote_note(label)
                            _ea_seen(label, _forced_ea)
                            return True
                    else:
                        # the emote we are forcing is not owned, so
                        # the game's own permission check would refuse
                        # it
                        _emote_note(label)
                        return True
        except Exception:
            pass
        # v8.08: the game's own GetEmoteProto raises on dolls without
        # emote_item_id armed (v8.07 dump: HallDollShowModel). Fill the
        # missing attr with 0 (= no emote) and retry - the honest
        # answer for a doll with no emote, instead of a traceback.
        if mode == 'proto':
            try:
                return original(self, *args, **kwargs)
            except AttributeError as _ae:
                if 'emote_item_id' in str(_ae):
                    try:
                        self.emote_item_id = 0
                    except Exception:
                        pass
                    return original(self, *args, **kwargs)
                raise
        if mode == 'entry':
            # v8.15: EnterEmoteState with an emote whose model-info
            # row is missing (v8.14 device: Emote - Throne 9970000013,
            # two dead processes at cimp_emote.py:550) unpacks a None
            # the game itself produced. The pre-check above skips the
            # force for those; this catch keeps the process alive if
            # a guard misses (the UI caller ignores the return).
            try:
                return original(self, *args, **kwargs)
            except TypeError as _te:
                if 'cannot unpack' in str(_te):
                    _plog('[V815] %s unpack guarded: %r'
                          % (label, _te))
                    return None
                raise
        return original(self, *args, **kwargs)
    wrapper._treacky_emote = True
    wrapper._treacky_orig = original
    return wrapper


emote_info_cache = {}


def space_instance():
    """v8.16: the live Space instance for the _space heals."""
    try:
        _spc = sys.modules.get(
            'gclient.framework.entities.space')
        _Space = getattr(_spc, 'Space', None) if _spc else None
        if _Space is not None:
            inst = getattr(_Space, '_instance', None)
            if inst is not None:
                return inst
    except Exception:
        pass
    return None


def emote_info_ok(self, item):
    """v8.15: True when the game can build model info for this
    emote. The v8.14 device crashed twice on Emote - Throne
    (9970000013): EnterEmoteState unpacks the GetEmoteModelInfo
    result and the game table has no row for that emote - None -
    TypeError - dead process. The very next pick (Mythic Power
    6041000200) played clean, so it is per-emote data, not the
    flow. Probe once per (avatar class, emote id); no getter on the
    object = no evidence of trouble = allow."""
    try:
        item = _safe_int(item, 0)
        if not item:
            return True
        _key = (type(self).__name__, item)
        if _key in emote_info_cache:
            return emote_info_cache[_key]
        ok = True
        try:
            getter = getattr(self, 'GetEmoteModelInfo', None)
            if callable(getter):
                res = getter(item)
                if res is None:
                    ok = False
        except Exception:
            ok = False
        emote_info_cache[_key] = ok
        if not ok:
            _plog('[V815] emote %s has no model info - force skipped '
                  '(crash guard)' % (item,))
            # v8.16: EVA-01 on the v8.15 device - a VALID collab
            # emote whose model resources are simply not on the
            # device yet. Ask the game to download THAT item; the
            # next press after it lands has its model info.
            try:
                threading.Thread(
                    target=try_dlc_download,
                    args=(item, None), daemon=True).start()
            except Exception:
                pass
        return ok
    except Exception:
        return True


_emote_notes = set()
_emote_hook_sig = [None]


def _emote_note(what):
    if what in _emote_notes:
        return
    _emote_notes.add(what)
    _plog('[EMOTE] applied via %s' % (what,))
    # v8.06: an emote is now showing in the hall - keep the paint away
    # so it can play out (the paint would replace the emote model).
    # v8.10: the window opens in MATCHES too (15s - the longest emote
    # anim) - it gates the hero_skin_proto property force that puts
    # our skin on the TPS body (gameplay emotes + sprays). cached_-
    # property values read before the window opened stick in the
    # instance dict, so the cache is purged when it opens.
    try:
        _striker_emote_until[0] = max(_striker_emote_until[0],
                                      time.time() + 15.0)
        _striker_invalidate_skin_caches('emote-start')
    except Exception:
        pass


def _install_emote_hooks(verbose=False):
    installed = []
    missing = []
    for mod_name, cls_name, attr, mode in _EA_SPECS:
        label = '%s.%s' % (cls_name, attr)
        mod = _ea_import(mod_name)
        cls = getattr(mod, cls_name, None) if mod is not None else None
        if not isinstance(cls, type):
            missing.append(label)
            continue
        fn = cls.__dict__.get(attr)
        if fn is None:
            # inherited: wrap on this class anyway so the subclass gets it
            fn = getattr(cls, attr, None)
        if not callable(fn):
            missing.append(label)
            continue
        if getattr(fn, '_treacky_emote', False):
            installed.append(label)
            continue
        try:
            wrapped = _emote_wrap(mode, fn, label)
            setattr(cls, attr, wrapped)
            installed.append(label)
        except Exception as e:
            missing.append('%s(%r)' % (label, e))
    _EMOTE_HOOKED[:] = installed
    # v6.5: this used to print on every pass (the loop retries forever, one
    # spec is never present), which buried the log under an 'installed=15'
    # line every 5s. Print only when the picture actually changes.
    sig = (len(installed), tuple(missing))
    if verbose or sig != _emote_hook_sig[0]:
        _emote_hook_sig[0] = sig
        _plog("[EMOTE] hooks installed=%d %r missing=%r"
              % (len(installed), installed, missing))
    return installed


# ---- the actual fix: replay on selection change -----------------------------
def _emote_replay():
    """Make the picked emote play on the live models, in the game's own order.

    Device evidence (v6.1 run):
      [EMOTE] replay item=6041000161 ... targets=7  played=[] misses=7
      [EMOTE] replay item=9970000013 name='Emote - Throne' ... misses=14
    i.e. objects were found but none of them ever started anything, and the
    prop emotes (Throne, One Shot Victory) never played even once.
    Three things changed here:
      1. the game's own entry points run FIRST - EnterHallEmoteState /
         EnterEmoteState take an item id and do the whole job (attach models,
         camera, dlc, sound), which is exactly what the prop emotes need;
      2. the model path is tried with the node's real signature
         (ShowEmoteModel(proto, emote_loop=True)) and then the cue;
      3. what each class actually did is reported, so a miss is never silent.
    v6.3: the entry point is chosen by scene (combat avatars never get the hall
    call), re-entry is blocked, and live objects are recorded by the hooks
    instead of walking the heap (that walk blocked the game thread ~1 s).
    """
    if _emote_replay_busy[0]:
        return 0
    _emote_replay_busy[0] = True
    try:
        return _emote_replay_inner()
    finally:
        _emote_replay_busy[0] = False


_emote_traces = set()


def _emote_trace(cls_name, meth, exc):
    """Once per (class, method), the real traceback.

    repr() alone hid where the game's own code fell over in a match; the last
    two frames of the traceback name the internal call that received None.
    """
    key = (cls_name, meth)
    if key in _emote_traces:
        return
    _emote_traces.add(key)
    try:
        import traceback
        tb = traceback.format_exc(limit=4).strip().splitlines()
        tail = ' <- '.join(l.strip() for l in tb[-3:])
        _plog('[EMOTE] %s.%s failed: %r | %s' % (cls_name, meth, exc, tail[:400]))
    except Exception:
        pass


_emote_replay_busy = [False]


def _emote_replay_inner():
    proto = _get_forced_emote_proto()
    item_id = _get_forced_emote()
    name = _get_forced_emote_name()
    done = []
    misses = []
    errors = []
    targets = _emote_expand_targets(_emote_live_objects())
    # v6.6: only objects that belong to the scene we are in. The list still
    # holds the training avatar while you stand in the lobby, and calling a
    # match emote entry point from the hall is what "emotes only work in
    # training" looked like.
    try:
        scene_ok = [o for o in targets if _hero_scene_ok(o)]
        if scene_ok:
            targets = scene_ok
    except Exception:
        pass
    if proto is None or item_id is None:
        return 0
    for obj in targets:
        cls_name = type(obj).__name__
        played = None
        # v6.3: the entry point has to match the scene. Calling the HALL one on
        # an in-match combat avatar was the last thing the payload did before
        # the app died on device:
        #     [EMOTE] applied via PlayerCombatAvatar.EnterHallEmoteState
        #     <end of log>
        # Combat avatars get EnterEmoteState, hall objects get the hall one,
        # and neither is ever asked to do the other's job.
        mod = (type(obj).__module__ or '')
        hall_like = ('hall' in mod) or ('models.' in mod) or \
                    ('gamesystem' in mod and 'logic_base' not in mod)
        entries = (('EnterHallEmoteState',) if hall_like
                   else ('EnterEmoteState',))
        # ---- 1. the game's own emote entry points -------------------------
        for meth in entries:
            fn = getattr(obj, meth, None)
            if not callable(fn):
                continue
            # v6.4: the match avatar's signature is
            #   EnterEmoteState(item_id, follow_avatar='', is_hall_emote=False)
            # and its own body raises TypeError('cannot unpack non-iterable
            # NoneType object') when it is handed only an item id, so every
            # shape the device can want is tried here.
            for args, kwargs in (
                    ((item_id,), {}),
                    ((item_id, ''), {}),
                    ((item_id, ''), {'is_hall_emote': False}),
                    ((), {'item_id': item_id})):
                try:
                    fn(*args, **kwargs)
                    played = '%s.%s' % (cls_name, meth)
                    break
                except TypeError as e:
                    _emote_trace(cls_name, meth, e)
                    continue
                except Exception as e:
                    _emote_trace(cls_name, meth, e)
                    break
            if played:
                break
        # ---- 2. the model path -------------------------------------------
        if played is None:
            # v6.6: prop emotes (Throne 9970000013, One Shot Victory) attach a
            # separate model through a DLC record. The doll asks for that info
            # itself right before it shows the model, so ask for it here.
            _emote_call(obj, '_RefreshDlcInfoForPlayEmote', (item_id,))
            for _cargs, _ckw in (((False,), {'emote_item_id': item_id}),
                                 ((), {'emote_item_id': item_id}),
                                 ((item_id,), {}),
                                 ((), {})):
                if _emote_call(obj, 'CheckEmoteModelAttach', _cargs, _ckw):
                    break
            for meth in ('ClearEmoteInfo', 'CancelEmoteAnim', 'ClearEmoteModel'):
                _emote_call(obj, meth)
            show = getattr(obj, 'ShowEmoteModel', None)
            if callable(show):
                for args, kwargs in (((proto,), {'emote_loop': True}),
                                     ((proto,), {}),
                                     ((proto, True), {})):
                    try:
                        show(*args, **kwargs)
                        played = '%s.ShowEmoteModel' % cls_name
                        break
                    except TypeError:
                        continue
                    except Exception as e:
                        errors.append('%s.ShowEmoteModel:%r' % (cls_name, e))
                        break
            if played is None:
                anim = getattr(obj, 'PlayEmoteAnim', None)
                if callable(anim):
                    try:
                        anim(interrupt=True)
                        played = '%s.PlayEmoteAnim' % cls_name
                    except TypeError:
                        try:
                            anim()
                            played = '%s.PlayEmoteAnim' % cls_name
                        except Exception as e:
                            errors.append('%s.PlayEmoteAnim:%r' % (cls_name, e))
                    except Exception as e:
                        errors.append('%s.PlayEmoteAnim:%r' % (cls_name, e))
        if played:
            done.append(played)
        else:
            misses.append(cls_name)
    _emote_replay_stats['targets'] = len(targets)
    _emote_replay_stats['done'] = sorted(set(done))[:8]
    _emote_replay_stats['misses'] = len(misses)
    if misses and not _debug_dump_seen[0]:
        _debug_dump_seen[0] = _safe_int(sync_attrs.get('iDebugDump', 0), 0) or 1
        try:
            _debug_dump_emote('auto: emote refused to play')
        except Exception:
            pass
    if misses and not done:
        try:
            _emote_explore(targets, item_id, proto, errors)
        except Exception:
            pass
    _emote_replay_stats['errors'] = errors[:4]
    _plog('[EMOTE] replay item=%d name=%r targets=%d played=%r misses=%d '
          'miss_types=%r errors=%r'
          % (item_id, name, len(targets), _emote_replay_stats['done'],
             len(misses), sorted(set(misses))[:6], errors[:4]))
    return len(_emote_replay_stats['done'])


# ============================================================
# v6.5: EMOTE API INVENTORY + EXPLORATION
# ============================================================
# Why this exists: in the 6.4 log the replay found ONE live object
# (PlayerAvatar), reported played=[] misses=1 and no error - i.e. it never
# found an object that owns an emote API. Guessing more method names is not
# engineering; listing what the client actually exposes is.
_EMOTE_MODEL_ATTRS = ('model', '_model', 'GetModel', 'GetModelUnit', 'model_unit',
                      'actor', 'GetActor', 'owner', 'doll', 'GetDoll',
                      'show_model', 'GetShowModel', 'GetModelComponent')
_emote_api_tried = set()


def _emote_api_inventory(objs=None, limit=10):
    """Every emote-related member of every live class, with its real signature."""
    out = []
    objs = objs if objs is not None else _emote_live_objects()
    seen = set()
    for obj in objs[:limit]:
        cn = type(obj).__name__
        if cn in seen:
            continue
        seen.add(cn)
        names = [n for n in dir(obj) if 'emote' in n.lower()]
        out.append('-- %s (%s) emote members=%d' % (cn, type(obj).__module__, len(names)))
        for n in sorted(names):
            fn = getattr(obj, n, None)
            sig = ''
            if callable(fn):
                try:
                    sig = str(inspect.signature(fn))
                except Exception as e:
                    sig = '<sig %r>' % (e,)
            out.append('   %-30s %s' % (n, sig))
        extra = []
        for a in _EMOTE_MODEL_ATTRS:
            v = getattr(obj, a, None)
            if v is not None and v is not obj and not isinstance(v, (int, str, float, bool)):
                extra.append('%s->%s' % (a, type(v).__name__))
        if extra:
            out.append('   model refs: %s' % (', '.join(extra),))
    return out


def _emote_expand_targets(targets):
    """Follow avatars to the model objects that own the emote API."""
    out = list(targets)
    have = set(id(o) for o in out)
    for obj in list(targets):
        for a in _EMOTE_MODEL_ATTRS:
            try:
                v = getattr(obj, a, None)
            except Exception:
                continue
            if v is None or v is obj or isinstance(v, (int, str, float, bool, bytes, dict, list, tuple)):
                continue
            try:
                if id(v) in have:
                    continue
                if any(callable(getattr(v, m, None)) for m in
                       ('ShowEmoteModel', 'PlayEmoteAnim', 'EnterEmoteState',
                        'EnterHallEmoteState')):
                    out.append(v)
                    have.add(id(v))
            except Exception:
                continue
    return out


def _emote_explore(targets, item_id, proto, errors):
    """Try every live emote entry point ONCE, and report the return value.

    Runs only from the debug dump / a replay that already missed, i.e. from the
    game thread via _game_run, never from our own tick.
    """
    out = []
    pat = re.compile(r'(?i)(enter|play|show|use|do|start|trigger|apply|request)'
                     r'[a-z_]*(emote|action|expression)')
    for obj in targets[:10]:
        cn = type(obj).__name__
        for n in dir(obj):
            if not pat.search(n):
                continue
            fn = getattr(obj, n, None)
            if not callable(fn):
                continue
            key = (cn, n)
            if key in _emote_api_tried:
                continue
            _emote_api_tried.add(key)
            shapes = [((item_id,), {}), ((item_id, ''), {}), ((), {}),
                      ((proto,), {}), ((proto,), {'emote_loop': True})]
            for args, kwargs in shapes:
                try:
                    ret = fn(*args, **kwargs)
                    if ret is False or ret is None:
                        out.append('%s.%s%r%s -> %r' % (cn, n, args, kwargs, ret))
                    else:
                        out.append('%s.%s%r%s -> %r' % (cn, n, args, kwargs, ret))
                    break
                except TypeError as e:
                    continue
                except Exception as e:
                    out.append('%s.%s%r RAISED %r' % (cn, n, args, e))
                    errors.append('%s.%s:%r' % (cn, n, e))
                    break
    if out:
        _plog('[EMOTE] explore %s' % (' | '.join(out)[:900],))
        _dlog('[EMOTE] explore\n  ' + '\n  '.join(out))
    return out


def _emote_probe():
    """Once: which classes the game exposes and what they can do."""
    out = []
    for cls in _emote_classes() or []:
        have = [m for m in _EMOTE_TARGET_METHODS if callable(getattr(cls, m, None))]
        out.append('%s:%s' % (cls.__name__, ','.join(have) or 'none'))
    live = {}
    for obj in _emote_live_objects():
        live[type(obj).__name__] = live.get(type(obj).__name__, 0) + 1
    _plog('[EMOTE] probe %s | live=%r' % (' | '.join(out[:10]), live))


def _loop_gen(key):
    """Start/replace a long-running loop, even across a re-exec.

    The old guard was `if not _ALREADY_LOADED`, so a hot reload skipped every
    loop this payload owns - including the emote feed and the apply loop -
    while the striker block's own thread kept running. That is why the Emotes
    tab sat on "scanning..." after a reload and equipping did nothing.
    """
    reg = getattr(sys, '_treacky_loops', None)
    if reg is None:
        reg = {}
        sys._treacky_loops = reg
    gen = reg.get(key, 0) + 1
    reg[key] = gen
    return gen


def _loop_alive(key, gen):
    return getattr(sys, '_treacky_loops', {}).get(key) == gen


def _ea_loop(gen=0):
    """Rebuild the catalog, resend it, and keep trying the hooks."""
    installed = []
    tries = 0
    reported = -1
    while _loop_alive('emotes', gen):
        try:
            # v8.11: the racer shield retries here until it sticks
            # (sys.modules-only, no import - the game loads the
            # weapon-case modules long after payload boot).
            try:
                install_racer_shield()
            except Exception:
                pass
            if not EMOTE:
                _ea_build_catalog()
            # v7.23: the emote item ids, once - the user asked for them
            # ("still have 2 free emotes find them IDs").
            if EMOTE_INFO and not globals().get('_emote_ids_logged', [False])[0]:
                try:
                    _eids = list(EMOTE_INFO.items())[:30]
                    _plog('[EMOTE-IDS] catalog=%d sample=%r'
                          % (len(EMOTE_INFO), _eids))
                except Exception:
                    pass
                globals().setdefault('_emote_ids_logged', [False])[0] = True
            if EMOTE:
                if len(installed) < len(_EA_SPECS) and tries < 20:
                    tries += 1
                    installed = _install_emote_hooks(verbose=(tries == 1))
                    # v8.10: the property/camera/anim hooks rescan with
                    # the emote hooks (late-loading classes).
                    try:
                        _install_v810_hooks()
                    except Exception:
                        pass
                _ea_send()
                sent = _emote_stats['sent']
                # v7.20: this fired every 5 s (232 lines in one session).
                # First sends, errors, then once every 60th send.
                if sent and sent != reported and (sent <= 3 or sent % 60 == 0
                                                  or _emote_stats['errors']):
                    reported = sent
                    _plog("[EMOTE] feed sent=%d bytes=%d errors=%d"
                          % (sent, _emote_stats['bytes'], _emote_stats['errors']))
        except Exception as e:
            _plog("[EMOTE] loop error=%r" % (e,))
        time.sleep(5.0)


# ============================================================
# v6.5: ADVANCED DEBUGGER  (emotes + striker)
# ============================================================
# A separate file, so skin_diag.txt stays readable:
#     /storage/emulated/0/Nexora/nexora_debug.txt
# Written when you press "Dump debug" in the Striker or Emotes tab, and once
# automatically the first time an emote refuses to play. It records the exact
# data the game has, the calls that were attempted, their RETURN VALUES and
# their tracebacks - the three things missing from every log so far.
DEBUG_PATH = DIAG_PATH   # v7.1: same file as the live log


def _dlog(text):
    try:
        os.makedirs("/storage/emulated/0/Nexora", exist_ok=True)
        with open(DEBUG_PATH, "a") as f:
            f.write(str(text) + "\n")
    except Exception:
        pass


def _debug_call(obj, meth, *args, **kwargs):
    """Call a method and describe exactly what came back."""
    fn = getattr(obj, meth, None)
    if not callable(fn):
        return 'MISSING'
    try:
        ret = fn(*args, **kwargs)
        return 'ok -> %r' % (ret,)
    except Exception as e:
        try:
            import traceback
            tb = traceback.format_exc(limit=6).strip().splitlines()
            return 'RAISED %r | %s' % (e, ' <- '.join(l.strip() for l in tb[-4:])[:500])
        except Exception:
            return 'RAISED %r' % (e,)


def _debug_short(value, limit=240):
    try:
        t = type(value).__name__
        r = repr(value)
        if len(r) > limit:
            r = r[:limit] + '...'
        return '%s %s' % (t, r)
    except Exception:
        return '<unrepresentable>'


def _debug_dump_emote(tag='manual'):
    """Everything the client knows about the selected emote."""
    out = []
    item = _get_forced_emote()
    name = _get_forced_emote_name()
    out.append('')
    out.append('=== EMOTE DUMP (%s) utc=%s ===' % (tag, _utc_stamp()))
    # v7.30R20: the R19 device log showed gate=False / item=None with no
    # way to tell "checkbox off" from "no emote picked" apart. Say both.
    out.append('selected item=%r name=%r gate=%r in_match=%r '
               '[bEmoteHack=%r iEmoteSel=%r catalog=%d]'
               % (item, name, _ea_gate(), _hero_in_match(),
                  sync_attrs.get('bEmoteHack', False),
                  sync_attrs.get('iEmoteSel', 0), len(_emote_ids())))
    proto = _get_forced_emote_proto()
    out.append('proto %s' % (_debug_short(proto, 400),))
    if proto is not None:
        for k in _hero_proto_keys(proto, 40):
            out.append('   %-24s = %s' % (k, _debug_short(_hero_proto_get(proto, k), 120)))
    # the data tables the game itself resolves emotes through
    for mod_name in ('gclient.data.hero_emote_data',
                     'gclient.data.hero_display_action_data',
                     'gclient.data.hero_execution_data',
                     'gclient.data.lobby_item_data'):
        mod = sys.modules.get(mod_name)
        if mod is None:
            try:
                mod = __import__(mod_name, globals(), locals(), ['x'], 0)
            except Exception as e:
                out.append('%-45s import failed %r' % (mod_name, e))
                continue
        data = getattr(mod, 'data', None)
        try:
            hit = data.get(item) if hasattr(data, 'get') else None
        except Exception:
            hit = None
        out.append('%-45s size=%s item_present=%s %s'
                   % (mod_name, len(data) if hasattr(data, '__len__') else '?',
                      bool(hit), _debug_short(hit, 300) if hit else ''))
    # what the live objects say, and what happens when each is asked
    live = _emote_live_objects()
    out.append('live objects=%d' % (len(live),))
    for obj in live[:8]:
        cn = type(obj).__name__
        out.append('-- %s mod=%s' % (cn, type(obj).__module__))
        for meth in ('GetEmoteProto', 'GetEmoteId', 'GetEmoteWheelUI',
                     'IsInEmoteState', 'GetEmoteModelInfo'):
            if callable(getattr(obj, meth, None)):
                if meth == 'GetEmoteModelInfo':
                    out.append('   %-18s %s' % (meth, _debug_call(obj, meth, item, '')))
                else:
                    out.append('   %-18s %s' % (meth, _debug_call(obj, meth)))
        for meth in ('EnterHallEmoteState', 'EnterEmoteState'):
            if callable(getattr(obj, meth, None)):
                out.append('   %-18s %s' % (meth, 'present (not called by the dump)'))
        out.append('   %-18s %s' % ('ShowEmoteModel',
                                    'present' if callable(getattr(obj, 'ShowEmoteModel', None))
                                    else 'missing'))
    out.append('-- emote API inventory (real signatures) --')
    out.extend(_emote_api_inventory(live + list(_emote_expand_targets(live))))
    out.append('replay stats %r' % (_emote_replay_stats,))
    out.append('hook stats %r' % ({k: v for k, v in _emote_stats.items()},))
    _dlog('\n'.join(out))
    _plog('[DEBUG] emote dump written (%s)' % (tag,))
    return DEBUG_PATH


def _debug_dump_weapon(tag='manual'):
    """Every live WeaponCase we know about: is the forced skin still on it?"""
    out = []
    out.append('')
    out.append('=== WEAPON SKIN DUMP (%s) utc=%s ===' % (tag, _utc_stamp()))
    out.append('gate bSkinHack=%r enforce=%r'
               % (sync_attrs.get('bSkinHack'), _weaponfx_enforce_stat))
    out.append('live cases remembered=%d' % (len(_weaponfx_cases),))
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
            continue
        wid = stored_wid or _weapon_case_wid(case)
        forced = _weaponfx_forced_for(wid)
        have = getattr(case, '_treacky_skin_template_id', None)
        out.append('  %-28s wid=%-5d forced=%-12r on_case=%-12r %s'
                   % (type(case).__name__, wid, forced, have,
                      'OK' if (forced and have == forced) else 'NEEDS RE-APPLY'))
        for k in ('skin_id', 'guise_id', 'skin_item_id', 'guise_item_id',
                  'skin_template_id', '_selected_skin_id'):
            try:
                v = getattr(case, k, None)
            except Exception:
                v = None
            if v is not None:
                out.append('      %-22s %r' % (k, v))
    _dlog('\n'.join(out))
    _plog('[DEBUG] weapon dump written (%d cases)' % (len(_weaponfx_cases),))
    return out


_debug_inventory_done = set()


def _debug_dump_striker(tag='manual'):
    out = []
    out.append('')
    out.append('=== STRIKER DUMP (%s) utc=%s ===' % (tag, _utc_stamp()))
    picks = {k: v for k, v in sync_attrs.items()
             if str(k).startswith('iHeroSkin_') and _safe_int(v, 0) > 0}
    out.append('gate bHeroSkinHack=%r bStrikerHack=%r in_match=%r picks=%r'
               % (sync_attrs.get('bHeroSkinHack'), sync_attrs.get('bStrikerHack'),
                  _hero_in_match(), picks))
    out.append('hook counters %r' % (_hero_stats2,))
    out.append('forced per picked hero:')
    for hid in list(picks.keys()):
        try:
            h = int(str(hid).split('_')[-1])
        except Exception:
            continue
        proto = _get_forced_skin_proto(h)
        out.append('   hero=%d idx=%r skin=%r proto=%s model_id=%r'
                   % (h, picks.get(hid), _get_forced_skin(h),
                      _debug_short(proto, 200) if proto else None,
                      _get_forced_model_id(h)))
    live = _hero_live_objects()
    out.append('live objects=%d' % (len(live),))
    for obj in live[:8]:
        cn = type(obj).__name__
        out.append('-- %s mod=%s' % (cn, type(obj).__module__))
        out.append('   GetHeroId            %s'
                   % (_debug_call(obj, 'GetHeroId')
                      if callable(getattr(obj, 'GetHeroId', None)) else 'MISSING'))
        out.append('   deep hero id         %r' % (_hero_id_deep(obj),))
        desc = None
        for base in getattr(type(obj), '__mro__', ()):
            if 'hero_skin_proto' in base.__dict__:
                desc = '%s.%s' % (base.__name__, type(base.__dict__['hero_skin_proto']).__name__)
                break
        out.append('   hero_skin_proto      %s (owner %s)' % (desc, 'yes' if desc else 'no'))
        try:
            out.append('   proto read           %s'
                       % (_debug_short(obj.hero_skin_proto, 200),))
        except Exception as e:
            out.append('   proto read           RAISED %r' % (e,))
        out.append('   GetModelUnitID       %s'
                   % (_debug_call(obj, 'GetModelUnitID')
                      if callable(getattr(obj, 'GetModelUnitID', None)) else 'MISSING'))
        for meth in ('GetCurArmHeroSkinProto', 'GetActualArmHeroSkinProto',
                     'GetHeroSkinProto'):
            if callable(getattr(obj, meth, None)):
                out.append('   %-20s %s' % (meth, _debug_call(obj, meth)))
        # v7.0: what this avatar actually exposes around its appearance. The
        # match has no hero_skin_proto and no doll, so this list is the only way
        # to find the call that rebuilds it.
        dcname = type(obj).__name__
        if _hero_kind(obj) == 'match' and dcname not in _debug_inventory_done:
            _debug_inventory_done.add(dcname)
            names = [n for n in dir(obj) if not n.startswith('__') and
                     re.search(r'(?i)skin|striker|hero|model|cloth|arm|dress|'
                               r'appearance|guise|unit|rebuild|refresh|reset',
                               n)]
            out.append('   members=%d appearance-related=%d'
                       % (len([n for n in dir(obj) if not n.startswith('__')]),
                          len(names)))
            for n in names[:400]:
                v = getattr(obj, n, None)
                if callable(v):
                    try:
                        out.append('      %-34s %s' % (n, inspect.signature(v)))
                    except Exception:
                        out.append('      %-34s (sig ?)' % (n,))
                elif not isinstance(v, (dict, list, tuple)) or len(str(v)) < 120:
                    out.append('      %-34s = %s' % (n, _debug_short(v, 90)))
        elif _hero_kind(obj) == 'match':
            out.append('   (appearance inventory already printed for this class)')
        owner = getattr(obj, 'owner', None)
        if owner is not None and owner is not obj:
            out.append('   owner                %s deep=%r'
                       % (type(owner).__name__, _hero_id_deep(owner)))
    _dlog('\n'.join(out))
    _plog('[DEBUG] striker dump written (%s)' % (tag,))
    return DEBUG_PATH


_debug_dump_seen = [0]


# ============================================================
# v7.1: AUTO DEBUG - nobody should have to press a button
# ============================================================
# The dumps are written by themselves now: on every scene change (after the
# new scene has settled), every 60 s in a match and every 120 s in the hall,
# and immediately whenever a striker push in a match does not land. Everything
# goes into the single log file, so the sequence reads top to bottom. The menu
# buttons still work if you want a dump right now.
_AUTO = {'last_scene': None, 'scene_at': 0.0, 'next_at': 0.0,
         'count': 0, 'last_tag': ''}
dump_busy = [False]


def runtime_dump(tag='auto'):
    """v8.16: the live runtime dumper is BACK and now covers
    EVERYTHING, separated into one txt per category in
    <debugdir>/runtime/: modules, classes + methods, module
    functions, live-object type census, every distinct string
    found on the heap, and the id catalogs. Background thread
    only (never the game thread); GIL-releasing sleeps between
    batches so the game keeps breathing while it runs."""
    if dump_busy[0]:
        return
    dump_busy[0] = True
    try:
        import gc as _gc
        import os as _os
        base = _os.path.dirname(DEBUG_PATH) \
            if isinstance(DEBUG_PATH, str) else '.'
        outdir = _os.path.join(base, 'runtime')
        try:
            _os.makedirs(outdir, exist_ok=True)
        except Exception:
            outdir = base
        stamp = _utc_stamp()

        def _wf(name, lines):
            try:
                path = _os.path.join(outdir, name)
                with open(path, 'w', encoding='utf-8',
                          errors='replace') as _f:
                    _f.write('# %s  utc=%s\n' % (tag, stamp))
                    for _i, _ln in enumerate(lines):
                        _f.write(_ln)
                        _f.write('\n')
                        if (_i % 400) == 399:
                            time.sleep(0.01)
                return path
            except Exception:
                return None

        mods = sorted(
            m for m in sys.modules.keys() if isinstance(m, str))
        _wf('modules.txt', mods)

        cls_lines = []
        fn_lines = []
        for _mi, _mn in enumerate(mods):
            try:
                _m = sys.modules.get(_mn)
                if _m is None:
                    continue
                _fns = []
                for _n in vars(_m):
                    _o = getattr(_m, _n, None)
                    if isinstance(_o, type):
                        _meths = sorted(
                            k for k in _o.__dict__
                            if isinstance(k, str))
                        cls_lines.append('CLASS %s.%s methods=%r'
                                         % (_mn, _n, _meths))
                    elif callable(_o) and not isinstance(
                            _o, type) and getattr(
                            _o, '__module__', None) == _mn:
                        _fns.append(_n)
                if _fns:
                    fn_lines.append('FUNCS %s %r'
                                    % (_mn, sorted(_fns)))
            except Exception:
                continue
            if (_mi % 50) == 49:
                time.sleep(0.01)
        _wf('classes.txt', cls_lines)
        _wf('functions.txt', fn_lines)

        type_counts = {}
        str_set = set()

        def _harvest16(_ob):
            try:
                _tn = type(_ob).__name__
                type_counts[_tn] = type_counts.get(_tn, 0) + 1
                if _tn == 'str':
                    if 3 <= len(_ob) <= 96:
                        str_set.add(_ob)
                    return
                if len(str_set) >= 200000:
                    return
                if _tn == 'dict':
                    for _v in _ob.values():
                        if (type(_v).__name__ == 'str'
                                and 3 <= len(_v) <= 96):
                            str_set.add(_v)
                elif _tn in ('list', 'tuple', 'set', 'frozenset'):
                    for _v in list(_ob)[:64]:
                        if (type(_v).__name__ == 'str'
                                and 3 <= len(_v) <= 96):
                            str_set.add(_v)
            except Exception:
                pass

        try:
            for _oi, _ob in enumerate(_gc.get_objects()):
                _harvest16(_ob)
                if (_oi % 2000) == 1999:
                    time.sleep(0.01)
        except Exception:
            pass
        _wf('live_types.txt', (
            '%s=%d' % (_t, _c)
            for _t, _c in sorted(type_counts.items(),
                                 key=lambda kv: -kv[1])))
        _wf('strings.txt', sorted(str_set))

        id_lines = []
        try:
            for _eq, _ent in sorted(
                    (globals().get('WEP') or {}).items()):
                id_lines.append(
                    'WEAPON %s %s skins=%d'
                    % (_eq, _ent[0] if _ent else '?',
                       len(_ent) - 1 if _ent else 0))
            for _sid, _inf in sorted(
                    (globals().get('WEP_SKIN_INFO') or {}).items(),
                    key=lambda kv: _safe_int(kv[0], 0)):
                id_lines.append('SKIN %s %r'
                                % (_sid,
                                   _proto_get(_inf, 'name', None)))
            for _hid, _hent in sorted(
                    (globals().get('HERO') or {}).items()):
                id_lines.append('HERO %s %r' % (_hid, _hent))
            for _eid, _enm in sorted(
                    (globals().get('EMOTE_INFO') or {}).items()):
                id_lines.append('EMOTE %s %r' % (_eid, _enm))
        except Exception:
            pass
        _wf('ids.txt', id_lines)
        _plog('[V816] runtime dump written (%s) mods=%d classes=%d '
              'strings=%d types=%d'
              % (tag, len(mods), len(cls_lines), len(str_set),
                 len(type_counts)))
    except Exception:
        try:
            _plog('[V816] runtime dump failed: %s' % (_exc_text(),))
        except Exception:
            pass
    finally:
        dump_busy[0] = False


def _auto_debug_reason(scene):
    now = time.time()
    reason = None
    if scene != _AUTO['last_scene']:
        _AUTO['last_scene'] = scene
        _AUTO['scene_at'] = now
        # give the game time to build the new scene's models before asking
        # anything of it (v7.2: 12 s - the lobby is still rebuilding at 6 s)
        _AUTO['next_at'] = now + 12.0
        reason = 'scene=%s' % (scene,)
        return None if reason else None
    if _AUTO['next_at'] and now >= _AUTO['next_at']:
        # v7.22: periodic dumps are HALL ONLY. The v7.21 device log shows a
        # full emote+striker+weapon+unlock dump every ~90 s MID-MATCH -
        # each one is 0.5-1.3 s of frozen combat ("it cause freeze when
        # playing other modes"). In a match the dump runs only from the
        # menu button or a genuine failure.
        if scene == 'match':
            _AUTO['next_at'] = now + 3600.0
            _plog('[AUTO] periodic dump skipped in match (next in 1 h)')
            return None
        _AUTO['next_at'] = now + 180.0
        return 'periodic scene=%s' % (scene,)
    return None


def _auto_debug_tick():
    """Called from the game thread every tick. Cheap when idle."""
    if not _V841PERF_AUTO_DIAGNOSTICS or not _debug_log_on():
        return False
    scene = _hero_scene_stable()
    reason = _auto_debug_reason(scene)
    if reason is None:
        return False
    _AUTO['count'] += 1
    _AUTO['last_tag'] = reason
    _plog('[AUTO] dump #%d (%s) utc=%s' % (_AUTO['count'], reason, _utc_stamp()))
    _debug_dump_all('auto: %s' % (reason,))
    try:
        threading.Thread(target=runtime_dump,
                         args=('auto: %s' % (reason,),),
                         daemon=True).start()
    except Exception:
        pass
    return True


def _auto_avatar_watch():
    """v7.3: keep the match Space's avatar entities in the live list.

    Runs every tick; the scan itself is throttled to 5 s and only walks the
    entities dict. When a NEW avatar entity appears (spawn, scene change) a
    striker reapply is queued, which arms it on the game thread.
    """
    # v7.30R17: the striker-reapply queue is gone with the v7.30
    # block; the ORIGINAL BSB hooks arm new avatars as they spawn.


def _auto_debug_force(reason):
    if not _V841PERF_AUTO_DIAGNOSTICS or not _debug_log_on():
        return
    # v7.2: the first seconds of a new scene are exactly when a 0.5 s write
    # stall can take the client down (the v7.1 crash was within ~6 s of
    # entering the lobby). During that window the dump is postponed, not
    # dropped - the periodic tick picks it up once the scene has settled.
    try:
        if _AUTO.get('scene_at') and time.time() - _AUTO['scene_at'] < 12.0:
            _AUTO['next_at'] = _AUTO['scene_at'] + 13.0
            _plog('[AUTO] dump postponed during scene change (%s)' % (reason,))
            return
    except Exception:
        pass
    _AUTO['count'] += 1
    _plog('[AUTO] dump #%d (%s) utc=%s' % (_AUTO['count'], reason, _utc_stamp()))
    _debug_dump_all('auto: %s' % (reason,))


_ids_scan = {'on': False, 'thread': None, 'cat_text': '', 'cat_sig': None,
             'cat_counts': None, 'last_sig': None, 'last_names': 0,
             'saves': 0, 'passes': 0}


def _process_ids_dump_requests():
    """Menu 'Live ID scan' checkbox -> bIdsScan -> live BS_IDs.py.

    v7.30R5: the one-shot button became a checkbox. While it is checked
    a worker thread rescans the runtime every 3 s. sys.modules grows as
    you move around the game (lobby -> training ground -> match...), and
    every new module / class / method / function / live object type
    lands in BS_IDs.py on the next pass. Progress goes to the log as
    [IDS] live: names=... lines. Uncheck to stop - the file keeps the
    last save.
    """
    on = bool(sync_attrs.get('bIdsScan', False))
    if on == _ids_scan['on']:
        return False
    _ids_scan['on'] = on
    if on:
        _plog('[IDS] live scan ON - full dump first, then rescan every 3 s')
        t = _ids_scan.get('thread')
        if t is None or not t.is_alive():
            t = threading.Thread(target=_ids_live_scan_loop, daemon=True)
            _ids_scan['thread'] = t
            t.start()
    else:
        _plog('[IDS] live scan OFF - BS_IDs.py keeps the last save '
              '(names=%d, saves=%d)'
              % (_ids_scan.get('last_names', 0), _ids_scan['saves']))
    return True


def _ids_live_scan_loop():
    """One long-lived worker: scans while the checkbox is on, idles at
    1 Hz when off. Never exits, so a fast off/on flip cannot kill it and
    the 65k-row walk never touches the game thread."""
    while True:
        try:
            if _ids_scan['on']:
                # v7.30R11: never scan DURING a match / training ground.
                # Each pass holds the GIL for ~4 s and the device log
                # shows the game thread stalling behind it mid-fight
                # (standing rule: diagnostics never in matches). The
                # scan resumes in the lobby - modules stay loaded, so
                # nothing is lost.
                try:
                    if _hero_in_match():
                        time.sleep(3.0)
                        continue
                except Exception:
                    pass
                _ids_scan_pass()
                time.sleep(3.0)
            else:
                time.sleep(1.0)
        except Exception as e:
            _plog('[IDS] scan pass failed: %r' % (e,))
            try:
                time.sleep(3.0)
            except Exception:
                return


def _ids_catalog_text():
    """The static catalogs: weapons, weapon skins, strikers, striker
    skins, emotes, gun-skin items and the full vault table."""
    import io
    out = io.StringIO()
    w = out.write
    counts = {}
    nw = 0
    w('\nWEAPONS = {  # equip_id: {"name": str, "skins": [skin_id, ...]}\n')
    for equip_id, entries in sorted(WEP.items()):
        nm = _display_text(entries[0], str(equip_id))
        w('    %d: {"name": %r, "skins": %r},\n'
          % (equip_id, nm, [int(x) for x in entries[1:]]))
        nw += 1
    w('}\n')
    counts['weapons'] = nw
    nws = 0
    w('\nWEAPON_SKINS = {  # skin_id: {"name": str, "level": int}\n')
    for skin_id in sorted(WEP_SKIN_INFO):
        _info = WEP_SKIN_INFO.get(skin_id) or {}
        nm = _display_text(_info.get('name') or str(skin_id), str(skin_id))
        w('    %d: {"name": %r, "level": %d},\n'
          % (skin_id, nm, _safe_int(_info.get('skin_level'), 0)))
        nws += 1
    w('}\n')
    counts['weapon_skins'] = nws
    nh = 0
    w('\nSTRIKERS = {  # hero_id: {"name": str, "skins": [skin_id, ...]}\n')
    for hero_id in sorted(HERO):
        entries = HERO[hero_id]
        w('    %d: {"name": %r, "skins": %r},\n'
          % (hero_id, str(entries[0]), [int(x) for x in entries[1:]]))
        nh += 1
    w('}\n')
    counts['strikers'] = nh
    nhs = 0
    w('\nSTRIKER_SKINS = {  # skin_id: {"name": str, "hero": int}\n')
    for skin_id in sorted(HERO_SKIN_INFO):
        proto = HERO_SKIN_INFO.get(skin_id) or {}
        nm = _proto_english_name(
            proto, ('en_name', 'english_name', 'name_en', 'name'),
            str(skin_id))
        w('    %d: {"name": %r, "hero": %r},\n'
          % (skin_id, nm, proto.get('hero_id')))
        nhs += 1
    w('}\n')
    counts['striker_skins'] = nhs
    ne = 0
    w('\nEMOTES = {  # emote_id: name\n')
    for item_id in sorted(EMOTE_INFO):
        nm = str(EMOTE_INFO.get(item_id, '')).replace('\n', ' ').strip()
        w('    %d: %r,\n' % (item_id, nm))
        ne += 1
    w('}\n')
    counts['emotes'] = ne
    ng = 0
    w('\nGUN_SKIN_ITEMS = {  # item_id: {"name": str, "guise": int}\n')
    try:
        gs_mod = _import_module('gclient.data.lobby_gun_skin_item_data')
        gs_data = getattr(gs_mod, 'data', None) or {}
        for item_id in sorted(gs_data):
            _ids_gil_yield()
            proto = gs_data.get(item_id) or {}
            nm = _proto_english_name(
                proto, ('en_name', 'english_name', 'name_en', 'name'),
                str(item_id))
            w('    %d: {"name": %r, "guise": %r},\n'
              % (item_id, nm, proto.get('guise_id', proto.get('id'))))
            ng += 1
    except Exception as e:
        w('    # unavailable: %r\n' % (e,))
    w('}\n')
    counts['gun_items'] = ng
    nv = 0
    w('\nVAULT_ITEMS = {  # item_id: {"name": str, "model_id": int}\n')
    try:
        lid_mod = _import_module('gclient.data.lobby_item_data')
        lid_data = getattr(lid_mod, 'data', None) or {}
        for item_id in sorted(lid_data):
            _ids_gil_yield()
            proto = lid_data.get(item_id) or {}
            nm = _proto_english_name(
                proto, ('en_name', 'english_name', 'name_en', 'name'),
                str(item_id))
            w('    %d: {"name": %r, "model_id": %r},\n'
              % (item_id, nm, proto.get('model_id')))
            nv += 1
    except Exception as e:
        w('    # unavailable: %r\n' % (e,))
    w('}\n')
    counts['vault_items'] = nv
    # v8.20: THE FULL EQUIP ROSTER - the v8.20 report asked for all
    # real guns; the weapon/skin catalogs only see equips that carry
    # skins, so skinless guns are invisible to them. This dumps EVERY
    # equip row with its own type fields, so future menu categories
    # come from device evidence instead of guesses.
    nr = 0
    w('\nEQUIP_ROSTER = {  # equip_id: {"name", "equip_type", "gun_id",'
      ' "melee_weapon_id", "equip_case", "icon_id", "model_id"}\n')
    try:
        ed = _import_module('gclient.data.equip_data')
        ed_data = getattr(ed, 'data', None) or {}
        for equip_id in sorted(ed_data):
            _ids_gil_yield()
            row = ed_data.get(equip_id) or {}
            nm = _proto_english_name(
                row, ('en_name', 'english_name', 'name_en', 'name'),
                str(equip_id))
            w('    %d: {"name": %r, "equip_type": %r, "gun_id": %r, '
              '"melee_weapon_id": %r, "equip_case": %r, "icon_id": %r, '
              '"model_id": %r},\n'
              % (equip_id, nm,
                 _proto_get(row, 'equip_type', None),
                 _proto_get(row, 'gun_id', None),
                 _proto_get(row, 'melee_weapon_id', None),
                 _display_text(_proto_get(row, 'equip_case', ''), ''),
                 _proto_get(row, 'icon_id', None),
                 _proto_get(row, 'model_id', None)))
            nr += 1
    except Exception as e:
        w('    # unavailable: %r\n' % (e,))
    w('}\n')
    counts['equip_roster'] = nr
    return out.getvalue(), counts


_ids_sock = [None]


def _ids_send_status(names, mods, classes, methods, funcs, live, saves, kb):
    """v7.30R6: push the scan counters to the menu (UDP 50006) so the
    status line under the checkbox updates in real time - no more
    exiting the game to read the log."""
    try:
        if _ids_sock[0] is None:
            _ids_sock[0] = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        msg = 'I|%d|%d|%d|%d|%d|%d|%d|%d\n' % (names, mods, classes,
                                               methods, funcs, live,
                                               saves, kb)
        _ids_sock[0].sendto(msg.encode('utf-8'),
                            ('127.0.0.1', UDP_IDS_PORT))
    except Exception:
        pass


_ids_yield_at = [0.0]


def _ids_gil_yield():
    """v7.30R12: hand the GIL back for a moment inside long scan passes.

    The first full pass held it for 52.6 s straight on device ([STALL]
    game thread blocked 52.62s) - the game and the ESP thread could not
    run a single tick behind it. That is the "lag" and the twitching
    ESP. Capping each hold at ~50 ms makes the pass invisible in-game;
    it only takes a few seconds longer overall."""
    try:
        now = time.time()
        if now - _ids_yield_at[0] >= 0.05:
            _ids_yield_at[0] = now
            time.sleep(0.002)
    except Exception:
        pass


def _ids_scan_pass():
    """One scan pass: catalogs (only if a table moved) + the runtime
    walk (modules, classes, methods, functions, live object census).
    Saves BS_IDs.py only when something new showed up; the status goes
    to the menu line (50006) on EVERY pass."""
    import io, types as _types
    t0 = time.time()
    try:
        gs_len = len(getattr(_import_module(
            'gclient.data.lobby_gun_skin_item_data'), 'data', None) or {})
    except Exception:
        gs_len = -1
    try:
        lid_len = len(getattr(_import_module(
            'gclient.data.lobby_item_data'), 'data', None) or {})
    except Exception:
        lid_len = -1
    cat_sig = (len(WEP), len(WEP_SKIN_INFO), len(HERO), len(HERO_SKIN_INFO),
               len(EMOTE_INFO), gs_len, lid_len)
    cat_rebuilt = False
    if cat_sig != _ids_scan['cat_sig']:
        _ids_scan['cat_sig'] = cat_sig
        _ids_scan['cat_text'], _ids_scan['cat_counts'] = _ids_catalog_text()
        cat_rebuilt = True
    # -- runtime walk: every loaded module, its classes + methods + funcs
    r_mods, r_classes, r_methods, r_funcs = [], {}, {}, {}
    for mname in sorted(sys.modules):
        _ids_gil_yield()
        mod = sys.modules.get(mname)
        if mod is None or mname == '__main__':
            continue
        try:
            mvars = vars(mod)
            items = list(mvars.items())
        except Exception:
            continue
        r_mods.append(mname)
        cl, fn = [], []
        for attr, obj in items:
            try:
                if isinstance(obj, type):
                    cl.append(attr)
                    try:
                        # v7.30R6: OWN members via vars() only - dir()
                        # pulled every inherited/builtin member and the
                        # R5 device scan exploded to 1.8M entries / 41 MB
                        # / 30 s passes. Callable + non-type, dunderless,
                        # capped at 128 per class / 60k classes total.
                        meths = sorted(
                            n for n, v in list(vars(obj).items())
                            if not n.startswith('_')
                            and callable(v) and not isinstance(v, type))
                        if len(meths) > 128:
                            meths = meths[:128]
                    except Exception:
                        meths = []
                    if len(r_methods) < 60000:
                        r_methods['%s.%s' % (mname, attr)] = meths
                elif isinstance(obj, (_types.FunctionType,
                                      _types.BuiltinFunctionType)):
                    fn.append(attr)
            except Exception:
                continue
        if cl:
            r_classes[mname] = sorted(cl)
        if fn:
            r_funcs[mname] = sorted(fn)
    # -- live object census every 5th pass: type name -> alive count.
    #    The last census is KEPT between census passes so the headline
    #    names= counter stays stable instead of oscillating.
    _ids_scan['passes'] += 1
    if _ids_scan['passes'] % 5 == 1:
        try:
            import gc
            census = {}
            for obj in gc.get_objects():
                _ids_gil_yield()
                tn = type(obj).__name__
                census[tn] = census.get(tn, 0) + 1
            _ids_scan['last_live'] = census
        except Exception:
            pass
    live_types = _ids_scan.get('last_live') or {}
    n_cls = sum(len(v) for v in r_classes.values())
    n_meth = sum(len(v) for v in r_methods.values())
    n_func = sum(len(v) for v in r_funcs.values())
    names = len(r_mods) + n_cls + n_meth + n_func + len(live_types)
    sig = (names, len(r_mods), len(r_classes), len(r_methods),
           len(r_funcs), len(live_types))
    changed = cat_rebuilt or sig != _ids_scan['last_sig']
    if not changed:
        _ids_send_status(names, len(r_mods), n_cls, n_meth, n_func,
                         len(live_types), _ids_scan['saves'],
                         _ids_scan.get('last_kb', 0))
        return
    _ids_scan['last_sig'] = sig
    _ids_scan['last_names'] = names
    out = io.StringIO()
    w = out.write
    w('# BS_IDs.py - NEXORA BS live ID dump\n')
    w('# While the Live ID scan checkbox is on, this file keeps updating\n')
    w('# as the game loads more (classes, methods, functions, live types).\n')
    w('# build=%s utc=%s\n' % (PAYLOAD_BUILD, _utc_stamp()))
    w('# live: names=%d modules=%d classes=%d methods=%d functions=%d '
      'live_types=%d | save #%d\n'
      % (names, len(r_mods), n_cls, n_meth, n_func, len(live_types),
         _ids_scan['saves'] + 1))
    cc = _ids_scan.get('cat_counts') or {}
    w('# catalogs: weapons=%d weapon_skins=%d strikers=%d striker_skins=%d '
      'emotes=%d gun_items=%d vault_items=%d\n'
      % (cc.get('weapons', 0), cc.get('weapon_skins', 0),
         cc.get('strikers', 0), cc.get('striker_skins', 0),
         cc.get('emotes', 0), cc.get('gun_items', 0),
         cc.get('vault_items', 0)))
    w(_ids_scan['cat_text'])
    w('\nRUNTIME_MODULES = [  # every loaded Python module\n')
    for m in r_mods:
        _ids_gil_yield()
        w('    %r,\n' % (m,))
    w(']\n')
    w('\nRUNTIME_CLASSES = {  # module: [class names]\n')
    for m in sorted(r_classes):
        _ids_gil_yield()
        w('    %r: %r,\n' % (m, r_classes[m]))
    w('}\n')
    w('\nRUNTIME_METHODS = {  # module.Class: [method names]\n')
    for k in sorted(r_methods):
        w('    %r: %r,\n' % (k, r_methods[k]))
    w('}\n')
    w('\nRUNTIME_FUNCTIONS = {  # module: [function names]\n')
    for m in sorted(r_funcs):
        w('    %r: %r,\n' % (m, r_funcs[m]))
    w('}\n')
    w('\nLIVE_TYPES = {  # type name -> alive objects (census)\n')
    for k in sorted(live_types):
        w('    %r: %d,\n' % (k, live_types[k]))
    w('}\n')
    text = out.getvalue()
    path = '/storage/emulated/0/Nexora/BS_IDs.py'
    tmp = path + '.tmp'
    try:
        with open(tmp, 'w', encoding='utf-8') as f:
            # v7.30R12: chunked write - one 10 MB f.write(text) held the
            # GIL through the whole encode+copy.
            for _i in range(0, len(text), 262144):
                f.write(text[_i:_i + 262144])
                _ids_gil_yield()
        os.replace(tmp, path)
    except Exception as e:
        _plog('[IDS] save failed: %r' % (e,))
        try:
            os.remove(tmp)
        except Exception:
            pass
        return
    _ids_scan['saves'] += 1
    _ids_scan['last_kb'] = len(text) // 1024
    _plog('[IDS] live: names=%d mods=%d classes=%d methods=%d funcs=%d '
          'live_types=%d -> saved #%d (%.0f kB in %.1fs)'
          % (names, len(r_mods), n_cls, n_meth, n_func, len(live_types),
             _ids_scan['saves'], len(text) / 1024.0, time.time() - t0))
    _ids_send_status(names, len(r_mods), n_cls, n_meth, n_func,
                     len(live_types), _ids_scan['saves'],
                     _ids_scan['last_kb'])


def _process_debug_requests():
    """Menu "Dump debug" button -> iDebugDump counter."""
    try:
        _process_ids_dump_requests()
    except Exception:
        pass
    n = _safe_int(sync_attrs.get('iDebugDump', 0), 0)
    if n == _debug_dump_seen[0]:
        return False
    _debug_dump_seen[0] = n
    _game_run('debug-dump', _debug_dump_all, 'menu')
    return True


def _debug_dump_all(tag):
    try:
        _debug_dump_emote(tag)
    except Exception as e:
        _plog('[DEBUG] emote dump failed: %r' % (e,))
    try:
        _debug_dump_striker(tag)
    except Exception as e:
        _plog('[DEBUG] striker dump failed: %r' % (e,))
    try:
        _debug_dump_weapon(tag)
    except Exception as e:
        _plog('[DEBUG] weapon dump failed: %r' % (e,))
    try:
        _unlock_dump()
    except Exception as e:
        _plog('[DEBUG] unlock dump failed: %r' % (e,))


# ============================================================
# v6.6: UNLOCK  (the panel that took the executions slot)
# ============================================================
# The client decides whether an item can be used by asking its own bag/lobby
# data "do I own this". Nothing here invents an API: every gclient module that
# is already loaded is scanned for zero-or-one-argument predicates whose name
# says ownership, and each is wrapped to answer True while the matching switch
# is on. Whatever is found is written to the debug file, so if a build answers
# ownership somewhere else, the list says so instead of the toggle silently
# doing nothing.
_UNLOCK_HOOKED = []
_UNLOCK_SIG = [None]

# v6.6b: WHAT WENT WRONG IN THE FIRST ATTEMPT, AND WHY IT LOCKED THE LOBBY
# ---------------------------------------------------------------------
# v6.6 matched any gclient callable whose name contained "unlock", "own" or
# "possess". "own" is inside *Down*load, *Count*down* and *Shut*down*, so the
# build wrapped:
#     cdata_util.GetHasDownloadedMapsByMatchId
#     cdata_util.GetHasDownloadedMatchByMatchId
#     cdata_util.GetHasDownloadedMapsBySpaceIds
#     dlc_download_request.DlcDownloadRequest   (a CLASS)
#     cconst.LoadingBarCountDownTxtType         (a CLASS)
# every one of them answered True, so the client believed it already had the
# match data and the DLC request object was replaced by a function. The loading
# bar then waited forever - the app never got into the lobby.
#
# The rules are strict now:
#   * never wrap a class or a non-function;
#   * the name must END in a real ownership word (Owned / Unlocked / Own /
#     Possess), so "Download" and "Countdown" can never match;
#   * anything mentioning download / dlc / loading / request / progress is
#     refused outright, even if it ends in "Owned";
#   * nothing is wrapped at all unless one of the three switches is ON.
_UNLOCK_BLOCK = ('download', 'dlc', 'loading', 'countdown', 'shutdown',
                 'request', 'pending', 'progress', 'map', 'space', 'update',
                 'patch', 'install')
_UNLOCK_ENDINGS = ('owned', 'unlocked', 'own', 'unlock', 'possess',
                   'possessed', 'purchased', 'bought')
# v7.23: vault/warehouse/collection added - the vault's own UI modules
# (where the emote list checks live) load LATE, after boot.
# v7.30R24: card/profile/title/action/frame/avatar/display/pose - the
# avatar-card, name-frame and join-team-animation (display action)
# modules the R23 report asked to unlock ride these name families.
_UNLOCK_MODULE_HINT = ('util', 'bag', 'inventory', 'item', 'skin', 'hero',
                       'emote', 'lobby', 'shop', 'mall', 'store', 'package',
                       'vault', 'warehouse', 'wardrobe', 'collection',
                       'card', 'profile', 'title', 'action', 'frame',
                       'avatar', 'display', 'pose', 'anim')
_unlock_mod_seen = [-1]
_UNLOCK_REFUSED = []


def _unlock_gate(attr):
    """'' when this name is not an ownership predicate, else the switch key."""
    low = str(attr).lower()
    if not low or any(b in low for b in _UNLOCK_BLOCK):
        return ''
    # v7.27: "Down".endswith("own") - the v7.25 class-method scan wrapped
    # every *Down input handler (_OnJumpDown, listenKeyDown,
    # PlayerInput_*Down, OnMouseRDown...) and forced True, so the jump
    # button - and half the HUD - went dead while unlock switches were
    # on. Same trap: 'shown' (MarkFirstGuideShown) and setters
    # (SetIsBought). Input handlers are never ownership predicates.
    if low.endswith(('down', 'shown', 'rown', 'town', 'crown')):
        return ''
    if low.startswith(('set', 'refresh', 'handle')):
        return ''
    if not low.endswith(_UNLOCK_ENDINGS):
        return ''
    if 'emote' in low:
        return 'bUnlockEmotes'
    # v7.21: scopes ride the skin gate
    if 'optic' in low or 'scope' in low or 'reticle' in low:
        return 'bUnlockSkins'
    if 'skin' in low or 'hero' in low or 'guise' in low or 'striker' in low:
        return 'bUnlockSkins'
    # v7.30R24: avatar cards, name frames, titles, display actions
    # (join-team animations) and poses ride the master unlock switch
    if any(t in low for t in ('card', 'avatar', 'frame', 'title',
                              'action', 'pose', 'anim', 'display')):
        return 'bUnlockAll'
    return 'bUnlockAll'


def _unlock_enabled():
    # v7.30R27: REMOVED by user request - the unlock tab and all its
    # features are gone. This hard-off replaces the switch read, so
    # every installer gated on it (unlock predicates, emote unlock,
    # hall item emote unlock) stays permanently off and unwrapped even
    # if a stale switch value arrives from an old config.
    return False


def unlock_family(item_id):
    """v2.112: Collection + Consumable vault families unlock
    with the emote/Collection toggle (the cosmetic gate)."""
    try:
        item_id = _safe_int(item_id, 0)
        if not item_id:
            return False
        cat = _v109_category(item_id)
        return cat in ('emote', 'collection', 'consumable',
                       'profile', 'other')
    except Exception:
        return False


# #======================================================================
# //  UNLOCKS.PY
# //
# //  This file is for: UNLOCKS: the vault ownership force (IHallItems.HasItemByItemId), the v832/v839 hall-item hooks, the unlock gates - the melee, striker, emote, Collection + Consumable families.
# //
# //  Part of the split TREACKY BS payload (v2.112).  The runtime
# //  file payload/skins_payload.py is GENERATED: run
# //  tools/build_payload.py after editing these modules.
# #======================================================================
# ============================ v2.113 ===================================
# One menu checkbox per unlock family (the user's fine-grained request).
FINE_FLAGS = {
    'melee': 'bUnlockMelee', 'striker': 'bUnlockHeroes', 'emote': 'bUnlockEmotes',
    'playpal': 'bUnlockPlayPal', 'vehicle': 'bUnlockVehicles',
    'parachute': 'bUnlockParachute', 'glide': 'bUnlockGlide',
    'loadoutdrop': 'bUnlockLoadoutDrop', 'skydive': 'bUnlockSkydive',
    'grenade': 'bUnlockGrenades', 'meds': 'bUnlockMeds',
    'avatar': 'bUnlockAvatar', 'profile': 'bUnlockProfile',
    'consumable': 'bUnlockMeds', 'other': 'bUnlockEmotes',
}
NAME_FAMILY = (
    (('parachute',), 'parachute'),
    (('glide',), 'glide'),
    (('skydiv', 'skydive', 'trailing', 'aircraft'), 'skydive'),
    (('loadout', 'airdrop', 'air drop'), 'loadoutdrop'),
    (('grenade', 'bomb', 'throw', 'throwing'), 'grenade'),
    (('med', 'bandage', 'heal', 'deathbox', 'death box', 'consumable'), 'meds'),
    (('avatar',), 'avatar'),
    (('banner', 'frame', 'homepage', 'card', 'chat', 'hall background',
      'hall music', 'nameplate'), 'profile'),
    (('vehicle', 'car', 'drift', 'motor'), 'vehicle'),
    (('playpal', 'panpan', 'pet', 'buddy'), 'playpal'),
)


def fine_family(item_id):
    try:
        row = _v109_row(item_id) or {}
        blob = ''
        for key in ('name', 'short_desc', 'sub_type', 'main_name', 'desc'):
            try:
                val = _data_get(row, key, '') if not isinstance(row, dict) else row.get(key, '')
            except Exception:
                val = ''
            if isinstance(val, str):
                blob += ' ' + val.lower()
        if not blob.strip():
            return None
        for needles, family in NAME_FAMILY:
            for nd in needles:
                if nd in blob:
                    return family
    except Exception:
        return None
    return None


def should_unlock(item_id):
    """Fine family flag -> coarse family flag -> the emote-range rule."""
    try:
        fam = fine_family(item_id)
        if fam:
            key = FINE_FLAGS.get(fam)
            if key and flag_on_local(key):
                return True
        cat = _v109_category(item_id)
        if cat:
            key = FINE_FLAGS.get(cat)
            if key and flag_on_local(key):
                return True
        if (isinstance(item_id, int) and 6040000000 <= item_id < 6050000000
                and _unlock_should_force('bUnlockEmotes')):
            return True
        # v2.114: the cosmetic band fallback - rows whose
        # names never resolve still unlock through the band.
        if (isinstance(item_id, int)
                and 6000000000 <= item_id < 6700000000):
            return flag_on_local('bUnlockEmotes')
        return unlock_family(item_id) and _unlock_should_force('bUnlockEmotes')
    except Exception:
        return False


def flag_on_local(key):
    try:
        return bool(sync_attrs.get(key, False) or sync_attrs.get('bUnlockAllVault', False)
                    or _unlock_should_force(key))
    except Exception:
        return False

# ========================== end v2.113 ===================================
