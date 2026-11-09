# ============================================================
# KILLS.PY (payload feature module)
# PROVIDES: is_gun_upgrade_item, is_upgrade_item, cur_level_factory, feature_probe_factory, install_upgrade_level, _v839_install, _v839_loop, _v841_log, unique_ids, _v841_skin_ids, current_skin_ids, context_ids, empty_config, config_brief, ... +76 more | HUDCFG_CACHE, _V841M2_MELEE_EQUIPS, _V841M2_MERGED_DAGGER_ROWS, _V841M2_BASE_ITEMS, _V842G_TRACER_FIELDS, _V842G_BROADCAST_FIELDS
# REQUIRES: shared namespace (config/names/main/game_api/catalog);
#           game modules imported inline, verified against the dumps.
# Feature module - see REWRITE_PLAN.md S1.
# ============================================================
"""Kill-feed + HUD icons: PushKillRecord wrap-chain seed, kill-anim selection, HUD icon tier rules (_v286_TIERS)."""

# #======================================================================
# //  KILLS.PY
# //
# //  This file is for: KILL CONFIG: the v841 kill-anim selection + kill-config cache + the PlayKillAnim/OnShowKillHudAnim front factories (the kill-anim companion prefetch lives here).
# //
# //  Part of the split TREACKY BS payload (v2.112).  The runtime
# //  file payload/skins_payload.py is GENERATED: run
# //  tools/build_payload.py after editing these modules.
# #======================================================================
def is_gun_upgrade_item(manager, item_id):
    try:
        included = gun_upgrade_items()
        if item_id in included:
            return True
        base = _v839_base_item(manager, item_id)
        return bool(base and base in included)
    except Exception:
        return False


def is_upgrade_item(manager, item_id):
    # New directive covers every included gun skin; the old selected-item path
    # remains for melee and for backwards-compatible selected base families.
    return (is_gun_upgrade_item(manager, item_id)
            or is_selected_upgrade_item(manager, item_id))


def cur_level_factory(prev):
    def wrapper(*a, **k):
        original = prev(*a, **k)
        try:
            if not melee_active():
                return original
            item_id = item_arg(a, k)
            if item_id is None:
                return original
            manager = manager_for_call(wrapper._v839_cls, a)
            if not is_upgrade_item(manager, item_id):
                return original
            maximum = real_max_level(manager, item_id)
            if maximum is not None:
                _v839_log(('max-level', item_id, original, maximum),
                          'included gun/selected item=%d level %r -> game max %d'
                          % (item_id, original, maximum), 1)
                return maximum
        except Exception as e:
            _v839_log(('cur-level-error', repr(e)),
                      'current-level wrapper absorbed: %r' % (e,), 2)
        return original
    return wrapper


def feature_probe_factory(prev, label):
    """Evidence only: the game's real feature configuration decides."""
    def wrapper(*a, **k):
        result = prev(*a, **k)
        try:
            if melee_active():
                item_id = item_arg(a, k)
                if item_id is not None:
                    manager = manager_for_call(wrapper._v839_cls, a)
                    if is_selected_upgrade_item(manager, item_id):
                        sig = call_sig(a)
                        _v839_log(('feature', label, sig, repr(result)),
                                  '%s(%s) -> %r (configuration preserved)'
                                  % (label, sig, result), 1)
        except Exception:
            pass
        return result
    return wrapper


def install_upgrade_level():
    mod = sys.modules.get('gclient.util.gun_upgrade_util')
    cls = getattr(mod, 'GunUpgradeDataMgr', None) if mod is not None else None
    if cls is None:
        return 0

    def cur_factory(prev):
        wrapper = cur_level_factory(prev)
        wrapper._v839_cls = cls
        return wrapper

    def feature_factory(prev, label):
        wrapper = feature_probe_factory(prev, label)
        wrapper._v839_cls = cls
        return wrapper

    done = bool(_v839_wrap_method(cls, 'GetCurItemLevel', cur_factory))
    for meth in ('HasFeatureByItemId', 'CanShowFeature'):
        done += bool(_v839_wrap_method(
            cls, meth,
            lambda prev, meth=meth: feature_factory(prev, meth)))
    if done:
        _v839_log('max-installed',
                  'selected-skin real-max hooks=%d; kill features remain '
                  'configuration-driven' % done, 1)
    return int(done)


def _v839_install():
    """sys.modules-only installer; safe to repeat from the retry thread."""
    result = {'melee': 0, 'favorite': 0, 'max': 0}
    try:
        result['melee'] = install_melee_access()
    except Exception:
        pass
    try:
        result['favorite'] = install_favorite_recovery()
    except Exception:
        pass
    try:
        result['max'] = install_upgrade_level()
    except Exception:
        pass
    # v8.41 is appended after this function; early boot calls simply skip it,
    # while the established retry watcher installs it once modules exist.
    try:
        late_v841 = globals().get('install_kill_hud')
        if callable(late_v841):
            late_v841()
    except Exception:
        pass
    # Same retry/result contract: melee2 adds no result key and no thread.
    try:
        late_melee2 = globals().get('_v841m2_install')
        if callable(late_melee2):
            late_melee2()
    except Exception:
        pass
    try:
        late_gunfx = globals().get('_v842g_install')
        if callable(late_gunfx):
            late_gunfx()
    except Exception:
        pass
    return result


def _v839_loop():
    # Avoid the game's boot-import storm.  No game import is performed
    # here; the game must load each module before it can be wrapped.
    time.sleep(30.0)
    for _ in range(120):
        try:
            _v839_install()
        except Exception:
            pass
        time.sleep(5.0)


try:
    _v839_log('initial', 'initial hooks %r' % (_v839_install(),), 1)
except Exception as _v839_boot_error:
    _v839_log('initial-error', 'initial install failed: %r'
              % (_v839_boot_error,), 1)
try:
    if not _ALREADY_LOADED:
        threading.Thread(target=_v839_loop, daemon=True,
                         name='v839-native-hooks').start()
except Exception:
    pass


# ============================================================
# v8.41: SELECTED-SKIN KILL HUD CONFIG / FRONT-SIGHT RECOVERY
# ============================================================
# Runtime evidence distinguishes the kill RECORD from the local front-sight
# kill animation.  v8.40 enriched only the record and overrode one config
# lookup.  This layer covers both config entry points, keeps the real game
# config/result as fallback, and never forces DLC readiness.
# Scope: bSkinHack + the current selected skin + an active local kill-HUD call.

_v841_log_seen = {}
front_state = {'ids': (), 'depth': 0}


def _v841_log(key, msg, limit=3):
    try:
        n = _v841_log_seen.get(key, 0)
        if n >= limit:
            return
        if len(_v841_log_seen) >= 160 and key not in _v841_log_seen:
            return
        _v841_log_seen[key] = n + 1
        _plog('[V841] %s' % (msg,))
    except Exception:
        pass


def unique_ids(values):
    out = []
    try:
        for value in values:
            if isinstance(value, bool):
                continue
            try:
                value = int(value or 0)
            except Exception:
                continue
            if value > 0 and value not in out:
                out.append(value)
    except Exception:
        pass
    return out


def _v841_skin_ids(skin_id):
    """Both real namespaces for one selected skin, preferred item first."""
    try:
        template_id = ITEM_TO_SKIN.get(skin_id, skin_id)
        info = WEP_SKIN_INFO.get(template_id) or {}
        item_id = (SKIN_TO_ITEM.get(template_id)
                   or info.get('lobby_item_id') or template_id)
        return unique_ids((item_id, template_id))
    except Exception:
        return []


def current_skin_ids():
    """Resolve only the CURRENT weapon's menu pick; never every menu pick."""
    if not sync_attrs.get('bSkinHack', False):
        return []
    skin_id = 0
    try:
        ca = None
        get_local = globals().get('_local_combat_avatar')
        if callable(get_local):
            ca = get_local()
        if ca is None:
            sp = getattr(Space, '_instance', None)
            owner = getattr(sp, 'owner', None) if sp else None
            ca = getattr(owner, 'combat_avatar', None) if owner else None
        weapon = ca.GetCurWeapon() if ca is not None else None
        wid = (getattr(weapon, 'weapon_id', 0)
               or getattr(weapon, 'equip_id', 0)) if weapon else 0
        if wid:
            skin_id = _get_selected_skin_for_weapon(wid)
    except Exception:
        skin_id = 0
    if not skin_id:
        try:
            skin_id, _wc = _get_kill_skin(None)
        except Exception:
            skin_id = 0
    return _v841_skin_ids(skin_id) if skin_id else []


def context_ids():
    values = []
    try:
        forced = globals().get('_force_kill_hud_skin', [None])[0]
        if forced:
            values.extend(_v841_skin_ids(forced))
            values.append(forced)
    except Exception:
        pass
    try:
        values.extend(front_state.get('ids') or ())
    except Exception:
        pass
    return unique_ids(values)


def empty_config(value):
    if value is None or value is False:
        return True
    try:
        if isinstance(value, (dict, list, tuple, set, str, bytes)):
            return len(value) == 0
    except Exception:
        pass
    return False


def config_brief(value):
    try:
        if isinstance(value, dict):
            return 'dict keys=%r' % (list(value.keys())[:18],)
        if isinstance(value, (tuple, list)):
            return '%s %r' % (type(value).__name__, list(value)[:4])
        keys = _proto_keys(value, 18)
        if keys:
            return '%s keys=%r' % (type(value).__name__, keys)
        return '%s %r' % (type(value).__name__, value)
    except Exception:
        return type(value).__name__


HUDCFG_CACHE = {}


def config_variants(prev, args, kwargs, candidates, label):
    """Try selected IDs, then the exact original call; first REAL config wins."""
    if not args or not candidates:
        return prev(*args, **kwargs)
    original_id = args[0]
    # Do not coerce the original ID (or its type). Keep its selected priority
    # when already present; otherwise append it as the final fallback.
    ordered = unique_ids(candidates)
    original_index = -1
    for index, candidate in enumerate(ordered):
        try:
            same = type(candidate) is type(original_id) and candidate == original_id
        except Exception:
            same = False
        if same:
            ordered[index] = original_id  # retain exact type/object and priority
            original_index = index
            break
    if original_index < 0:
        ordered.append(original_id)
        original_index = len(ordered) - 1
    last_empty = None
    for index, candidate in enumerate(ordered):
        is_original = index == original_index
        call_args = (candidate,) + tuple(args[1:])
        try:
            result = prev(*call_args, **kwargs)
        except Exception as exc:
            _v841_log((label, 'error', candidate, repr(exc)),
                      '%s id=%s error=%r' % (label, candidate, exc), 1)
            if is_original:
                raise
            continue
        _v841_log((label, candidate, config_brief(result)),
                  '%s id=%s -> %s' % (label, candidate,
                                      config_brief(result)), 1)
        if not empty_config(result):
            return result
        last_empty = result
    return last_empty


