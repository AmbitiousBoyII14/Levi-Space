# ============================================================
# EQUIP.PY (payload feature module)
# PROVIDES: _striker_is_local_avatarish, _doll_is_local, _striker_native_local_display, _create_owner_is_local, _v218drop_log, call_guid, note_local, _v218drop_forced_skin, Create, AddWeaponForDoll, AddWeaponByEquipId, AddWeaponByEquipIdForHeroSkin, ChangeWeaponSkinId, _game_mark_thread, ... +40 more | _GAME_ACTIONS, _GAME_ACTIONS_LOCK, _GAME_PUMP_BUSY, _GAME_TID, _GAME_STATS, UDP_FX_PORT, FX_KIND_TOKENS, FX_SOURCE_MODULES, _FX_HEALTH_FIELDS, _NAME_OVERRIDE_PATH, ...
# REQUIRES: shared namespace (config/names/main/game_api/catalog);
#           game modules imported inline, verified against the dumps.
# Feature module - see REWRITE_PLAN.md S1.
# ============================================================
"""Game-thread dispatch + watchdog: _game_pump event routing, equip RPC intercept, tick stall attribution (slow= tags), native case/env plumbing."""

# #======================================================================
# //  EQUIP.PY
# //
# //  This file is for: EQUIP PLUMBING: the forced-skin resolver (get_forced_skin rebind STAYS LAST), the equip nonces, the equip signature probes.
# //
# //  Part of the split TREACKY BS payload (v2.112).  The runtime
# //  file payload/skins_payload.py is GENERATED: run
# //  tools/build_payload.py after editing these modules.
# #======================================================================



def _striker_is_local_avatarish(av):
    """v8.07: True for ANY flavor of the local player's avatar - the
    combat avatar, the hall PlayerAvatar, an avatarish owner. Used by
    the gun-skin local gates and the arm-skin id force."""
    try:
        if av is None:
            return False
        if _striker_is_local(av):
            return True
        try:
            genv_obj = globals().get('genv')
            if av is getattr(genv_obj, 'avatar', None):
                return True
        except Exception:
            pass
        try:
            sp = getattr(Space, '_instance', None)
            owner = getattr(sp, 'owner', None) if sp else None
            if owner is not None:
                if av is getattr(owner, 'avatar', None):
                    return True
                if av is getattr(owner, 'combat_avatar', None):
                    return True
        except Exception:
            pass
        return False
    except Exception:
        return False


def _doll_is_local(doll):
    """v8.07: is this doll the local player's? Keeps gun skins off
    OTHER players' weapons while in a match."""
    try:
        if doll is None:
            return False
        if _striker_is_local_avatarish(doll):
            return True
        for attr in ('owner', 'avatar', 'player_avatar',
                     'combat_avatar'):
            try:
                o = getattr(doll, attr, None)
                if o is not None and _striker_is_local_avatarish(o):
                    return True
            except Exception:
                pass
        return False
    except Exception:
        return False


def _striker_native_local_display(obj):
    """Authenticate a local lobby/profile display without a hero-only guess.

    Native Striker selection is process-local, but many dolls can share one
    hero.  Only the established avatar/combat links or the official local
    hall_model_mgr.main_npc chain are eligible.  Unknown profile/result/team
    objects fail closed; their official server/replay appearance is retained.
    """
    try:
        if obj is None:
            return False
        # v2.104: the hero-select showroom / personal-homepage / warehouse
        # showroom controllers render the LOCAL player by definition (the
        # v8.17 note: 'the profile shows the LOCAL player').  Their class
        # identity authenticates them - they hold no avatar links.
        try:
            _nm = type(obj).__name__
            _mod = type(obj).__module__ or ''
            if ('showroom' in _mod or 'personal_homepage' in _mod
                    or _nm in ('PersonalHomepageModelCtrl',
                               'PersonalHomepageModelComp')):
                return True
        except Exception:
            pass
        if _doll_is_local(obj):
            return True
        candidates = []
        genv_obj = globals().get('genv')
        if genv_obj is None:
            getter = globals().get('_game_genv')
            if callable(getter):
                try:
                    genv_obj = getter()
                except Exception:
                    genv_obj = None
        for value in (
                getattr(genv_obj, 'avatar', None),
                getattr(getattr(genv_obj, 'hall_model_mgr', None),
                        'main_npc', None)):
            if value is not None and all(value is not old for old in candidates):
                candidates.append(value)
        try:
            sp = getattr(Space, '_instance', None)
            owner = getattr(sp, 'owner', None) if sp else None
            for value in (getattr(owner, 'avatar', None),
                          getattr(owner, 'combat_avatar', None)):
                if value is not None and all(
                        value is not old for old in candidates):
                    candidates.append(value)
        except Exception:
            pass
        if not candidates:
            return False
        queue = [obj]
        seen = set()
        steps = 0
        while queue and steps < 12:
            current = queue.pop(0)
            steps += 1
            if current is None or id(current) in seen:
                continue
            seen.add(id(current))
            if any(current is candidate for candidate in candidates):
                return True
            for attr in ('owner', 'avatar', 'player_avatar', 'combat_avatar',
                         'model_owner', 'doll', 'npc', 'ctrl'):
                try:
                    value = getattr(current, attr, None)
                except Exception:
                    value = None
                if value is not None and id(value) not in seen:
                    queue.append(value)
    except Exception:
        pass
    return False


def _create_owner_is_local(args, kwargs):
    """v8.07: EquipCaseFactory.Create runs for EVERY weapon in the
    match - enemies, teammates, training-range robots. The v8.06 leak:
    our selected gun skin was armed on ALL of them (user: 'gun skin
    shows on other players too'). Only the LOCAL player's creates get
    the skin now; everything else stays honest."""
    try:
        cands = []
        if args:
            cands.append(args[0])
        cands.extend(kwargs.values())
        saw_avatar = False
        for c in cands:
            if hasattr(c, 'GetCurWeapon') or hasattr(
                    c, 'combat_avatar'):
                saw_avatar = True
                if _striker_is_local_avatarish(c):
                    return True
        if saw_avatar:
            return False
        # no owner in the args: world/pickup creates in a match stay
        # honest; the hall keeps the old behavior (the lobby weapon
        # show relies on it)
        try:
            return not _hero_in_match()
        except Exception:
            return False
    except Exception:
        return False


# pairicon4: retain the exact local weapon-instance identity for an own drop.
# EquipCaseFactory.Create carries (owner, guid, weapon_id, ...).  A world case
# is eligible only when its guid was previously observed on a LOCAL create and
# the weapon id still matches.  This deliberately cannot paint every floor
# weapon of the same base, and another player's create remains excluded.
_v218drop_local_guids = {}
_v218drop_log_seen = {}


def _v218drop_log(key, message, limit=1):
    try:
        count = _v218drop_log_seen.get(key, 0)
        if count >= limit:
            return
        if len(_v218drop_log_seen) >= 64 and key not in _v218drop_log_seen:
            return
        _v218drop_log_seen[key] = count + 1
        _plog('[V218DROP] %s' % message)
    except Exception:
        pass


def call_guid(wid, args):
    """Return the documented factory guid only for the proven call layout."""
    try:
        if (len(args) < 3
                or _safe_int(args[2], 0) != _safe_int(wid, 0)):
            return ''
        guid = args[1]
        if not isinstance(guid, str) or not guid:
            return ''
        return guid
    except Exception:
        return ''


def note_local(wid, args):
    try:
        guid = call_guid(wid, args)
        if not guid:
            return
        wid = _safe_int(wid, 0)
        _v218drop_local_guids[guid] = (wid, time.time())
        if len(_v218drop_local_guids) > 128:
            # Dict order is insertion order; bound memory without a scan.
            _v218drop_local_guids.pop(next(iter(_v218drop_local_guids)))
        # One creation-time record per weapon, never a per-frame case log.
        _v218drop_log(
            ('local-create', wid),
            'local create wid=%d guid=%r owner=%s match=%r'
            % (wid, guid, type(args[0]).__name__ if args else 'none',
               _hero_in_match()))
    except Exception:
        pass


def _v218drop_forced_skin(wid, args, kwargs):
    """Resolve one own dropped world case; all other creates fail closed."""
    try:
        guid = call_guid(wid, args)
        if not guid:
            return None
        wid = _safe_int(wid, 0)
        entry = _v218drop_local_guids.get(guid)
        if entry is None or _safe_int(entry[0], 0) != wid:
            # Pairicon5 bounded evidence: check an ownerless in-match create
            # once per wid.  Held/other-player creates still do no scene or
            # selection query, and subsequent misses remain lookup-only.
            diagnostic_key = ('unmatched-check', wid)
            if diagnostic_key not in _v218drop_log_seen:
                _v218drop_log_seen[diagnostic_key] = 1
                candidates = list(args[:1]) + list(kwargs.values())
                held = any(hasattr(candidate, 'GetCurWeapon')
                           or hasattr(candidate, 'combat_avatar')
                           for candidate in candidates)
                if not held and _hero_in_match():
                    forced = _get_forced_weapon_skin(wid)
                    if forced:
                        known = [key for key, value in
                                 _v218drop_local_guids.items()
                                 if _safe_int(value[0], 0) == wid][-4:]
                        _v218drop_log(
                            ('unmatched-create', wid),
                            'unmatched ownerless create wid=%d guid=%r '
                            'local_guids=%r skin=%d'
                            % (wid, guid, known, forced))
            return None
        if time.time() - entry[1] > 1800.0:
            _v218drop_local_guids.pop(guid, None)
            return None
        candidates = []
        if args:
            candidates.append(args[0])
        candidates.extend(kwargs.values())
        for candidate in candidates:
            if (hasattr(candidate, 'GetCurWeapon')
                    or hasattr(candidate, 'combat_avatar')):
                # A local or remote avatar is holding this create.  The local
                # path above handles the former; neither is a world drop.
                return None
        if not _hero_in_match():
            return None
        forced = _get_forced_weapon_skin(wid)
        if not forced:
            return None
        _v218drop_log(('world-apply', guid, wid, forced),
                      'own drop matched wid=%d guid=%r skin=%d'
                      % (wid, guid[:32], forced))
        return forced
    except Exception:
        return None


