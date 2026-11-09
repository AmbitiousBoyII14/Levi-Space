# ============================================================
# MELEE.PY (payload feature module)
# PROVIDES: melee_visual_player, melee_visual_get, melee_visual_remove, melee_template, melee_combat_item_id, melee_visual_dlc_ready, melee_visual_sync_current_case, melee_active_visual, melee_kill_record_fields, melee_kill_avatar_case, melee_kill_avatar_factory, melee_visual_refresh, melee_visual_case_supported, melee_visual_case_matches, ... +36 more | COMBAT_VISUALS, COMBAT_VISUAL_LIMIT, WEAPON_VISUAL_TICK, PLAYPAL_COMBAT_TICK
# REQUIRES: shared namespace (config/names/main/game_api/catalog);
#           game modules imported inline, verified against the dumps.
# Feature module - see REWRITE_PLAN.md S1.
# ============================================================
"""Genuine-GUID melee visual chain: melee rows 33/84/86/89/97/107/141 (dual/standalone/merged), identity preservation, native melee registration."""

# #======================================================================
# //  MELEE.PY
# //
# //  This file is for: MELEE VISUAL: the genuine-GUID melee visual chain (the clone, the case repair, the dual/replay case targets, the DLC readiness).
# //
# //  Part of the split TREACKY BS payload (v2.112).  The runtime
# //  file payload/skins_payload.py is GENERATED: run
# //  tools/build_payload.py after editing these modules.
# #======================================================================
def melee_visual_player():
    try:
        helper = globals().get('_game_genv')
        root = helper() if callable(helper) else globals().get('genv')
        return root, getattr(root, 'player', None)
    except Exception:
        return None, None


def melee_visual_get(backpack, guid):
    try:
        getter = getattr(backpack, 'Get', None)
        if callable(getter):
            return getter(guid)
        getter = getattr(backpack, 'get', None)
        if callable(getter):
            return getter(guid)
    except Exception:
        pass
    return None


def melee_visual_remove(backpack, guid):
    """Remove by GUID and require the official identity-returning contract."""
    try:
        item = melee_visual_get(backpack, guid)
        if item is None:
            return False
        return backpack.Remove(guid) is item
    except Exception:
        return False


def melee_template(item, row, kind, item_id):
    """Read the native item property, then its authoritative lobby row."""
    value = _v109_int(_v109_field(item, kind + '_id', 0), 0)
    if value:
        return value
    nested = _v109_field(row, kind, None)
    value = _v109_int(nested, 0) or _v109_int(
        _v109_field(nested, 'template_id', 0), 0)
    if value or kind != 'guise':
        return value
    try:
        catalog_fn = globals().get('_v841m2_catalog')
        catalog = catalog_fn() if callable(catalog_fn) else None
        return _v109_int(
            (catalog.get('item_to_template') or {}).get(item_id), 0)
    except Exception:
        return 0


def melee_combat_item_id(equip_id):
    """Resolve the combat item row whose official equip_id matches exactly."""
    equip_id = _v109_int(equip_id, 0)
    if not equip_id:
        return 0
    cached = MELEE_COMBAT_ID_CACHE.get(equip_id)
    if cached:
        return cached
    module = sys.modules.get('gclient.data.combat_item_data')
    data = getattr(module, 'data', None) if module is not None else None
    if data is None:
        return 0
    try:
        row = _v109_field(data, equip_id, None)
        if row is None:
            row = _v109_field(data, str(equip_id), None)
        if (row is not None and _v109_int(
                _v109_field(row, 'equip_id', 0), 0) == equip_id):
            MELEE_COMBAT_ID_CACHE[equip_id] = equip_id
            return equip_id
        items = list(data.items())[:32768]
    except Exception:
        return 0
    for candidate, row in items:
        if _v109_int(_v109_field(row, 'equip_id', 0), 0) != equip_id:
            continue
        candidate = _v109_int(candidate, 0)
        if candidate:
            MELEE_COMBAT_ID_CACHE[equip_id] = candidate
            return candidate
    return 0


def melee_visual_dlc_ready(root, item_id, guise_id):
    """Use WeaponCaseBase's own readiness check; never fabricate readiness."""
    if not guise_id:
        return True
    manager = getattr(root, 'dlc_manager', None) if root is not None else None
    init = getattr(manager, 'InitGuiseDlcId', None)
    check = getattr(manager, 'CheckDlcExists', None)
    if not callable(init) or not callable(check):
        # v2.102: MeleeCase usually has no dlc_manager - probe the
        # module DownloadableContentManager before trusting readiness.
        try:
            _mgr2 = dlcmgr()
        except Exception:
            _mgr2 = None
        init = getattr(_mgr2, 'InitGuiseDlcId', None)
        check = getattr(_mgr2, 'CheckDlcExists', None)
    if not callable(init) or not callable(check):
        # v2.102: never fabricate silent readiness - put the per-item
        # download request out (dedupes; match-skip logs) and let the
        # visual proceed; the game pump re-applies once it lands.
        try:
            try_dlc_download(item_id, [])
        except Exception:
            pass
        return True
    try:
        dlc_id = init(guise_id)
        ready = check(dlc_id)
    except Exception as exc:
        _v109_log(('visual-dlc-error', item_id, repr(exc)),
                  'native melee visual DLC preflight item=%d error=%r'
                  % (item_id, exc), 1)
        return False
    if ready:
        return True
    try:
        try_dlc_download(item_id, [])
    except Exception:
        pass
    _v109_log(('visual-dlc-wait', item_id, guise_id, repr(dlc_id)),
              'native melee visual waiting for authentic DLC item=%d '
              'guise=%d dlc=%r' % (item_id, guise_id, dlc_id), 2)
    return False


def melee_visual_sync_current_case(player):
    """Read current-case identity without forcing a native weapon raise.

    Same-GUID cosmetic changes keep the existing current case.  A readback is
    sufficient; RaiseCurWeaponByCurWeaponGuid is not a visual-refresh API.
    """
    try:
        hand = getattr(player, 'hand_model', None)
        cases = getattr(hand, 'weapon_dict', None) if hand is not None else None
        if cases is None:
            return False
        guid = (getattr(player, 'cur_spec_weapon_guid', '')
                or getattr(player, 'cur_weapon_guid', ''))
        current = cases.get(guid) if guid else None
        return current is not None and getattr(hand, 'weapon_case', None) is current
    except Exception:
        return False


def melee_active_visual(player=None, template_id=0):
    """Return a still-valid active native melee scope, never a stale record."""
    template_id = _v109_int(template_id, 0)
    for _key, record in list(MELEE_VISUAL.items())[:8]:
        try:
            if not record.get('preserve_guid'):
                continue
            owner_ref = record.get('player_ref')
            backpack_ref = record.get('backpack_ref')
            owner = owner_ref() if callable(owner_ref) else None
            backpack = backpack_ref() if callable(backpack_ref) else None
            if owner is None or backpack is None:
                continue
            if player is not None and owner is not player:
                continue
            guid = record.get('new_guid')
            new_item = record.get('new_item')
            if not guid or new_item is None:
                continue
            if backpack.GetMeleeWeapon() != guid:
                continue
            if melee_visual_get(backpack, guid) is not new_item:
                continue
            if template_id and _v109_int(getattr(
                    new_item, 'guise_template_id', 0), 0) != template_id:
                continue
            return owner, backpack, record
        except Exception:
            continue
    return None


def melee_kill_record_fields(info, template_id):
    """Use the active melee's authentic lobby item for official HUD lookup."""
    try:
        if (info is None or not sync_attrs.get('bSkinHack', False)
                or not category_enabled('melee')):
            return False
        template_id = _v109_int(template_id, 0)
        active = melee_active_visual(template_id=template_id)
        if not active:
            return False
        _owner, _backpack, record = active
        new_item = record.get('new_item')
        weapon_id = _v109_int(_mapping_get(info, 'weapon_id', 0), 0)
        display_equip = _v109_int(
            getattr(new_item, 'display_equip_id', 0), 0)
        if weapon_id and display_equip and weapon_id != display_equip:
            return False
        item_id = _v109_int(record.get('item_id'), 0)
        if not item_id:
            return False
        changed = _mapping_set(info, 'guise_item_id', item_id)
        if changed:
            _v109_log(('kill-record-lobby-item', item_id, template_id),
                      'native melee kill record authentic lobby item=%d '
                      'template=%d; template/HUD identity preserved'
                      % (item_id, template_id), 2)
        return changed
    except Exception:
        return False