def log_code_contract(prev, label):
    """Opt-in diagnostic metadata; never wraps or alters original code."""
    # optimized1: this diagnostic used to disassemble/log even while the global
    # automatic-diagnostics switch was False. Keep manual debug dumps elsewhere,
    # but do no bytecode rendering or file I/O in the normal runtime configuration.
    if not _V841PERF_AUTO_DIAGNOSTICS:
        return
    try:
        code = getattr(prev, '__code__', None)
        if code is None:
            return
        names = tuple(code.co_names)[:48]
        variables = tuple(code.co_varnames)[:32]
        strings = tuple(value[:100] for value in code.co_consts
                        if isinstance(value, str))[:32]
        _v841_log(('code-contract', label),
                  '%s code names=%r vars=%r strings=%r'
                  % (label, names, variables, strings), 1)
        # Log 10 proves record enrichment but not which original branch emits
        # only the normal feed.  Preserve behavior and capture the REAL game
        # bytecode once; no decompiler guesses or renderer-hook assumptions.
        try:
            import dis as _dis
            instructions = list(_dis.get_instructions(prev))
            rendered = '\n'.join(
                '%04d %-32s %s' % (ins.offset, ins.opname, ins.argrepr)
                for ins in instructions[:1600])
            if len(instructions) > 1600:
                rendered += '\n... truncated %d instructions ...' % (
                    len(instructions) - 1600)
            _v841_log(('code-bytecode', label),
                      '%s BYTECODE instructions=%d\n%s'
                      % (label, len(instructions), rendered), 1)
        except Exception as exc:
            _v841_log(('code-bytecode-error', label, repr(exc)),
                      '%s bytecode unavailable: %r' % (label, exc), 1)
    except Exception:
        pass


def kill_record_trace(info, skin_id, stage):
    """Bounded before/after evidence; never changes the record or config."""
    try:
        fields = ('item_id', 'weapon_id', 'guise_id', 'guise_item_id',
                  'hud_kill_ui', 'kill_effect', 'kill_fx', 'kill_mat',
                  'kill_tip_icon_replace', 'kill_avatar_effect',
                  'kill_hud_id', 'kill_hud_csb_path', 'kill_num_cam')
        values = {key: _mapping_get(info, key, None) for key in fields}
        _v841_log(('record-stage', stage, skin_id),
                  'record %s skin=%s identity=%s values=%r'
                  % (stage, skin_id, id(info), values), 1)
        if stage != 'after-seed':
            return
        feature_mod = sys.modules.get('gclient.data.item_feature_data')
        feature_data = getattr(feature_mod, 'data', None) if feature_mod else None
        # _v841_skin_ids returns integer IDs, not (namespace, id) pairs.
        # Keep every real namespace visible without aborting the dump.
        for namespace, row_id in enumerate(_v841_skin_ids(skin_id)):
            row = _data_get(feature_data, row_id, None)
            brief = {}
            for key, value in _data_items(row):
                lower = str(key).lower()
                if ('kill' in lower or lower in
                        ('id', 'dlc_id', 'dlc_pack_ids', 'guise')):
                    brief[str(key)] = value
            _v841_log(('record-feature-row', skin_id, namespace, row_id),
                      'record authentic item_feature skin=%s namespace=%s '
                      'id=%s values=%r'
                      % (skin_id, namespace, row_id, brief), 1)
    except Exception as exc:
        _v841_log(('record-stage-error', stage, skin_id, repr(exc)),
                  'record %s trace skipped skin=%s: %r'
                  % (stage, skin_id, exc), 1)


def config_factory(prev, label):
    log_code_contract(prev, label)
    def wrapper(*args, **kwargs):
        candidates = context_ids()
        if not candidates or not sync_attrs.get('bSkinHack', False):
            return prev(*args, **kwargs)
        return config_variants(prev, args, kwargs, candidates, label)
    wrapper._v841_wrap = True
    return wrapper


def _v841_install_module(mod, name, factory, original=None):
    guard = '_orig_v841_' + name
    try:
        if mod is None or guard in vars(mod):
            return False
        current = getattr(mod, name, None)
        prev = original if callable(original) else current
        if not callable(prev):
            return False
        wrapper = factory(prev)
        setattr(mod, guard, prev)
        setattr(mod, name, wrapper)
        return True
    except Exception:
        return False


def _v841_front_factory(prev, label):
    log_code_contract(prev, label)
    def wrapper(self, *args, **kwargs):
        if not sync_attrs.get('bSkinHack', False):
            return prev(self, *args, **kwargs)
        ids = current_skin_ids()
        if not ids:
            return prev(self, *args, **kwargs)
        # v2.112: prefetch the kill-anim companion bundles so
        # the first kill never stalls fetching them (debug-12:
        # the 7.45s first-kill freeze right after this memo).
        try:
            _dl2112 = globals().get('try_dlc_download')
            if callable(_dl2112):
                for _kid in list(ids)[:4]:
                    _dl2112(_kid, [])
        except Exception:
            pass
        old_ids = front_state.get('ids', ())
        front_state['ids'] = ids
        front_state['depth'] += 1
        _v841_log((label, 'call', tuple(ids)),
                  '%s selected ids=%r args=%r kwargs=%r'
                  % (label, ids, args[:5], list(kwargs.keys())), 2)
        try:
            return prev(self, *args, **kwargs)
        finally:
            front_state['depth'] -= 1
            front_state['ids'] = old_ids
    return wrapper


def dlc_probe_factory(prev):
    log_code_contract(prev, 'dlc-probe')
    def wrapper(*args, **kwargs):
        result = prev(*args, **kwargs)
        try:
            ids = context_ids()
            brief = []
            for value in args[:4]:
                if isinstance(value, dict):
                    brief.append({key: value.get(key) for key in
                                  ('id', 'item_id', 'guise_id', 'template_path',
                                   'is_dlc_ready') if key in value})
                elif isinstance(value, (int, str, bool)) or value is None:
                    brief.append(value)
                else:
                    brief.append(type(value).__name__)
            if ids or sync_attrs.get('bSkinHack', False):
                _v841_log(('dlc-result', repr(brief), repr(result)),
                          'kill HUD DLC probe ids=%r args=%r kwargs=%r -> %r'
                          % (ids, brief, list(kwargs.keys()), result), 2)
            if ids and not result:
                # The item's native downloader resolves its own real packs.
                # Keep the false answer; a later call may succeed after download.
                try_dlc_download(ids[0], [])
                _v841_log(('dlc-wait', tuple(ids)),
                          'kill HUD DLC not ready for ids=%r; real item '
                          'download queued, result preserved' % (ids,), 2)
        except Exception:
            pass
        return result
    wrapper._v841_wrap = True
    return wrapper


def seed_info_from_config(info, config):
    """Seed only real kill_hud_* values returned by the game config."""
    if info is None or empty_config(config):
        return 0
    copied = 0
    try:
        for key, value in _data_items(config):
            if (str(key).startswith('kill_hud_') and value is not None
                    and _mapping_set(info, key, value)):
                copied += 1
    except Exception:
        pass
    # Some game builds return (kill_hud_id, kill_hud_csb_path) instead of a
    # mapping.  Accept only the unambiguous int/string pair; never invent data.
    if not copied and isinstance(config, (tuple, list)) and len(config) >= 2:
        first, second = config[0], config[1]
        hid = first if isinstance(first, int) and not isinstance(first, bool) else None
        path = second if isinstance(second, str) and second else None
        if hid is None and isinstance(second, int) and not isinstance(second, bool):
            hid = second
            path = first if isinstance(first, str) and first else None
        if hid is not None:
            copied += int(_mapping_set(info, 'kill_hud_id', hid))
        if path:
            copied += int(_mapping_set(info, 'kill_hud_csb_path', path))
    return copied


def enrich_kill_config(info, skin_id):
    """Called by the existing record hook after its normal skin enrichment."""
    try:
        ids = _v841_skin_ids(skin_id)
        if not ids:
            return 0
        mod = sys.modules.get('gclient.gameplay.uicomponents.hud_killrecord_comp')
        prev = (getattr(mod, '_orig_v841_GetKillHudConfigForGameplay', None)
                or getattr(mod, '_orig_GetKillHudConfigForGameplay', None)
                or getattr(mod, 'GetKillHudConfigForGameplay', None)) if mod else None
        if not callable(prev):
            return 0
        config = config_variants(prev, (ids[0],), {}, ids,
                                       'record-seed')
        copied = seed_info_from_config(info, config)
        if copied:
            _v841_log(('record-seeded', tuple(ids), copied),
                      'kill record seeded with %d real HUD fields for ids=%r'
                      % (copied, ids), 2)
        return copied
    except Exception as exc:
        _v841_log(('record-seed-error', repr(exc)),
                  'record HUD config seed skipped: %r' % (exc,), 1)
        return 0