wv_probe_done = [False]   # one-shot weapon-visual API probe
melee_born_clean = set()  # v8.36: melees born clean, applied after


@HOOK(EquipCaseFactory, 0)
def Create(wid, *args, **kwargs):
    # v8.70 reference picker repair, scoped to authentic melee rows only.
    try:
        normalizer = globals().get('melee_create_id')
        if callable(normalizer):
            wid = normalizer(wid)
    except Exception:
        pass
    # v8.10: lazy racer shield retry - weapons are being created, so
    # the equip modules are loaded by now (the boot install missed).
    try:
        install_racer_shield()
    except Exception:
        pass
    _create_diag_once(wid, args, kwargs)
    args_list = list(args)
    forced_skin = None
    _native_preview_gate = globals().get('native_equip_takeover')
    _native_preview = False
    try:
        if callable(_native_preview_gate):
            _native_preview = _native_preview_gate(wid)
    except Exception:
        _native_preview = False
    if (sync_attrs.get('bSkinHack') and not _native_preview
            and has_weapon_row(wid)):
        if _create_owner_is_local(args, kwargs):
            note_local(wid, args_list)
            forced_skin = _get_forced_weapon_skin(wid)
        else:
            # No base-wide world fallback: only the exact guid recorded by a
            # local create can identify the player's own dropped weapon.
            forced_skin = _v218drop_forced_skin(wid, args_list, kwargs)
        if forced_skin is not None:
            # v8.13: born-with-skin is RESTORED - it is the only
            # channel that refreshes the weapon MODEL. The v8.12
            # removal proved it: effects kept working (case data) but
            # the visible model stayed default. The v8.10/11 crash
            # loop is handled separately now: a case born with an
            # UNOWNED skin comes out half-initialized, so the two
            # known holes are completed right here (below) and the
            # racer shields absorb anything else.
            # v8.23: inject ONLY into an int/None slot 4 - every call
            # shape in the device logs carries an int there (0), but
            # a weapon whose factory passes a complex object (a dict,
            # per the parallel v8.23 review) must pass through
            # untouched; the post-create apply still lands the skin.
            # v8.36: MELEE equips are exempt from the injection. The
            # v8.34 device log (nexora_debug-9.txt) proved the melee
            # factory aborts partway on an injected skin: EVERY forced
            # melee create printed '[V813] completed born-with-skin
            # case wid=33' (43 in one session; no gun ever did), the
            # half-born case never builds its model/guise component,
            # and the post-create apply dies inside ChangeWeaponGuise
            # with "'NoneType' object has no attribute 'IsValid'" -
            # the melee rendered NOTHING in gameplay. The melee is now
            # born with the game's own slot-4 value (a fully-built
            # case) and the post-create apply below drives the pick
            # through ChangeWeaponSkin/ChangeWeaponGuise/LoadModelSkin
            # on the healthy case. Guns keep born-with-skin: v8.12
            # proved the apply alone does not refresh a GUN model.
            _melee836 = wid in (globals().get('WEP_MELEE_IDS') or {})
            if (not _melee836 and len(args_list) > 4
                    and (args_list[4] is None
                         or isinstance(args_list[4], int))):
                args_list[4] = forced_skin
            elif _melee836:
                try:
                    if wid not in melee_born_clean:
                        melee_born_clean.add(wid)
                        _plog('[V836] melee wid=%s born CLEAN (no '
                              'slot-4 injection; pick=%s lands via the '
                              'post-create apply)'
                              % (wid, forced_skin))
                except Exception:
                    pass
    if not wid:
        # v2.87: the melee preview path calls AddWeaponByEquipId(None)
        # -> _DoAddWeapon -> Create(None) -> KeyError(None).  Resolve
        # the id from the args through the official melee chain.
        try:
            _mids287 = globals().get('WEP_MELEE_IDS') or {}
            for _cand287 in list(args_list[:5]):
                if isinstance(_cand287, bool):
                    continue
                _ci287 = _v109_int(_cand287, 0)
                if not _ci287:
                    continue
                if _ci287 in _mids287:
                    wid = _ci287
                    break
                _we287 = melee_equip(_v109_row(_ci287))
                if _we287:
                    wid = _we287
                    break
            if not wid:
                for _cand287 in list(args_list[:5]):
                    if isinstance(_cand287, bool):
                        continue
                    _ci287 = _v109_int(_cand287, 0)
                    if _ci287:
                        wid = melee_create_id(_cand287)
                        if wid:
                            break
            if wid:
                _v109_log(('create-resolve', wid),
                          'create id resolved wid=%s from args=%r'
                          % (wid, [getattr(a, 'item_id', a)
                                   for a in args_list[:5]]), 1)
        except Exception as _e287c:
            _v109_log(('create-resolve-err', repr(_e287c)),
                      'create id resolve failed: %r' % (_e287c,), 1)
    result = EquipCaseFactory._Create(wid, *args_list, **kwargs)
    # v8.13: complete a born-with-skin case. v8.10/11 device logs: the
    # factory aborts partway for unowned skins -> the case is missing
    # is_in_combat and play_other_effect_tick -> the racer refresh
    # crashed the game thread. Fill the two known holes at the source;
    # the (now broad) racer shields stay as the net for the rest.
    if result is not None and forced_skin is not None:
        try:
            _miss = [a2 for a2 in ('is_in_combat',
                                   'play_other_effect_tick',
                                   'is_show_simple_part_model')
                     if not hasattr(result, a2)]
            if _miss:
                if 'is_in_combat' in _miss:
                    result.is_in_combat = bool(_hero_in_match())
                    result._treacky_case_state_default = True
                if 'play_other_effect_tick' in _miss:
                    # v8.14: must return a 2-TUPLE - the game unpacks
                    # it (cimp_emote.py:550 'cannot unpack non-
                    # iterable NoneType' crashed EnterEmoteState in
                    # the v8.13 log).
                    result.play_other_effect_tick = \
                        lambda *a3, **k3: (None, None)
                if 'is_show_simple_part_model' in _miss:
                    # v8.14: the profile homepage's weapon refresh
                    # crashed on this one (v8.13 log).
                    result.is_show_simple_part_model = False
                _plog('[V813] completed born-with-skin case wid=%s '
                      'missing=%r' % (wid, _miss))
        except Exception:
            pass
        try:
            if not wv_probe_done[0] and _hero_in_match() \
                    and result is not None:
                wv_probe_done[0] = True
                _meths = [m for m in dir(result)
                          if any(t in m.lower() for t in
                                 ('model', 'skin', 'guise', 'load',
                                  'refresh', 'show', 'attach'))]
                _plog('[V813] weapon-visual probe %s modelish=%r'
                      % (type(result).__name__, _meths[:150]))
                # v8.14: the melee skin needs the game's per-item
                # resource download (born-with-skin alone did not
                # fetch it). Find the download/cdn managers so the
                # next log names the exact call to wire.
                try:
                    _dl_mods = [m for m in list(sys.modules)
                                if any(t in m.lower() for t in
                                       ('download', 'cdn', 'preload'))
                                and not m.startswith('_')][:12]
                    _dl_detail = []
                    for _dm in _dl_mods[:6]:
                        try:
                            _mo = sys.modules.get(_dm)
                            _fns = [n for n in dir(_mo)
                                    if callable(getattr(_mo, n, None))
                                    and not n.startswith('_')][:20]
                            _dl_detail.append('%s:%r' % (_dm, _fns))
                        except Exception:
                            pass
                    _plog('[V814] download-api probe mods=%r detail=%r'
                          % (_dl_mods, _dl_detail))
                except Exception as _dpe:
                    _plog('[V814] download-api probe error=%r'
                          % (_dpe,))
        except Exception:
            pass
    if result and sync_attrs.get('bSkinHack'):
        if forced_skin is not None:
            _apply_weapon_case_skin(result, wid, forced_skin, 'EquipCaseFactory.Create')
    return result

@HOOK(Doll, 0)
def AddWeaponForDoll(self, equip_id=None, skin_id=None, guise_id=None, part_slots=None, extra=None, *args, **kwargs):
    # v8.21: the original v7.30R26 gate, restored - the v8.x
    # in-match local-doll gate and the last_wid bookkeeping
    # are gone (owner directive: bring back the 7.30 behavior).
    try:
        _striker_doll_note(self)
    except Exception:
        pass
    _native_gate = globals().get('native_equip_takeover')
    _native_block = (callable(_native_gate) and _native_gate(equip_id))
    if (sync_attrs.get('bSkinHack') and not _native_block
            and equip_id is not None
            and has_weapon_row(equip_id)):
        try:
            new_skin = _get_forced_weapon_skin(equip_id)
            if new_skin is not None:
                if guise_id is not None:
                    guise_id = new_skin
                else:
                    # v8.23: was "elif skin_id is not None" - a
                    # slotless add (skin AND guise both None) never
                    # substituted. Set the skin slot unconditionally.
                    skin_id = new_skin
        except:
            pass
    return Doll._AddWeaponForDoll(self, equip_id, skin_id, guise_id, part_slots, extra, *args, **kwargs)

@HOOK(Doll, 0)
def AddWeaponByEquipId(self, equip_id=None, skin_id=None, guise_id=None, part_slots=None, principle_role=False, extra=None, *args, **kwargs):
    # v8.21: the original v7.30R26 gate, restored - the v8.x
    # in-match local-doll gate and the last_wid bookkeeping
    # are gone (owner directive: bring back the 7.30 behavior).
    try:
        _striker_doll_note(self)
    except Exception:
        pass
    _native_gate = globals().get('native_equip_takeover')
    _native_block = (callable(_native_gate) and _native_gate(equip_id))
    if (sync_attrs.get('bSkinHack') and not _native_block
            and equip_id is not None
            and has_weapon_row(equip_id)):
        try:
            new_skin = _get_forced_weapon_skin(equip_id)
            if new_skin is not None:
                if guise_id is not None:
                    guise_id = new_skin
                else:
                    # v8.23: slotless adds substitute too (see
                    # AddWeaponForDoll above).
                    skin_id = new_skin
        except:
            pass
    return Doll._AddWeaponByEquipId(self, equip_id, skin_id, guise_id, part_slots, principle_role, extra, *args, **kwargs)