def melee_kill_avatar_case(player):
    """Verify the exact current injected melee before native KillAvatar."""
    try:
        if (not sync_attrs.get('bSkinHack', False)
                or not category_enabled('melee')):
            return None
        active = melee_active_visual(player=player)
        if not active:
            return None
        _owner, backpack, record = active
        guid = record.get('new_guid')
        if (getattr(player, 'cur_spec_weapon_guid', '')
                or getattr(player, 'cur_weapon_guid', '')) != guid:
            return None
        case = None
        hand = getattr(player, 'hand_model', None)
        cases = getattr(hand, 'weapon_dict', None) if hand is not None else None
        if cases is not None:
            case = cases.get(guid)
        if case is None:
            getter = getattr(player, 'GetWeaponCase', None)
            if callable(getter):
                try:
                    case = getter(guid, is_fps_weapon=True)
                except TypeError:
                    case = getter(guid, True)
        if case is None:
            getter = getattr(player, 'GetCurWeaponCase', None)
            case = getter() if callable(getter) else None
        if case is None:
            return None
        case_guid = getattr(case, 'weapon_guid', guid)
        if case_guid != guid:
            return None
        new_item = record.get('new_item')
        item_id = _v109_int(record.get('item_id'), 0)
        if (_v109_int(getattr(case, 'guise_item_id', 0), 0) != item_id
                or _v109_int(getattr(
                    new_item, 'display_guise_item_id', 0), 0) != item_id):
            return None
        expected = _v109_int(getattr(new_item, 'guise_template_id', 0), 0)
        actual = _v109_int(getattr(case, 'guise_id', 0), 0)
        if not expected or actual != expected:
            return None
        return record, case
    except Exception:
        return None


def melee_kill_avatar_factory(previous):
    """Let the official melee KillAvatar comparison see the local guise.

    The genuine server caster/damage payload is otherwise untouched.  Only
    the verified current injected melee's cosmetic lobby item is aligned;
    WeaponCaseBase then reads its own authentic kill sound/effect fields.
    """
    def wrapper(self, caster, target, critical_spell, *args, **kwargs):
        try:
            verified = melee_kill_avatar_case(self)
            if verified and caster is not None:
                record, case = verified
                item_id = _v109_int(record.get('item_id'), 0)
                old_item = _mapping_get(caster, 'guise_item_id', None)
                if (item_id and old_item != item_id
                        and _mapping_set(caster, 'guise_item_id', item_id)):
                    _v109_log(('kill-avatar-native', item_id,
                               getattr(case, 'guise_id', 0), old_item),
                              'native melee KillAvatar guise aligned item=%d '
                              'template=%r previous=%r; official sound/effect '
                              'comparison preserved'
                              % (item_id, getattr(case, 'guise_id', 0),
                                 old_item), 2)
        except Exception as exc:
            _v109_log(('kill-avatar-error', repr(exc)),
                      'native melee KillAvatar cosmetic alignment skipped: %r'
                      % (exc,), 1)
        return previous(self, caster, target, critical_spell, *args, **kwargs)
    return wrapper


def melee_visual_refresh(player, rebuild_guid=None, sync_current=False):
    """Incrementally refresh native cases without destroying or re-raising.

    RefreshWeaponList/AddWeapon owns missing-case construction.  Existing
    same-GUID cases are deliberately retained; their visual update is a
    separate ChangeWeaponGuise transaction.  The two legacy keyword arguments
    remain accepted for callers, but neither permits case destruction.
    """
    refresh = getattr(player, 'OnWeaponListChanged', None)
    if not callable(refresh):
        return False
    refresh()
    return True


def melee_visual_case_supported(case):
    """Check the actual same-case model contract, including heirloom safety."""
    if case is None:
        return False
    cls = type(case)
    label = (getattr(cls, '__name__', '') + '.' +
             getattr(cls, '__module__', '')).lower()
    model = getattr(case, 'model', None)
    model_label = (getattr(type(model), '__name__', '') + '.' +
                   getattr(type(model), '__module__', '')).lower()
    if 'melee' not in label or 'heirloom' in label or 'heirloom' in model_label:
        return False
    if not callable(getattr(case, 'ChangeWeaponGuise', None)):
        return False
    if not callable(getattr(model, 'ChangePartModel', None)):
        return False
    left = getattr(case, 'lefthand_melee_model', None)
    if left is not None and not callable(getattr(left, 'ChangePartModel', None)):
        return False
    return True


def melee_visual_case_matches(case, item):
    """Verify all visual fields after a native same-GUID case rebuild.

    GUID/case presence alone is not readiness: native RefreshWeaponList and
    loadout transitions can construct a fresh case from older stored fields.
    Keep this readback cheap and side-effect free; the official guise-change
    transaction runs only when one of these authenticated values is stale.
    """
    try:
        equip_id = _v109_int(getattr(item, 'display_equip_id', 0), 0) or \
            _v109_int(getattr(item, 'equip_id', 0), 0)
        expected, replay = melee_visual_target_classes(equip_id)
        if not melee_visual_case_compatible(case, expected, replay):
            return False
        guise_id = _v109_int(getattr(item, 'guise_template_id', 0), 0)
        guise_item_id = _v109_int(
            getattr(item, 'display_guise_item_id', 0), 0)
        skin_id = _v109_int(getattr(item, 'skin_template_id', 0), 0)
        return bool(getattr(case, 'weapon_guid', None)) and \
            _v109_int(getattr(case, 'weapon_id', 0), 0) == equip_id and \
            _v109_int(getattr(case, 'body_weapon_id', 0), 0) == equip_id and \
            _v109_int(getattr(case, 'skin_id', 0), 0) == skin_id and \
            _v109_int(getattr(case, 'guise_id', 0), 0) == guise_id and \
            _v109_int(getattr(case, 'guise_item_id', 0), 0) == guise_item_id
    except Exception:
        return False


def melee_visual_equip_row(equip_id):
    """Return the official equip prototype for `equip_id`, or None.

    `equip_data.data` is the same table `EquipCaseFactory.Create` reads, so
    its `equip_case` value is the game's own class selector.
    """
    equip_id = _v109_int(equip_id, 0)
    if not equip_id:
        return None
    module = sys.modules.get('gclient.data.equip_data')
    data = getattr(module, 'data', None) if module is not None else None
    if data is None:
        state = MELEE_EQUIP_DATA
        now = time.time()
        if not state.get('failed') and now - state.get('retry', 0.0) >= 2.0:
            state['retry'] = now
            try:
                module = _import_module('gclient.data.equip_data')
                data = getattr(module, 'data', None)
            except Exception:
                data = None
            if data is None:
                state['failed'] = True
        if data is None:
            return None
    try:
        row = _v109_field(data, equip_id, None)
        if row is None:
            row = _v109_field(data, str(equip_id), None)
        return row
    except Exception:
        return None


def melee_visual_equip_case_code(equip_id):
    """Read the official equip row's `equip_case` code, or '' when unknown."""
    row = melee_visual_equip_row(equip_id)
    if row is None:
        return ''
    try:
        value = _v109_field(row, 'equip_case', '')
        if callable(value):
            value = value()
        if not isinstance(value, str):
            return ''
        return value
    except Exception:
        return ''


def melee_visual_case_class(code):
    """Resolve the exact class EquipCaseFactory.Create would build for `code`.

    RegisterEquipCaseClass registers every ``<Type>Case`` subclass in its own
    module under the bare type name, so the registry already holds the one
    authoritative class per equip_case code.  Nothing is constructed here and
    no fallback class is invented.
    """
    if not code:
        return None
    try:
        from gclient.gameplay.logic_base.equips.equip_case import EQUIP_CASE_DICT
    except Exception:
        module = sys.modules.get(
            'gclient.gameplay.logic_base.equips.equip_case')
        EQUIP_CASE_DICT = getattr(module, 'EQUIP_CASE_DICT', None) \
            if module is not None else None
    if not isinstance(EQUIP_CASE_DICT, dict):
        return None
    try:
        expected = EQUIP_CASE_DICT.get(code)
    except Exception:
        return None
    return expected if isinstance(expected, type) else None


def melee_visual_target_class(equip_id):
    """Return the official class for an equip id and whether it is provable."""
    expected, replay = melee_visual_target_classes(equip_id)
    return expected, expected is not None


def melee_visual_target_classes(equip_id):
    """Return (normal_class, replay_class); either may be None when unknown."""
    code = melee_visual_equip_case_code(equip_id)
    if not code:
        # Unknown data is not evidence of incompatibility; the model contract
        # checks below still apply.  Never guess a concrete class here.
        return None, None
    return (melee_visual_case_class(code),
            melee_visual_case_class('Replay' + code))


