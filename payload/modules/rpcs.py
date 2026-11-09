# ============================================================
# RPCS.PY (payload feature module)
# PROVIDES: combat_prune, combat_active, _v109_combat_swap, combat_baseline_fields, item_record, weapon_visual_apply_gun, weapon_visual_selections, weapon_visual_tick, playpal_combat_item_id, playpal_combat_apply, playpal_combat_tick, emote_reader_factory, remember_melee_receiver, cached_melee_receiver, ... +177 more | STRIKER_PENDING, STRIKER_PREFLIGHT_CAP, COSMETIC_READBACK_GETTERS, RPC_FLAGS, ENABLE_METHODS, DONE, GATE_FLAGS, FLAG_CLASSES, MEMBER_METHODS, EXTRA_EMOTE_CALLERS, ...
# REQUIRES: shared namespace (config/names/main/game_api/catalog);
#           game modules imported inline, verified against the dumps.
# ABI: boot hero-catalog send lives at module tail (single v842 sender).
# ============================================================
"""RPC dispatch/apply interceptors: equip/hero/emote/execution RPC windows (v109 family), striker apply + bounded retry, equip nonces, panel-invoke outermost chain layer."""

# #======================================================================
# //  RPCS.PY
# //
# //  This file is for: RPC DISPATCH + APPLY: the equip RPC interceptors (ApplyMelee, ArmHeroSkin, ArmDisplayItem ...), the striker action RPC partition, the combat prune, the late hook installs.
# //
# //  Part of the split TREACKY BS payload (v2.112).  The runtime
# //  file payload/skins_payload.py is GENERATED: run
# //  tools/build_payload.py after editing these modules.
# #======================================================================
def combat_prune(current_player=None):
    """Drop dead match scopes and bound retained authentic baselines."""
    for key, record in list(COMBAT_VISUALS.items()):
        try:
            owner = record['player_ref']()
        except Exception:
            owner = None
        if owner is None or (current_player is not None and owner is not current_player):
            COMBAT_VISUALS.pop(key, None)
    while len(COMBAT_VISUALS) >= COMBAT_VISUAL_LIMIT:
        oldest = next(iter(COMBAT_VISUALS), None)
        if oldest is None:
            break
        _v109_combat_restore(oldest, 'combat-cap')


def combat_active(player, backpack, kind, slot, item_id):
    key = combat_key(player, backpack, kind, slot)
    record = COMBAT_VISUALS.get(key)
    if not record or record.get('item_id') != item_id:
        return None
    try:
        new_item = record['new_item']
        if melee_visual_get(backpack, record['new_guid']) is not new_item:
            return None
        if slot is not None and getattr(backpack, 'slots', {}).get(slot) != record['new_guid']:
            return None
        return record
    except Exception:
        return None


def _v109_combat_swap(player, kind, slot, gun_id, old_item, new_item, item_id):
    """Atomically replace one tracked item; rollback construction/slot errors."""
    backpack = getattr(player, 'backpack', None)
    if backpack is None or new_item is None:
        return False
    combat_prune(player)
    old_guid = getattr(old_item, 'guid', '') if old_item is not None else ''
    new_guid = getattr(new_item, 'guid', '')
    key = combat_key(player, backpack, kind, slot)
    removed = False
    added = False
    try:
        if old_item is not None and melee_visual_get(backpack, old_guid) is not old_item:
            return False
        if melee_visual_get(backpack, new_guid) is not None:
            return False
        slots = getattr(backpack, 'slots', None)
        if slot is not None and slots is not None:
            if slots.get(slot) not in (old_guid, '', None):
                return False
        if old_item is not None:
            removed = melee_visual_remove(backpack, old_guid)
            if not removed:
                return False
        if not backpack.Add(new_item):
            raise RuntimeError('native backpack refused combat replacement')
        added = True
        if melee_visual_get(backpack, new_guid) is not new_item:
            raise RuntimeError('combat replacement GUID readback mismatch')
        if slot is not None and slots is not None:
            slots[slot] = new_guid
        COMBAT_VISUALS[key] = {
            'kind': kind, 'gun_id': gun_id, 'slot': slot,
            'old_guid': old_guid, 'new_guid': new_guid,
            'old_item': old_item, 'new_item': new_item,
            'item_id': item_id,
            'player_ref': weakref.ref(player),
            'backpack_ref': weakref.ref(backpack),
        }
        melee_visual_refresh(player)
        _v109_log('combat_swap', '%s item=%s slot=%s' % (kind, item_id, slot))
        return True
    except Exception as exc:
        _v109_log('combat_swap_rollback', str(exc)[:160])
        COMBAT_VISUALS.pop(key, None)
        try:
            if added:
                melee_visual_remove(backpack, new_guid)
            if removed and old_item is not None and melee_visual_get(backpack, old_guid) is None:
                backpack.Add(old_item)
            if slot is not None and getattr(backpack, 'slots', None) is not None:
                backpack.slots[slot] = old_guid if old_item is not None else ''
            melee_visual_refresh(player)
        except Exception:
            pass
        return False


def combat_baseline_fields(target, baseline, changes):
    for field in ('skin_item_id', 'guise_item_id', 'skin_random', 'guise_random'):
        try:
            if baseline is not None and hasattr(baseline, field):
                changes[field] = getattr(baseline, field)
            elif hasattr(target, field):
                changes[field] = getattr(target, field)
        except Exception:
            continue


def item_record(item_id):
    """Return only a live, enabled, injected native item record."""
    try:
        item_id = _v109_int(item_id, 0)
        record = injected_record(item_id) if item_id else None
        return record if record and record[0] == item_id else None
    except Exception:
        return None


def weapon_visual_apply_gun(root, player, gun_id, selection):
    backpack = getattr(player, 'backpack', None)
    getter = getattr(backpack, 'GetByGunId', None)
    if not callable(getter):
        return False
    try:
        current = getter(gun_id)
    except Exception:
        return False
    if current is None:
        return False
    item_id = selection.get('guise') or selection.get('skin')
    if not item_id:
        return False
    slot = combat_slot(backpack, getattr(current, 'guid', ''))
    if slot is None:
        return False
    guid_item_id = selection.get('guise') or selection.get('skin')
    guid_record = item_record(guid_item_id)
    new_guid = getattr(guid_record[2], 'guid', None) if guid_record else None
    if not new_guid:
        return False
    active = combat_active(player, backpack, 'gun', slot, item_id)
    if (active and active.get('new_guid') == new_guid
            and active.get('selection') == dict(selection)):
        try:
            now = time.time()
            hand = getattr(player, 'hand_model', None)
            model = getattr(player, 'model', None)
            present = ((hand is not None and new_guid in getattr(hand, 'weapon_dict', {}))
                       or (model is not None and new_guid in getattr(model, 'weapon_dict', {})))
            if not present and now - active.get('refresh_at', 0.0) >= 2.0:
                if melee_visual_refresh(player):
                    active['refresh_at'] = now
        except Exception:
            pass
        return True
    try:
        changes = {}
        baseline = current
        key = combat_key(player, backpack, 'gun', slot)
        existing = COMBAT_VISUALS.get(key)
        if existing and current is existing.get('new_item'):
            baseline = existing.get('old_item') or current
        combat_baseline_fields(current, baseline, changes)
        expected = {'skin': 0, 'guise': 0}
        for rpc in ('skin', 'guise'):
            selected = selection.get(rpc)
            if not selected:
                continue
            record = item_record(selected)
            if not record or record[1] != 'weapon':
                return False
            row = getattr(record[2], 'item_proto', None) or _v109_row(selected)
            template = melee_template(record[2], row, rpc, selected)
            if not template:
                return False
            field = 'skin_item_id' if rpc == 'skin' else 'guise_item_id'
            changes[field] = selected
            expected[rpc] = template
        if not expected['skin'] and not expected['guise']:
            return False
        if not melee_visual_dlc_ready(root, item_id, expected['guise']):
            return False
        candidate = combat_clone(current, new_guid, changes)
        if candidate is None:
            return False
        if (not bool(getattr(candidate, 'is_gun', False))
                or getattr(candidate, 'gun_id', None) != gun_id
                or getattr(candidate, 'equip_id', None) != getattr(current, 'equip_id', None)):
            return False
        if expected['skin'] and _v109_int(getattr(
                candidate, 'skin_template_id', 0), 0) != expected['skin']:
            return False
        if expected['guise'] and _v109_int(getattr(
                candidate, 'guise_template_id', 0), 0) != expected['guise']:
            return False
        if key in COMBAT_VISUALS:
            _v109_combat_restore(key, 'switch', refresh=False)
        old_item = baseline
        # After restoring a prior injection, its authentic baseline is back.
        if melee_visual_get(backpack, getattr(old_item, 'guid', '')) is not old_item:
            old_item = current if melee_visual_get(
                backpack, getattr(current, 'guid', '')) is current else old_item
        swapped = _v109_combat_swap(player, 'gun', slot, gun_id, old_item,
                                    candidate, item_id)
        if swapped:
            record = COMBAT_VISUALS.get(key)
            if record:
                record['selection'] = dict(selection)
                record['refresh_at'] = time.time()
        return swapped
    except Exception as exc:
        _v109_log('weapon_visual_error', str(exc)[:160])
        return False


def weapon_visual_selections():
    """Read the existing RPC-keyed persisted picks and latest local clicks."""
    selections = {}
    picks = {(rpc, slot): item_id
             for rpc, slot, item_id in config_cosmetic_picks()}
    picks.update(COSMETIC_SAVED)
    for (rpc, gun_id), item_id in picks.items():
        if rpc not in ('ArmGunSkin', 'ArmGunGuise'):
            continue
        kind = 'skin' if rpc == 'ArmGunSkin' else 'guise'
        record = item_record(item_id)
        if not record or record[1] != 'weapon' or not gun_id:
            continue
        row = getattr(record[2], 'item_proto', None) or _v109_row(item_id)
        row_gun_id = _v109_int(_v109_field(row, 'gun_id', 0), 0)
        if row_gun_id and row_gun_id != gun_id:
            continue
        selections.setdefault(gun_id, {})[kind] = item_id
    return selections


def weapon_visual_tick():
    now = time.time()
    if now - WEAPON_VISUAL_TICK[0] < 0.35:
        return None
    WEAPON_VISUAL_TICK[0] = now
    if not category_enabled('weapon'):
        combat_restore_kind('gun', 'weapon_off')
        return None
    root, player = melee_visual_player()
    if player is None:
        return None
    selections = weapon_visual_selections()
    for key, record in list(COMBAT_VISUALS.items()):
        if record.get('kind') == 'gun' and record.get('gun_id') not in selections:
            _v109_combat_restore(key, 'weapon_unselected')
    applied = 0
    for gun_id, selection in selections.items():
        if weapon_visual_apply_gun(root, player, gun_id, selection):
            applied += 1
    return applied


def playpal_combat_item_id(record, item_id):
    if not record:
        return 0
    try:
        skin_mod = __import__('gclient.data.gun_skin_template_data',
                              fromlist=['data'])
        native_item = record[2]
        lobby_row = getattr(native_item, 'item_proto', None) or _v109_row(item_id)
        guise_id = melee_template(native_item, lobby_row, 'guise', item_id)
        skin_id = melee_template(native_item, lobby_row, 'skin', item_id)
        template = guise_id or skin_id
        row = skin_mod.data.get(template) or {}
        combat_id = _v109_int(_v109_field(row, 'panpan_combat_item', 0), 0)
        if not combat_id:
            return 0
        data_mod = __import__('gclient.data.combat_item_data', fromlist=['data'])
        combat_row = data_mod.data.get(combat_id) or {}
        equip_id = _v109_field(combat_row, 'equip_id', combat_id) or combat_id
        weapon_util = __import__('gshare.weapon_util', fromlist=['IsPanpan'])
        return combat_id if weapon_util.IsPanpan(equip_id) else 0
    except Exception:
        return 0


def playpal_combat_apply(item_id):
    root, player = melee_visual_player()
    if player is None:
        return False
    backpack = getattr(player, 'backpack', None)
    record = item_record(item_id)
    if backpack is None or not record or record[1] != 'playpal':
        return False
    native_item = record[2]
    lobby_row = getattr(native_item, 'item_proto', None) or _v109_row(item_id)
    if subtype_name(_v109_field(lobby_row, 'sub_type', 0)) != 'PanPan':
        return False
    try:
        existing_record = None
        current = None
        for rec in COMBAT_VISUALS.values():
            if rec.get('kind') == 'playpal':
                existing_record = rec
                break
        if existing_record:
            candidate = melee_visual_get(backpack, existing_record['new_guid'])
            if candidate is existing_record.get('new_item'):
                current = candidate
        panpans = [item for item in combat_values(backpack)
                   if bool(getattr(item, 'is_panpan', False))]
        if current is None:
            if len(panpans) == 1:
                current = panpans[0]
            elif existing_record and existing_record.get('old_item') in panpans:
                current = existing_record.get('old_item')
            elif len(panpans) > 1:
                return False
        slot = (combat_slot(backpack, getattr(current, 'guid', ''))
                if current is not None else None)
        active = combat_active(player, backpack, 'playpal', slot, item_id)
        if active:
            return True
        baseline = current
        if existing_record and current is existing_record.get('new_item'):
            baseline = existing_record.get('old_item')
        changes = {}
        combat_baseline_fields(current, baseline, changes)
        skin_id = melee_template(native_item, lobby_row, 'skin', item_id)
        guise_id = melee_template(native_item, lobby_row, 'guise', item_id)
        if not skin_id and not guise_id:
            return False
        changes['skin_item_id'] = item_id if skin_id else 0
        changes['guise_item_id'] = item_id if guise_id else 0
        new_guid = getattr(native_item, 'guid', None)
        if not new_guid:
            return False
        try:
            avatar = getattr(root, 'avatar', None)
            manager = getattr(avatar, 'panpan_mgr', None)
            if manager is None:
                avatar = getattr(player, 'avatar', None)
                manager = getattr(avatar, 'panpan_mgr', None)
            info = manager.GetPanpanEnsure(new_guid)
            for field in ('color_attr', 'position_attr', 'dyn_effect_attr',
                          'sp_effect_attr', 'panpan_lv'):
                value = getattr(info, field, None)
                if value is not None:
                    changes[field] = value
        except Exception:
            pass
        if not melee_visual_dlc_ready(root, item_id, guise_id):
            return False
        combat_id = playpal_combat_item_id(record, item_id)
        if not combat_id:
            return False
        candidate = combat_clone(current, new_guid, changes, combat_id)
        if (candidate is None
                or _v109_int(getattr(candidate, 'item_id', 0), 0) != combat_id
                or not bool(getattr(candidate, 'is_panpan', False))):
            return False
        if _v109_int(getattr(candidate, 'skin_template_id', 0), 0) != skin_id:
            return False
        if _v109_int(getattr(candidate, 'guise_template_id', 0), 0) != guise_id:
            return False
        if guise_id and _v109_int(getattr(
                candidate, 'display_guise_item_id', 0), 0) != item_id:
            return False
        if existing_record:
            old_key = combat_key(player, backpack, 'playpal',
                                       existing_record.get('slot'))
            _v109_combat_restore(old_key, 'playpal_switch', refresh=False)
        old_item = baseline
        if old_item is not None and melee_visual_get(
                backpack, getattr(old_item, 'guid', '')) is not old_item:
            if current is not None and melee_visual_get(
                    backpack, getattr(current, 'guid', '')) is current:
                old_item = current
            else:
                return False
        return _v109_combat_swap(player, 'playpal', slot, 0, old_item,
                                 candidate, item_id)
    except Exception as exc:
        _v109_log('playpal_combat_error', str(exc)[:160])
        return False


def playpal_combat_tick():
    now = time.time()
    if now - PLAYPAL_COMBAT_TICK[0] < 0.5:
        return None
    PLAYPAL_COMBAT_TICK[0] = now
    if not category_enabled('playpal'):
        combat_restore_kind('playpal', 'playpal_off')
        return None
    item_id = (_v109_int(PANPAN_SAVED.get('item_id'), 0)
               or config_pick('iNativePlayPal'))
    if not item_id:
        combat_restore_kind('playpal', 'playpal_unselected')
        return None
    return playpal_combat_apply(item_id)


def emote_reader_factory(previous):
    """Reference-style saved-pick readback, restricted to injected emotes."""
    def wrapper(self, *args, **kwargs):
        current = previous(self, *args, **kwargs)
        try:
            if not category_enabled('emote'):
                return current
            hero_id = _v109_int(
                args[0] if args else kwargs.get('hero_id'), 0)
            slot = _v109_int(
                args[1] if len(args) > 1 else kwargs.get('slot'), -1)
            pick = (hero_id, slot)
            item_id = _v109_int(EMOTE_SAVED.get(pick), 0)
            if not item_id:
                return current
            current_id = _v109_int(current, 0)
            if current_id == item_id:
                return current
            if current_id:
                # A later native/genuine equip always wins over our memory.
                EMOTE_SAVED.pop(pick, None)
                persist_pick('E', hero_id, slot, 0)
                return current
            record = injected_record(item_id)
            if not record or record[0] != item_id or record[1] != 'emote':
                EMOTE_SAVED.pop(pick, None)
                persist_pick('E', hero_id, slot, 0)
                return current
            return item_id
        except Exception:
            return current
    return wrapper


def remember_melee_receiver(owner, warehouse=None):
    """Capture the loaded native ApplyMelee owner without a gc/object scan."""
    try:
        if owner is None or not callable(getattr(owner, 'ApplyMelee', None)):
            return None
        if warehouse is None:
            warehouse = getattr(owner, 'warehouse', None)
        if warehouse is None:
            helper = globals().get('method_warehouse')
            warehouse = helper(owner) if callable(helper) else None
        reference = weakref.ref(owner)
        warehouse_ref = weakref.ref(warehouse) if warehouse is not None else None
        MELEE_RECEIVER.update(
            {'ref': reference, 'warehouse': warehouse_ref})
        return owner
    except Exception:
        return None


def cached_melee_receiver(owner):
    """Return only a live member captured for this avatar's warehouse."""
    try:
        reference = MELEE_RECEIVER.get('ref')
        candidate = reference() if callable(reference) else None
        if candidate is None or candidate is owner:
            return None
        if not callable(getattr(candidate, 'ApplyMelee', None)):
            return None
        expected = getattr(owner, 'warehouse', None)
        if expected is None:
            _avatar, expected = native_avatar()
        warehouse_ref = MELEE_RECEIVER.get('warehouse')
        captured = warehouse_ref() if callable(warehouse_ref) else None
        if expected is not None and captured is not expected:
            return None
        return candidate
    except Exception:
        return None


def melee_observations(owner, receiver=None):
    """Snapshot only the RPC owner, real receiver and current native avatar."""
    objects = []
    try:
        avatar, _warehouse = native_avatar()
    except Exception:
        avatar = None
    for value in (owner, receiver, avatar):
        if value is None or any(value is old for old in objects):
            continue
        objects.append(value)
    result = []
    for value in objects:
        try:
            old_melee = getattr(value, 'arm_melee', _V109_MISSING)
            old_random = getattr(value, 'arm_melee_random', _V109_MISSING)
            if old_melee is _V109_MISSING and old_random is _V109_MISSING:
                continue
            result.append((value, old_melee, old_random))
        except Exception:
            continue
    return result


def melee_finish_native(owner, receiver, item_id, guid, random,
                              result, observations, persist=True):
    """Remember verified readback; return None when the RPC has no sync readback."""
    matched = []
    brief = []
    for value, old_melee, old_random in observations:
        try:
            current = getattr(value, 'arm_melee', _V109_MISSING)
            current_random = getattr(
                value, 'arm_melee_random', _V109_MISSING)
            brief.append((type(value).__name__, current, current_random))
            if (current == guid and
                    (current_random is _V109_MISSING or current_random == random)):
                matched.append((value, old_melee, old_random,
                                current, current_random))
        except Exception:
            continue
    if result is False:
        _v109_log(('native-melee-receiver-rejected', item_id, repr(result),
                   repr(brief)),
                  'native ApplyMelee receiver item=%d result=%r readback=%r'
                  % (item_id, result, brief), 1)
        return False
    if not matched:
        # Official PlayerAvatarMember.ApplyMelee only forwards CallServer,
        # discards its result and returns None.  It does not synchronously
        # write arm_melee/arm_melee_random.  No readback is therefore
        # inconclusive, not an RPC rejection: let the tracked injected item
        # continue through the existing bounded local-completion plan.
        _v109_log(('native-melee-receiver-no-readback', item_id, repr(result),
                   repr(brief)),
                  'native ApplyMelee RPC item=%d result=%r has no synchronous '
                  'readback=%r; scoped local completion remains required'
                  % (item_id, result, brief), 1)
        return None
    state = _v109_state
    for value, old_melee, old_random, current, current_random in matched:
        if old_melee != current:
            remember_equip(
                state, item_id, value, 'attr', 'arm_melee', old_melee, current)
        if (current_random is not _V109_MISSING
                and old_random != current_random):
            remember_equip(
                state, item_id, value, 'attr', 'arm_melee_random',
                old_random, current_random)
    melee_remember_pick(item_id, random, persist=persist)
    visual = globals().get('melee_visual_apply')
    if callable(visual):
        visual(item_id)
    _v109_log(('local-equip-native-receiver', item_id),
              'local equip RPC=ApplyMelee item=%d category=melee '
              'native_receiver=True receiver=%s result=%r readback=%r'
              % (item_id, type(receiver).__name__, result, brief), 1)
    return True


def melee_native_receiver(owner, item_id, guid, random=False, persist=True):
    """Call the real avatar/member ApplyMelee receiver when it is available."""
    if MELEE_RECEIVER_DEPTH[0]:
        # The official receiver forwarded here through CallServer.  Returning
        # to that active receiver is mandatory; calling it again recurses.
        return None
    try:
        candidate = owner if callable(getattr(owner, 'ApplyMelee', None)) \
            else cached_melee_receiver(owner)
    except Exception:
        candidate = None
    if candidate is None:
        _v109_log(('native-melee-receiver-missing', item_id),
                  'native ApplyMelee receiver unavailable item=%d; '
                  'bounded field fallback' % item_id, 1)
        return None
    try:
        receiver = getattr(candidate, 'ApplyMelee', None)
        observations = melee_observations(owner, candidate)
        MELEE_RECEIVER_DEPTH[0] += 1
        try:
            result = receiver(guid, random)
        finally:
            MELEE_RECEIVER_DEPTH[0] -= 1
    except Exception as exc:
        _v109_log(('native-melee-receiver-error', item_id, repr(exc)),
                  'native ApplyMelee receiver item=%d error=%r' % (item_id, exc), 1)
        return False
    return melee_finish_native(
        owner, candidate, item_id, guid, random, result, observations,
        persist=persist)


def melee_receiver_factory(previous):
    """Observe one official receiver without re-entering its forwarded RPC."""
    def wrapper(*args, **kwargs):
        owner = args[0] if args else None
        remember_melee_receiver(owner)
        guid = args[1] if len(args) > 1 else kwargs.get('item_guid')
        random = args[2] if len(args) > 2 else kwargs.get('melee_random', False)
        record = injected_record(guid)
        observations = None
        if record and not MELEE_RECEIVER_DEPTH[0]:
            observations = melee_observations(owner, owner)
        MELEE_RECEIVER_DEPTH[0] += 1
        try:
            # Keep the official bound (guid, random) call and all kwargs exact.
            result = previous(*args, **kwargs)
        finally:
            MELEE_RECEIVER_DEPTH[0] -= 1
        if record and observations is not None:
            item_id = record[0]
            completed = melee_finish_native(
                owner, owner, item_id, guid, random, result, observations)
            if completed is None:
                # Official ApplyMelee is RPC-only.  Its forwarded injected
                # CallServer returned to this frame; complete fields once here.
                melee_complete_fields(
                    owner, item_id, guid, random, persist=True)
        elif guid and not MELEE_RECEIVER_DEPTH[0]:
            # A later genuine native equip retires the saved injected pick,
            # just like the established genuine CallServer path.
            if melee_guid_present(owner, guid):
                melee_remember_pick(0)
        return result
    return wrapper


def melee_guid_present(owner, guid):
    try:
        cached = cached_melee_receiver(owner)
        for value, _old, _random in melee_observations(owner, cached):
            if getattr(value, 'arm_melee', _V109_MISSING) == guid:
                return True
    except Exception:
        pass
    return False


def melee_clear_local(owner):
    """Retire only the currently injected melee before a genuine empty RPC.

    ApplyMelee('', random) must still reach the official server.  The local
    GUID written by our RPC-only completion, however, is not server-owned and
    needs its own exact baseline restoration.  Later genuine equipment wins;
    no old baseline is restored when the current GUID is no longer ours.
    """
    try:
        receiver = cached_melee_receiver(owner)
        observations = melee_observations(owner, receiver)
        active = []
        item_ids = []
        for target, _old, _old_random in observations:
            guid = getattr(target, 'arm_melee', None)
            record = injected_record(guid)
            if not record or record[1] != 'melee':
                continue
            active.append((target, guid))
            if record[0] not in item_ids:
                item_ids.append(record[0])
        if not active:
            return False
        restored = 0
        for item_id in item_ids:
            restored += restore_item(_v109_state, item_id)
        remaining = [guid for target, guid in active
                     if getattr(target, 'arm_melee', None) == guid]
        _v109_log(('melee-local-clear', tuple(item_ids), restored,
                   bool(remaining)),
                  'native melee local empty/random cleanup items=%r '
                  'restored=%d remaining=%s'
                  % (item_ids, restored, bool(remaining)), 1)
        return bool(restored) and not remaining
    except Exception as exc:
        _v109_log(('melee-local-clear-error', repr(exc)),
                  'native melee local empty/random cleanup error=%r'
                  % (exc,), 1)
        return False


def melee_complete_fields(owner, item_id, guid, random=False,
                                 persist=True):
    """Complete RPC-only melee state once, on the member and native avatar."""
    try:
        receiver = cached_melee_receiver(owner)
    except Exception:
        receiver = None
    applied = False
    for target, _old, _old_random in melee_observations(owner, receiver):
        operations = [('attr', 'arm_melee', guid)]
        if getattr(target, 'arm_melee_random', _V109_MISSING) \
                is not _V109_MISSING:
            operations.append(('attr', 'arm_melee_random', random))
        try:
            applied = apply_equip(item_id, target, operations) or applied
        except Exception:
            continue
    if not applied:
        return False
    melee_remember_pick(item_id, random, persist=persist)
    visual = globals().get('melee_visual_apply')
    if callable(visual):
        visual(item_id)
    _v109_log(('local-equip', 'ApplyMelee', item_id),
              'local equip RPC=ApplyMelee item=%d category=melee' % item_id, 1)
    return True


def striker_pending_pop(owner, owned_item_id):
    key = (id(owner), _v109_int(owned_item_id, 0))
    pending = STRIKER_PENDING.pop(key, None)
    if not pending:
        return None
    reference, selected, created = pending
    try:
        if reference() is not owner or time.time() - created > 2.0:
            return None
    except Exception:
        return None
    return _v109_int(selected, 0)


def striker_pending_put(owner, owned_item_id, selected_item_id):
    owned_item_id = _v109_int(owned_item_id, 0)
    selected_item_id = _v109_int(selected_item_id, 0)
    if not owned_item_id or not selected_item_id:
        return False
    try:
        reference = weakref.ref(owner)
    except Exception:
        return False
    key = (id(owner), owned_item_id)
    if len(STRIKER_PENDING) >= 32:
        STRIKER_PENDING.pop(next(iter(STRIKER_PENDING)))
    STRIKER_PENDING[key] = (reference, selected_item_id, time.time())
    return True


def striker_subtype(item_id):
    row = _v109_row(item_id)
    value = _v109_int(_v109_field(row, 'sub_type', 0), 0)
    name = subtype_name(value)
    # Official ItemSubType.Suit is 300. The dynamic enum remains preferred;
    # this recovered numeric fallback also covers a late enum load only for a
    # row independently classified as a Striker by its hero_skin_id.
    if (name is None and value == 300
            and _v109_field(row, 'hero_skin_id', None) is not None):
        name = 'Suit'
    return name, value


def striker_is_suit(item_id):
    return striker_subtype(item_id)[0] == 'Suit'


def striker_current_hero(owner):
    try:
        helper = globals().get('_hero_id_deep')
        if callable(helper):
            value = _v109_int(helper(owner), 0)
            if value:
                return value
    except Exception:
        pass
    for name in ('GetHeroId', 'GetCurHeroId'):
        try:
            getter = getattr(owner, name, None)
            value = _v109_int(getter() if callable(getter) else 0, 0)
            if value:
                return value
        except Exception:
            continue
    for name in ('hero_id', 'real_hero_id', 'cur_hero_id', 'arm_hero_id'):
        try:
            value = _v109_int(getattr(owner, name, 0), 0)
            if value:
                return value
        except Exception:
            continue
    return 0


def striker_compact(operations):
    # Multiple selected skins may update one hero's current-action scalar.
    # Keep the last official list value while retaining one genuine baseline.
    compact = {}
    for kind, key, value in operations:
        compact[(kind, key)] = (kind, key, value)
    return list(compact.values())


def striker_verify(item_id, owner, operations, rpc):
    observed = []
    matched = True
    for kind, key, expected in operations:
        ok, actual = path_get(owner, kind, key)
        observed.append(actual)
        matched = matched and ok and actual == expected
    if matched:
        _v109_log(('striker-equip-readback', rpc, item_id),
                  'Striker native RPC=%s item=%d readback=%r'
                  % (rpc, item_id, observed), 2)
        return True
    restore_item(_v109_state, item_id)
    _v109_log(('striker-equip-mismatch', rpc, item_id),
              'Striker native RPC=%s item=%d readback=%r mismatch; baseline restored'
              % (rpc, item_id, observed), 2)
    return False


def striker_delete(item_id, owner, kind, key, rpc):
    ok, old = path_get(owner, kind, key)
    if not ok:
        return False
    if old is _V109_MISSING:
        return True
    record = remember_equip(
        _v109_state, item_id, owner, kind, key, old, DELETE)
    if not path_delete(owner, kind, key):
        restore_record(record)
        return False
    ok, current = path_get(owner, kind, key)
    if ok and current is _V109_MISSING:
        return True
    restore_record(record)
    _v109_log(('striker-delete-mismatch', rpc, item_id),
              'Striker delete RPC=%s item=%d readback failed' % (rpc, item_id), 2)
    return False


def striker_low_level(owner, params, persist=True):
    """Return True when this call contains local content and is terminal."""
    if len(params) != 2:
        return any(injected_record(value) is not None
                   for value in params)
    owned = _v109_int(params[0], 0)
    selected = _v109_int(params[1], 0)
    owned_rec = injected_record(params[0])
    selected_rec = injected_record(params[1]) if selected else None
    if owned_rec is None and selected_rec is None:
        striker_pending_pop(owner, owned)
        if persist and owned > 0:
            hero_id = _v109_int(_v109_field(
                _v109_row(owned), 'hero_id', 0), 0)
            if hero_id:
                cosmetic_remember_pick(
                    'ArmLowLevelSkin', hero_id, 0)
        return False
    if owned <= 0 or selected < 0:
        _v109_log(('striker-low-level-invalid', owned, selected),
                  'Striker low-level invalid owned=%d selected=%d; withheld'
                  % (owned, selected), 2)
        return True
    if not striker_is_suit(owned) or (
            selected and not striker_is_suit(selected)):
        _v109_log(('striker-low-level-row', owned, selected),
                  'Striker low-level rejected non-suit owned=%d selected=%d'
                  % (owned, selected), 2)
        return True
    baseline_item = (owned_rec[0] if owned_rec is not None
                     else selected_rec[0])
    if selected:
        # Official callers pass (owned, selected appearance), then equip owned.
        # Both hall and combat models index this map by the equipped owned ID.
        operations = [('map', ('arm_low_level_skin', owned), selected)]
        success = apply_equip(baseline_item, owner, operations)
        success = success and striker_verify(
            baseline_item, owner, operations, 'ArmLowLevelSkin')
        pending_selected = selected
    else:
        success = striker_delete(
            baseline_item, owner, 'map', ('arm_low_level_skin', owned),
            'ArmLowLevelSkin')
        pending_selected = owned
    if success:
        if selected:
            striker_pending_put(owner, owned, pending_selected)
        else:
            # Official setting toggles use zero as a standalone reset, with no
            # following ArmHeroSkin call. Do not leave a stale two-call pending.
            striker_pending_pop(owner, owned)
        if persist:
            hero_id = _v109_int(_v109_field(
                _v109_row(owned), 'hero_id', 0), 0)
            if hero_id:
                cosmetic_remember_pick(
                    'ArmLowLevelSkin', hero_id, selected)
        _v109_log(('striker-low-level', owned, selected),
                  'Striker low-level owned=%d selected=%d map/delete readback OK'
                  % (owned, selected), 2)
    return True


def striker_level_info(item_id):
    """Return the official (base item, level) mapping when one exists."""
    try:
        cdata = sys.modules.get('gclient.util.cdata_util')
        resolver = getattr(cdata, 'ItemId2BaseLevelItem', None)
        mapping = resolver() if callable(resolver) else None
        info = mapping.get(item_id) if callable(getattr(mapping, 'get', None)) else None
        if not isinstance(info, (tuple, list)) or len(info) != 2:
            return None
        base = _v109_int(info[0], 0)
        level = _v109_int(info[1], -1)
        return (base, level) if base > 0 and level >= 0 else None
    except Exception:
        return None


def striker_evolution_family(item_id):
    """Return the official bounded ``(level, item)`` family for one suit.

    This is the same lobby_item_upgrade_data table consumed by
    IHallItems.GetUpgradeItemInfo.  The cdata family helper is only a fallback
    for a delayed table load; no numeric ID or maximum-level guess is made.
    """
    info = striker_level_info(item_id)
    if not info:
        return ()
    base, _selected_level = info
    row = _v109_row(item_id)
    expected_hero = _v109_int(_v109_field(row, 'hero_id', 0), 0)
    candidates = []
    try:
        module = sys.modules.get('gclient.data.lobby_item_upgrade_data')
        table = getattr(module, 'data', None) if module is not None else None
        proto = table.get(base) if callable(getattr(table, 'get', None)) else None
        if proto is None and callable(getattr(table, 'get', None)):
            proto = table.get(str(base))
        items = getattr(proto, 'items', None)
        if callable(items):
            for level, sub_proto in list(items())[:64]:
                candidate = _v109_int(
                    _v109_field(sub_proto, 'item_id', 0), 0)
                candidates.append((_v109_int(level, -1), candidate))
    except Exception:
        candidates = []
    if not candidates:
        try:
            cdata = sys.modules.get('gclient.util.cdata_util')
            resolver = getattr(cdata, 'BaseItemId2AllLevelItems', None)
            values = resolver(base) if callable(resolver) else ()
            for candidate in list(values or ())[:64]:
                candidate = _v109_int(candidate, 0)
                candidate_info = striker_level_info(candidate)
                if candidate_info:
                    candidates.append((candidate_info[1], candidate))
        except Exception:
            return ()
    if not candidates or len(candidates) > 32:
        _v109_log(('striker-evolution-family-bound', base, len(candidates)),
                  'Striker evolution family base=%d entries=%d exceeds safe bounds'
                  % (base, len(candidates)), 1)
        return ()
    family = []
    seen = set()
    for level, candidate in candidates:
        candidate_info = striker_level_info(candidate)
        candidate_row = _v109_row(candidate)
        candidate_hero = _v109_int(
            _v109_field(candidate_row, 'hero_id', 0), 0)
        if (level < 0 or not candidate or candidate in seen
                or not candidate_info or candidate_info[0] != base
                or candidate_row is None or not striker_is_suit(candidate)
                or (expected_hero and candidate_hero
                    and candidate_hero != expected_hero)):
            _v109_log(('striker-evolution-family-invalid', base, candidate),
                      'Striker evolution family rejected base=%d candidate=%d'
                      % (base, candidate), 1)
            return ()
        seen.add(candidate)
        family.append((level, candidate))
    if item_id not in seen:
        return ()
    family.sort()
    return tuple(family)