@HOOK(Doll, 0)
def AddWeaponByEquipIdForHeroSkin(self, *args, **kwargs):
    # v8.22: the HERO-SKIN weapon channel. The v8.20/v8.21 device
    # logs: the lobby/profile weapon adds carry skin_id=0 (the REAL
    # equip state has no skin), and this sibling method exists on
    # Doll and every showroom controller (BS_IDs dump) - while a
    # hero skin is showing (this payload's default state) the
    # weapon rides THIS channel. Same R26 argument gate as the
    # other two adds: substitute the picked skin into the EXISTING
    # argument slot (never reorders - the exact signature is
    # unverified, so the slot map follows the known siblings:
    # (equip, skin, guise, ...)). No apply chain, no case surgery.
    try:
        _striker_doll_note(self)
    except Exception:
        pass
    try:
        _equip = args[0] if args else kwargs.get('equip_id')
        _native_gate = globals().get('native_equip_takeover')
        _native_block = (callable(_native_gate) and _native_gate(_equip))
        if (sync_attrs.get('bSkinHack') and not _native_block
                and _equip is not None and has_weapon_row(_equip)):
            new_skin = _get_forced_weapon_skin(_equip)
            if new_skin is not None:
                _a = list(args)
                if len(_a) >= 3 and _a[2] is not None:
                    _a[2] = new_skin
                elif len(_a) >= 2:
                    _a[1] = new_skin          # v8.23: even when None
                elif kwargs.get('guise_id') is not None:
                    kwargs['guise_id'] = new_skin
                else:
                    kwargs['skin_id'] = new_skin   # v8.23: slotless too
                args = tuple(_a)
    except Exception:
        pass
    return Doll._AddWeaponByEquipIdForHeroSkin(self, *args, **kwargs)

# (v2: Doll._DoAddWeapon hook removed - no such method in the game stubs;
#  the old code had installed a wrapper that could only crash-call a
#  nonexistent original. AddWeaponForDoll/AddWeaponByEquipId cover it.)

@HOOK(Doll, 0)
def ChangeWeaponSkinId(self, skin_id, *args, **kwargs):
    if sync_attrs.get('bSkinHack'):
        try:
            equip_id = getattr(self, 'equip_id', 0)
            _native_gate = globals().get('native_equip_takeover')
            _native_block = (callable(_native_gate) and _native_gate(equip_id))
            if not _native_block and has_weapon_row(equip_id):
                new_skin = _get_forced_weapon_skin(equip_id)
                if new_skin is not None:
                    skin_id = new_skin
        except:
            pass
    return Doll._ChangeWeaponSkinId(self, skin_id, *args, **kwargs)

# ============================================================
# EQUIP NONCES (weapon only) - v3.1
# ============================================================
# The Striker / hero skin feature was removed in v3.1 and this handler
# went with it, minus the weapon half, which keeps its exact behaviour:
# the menu bumps iSkinEquipNonce and the skin is applied immediately
# instead of waiting for the next throttled pass.
_weapon_equip_nonce_seen = [0]


_hero_equip_nonce_seen = [0]
_emote_sel_seen = [-1]

# ============================================================
# v6.5: GAME-THREAD PUMP  --  the crash fix
# ============================================================
# Everything in this payload that runs on a timer runs on a Python thread, and
# the game objects it calls (models, entities, dlc, effects) belong to the game
# thread. Calling them from ours is what killed the app the moment an emote was
# applied in a match - the log stops between the selection line and the replay
# line, i.e. inside the game call itself, with no Python exception to catch
# because it dies natively.
#
# So: a thread may ENQUEUE, only the game thread EXECUTES. The pump is drained
# from functions the game engine itself calls every frame
# (_esp_aim_tick on a Space post-tick, and every emote/proto hook we own).
# In the lobby, where no Space tick exists, the calls are still safe (the game
# tolerates them there) so they run inline.
_GAME_ACTIONS = []
_GAME_ACTIONS_LOCK = threading.Lock()
_GAME_PUMP_BUSY = [False]
_GAME_TID = [None]
_GAME_STATS = {'posted': 0, 'ran': 0, 'errors': 0, 'last_error': None}


def _game_mark_thread():
    """Remember which thread the game calls us on."""
    if _GAME_TID[0] is None:
        _GAME_TID[0] = threading.current_thread().ident


def _game_on_game_thread():
    tid = _GAME_TID[0]
    return tid is not None and tid == threading.current_thread().ident


def _game_post(name, fn, *args, **kwargs):
    with _GAME_ACTIONS_LOCK:
        # A burst of menu picks must not queue a sequence of stale native
        # rebuilds.  Keep the newest equip request; other action types retain
        # their original FIFO behavior.
        if name in ('weapon-equip', 'hero-equip',
                    'attachment-catalog', 'attachment-inject',
                    'special-optic-catalog', 'special-optic-apply',
                    'special-optic-restore', 'special-optic-enforce',
                    'striker-combat-refresh', 'v109-native-visual-ticks',
                    'v109-melee-visual-apply', 'v109-melee-visual-restore'):
            for i, action in enumerate(_GAME_ACTIONS):
                if action[0] == name:
                    _GAME_ACTIONS[i] = (name, fn, args, kwargs)
                    break
            else:
                _GAME_ACTIONS.append((name, fn, args, kwargs))
        else:
            if len(_GAME_ACTIONS) > 8:      # never let a queue grow
                del _GAME_ACTIONS[:-8]
            _GAME_ACTIONS.append((name, fn, args, kwargs))
    _GAME_STATS['posted'] += 1
    return True


def _game_pump():
    """Run whatever a thread queued. Called from the game thread only."""
    if _GAME_PUMP_BUSY[0]:
        return 0
    _GAME_MARK = threading.current_thread().ident
    if _GAME_TID[0] is None:
        _GAME_TID[0] = _GAME_MARK
    _GAME_PUMP_BUSY[0] = True
    ran = 0
    try:
        for _ in range(3):
            with _GAME_ACTIONS_LOCK:
                if not _GAME_ACTIONS:
                    break
                name, fn, args, kwargs = _GAME_ACTIONS.pop(0)
            try:
                fn(*args, **kwargs)
                _GAME_STATS['ran'] += 1
                ran += 1
            except Exception as e:
                _GAME_STATS['errors'] += 1
                if _GAME_STATS['last_error'] != repr(e):
                    _GAME_STATS['last_error'] = repr(e)
                    _plog('[THREAD] %s failed: %r' % (name, e))
    finally:
        _GAME_PUMP_BUSY[0] = False
    return ran


def _game_run(name, fn, *args, **kwargs):
    """Run a game call from a safe context.

    On a match the Space post-tick is guaranteed, so queue it. In the lobby
    (or before the tid is known) run it inline - that is what already worked
    there.
    """
    try:
        if _game_on_game_thread() or not _hero_in_match():
            return fn(*args, **kwargs)
    except NameError:
        return fn(*args, **kwargs)
    _plog('[THREAD] %s queued for the game thread' % (name,))
    _game_post(name, fn, *args, **kwargs)
    return None




def _process_emote_selection():
    """When the menu changes the emote pick, play it NOW.

    v6.0 only cleared cached state and hoped the next read would pick the new
    value up. Nothing re-reads it, so the doll kept looping the emote it had
    already started - exactly the "same animation whatever I choose" bug.
    v6.1 replays: clear the live model, then start the forced emote on it.
    """
    try:
        if not _emote_gate():
            return False
        cur = _safe_int(sync_attrs.get('iEmoteSel', 0), 0)
        if cur == _emote_sel_seen[0]:
            return False
        _emote_sel_seen[0] = cur
        _plog('[EMOTE] selection idx=%d item=%r name=%r'
              % (cur, _emote_forced(), globals().get('_get_forced_emote_name',
                                                    lambda: None)()))
        replay = globals().get('_emote_replay')
        if callable(replay):
            _game_run('emote-replay', replay)
        return True
    except Exception as e:
        _plog('[EMOTE] selection error=%r' % (e,))
        return False




# ============================================================
# WEAPON FX  -  tracer / muzzle / kill broadcast  (v5.0)
# ============================================================
# v4.9 shipped this behind three checkboxes and it never ran:
#   * every call raised UnboundLocalError on _fx_pools (a missing
#     `global`, so the name was local to the function and read before
#     assignment) - 8,720 of them, 0 skins seeded
#   * so even with the toggles on, nothing was ever patched
#
# v5.0 does what the kill-animation fix does:
#   * NO toggles. It rides with bSkinHack, exactly like
#     _ensure_kill_effect_data, and always runs when a skin is forced.
#   * the skin's OWN row is the primary source. The v4.9 device probe
#     proved gun_skin_template_data[331199011] already carries real FX:
#       fps_tracer_bullet_id 1330117 / tps_tracer_bullet_id 1330115 /
#       fps_adstracer_bullet_id 1330118 / fps_simple_* 1330119,13301110 /
#       skin_hit_object_effect_id {..}, skin_optic_id 233011
#     The gap was never missing data - it was that those values were
#     never copied onto the weapon case the runtime reads during a shot.
#   * donors (harvested from the game's own rows) only fill fields the
#     skin genuinely lacks. Real field names/values from the v4.9 log:
#       tracer   : fps_tracer_bullet_id 110117 (20 rows), tps_* 110115,
#                  extra_ballistic_tracer_bullet_id 1101129, fps_ads* 110118
#       broadcast: kill_tip_icon_replace 5100101105 (40 rows),
#                  kill_avatar_effect 14300947, kill_tip_icon_2_replace
#   * muzzle: the skin tables carry NO muzzle flash *effect id* - only
#     skin_fire_sfx_id_replace / skin_fire_ads_sfx_id_replace (sound) and
#     the model replace ids. Those are mirrored under their own names
#     (a sound id into a sound field - never an id into the wrong field),
#     and the muzzle flash itself comes from the model replace the game
#     already applies. The log says so instead of pretending otherwise.
#
# Audio fields ending in a bare 'sfx_id' are excluded from donor pooling:
# those are the template's own sounds, not skin FX. '*_replace' skin-level
# replacements are kept because that is what a gun skin actually changes.
# ============================================================