def melee_visual_replay_avatar(owner):
    """True when the official factory would build the `Replay<Code>` family.

    `EquipCaseFactory.Create` rewrites its `equip_case` code to "Replay%s" when
    the first positional argument (the case owner/avatar) has a truthy
    `is_replay_avatar`, and then looks that name up instead of the normal
    class.  In a normal match every combat avatar keeps that attribute set,
    so the class the game itself builds there is the Replay family, and a
    plan-MeleeCase check alone would reject the correct pairing.
    """
    if owner is None:
        return False
    try:
        return bool(getattr(owner, 'is_replay_avatar', False))
    except Exception:
        return False


def melee_visual_case_compatible(case, expected=None, replay=None):
    """Accept only a case class the official factory would itself construct.

    `expected` is the registered class behind the target equip's own
    `equip_case` code, and `replay` is the registered `Replay<Code>` variant.
    The comparison is an identity check against the registry (or a subclass
    of it), never a name substring: `MeleeCase` and `DualMeleeCase` are
    siblings over `WeaponCaseBase`, so neither may stand in for the other.

    Unknown data stays permissive - a missing registry entry is not evidence
    of incompatibility - but a *contradicted* class is always rejected.
    """
    if not melee_visual_case_supported(case):
        return False
    options = []
    for candidate in (expected, replay):
        if isinstance(candidate, type) and candidate not in options:
            options.append(candidate)
    if not options:
        return True
    for candidate in options:
        try:
            if isinstance(case, candidate):
                return True
        except Exception:
            continue
    return False


def melee_visual_equip_row_for_type(equip_id):
    """Return the official equip prototype row for `equip_id` (alias)."""
    return melee_visual_equip_row(equip_id)


def melee_visual_equip_type(equip_id):
    """Read the official `equip_type` of an equip row, or None when unknown."""
    row = melee_visual_equip_row(equip_id)
    if row is None:
        return None
    try:
        value = _v109_field(row, 'equip_type', None)
        if callable(value):
            value = value()
        return _v109_int(value, None)
    except Exception:
        return None


def melee_visual_melee_type():
    """Return the official EquipmentType.MELEE constant, or None."""
    try:
        consts = sys.modules.get('gshare.consts')
        enum = getattr(consts, 'EquipmentType', None) if consts else None
        value = getattr(enum, 'MELEE', None) if enum is not None else None
        return _v109_int(value, None)
    except Exception:
        return None


def melee_visual_is_melee_item(item, equip_id):
    """Authenticate a constructed melee item without trusting one property.

    The item is accepted when either the official native property says melee
    or the very equip id we resolved and read back matches the official
    equipment table - both are game-owned sources, and the caller has already
    proven the clone's equip id equals `equip_id`.  An unreadable/absent equip
    type never *grants* acceptance; it only fails to contradict it, and the
    remaining native readbacks still have to pass.
    """
    try:
        if bool(getattr(item, 'is_melee', False)):
            return True
    except Exception:
        pass
    if not equip_id:
        return False
    melee_type = melee_visual_melee_type()
    equip_type = melee_visual_equip_type(equip_id)
    if melee_type is None or equip_type is None:
        # No authoritative type table to consult: keep the strict native
        # answer instead of inventing acceptance.
        return False
    return equip_type == melee_type


def melee_visual_case_class_name(equip_id):
    """Human-readable target class name(s) for diagnostics."""
    expected, replay = melee_visual_target_classes(equip_id)
    names = [getattr(cls, '__name__', None) for cls in (expected, replay)]
    names = [name for name in names if name]
    return '/'.join(names) if names else None


def melee_visual_case_type_names(player, guid):
    """Actual held-case type names on both models, for diagnostics only."""
    names = []
    try:
        for model in (getattr(player, 'hand_model', None),
                      getattr(player, 'model', None)):
            cases = getattr(model, 'weapon_dict', None) if model is not None else None
            case = cases.get(guid) if cases is not None else None
            names.append(type(case).__name__ if case is not None else None)
    except Exception:
        return tuple()
    return tuple(names)


def melee_visual_case_accepts_change(case, equip_id):
    """True when this held case can itself express the requested change.

    The official game never compares case *types* when it changes an
    appearance.  `HudGunSkinComponent.ChangeGunGuise` takes whatever case is
    current (`GetCurWeaponCase()`) and calls `ChangeWeaponGuise` on it, and
    `MeleeCase`/`DualMeleeCase`/`HeirloomCase` all re-derive the body model
    from the guise template's own `replace_equip_id`.  A held `MeleeCase`
    therefore renders a dual/heirloom appearance correctly, and refusing the
    pairing made the build stricter than the game - the r4/r5 in-match
    refusals came from exactly that.

    What must still be proven is that the change will actually take effect:
    a case frozen to a different body equip, or with no model to repaint,
    cannot show the new appearance and is still refused.
    """
    if not melee_visual_case_supported(case):
        # Still a melee-family object: a gun case re-derives from a gun guise
        # template and can never show a melee appearance, which is what the
        # official melee warehouse avoids by resolving GetMeleeWeaponCase().
        return False
    # NOTE: do not compare `case.weapon_id` with the target equip here.  That
    # field holds the body equip the case is CURRENTLY on; before
    # ChangeWeaponGuise runs it legitimately differs from the target (the r6
    # device log showed weapon_id=16 against target_equip=132 for exactly this
    # reason).  Requiring them to match up front is circular.  ChangeWeaponGuise
    # itself assigns weapon_id from the guise template's replace_equip_id, and
    # the post-change body readback already verifies the result.
    return True


def melee_visual_case_weapon_ids(player, guid):
    """Held-case body weapon ids on both models, for diagnostics only."""
    values = []
    try:
        for model in (getattr(player, 'hand_model', None),
                      getattr(player, 'model', None)):
            cases = getattr(model, 'weapon_dict', None) if model is not None else None
            case = cases.get(guid) if cases is not None else None
            values.append(_v109_int(getattr(case, 'weapon_id', 0), 0)
                          if case is not None else None)
    except Exception:
        return tuple()
    return tuple(values)


def melee_visual_preflight_cases(player, guid, equip_id=0):
    """Verify the held case can express the change; never veto on class alone.

    Returns True when every present case can take the appearance.  The target
    class is reported by the caller for diagnostics only, because the game
    itself does not gate appearance changes on it.
    """
    try:
        seen = False
        for model in (getattr(player, 'hand_model', None),
                      getattr(player, 'model', None)):
            cases = getattr(model, 'weapon_dict', None) if model is not None else None
            if cases is None:
                continue
            case = cases.get(guid)
            if case is None:
                continue
            seen = True
            if not melee_visual_case_accepts_change(case, equip_id):
                return False
        return seen or True
    except Exception:
        return False