def install_kill_hud():
    stats = {'gameplay_config': 0, 'hall_config': 0,
             'front': 0, 'dlc_probe': 0}
    hkrc = sys.modules.get('gclient.gameplay.uicomponents.hud_killrecord_comp')
    if hkrc is not None:
        original = (getattr(hkrc, '_orig_GetKillHudConfigForGameplay', None)
                    or getattr(hkrc, 'GetKillHudConfigForGameplay', None))
        stats['gameplay_config'] += bool(_v841_install_module(
            hkrc, 'GetKillHudConfigForGameplay',
            lambda prev: config_factory(prev, 'gameplay-config'),
            original=original))
        # PushKillRecord is installed by the earlier established feed hook.
        # Log its ORIGINAL code here, after this late diagnostic helper exists.
        seen_push_code = set()
        for class_name in ('HudKillRecordComp', 'HudKillRecordCompPC',
                           'HudKillRecordCompV2'):
            cls = getattr(hkrc, class_name, None)
            original_push = getattr(
                cls, '_actual_skin_original_push_kill_record', None)
            code = getattr(original_push, '__code__', None)
            if callable(original_push) and id(code) not in seen_push_code:
                seen_push_code.add(id(code))
                log_code_contract(
                    original_push, 'push-record:' + class_name)

    hall = sys.modules.get('gclient.gamesystem.uihall.hall_ui_util')
    if hall is not None:
        stats['hall_config'] += bool(_v841_install_module(
            hall, 'GetKillHudConfig',
            lambda prev: config_factory(prev, 'hall-config')))
        stats['dlc_probe'] += bool(_v841_install_module(
            hall, '_is_kill_hud_dlc_ready', dlc_probe_factory))

    front_mod = sys.modules.get('gclient.gameplay.uicomponents.hud_frontsight_comp')
    front_cls = getattr(front_mod, 'HudFrontsightComp', None) if front_mod else None
    if front_cls is not None:
        for meth in ('OnShowKillHudAnim', 'PlayKillAnim'):
            stats['front'] += bool(_v839_wrap_method(
                front_cls, meth,
                lambda prev, meth=meth: _v841_front_factory(prev, meth)))
    if any(stats.values()):
        _v841_log('installed', 'kill HUD hooks %r' % (stats,), 1)
    return stats


# Reuse the established v8.39 retry watcher.  No new thread, game import, RPC,
# server call, blanket feature answer, or DLC-ready override is introduced.
try:
    install_kill_hud()
except Exception as _v841_boot_error:
    _v841_log('boot-error', 'initial kill HUD install failed: %r'
              % (_v841_boot_error,), 1)

# ============================================================
# v8.41-melee2: COMPLETE MELEE CATALOG / NATIVE EQUIP ACCESS
# APK and APP VERSIONS REMAIN v2.15 / v8.41 BY OWNER REQUEST.
# ============================================================
# v8.39's 2xxxxxxxxxx namespace test missed real melee items outside that
# range.  This layer derives scope from the actual melee catalog, covers
# GunSkinUtil module AND class/static surfaces, the base-equip lock, native
# warehouse lists and melee-guise lookup.  Pairicon6 removes the erroneous
# Spear/gun mapping: Spear is an assault rifle and must stay out of melee.
# No account-level override, gun/emote unlock, RPC/server answer or new thread.

_V841M2_MELEE_EQUIPS = frozenset((33, 84, 86, 89, 97, 107, 141))
_V841M2_MERGED_DAGGER_ROWS = frozenset((97, 107, 141))
_V841M2_BASE_ITEMS = {
    33: 2010000010,    # Dagger (also the merged Dual/Scythe/Artifact channel)
    84: 2020000010,    # Axe
    86: 2030000010,    # Katana
}
_v841m2_log_seen = {}
_v841m2_cache = {
    'at': 0.0, 'sig': None, 'items': set(), 'by_equip': {},
    'by_display': {}, 'by_melee': {},
    'item_to_template': {}, 'template_to_item': {},
}


def _v841m2_log(key, msg, limit=3):
    try:
        n = _v841m2_log_seen.get(key, 0)
        if n >= limit:
            return
        if len(_v841m2_log_seen) >= 180 and key not in _v841m2_log_seen:
            return
        _v841m2_log_seen[key] = n + 1
        _plog('[V841M2] %s' % (msg,))
    except Exception:
        pass


def _v841m2_int(value):
    if isinstance(value, bool):
        return 0
    try:
        if isinstance(value, int):
            return value if value > 0 else 0
        # _ZLVal and game scalar wrappers are int subclasses/callable.
        if callable(value):
            return _v841m2_int(value())
    except Exception:
        pass
    return 0


def _v841m2_catalog():
    """Build only real melee mappings; refresh as late item mappings arrive."""
    now = time.time()
    try:
        sig = (len(WEP), len(globals().get('WEP_MERGED_DISPLAY') or {}),
               len(SKIN_TO_ITEM), len(globals().get('WEP_MELEE_IDS') or {}),
               len(globals().get('WEP_GUN_IDS') or {}))
        if (_v841m2_cache['sig'] == sig
                and now - _v841m2_cache['at'] < 1.0):
            return _v841m2_cache
    except Exception:
        sig = None
    items = set()
    by_equip = {}
    by_display = {}
    by_melee = {}
    item_to_template = {}
    template_to_item = {}
    melee_ids = globals().get('WEP_MELEE_IDS') or {}
    gun_equips = globals().get('WEP_GUN_IDS') or {}
    skin_to_equip = globals().get('SKIN_TO_EQUIP') or {}
    try:
        rows = list(WEP.items())
        rows += list((globals().get('WEP_MERGED_DISPLAY') or {}).items())
    except Exception:
        rows = []
    for display_equip, row in rows:
        try:
            display_equip = _v841m2_int(display_equip)
            if (display_equip in gun_equips
                    or (display_equip not in _V841M2_MELEE_EQUIPS
                        and display_equip not in melee_ids)):
                continue
            for template_id in list(row[1:]):
                template_id = _v841m2_int(template_id)
                if not template_id:
                    continue
                info = WEP_SKIN_INFO.get(template_id) or {}
                item_id = (SKIN_TO_ITEM.get(template_id)
                           or info.get('lobby_item_id') or 0)
                item_id = _v841m2_int(item_id)
                if not item_id:
                    continue
                actual_equip = _v841m2_int(
                    skin_to_equip.get(template_id, display_equip))
                if actual_equip in gun_equips:
                    continue
                if (actual_equip not in _V841M2_MELEE_EQUIPS
                        and actual_equip not in melee_ids):
                    actual_equip = (33 if display_equip
                                    in _V841M2_MERGED_DAGGER_ROWS
                                    else display_equip)
                items.add(item_id)
                by_equip.setdefault(actual_equip, set()).add(item_id)
                by_display.setdefault(display_equip, set()).add(item_id)
                item_to_template[item_id] = template_id
                template_to_item[template_id] = item_id
        except Exception:
            continue
    for equip_id, item_id in _V841M2_BASE_ITEMS.items():
        items.add(item_id)
        by_equip.setdefault(equip_id, set()).add(item_id)
    for equip_id, melee_id in melee_ids.items():
        try:
            equip_id = _v841m2_int(equip_id)
            melee_id = _v841m2_int(melee_id)
            if equip_id in gun_equips:
                continue
            if melee_id and equip_id in by_equip:
                by_melee.setdefault(melee_id, set()).update(by_equip[equip_id])
        except Exception:
            continue
    _v841m2_cache.update({
        'at': now, 'sig': sig, 'items': items, 'by_equip': by_equip,
        'by_display': by_display, 'by_melee': by_melee,
        'item_to_template': item_to_template,
        'template_to_item': template_to_item,
    })
    return _v841m2_cache


def _v841m2_real_item(item_id):
    try:
        if melee_proto_cache.get(item_id) is True:
            return True
        proto, source = _zlu_lookup_proto(item_id)
        ok = proto is not None
        if ok and len(melee_proto_cache) < 512:
            melee_proto_cache[item_id] = True
        _v841m2_log(('real-row', item_id, ok),
                    'catalog melee item=%d real_proto=%s source=%s'
                    % (item_id, ok, source), 1)
        return ok
    except Exception:
        return False


def _v841m2_is_catalog_melee_item(item_id):
    """Positive catalog membership AND a real row; never a namespace guess."""
    try:
        if isinstance(item_id, bool) or not isinstance(item_id, int):
            return False
        if item_id not in _v841m2_catalog()['items']:
            return False
        return _v841m2_real_item(item_id)
    except Exception:
        return False


def _v841m2_fake(item_id):
    try:
        if not legacy_melee_active():
            return None
        if not _v841m2_is_catalog_melee_item(item_id):
            return None
        old = _zlu_fake_by_id.get(item_id)
        if old is not None:
            return old
        item = _ZLFakeItem(item_id)
        if isinstance(getattr(item, 'item_proto', None), _ZLNullProto):
            return None
        _zlu_fake_by_id[item_id] = item
        _zlu_fakes[item.guid] = item
        _v841m2_log(('fake', item_id),
                    'native melee item=%d guid=%s proto=%s %s'
                    % (item_id, item.guid,
                       getattr(item, '_zl_proto_src', 'none'),
                       _zl_fake_row_desc(item)), 1)
        return item
    except Exception as exc:
        _v841m2_log(('fake-error', item_id, repr(exc)),
                    'melee item=%d fake failed: %r' % (item_id, exc), 1)
        return None


def _v841m2_values(a, k):
    """Yield call scalars plus bounded item/equip fields from objects."""
    values = []
    try:
        raw = list(tuple(a) + tuple(k.values()))
        for value in raw:
            values.append(value)
            if isinstance(value, (str, bytes, int, bool, type(None))):
                continue
            for attr in ('item_id', 'skin_item_id', 'guise_item_id',
                         'skin_id', 'guise_id', 'guise_template_id',
                         'equip_id', 'melee_id', 'gun_id', 'id'):
                try:
                    values.append(getattr(value, attr))
                except Exception:
                    pass
    except Exception:
        pass
    return values


def _v841m2_has_owned_scope(a, k):
    try:
        cat = _v841m2_catalog()
        for value in _v841m2_values(a, k):
            item_id = _v841m2_int(value)
            if item_id and _v841m2_is_catalog_melee_item(item_id):
                return item_id
            # New-SDK call shapes may pass (equip_id, skin_template_id).
            mapped = cat['template_to_item'].get(item_id)
            if mapped and _v841m2_is_catalog_melee_item(mapped):
                return mapped
    except Exception:
        pass
    return 0


def _v841m2_item_id_of(value):
    item_id = _v841m2_int(value)
    if item_id:
        return item_id
    try:
        for attr in ('item_id', 'skin_item_id', 'guise_item_id', 'id'):
            item_id = _v841m2_int(getattr(value, attr))
            if item_id:
                return item_id
    except Exception:
        pass
    return 0


def _v841m2_result_shape(result):
    try:
        entries = list(result or ())
        ids = [_v841m2_item_id_of(x) for x in entries[:8]]
        first_type = type(entries[0]).__name__ if entries else 'empty'
        return '%s(len=%d,first=%s,ids=%r)' % (
            type(result).__name__, len(entries), first_type, ids)
    except Exception:
        return '%s(non-iterable)' % (type(result).__name__,)