def striker_prepare_evolution(owner, item_id):
    """Make the authentic family visible before the official max-level query.

    Vault list injection is deliberately batched.  Without this focused step,
    clicking an already-visible base card can let the official UI query a
    partially injected family and legitimately choose a lower level.
    """
    family = striker_evolution_family(item_id)
    if not family:
        return ()
    level_info = striker_level_info(item_id)
    base = level_info[0] if level_info else family[0][1]
    try:
        warehouse = getattr(owner, 'warehouse', None)
        if warehouse is None:
            _native, warehouse = native_avatar()
        if warehouse is None:
            return ()
        state = get_state(warehouse)
        genuine_check = getattr(warehouse, '_HasItemById', None)
        ready = True
        for _level, candidate in family:
            if injected_record(candidate) is not None:
                continue
            genuine = False
            if callable(genuine_check):
                try:
                    genuine = bool(genuine_check(candidate, True))
                except Exception:
                    genuine = False
            if genuine:
                continue
            inserted = _v109_insert(warehouse, state, candidate, 'striker')
            if not inserted and injected_record(candidate) is None:
                ready = False
        _v109_log(('striker-evolution-family', base,
                   tuple(item for _level, item in family), ready),
                  'Striker evolution family base=%d items=%r synchronously_ready=%s'
                  % (base, tuple(item for _level, item in family), ready), 2)
        return family if ready else ()
    except Exception as exc:
        _v109_log(('striker-evolution-family-error', item_id, repr(exc)),
                  'Striker evolution family preparation item=%d error=%r'
                  % (item_id, exc), 1)
        return ()


def striker_evolution_item(owner, item_id):
    """Resolve the highest available level after authentic family preparation."""
    item_id = _v109_int(item_id, 0)
    info = striker_level_info(item_id)
    if not info:
        return item_id
    family = striker_prepare_evolution(owner, item_id)
    try:
        warehouse = getattr(owner, 'warehouse', None)
        resolver = getattr(warehouse, 'GetUpgradeItemInfo', None)
        if not callable(resolver):
            return item_id
        base, selected_level = info
        owned_level, owned_item_id = resolver(
            base, include_experience_item=True)
        owned_level = _v109_int(owned_level, -1)
        owned_item_id = _v109_int(owned_item_id, 0)
        if owned_item_id and owned_level >= selected_level:
            if family:
                maximum_level, maximum_item = family[-1]
                _v109_log(('striker-max-level', base, selected_level,
                           owned_level, owned_item_id),
                          'Striker maximum query base=%d requested_level=%d '
                          'resolved_level=%d item=%d official_maximum=%r'
                          % (base, selected_level, owned_level, owned_item_id,
                             (maximum_level, maximum_item)), 2)
            return owned_item_id
    except Exception:
        pass
    return item_id


def striker_hero_skin(owner, params, persist=True, retry=False):
    """Complete ordinary equips at max level; preserve explicit appearance choices."""
    if len(params) != 2:
        return any(injected_record(value) is not None
                   for value in params)
    hero_id = _v109_int(params[0], 0)
    owned = _v109_int(params[1], 0)
    owned_rec = injected_record(params[1])
    pending = striker_pending_pop(owner, owned)
    if owned_rec is None and pending is None:
        if persist and hero_id > 0:
            cosmetic_remember_pick('ArmHeroSkin', hero_id, 0)
            cosmetic_remember_pick('ArmLowLevelSkin', hero_id, 0)
        return False
    # An explicit ArmLowLevelSkin sequence equips owned and maps owned to the
    # requested appearance. Ordinary direct equips instead use the authentic
    # highest available evolution; they must not inherit a stale lower override.
    selected = owned if pending is not None else striker_evolution_item(
        owner, owned)
    appearance = pending if pending is not None else selected
    # An official low-level call can carry either the automatic maximum or an
    # explicit lower/twin appearance.  Only the former activates max features.
    maximum = (selected if pending is None
               else striker_evolution_item(owner, owned))
    kind, sub_type = striker_subtype(owned)
    selected_kind, selected_sub_type = striker_subtype(selected)
    appearance_kind, _appearance_sub_type = striker_subtype(appearance)
    valid = hero_id > 0 and owned > 0 and selected > 0 and appearance > 0
    if pending is not None:
        valid = valid and kind == 'Suit' and appearance_kind == 'Suit'
    if kind == 'Suit':
        valid = valid and selected_kind == 'Suit'
    else:
        valid = valid and pending is None and kind in (
            'Head', 'Body', 'Hair', 'Mask', 'Mustache', 'Watch')
        selected = appearance = owned
        selected_sub_type = sub_type
    for item_id in (owned, selected, appearance):
        row_hero = _v109_int(_v109_field(_v109_row(item_id), 'hero_id', 0), 0)
        if row_hero and row_hero != hero_id:
            valid = False
    if not valid:
        _v109_log(('striker-skin-invalid', hero_id, owned, selected, appearance),
                  'Striker skin invalid hero=%d owned=%d equipped=%d appearance=%d kind=%r; withheld'
                  % (hero_id, owned, selected, appearance, kind), 2)
        return True
    pending_rec = injected_record(pending) if pending is not None else None
    baseline_item = (owned_rec[0] if owned_rec is not None
                     else pending_rec[0] if pending_rec is not None
                     else _v109_int(selected, 0))
    operations = []
    if kind == 'Suit':
        operations.append(('hero_info', ('hero_infos', hero_id, 'skin_item_id'), selected))
        if pending is not None:
            operations.append(('map', ('arm_low_level_skin', owned), pending))
        else:
            ok, lower = path_get(
                owner, 'map', ('arm_low_level_skin', selected))
            if ok and lower:
                operations.append(('map', ('arm_low_level_skin', selected), 0))
    # v2.107: arm_clothes is the GLOBAL outfit map - writing every
    # restored hero's suit here made the lobby doll wear the wrong
    # hero's suit ('loads wrong character skin').  Only the currently
    # displayed hero's suit may touch arm_clothes; the other heroes'
    # hero_infos data still restores (per-hero, correct).
    _cur2107 = 0
    try:
        _cch2107 = globals().get('striker_current_hero')
        _cur2107 = _cch2107(owner) if callable(_cch2107) else 0
    except Exception:
        _cur2107 = 0
    if not _cur2107 or _cur2107 == hero_id:
        operations.append(
            ('map', ('arm_clothes', selected_sub_type), selected))
    operations = striker_compact(operations)
    if apply_equip(baseline_item, owner, operations):
        verified = striker_verify(
            baseline_item, owner, operations, 'ArmHeroSkin')
        if verified:
            # v2.108: local field writes are invisible to other
            # players - also arm the skin through the game's own
            # equip verb so the SERVER records it (the round-125
            # report: teammates see the default while the join
            # team action - whose genuine RPC forwards - shows
            # fine).  The equip-by-game dedupes per (pick, hero,
            # avatar) and defers 0.5s off the game frame.
            try:
                _arm2109 = globals().get('server_arm')
                if callable(_arm2109):
                    _arm2109(owner, hero_id, selected)
            except Exception:
                pass
            try:
                # v2.89: the MODEL builder keys on the hero-skin PROTO
                # (hero_skin_id - the small int, e.g. 19/35), NOT the item id.
                # Without it OnReloadModel dies with KeyError(None) (the
                # half-built GIANT model) and the skin never renders (effects
                # only).  Resolve hero_skin_id from HERO_SKIN_INFO first, then
                # the lobby row, write hero_skin_proto + skin_proto and shadow
                # the avatar's cached_property so the next model read sees it.
                _proto288 = 0
                try:
                    _hs288 = (globals().get('HERO_SKIN_INFO') or {}).get(
                        selected) or {}
                    _proto288 = _v109_int(_hs288.get('hero_skin_id'), 0)
                except Exception:
                    _proto288 = 0
                if not _proto288:
                    for _f288 in ('hero_skin_id', 'skin_proto_id', 'skin_proto',
                                  'hero_skin_proto', 'skin_id', 'proto_id'):
                        try:
                            _proto288 = _v109_int(
                                _v109_field(_v109_row(selected), _f288, 0), 0)
                        except Exception:
                            _proto288 = 0
                        if _proto288:
                            break
                if _proto288:
                    for _k288 in ('hero_skin_proto', 'skin_proto'):
                        try:
                            path_set(
                                owner, 'hero_info',
                                ('hero_infos', hero_id, _k288), _proto288)
                        except Exception:
                            pass
                    try:
                        # v2.91: mirror the pick into the menu key so the
                        # v2.50-era forces (fps arms/unit model) and the menu
                        # see game-window equips exactly like menu picks.
                        _sids291 = (globals().get('HERO') or {}).get(
                            hero_id) or []
                        for _i291, _it291 in enumerate(_sids291[1:], 1):
                            if _v109_int(_it291, 0) == selected:
                                sync_attrs['iHeroSkin_%d' % hero_id] = _i291
                                break
                    except Exception:
                        pass
                    try:
                        # v2.92: THE METHOD (the v2.50 ZeLeWin arm-clothes
                        # channel).  The map write mutates arm_clothes in
                        # place and never fires _on_set_arm_clothes - the
                        # game's arms-model driver.  Re-assign the merged
                        # CArmClothes({300: sid}) so the game rebuilds the
                        # FPS arms (and the lobby doll) from the pick.
                        # v2.107: that rebuild belongs to the CURRENT
                        # hero only - a restored suit for another hero
                        # must not rebuild the doll/arms (the saver bug).
                        _cur2107b = 0
                        try:
                            _cch2107b = globals().get(
                                'striker_current_hero')
                            _cur2107b = _cch2107b(owner) \
                                if callable(_cch2107b) else 0
                        except Exception:
                            _cur2107b = 0
                        _acfn292 = None
                        if not _cur2107b or _cur2107b == hero_id:
                            _acfn292 = globals().get('_zle_arm_clothes')
                        _ac292 = _acfn292(
                            selected,
                            getattr(owner, 'arm_clothes', None)
                        ) if callable(_acfn292) else (None, 0)
                        if _ac292 and _ac292[0] is not None:
                            # v2.93: _on_set_arm_clothes lives on the MODEL
                            # component (cimp_model), not the avatar.
                            for _t293 in (getattr(owner, 'model', None),
                                          getattr(owner, 'hand_model', None),
                                          owner):
                                if _t293 is None:
                                    continue
                                try:
                                    _t293.arm_clothes = _ac292[0]
                                except Exception:
                                    _acf292 = getattr(
                                        _t293, 'ChangeArmClothes', None)
                                    if callable(_acf292):
                                        _acf292(_ac292[0])
                    except Exception:
                        pass
                    try:
                        # FPSARMS v1: every verified striker equip (vault
                        # click, boot restore, menu equip) rebuilds the FPS
                        # hands through the arm-clothes dispatch.  Lobby
                        # equips no-op (scene gate) - the ZLSKIN doll path
                        # owns the lobby.
                        _fpsarms_refresh(owner, hero_id, selected)
                    except Exception:
                        pass
                    try:
                        setattr(owner, 'hero_skin_proto', _proto288)
                    except Exception:
                        try:
                            owner.__dict__['hero_skin_proto'] = _proto288
                        except Exception:
                            pass
            except Exception:
                pass
            if persist and kind == 'Suit':
                cosmetic_remember_pick(
                    'ArmHeroSkin', hero_id, selected)
                cosmetic_remember_pick(
                    'ArmLowLevelSkin', hero_id,
                    appearance if appearance != selected else 0)
            if appearance == maximum:
                striker_enable_max_features(
                    owner, hero_id, selected, appearance, persist=persist)
            # ArmHeroSkin can complete after the native hero broadcast.  Queue
            # a fresh official body+hands reload for this still-current hero.
            striker_request_combat_refresh(owner, hero_id)
        if selected != owned:
            _v109_log(('striker-evolution-equip', hero_id, owned, selected),
                      'Striker native evolution hero=%d requested=%d equipped=%d '
                      'using official highest-owned level'
                      % (hero_id, owned, selected), 2)
    else:
        _v109_log(('striker-skin-apply', hero_id, owned),
                  'Striker skin hero=%d owned=%d native fields unavailable in '
                  'this native state; transaction rolled back, nothing written'
                  % (hero_id, owned), 2)
        if not retry:
            # Not a rejection: the official hero detail channel may simply not
            # exist yet (startup restore races the native row creation).
            striker_retry(owner, hero_id, owned, pending, persist)
    return True


STRIKER_PENDING = {}



def striker_apply(live, hero_id, owned, pending=None,
                        persist=True, retry=False):
    """Retry-time striker apply (reconstructed - this wrapper was called by
    striker_retry but never defined; every retry died with NameError
    and only logged 'striker-retry-error'). Restores the deferred pending
    selection (popped when the first attempt was abandoned) and re-runs the
    validated hero-skin path from scratch."""
    try:
        if pending is not None:
            striker_pending_put(live, owned, pending)
        return striker_hero_skin(live, [hero_id, owned],
                                       persist=persist, retry=retry)
    except Exception as exc:
        _v109_log(('striker-apply-error', hero_id, repr(exc)),
                  'Striker apply hero=%d owned=%d failed: %r'
                  % (hero_id, owned, exc), 2)
        return False

def striker_retry(owner, hero_id, owned, pending, persist, delay=None):
    """Re-run a striker equip after the official hero detail data arrives.

    Device evidence (nexora_debug-8.txt line 1025, r4 build): the startup
    restore applied saved picks in the same batch that created their native
    rows, and the write was refused with "native fields unavailable; withheld"
    before `native list=detail:623 complete` had run.  `path_get` cannot
    read a `hero_infos[hero_id]` entry that does not exist yet, so the whole
    transaction was abandoned even though the pick was perfectly valid and
    applied a few seconds later by the next event.

    The readback gate is correct and stays: nothing is written speculatively.
    We only stop throwing the request away.  A bounded, deduplicated retry is
    armed on the native timer and re-validates everything from scratch.
    """
    if hero_id <= 0:
        return False
    key = (hero_id, owned, pending)
    record = STRIKER_PENDING.get(key)
    attempts = int(record.get('attempts', 0)) if record else 0
    if attempts >= STRIKER_RETRY_LIMIT:
        STRIKER_PENDING.pop(key, None)
        _v109_log(('striker-retry-exhausted', hero_id, owned),
                  'Striker skin hero=%d owned=%d still unavailable after %d '
                  'native retries; withheld' % (hero_id, owned, attempts), 2)
        return False
    if record and record.get('timer'):
        return True
    try:
        timer = sys.modules.get('Timer')
        if timer is None:
            timer = __import__('Timer')
        add = getattr(timer, 'addTimer', None)
        if not callable(add):
            raise RuntimeError('Timer.addTimer unavailable')
    except Exception:
        # No native scheduler: leave it to the next native event/read.
        return False
    try:
        owner_ref = weakref.ref(owner)
    except Exception:
        owner_ref = lambda: owner
    entry = {'attempts': attempts + 1, 'timer': True}
    STRIKER_PENDING[key] = entry

    def _retry():
        try:
            entry['timer'] = False
            STRIKER_PENDING.pop(key, None)
            live = owner_ref()
            if live is None:
                return
            if not category_enabled('striker'):
                return
            striker_apply(live, hero_id, owned, pending=pending,
                                persist=persist, retry=True)
        except Exception as exc:
            _v109_log(('striker-retry-error', hero_id, repr(exc)),
                      'Striker retry hero=%d failed: %r' % (hero_id, exc), 2)

    try:
        add(STRIKER_RETRY_DELAY if delay is None else delay, _retry)
        _v109_log(('striker-defer', hero_id, owned, attempts + 1),
                  'Striker skin hero=%d owned=%d deferred for native hero '
                  'detail readiness (attempt %d/%d); nothing written'
                  % (hero_id, owned, attempts + 1,
                     STRIKER_RETRY_LIMIT), 2)
        return True
    except Exception:
        entry['timer'] = False
        STRIKER_PENDING.pop(key, None)
        return False


def striker_info_item(avatar, hero_id, field='skin_item_id'):
    """Read the official CHeroInfo item channel before its attr fallback."""
    try:
        info = getattr(avatar, 'hero_infos').get(hero_id)
        if info is None:
            return None
        try:
            value = info[field]
        except Exception:
            value = getattr(info, field)
        return _v109_int(value, 0)
    except Exception:
        return None


def striker_window_context(window):
    """Authenticate one explicit HeroSkinWindow.UseSkinImp selection."""
    try:
        if not category_enabled('striker'):
            return None
        getter = getattr(window, 'GetCurSelectNode', None)
        node = getter() if callable(getter) else None
        data = getattr(node, 'data', None)
        item_id = _v109_int(_v109_field(data, 'skin_item_id', 0), 0)
        record = injected_record(item_id)
        if (not record or record[1] != 'striker'
                or not striker_is_suit(item_id)):
            return None
        avatar, _warehouse = native_avatar()
        hero_id = _v109_int(getattr(window, 'hero_id', 0), 0) or _v109_int(
            _v109_field(_v109_row(item_id), 'hero_id', 0), 0)
        row_hero = _v109_int(_v109_field(_v109_row(item_id), 'hero_id', 0), 0)
        if (avatar is None or hero_id <= 0
                or (row_hero and row_hero != hero_id)):
            return None
        before = striker_info_item(avatar, hero_id)
        if before is None:
            return None
        expected = striker_evolution_item(avatar, item_id)
        return avatar, hero_id, item_id, expected, before
    except Exception:
        return None


def striker_refresh_ui(window, hero_id, old_item_id, new_item_id):
    """Use the native skin-event/UI refresh methods after local completion."""
    refreshed = False
    try:
        handler = getattr(window, 'OnArmHeroSkinItemId', None)
        if callable(handler):
            handler(hero_id, old_item_id, new_item_id)
            refreshed = True
    except Exception:
        pass
    if not refreshed:
        try:
            refresh = getattr(window, 'RefreshSpecifySkinNode', None)
            if callable(refresh):
                for item_id in (old_item_id, new_item_id):
                    refresh(hero_id, item_id)
                refreshed = True
        except Exception:
            pass
        try:
            refresh = getattr(window, 'RefreshPanelBuy', None)
            if callable(refresh):
                refresh()
                refreshed = True
        except Exception:
            pass
    try:
        refresh = getattr(window, 'RefreshEquipState', None)
        if callable(refresh):
            refresh(True)
            refreshed = True
    except Exception:
        pass
    return refreshed


def striker_model_state(model, sub_type):
    """Read the official suit -> actual body -> DLC -> model resolution."""
    slot = body = dlc_id = need_download = model_id = real_model_id = None
    try:
        clothes = getattr(model, 'arm_clothes', None)
        if callable(getattr(clothes, 'get', None)):
            slot = clothes.get(sub_type)
    except Exception:
        pass
    try:
        getter = getattr(model, 'GetCurBodyItem', None)
        if callable(getter):
            body = getter()
    except Exception:
        pass
    try:
        getter = getattr(model, '_GetClothesDownloadInfo', None)
        if callable(getter):
            _body, dlc_id, need_download = getter()
    except Exception:
        pass
    try:
        getter = getattr(model, 'GetModelUnitID', None)
        if callable(getter):
            model_id = getter()
    except Exception:
        pass
    try:
        real_model_id = getattr(model, 'real_model_id', None)
    except Exception:
        pass
    return slot, body, dlc_id, need_download, model_id, real_model_id


def striker_refresh_model(window, avatar, hero_id, item_id):
    """Run the official hall-model consumer and authentic DLC download path.

    A Wi-Fi-only UI request is insufficient on a cellular device. Queue the
    real item/DLC through the established downloader, then leave a bounded
    weak-reference pending entry. Only the official readiness gate can trigger
    the later model refresh; no model or DLC result is forced here.
    """
    refreshed = False
    requested = []
    download_results = []
    before = after = None
    pending_key = (id(avatar), hero_id, item_id)
    try:
        if not category_enabled('striker'):
            return False
        if striker_info_item(avatar, hero_id) != item_id:
            return False                 # a genuine/later selection wins
        _kind, sub_type = striker_subtype(item_id)
        ok, current = path_get(
            avatar, 'map', ('arm_clothes', sub_type))
        if not ok or current != item_id:
            return False
        try:
            helper = globals().get('_game_genv')
            root = helper() if callable(helper) else globals().get('genv')
        except Exception:
            root = globals().get('genv')
        manager = getattr(root, 'hall_model_mgr', None)
        model = getattr(manager, 'main_npc', None)
        handler = getattr(manager, 'OnAvatarArmClothesChanged', None)
        if model is None or not callable(handler):
            _v109_log(('striker-model-consumer-unavailable', hero_id, item_id),
                      'Striker native model consumer unavailable hero=%d item=%d'
                      % (hero_id, item_id), 2)
            return False
        before = striker_model_state(model, sub_type)
        handler(sub_type)                # official SetArmClothes + ShowModel
        refreshed = True
        after = striker_model_state(model, sub_type)
        if after[3]:
            download = globals().get('try_dlc_download')
            for selected in (item_id, after[1]):
                selected = _v109_int(selected, 0)
                if not selected or selected in requested:
                    continue
                requested.append(selected)
                dlc_ids = ([after[2]] if selected == _v109_int(after[1], 0)
                           and after[2] else [])
                try:
                    result = (download(selected, dlc_ids)
                              if callable(download) else ['unavailable'])
                except Exception as exc:
                    result = ['guarded', repr(exc)]
                download_results.append((selected, result))
            try:
                avatar_ref = weakref.ref(avatar)
            except Exception:
                avatar_ref = None
            if avatar_ref is not None:
                if (len(STRIKER_MODEL_PENDING) >= 8
                        and pending_key not in STRIKER_MODEL_PENDING):
                    oldest = next(iter(STRIKER_MODEL_PENDING))
                    STRIKER_MODEL_PENDING.pop(oldest, None)
                old_pending = STRIKER_MODEL_PENDING.get(pending_key)
                created = old_pending[4] if old_pending else time.time()
                STRIKER_MODEL_PENDING[pending_key] = (
                    avatar_ref, hero_id, item_id,
                    _v109_int(after[1], 0), created)
        else:
            STRIKER_MODEL_PENDING.pop(pending_key, None)
        actual_item = after[1] or item_id
        expected_model = _v109_field(
            _v109_row(actual_item), 'model_id', None)
        _v109_log(('striker-model-local-rpc-refresh', hero_id, item_id),
                  'Striker native model local-RPC refresh hero=%d item=%d '
                  'before(slot/body/dlc/need/model/real)=%r after=%r '
                  'expected_model=%r dlc_requested=%r dlc_result=%r '
                  'pending=%s refreshed=%s'
                  % (hero_id, item_id, before, after, expected_model,
                     requested, download_results,
                     pending_key in STRIKER_MODEL_PENDING, refreshed), 4)
    except Exception as exc:
        _v109_log(('striker-model-refresh-error', hero_id, item_id, repr(exc)),
                  'Striker native model refresh guarded error=%r' % (exc,), 2)
    return refreshed


def striker_model_tick():
    """Refresh only after the authentic gate clears for the same selection."""
    if not STRIKER_MODEL_PENDING:
        return False
    if not category_enabled('striker'):
        STRIKER_MODEL_PENDING.clear()
        return False
    now = time.time()
    refreshed = False
    for key, record in list(STRIKER_MODEL_PENDING.items())[:8]:
        avatar_ref, hero_id, item_id, pending_body, created = record
        if now - created > STRIKER_MODEL_PENDING_SECONDS:
            STRIKER_MODEL_PENDING.pop(key, None)
            _v109_log(('striker-model-dlc-timeout', hero_id, item_id),
                      'Striker native model DLC wait expired hero=%d item=%d; '
                      'authentic gate unchanged' % (hero_id, item_id), 1)
            continue
        avatar = avatar_ref()
        if avatar is None or striker_info_item(avatar, hero_id) != item_id:
            STRIKER_MODEL_PENDING.pop(key, None)
            continue
        _kind, sub_type = striker_subtype(item_id)
        ok, current = path_get(
            avatar, 'map', ('arm_clothes', sub_type))
        if not ok or current != item_id:
            STRIKER_MODEL_PENDING.pop(key, None)
            continue
        try:
            helper = globals().get('_game_genv')
            root = helper() if callable(helper) else globals().get('genv')
        except Exception:
            root = globals().get('genv')
        manager = getattr(root, 'hall_model_mgr', None)
        model = getattr(manager, 'main_npc', None)
        if model is None:
            continue
        before = striker_model_state(model, sub_type)
        if before[3] is not False:
            continue                     # missing or unknown readiness waits
        if not striker_refresh_model(None, avatar, hero_id, item_id):
            continue
        after = striker_model_state(model, sub_type)
        if after[3] is False:
            refreshed = True
            _v109_log(('striker-model-dlc-ready', hero_id, item_id),
                      'Striker native model DLC-ready refresh hero=%d item=%d '
                      'pending_body=%d before=%r after=%r'
                      % (hero_id, item_id, pending_body, before, after), 2)
    return refreshed


def striker_apply_window(window, context):
    """Refresh the authentic evolved equip after the original UI call runs.

    A changed answer other than the official evolution result is genuine-later
    state and wins. Only the selected row's expected local result, or unchanged
    state, may be completed/refreshed here.
    """
    avatar, hero_id, item_id, expected, before = context
    try:
        if not category_enabled('striker'):
            return False
        record = injected_record(item_id)
        if not record or record[1] != 'striker':
            return False
        getter = getattr(window, 'GetCurSelectNode', None)
        node = getter() if callable(getter) else None
        current_item = _v109_int(_v109_field(
            getattr(node, 'data', None), 'skin_item_id', 0), 0)
        if current_item != item_id:
            return False
        after = striker_info_item(avatar, hero_id)
        if after is None:
            return False
        if after == expected:
            if before == expected:
                return False
            # The original UI call can reach our local ArmHeroSkin handler.
            # Unlike a genuine server RPC, that path has no server response to
            # refresh the window. Refresh the actual evolved item, not merely
            # the clicked base row.
            _kind, sub_type = striker_subtype(expected)
            ok, clothes = path_get(
                avatar, 'map', ('arm_clothes', sub_type))
            if not ok or clothes != expected:
                return False
            refreshed = striker_refresh_ui(
                window, hero_id, before, expected)
            striker_refresh_model(window, avatar, hero_id, expected)
            _v109_log(('striker-ui-local-rpc-refresh', hero_id, item_id, expected),
                      'Striker native UI local-RPC refresh hero=%d requested=%d '
                      'equipped=%d old=%d refreshed=%s'
                      % (hero_id, item_id, expected, before, refreshed), 4)
            return True
        if after != before:
            _v109_log(('striker-ui-genuine-later', hero_id, before, after),
                      'Striker native UI genuine-later hero=%d before=%d after=%d; local fallback skipped'
                      % (hero_id, before, after), 2)
            return False
        # This fallback is an explicit direct suit selection, not a pending
        # low-level sequence. Do not let stale pending state substitute a row.
        striker_pending_pop(avatar, item_id)
        striker_hero_skin(avatar, (hero_id, item_id))
        current = striker_info_item(avatar, hero_id)
        _kind, sub_type = striker_subtype(expected)
        ok, clothes = path_get(
            avatar, 'map', ('arm_clothes', sub_type))
        if current != expected or not ok or clothes != expected:
            restore_item(_v109_state, item_id)
            _v109_log(('striker-ui-readback-failed', hero_id, item_id, expected),
                      'Striker native UI hero=%d requested=%d expected=%d '
                      'official readback failed; baseline restored'
                      % (hero_id, item_id, expected), 2)
            return False
        refreshed = striker_refresh_ui(
            window, hero_id, before, expected)
        striker_refresh_model(window, avatar, hero_id, expected)
        _v109_log(('striker-ui-equip', hero_id, item_id, expected),
                  'Striker native UI equip hero=%d requested=%d equipped=%d '
                  'old=%d readback=OK refreshed=%s'
                  % (hero_id, item_id, expected, before, refreshed), 4)
        return True
    except Exception as exc:
        _v109_log(('striker-ui-equip-error', repr(exc)),
                  'Striker native UI equip guarded error=%r' % (exc,), 2)
        return False


def striker_skin_ui_factory(previous):
    def wrapper(self, *args, **kwargs):
        try:
            context = striker_window_context(self)
        except Exception:
            context = None
        result = previous(self, *args, **kwargs)
        if context is not None:
            try:
                striker_apply_window(self, context)
            except Exception:
                pass
        return result
    return wrapper


def striker_transform_binding(item_id):
    try:
        module = sys.modules.get('gclient.util.hero_transform_util')
        resolver = getattr(module, 'GetHeroTransformBoundSkin', None)
        if not callable(resolver):
            return None
        binding = resolver(item_id)
        if not isinstance(binding, (tuple, list)) or len(binding) != 2:
            return None
        hero_id = _v109_int(binding[0], 0)
        skin_id = _v109_int(binding[1], 0)
        return (hero_id, skin_id) if hero_id > 0 and skin_id > 0 else None
    except Exception:
        return None


def striker_feature_trace(owner, hero_id, equipped, appearance,
                                transform_item=0):
    """Bounded authentic maximum-feature evidence for the next device log."""
    try:
        row = _v109_row(appearance)
        skin_id = _v109_int(_v109_field(row, 'hero_skin_id', 0), 0)
        skin_module = sys.modules.get('gclient.data.hero_skin_data')
        skin_table = getattr(skin_module, 'data', None) if skin_module else None
        group = skin_table.get(hero_id) if callable(
            getattr(skin_table, 'get', None)) else None
        proto = group.get(skin_id) if callable(
            getattr(group, 'get', None)) else None
        feature_module = sys.modules.get('gclient.data.item_feature_data')
        feature_table = getattr(feature_module, 'data', None) if feature_module else None
        feature = feature_table.get(appearance) if callable(
            getattr(feature_table, 'get', None)) else None
        slide = _v109_field(feature, 'exclusive_slide_effect', ()) or ()
        if isinstance(slide, (int, str)) and not isinstance(slide, bool):
            slide = (slide,)
        slide = tuple(_v109_int(value, 0) for value in list(slide)[:4])
        effect_fields = {}
        for name in ('hero_effect_lobby', 'hero_effect_Ingame_self',
                     'hero_effect_Ingame', 'hero_effect_Ingame_can_hide'):
            value = _v109_field(proto, name, None)
            if value:
                effect_fields[name] = value if isinstance(value, bool) else str(value)[:80]
        twin_id = _v109_int(_v109_field(proto, 'twin_skin_item_id', 0), 0)
        level = striker_level_info(appearance)
        _v109_log(('striker-max-feature-trace', hero_id, equipped, appearance,
                   transform_item, slide, twin_id),
                  'Striker maximum features hero=%d equipped=%d appearance=%d '
                  'level=%r transform=%d twin=%d slide=%r hero_effects=%r'
                  % (hero_id, equipped, appearance, level, transform_item,
                     twin_id, slide, effect_fields), 2)
    except Exception as exc:
        _v109_log(('striker-max-feature-trace-error', hero_id, repr(exc)),
                  'Striker maximum feature trace hero=%d error=%r'
                  % (hero_id, exc), 1)


def striker_enable_max_features(owner, hero_id, equipped, appearance,
                                      persist=True):
    """Activate the official linked form switch for one actual maximum suit.

    Model, hero effects and exclusive slide effects remain data-driven from
    the authentic maximum appearance.  Only the separate transform map needs
    local completion here.  Existing genuine values (including zero/off) win.
    """
    transform_id = 0
    try:
        family = striker_evolution_family(appearance)
        if family and appearance != family[-1][1]:
            _v109_log(('striker-max-transform-not-maximum', hero_id, appearance,
                       family[-1][1]),
                      'Striker form autoactivation skipped nonmaximum hero=%d '
                      'appearance=%d official_maximum=%d'
                      % (hero_id, appearance, family[-1][1]), 1)
            return False
        module = sys.modules.get('gclient.util.hero_transform_util')
        if module is None:
            importer = globals().get('_ea_import')
            module = importer('gclient.util.hero_transform_util') \
                if callable(importer) else None
        normalizer = getattr(module, 'GetCombatHeroTransformSkinItemId', None)
        resolver = getattr(module, 'GetHeroTransformItemId', None)
        if not callable(normalizer) or not callable(resolver):
            striker_feature_trace(owner, hero_id, equipped, appearance)
            return False
        normalized = _v109_int(normalizer(appearance), 0)
        transform_id = _v109_int(resolver(normalized), 0) if normalized else 0
        if not transform_id:
            striker_feature_trace(owner, hero_id, equipped, appearance)
            return False
        binding = striker_transform_binding(transform_id)
        if (binding is None or binding[0] != hero_id
                or _v109_category(transform_id) != 'striker'
                or striker_subtype(transform_id)[0] != 'SkinTransformAni'):
            _v109_log(('striker-max-transform-invalid', hero_id, appearance,
                       transform_id),
                      'Striker maximum transform rejected hero=%d appearance=%d item=%d'
                      % (hero_id, appearance, transform_id), 1)
            return False
        record = injected_record(transform_id)
        if record is None:
            warehouse = getattr(owner, 'warehouse', None)
            if warehouse is None:
                _native, warehouse = native_avatar()
            if warehouse is not None:
                _v109_queue(warehouse, (transform_id,),
                            reason='striker-max-transform', immediate=True)
            record = injected_record(transform_id)
        if record is None or record[1] != 'striker':
            # A genuine linked item is left to the genuine native UI/RPC path.
            striker_feature_trace(owner, hero_id, equipped, appearance)
            return False
        key = ('hero_infos', hero_id, 'skin_transform_item_map', binding[1])
        ok, current = path_get(owner, 'hero_map', key)
        if not ok:
            return False
        if current == transform_id:
            striker_feature_trace(
                owner, hero_id, equipped, appearance, transform_id)
            return True
        if current is not _V109_MISSING and injected_record(current) is None:
            _v109_log(('striker-max-transform-genuine', hero_id, binding[1],
                       repr(current)),
                      'Striker maximum transform preserved genuine hero=%d skin=%d value=%r'
                      % (hero_id, binding[1], current), 1)
            striker_feature_trace(owner, hero_id, equipped, appearance)
            return False
        operations = [('hero_map', key, transform_id)]
        if not (apply_equip(transform_id, owner, operations)
                and striker_verify(
                    transform_id, owner, operations, 'ArmHeroTransform:max')):
            return False
        if persist:
            cosmetic_remember_pick(
                'ArmHeroTransform', hero_id, transform_id)
        try:
            download = globals().get('try_dlc_download')
            result = download(transform_id, []) if callable(download) else ['unavailable']
            _v109_log(('striker-max-transform-dlc', transform_id, repr(result)),
                      'Striker maximum transform authentic DLC queued item=%d result=%r'
                      % (transform_id, result), 1)
        except Exception as exc:
            _v109_log(('striker-max-transform-dlc-error', transform_id, repr(exc)),
                      'Striker maximum transform DLC item=%d guarded error=%r'
                      % (transform_id, exc), 1)
        _v109_log(('striker-max-transform', hero_id, equipped, appearance,
                   normalized, binding[1], transform_id),
                  'Striker maximum form link hero=%d equipped=%d appearance=%d '
                  'normalized=%d bound_skin=%d transform=%d readback=OK'
                  % (hero_id, equipped, appearance, normalized,
                     binding[1], transform_id), 2)
        striker_feature_trace(
            owner, hero_id, equipped, appearance, transform_id)
        return True
    except Exception as exc:
        _v109_log(('striker-max-transform-error', hero_id, appearance, repr(exc)),
                  'Striker maximum form link hero=%d appearance=%d error=%r'
                  % (hero_id, appearance, exc), 1)
        return False