def melee_visual_change_cases(player, guid, item, refresh=True):
    """Apply one item's authentic visual fields to existing compatible cases.

    Official AddWeapon initializes cases which were missing.  Pre-existing
    normal/dual/replay melee cases instead use their official ChangeWeaponGuise
    path, avoiding DestroyWeapon and preserving current/next weapon prediction.
    """
    try:
        equip_id = _v109_int(getattr(item, 'display_equip_id', 0), 0) or \
            _v109_int(getattr(item, 'equip_id', 0), 0)
        guise_id = _v109_int(getattr(item, 'guise_template_id', 0), 0)
        guise_item_id = _v109_int(getattr(item, 'display_guise_item_id', 0), 0)
        skin_id = _v109_int(getattr(item, 'skin_template_id', 0), 0)
        if not guid or not equip_id:
            return False
        # v2.101: the official ChangeWeaponGuise first positional is the
        # SKIN id (Eclipse _apply_weapon_case_skin_core), never a guise
        # template and never None.
        _v2101_first = skin_id or guise_id or 0
        expected, replay = melee_visual_target_classes(equip_id)
        models = []
        existing = []
        for model in (getattr(player, 'hand_model', None),
                      getattr(player, 'model', None)):
            cases = getattr(model, 'weapon_dict', None) if model is not None else None
            if cases is None:
                continue
            models.append((model, cases))
            case = cases.get(guid)
            if case is not None:
                if not melee_visual_case_accepts_change(case, equip_id):
                    raise RuntimeError(
                        'held case cannot express the appearance for equip %d '
                        '(type=%s weapon_id=%r target=%d)'
                        % (equip_id, type(case).__name__,
                           getattr(case, 'weapon_id', None), equip_id))
                existing.append((cases, case))
        if not models:
            return False
        if refresh and not melee_visual_refresh(player):
            return False
        for _model, cases in models:
            if cases.get(guid) is None:
                raise RuntimeError('official incremental refresh left a missing case')
        for cases, case in existing:
            if cases.get(guid) is not case:
                # A genuine newer case constructed during refresh owns the
                # item's state; never mutate a detached stale native object.
                continue
            # v2.124: never clobber a genuine different identity (the
            # module invariant is "switch/damage identity preserved"). Set
            # the ids only on a fresh/unset case or when they agree.
            _cur_w24 = _v109_int(getattr(case, 'weapon_id', 0), 0)
            if not _cur_w24 or _cur_w24 == equip_id:
                case.weapon_id = equip_id
                case.body_weapon_id = equip_id
            case.skin_id = skin_id
            # v2.101: skin-first call shape (Eclipse v8.36 contract).  The
            # old `ChangeWeaponGuise(guise_id or None, ...)` passed a
            # zero guise template -> None -> melee_case.py:169
            # NoneType.IsValid crash killed the model build.
            if _v2101_first:
                # v2.102: Eclipse's healthy-case chain - skin first,
                # then the guise transaction, then the mesh load.  All
                # steps are tolerant per-call; a missing method (e.g.
                # MeleeCase.LoadModelSkin) is a no-op.
                try:
                    case.ClearGuiseItemCache()
                except Exception:
                    pass
                _skin_done = False
                try:
                    _sf = getattr(case, 'ChangeWeaponSkin', None)
                    if callable(_sf):
                        _sf(_v2101_first, data_changed=True,
                            force_refresh=True)
                        _skin_done = True
                except Exception:
                    pass
                if not _skin_done:
                    try:
                        case.ChangeWeaponSkin(_v2101_first)
                    except Exception:
                        pass
                try:
                    case.ChangeWeaponGuise(_v2101_first,
                                           guise_item_id=guise_item_id or None)
                except Exception:
                    try:
                        case.ChangeWeaponGuise(_v2101_first)
                    except Exception:
                        pass
                for _fn, _a, _k in (
                        ('InitGuiseIllusion', (), {}),
                        ('WeaponBodyIllusion', (True,), {}),
                        ('RefreshIllusionEffect', (), {}),
                        ('ShowWeaponBodyEffectVisible', (True,), {}),
                        ('ShowWeaponAdsSfxVisible', (True,), {}),
                        ('LoadModelSkin', (_v2101_first,),
                         {'is_init': False, 'start_load': True}),
                        ('LoadModelSkin', (_v2101_first,), {}),
                        ('RefreshModelSkin', (), {}),
                        ('PostprocessMeleePerformance', (), {}),
                        ('PostprocessPerformance', (), {}),
                        ('RefreshGuiseEffect', (), {}),
                ):
                    try:
                        _f = getattr(case, _fn, None)
                        if callable(_f):
                            _f(*_a, **_k)
                    except Exception:
                        pass
            # MeleeCase intentionally leaves this to its official twin-weapon
            # caller; WeaponCaseBase writes it directly.  Cover both contracts.
            case.guise_item_id = guise_item_id or None
        for _model, cases in models:
            case = cases.get(guid)
            if _v109_int(getattr(case, 'weapon_id', 0), 0) != equip_id:
                raise RuntimeError('case equip readback mismatch')
            if _v109_int(getattr(case, 'body_weapon_id', 0), 0) != equip_id:
                raise RuntimeError('case body-equip readback mismatch')
            if _v2101_first and _v109_int(
                    getattr(case, 'guise_id', 0), 0) not in (
                        _v109_int(guise_id, 0),
                        _v109_int(skin_id, 0)):
                raise RuntimeError('case guise readback mismatch')
            if _v109_int(getattr(case, 'guise_item_id', 0), 0) != guise_item_id:
                raise RuntimeError('case guise-item readback mismatch')
        return True
    except Exception as exc:
        _v109_log(('visual-same-case-error', guid, repr(exc)),
                  'native melee same-case visual update guid=%r error=%r'
                  % (guid, exc), 2)
        return False


def melee_visual_repair_cases(player, reason='ui', force=False,
                                    min_interval=0.75,
                                    rate_field='case_repair_at'):
    """Add only missing native cases for our active genuine-GUID visual.

    RefreshWeaponList is incremental and does not destroy existing cases.  A
    single bounded refresh can therefore repair the FPS/TPS case required by
    the refit UI without repeating the expensive apply-time case rebuild.
    """
    backpack = getattr(player, 'backpack', None)
    key = (id(player), id(backpack))
    record = MELEE_VISUAL.get(key)
    if not record or not record.get('preserve_guid'):
        return None
    guid = record.get('new_guid')
    try:
        if (backpack.GetMeleeWeapon() != guid
                or melee_visual_get(backpack, guid)
                is not record.get('new_item')):
            return None
        missing = []
        for label, model in (('fps', getattr(player, 'hand_model', None)),
                             ('tps', getattr(player, 'model', None))):
            if model is None:
                continue
            cases = getattr(model, 'weapon_dict', None)
            if cases is not None and guid not in cases:
                missing.append(label)
        now = time.time()
        if ((force or missing)
                and now - record.get(rate_field, 0.0) >= min_interval):
            # Set the rate-limit marker before the native call so a reentrant
            # UI observer cannot start another refresh in the same frame.
            record[rate_field] = now
            if not melee_visual_refresh(player):
                raise RuntimeError('incremental native case refresh failed')
            _v109_log(('visual-case-repair', record.get('item_id'), reason,
                       tuple(missing), bool(force)),
                      'native melee incremental case repair item=%d reason=%s '
                      'missing=%r forced=%s' % (
                          record.get('item_id'), reason, missing, force), 2)
        return record
    except Exception as exc:
        _v109_log(('visual-case-repair-error', record.get('item_id'), reason,
                   repr(exc)),
                  'native melee incremental case repair item=%d reason=%s '
                  'error=%r' % (record.get('item_id'), reason, exc), 2)
        raise


def melee_ui_case_precheck(kind):
    """Prevent the injected melee UI from dereferencing a missing native case."""
    if not category_enabled('melee'):
        return True
    _root, player = melee_visual_player()
    if player is None:
        return True
    backpack = getattr(player, 'backpack', None)
    record = MELEE_VISUAL.get((id(player), id(backpack)))
    if not record or not record.get('preserve_guid'):
        return True
    try:
        melee_visual_repair_cases(player, reason=kind)
        getter_name = ('GetCurWeaponCase' if kind == 'enter-refit'
                       else 'GetMeleeWeaponCase')
        getter = getattr(player, getter_name, None)
        case = getter() if callable(getter) else None
        if case is None:
            # EnterGunRefit may need a missing current gun case rather than the
            # melee case.  The same official incremental refresh adds any
            # missing backpack case; it still performs no destruction.
            melee_visual_repair_cases(
                player, reason=kind + '-required', force=True)
            case = getter() if callable(getter) else None
        if case is None:
            _v109_log(('visual-ui-case-blocked', record.get('item_id'), kind),
                      'native melee UI kind=%s held safely: required genuine '
                      'case remains unavailable' % kind, 2)
            return False
        if kind == 'enter-refit':
            # Official EnterGunRefit can skip its slot fallback and later read
            # hand_model.weapon_case.body_weapon_id directly.  Never invent a
            # raise for a stale/partially raised current case; its next genuine
            # native take owns that lifecycle.
            hand = getattr(player, 'hand_model', None)
            current_guid = (getattr(player, 'cur_spec_weapon_guid', '')
                            or getattr(player, 'cur_weapon_guid', ''))
            case_guid = getattr(case, 'weapon_guid', '')
            if hand is not None and current_guid and case_guid == current_guid \
                    and getattr(hand, 'weapon_case', None) is not case:
                _v109_log(('visual-refit-binding-blocked', record.get('item_id')),
                          'native melee refit held safely until official '
                          'current-case binding is healthy', 2)
                return False
        return True
    except Exception as exc:
        _v109_log(('visual-ui-case-error', record.get('item_id'), kind,
                   repr(exc)),
                  'native melee UI kind=%s precheck failed safely: %r'
                  % (kind, exc), 2)
        return False


def melee_ui_case_factory(previous, kind):
    def wrapper(*args, **kwargs):
        if not melee_ui_case_precheck(kind):
            return None
        try:
            return previous(*args, **kwargs)
        except AttributeError as exc:
            # The official melee window and refit entry dereference these two
            # fields directly.  Contain only that exact injected-case failure;
            # every genuine path and every unrelated exception propagates.
            expected = ("'NoneType' object has no attribute 'weapon_id'"
                        if kind != 'enter-refit' else
                        "'NoneType' object has no attribute 'body_weapon_id'")
            if str(exc) != expected:
                raise
            _root, player = melee_visual_player()
            backpack = getattr(player, 'backpack', None)
            record = MELEE_VISUAL.get((id(player), id(backpack)))
            if not record or not record.get('preserve_guid'):
                raise
            _v109_log(('visual-ui-case-contained', record.get('item_id'), kind),
                      'native melee UI kind=%s contained missing-case failure '
                      'without a substitute case' % kind, 2)
            return None
    return wrapper