def _v841m2_merge_items(result, item_ids, label):
    """Preserve container/entry shape; add only real melee item objects."""
    additions = []
    existing = set()
    try:
        entries = list(result or ())
        if entries and isinstance(entries[0], (
                int, str, bytes, tuple, list, dict)):
            # Do not mix raw item objects into IDs/(item, mall) record lists.
            _v841m2_log((label, 'entry-shape', _v841m2_result_shape(result)),
                        '%s unsupported entry shape preserved: %s'
                        % (label, _v841m2_result_shape(result)), 1)
            return result, 0
        for entry in entries:
            item_id = _v841m2_item_id_of(entry)
            if item_id:
                existing.add(item_id)
    except Exception:
        # Unknown result shapes remain untouched.
        return result, 0
    for item_id in sorted(set(item_ids)):
        if item_id in existing or len(additions) >= 128:
            continue
        item = _v841m2_fake(item_id)
        if item is not None:
            additions.append(item)
            existing.add(item_id)
    if not additions:
        return result, 0
    if isinstance(result, list):
        merged = result + additions
    elif isinstance(result, tuple):
        merged = tuple(result) + tuple(additions)
    elif result is None or result is False:
        merged = additions
    else:
        return result, 0
    _v841m2_log((label, 'merge', tuple(sorted(existing))),
                '%s merged %d real melee item(s); shape=%s'
                % (label, len(additions), _v841m2_result_shape(result)), 2)
    return merged, len(additions)


def _v841m2_owned_factory(prev):
    def wrapper(*a, **k):
        scoped = _v841m2_has_owned_scope(a, k) if legacy_melee_active() else 0
        # v2.114: the cosmetic band unlocks through the fine gates.
        if not scoped:
            for _v in _v841m2_values(a, k):
                _c = _v841m2_int(_v)
                if (_c and 6000000000 <= _c < 6700000000
                        and should_unlock(_c)):
                    scoped = _c
                    break
        try:
            result = prev(*a, **k)
        except Exception:
            if not scoped:
                raise
            result = None
        if scoped and not result:
            _v841m2_log(('owned', scoped),
                        'CheckGunSkinOwned item=%d original=%r -> melee owned'
                        % (scoped, result), 1)
            return True
        return result
    return wrapper


def _v841m2_equip_lock_factory(prev):
    def wrapper(*a, **k):
        equip_id = 0
        if legacy_melee_active():
            for value in _v841m2_values(a, k):
                candidate = _v841m2_int(value)
                if candidate in _V841M2_MELEE_EQUIPS:
                    equip_id = candidate
                    break
                # v2.114: the cosmetic band unlocks too.
                if (candidate and 6000000000 <= candidate < 6700000000
                        and should_unlock(candidate)):
                    equip_id = candidate
                    break
        try:
            result = prev(*a, **k)
        except Exception:
            if not equip_id:
                raise
            result = True
        if equip_id and result:
            _v841m2_log(('equip-lock', equip_id, repr(result)),
                        'IsEquipIdLock* melee equip=%d original=%r -> False'
                        % (equip_id, result), 1)
            return False
        return result
    return wrapper


def _v841m2_items_for_melee(melee_id):
    melee_id = _v841m2_int(melee_id)
    if not melee_id:
        return set()
    cat = _v841m2_catalog()
    if melee_id in _V841M2_MERGED_DAGGER_ROWS:
        # A native window addressing the display row gets only that row's
        # skins, while the actual equip channel remains Dagger (33).
        return set(cat['by_display'].get(melee_id) or set())
    return set(cat['by_melee'].get(melee_id) or
               cat['by_equip'].get(melee_id) or set())


def _v841m2_all_list_factory(prev):
    def wrapper(*a, **k):
        if _v841m2_native_melee_active():
            return prev(*a, **k)
        melee_id = 0
        for value in _v841m2_values(a, k):
            candidate = _v841m2_int(value)
            if candidate and _v841m2_items_for_melee(candidate):
                melee_id = candidate
                break
        try:
            _v841m3_relax_melee_lobby()
        except Exception:
            pass
        try:
            result = prev(*a, **k)
        except Exception:
            if not melee_id or not legacy_melee_active():
                raise
            result = None
        _v841m2_log(('all-list-call', melee_id,
                     _v841m2_result_shape(result)),
                    'GetAllMeleeSkinItemList context=%d active=%s result=%s'
                    % (melee_id, legacy_melee_active(),
                       _v841m2_result_shape(result)), 1)
        if not melee_id or not legacy_melee_active():
            return result
        merged, added = _v841m2_merge_items(
            result, _v841m2_items_for_melee(melee_id),
            'GetAllMeleeSkinItemList(%d)' % melee_id)
        if added:
            return merged
        return result
    return wrapper


def _v841m2_context_from_result(result):
    try:
        for entry in list(result or ())[:8]:
            for value in _v841m2_values((entry,), {}):
                candidate = _v841m2_int(value)
                if candidate and _v841m2_items_for_melee(candidate):
                    return candidate
    except Exception:
        pass
    return 0


def _v841m2_member_list_factory(prev):
    """Merge only when self/args/result identify the actual melee context."""
    def wrapper(*a, **k):
        # Native melee owns these calls.  Avoid the old catalog scan, lobby
        # relaxation, merge, and per-call logging while that path is enabled.
        if _v841m2_native_melee_active():
            return prev(*a, **k)
        context = 0
        for value in _v841m2_values(a, k):
            candidate = _v841m2_int(value)
            if candidate and _v841m2_items_for_melee(candidate):
                context = candidate
                break
        try:
            _v841m3_relax_melee_lobby()
        except Exception:
            pass
        try:
            result = prev(*a, **k)
        except Exception:
            if not context or not legacy_melee_active():
                raise
            result = None
        if not context:
            context = _v841m2_context_from_result(result)
        _v841m2_log(('member-list-call', context,
                     _v841m2_result_shape(result)),
                    'GetMeleeSkinItemList context=%d active=%s result=%s'
                    % (context, legacy_melee_active(),
                       _v841m2_result_shape(result)), 1)
        if not context or not legacy_melee_active():
            return result
        merged, added = _v841m2_merge_items(
            result, _v841m2_items_for_melee(context),
            'GetMeleeSkinItemList(%d)' % context)
        return merged if added else result
    return wrapper


def _v841m2_guise_factory(prev):
    def wrapper(*a, **k):
        item_id = 0
        if legacy_melee_active():
            cat = _v841m2_catalog()
            for value in _v841m2_values(a, k):
                template_id = _v841m2_int(value)
                mapped = cat['template_to_item'].get(template_id)
                if mapped and _v841m2_is_catalog_melee_item(mapped):
                    item_id = mapped
                    break
        try:
            result = prev(*a, **k)
        except Exception:
            if not item_id:
                raise
            result = None
        if item_id and not result:
            item = _v841m2_fake(item_id)
            if item is not None:
                return item
        return result
    return wrapper


def _v841m2_probe_factory(prev, label):
    """Evidence only for the real click/apply/setter path; never fake success."""
    def wrapper(*a, **k):
        if _v841m2_native_melee_active():
            return prev(*a, **k)
        ids = []
        for value in _v841m2_values(a, k):
            candidate = _v841m2_int(value)
            if candidate and candidate not in ids:
                ids.append(candidate)
        try:
            result = prev(*a, **k)
        except Exception as exc:
            _v841m2_log((label, 'error', tuple(ids), repr(exc)),
                        '%s ids=%r raised=%r' % (label, ids[:12], exc), 2)
            raise
        _v841m2_log((label, 'call', tuple(ids), repr(result)),
                    '%s ids=%r original_result=%r'
                    % (label, ids[:12], result), 2)
        return result
    return wrapper


def _v841m2_install_module(mod, name, factory):
    guard = '_orig_v841m2_' + name
    try:
        if mod is None or guard in vars(mod):
            return False
        prev = getattr(mod, name, None)
        if not callable(prev):
            return False
        wrapper = factory(prev)
        setattr(mod, guard, prev)
        try:
            setattr(mod, name, wrapper)
        except Exception:
            try:
                delattr(mod, guard)
            except Exception:
                pass
            return False
        return True
    except Exception:
        return False


def _v841m2_gun_skin_targets(mod):
    """Cover module functions and Singleton/class/static SDK variants."""
    targets = [mod] if mod is not None else []
    try:
        candidate = getattr(mod, 'GunSkinUtil', None) if mod is not None else None
        if isinstance(candidate, type):
            targets.append(candidate)
        elif candidate is not None:
            # Singleton instances may themselves be callable.
            targets.append(type(candidate))
        instance = getattr(candidate, '_instance', None)
        if instance is not None:
            targets.append(type(instance))
    except Exception:
        pass
    unique = []
    seen = set()
    for target in targets:
        if target is None or id(target) in seen:
            continue
        seen.add(id(target))
        unique.append(target)
    return unique


# v8.41-meleskin: scoped use of the owner-supplied meleskin.cpp surfaces.
# The raw snippet is NOT executed: it duplicates the established catalog/apply
# paths, references globals absent from this payload, adds a retry thread and
# repeatedly scans the full lobby table.  These adapters use the current
# bSkinHack gate, real melee2 catalog and existing sys.modules-only watcher.

def _v841m3_goto_lock_factory(prev):
    """Only locked-list classification changes; real navigation is untouched."""
    def wrapper(guise_item_id, check_only=False, *a, **k):
        scoped_item = 0
        if check_only and legacy_melee_active():
            try:
                item_id = _v841m2_int(guise_item_id)
                mapped = _v841m2_catalog()['template_to_item'].get(
                    item_id, item_id)
                if mapped and _v841m2_is_catalog_melee_item(mapped):
                    scoped_item = mapped
            except Exception:
                scoped_item = 0
        if scoped_item:
            _v841m2_log(('goto-lock-guise', scoped_item),
                        'GotoLockGunGuise check_only melee item=%d -> False'
                        % scoped_item, 1)
            return False
        return prev(guise_item_id, check_only, *a, **k)
    return wrapper


def _v841m3_random_item_factory(prev):
    """Positional/keyword-safe is_guise adaptation for melee random items."""
    def wrapper(self, *a, **k):
        if legacy_melee_active():
            args = list(a)
            if len(args) >= 2:
                # The supplied snippet always used kwargs and could raise
                # "multiple values for is_guise" on this common call shape.
                args[1] = True
            else:
                k['is_guise'] = True
            a = tuple(args)
            _v841m2_log('random-item-guise',
                        'MeleeSkinRandomItem is_guise scoped True', 1)
        return prev(self, *a, **k)
    return wrapper