def striker_transform_zero(owner, params):
    """Clear local injected entries, but preserve the official genuine zero RPC."""
    if len(params) != 2 or _v109_int(params[1], -1) != 0:
        return 0
    hero_id = _v109_int(params[0], 0)
    cleared = 0
    try:
        info = getattr(owner, 'hero_infos').get(hero_id)
        mapping = getattr(info, 'skin_transform_item_map')
        for skin_id, item_id in list(mapping.items())[:256]:
            record = injected_record(item_id)
            if record is None or record[1] != 'striker':
                continue
            key = ('hero_infos', hero_id, 'skin_transform_item_map', skin_id)
            if path_set(owner, 'hero_map', key, 0):
                cleared += 1
    except Exception:
        pass
    if cleared:
        _v109_log(('striker-transform-zero', hero_id, cleared),
                  'Striker transform zero hero=%d cleared local entries=%d; genuine RPC preserved'
                  % (hero_id, cleared), 2)
    return cleared


def striker_nested_injected(value, depth=0, budget=None):
    if budget is None:
        budget = [128]
    # Nonofficial shapes/depths fail closed rather than risking a partial
    # forward which a shallow scalar scan could mistake for genuine input.
    if budget[0] <= 0 or depth > 3:
        return True
    budget[0] -= 1
    if injected_record(value) is not None:
        return True
    if isinstance(value, dict):
        children = list(value.values())[:128]
    elif isinstance(value, (list, tuple)):
        children = list(value[:128])
    else:
        children = ()
    for child in children:
        if striker_nested_injected(child, depth + 1, budget):
            return True
    return False


def striker_action_rpc(owner, rpc, params, persist=True):
    """Return (engaged, genuine_entries); local entries never reach the server."""
    if len(params) != 1 or not isinstance(params[0], (list, tuple)):
        if striker_nested_injected(params):
            _v109_log(('striker-action-shape', rpc),
                      'Striker action RPC=%s malformed local input; withheld' % rpc, 2)
            return True, []
        return False, None
    entries = params[0]
    if len(entries) > 128:
        _v109_log(('striker-action-bound', rpc),
                  'Striker action RPC=%s exceeded safe local list bound; withheld' % rpc, 2)
        return True, []
    map_name = ('skin_execute_item_map' if rpc == 'ArmSkinExecuteItem'
                else 'skin_display_item_map')
    scalar_name = ('execute_item_id' if rpc == 'ArmSkinExecuteItem'
                   else 'display_item_id')
    engaged = False
    genuine = []
    plans = {}
    scalars = {}
    local_count = 0
    warehouse = None
    if category_enabled('striker'):
        try:
            warehouse = method_warehouse(owner)
            if warehouse is None:
                _avatar, warehouse = native_avatar()
        except Exception:
            warehouse = None
    for entry in entries:
        valid_shape = isinstance(entry, (list, tuple)) and len(entry) in (2, 3)
        if not valid_shape:
            if striker_nested_injected(entry):
                engaged = True
                _v109_log(('striker-action-entry-shape', rpc),
                          'Striker action RPC=%s malformed local entry; withheld' % rpc, 2)
            else:
                genuine.append(entry)
            continue
        hero_id = _v109_int(entry[0], -1)
        if len(entry) == 2:
            skin_id = 0
            action_id = _v109_int(entry[1], 0)
        else:
            skin_id = _v109_int(entry[1], 0)
            action_id = _v109_int(entry[2], 0)
        skin_rec = (injected_record(skin_id)
                   if skin_id else None)
        action_rec = (injected_record(action_id)
                     if action_id else None)
        saved_action = COSMETIC_SAVED.get((rpc, hero_id), 0)
        saved_skin = COSMETIC_SAVED.get(('ArmHeroSkin', hero_id), 0)
        local_evidence = (skin_rec is not None or action_rec is not None
                          or saved_action == action_id or saved_skin == skin_id)
        if warehouse is not None and local_evidence:
            # Complete only this evidenced local triple.  Blindly materializing
            # every official-looking triple would reclassify independent
            # genuine entries in the same RPC list as injected local entries.
            for candidate in (skin_id, action_id):
                if candidate and _v109_category(candidate) == 'striker':
                    ensure_item(warehouse, candidate, mode='single')
        skin_rec = (injected_record(skin_id)
                   if skin_id else None)
        action_rec = (injected_record(action_id)
                     if action_id else None)
        if skin_rec is None and action_rec is None:
            # v2.124: the game's own execution/display windows equipping a
            # REAL item id. Forwarding hits the server ownership check and
            # the equip rolls back ("execution ain't equipping"). Complete
            # locally like every other forced cosmetic (emote-style rule;
            # nothing local ever reaches the server) and let the save below
            # remember the real pick so the boot restore replays it.
            if (rpc in ('ArmSkinExecuteItem', 'ArmDisplayItem')
                    and hero_id >= 0 and action_id > 0
                    and category_enabled('striker')):
                try:
                    if warehouse is not None:
                        for candidate in (skin_id, action_id):
                            if (candidate
                                    and _v109_category(candidate) == 'striker'):
                                ensure_item(warehouse, candidate,
                                                  mode='single')
                except Exception:
                    pass
                engaged = True
                baseline_item = action_id
                plans.setdefault(baseline_item, []).append((
                    'hero_map',
                    ('hero_infos', hero_id, map_name, skin_id), action_id))
                scalars[(baseline_item, hero_id)] = action_id
                local_count += 1
                continue
            genuine.append(entry)
            if persist and hero_id > 0:
                cosmetic_remember_pick(rpc, hero_id, 0)
            continue
        engaged = True
        if hero_id < 0 or skin_id <= 0 or action_id <= 0:
            _v109_log(('striker-action-entry-invalid', rpc),
                      'Striker action RPC=%s invalid local triple; withheld' % rpc, 2)
            continue
        baseline_item = action_rec[0] if action_rec is not None else skin_rec[0]
        plans.setdefault(baseline_item, []).append((
            'hero_map', ('hero_infos', hero_id, map_name, skin_id), action_id))
        scalars[(baseline_item, hero_id)] = action_id
        local_count += 1
    if not engaged:
        if entries:
            _v109_log(('striker-action-unrecognized', rpc),
                      'Striker action RPC=%s entries not recognized as local;'
                      ' shape=%r' % (rpc, entries), 1)
        return False, None
    succeeded = 0
    for baseline_item, operations in plans.items():
        for (item_id, hero_id), action_id in scalars.items():
            if item_id == baseline_item:
                operations.append(('hero_info', ('hero_infos', hero_id, scalar_name), action_id))
        operations = striker_compact(operations)
        if (apply_equip(baseline_item, owner, operations)
                and striker_verify(baseline_item, owner, operations, rpc)):
            succeeded += 1
            if persist:
                for (planned_item, planned_hero), action_id in scalars.items():
                    if planned_item == baseline_item and planned_hero > 0:
                        cosmetic_remember_pick(
                            rpc, planned_hero, action_id)
                        _v109_log(
                            ('striker-action-save', rpc, planned_hero, action_id),
                            'Striker action saved rpc=%s hero=%d item=%d'
                            % (rpc, planned_hero, action_id), 1)
            if rpc == 'ArmDisplayItem':
                download = globals().get('try_dlc_download')
                for (planned_item, _planned_hero), action_id in scalars.items():
                    if planned_item != baseline_item:
                        continue
                    try:
                        result = (download(action_id, [])
                                  if callable(download) else ['unavailable'])
                    except Exception as exc:
                        result = ['guarded', repr(exc)]
                    _v109_log(('striker-action-dlc', baseline_item, action_id),
                              'Striker Join Team Action authentic DLC queued '
                              'item=%d result=%r; official playback gate unchanged'
                              % (action_id, result), 2)
        else:
            _v109_log(('striker-action-apply', rpc, baseline_item),
                      'Striker action RPC=%s item=%d local completion failed; entry withheld'
                      % (rpc, baseline_item), 2)
    _v109_log(('striker-action-partition', rpc, local_count, len(genuine)),
              'Striker action RPC=%s local entries=%d groups=%d/%d genuine forwarded=%d'
              % (rpc, local_count, succeeded, len(plans), len(genuine)), 2)
    return True, genuine


def striker_selected_skin(avatar, hero_id):
    try:
        info = getattr(avatar, 'hero_infos').get(hero_id)
        selected = _v109_int(getattr(info, 'skin_item_id', 0), 0)
        if not selected:
            return 0
        if injected_record(selected) is not None:
            return selected
        mapping = getattr(avatar, 'arm_low_level_skin', {}) or {}
        owned = _v109_int(mapping.get(selected, selected), 0) or selected
        if injected_record(owned) is not None:
            return selected
    except Exception:
        pass
    return 0


def striker_actual_skin(avatar, hero_id):
    """Apply the native equipped -> selected-appearance mapping exactly once."""
    equipped = striker_selected_skin(avatar, hero_id)
    if not equipped:
        return 0
    try:
        mapping = getattr(avatar, 'arm_low_level_skin', {}) or {}
        actual = _v109_int(mapping.get(equipped, equipped), 0) or equipped
        if actual == equipped:
            return equipped
        if not striker_is_suit(actual):
            return equipped
        row_hero = _v109_int(_v109_field(_v109_row(actual), 'hero_id', 0), 0)
        if row_hero and row_hero != hero_id:
            return equipped
        return actual
    except Exception:
        return equipped


def striker_legacy_skin(hero_id):
    """Native actual item shared with older hall/emote/combat consumers.

    Returning zero means genuine/default/unresolved and lets every legacy
    caller retain its original answer.  No family injection or model refresh
    is performed inside these rendering getters.
    """
    try:
        hero_id = _v109_int(hero_id, 0)
        if not hero_id or not category_enabled('striker'):
            return 0
        avatar, _warehouse = native_avatar()
        if avatar is None:
            return 0
        # The requested hero is the key into hero_infos.  A match may use a
        # different operator from the lobby's current hero; requiring those
        # two IDs to match incorrectly hid valid FPS-hand/effect/legacy state.
        appearance = striker_actual_skin(avatar, hero_id)
        if not appearance or not striker_is_suit(appearance):
            return 0
        row_hero = _v109_int(_v109_field(
            _v109_row(appearance), 'hero_id', 0), 0)
        if row_hero and row_hero != hero_id:
            return 0
        return appearance
    except Exception:
        return 0


def striker_selected_execution(avatar, hero_id):
    try:
        info = getattr(avatar, 'hero_infos').get(hero_id)
        selected = _v109_int(getattr(info, 'skin_item_id', 0), 0)
        low_level = getattr(avatar, 'arm_low_level_skin', {}) or {}
        owned = _v109_int(low_level.get(selected, selected), 0) or selected
        mapping = getattr(info, 'skin_execute_item_map', {}) or {}
        mapped = _v109_int(mapping.get(selected, 0), 0) or _v109_int(
            mapping.get(owned, 0), 0)
        skin_local = (injected_record(selected) is not None
                      or injected_record(owned) is not None)
        if mapped and (skin_local or injected_record(mapped) is not None):
            return mapped
        current = _v109_int(getattr(info, 'execute_item_id', 0), 0)
        if current and injected_record(current) is not None:
            return current
    except Exception:
        pass
    return 0


def striker_selected_display(avatar, hero_id):
    try:
        info = getattr(avatar, 'hero_infos').get(hero_id)
        current = _v109_int(getattr(info, 'display_item_id', 0), 0)
        if not current:
            return 0
        if injected_record(current) is not None:
            return current
        selected = _v109_int(getattr(info, 'skin_item_id', 0), 0)
        low_level = getattr(avatar, 'arm_low_level_skin', {}) or {}
        owned = _v109_int(low_level.get(selected, selected), 0) or selected
        if (injected_record(selected) is None
                and injected_record(owned) is None):
            return 0
        mapping = getattr(info, 'skin_display_item_map', {}) or {}
        if current in (_v109_int(mapping.get(selected, 0), 0),
                       _v109_int(mapping.get(owned, 0), 0)):
            return current
    except Exception:
        pass
    # v2.104: the unified equipped-item fallback - the post-match MVP
    # card must resolve the same item as the native path even when
    # hero_infos has not carried a display_item_id mapping.
    try:
        gf = globals().get('get_forced_skin')
        item = _v109_int(gf(hero_id), 0) if callable(gf) else 0
        if item and injected_record(item) is not None:
            return item
    except Exception:
        pass
    return 0


def striker_team_display(avatar, hero_id):
    """Return (item, skin_linked, default) for the official self-join consumer.

    Explicit native selections remain first. Only an empty/default selection on
    an injected suit can fall back to the official skin-linked start-action
    resolver. The caller still uses PlayMainNpcDisplay and its real DLC gate.
    """
    default_item = 0
    try:
        consts = sys.modules.get('gshare.consts')
        item_ids = getattr(consts, 'ItemID', None) if consts else None
        default_item = _v109_int(getattr(
            item_ids, 'DEFAULT_DISPLAY_ITEM_ID', 0), 0)
    except Exception:
        default_item = 0
    explicit = striker_selected_display(avatar, hero_id)
    if explicit and explicit != default_item:
        return explicit, False, default_item
    try:
        info = getattr(avatar, 'hero_infos').get(hero_id)
        if info is None:
            return 0, False, default_item
        selected = _v109_int(getattr(info, 'skin_item_id', 0), 0)
        low_level = getattr(avatar, 'arm_low_level_skin', {}) or {}
        owned = _v109_int(low_level.get(selected, selected), 0) or selected
        skin_local = (injected_record(selected) is not None
                      or injected_record(owned) is not None)
        if not skin_local:
            return 0, False, default_item
        current = _v109_int(getattr(info, 'display_item_id', 0), 0)
        if current and current != default_item:
            # An unrelated genuine current action always stands down.
            return 0, False, default_item
        mapping = getattr(info, 'skin_display_item_map', {}) or {}
        selected_mapped = _v109_int(mapping.get(selected, 0), 0)
        owned_mapped = _v109_int(mapping.get(owned, 0), 0)
        if default_item and default_item in (selected_mapped, owned_mapped):
            # An explicit native default/random selection is not an invitation
            # to substitute a linked action.
            return 0, False, default_item
        mapped = selected_mapped or owned_mapped
        if mapped and mapped != default_item:
            return mapped, False, default_item

        util = sys.modules.get('gclient.util.hero_data_util')
        resolver = getattr(util, 'GetDisplayActionBySkinItemId', None)
        if not callable(resolver):
            _v109_log(('striker-team-linked-unavailable', selected, owned),
                      'Striker Join Team Action official skin-link unavailable '
                      'selected=%d actual=%d' % (selected, owned), 2)
            return 0, False, default_item
        candidates = [selected, owned]
        level_info = (striker_level_info(selected)
                      or striker_level_info(owned))
        if level_info:
            cdata = sys.modules.get('gclient.util.cdata_util')
            all_levels = getattr(cdata, 'BaseItemId2AllLevelItems', None)
            try:
                family = all_levels(level_info[0]) if callable(all_levels) else ()
                if isinstance(family, (list, tuple)):
                    # Prefer the highest authentic level nearest the equip.
                    candidates.extend(reversed(family[-16:]))
            except Exception:
                pass
            candidates.append(level_info[0])
        attempted = []
        for skin_id in candidates:
            skin_id = _v109_int(skin_id, 0)
            if not skin_id or skin_id in attempted:
                continue
            attempted.append(skin_id)
            resolved = []
            eligible = []
            try:
                protos = resolver(skin_id) or ()
            except Exception:
                continue
            count = 0
            for proto in protos:
                count += 1
                if count > 16:
                    break
                if not _v109_field(proto, 'is_skin_start_anim', False):
                    continue
                item_id = _v109_int(_v109_field(
                    proto, 'display_item_id', 0), 0)
                if not item_id:
                    continue
                if item_id not in resolved:
                    resolved.append(item_id)
                record = injected_record(item_id)
                if (record is not None and record[1] == 'striker'
                        and striker_subtype(item_id)[1] == 302
                        and item_id not in eligible):
                    eligible.append(item_id)
            _v109_log(('striker-team-linked', selected, owned, skin_id,
                       tuple(resolved), tuple(eligible)),
                      'Striker Join Team Action official skin-link selected=%d '
                      'actual=%d candidate=%d resolved=%r eligible=%r'
                      % (selected, owned, skin_id, resolved, eligible), 2)
            if len(eligible) == 1:
                return eligible[0], True, default_item
            if len(eligible) > 1:
                break               # ambiguity on the best row fails closed
    except Exception as exc:
        _v109_log(('striker-team-linked-error', hero_id, repr(exc)),
                  'Striker Join Team Action skin-link error=%r' % (exc,), 2)
    return 0, False, default_item


def striker_local_combat(owner):
    try:
        for name in ('_striker_is_local', '_striker_is_local_avatarish'):
            helper = globals().get(name)
            if callable(helper) and helper(owner):
                return True
        getter = globals().get('_local_combat_avatar')
        local = getter() if callable(getter) else None
        if owner is local and local is not None:
            return True
        for name in ('owner', 'parent', 'master', 'source_avatar'):
            if getattr(owner, name, None) is local and local is not None:
                return True
    except Exception:
        pass
    return False


def striker_request_combat_refresh(owner, hero_id):
    """Queue the latest official ShowModel for one current local selection."""
    try:
        hero_id = _v109_int(hero_id, 0)
        if (not hero_id or not category_enabled('striker')
                or striker_current_hero(owner) != hero_id):
            return False
        expected = striker_actual_skin(owner, hero_id)
        if not expected:
            return False                 # genuine/default heroes stay native
        native, _warehouse = native_avatar()
        if native is not None and owner is not native:
            return False                 # never repaint another player
        getter = globals().get('_local_combat_avatar')
        combat = getter() if callable(getter) else None
        if combat is None or not striker_local_combat(combat):
            return False
        reference = weakref.ref(owner)
    except Exception:
        return False
    key = id(owner)
    STRIKER_COMBAT_GENERATION[0] += 1
    generation = STRIKER_COMBAT_GENERATION[0]
    if (len(STRIKER_COMBAT_PENDING) >= 8
            and key not in STRIKER_COMBAT_PENDING):
        STRIKER_COMBAT_PENDING.pop(
            next(iter(STRIKER_COMBAT_PENDING)), None)
    STRIKER_COMBAT_PENDING[key] = (
        reference, hero_id, expected, generation)
    poster = globals().get('_game_post')
    if callable(poster):
        try:
            posted = poster('striker-combat-refresh',
                            striker_refresh_combat, key, generation)
        except Exception:
            posted = False
        if not posted:
            current = STRIKER_COMBAT_PENDING.get(key)
            if current and current[3] == generation:
                STRIKER_COMBAT_PENDING.pop(key, None)
        return bool(posted)
    # Host-contract fallback; the installed payload always uses _game_post.
    return striker_refresh_combat(key, generation)


def striker_invalidate_combat_cache(combat):
    """Clear only the local avatar's cached official hero proto.

    ``CombatAvatarMember.hero_skin_proto`` is a cached_property whose official
    getter delegates to GetHeroSkinProto.  A previous skin's cached row would
    otherwise survive an A->B equip and feed stale effect/component data after
    the body has reloaded.  No heap walk, model substitution, or other-player
    object is involved.
    """
    try:
        values = getattr(combat, '__dict__', None)
        if values is not None and 'hero_skin_proto' in values:
            del values['hero_skin_proto']
            return 1
    except Exception:
        pass
    return 0


def striker_refresh_combat(key, generation):
    """Run native body+hands reload only if this request is still current."""
    record = STRIKER_COMBAT_PENDING.get(key)
    if not record or record[3] != generation:
        return False                     # a newer request owns this avatar
    STRIKER_COMBAT_PENDING.pop(key, None)
    reference, hero_id, expected, _generation = record
    try:
        owner = reference()
        if (owner is None or not category_enabled('striker')
                or striker_current_hero(owner) != hero_id
                or striker_actual_skin(owner, hero_id) != expected):
            return False
        native, _warehouse = native_avatar()
        if native is not None and owner is not native:
            return False
        getter = globals().get('_local_combat_avatar')
        combat = getter() if callable(getter) else None
        if combat is None or not striker_local_combat(combat):
            return False
        combat_hero = striker_current_hero(combat)
        if combat_hero and combat_hero != hero_id:
            _v109_log(('striker-combat-stale-hero', hero_id, combat_hero),
                      'Striker combat refresh cancelled: requested hero=%d '
                      'but native combat hero=%d' % (hero_id, combat_hero), 1)
            return False
        show = getattr(combat, 'ShowModel', None)
        if not callable(show):
            return False
        cache_cleared = striker_invalidate_combat_cache(combat)
        show()                           # official Reload + OnReloadModel path
        _v109_log(('striker-combat-show', hero_id, expected),
                  'Striker native combat ShowModel hero=%d selected=%d '
                  'generation=%d local_proto_cache_cleared=%d'
                  % (hero_id, expected, generation, cache_cleared), 2)
        return True
    except Exception as exc:
        _v109_log(('striker-combat-show-error', hero_id, repr(exc)),
                  'Striker native combat ShowModel hero=%d guarded error=%r'
                  % (hero_id, exc), 1)
        return False


def striker_native_proto(previous, item_id):
    """Use the official combat resolver and authentic hero/hero-skin tables."""
    try:
        module = sys.modules.get(
            'gclient.gameplay.logic_base.entities.combatavatarmembers.cimp_model')
        namespace = getattr(previous, '__globals__', {})
        util = (getattr(module, 'hero_data_util', None)
                or namespace.get('hero_data_util')
                or sys.modules.get('gclient.util.hero_data_util'))
        resolver = getattr(util, 'GetHeroIdAndSkinId', None)
        if not callable(resolver):
            return None
        hero_id, skin_id = resolver(item_id)
        if not hero_id:
            return None
        if skin_id is not None:
            table = (getattr(module, 'hero_skin_data', None)
                     or namespace.get('hero_skin_data')
                     or sys.modules.get('gclient.data.hero_skin_data'))
            return getattr(table, 'data')[hero_id][skin_id]
        table = (getattr(module, 'hero_data', None)
                 or namespace.get('hero_data')
                 or sys.modules.get('gclient.data.hero_data'))
        return getattr(table, 'data')[hero_id]
    except Exception:
        return None


def striker_dsid_factory(previous):
    def wrapper(self, *args, **kwargs):
        genuine = previous(self, *args, **kwargs)
        try:
            specific = kwargs.get('skin_item_id', args[0] if args else None)
            if _v109_int(specific, 0) or not striker_local_combat(self):
                return genuine
            avatar, _warehouse = native_avatar()
            hero_id = striker_current_hero(self) or striker_current_hero(avatar)
            selected = striker_actual_skin(avatar, hero_id)
            if selected:
                return selected
        except Exception:
            pass
        return genuine
    return wrapper


def striker_bind_game_logic(owner):
    """Bind the actual runtime game-logic class before official model build."""
    try:
        space = getattr(owner, 'space', None)
        game_logic = getattr(space, 'game_logic', None)
        if game_logic is None:
            game_logic = getattr(owner, 'game_logic', None)
        if game_logic is None:
            return False
        cls = type(game_logic)
        key = (id(cls), 'striker-consumer:GetDisplayHeroSkinItemId')
        if key in install_seen:
            return True
        wrapped = _v109_wrap_method(
            cls, 'GetDisplayHeroSkinItemId',
            striker_game_logic_dsid_factory)
        already = getattr(getattr(
            cls, 'GetDisplayHeroSkinItemId', None), '_v109_wrap', False)
        if not wrapped and not already:
            _v109_log(('striker-game-logic-bind-missing',
                       cls.__module__, cls.__name__),
                      'Striker combat game-logic bind unavailable cls=%s.%s'
                      % (cls.__module__, cls.__name__), 1)
            return False
        install_seen.add(key)
        if wrapped:
            _v109_log(('striker-game-logic-bind',
                       cls.__module__, cls.__name__),
                      'Striker combat game-logic bound actual cls=%s.%s'
                      % (cls.__module__, cls.__name__), 2)
        return True
    except Exception as exc:
        _v109_log(('striker-game-logic-bind-error', repr(exc)),
                  'Striker combat game-logic bind guarded error=%r' % (exc,), 1)
        return False


def striker_bind_combat_owner(owner):
    """Late-bind the actual mode/replay avatar's official skin consumers.

    Base-class hooks cover ordinary combat, but a late-loaded mode can override
    the getters on its own class.  inspect.getattr_static in _v109_wrap_method
    prevents double-wrapping inherited native hooks.  Local/other-player and
    explicit-skin decisions remain inside the resolver, not in this binder.
    """
    if owner is None:
        return False
    bound = False
    try:
        cls = type(owner)
        for method, factory in (
                ('GetDisplayHeroSkinItemId', striker_dsid_factory),
                ('GetHeroSkinProto', striker_proto_factory)):
            key = (id(cls), 'striker-consumer:' + method)
            if key in install_seen:
                bound = True
                continue
            wrapped = _v109_wrap_method(cls, method, factory)
            already = getattr(getattr(cls, method, None), '_v109_wrap', False)
            if wrapped or already:
                install_seen.add(key)
                bound = True
                if wrapped:
                    _v109_log(('striker-combat-owner-bind', cls.__module__,
                               cls.__name__, method),
                              'Striker combat owner bound actual cls=%s.%s method=%s'
                              % (cls.__module__, cls.__name__, method), 2)
    except Exception as exc:
        _v109_log(('striker-combat-owner-bind-error', repr(exc)),
                  'Striker combat owner bind guarded error=%r' % (exc,), 1)
    return bound


def striker_owner_consumer_factory(previous):
    """Bind an official hand/replay owner's class, then run it unchanged."""
    def wrapper(self, *args, **kwargs):
        try:
            if category_enabled('striker'):
                striker_bind_combat_owner(getattr(self, 'owner', None))
        except Exception:
            pass
        return previous(self, *args, **kwargs)
    return wrapper


def striker_model_factory(previous):
    """Late-bind real game-logic/owner consumers, then preserve model execution."""
    def wrapper(self, *args, **kwargs):
        striker_bind_game_logic(self)
        striker_bind_combat_owner(self)
        return previous(self, *args, **kwargs)
    return wrapper


def striker_game_logic_dsid_factory(previous):
    """Cover the direct game-logic model path for the local combat avatar only."""
    def wrapper(self, *args, **kwargs):
        genuine = previous(self, *args, **kwargs)
        try:
            avatar_id = kwargs.get('avatar_id', args[0] if args else None)
            specific = kwargs.get('skin_item_id', args[1] if len(args) > 1 else None)
            if specific is not None:  # explicit skins and transform IDs are native
                return genuine
            space = getattr(self, 'space', None)
            combat_avatars = getattr(space, 'combat_avatars', None)
            combat = (combat_avatars.get(avatar_id)
                      if callable(getattr(combat_avatars, 'get', None)) else None)
            if combat is None:
                getter = getattr(space, 'GetEntityByID', None)
                entity = getter(avatar_id) if callable(getter) else None
                if entity is not None and getattr(entity, 'IsCombatAvatar', False):
                    combat = entity
            if combat is None or not striker_local_combat(combat):
                return genuine
            avatar, _warehouse = native_avatar()
            hero_id = striker_current_hero(combat)
            if not hero_id:
                return genuine       # never reuse a stale lobby hero in combat
            selected = striker_actual_skin(avatar, hero_id)
            if not selected or not striker_is_suit(selected):
                return genuine
            row_hero = _v109_int(_v109_field(
                _v109_row(selected), 'hero_id', 0), 0)
            if row_hero and row_hero != hero_id:
                return genuine
            _v109_log(('striker-combat-display', avatar_id, hero_id, selected),
                      'Striker combat display avatar=%r hero=%d item=%d '
                      'genuine=%r source=game-logic'
                      % (avatar_id, hero_id, selected, genuine), 2)
            return selected
        except Exception:
            pass
        return genuine
    return wrapper


def striker_proto_factory(previous):
    def wrapper(self, *args, **kwargs):
        genuine = previous(self, *args, **kwargs)
        try:
            if args or kwargs or not striker_local_combat(self):
                return genuine
            avatar, _warehouse = native_avatar()
            hero_id = striker_current_hero(self) or striker_current_hero(avatar)
            selected = striker_actual_skin(avatar, hero_id)
            if selected:
                proto = striker_native_proto(previous, selected)
                if proto is not None:
                    return proto
        except Exception:
            pass
        return genuine
    return wrapper


def striker_combat_transform_selection(owner):
    """Return the authenticated injected suit for this local combat hero."""
    try:
        if not striker_local_combat(owner):
            return 0, 0
        avatar, _warehouse = native_avatar()
        hero_id = (striker_current_hero(owner)
                   or striker_current_hero(avatar))
        if not hero_id:
            return 0, 0
        info = getattr(avatar, 'hero_infos').get(hero_id)
        equipped = _v109_int(getattr(info, 'skin_item_id', 0), 0)
        appearance = striker_actual_skin(avatar, hero_id)
        low_level = getattr(avatar, 'arm_low_level_skin', {}) or {}
        owned = _v109_int(low_level.get(equipped, equipped), 0) or equipped
        if not any(injected_record(value) is not None
                   for value in (equipped, owned, appearance) if value):
            return 0, 0
        if not appearance or not striker_is_suit(appearance):
            return 0, 0
        row_hero = _v109_int(_v109_field(
            _v109_row(appearance), 'hero_id', 0), 0)
        if row_hero and row_hero != hero_id:
            return 0, 0
        return hero_id, appearance
    except Exception:
        return 0, 0


def striker_combat_transform_predicates(owner, item_id, namespace):
    """Evaluate the official Switch Form contract for one substituted suit.

    The official Request reads self.arm_clothes[Suit].  Writing that native
    property would itself reload the model, so this scoped path instead calls
    the same live gates with the injected suit and then uses the original
    TryPlayNovaTwinSkinTransform request.  Nothing is forced on failure.
    """
    details = {'item': item_id}
    try:
        if not item_id or not striker_local_combat(owner):
            return False, 0, details
        consts = namespace.get('consts') or sys.modules.get('gshare.consts')
        cconst = namespace.get('cconst') or sys.modules.get('gshare.cconst')
        alive = getattr(getattr(consts, 'CombatState', None), 'ALIVE', None)
        emote = getattr(getattr(cconst, 'StateRelationship', None), 'Emote', None)
        destroyed = getattr(owner, 'is_destroyed', None)
        state_check = getattr(owner, 'IsStateInRelationshipSet', None)
        emote_check = getattr(owner, 'CheckCanUseEmote', None)
        model = getattr(owner, 'model', None)
        transforming = getattr(model, 'IsNovaTwinSkinTransforming', None) if model else None
        if (alive is None or emote is None or model is None
                or not callable(destroyed) or not callable(state_check)
                or not callable(emote_check) or not callable(transforming)):
            details['reason'] = 'native-gate-unavailable'
            return False, 0, details
        hand_refresh = getattr(model, 'nova_twin_skin_hand_refresh_item_id', None)
        checks = {
            'alive': (not destroyed() and not getattr(owner, 'is_replaying', False)
                      and getattr(owner, 'combat_state', None) == alive),
            'model': not transforming() and hand_refresh is None,
            'emote': (not state_check(emote) and bool(emote_check())),
        }
        details.update(checks)
        if not all(checks.values()):
            details['reason'] = 'combat-state'
            return False, 0, details

        module = sys.modules.get(
            'gclient.gameplay.logic_base.models.nova_twin_skin_model_component')
        if module is None:
            importer = globals().get('_ea_import')
            module = importer(
                'gclient.gameplay.logic_base.models.nova_twin_skin_model_component'
            ) if callable(importer) else None
        twin_resolver = getattr(module, 'GetNovaTwinSkinItemId', None)
        util = sys.modules.get('gclient.util.hero_transform_util')
        equipped_resolver = (namespace.get('IsCombatHeroTransformEquipped')
                             or getattr(util, 'IsCombatHeroTransformEquipped', None))
        anim_resolver = (namespace.get('GetCombatHeroTransformAnim')
                         or getattr(util, 'GetCombatHeroTransformAnim', None))
        graph_resolver = (namespace.get('GetCombatHeroTransformGraph')
                          or getattr(util, 'GetCombatHeroTransformGraph', None))
        if not all(callable(value) for value in (
                twin_resolver, equipped_resolver, anim_resolver, graph_resolver)):
            details['reason'] = 'transform-resolver-unavailable'
            return False, 0, details
        twin_id = _v109_int(twin_resolver(item_id), 0)
        transform_ok = bool(twin_id and equipped_resolver(item_id)
                            and anim_resolver(item_id)
                            and graph_resolver(item_id))
        details['twin'] = twin_id
        details['transform'] = transform_ok
        if not transform_ok:
            details['reason'] = 'official-transform-gate'
            return False, twin_id, details
        return True, twin_id, details
    except Exception as exc:
        details['reason'] = 'guarded:' + repr(exc)[:100]
        return False, 0, details


def striker_transform_gate_factory(previous):
    def wrapper(self, *args, **kwargs):
        genuine = previous(self, *args, **kwargs)
        if args or kwargs:
            return genuine
        hero_id, item_id = striker_combat_transform_selection(self)
        if not item_id:
            return genuine
        ok, twin_id, details = striker_combat_transform_predicates(
            self, item_id, getattr(previous, '__globals__', {}))
        _v109_log(('striker-combat-transform-gate', hero_id, item_id,
                   bool(ok), details.get('reason')),
                  'Striker Switch Form native gate hero=%d suit=%d twin=%d allowed=%s details=%r genuine_default=%r'
                  % (hero_id, item_id, twin_id, ok, details, genuine), 2)
        return bool(ok)
    return wrapper


def striker_transform_request_factory(previous):
    def wrapper(self, *args, **kwargs):
        if args or kwargs:
            return previous(self, *args, **kwargs)
        hero_id, item_id = striker_combat_transform_selection(self)
        if not item_id:
            return previous(self, *args, **kwargs)
        namespace = getattr(previous, '__globals__', {})
        ok, twin_id, details = striker_combat_transform_predicates(
            self, item_id, namespace)
        if not ok:
            _v109_log(('striker-combat-transform-request-denied', hero_id,
                       item_id, details.get('reason')),
                      'Striker Switch Form request withheld hero=%d suit=%d details=%r'
                      % (hero_id, item_id, details), 2)
            return False
        enum = _v109_enum()
        suit = getattr(enum, 'Suit', None) if enum is not None else None
        request = getattr(self, 'TryPlayNovaTwinSkinTransform', None)
        if suit is None or not callable(request):
            return False
        # This is the official RequestNovaTwinSkinTransform terminal call,
        # with only its arm_clothes[Suit] argument authenticated to our pick.
        result = request(suit, item_id, twin_id, True)
        _v109_log(('striker-combat-transform-request', hero_id, item_id,
                   twin_id, repr(result)),
                  'Striker Switch Form official request hero=%d suit=%d twin=%d result=%r'
                  % (hero_id, item_id, twin_id, result), 2)
        return result
    return wrapper


STRIKER_PREFLIGHT_CAP = 384


def striker_preflight_native(warehouse, item_ids):
    """Synchronously materialize a bounded official candidate set.

    Generic ownership hooks deliberately defer list-building work.  These
    Striker builders filter in the same call, so their candidates must instead
    be complete before the original builder/collection function is entered.
    """
    state = _v109_prepare(warehouse, defer=True)
    if state is None or state.get('busy'):
        return 0, len(item_ids)
    ready = 0
    missing = 0
    seen = set()
    for raw in item_ids:
        item_id = _v109_int(raw, 0)
        if not item_id or item_id in seen:
            continue
        seen.add(item_id)
        if len(seen) > STRIKER_PREFLIGHT_CAP:
            missing += 1
            continue
        ensure_item(warehouse, item_id, mode='single')
        if (item_id in state.get('by_item', {})
                or item_id in state.get('owned', set())):
            ready += 1
        else:
            # Genuine rows not represented in the cheap cache still remain the
            # original builder's decision; never fabricate a successful count.
            try:
                getter = getattr(warehouse, 'HasItemByItemId', None)
                if callable(getter) and getter(item_id, True):
                    ready += 1
                    continue
            except Exception:
                pass
            missing += 1
    return ready, missing