def melee_case_get_factory(previous, kind):
    """Repair an active injected case only after the native getter misses."""
    def wrapper(player, *args, **kwargs):
        case = previous(player, *args, **kwargs)
        if case is not None or not category_enabled('melee'):
            return case
        backpack = getattr(player, 'backpack', None)
        record = MELEE_VISUAL.get((id(player), id(backpack)))
        if not record or not record.get('preserve_guid'):
            return case
        try:
            melee_visual_repair_cases(
                player, reason=kind, force=True,
                rate_field='case_get_repair_at')
            return previous(player, *args, **kwargs)
        except Exception as exc:
            _v109_log(('visual-case-get-error', record.get('item_id'), kind,
                       repr(exc)),
                      'native melee case getter kind=%s repair error=%r'
                      % (kind, exc), 2)
            return case
    return wrapper


def melee_visual_rebind(player, from_guid, to_guid):
    """Keep native current/next prediction attached to a replacement melee.

    Official PlayerCombatAvatarMember.OnWeaponListChanged first corrects stale
    GUIDs, then CorrectCurrentWeapons falls back to WEAPON_1/WEAPON_2 when the
    current melee GUID was removed.  Rebind before that refresh whenever (and
    only when) the prediction still points at our replaced GUID.  The explicit
    True argument selects ChangeWeaponClientAhead's server-notified branch:
    local-only injected GUIDs are never sent through ClientChangeWeapon.
    """
    if not from_guid or from_guid == to_guid:
        return True
    target = to_guid or ''
    try:
        if getattr(player, 'next_weapon_guid', None) == from_guid:
            player.next_weapon_guid = target
        if getattr(player, 'cur_weapon_guid', None) != from_guid:
            return True
        changer = getattr(player, 'ChangeWeaponClientAhead', None)
        if not callable(changer):
            raise RuntimeError('official current-weapon rebind unavailable')
        changer(target, True)
        if getattr(player, 'cur_weapon_guid', None) != target:
            raise RuntimeError('current-weapon rebind readback mismatch')
        _v109_log(('visual-rebind', from_guid, target),
                  'native melee current/next rebound without server RPC',
                  1)
        return True
    except Exception as exc:
        _v109_log(('visual-rebind-error', from_guid, target, repr(exc)),
                  'native melee current/next rebind failed: %r' % (exc,), 2)
        return False


def melee_visual_restore_preserved(player, backpack, key, record,
                                         reason='restore', refresh=True):
    """Restore a visual clone while its genuine server GUID stays unchanged."""
    old_guid = record.get('old_guid')
    old_item = record.get('old_item')
    new_item = record.get('new_item')
    slot = record.get('slot')
    try:
        slots = backpack.slots
        current = melee_visual_get(backpack, old_guid)
        occupant = slots.get(slot)
        if (occupant not in (old_guid, '', None)
                or (occupant in ('', None) and current is new_item)):
            # A different genuine equip or deliberate empty slot is newer
            # state.  Remove only our unslotted clone, never the genuine item.
            if current is new_item:
                backpack.Remove(old_guid)
            MELEE_VISUAL.pop(key, None)
            _v109_log(('visual-preserved-genuine-slot-wins',
                       record.get('item_id'), reason),
                      'native melee visual preserved genuine later slot item=%d '
                      'reason=%s' % (record.get('item_id'), reason), 1)
            return True
        if current is old_item:
            # The authentic baseline is already back.  Finish a previously
            # interrupted same-case visual restoration before retiring the
            # record; refresh=False means the caller is about to apply anew.
            if refresh and occupant == old_guid and not \
                    melee_visual_change_cases(player, old_guid, old_item):
                raise RuntimeError('original same-case visual restore failed')
            MELEE_VISUAL.pop(key, None)
            return True
        if current is not new_item:
            if current is None and occupant == old_guid:
                # Complete a partially restored same-GUID transaction only.
                if not backpack.Add(old_item):
                    raise RuntimeError('native backpack refused original melee')
                slots[slot] = old_guid
                if melee_visual_get(backpack, old_guid) is not old_item:
                    raise RuntimeError('original melee identity was not restored')
                if refresh and not melee_visual_change_cases(
                        player, old_guid, old_item):
                    raise RuntimeError('original same-case visual restore failed')
            # A genuine same-GUID rebuild, genuine empty slot, or a different
            # genuine occupant is newer state and must not be overwritten.
            MELEE_VISUAL.pop(key, None)
            _v109_log(('visual-preserved-genuine-wins', record.get('item_id'), reason),
                      'native melee visual preserved genuine later state item=%d reason=%s'
                      % (record.get('item_id'), reason), 1)
            return True
        removed = backpack.Remove(old_guid)
        if removed is not new_item:
            raise RuntimeError('visual clone removal identity mismatch')
        if not backpack.Add(old_item):
            # Best-effort reversal to the still-valid visual clone; retain the
            # record so a later OFF can retry the authentic restoration.
            backpack.Add(new_item)
            slots[slot] = old_guid
            raise RuntimeError('native backpack refused original melee')
        slots[slot] = old_guid
        if melee_visual_get(backpack, old_guid) is not old_item:
            raise RuntimeError('original melee identity was not restored')
        if refresh and not melee_visual_change_cases(
                player, old_guid, old_item):
            raise RuntimeError('original same-case visual restore failed')
        MELEE_VISUAL.pop(key, None)
        _v109_log(('visual-preserved-restored', record.get('item_id'), reason),
                  'native melee visual restored genuine item/GUID item=%d reason=%s'
                  % (record.get('item_id'), reason), 1)
        return True
    except Exception as exc:
        _v109_log(('visual-preserved-restore-error', record.get('item_id'), repr(exc)),
                  'native melee preserved-GUID restore item=%d reason=%s error=%r'
                  % (record.get('item_id'), reason, exc), 2)
        return False


def melee_visual_restore(key, reason='restore', refresh=True):
    """Restore only our active swap; a later genuine slot occupant wins."""
    record = MELEE_VISUAL.get(key)
    if not record:
        return False
    player_ref = record.get('player_ref')
    backpack_ref = record.get('backpack_ref')
    player = player_ref() if callable(player_ref) else None
    backpack = backpack_ref() if callable(backpack_ref) else None
    if player is None or backpack is None:
        MELEE_VISUAL.pop(key, None)
        return True
    old_guid = record.get('old_guid')
    old_item = record.get('old_item')
    new_guid = record.get('new_guid')
    new_item = record.get('new_item')
    slot = record.get('slot')
    if record.get('preserve_guid'):
        return melee_visual_restore_preserved(
            player, backpack, key, record, reason, refresh=refresh)
    try:
        slots = backpack.slots
        current_slot = slots.get(slot)
        current_new = melee_visual_get(backpack, new_guid)
        current_old = melee_visual_get(backpack, old_guid)
        if current_slot == old_guid and current_old is old_item \
                and current_new is not new_item:
            # A prior restore may have completed the backpack transaction but
            # failed its current-weapon rebind.  Finish that native contract
            # before retiring the record; never leave a stale injected GUID.
            if not melee_visual_rebind(player, new_guid, old_guid):
                return False
            MELEE_VISUAL.pop(key, None)
            return True
        genuine_other = current_slot not in (new_guid, old_guid, '', None)
        genuine_old = (bool(old_guid) and current_slot == old_guid
                       and current_old is not old_item)
        genuine_empty = (current_slot in ('', None)
                         and current_new is not new_item
                         and current_old is not old_item)
        if genuine_other or genuine_old or genuine_empty:
            # Do not overwrite a genuine later equip.  Our now-unslotted item
            # can still be removed by identity without touching that equip.
            if current_new is new_item:
                backpack.Remove(new_guid)
            MELEE_VISUAL.pop(key, None)
            _v109_log(('visual-genuine-wins', record.get('item_id'), reason),
                      'native melee visual restore item=%d reason=%s: '
                      'genuine later slot preserved' % (record.get('item_id'), reason), 1)
            return True
        if current_new is new_item:
            backpack.Remove(new_guid)
        elif slots.get(slot) == new_guid:
            slots[slot] = ''
        if old_item is not None:
            if melee_visual_get(backpack, old_guid) is None:
                if not backpack.Add(old_item):
                    raise RuntimeError('native backpack refused original melee')
            if melee_visual_get(backpack, old_guid) is not old_item:
                raise RuntimeError('original melee identity was not restored')
            slots[slot] = old_guid
        restored = (slots.get(slot) == old_guid and
                    (old_item is None or
                     melee_visual_get(backpack, old_guid) is old_item))
        if not restored:
            raise RuntimeError('native melee slot restore readback mismatch')
        if not melee_visual_rebind(player, new_guid, old_guid):
            raise RuntimeError('native melee current-weapon restore failed')
        if refresh:
            melee_visual_refresh(player)
        MELEE_VISUAL.pop(key, None)
        _v109_log(('visual-restored', record.get('item_id'), reason),
                  'native melee visual restored item=%d reason=%s'
                  % (record.get('item_id'), reason), 1)
        return True
    except Exception as exc:
        _v109_log(('visual-restore-error', record.get('item_id'), repr(exc)),
                  'native melee visual restore item=%d reason=%s error=%r'
                  % (record.get('item_id'), reason, exc), 2)
        return False