UDP_FX_PORT = 50004

FX_KIND_TOKENS = {
    'tracer':    (('tracer',), ('trail',)),
    'muzzle':    (('muzzle',), ('fire', 'effect'), ('fire', 'fx'), ('gunfire',),
                  ('fire', 'sfx', 'replace'), ('muzzle', 'sfx')),
    'broadcast': (('broadcast',), ('racer',), ('kill_tip',), ('kill', 'effect'),
                  ('kill', 'avatar'), ('kill', 'icon')),
}

FX_SOURCE_MODULES = (
    'gclient.data.gun_skin_template_data',
    'gclient.data.gun_skin_equip_data',
    'gclient.data.gun_skin_item_data',
    'gclient.data.gun_skin_base_data',
)

# fields mirrored from the skin's own row onto the case even when the
# substring tables above would not classify them

_fx_scanned = [False]
_fx_logged = [False]
_fx_applied = set()
_fx_stats_pushed = [False]


def _fx_value_ok(value):
    if value is None or isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return value > 0
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict, set)):
        return len(value) > 0
    return False


def _fx_classify(field):
    low = str(field).lower()
    # a bare template sound id is audio, not an effect
    if low.endswith('sfx_id') and not low.endswith('_replace'):
        return None
    for kind, rules in FX_KIND_TOKENS.items():
        for tokens in rules:
            if not all(t in low for t in tokens):
                continue
            if kind == 'muzzle' and len(tokens) == 1 and tokens[0] == 'fire':
                continue
            return kind
    return None




def _fx_donor_values():
    """field -> most common real value across the whole table."""
    out = {}
    for kind, fields in (_fx_pools or {}).items():
        for field, values in fields.items():
            try:
                out[field] = max(values.items(), key=lambda kv: kv[1])[0]
            except Exception:
                continue
    return out


def _fx_row(module_name, skin_id):
    try:
        mod = sys.modules.get(module_name) or _import_module(module_name)
    except Exception:
        return None
    data = getattr(mod, 'data', None)
    if data is None:
        return None
    try:
        return _data_get(data, skin_id, None)
    except Exception:
        return None




def _fx_mirror_case(case, skin_id):
    """Step 2 - runs AFTER the case exists. This is the actual gap: the
    skin row already holds real tracer / hit / model ids, they were simply
    never copied onto the weapon case the runtime reads during a shot."""
    if case is None or not skin_id:
        return []
    row = None
    for module_name in FX_SOURCE_MODULES:
        row = _fx_row(module_name, skin_id)
        if row is not None:
            break
    if row is None:
        return []
    names = list(FX_ALWAYS_MIRROR)
    try:
        for field, value in _data_items(row):
            if not _fx_value_ok(value):
                continue
            if field in names:
                continue
            if _fx_classify(field) is not None:
                names.append(str(field))
    except Exception:
        pass
    mirrored = []
    for field in names:
        try:
            value = _proto_get(row, field, None)
            if not _fx_value_ok(value):
                continue
            _set_case_attr(case, field, value)
            mirrored.append(field)
        except Exception:
            continue
    # the same unconditional flags the kill fix sets
    try:
        _set_case_attr(case, 'show_guise_bullet_trace', True)
        _set_case_attr(case, 'show_guise_hit_effect', True)
        _set_case_attr(case, 'show_hit_effect', True)
    except Exception:
        pass
    key = (skin_id, len(mirrored))
    if key not in _fx_applied:
        _fx_applied.add(key)
        _plog('[FX] mirror skin=%s fields=%d %r'
              % (skin_id, len(mirrored), mirrored[:14]))
    return mirrored


_FX_HEALTH_FIELDS = (
    'fps_tracer_bullet_id', 'tps_tracer_bullet_id',
    'fps_adstracer_bullet_id', 'skin_hit_object_effect_id',
    'kill_tip_icon_replace',
)
_fx_health = [None]
_fx_last_force = [0.0]
_fx_drift_reported = set()


def _fx_case_state(case, skin_id):
    """Cheap snapshot of the fields the runtime reads. Used to catch the
    game wiping our values, which is the 'works / stops / works' flicker."""
    if case is None or not skin_id:
        return None
    parts = []
    for field in _FX_HEALTH_FIELDS:
        try:
            parts.append(_safe_int(getattr(case, field, None), 0) or str(getattr(case, field, '') or ''))
        except Exception:
            parts.append('')
    return (id(case), skin_id, tuple(parts))


def _fx_state_is_healthy(skin_id):
    """True when the current case still carries the values we set.

    Conservative on purpose: if we cannot observe the avatar or the case,
    it reports healthy, so the pump never re-applies in a loop. Only a
    case we actually seeded and can still see may report drift.
    """
    state = _fx_health[0]
    if state is None:
        return True                      # nothing observed yet
    if state[1] != skin_id:
        return False                     # different skin -> must (re)apply
    try:
        ca = _local_combat_avatar()
    except Exception:
        ca = None
    if ca is None:
        return True
    try:
        cases = _current_weapon_cases(ca)
    except Exception:
        cases = []
    if not cases:
        return True
    seen = False
    for case in cases:
        current = _fx_case_state(case, skin_id)
        if current is None:
            continue
        if current[0] == state[0]:        # this is the case we seeded
            seen = True
            if current[2] != state[2]:
                if skin_id not in _fx_drift_reported:
                    _fx_drift_reported.add(skin_id)
                    _plog('[FX] drift skin=%s -> re-applying (game wiped the '
                          'fields we set)' % (skin_id,))
                return False
    if not seen:
        if skin_id not in _fx_drift_reported:
            _fx_drift_reported.add(skin_id)
            _plog('[FX] drift skin=%s -> case re-created, re-applying' % (skin_id,))
        return False
    return True


def _fx_remember_state(case, skin_id):
    try:
        _fx_health[0] = _fx_case_state(case, skin_id)
    except Exception:
        pass


def _fx_send_stats():
    try:
        _fx_build_pools()
        lines = ['BEGIN\n']
        for kind in ('tracer', 'muzzle', 'broadcast'):
            fields = _fx_pools.get(kind) or {}
            parts = []
            for field in sorted(fields):
                try:
                    best = max(fields[field].items(), key=lambda kv: kv[1])
                    parts.append('%s=%r' % (field, best[0]))
                except Exception:
                    continue
            lines.append('F|%s|%d|%s\n' % (kind, len(fields), ';'.join(parts[:6])))
        lines.append('END\n')
        _write_udp_chunked(_write_udp_fx, ''.join(lines))
    except Exception as e:
        _plog('[FX] stats error=%r' % (e,))


_fx_sock = None


def _write_udp_fx(data):
    global _fx_sock
    try:
        if _fx_sock is None:
            _fx_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            _fx_sock.setblocking(False)
        if isinstance(data, str):
            data = data.encode('utf-8')
        _fx_sock.sendto(data, ("127.0.0.1", UDP_FX_PORT))
    except Exception:
        _fx_sock = None


# ============================================================
# ESP + AIMBOT (restored in v2.5 from the original payload)
# Python runs on the game thread via Space.AddSpacePostTick.
# ESP entities are sent as JSON on UDP 50001 to sync_entities.h;
# Aimbot rotates the real FPS camera placer (client-side only).
# ============================================================



def _game_genv():
    candidates = []
    try:
        candidates.append(globals().get('genv'))
    except Exception:
        pass
    try:
        candidates.append(sys.modules.get('genv'))
    except Exception:
        pass
    try:
        import builtins
        candidates.append(getattr(builtins, 'genv', None))
    except Exception:
        pass
    try:
        raw_builtins = globals().get('__builtins__')
        if isinstance(raw_builtins, dict):
            candidates.append(raw_builtins.get('genv'))
        elif raw_builtins is not None:
            candidates.append(getattr(raw_builtins, 'genv', None))
    except Exception:
        pass
    for candidate in candidates:
        if candidate is not None:
            return candidate
    try:
        return __import__('genv')
    except Exception:
        return None


def _local_combat_avatar():
    genv_obj = _game_genv()
    try:
        avatar = getattr(genv_obj, 'avatar', None)
        if avatar is not None:
            return getattr(avatar, 'combat_avatar', None)
    except Exception:
        pass
    return None



def Distance(a, b):
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    dz = b[2] - a[2]
    return (dx * dx + dy * dy + dz * dz) ** 0.5










def on_space_tick(dtime):
    # v8.12: the v8.11 exec-skin call that lived here NEVER RAN -
    # on_space_tick is dead code in this SRC (defined, never
    # registered; see the ESP tick block below). The live call site is
    # _esp_aim_tick, which the game runs via AddSpacePostTick.
    try:
        install_fx = globals().get('_install_effect_util_hooks')
        if callable(install_fx):
            install_fx()
        apply_fx = globals().get('_apply_current_weapon_skin_effects')
        if callable(apply_fx):
            apply_fx('space_tick')
    except Exception:
        pass
    try:
        process_equip = globals().get('_process_equip_nonces')
        if callable(process_equip):
            process_equip('space_tick')
    except Exception:
        pass
    try:
        refresh_hero = globals().get('_refresh_hero_if_selection_changed')
        if callable(refresh_hero):
            refresh_hero('space_tick')
    except Exception:
        pass
    try:
        _late_tick = globals().get('_late_enrich_tick')
        _enrich = globals().get('_enrich_weapon_names_late')
        _count_cjk = globals().get('_count_cjk_weapon_names')
        if _late_tick is not None and callable(_enrich) and callable(_count_cjk):
            _late_tick[0] += 1
            if (_late_tick[0] % 300) == 0 and _count_cjk() > 0:
                _enrich('space_tick', allow_gunskinutil=True)
    except Exception:
        pass