def striker_list_preflight(window, kind, previous, action_data=None):
    if not category_enabled('striker'):
        return False
    avatar, warehouse = native_avatar()
    if avatar is None or warehouse is None:
        return False
    namespace = getattr(previous, '__globals__', {}) or {}
    util = (namespace.get('hero_data_util')
            or sys.modules.get('gclient.util.hero_data_util'))
    cdata = (namespace.get('cdata_util')
             or sys.modules.get('gclient.util.cdata_util'))
    if util is None:
        return False
    hero_id = _v109_int(getattr(window, 'hero_id', 0), 0)
    action = action_data
    if action is None:
        action = getattr(window, 'action_data', None)
    execution_ids = []
    skin_ids = []
    display_ids = []

    def add_skin(value):
        value = _v109_int(value, 0)
        if value:
            skin_ids.append(value)

    def add_execution(value):
        value = _v109_int(value, 0)
        if value:
            execution_ids.append(value)
            resolver = getattr(util, 'GetSkinItemIdsByExecutionItemId', None)
            if callable(resolver):
                try:
                    for skin_id in list(resolver(value) or ())[:48]:
                        add_skin(skin_id)
                except Exception:
                    pass

    try:
        if kind in ('execution', 'execution-show'):
            add_execution(_v109_field(action, 'execution_item_id', 0))
            if kind == 'execution':
                getter = getattr(util, 'GetAllHeroExecutionProtos', None)
                if not callable(getter) or not hero_id:
                    return False
                rows = getter(hero_id, include_expired=True) or ()
                for row in list(rows)[:192]:
                    add_execution(_v109_field(row, 'execution_item_id', 0))
        elif kind in ('display', 'popup', 'popup-show'):
            action_display = _v109_int(_v109_field(
                action, 'display_item_id', 0), 0)
            if action_display:
                display_ids.append(action_display)
            if kind == 'display':
                getter = getattr(util, 'GetAllHeroAppearanceAniItemIds', None)
                if not callable(getter) or not hero_id:
                    return False
                rows = getter(hero_id, include_expired=True) or ()
                for row in list(rows)[:192]:
                    display_ids.append(_v109_int(_v109_field(
                        row, 'display_item_id', 0), 0))
        else:
            return False

        effective = 0
        resolver = getattr(util, 'GetEffectiveSkinItemId', None)
        if callable(resolver) and hero_id:
            try:
                effective = resolver(hero_id)
            except Exception:
                effective = 0
        add_skin(effective)
        add_skin(striker_info_item(avatar, hero_id))
        add_skin(striker_actual_skin(avatar, hero_id))

        if kind in ('popup', 'popup-show'):
            exclusive = _v109_int(_v109_field(
                action, 'exclusive_aa_skin_id', 0), 0)
            if exclusive:
                add_skin(exclusive)
                level = striker_level_info(exclusive)
                all_levels = getattr(cdata, 'BaseItemId2AllLevelItems', None)
                if level and callable(all_levels):
                    try:
                        for skin_id in list(all_levels(level[0]) or ())[:48]:
                            add_skin(skin_id)
                    except Exception:
                        pass
            else:
                action_id = _v109_field(action, 'id', '') or ''
                try:
                    action_hero = int(str(action_id).split('.')[0])
                except Exception:
                    action_hero = 0
                common = _v109_int(getattr(util, 'COMMON_HERO_ID', 0), 0)
                if not action_hero:
                    action_hero = common
                if action_hero and action_hero != common:
                    hero_ids = [action_hero]
                else:
                    chooser = getattr(cdata, 'GetAllHeroChooseList', None)
                    hero_ids = (list(chooser() or ())[:64]
                                if callable(chooser) else [])
                skin_getter = getattr(util, 'GetAllHeroSkinItemIds', None)
                origin_getter = getattr(util, 'GetHeroOriginSkin', None)
                if not callable(skin_getter):
                    return False
                for hid in hero_ids:
                    hid = _v109_int(hid, 0)
                    if not hid:
                        continue
                    try:
                        rows = skin_getter(hid, include_expired=True) or ()
                    except Exception:
                        continue
                    for row in list(rows)[:192]:
                        add_skin(_v109_field(row, 'skin_item_id', 0))
                    if callable(origin_getter):
                        try:
                            add_skin(origin_getter(hid))
                        except Exception:
                            pass

        # Execution/display ownership is required first; linked/effective skins
        # then satisfy the pair and popup predicates in the same original call.
        ordered = execution_ids + display_ids + skin_ids
        ready, missing = striker_preflight_native(warehouse, ordered)
        _v109_log(('striker-sync-preflight', kind, hero_id, ready, missing),
                  'Striker synchronous list preflight kind=%s hero=%d ready=%d unresolved=%d candidates=%d'
                  % (kind, hero_id, ready, missing, len(ordered)), 2)
        return missing == 0
    except Exception as exc:
        _v109_log(('striker-sync-preflight-error', kind, repr(exc)),
                  'Striker synchronous list preflight kind=%s guarded error=%r'
                  % (kind, exc), 1)
        return False


def striker_list_factory(previous, kind):
    def wrapper(self, *args, **kwargs):
        data = kwargs.get('data')
        if data is None and len(args) >= 3:
            data = args[2]
        try:
            striker_list_preflight(self, kind, previous, data)
        except Exception:
            pass
        return previous(self, *args, **kwargs)
    return wrapper


def striker_execution_factory(previous):
    def wrapper(self, *args, **kwargs):
        genuine = previous(self, *args, **kwargs)
        try:
            if not striker_local_combat(self):
                return genuine
            avatar, _warehouse = native_avatar()
            hero_id = striker_current_hero(self) or striker_current_hero(avatar)
            item_id = striker_selected_execution(avatar, hero_id)
            if not item_id:
                return genuine
            module = sys.modules.get(
                'gclient.gameplay.logic_base.entities.combatavatarmembers.cimp_execute')
            namespace = getattr(previous, '__globals__', {})
            replace = (namespace.get('GetReplaceExecuteItemId')
                       or getattr(module, 'GetReplaceExecuteItemId', None))
            if callable(replace):
                return replace(item_id)
        except Exception:
            pass
        return genuine
    return wrapper


def striker_team_factory(previous):
    def wrapper(self, *args, **kwargs):
        avatar = None
        member = None
        old = _V109_MISSING
        try:
            if getattr(self, 'is_self_join', False):
                avatar, _warehouse = native_avatar()
                hero_id = striker_current_hero(avatar)
                item_id, linked, default_item = striker_team_display(
                    avatar, hero_id)
                player_id = getattr(avatar, 'id', None)
                members = getattr(getattr(avatar, 'team', None), 'member_dict', None)
                current_member = (members.get(player_id)
                                  if player_id is not None and members is not None
                                  else None)
                current = (current_member.get('display_item_id', _V109_MISSING)
                           if current_member is not None else _V109_MISSING)
                event_type = args[0] if args else kwargs.get('event_type')
                _v109_log(('striker-team-event', repr(event_type), hero_id,
                           item_id, repr(current)),
                          'Striker Join Team event=%r self_join=True hero=%d '
                          'selected=%d linked=%s current=%r'
                          % (event_type, hero_id, item_id, linked, current), 2)
                member = current_member if item_id else None
                if member is not None:
                    old = member.get('display_item_id', _V109_MISSING)
                    genuine_old = (old is not _V109_MISSING and old
                                   and old != default_item and old != item_id
                                   and not injected_record(old))
                    if linked and genuine_old:
                        # Genuine server/team state beats an inferred linked
                        # action. Explicit native selections keep the existing
                        # local completion behavior.
                        _v109_log(('striker-team-genuine', hero_id, old, item_id),
                                  'Striker Join Team Action preserved genuine '
                                  'team item=%r hero=%d' % (old, hero_id), 2)
                        member = None
                        old = _V109_MISSING
                    else:
                        member['display_item_id'] = item_id
                        download = globals().get('try_dlc_download')
                        try:
                            result = (download(item_id, [])
                                      if callable(download) else ['unavailable'])
                        except Exception as exc:
                            result = ['guarded', repr(exc)]
                        _v109_log(('striker-team-display', hero_id, item_id),
                                  'Striker Join Team Action hero=%d item=%d '
                                  'source=%s supplied to official self-join consumer; '
                                  'authentic DLC result=%r gate unchanged'
                                  % (hero_id, item_id,
                                     'skin-linked' if linked else 'selected', result), 2)
        except Exception:
            member = None
            old = _V109_MISSING
        try:
            return previous(self, *args, **kwargs)
        finally:
            if member is not None:
                try:
                    if old is _V109_MISSING:
                        del member['display_item_id']
                    else:
                        member['display_item_id'] = old
                except Exception:
                    pass
    return wrapper


def striker_postmatch_factory(previous):
    def wrapper(self, *args, **kwargs):
        data = None
        old = _V109_MISSING
        try:
            avatar, _warehouse = native_avatar()
            hero_id = striker_current_hero(avatar)
            item_id = striker_selected_display(avatar, hero_id)
            getter = getattr(self, '_GetMvpCombatData', None)
            candidate = getter() if item_id and callable(getter) else None
            player_id = getattr(avatar, 'id', None)
            mvp_id = candidate.get('id') if candidate is not None else None
            same_player = (player_id is not None and mvp_id is not None
                           and (mvp_id == player_id or _v109_int(mvp_id, 0) == _v109_int(player_id, -1)))
            if candidate is not None and same_player:
                data = candidate
                old = data.get('display_item_id', _V109_MISSING)
                data['display_item_id'] = item_id
                _v109_log(('striker-postmatch-display', hero_id, item_id),
                          'Striker post-match action hero=%d item=%d supplied with official DLC gate intact'
                          % (hero_id, item_id), 2)
        except Exception:
            data = None
            old = _V109_MISSING
        try:
            return previous(self, *args, **kwargs)
        finally:
            if data is not None:
                try:
                    if old is _V109_MISSING:
                        del data['display_item_id']
                    else:
                        data['display_item_id'] = old
                except Exception:
                    pass
    return wrapper


def local_equip(owner, rpc, params, persist=True):
    """Complete one injected item's native equip locally; never genuine rows."""
    rec = None
    item_index = -1
    for index, value in enumerate(params):
        rec = injected_record(value)
        if rec is not None:
            item_index = index
            break
    if rec is None:
        return False
    item_id, category, item = rec
    row = getattr(item, 'item_proto', None) or _v109_row(item_id)
    guid = getattr(item, 'guid', None)
    panpan_before_guid = (getattr(owner, 'arm_panpan', '')
                          if rpc == 'ApplyPanpan' else '')
    if rpc == 'ApplyMelee':
        native = melee_native_receiver(
            owner, item_id, guid,
            params[1] if len(params) > 1 else False, persist=persist)
        if native is not None:
            return native
        return melee_complete_fields(
            owner, item_id, guid,
            params[1] if len(params) > 1 else False, persist=persist)
    operations = []

    def one_attr(name, value):
        operations.append(('attr', name, value))

    def one_map(name, key, value):
        operations.append(('map', (name, key), value))

    def one_obj(name, key, field, value):
        operations.append(('obj', (name, key, field), value))

    if rpc == 'ArmVehicleSkin' and len(params) >= 2:
        one_map('vehicle_skins', params[1], item_id)
    elif rpc in ('ArmGunSkin', 'ArmGunGuise') and len(params) >= 2:
        gun_id = params[0]
        # Official IGunInfo skin/guise template IDs are getter-only computed
        # properties.  Mutate only the stored item/random fields; attempting to
        # assign the derived properties aborts native equip on getter-only
        # implementations and can never be a substitute for visual readback.
        if rpc == 'ArmGunSkin':
            one_obj('gun_infos', gun_id, 'skin_item_id', item_id)
            if len(params) > 3:
                one_obj('gun_infos', gun_id, 'skin_random', params[3])
        else:
            one_obj('gun_infos', gun_id, 'guise_item_id', item_id)
            if len(params) > 3:
                one_obj('gun_infos', gun_id, 'guise_random', params[3])
    elif rpc in ('ArmHeroSkin', 'ArmLowLevelSkin',
                 'ArmSkinExecuteItem', 'ArmDisplayItem'):
        # These have dedicated sequence/nested-list handlers in the RPC gate.
        return False
    elif rpc == 'ArmHeroTransform' and len(params) == 2:
        if item_index != 1 or _v109_int(params[1], 0) != item_id:
            return False
        binding = striker_transform_binding(item_id)
        if binding is None or binding[0] != _v109_int(params[0], 0):
            _v109_log(('striker-transform-binding', item_id),
                      'Striker transform item=%d has no matching official binding; withheld'
                      % item_id, 2)
            return False
        operations.append(('hero_map', (
            'hero_infos', binding[0], 'skin_transform_item_map', binding[1]), item_id))
    elif rpc in ('SetHeroSkinEffectShow',
                 'SetHeroSkinSlideEffectVisibility') and len(params) == 2:
        if item_index != 0:
            return False
        map_name = ('hero_skin_effect_show' if rpc == 'SetHeroSkinEffectShow'
                    else 'hero_skin_slide_effect_visibility')
        one_map(map_name, item_id, params[1])
    elif rpc == 'ArmHeroEmo':
        operations = emote_equip_plan(
            owner, params, item_index, item_id)
        if not operations:
            emote_probe(owner, params, 'unrecognized-equip')
            _v109_log(('emote-unrecognized', item_id, len(params)),
                      'EMOTE item=%d equip shape unrecognized; original RPC preserved'
                      % item_id, 1)
            return False
    elif rpc == 'ArmSkyBox':
        slot = None
        for index, value in enumerate(params):
            if index == item_index:
                continue
            number = _v109_int(value, -1)
            if 0 <= number <= 64:
                slot = number
                break
        if slot is None:
            return False
        one_map('skybox_info', slot, item_id)
    elif rpc == 'ApplyPanpan':
        # Official direct selection is CallServer('ApplyPanpan', guid).
        # Never confuse it with the separate random-favorite RPC/flow.
        if item_index != 0 or len(params) != 1:
            return False
        one_attr('arm_panpan', guid)
        if getattr(owner, 'arm_panpan_random', _V109_MISSING) \
                is not _V109_MISSING:
            one_attr('arm_panpan_random', False)
    elif rpc in ('ArmBombSkin', 'ArmMedicineSkin') and len(params) >= 2:
        one_map('bomb_skins' if rpc == 'ArmBombSkin' else 'medicine_skins',
                params[1], item_id)
    elif rpc == 'ApplyDeathBoxSkin':
        one_attr('death_box_skin_id', item_id)
    elif rpc == 'SetAircraftSkin':
        one_attr('aircraft_skin', item_id)
    elif rpc == 'SetParachuteSkin':
        # Official order: clear the aircraft slot, then set parachute.
        if not sky_clear_aircraft(owner, rpc):
            return False
        one_attr('parachute_skin', item_id)
    elif rpc == 'SetSkydiveSkin':
        if not sky_clear_aircraft(owner, rpc):
            return False
        one_attr('skydive_skin', item_id)
    elif rpc == 'ApplyTrailingSkin':
        if not sky_clear_aircraft(owner, rpc):
            return False
        one_attr('trailing_skin_item_id', item_id)
    elif rpc == 'SetAirDropItem':
        one_attr('airdrop_skin', item_id)
    elif rpc == 'SetVoicePackage':
        one_attr('voice_package', item_id)
    elif rpc == 'ArmBanner':
        one_attr('banner_item_id', item_id)
    elif rpc == 'ArmHallBackground':
        one_attr('hall_background_item_id', item_id)
    elif rpc == 'ArmHallMusic':
        one_attr('hall_music', item_id)
    elif rpc == 'SetNameFrame':
        one_attr('name_frame', item_id)
    elif rpc == 'ChangeHeadFrame':
        one_attr('head_frame', item_id)
    elif rpc == 'ChangeCardBackground':
        one_attr('card_background', item_id)
    elif rpc == 'ChangeHomepageBackground':
        one_attr('homepage_background', item_id)
    elif rpc == 'UseChatBubbles':
        one_attr('chat_bubbles_item_id', item_id)
    elif rpc == 'ArmAvatarItem':
        one_attr('avatar_item_id', item_id)
    else:
        return False
    cosmetic_slot = (_v109_cosmetic_slot(rpc, params)
                     if rpc in COSMETIC_RPC_CODES else None)
    if rpc in COSMETIC_RPC_CODES and cosmetic_slot is None:
        return False
    if not apply_equip(item_id, owner, operations):
        return False
    if rpc == 'ApplyPanpan':
        verified, observed = panpan_readback(owner, item_id, guid)
        if not verified:
            restore_item(_v109_state, item_id)
            panpan_notify(owner, guid)
            _v109_log(('playpal-equip-readback-mismatch', item_id),
                      'native PlayPal item=%d armed/direct/resolved/random=%r mismatch; genuine baseline restored'
                      % (item_id, observed), 2)
            return False
        notified = panpan_notify(owner, panpan_before_guid)
        _v109_log(('playpal-equip-readback', item_id, notified),
                  'native PlayPal equipped item=%d armed/direct/resolved/random=%r notify=%s'
                  % (item_id, observed, notified), 1)
    if rpc in ('ArmGunSkin', 'ArmGunGuise'):
        # A native CGunInfo setter is not acceptance evidence.  Read back every
        # stored field, then independently verify the official computed template
        # getter against the authentic nested lobby row.  Never write or restore
        # that derived property directly.  Any mismatch restores the genuine
        # baseline; the gun RPC gate below also withholds the injected GUID.
        observed = []
        matched = True
        for kind, key, expected in operations:
            ok, actual = path_get(owner, kind, key)
            observed.append(actual)
            matched = matched and ok and actual == expected
        template_kind = 'skin' if rpc == 'ArmGunSkin' else 'guise'
        template_field = template_kind + '_template_id'
        template_row = _v109_field(row, template_kind, {}) or {}
        expected_template = _v109_int(
            _v109_field(template_row, 'template_id', 0), 0)
        ok, actual_template = path_get(
            owner, 'obj', ('gun_infos', params[0], template_field))
        observed.append(actual_template)
        matched = (matched and ok and expected_template > 0
                   and actual_template == expected_template)
        if not matched:
            restore_item(_v109_state, item_id)
            _v109_log(('gun-equip-readback-mismatch', rpc, item_id),
                      'native gun equip RPC=%s item=%d readback=%r mismatch; genuine baseline restored'
                      % (rpc, item_id, observed), 2)
            return False
        _v109_log(('gun-equip-readback', rpc, item_id),
                  'native gun equip RPC=%s item=%d readback=%r'
                  % (rpc, item_id, observed), 2)
    if rpc in ('ArmHeroTransform', 'SetHeroSkinEffectShow',
               'SetHeroSkinSlideEffectVisibility'):
        if not striker_verify(item_id, owner, operations, rpc):
            return False
    if rpc == 'ArmHeroEmo':
        emote_remember_pick(item_id, operations, persist=persist)
    elif rpc == 'ApplyPanpan':
        panpan_remember_pick(item_id, persist=persist)
    elif rpc in COSMETIC_RPC_CODES and persist:
        cosmetic_remember_pick(
            rpc, cosmetic_slot, item_id, persist=True)
    # v2.105: download-cloud on selection - the model build's
    # synchronous resource load must never block the game thread
    # 39-75s waiting for bundles nobody requested (round-122).
    try:
        if item_id:
            _dl2105 = globals().get('try_dlc_download')
            if callable(_dl2105):
                _dl2105(item_id, [])
    except Exception:
        pass
    _v109_log(('local-equip', rpc, item_id),
              'local equip RPC=%s item=%d category=%s' % (rpc, item_id, category), 1)
    if category in ('vehicle', 'other'):
        # These families have no model readback of their own (unlike guns and
        # hero skins); the official setters are plain avatar fields, so the
        # stored value IS the acceptance evidence.  Print it so the next device
        # log shows exactly what landed per slot.
        observed = []
        for kind, key, expected in operations:
            ok, actual = path_get(owner, kind, key)
            observed.append((key, actual, ok and actual == expected))
        _v109_log(('slot-readback', rpc, item_id),
                  'native slot readback RPC=%s item=%d category=%s values=%r'
                  % (rpc, item_id, category, observed), 2)
    # v10.12.2-lagfix-r1: "equipped but did not work" on device.
    #
    # Writing the slot is only half of an equip.  The other half is what the
    # game's own consumers READ back out of that slot when they build the
    # visual - GetAircraftItemList / GetAirDropItemList / GetTrailingItemList /
    # GetDeathBoxItemList in WarehouseItemWindow (warehouse_item_methods.txt),
    # and the matching Arm*/Apply* state in a match.  If the write lands in a
    # field the consumer does not read, the RPC still reports success while
    # nothing changes on screen - exactly the report.
    #
    # So resolve the SAME slot through the official getter (when one exists)
    # and log stored-vs-consumed.  No guessing, no rewriting: this is a probe
    # that makes the next log decisive.
    try:
        getter_name = COSMETIC_READBACK_GETTERS.get(rpc)
        if getter_name and owner is not None:
            getter = getattr(owner, getter_name, None)
            if callable(getter):
                consumed = None
                try:
                    consumed = getter()
                except Exception as exc:
                    consumed = 'err=%r' % (exc,)
                _v109_log(('slot-consumer', rpc, item_id),
                          'native slot consumer RPC=%s item=%d getter=%s '
                          'consumed=%r stored=%r'
                          % (rpc, item_id, getter_name,
                             consumed,
                             [entry[1] for entry in observed]), 2)
            else:
                _v109_log(('slot-consumer-missing', rpc, item_id),
                          'native slot consumer RPC=%s item=%d getter=%s '
                          'absent on %s'
                          % (rpc, item_id, getter_name,
                             type(owner).__name__), 2)
    except Exception:
        pass
    return True


# Exact official PlayerAvatarMember entry points.  The item/GUID position is
# method-specific: intercepting every integer would break gun/equip/slot IDs.
# ArmPartGuise is deliberately absent; its nested dictionary is not this RPC's
# flat item contract and must retain the original implementation.
# v10.12.2-lagfix-r1: official READ side of each cosmetic slot. Used only by
# the consumer probe above; nothing is written from this table.
COSMETIC_READBACK_GETTERS = {
    'SetSkydiveSkin': 'GetSkydiveSkinItemId',
    'SetParachuteSkin': 'GetParachuteSkinItemId',
    'SetAircraftSkin': 'GetAircraftSkinItemId',
    'ApplyTrailingSkin': 'GetTrailingSkinItemId',
    'SetAirDropItem': 'GetAirDropItemId',
    'ApplyDeathBoxSkin': 'GetDeathBoxSkinItemId',
    'ArmVehicleSkin': 'GetVehicleSkinItemId',
    'ArmBombSkin': 'GetBombSkinItemId',
    'ArmMedicineSkin': 'GetMedicineSkinItemId',
}

# ============================ v2.113 ===================================
# The GAMEPLAY display fix: the game builds the in-match med/grenade/trail/
# airdrop/deathbox/vehicle models from these official readback getters and
# got 0 for unowned items (the vault equip worked, gameplay showed default).
# Wrap them: a genuine owned readback ALWAYS wins; otherwise return the
# locally saved pick, gated on the family's menu checkbox.
RPC_FLAGS = {
    'SetSkydiveSkin': 'bUnlockSkydive',
    'SetAircraftSkin': 'bUnlockSkydive',
    'ApplyTrailingSkin': 'bUnlockSkydive',
    'SetParachuteSkin': 'bUnlockParachute',
    'SetAirDropItem': 'bUnlockLoadoutDrop',
    'ApplyDeathBoxSkin': 'bUnlockMeds',
    'ArmVehicleSkin': 'bUnlockVehicles',
    'ArmBombSkin': 'bUnlockGrenades',
    'ArmMedicineSkin': 'bUnlockMeds',
}


def flag_on(key):
    try:
        if sync_attrs.get('bUnlockAllVault', False):
            return True
        if sync_attrs.get(key, False):
            return True
        return bool(_unlock_should_force(key))
    except Exception:
        return False


def local_pick(rpc):
    if not flag_on(RPC_FLAGS.get(rpc, 'bUnlockAllVault')):
        return 0
    try:
        saved = globals().get('COSMETIC_SAVED') or {}
        val = saved.get((rpc, 0), 0)
        if not val:
            for (r, _h), v in saved.items():
                if r == rpc and v:
                    val = v
        return _safe_int(val, 0)
    except Exception:
        return 0


def readback_factory(prev, getter):
    rpc = None
    for _r, _g in (globals().get('COSMETIC_READBACK_GETTERS') or {}).items():
        if _g == getter:
            rpc = _r
            break
    # the getter->rpc inverse may be absent (self map); resolve lazily
    def wrapper(*a, **k):
        try:
            r = prev(*a, **k)
        except Exception:
            r = 0
        if r:
            return r
        try:
            pick = local_pick(rpc) if rpc else 0
        except Exception:
            pick = 0
        return pick if pick else r
    wrapper._v109_wrap = True
    wrapper._label = 'readback:' + getter
    return wrapper


# ============================ v2.114 ===================================
# The gameplay-display layer: the visual consumers read IsEnable*Skin gates
# and the Get*SkinItemId readbacks.  Wrap both, EVERYWHERE they exist (the
# consumer probe proved the getters are absent on PlayerAvatar), plus a
# bounded family-token probe so any leftover consumer lands in the log.
ENABLE_METHODS = (
    'IsEnableBombSkin', 'IsEnableGrenadeSkin', 'IsEnableDeathBoxSkin',
    'IsEnableVehicleSkin', 'IsEnableMedicineSkin', 'IsEnableSkydiveSkin',
    'IsEnableParachuteSkin', 'IsEnableTrailingSkin', 'IsEnableAirDropSkin',
    'IsEnableAircraftSkin',
)


def enable_factory(prev):
    def wrapper(*a, **k):
        try:
            return True
        except Exception:
            return prev(*a, **k)
    wrapper._v109_wrap = True
    wrapper._label = 'enable-skin'
    return wrapper


def walk_classes():
    # v2.114: scan each gclient module only once (the install retries every
    # 5s); new modules are picked up as the game lazy-loads them.
    scanned = _v2114_scanned
    seen = seen_classes
    for name, module in list(sys.modules.items()):
        if not name.startswith('gclient') or module is None or name in scanned:
            continue
        scanned.add(name)
        try:
            for attr in dir(module):
                cls = getattr(module, attr, None)
                if isinstance(cls, type) and id(cls) not in seen:
                    seen.add(id(cls))
                    yield cls
        except Exception:
            continue


_v2114_scanned = set()
seen_classes = set()


# ============================ v2.119 ===================================
# v2.114 base + targeted display/vault hooks only.  Everything installs
# ONCE from exact module paths (the runtime dump named them); after that
# the install chain costs nothing.  No class walks, no show-method wraps,
# no queue policy changes.
DONE = [False]


def _v2119_flag_on(flag):
    try:
        return bool(sync_attrs.get(flag, False)
                    or sync_attrs.get('bUnlockAllVault', False)
                    or _unlock_should_force(flag))
    except Exception:
        return False


def any_flag():
    try:
        if sync_attrs.get('bUnlockAllVault', False):
            return True
        for _f in ('bUnlockGrenades', 'bUnlockMeds', 'bUnlockSkydive',
                   'bUnlockParachute', 'bUnlockLoadoutDrop',
                   'bUnlockVehicles', 'bUnlockEmotes'):
            if _v2119_flag_on(_f):
                return True
    except Exception:
        pass
    return False


GATE_FLAGS = {
    'IsEnableBombSkin': 'bUnlockGrenades',
    'IsEnableDeathBox': 'bUnlockMeds',
    'IsEnableSkydive': 'bUnlockSkydive',
    'IsEnableAircraft': 'bUnlockSkydive',
    'CheckCanShowCloseParachute': 'bUnlockParachute',
}

FLAG_CLASSES = (
    ('gclient.framework.entities.avatar', 'PlayerAvatar'),
    ('gclient.framework.entities.avatarmembers.cimp_abc',
     'PlayerAvatarMember'),
    ('gclient.framework.entities.avatarmembers.cimp_csharp_battle',
     'PlayerAvatarMember'),
    ('gclient.framework.entities.avatarmembers.cimp_debug',
     'PlayerAvatarMember'),
    ('gclient.framework.entities.avatarmembers.cimp_hall_item',
     'PlayerAvatarMember'),
)


def gate_factory(prev, flag):
    def wrapper(*a, **k):
        try:
            if _v2119_flag_on(flag):
                return True
        except Exception:
            pass
        return prev(*a, **k)
    wrapper._v109_wrap = True
    wrapper._label = 'v2119-gate'
    return wrapper


def _v2119_readback_factory(prev, rpc):
    def wrapper(*a, **k):
        # the PICK wins - dict lookup only, never scans (the scans were
        # part of the per-frame lag family).
        try:
            pick = COSMETIC_SAVED.get((rpc, 0), 0)
            if pick and _v2119_flag_on(RPC_FLAGS.get(rpc, '')):
                return _v109_int(pick, 0)
        except Exception:
            pass
        return prev(*a, **k)
    wrapper._v109_wrap = True
    wrapper._label = 'v2119-readback'
    return wrapper


def row_flags(row):
    try:
        keys = tuple(row.keys()) if isinstance(row, dict) else tuple(dir(row))
    except Exception:
        return
    for key in keys:
        low = str(key).lower()
        try:
            cur = row.get(key) if isinstance(row, dict) \
                else getattr(row, key, None)
        except Exception:
            continue
        if not isinstance(cur, (bool, int)):
            continue
        try:
            if any(t in low for t in ('owned', 'unlock', 'can_equip',
                                      'can_use', 'can_select')):
                new = True
            elif any(t in low for t in ('lock', 'limit')):
                new = False
            else:
                continue
            if isinstance(row, dict):
                row[key] = new
            else:
                setattr(row, key, new)
        except Exception:
            continue


def list_factory(prev, name):
    def wrapper(*a, **k):
        result = None
        forced = False
        try:
            k2 = dict(k)
            k2['include_locked'] = True
            result = prev(*a, **k2)
            forced = True
        except TypeError:
            try:
                result = prev(*a, **k)
            except Exception:
                result = None
        except Exception:
            try:
                result = prev(*a, **k)
            except Exception:
                result = None
        try:
            rows = list(result) if result is not None else []
            if rows and any_flag():
                for row in rows[:400]:
                    row_flags(row)
            _v109_log(('v2119-list', name),
                      'subtype list %s rows=%d incl=%s'
                      % (name, len(rows), forced), 2)
        except Exception:
            pass
        return result
    wrapper._v109_wrap = True
    wrapper._label = 'v2119-list'
    return wrapper


def true_factory(prev, name):
    def wrapper(*a, **k):
        try:
            if any_flag():
                return True
        except Exception:
            pass
        return prev(*a, **k)
    wrapper._v109_wrap = True
    wrapper._label = 'v2119-true'
    return wrapper


def install_display():
    added = []
    # 1. the visual gates on the avatar classes
    for modname, clsname in FLAG_CLASSES:
        mod = sys.modules.get(modname)
        cls = getattr(mod, clsname, None) if mod else None
        if not isinstance(cls, type):
            continue
        for meth, flag in GATE_FLAGS.items():
            key = (id(cls), 'v2119-gate:' + meth)
            if key in install_seen:
                continue
            if not callable(getattr(cls, meth, None)):
                continue
            if _v109_wrap_method(cls, meth,
                                 lambda prev, f=flag:
                                 gate_factory(prev, f)):
                install_seen.add(key)
                added.append('%s.%s' % (clsname, meth))
    # 2. the real case-class readback (pick wins)
    for modname, mod in list(sys.modules.items()):
        if not modname.startswith(
                'gclient.gameplay.logic_base.equips.') or mod is None:
            continue
        for attr in dir(mod):
            cls = getattr(mod, attr, None)
            if not isinstance(cls, type):
                continue
            key = (id(cls), 'v2119-readback:_GetCombatMedicineSkinId')
            if key in install_seen:
                continue
            if callable(getattr(cls, '_GetCombatMedicineSkinId', None)):
                if _v109_wrap_method(
                        cls, '_GetCombatMedicineSkinId',
                        lambda prev: _v2119_readback_factory(
                            prev, 'ArmMedicineSkin')):
                    install_seen.add(key)
                    added.append('%s._GetCombatMedicineSkinId' % attr)
    # 3. the vault list + row gates on WarehouseItemWindow
    wmod = sys.modules.get(
        'gclient.gamesystem.uiwarehouse.warehouse_item_window')
    wcls = getattr(wmod, 'WarehouseItemWindow', None) if wmod else None
    if isinstance(wcls, type):
        for meth in ('GetItemListBySubType', 'GetRealItemListBySubType'):
            key = (id(wcls), 'v2119-list:' + meth)
            if key not in install_seen and                     callable(getattr(wcls, meth, None)):
                if _v109_wrap_method(wcls, meth,
                                     lambda prev, m=meth:
                                     list_factory(prev, m)):
                    install_seen.add(key)
                    added.append('WarehouseItemWindow.%s' % meth)
        for meth in ('CheckDLcExist', 'CheckBreakItem',
                     'IsShowModelPreviewItem', 'IsShowModelPreviewSkin'):
            key = (id(wcls), 'v2119-true:' + meth)
            if key not in install_seen and                     callable(getattr(wcls, meth, None)):
                if _v109_wrap_method(wcls, meth,
                                     lambda prev, m=meth:
                                     true_factory(prev, m)):
                    install_seen.add(key)
                    added.append('WarehouseItemWindow.%s' % meth)
    if added:
        _v109_log(('v2119-hooks', tuple(added)),
                  'v2119 targeted display/vault hooks=%r' % (added,), 1)
    return len(added)


_v2119_tries = [0]
# ========================== end v2.119 ===================================
def install_visual_gates():
    added = 0
    getters = list((globals().get('COSMETIC_READBACK_GETTERS')
                    or {}).values())
    getters += ['GetAvatarItemId', 'GetAvatarIconItemId']
    probe_key = 'v2114-probe'
    for cls in walk_classes():
        for method in ENABLE_METHODS:
            if not callable(getattr(cls, method, None)):
                continue
            key = (id(cls), 'v2114-enable:' + method)
            if key in install_seen:
                continue
            if _v109_wrap_method(cls, method,
                                 lambda prev: enable_factory(prev)):
                install_seen.add(key)
                added += 1
        for getter in getters:
            if not callable(getattr(cls, getter, None)):
                continue
            key = (id(cls), 'v2114-readback:' + getter)
            if key in install_seen:
                continue
            if _v109_wrap_method(cls, getter,
                                 (lambda prev, getter=getter:
                                  readback_factory(prev, getter))):
                install_seen.add(key)
                added += 1
        if (probe_key, id(cls)) not in install_seen:
            try:
                hits = [m for m in dir(cls) if
                        ('Parachute' in m or 'AirDrop' in m or 'Aircraft' in m
                         or 'Trailing' in m or 'Skydive' in m
                         or 'Medicine' in m or 'DeathBox' in m
                         or 'Bomb' in m or 'Grenade' in m) and
                        ('Get' in m or 'Enable' in m or 'Show' in m
                         or 'Create' in m or 'Play' in m)]
                if hits:
                    install_seen.add((probe_key, id(cls)))
                    _v109_log(('v2114-probe', cls.__name__),
                              'visual-consumer candidates cls=%s %r'
                              % (cls.__name__, hits[:24]), 1)
            except Exception:
                pass
    return added