def melee_visual_restore_all_on_game(reason='restore', player=None,
                                           refresh=True):
    restored = False
    for key, record in list(MELEE_VISUAL.items())[:8]:
        if player is not None:
            reference = record.get('player_ref')
            owner = reference() if callable(reference) else None
            if owner is not player:
                continue
        restored = melee_visual_restore(
            key, reason, refresh=refresh) or restored
    return restored


def melee_visual_restore_all(reason='restore', player=None, refresh=True):
    """Queue OFF restoration with applies, never from the worker thread."""
    return native_game_dispatch(
        'v109-melee-visual-restore', melee_visual_restore_all_on_game,
        reason, player, refresh)


def melee_visual_apply_on_game(item_id=None):
    """Apply native melee visuals without replacing the genuine server GUID.

    A local-only combat GUID can render briefly, but normal ClientChangeWeapon
    and damage resolution do not own it.  Clone the authentic melee's stored
    gameplay data instead, retain its GUID, and change only the local combat
    item/template fields.  With no authentic melee base there is no honest
    damage-capable equip, so this path fails closed.
    """
    if not category_enabled('melee'):
        melee_visual_restore_all('visual-disabled')
        return False
    item_id = _v109_int(item_id, 0) or _v109_int(
        MELEE_SAVED.get('item_id'), 0) or config_pick('iNativeMelee')
    record = injected_record(item_id) if item_id else None
    if not record or record[1] != 'melee':
        if item_id:
            _v109_log(('visual-record-wait', item_id),
                      'native melee visual item=%d waiting for retained lobby row'
                      % item_id, 1)
        return False
    native_item = record[2]
    lobby_guid = getattr(native_item, 'guid', None)
    row = getattr(native_item, 'item_proto', None) or _v109_row(item_id)
    if not lobby_guid or row is None:
        _v109_log(('visual-row-rejected', item_id),
                  'native melee visual item=%d rejected missing GUID/prototype'
                  % item_id, 1)
        return False
    root, player = melee_visual_player()
    if player is None:
        _v109_log(('visual-player-wait', item_id),
                  'native melee visual item=%d waiting for combat player'
                  % item_id, 1)
        melee_visual_restore_all('no-combat-player')
        return None
    backpack = getattr(player, 'backpack', None)
    slots = getattr(backpack, 'slots', None)
    consts = sys.modules.get('gshare.consts')
    slot_enum = getattr(consts, 'BackpackSlot', None) if consts else None
    slot = getattr(slot_enum, 'VICE_WEAPON', None) if slot_enum else None
    if (backpack is None or slots is None or slot is None
            or not callable(getattr(backpack, 'Add', None))
            or not callable(getattr(backpack, 'Remove', None))
            or not callable(getattr(player, 'OnWeaponListChanged', None))):
        _v109_log(('visual-backpack-wait', item_id),
                  'native melee visual item=%d waiting for combat backpack/case API'
                  % item_id, 1)
        return None
    key = (id(player), id(backpack))
    active = MELEE_VISUAL.get(key)
    if (active and active.get('preserve_guid')
            and active.get('item_id') == item_id
            and active.get('lobby_guid') == lobby_guid):
        try:
            genuine_guid = active.get('new_guid')
            if (slots.get(active.get('slot')) == genuine_guid
                    and melee_visual_get(backpack, genuine_guid)
                    is active.get('new_item')):
                hand = getattr(player, 'hand_model', None)
                model = getattr(player, 'model', None)
                models = [m for m in (hand, model)
                          if m is not None and getattr(
                              m, 'weapon_dict', None) is not None]
                # FPS and TPS readers are independent.  Presence in only one
                # model is not sufficient: HudMeleeSkinWindow can request the
                # other case and otherwise dereference None.
                present = bool(models) and all(
                    genuine_guid in m.weapon_dict for m in models)
                now = time.time()
                if not present and now - active.get('refresh_at', 0.0) >= 2.0:
                    if melee_visual_refresh(player):
                        active['refresh_at'] = now
                        _v109_log(('visual-case-retry', item_id),
                                  'native melee visual retrying missing case item=%d'
                                  % item_id, 1)
                        present = bool(models) and all(
                            genuine_guid in m.weapon_dict for m in models)
                new_item = active.get('new_item')
                stale = present and any(
                    not melee_visual_case_matches(
                        m.weapon_dict.get(genuine_guid), new_item)
                    for m in models)
                if (stale and now - active.get('state_repair_at', 0.0)
                        >= 0.75):
                    # A same-GUID native rebuild can retain identity while
                    # restoring default equip/guise fields.  Repair that exact
                    # state through the official path; never clone again or
                    # destroy/re-raise the user's current weapon.
                    active['state_repair_at'] = now
                    active['repair291'] = active.get('repair291', 0) + 1
                    if active['repair291'] > 3:
                        # v2.91: the repair loop fought the game's own case
                        # rebuild every ~1s - each cycle re-ran the native
                        # visual refresh = the 2-3 FPS "lag".  Stop after
                        # three tries; the scene reload rebuilds the visual.
                        _v109_log(('visual-repair-dead', item_id),
                                  'melee visual repair bounded item=%d '
                                  '(state never settles)' % item_id, 1)
                        active['state_repair_at'] = now + 60.0
                        return False
                    repaired = melee_visual_change_cases(
                        player, genuine_guid, new_item)
                    _v109_log(('visual-case-state-repair', item_id,
                               bool(repaired)),
                              'native melee stale same-GUID case repair '
                              'item=%d verified=%s' % (item_id, repaired), 2)
                    if not repaired:
                        return False
                ready = present and all(
                    melee_visual_case_matches(
                        m.weapon_dict.get(genuine_guid), new_item)
                    for m in models)
                if not ready:
                    _v109_log(('visual-case-state-wait', item_id, present),
                              'native melee visual item=%d waiting for '
                              'verified FPS/TPS case state present=%s'
                              % (item_id, present), 2)
                return ready
        except Exception:
            pass

    skin_id = melee_template(native_item, row, 'skin', item_id)
    guise_id = melee_template(native_item, row, 'guise', item_id)
    template_id = skin_id or guise_id
    equip_id = 0
    try:
        module = sys.modules.get('gshare.weapon_util')
        resolver = getattr(module, 'GetMeleeSkinRealEquipId', None) \
            if module is not None else None
        if template_id and callable(resolver):
            equip_id = _v109_int(resolver(template_id), 0)
    except Exception:
        equip_id = 0
    if not equip_id:
        equip_id = melee_equip(row)
    if not equip_id or equip_id in (globals().get('WEP_GUN_IDS') or {}):
        _v109_log(('visual-equip-unresolved', item_id, template_id),
                  'native melee visual item=%d template=%d has no authentic '
                  'melee equip' % (item_id, template_id), 1)
        return False
    if not melee_visual_dlc_ready(root, item_id, guise_id):
        return None
    combat_id = melee_combat_item_id(equip_id)
    clone = globals().get('combat_clone')
    if not combat_id or not callable(clone):
        _v109_log(('visual-api-missing', item_id, equip_id, combat_id),
                  'native melee visual preflight unavailable item=%d '
                  'equip=%d combat=%d' % (item_id, equip_id, combat_id), 1)
        return False

    try:
        getter = getattr(backpack, 'GetMeleeWeapon', None)
        genuine_guid = getter() if callable(getter) else slots.get(slot, '')
    except Exception:
        genuine_guid = None
    genuine = melee_visual_get(backpack, genuine_guid) \
        if genuine_guid else None
    if (not genuine_guid or genuine is None
            or genuine_guid == lobby_guid
            or not bool(getattr(genuine, 'is_melee', False))):
        _v109_log(('visual-authentic-base-required', item_id),
                  'native melee visual item=%d requires a genuine combat '
                  'melee/GUID; local-only damage-equip rejected' % item_id, 2)
        return False

    # A prior visual clone is not the authentic baseline.  Build from its
    # saved genuine item, but do not disturb that valid visual until the new
    # candidate has passed every readback.  A different current item/GUID is
    # a genuine later equip and wins instead of receiving our selection.
    baseline = genuine
    if active and active.get('preserve_guid'):
        if (genuine_guid != active.get('new_guid')
                or genuine not in (active.get('new_item'), active.get('old_item'))):
            melee_visual_restore(key, 'visual-genuine-later')
            return False
        if genuine is active.get('new_item'):
            baseline = active.get('old_item') or genuine
    if not bool(getattr(baseline, 'is_melee', False)):
        return False
    if not melee_visual_preflight_cases(player, genuine_guid, equip_id):
        _v109_log(('visual-case-unsupported', item_id, genuine_guid, equip_id),
                  'native melee visual item=%d equip=%d held case cannot '
                  'express this appearance guid=%r held=%r weapon_id=%r '
                  'target_equip=%d target_class=%r replay_owner=%s; no case '
                  'rebuild attempted'
                  % (item_id, equip_id, genuine_guid,
                     melee_visual_case_type_names(player, genuine_guid),
                     melee_visual_case_weapon_ids(player, genuine_guid),
                     equip_id,
                     melee_visual_case_class_name(equip_id),
                     melee_visual_replay_avatar(player)), 2)
        return False

    changes = {
        'skin_item_id': item_id if skin_id else 0,
        'guise_item_id': item_id if guise_id else 0,
    }
    try:
        # Official CreateBackpackItemByData(CItem, data) preserves the genuine
        # item's stored gameplay fields and runs OnCreated.  Only item/template
        # fields change; the server-recognized GUID remains genuine_guid.
        new_item = clone(baseline, genuine_guid, changes, combat_id)
        if new_item is None or getattr(new_item, 'guid', None) != genuine_guid:
            raise RuntimeError('genuine combat GUID was not preserved')
        if _v109_int(getattr(new_item, 'item_id', 0), 0) != combat_id:
            raise RuntimeError('combat item ID readback mismatch')
        display_equip = _v109_int(
            getattr(new_item, 'display_equip_id', 0), 0)
        raw_equip = _v109_int(getattr(new_item, 'equip_id', 0), 0)
        if raw_equip != equip_id or display_equip != equip_id:
            raise RuntimeError('combat equip readback mismatch raw=%r display=%r'
                               % (raw_equip, display_equip))
        # Authenticate the melee channel through the same verified equip id
        # that the official resolved above, not only through IItem.is_melee.
        # `is_melee` is `weapon_util.IsWeaponMelee(equip_id)` -> EquipmentType
        # == MELEE, and it legitimately returns False for real melee equips in
        # the 14x/58x families (observed: 2010000190/equip 580 and
        # 2000000010/equip 141), which would otherwise reject valid swaps.
        if not melee_visual_is_melee_item(new_item, equip_id):
            raise RuntimeError(
                'replacement is not an authentic melee item (equip=%d '
                'is_melee=%r equip_type=%r)'
                % (equip_id, getattr(new_item, 'is_melee', None),
                   melee_visual_equip_type(equip_id)))
        if (_v109_int(getattr(new_item, 'skin_template_id', 0), 0)
                != skin_id):
            raise RuntimeError('skin template readback mismatch')
        if (_v109_int(getattr(new_item, 'guise_template_id', 0), 0)
                != guise_id):
            raise RuntimeError('guise template readback mismatch')
        if guise_id and _v109_int(getattr(
                new_item, 'display_guise_item_id', 0), 0) != item_id:
            raise RuntimeError('guise lobby item readback mismatch')
    except Exception as exc:
        _v109_log(('visual-create-error', item_id, equip_id, repr(exc)),
                  'native melee visual item=%d equip=%d creation rejected: %r'
                  % (item_id, equip_id, exc), 2)
        return False

    # Construction succeeded.  Retire the prior visual first, then commit this
    # same-GUID replacement.  Current/next predictions remain valid throughout
    # the subsequent official refresh, so CorrectCurrentWeapons cannot fall
    # back to WEAPON_1 and normal switching still uses the genuine GUID.
    melee_visual_restore_all(
        'visual-switch', player=player, refresh=False)
    for _key, _record in list(MELEE_VISUAL.items()):
        _reference = _record.get('player_ref')
        if callable(_reference) and _reference() is player:
            melee_visual_refresh(player)
            return False
    genuine = melee_visual_get(backpack, genuine_guid)
    if genuine is not baseline:
        _v109_log(('visual-baseline-changed', item_id),
                  'native melee visual item=%d genuine baseline changed; '
                  'newer state preserved' % item_id, 1)
        melee_visual_refresh(player)
        return False

    try:
        if backpack.Remove(genuine_guid) is not genuine:
            raise RuntimeError('original melee removal identity mismatch')
        if not backpack.Add(new_item):
            raise RuntimeError('native backpack refused replacement')
        if melee_visual_get(backpack, genuine_guid) is not new_item:
            raise RuntimeError('replacement backpack readback mismatch')
        slots[slot] = genuine_guid
        if slots.get(slot) != genuine_guid:
            raise RuntimeError('replacement melee slot readback mismatch')
        if not melee_visual_change_cases(player, genuine_guid, new_item):
            # v2.88: a visual-only failure must NOT roll the pick back - the
            # backpack item + slots already hold the swap and the scene
            # reload rebuilds the visual from them.  Keep the pick.
            _v109_log(('visual-refresh-soft', item_id),
                      'same-case visual refresh incomplete; pick kept', 1)
    except Exception as exc:
        rollback_error = None
        try:
            if melee_visual_get(backpack, genuine_guid) is new_item:
                backpack.Remove(genuine_guid)
            if melee_visual_get(backpack, genuine_guid) is None:
                backpack.Add(genuine)
            if melee_visual_get(backpack, genuine_guid) is not genuine:
                raise RuntimeError('rollback backpack identity readback failed')
            slots[slot] = genuine_guid
            if slots.get(slot) != genuine_guid:
                raise RuntimeError('rollback melee slot readback failed')
            if not melee_visual_change_cases(
                    player, genuine_guid, genuine):
                raise RuntimeError('rollback same-case visual refresh failed')
        except Exception as recovery_exc:
            rollback_error = recovery_exc
        if rollback_error is not None:
            # Keep the authentic baseline reachable.  OFF or a later game-pump
            # restore can retry ChangeWeaponGuise; never claim a rollback which
            # did not pass backpack and native-case readback.
            try:
                player_ref = weakref.ref(player)
                backpack_ref = weakref.ref(backpack)
            except Exception:
                player_ref = lambda: player
                backpack_ref = lambda: backpack
            MELEE_VISUAL[key] = {
                'player_ref': player_ref, 'backpack_ref': backpack_ref,
                'old_guid': genuine_guid, 'old_item': genuine,
                'new_guid': genuine_guid, 'new_item': new_item,
                'slot': slot, 'item_id': item_id, 'lobby_guid': lobby_guid,
                'preserve_guid': True, 'recovery': True,
                'refresh_at': time.time(),
            }
            _v109_log(('visual-swap-recovery', item_id, repr(exc),
                       repr(rollback_error)),
                      'native melee visual item=%d swap failed; authentic '
                      'recovery pending after %r / %r'
                      % (item_id, exc, rollback_error), 1)
            return False
        MELEE_VISUAL.pop(key, None)
        _v109_log(('visual-swap-error', item_id, repr(exc)),
                  'native melee visual item=%d swap rolled back and read '
                  'back authentic item/cases: %r' % (item_id, exc), 2)
        return False

    try:
        player_ref = weakref.ref(player)
        backpack_ref = weakref.ref(backpack)
    except Exception:
        player_ref = None
        backpack_ref = None
    if player_ref is None or backpack_ref is None:
        player_ref = lambda: player
        backpack_ref = lambda: backpack
    if len(MELEE_VISUAL) >= 4 and key not in MELEE_VISUAL:
        oldest = next(iter(MELEE_VISUAL))
        melee_visual_restore(oldest, 'visual-cap')
    MELEE_VISUAL[key] = {
        'player_ref': player_ref, 'backpack_ref': backpack_ref,
        'old_guid': genuine_guid, 'old_item': genuine,
        'new_guid': genuine_guid, 'new_item': new_item,
        'slot': slot, 'item_id': item_id, 'lobby_guid': lobby_guid,
        'preserve_guid': True, 'refresh_at': time.time(),
    }
    try:
        hand = getattr(player, 'hand_model', None)
        model = getattr(player, 'model', None)
        fps_case = getattr(hand, 'weapon_dict', {}).get(genuine_guid) \
            if hand is not None else None
        tps_case = getattr(model, 'weapon_dict', {}).get(genuine_guid) \
            if model is not None else None
        case_names = (type(fps_case).__name__ if fps_case is not None else None,
                      type(tps_case).__name__ if tps_case is not None else None)
    except Exception:
        case_names = (None, None)
    _v109_log(('visual-refresh-preserved', item_id, equip_id, skin_id, guise_id),
              'native melee visual genuine-GUID refresh item=%d guid=%r '
              'equip=%d combat=%d skin=%d guise=%d cases=%r; '
              'switch/damage identity preserved'
              % (item_id, genuine_guid, equip_id, combat_id, skin_id,
                 guise_id, case_names), 2)
    return True