# ============================================================
# DIAGNOSTICS - one-shot evidence dump for anything SRC alone
# could not confirm. Read it after first run and adjust if a
# line says MISSING / args[4] does not look like a skin/guise.
# ============================================================
def _sig(obj):
    try:
        return str(inspect.signature(obj))
    except Exception as e:
        return "<no signature: %r>" % (e,)

def _run_diag(tag):
    try:
        # v7.30R13: this runs at boot ("run1") BEFORE _debug_log_on has
        # been defined further down the file - the forward reference
        # raised NameError and the skins boot diag silently never ran
        # ("[DIAG] error NameError" in the R12 device log).
        _dbg_gate = globals().get('_debug_log_on')
        if _dbg_gate is not None and not _dbg_gate():
            return
        lines = []
        lines.append("==== SKINS PAYLOAD DIAG %s py=%s ====" % (tag, sys.version.split()[0]))
        try:
            lines.append("WEP weapons=%d skins=%d" % (len(WEP), len(WEP_SKIN_INFO)))
        except Exception as e:
            lines.append("counts error %r" % (e,))
        targets = []
        try: targets.append(('EquipCaseFactory', EquipCaseFactory, ['Create']))
        except Exception: pass
        try: targets.append(('Doll', Doll, ['AddWeaponForDoll', 'AddWeaponByEquipId', 'ChangeWeaponSkinId', 'GetModelUnitID', 'GetModelComponentList', 'ShowHeroSkinModel', 'ShowDisplayModel', 'GetActualSkinItemId']))
        except Exception: pass
        try: targets.append(('HallShowModel', HallShowModel, ['Load', 'Reload', 'ClearHeroSkinInfo', 'CueChangeHeroSkin', 'ReloadHeroSkinPrimitivesAndEffects']))
        except Exception: pass
        for modname, clsname, meths, extra in (
            ('gclient.framework.entities.avatar', 'PlayerAvatar', ['GetHeroSkinProto', 'GetCurArmSkinItemId', 'GetActualArmSkinItemId', 'GetCurArmHeroSkinProto', 'GetActualArmHeroSkinProto'], True),
            ('gclient.gamesystem.entities.avatarmembers.cimp_hero', 'PlayerAvatarMember', ['GetHeroSkinProto', 'GetCurArmSkinItemId', 'GetActualArmSkinItemId', 'GetCurArmHeroSkinProto', 'GetActualArmHeroSkinProto'], False),
            ('gclient.gameplay.logic_base.entities.combat_avatar', 'CombatAvatar', ['GetHeroSkinProto'], True),
            ('gclient.gameplay.logic_base.entities.combat_avatar', 'PlayerCombatAvatar', ['GetHeroSkinProto'], True),
            ('gclient.gameplay.logic_base.entities.combat_avatar', 'PlayerCombatAvatar', ['on_enter_space'], False),
            ('gclient.gameplay.logic_base.models.avatar_model', 'AvatarModel', ['PlaySkinDeadAnimAndEffect', 'PlaySkinDeadEffect'], False),
            ('gclient.gameplay.uicomponents.hud_killrecord_comp', 'HudKillRecordCompV2', ['PushKillRecord'], False),
            ('gclient.gameplay.logic_base.equips.weapon_case', 'WeaponCase', ['ChangeWeaponSkin', 'ChangeWeaponGuise', 'ChangeWeaponOpticReticle', 'InitGuiseIllusion', 'WeaponBodyIllusion', 'RefreshIllusionEffect', 'ShowWeaponAdsSfxVisible', 'ShowWeaponBodyEffectVisible', 'LoadModelSkin', 'GetSkinOpticIdByOpticItemId', 'PostprocessPerformance'], False),
            ('gclient.gameplay.logic_base.equips.weapon_case', 'WeaponCaseBase', ['ChangeWeaponSkin', 'ChangeWeaponGuise', 'LoadModelSkin'], False),
        ):
            try:
                mod = __import__(modname, fromlist=[clsname])
                cls = getattr(mod, clsname, None)
                if cls is None:
                    lines.append("%s: class not found in %s" % (clsname, modname))
                    continue
                targets.append((clsname, cls, meths))
                if extra:
                    desc = cls.__dict__.get('hero_skin_proto')
                    lines.append("%s.hero_skin_proto own descriptor: %s" % (clsname, type(desc).__name__ if desc is not None else "NONE (inherited?)"))
                    lines.append("%s MRO: %s" % (clsname, [c.__name__ for c in cls.__mro__[:5]]))
            except Exception as e:
                lines.append("%s import error: %r" % (clsname, e))
        for cname, cls, meths in targets:
            for m in meths:
                fn = getattr(cls, m, None)
                own = m in getattr(cls, '__dict__', {})
                lines.append("%s.%s present=%s own=%s sig=%s" % (cname, m, fn is not None, own, _sig(fn) if fn else "-"))
        try:
            raw = EquipCaseFactory.__dict__.get('Create')
            lines.append("EquipCaseFactory.Create raw type: %s" % (type(raw).__name__,))
        except Exception as e:
            lines.append("Create raw check error %r" % (e,))
        try:
            w = globals().get('WEP', {})
            h = globals().get('HERO', {})
            lines.append("WEP sample: %r" % (dict(list(w.items())[:3]),))
            lines.append("HERO sample: %r" % (dict(list(h.items())[:3]),))
        except Exception:
            pass

        # v2.6 bounded probes: exact field evidence for English names
        # and weapon tracer/hit/scope/kill paths if anything remains.
        try:
            def _probe_scalar_fields(record, limit=36):
                fields = {}
                for _k, _v in _data_items(record)[:80]:
                    if isinstance(_v, (str, int, float, bool)) or _v is None:
                        fields[str(_k)] = _v
                    if len(fields) >= limit:
                        break
                return fields
            _probe_skin_id = None
            for _equip_id in list(WEP.keys()):
                _selected = _get_forced_skin(_equip_id)
                if _selected:
                    _probe_skin_id = _selected
                    break
            if not _probe_skin_id:
                for _sid, _info in WEP_SKIN_INFO.items():
                    if _contains_cjk(_display_text(_info.get('name'), '')):
                        _probe_skin_id = _sid
                        break
            if _probe_skin_id:
                _probe_info = WEP_SKIN_INFO.get(_probe_skin_id) or {}
                lines.append('[WEAPONFX-PROBE] skin=%s item=%s info=%r' % (
                    _probe_skin_id,
                    SKIN_TO_ITEM.get(_probe_skin_id) or _probe_info.get('lobby_item_id'),
                    {k: v for k, v in list(_probe_info.items())[:24]}))
                for _modname in ('gclient.data.gun_skin_template_data', 'gclient.data.gun_skin_template_base_data', 'gclient.data.lobby_item_data'):
                    try:
                        _mod = _import_module(_modname)
                        _record = _data_get(getattr(_mod, 'data', None), _probe_skin_id, None)
                        lines.append('[WEAPONFX-PROBE] %s[%s]=%r' % (_modname, _probe_skin_id, _probe_scalar_fields(_record)))
                    except Exception as _e:
                        lines.append('[WEAPONFX-PROBE] %s error=%r' % (_modname, _e))
                _mapped_item = SKIN_TO_ITEM.get(_probe_skin_id) or _probe_info.get('lobby_item_id')
                if _mapped_item and _mapped_item != _probe_skin_id:
                    try:
                        _lid_mod = _import_module('gclient.data.lobby_item_data')
                        _record = _data_get(getattr(_lid_mod, 'data', None), _mapped_item, None)
                        lines.append('[WEAPONFX-PROBE] lobby mapped item=%s fields=%r' % (_mapped_item, _probe_scalar_fields(_record)))
                    except Exception:
                        pass
        except Exception as _e:
            lines.append('[WEAPONFX-PROBE] error=%r' % (_e,))
        try:
            _lang_mod = _import_module('gclient.lang')
            _lang_attrs = []
            for _name in sorted(dir(_lang_mod))[:100]:
                try:
                    _value = getattr(_lang_mod, _name, None)
                    _lang_attrs.append('%s:%s%s' % (_name, type(_value).__name__, '()' if callable(_value) else ''))
                except Exception:
                    pass
            lines.append('[LANG-PROBE] gclient.lang attrs=%r' % (_lang_attrs,))
            for _modname in ('gclient.data.string_message_data', 'gclient.data.text_message_data'):
                try:
                    _mod = _import_module(_modname)
                    _items = _data_items(getattr(_mod, 'data', None))[:2]
                    lines.append('[LANG-PROBE] %s data_type=%s sample=%r' % (_modname, type(getattr(_mod, 'data', None)).__name__, _items))
                except Exception as _e:
                    lines.append('[LANG-PROBE] %s error=%r' % (_modname, _e))
        except Exception as _e:
            lines.append('[LANG-PROBE] error=%r' % (_e,))
        try:
            _eu = _import_module('gshare.effect_util')
            for _fname in ('PlayBallisticEffect', 'WrapperHitEffectResult', 'PlayHitEffect'):
                _fn = getattr(_eu, _fname, None)
                lines.append('[WEAPONFX-PROBE] effect_util.%s present=%s treacky=%s sig=%s' % (_fname, _fn is not None, bool(getattr(_fn, '_treacky_weaponfx', False)), _sig(_fn) if _fn else '-'))
        except Exception as _e:
            lines.append('[WEAPONFX-PROBE] effect_util error=%r' % (_e,))

        lines.append("sync_attrs keys=%d bSkinHack=%r" % (
            len(sync_attrs), sync_attrs.get('bSkinHack')))
        _plog("\n".join(lines))
    except Exception as e:
        _plog("[DIAG] error %r" % (e,))

_run_diag("run1")

def _diag_later():
    time.sleep(30)
    _run_diag("run2-after-30s")

if not _ALREADY_LOADED:
    threading.Thread(target=_diag_later, daemon=True).start()