# ========================== end v2.114 ===================================
def install_readback_getters():
    """Wrap the cosmetic readback getters on the avatar member classes."""
    added = 0
    getters = list((globals().get('COSMETIC_READBACK_GETTERS')
                    or {}).values()) + ['GetAvatarItemId', 'GetAvatarIconItemId']
    modules = (
        'gclient.gamesystem.entities.avatarmembers',
        'gclient.gamesystem.entities.avatarmembers.cimp_backpack',
        'gclient.gamesystem.entities.avatarmembers.cimp_hall_item',
        'gclient.gamesystem.entities.avatarmembers.cimp_zone',
    )
    for module_name in modules:
        module = sys.modules.get(module_name)
        cls = getattr(module, 'PlayerAvatarMember', None) if module else None
        if not isinstance(cls, type):
            continue
        for getter in getters:
            if not callable(getattr(cls, getter, None)):
                continue
            key = (id(cls), 'v2113-readback:' + getter)
            if key in install_seen:
                continue
            factory = (lambda prev, getter=getter:
                       readback_factory(prev, getter))
            if _v109_wrap_method(cls, getter, factory):
                install_seen.add(key)
                added += 1
            elif getattr(getattr(cls, getter, None), '_v109_wrap', False):
                install_seen.add(key)
    return added

# ========================== end v2.113 ===================================


MEMBER_METHODS = {
    'ArmGunSkin': ('ArmGunSkin', 1,
                   ('gun_id', 'skin_guid', 'need_publish', 'skin_random')),
    'ArmGunGuise': ('ArmGunGuise', 1,
                    ('gun_id', 'guise_guid', 'need_publish', 'guise_random')),
    'ArmVehicleSkin': ('ArmVehicleSkin', 0, ('item_id', 'vehicle_type')),
    'ArmBombSkin': ('ArmBombSkin', 0, ('item_id', 'equip_id')),
    'ArmMedicineSkin': ('ArmMedicineSkin', 0, ('item_id', 'equip_id')),
    'ApplyDeathBoxSkin': ('ApplyDeathBoxSkin', 0, ('guid',)),
    'ArmHeroSkin': ('ArmHeroSkin', 1, ('hero_id', 'skin_item_id')),
    'SetNameFrame': ('SetNameFrame', 0, ('item_id',)),
    'SetAvatarHallMusic': ('ArmHallMusic', 0, ('item_id',)),
    'SetAvatarHallBackground': ('ArmHallBackground', 0, ('item_id',)),
    'ChangeHeadFrame': ('ChangeHeadFrame', 0, ('head_frame_item_id',)),
    'ChangeCardBg': ('ChangeCardBackground', 0, ('card_bg_item_id',)),
    'ChangeHomepageBackground': (
        'ChangeHomepageBackground', 0, ('homepage_background_item_id',)),
    'ChangeChatBubble': ('UseChatBubbles', 0, ('chat_bubbles_item_id',)),
    # v2.113: the profile-avatar equip RPC (the name is not
    # confirmed on device yet - tolerant candidates; the
    # discovery probe below lists the class's real names).
    'SetAvatarItem': ('ArmAvatarItem', 0, ('item_id',)),
    'SetAvatarIcon': ('ArmAvatarItem', 0, ('item_id',)),
    'ChangeAvatar': ('ArmAvatarItem', 0, ('item_id',)),
    'ChangeAvatarIcon': ('ArmAvatarItem', 0, ('item_id',)),
    'SetPlayerAvatar': ('ArmAvatarItem', 0, ('item_id',)),
    'ChangePlayerAvatar': ('ArmAvatarItem', 0, ('item_id',)),
    'SetHeadIcon': ('ArmAvatarItem', 0, ('item_id',)),
}


def member_factory(previous, method):
    rpc, item_index, names = MEMBER_METHODS[method]

    def wrapper(*args, **kwargs):
        if not args:
            return previous(*args, **kwargs)
        owner = args[0]
        injected_any = None
        for value in tuple(args[1:]) + tuple(kwargs.values()):
            try:
                injected_any = injected_record(value)
            except Exception:
                injected_any = None
            if injected_any is not None:
                break
        params = []
        for index, name in enumerate(names):
            if index + 1 < len(args):
                value = args[index + 1]
            elif name in kwargs:
                value = kwargs[name]
            else:
                break
            params.append(value)
        if len(params) <= item_index:
            if injected_any is not None:
                _v109_log(('member-malformed-withheld', method, injected_any[0]),
                          'native member=%s item=%d malformed local-only call withheld'
                          % (method, injected_any[0]), 2)
                return None
            return previous(*args, **kwargs)
        record = injected_record(params[item_index])
        try:
            if record is None and injected_any is None and any_enabled():
                warehouse = method_warehouse(owner)
                state = _v109_prepare(warehouse, defer=True)
                if state is not None and not state.get('busy'):
                    ensure_item(
                        warehouse, params[item_index], mode='single')
                record = injected_record(params[item_index])
        except Exception as exc:
            _v109_log(('member-ensure', method, repr(exc)),
                      'native member=%s injected-item preflight error=%r'
                      % (method, exc), 1)
        if record is None:
            if injected_any is not None:
                _v109_log(('member-position-withheld', method, injected_any[0]),
                          'native member=%s item=%d appeared outside the official item position; call withheld'
                          % (method, injected_any[0]), 2)
                return None
            return previous(*args, **kwargs)
        # Once a local-only record is identified, every outcome is terminal.
        # In particular, a malformed call must not leak its GUID upstream.
        unsupported = (len(args) - 1 > len(names)
                       or any(key not in names for key in kwargs))
        completed = False
        try:
            if not unsupported:
                if rpc == 'ArmHeroSkin':
                    completed = striker_hero_skin(
                        owner, tuple(params), persist=True)
                else:
                    completed = local_equip(
                        owner, rpc, tuple(params), persist=True)
        except Exception as exc:
            _v109_log(('member-equip-error', method, repr(exc)),
                      'native member=%s local completion error=%r'
                      % (method, exc), 1)
        if not completed:
            _v109_log(('member-equip-withheld', method, record[0], unsupported),
                      'native member=%s item=%d local completion failed unsupported=%s; injected value withheld'
                      % (method, record[0], unsupported), 2)
        return None
    return wrapper


def call_server_factory(previous):
    def wrapper(*args, **kwargs):
        if len(args) >= 2:
            owner, rpc, params = args[0], args[1], args[2:]
            if isinstance(rpc, str):
                if rpc in ('PlayEmote', 'TeamShowEmote'):
                    # Official local playback already owns these broadcasts.
                    # Observe exactly one original call; never repeat it or
                    # mistake a return value for teammate/second-client proof.
                    try:
                        result = previous(*args, **kwargs)
                    except Exception as exc:
                        _v109_log(('emote-broadcast-exception', rpc,
                                   type(exc).__name__),
                                  'native emote broadcast RPC=%s params=%r raised=%r; visibility unverified'
                                  % (rpc, params, exc), 2)
                        raise
                    _v109_log(('emote-broadcast-result', rpc,
                               tuple(repr(value) for value in params),
                               repr(result)),
                              'native emote broadcast RPC=%s params=%r original_result=%r; one official call, second-client visibility unverified'
                              % (rpc, params, result), 2)
                    return result
                if rpc == 'ArmHeroEmo':
                    emote_probe(owner, params, 'PlayerAvatar.CallServer')
                if rpc not in ACTIVE_LOCAL_RPCS:
                    # Sequential equip repairs: genuine RPCs always pass through,
                    # but a not-yet-mapped injected GUID must never reach the
                    # server.  Its native list row remains local and removable.
                    if any(injected_record(value) is not None
                           for value in params):
                        _v109_log(('deferred-local-rpc', rpc),
                                  'local equip RPC=%s is pending scoped consumer repair; injected GUID withheld'
                                  % rpc, 1)
                        return None
                    return previous(*args, **kwargs)
                if rpc == 'PanpanHallPlaying':
                    try:
                        if panpan_hall_playing(owner, params):
                            return None
                    except Exception as exc:
                        _v109_log(('playpal-wheel-rpc-error', repr(exc)),
                                  'native PlayPal wheel RPC guarded error=%r'
                                  % (exc,), 1)
                        if any(injected_record(value) is not None
                               for value in params):
                            return None
                if rpc == 'ArmHeroTransform':
                    # Official zero unequip is genuine and must still reach the
                    # server; only matching local entries are cleared locally.
                    striker_transform_zero(owner, params)
                if rpc == 'ArmLowLevelSkin':
                    if striker_low_level(owner, params):
                        return None
                if rpc == 'ArmHeroSkin':
                    if striker_hero_skin(owner, params):
                        return None
                if rpc in ('ArmSkinExecuteItem', 'ArmDisplayItem'):
                    engaged, genuine_entries = striker_action_rpc(
                        owner, rpc, params)
                    if engaged:
                        if genuine_entries:
                            forward_args = ((owner, rpc, genuine_entries)
                                            + tuple(args[3:]))
                            return previous(*forward_args, **kwargs)
                        return None
                if (rpc == 'ApplyMelee' and MELEE_RECEIVER_DEPTH[0]
                        and params and injected_record(params[0])):
                    # We are inside the official ApplyMelee -> CallServer
                    # forward.  The outer receiver/local-equip frame owns the
                    # single completion; invoking it here caused RecursionError.
                    return None
                if (rpc in ('ArmGunSkin', 'ArmGunGuise')
                        and any(injected_record(value) is not None
                                for value in params)):
                    # Gun success and failure are both local terminal outcomes.
                    # Never fall through to a server RPC with a local-only GUID.
                    if not local_equip(owner, rpc, params):
                        _v109_log(('gun-equip-withheld', rpc),
                                  'native gun equip RPC=%s failed local validation; injected GUID withheld'
                                  % rpc, 2)
                    return None
                if (rpc in ('ArmHeroTransform', 'SetHeroSkinEffectShow',
                            'SetHeroSkinSlideEffectVisibility')
                        and any(injected_record(value) is not None
                                for value in params)):
                    # Positive Striker transform/settings outcomes are local
                    # terminal too: validation failure must never leak the ID.
                    if not local_equip(owner, rpc, params):
                        _v109_log(('striker-equip-withheld', rpc),
                                  'Striker RPC=%s failed local validation; injected item withheld'
                                  % rpc, 2)
                    return None
                if (rpc == 'ApplyPanpan' and len(params) == 1
                        and any(injected_record(value) is not None
                                for value in params)):
                    # A field write is not PlayPal acceptance.  The local
                    # completion above verifies the official resolved item;
                    # failure is terminal and must not leak our GUID upstream.
                    try:
                        completed = local_equip(owner, rpc, params)
                    except Exception as exc:
                        completed = False
                        _v109_log(('local-equip-error', rpc, repr(exc)),
                                  'local equip RPC=%s guarded error=%r'
                                  % (rpc, exc), 1)
                    if not completed:
                        _v109_log(('playpal-equip-withheld',),
                                  'native PlayPal local validation failed; injected GUID withheld', 2)
                    return None
                if rpc in LOCAL_RPCS:
                    try:
                        if local_equip(owner, rpc, params):
                            return None
                    except Exception as exc:
                        _v109_log(('local-equip-error', rpc, repr(exc)),
                                  'local equip RPC=%s guarded error=%r' % (rpc, exc), 1)
                else:
                    try:
                        if any(injected_record(value) is not None
                               for value in params):
                            _v109_log(('unmapped-local-rpc', rpc),
                                      'injected item reached unmapped RPC=%s argc=%d; original preserved'
                                      % (rpc, len(params)), 1)
                    except Exception:
                        pass
                if (rpc in COSMETIC_RPC_CODES
                        and (rpc not in STRIKER_PERSIST_RPCS
                             or rpc == 'ArmHeroTransform')
                        and not any(injected_record(value) is not None
                                    for value in params)):
                    cosmetic_slot = _v109_cosmetic_slot(rpc, params)
                    if cosmetic_slot is not None:
                        cosmetic_remember_pick(
                            rpc, cosmetic_slot, 0)
                        cosmetic_forget_baselines(
                            owner, rpc, cosmetic_slot)
                if rpc == 'ApplyMelee':
                    # Empty/random is a genuine server request.  Retire only
                    # our current local GUID first; a later genuine GUID wins.
                    if params and not params[0]:
                        melee_clear_local(owner)
                    # Reaching the genuine handler retires our saved local pick.
                    melee_remember_pick(0)
                elif rpc == 'ApplyPanpan' and not any(
                        injected_record(value) is not None
                        for value in params):
                    # A genuine direct pick/unequip retires the injected baseline.
                    panpan_remember_pick(0)
        return previous(*args, **kwargs)
    return wrapper


def native_arm_takeover(category):
    """Native Vault selection wins over the older menu-forced preview paint."""
    try:
        if not category_enabled(category):
            return False
        if category == 'melee':
            item_id = _v109_int(MELEE_SAVED.get('item_id'), 0) or \
                config_pick('iNativeMelee')
            record = injected_record(item_id) if item_id else None
            if record and record[1] == 'melee':
                return True
        return not bool(_hero_in_match())
    except Exception:
        return False


def native_equip_takeover(equip_id):
    try:
        melee = equip_id in (globals().get('WEP_MELEE_IDS') or {})
        return native_arm_takeover('melee' if melee else 'weapon')
    except Exception:
        return False


def remove_guid(warehouse, state, guid):
    tracked = state.get('injected', {}).get(guid)
    if not tracked:
        return False
    item_id, category, expected = tracked
    restore_item(state, item_id)
    removed = False
    try:
        current = warehouse.get(guid)
        # Never delete a server item which may have replaced our local GUID.
        if current is expected:
            del warehouse[guid]
            invalidate_item_index(warehouse)
            removed = True
    except Exception as exc:
        _v109_log(('remove-error', guid, repr(exc)),
                  'remove guid=%s item=%s failed: %r' % (guid, item_id, exc), 1)
        return None                 # keep tracking so the next read retries
    state['injected'].pop(guid, None)
    if state.get('by_item', {}).get(item_id) == guid:
        state['by_item'].pop(item_id, None)
        state.get('owned', set()).discard(item_id)
    return removed


def sync_state(warehouse, state):
    """Apply a config edge before any native read; unchanged calls are cheap."""
    signature = _v109_signature()
    if state.get('sig') == signature:
        return 0
    previous = state.get('sig')
    state['sig'] = signature
    if previous is None:
        return 0
    state['jobs'][:] = []
    state['pending'].clear()
    STRIKER_COMBAT_PENDING.clear()
    state['failed'].clear()
    state['completed'].clear()
    state['owned_at'] = 0.0
    state['warehouse'] = None
    if not category_enabled('melee'):
        visual_restore = globals().get('melee_visual_restore_all')
        if callable(visual_restore):
            visual_restore('category-off')
    removed = 0
    cleanup_failed = False
    for guid, (item_id, category, expected) in list(
            state.get('injected', {}).items()):
        if not category_enabled(category):
            result = remove_guid(warehouse, state, guid)
            cleanup_failed = cleanup_failed or result is None
            removed += int(bool(result))
    if not category_enabled('emote'):
        clear_saved_picks('emote')
    if not category_enabled('melee'):
        clear_saved_picks('melee')
    if not category_enabled('playpal'):
        clear_saved_picks('playpal')
    for category in ('weapon', 'vehicle', 'profile', 'other'):
        if not category_enabled(category):
            clear_saved_picks(category)
    if not category_enabled('striker'):
        clear_saved_picks('striker')
        STRIKER_PENDING.clear()
        STRIKER_MODEL_PENDING.clear()
    if cleanup_failed:
        # Keep the previous signature so the next native read retries instead
        # of forgetting a still-present injected GUID.
        state['sig'] = previous
    if removed:
        _v109_log(('cleanup', state.get('token'), signature, removed),
                  'disabled categories removed=%d; genuine owned items untouched'
                  % removed, 1)
    return removed


def create_native(item_id):
    """Construct a real IHallItem with an isolated, non-expiring prototype.

    IHallItem.item_proto normally resolves the shared lobby_item_data row.
    Mutating that row would also rewrite genuine inventory objects.  Instead,
    retain the native object's documented ``(item_id, proto)`` override with a
    deep copy belonging only to this injected GUID.  Prototype/activity/season
    expiry is cleared on that copy; the authoritative catalog is never edited.
    """
    module = sys.modules.get('gshare.ihall_item')
    creator = getattr(module, 'CreateHallItems', None) if module else None
    if not callable(creator):
        raise RuntimeError('native CreateHallItems unavailable')
    created = creator(item_id, 1, {'expire_time': 0})
    if not created:
        return None
    item = list(created)[0]
    if _v109_int(getattr(item, 'item_id', 0), 0) != item_id:
        raise ValueError('native item_id mismatch')
    guid = getattr(item, 'guid', None)
    if not guid:
        raise ValueError('native item has no GUID')
    authentic = getattr(item, 'item_proto', None)
    if authentic is None:
        raise ValueError('native item lost its authentic lobby row')
    try:
        copied = __import__('copy').deepcopy(authentic)
    except Exception as exc:
        raise ValueError('native prototype cannot be isolated: %r' % (exc,))
    if copied is authentic:
        raise ValueError('native prototype copy aliases the authentic row')
    # v10.12.2-lagfix-r1: DO NOT INVENT an expiry field.
    #
    # This used to write `copied['end_time'] = 0`.  The r1/r5 device logs
    # (63 and 70 times respectively, zero times in the two builds that never
    # opened the warehouse list) came back with:
    #
    #   [CRASH] TypeError: strptime() argument 0 must be str, not <class 'int'>
    #     warehouse_item_node.py in RefreshEmoteLimitedTime
    #     gshare/time_util.py in StrToZoneSecond
    #
    # The official engine's contract, decoded from gshare/ihall_item.py
    # `_fixed_expired` (ihall_item_native_all.dis): end_time is validated as
    #     if not end_time: return None
    #     StrToZoneSecond(end_time, zone)          <-- requires a STRING
    # so `0` is not "no expiry" to it; it is a type error raised inside the
    # warehouse list's own RefreshInfo, once per visible row, on the UI thread.
    # That is exactly the "delay on button icons" and the stutter when the
    # item list is on screen.
    #
    # Genuine lobby rows in the captured dumps carry NO end_time /
    # bind_activity / bind_qualifying keys at all - the engine treats a
    # missing key as falsy and returns None at the first guard.  So the honest
    # fix is to make our isolated copy look like a genuine row: remove the
    # keys entirely when the factory put them there, and never add them.
    for key in ('end_time', 'bind_activity', 'bind_qualifying',
                'expire_not_del'):
        try:
            if isinstance(copied, dict):
                if key in copied:
                    del copied[key]
            else:
                try:
                    del copied[key]
                except Exception:
                    try:
                        delattr(copied, key)
                    except Exception:
                        pass
        except Exception as exc:
            raise ValueError('native prototype expiry field=%s failed: %r'
                             % (key, exc))
    # This is IHallItem's own cached-prototype representation, not a new item
    # type or ownership spoof.  Verify the property actually retained it.
    item._item_proto = (item_id, copied)
    if getattr(item, 'item_proto', None) is not copied:
        raise ValueError('native item rejected its isolated prototype')
    # CreateHallItems owns the native expire_time setter.  If it refused the
    # requested zero value, do not hide that failure with a second forced write.
    if _v109_int(getattr(item, 'expire_time', 0), 0):
        raise ValueError('native factory refused expire_time=0')
    if bool(getattr(item, 'expired', False)):
        raise ValueError('native item is expired after isolated sanitization')
    if not bool(getattr(item, 'is_permanent', False)):
        raise ValueError('native item has no valid permanent contract')
    return item


def _v109_insert(warehouse, state, item_id, category):
    item_id = _v109_int(item_id, 0)
    if not item_id or not category_enabled(category):
        return False
    if item_id in state.get('by_item', {}):
        return False
    owned = state.get('owned')
    if owned is None:
        owned = native_item_ids(warehouse)
        state['owned'] = owned
    if item_id in owned:
        return False
    if len(state.get('injected', {})) >= MAX_TRACKED:
        _v109_log(('cap', state.get('token')),
                  'native injection cap=%d reached' % MAX_TRACKED, 1)
        return False
    item = None
    guid = None
    try:
        if category == 'melee' and not melee_equip(_v109_row(item_id)):
            raise ValueError('melee row has no native equip mapping')
        item = create_native(item_id)
        if item is None:
            raise ValueError('native constructor returned no item')
        guid = getattr(item, 'guid', None)
        if warehouse.get(guid) is not None:
            raise ValueError('native GUID collision')
        warehouse[guid] = item
        if warehouse.get(guid) is not item:
            raise ValueError('warehouse did not retain native item')
        if state.get('busy'):
            # Bulk Timer batches invalidate cheaply; the native list read after
            # the batch rebuilds once.  Do not turn N inserts into N full scans.
            invalidate_item_index(warehouse)
        elif not item_index_has(warehouse, item_id, guid):
            # A single ownership/equip read must resolve this GUID before its
            # original native method runs.  Its own read would rebuild anyway.
            raise ValueError('native item_id index did not retain GUID')
        else:
            _v109_log(('native-index', state.get('token'), item_id),
                      'native item=%d category=%s GUID ownership index verified'
                      % (item_id, category), 1)
        state['injected'][guid] = (item_id, category, item)
        state['by_item'][item_id] = guid
        state.setdefault('owned', set()).add(item_id)
        state.get('failed', {}).pop(item_id, None)
        _v109_log(('first-native-item', state.get('token'), category),
                  'native item=%d category=%s created with a real GUID'
                  % (item_id, category), 1)
        return True
    except Exception as exc:
        # If a native setter accepted the value and a later verification/event
        # failed, roll back our partial insertion instead of leaking an
        # untracked unlocked row.
        try:
            if item is not None and guid and warehouse.get(guid) is item:
                del warehouse[guid]
                invalidate_item_index(warehouse)
        except Exception:
            pass
        state.setdefault('failed', {})[item_id] = time.time()
        _v109_log(('insert', item_id, repr(exc)),
                  'native item=%d category=%s insertion failed: %r'
                  % (item_id, category, exc), 1)
        return False


def timer_callback(token):
    state = _v109_state
    if state.get('token') != token:
        return False
    state['timer'] = False
    warehouse = state_warehouse(state)
    if warehouse is None:
        state['jobs'][:] = []
        state['pending'].clear()
        return False
    try:
        sync_state(warehouse, state)
        return _v109_process(warehouse, state)
    except Exception as exc:
        _v109_log(('timer', token, repr(exc)),
                  'native timer batch failed: %r' % (exc,), 1)
        return False


def _v109_schedule(warehouse, state):
    if state.get('timer') or not state.get('jobs'):
        return False
    state['warehouse'] = warehouse
    try:
        timer = sys.modules.get('Timer')
        if timer is None:
            timer = __import__('Timer')
        add = getattr(timer, 'addTimer', None)
        if not callable(add):
            raise RuntimeError('Timer.addTimer unavailable')
        state['timer'] = True
        try:
            add(TIMER_DELAY, timer_callback, state['token'])
        except Exception:
            state['timer'] = False
            raise
        return True
    except Exception as exc:
        # A later native warehouse read continues the same bounded job.
        _v109_log(('schedule', repr(exc)),
                  'native Timer unavailable; batch will continue on vault reads: %r'
                  % (exc,), 1)
        return False


def _v109_process(warehouse, state):
    if state.get('busy'):
        return 0
    if not state.get('jobs'):
        state['warehouse'] = None
        return 0
    state['busy'] = True
    state['warehouse'] = warehouse
    # One native index refresh per batch, never once per candidate item.
    state.setdefault('owned', set()).update(native_item_ids(warehouse))
    state['owned_at'] = time.time()
    added = 0
    visited = 0
    started = time.time()
    try:
        while state.get('jobs') and visited < BATCH_SIZE:
            job = state['jobs'][0]
            entries = job.get('entries') or []
            if job.get('index', 0) >= len(entries):
                state['jobs'].pop(0)
                if job.get('cache_key') is not None:
                    state.get('completed', {})[job['cache_key']] = (
                        _v109_signature(), time.time())
                state['warehouse'] = warehouse if state['jobs'] else None
                _v109_log(('job-done', state.get('token'), job.get('serial')),
                          'native list=%s complete added=%d total=%d'
                          % (job.get('reason'), job.get('added', 0),
                             len(entries)), 1)
                continue
            item_id, category = entries[job.get('index', 0)]
            job['index'] = job.get('index', 0) + 1
            state.get('pending', set()).discard(item_id)
            visited += 1
            if category is None:
                category = _v109_category(item_id)
            if category is not None and category_enabled(category):
                inserted = _v109_insert(warehouse, state, item_id, category)
                added += int(bool(inserted))
                job['added'] = job.get('added', 0) + int(bool(inserted))
                if not inserted:
                    # v2.87: bounded attempts - the device re-queued the
                    # same 16 forever (queued=16 batch=16 added=0) and
                    # stalled the game thread 10-22s.
                    _tries287 = state.setdefault('tries287', {})
                    _n287 = _tries287.get(item_id, 0) + 1
                    _tries287[item_id] = _n287
                    if _n287 >= 3:
                        state.setdefault('dead287', set()).add(item_id)
            if visited > 1 and time.time() - started >= BATCH_SECONDS:
                break
        if not state.get('jobs'):
            state['warehouse'] = None
        return added
    finally:
        state['busy'] = False
        if state.get('jobs'):
            _v109_schedule(warehouse, state)


def _v109_queue(warehouse, item_ids, reason='items', immediate=False):
    if not any_enabled():
        return 0
    state = get_state(warehouse)
    sync_state(warehouse, state)
    try:
        candidates = list(item_ids or ())
    except Exception:
        candidates = []
    now = time.time()
    if (immediate and now - state.get('owned_at', 0.0) < 0.25
            and state.get('owned')):
        owned = set(state['owned'])
    else:
        owned = native_item_ids(warehouse)
        state['owned'] = set(owned)
        state['owned_at'] = now
    entries = []
    seen = set()
    for raw in candidates:
        item_id = _v109_int(raw, 0)
        if (not item_id or item_id in seen or item_id in owned
                or item_id in state.get('dead287', ())):
            continue
        seen.add(item_id)
        if item_id in state.get('by_item', {}):
            continue
        # A selected/equipping item is allowed to jump ahead of its own
        # pending list job.  Other callers never duplicate queued work.
        if not immediate and item_id in state.get('pending', set()):
            continue
        failed_at = state.get('failed', {}).get(item_id)
        if failed_at and now - failed_at < RETRY_FAILED_SECONDS:
            continue
        if immediate:
            row = _v109_row(item_id)
            category = _v109_category(item_id, row)
            if category is None or not category_enabled(category):
                continue
            entries.append((item_id, category))
        else:
            # Row/category resolution happens inside the timed game-thread
            # batches, not in this potentially large native list call.
            entries.append((item_id, None))
        if len(entries) + len(state.get('pending', set())) >= MAX_TRACKED:
            break
    if immediate and len(entries) == 1 and not state.get('busy'):
        item_id, category = entries[0]
        state.get('pending', set()).discard(item_id)
        return int(_v109_insert(warehouse, state, item_id, category))
    if not entries:
        if state.get('jobs'):
            if reason == 'ownership-list':
                _v109_schedule(warehouse, state)
            else:
                _v109_process(warehouse, state)
        return 0
    if reason == 'ownership-list':
        # Coalesce hundreds of CheckGunSkinOwned/GetItemByItemId calls into
        # one deferred job.  Do not inject a new batch inside each native
        # list-loop iteration; Timer runs after the native list returns.
        for job in reversed(state.get('jobs') or []):
            if job.get('reason') == 'ownership-list':
                job.setdefault('entries', []).extend(entries)
                state.setdefault('pending', set()).update(
                    item_id for item_id, _cat in entries)
                state['warehouse'] = warehouse
                _v109_schedule(warehouse, state)
                return len(entries)
    if len(state.get('jobs')) >= MAX_JOBS:
        _v109_log(('jobs-cap', reason), 'too many pending native lists; retry later', 1)
        return 0
    state['job_serial'] = state.get('job_serial', 0) + 1
    job = {
        'serial': state['job_serial'], 'reason': str(reason)[:80],
        'entries': entries, 'index': 0, 'added': 0,
        'cache_key': ((reason.startswith('detail:'), 
                       _v109_int(reason.split(':')[-1], 0))
                      if reason.startswith(('detail:', 'main:')) else None),
    }
    if reason == 'ownership-list':
        state['jobs'].append(job)
    else:
        state['jobs'].insert(0, job)
    state.setdefault('pending', set()).update(item_id for item_id, _cat in entries)
    state['warehouse'] = warehouse
    _v109_log(('queue', state.get('token'), job['serial']),
              'native list=%s queued=%d batch=%d'
              % (job['reason'], len(entries), BATCH_SIZE), 1)
    if reason == 'ownership-list':
        _v109_schedule(warehouse, state)
    else:
        _v109_process(warehouse, state)
    return len(entries)


def map_values(source, key):
    if source is None:
        return None
    value = None
    try:
        value = source.get(key)
        if value is None:
            value = source.get(str(key))
    except Exception:
        try:
            value = source[key]
        except Exception:
            value = None
    if value is None:
        return None
    if isinstance(value, dict):
        return list(value.keys())
    if isinstance(value, (int, str)) and not isinstance(value, bool):
        return [value]
    try:
        return list(value)
    except Exception:
        return [value]


def candidate_ids(sub_type, detail=True):
    """Use native subtype indexes; never walk the 65k lobby table here."""
    sub_type = _v109_int(sub_type, 0)
    if not sub_type:
        return []
    module = sys.modules.get('gshare.ihall_item')
    data_module = sys.modules.get('gclient.data.sub_type_to_item_ids_data')
    global_name = 'DETAIL_SUB_TYPE_TO_ITEM_IDS' if detail else 'SUB_TYPE_TO_ITEM_IDS'
    sources = [getattr(module, global_name, None) if module else None]
    if data_module is not None:
        sources.append(getattr(data_module, global_name, None))
        sources.append(getattr(data_module, 'data', None))
    for source in sources:
        values = map_values(source, sub_type)
        if values is not None:
            return values
    _v109_log(('index-missing', detail, sub_type),
              'native subtype index unavailable detail=%r subtype=%d'
              % (detail, sub_type), 1)
    return []


def call_mode():
    """Known native list/refresh loops defer; explicit equip calls win."""
    list_caller = False
    try:
        frame = sys._getframe(1)
        for _depth in range(10):
            if frame is None:
                break
            name = frame.f_code.co_name
            frame = frame.f_back
            if name.startswith('_v109_') or name == 'wrapper':
                continue
            if name in ('UseSkinImp', 'OnBtnEquip', 'OnEquip', 'EquipItem',
                        'ArmGunSkin', 'ArmGunGuise', 'ArmHeroSkin',
                        'ArmVehicleSkin', 'ArmBombSkin', 'ArmMedicineSkin',
                        'ArmPartGuise', 'SetNameFrame', 'OnBtnUse'):
                return 'equip'
            if (name.startswith(('Get', 'Refresh', 'Build', 'Iter', 'Show'))
                    or 'List' in name):
                list_caller = True
    except Exception:
        return 'single'
    return 'list' if list_caller else 'single'


def ensure_item(warehouse, item_id, mode=None):
    if warehouse is None or not any_enabled():
        return 0
    item_id = _v109_int(item_id, 0)
    if not item_id:
        return 0
    state = get_state(warehouse)
    if item_id in state.get('by_item', {}):
        return 0                       # already native; no extra index walk
    now = time.time()
    if (now - state.get('owned_at', 0.0) < 0.25
            and item_id in state.get('owned', set())):
        return 0                       # genuine/already native, original answers
    row = _v109_row(item_id)
    category = _v109_category(item_id, row)
    if category is None or not category_enabled(category):
        return 0                       # cheap fail-closed non-cosmetic path
    if mode is None:
        mode = call_mode()
    if mode == 'list':
        return _v109_queue(warehouse, [item_id], 'ownership-list',
                           immediate=False)
    return _v109_queue(warehouse, [item_id],
                       'item:%s' % item_id, immediate=True)


def ensure_subtype(warehouse, sub_type, detail=True):
    if warehouse is None or not any_enabled():
        return 0
    sub_type = _v109_int(sub_type, 0)
    if not detail and not main_supported(sub_type):
        return 0
    if not detail:
        main_name = _v109_main_name(sub_type)
        main_category = {
            'GunSkin': 'weapon', 'GunGuise': 'weapon',
            'MeleeWeapon': 'melee', 'Vehicle': 'vehicle',
            'Clothes': 'striker', 'Panpan': 'other',
        }.get(main_name)
        if main_category and not category_enabled(main_category):
            return 0
    state = get_state(warehouse)
    cache_key = (bool(detail), sub_type)
    now = time.time()
    cached = state.get('completed', {}).get(cache_key)
    if (cached and cached[0] == _v109_signature()
            and now - cached[1] < 1.0):
        return 0
    if detail:
        name = subtype_name(sub_type)
        category = SUBTYPE_CATEGORIES.get(name)
        # Suit/Body/Heirloom can contain a different special row category;
        # every unambiguous disabled detail type can skip queuing entirely.
        if (category and name not in ('Suit', 'Body', 'Heirloom')
                and not category_enabled(category)):
            return 0
    ids = candidate_ids(sub_type, detail)
    queued = _v109_queue(warehouse, ids, '%s:%d' % (
        'detail' if detail else 'main', sub_type))
    return queued


def _v109_prepare(warehouse, defer=False):
    if warehouse is None:
        return None
    state = get_state(warehouse)
    sync_state(warehouse, state)
    if state.get('jobs') and not state.get('busy') and not defer:
        _v109_process(warehouse, state)
    return state


def method_warehouse(owner):
    try:
        warehouse = getattr(owner, 'warehouse', None)
        if warehouse is not None:
            return warehouse
    except Exception:
        pass
    try:
        avatar_ref = globals().get('_avatar_seen_ref')
        avatar = avatar_ref() if callable(avatar_ref) else None
        return getattr(avatar, 'warehouse', None) if avatar is not None else None
    except Exception:
        return None


def _v109_arg(args, kwargs, name):
    if len(args) > 1:
        return args[1]
    return kwargs.get(name)


def item_factory(previous, direct=False):
    def wrapper(*args, **kwargs):
        owner = args[0] if args else None
        warehouse = owner if direct else method_warehouse(owner)
        if not direct:
            remember_melee_receiver(owner, warehouse)
        item_id = _v109_arg(args, kwargs, 'item_id')
        try:
            if warehouse is not None and any_enabled():
                # Never spend an equip/ownership read draining an older bulk
                # job.  The selected item may jump that job immediately;
                # Timer and subtype list reads advance bulk work instead.
                state = _v109_prepare(warehouse, defer=True)
                if state is not None and not state.get('busy'):
                    ensure_item(warehouse, item_id)
            elif warehouse is not None:
                _v109_prepare(warehouse)       # lazy OFF cleanup
        except Exception as exc:
            _v109_log(('item-wrapper', repr(exc)),
                      'item ensure guarded error=%r' % (exc,), 1)
        # No pending-row bool/count override: native ownership and getters
        # always agree on the same actual warehouse object.
        return previous(*args, **kwargs)
    return wrapper


def subtype_factory(previous, detail=True):
    def wrapper(*args, **kwargs):
        try:
            warehouse = args[0] if args else None
            state = _v109_prepare(warehouse, defer=True)
            if (state is not None and not state.get('busy')
                    and any_enabled()):
                ensure_subtype(
                    warehouse, _v109_arg(args, kwargs, 'sub_type'), detail)
        except Exception as exc:
            _v109_log(('subtype-wrapper', detail, repr(exc)),
                      'subtype ensure guarded error=%r' % (exc,), 1)
        return previous(*args, **kwargs)
    return wrapper


def subtype_list_factory(previous):
    def wrapper(*args, **kwargs):
        try:
            warehouse = args[0] if args else None
            state = _v109_prepare(warehouse, defer=True)
            if (state is not None and not state.get('busy')
                    and any_enabled()):
                values = _v109_arg(args, kwargs, 'sub_type_list') or ()
                for sub_type in list(values)[:128]:
                    ensure_subtype(warehouse, sub_type, True)
        except Exception as exc:
            _v109_log(('subtype-list-wrapper', repr(exc)),
                      'subtype-list ensure guarded error=%r' % (exc,), 1)
        return previous(*args, **kwargs)
    return wrapper