# item -> {row, originals:{field:(original, forced)}}.  Row references allow
# OFF restoration even if the game's data module is later unloaded.
_v841m3_lobby_state = {'active': False, 'rows': {}}


def _v841m3_relax_melee_lobby():
    """Apply the snippet's two visibility fields to real melee rows only.

    This uses the already-built melee2 cache and direct key lookups.  It never
    imports a module, iterates the 65k lobby table, starts a thread or runs a
    retry loop.  Repeated ON passes process only previously unseen rows.
    """
    state = _v841m3_lobby_state
    tracked = state['rows']

    def set_field(row, key, value):
        try:
            row[key] = value
            return True
        except Exception:
            return False

    if not legacy_melee_active():
        if not state.get('active'):
            return
        restored = 0
        for record in list(tracked.values()):
            row = record['row']
            for key, (original, forced) in record['originals'].items():
                try:
                    # Do not overwrite a newer game/UI value while restoring.
                    if _proto_get(row, key, None) == forced:
                        restored += bool(set_field(row, key, original))
                except Exception:
                    pass
        state['active'] = False
        if restored:
            _v841m2_log('visibility-restored',
                        'melee lobby visibility restored fields=%d' % restored, 1)
        return

    if not state.get('active'):
        # Re-apply after an OFF -> ON transition without rebuilding the catalog.
        for record in list(tracked.values()):
            for key, (_original, forced) in record['originals'].items():
                set_field(record['row'], key, forced)
        state['active'] = True

    new_ids = [item_id for item_id in (_v841m2_cache.get('items') or ())
               if item_id not in tracked]
    if not new_ids:
        return
    data_sources = []
    for modname in ('gclient.data.lobby_item_data',
                    'gclient.data.lobby_gun_skin_item_data'):
        module = sys.modules.get(modname)
        data = getattr(module, 'data', None) if module is not None else None
        if data is not None:
            data_sources.append(data)
    if not data_sources:
        return

    changed = 0
    for item_id in sorted(new_ids)[:1024]:
        row = None
        for data in data_sources:
            row = _data_get(data, item_id, None)
            if row is not None:
                break
        if row is None:
            continue
        record = {'row': row, 'originals': {}}
        # Record first so OFF can restore even if a later field is malformed.
        tracked[item_id] = record
        for key, forced in (('visible_limit', 0),
                            ('enable_data_visible', True)):
            try:
                original = _proto_get(row, key, None)
                needed = (key == 'visible_limit' and bool(original)) or (
                    key == 'enable_data_visible' and original is False)
                if not needed:
                    continue
                record['originals'][key] = (original, forced)
                if set_field(row, key, forced):
                    changed += 1
                else:
                    del record['originals'][key]
            except Exception:
                record['originals'].pop(key, None)
    if changed:
        _v841m2_log('visibility-relaxed',
                    'catalog melee lobby visibility fields=%d' % changed, 1)


# v8.41-guncatalog4: show every real entry admitted by the ORIGINAL
# GetAllGunSkinItemList builder. Never return True from the list function
# itself: its callers require a list. Only CheckGunSkinCanShow is scoped True,
# on this thread, while that original builder runs and the skin hack is ON.
_v841g4_state = threading.local()


def _v841g4_list_depth():
    try:
        return int(getattr(_v841g4_state, 'depth', 0))
    except Exception:
        return 0


def _v841g4_can_show_factory(prev):
    def wrapper(*a, **k):
        if _v841g4_list_depth() > 0 and melee_active():
            _v841m2_log('gun-list-can-show',
                        'GetAllGunSkinItemList scope: CheckGunSkinCanShow -> True', 1)
            return True
        return prev(*a, **k)
    return wrapper


def _v841g4_all_gun_list_factory(prev):
    def wrapper(*a, **k):
        old_depth = _v841g4_list_depth()
        _v841g4_state.depth = old_depth + 1
        try:
            # Arguments (including include_locked/include_mall/need_random),
            # original exceptions, and the original return object are preserved.
            result = prev(*a, **k)
        finally:
            _v841g4_state.depth = old_depth
        if melee_active():
            gun_id = _v841m2_int(a[0]) if a else _v841m2_int(k.get('gun_id'))
            log_key = ('gun-list-result', gun_id)
            if _v841m2_log_seen.get(log_key, 0) < 1:
                _v841m2_log(log_key,
                            'GetAllGunSkinItemList gun=%d original result=%s; visibility scoped'
                            % (gun_id, _v841m2_result_shape(result)), 1)
        return result
    return wrapper


def _v841g4_install():
    # sys.modules only: no game import or new thread is introduced here.
    stats = {'gun_list': 0, 'gun_can_show': 0}
    gun_mod = sys.modules.get('gclient.util.gun_skin_util')
    release_mod = sys.modules.get('gshare.gun_skin_release_util')
    for target in (release_mod, gun_mod):
        stats['gun_can_show'] += bool(_v841m2_install_module(
            target, 'CheckGunSkinCanShow', _v841g4_can_show_factory))
    for target in _v841m2_gun_skin_targets(gun_mod):
        if isinstance(target, type):
            stats['gun_list'] += bool(_v839_wrap_method(
                target, 'GetAllGunSkinItemList', _v841g4_all_gun_list_factory))
        else:
            stats['gun_list'] += bool(_v841m2_install_module(
                target, 'GetAllGunSkinItemList', _v841g4_all_gun_list_factory))
    if any(stats.values()):
        _v841m2_log('gun-list-installed',
                    'scoped native gun-list visibility hooks %r' % (stats,), 1)
    return stats