# ============================================================
# ESP NEEDS A RUNNING TICK.
# In this SRC on_space_tick() is DEFINED but never registered - the only
# occurrence of "AddSpacePostTick" in the file is inside a comment, and
# on_enter_space appears only in the diagnostics probe list. So this block
# registers the tick for ESP/Aimbot. It deliberately does NOT change what
# on_space_tick does for skins - the skin passes in it behave exactly as
# they did before (which, in this SRC, means they only ever ran from the
# Doll hooks).
# ============================================================
_space_tick_spaces = []
_space_tick_last_attempt = [0.0]


def wrap_space_post_tick():
    """v8.14: the registration-time heal (v8.13) still lost the race -
    the v8.13 device log crashed 3x, each right AFTER '[ESP-TICK]
    registered', because the post-tick that reads space_tick_pending
    can run on a Space instance we never saw. Wrapping
    Space.OnSpacePostTick itself heals EVERY instance at the top of
    EVERY post-tick, before line 1832 can read the attribute."""
    try:
        _spc = _import_module('gclient.framework.entities.space')
        _Space = getattr(_spc, 'Space', None)
        if _Space is None:
            return False
        _prev = _Space.__dict__.get('OnSpacePostTick')
        if not callable(_prev) or getattr(_prev, '_treacky_v814',
                                          False):
            return False

        def _OnSpacePostTick(self, *a, **k):
            try:
                if not hasattr(self, 'space_tick_pending'):
                    self.space_tick_pending = []
                    _plog('[V814] healed missing '
                          'Space.space_tick_pending (post-tick wrap)')
                # v8.15: the v8.14 device healed space_tick_pending
                # and then crashed 3x on the NEXT attr the game reads
                # at space.py:1840 - space_tickers. Heal every attr
                # the post-tick path touches, not just the first.
                if not hasattr(self, 'space_tickers'):
                    self.space_tickers = []
                    _plog('[V815] healed missing '
                          'Space.space_tickers (post-tick wrap)')
            except Exception:
                pass
            return _prev(self, *a, **k)
        _OnSpacePostTick._treacky_v814 = True
        _OnSpacePostTick.__name__ = 'OnSpacePostTick'
        _Space.OnSpacePostTick = _OnSpacePostTick
        _plog('[V814] Space.OnSpacePostTick wrap installed')
        return True
    except Exception as _e:
        try:
            _plog('[V814] space post-tick wrap failed: %r' % (_e,))
        except Exception:
            pass
        return False


try:
    wrap_space_post_tick()
except Exception:
    pass


def _game_space():
    try:
        sp = getattr(Space, '_instance', None)
        if sp is not None:
            return sp
    except Exception:
        pass
    try:
        g = _game_genv()
        sp = getattr(g, 'space', None)
        if sp is not None:
            return sp
    except Exception:
        pass
    return None


# ================================================================
# v3.0 ADDITIONS  -  all new functions, no pristine code touched
# ================================================================

_v30_name_overrides = [None]
name_pass_done = [False]
name_last = [0.0]
_v30_sanitized = [False]
aim_hold = [0.0]

def _v30_float(value, default):
    try:
        f = float(value)
        return f if f == f and abs(f) < 1e9 else default
    except Exception:
        return default

_NAME_OVERRIDE_PATH = '/storage/emulated/0/Nexora/name_overrides.json'
_CJK_REPORT_PATH    = '/storage/emulated/0/Nexora/weapon_names_cjk.txt'


def load_name_overrides():
    """Optional CJK->English map. Edit the JSON, restart the game, done.
    Shape: {"\u9ad8\u7ea7\u6b65\u67aa": "Advanced Rifle", ...}"""
    try:
        with open(_NAME_OVERRIDE_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict):
            _plog('[NAME] overrides loaded: %d entries' % (len(data),))
            return data
    except Exception:
        pass
    return {}


def translate_names():
    """Turn CJK weapon + weapon-skin names into English.

    Returns (fixed, still_cjk). The caller keeps retrying while still_cjk
    is above zero, because the game's language tables are not necessarily
    loaded the first time this runs - that is why v3.0 appeared to do
    nothing: it gave up after a single pass.

    Resolution order per string, first hit wins:
      1. /Nexora/name_overrides.json      (yours, vetted)
      2. gclient.lang via _lang_translate
      3. the game message tables via _display_text
      4. leave it, and record it in weapon_names_cjk.txt
    Nothing here reorders WEP or WEP_SKIN_INFO, so saved menu indices hold.
    """
    book = globals()
    contains_cjk = book.get('_contains_cjk')
    if not callable(contains_cjk):
        return 0, 0
    if _v30_name_overrides[0] is None:
        _v30_name_overrides[0] = load_name_overrides()
    overrides = _v30_name_overrides[0] or {}
    lang_translate = book.get('_lang_translate')
    display_text = book.get('_display_text')
    reset_caches = book.get('_reset_lang_caches_if_empty')
    if callable(reset_caches):
        try:
            reset_caches()
        except Exception:
            pass

    def resolve(text):
        if not text:
            return None
        text = str(text)
        if text in overrides:
            return overrides[text]
        cand = None
        if callable(lang_translate):
            try:
                cand = lang_translate(text)
            except Exception:
                cand = None
        if (not cand or contains_cjk(cand)) and callable(display_text):
            try:
                cand = display_text(text, '')
            except Exception:
                pass
        if cand and not contains_cjk(cand) and cand != text:
            return cand
        return None

    fixed = 0
    pending = []

    # weapon names first, so skin fallbacks can use the English weapon name
    wep_names = book.get('WEP_NAMES')
    if isinstance(wep_names, dict):
        for equip_id, name in list(wep_names.items()):
            if not name or not contains_cjk(name):
                continue
            english = resolve(name)
            if english:
                wep_names[equip_id] = english
                fixed += 1
            else:
                pending.append(('WEP_NAMES', equip_id, str(name)))

    info = book.get('WEP_SKIN_INFO')
    if isinstance(info, dict):
        for skin_id, entry in list(info.items()):
            if not isinstance(entry, dict):
                continue
            name = entry.get('name')
            if not name or not contains_cjk(name):
                continue
            english = resolve(name)
            if english:
                entry['name'] = english
                fixed += 1
            else:
                pending.append(('SKIN', skin_id, str(name)))

    try:
        with open(_CJK_REPORT_PATH, 'w', encoding='utf-8') as f:
            f.write('# weapon / weapon-skin names still in CJK\n')
            f.write('# format: kind<TAB>id<TAB>name\n')
            f.write('# copy lines into name_overrides.json as  "CJK": "English"\n')
            f.write('# fixed this pass: %d   still CJK: %d\n' % (fixed, len(pending)))
            for kind, ident, name in pending:
                f.write('%s\t%s\t%s\n' % (kind, ident, name))
    except Exception:
        pass

    if fixed or pending:
        _plog('[NAME] translated=%d still_cjk=%d -> %s'
              % (fixed, len(pending), _CJK_REPORT_PATH))
    return fixed, len(pending)


def _fx_restore_effect_util_hooks():
    """Undo _install_effect_util_hooks().

    The installer stashes each untouched callable as
    `_treacky_orig_<name>` on gshare.effect_util and marks its wrapper with
    `_treacky_weaponfx`. Restoring means putting those originals back
    everywhere the wrapper was written, so OFF is bit-for-bit the original
    payload's behaviour.
    """
    try:
        effect_util = _import_module('gshare.effect_util')
    except Exception as e:
        _plog('[WEAPONFX] restore deferred error=%r' % (e,))
        return False
    names = ('PlayBallisticEffect', 'WrapperHitEffectResult',
             'PlayHitEffect', 'ConfigBallisticEffect')
    restored = []
    for name in names:
        orig = getattr(effect_util, '_treacky_orig_' + name, None)
        if orig is None:
            continue
        try:
            setattr(effect_util, name, orig)
            restored.append('gshare.effect_util.' + name)
        except Exception:
            pass
        try:
            for mod_name, mod in list(sys.modules.items()):
                if mod is None or mod is effect_util:
                    continue
                cur = getattr(mod, name, None)
                if cur is not None and getattr(cur, '_treacky_weaponfx', False):
                    setattr(mod, name, orig)
                    restored.append(str(mod_name) + '.' + name)
        except Exception:
            pass
    _weaponfx_effect_hooks_installed[0] = False
    _plog('[WEAPONFX] forced FX OFF - restored=%r' % (restored[:16],))
    return True


def _v31_weapon_fx_pump():
    """Install the effect hooks and keep the selected skin's effects on.

    Why this exists: in the SRC you sent, _install_effect_util_hooks() and
    _apply_current_weapon_skin_effects() have no caller anywhere - the
    whole weapon-FX pipeline is dead code. The gun model still swapped
    because that happens on a different path, which is exactly the
    symptom you described: the skin applies but only some of it works.
    Tracer colour, hit effect and kill effect all live behind those two
    functions, so nothing was ever installed or applied.

    Reload guard: while the weapon is reloading we do not force a re-apply,
    because rebuilding the weapon case mid-reload is what cuts the reload
    animation short. The normal throttled path is allowed through.
    """
    g = globals()
    now = time.time()
    try:
        _weaponfx_enforce('pump')
    except Exception:
        pass
    # Install is cheap once it succeeded, but while the import is failing it
    # retries the import. Cap it at once a second instead of every frame.
    forced = _fx_forced()
    if not forced and g.get('_weaponfx_effect_hooks_installed', [False])[0]:
        # v4.1: switch back to the untouched game behaviour at runtime.
        try:
            restorer = g.get('_fx_restore_effect_util_hooks')
            if callable(restorer):
                restorer()
            _plog('[WEAPONFX] forced FX OFF - original effect hooks restored')
        except Exception as e:
            _plog('[WEAPONFX] hook restore error: %r' % (e,))
        return
    if forced and not g.get('_weaponfx_effect_hooks_installed', [False])[0]:
        if (now - g.get('install_last', [0.0])[0]) >= 1.0:
            g['install_last'] = [now]
            try:
                install = g.get('_install_effect_util_hooks')
                if callable(install):
                    install()
            except Exception as e:
                _plog('[WEAPONFX] hook install error: %r' % (e,))

    # v5.0: report the FX donor scan once, purely as diagnostics.
    try:
        if not _fx_stats_pushed[0] and _fx_build_pools():
            _fx_stats_pushed[0] = True
            _fx_send_stats()
    except Exception as e:
        _plog('[FX] tick error: %r' % (e,))

    reloading = False
    try:
        get_local = g.get('_local_combat_avatar')
        ca = get_local() if callable(get_local) else None
        if ca is not None:
            for attr in ('is_reloading', 'is_reload', 'reloading', 'IsReloading'):
                v = getattr(ca, attr, None)
                if v:
                    reloading = True
                    break
            if not reloading:
                weapon = None
                try:
                    weapon = ca.GetCurWeapon()
                except Exception:
                    weapon = None
                if weapon is not None:
                    for attr in ('is_reloading', 'reloading'):
                        if getattr(weapon, attr, None):
                            reloading = True
                            break
    except Exception:
        reloading = False

    # The apply pass rebuilds weapon cases and walks the catalog, so it is
    # hard-capped to 4 Hz no matter what the internal throttle would allow,
    # and it is skipped entirely during a reload.
    if reloading:
        return reloading
    if (now - g.get('apply_last', [0.0])[0]) < 0.25:
        return reloading
    g['apply_last'] = [now]
    try:
        apply_fx = g.get('_apply_current_weapon_skin_effects')
        if callable(apply_fx):
            t0 = time.time()
            apply_fx('tick')
            dt = time.time() - t0
            if dt > 0.10 and (time.time() - g.get('apply_slow', [0.0])[0]) > 2.0:
                g['apply_slow'] = [time.time()]
                _plog('[WEAPONFX] apply pass took %.2fs' % (dt,))
    except Exception as e:
        _plog('[WEAPONFX] apply error: %r' % (e,))
    return reloading