def _v109_wrap_method(cls, method, factory):
    guard = '_orig_v109_' + method
    try:
        static = inspect.getattr_static(cls, method)
        if getattr(static, '_v109_wrap', False):
            return False
        previous = (static.__func__ if isinstance(
            static, (staticmethod, classmethod)) else static)
        if not callable(previous):
            return False
        wrapper = factory(previous)
        wrapper._v109_wrap = True
        setattr(cls, guard, previous)
        try:
            if isinstance(static, staticmethod):
                setattr(cls, method, staticmethod(wrapper))
            elif isinstance(static, classmethod):
                setattr(cls, method, classmethod(wrapper))
            else:
                setattr(cls, method, wrapper)
        except Exception:
            try:
                delattr(cls, guard)
            except Exception:
                pass
            return False
        return True
    except Exception:
        return False


def bind_avatar_calls(avatar):
    """Repair official instance-bound RPCs when hooks install after avatar init.

    PlayerAvatar.init_from_dict stores bound CallServerOld/Offline objects on
    CallServer (and sometimes CallServerNew).  Rebinding only those known
    implementations is safe; an external area.call_server_new is left native.
    Already wrapped bound methods are idempotently preserved.
    """
    added = 0
    try:
        cls = type(avatar)
        for public in ('CallServer', 'CallServerNew'):
            try:
                current = getattr(avatar, public, None)
                function = getattr(current, '__func__', None)
                if getattr(function, '_v109_wrap', False):
                    continue
                source = getattr(function, '__name__', '')
                if source not in ('CallServerOld', 'CallServerOffline'):
                    continue
                wrapped = inspect.getattr_static(cls, source)
                if not callable(wrapped) or not getattr(
                        wrapped, '_v109_wrap', False):
                    continue
                setattr(avatar, public, wrapped.__get__(avatar, cls))
                added += 1
            except Exception:
                continue
        if added:
            _v109_log(('avatar-instance-rpc-bind', added),
                      'native avatar instance RPC bindings repaired=%d' % added, 2)
    except Exception:
        pass
    return added


# HasExtraEmote is a real Battle Pass entitlement query.  Do not rewrite its
# answer globally: only the recovered native emote consumers may use the
# disclosed local 12-slot UI capability.  Other callers keep the genuine bit.
EXTRA_EMOTE_CALLERS = frozenset((
    ('gclient.gamesystem.uihall.hall_main_window', 'OnEmote'),
    ('gclient.gameplay.logic_base.entities.combatavatarmembers.cimp_emote',
     'GetEmoteWheelUI'),
    ('gclient.gamesystem.entities.avatarmembers.cimp_combat', 'HasEquip'),
    ('gclient.gamesystem.uiwarehouse.warehouse_item_window',
     'RefreshSelectItemUI'),
    ('gclient.gamesystem.uiwarehouse.warehouse_item_window',
     'LoadOrReplaceEmote'),
    ('gclient.gamesystem.uiwarehouse.warehouse_item_window',
     'AutoSelectValidSlotForEmote'),
))


def extra_emote_factory(previous):
    """Enable native VIP emote UI locally, never a Battle Pass entitlement."""
    def wrapper(self, *args, **kwargs):
        genuine = previous(self, *args, **kwargs)
        if genuine or not category_enabled('emote'):
            return genuine
        try:
            caller = sys._getframe(1)
            source = (caller.f_globals.get('__name__', ''),
                      caller.f_code.co_name)
            if source in EXTRA_EMOTE_CALLERS:
                _v109_log(('extra-emote-ui', source[0], source[1]),
                          'EMOTE native 12-slot UI source=%s.%s; genuine entitlement unchanged'
                          % source, 2)
                return True
        except Exception:
            pass
        return genuine
    return wrapper


def emote_apply_window(window):
    """Apply the official nested emote contract after the native UI call.

    LoadOrReplaceEmote uses genv.avatar, HasExtraEmote, GetSelectSlot,
    GetEquipSlot and ArmHeroEmo(item_id, slot).  The original method always
    runs first.  If an injected item is still unequipped, complete only its
    local native slot map and refresh with RefreshEmoteSlots(item_id).
    """
    try:
        if window is None or not category_enabled('emote'):
            return False
        getter = getattr(window, 'GetCurSelectWarehouseItem', None)
        if not callable(getter):
            return False
        item = getter()
        item_id = _v109_int(getattr(item, 'item_id', 0), 0)
        if not item_id:
            return False
        guid = getattr(item, 'guid', None)
        record = injected_record(guid or item_id)
        if not record or record[0] != item_id or record[1] != 'emote':
            return False
        injected = record[2]
        if injected is not item and guid != getattr(injected, 'guid', None):
            return False

        root = None
        try:
            helper = globals().get('_game_genv')
            root = helper() if callable(helper) else globals().get('genv')
        except Exception:
            root = globals().get('genv')
        avatar = getattr(root, 'avatar', None)
        if avatar is None:
            warehouse = getattr(root, 'warehouse', None)
            avatar = getattr(warehouse, 'avatar', None)
        if avatar is None:
            try:
                reference = globals().get('_avatar_seen_ref')
                avatar = reference() if callable(reference) else None
            except Exception:
                avatar = None
        if avatar is None:
            return False
        has_extra = getattr(avatar, 'HasExtraEmote', None)
        if not callable(has_extra):
            return False
        # This payload helper is not one of the native allowlisted callers.
        # Its direct query therefore returns the genuine bit; local emotes
        # explicitly select the same extra panel used by the wrapped native
        # LoadOrReplaceEmote call immediately before this fallback.
        use_extra = bool(has_extra()) or category_enabled('emote')
        panel = getattr(window, 'panel_emote_extra' if use_extra
                        else 'panel_emote', None)
        select_slot = getattr(panel, 'GetSelectSlot', None) \
            if panel is not None else None
        if not callable(select_slot):
            return False
        slot = _v109_int(select_slot(), -1)
        if not 0 <= slot < 12:
            return False
        info = getattr(avatar, 'emote_info', None)
        get_equip_slot = getattr(info, 'GetEquipSlot', None) \
            if info is not None else None
        if not callable(get_equip_slot):
            return False
        if _v109_int(get_equip_slot(item_id), -1) == slot:
            return False               # native/original path already equipped
        operations = emote_equip_plan(
            avatar, (item_id, slot), 0, item_id)
        if not operations or not apply_equip(
                item_id, avatar, operations):
            return False
        emote_remember_pick(item_id, operations)
        refreshed = False
        try:
            refresh = getattr(panel, 'RefreshEmoteSlots', None)
            if callable(refresh):
                refresh(item_id)
                refreshed = True
        except Exception:
            pass
        hero_key = operations[-1][1][1]
        _v109_log('emote-ui-equip',
                  'EMOTE native UI equip item=%d hero=%s slot=%d refreshed=%s'
                  % (item_id, hero_key, slot, refreshed), 4)
        return True
    except Exception as exc:
        _v109_log(('emote-ui-equip-error', repr(exc)),
                  'EMOTE native UI equip guarded error=%r' % (exc,), 2)
        return False


def emote_ui_factory(previous, label, bound=True):
    def wrapper(*args, **kwargs):
        owner = args[0] if bound and args else None
        before = ''
        try:
            params = (args[1:] if bound else args) + tuple(kwargs.values())
            emote_code_contract(previous, label)
            emote_probe(owner, params, label, kind='ui')
            if EMOTE_VERBOSE_TRACE and category_enabled('emote'):
                before = emote_window_state(owner)
        except Exception:
            pass
        result = previous(*args, **kwargs)
        try:
            if bound and label.endswith(
                    'WarehouseItemWindow.LoadOrReplaceEmote'):
                emote_apply_window(owner)
        except Exception:
            pass                 # original native result is always preserved
        try:
            state = emote_probe_state
            count = state.get('after', 0)
            if EMOTE_VERBOSE_TRACE and category_enabled('emote') \
                    and count < 6:
                state['after'] = count + 1
                _plog('[CUNLOCK] EMOTE UI result=%d source=%s value=%s before=%s after=%s'
                      % (count + 1, label, emote_compact(result),
                         before or 'fields=not-captured',
                         emote_window_state(owner)))
        except Exception:
            pass
        return result
    return wrapper


def install_emote_observers():
    """Observe exact loaded emote UI entry points; never import/scan for them."""
    added = 0
    module_names = (
        'gclient.gamesystem.uiwarehouse.warehouse_item_window',
        'gclient.gamesystem.uiwarehouse.extra_warehouse_item_window',
        'gclient.gamesystem.uihall.warehouse_item_window',
        'warehouse_item_window',
    )
    methods = ('LoadOrReplaceEmote', 'AutoSelectValidSlotForEmote')
    for module_name in module_names:
        module = sys.modules.get(module_name)
        if module is None:
            continue
        short_name = module_name.rsplit('.', 1)[-1]
        for method in methods:
            key = (id(module), 'emote-module:' + method)
            if key in install_seen:
                continue
            try:
                previous = inspect.getattr_static(module, method)
                if not callable(previous) or getattr(
                        previous, 'emote_observer', False):
                    continue
                wrapper = emote_ui_factory(
                    previous, short_name + '.' + method, bound=False)
                wrapper.emote_observer = True
                setattr(module, method, wrapper)
                install_seen.add(key)
                added += 1
            except Exception:
                continue
        for class_name in ('WarehouseItemWindow', 'ExtraWarehouseItemWindow',
                           'WarehouseExtraItemWindow'):
            cls = getattr(module, class_name, None)
            if not isinstance(cls, type):
                continue
            for method in methods:
                key = (id(cls), 'emote-ui:' + method)
                if key in install_seen:
                    continue
                label = '%s.%s.%s' % (short_name, class_name, method)
                factory = lambda prev, label=label: emote_ui_factory(
                    prev, label, bound=True)
                if _v109_wrap_method(cls, method, factory):
                    install_seen.add(key)
                    added += 1
                elif getattr(getattr(cls, method, None), '_v109_wrap', False):
                    install_seen.add(key)
                # v2.113: bounded discovery probe - list the class's
                # profile-cosmetic method names once so the avatar
                # equip RPC name lands in the next debug log.
                try:
                    _probe_cls = cls
                except Exception:
                    _probe_cls = None
                if (_probe_cls is not None and
                        ('v2113-member-probe', id(_probe_cls)) not in install_seen):
                    install_seen.add(('v2113-member-probe', id(_probe_cls)))
                    try:
                        _pn = [m for m in dir(_probe_cls) if
                               ('Avatar' in m or 'HeadIcon' in m or
                                'CardBg' in m or 'ChatBubble' in m)]
                        _v109_log(('member-probe',),
                                  'member cosmetic names %r'
                                  % (_pn[:48],), 1)
                    except Exception:
                        pass
    return added


def melee_catalog():
    try:
        fn = globals().get('_v841m2_catalog')
        return fn() if callable(fn) else None
    except Exception:
        return None


def melee_int(value, default=0):
    """Read official melee scalars, including callable SDK wrapper values.

    The older melee path accepted these wrappers while the native path only
    accepted int()/`.value`.  A callable melee_id could otherwise hide a real
    Dagger/Axe/Katana context from the native list.  Keep this compatibility
    local to melee rather than invoking callables in the generic converter.
    """
    try:
        if isinstance(value, bool):
            return default
        if callable(value) and not isinstance(value, type):
            value = value()
        return _v109_int(value, default)
    except Exception:
        return default


def melee_arg_item(value):
    """Resolve an item/object/template argument only through real melee rows."""
    try:
        candidate = melee_int(value, 0)
        if candidate:
            if _v109_category(candidate) == 'melee':
                return candidate
            catalog = melee_catalog() or {}
            mapped = _v109_int(
                (catalog.get('template_to_item') or {}).get(candidate), 0)
            if mapped and _v109_category(mapped) == 'melee':
                return mapped
            return 0
        for field in ('item_id', 'guise_item_id', 'skin_item_id', 'id',
                      'skin_id', 'guise_id', 'guise_template_id', 'template_id'):
            candidate = _v109_int(_v109_field(value, field, 0), 0)
            if candidate:
                resolved = melee_arg_item(candidate)
                if resolved:
                    return resolved
    except Exception:
        pass
    return 0


def melee_context_ids(values):
    """Return authenticated catalog items for one melee equip/display context."""
    try:
        catalog = melee_catalog() or {}
        context = 0
        for value in values:
            candidate = melee_int(value, 0)
            if not candidate:
                continue
            if (candidate in (catalog.get('by_melee') or {})
                    or candidate in (catalog.get('by_equip') or {})
                    or candidate in (catalog.get('by_display') or {})):
                context = candidate
                break
        if context:
            if context in (97, 107, 141):
                ids = (catalog.get('by_display') or {}).get(context)
            else:
                ids = ((catalog.get('by_melee') or {}).get(context)
                       or (catalog.get('by_equip') or {}).get(context)
                       or (catalog.get('by_display') or {}).get(context))
        else:
            # Even GetAllMeleeSkinItemList is context-sensitive in the native
            # UI.  With no authenticated melee context, preserve its result.
            ids = None
        out = []
        for item_id in sorted(ids or ()):
            if _v109_category(item_id) == 'melee':
                out.append(item_id)
            if len(out) >= 256:
                break
        return out
    except Exception:
        return []


def melee_list_native_entry(warehouse, entry):
    """Resolve one stale locked-list placeholder to its retained native row.

    A genuine warehouse object always wins, even when an injected row with the
    same item ID also exists.  Only a non-retained placeholder may be replaced.
    """
    try:
        if warehouse is None:
            return None
        item_id = melee_int(getattr(entry, 'item_id', 0), 0)
        if not item_id or _v109_category(item_id) != 'melee':
            return None
        entry_guid = getattr(entry, 'guid', None)
        if entry_guid and warehouse.get(entry_guid) is entry:
            return None
        record = injected_record(item_id)
        if not record or record[0] != item_id or record[1] != 'melee':
            return None
        item = record[2]
        guid = getattr(item, 'guid', None)
        if not guid or warehouse.get(guid) is not item:
            return None
        if melee_int(getattr(item, 'item_id', 0), 0) != item_id:
            return None
        return item
    except Exception:
        return None


def melee_merge(result, item_ids, warehouse=None):
    """Reconcile placeholders and merge real native melee rows in-place.

    The official locked-list builder is synchronous.  If its first pass saw a
    locked placeholder, merely appending the later native object leaves the
    placeholder's foreign GUID in the selection path.  Replace only that
    non-retained placeholder, preserve the original container, and never mix
    native objects into scalar/record-list result shapes.
    """
    try:
        entries = list(result or ())
    except Exception:
        return result
    if entries and isinstance(entries[0], (int, str, bytes, tuple, list, dict)):
        # Never mix native objects into ID/(item, mall) record lists.
        return result
    if warehouse is None:
        try:
            _avatar, warehouse = native_avatar()
        except Exception:
            warehouse = None
    resolved = []
    reconciled = 0
    for entry in entries[:2048]:
        native = melee_list_native_entry(warehouse, entry)
        if native is not None and native is not entry:
            resolved.append(native)
            reconciled += 1
        else:
            resolved.append(entry)
    if len(entries) > 2048:
        resolved.extend(entries[2048:])
    existing_guids = set()
    existing_items = set()
    for entry in resolved[:2048]:
        guid = _v109_field(entry, 'guid', None)
        item_id = _v109_int(_v109_field(entry, 'item_id', 0), 0)
        if guid is not None:
            existing_guids.add(guid)
        if item_id:
            existing_items.add(item_id)
    additions = []
    for item_id in item_ids:
        if len(additions) >= 128:
            break
        record = injected_record(item_id)
        if not record or record[1] != 'melee':
            continue
        item = record[2]
        guid = getattr(item, 'guid', None)
        if warehouse is not None and (
                not guid or warehouse.get(guid) is not item):
            continue
        if guid in existing_guids or item_id in existing_items:
            continue
        additions.append(item)
        existing_guids.add(guid)
        existing_items.add(item_id)
    if reconciled:
        _v109_log(('melee-list-reconciled', tuple(sorted(existing_items))),
                  'native melee list reconciled retained real rows=%d'
                  % reconciled, 2)
    if not reconciled and not additions:
        return result
    if isinstance(result, list):
        # The official caller may retain this exact list object.
        result[:] = resolved + additions
        return result
    if isinstance(result, tuple):
        return tuple(resolved + additions)
    if result is None or result is False:
        return resolved + additions
    return result


def melee_owned_factory(previous):
    def wrapper(*args, **kwargs):
        item_id = 0
        warehouse = None
        if category_enabled('melee'):
            _avatar, warehouse = native_avatar()
            for value in tuple(args) + tuple(kwargs.values()):
                item_id = melee_arg_item(value)
                if item_id:
                    break
            if item_id and warehouse is not None:
                ensure_item(warehouse, item_id, mode='single')
        result = previous(*args, **kwargs)
        if result or not item_id:
            return result
        # This is local ownership by an actual native object, not a bool-only
        # ownership override.  Without that object the original False remains.
        record = injected_record(item_id)
        return True if record and record[1] == 'melee' else result
    return wrapper


def melee_guise_factory(previous):
    def wrapper(*args, **kwargs):
        item_id = 0
        warehouse = None
        if category_enabled('melee'):
            catalog = melee_catalog() or {}
            for value in tuple(args) + tuple(kwargs.values()):
                template_id = melee_int(value, 0)
                mapped = _v109_int(
                    (catalog.get('template_to_item') or {}).get(template_id), 0)
                if mapped and _v109_category(mapped) == 'melee':
                    item_id = mapped
                    break
            _avatar, warehouse = native_avatar()
            if item_id and warehouse is not None:
                ensure_item(warehouse, item_id, mode='single')
        result = previous(*args, **kwargs)
        if result or not item_id:
            return result
        record = injected_record(item_id)
        return record[2] if record and record[1] == 'melee' else result
    return wrapper


def melee_list_factory(previous):
    def wrapper(*args, **kwargs):
        enabled = category_enabled('melee')
        started = time.time() if enabled else 0.0
        item_ids = []
        warehouse = None
        prepared = 0
        values = []
        if enabled:
            owner = args[0] if args else None
            values = list(args) + list(kwargs.values())
            for field in ('cur_gun_id', 'melee_id', 'equip_id', 'gun_id'):
                values.append(_v109_field(owner, field, 0))
            item_ids = melee_context_ids(values)
            _avatar, warehouse = native_avatar()
            if warehouse is not None:
                for item_id in item_ids:
                    prepared += int(bool(ensure_item(
                        warehouse, item_id, mode='single')))
        result = previous(*args, **kwargs)
        merged = (melee_merge(result, item_ids, warehouse)
                  if item_ids else result)
        if item_ids:
            try:
                rows = len(merged)
            except Exception:
                rows = -1
            _v109_log(('melee-list-ready', tuple(item_ids)),
                      'native melee list ready rows=%d candidates=%d '
                      'prepared=%d total_ms=%.1f'
                      % (rows, len(item_ids), prepared,
                         (time.time() - started) * 1000.0), 1)
        elif enabled:
            signature = tuple(type(value).__name__ for value in values[:8])
            _v109_log(('melee-list-context-missing', signature),
                      'native melee list context unresolved value_types=%r'
                      % (signature,), 1)
        return merged
    return wrapper


def melee_resolver_factory(previous):
    def wrapper(*args, **kwargs):
        result = previous(*args, **kwargs)
        if _v109_int(result, 0) or not category_enabled('melee'):
            return result
        for value in tuple(args) + tuple(kwargs.values()):
            item_id = melee_arg_item(value)
            if item_id:
                equip_id = melee_equip(_v109_row(item_id))
                if equip_id:
                    return equip_id
        return result
    return wrapper


def melee_ui_preflight(window):
    """Make the official selected row native before its GUID is consumed.

    OnSelectGuise stores the exact list object in cur_selected_skin_item and
    OnClickEquip later reads its GUID.  Preflight just that selection, replace
    only a stale non-retained placeholder, and keep the selected node pointing
    at the same real object.  Genuine retained rows are never substituted.
    """
    try:
        if window is None or not category_enabled('melee'):
            return False
        selected = getattr(window, 'cur_selected_skin_item', None)
        item_id = melee_arg_item(selected)
        if not item_id:
            return False
        _avatar, warehouse = native_avatar()
        if warehouse is None:
            return False
        ensure_item(warehouse, item_id, mode='equip')
        native = melee_list_native_entry(warehouse, selected)
        if native is None:
            return False
        window.cur_selected_skin_item = native
        node = getattr(window, 'cur_selected_skin_node', None)
        if node is not None and getattr(node, 'item', None) is selected:
            node.item = native
        _v109_log(('melee-ui-preflight', item_id),
                  'native melee confirm preflight item=%d retained row ready'
                  % item_id, 2)
        return True
    except Exception as exc:
        _v109_log(('melee-ui-preflight-error', repr(exc)),
                  'native melee confirm preflight guarded error=%r'
                  % (exc,), 1)
        return False


def melee_apply_window(window):
    """Complete a selected injected melee through the official local RPC state."""
    try:
        if window is None or not category_enabled('melee'):
            return False
        item_id = 0
        for field in ('cur_selected_skin_item', 'cur_select_skin_item',
                      'selected_skin_item', 'cur_skin_item',
                      'show_model_item_id', 'selected_skin_item_id',
                      'cur_selected_item', 'item_id'):
            item_id = melee_arg_item(getattr(window, field, None))
            if item_id:
                break
        record = injected_record(item_id)
        if not record or record[1] != 'melee':
            return False
        avatar, _warehouse = native_avatar()
        if avatar is None:
            return False
        guid = getattr(record[2], 'guid', None)
        if melee_guid_present(avatar, guid):
            return False
        return local_equip(avatar, 'ApplyMelee', (guid, False))
    except Exception as exc:
        _v109_log(('melee-ui-equip-error', repr(exc)),
                  'native melee UI equip guarded error=%r' % (exc,), 2)
        return False


def melee_ui_factory(previous):
    def wrapper(*args, **kwargs):
        window = args[0] if args else None
        positive_selection = False
        try:
            # Capture the official branch BEFORE UpdateBtnEquipStatus runs.
            # Unequip and cur_gun_id==0 both deliberately send an empty GUID;
            # their stale cur_selected_skin_item is not a new equip request.
            cur_gun_id = melee_int(
                _v109_field(window, 'cur_gun_id', 0), 0)
            button = getattr(window, 'btn_equip', None)
            equipped = bool(_v109_field(button, 'status', False))
            positive_selection = bool(cur_gun_id and not equipped)
            if positive_selection:
                melee_ui_preflight(window)
        except Exception as exc:
            _v109_log(('melee-ui-before-error', repr(exc)),
                      'native melee UI preflight guarded error=%r' % (exc,), 1)
        result = previous(*args, **kwargs)
        try:
            if positive_selection:
                melee_apply_window(window)
        except Exception as exc:
            _v109_log(('melee-ui-after-error', repr(exc)),
                      'native melee UI completion guarded error=%r' % (exc,), 1)
        return result
    return wrapper


GUN_LIST_LIMIT = 512


def gun_list_item_ids(gun_id):
    """Return both official per-gun catalogs, never the whole lobby table.

    GunSkin and GunGuise rows share this data module but have separate maps.
    Omitting the guise map left guise-heavy weapon classes locked even when
    pistol skin rows happened to be present.
    """
    module = sys.modules.get('gclient.data.lobby_gun_skin_item_data')
    result = []
    seen = set()
    gun_id = _v109_int(gun_id, 0)
    for field in ('GUN_ID_TO_SKIN_ITEM_IDS', 'GUN_ID_TO_GUISE_ITEM_IDS'):
        source = getattr(module, field, None) if module is not None else None
        values = map_values(source, gun_id) or ()
        for raw in values:
            item_id = _v109_int(raw, 0)
            if not item_id or item_id in seen:
                continue
            seen.add(item_id)
            result.append(item_id)
            if len(result) >= GUN_LIST_LIMIT:
                _v109_log(('gun-list-cap', gun_id),
                          'native gun list=%d reached bounded preflight cap=%d'
                          % (gun_id, GUN_LIST_LIMIT), 1)
                return result
    return result


def gun_list_native_entry(warehouse, entry):
    """Resolve one stale UI placeholder to its retained real IHallItem."""
    try:
        item_id = _v109_int(getattr(entry, 'item_id', 0), 0)
        if not item_id:
            return None
        entry_guid = getattr(entry, 'guid', None)
        if entry_guid and warehouse.get(entry_guid) is entry:
            # A genuine row already retained by Warehouse always wins.  Only
            # the official builder's non-retained placeholder is replaceable.
            return None
        record = injected_record(item_id)
        if not record or record[0] != item_id or record[1] != 'weapon':
            return None
        item = record[2]
        guid = getattr(item, 'guid', None)
        if not guid or warehouse.get(guid) is not item:
            return None
        if _v109_int(getattr(item, 'item_id', 0), 0) != item_id:
            return None
        return item
    except Exception:
        return None


def gun_list_factory(previous):
    """Make native ownership true before the official lock/unlock list split.

    Official GetAllGunSkinItemList calls GetItemByItemId, creates a locked
    placeholder on a miss, then calls CheckGunSkinOwned.  The generic deferred
    ownership-list mode is too late for that synchronous builder.  Preflight
    only this gun's authentic IDs, run the original builder, and reconcile any
    stale placeholder in its returned list to the retained native object.
    """
    def wrapper(*args, **kwargs):
        gun_id = _v109_int(args[0] if args else kwargs.get('gun_id'), 0)
        warehouse = None
        try:
            if gun_id and category_enabled('weapon'):
                _avatar, warehouse = native_avatar()
                if warehouse is not None:
                    state = _v109_prepare(warehouse, defer=True)
                    if state is not None and not state.get('busy'):
                        ids = gun_list_item_ids(gun_id)
                        added = 0
                        for item_id in ids:
                            added += int(bool(ensure_item(
                                warehouse, item_id, mode='equip')))
                        if added:
                            _v109_log(('gun-list-preflight', gun_id),
                                      'native gun list=%d preflight added=%d total=%d'
                                      % (gun_id, added, len(ids)), 2)
        except Exception as exc:
            _v109_log(('gun-list-preflight-error', gun_id, repr(exc)),
                      'native gun list=%d preflight guarded error=%r'
                      % (gun_id, exc), 1)
        # Original exceptions, arguments and return shape remain authoritative.
        result = previous(*args, **kwargs)
        try:
            if (warehouse is not None and isinstance(result, list)
                    and category_enabled('weapon')):
                resolved = []
                changed = 0
                for entry in result:
                    native = gun_list_native_entry(warehouse, entry)
                    if native is not None and native is not entry:
                        changed += 1
                        resolved.append(native)
                    else:
                        resolved.append(entry)
                if changed:
                    # The official caller may retain this exact list object.
                    result[:] = resolved
                    _v109_log(('gun-list-reconciled', gun_id),
                              'native gun list=%d reconciled real rows=%d'
                              % (gun_id, changed), 2)
        except Exception as exc:
            _v109_log(('gun-list-reconcile-error', gun_id, repr(exc)),
                      'native gun list=%d reconciliation guarded error=%r'
                      % (gun_id, exc), 1)
        return result
    return wrapper


def gun_ui_preflight(window, node=None, weapon_case=None):
    """Synchronously prepare the current official gun selection/list scope."""
    if not category_enabled('weapon'):
        return 0, 0
    avatar, warehouse = native_avatar()
    if avatar is None or warehouse is None:
        return 0, 0
    ids = []
    seen = set()

    def add(item_id):
        item_id = _v109_int(item_id, 0)
        if item_id and item_id not in seen and _v109_category(item_id) == 'weapon':
            seen.add(item_id)
            ids.append(item_id)

    gun_id = _v109_int(getattr(node, 'gun_id', 0), 0)
    if not gun_id:
        gun_id = _v109_int(getattr(window, 'cur_gun_id', 0), 0)
    if not gun_id and weapon_case is not None:
        weapon = getattr(weapon_case, 'weapon', None)
        gun_id = _v109_int(getattr(weapon, 'gun_id', 0), 0)
        if not gun_id:
            try:
                _root, player = melee_visual_player()
                backpack = getattr(player, 'backpack', None)
                guid = getattr(weapon_case, 'weapon_guid', None)
                weapon_item = melee_visual_get(backpack, guid)
                gun_id = _v109_int(getattr(weapon_item, 'gun_id', 0), 0)
            except Exception:
                gun_id = 0
    if gun_id:
        for item_id in gun_list_item_ids(gun_id):
            add(item_id)
    # Confirm remains authoritative even if a custom/reward view did not use
    # the normal list builder.  These are real IHallItem objects, not guessed
    # IDs extracted from a GUID.
    for field in ('cur_selected_skin_item', 'cur_selected_guise_item',
                  'selected_skin_item', 'selected_guise_item'):
        add(getattr(getattr(window, field, None), 'item_id', 0))
    state = _v109_prepare(warehouse, defer=True)
    if state is None or state.get('busy'):
        return 0, len(ids)
    added = 0
    for item_id in ids[:GUN_LIST_LIMIT]:
        added += int(bool(ensure_item(warehouse, item_id, mode='equip')))
    return added, len(ids)


def gun_ui_factory(previous, kind):
    """Cover the current warehouse/HUD synchronous gun-list and confirm flow."""
    def wrapper(*args, **kwargs):
        window = args[0] if args else None
        try:
            node = args[1] if kind == 'select' and len(args) > 1 else None
            weapon_case = kwargs.get('weapon_case')
            if kind == 'show' and weapon_case is None and category_enabled('weapon'):
                # Official HudGunSkinWindow.OnShow(info) resolves the current
                # case itself; info is not a weapon-case argument.
                _root, player = melee_visual_player()
                getter = getattr(player, 'GetCurWeaponCase', None)
                weapon_case = getter() if callable(getter) else None
            added, total = gun_ui_preflight(window, node, weapon_case)
            if total:
                _v109_log(('gun-ui-preflight', kind, added, total),
                          'native gun UI kind=%s preflight added=%d candidates=%d'
                          % (kind, added, total), 2)
        except Exception as exc:
            _v109_log(('gun-ui-preflight-error', kind, repr(exc)),
                      'native gun UI kind=%s preflight guarded error=%r'
                      % (kind, exc), 1)
        return previous(*args, **kwargs)
    return wrapper


def install_gun_observers():
    """Cover the SDK-proven module-level native gun-list/button boundary."""
    added = 0
    module = sys.modules.get('gclient.util.gun_skin_util')
    if module is not None:
        key = (id(module), 'native-gun:GetAllGunSkinItemList')
        if key not in install_seen:
            if _v109_wrap_method(module, 'GetAllGunSkinItemList',
                                 gun_list_factory):
                install_seen.add(key)
                added += 1
            elif getattr(getattr(module, 'GetAllGunSkinItemList', None),
                         '_v109_wrap', False):
                install_seen.add(key)
    specs = (
        ('gclient.gamesystem.uiwarehouse.warehouse_gun_skin_window',
         'WarehouseGunSkinWindow', 'OnSelectGun', 'select'),
        ('gclient.gamesystem.uiwarehouse.warehouse_gun_skin_window',
         'WarehouseGunSkinWindow', 'OnDiyEquip', 'confirm'),
        ('gclient.gameplay.uicomponents.uigunrefit.hud_weapon_skin_comp',
         'HudGunSkinWindow', 'OnShow', 'show'),
        ('gclient.gameplay.uicomponents.uigunrefit.hud_weapon_skin_comp',
         'HudGunSkinWindow', 'OnDiyEquip', 'confirm'),
    )
    for module_name, class_name, method, kind in specs:
        module = sys.modules.get(module_name)
        cls = getattr(module, class_name, None) if module is not None else None
        if not isinstance(cls, type):
            continue
        key = (id(cls), 'native-gun-ui:' + kind)
        if key in install_seen:
            continue
        if _v109_wrap_method(
                cls, method, lambda prev, k=kind: gun_ui_factory(prev, k)):
            install_seen.add(key)
            added += 1
        elif getattr(getattr(cls, method, None), '_v109_wrap', False):
            install_seen.add(key)
        # v2.113: bounded discovery probe - list the class's
        # profile-cosmetic method names once so the avatar
        # equip RPC name lands in the next debug log.
        try:
            _probe_cls = cls
        except Exception:
            _probe_cls = None
        if (_probe_cls is not None and
                ('v2113-member-probe', id(_probe_cls)) not in install_seen):
            install_seen.add(('v2113-member-probe', id(_probe_cls)))
            try:
                _pn = [m for m in dir(_probe_cls) if
                       ('Avatar' in m or 'HeadIcon' in m or
                        'CardBg' in m or 'ChatBubble' in m)]
                _v109_log(('member-probe',),
                          'member cosmetic names %r'
                          % (_pn[:48],), 1)
            except Exception:
                pass
    return added


def install_melee_observers():
    """Install native melee coverage only on modules already loaded by the game."""
    added = 0
    gun_module = sys.modules.get('gclient.util.gun_skin_util')
    targets = []
    candidate = getattr(gun_module, 'GunSkinUtil', None) if gun_module else None
    for target in (gun_module, candidate,
                   type(candidate) if candidate is not None and
                   not isinstance(candidate, type) else None):
        if target is not None and all(id(target) != id(old) for old in targets):
            targets.append(target)
    for target in targets:
        for method, factory in (
                ('CheckGunSkinOwned', melee_owned_factory),
                ('GetAllMeleeSkinItemList', melee_list_factory),
                ('GetItemByMeleeGuiseId', melee_guise_factory)):
            key = (id(target), 'native-melee:' + method)
            if key in install_seen:
                continue
            if _v109_wrap_method(target, method, factory):
                install_seen.add(key)
                added += 1
    weapon_util = sys.modules.get('gshare.weapon_util')
    if weapon_util is not None:
        key = (id(weapon_util), 'native-melee:GetMeleeSkinRealEquipId')
        if key not in install_seen and _v109_wrap_method(
                weapon_util, 'GetMeleeSkinRealEquipId',
                melee_resolver_factory):
            install_seen.add(key)
            added += 1
    refit_module = sys.modules.get('gclient.gameplay.logic_base.comps.comp_gunrefit')
    if refit_module is not None:
        key = (id(refit_module), 'native-melee-ui-case:EnterGunRefit')
        if key not in install_seen and _v109_wrap_method(
                refit_module, 'EnterGunRefit',
                lambda prev: melee_ui_case_factory(prev, 'enter-refit')):
            install_seen.add(key)
            added += 1
    backpack_module = sys.modules.get(
        'gclient.gameplay.logic_base.entities.combatavatarmembers.cimp_backpack')
    backpack_member = getattr(backpack_module, 'CombatAvatarMember', None) \
        if backpack_module is not None else None
    if isinstance(backpack_member, type):
        for method, kind in (('GetMeleeWeaponCase', 'get-melee-case'),
                             ('GetCurWeaponCase', 'get-current-case')):
            key = (id(backpack_member), 'native-melee-case-get:' + method)
            if key in install_seen:
                continue
            if _v109_wrap_method(
                    backpack_member, method,
                    lambda prev, k=kind: melee_case_get_factory(prev, k)):
                install_seen.add(key)
                added += 1
    combat_unit_module = sys.modules.get(
        'gclient.gameplay.logic_base.entities.combatavatarmembers.cimp_combat_unit')
    combat_member = getattr(combat_unit_module, 'CombatAvatarMember', None) \
        if combat_unit_module is not None else None
    if isinstance(combat_member, type):
        key = (id(combat_member), 'native-melee-kill:KillAvatar')
        if key not in install_seen:
            if _v109_wrap_method(
                    combat_member, 'KillAvatar',
                    melee_kill_avatar_factory):
                install_seen.add(key)
                added += 1
            elif getattr(getattr(combat_member, 'KillAvatar', None),
                         '_v109_wrap', False):
                install_seen.add(key)
    surfaces = (
        ('gclient.gamesystem.uiwarehouse.warehouse_melee_skin_window',
         ('WarehouseMeleeSkinWindow', 'CommonMeleeSkinComponent',
          'WarehouseMeleeSkinComp')),
        ('gclient.gamesystem.uiwarehouse.warehouse_window',
         ('WarehouseMeleeSkinWindow',)),
        ('gclient.gameplay.uicomponents.uigunrefit.hud_weapon_skin_comp',
         ('HudMeleeSkinWindow', 'CommonMeleeSkinComponent',
          'HudMeleeSkinComponent')),
        ('gclient.gameplay.uicomponents.uigunrefit.hud_gunrefit_backpack_comp',
         ('HudMeleeSkinWindow', 'CommonMeleeSkinComponent')),
        ('gclient.ui.common.common_skin_window',
         ('CommonMeleeSkinComponent',)),
    )
    for module_name, class_names in surfaces:
        module = sys.modules.get(module_name)
        for class_name in class_names:
            cls = getattr(module, class_name, None) if module else None
            if not isinstance(cls, type):
                continue
            for method, factory in (
                    ('GetMeleeSkinItemList', melee_list_factory),
                    ('OnClickEquip', melee_ui_factory)):
                key = (id(cls), 'native-melee:' + method)
                if key in install_seen:
                    continue
                if _v109_wrap_method(cls, method, factory):
                    install_seen.add(key)
                    added += 1
    melee_window_module = sys.modules.get(
        'gclient.gameplay.uicomponents.uigunrefit.hud_weapon_skin_comp')
    melee_window = getattr(melee_window_module, 'HudMeleeSkinWindow', None) \
        if melee_window_module is not None else None
    if isinstance(melee_window, type):
        key = (id(melee_window), 'native-melee-ui-case:OnShow')
        if key not in install_seen and _v109_wrap_method(
                melee_window, 'OnShow',
                lambda prev: melee_ui_case_factory(prev, 'melee-window')):
            install_seen.add(key)
            added += 1
    return added