def melee_visual_apply(item_id=None):
    """Dispatch a latest-only native apply; never run it on a worker thread."""
    return native_game_dispatch(
        'v109-melee-visual-apply', melee_visual_apply_on_game, item_id)


def melee_visual_tick():
    """Retry on the game-thread pump for match entry, DLC, and missing cases."""
    try:
        item_id = _v109_int(MELEE_SAVED.get('item_id'), 0) or \
            config_pick('iNativeMelee')
        if not category_enabled('melee') or not item_id:
            melee_visual_restore_all('visual-tick-inactive')
            return False
        record = injected_record(item_id)
        if not record or record[1] != 'melee':
            melee_visual_restore_all('visual-record-missing')
            return False
        return melee_visual_apply(item_id)
    except Exception as exc:
        _v109_log(('visual-tick-error', repr(exc)),
                  'native melee visual tick guarded error=%r' % (exc,), 1)
        return False



# v10.12.3: transactional native combat visuals. Real combat items are
# constructed by the game's factories and committed through IBackpack.
COMBAT_VISUALS = {}
COMBAT_VISUAL_LIMIT = 32
WEAPON_VISUAL_TICK = [0.0]
PLAYPAL_COMBAT_TICK = [0.0]


def combat_values(backpack):
    try:
        values = getattr(backpack, 'values', None)
        return list(values())[:512] if callable(values) else []
    except Exception:
        return []