AIM_LIMITS = (
    # v8.33: menu slider now reaches FOV 300 (user request) - the
    # clamp table follows the slider instead of silently pulling the
    # saved value back to 200 every frame.
    ("fAIM_Fov", 10.0, 300.0),
    ("fAIM_MaxDist", 10.0, 500.0),
    ("fAIM_SnapStrength", 0.5, 5.0),
    ("fAIM_BulletSpeed", 200.0, 1200.0),
)


def name_worker():
    """Name translation, off the game thread and self-limiting.

    Runs at most 10 passes, 8 s apart, and stops as soon as nothing is left
    in CJK. Everything here only edits display dicts; the pristine payload
    already does name enrichment from _send_skin_info_loop, so doing it on a
    worker thread is the same pattern, not a new risk.
    """
    runs = 0
    deadline = time.time() + 300.0
    while runs < 1 and time.time() < deadline:
        try:
            time.sleep(8.0)
            try:
                if _hero_scene_stable() == 'match':
                    # v2.95: never translate during a match - each pass
                    # holds the GIL 2-2.8s and stalls the game thread
                    # (the 'peak lag').  Wait for the lobby instead.
                    continue
            except Exception:
                pass
            runs += 1
            t0 = time.time()
            fixed, left = translate_names()
            dt = time.time() - t0
            _plog('[NAME] pass %d fixed=%d still_cjk=%d took=%.2fs'
                  % (runs, fixed, left, dt))
            if left == 0:
                _plog('[NAME] complete after %d pass(es)' % (runs,))
                return
        except Exception as e:
            _plog('[NAME] worker error: %r' % (e,))
    _plog('[NAME] stopped (bounded v2.95); unresolved names are listed in '
          'weapon_names_cjk.txt - send that file')


def clamp_aim():
    """Clamp the aim keys in place. Runs every frame on purpose.

    In v2.9 fAIM_Fov / fAIM_MaxDist / fAIM_SnapStrength were written by the
    menu but read by nobody, so an old saved value like FOV=300 sat inert
    in the config. v3.0 connects them, and a big FOV means AIMUpdate finds
    a "candidate" almost always and calls Rotate() every frame - the view
    stays stuck facing one side and your own turning is overwritten. The
    menu re-sends its value on every sync, so clamping once is not enough:
    this has to run before each use.
    """
    changed = []
    for key, lo, hi in AIM_LIMITS:
        try:
            cur = float(sync_attrs.get(key))
        except Exception:
            continue
        fixed = min(max(cur, lo), hi)
        if abs(fixed - cur) > 1e-6:
            sync_attrs[key] = fixed
            changed.append('%s %.1f->%.1f' % (key, cur, fixed))
    try:
        bone = _safe_int(sync_attrs.get('iAIM_TargetBone', 5), 5)
    except Exception:
        bone = 5
    if bone < 0 or bone > 5:
        sync_attrs['iAIM_TargetBone'] = 5
        changed.append('iAIM_TargetBone %r->5' % (bone,))
    return changed


def sanitize_sync():
    """One-shot: clamp, then say so in the log exactly once."""
    changed = clamp_aim()
    if changed:
        _plog('[AIM] clamped out-of-range aim settings: %s' % (', '.join(changed),))
    else:
        _plog('[AIM] aim settings within safe range')
    _v30_sanitized[0] = True
    return changed


def aim_gate_open():
    """True only when it is safe to let the aimbot drive the camera.

    bAIM_SafeMode (default ON) additionally requires the player to be
    aiming or firing. Outside those windows AIMUpdate is not called at
    all, so the camera is never held hostage and you can always rotate.
    """
    if not sync_attrs.get('bAIM_SafeMode', True):
        return True
    try:
        local = _local_combat_avatar()
    except Exception:
        local = None
    if local is None:
        return False
    try:
        if not getattr(local, 'is_alive', False):
            return False
    except Exception:
        pass
    try:
        shooting = bool(getattr(local, 'is_shooting', False))
        ads = bool(getattr(local, 'is_ads', False) or getattr(local, 'is_real_ads', False))
    except Exception:
        return True
    return bool(shooting or ads)



# ---------------- v7.21: bullet trace / kill broadcast diagnostics -------------
# The user report: everything on the weapon skin works EXCEPT the bullet
# trace and the kill broadcast. Both are read by engine code we have not
# located yet, so this block records the facts at the exact moments they
# matter: every trigger pull dumps what the live weapon case holds
# (tracer ids, from-tip flag, kill fields), and a kill-counter watch dumps
# what the skin row promises for the broadcast. Plus a one-shot map of
# every module/class in the game that owns bullets, tracers or kill feeds.
_shots_state = {'was': False, 'count': 0, 'next_dump': 0.0}
_kill_state = {'attrs': None, 'vals': {}, 'events': 0, 'next_dump': 0.0}
_bullet_probe_done = [False]
_bullet_probe_started = [False]  # v7.22: start guard, separate from done
_bullet_probe_scene = ['']       # v7.23: last scene the probe ran for
_bullet_probe_re_at = [0.0]      # v7.23: scheduled match-entry re-run


def _shots_case_fields(case):
    """The tracer/kill fields the ballistic code should be reading."""
    out = {}
    for _k in ('_treacky_skin_template_id', 'guise_template_id',
               'skin_template_id', 'fps_tracer_bullet_id',
               'fps_adstracer_bullet_id', 'fps_simple_tracer_bullet_id',
               'tps_tracer_bullet_id', 'fps_trace_bullet_from_tip',
               'show_guise_bullet_trace', 'upgrade_level',
               'skin_optic_id', 'kill_mat', 'kill_tip_icon_replace'):
        try:
            _v = getattr(case, _k, None)
            if _v is not None:
                out[_k] = _v
        except Exception:
            continue
    return out


def _shots_dump(tag):
    """Bounded dump of every live weapon case's tracer state."""
    try:
        _rows = []
        for _item in list(_weaponfx_cases)[:6]:
            try:
                _ref = _item[0] if isinstance(_item, tuple) else _item
                _case = _ref() if callable(_ref) else _ref
            except Exception:
                _case = None
            if _case is None:
                continue
            _rows.append('%s' % (_shots_case_fields(_case),))
        _plog('[SHOTS] #%d %s cases=%d %s'
              % (_shots_state['count'], tag, len(_rows),
                 ' | '.join(_rows)[:700]))
    except Exception as e:
        _plog('[SHOTS] dump error=%r' % (e,))


def _shots_logger(now):
    """Per-frame: count trigger pulls, dump tracer state at fire time."""
    try:
        _le = _local_combat_avatar()
        if _le is None:
            return
        _shooting = bool(getattr(_le, 'is_shooting', False))
        if _shooting and not _shots_state['was']:
            _shots_state['count'] += 1
            _n = _shots_state['count']
            if _n <= 5 or _n % 50 == 0 or now >= _shots_state['next_dump']:
                _shots_state['next_dump'] = now + 20.0
                _shots_dump('fire')
        _shots_state['was'] = _shooting
    except Exception:
        pass
    try:
        _kill_watch(_le, now)
    except Exception:
        pass


def _kill_watch(local, now):
    """Watch the local avatar's kill counters; dump broadcast fields."""
    if _kill_state['attrs'] is None:
        # v7.22: v7.21's dir() filter caught METHODS (AddWrathSkillTimer...)
        # which never change value - the watcher saw nothing. Only real
        # int counters count.
        _cand = []
        for _a in dir(local):
            if 'kill' not in _a.lower() or _a.startswith('_'):
                continue
            try:
                _v = getattr(local, _a, None)
                if callable(_v) or not isinstance(_v, (int, float)):
                    continue
                _cand.append(_a)
            except Exception:
                continue
            if len(_cand) >= 8:
                break
        _kill_state['attrs'] = _cand or []
        _plog('[KILL] watcher attrs=%r (empty = counters live elsewhere; '
              'the PushKillRecord hook below is the real kill event)' % (_cand,))
    fired = []
    for _a in _kill_state['attrs']:
        try:
            _v = _safe_int(getattr(local, _a, None), -1)
        except Exception:
            continue
        if _v < 0:
            continue
        _prev = _kill_state['vals'].get(_a, _v)
        _kill_state['vals'][_a] = _v
        if _v > _prev:
            fired.append('%s %d->%d' % (_a, _prev, _v))
    if not fired:
        return
    _kill_state['events'] += 1
    if _kill_state['events'] > 10 and _kill_state['events'] % 10 != 0:
        return
    _skin = None
    try:
        _wid = _safe_int(sync_attrs.get('iRecentWeapon', 0), 0)
        _skin = _get_forced_skin(_wid) if _wid else None
    except Exception:
        pass
    _plog('[KILL] #%d %s skin=%s (broadcast fields live on the case dump '
          'above - if the icon/effect is missing here, the feed reads '
          'server data, not the case)' % (_kill_state['events'],
                                          '+'.join(fired), _skin))