def panpan_ui_factory(previous):
    """Keep native confirm authoritative; verify and complete injected equip."""
    def wrapper(*args, **kwargs):
        window = args[0] if args else None
        avatar = None
        record = None
        item_id = 0
        guid = None
        getter = None
        current = None
        before_guid = _V109_MISSING
        ready = False
        try:
            item_id = _v109_int(getattr(window, 'select_item_id', 0), 0)
            if (window is not None and item_id
                    and category_enabled('playpal')):
                avatar, warehouse = native_avatar()
                if warehouse is not None:
                    # Official confirm calls avatar.GetItemIncludeUpgradeItem,
                    # which immediately reads warehouse.GetItemByItemId.  A
                    # first/late selection must therefore be a real native item
                    # BEFORE that resolver runs; deferring it sends the native
                    # UI down its acquisition path and no ApplyPanpan occurs.
                    ensure_item(warehouse, item_id, mode='equip')
                record = injected_record(item_id)
            if (window is not None and record
                    and record[1] == 'playpal'
                    and category_enabled('playpal')):
                guid = getattr(record[2], 'guid', None)
                if avatar is None:
                    avatar, _warehouse = native_avatar()
                before_guid = getattr(avatar, 'arm_panpan', _V109_MISSING)
                getter = getattr(avatar, 'get_arm_panpan_item_id', None)
                current = getter() if callable(getter) else None
                # Same-item confirm is the official unequip flow, not a
                # download request or a candidate for post-native re-equip.
                if current != item_id:
                    check = getattr(window, 'CheckPanPanCaseDlcExist', None)
                    ready = bool(check(item_id)) if callable(check) else False
                    if not ready:
                        download = globals().get('try_dlc_download')
                        if callable(download):
                            download(item_id, [])
                        _v109_log(('playpal-dlc', item_id),
                                  'native PlayPal item=%d waiting for authentic DLC'
                                  % item_id, 2)
                _v109_log(('playpal-confirm-preflight', item_id, current,
                           ready, repr(guid)),
                          'native PlayPal confirm preflight item=%d current=%r ready=%s native_guid=%r'
                          % (item_id, current, ready, guid), 3)
        except Exception as exc:
            _v109_log(('playpal-ui-error', repr(exc)),
                      'native PlayPal confirm preflight guarded error=%r'
                      % (exc,), 1)
        result = previous(*args, **kwargs)
        try:
            if (avatar is not None and record and guid
                    and current != item_id and ready
                    and category_enabled('playpal')):
                after_guid = getattr(avatar, 'arm_panpan', _V109_MISSING)
                fallback = False
                if after_guid != guid and after_guid == before_guid:
                    # A post-init instance binding can bypass a class RPC hook.
                    # Complete only an unchanged injected selection.  If native
                    # code moved to any other GUID, that genuine/native result
                    # takes precedence and is never overwritten here.
                    fallback = local_equip(
                        avatar, 'ApplyPanpan', (guid,))
                    after_guid = getattr(avatar, 'arm_panpan', _V109_MISSING)
                try:
                    resolved = getter() if callable(getter) else None
                except Exception:
                    resolved = None
                _v109_log(('playpal-confirm-readback', item_id,
                           repr(before_guid), repr(after_guid), resolved,
                           fallback),
                          'native PlayPal confirm item=%d before_guid=%r after_guid=%r resolved=%r fallback=%s'
                          % (item_id, before_guid, after_guid, resolved,
                             fallback), 3)
        except Exception as exc:
            _v109_log(('playpal-ui-after-error', repr(exc)),
                      'native PlayPal confirm readback guarded error=%r'
                      % (exc,), 1)
        return result
    return wrapper


def panpan_selection_factory(previous):
    """Make the selected PlayPal native before row/button ownership reads."""
    def wrapper(*args, **kwargs):
        try:
            window = args[0] if args else None
            raw_item = (args[1] if len(args) > 1 else
                        getattr(window, 'select_item_id', 0))
            item_id = _v109_int(raw_item, 0)
            if (window is not None and item_id
                    and category_enabled('playpal')):
                _avatar, warehouse = native_avatar()
                if warehouse is not None:
                    # refresh_right_btn_state calls HasItemByItemId and can
                    # disable Equip before on_confirm_btn_click is reachable.
                    # set_select_item_id also refreshes rows first, so ensure
                    # the same real native item before either original method.
                    ensure_item(warehouse, item_id, mode='equip')
                record = injected_record(item_id)
                _v109_log(('playpal-selection-preflight',
                           previous.__name__, item_id, bool(record)),
                          'native PlayPal %s item=%d tracked_native=%s'
                          % (previous.__name__, item_id, bool(record)), 3)
        except Exception as exc:
            _v109_log(('playpal-selection-error', repr(exc)),
                      'native PlayPal selection preflight guarded error=%r'
                      % (exc,), 1)
        return previous(*args, **kwargs)
    return wrapper


def wheel_panpan_dlc_factory(previous):
    """Preserve the wheel's real DLC answer and request only authentic content."""
    def wrapper(*args, **kwargs):
        result = previous(*args, **kwargs)
        try:
            item_id = _v109_int(args[1] if len(args) > 1 else 0, 0)
            record = injected_record(item_id) if item_id else None
            if (not result and record and record[1] == 'playpal'
                    and category_enabled('playpal')):
                download = globals().get('try_dlc_download')
                if callable(download):
                    download(item_id, [])
                _v109_log(('playpal-wheel-check-dlc', item_id),
                          'native PlayPal wheel check item=%d requested authentic DLC'
                          % item_id, 2)
        except Exception as exc:
            _v109_log(('playpal-wheel-check-error', repr(exc)),
                      'native PlayPal wheel DLC observer error=%r' % (exc,), 1)
        return result
    return wrapper


def wheel_emote_factory(previous):
    """Preflight the real lobby-emote DLC; never replace native playback."""
    def wrapper(*args, **kwargs):
        try:
            manager = args[0] if args else None
            item_id = _v109_int(args[1] if len(args) > 1 else 0, 0)
            record = injected_record(item_id) if item_id else None
            if (record and record[1] == 'emote'
                    and category_enabled('emote')):
                actual_id = item_id
                cdata = sys.modules.get('gclient.util.cdata_util')
                twin = getattr(cdata, 'GetTwinSkinEmoteItemId', None)
                if callable(twin):
                    npc = getattr(manager, 'main_npc', None)
                    case = getattr(npc, 'attached_weapon_case', None)
                    guise = getattr(case, 'guise_id', None) if case else None
                    actual_id = _v109_int(twin(item_id, guise), item_id)
                root = globals().get('genv')
                dlc_manager = getattr(root, 'dlc_manager', None)
                init = getattr(dlc_manager, 'InitLobbyItemDlcId', None)
                check = getattr(dlc_manager, 'CheckDlcExists', None)
                if actual_id and callable(init) and callable(check):
                    value = init(actual_id)
                    dlc_id = value[0] if isinstance(value, (tuple, list)) else value
                    dlc_id = _v109_int(dlc_id, 0)
                    if dlc_id and not check(dlc_id):
                        download = globals().get('try_dlc_download')
                        if callable(download):
                            download(actual_id, [dlc_id])
                        _v109_log(('emote-wheel-dlc', item_id, actual_id, dlc_id),
                                  'native emote wheel item=%d actual=%d waiting for authentic DLC'
                                  % (item_id, actual_id), 2)
        except Exception as exc:
            _v109_log(('emote-wheel-preflight-error', repr(exc)),
                      'native emote wheel preflight guarded error=%r' % (exc,), 1)
        return previous(*args, **kwargs)
    return wrapper


def wheel_panpan_click_factory(previous):
    """Verify native wheel start/stop and complete only an injected armed GUID."""
    def wrapper(*args, **kwargs):
        node = args[0] if args else None
        avatar = None
        record = None
        guid = None
        before_playing = False
        try:
            if category_enabled('playpal'):
                avatar, _warehouse = native_avatar()
                guid = getattr(avatar, 'arm_panpan', None)
                record = injected_record(guid) if guid else None
                before_playing = bool(getattr(
                    avatar, 'panpan_playing', False))
        except Exception:
            avatar = None
            record = None
        result = previous(*args, **kwargs)
        try:
            if (avatar is not None and record
                    and record[1] == 'playpal'
                    and category_enabled('playpal')
                    and getattr(avatar, 'arm_panpan', None) == guid):
                after_guid = getattr(avatar, 'arm_panpan', None)
                after_playing = bool(getattr(
                    avatar, 'panpan_playing', False))
                fallback = False
                if after_playing == before_playing:
                    desired = 0 if before_playing else 1
                    # This helper repeats the authentic PanPan + lobby DLC
                    # checks and uses the official panpan_playing setter now;
                    # only the official model event waits for missing assets.
                    fallback = panpan_hall_playing(
                        avatar, (desired, guid))
                    after_playing = bool(getattr(
                        avatar, 'panpan_playing', False))
                getter = getattr(node, 'get_arm_panpan_resolved_item_id', None)
                try:
                    resolved = getter() if callable(getter) else record[0]
                except Exception:
                    resolved = None
                _v109_log(('playpal-wheel-click-readback', record[0],
                           before_playing, after_playing, repr(after_guid),
                           resolved, fallback),
                          'native PlayPal wheel click item=%d before=%s after=%s guid=%r resolved=%r fallback=%s'
                          % (record[0], before_playing, after_playing,
                             after_guid, resolved, fallback), 3)
        except Exception as exc:
            _v109_log(('playpal-wheel-click-error', repr(exc)),
                      'native PlayPal wheel click readback guarded error=%r'
                      % (exc,), 1)
        return result
    return wrapper


def panpan_model_trace_factory(previous, label):
    """Read-only evidence for the official event -> lobby-model playback chain."""
    def snapshot(owner):
        avatar, _warehouse = native_avatar()
        npc = getattr(owner, 'main_npc', None)
        emote_active = None
        try:
            getter = getattr(npc, 'IsEmotePlaying', None)
            if callable(getter):
                emote_active = bool(getter())
        except Exception:
            emote_active = None
        return (bool(getattr(avatar, 'panpan_playing', False)),
                getattr(avatar, 'arm_panpan', None), npc is not None,
                emote_active)
    def wrapper(*args, **kwargs):
        owner = args[0] if args else None
        try:
            before = snapshot(owner)
            _v109_log(('playpal-model-enter', label, repr(before)),
                      'PLAYPAL MODEL enter=%s playing=%s guid=%r main_npc=%s emote_active=%s'
                      % ((label,) + before), 2)
        except Exception:
            before = None
        result = previous(*args, **kwargs)
        try:
            after = snapshot(owner)
            _v109_log(('playpal-model-exit', label, repr(after)),
                      'PLAYPAL MODEL exit=%s playing=%s guid=%r main_npc=%s emote_active=%s'
                      % ((label,) + after), 2)
        except Exception:
            pass
        return result
    return wrapper


def install_wheel_observers():
    """Install on the recovered regular/VIP hall-wheel playback surfaces."""
    added = 0
    module = sys.modules.get('gclient.gamesystem.uihall.hall_emote_window')
    for class_name in ('WheelPanpanNode', 'EmoteWheelCompInHall'):
        cls = getattr(module, class_name, None) if module else None
        if not isinstance(cls, type):
            continue
        key = (id(cls), 'native-wheel:CheckPanPanCaseDlcExist')
        if key not in install_seen:
            if _v109_wrap_method(cls, 'CheckPanPanCaseDlcExist',
                                 wheel_panpan_dlc_factory):
                install_seen.add(key)
                added += 1
        if class_name == 'WheelPanpanNode':
            key = (id(cls), 'native-wheel:on_click_panapn')
            if key not in install_seen:
                if _v109_wrap_method(cls, 'on_click_panapn',
                                     wheel_panpan_click_factory):
                    install_seen.add(key)
                    added += 1
    module = sys.modules.get(
        'gclient.gamesystem.models.hall_teammate_model_manager')
    cls = getattr(module, 'HallModelManager', None) if module else None
    if isinstance(cls, type):
        for method, factory in (
                ('PlayMainNpcEmote', wheel_emote_factory),
                ('EnterPanpanPlayingStatus',
                 lambda prev: panpan_model_trace_factory(
                     prev, 'HallModelManager.EnterPanpanPlayingStatus')),
                ('PlayMainNpcPanpan',
                 lambda prev: panpan_model_trace_factory(
                     prev, 'HallModelManager.PlayMainNpcPanpan'))):
            key = (id(cls), 'native-wheel:' + method)
            if key not in install_seen:
                if _v109_wrap_method(cls, method, factory):
                    install_seen.add(key)
                    added += 1
    module = sys.modules.get('gclient.gamesystem.uihall.hall_main_window')
    cls = getattr(module, 'HallMainWindow', None) if module else None
    if isinstance(cls, type):
        method = 'OnPanpanPlayingUpdateHall'
        key = (id(cls), 'native-wheel:' + method)
        if key not in install_seen:
            if _v109_wrap_method(
                    cls, method,
                    lambda prev: panpan_model_trace_factory(
                        prev, 'HallMainWindow.OnPanpanPlayingUpdateHall')):
                install_seen.add(key)
                added += 1
    return added


def install_panpan_observers():
    """Cover native PlayPal selection, button state and confirm; no scans."""
    added = 0
    module = sys.modules.get(
        'gclient.gamesystem.uiwarehouse.panpan.warehouse_panpan_window')
    cls = getattr(module, 'WarehousePanpanWindow', None) if module else None
    if isinstance(cls, type):
        for method, factory in (
                ('set_select_item_id', panpan_selection_factory),
                ('refresh_right_btn_state', panpan_selection_factory),
                ('on_confirm_btn_click', panpan_ui_factory)):
            key = (id(cls), 'native-playpal:' + method)
            if key not in install_seen:
                if _v109_wrap_method(cls, method, factory):
                    install_seen.add(key)
                    added += 1
    return added


def install_striker_observers():
    """Attach only the recovered local Striker consumer boundaries."""
    added = 0
    specs = []
    for module_name, class_name in (
            ('gclient.gameplay.logic_base.entities.combat_avatar', 'CombatAvatar'),
            ('gclient.gameplay.logic_base.entities.combat_avatar', 'PlayerCombatAvatar'),
            ('gclient.gameplay.logic_shootingrange.combat_avatar_shootingrange',
             'PlayerCombatAvatarShootingRange')):
        specs.append((module_name, class_name, 'GetDisplayHeroSkinItemId',
                      striker_dsid_factory))
        specs.append((module_name, class_name, 'GetHeroSkinProto',
                      striker_proto_factory))
    specs.extend((
        ('gclient.gameplay.logic_base.entities.combatavatarmembers.cimp_model',
         'CombatAvatarMember', 'GetModelData', striker_model_factory),
        ('gclient.gameplay.logic_base.entities.combat_avatar', 'CombatAvatar',
         'GetModelData', striker_model_factory),
        ('gclient.gameplay.logic_base.entities.combat_avatar', 'PlayerCombatAvatar',
         'CanRequestNovaTwinSkinTransform', striker_transform_gate_factory),
        ('gclient.gameplay.logic_base.entities.combat_avatar', 'PlayerCombatAvatar',
         'RequestNovaTwinSkinTransform', striker_transform_request_factory),
        ('gclient.gameplay.logic_moba_zombie.combat_avatar_moba_zombie',
         'PlayerCombatAvatarMobaZombie', 'CanRequestNovaTwinSkinTransform',
         striker_transform_gate_factory),
        ('gclient.gameplay.logic_moba_zombie.combat_avatar_moba_zombie',
         'PlayerCombatAvatarMobaZombie', 'RequestNovaTwinSkinTransform',
         striker_transform_request_factory),
        ('gclient.gameplay.logic_moba_nightmare.combat_avatar_moba_nightmare',
         'PlayerCombatAvatarMobaNightmare', 'CanRequestNovaTwinSkinTransform',
         striker_transform_gate_factory),
        ('gclient.gameplay.logic_moba_nightmare.combat_avatar_moba_nightmare',
         'PlayerCombatAvatarMobaNightmare', 'RequestNovaTwinSkinTransform',
         striker_transform_request_factory),
        ('gclient.gameplay.game_logic_base', 'CGameLogicBase',
         'GetDisplayHeroSkinItemId', striker_game_logic_dsid_factory),
        ('gclient.gameplay.logic_base.models.hand_model', 'HandModel',
         'Refresh', striker_owner_consumer_factory),
        ('gclient.gameplay.logic_base.models.replay_hand_model',
         'ReplayHandModel', 'PlayHeroSkinHandEffect',
         striker_owner_consumer_factory),
        ('gclient.gamesystem.uihall.uihero.hero_skin_window',
         'HeroSkinWindow', 'UseSkinImp', striker_skin_ui_factory),
        ('gclient.gamesystem.uihall.uihero.hero_execution_window',
         'HeroExecutionWindow', 'BuildListviewData',
         lambda prev: striker_list_factory(prev, 'execution')),
        ('gclient.gamesystem.uihall.uihero.hero_appearance_ani_window',
         'HeroAppearanceAniWindow', 'BuildListviewData',
         lambda prev: striker_list_factory(prev, 'display')),
        ('gclient.gamesystem.uihall.uihero.skin_animation_pop_window',
         'SkinAnimationPopWindow', '_CollectSkins',
         lambda prev: striker_list_factory(prev, 'popup')),
        ('gclient.gamesystem.uihall.uihero.skin_animation_pop_window',
         'SkinAnimationPopWindow', 'Show',
         lambda prev: striker_list_factory(prev, 'popup-show')),
        ('gclient.gamesystem.uihall.uihero.skin_execute_pop_window',
         'SkinExecutePopWindow', '_CollectSkins',
         lambda prev: striker_list_factory(prev, 'execution-show')),
        ('gclient.gamesystem.uihall.uihero.skin_execute_pop_window',
         'SkinExecutePopWindow', 'Show',
         lambda prev: striker_list_factory(prev, 'execution-show')),
        ('gclient.gameplay.logic_base.entities.combatavatarmembers.cimp_execute',
         'CombatAvatarMember', 'GetCurArmExecutionItemId',
         striker_execution_factory),
        ('gclient.gameplay.logic_moba_zombie.combat_avatar_moba_zombie',
         'CombatAvatarMobaZombie', 'GetCurArmExecutionItemId',
         striker_execution_factory),
        ('gclient.gameplay.logic_moba_zombie.combat_avatar_moba_zombie',
         'PlayerCombatAvatarMobaZombie', 'GetCurArmExecutionItemId',
         striker_execution_factory),
        ('gclient.gameplay.logic_moba_nightmare.combat_avatar_moba_nightmare',
         'PlayerCombatAvatarMobaNightmare', 'GetCurArmExecutionItemId',
         striker_execution_factory),
        ('gclient.gamesystem.models.hall_teammate_model_manager',
         'HallModelManager', 'OnTeamMemberChanged', striker_team_factory),
        ('gclient.gameplay.logic_base.models.calculation_model_manager',
         'CalculationModelManager', 'PlayDisplayAnim', striker_postmatch_factory),
    ))
    for module_name, class_name, method, factory in specs:
        module = sys.modules.get(module_name)
        cls = getattr(module, class_name, None) if module is not None else None
        if not isinstance(cls, type):
            continue
        key = (id(cls), 'striker-consumer:' + method)
        if key in install_seen:
            continue
        if _v109_wrap_method(cls, method, factory):
            install_seen.add(key)
            added += 1
        elif getattr(getattr(cls, method, None), '_v109_wrap', False):
            install_seen.add(key)
        # v2.113: bounded discovery probe - list the class's
        # profile-cosmetic method names once so the avatar
        # equip RPC name lands in the next debug log.
        try:
            _probe_cls = cls
        except Exception:
            _probe_cls = None
        if (_probe_cls is not None and
                ('v2113-member-probe', id(_probe_cls)) not in install_seen):
            install_seen.add(('v2113-member-probe', id(_probe_cls)))
            try:
                _pn = [m for m in dir(_probe_cls) if
                       ('Avatar' in m or 'HeadIcon' in m or
                        'CardBg' in m or 'ChatBubble' in m)]
                _v109_log(('member-probe',),
                          'member cosmetic names %r'
                          % (_pn[:48],), 1)
            except Exception:
                pass
        if (key in install_seen
                and module_name == 'gclient.gamesystem.models.hall_teammate_model_manager'
                and method == 'OnTeamMemberChanged'):
            refresh_key = (id(cls), 'striker-team-listeners-refreshed')
            if refresh_key not in install_seen:
                events = sys.modules.get('gclient.framework.util.events')
                refresh = getattr(events, 'RefreshListeners', None)
                if callable(refresh):
                    try:
                        refresh(cls)       # official hotfix listener rebind API
                        install_seen.add(refresh_key)
                        _v109_log(('striker-team-listener-refresh',
                                   cls.__module__, cls.__name__),
                                  'Striker Join Team listeners refreshed cls=%s.%s'
                                  % (cls.__module__, cls.__name__), 2)
                    except Exception as exc:
                        _v109_log(('striker-team-listener-error', repr(exc)),
                                  'Striker Join Team listener refresh error=%r'
                                  % (exc,), 1)
                else:
                    install_seen.add(refresh_key)
                    _v109_log(('striker-team-listener-unavailable',),
                              'Striker Join Team official RefreshListeners unavailable', 1)
    return added


def install_member_observers():
    """Complete injected flat-item member calls at their official boundaries."""
    added = 0
    modules = (
        'gclient.gamesystem.entities.avatarmembers',
        'gclient.gamesystem.entities.avatarmembers.cimp_backpack',
        'gclient.gamesystem.entities.avatarmembers.cimp_hall_item',
        'gclient.gamesystem.entities.avatarmembers.cimp_zone',
    )
    for module_name in modules:
        module = sys.modules.get(module_name)
        cls = getattr(module, 'PlayerAvatarMember', None) if module else None
        if not isinstance(cls, type):
            continue
        for method in MEMBER_METHODS:
            if not callable(getattr(cls, method, None)):
                continue
            key = (id(cls), 'native-member:' + method)
            if key in install_seen:
                continue
            factory = (lambda prev, method=method:
                       member_factory(prev, method))
            if _v109_wrap_method(cls, method, factory):
                install_seen.add(key)
                added += 1
            elif getattr(getattr(cls, method, None), '_v109_wrap', False):
                install_seen.add(key)
            # v2.113: bounded discovery probe - list the class's
            # profile-cosmetic method names once so the avatar
            # equip RPC name lands in the next debug log.
            try:
                _probe_cls = cls
            except Exception:
                _probe_cls = None
            if (_probe_cls is not None and
                    ('v2113-member-probe', id(_probe_cls)) not in install_seen):
                install_seen.add(('v2113-member-probe', id(_probe_cls)))
                try:
                    _pn = [m for m in dir(_probe_cls) if
                           ('Avatar' in m or 'HeadIcon' in m or
                            'CardBg' in m or 'ChatBubble' in m)]
                    _v109_log(('member-probe',),
                              'member cosmetic names %r'
                              % (_pn[:48],), 1)
                except Exception:
                    pass
    return added


def _v109_install():
    """Install only on loaded native classes; repeated calls are idempotent."""
    added = install_gun_observers()
    added += install_emote_observers()
    added += install_melee_observers()
    added += install_panpan_observers()
    added += install_wheel_observers()
    added += install_readback_getters()
    added += install_display()
    added += install_striker_observers()
    added += install_member_observers()
    classes = []
    for module_name in (
            'gshare.ihall_item',
            'gclient.gamesystem.entities.avatarmembers.cimp_hall_item'):
        try:
            module = sys.modules.get(module_name)
            cls = getattr(module, 'IHallItems', None) if module else None
            if isinstance(cls, type) and all(id(cls) != id(old) for old in classes):
                classes.append(cls)
        except Exception:
            continue
    for cls in classes:
        for method in ('_HasItemById', 'HasItemByItemId',
                       'ItemCountByItemId', 'GetItemByItemId'):
            key = (id(cls), method)
            if key in install_seen:
                continue
            factory = lambda prev: item_factory(prev, direct=True)
            if _v109_wrap_method(cls, method, factory):
                install_seen.add(key)
                added += 1
            elif getattr(getattr(cls, method, None), '_v109_wrap', False):
                install_seen.add(key)
            # v2.113: bounded discovery probe - list the class's
            # profile-cosmetic method names once so the avatar
            # equip RPC name lands in the next debug log.
            try:
                _probe_cls = cls
            except Exception:
                _probe_cls = None
            if (_probe_cls is not None and
                    ('v2113-member-probe', id(_probe_cls)) not in install_seen):
                install_seen.add(('v2113-member-probe', id(_probe_cls)))
                try:
                    _pn = [m for m in dir(_probe_cls) if
                           ('Avatar' in m or 'HeadIcon' in m or
                            'CardBg' in m or 'ChatBubble' in m)]
                    _v109_log(('member-probe',),
                              'member cosmetic names %r'
                              % (_pn[:48],), 1)
                except Exception:
                    pass
        for method, detail in (
                ('GetItemsBySubType', False),
                ('GetItemsByDetailSubType', True),
                ('IterItemsByDetailSubType', True),
                ('HasItemsByDetailSubType', True)):
            key = (id(cls), method)
            if key in install_seen:
                continue
            factory = lambda prev, detail=detail: subtype_factory(prev, detail)
            if _v109_wrap_method(cls, method, factory):
                install_seen.add(key)
                added += 1
            elif getattr(getattr(cls, method, None), '_v109_wrap', False):
                install_seen.add(key)
            # v2.113: bounded discovery probe - list the class's
            # profile-cosmetic method names once so the avatar
            # equip RPC name lands in the next debug log.
            try:
                _probe_cls = cls
            except Exception:
                _probe_cls = None
            if (_probe_cls is not None and
                    ('v2113-member-probe', id(_probe_cls)) not in install_seen):
                install_seen.add(('v2113-member-probe', id(_probe_cls)))
                try:
                    _pn = [m for m in dir(_probe_cls) if
                           ('Avatar' in m or 'HeadIcon' in m or
                            'CardBg' in m or 'ChatBubble' in m)]
                    _v109_log(('member-probe',),
                              'member cosmetic names %r'
                              % (_pn[:48],), 1)
                except Exception:
                    pass
        method = 'GetItemsByDetailSubTypeList'
        key = (id(cls), method)
        if key not in install_seen:
            if _v109_wrap_method(cls, method, subtype_list_factory):
                install_seen.add(key)
                added += 1
            elif getattr(getattr(cls, method, None), '_v109_wrap', False):
                install_seen.add(key)
            # v2.113: bounded discovery probe - list the class's
            # profile-cosmetic method names once so the avatar
            # equip RPC name lands in the next debug log.
            try:
                _probe_cls = cls
            except Exception:
                _probe_cls = None
            if (_probe_cls is not None and
                    ('v2113-member-probe', id(_probe_cls)) not in install_seen):
                install_seen.add(('v2113-member-probe', id(_probe_cls)))
                try:
                    _pn = [m for m in dir(_probe_cls) if
                           ('Avatar' in m or 'HeadIcon' in m or
                            'CardBg' in m or 'ChatBubble' in m)]
                    _v109_log(('member-probe',),
                              'member cosmetic names %r'
                              % (_pn[:48],), 1)
                except Exception:
                    pass
    avatar_module = sys.modules.get('gclient.framework.entities.avatar')
    avatar_cls = getattr(avatar_module, 'PlayerAvatar', None) if avatar_module else None
    if isinstance(avatar_cls, type):
        # init_from_dict binds CallServer to one of these implementations on
        # each avatar instance, so a class-only CallServer hook is insufficient.
        for method in ('CallServer', 'CallServerOld', 'CallServerOffline'):
            key = (id(avatar_cls), method)
            if key in install_seen:
                continue
            if _v109_wrap_method(avatar_cls, method, call_server_factory):
                install_seen.add(key)
                added += 1
            elif getattr(getattr(avatar_cls, method, None), '_v109_wrap', False):
                install_seen.add(key)
        key = (id(avatar_cls), 'HasExtraEmote')
        if key not in install_seen:
            if _v109_wrap_method(
                    avatar_cls, 'HasExtraEmote', extra_emote_factory):
                install_seen.add(key)
                added += 1
            elif getattr(getattr(
                    avatar_cls, 'HasExtraEmote', None), '_v109_wrap', False):
                install_seen.add(key)
        try:
            avatar, _warehouse = native_avatar()
            if isinstance(avatar, avatar_cls):
                added += bind_avatar_calls(avatar)
        except Exception:
            pass
    combat_module = sys.modules.get(
        'gclient.gamesystem.entities.avatarmembers.cimp_combat')
    emote_cls = getattr(combat_module, 'CArmEmoteInfos', None) \
        if combat_module else None
    if isinstance(emote_cls, type):
        key = (id(emote_cls), 'GetEmoteItemID')
        if key not in install_seen:
            if _v109_wrap_method(
                    emote_cls, 'GetEmoteItemID', emote_reader_factory):
                install_seen.add(key)
                added += 1
            elif getattr(getattr(
                    emote_cls, 'GetEmoteItemID', None), '_v109_wrap', False):
                install_seen.add(key)
    # Emote/vault code also asks the avatar member directly.  The wrapper
    # resolves its warehouse and inserts the same real item before the call.
    for module_name in (
            'gclient.gamesystem.entities.avatarmembers',
            'gclient.gamesystem.entities.avatarmembers.cimp_backpack'):
        try:
            module = sys.modules.get(module_name)
            cls = getattr(module, 'PlayerAvatarMember', None) if module else None
            if not isinstance(cls, type):
                continue
            for method, factory in (
                    ('HasItemByItemIdIncludeTimeLimit',
                     lambda prev: item_factory(prev, direct=False)),
                    ('ApplyMelee', melee_receiver_factory)):
                key = (id(cls), method)
                if key in install_seen:
                    continue
                if _v109_wrap_method(cls, method, factory):
                    install_seen.add(key)
                    added += 1
                elif getattr(getattr(cls, method, None), '_v109_wrap', False):
                    install_seen.add(key)
                # v2.113: bounded discovery probe - list the class's
                # profile-cosmetic method names once so the avatar
                # equip RPC name lands in the next debug log.
                try:
                    _probe_cls = cls
                except Exception:
                    _probe_cls = None
                if (_probe_cls is not None and
                        ('v2113-member-probe', id(_probe_cls)) not in install_seen):
                    install_seen.add(('v2113-member-probe', id(_probe_cls)))
                    try:
                        _pn = [m for m in dir(_probe_cls) if
                               ('Avatar' in m or 'HeadIcon' in m or
                                'CardBg' in m or 'ChatBubble' in m)]
                        _v109_log(('member-probe',),
                                  'member cosmetic names %r'
                                  % (_pn[:48],), 1)
                    except Exception:
                        pass
        except Exception:
            continue
    if added:
        _v109_log(('installed', added), 'native warehouse wrappers added=%d' % added, 1)
    return added


# ---------------------------------------------------------------------------
# v10.12.2: stable-row max-variant metadata + validated native menu equip
# ---------------------------------------------------------------------------
WEAPON_MENU_NONCE = [0]
WEAPON_MENU_THREAD = [False]


def weapon_menu_name(item_id, max_level=0):
    """Authentic translated max-item name; custom labels stay in C++ only."""
    item_id = _v109_int(item_id, 0)
    template_id = _v109_int(ITEM_TO_SKIN.get(item_id, item_id), item_id)
    info = WEP_SKIN_INFO.get(template_id) or {}
    name = _display_text(info.get('name') or '', '')
    if not name or name == str(template_id):
        row = _v109_row(item_id)
        name = _proto_english_name(
            row, ('en_name', 'english_name', 'name_en', 'name', 'skin_name'), '')
        name = _display_text(name, str(item_id))
    if _contains_cjk(name):
        translated = _lang_translate(name)
        if translated and not _contains_cjk(translated):
            name = translated
    name = str(name or item_id).replace('|', '/').replace('\n', ' ')
    name = name.replace('\r', ' ').strip()[:220]
    if max_level > 0 and 'Lv.' not in name:
        name = '%s  Lv.%d' % (name, max_level)
    return name


def weapon_menu_meta_lines():
    """Build V| rows without changing WEP/WEP_SKIN_INFO or stable indices."""
    lines = ['VBEGIN']
    total = 0
    catalogs = (WEP, globals().get('WEP_MERGED_DISPLAY') or {})
    for catalog in catalogs:
        for equip_id, entries in catalog.items():
            rows = []
            for index, skin_id in enumerate(entries[1:], start=1):
                item_id = base_id = max_item = max_level = 0
                try:
                    item_id, base_id, max_item, max_level = upgrade_state(
                        skin_id)
                except Exception:
                    pass
                category = _v109_category(item_id)
                if category not in ('weapon', 'melee'):
                    item_id = max_item = max_level = 0
                    category = None
                if max_item and _v109_category(max_item) != category:
                    max_item = 0
                family = base_id or item_id or _v109_int(skin_id, 0)
                # Native max mode must select an actual max row from the same
                # stable catalog.  A base-only family is not silently upgraded.
                candidate = bool(item_id and (
                    (max_level and max_item == item_id)
                    or not max_level))
                rows.append({
                    'equip': _v109_int(equip_id, 0), 'index': index,
                    'item': item_id, 'max': max_item, 'level': max_level,
                    'family': family, 'candidate': candidate,
                    'native': item_id if category == 'weapon' else 0,
                    'native_max': (max_item if category == 'weapon' else 0),
                })
            chosen = set()
            for row in rows:
                representative = False
                if row['candidate'] and row['family'] not in chosen:
                    chosen.add(row['family'])
                    representative = True
                name = (weapon_menu_name(
                    row['max'] or row['item'], row['level'])
                    if representative and row['item'] else '-')
                lines.append('V|%d|%d|%d|%d|%d|%d|%s' % (
                    row['equip'], row['index'], row['native'],
                    row['native_max'], row['level'], int(representative), name))
                total += 1
                if total >= 65535:
                    lines.append('VEND')
                    return '\n'.join(lines) + '\n'
    lines.append('VEND')
    return '\n'.join(lines) + '\n'