def _v841m2_install():
    stats = {'owned': 0, 'all_list': 0, 'equip_lock': 0, 'trial_lock': 0,
             'guise': 0, 'member_list': 0, 'probe': 0,
             'guise_lock': 0, 'random_item': 0}
    gun_mod = sys.modules.get('gclient.util.gun_skin_util')
    for target in _v841m2_gun_skin_targets(gun_mod):
        is_class = isinstance(target, type)
        for name, factory, key in (
                ('CheckGunSkinOwned', _v841m2_owned_factory, 'owned'),
                ('GetAllMeleeSkinItemList', _v841m2_all_list_factory,
                 'all_list')):
            if is_class:
                stats[key] += bool(_v839_wrap_method(target, name, factory))
            else:
                stats[key] += bool(_v841m2_install_module(
                    target, name, factory))

    weapon_util = sys.modules.get('gshare.weapon_util')
    stats['equip_lock'] += bool(_v841m2_install_module(
        weapon_util, 'IsEquipIdLock', _v841m2_equip_lock_factory))
    stats['trial_lock'] += bool(_v841m2_install_module(
        weapon_util, 'IsEquipIdLockByTrial', _v841m2_equip_lock_factory))

    task_mod = sys.modules.get('gclient.framework.util.task_gofunc_util')
    stats['guise_lock'] += bool(_v841m2_install_module(
        task_mod, 'GotoLockGunGuise', _v841m3_goto_lock_factory))
    random_cls = getattr(gun_mod, 'MeleeSkinRandomItem', None) if gun_mod else None
    if random_cls is not None:
        stats['random_item'] += bool(_v839_wrap_method(
            random_cls, '__init__', _v841m3_random_item_factory))

    hall_mod = sys.modules.get(
        'gclient.gamesystem.entities.avatarmembers.cimp_hall_item')
    hall_cls = getattr(hall_mod, 'IHallItems', None) if hall_mod else None
    if hall_cls is not None:
        stats['guise'] += bool(_v839_wrap_method(
            hall_cls, 'GetItemByMeleeGuiseId', _v841m2_guise_factory))

    member_surfaces = (
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
    for modname, class_names in member_surfaces:
        mod = sys.modules.get(modname)
        for class_name in class_names:
            cls = getattr(mod, class_name, None) if mod else None
            if cls is None:
                continue
            stats['member_list'] += bool(_v839_wrap_method(
                cls, 'GetMeleeSkinItemList', _v841m2_member_list_factory))
            stats['probe'] += bool(_v839_wrap_method(
                cls, 'OnClickEquip',
                lambda prev: _v841m2_probe_factory(
                    prev, class_name + '.OnClickEquip')))

    for modname, class_name in (
            ('gclient.framework.entities.avatar', 'PlayerAvatar'),
            ('gclient.gamesystem.entities.avatarmembers.cimp_backpack',
             'PlayerAvatarMember')):
        mod = sys.modules.get(modname)
        cls = getattr(mod, class_name, None) if mod else None
        if cls is None:
            continue
        stats['probe'] += bool(_v839_wrap_method(
            cls, 'ApplyMelee',
            lambda prev: _v841m2_probe_factory(prev, 'ApplyMelee')))
        if class_name == 'PlayerAvatar':
            stats['probe'] += bool(_v839_wrap_method(
                cls, '_on_set_arm_melee',
                lambda prev: _v841m2_probe_factory(
                    prev, '_on_set_arm_melee')))
    try:
        _v841m3_relax_melee_lobby()
    except Exception:
        pass
    stats.update(_v841g4_install())
    # The legacy watcher is independently proven to see late-loaded melee UI
    # modules.  Arm the native observers from that same pass instead of
    # relying only on the separate five-second retry and its install-seen set.
    if _v841m2_native_melee_active():
        try:
            native_install = globals().get('install_melee_observers')
            if callable(native_install):
                stats['native_melee'] = int(native_install())
        except Exception:
            stats['native_melee'] = 0
    if any(stats.values()):
        _v841m2_log('installed', 'native skin list/equip hooks %r' % (stats,), 1)
    return stats


# Reuse the established retry watcher.  The initial call is best-effort;
# later calls install only modules the game has already loaded.
try:
    _v841m2_install()
except Exception as _v841m2_boot_error:
    _v841m2_log('boot-error', 'initial melee install failed: %r'
                % (_v841m2_boot_error,), 1)

# ============================================================
# v8.42-gunfx: automatic gun tracer + kill broadcast activation
# ============================================================
# Scope is deliberate: the weapon-skin master switch, selected GUN rows, real
# template data, and the game's own loaded GunUpgradeFeature constants.  No
# numeric feature-ID guess, blanket feature answer, RPC, or server call.

_v842g_log_seen = {}
selected_cache = {'at': 0.0, 'records': ()}
feature_cache = {'sig': None, 'features': {}}


def _v842g_log(key, message, limit=3):
    try:
        count = _v842g_log_seen.get(key, 0)
        if count >= limit:
            return
        if len(_v842g_log_seen) >= 120 and key not in _v842g_log_seen:
            return
        _v842g_log_seen[key] = count + 1
        _plog('[V842GFX] %s' % message)
    except Exception:
        pass


def fx_forced():
    """Tracer/broadcast hooks ride the weapon-skin master, not legacy bForceFX."""
    try:
        return bool(sync_attrs.get('bSkinHack', False))
    except Exception:
        return False


_fx_forced = fx_forced


def selected_gun_records(force=False):
    """Selected gun picks as (equip, template, item, info), never melee rows."""
    now = time.time()
    if not force and now - selected_cache['at'] < 0.50:
        return selected_cache['records']
    records = []
    try:
        gun_ids = globals().get('WEP_GUN_IDS') or {}
        melee_ids = globals().get('WEP_MELEE_IDS') or {}
        for equip_id, row in list(WEP.items()):
            try:
                equip_id = _safe_int(equip_id, 0)
                if (not equip_id or equip_id in melee_ids
                        or (gun_ids and equip_id not in gun_ids)):
                    continue
                # With no gun classification yet, stay conservative rather
                # than accidentally treating an unknown melee row as a gun.
                if not gun_ids:
                    continue
                skins = list(row[1:])
                idx = _safe_int(sync_attrs.get('iSkin_%s' % equip_id, 0), 0)
                if not (0 < idx <= len(skins)):
                    continue
                template_id = skins[idx - 1]
                info = WEP_SKIN_INFO.get(template_id) or {}
                item_id = _v842r_item_id(template_id)
                item_id = _safe_int(item_id, 0)
                template_id = _safe_int(template_id, 0)
                if template_id and item_id:
                    records.append((equip_id, template_id, item_id, info))
            except Exception:
                continue
    except Exception:
        pass
    selected_cache.update({'at': now, 'records': tuple(records)})
    return tuple(records)


def enum_owners():
    owners = []
    for module_name in (
            'gclient.util.gun_upgrade_util', 'gclient.cconst',
            'gclient.lang.cconst', 'gclient.lang'):
        module = sys.modules.get(module_name)
        if module is None:
            continue
        candidates = [getattr(module, 'GunUpgradeFeature', None)]
        if module_name in ('gclient.cconst', 'gclient.lang.cconst'):
            candidates.append(module)
        candidates.append(getattr(module, 'cconst', None))
        for owner in candidates:
            if owner is not None and isinstance(owner, type):
                if not any(owner is old for old in owners):
                    owners.append(owner)
            elif owner is not None and hasattr(owner, '__dict__'):
                if not any(owner is old for old in owners):
                    owners.append(owner)
    return owners


def _v842g_feature_number(value):
    try:
        if isinstance(value, bool):
            return 0
        number = _safe_int(value, 0)
        if not number and hasattr(value, 'value'):
            number = _safe_int(getattr(value, 'value', 0), 0)
        return number
    except Exception:
        return 0


def _v842g_feature_kinds(name):
    name = str(name).upper()
    if not name.startswith('UPGRADE_FEATURE_'):
        return ()
    kinds = []
    # KULL is the game's historical spelling in the runtime evidence.
    if (('KILL' in name or 'KULL' in name)
            and any(token in name for token in
                    ('UI', 'BROADCAST', 'FEED', 'RECORD'))
            and 'COUNTER' not in name):
        kinds.append('broadcast')
    if any(token in name for token in
           ('TRACER', 'BULLET_TRACE', 'BULLET_RACER', 'RACER')):
        kinds.append('tracer')
    return tuple(kinds)


def feature_map():
    owners = enum_owners()
    if not owners:
        # Do not cache an early-boot empty answer; the enum may load later.
        return {}
    signature = tuple(id(owner) for owner in owners)
    if feature_cache['sig'] == signature:
        return feature_cache['features']
    features = {}
    for owner in owners:
        try:
            names = dir(owner)
        except Exception:
            continue
        for name in names:
            kinds = _v842g_feature_kinds(name)
            if not kinds:
                continue
            try:
                number = _v842g_feature_number(getattr(owner, name, None))
            except Exception:
                continue
            if number:
                features.setdefault(number, set()).update(kinds)
    feature_cache.update({'sig': signature, 'features': features})
    if features:
        _v842g_log(('features', signature),
                   'loaded game feature IDs=%r'
                   % ({key: sorted(value) for key, value in features.items()},), 1)
    return features


_V842G_TRACER_FIELDS = (
    'fps_tracer_bullet_id', 'fps_adstracer_bullet_id',
    'fps_simple_tracer_bullet_id', 'fps_simple_adstracer_bullet_id',
    'tps_tracer_bullet_id', 'tps_simple_tracer_bullet_id',
    'extra_ballistic_tracer_bullet_id',
)
_V842G_BROADCAST_FIELDS = (
    'kill_tip_icon_replace', 'kill_tip_icon_2_replace',
    'kill_avatar_effect', 'kill_mat', 'Team_kill_mat', 'team_kill_mat',
    'kill_fx', 'kill_fx_id', 'kill_effect_id', 'hud_kill_ui',
    'kill_hud_id', 'kill_hud_csb_path',
)


def info_value(info, field):
    try:
        value = info.get(field, None)
        if value is None:
            value = _skin_raw_field(info, field)
        if value in (None, False, 0, '', (), [], {}):
            return None
        return value
    except Exception:
        return None


def _v842g_record_supports(record, kind):
    fields = (_V842G_TRACER_FIELDS if kind == 'tracer'
              else _V842G_BROADCAST_FIELDS)
    info = record[3]
    return any(info_value(info, field) is not None
               for field in fields)


def matching_records(manager, item_id):
    item_id = _v842g_feature_number(item_id)
    if not item_id:
        return ()
    records = selected_gun_records()
    direct = tuple(record for record in records
                   if item_id in (record[1], record[2]))
    if direct or manager is None:
        return direct
    try:
        query_base = _v839_base_item(manager, item_id)
    except Exception:
        query_base = None
    if not query_base:
        return ()
    matched = []
    for record in records:
        try:
            if query_base == _v839_base_item(manager, record[2]):
                matched.append(record)
        except Exception:
            continue
    return tuple(matched)


def activate_feature(manager, item_id, feature):
    """True only for a selected gun's real data and matching game enum."""
    if not sync_attrs.get('bSkinHack', False):
        return False
    number = _v842g_feature_number(feature)
    kinds = feature_map().get(number) or ()
    if not kinds:
        return False
    for record in matching_records(manager, item_id):
        for kind in kinds:
            if _v842g_record_supports(record, kind):
                _v842g_log(('activate', record[2], number, kind),
                           'activate %s item=%d template=%d feature=%d'
                           % (kind, record[2], record[1], number), 2)
                return True
    return False


def _v842g_feature_factory(previous):
    def wrapper(*args, **kwargs):
        # Preserve the real configured answer and all original exceptions.
        result = previous(*args, **kwargs)
        if result:
            return result
        try:
            manager = None
            offset = 0
            if args and callable(getattr(args[0], 'ItemId2BaseLevelItem', None)):
                manager = args[0]
                offset = 1
            item_id = kwargs.get('item_id')
            feature = kwargs.get('feature')
            if len(args) > offset:
                item_id = args[offset]
            if len(args) > offset + 1:
                feature = args[offset + 1]
            if activate_feature(manager, item_id, feature):
                return True
        except Exception as exc:
            _v842g_log(('feature-error', repr(exc)),
                       'scoped feature check skipped: %r' % (exc,), 1)
        return result
    wrapper._v842g_wrap = True
    return wrapper


def _v842g_wrap_method(cls, method, factory):
    guard = '_orig_v842g_' + method
    try:
        if cls is None or guard in vars(cls):
            return False
        static = inspect.getattr_static(cls, method)
        previous = (static.__func__ if isinstance(
            static, (staticmethod, classmethod)) else static)
        if not callable(previous):
            return False
        wrapper = factory(previous)
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


def refresh_effect_references():
    """Patch late `from effect_util import ...` callers, not just boot callers."""
    if not fx_forced():
        return 0
    if not _weaponfx_effect_hooks_installed[0]:
        return 0
    effect_util = sys.modules.get('gshare.effect_util')
    if effect_util is None:
        return 0
    patched = 0
    for name in ('PlayBallisticEffect', 'WrapperHitEffectResult',
                 'PlayHitEffect', 'ConfigBallisticEffect'):
        wrapper = getattr(effect_util, name, None)
        original = getattr(effect_util, '_treacky_orig_' + name, None)
        if (not callable(wrapper) or not callable(original)
                or not getattr(wrapper, '_treacky_weaponfx', False)):
            continue
        for module_name, module in list(sys.modules.items()):
            if module is None or module is effect_util:
                continue
            lower = str(module_name).lower()
            if not any(token in lower for token in
                       ('combat', 'effect', 'spell', 'weapon')):
                continue
            try:
                if getattr(module, name, None) is original:
                    setattr(module, name, wrapper)
                    patched += 1
            except Exception:
                continue
    if patched:
        _v842g_log(('late-effect', patched),
                   'late effect caller references patched=%d' % patched, 2)
    return patched


def _v842g_refresh_kill_feed():
    installer = globals().get('_install_kill_feed')
    if not callable(installer):
        return 0
    module = sys.modules.get(
        'gclient.gameplay.uicomponents.hud_killrecord_comp')
    if module is None:
        return 0
    installed = 0
    for name in ('HudKillRecordComp', 'HudKillRecordCompPC',
                 'HudKillRecordCompV2'):
        cls = getattr(module, name, None)
        if cls is None:
            continue
        try:
            existed = hasattr(cls, '_actual_skin_original_push_kill_record')
            installer(cls)
            installed += int(not existed and hasattr(
                cls, '_actual_skin_original_push_kill_record'))
        except Exception:
            continue
    return installed


def _v842g_install():
    stats = {'features': 0, 'kill_feed': 0, 'effect_refs': 0}
    try:
        module = sys.modules.get('gclient.util.gun_upgrade_util')
        cls = getattr(module, 'GunUpgradeDataMgr', None) if module else None
        for method in ('HasFeatureByItemId', 'CanShowFeature'):
            stats['features'] += int(_v842g_wrap_method(
                cls, method, _v842g_feature_factory))
    except Exception:
        pass
    try:
        stats['kill_feed'] = _v842g_refresh_kill_feed()
    except Exception:
        pass
    try:
        stats['effect_refs'] = refresh_effect_references()
    except Exception:
        pass
    if any(stats.values()):
        _v842g_log('installed', 'gun FX hooks %r' % (stats,), 2)
    return stats


try:
    _v842g_install()
except Exception as _v842g_boot_error:
    _v842g_log('boot-error', 'initial gun FX install failed: %r'
               % (_v842g_boot_error,), 1)

# ============================================================
# v2.18-fxfix: device-log guided tracer + kill-HUD repair
# ============================================================
# Evidence: selected upgrade skins had no lobby-item mapping, and the racer
# shield absorbed missing WeaponCase state without completing the refresh.
# Use only real game mappings and cases already marked by the local skin hack.

_v842r_log_seen = {}
mapping_seen = set()
lookup_retry = {}


def _v842r_log(key, message, limit=3):
    try:
        count = _v842r_log_seen.get(key, 0)
        if count >= limit:
            return
        if len(_v842r_log_seen) >= 100 and key not in _v842r_log_seen:
            return
        _v842r_log_seen[key] = count + 1
        _plog('[V218FX] %s' % message)
    except Exception:
        pass


def _v842r_item_id(skin_id):
    """Resolve a template's REAL lobby/base item; never fabricate an ID."""
    try:
        skin_id = _safe_int(skin_id, 0)
        if not skin_id:
            return 0
        info = WEP_SKIN_INFO.get(skin_id) or {}
        item_id = _safe_int(SKIN_TO_ITEM.get(skin_id)
                            or info.get('lobby_item_id'), 0)
        if item_id and item_id != skin_id:
            return item_id
        now = time.time()
        if now - lookup_retry.get(skin_id, 0.0) >= 1.0:
            lookup_retry[skin_id] = now
            refresh_mappings()
        info = WEP_SKIN_INFO.get(skin_id) or {}
        return _safe_int(SKIN_TO_ITEM.get(skin_id)
                         or info.get('lobby_item_id'), 0) or item_id or skin_id
    except Exception:
        return skin_id


def refresh_mappings():
    """Read the game's upgrade mapping table, including late-loaded skins."""
    changed = 0
    try:
        module = sys.modules.get(
            'gclient.data.lobby_item_upgrade_extra_data')
        table = getattr(module, 'GUISE_ID_TO_ITEM_ID', None) if module else None
        for guise_id, item_id in list(_data_items(table)):
            skin_id = _safe_int(guise_id, 0)
            item_id = _safe_int(item_id, 0)
            if (not skin_id or not item_id
                    or skin_id not in WEP_SKIN_INFO):
                continue
            info = WEP_SKIN_INFO.get(skin_id) or {}
            old_item = _safe_int(SKIN_TO_ITEM.get(skin_id)
                                 or info.get('lobby_item_id'), 0)
            pair = (skin_id, item_id)
            if old_item == item_id and pair in mapping_seen:
                continue
            mapping_seen.add(pair)
            if old_item == item_id:
                continue
            SKIN_TO_ITEM[skin_id] = item_id
            # Several upgrade templates may share one base item.  Never let a
            # later row silently redirect an existing reverse mapping.
            if item_id not in ITEM_TO_SKIN:
                ITEM_TO_SKIN[item_id] = skin_id
            info['lobby_item_id'] = item_id
            WEP_SKIN_INFO[skin_id] = info
            changed += 1
            _v842r_log(('map', pair),
                       'real upgrade mapping template=%d -> item=%d'
                       % (skin_id, item_id), 2)
        if changed:
            try:
                selected_cache['at'] = 0.0
                sel_cache['at'] = 0.0
                base_cache.clear()
            except Exception:
                pass
    except Exception as exc:
        _v842r_log(('map-error', repr(exc)),
                   'upgrade mapping scan skipped: %r' % (exc,), 1)
    return changed


def marked_case(value):
    """Only a case explicitly marked by our local apply path qualifies."""
    try:
        if getattr(value, '_treacky_skin_template_id', None):
            return value
    except Exception:
        pass
    for attr in ('weapon_case', 'case'):
        try:
            candidate = getattr(value, attr, None)
            if (candidate is not None
                    and getattr(candidate, '_treacky_skin_template_id', None)):
                return candidate
        except Exception:
            continue
    return None


def prepare_case(value):
    """Complete known half-born case state BEFORE the native racer refresh."""
    if not sync_attrs.get('bSkinHack', False):
        return 0
    case = marked_case(value)
    if case is None:
        return 0
    filled = []
    try:
        if not hasattr(case, 'play_other_effect_tick'):
            case.play_other_effect_tick = lambda *args, **kwargs: (None, None)
            filled.append('play_other_effect_tick')
    except Exception:
        pass
    try:
        if not hasattr(case, 'is_show_simple_part_model'):
            case.is_show_simple_part_model = False
            filled.append('is_show_simple_part_model')
    except Exception:
        pass
    try:
        synthetic = bool(getattr(
            case, '_treacky_case_state_default', False))
        if synthetic or not hasattr(case, 'is_in_combat'):
            try:
                in_match = bool(_hero_in_match())
            except Exception:
                in_match = False
            case.is_in_combat = in_match
            case._treacky_case_state_default = False
            filled.append('is_in_combat=%r' % in_match)
    except Exception:
        pass
    if filled:
        _v842r_log(('racer-prepare', id(case), tuple(filled)),
                   'prepared racer case skin=%r %r'
                   % (getattr(case, '_treacky_skin_template_id', None),
                      filled), 2)
    return len(filled)


def wrap_racer_method(cls, method):
    guard = '_orig_v218fx_' + method
    try:
        if cls is None or guard in vars(cls):
            return False
        previous = cls.__dict__.get(method)
        if not callable(previous):
            return False

        def wrapper(self, *args, **kwargs):
            if sync_attrs.get('bSkinHack', False):
                try:
                    prepare_case(self)
                except Exception:
                    pass
            return previous(self, *args, **kwargs)

        wrapper._v218fx_racer = True
        setattr(cls, guard, previous)
        setattr(cls, method, wrapper)
        return True
    except Exception:
        return False


def wrap_racer_module(module, method):
    guard = '_orig_v218fx_' + method
    try:
        if module is None or guard in vars(module):
            return False
        previous = getattr(module, method, None)
        if not callable(previous):
            return False

        def wrapper(*args, **kwargs):
            if args and sync_attrs.get('bSkinHack', False):
                try:
                    prepare_case(args[0])
                except Exception:
                    pass
            return previous(*args, **kwargs)

        wrapper._v218fx_racer = True
        setattr(module, guard, previous)
        setattr(module, method, wrapper)
        return True
    except Exception:
        return False


def install_racer():
    installed = 0
    methods = ('RefreshRacerForChangeGuise', 'UnLoadRacerEffect',
               '__refresh_racer_component__')
    for module_name in (
            'gclient.gameplay.logic_base.equips.weapon_case_components',
            'gclient.gameplay.logic_base.equips.weapon_case'):
        module = sys.modules.get(module_name)
        if module is None:
            continue
        for method in methods:
            installed += int(wrap_racer_module(module, method))
        for cls in list(vars(module).values()):
            if not isinstance(cls, type):
                continue
            for method in methods:
                installed += int(wrap_racer_method(cls, method))
    if installed:
        _v842r_log(('racer-installed', installed),
                   'racer preflight hooks installed=%d' % installed, 2)
    return installed


def _v842r_empty_config(value):
    """A dict of default/empty values is not a REAL kill-HUD configuration."""
    if value is None or value is False:
        return True
    if isinstance(value, dict):
        if not value:
            return True
        for key, item in value.items():
            name = str(key)
            # Readiness alone does not supply an animation/configuration.
            if name == 'is_dlc_ready':
                continue
            if name in ('use_new_template', 'use_new_icon'):
                if bool(item):
                    return False
                continue
            if item is None or item is False:
                continue
            if isinstance(item, (int, float)) and item == 0:
                continue
            if isinstance(item, (str, bytes, list, tuple, set, dict)) \
                    and not item:
                continue
            return False
        return True
    return previous_empty_config(value)


def _v842r_config_brief(value):
    if isinstance(value, dict):
        try:
            brief = []
            for key, item in list(value.items())[:12]:
                text = repr(item)
                if len(text) > 100:
                    text = text[:97] + '...'
                brief.append('%s=%s' % (key, text))
            return 'dict {%s}' % ', '.join(brief)
        except Exception:
            pass
    return previous_config_brief(value)


# Resolve the real item before the established apply/kill paths read their
# mappings.  Idempotent wrappers preserve all original calls and results.
if not getattr(_apply_weapon_case_skin_core, '_v218fx_mapping', False):
    previous_apply_core = _apply_weapon_case_skin_core

    def apply_core(case, equip_id, forced_skin, reason='apply', force=False):
        _v842r_item_id(forced_skin)
        return previous_apply_core(case, equip_id, forced_skin,
                                          reason=reason, force=force)

    apply_core._v218fx_mapping = True
    _apply_weapon_case_skin_core = apply_core

if not getattr(_v841_skin_ids, '_v218fx_mapping', False):
    _v842r_previous_skin_ids = _v841_skin_ids

    def _v842r_skin_ids(skin_id):
        _v842r_item_id(skin_id)
        return _v842r_previous_skin_ids(skin_id)

    _v842r_skin_ids._v218fx_mapping = True
    _v841_skin_ids = _v842r_skin_ids

if not getattr(empty_config, '_v218fx_empty', False):
    previous_empty_config = empty_config
    _v842r_empty_config._v218fx_empty = True
    empty_config = _v842r_empty_config
if not getattr(config_brief, '_v218fx_brief', False):
    previous_config_brief = config_brief
    _v842r_config_brief._v218fx_brief = True
    config_brief = _v842r_config_brief

if not getattr(_v842g_install, '_v218fx_install', False):
    _v842r_previous_install = _v842g_install

    def _v842r_install():
        stats = _v842r_previous_install()
        try:
            stats['upgrade_mappings'] = refresh_mappings()
        except Exception:
            pass
        try:
            stats['racer'] = install_racer()
        except Exception:
            pass
        return stats

    _v842r_install._v218fx_install = True
    _v842g_install = _v842r_install

try:
    _v842g_install()
except Exception as _v842r_boot_error:
    _v842r_log('boot-error', 'initial FX repair install failed: %r'
               % (_v842r_boot_error,), 1)

# ============================================================
# v2.18-loadout: selected ECLIPSE gun skin on backpack/loadout UI
# ============================================================
# GetBackpackGunSkinItemId is the game's own local backpack display query.
# Override only a real selected GUN row with a real lobby-item mapping.  Do not
# rewrite inventory, unlock rows, force DLC, or touch melee/other players.

_v843l_log_seen = {}


def _v843l_log(key, message, limit=3):
    try:
        count = _v843l_log_seen.get(key, 0)
        if count >= limit:
            return
        if len(_v843l_log_seen) >= 100 and key not in _v843l_log_seen:
            return
        _v843l_log_seen[key] = count + 1
        _plog('[V218LOAD] %s' % message)
    except Exception:
        pass


def _v843l_selected_record(gun_id):
    """Return (equip, template, REAL lobby item) for one selected local gun."""
    try:
        if not sync_attrs.get('bSkinHack', False):
            return None
        gun_id = _safe_int(gun_id, 0)
        gun_ids = globals().get('WEP_GUN_IDS') or {}
        melee_ids = globals().get('WEP_MELEE_IDS') or {}
        if not gun_id or not gun_ids:
            return None
        for equip_id, row in list(WEP.items()):
            try:
                equip_id = _safe_int(equip_id, 0)
                if (not equip_id or equip_id in melee_ids
                        or _safe_int(gun_ids.get(equip_id), 0) != gun_id):
                    continue
                skins = list(row[1:])
                index = _safe_int(sync_attrs.get('iSkin_%s' % equip_id, 0), 0)
                if not (0 < index <= len(skins)):
                    return None
                template_id = _safe_int(skins[index - 1], 0)
                info = WEP_SKIN_INFO.get(template_id) or {}
                if not template_id or not info:
                    return None
                item_id = _safe_int(
                    SKIN_TO_ITEM.get(template_id)
                    or info.get('lobby_item_id'), 0)
                if not item_id:
                    # v2.86: the template row itself + the kit map before
                    # the upgrade-table refresh (device: 140100305).
                    try:
                        _m286 = sys.modules.get(
                            'gclient.data.gun_skin_template_data')
                        _r286 = (_data_get(getattr(_m286, 'data', None),
                                           template_id, None)
                                 if _m286 is not None else None)
                        item_id = (_safe_int(_proto_get(
                            _r286, 'lobby_item_id', 0), 0)
                            if _r286 is not None else 0)
                    except Exception:
                        item_id = 0
                    if not item_id:
                        item_id = _safe_int(kit_item(template_id), 0)
                if not item_id:
                    # Use the established real upgrade-table refresh, but never
                    # accept its template-ID fallback as a lobby display item.
                    resolver = globals().get('_v842r_item_id')
                    if callable(resolver):
                        resolver(template_id)
                    info = WEP_SKIN_INFO.get(template_id) or {}
                    item_id = _safe_int(
                        SKIN_TO_ITEM.get(template_id)
                        or info.get('lobby_item_id'), 0)
                if not item_id:
                    _v843l_log(('unmapped', gun_id, template_id),
                               'loadout stays original: no real lobby item for '
                               'gun=%d template=%d' % (gun_id, template_id), 2)
                    return None
                return equip_id, template_id, item_id
            except Exception:
                continue
    except Exception:
        pass
    return None


def gun_arg(args, kwargs):
    try:
        value = kwargs.get('gun_id')
        if value is None and args:
            # Module function: (gun_id).  Static/class/instance variants carry
            # their descriptor subject first, so the real gun remains last.
            value = args[-1]
        return _safe_int(value, 0)
    except Exception:
        return 0


def backpack_skin_factory(previous):
    def wrapper(*args, **kwargs):
        # Preserve the original call, side effects, return type and exceptions.
        result = previous(*args, **kwargs)
        try:
            if not sync_attrs.get('bSkinHack', False):
                return result
            gun_id = gun_arg(args, kwargs)
            record = _v843l_selected_record(gun_id)
            if not record:
                return result
            equip_id, template_id, item_id = record
            if _safe_int(result, 0) == item_id:
                return result
            _v843l_log(('display', gun_id, equip_id, template_id, item_id),
                       'loadout gun=%d equip=%d template=%d -> real item=%d '
                       '(original=%r)' % (gun_id, equip_id, template_id,
                                          item_id, result), 2)
            return item_id
        except Exception as exc:
            _v843l_log(('display-error', repr(exc)),
                       'loadout display override skipped: %r' % (exc,), 1)
            return result
    wrapper._v843l_wrap = True
    return wrapper


def _v843l_install():
    """sys.modules-only, descriptor-preserving and safe on every retry."""
    installed = 0
    try:
        module = sys.modules.get('gclient.util.gun_skin_util')
        for target in _v841m2_gun_skin_targets(module):
            if isinstance(target, type):
                installed += int(bool(_v839_wrap_method(
                    target, 'GetBackpackGunSkinItemId',
                    backpack_skin_factory)))
            else:
                installed += int(bool(_v841m2_install_module(
                    target, 'GetBackpackGunSkinItemId',
                    backpack_skin_factory)))
        if installed:
            _v843l_log(('installed', installed),
                       'selected-gun loadout display hooks=%d' % installed, 2)
    except Exception as exc:
        _v843l_log(('install-error', repr(exc)),
                   'loadout hook install skipped: %r' % (exc,), 1)
    return installed


# Ride the established FX retry installer so a late-loaded gun_skin_util is
# covered without adding a thread or performing game imports in the watcher.
if not getattr(_v842g_install, '_v843l_install', False):
    _v843l_previous_install = _v842g_install

    def install_with_fx():
        stats = _v843l_previous_install()
        try:
            stats['loadout'] = _v843l_install()
        except Exception:
            pass
        return stats

    install_with_fx._v843l_install = True
    _v842g_install = install_with_fx

try:
    _v842g_install()
except Exception as _v843l_boot_error:
    _v843l_log(('boot-error', repr(_v843l_boot_error)),
               'initial loadout display install failed: %r'
               % (_v843l_boot_error,), 1)



# ============================================================
# v2.18-loadout-icon: gun-refit caller-scoped selected skin icon
# ============================================================
# Device evidence showed GetBackpackGunSkinItemId was installed but never
# called by Modify. GetRealGunSkinIcon carries item/equip/skin/guise directly.
# Change only its skin_item_id argument for actual gun-refit UI callers.

_v218li_log_seen = {}


def _v218li_log(key, message, limit=3):
    try:
        count = _v218li_log_seen.get(key, 0)
        if count >= limit:
            return
        if len(_v218li_log_seen) >= 120 and key not in _v218li_log_seen:
            return
        _v218li_log_seen[key] = count + 1
        _plog('[V218ICON] %s' % message)
    except Exception:
        pass


# ============================================================
# v2.124 HUD icon tier rule (operator): the weapon HUD/loadout
# icon keeps the DEFAULT gun icon for no-tier / Epic / Legendary
# / Ultra skins (quality 0-5). Only the top tiers carry their
# skinned icon: Eternal / EVO / Xtreme + higher/collab rows
# ("it can show the rest").
# ============================================================
def tier_icon_ok(skin_item_id):
    try:
        sid = _safe_int(skin_item_id, 0)
        if not sid:
            return True
        info = (globals().get('WEP_SKIN_INFO') or {}).get(sid) or {}
        found = bool(info)
        q = _safe_int(info.get('skin_quality'), 0) if info else 0
        if not found:
            try:
                _m = sys.modules.get('gclient.data.gun_skin_template_data')
                row = (_data_get(getattr(_m, 'data', None), sid, None)
                       if _m is not None else None)
                if row is not None:
                    found = True
                    q = _safe_int(_proto_get(
                        row, 'quality',
                        _proto_get(row, 'rarity', 0)), 0)
            except Exception:
                pass
        if not found:
            return True
        return q >= 6
    except Exception:
        return True


def selected_equip(value):
    # v2.125: pass-through - the tier rule lives in the icon factory
    # (it must REWRITE to the default icon, not skip the rewrite).
    return selected_equip_orig(value)


def selected_equip_orig(equip_id):
    """Resolve through the real equip->gun map and the existing loadout gate."""
    try:
        equip_id = _safe_int(equip_id, 0)
        gun_id = _safe_int((globals().get('WEP_GUN_IDS') or {}).get(
            equip_id), 0)
        if not equip_id or not gun_id:
            return None
        record = _v843l_selected_record(gun_id)
        if not record or _safe_int(record[0], 0) != equip_id:
            return None
        return record
    except Exception:
        return None


def caller_info():
    """Return (immediate caller, actual gun-refit caller), without gc walks."""
    frame = None
    try:
        # helper -> wrapper -> original Python caller
        frame = sys._getframe(2)
        first = ''
        for _ in range(10):
            if frame is None:
                break
            module = str(frame.f_globals.get('__name__', ''))
            label = '%s.%s' % (module, frame.f_code.co_name)
            if not first:
                first = label
            lowered = module.lower()
            if ('gunrefit' in lowered or 'gun_diy_ui_component' in lowered
                    or 'hud_backpack_select_comp' in lowered):
                return first, label
            frame = frame.f_back
        return first, ''
    except Exception:
        return '', ''
    finally:
        # Do not retain frame/reference cycles in the payload.
        frame = None


def icon_values(args, kwargs):
    keys = ('item_id', 'equip_id', 'skin_item_id', 'guise_item_id')
    values = {key: kwargs.get(key) for key in keys}
    base = 0
    if (args and args[0] is not None
            and not (isinstance(args[0], int)
                     and not isinstance(args[0], bool))):
        # classmethod/instancemethod subject before the four documented args.
        # None is a real static-method item_id, never a subject: Gunsmith's
        # canonical (None, equip, skin, guise) shape used to be logged/shifted.
        base = 1
    for index, value in enumerate(args[base:base + 4]):
        values[keys[index]] = value
    return base, values


# #======================================================================
# //  SCOPESYNC.PY
# //
# //  This file is for: WEAPON UI + SCOPESYNC: the loadout icons/panels (v218li/v218ui), the accessory + optic catalogs, the authentic optic cosmetics (scopesync), the display install.
# //
# //  Part of the split TREACKY BS payload (v2.112).  The runtime
# //  file payload/skins_payload.py is GENERATED: run
# //  tools/build_payload.py after editing these modules.
# #======================================================================