def combat_slot(backpack, guid):
    if not guid:
        return None
    try:
        query = getattr(backpack, 'QueryEquipSlot', None)
        slot = query(guid) if callable(query) else None
        if slot not in (None, ''):
            return slot
        slots = getattr(backpack, 'slots', None)
        values = slots.values() if callable(getattr(slots, 'values', None)) else slots
        if isinstance(values, dict):
            values = values.values()
        for slot in values or ():
            try:
                if slot.guid == guid:
                    return slot.slot_id
            except Exception:
                continue
    except Exception:
        pass
    return None


def combat_key(player, backpack, kind, slot):
    return (id(player), id(backpack), kind, slot if slot is not None else 0)


def combat_data(item):
    """Return stored item data only; never invent a lobby-to-combat mapping."""
    if item is None:
        return {}
    data = None
    try:
        pack = getattr(item, 'Pack', None)
        if callable(pack):
            packed = pack()
            if isinstance(packed, dict):
                data = packed
    except Exception:
        data = None
    if data is None:
        try:
            pairs = item.items()
            data = pairs if isinstance(pairs, dict) else dict(pairs)
        except Exception:
            data = {}
    if not data:
        # Some host builds expose mapping fields but not items(). Copy only
        # known stored state, never model or ownership flags.
        for field in (
                'guid', 'item_id', 'count', 'skin_item_id', 'guise_item_id',
                'skin_random', 'guise_random', 'part_slots', 'parts',
                'gun_blueprint_id', 'sight_info', 'anim_info', 'sticker',
                'hangings_info', 'ornament_item_id', 'skin_sticker',
                'part_guise_info', 'client_ammo', 'client_grenade_ammo',
                'client_left_ammo', 'server_ammo', 'left_hand_ammo',
                'spec_ammo', 'dye_owner_id', 'color_attr', 'position_attr',
                'dyn_effect_attr', 'sp_effect_attr', 'panpan_lv',
                'extra_attr', 'create_time', 'expire_time'):
            try:
                if hasattr(item, field):
                    value = getattr(item, field)
                    if not callable(value):
                        data[field] = value
            except Exception:
                continue
    try:
        import copy
        return copy.deepcopy(dict(data))
    except Exception:
        return dict(data)


def combat_clone(source, new_guid, changes, combat_item_id=0):
    """Use official factories, not a model-only facade or assumed Pack API."""
    if not new_guid:
        return None
    try:
        iitem = __import__('gshare.iitem',
                           fromlist=['CreateBackpackItemByData',
                                     'CreateBackpackItem'])
        citem = __import__('gclient.gameplay.logic_base.equips.citem',
                           fromlist=['CItem'])
        item_cls = getattr(citem, 'CItem', None)
        if item_cls is None:
            return None
        if source is not None:
            factory = getattr(iitem, 'CreateBackpackItemByData', None)
            if not callable(factory):
                return None
            data = combat_data(source)
            if not data:
                return None
            data.update(changes or {})
            data['guid'] = new_guid
            if combat_item_id:
                data['item_id'] = combat_item_id
            item = factory(item_cls, data)
        else:
            factory = getattr(iitem, 'CreateBackpackItem', None)
            if not callable(factory) or not combat_item_id:
                return None
            item = factory(item_cls, combat_item_id, 1,
                           dict(changes or {}), new_guid)
        if item is None or getattr(item, 'guid', None) != new_guid:
            return None
        return item
    except Exception as exc:
        _v109_log('combat_construct', str(exc)[:160])
        return None


def _v109_combat_restore(key, reason='', refresh=True):
    record = COMBAT_VISUALS.get(key)
    if not record:
        return True
    COMBAT_VISUALS.pop(key, None)
    try:
        player = record['player_ref']()
        backpack = record['backpack_ref']()
        old_item = record.get('old_item')
        new_guid = record['new_guid']
        old_guid = record.get('old_guid', '')
        slot = record.get('slot')
        if player is None or backpack is None:
            return True
        current_new = melee_visual_get(backpack, new_guid)
        current_old = melee_visual_get(backpack, old_guid) if old_guid else None
        slots = getattr(backpack, 'slots', None)
        occupant = slots.get(slot) if slot is not None and slots is not None else None
        if current_new is not record.get('new_item'):
            # A server rebuild, genuine equip, drop, or empty slot is newer
            # authoritative state. Never resurrect the pre-injection item.
            _v109_log('combat_restore_obsolete', reason)
            return True
        if slot is not None and occupant not in (new_guid, old_guid, '', None):
            melee_visual_remove(backpack, new_guid)
            _v109_log('combat_restore_genuine_wins', reason)
            return True
        removed = melee_visual_remove(backpack, new_guid)
        if not removed:
            COMBAT_VISUALS[key] = record
            return False
        if old_item is not None and current_old is None:
            if not backpack.Add(old_item):
                # Best-effort transaction reversal; keep the record only when
                # the injected item is whole again and can be retried safely.
                try:
                    if backpack.Add(record['new_item']):
                        if slot is not None and slots is not None:
                            slots[slot] = new_guid
                        COMBAT_VISUALS[key] = record
                except Exception:
                    pass
                if refresh:
                    melee_visual_refresh(player)
                return False
        if slot is not None and slots is not None:
            slots[slot] = old_guid if old_item is not None else ''
        if refresh:
            melee_visual_refresh(player)
        _v109_log('combat_restore', '%s removed=%s' % (reason, removed))
        return True
    except Exception as exc:
        _v109_log('combat_restore_error', str(exc)[:160])
        return False


def combat_restore_kind(kind, reason='off'):
    for key, record in list(COMBAT_VISUALS.items()):
        if record.get('kind') == kind:
            _v109_combat_restore(key, reason)


# #======================================================================
# //  RPCS.PY
# //
# //  This file is for: RPC DISPATCH + APPLY: the equip RPC interceptors (ApplyMelee, ArmHeroSkin, ArmDisplayItem ...), the striker action RPC partition, the combat prune, the late hook installs.
# //
# //  Part of the split TREACKY BS payload (v2.112).  The runtime
# //  file payload/skins_payload.py is GENERATED: run
# //  tools/build_payload.py after editing these modules.
# #======================================================================