def _bullet_kill_probe():
    """Once: map every module/class owning bullets, tracers, kill feeds."""
    if _bullet_probe_done[0]:
        return
    _bullet_probe_done[0] = True
    out = []
    try:
        for _mn, _mod in list(sys.modules.items()):
            _low = _mn.lower()
            if not _mn.startswith(('gclient', 'gshare', 'engine')):
                continue
            if not any(_t in _low for _t in ('bullet', 'tracer', 'killfeed',
                                             'kill_broadcast', 'ballistic',
                                             'projectile', 'trajectory')):
                continue
            _clss = []
            for _cn in dir(_mod):
                _c = getattr(_mod, _cn, None)
                if not isinstance(_c, type):
                    continue
                _meths = [m for m in dir(_c)
                          if any(_t in m.lower()
                                 for _t in ('spawn', 'create', 'fire',
                                            'show', 'broadcast', 'add'))][:6]
                if _meths:
                    _clss.append('%s:%s' % (_cn, ','.join(_meths)))
            if _clss:
                out.append('%s -> %s' % (_mn, ' ; '.join(_clss)[:220]))
    except Exception as e:
        out.append('probe error=%r' % (e,))
    if out:
        _plog('[TRACER-PROBE] %s' % (' || '.join(out)[:1800],))
        _dlog('[TRACER-PROBE]\n  ' + '\n  '.join(out))
    else:
        _plog('[TRACER-PROBE] no bullet/tracer/killfeed modules loaded yet')


def _esp_aim_tick(dtime):
    """ESP/Aimbot per-frame tick, plus a stall watchdog. This is OUR function.

    It never calls on_space_tick(). In the SRC you sent, on_space_tick() is
    dead code: defined, never registered, and carrying the skin passes, a
    %300 warehouse/GunSkinUtil scan and the entry refresh. Registering it
    put that work on the game thread - that was a mistake in v2.9 and it
    is reverted here. Every skin function stays byte-identical and unreached.

    The watchdog is read-only. It never writes skin state; it only records
    how long the game thread was gone and how long EspUpdate took, so the
    2s freeze can be pinned to a specific loop instead of guessed at.
    """
    g = globals()
    try:
        # v6.5: this is the only guaranteed game-thread slot we own - drain
        # whatever a worker thread queued (emote replay, striker push).
        _ph24 = g.setdefault('_phase24', {})
        try:
            _t24 = time.time()
            _game_pump()
        except Exception:
            pass
        finally:
            _ph24['game_pump'] = time.time() - _t24
        try:
            if not _emote_live_cache['objs']:
                _emote_scan_step(600)      # sliced heap scan, never blocks
        except Exception:
            pass
        # v7.21: bullet-trace / kill-broadcast diagnostics (cheap per frame)
        now = time.time()
        try:
            if _V841PERF_AUTO_DIAGNOSTICS and _debug_log_on():
                _shots_logger(now)
        except Exception:
            pass
        prev = g.get('_esp_tick_prev')
        if prev is None:
            g['_esp_tick_prev'] = now
        else:
            gap = now - prev
            g['_esp_tick_prev'] = now
            # a healthy tick is a few ms. >400ms means the game thread was
            # blocked by something that is not us. v8.16: gaps >120 s
            # are the app being PAUSED/backgrounded (the 884.92 s
            # "stall" in the v8.15 log) - not a stall, no log spam.
            # v10.12.2-lagfix-r1: the `not _hero_in_match()` term meant
            # every stall INSIDE a match - the only place the user actually
            # feels lag - was measured and thrown away. The sky-r1 log has
            # 9 [STALL] lines, all 'EspUpdate took' from a hall/training
            # load, and not one game-thread-blocked report from the match
            # the user describes as laggy. Report it, tagged with the scene,
            # so the next log names the real culprit instead of us guessing.
            if (gap > 0.4 and gap < 120.0
                    and (now - g.get('_esp_stall_logged', 0.0)) > 1.0):
                g['_esp_stall_logged'] = now
                _match = _hero_in_match()
                cat = g.get('_weapon_catalog_ready')
                cat_ready = bool(cat[0]) if isinstance(cat, list) and cat else None
                try:
                    cjk = g.get('_count_cjk_weapon_names')
                    cjk_n = cjk() if callable(cjk) else None
                except Exception:
                    cjk_n = 'err'
                _ph24s = g.get('_phase24') or {}
                _slow24 = (','.join('%s=%.2f' % (_k24, _v24) for _k24, _v24
                                    in sorted(_ph24s.items())
                                    if _v24 >= 0.05) or '-')
                _plog('[STALL] game thread blocked %.2fs  scene=%s '
                      'catalog_ready=%s  cjk_names=%s slow=%s'
                      % (gap, 'match' if _match else 'hall', cat_ready,
                         cjk_n, _slow24))
        attrs = g.get('sync_attrs', {})
        want_esp = attrs.get('bESP', True) or (
            attrs.get('bAIM', False) and
            (attrs.get('bAIM_Lane', True) or attrs.get('bAIM_Dot', True)))
        if want_esp:
            fn = g.get('EspUpdate')
            if callable(fn):
                t0 = time.time()
                try:
                    fn()
                finally:
                    dt = time.time() - t0
                    g.setdefault('_phase24', {})['esp_update'] = dt
                    if dt > 0.05 and (time.time() - g.get('_esp_slow_logged', 0.0)) > 1.0:
                        g['_esp_slow_logged'] = time.time()
                        _plog('[STALL] EspUpdate took %.2fs (%d players)'
                              % (dt, len(g.get('current_players') or [])))
        # weapon FX: tracer / hit / kill effects (see _v31_weapon_fx_pump)
        try:
            _t24 = time.time()
            _v31_weapon_fx_pump()
        finally:
            _ph24['weaponfx_pump'] = time.time() - _t24

        if attrs.get('bAIM', False):
            if not g.get('_v30_sanitized', [False])[0]:
                sanitize_sync()
            else:
                clamp_aim()   # menu re-sends old values every sync
            # v3.0.1: never let the aimbot hold the camera outside an
            # aim/fire window - that was the "stuck on one side" report.
            if aim_gate_open():
                fn2 = g.get('AIMUpdate')
                if callable(fn2):
                    fn2()
                g['aim_hold'] = [now]
            else:
                held = g.get('aim_hold', [0.0])[0]
                if held and (now - held) > 1.5:
                    g['aim_hold'] = [0.0]
                    _plog('[AIM] released camera hold - no ADS/fire for 1.5s')

        # v8.12: the R6 exec-skin apply. THIS is the live per-tick
        # path (the game runs us via AddSpacePostTick; the v8.11 call
        # in on_space_tick never ran - dead code in this SRC). One
        # attempt per 2 s; the brakes inside make it ~free once worn.
        try:
            _now0 = time.time()
            if _now0 - exec_tick_at[0] >= 2.0:
                exec_tick_at[0] = _now0
                apply_exec_skin()
        except Exception:
            pass
        # v8.12: a crash mid-load can leave the Space without this
        # attr and the game's OnSpacePostTick then dies uncaught (the
        # v8.11 log). Default it so the tick chain survives; the game
        # overwrites it on its next pre-tick.
        try:
            _sp_obj = _game_space()
            if _sp_obj is not None \
                    and not hasattr(_sp_obj, 'space_tick_pending'):
                _sp_obj.space_tick_pending = []
                _plog('[V812] healed missing Space.space_tick_pending')
        except Exception:
            pass
        # 1. names -> English now runs in name_worker() on its own
        # thread. It is NOT called here: _lang_translate falls back to
        # walking module attributes per string, which is far too expensive
        # for the game thread. This was the 2 s freeze regression.
        # 2. Striker feature removed in v3.1
    except Exception:
        pass


def _ensure_space_tick_registered():
    try:
        now = time.time()
        if now - _space_tick_last_attempt[0] < 1.0:
            return False
        _space_tick_last_attempt[0] = now
        sp = _game_space()
        if sp is None:
            return False
        for old in _space_tick_spaces:
            try:
                if old() is sp:
                    return True
            except Exception:
                pass
        add = getattr(sp, 'AddSpacePostTick', None)
        if not callable(add):
            _plog('[ESP-TICK] %s has no AddSpacePostTick' % (type(sp).__name__,))
            return False
        add(_esp_aim_tick)
        _space_tick_spaces.append(weakref.ref(sp))
        del _space_tick_spaces[:-4]
        # v8.13: the v8.12 heal lived inside the tick callback - too
        # late, OnSpacePostTick reads space_tick_pending BEFORE it
        # calls us (4x crashes in the v8.12 log, all right after
        # registration). Heal NOW, before the first post-tick runs.
        try:
            if not hasattr(sp, 'space_tick_pending'):
                sp.space_tick_pending = []
                _plog('[V813] healed missing Space.space_tick_pending '
                      '(at registration)')
        except Exception:
            pass
        _plog('[ESP-TICK] registered on %r' % (type(sp).__name__,))
        return True
    except Exception as e:
        _plog('[ESP-TICK] failed: %r' % (e,))
        return False


# #======================================================================
# //  ESP.PY
# //
# //  This file is for: ESP + AIMBOT: the entity feed (UDP 50001 to C++), the ESP hooks, the aim settings, the ESP diagnostics.
# //
# //  Part of the split TREACKY BS payload (v2.112).  The runtime
# //  file payload/skins_payload.py is GENERATED: run
# //  tools/build_payload.py after editing these modules.
# #======================================================================