def weapon_menu_meta_loop():
    cached = None
    last_signature = None
    last_sent = 0.0
    while True:
        try:
            if _weapon_catalog_ready[0]:
                try:
                    owners = tuple(id(owner) for owner in upgrade_owners())
                except Exception:
                    owners = ()
                consts = sys.modules.get('gshare.consts')
                warehouse_enum = getattr(
                    consts, 'WarehouseItemType', None) if consts else None
                signature = (id(WEP), len(WEP), id(WEP_SKIN_INFO),
                             len(WEP_SKIN_INFO), len(SKIN_TO_ITEM),
                             len(ITEM_TO_SKIN), owners, id(warehouse_enum),
                             id(main_cache.get('enum')))
                now = time.time()
                if cached is None or signature != last_signature:
                    cached = weapon_menu_meta_lines()
                    last_signature = signature
                    last_sent = 0.0
                if cached and (not last_sent or (
                        now - last_sent >= 30.0
                        and _hero_scene_stable() != 'match')):
                    _write_udp_chunked(_write_udp_skin, cached)
                    last_sent = now
        except Exception as exc:
            _v109_log(('weapon-meta-loop', repr(exc)),
                      'native weapon metadata loop guarded error=%r' % (exc,), 1)
        time.sleep(5 if not _weapon_catalog_ready[0] else 15)


def weapon_menu_status(nonce, level, text):
    try:
        text = str(text).replace('|', '/').replace('\n', ' ')[:320]
        _write_udp_skin('NW|%d|%d|%s\n' % (nonce, level, text))
    except Exception:
        pass


def weapon_menu_gun_id(avatar, equip_id):
    """Resolve equip_id -> official gun_id and verify its native IGunInfo."""
    try:
        infos = getattr(avatar, 'gun_infos')
    except Exception:
        return 0
    gun_id = 0
    try:
        module = sys.modules.get('gclient.data.equip_data')
        data = getattr(module, 'data', None) if module else None
        row = data.get(equip_id) if data is not None else None
        if row is None and data is not None:
            row = data.get(str(equip_id))
        gun_id = _v109_int(_v109_field(row, 'gun_id', 0), 0)
    except Exception:
        gun_id = 0
    if gun_id and infos.get(gun_id) is not None:
        return gun_id
    # Some merged/legacy rows have no equip_data gun_id.  The equip ID is
    # acceptable only when the official gun_infos map itself verifies that key.
    if infos.get(equip_id) is not None:
        return equip_id
    return 0


def weapon_menu_clear(avatar, item_id, rpc, gun_id):
    """Restore only this gun/skin-or-guise slot, not other users of the item."""
    stem = 'skin' if rpc == 'ArmGunSkin' else 'guise'
    tokens = {
        ('obj', ('gun_infos', gun_id, stem + '_item_id'), id(avatar)),
        ('obj', ('gun_infos', gun_id, stem + '_random'), id(avatar)),
    }
    state = _v109_state
    records = state.get('equip_restore', {}).get(item_id, [])
    restored = 0
    for record in reversed(list(records)):
        if record.get('token') not in tokens:
            continue
        if restore_record(record):
            restored += 1
        try:
            records.remove(record)
        except Exception:
            pass
    if not records:
        state.get('equip_restore', {}).pop(item_id, None)
    cosmetic_remember_pick(rpc, gun_id, 0)
    try:
        info = getattr(avatar, 'gun_infos').get(gun_id)
        current = _v109_int(getattr(info, stem + '_item_id', 0), 0)
    except Exception:
        current = item_id
    return current != item_id, restored


def weapon_menu_command():
    nonce = _v109_int(sync_attrs.get('iNativeWeaponNonce', 0), 0)
    if nonce <= 0 or nonce == WEAPON_MENU_NONCE[0]:
        return False
    WEAPON_MENU_NONCE[0] = nonce
    action = _v109_int(sync_attrs.get('iNativeWeaponAction', 1), 1)
    equip_id = _v109_int(sync_attrs.get('iNativeWeaponEquip', 0), 0)
    index = _v109_int(sync_attrs.get('iNativeWeaponIndex', 0), 0)
    item_id = config_pick('iNativeWeaponItem')
    try:
        if action not in (1, 2) or not equip_id or not index or not item_id:
            raise ValueError('invalid native weapon command')
        _row_id, entries = weapon_row(equip_id)
        if not entries or not 0 < index < len(entries):
            raise ValueError('stable weapon row is unavailable')
        skin_id = entries[index]
        expected = upgrade_state(skin_id)[0]
        if not expected or item_id != expected:
            raise ValueError('item does not match the stable official row')
        if _v109_category(item_id) != 'weapon':
            raise ValueError('row is not a native gun skin/guise')
        avatar, warehouse = native_avatar()
        if avatar is None or warehouse is None:
            raise ValueError('native avatar/warehouse unavailable')
        gun_id = weapon_menu_gun_id(avatar, equip_id)
        if not gun_id:
            raise ValueError('official gun_id/gun_infos mapping unavailable')
        row = _v109_row(item_id)
        main_name = _v109_main_name(_v109_field(row, 'sub_type', 0))
        rpc = ('ArmGunGuise' if main_name == 'GunGuise'
               else 'ArmGunSkin' if main_name == 'GunSkin' else None)
        if rpc is None:
            raise ValueError('official gun RPC mapping unavailable')
        if action == 2:
            cleared, restored = weapon_menu_clear(
                avatar, item_id, rpc, gun_id)
            if not cleared:
                raise ValueError('native clear readback still holds the item')
            weapon_menu_status(
                nonce, 1, '%s cleared; genuine slot baseline restored (%d fields)'
                % (rpc, restored))
            return True
        if not category_enabled('weapon'):
            raise ValueError('native Unlock Weapons is disabled')
        ensure_item(warehouse, item_id, mode='equip')
        record = injected_record(item_id)
        if not record or record[1] != 'weapon':
            raise ValueError('validated injected native item unavailable')
        info = getattr(avatar, 'gun_infos').get(gun_id)
        random_field = 'guise_random' if rpc == 'ArmGunGuise' else 'skin_random'
        random = bool(getattr(info, random_field, False))
        guid = getattr(record[2], 'guid', None)
        if not local_equip(
                avatar, rpc, (gun_id, guid, False, random), persist=True):
            raise ValueError('native field/template readback failed')
        weapon_menu_status(
            nonce, 1, '%s item=%d local readback verified; server authority unchanged'
            % (rpc, item_id))
        return True
    except Exception as exc:
        weapon_menu_status(nonce, 2, str(exc) or 'native equip failed')
        _v109_log(('weapon-menu-command', nonce, action, equip_id, index,
                   item_id, repr(exc)),
                  'native weapon menu nonce=%d action=%d equip=%d index=%d item=%d failed=%r'
                  % (nonce, action, equip_id, index, item_id, exc), 2)
        return False



def native_visual_ticks(now):
    """Run every native combat visual transaction on the game thread."""
    if now - STRIKER_MODEL_TICK[0] >= 0.75:
        STRIKER_MODEL_TICK[0] = now
        striker_model_tick()
    if now - PANPAN_PLAY_TICK[0] >= 0.75:
        PANPAN_PLAY_TICK[0] = now
        panpan_play_tick()
    if now - MELEE_VISUAL_TICK[0] >= 0.75:
        MELEE_VISUAL_TICK[0] = now
        melee_visual_tick()
    weapon_visual_tick()
    playpal_combat_tick()


base_process_nonces = globals().get('_process_equip_nonces')


def process_nonces(reason='tick'):
    processed = False
    try:
        if callable(base_process_nonces):
            processed = bool(base_process_nonces(reason))
    except Exception:
        pass
    try:
        report_config()
        weapon_menu_command()
        now = time.time()
        if any_enabled() and now - install_retry[0] >= 5.0:
            install_retry[0] = now
            _v109_install()             # loaded-module lookup only; no scans
        if (any_enabled()
                and now - restore_state.get('at', 0.0) >= 0.75):
            restore_state['at'] = now
            restore_native_picks()
        native_game_dispatch(
            'v109-native-visual-ticks', native_visual_ticks, now)
    except Exception:
        pass
    return processed


_process_equip_nonces = process_nonces
try:
    _v109_install()
except Exception as boot_error:
    _v109_log(('boot', repr(boot_error)),
              'boot install guarded error=%r' % (boot_error,), 1)
if not WEAPON_MENU_THREAD[0]:
    WEAPON_MENU_THREAD[0] = True
    threading.Thread(target=weapon_menu_meta_loop, daemon=True).start()
_plog('[CUNLOCK] native real-row cosmetic vault layer ready (%s)'
      % _COSMETIC_UNLOCK_BUILD)


# ---------------------------------------------------------------------------
# v2.19-newhud: complete authentic Ultra/EVO kill-broadcast resources
# ---------------------------------------------------------------------------
# Device rows proved that several newer skins use GetKillHudConfigForGameplay's
# new_kill_hud_* bundle while older skins use a self-contained legacy CSB.
# The established record copier intentionally handled legacy fields only.  Add
# the missing bundle at the two final record boundaries; do not rewrite the
# template row, derive resource IDs, force DLC readiness, or borrow a donor.
_V218U_NEW_HUD_FIELDS = (
    'new_kill_hud_bg', 'new_kill_hud_fx',
    'new_kill_hud_head', 'new_kill_hud_vx_node',
)
_V218U_CONFIG_CACHE = {}
_V218U_LOG_SEEN = {}


def _v218u_log(key, message, limit=2):
    try:
        count = _V218U_LOG_SEEN.get(key, 0)
        if count < limit:
            _plog('[V218U] %s' % message)
        _V218U_LOG_SEEN[key] = count + 1
    except Exception:
        pass


def real_new_hud_config(skin_id):
    """Return one complete config from the selected skin's real ID family."""
    template_id = positive_id(ITEM_TO_SKIN.get(skin_id, skin_id))
    if not template_id:
        return None
    now = time.time()
    cached = _V218U_CONFIG_CACHE.get(template_id)
    if cached:
        cached_config = cached[1]
        cached_ready = (cached_config.get('_is_dlc_ready')
                        if isinstance(cached_config, dict) else None)
        # A not-ready answer must be re-queried promptly after the real DLC
        # request.  Ready and legacy cache behavior remain unchanged.
        ttl = 10.0 if cached_config and cached_ready is not False else 1.0
        if now - cached[0] < ttl:
            return cached_config
    result = None
    try:
        ids = list(upgrade_ids(template_id) or
                   _v841_skin_ids(template_id))
        mod = sys.modules.get(
            'gclient.gameplay.uicomponents.hud_killrecord_comp')
        # Call the preserved game function.  Falling back to the current export
        # is safe (it only adds the same selected-ID candidates), but prefer the
        # original so this diagnostic/enrichment layer cannot recurse through
        # another config wrapper.
        previous = None
        if mod is not None:
            previous = (getattr(
                mod, '_orig_v841_GetKillHudConfigForGameplay', None)
                or getattr(mod, '_orig_GetKillHudConfigForGameplay', None)
                or getattr(mod, 'GetKillHudConfigForGameplay', None))
        if ids and callable(previous):
            _cfg291 = HUDCFG_CACHE.get(tuple(ids))
            if _cfg291 is None:
                _cfg291 = config_variants(
                    previous, (ids[0],), {}, ids, 'v218u-new-hud-config')
                HUDCFG_CACHE[tuple(ids)] = _cfg291
            config = _cfg291
            if _proto_get(config, 'use_new_template', None) is True:
                values = {}
                for field in _V218U_NEW_HUD_FIELDS:
                    value = _proto_get(config, field, None)
                    if not _fx_value_ok(value):
                        values = {}
                        break
                    values[field] = value
                if values:
                    # Keep the authentic legacy path with the same bundle.  It
                    # is evidence for diagnostics only; the established copier
                    # remains responsible for writing legacy record fields.
                    result = dict(values)
                    result['_source_ids'] = tuple(ids)
                    # Internal resource-preflight evidence only.  The record
                    # copier still copies exactly the four public HUD fields.
                    result['_is_dlc_ready'] = _proto_get(
                        config, 'is_dlc_ready', None)
                    result['_kill_hud_csb_path'] = _proto_get(
                        config, 'kill_hud_csb_path', None)
    except Exception as exc:
        _v218u_log(('config-error', template_id, repr(exc)),
                   'new-HUD config skipped skin=%d error=%r'
                   % (template_id, exc), 1)
        result = None
    _V218U_CONFIG_CACHE[template_id] = (now, result)
    return result


def enrich_new_hud(info, skin_id):
    if info is None or not sync_attrs.get('bSkinHack', False):
        return 0
    template_id = positive_id(ITEM_TO_SKIN.get(skin_id, skin_id))
    if not template_id:
        return 0
    config = real_new_hud_config(template_id)
    if not config:
        return 0
    copied = []
    for field in _V218U_NEW_HUD_FIELDS:
        value = config[field]
        try:
            if _mapping_get(info, field, None) == value:
                continue
            if _mapping_set(info, field, value):
                copied.append(field)
        except Exception:
            continue
    if copied:
        _v218u_log(('record', template_id, tuple(copied)),
                   'authentic new-HUD bundle skin=%d ids=%r fields=%r '
                   'legacy_path=%r values=%r'
                   % (template_id, config.get('_source_ids'), copied,
                      config.get('_kill_hud_csb_path'),
                      {field: config[field]
                       for field in _V218U_NEW_HUD_FIELDS}), 1)
    return len(copied)


_v218u_previous_copy = globals().get('_copy_skin_kill_broadcast_data')


def copy_with_new_hud(info, skin_id):
    result = (_v218u_previous_copy(info, skin_id)
              if callable(_v218u_previous_copy) else None)
    try:
        enrich_new_hud(info, skin_id)
    except Exception as exc:
        _v218u_log(('copy-error', skin_id, repr(exc)),
                   'new-HUD record copy skipped skin=%s error=%r'
                   % (skin_id, exc), 1)
    return result


if callable(_v218u_previous_copy):
    _copy_skin_kill_broadcast_data = copy_with_new_hud


# panel_kill.Push has its own previously captured legacy copier, so enriching
# only PushKillRecord would still lose the bundle on the final renderer path.
previous_panel_invoke = _v218m_panel_invoke


def _v218u_panel_invoke(previous, args, kwargs, has_subject):
    info = kwargs.get('info')
    if info is None:
        index = 1 if has_subject else 0
        if len(args) > index:
            info = args[index]
    try:
        if info is not None and sync_attrs.get('bSkinHack', False):
            enrich_new_hud(info, forced_template())
    except Exception as exc:
        _v218u_log(('panel-error', repr(exc)),
                   'new-HUD panel copy skipped error=%r' % (exc,), 1)
    return previous_panel_invoke(
        previous, args, kwargs, has_subject)


_v218m_panel_invoke = _v218u_panel_invoke
_plog('[V218U] authentic complete Ultra/EVO new-HUD broadcast bundle ready')


# ---------------------------------------------------------------------------
# v2.19-newhud-resources: real selected-row DLC completion + final-call evidence
# ---------------------------------------------------------------------------
# Hellride's complete new-HUD config still reported is_dlc_ready=False after
# AutoDownloadItem(max_item) returned.  Start the same authentic config lookup
# during the established merge/apply path and, only while that answer is False,
# request the selected row's real string dlc_id through the loaded native API.
# Never copy/force readiness, derive a DLC id, or turn a numeric resource icon
# into a lobby item.  The original PlayKillAnim call and result stay exact.
_V218UR_DLC_STATE = {}
_V218UR_LOG_SEEN = {}
_V218UR_DLC_ATTEMPTS = 3
_V218UR_DLC_SPACING = 1.5


def _v218ur_log(key, message, limit=2):
    try:
        count = _V218UR_LOG_SEEN.get(key, 0)
        if count < limit:
            _plog('[V218UR] %s' % message)
        _V218UR_LOG_SEEN[key] = count + 1
    except Exception:
        pass


def dlc_callback(success, key):
    """Observe the native (success, key) callback; never synthesize readiness."""
    try:
        template_id, dlc_id = key
    except Exception:
        template_id, dlc_id = 0, key
    _v218ur_log(('callback', key, repr(success)),
                'authentic new-HUD DLC callback skin=%s dlc=%r success=%r '
                'readiness_unchanged' % (template_id, dlc_id, success), 1)
    return None


def authentic_dlc_id(template_id, config):
    """Read a real string dlc_id from this selected item/template family."""
    rows = []
    ids = list(config.get('_source_ids') or ())
    if template_id not in ids:
        ids.append(template_id)
    for module_name in ('gclient.data.lobby_item_data',
                        'gclient.data.item_feature_data'):
        module = sys.modules.get(module_name)
        data = getattr(module, 'data', None) if module is not None else None
        if data is None:
            continue
        for row_id in ids:
            try:
                row = _data_get(data, row_id, None)
                if row is not None:
                    rows.append(row)
            except Exception:
                continue
    try:
        for module_name in FX_SOURCE_MODULES:
            row = _fx_row(module_name, template_id)
            if row is not None:
                rows.append(row)
                break
    except Exception:
        pass
    seen = set()
    for row in rows:
        if id(row) in seen:
            continue
        seen.add(id(row))
        try:
            value = _proto_get(row, 'dlc_id', None)
            if isinstance(value, str) and value.strip():
                return value.strip()
        except Exception:
            continue
    return None


def request_real_dlc(template_id, config):
    if not isinstance(config, dict) or config.get('_is_dlc_ready') is not False:
        return 0
    dlc_id = authentic_dlc_id(template_id, config)
    if not dlc_id:
        _v218ur_log(('no-dlc-id', template_id),
                    'new-HUD not ready skin=%d; selected rows expose no '
                    'string dlc_id, nothing fabricated' % template_id, 1)
        return 0
    key = (template_id, dlc_id)
    now = time.time()
    count, last = _V218UR_DLC_STATE.get(key, (0, 0.0))
    if count >= _V218UR_DLC_ATTEMPTS or now - last < _V218UR_DLC_SPACING:
        return 0
    try:
        module = sys.modules.get('gclient.framework.util.dlc_download_request')
        request_cls = getattr(module, 'DlcDownloadRequest', None) \
            if module is not None else None
        instance_fn = getattr(request_cls, 'instance', None) \
            if isinstance(request_cls, type) else None
        owner = instance_fn() if callable(instance_fn) else None
        request = getattr(owner, 'RequestDlc', None) if owner is not None else None
        if not callable(request):
            _v218ur_log(('api-missing', template_id),
                        'new-HUD DLC request API unavailable skin=%d; '
                        'native readiness preserved' % template_id, 1)
            return 0
        _V218UR_DLC_STATE[key] = (count + 1, now)
        # Official signature: RequestDlc(dlc_ids, callback, key).  The first
        # argument is iterated, so a bare string would incorrectly request
        # one DLC per character.  The callback receives (success, key); its
        # result is evidence only and never marks the HUD config ready.
        result = request([dlc_id], dlc_callback, key)
        _v218ur_log(('request', key, count + 1, repr(result)),
                    'authentic new-HUD DLC skin=%d item=%s dlc=%r '
                    'attempt=%d result=%r readiness_unchanged=False'
                    % (template_id,
                       (config.get('_source_ids') or (None,))[0],
                       dlc_id, count + 1, result), 1)
        return 1
    except Exception as exc:
        _v218ur_log(('request-error', key, count + 1, repr(exc)),
                    'new-HUD DLC request skin=%d dlc=%r attempt=%d '
                    'error=%r readiness_unchanged=False'
                    % (template_id, dlc_id, count + 1, exc), 1)
        return 0


previous_real_config = real_new_hud_config


def real_config_with_dlc(skin_id):
    config = previous_real_config(skin_id)
    try:
        if config and sync_attrs.get('bSkinHack', False):
            template_id = positive_id(ITEM_TO_SKIN.get(skin_id, skin_id))
            request_real_dlc(template_id, config)
    except Exception as exc:
        _v218ur_log(('config-error', skin_id, repr(exc)),
                    'new-HUD resource preflight skipped skin=%s error=%r'
                    % (skin_id, exc), 1)
    return config


real_new_hud_config = real_config_with_dlc
_v218ur_previous_merge = _v218m_merge_skin


def merge_with_resource_preflight(skin_id):
    result = _v218ur_previous_merge(skin_id)
    try:
        if sync_attrs.get('bSkinHack', False):
            real_config_with_dlc(skin_id)
    except Exception as exc:
        _v218ur_log(('merge-error', skin_id, repr(exc)),
                    'new-HUD merge preflight skipped skin=%s error=%r'
                    % (skin_id, exc), 1)
    return result


if callable(_v218ur_previous_merge):
    _v218m_merge_skin = merge_with_resource_preflight


def front_factory(previous, label):
    def wrapper(self, *args, **kwargs):
        template_id = 0
        config = None
        if sync_attrs.get('bSkinHack', False):
            try:
                template_id = forced_template()
                if template_id:
                    config = real_config_with_dlc(template_id)
            except Exception:
                config = None
        try:
            result = previous(self, *args, **kwargs)
        except Exception as exc:
            if template_id:
                _v218ur_log(('final-error', label, template_id, repr(exc)),
                            'final %s skin=%d args=%r kwargs=%r error=%r'
                            % (label, template_id, args, kwargs, exc), 1)
            raise
        if template_id:
            ready = config.get('_is_dlc_ready') if isinstance(config, dict) else None
            _v218ur_log(('final', label, template_id, ready,
                         repr(args), repr(result)),
                        'final %s skin=%d authentic_ready=%r args=%r '
                        'kwargs=%r result=%r'
                        % (label, template_id, ready, args, kwargs, result), 1)
        return result
    wrapper._v218ur_final = True
    return wrapper


def wrap_final(cls, method):
    guard = '_orig_v218ur_' + method
    try:
        if cls is None or guard in vars(cls):
            return False
        static = inspect.getattr_static(cls, method)
        previous = static.__func__ if isinstance(
            static, (staticmethod, classmethod)) else static
        if not callable(previous):
            return False
        wrapper = front_factory(previous, method)
        setattr(cls, guard, previous)
        if isinstance(static, staticmethod):
            setattr(cls, method, staticmethod(wrapper))
        elif isinstance(static, classmethod):
            setattr(cls, method, classmethod(wrapper))
        else:
            setattr(cls, method, wrapper)
        return True
    except Exception:
        return False


def install_final():
    installed = 0
    try:
        module = sys.modules.get('gclient.gameplay.uicomponents.hud_frontsight_comp')
        cls = getattr(module, 'HudFrontsightComp', None) if module is not None else None
        for method in ('OnShowKillHudAnim', 'PlayKillAnim'):
            installed += int(bool(wrap_final(cls, method)))
    except Exception:
        pass
    return installed


if not getattr(_v842g_install, '_v218ur_install', False):
    _v218ur_previous_install = _v842g_install

    def install_with_final():
        stats = _v218ur_previous_install()
        try:
            stats['newhud_final'] = install_final()
        except Exception:
            pass
        return stats

    install_with_final._v218ur_install = True
    _v842g_install = install_with_final

try:
    install_final()
except Exception:
    pass
_plog('[V218UR] authentic new-HUD resource preflight/final-call layer ready')


# ============================================================
# v2.85: the "UMP45 - TimeKeeper" card-name spoof (from our line)
# ============================================================
_V875_ONCE = {}
_V875_NAMES = {}
NAME_HELPERS = (
    'GetGuiseDisplayName',
    'GetSkinDisplayName',
    'GetGunSkinDisplayName',
)

def _v875_note(key, message):
    if key in _V875_ONCE:
        return
    _V875_ONCE[key] = 1
    try:
        _plog(message)
    except Exception:
        pass
def _v875_int(value):
    for attempt in ((value, 0), (value,)):
        try:
            return _safe_int(*attempt)
        except Exception:
            continue
    return 0


# ---------------------------------------------------------------------
# (1) the display-item tail: 520080096 came out as 5200800900
# ---------------------------------------------------------------------
def item_of(result):
    """A real lobby item id hiding in whatever the icon call returned."""
    if isinstance(result, bool) or result is None:
        return 0
    if isinstance(result, int):
        value = result
    else:
        try:
            text = str(result).strip()
        except Exception:
            return 0
        if not text.isdigit():
            return 0
        value = int(text)
    return value if value >= 5000000 else 0
def sig_call(fn, args, kwargs=None):
    """Call fn the way fn says it wants to be called - never crash.

    Trims positionals the callee has no room for, fills the ones it
    requires and we left empty, and hands the rest through untouched.
    Returns (called_ok, result).
    """
    if kwargs is None:
        kwargs = {}
    args = tuple(args or ())
    try:
        sig = inspect.signature(fn)
    except Exception:
        sig = None
    if sig is not None:
        named = [p for p in sig.parameters.values()
                 if p.kind in (getattr(inspect, 'Parameter').POSITIONAL_ONLY,
                               getattr(inspect, 'Parameter').POSITIONAL_OR_KEYWORD)]
        var_pos = any(p.kind == getattr(inspect, 'Parameter').VAR_POSITIONAL
                      for p in sig.parameters.values())
        try:
            sig.bind(*args, **kwargs)
        except TypeError:
            if named and not var_pos and len(args) > len(named):
                args = args[:len(named)]
            needs = []
            for index, param in enumerate(named):
                if param.default is not param.empty:
                    continue
                if param.kind == getattr(inspect, 'Parameter').POSITIONAL_ONLY:
                    continue
                if index < len(args) or param.name in kwargs:
                    continue
                needs.append(index)
            if needs:
                args = list(args)
                for index in needs:
                    while len(args) <= index:
                        args.append(None)
                    args[index] = None
                args = tuple(args)
    try:
        return True, fn(*args, **kwargs)
    except Exception as error:
        return False, error
def is_placeholder_name(text):
    try:
        low = str(text or '').strip().lower()
    except Exception:
        return True
    if not low:
        return True
    if low.isdigit():
        return True
    for token in ('custom', 'custom_guise', 'default', 'none', 'unknown',
                  'guise_name', 'show_gun_name', 'custom_guise_name'):
        if low == token or low.endswith('_' + token):
            return True
    return False
def _v875_weapon_name(item, base_item=0):
    """The gun name and the skin name, from the game's own tables."""
    gun_name = ''
    skin_name = ''
    try:
        util = sys.modules.get('gclient.util.cdata_util') or _ea_import(
            'gclient.util.cdata_util')
        for fn_name in ('GetItemName', 'GetName', 'GetItemShowName'):
            fn = getattr(util, fn_name, None) if util is not None else None
            if callable(fn):
                for arg in (base_item, item):
                    if not arg:
                        continue
                    ok, value = sig_call(fn, (arg,))
                    if ok and value and not is_placeholder_name(value):
                        gun_name = gun_name or str(value)
                        break
    except Exception:
        pass
    try:
        row = None
        resolver = globals().get('row_of')
        if callable(resolver):
            row = resolver(item)
        if row is not None:
            for col in ('name', 'skin_name', 'guise_name', 'show_name',
                        'item_name'):
                try:
                    value = (row.get(col) if hasattr(row, 'get')
                             else getattr(row, col, None))
                except Exception:
                    value = None
                if value and not is_placeholder_name(value):
                    skin_name = str(value)
                    break
    except Exception:
        pass
    for name in ('_dname', '_display_text', '_lang_translate'):
        if gun_name and skin_name:
            break
        fn = globals().get(name)
        if not callable(fn):
            continue
        for arg in (skin_name, item, base_item):
            if not arg:
                continue
            try:
                value = fn(arg) if not isinstance(arg, str) else fn(arg)
            except Exception:
                continue
            if value and not is_placeholder_name(value):
                if not skin_name and isinstance(arg, str):
                    skin_name = str(value)
                elif not gun_name:
                    gun_name = str(value)
                break
    if gun_name and skin_name and gun_name.strip().lower() == \
            skin_name.strip().lower():
        # the helper answered with the skin name twice - keep one
        gun_name = ''
    return gun_name, skin_name
def _v875_display_name(previous, args, kwargs):
    """Call the real helper; only replace a custom/empty answer."""
    result = previous(*args, **kwargs)
    try:
        if not is_placeholder_name(result):
            return result
        item = 0
        for candidate in list(args) + list(kwargs.values()):
            got = item_of(candidate)
            if got:
                item = got
                break
        if not item:
            return result
        gun_name, skin_name = _v875_weapon_name(item)
        if not skin_name:
            return result
        name = ('%s - %s' % (gun_name, skin_name)) if gun_name else skin_name
        if name != result:
            key = (item, name)
            if key not in _V875_NAMES:
                _V875_NAMES[key] = 1
                _plog('[V875] drop name item=%d -> %r (was %r)'
                      % (item, name, result))
        return name
    except Exception:
        return result
def install_names():
    out = []
    try:
        mod = sys.modules.get('gclient.util.gun_skin_util') or _ea_import(
            'gclient.util.gun_skin_util')
    except Exception:
        mod = None
    if mod is not None:
        for name in NAME_HELPERS:
            prev = getattr(mod, name, None)
            if not callable(prev) or getattr(prev, '_v875_name', False):
                continue

            def make(previous, label):
                def wrapper(*a, **k):
                    return _v875_display_name(previous, a, k)
                wrapper._v875_name = True
                wrapper.__name__ = label
                return wrapper
            try:
                setattr(mod, name, make(prev, name))
                out.append(name)
            except Exception:
                pass

    # the pickup windows themselves, as a fallback for the drop card
    for mod_name, cls_name, meths in (
        ('gclient.gameplay.logic_base.ui.hud_pickup_pc_comp', 'PickupItem',
         ('LoadData',)),
        ('gclient.gameplay.logic_moba.ui.moba_hud_pickup_comp', 'PickupItem',
         ('LoadData',)),
    ):
        try:
            pickup = sys.modules.get(mod_name) or _ea_import(mod_name)
        except Exception:
            pickup = None
        cls = getattr(pickup, cls_name, None) if pickup is not None else None
        if not isinstance(cls, type):
            continue
        for meth in meths:
            prev = getattr(cls, meth, None)
            if not callable(prev) or getattr(prev, '_v875_pickup', False):
                continue

            def make(previous, label):
                def wrapper(self, *a, **k):
                    result = previous(self, *a, **k)
                    try:
                        item = 0
                        for attr in ('item_id', 'base_item_id', 'guise_item_id',
                                     'skin_item_id'):
                            item = item or _v875_int(
                                getattr(self, attr, None))
                        if item:
                            gun_name, skin_name = _v875_weapon_name(item)
                            if skin_name:
                                full = ('%s - %s' % (gun_name, skin_name)
                                        if gun_name else skin_name)
                                for attr in ('name_text', 'item_name',
                                             'show_name'):
                                    node = getattr(self, attr, None)
                                    if node is None:
                                        continue
                                    for setter in ('setString', 'SetString',
                                                   'setText', 'SetText'):
                                        fn = getattr(node, setter, None)
                                        if callable(fn):
                                            fn(full)
                                            break
                                _v875_note(
                                    ('pickup-name', item),
                                    '[V875] pickup card name item=%d -> %r'
                                    % (item, full))
                    except Exception:
                        pass
                    return result
                wrapper._v875_pickup = True
                wrapper.__name__ = meth
                return wrapper
            try:
                setattr(cls, meth, make(prev, cls_name + '.' + meth))
                out.append('%s.%s' % (cls_name, meth))
            except Exception:
                pass
    if out:
        _v875_note(('names', tuple(out)),
                   '[V875] drop names hooked: %s' % (', '.join(out),))
    return out


# ---------------------------------------------------------------------
# loop
# ---------------------------------------------------------------------


# install + bounded retry (gun_skin_util may load late)
def _v875_boot():
    for _try in range(24):
        try:
            got = install_names()
        except Exception:
            got = []
        if got:
            return
        try:
            time.sleep(15.0)
        except Exception:
            return


try:
    threading.Thread(target=_v875_boot, daemon=True).start()
except Exception:
    pass

try:
    install_names()
except Exception:
    pass


# ============================================================
# v2.86 helpers: the tier filter + the kit item map
# ============================================================
_V286_TIERS = frozenset((5, 6, 7, 8))


CAMO_CACHE = {}
CAMO_BLOCK = frozenset((
    'abyss', 'venom', 'hellhound', 'digital', 'geometric', 'stripe',
    'wings', 'festival', 'cheetah', 'lantern', 'chinese opera', 'sakura',
    'death', 'silent', 'dragons', 'sakura festival', 'snakeskin', 'monarch',
    'phoenix', 'frost', 'ember', 'inferno', 'reaper', 'doom',
))


def shared_camo_tails():
    """Name tails (after 'Gun - ') that appear on MANY guns = the shared
    cross-gun camo families (the 0100-family paints).  Computed once."""
    cache = CAMO_CACHE
    if cache.get('tails') is not None:
        return cache['tails']
    tails = {}
    try:
        wep = globals().get('WEP') or {}
        info = globals().get('WEP_SKIN_INFO') or {}
        for _eid, row in wep.items():
            if not isinstance(row, (list, tuple)):
                continue
            for tpl in row:
                if not isinstance(tpl, int):
                    continue
                name = (info.get(tpl) or {}).get('name') or ''
                if ' - ' not in name:
                    continue
                tail = name.split(' - ', 1)[1].strip().lower()
                if tail:
                    tails.setdefault(tail, set()).add(_eid)
    except Exception:
        tails = {}
    shared = frozenset(t for t, guns in tails.items() if len(guns) >= 6)
    cache['tails'] = shared
    return shared


def menu_keep(skin_id, info):
    """v2.88 per the operator: keep EVERY skin except the cross-gun camo
    families listed in every gun picker ("Abyss","Venom","Hellhound",...
    there's a lot").  A family is dropped when its name tail is shared
    across many guns or is in the explicit blocklist.  Fail open."""
    try:
        info = info or (globals().get('WEP_SKIN_INFO') or {}).get(skin_id) or {}
        name = info.get('name') or ''
        tail = name.split(' - ', 1)[1].strip().lower() if ' - ' in name else ''
        if not tail:
            return True
        tail = tail.rsplit(' lv', 1)[0].strip()
        if tail in CAMO_BLOCK:
            return False
        if tail in shared_camo_tails():
            return False
        return True
    except Exception:
        return True


def menu_tier_ok(skin_id, info):
    """Ultra/Eternal/EVO/Xtreme (the payload's own _v218so_tiers) or a
    leveled (Evo/LV) row.  Fail open - errors never hide a skin."""
    try:
        info = info or (globals().get('WEP_SKIN_INFO') or {}).get(skin_id)             or {}
        q = _safe_int(info.get('skin_quality'), 0)
        if not q:
            try:
                _m = sys.modules.get('gclient.data.gun_skin_template_data')
                row = (_data_get(getattr(_m, 'data', None), skin_id, None)
                       if _m is not None else None)
                if row is not None:
                    q = _safe_int(_proto_get(
                        row, 'quality', _proto_get(row, 'rarity', 0)), 0)
            except Exception:
                q = 0
        if q in _V286_TIERS:
            return True
        return _safe_int(info.get('skin_level'), 0) > 0
    except Exception:
        return True


def kit_item(template_id):
    """The kit map fallback: mall_diy_gift_kit rows carry the skin and
    the lobby_item_id."""
    try:
        _km = sys.modules.get('gclient.data.mall_diy_gift_kit_data')
        data = getattr(_km, 'data', None) if _km is not None else None
        if data is None:
            return 0
        template_id = _safe_int(template_id, 0)
        for _k, row in _data_items(data):
            try:
                for field in ('skin_id', 'gun_skin_id', 'template_id',
                              'gun_skin_template_id', 'reward_id',
                              'reward_item_id'):
                    if _safe_int(_proto_get(row, field, 0), 0) == template_id:
                        got = _safe_int(
                            _proto_get(row, 'lobby_item_id', 0), 0)
                        if got:
                            return got
            except Exception:
                continue
    except Exception:
        pass
    return 0

# boot hero-catalog send - single sender (v842). Replaces the
# duplicate early send that lived in esp.py (same exec pass).
if not _ALREADY_LOADED:
    try:
        _send_hero_info()
    except Exception:
        pass
