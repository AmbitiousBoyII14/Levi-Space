# ============================================================
# SCOPESYNC.PY (payload feature module)
# PROVIDES: real_icon_factory, _v218li_install, _v218li2_record_from_object, _v218li2_refresh_factory, install_refresh, no_donor_pools, real_row_only, _v218m_log, positive_id, _v218m_query, upgrade_owners, upgrade_ids, _v218m_feature_rows, _v218m_merge_skin, ... +170 more | _V218M_LEGACY_BROADCAST_FIELDS, _V218A_MAX_FX_FIELDS, _V218A_TRUE_FIELDS, _V218A_DEATH_FIELDS, _V218A_FEATURE_FIELDS, _V218A_LOG_SEEN, _V218A_UPGRADE_CACHE, _V218A_REFRESH_STATE, _V218A_REFRESH_LOG_COUNTS, _V218A_HIT_LOG_COUNTS, ...
# REQUIRES: shared namespace (config/names/main/game_api/catalog);
#           game modules imported inline, verified against the dumps.
# Feature module - see REWRITE_PLAN.md S1.
# ============================================================
"""Weapon UI icons/panels + authentic optic cosmetics: icon factory wrap chains, special-optic apply/restore, panel invoke, and the v218p/v218m/v218a/v218bc2/v218scope fx wrap layers."""

# #======================================================================
# //  SCOPESYNC.PY
# //
# //  This file is for: WEAPON UI + SCOPESYNC: the loadout icons/panels (v218li/v218ui), the accessory + optic catalogs, the authentic optic cosmetics (scopesync), the display install.
# //
# //  Part of the split TREACKY BS payload (v2.112).  The runtime
# //  file payload/skins_payload.py is GENERATED: run
# //  tools/build_payload.py after editing these modules.
# #======================================================================
def real_icon_factory(previous):
    def wrapper(*args, **kwargs):
        if not sync_attrs.get('bSkinHack', False):
            return previous(*args, **kwargs)
        base = 0
        values = {}
        first = ''
        loadout = ''
        equip_id = 0
        try:
            base, values = icon_values(args, kwargs)
            equip_id = _safe_int(values.get('equip_id'), 0)
            first, loadout = caller_info()
        except Exception:
            pass
        record = selected_equip(equip_id) if loadout else None
        if loadout and not record:
            # The device backpack/loadout RefreshInfo passes the equip id in
            # its first (item_id) slot and leaves equip_id=0.  Accept it only
            # through the real WEP_GUN_IDS + selected-record validation; an
            # arbitrary lobby item id must never be guessed as an equip id.
            record = selected_equip(values.get('item_id'))
        if loadout and not record:
            try:
                record = (refresh_stack[-1]
                          if refresh_stack else None)
            except Exception:
                record = None
        if record:
            # v2.125: HUD icon tier rule (operator). No-tier / Epic /
            # Legendary / Ultra skins show the DEFAULT gun icon on the HUD:
            # force the call with both cosmetics zeroed - that is the plain
            # (white/grey) gun art, the "paint them white" fallback. Big /
            # Eternal / EVO / Xtreme / collab-grade rows keep the skinned
            # icon ("it can show the rest").
            try:
                if not tier_icon_ok(record[2]):
                    na25, nk25 = set_argument(
                        args, kwargs, base, 2, 'skin_item_id', 0)
                    na25, nk25 = set_argument(
                        na25, nk25, base, 3, 'guise_item_id', 0)
                    result = previous(*na25, **nk25)
                    _v218li_log(('default-icon', equip_id, record[2]),
                                'hud default icon equip=%d skin=%d '
                                '(tier rule applied)' % (equip_id, record[2]), 2)
                    return result
            except Exception:
                pass
            # Pairicon4: the pre-match Backpack and bottom HUD reach this
            # established wrapper with both cosmetic arguments empty.  The
            # working gunsmith path proved that a real lobby row must use its
            # own skin/guise branch.  Reuse that exact canonical call here;
            # explicit cosmetics and unknown rows keep the legacy behavior.
            kind = ''
            if (not _safe_int(values.get('skin_item_id'), 0)
                    and not _safe_int(values.get('guise_item_id'), 0)):
                resolver = globals().get('cosmetic_kind')
                if callable(resolver):
                    kind = resolver(record)
            canonical = globals().get('canonical_call')
            if kind in ('skin', 'guise') and callable(canonical):
                result = canonical(previous, base, args, kwargs, record, kind)
                shape = 'canonical-' + kind
            else:
                new_args = list(args)
                new_kwargs = dict(kwargs)
                skin_index = base + 2
                if len(new_args) > skin_index:
                    new_args[skin_index] = record[2]
                else:
                    new_kwargs['skin_item_id'] = record[2]
                result = previous(*new_args, **new_kwargs)
                shape = 'legacy-skin'
            _v218li_log(('apply', equip_id, record[1], record[2], loadout),
                        'loadout icon input_item=%r equip=%d template=%d '
                        'skin=%r -> real item=%d guise=%r shape=%s result=%s '
                        'caller=%s'
                        % (values.get('item_id'), equip_id, record[1],
                           values.get('skin_item_id'), record[2],
                           values.get('guise_item_id'), shape,
                           repr(result)[:80], loadout), 2)
            return result
        result = previous(*args, **kwargs)
        # Bounded evidence for a missed caller or unresolved selection. This
        # does not change Nearby/HUD/other consumers of the same helper.
        _v218li_log(('original', equip_id, values.get('skin_item_id'),
                     first, loadout),
                    'icon original item=%r equip=%d skin=%r guise=%r '
                    'caller=%s loadout=%s'
                    % (values.get('item_id'), equip_id,
                       values.get('skin_item_id'), values.get('guise_item_id'),
                       loadout or first or 'unknown', bool(loadout)), 1)
        return result
    wrapper._v218li_wrap = True
    return wrapper


def _v218li_install():
    installed = 0
    try:
        module = sys.modules.get('gclient.util.gun_skin_util')
        for target in _v841m2_gun_skin_targets(module):
            if isinstance(target, type):
                installed += int(bool(_v839_wrap_method(
                    target, 'GetRealGunSkinIcon', real_icon_factory)))
            else:
                installed += int(bool(_v841m2_install_module(
                    target, 'GetRealGunSkinIcon', real_icon_factory)))
        if installed:
            _v218li_log(('installed', installed),
                        'gun-refit selected-skin icon hooks=%d' % installed, 2)
    except Exception as exc:
        _v218li_log(('install-error', repr(exc)),
                    'icon hook install skipped: %r' % (exc,), 1)
    return installed


if not getattr(_v842g_install, '_v218li_install', False):
    _v218li_previous_install = _v842g_install

    def install_with_loadout():
        stats = _v218li_previous_install()
        try:
            stats['loadout_icon'] = _v218li_install()
        except Exception:
            pass
        return stats

    install_with_loadout._v218li_install = True
    _v842g_install = install_with_loadout

try:
    _v842g_install()
except Exception as _v218li_boot_error:
    _v218li_log(('boot-error', repr(_v218li_boot_error)),
                'initial loadout icon install failed: %r'
                % (_v218li_boot_error,), 1)


# ============================================================
# v2.18-device-context-dlc: RefreshInfo context + real DLC retries
# ============================================================
# Device evidence: Modify calls GetRealGunSkinIcon with equip_id=0 from
# HudGunrefitBackpackComp.RefreshInfo.  Carry that method's real gun/equipment
# context through the nested call.  Separately, real kill-HUD config can remain
# is_dlc_ready=False after the one-shot downloader dedupe; permit bounded real
# item-download retries without changing the config or forcing readiness.

refresh_stack = []


def _v218li2_record_from_object(value, depth=0):
    """Find a selected record only from real gun/equip/proto context fields."""
    if value is None:
        return None
    try:
        if isinstance(value, int) and not isinstance(value, bool):
            number = _safe_int(value, 0)
            gun_ids = globals().get('WEP_GUN_IDS') or {}
            if number in gun_ids:
                return selected_equip(number)
            if number in set(gun_ids.values()):
                return _v843l_selected_record(number)
            return None
        if isinstance(value, (str, bytes, float, bool)):
            return None
        gun_id = _safe_int(getattr(value, 'gun_id', 0), 0)
        if gun_id:
            record = _v843l_selected_record(gun_id)
            if record:
                return record
        equip_id = _safe_int(getattr(value, 'equip_id', 0), 0)
        if equip_id:
            record = selected_equip(equip_id)
            if record:
                return record
        equip_proto = getattr(value, 'equip_proto', None)
        if equip_proto is not None:
            equip_id = _safe_int(
                getattr(equip_proto, 'equip_id', 0)
                or getattr(equip_proto, 'id', 0), 0)
            if equip_id:
                record = selected_equip(equip_id)
                if record:
                    return record
        gun_proto = getattr(value, 'gun_proto', None)
        if gun_proto is not None:
            gun_id = _safe_int(
                getattr(gun_proto, 'gun_id', 0)
                or getattr(gun_proto, 'id', 0), 0)
            if gun_id:
                record = _v843l_selected_record(gun_id)
                if record:
                    return record
        item_proto = getattr(value, 'item_proto', None)
        if item_proto is not None:
            gun_id = _safe_int(getattr(item_proto, 'gun_id', 0), 0)
            if gun_id:
                record = _v843l_selected_record(gun_id)
                if record:
                    return record
            equip_id = _safe_int(getattr(item_proto, 'equip_id', 0), 0)
            if equip_id:
                record = selected_equip(equip_id)
                if record:
                    return record
        if depth < 1:
            for name in ('gun_info', '_gun_info', 'equipment',
                         'hall_equipment', 'item', 'gun', 'cur_gun',
                         'current_gun'):
                nested = getattr(value, name, None)
                if nested is None or nested is value or callable(nested):
                    continue
                record = _v218li2_record_from_object(nested, depth + 1)
                if record:
                    return record
    except Exception:
        return None
    return None


def _v218li2_refresh_factory(previous):
    def wrapper(self, *args, **kwargs):
        record = None
        if sync_attrs.get('bSkinHack', False):
            # v10.4: an explicit row/drop identity wins over the panel's
            # currently selected gun.  The display-sync resolver also prevents
            # an unselected explicit row from inheriting that panel selection.
            resolver = globals().get('refresh_record')
            if callable(resolver):
                record = resolver(self, args, kwargs)
            else:
                for value in (self,) + tuple(args) + tuple(kwargs.values()):
                    record = _v218li2_record_from_object(value)
                    if record:
                        break
        refresh_stack.append(record)
        try:
            if record:
                _v218li_log(('refresh-context', record[0], record[1],
                             record[2]),
                            'RefreshInfo context equip=%d template=%d item=%d'
                            % (record[0], record[1], record[2]), 2)
            else:
                signature = (type(self).__name__,
                             tuple(type(value).__name__ for value in args[:3]))
                _v218li_log(('refresh-no-context', signature),
                            'RefreshInfo no selected context self=%s args=%r'
                            % signature, 1)
            call_args = args
            call_kwargs = kwargs
            proxy_factory = globals().get('_v218display_proxy')
            if record and callable(proxy_factory):
                # Native RefreshInfo consumes more than GetRealGunSkinIcon:
                # names, template IDs and realtime/3D icon baking also read
                # this object.  Supply a read-only visual view; never write
                # the real CItem/info mapping or its attachment containers.
                call_args = tuple(proxy_factory(value, record)
                                  for value in args)
                call_kwargs = {key: proxy_factory(value, record)
                               for key, value in kwargs.items()}
            return previous(self, *call_args, **call_kwargs)
        finally:
            try:
                refresh_stack.pop()
            except Exception:
                pass
    wrapper._v218li2_refresh = True
    return wrapper


def install_refresh():
    installed = 0
    try:
        module = sys.modules.get(
            'gclient.gameplay.uicomponents.uigunrefit.'
            'hud_gunrefit_backpack_comp')
        if module is not None:
            for value in list(vars(module).values()):
                if not isinstance(value, type):
                    continue
                if getattr(value, '__module__', None) != module.__name__:
                    continue
                if not callable(getattr(value, 'RefreshInfo', None)):
                    continue
                installed += int(bool(_v839_wrap_method(
                    value, 'RefreshInfo', _v218li2_refresh_factory)))
        if installed:
            _v218li_log(('refresh-installed', installed),
                        'Modify RefreshInfo context hooks=%d' % installed, 2)
    except Exception as exc:
        _v218li_log(('refresh-install-error', repr(exc)),
                    'RefreshInfo context install skipped: %r' % (exc,), 1)
    return installed


# The established icon retry now covers both the helper and its UI caller.
if not getattr(_v218li_install, '_v218li2_install', False):
    _v218li2_previous_icon_install = _v218li_install

    def _v218li2_install():
        installed = _v218li2_previous_icon_install()
        installed += install_refresh()
        return installed

    _v218li2_install._v218li2_install = True
    _v218li_install = _v218li2_install


try:
    _v218li_install()
except Exception as _v218li2_boot_error:
    _v218li_log(('refresh-boot-error', repr(_v218li2_boot_error)),
                'initial RefreshInfo context install failed: %r'
                % (_v218li2_boot_error,), 1)



# ============================================================
# v2.18-precision: real per-skin FX; FXFIX kill contract retained
# ============================================================
# The device-confirmed FXFIX kill record/config implementation above is
# intentionally active.  Later content ranking and template_path injection
# altered the working record; do not re-layer them here.

# Cross-skin donor values are not valid per-skin data.  Disable the complete
# 29k-row game-thread scan and all donor creation/fills; retain real rows and
# bounded one-shot diagnostics so missing data stays visible and honest.
def no_donor_pools(force=False):
    _fx_scanned[0] = True
    return False


def real_row_only(skin_id):
    if not skin_id:
        return []
    row = None
    for module_name in FX_SOURCE_MODULES:
        row = _fx_row(module_name, skin_id)
        if row is not None:
            break
    if row is None:
        _weaponfx_log_once(
            ('real-row-missing', skin_id),
            '[FXROW-REAL] skin=%s missing; no donor row created' % skin_id)
        return []
    if skin_id not in _fx_row_keys_done:
        _fx_row_keys_done.add(skin_id)
        try:
            names = ('fps_tracer_bullet_id', 'fps_adstracer_bullet_id',
                     'fps_simple_tracer_bullet_id',
                     'fps_simple_adstracer_bullet_id',
                     'extra_ballistic_tracer_bullet_id',
                      'skin_hit_object_effect_id', 'kill_fx',
                      'kill_fx_id', 'kill_mat', 'kill_tip_icon_replace',
                     'kill_hud_id', 'kill_hud_csb_path', 'dlc_id',
                     'dlc_pack_ids')
            values = {name: _proto_get(row, name, None) for name in names}
            keys = [str(key) for key, _value in _data_items(row)[:64]]
            _plog('[FXROW-REAL] skin=%s values=%r keys=%r' %
                  (skin_id, values, keys))
        except Exception as exc:
            _plog('[FXROW-REAL] skin=%s diagnostic error=%r' %
                  (skin_id, exc))
    return []


_fx_pools = {}
_fx_scanned[0] = True
_fx_stats_pushed[0] = True
_fx_build_pools = no_donor_pools
_fx_seed_row = real_row_only
_plog('[V218P] real per-skin FX only; donor scan/fills disabled')


# ============================================================
# v2.18-maxbroadcast: authentic max-level row + final panel repair
# ============================================================
# Log 11 proved that the enriched HudKillRecordComp record can match the old
# working M4 record while panel_kill still renders the normal feed.  The
# record hook is therefore not the final consumer.  Resolve the selected
# item's REAL max-level row, merge only its own legacy broadcast fields into
# the real template row, and repeat the established FXFIX enrichment at the
# actual panel_kill.Push boundary.  No donor rows, cross-skin values, derived
# paths, new-HUD propagation, DLC/readiness overrides, or fabricated IDs.

_V218M_LEGACY_BROADCAST_FIELDS = frozenset((
    'kill_tip_icon_replace', 'kill_tip_icon_2_replace',
    'kill_avatar_effect', 'kill_avatar_effect_id',
    'kill_avatar_effect_id_replace', 'kill_mat', 'Team_kill_mat',
    'team_kill_mat', 'kill_mat_start_time', 'team_kill_mat_start_time',
    'kill_team_extra_model_id', 'kill_fx', 'kill_fx_id',
    'kill_effect', 'kill_effect_id', 'kill_effect_type',
    'kill_num_cam', 'kill_hud_id', 'kill_hud_csb_path',
    'kill_hud_vx_node',
))
_v218m_log_seen = {}
id_cache = {}
merge_logged = set()
panel_logged = set()


def _v218m_log(key, message, limit=2):
    try:
        count = _v218m_log_seen.get(key, 0)
        if count >= limit:
            return
        if len(_v218m_log_seen) >= 140 and key not in _v218m_log_seen:
            return
        _v218m_log_seen[key] = count + 1
        _plog('[V218M] %s' % message)
    except Exception:
        pass


def positive_id(value):
    if isinstance(value, bool):
        return 0
    try:
        value = int(value or 0)
    except Exception:
        return 0
    return value if value > 0 else 0


def _v218m_query(owner, name, *args):
    """Read a pure game upgrade query, including unbound class variants."""
    try:
        function = getattr(owner, name, None)
        if not callable(function):
            return None
        try:
            return function(*args)
        except TypeError:
            # Some game builds expose these as plain functions on a manager
            # class rather than staticmethods.  Do not instantiate a manager.
            if not isinstance(owner, type):
                return None
            try:
                return function(owner, *args)
            except Exception:
                return None
    except Exception:
        return None


def upgrade_owners():
    owners = []
    try:
        module = sys.modules.get('gclient.util.gun_upgrade_util')
        cls = getattr(module, 'GunUpgradeDataMgr', None) if module else None
        instance = getattr(cls, '_instance', None) if cls is not None else None
        for owner in (instance, cls,
                      sys.modules.get('gclient.util.cdata_util')):
            if owner is not None and not any(owner is old for old in owners):
                owners.append(owner)
    except Exception:
        pass
    return owners


def upgrade_ids(skin_id):
    """(max item, base/item, template) using only real game level mappings."""
    template_id = positive_id(ITEM_TO_SKIN.get(skin_id, skin_id))
    if not template_id:
        return ()
    try:
        item_id = positive_id(_v842r_item_id(template_id))
    except Exception:
        item_id = positive_id(SKIN_TO_ITEM.get(template_id))
    if not item_id:
        item_id = template_id
    cache_key = (template_id, item_id)
    now = time.time()
    cached = id_cache.get(cache_key)
    if cached and now - cached[0] < 10.0:
        return cached[1]

    owners = upgrade_owners()
    base_id = 0
    maximum = 0
    max_item_id = 0
    for owner in owners:
        if not base_id:
            base_id = positive_id(_v218m_query(
                owner, 'ItemId2BaseLevelItem', item_id))
        if not maximum:
            maximum = positive_id(_v218m_query(
                owner, 'GetMaxLevel', item_id))
    if not base_id:
        base_id = item_id
    if maximum:
        for owner in owners:
            max_item_id = positive_id(_v218m_query(
                owner, 'GetItemIdByBaseItemIdAndLevel', base_id, maximum))
            if max_item_id:
                break
    if max_item_id:
        # A malformed/custom table must not redirect one skin to another
        # family.  Validate against the game's own base-level mapping.
        for owner in owners:
            mapped_base = positive_id(_v218m_query(
                owner, 'ItemId2BaseLevelItem', max_item_id))
            if mapped_base:
                if mapped_base != base_id:
                    _v218m_log(('reject-max', template_id, max_item_id,
                                mapped_base, base_id),
                               'rejected cross-family max item skin=%d item=%d '
                               'candidate=%d base=%d/%d'
                               % (template_id, item_id, max_item_id,
                                  mapped_base, base_id), 1)
                    max_item_id = 0
                break

    ordered = []
    # Preserve the established item/template candidate contract.  The base
    # item is used to resolve the real max row, not inserted as an extra HUD
    # candidate that could change legacy config selection.
    for value in (max_item_id, item_id, template_id):
        if value and value not in ordered:
            ordered.append(value)
    result = tuple(ordered)
    # Negative answers may simply mean the upgrade module loaded late.
    id_cache[cache_key] = (now, result)
    if max_item_id:
        _v218m_log(('max-item', template_id, item_id, max_item_id, maximum),
                   'real upgrade IDs skin=%d item=%d max_item=%d level=%d'
                   % (template_id, item_id, max_item_id, maximum), 1)
    return result


def _v218m_feature_rows(skin_id):
    """Same-family rows, low priority first and real max item last."""
    rows = []
    ids = upgrade_ids(skin_id)
    modules = []
    for module_name in ('gclient.data.item_feature_data',
                        'gclient.data.lobby_item_upgrade_extra_data'):
        try:
            module = sys.modules.get(module_name) or _import_module(module_name)
            data = getattr(module, 'data', None) if module else None
            if data is not None:
                modules.append((module_name, data))
        except Exception:
            continue
    for row_id in reversed(ids):
        for module_name, data in modules:
            try:
                row = _data_get(data, row_id, None)
                if row is not None:
                    rows.append((module_name, row_id, row))
            except Exception:
                continue
    return rows


def _v218m_merge_skin(skin_id):
    """Merge one selected skin's authentic legacy fields; never create a row."""
    template_id = positive_id(ITEM_TO_SKIN.get(skin_id, skin_id))
    if not template_id:
        return []
    row = None
    for module_name in FX_SOURCE_MODULES:
        row = _fx_row(module_name, template_id)
        if row is not None:
            break
    if row is None:
        return []

    changes = {}
    values = {}
    try:
        sources = _v218m_feature_rows(template_id)
    except Exception as exc:
        _v218m_log(('sources-error', template_id, repr(exc)),
                   'same-skin feature lookup skipped for %d: %r'
                   % (template_id, exc), 1)
        return []
    for module_name, row_id, source in sources:
        for field in _V218M_LEGACY_BROADCAST_FIELDS:
            try:
                value = _proto_get(source, field, None)
                valid = (value is True if field == 'kill_effect'
                         else _fx_value_ok(value))
                if not valid:
                    continue
                old_value = _proto_get(row, field, None)
                if old_value == value:
                    continue
                if _mapping_set(row, field, value):
                    changes[field] = (module_name.rsplit('.', 1)[-1], row_id)
                    values[field] = value
            except Exception:
                continue

    if changes:
        # Keep the existing feature-activation predicate informed by the same
        # authentic values.  Do not touch raw hit/tracer/muzzle mirrors.
        try:
            info = WEP_SKIN_INFO.get(template_id)
            if isinstance(info, dict):
                for field, value in values.items():
                    info[field] = value
                WEP_SKIN_INFO[template_id] = info
        except Exception:
            pass
        signature = (template_id, tuple(sorted(
            (field, source[0], source[1], repr(values[field])[:100])
            for field, source in changes.items())))
        if signature not in merge_logged:
            if len(merge_logged) < 180:
                merge_logged.add(signature)
            _v218m_log(('merge', signature),
                       'authentic max broadcast skin=%d ids=%r fields=%r '
                       'sources=%r' % (template_id, upgrade_ids(template_id),
                                      sorted(changes), changes), 1)
    return sorted(changes)


# Include the real max-level item in native config probes.  The original item
# and template remain fallbacks, and the original call is always preserved by
# config_variants.
previous_skin_ids = _v841_skin_ids


def _v218m_skin_ids(skin_id):
    try:
        original = tuple(previous_skin_ids(skin_id))
        return unique_ids(upgrade_ids(skin_id) + original)
    except Exception:
        return list(previous_skin_ids(skin_id))


_v841_skin_ids = _v218m_skin_ids


# Accept the game's bare KILL_UI / DYNAMIC_KULL_UI spellings as well as its
# UPGRADE_FEATURE_* constants.  Numeric IDs still come only from loaded enums.
_v218m_previous_feature_kinds = _v842g_feature_kinds


def _v218m_feature_kinds(name):
    kinds = _v218m_previous_feature_kinds(name)
    if kinds:
        return kinds
    upper = str(name).upper()
    result = []
    if (('KILL' in upper or 'KULL' in upper)
            and any(token in upper for token in
                    ('UI', 'BROADCAST', 'FEED', 'RECORD'))
            and 'COUNTER' not in upper and 'NUM' not in upper):
        result.append('broadcast')
    if any(token in upper for token in
           ('TRACER', 'BULLET_TRACE', 'BULLET_RACER', 'RACER')):
        result.append('tracer')
    return tuple(result)


_v842g_feature_kinds = _v218m_feature_kinds
previous_feature_number = _v842g_feature_number


def feature_number(value):
    number = previous_feature_number(value)
    if number or not isinstance(value, str):
        return number
    target = value.strip().upper()
    if not target:
        return 0
    try:
        for owner in enum_owners():
            for name in dir(owner):
                upper = str(name).upper()
                if upper != target and not upper.endswith('_' + target):
                    continue
                if not _v842g_feature_kinds(name):
                    continue
                number = previous_feature_number(
                    getattr(owner, name, None))
                if number:
                    return number
    except Exception:
        pass
    return 0


_v842g_feature_number = feature_number


# Repair at the actual renderer boundary.  This is a behavior fix, not just a
# probe: if PushKillRecord rebuilt or stripped the mapping, panel_kill.Push
# receives the same authentic max-level legacy record immediately before the
# original renderer consumes it.
def forced_template():
    try:
        forced = globals().get('_force_kill_hud_skin', [None])[0]
        if forced:
            template_id = positive_id(ITEM_TO_SKIN.get(forced, forced))
            if template_id in WEP_SKIN_INFO:
                return template_id
            if forced in WEP_SKIN_INFO:
                return forced
    except Exception:
        pass
    try:
        skin_id, _case = _get_kill_skin(None)
        return positive_id(ITEM_TO_SKIN.get(skin_id, skin_id))
    except Exception:
        return 0


def panel_brief(info):
    values = {}
    for field in ('guise_id', 'guise_item_id', 'hud_kill_ui', 'kill_effect',
                  'kill_fx', 'kill_mat', 'kill_avatar_effect',
                  'kill_tip_icon_replace', 'kill_hud_id',
                  'kill_hud_csb_path', 'kill_num_cam'):
        try:
            values[field] = _mapping_get(info, field, None)
        except Exception:
            values[field] = None
    return values


def before_panel(info):
    if not sync_attrs.get('bSkinHack', False) or info is None:
        return 0
    template_id = forced_template()
    if not template_id:
        return 0
    _v218m_merge_skin(template_id)
    if callable(_v218m_previous_copy):
        _v218m_previous_copy(info, template_id)
    try:
        enrich_kill_config(info, template_id)
    except Exception:
        pass
    _v218m_log(('panel-record', template_id,
                repr(panel_brief(info))),
               'panel authentic record skin=%d values=%r'
               % (template_id, panel_brief(info)), 1)
    return template_id


def _v218m_panel_invoke(previous, args, kwargs, has_subject):
    info = kwargs.get('info')
    if info is None:
        index = 1 if has_subject else 0
        if len(args) > index:
            info = args[index]
    template_id = 0
    try:
        template_id = before_panel(info)
    except Exception as exc:
        _v218m_log(('panel-error', repr(exc)),
                   'panel enrichment skipped: %r' % (exc,), 1)
    try:
        result = previous(*args, **kwargs)
    except Exception:
        raise
    if template_id:
        _v218m_log(('panel-return', template_id, type(result).__name__),
                   'panel original Push returned skin=%d type=%s value=%s'
                   % (template_id, type(result).__name__,
                      repr(result)[:160]), 1)
    return result


def wrap_panel_class(cls):
    guard = '_orig_v218m_panel_push'
    try:
        if cls is None or guard in vars(cls):
            return int(cls is not None and guard in vars(cls))
        static = inspect.getattr_static(cls, 'Push')
        previous = (static.__func__ if isinstance(
            static, (staticmethod, classmethod)) else static)
        if not callable(previous):
            return 0
        has_subject = not isinstance(static, staticmethod)

        def wrapper(*args, **kwargs):
            return _v218m_panel_invoke(previous, args, kwargs, has_subject)

        setattr(cls, guard, previous)
        if isinstance(static, staticmethod):
            setattr(cls, 'Push', staticmethod(wrapper))
        elif isinstance(static, classmethod):
            setattr(cls, 'Push', classmethod(wrapper))
        else:
            setattr(cls, 'Push', wrapper)
        try:
            log_code_contract(previous, 'panel-push')
        except Exception:
            pass
        return 1
    except Exception:
        return 0


def _v218m_install_panel():
    try:
        if not sync_attrs.get('bSkinHack', False):
            return 0
        game_genv = _game_genv()
        player = getattr(game_genv, 'player', None) if game_genv else None
        panel = getattr(player, 'panel_kill', None) if player else None
        if panel is None:
            return 0
        cls = panel if isinstance(panel, type) else type(panel)
        installed = wrap_panel_class(cls)
        if installed and cls not in panel_logged:
            panel_logged.add(cls)
            try:
                apis = [name for name in dir(panel)
                        if any(token in name.lower() for token in
                               ('kill', 'push', 'show', 'anim', 'vx',
                                'broadcast', 'refresh'))]
            except Exception:
                apis = []
            _v218m_log(('panel-installed', cls),
                       'panel_kill.Push hooked class=%s apis=%r'
                       % (cls.__name__, apis[:48]), 1)
        return installed
    except Exception as exc:
        _v218m_log(('panel-install-error', repr(exc)),
                   'panel hook install skipped: %r' % (exc,), 1)
        return 0


_v218m_previous_copy = globals().get('_copy_skin_kill_broadcast_data')


def copy_with_max(info, skin_id):
    try:
        _v218m_merge_skin(skin_id)
        _v218m_install_panel()
    except Exception as exc:
        _v218m_log(('copy-error', skin_id, repr(exc)),
                   'max broadcast preflight skipped skin=%s: %r'
                   % (skin_id, exc), 1)
    if callable(_v218m_previous_copy):
        return _v218m_previous_copy(info, skin_id)
    return None


if callable(_v218m_previous_copy):
    _copy_skin_kill_broadcast_data = copy_with_max


def seed_row(skin_id):
    original = real_row_only(skin_id)
    try:
        merged = _v218m_merge_skin(skin_id)
        return list(original or []) + list(merged)
    except Exception as exc:
        _v218m_log(('seed-error', skin_id, repr(exc)),
                   'max broadcast seed skipped skin=%s: %r'
                   % (skin_id, exc), 1)
        return original


_fx_seed_row = seed_row
_plog('[V218M] authentic max-level broadcast row + panel repair ready')


# ============================================================
# v2.18-allfx: authentic max-level FX across every native consumer
# ============================================================
# This layer is deliberately additive.  It does not rewrite the confirmed
# tracer or muzzle/fire pipelines.  It completes the other native paths with
# values from the SAME selected skin and its REAL same-family max item:
#   * item_feature_data storage read directly by gun_skin_util/WeaponCase;
#   * WeaponCase._RefreshFeatureCache and inspection/death/optic refreshes;
#   * skin_hit_object_effect_dict / dual_skin_hit_object_effect_dict;
#   * weapon-case context at the final PlayHitEffect call;
#   * authentic death fields at PlaySkinDeadEffect;
#   * an instance fallback when panel_kill.Push is not a class attribute.
# No donor rows, global scans, derived paths, fabricated effect IDs, DLC
# readiness overrides, new-HUD propagation, or base-item HUD candidates.

_V218A_MAX_FX_FIELDS = frozenset((
    # Native dye effects (tracer and fire/muzzle fields intentionally omitted).
    'skin_hit_object_effect_id', 'skin_hit_object_effect_id_replace',
    'team_dead_fx', 'guise_anim_effect_dict', 'dlc_effects',
    'optic_b_fx', 'skin_optic_effect', 'skin_part_optic_effect',
    'gun_skin_permanent_sfx', 'gun_skin_permanent_show_sfx',
    'sub_gun_skin_permanent_sfx', 'sub_gun_skin_permanent_show_sfx',
    'gun_skin_permanent_sfx_3p', 'sub_gun_skin_permanent_sfx_3p',
    'gun_skin_permanent_warehouse_sfx', 'gun_skin_icon_show_effect',
    'gun_skin_part_cannon_off_base_sfx_list', 'gun_skin_ads_sfx',
    'twin_skin_change_color_dict',
    # Inspection / raise / active idle animation data.
    'SkinInspectAnimName', 'CanInspectionPlayActive',
    'SpecialInspectionThreshold', 'SkinRaiseNewAnimName',
    'SkinIdleActivePoseAnimName', 'SkinLobbyIdleActivePoseAnimName',
    # Death and team-death effects / animation data.
    'SpecialDieActionPose', 'TeamDieActionPose',
    'die_action_attach_model_id', 'die_action_attach_model_time',
    'die_action_disappear_time', 'team_die_action_attach_model_id',
    'team_die_action_attach_model_time', 'team_die_action_disappear_time',
    'kill_team_extra_model_id', 'kill_team_extra_hexie_model_id',
    'ExtraModelKillTeamAnimName',
))
_V218A_TRUE_FIELDS = frozenset((
    'CanInspectionPlayActive', 'show_hit_effect', 'show_guise_hit_effect',
))
_V218A_DEATH_FIELDS = tuple(sorted(
    set(_V218A_MAX_FX_FIELDS).intersection((
        'team_dead_fx', 'guise_anim_effect_dict',
        'SpecialDieActionPose', 'TeamDieActionPose',
        'die_action_attach_model_id', 'die_action_attach_model_time',
        'die_action_disappear_time', 'team_die_action_attach_model_id',
        'team_die_action_attach_model_time', 'team_die_action_disappear_time',
        'kill_team_extra_model_id', 'kill_team_extra_hexie_model_id',
        'ExtraModelKillTeamAnimName',
    ))))
_V218A_FEATURE_FIELDS = {
    'hit': (
        'skin_hit_object_effect_id', 'skin_hit_object_effect_id_replace',
        'hit_effect_id', 'hit_fx_id', 'show_hit_effect',
        'show_guise_hit_effect',
    ),
    'inspection': (
        'SkinInspectAnimName', 'CanInspectionPlayActive',
        'SpecialInspectionThreshold', 'SkinIdleActivePoseAnimName',
        'SkinLobbyIdleActivePoseAnimName', 'guise_anim_effect_dict',
    ),
    'raise': (
        'SkinRaiseNewAnimName', 'SkinIdleActivePoseAnimName',
        'SkinLobbyIdleActivePoseAnimName', 'v8_skin_id', 'twin_skin_list',
    ),
    'death': _V218A_DEATH_FIELDS + ('kill_fx', 'kill_mat'),
    'optic': (
        'optic_b_fx', 'skin_optic_effect', 'skin_part_optic_effect',
        'skin_optic_id',
    ),
    'color': (
        'twin_skin_change_color_dict', 'gun_skin_set_fx_color_config',
        'skin_effect_color', 'skin_fx_color', 'cur_sfx_hsv', 'cur_sfx_color',
    ),
}
_V218A_LOG_SEEN = {}
_V218A_UPGRADE_CACHE = {}
_V218A_REFRESH_STATE = {}
_V218A_REFRESH_LOG_COUNTS = {}
_V218A_HIT_LOG_COUNTS = {}
_V218A_AUDIT_SEEN = set()
_V218A_HIT_MERGE_AT = {}


def _v218a_log(key, message, limit=2):
    try:
        count = _V218A_LOG_SEEN.get(key, 0)
        if count >= limit:
            return
        if len(_V218A_LOG_SEEN) >= 180 and key not in _V218A_LOG_SEEN:
            return
        _V218A_LOG_SEEN[key] = count + 1
        _plog('[V218A] %s' % message)
    except Exception:
        pass


def _v218a_template_row(skin_id):
    template_id = positive_id(ITEM_TO_SKIN.get(skin_id, skin_id))
    if not template_id:
        return 0, None
    for module_name in FX_SOURCE_MODULES:
        row = _fx_row(module_name, template_id)
        if row is not None:
            return template_id, row
    return template_id, None


def upgrade_state(skin_id):
    """(item, base, real max item, real max level), same family only."""
    template_id = positive_id(ITEM_TO_SKIN.get(skin_id, skin_id))
    if not template_id:
        return (0, 0, 0, 0)
    try:
        item_id = positive_id(_v842r_item_id(template_id))
    except Exception:
        item_id = positive_id(SKIN_TO_ITEM.get(template_id))
    if not item_id:
        item_id = template_id
    now = time.time()
    cached = _V218A_UPGRADE_CACHE.get((template_id, item_id))
    if cached and now - cached[0] < 10.0:
        return cached[1]
    owners = upgrade_owners()
    base_id = 0
    max_level = 0
    max_item = 0
    for owner in owners:
        if not base_id:
            base_id = positive_id(_v218m_query(
                owner, 'ItemId2BaseLevelItem', item_id))
        if not max_level:
            max_level = positive_id(_v218m_query(
                owner, 'GetMaxLevel', item_id))
    if not base_id:
        base_id = item_id
    if max_level:
        for owner in owners:
            max_item = positive_id(_v218m_query(
                owner, 'GetItemIdByBaseItemIdAndLevel', base_id, max_level))
            if max_item:
                break
    if max_item:
        valid = False
        for owner in owners:
            mapped = positive_id(_v218m_query(
                owner, 'ItemId2BaseLevelItem', max_item))
            if mapped:
                valid = mapped == base_id
                break
        if not valid:
            max_item = 0
    result = (item_id, base_id, max_item, max_level)
    _V218A_UPGRADE_CACHE[(template_id, item_id)] = (now, result)
    return result


def feature_key(key):
    if isinstance(key, int) and not isinstance(key, bool):
        return True
    if not isinstance(key, str):
        return False
    lower = key.strip().lower()
    if lower.lstrip('-').isdigit():
        return True
    exact = {
        'feature', 'features', 'feature_list', 'feature_ids',
        'feature_mask', 'feature_bits', 'feature_flags', 'feature_data',
        'features_data', 'item_feature', 'item_features',
        'item_feature_list', 'item_feature_mask', 'upgrade_feature',
        'upgrade_features', 'upgrade_feature_list', 'upgrade_feature_mask',
        'gun_upgrade_feature', 'gun_upgrade_features',
    }
    if lower in exact:
        return True
    return ('feature' in lower and any(token in lower for token in
            ('mask', 'bits', 'flags', 'list', 'ids', 'data')))


def scalar_feature_row(value):
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, int):
        return True
    if isinstance(value, (list, tuple, set, frozenset)):
        return all(isinstance(item, (int, str)) and
                   not isinstance(item, bool) for item in value)
    return False


def copy_feature_storage(data, target_id, max_row):
    """Copy only authentic feature storage, preserving target identity rows."""
    if target_id is None or max_row is None:
        return 0, 'empty'
    target_row = _data_get(data, target_id, None)
    if scalar_feature_row(max_row):
        if target_row is not None and (
                scalar_feature_row(target_row) is False):
            return 0, 'feature-row-shape-mismatch'
        if target_row == max_row:
            return 0, type(max_row).__name__
        if _mapping_set(data, target_id, max_row):
            verified = _data_get(data, target_id, None) == max_row
            return (1 if verified else 0), type(max_row).__name__
        return 0, 'scalar-set-failed'
    if isinstance(max_row, (list, tuple, set, frozenset)):
        return 0, 'unsupported-sequence'
    entries = [(key, value) for key, value in _data_items(max_row)
               if feature_key(key)]
    if not entries:
        return 0, 'mapping-no-feature-storage'
    if target_row is None:
        target_row = {}
        if not _mapping_set(data, target_id, target_row):
            return 0, 'mapping-create-failed'
    changed = 0
    for key, value in entries:
        try:
            if _proto_get(target_row, key, None) == value:
                continue
            if _mapping_set(target_row, key, value) and \
                    _proto_get(target_row, key, None) == value:
                changed += 1
        except Exception:
            continue
    return changed, 'mapping:%s' % sorted(str(key) for key, _v in entries)[:24]


def propagate_native_features(skin_id):
    """Make direct item_feature_data checks see the REAL max feature row.

    gun_skin_util.IsV8ColorSetUnlocked and UpdateV8RaiseGraphVariable read
    item_feature_data directly; a GunUpgradeDataMgr hook cannot reach them.
    Only feature masks/lists/numeric feature entries are copied.  Identity,
    level, DLC/readiness and new-HUD fields are never copied here.
    """
    item_id, base_id, max_item, max_level = upgrade_state(skin_id)
    if not max_item:
        return 0
    try:
        module = sys.modules.get('gclient.data.item_feature_data') or \
            _import_module('gclient.data.item_feature_data')
        data = getattr(module, 'data', None) if module else None
        if data is None:
            return 0
        max_row = _data_get(data, max_item, None)
        if max_row is None:
            return 0
    except Exception:
        return 0
    total = 0
    details = {}
    for target in (item_id, base_id):
        if not target or target == max_item or target in details:
            continue
        try:
            changed, shape = copy_feature_storage(data, target, max_row)
            total += changed
            details[target] = (changed, shape)
        except Exception as exc:
            details[target] = (0, 'error:%r' % (exc,))
    signature = (skin_id, item_id, base_id, max_item, max_level,
                 repr(details), repr(max_row)[:240])
    _v218a_log(('native-feature-storage', signature),
               'native max features skin=%d item=%d base=%d max=%d level=%d '
               'changed=%d targets=%r max_type=%s max_brief=%s'
               % (skin_id, item_id, base_id, max_item, max_level, total,
                  details, type(max_row).__name__, repr(max_row)[:420]), 1)
    return total


# Extend the previous broadcast merge without altering its protected source.
previous_merge = _v218m_merge_skin


def merge_skin(skin_id):
    try:
        changed = list(previous_merge(skin_id) or [])
    except Exception as exc:
        changed = []
        _v218a_log(('previous-merge-error', skin_id, repr(exc)),
                   'previous merge skipped skin=%s: %r' % (skin_id, exc), 1)
    try:
        propagate_native_features(skin_id)
    except Exception as exc:
        _v218a_log(('native-feature-error', skin_id, repr(exc)),
                   'native feature propagation skipped skin=%s: %r'
                   % (skin_id, exc), 1)
    template_id, row = _v218a_template_row(skin_id)
    if row is None:
        return sorted(set(changed))
    values = {}
    sources = {}
    try:
        feature_rows = _v218m_feature_rows(template_id)
    except Exception:
        feature_rows = []
    for module_name, row_id, source in feature_rows:
        for field in _V218A_MAX_FX_FIELDS:
            try:
                value = _proto_get(source, field, None)
                valid = (value is True if field in _V218A_TRUE_FIELDS
                         else _fx_value_ok(value))
                if not valid or _proto_get(row, field, None) == value:
                    continue
                if _mapping_set(row, field, value):
                    values[field] = value
                    sources[field] = (module_name.rsplit('.', 1)[-1], row_id)
                    if field not in changed:
                        changed.append(field)
            except Exception:
                continue
    if values:
        try:
            info = WEP_SKIN_INFO.get(template_id)
            if isinstance(info, dict):
                info.update(values)
                WEP_SKIN_INFO[template_id] = info
        except Exception:
            pass
        _v218a_log(('max-allfx-merge', template_id,
                    tuple(sorted(values)), repr(values)[:240]),
                   'authentic max FX skin=%d fields=%r sources=%r values=%r'
                   % (template_id, sorted(values), sources,
                      {key: repr(value)[:160]
                       for key, value in values.items()}), 1)
    return sorted(set(changed))


_v218m_merge_skin = merge_skin


_V218A_HIT_MEMO = {}


def merge_for_hit(skin_id):
    # Do not repeat the full max-row audit/propagation for every bullet.
    now = time.time()
    if now - _V218A_HIT_MERGE_AT.get(skin_id, 0.0) < 2.0:
        return []
    _V218A_HIT_MERGE_AT[skin_id] = now
    return _v218m_merge_skin(skin_id)


# FX_ALWAYS_MIRROR: base set of FX field names mirrored onto weapon cases.
# Must exist at module scope so merge_for_hit's rebind below and
# _fx_mirror_case (equip) can read it without NameError. merge_for_hit
# extends it with _V218A_MAX_FX_FIELDS on first use.
FX_ALWAYS_MIRROR = ()


# The existing mirror now carries the complete authentic non-fire dye,
# inspection and death field set.  Its tracer/muzzle fields are unchanged.
FX_ALWAYS_MIRROR = tuple(dict.fromkeys(
    list(FX_ALWAYS_MIRROR) + sorted(_V218A_MAX_FX_FIELDS)))


def _v218a_hit_map(skin_id):
    _template_id, row = _v218a_template_row(skin_id)
    value = _proto_get(row, 'skin_hit_object_effect_id', None) \
        if row is not None else None
    entries = _data_items(value)
    if not entries:
        info = WEP_SKIN_INFO.get(skin_id) or {}
        value = info.get('skin_hit_object_effect_id') or \
            _skin_raw_field(info, 'skin_hit_object_effect_id')
        entries = _data_items(value)
    # Preserve every authentic material key and effect ID.  Never collapse
    # this mapping to one scalar and never borrow another skin's map.
    return dict(entries) if entries else None


def repair_hit_case(case, skin_id):
    if case is None or not skin_id:
        return []
    hit_map = _v218a_hit_map(skin_id)
    _template_id, row = _v218a_template_row(skin_id)
    changed = []
    if hit_map:
        # Exact field names observed on the real WeaponCase/MeleeCase runtime.
        for attr in ('skin_hit_object_effect_dict',
                     'dual_skin_hit_object_effect_dict'):
            if attr.startswith('dual_') and not hasattr(case, attr):
                continue
            if _set_case_attr(case, attr, dict(hit_map)):
                changed.append(attr)
        _set_case_attr(case, 'show_guise_hit_effect', True)
        _set_case_attr(case, 'show_hit_effect', True)
    if row is not None:
        # Native code reads these template references after its own refresh.
        _set_case_attr(case, 'guise_template_data', row)
        if hasattr(case, 'dual_guise_template_data'):
            _set_case_attr(case, 'dual_guise_template_data', row)
        replacement = _proto_get(row, 'skin_hit_object_effect_id_replace', None)
        if _fx_value_ok(replacement):
            _set_case_attr(case, 'skin_hit_object_effect_id_replace', replacement)
        for field in _V218A_TRUE_FIELDS:
            value = _proto_get(row, field, None)
            if value is True:
                _set_case_attr(case, field, True)
    if hit_map:
        # Pairicon4: preserve every real cache write, but do not perform one
        # synchronous diagnostic write for every distinct WeaponCase.  The
        # device log showed 133 such lines, including pickup bursts.  Match
        # the established native-refresh cadence: first two, then each 25th.
        count = _V218A_HIT_LOG_COUNTS.get(skin_id, 0) + 1
        _V218A_HIT_LOG_COUNTS[skin_id] = count
        if count <= 2 or count % 25 == 0:
            _v218a_log(('hit-case', skin_id, count),
                       'hit caches skin=%d cases=%d case=%d materials=%r '
                       'dual=%s values=%r'
                       % (skin_id, count, id(case),
                          sorted(hit_map, key=str),
                          'dual_skin_hit_object_effect_dict' in changed,
                          repr(hit_map)[:420]), 1)
    return changed


previous_mirror = _fx_mirror_case


def mirror_case(case, skin_id):
    mirrored = list(previous_mirror(case, skin_id) or [])
    try:
        for field in repair_hit_case(case, skin_id):
            if field not in mirrored:
                mirrored.append(field)
    except Exception as exc:
        _v218a_log(('hit-mirror-error', skin_id, repr(exc)),
                   'hit-cache mirror skipped skin=%s: %r' % (skin_id, exc), 1)
    return mirrored


_fx_mirror_case = mirror_case


def case_for_caster(caster, skin_id=0):
    owner = caster
    try:
        if owner is None or not callable(getattr(owner, 'GetCurWeapon', None)):
            get_local = globals().get('_local_combat_avatar')
            owner = get_local() if callable(get_local) else owner
        weapon = owner.GetCurWeapon() if owner is not None else None
        guid = getattr(weapon, 'guid', None) if weapon is not None else None
        get_case = getattr(owner, 'GetWeaponCase', None) \
            if owner is not None else None
        if guid and callable(get_case):
            case = get_case(guid)
            if case is not None:
                return case
        cases = _current_weapon_cases(owner)
        for case in cases:
            if skin_id and skin_id in (
                    getattr(case, '_treacky_skin_template_id', None),
                    getattr(case, 'guise_id', None),
                    getattr(case, 'skin_id', None)):
                return case
        return cases[0] if cases else None
    except Exception:
        return None


def prepare_hit(caster, hit_effect):
    if not sync_attrs.get('bSkinHack', False) or hit_effect is None:
        return 0, 0
    skin_id = _selected_skin_for_caster(caster)
    if not skin_id:
        return 0, 0
    merge_for_hit(skin_id)
    case = _mapping_get(hit_effect, 'weapon_case', None)
    if case is None:
        case = case_for_caster(caster, skin_id)
    if case is not None:
        repair_hit_case(case, skin_id)
        _mapping_set(hit_effect, 'weapon_case', case)
    material = _mapping_get(hit_effect, 'hit_material_type', None)
    hit_id = _selected_hit_effect_id(skin_id, material)
    if hit_id:
        if not _mapping_get(hit_effect, 'hit_effect_id', None):
            _mapping_set(hit_effect, 'hit_effect_id', hit_id)
        if not _mapping_get(hit_effect, 'extra_effect_id', None):
            _mapping_set(hit_effect, 'extra_effect_id', hit_id)
        _mapping_set(hit_effect, 'show_hit_effect', True)
        _mapping_set(hit_effect, 'show_guise_hit_effect', True)
    item_id = SKIN_TO_ITEM.get(skin_id) or \
        (WEP_SKIN_INFO.get(skin_id) or {}).get('lobby_item_id') or skin_id
    for field, value in (
            ('guise_id', skin_id), ('guise_template_id', skin_id),
            ('skin_id', skin_id), ('guise_item_id', item_id),
            ('skin_item_id', item_id)):
        if not _mapping_get(hit_effect, field, None):
            _mapping_set(hit_effect, field, value)
    hit_map = _v218a_hit_map(skin_id)
    if hit_map:
        _mapping_set(hit_effect, 'skin_hit_object_effect_dict', hit_map)
    _template_id, row = _v218a_template_row(skin_id)
    replacement = _proto_get(row, 'skin_hit_object_effect_id_replace', None) \
        if row is not None else None
    if _fx_value_ok(replacement):
        _mapping_set(hit_effect, 'skin_hit_object_effect_id_replace', replacement)
    _v218a_log(('hit-final', skin_id, _safe_int(material, -1),
                repr(_mapping_keys(hit_effect))),
               'final hit skin=%d material=%r id=%r primary=%r extra=%r '
               'case=%s cache=%s flags=%r/%r keys=%r'
               % (skin_id, material, hit_id,
                  _mapping_get(hit_effect, 'hit_effect_id', None),
                  _mapping_get(hit_effect, 'extra_effect_id', None),
                  case is not None, bool(hit_map),
                  _mapping_get(hit_effect, 'show_hit_effect', None),
                  _mapping_get(hit_effect, 'show_guise_hit_effect', None),
                  _mapping_keys(hit_effect)), 1)
    return skin_id, hit_id


def wrap_hit_module(module, name):
    guard = '_orig_v218a_' + name
    try:
        if module is None or guard in vars(module):
            return 0
        previous = getattr(module, name, None)
        if not callable(previous):
            return 0
        if name == 'PlayHitEffect':
            def wrapper(caster, spell_id, hit_effect, is_immune=False,
                        heirloom_color=None, *args, **kwargs):
                original_case = None
                original_case_key = False
                transient_case = None
                try:
                    original_case = _mapping_get(
                        hit_effect, 'weapon_case', None)
                    original_case_key = (
                        'weapon_case' in _mapping_keys(hit_effect))
                    prepare_hit(caster, hit_effect)
                    if original_case is None:
                        transient_case = _mapping_get(
                            hit_effect, 'weapon_case', None)
                except Exception as exc:
                    _v218a_log(('hit-final-error', repr(exc)),
                               'final hit preparation skipped: %r' % (exc,), 1)
                try:
                    return previous(caster, spell_id, hit_effect, is_immune,
                                    heirloom_color, *args, **kwargs)
                finally:
                    # PlayHitEffect shares its dictionary with the later
                    # spell-result RPC. A live WeaponCase is valid while the
                    # native visual routine runs, but AsioServerProxy cannot
                    # serialize it. v10.1-v10.6 device logs show the repeated
                    # TickDealSpellResultRpc failure after this wrapper.
                    # Restore the caller's original key/value immediately;
                    # never suppress the RPC exception or rewrite the RPC.
                    try:
                        if (original_case is None
                                and transient_case is not None
                                and _mapping_get(hit_effect, 'weapon_case', None)
                                is transient_case):
                            restored = False
                            if original_case_key:
                                restored = _mapping_set(
                                    hit_effect, 'weapon_case', original_case)
                            else:
                                try:
                                    del hit_effect['weapon_case']
                                    restored = True
                                except Exception:
                                    pass
                                if not restored:
                                    try:
                                        hit_effect.pop('weapon_case')
                                        restored = True
                                    except Exception:
                                        pass
                                if not restored:
                                    try:
                                        delattr(hit_effect, 'weapon_case')
                                        restored = True
                                    except Exception:
                                        pass
                            if restored:
                                _v218a_log(
                                    'hit-transient-case-restored',
                                    'transient hit WeaponCase restored after '
                                    'native visual; RPC payload preserved', 1)
                    except Exception:
                        pass
        else:
            def wrapper(target, hit_pos, hit_normal, hit_material_type,
                        hit_dir, caster, weapon_id, effect_id=0,
                        extra_effect_id=None, heirloom_color=None,
                        *args, **kwargs):
                try:
                    if sync_attrs.get('bSkinHack', False):
                        skin_id = _selected_skin_for_caster(caster)
                        if skin_id:
                            case = case_for_caster(caster, skin_id)
                            # v2.97: the per-hit memo lives HERE (the lag
                            # fix) - the merge/repair functions stay pure
                            # so the melee visual callers keep their real
                            # change lists.  One merge/repair per
                            # (case, skin) per 30s.
                            _hk = (id(case), skin_id)
                            _now = time.time()
                            if _now - _V218A_HIT_MEMO.get(_hk, 0.0) > 30.0:
                                if len(_V218A_HIT_MEMO) > 512:
                                    _V218A_HIT_MEMO.clear()
                                _V218A_HIT_MEMO[_hk] = _now
                                merge_for_hit(skin_id)
                                repair_hit_case(case, skin_id)
                            hit_id = _selected_hit_effect_id(
                                skin_id, hit_material_type)
                            if hit_id and not extra_effect_id:
                                extra_effect_id = hit_id
                except Exception as exc:
                    _v218a_log(('hit-wrapper-error', repr(exc)),
                               'hit wrapper preparation skipped: %r' % (exc,), 1)
                return previous(target, hit_pos, hit_normal, hit_material_type,
                                hit_dir, caster, weapon_id, effect_id,
                                extra_effect_id, heirloom_color, *args, **kwargs)
        wrapper.hit_hook = True
        setattr(module, guard, previous)
        setattr(module, name, wrapper)
        patched = 1
        # Patch aliases imported before this layer, preserving the original
        # call chain in every combat/effect/spell/weapon module.
        for mod_name, other in list(sys.modules.items()):
            if other is None or other is module:
                continue
            if not any(token in str(mod_name).lower() for token in
                       ('combat', 'effect', 'spell', 'weapon')):
                continue
            try:
                if getattr(other, name, None) is previous:
                    setattr(other, name, wrapper)
                    patched += 1
            except Exception:
                pass
        raw = getattr(module, '_treacky_orig_' + name, None)
        if callable(raw):
            log_code_contract(raw, 'allfx-' + name)
        _v218a_log(('hit-hook', name, patched),
                   '%s final hook installed aliases=%d' % (name, patched), 1)
        return patched
    except Exception as exc:
        _v218a_log(('hit-hook-error', name, repr(exc)),
                   '%s hook skipped: %r' % (name, exc), 1)
        return 0


def install_hit_hooks():
    if not _weaponfx_effect_hooks_installed[0]:
        return 0
    try:
        module = _import_module('gshare.effect_util')
    except Exception:
        return 0
    installed = 0
    for name in ('WrapperHitEffectResult', 'PlayHitEffect'):
        installed += int(bool(wrap_hit_module(module, name)))
    return installed


previous_effect_install = _install_effect_util_hooks


def install_effect_util_hooks():
    result = previous_effect_install()
    if result:
        install_hit_hooks()
    return result


_install_effect_util_hooks = install_effect_util_hooks


def refresh_case(case, skin_id):
    if case is None or not skin_id or not sync_attrs.get('bSkinHack', False):
        return []
    _v218m_merge_skin(skin_id)
    repair_hit_case(case, skin_id)
    item_id, base_id, max_item, max_level = upgrade_state(skin_id)
    if max_level:
        _set_case_attr(case, 'upgrade_level', max_level)
    if max_item:
        # Derived from the game's real level mapping, not a fabricated asset.
        _set_case_attr(case, 'is_best_skin', True)
    signature = (skin_id, item_id, base_id, max_item, max_level)
    now = time.time()
    previous = _V218A_REFRESH_STATE.get(id(case))
    if previous and previous[0] == signature and now - previous[1] < 2.0:
        return []
    _V218A_REFRESH_STATE[id(case)] = (signature, now)
    called = []
    errors = []
    # This is the real native cache used by direct WeaponCase feature gates.
    _call_case_method(case, '_RefreshFeatureCache', called=called, errors=errors)
    try:
        static = inspect.getattr_static(type(case), '_RefreshFeatureCache')
        function = static.__func__ if isinstance(
            static, (staticmethod, classmethod)) else static
        if callable(function):
            log_code_contract(function, 'case-refresh-feature-cache')
    except Exception:
        pass
    # pairicon2: the core apply path has already run RefreshGuiseEffect,
    # RefreshGuise3PEffectInCombat, and ShowWeaponBodyEffectVisible.  Do not
    # repeat those three native calls in this post-apply layer.  Additional
    # feature/inspection/animation/optic consumers retain their contracts;
    # confirmed tracer and muzzle paths are not re-triggered here.
    for method in (
            'RefreshInspectExtraModel',
            'RefreshSkinInspectPlaybackSpeedForWeapon'):
        _call_case_method(case, method, called=called, errors=errors)
    # v2.124: these three errored on EVERY device call (best=False). Run
    # them only once the case reports its parts loaded, try the alternate
    # call shapes, and defer otherwise instead of failing forever.
    _parts24 = True
    try:
        _chk24 = getattr(case, 'IsAllPartsModelLoaded', None)
        if callable(_chk24):
            _parts24 = bool(_chk24())
    except Exception:
        _parts24 = True
    if _parts24:
        for method, shapes in (
                ('RefreshGuiseSkinAnimPoseForWeapon', ((),)),
                ('RefreshOpticEffect', ((),)),
                ('_ApplyGuiseSkinAnimNameVariables', ((), ({},)))):
            _ok24 = False
            for shape in shapes:
                try:
                    getattr(case, method)(*shape)
                    _ok24 = True
                    break
                except Exception:
                    continue
            if _ok24:
                called.append(method + '=ok')
            else:
                errors.append(method + '=shape')
    else:
        errors.append('parts-not-loaded=deferred')
    if getattr(case, 'dual_guise_id', None):
        _call_case_method(case, 'RefreshGuiseSkinAnimPoseForDualWeapon',
                          called=called, errors=errors)
    # Bounded compact evidence: _plog performs synchronous file I/O, so a new
    # case must not produce a large cache/error dump on every weapon event.
    refresh_count = _V218A_REFRESH_LOG_COUNTS.get(skin_id, 0) + 1
    _V218A_REFRESH_LOG_COUNTS[skin_id] = refresh_count
    if refresh_count <= 2 or refresh_count % 25 == 0:
        _v218a_log(('case-refresh', skin_id, refresh_count),
                   'native case refresh skin=%d cases=%d called=%r errors=%r '
                   'best=%r'
                   % (skin_id, refresh_count, called,
                      [item.split('=', 1)[0] for item in errors[:4]],
                      getattr(case, 'is_best_skin', None)), 1)
    audit_skin(skin_id, case)
    return called


previous_apply = _apply_weapon_case_skin


def apply_weapon_case_skin(case, equip_id, forced_skin,
                                  reason='apply', force=False):
    # pairicon2: a True result can mean the core declined duplicate work because
    # this exact case/equip/skin was already applied.  Only a changed apply map
    # (or an explicit force) represents work that needs the post-apply refresh.
    before = _weaponfx_applied.get(id(case))
    result = previous_apply(case, equip_id, forced_skin, reason, force)
    try:
        if result and sync_attrs.get('bSkinHack', False):
            after = _weaponfx_applied.get(id(case))
            if force or before != after:
                refresh_case(case, forced_skin)
    except Exception as exc:
        _v218a_log(('case-refresh-error', forced_skin, repr(exc)),
                   'native case refresh skipped skin=%s: %r'
                   % (forced_skin, exc), 1)
    return result


_apply_weapon_case_skin = apply_weapon_case_skin


# Broaden ONLY feature classification/predicates.  Numeric feature IDs still
# come from loaded game enums, and activation still requires an authentic
# selected-skin field.  Direct item_feature_data gates were repaired above.
previous_feature_kinds = _v842g_feature_kinds


def feature_kinds(name):
    kinds = list(previous_feature_kinds(name))
    upper = str(name).upper()

    def add(kind):
        if kind not in kinds:
            kinds.append(kind)

    if 'HIT' in upper and any(token in upper for token in
                              ('EFFECT', 'FX', 'OBJECT')):
        add('hit')
    if 'INSPECT' in upper:
        add('inspection')
    if 'RAISE' in upper:
        add('raise')
    if (any(token in upper for token in ('DEATH', 'DEAD', 'DIE'))
            and any(token in upper for token in
                    ('EFFECT', 'FX', 'ANIM', 'ACTION', 'POSE'))):
        add('death')
    if 'OPTIC' in upper and any(token in upper for token in ('EFFECT', 'FX')):
        add('optic')
    if 'COLOR_SET' in upper or 'COLOUR_SET' in upper:
        add('color')
    return tuple(kinds)


_v842g_feature_kinds = feature_kinds
previous_record_supports = _v842g_record_supports


def record_supports(record, kind):
    if kind in ('tracer', 'broadcast'):
        return previous_record_supports(record, kind)
    fields = _V218A_FEATURE_FIELDS.get(kind, ())
    info = record[3]
    return any(info_value(info, field) is not None for field in fields)


_v842g_record_supports = record_supports
try:
    feature_cache.update({'sig': None, 'features': {}})
except Exception:
    pass


# Complete authentic death data at the established final death-info copy.
previous_copy = globals().get('_copy_skin_kill_broadcast_data')


def copy_all_fx(info, skin_id):
    result = (previous_copy(info, skin_id)
              if callable(previous_copy) else None)
    try:
        if info is not None and any(_mapping_get(info, key, None) is not None
                for key in ('bullet_data_id', 'hit_pos', 'target_pos',
                            'hit_part', 'damage')):
            _template_id, row = _v218a_template_row(skin_id)
            copied = []
            for field in _V218A_DEATH_FIELDS:
                value = _proto_get(row, field, None) if row is not None else None
                if _fx_value_ok(value) and _mapping_set(info, field, value):
                    copied.append(field)
            if copied:
                _v218a_log(('death-final', skin_id, tuple(copied)),
                           'final death FX skin=%d fields=%r values=%r'
                           % (skin_id, copied,
                              {field: repr(_mapping_get(info, field, None))[:160]
                               for field in copied}), 1)
    except Exception as exc:
        _v218a_log(('death-final-error', skin_id, repr(exc)),
                   'final death FX copy skipped skin=%s: %r' % (skin_id, exc), 1)
    return result


_copy_skin_kill_broadcast_data = copy_all_fx


# Some game builds expose panel_kill.Push as an instance attribute rather
# than a class function.  Keep the class hook, but add an authentic bound-
# method fallback instead of silently returning zero in that shape.
previous_panel_install = _v218m_install_panel


def wrap_panel_instance(panel):
    if panel is None or isinstance(panel, type):
        return 0
    try:
        storage = vars(panel)
    except Exception:
        storage = {}
    guard = '_orig_v218a_panel_push'
    if guard in storage:
        return 1
    previous = getattr(panel, 'Push', None)
    if not callable(previous):
        return 0

    def wrapper(*args, **kwargs):
        # previous is already bound; args[0] is the kill info mapping.
        return _v218m_panel_invoke(previous, args, kwargs, False)

    try:
        setattr(panel, guard, previous)
        setattr(panel, 'Push', wrapper)
    except Exception:
        return 0
    try:
        log_code_contract(previous, 'panel-push-instance')
    except Exception:
        pass
    _v218a_log(('panel-instance', type(panel)),
               'panel_kill instance Push hooked class=%s'
               % type(panel).__name__, 1)
    return 1


def install_panel():
    if not sync_attrs.get('bSkinHack', False):
        return 0
    installed = previous_panel_install()
    try:
        game_genv = _game_genv()
        player = getattr(game_genv, 'player', None) if game_genv else None
        panel = getattr(player, 'panel_kill', None) if player else None
        # An instance-owned Push shadows an already-hooked class method.
        if panel is not None and 'Push' in vars(panel):
            return wrap_panel_instance(panel)
        if installed:
            return installed
        return wrap_panel_instance(panel)
    except Exception:
        return 0


_v218m_install_panel = install_panel


def _v218a_brief(value, limit=260):
    try:
        text = repr(value)
    except Exception:
        text = '<unrepresentable>'
    return text if len(text) <= limit else text[:limit - 3] + '...'


def effect_audit(skin_id, row):
    """Bounded config evidence for the selected skin's own hit/death IDs."""
    ids = []
    for field in ('skin_hit_object_effect_id', 'skin_hit_object_effect_id_replace',
                  'kill_fx', 'team_dead_fx', 'dlc_effects'):
        value = _proto_get(row, field, None)
        candidates = [item for _key, item in _data_items(value)]
        if isinstance(value, (list, tuple, set, frozenset)):
            candidates.extend(value)
        elif isinstance(value, int) and not isinstance(value, bool):
            candidates.append(value)
        for candidate in candidates:
            number = positive_id(candidate)
            if number and number not in ids:
                ids.append(number)
    if not ids:
        return
    try:
        module = sys.modules.get('gclient.data.effect_data') or \
            _import_module('gclient.data.effect_data')
        data = getattr(module, 'data', None) if module else None
    except Exception:
        data = None
    brief = []
    for effect_id in ids[:16]:
        effect_row = _data_get(data, effect_id, None) if data is not None else None
        if effect_row is None:
            brief.append((effect_id, 'NO effect_data ROW'))
            continue
        values = {}
        for key, value in _data_items(effect_row):
            lower = str(key).lower()
            if (lower == 'id' or any(token in lower for token in
                    ('path', 'effect', 'resource', 'dlc'))) and \
                    isinstance(value, (str, int, float, bool, tuple, list)):
                values[str(key)] = _v218a_brief(value, 120)
            if len(values) >= 16:
                break
        brief.append((effect_id, type(effect_row).__name__, values,
                      _mapping_keys(effect_row, 28)))
    _v218a_log(('effect-config-audit', skin_id, tuple(ids[:16]), repr(brief)),
               'effect config skin=%d ids=%r rows=%r'
               % (skin_id, ids[:16], brief), 1)


def audit_skin(skin_id, case=None):
    """One bounded, full-FX audit per skin/case; never a visual success claim."""
    # optimized1: auditing must not add table walks and large synchronous writes
    # to every native case refresh. Real refresh/merge calls above are unchanged.
    if not _V841PERF_AUTO_DIAGNOSTICS or not _debug_log_on():
        return
    template_id, row = _v218a_template_row(skin_id)
    if row is None:
        return
    key = (template_id, id(case) if case is not None else 0)
    if key in _V218A_AUDIT_SEEN:
        return
    _V218A_AUDIT_SEEN.add(key)
    state = upgrade_state(template_id)
    audit_fields = tuple(dict.fromkeys(
        list(_V218M_LEGACY_BROADCAST_FIELDS) +
        sorted(_V218A_MAX_FX_FIELDS) + [
            'fps_tracer_bullet_id', 'fps_adstracer_bullet_id',
            'fps_simple_tracer_bullet_id', 'fps_simple_adstracer_bullet_id',
            'tps_tracer_bullet_id', 'tps_simple_tracer_bullet_id',
            'extra_ballistic_tracer_bullet_id', 'skin_fire_sfx_id_replace',
            'skin_fire_ads_sfx_id_replace',
        ]))
    values = {}
    for field in audit_fields:
        value = _proto_get(row, field, None)
        if value is not None:
            values[field] = _v218a_brief(value)
    feature_brief = []
    try:
        module = sys.modules.get('gclient.data.item_feature_data')
        data = getattr(module, 'data', None) if module else None
        for row_id in tuple(dict.fromkeys(
                value for value in state[:3] if value)):
            feature_row = _data_get(data, row_id, None) \
                if data is not None else None
            feature_brief.append((row_id, type(feature_row).__name__,
                                  _v218a_brief(feature_row, 520)))
    except Exception as exc:
        feature_brief.append(('error', repr(exc)))
    try:
        features = feature_map()
    except Exception:
        features = {}
    case_brief = None
    if case is not None:
        case_brief = {
            'guise_id': getattr(case, 'guise_id', None),
            'guise_item_id': getattr(case, 'guise_item_id', None),
            'upgrade_level': getattr(case, 'upgrade_level', None),
            'is_best_skin': getattr(case, 'is_best_skin', None),
            'show_hit_effect': getattr(case, 'show_hit_effect', None),
            'show_guise_hit_effect': getattr(case, 'show_guise_hit_effect', None),
            'hit_cache': _v218a_brief(
                getattr(case, 'skin_hit_object_effect_dict', None), 360),
            'dual_hit_cache': _v218a_brief(
                getattr(case, 'dual_skin_hit_object_effect_dict', None), 360),
            'is_v8_raise_unlocked': getattr(case, 'is_v8_raise_unlocked', None),
            'is_v8_raise': getattr(case, 'is_v8_raise', None),
        }
    _v218a_log(('full-audit', key, repr(values), repr(feature_brief)),
               'FULL FX AUDIT skin=%d item/base/max/level=%r\n'
               'template=%r\nitem_feature=%r\nfeature_enum=%r\ncase=%r'
               % (template_id, state, values, feature_brief, features, case_brief), 1)
    try:
        effect_audit(template_id, row)
    except Exception as exc:
        _v218a_log(('effect-audit-error', template_id, repr(exc)),
                   'effect config audit skipped skin=%d: %r'
                   % (template_id, exc), 1)


# Install on the already-active effect hooks now; the wrapped installer above
# repeats this safely if gshare.effect_util loads later.
try:
    install_hit_hooks()
except Exception:
    pass

_plog('[V218A] full authentic max-FX layer ready: native features + hit caches/context + panel + death + inspection/optic')


# ============================================================
# v2.18-killcast: exact game-module panel_kill bridge
# ============================================================
# Broadcast-only.  Log 14 proved that the record was enriched, but the panel
# installer never found a panel.  The original PushKillRecord function keeps
# the authoritative `genv` in ITS module globals; searching the payload's
# globals can select a different object.  Resolve only that original context.
_v218kbc_local = threading.local()
_v218kbc_log_seen = {}
log_total = [0]


def _v218kbc_log(key, message, limit=2):
    try:
        marker = (key, limit)
        count = _v218kbc_log_seen.get(marker, 0)
        if count >= limit or log_total[0] >= 180:
            return
        _v218kbc_log_seen[marker] = count + 1
        log_total[0] += 1
        _plog('[KBCONLY] ' + message)
    except Exception:
        pass


def _v218kbc_context():
    ctx = getattr(_v218kbc_local, 'value', None)
    if ctx is None:
        ctx = {}
        _v218kbc_local.value = ctx
    return ctx


def raw_record(cls):
    try:
        for base in getattr(cls, '__mro__', (cls,)):
            raw = vars(base).get('_actual_skin_original_push_kill_record')
            if not callable(raw):
                continue
            if not hasattr(raw, '__globals__'):
                raw = getattr(raw, '__func__', raw)
            return raw
    except Exception:
        pass
    return None


def _v218kbc_prepare(cls, raw_hint=None):
    ctx = _v218kbc_context()
    raw = raw_hint if callable(raw_hint) else raw_record(cls)
    namespace = getattr(raw, '__globals__', None)
    module_name = getattr(raw, '__module__', '') if raw is not None else ''
    module = sys.modules.get(module_name) if module_name else None
    if module is None:
        module = sys.modules.get(
            'gclient.gameplay.uicomponents.hud_killrecord_comp')
    if not isinstance(namespace, dict):
        namespace = getattr(module, '__dict__', {})
    game_genv = namespace.get('genv')
    if game_genv is None and module is not None:
        game_genv = getattr(module, 'genv', None)
    player = getattr(game_genv, 'player', None) if game_genv is not None else None
    panel = getattr(player, 'panel_kill', None) if player is not None else None
    ctx.update({'cls': cls, 'raw': raw, 'genv': game_genv,
                'player': player, 'panel': panel})
    if panel is None:
        try:
            kill_apis = [name for name in dir(player)
                         if 'kill' in name.lower()][:24] if player is not None else []
        except Exception:
            kill_apis = []
        _v218kbc_log(
            ('missing', cls, type(game_genv), type(player), tuple(kill_apis)),
            'exact panel unavailable class=%s raw=%s genv=%s player=%s player_kill_apis=%r'
            % (getattr(cls, '__name__', repr(cls)),
               ('%s.%s' % (module_name, getattr(raw, '__name__', '?')))
               if raw is not None else None,
               type(game_genv).__name__ if game_genv is not None else None,
               type(player).__name__ if player is not None else None,
               kill_apis), 2)
    return panel


def hook_panel(panel):
    if panel is None:
        return 0
    class_result = 0
    instance_result = 0
    own_push = False
    if isinstance(panel, type):
        class_result = wrap_panel_class(panel)
    else:
        class_result = wrap_panel_class(type(panel))
        try:
            own_push = 'Push' in vars(panel)
        except Exception:
            own_push = False
        if own_push or not class_result:
            instance_result = wrap_panel_instance(panel)
    installed = int(bool(class_result or instance_result))
    cls = panel if isinstance(panel, type) else type(panel)
    if installed:
        _v218kbc_log(
            ('installed', cls, own_push),
            'exact game genv panel hooked class=%s module=%s class_hook=%s instance_hook=%s own_Push=%s'
            % (cls.__name__, getattr(cls, '__module__', ''),
               bool(class_result), bool(instance_result), own_push), 2)
    else:
        _v218kbc_log(
            ('not-callable', cls, own_push),
            'exact panel found but Push was not hookable class=%s module=%s own_Push=%s'
            % (cls.__name__, getattr(cls, '__module__', ''), own_push), 2)
    return installed


install_candidate = _v218m_install_panel
_v218kbc_previous_install = getattr(
    install_candidate, '_v218kbc_original',
    install_candidate)


def _v218kbc_install_panel():
    if not sync_attrs.get('bSkinHack', False):
        return 0
    ctx = _v218kbc_context()
    if ctx.get('active'):
        panel = ctx.get('panel')
        if panel is None and ctx.get('cls') is not None:
            panel = _v218kbc_prepare(ctx.get('cls'), ctx.get('raw'))
        if panel is None:
            return 0
        try:
            return hook_panel(panel)
        except Exception as exc:
            _v218kbc_log(('install-error', repr(exc)),
                         'exact panel install failed: %r' % (exc,), 2)
            return 0
    # Preserve the established installer for calls outside a kill record.
    try:
        return _v218kbc_previous_install()
    except Exception:
        return 0


_v218kbc_install_panel._v218kbc_original = _v218kbc_previous_install
_v218m_install_panel = _v218kbc_install_panel


def wrap_record_class(cls):
    if cls is None:
        return 0
    guard = '_orig_v218kbc_push_kill_record'
    try:
        if guard in vars(cls):
            return 1
        static = inspect.getattr_static(cls, 'PushKillRecord')
        previous = (static.__func__ if isinstance(
            static, (staticmethod, classmethod)) else static)
        if not callable(previous):
            return 0
        raw = raw_record(cls)
        has_subject = not isinstance(static, staticmethod)

        def wrapper(*args, **kwargs):
            info = kwargs.get('info')
            index = 1 if has_subject else 0
            if info is None and len(args) > index:
                info = args[index]
            owner = args[0] if has_subject and args else cls
            record_cls = (type(owner) if has_subject and not isinstance(owner, type)
                          else owner if isinstance(owner, type) else cls)
            if not sync_attrs.get('bSkinHack', False) or info is None:
                return previous(*args, **kwargs)
            ctx = _v218kbc_context()
            old = dict(ctx)
            try:
                ctx['active'] = True
                _v218kbc_prepare(record_cls, raw)
                _v218kbc_install_panel()
                # The established wrapper still performs all record enrichment;
                # this bridge neither rewrites the record nor calls the game raw.
                return previous(*args, **kwargs)
            finally:
                ctx.clear()
                ctx.update(old)

        setattr(cls, guard, previous)
        if isinstance(static, staticmethod):
            setattr(cls, 'PushKillRecord', staticmethod(wrapper))
        elif isinstance(static, classmethod):
            setattr(cls, 'PushKillRecord', classmethod(wrapper))
        else:
            setattr(cls, 'PushKillRecord', wrapper)
        _v218kbc_log(
            ('record-bridge', cls),
            'record bridge installed class=%s raw=%s'
            % (cls.__name__,
               ('%s.%s' % (getattr(raw, '__module__', ''),
                           getattr(raw, '__name__', '?')))
               if raw is not None else None), 1)
        return 1
    except Exception as exc:
        _v218kbc_log(('record-error', cls, repr(exc)),
                     'record bridge skipped class=%s: %r'
                     % (getattr(cls, '__name__', repr(cls)), exc), 1)
        return 0


def install_records():
    module = sys.modules.get(
        'gclient.gameplay.uicomponents.hud_killrecord_comp')
    if module is None:
        return 0
    installed = 0
    for name in ('HudKillRecordComp', 'HudKillRecordCompPC', 'HudKillRecordCompV2'):
        installed += int(bool(wrap_record_class(
            getattr(module, name, None))))
    return installed


refresh_candidate = globals().get('_v842g_refresh_kill_feed')
previous_refresh = getattr(
    refresh_candidate, '_v218kbc_original',
    refresh_candidate)


def refresh_kill_feed():
    result = (previous_refresh()
              if callable(previous_refresh) else 0)
    try:
        install_records()
    except Exception:
        pass
    return result


if callable(previous_refresh):
    refresh_kill_feed._v218kbc_original = previous_refresh
    _v842g_refresh_kill_feed = refresh_kill_feed


# Independent bounded evidence that the exact panel was entered and returned.
invoke_candidate = _v218m_panel_invoke
previous_invoke = getattr(
    invoke_candidate, '_v218kbc_original',
    invoke_candidate)


def panel_invoke(previous, args, kwargs, has_subject):
    info = kwargs.get('info')
    if info is None:
        index = 1 if has_subject else 0
        if len(args) > index:
            info = args[index]
    try:
        brief = panel_brief(info) if info is not None else None
    except Exception:
        brief = None
    key = (getattr(previous, '__module__', ''),
           getattr(previous, '__name__', '?'), repr(brief))
    _v218kbc_log(('push-enter', key),
                 'panel Push enter raw=%s.%s info_type=%s values=%r'
                 % (key[0], key[1], type(info).__name__ if info is not None else None,
                    brief), 2)
    try:
        result = previous_invoke(previous, args, kwargs, has_subject)
    except Exception as exc:
        _v218kbc_log(('push-error', key, repr(exc)),
                     'panel Push raised raw=%s.%s error=%r'
                     % (key[0], key[1], exc), 2)
        raise
    _v218kbc_log(('push-return', key, type(result).__name__),
                 'panel Push return raw=%s.%s result=%s'
                 % (key[0], key[1], repr(result)[:160]), 2)
    return result


panel_invoke._v218kbc_original = previous_invoke
_v218m_panel_invoke = panel_invoke

try:
    install_records()
except Exception:
    pass

_plog('[KBCONLY] exact original-module genv kill-broadcast bridge ready')

# ---------------------------------------------------------------------------
# Live panel recovery for the authentic kill broadcast.  This is deliberately
# independent of the model/FX paths: it only discovers PanelKill.Push, observes
# whether the game's record path called it, and supplies the same authentic
# enriched record for a confirmed local kill when that call was skipped.
# ---------------------------------------------------------------------------
_v218bc2_log_seen = {}
_v218bc2_calls = [0]
_v218bc2_gc_done = [False]
_v218bc2_panel_cache = [None]


def _v218bc2_log(key, text):
    try:
        count = _v218bc2_log_seen.get(key, 0)
        if count < 4:
            _plog('[BC2] %s %s' % (key, text))
        _v218bc2_log_seen[key] = count + 1
    except Exception:
        pass


def _v218bc2_panel(value, hint=''):
    if value is None or isinstance(value, type):
        return None
    try:
        push = getattr(value, 'Push', None)
        if not callable(push):
            return None
        cls = type(value)
        ident = ('%s.%s %s' % (getattr(cls, '__module__', ''),
                               getattr(cls, '__name__', ''), hint)).lower()
        if 'kill' in ident and ('panel' in ident or 'hud' in ident):
            return value
    except Exception:
        pass
    return None


def _v218bc2_cache_panel(panel):
    if panel is None:
        return None
    try:
        _v218bc2_panel_cache[0] = weakref.ref(panel)
    except Exception:
        # Some engine UI proxies are not weak-referenceable.  Keep only this
        # one authentic panel, never a collection of scene objects.
        _v218bc2_panel_cache[0] = panel
    return panel


def _v218bc2_cached_panel():
    value = _v218bc2_panel_cache[0]
    if value is None:
        return None
    try:
        panel = value() if isinstance(value, weakref.ref) else value
        if panel is not None and _v218bc2_panel(panel, 'cached.panel_kill') is not None:
            return panel
    except Exception:
        pass
    _v218bc2_panel_cache[0] = None
    return None


def _v218bc2_roots(record_owner):
    roots = [(record_owner, 'record')]
    try:
        roots.append((Space._instance, 'Space'))
    except Exception:
        pass
    try:
        roots.append((_local_combat_avatar(), 'local_avatar'))
    except Exception:
        pass
    try:
        cls = (record_owner if isinstance(record_owner, type)
               else type(record_owner))
        raw = raw_record(cls)
    except Exception:
        raw = None
    if raw is not None:
        try:
            namespace = getattr(raw, '__globals__', {})
            roots.append((namespace.get('genv'), 'raw_globals.genv'))
            builtins = namespace.get('__builtins__')
            if isinstance(builtins, dict):
                roots.append((builtins.get('genv'), 'raw_builtins.genv'))
            else:
                roots.append((getattr(builtins, 'genv', None),
                              'raw_builtins.genv'))
            module = sys.modules.get(getattr(raw, '__module__', ''))
            roots.append((module, 'raw_module'))
            if module is not None:
                roots.append((getattr(module, 'genv', None),
                              'raw_module.genv'))
        except Exception:
            pass
    try:
        roots.append((_game_genv(), 'module_genv'))
    except Exception:
        pass
    try:
        for name, module in list(sys.modules.items()):
            if name == 'genv' or name.endswith('.genv'):
                roots.append((module, name))
    except Exception:
        pass
    try:
        roots.append((sys.modules.get(
            'gclient.gameplay.uicomponents.hud_killrecord_comp'),
            'killrecord_module'))
    except Exception:
        pass
    return roots


def _v218bc2_walk_panel(record_owner):
    attrs = ('player', 'main_player', 'avatar', 'combat_avatar', 'owner',
             'space', 'ui', 'ui_manager', 'hud', 'hud_manager', 'panel',
             'panel_kill', '_panel_kill', 'kill_panel', '_player', '_owner',
             '_space', '_avatar')
    queue = []
    seen = set()
    for root, path in _v218bc2_roots(record_owner):
        if root is not None and id(root) not in seen:
            seen.add(id(root))
            queue.append((root, path, 0))
    pos = 0
    while pos < len(queue) and pos < 128:
        value, path, depth = queue[pos]
        pos += 1
        panel = _v218bc2_panel(value, path)
        if panel is not None:
            _v218bc2_log('panel-found', 'path=%s type=%s' %
                         (path, type(value).__name__))
            return panel
        if depth >= 5 or isinstance(value, (str, bytes, int, float, bool,
                                            tuple, list, dict, set)):
            continue
        for attr in attrs:
            try:
                child = getattr(value, attr, None)
            except Exception:
                continue
            if child is None or id(child) in seen:
                continue
            seen.add(id(child))
            queue.append((child, path + '.' + attr, depth + 1))
            if len(queue) >= 128:
                break
    return None


def _v218bc2_gc_panel():
    # One bounded recovery scan, only after a local enriched record and only
    # when every authentic owner root failed.  Filter class/module identity
    # before reading Push so unrelated dynamic properties are never invoked.
    if _v218bc2_gc_done[0]:
        return None
    _v218bc2_gc_done[0] = True
    candidates = []
    scanned = 0
    try:
        import gc
        for value in gc.get_objects():
            scanned += 1
            try:
                if isinstance(value, type):
                    continue
                cls = type(value)
                ident = ('%s.%s' % (getattr(cls, '__module__', ''),
                                    getattr(cls, '__name__', ''))).lower()
                if 'kill' not in ident or ('panel' not in ident and
                                           'hud' not in ident):
                    continue
                if len(candidates) < 20:
                    candidates.append(ident)
                panel = _v218bc2_panel(value)
                if panel is not None:
                    _v218bc2_log('gc-panel', 'type=%s scanned=%d' %
                                 (ident, scanned))
                    return panel
            except Exception:
                continue
    except Exception as exc:
        _v218bc2_log('gc-error', repr(exc))
    _v218bc2_log('gc-miss', 'scanned=%d candidates=%s' %
                 (scanned, ','.join(candidates[:12])))
    return None


def _v218bc2_hook_panel(panel):
    """Count the exact live Push surface without changing its call contract.

    The record is already enriched by the established local-kill wrapper.
    Therefore this counter calls the current original/wrapped Push directly;
    it does not add another enrichment or FX layer.
    """
    if panel is None:
        return False
    try:
        storage = vars(panel)
    except Exception:
        storage = {}
    own_push = 'Push' in storage
    try:
        cls = type(panel)
        static = None
        if own_push:
            previous = storage.get('Push')
            has_subject = False
        else:
            static = inspect.getattr_static(cls, 'Push')
            previous = (static.__func__ if isinstance(
                static, (staticmethod, classmethod)) else static)
            has_subject = not isinstance(static, staticmethod)
        if not callable(previous) and not own_push:
            previous = getattr(panel, 'Push', None)
            own_push = callable(previous)
            has_subject = False
        if not callable(previous):
            return False
        if getattr(previous, '_v218bc2_panel_wrapper', False):
            return True

        def invoke(*args, **kwargs):
            _v218bc2_calls[0] += 1
            return previous(*args, **kwargs)

        invoke._v218bc2_panel_wrapper = True
        if own_push:
            setattr(panel, 'Push', invoke)
            kind = 'instance'
        else:
            if isinstance(static, staticmethod):
                setattr(cls, 'Push', staticmethod(invoke))
            elif isinstance(static, classmethod):
                setattr(cls, 'Push', classmethod(invoke))
            else:
                setattr(cls, 'Push', invoke)
            kind = 'class'
        _v218bc2_log('panel-hook', 'kind=%s class=%s.%s' %
                     (kind, getattr(cls, '__module__', '?'),
                      getattr(cls, '__name__', '?')))
        return True
    except Exception as exc:
        _v218bc2_log('panel-hook-error', repr(exc))
        return False


def _v218bc2_local_kill(info):
    """Same local caster/current-weapon contract as the established feed hook."""
    if info is None:
        return False
    try:
        ca = _local_combat_avatar()
        if ca is None:
            space = getattr(Space, '_instance', None)
            owner = getattr(space, 'owner', None) if space else None
            ca = getattr(owner, 'combat_avatar', None) if owner else None
        if ca is None:
            return False
        my_ids = set()
        for attr in ('id', 'entity_id', 'guid', 'entityid'):
            value = getattr(ca, attr, None)
            if value is not None:
                my_ids.add(value)
                my_ids.add(str(value))
        caster = None
        for key in ('caster_id', 'killer_id', 'attacker_id', 'source_id',
                    'owner_id', 'caster', 'killer'):
            caster = _mapping_get(info, key, None)
            if caster is not None:
                break
        weapon_guid = _mapping_get(info, 'weapon_guid', None)
        try:
            weapon = ca.GetCurWeapon()
            current_guid = getattr(weapon, 'guid', None) if weapon else None
        except Exception:
            current_guid = None
        return bool(
            (caster is not None and
             (caster in my_ids or str(caster) in my_ids)) or
            (weapon_guid is not None and current_guid is not None and
             str(weapon_guid) == str(current_guid)))
    except Exception:
        return False


def _v218bc2_record_template(info):
    """Read only authentic template/item identity from the enriched record."""
    for key in ('guise_id', 'guise_item_id'):
        try:
            value = _safe_int(_mapping_get(info, key, 0), 0)
            template = _safe_int(ITEM_TO_SKIN.get(value, value), 0)
            if template and template in WEP_SKIN_INFO:
                return template
        except Exception:
            continue
    return 0


def _v218bc2_wrap_record_class(cls):
    guard = '_orig_v218bc2_pushkillrecord'
    try:
        if cls is None:
            return False
        if guard in vars(cls):
            return True
        static = inspect.getattr_static(cls, 'PushKillRecord')
        previous = (static.__func__ if isinstance(
            static, (staticmethod, classmethod)) else static)
        if not callable(previous):
            return False
        has_subject = not isinstance(static, staticmethod)

        def pushkillrecord(*args, **kwargs):
            info = kwargs.get('info')
            index = 1 if has_subject else 0
            if info is None and len(args) > index:
                info = args[index]
            if not sync_attrs.get('bSkinHack', False) or info is None:
                return previous(*args, **kwargs)
            owner = args[0] if has_subject and args else cls
            if not _v218bc2_local_kill(info):
                return previous(*args, **kwargs)
            panel = _v218bc2_cached_panel()
            if panel is None:
                panel = _v218bc2_cache_panel(_v218bc2_walk_panel(owner))
            if panel is not None:
                _v218bc2_hook_panel(panel)
            before = _v218bc2_calls[0]
            result = previous(*args, **kwargs)
            if _v218bc2_calls[0] != before:
                _v218bc2_log('observed', 'authentic panel Push observed')
                return result
            template = _v218bc2_record_template(info)
            if not template:
                _v218bc2_log('no-template', 'local record has no authentic '
                             'selected-skin identity; no direct Push')
                return result
            if panel is None:
                # The game call may have constructed the panel.  Hook it now,
                # but defer direct invocation so an unobserved original Push
                # can never be duplicated.  The next local record is observed.
                panel = _v218bc2_cache_panel(_v218bc2_walk_panel(owner))
                if panel is None:
                    panel = _v218bc2_cache_panel(_v218bc2_gc_panel())
                if panel is not None and _v218bc2_hook_panel(panel):
                    _v218bc2_log('deferred', 'panel discovered after record; '
                                 'next local kill can be observed')
                return result
            try:
                push_result = panel.Push(info)
                _v218bc2_log('direct', 'local skipped Push recovered skin=%d '
                             'ret=%r' % (template, push_result))
            except Exception as exc:
                _v218bc2_log('direct-error', repr(exc))
            return result

        pushkillrecord._v218bc2_record_wrapper = True
        setattr(cls, guard, previous)
        if isinstance(static, staticmethod):
            setattr(cls, 'PushKillRecord', staticmethod(pushkillrecord))
        elif isinstance(static, classmethod):
            setattr(cls, 'PushKillRecord', classmethod(pushkillrecord))
        else:
            setattr(cls, 'PushKillRecord', pushkillrecord)
        return True
    except Exception as exc:
        _v218bc2_log('record-hook-error', repr(exc))
        return False


def _v218bc2_install_records():
    module = sys.modules.get(
        'gclient.gameplay.uicomponents.hud_killrecord_comp')
    if module is None:
        return 0
    installed = 0
    for name in ('HudKillRecordComp', 'HudKillRecordCompPC',
                 'HudKillRecordCompV2'):
        try:
            if _v218bc2_wrap_record_class(getattr(module, name, None)):
                installed += 1
        except Exception:
            continue
    return installed


_v218bc2_refresh_candidate = globals().get('_v842g_refresh_kill_feed')
_v218bc2_previous_refresh = getattr(
    _v218bc2_refresh_candidate, '_v218bc2_original',
    _v218bc2_refresh_candidate)


def _v218bc2_refresh_kill_feed():
    result = (_v218bc2_previous_refresh()
              if callable(_v218bc2_previous_refresh) else 0)
    try:
        _v218bc2_install_records()
    except Exception:
        pass
    return result


_v218bc2_refresh_kill_feed._v218bc2_original = _v218bc2_previous_refresh
_v842g_refresh_kill_feed = _v218bc2_refresh_kill_feed

try:
    _v218bc2_records = _v218bc2_install_records()
    _plog('[BC2] live panel recovery ready records=%d' % _v218bc2_records)
except Exception:
    pass

# ---------------------------------------------------------------------------
# Genuine local weapon-icon consumers.  The range/loadout hook above remains
# unchanged.  These wrappers add the historically observed gunsmith/armory
# callers and local weapon/backpack HUD callers, then propagate the wrapped
# helper only where a module imported that exact same function object.
# ---------------------------------------------------------------------------
_v218ui_log_seen = {}
existing_refs_done = set()
_V218UI_EXCLUDED = ('nearby', 'lobby_member', 'lobbyplayers', 'visitor',
                    'other_player', 'otherplayer')


def _v218ui_caller():
    try:
        frame = sys._getframe(2)
        for _ in range(16):
            if frame is None:
                break
            name = str(frame.f_globals.get('__name__', '?'))
            label = '%s.%s' % (name, frame.f_code.co_name)
            low = name.lower()
            if any(part in low for part in _V218UI_EXCLUDED):
                return label, 'excluded'
            if 'uigunsmith' in low:
                return label, 'new'
            local_ui = (low.startswith('gclient.gamesystem.') or
                        low.startswith('gclient.gameplay.uicomponents.'))
            if (local_ui and any(part in low for part in
                                 ('gun', 'weapon', 'backpack')) and
                    'kill' not in low):
                if ('gunrefit' in low or 'hud_backpack_select' in low):
                    return label, 'existing'
                return label, 'new'
            frame = frame.f_back
    except Exception:
        pass
    return '?', ''


def _v218ui_record(values):
    """Resolve only explicit real equip/gun/item identity to a selected row."""
    try:
        for key in ('equip_id', 'item_id'):
            value = _safe_int(values.get(key), 0)
            if value in WEP_GUN_IDS:
                # This also validates that record[0] is the same equip row.
                return selected_equip(value)
        item_id = _safe_int(values.get('item_id'), 0)
        template = _safe_int(ITEM_TO_SKIN.get(item_id, 0), 0)
        if not template and item_id in SKIN_TO_ITEM:
            template = item_id
        if template:
            equip_id = _safe_int(SKIN_TO_EQUIP.get(template, 0), 0)
            if equip_id in WEP_GUN_IDS:
                record = selected_equip(equip_id)
                if (record and _safe_int(record[1], 0) == template and
                        (record[2] == item_id or item_id == template)):
                    return record
            return None
        for key in ('gun_id', 'item_id', 'equip_id'):
            value = _safe_int(values.get(key), 0)
            if value in WEP_GUN_IDS.values():
                return _v843l_selected_record(value)
        # No current-selection fallback: grid rows for other weapons must stay
        # honest, and an arbitrary lobby item is never guessed as an equip id.
        return None
    except Exception:
        return None


def _v218ui_log(caller, helper, values, record, result):
    try:
        count = _v218ui_log_seen.get(caller, 0)
        if count < 4 or count % 100 == 0:
            _plog('[UIICON] caller=%s helper=%s values=%s record=%s result=%s' %
                  (caller, helper,
                   ','.join('%s=%s' % item for item in values.items()),
                   repr(record), repr(result)[:100]))
        _v218ui_log_seen[caller] = count + 1
    except Exception:
        pass


def set_argument(args, kwargs, offset, index, name, value):
    mutable = list(args)
    position = offset + index
    if len(mutable) > position:
        mutable[position] = value
    else:
        kwargs[name] = value
    return tuple(mutable), kwargs


# v2.18-ui4: keep the authenticated pair fallback inside the ui2 wrapper.
# Log 17's native calls still passed through that exact function object while
# the ui3 outer layer recorded no applications.  Integrating here avoids
# relying on native code or importers acquiring a newly added outer reference.
_v218pair_log_seen = {}
_v218pair_catalog_cache = {'sig': None, 'records': {}}


def _v218pair_log(key, message, limit=1):
    try:
        count = _v218pair_log_seen.get(key, 0)
        if count >= limit:
            return
        if len(_v218pair_log_seen) >= 160 and key not in _v218pair_log_seen:
            return
        _plog('[PAIRICON] %s' % message)
        _v218pair_log_seen[key] = count + 1
    except Exception:
        pass


def catalog_record(equip_id, lobby_item):
    """Validate a real item against its own base-equip catalog row.

    This is deliberately independent of the current menu selection.  The
    native/backpack grids can legitimately ask for a row after the selection
    changes; their explicit base+item pair remains authentic.  A real item
    from another weapon, a template ID, or an unmapped number never qualifies.
    """
    try:
        equip_id = _safe_int(equip_id, 0)
        lobby_item = _safe_int(lobby_item, 0)
        gun_ids = globals().get('WEP_GUN_IDS') or {}
        wep = globals().get('WEP') or {}
        skin_to_item = globals().get('SKIN_TO_ITEM') or {}
        skin_to_equip = globals().get('SKIN_TO_EQUIP') or {}
        skin_info = globals().get('WEP_SKIN_INFO') or {}
        if (not equip_id or not lobby_item or equip_id not in gun_ids
                or equip_id not in wep):
            return None
        sig = (id(wep), id(skin_to_item), id(skin_info), len(wep),
               len(skin_to_item), len(skin_info))
        cache = _v218pair_catalog_cache
        if cache.get('sig') != sig:
            cache['sig'] = sig
            cache['records'] = {}
        key = (equip_id, lobby_item)
        cached = cache['records'].get(key)
        if cached:
            template_id = cached[1]
            info = skin_info.get(template_id) or {}
            current_item = _safe_int(
                skin_to_item.get(template_id)
                or info.get('lobby_item_id'), 0)
            if (template_id in list(wep.get(equip_id) or [])[1:]
                    and current_item == lobby_item):
                return cached
            cache['records'].pop(key, None)
        row = list(wep.get(equip_id) or ())
        for template_id in row[1:]:
            try:
                template_id = _safe_int(template_id, 0)
                if not template_id:
                    continue
                actual_equip = _safe_int(
                    skin_to_equip.get(template_id, equip_id), 0)
                if actual_equip != equip_id:
                    continue
                info = skin_info.get(template_id) or {}
                if not info:
                    continue
                item_id = _safe_int(
                    skin_to_item.get(template_id)
                    or info.get('lobby_item_id'), 0)
                if item_id != lobby_item:
                    continue
                record = (equip_id, template_id, lobby_item)
                if len(cache['records']) < 512:
                    cache['records'][key] = record
                return record
            except Exception:
                continue
    except Exception:
        pass
    return None


def _v218pair_record(values):
    """Accept a selected pair or a catalog-authenticated base+item pair."""
    try:
        equip_id = _safe_int(values.get('item_id'), 0)
        lobby_item = _safe_int(values.get('equip_id'), 0)
        if equip_id not in WEP_GUN_IDS or not lobby_item:
            return None
        record = selected_equip(equip_id)
        if record and _safe_int(record[2], 0) == lobby_item:
            return record
        return catalog_record(equip_id, lobby_item)
    except Exception:
        return None


def native_equip_record(values):
    """Resolve an opaque/missing native item + documented equip argument.

    Log21 supplied opaque integer first values.  The same-run Pairicon1 device
    log additionally proved a None first value for selected native rows.  None
    is admitted only after the same per-equip selected-record check; numeric
    zero, known catalog identities, explicit cosmetics, and missing selections
    still fail closed.  The first value is never guessed as a weapon identity.
    """
    try:
        raw_item = values.get('item_id')
        item_id = _safe_int(raw_item, 0)
        equip_id = _safe_int(values.get('equip_id'), 0)
        gun_ids = globals().get('WEP_GUN_IDS') or {}
        item_to_skin = globals().get('ITEM_TO_SKIN') or {}
        skin_to_item = globals().get('SKIN_TO_ITEM') or {}
        if (equip_id not in gun_ids
                or (raw_item is not None and not item_id)
                or item_id in gun_ids or item_id in item_to_skin
                or item_id in skin_to_item
                or _safe_int(values.get('skin_item_id'), 0)
                or _safe_int(values.get('guise_item_id'), 0)):
            return None
        return selected_equip(equip_id)
    except Exception:
        return None


def cosmetic_kind(record):
    """Read the real lobby row's skin/guise branch without import or I/O."""
    try:
        protos = globals().get('SKIN_LOBBY_PROTO') or {}
        proto = protos.get(record[1])
        if proto is None:
            # The catalog normally has this row cached.  Already-loaded game
            # data is a bounded O(1) fallback; never import a module here.
            for module_name in ('gclient.data.lobby_item_data',
                                'gclient.data.lobby_gun_skin_item_data'):
                module = sys.modules.get(module_name)
                data = getattr(module, 'data', None) if module is not None else None
                if data is None:
                    continue
                proto = _data_get(data, record[2], None)
                if proto is not None:
                    break
        if proto is None:
            return ''
        if _proto_get(proto, 'guise', None):
            return 'guise'
        if _proto_get(proto, 'skin', None):
            return 'skin'
    except Exception:
        pass
    return ''


def canonical_call(previous, offset, args, kwargs, record, kind):
    """Call the authentic helper with exactly one real cosmetic argument.

    Offset comes from the existing descriptor-aware installer; no CItem or
    subject guessing is involved.  Replacing a positional argument also drops
    its stale keyword copy, preventing duplicate-keyword TypeErrors.
    """
    mutable = list(args)
    named = dict(kwargs)
    values = (
        ('item_id', None),
        ('equip_id', record[0]),
        ('skin_item_id', record[2] if kind == 'skin' else 0),
        ('guise_item_id', record[2] if kind == 'guise' else 0),
    )
    for index, (name, value) in enumerate(values):
        position = offset + index
        if len(mutable) > position:
            mutable[position] = value
            named.pop(name, None)
        else:
            named[name] = value
    return previous(*mutable, **named)


def _v218pair_invoke(previous, offset, args, kwargs, caller, scope):
    # Confirmed new ui2 consumers keep their established order and behavior.
    if scope == 'new':
        return previous(*args, **kwargs)
    if scope == 'existing':
        # Preserve the established working chain: the inner wrapper owns the
        # rewrite when it is present.  Canonicalize only an outer-only saved
        # reference; feeding a None-first canonical call through the legacy
        # inner descriptor heuristic would shift its argument positions.
        previous_function = getattr(previous, '__func__', previous)
        if getattr(previous_function, '_v218li_wrap', False):
            return previous(*args, **kwargs)
        # Pairicon4 device evidence showed that a loaded Backpack reference
        # can reach this outer wrapper without reaching the inner loadout
        # wrapper.  Cover that real reference shape as well as inner-only
        # aliases.  Only a selected record + empty cosmetics is admitted;
        # explicit cosmetics, unknown rows and unselected bases fail closed.
        values = {}
        for index, name in enumerate(('item_id', 'equip_id', 'skin_item_id',
                                      'guise_item_id')):
            position = offset + index
            values[name] = (args[position] if len(args) > position else
                            kwargs.get(name))
        record_resolver = globals().get('_v218ui_record')
        record = (record_resolver(values)
                  if callable(record_resolver) else None)
        if record is None:
            try:
                record = (refresh_stack[-1]
                          if refresh_stack else None)
            except Exception:
                record = None
        if (record is not None
                and not _safe_int(values.get('skin_item_id'), 0)
                and not _safe_int(values.get('guise_item_id'), 0)):
            kind = cosmetic_kind(record)
            if kind in ('skin', 'guise'):
                result = canonical_call(
                    previous, offset, args, kwargs, record, kind)
                _v218pair_log(
                    ('apply', caller, scope, record[0], record[2]),
                    'applied caller=%s scope=existing base=%d real_item=%d '
                    'template=%d shape=existing:%s result=%s'
                    % (caller, record[0], record[2], record[1], kind,
                       repr(result)[:80]))
                return result
        return previous(*args, **kwargs)
    if scope == 'excluded':
        lowered = caller.lower()
        other_exclusion = any(
            part in lowered for part in _V218UI_EXCLUDED if part != 'nearby')
        # Only the local Nearby panel is re-admitted, and only for its own
        # explicit authentic base+item pair.  Other-player surfaces stay out.
        if 'nearby' not in lowered or other_exclusion:
            return previous(*args, **kwargs)
    values = {}
    for index, name in enumerate(('item_id', 'equip_id', 'skin_item_id',
                                  'guise_item_id')):
        position = offset + index
        values[name] = (args[position] if len(args) > position else
                        kwargs.get(name))
    record = _v218pair_record(values)
    shape = 'base+item'
    if record is None and not scope and caller in ('?', ''):
        record = native_equip_record(values)
        shape = 'native-equip'
    if record is None:
        result = previous(*args, **kwargs)
        _v218pair_log(
            ('miss', caller, scope, values.get('item_id'),
             values.get('equip_id')),
            'miss caller=%s scope=%s base=%r item=%r skin=%r result=%s' %
            (caller, scope or 'native', values.get('item_id'),
             values.get('equip_id'), values.get('skin_item_id'),
             repr(result)[:80]))
        return result
    kind = cosmetic_kind(record)
    if shape == 'native-equip' and kind not in ('skin', 'guise'):
        # This native shape had no established rewrite.  Without the real row
        # there is no safe new behavior to apply, so preserve the original.
        result = previous(*args, **kwargs)
        _v218pair_log(
            ('native-row-miss', caller, record[0], record[2]),
            'miss caller=%s scope=native base=%d item=%r '
            'reason=unverified-cosmetic-row result=%s' %
            (caller, record[0], values.get('item_id'), repr(result)[:80]))
        return result
    if kind in ('skin', 'guise'):
        result = canonical_call(
            previous, offset, args, kwargs, record, kind)
        shape += ':' + kind
    else:
        # Preserve the established ordinary-pair behavior when the real row
        # is unavailable; an unknown branch is never guessed as a guise.
        new_args, new_kwargs = set_argument(
            args, kwargs, offset, 2, 'skin_item_id', record[2])
        result = previous(*new_args, **new_kwargs)
        shape += ':unverified-row'
    _v218pair_log(
        ('apply', caller, record[0], record[2]),
        'applied caller=%s scope=%s base=%d real_item=%d template=%d '
        'shape=%s result=%s' % (caller, scope or 'native', record[0],
                               record[2], record[1], shape,
                               repr(result)[:80]))
    return result


def _v218ui_real_icon_factory(previous, offset):
    def getrealgunskinicon(*args, **kwargs):
        if not sync_attrs.get('bSkinHack', False):
            return previous(*args, **kwargs)
        caller, scope = _v218ui_caller()
        if scope != 'new':
            pair_invoke = globals().get('_v218pair_invoke')
            if callable(pair_invoke):
                return pair_invoke(previous, offset, args, kwargs,
                                   caller, scope)
            return previous(*args, **kwargs)
        values = {}
        for index, name in enumerate(('item_id', 'equip_id', 'skin_item_id',
                                      'guise_item_id')):
            position = offset + index
            values[name] = (args[position] if len(args) > position else
                            kwargs.get(name))
        record = _v218ui_record(values)
        if record is None:
            result = previous(*args, **kwargs)
            _v218ui_log(caller, 'GetRealGunSkinIcon', values, None, result)
            return result
        # Pairicon6: local new-UI/HUD callers can pass a selected base or
        # equip in item_id instead of the gunsmith's None shape.  Whenever a
        # verified selected record has both cosmetic arguments empty, use the
        # authentic row's own skin/guise branch.  Explicit cosmetics and the
        # established unverified-row fallback keep their prior behavior.
        if (not _safe_int(values.get('skin_item_id'), 0)
                and not _safe_int(values.get('guise_item_id'), 0)):
            resolver = globals().get('cosmetic_kind')
            kind = resolver(record) if callable(resolver) else ''
            if kind in ('skin', 'guise'):
                result = canonical_call(
                    previous, offset, args, kwargs, record, kind)
                _v218ui_log(caller, 'GetRealGunSkinIcon', values, record,
                            result)
                return result
        new_args, new_kwargs = set_argument(
            args, kwargs, offset, 2, 'skin_item_id', record[2])
        result = previous(*new_args, **new_kwargs)
        _v218ui_log(caller, 'GetRealGunSkinIcon', values, record, result)
        return result
    getrealgunskinicon._v218ui_wrapper = True
    return getrealgunskinicon


def gun_icon_factory(previous, offset):
    def getguniconbyskinguiseitemid(*args, **kwargs):
        if not sync_attrs.get('bSkinHack', False):
            return previous(*args, **kwargs)
        caller, scope = _v218ui_caller()
        # Existing Backpack/bottom-HUD consumers may use this helper instead
        # of GetRealGunSkinIcon.  Admit the same verified local UI scopes;
        # other-player and unknown native callers remain exact passthroughs.
        if scope not in ('new', 'existing'):
            return previous(*args, **kwargs)
        position = offset
        item_id = (args[position] if len(args) > position else
                   kwargs.get('item_id'))
        values = {'item_id': item_id}
        record = _v218ui_record(values)
        if record is None:
            result = previous(*args, **kwargs)
            _v218ui_log(caller, 'GetGunIconBySkinGuiseItemId', values, None,
                        result)
            return result
        new_args, new_kwargs = set_argument(
            args, kwargs, offset, 0, 'item_id', record[2])
        result = previous(*new_args, **new_kwargs)
        _v218ui_log(caller, 'GetGunIconBySkinGuiseItemId', values, record,
                    result)
        return result
    getguniconbyskinguiseitemid._v218ui_wrapper = True
    return getguniconbyskinguiseitemid


def wrap_target(target, name, factory):
    guard = '_orig_v218ui_' + name
    if hasattr(target, guard):
        return None
    try:
        raw = inspect.getattr_static(target, name)
    except Exception:
        return None
    try:
        if isinstance(raw, staticmethod):
            previous = raw.__func__
            wrapped = factory(previous, 0)
            setattr(target, name, staticmethod(wrapped))
        elif isinstance(raw, classmethod):
            previous = raw.__func__
            wrapped = factory(previous, 1)
            setattr(target, name, classmethod(wrapped))
        elif isinstance(target, type):
            previous = getattr(target, name)
            wrapped = factory(previous, 1)
            setattr(target, name, wrapped)
        else:
            previous = getattr(target, name)
            wrapped = factory(previous, 0)
            setattr(target, name, wrapped)
        setattr(target, guard, previous)
        return previous, wrapped
    except Exception:
        return None


def _v218ui_targets():
    module = sys.modules.get('gclient.util.gun_skin_util')
    return _v841m2_gun_skin_targets(module) if module is not None else []


def install_name(name, factory):
    replacements = {}
    keepalive = []
    try:
        targets = _v218ui_targets()
    except Exception:
        targets = []
    for target in targets:
        wrapped = wrap_target(target, name, factory)
        if wrapped is None:
            continue
        previous, replacement = wrapped
        old_references = [previous, getattr(previous, '__func__', None)]
        # A UI module may have imported the raw helper before any of the older
        # hook layers ran.  Those authentic saved originals are identity-safe
        # to propagate too; unrelated same-name functions remain untouched.
        for guard in ('_orig_v841m2_' + name, '_orig_v839_' + name):
            old_references.append(getattr(target, guard, None))
        for old in old_references:
            if old is not None:
                replacements[id(old)] = replacement
                keepalive.append(old)
        keepalive.append(replacement)
    patched = 0
    if replacements:
        try:
            for module in list(sys.modules.values()):
                if module is None:
                    continue
                module_name = str(getattr(module, '__name__', '')).lower()
                if any(part in module_name for part in _V218UI_EXCLUDED):
                    continue
                try:
                    reference = getattr(module, name, None)
                    base = getattr(reference, '__func__', reference)
                    replacement = replacements.get(id(base))
                    if replacement is not None and reference is not replacement:
                        setattr(module, name, replacement)
                        patched += 1
                except Exception:
                    continue
        except Exception:
            pass
    return len(keepalive), patched


def propagate_existing(name):
    if name in existing_refs_done:
        return 0
    replacements = {}
    keepalive = []
    try:
        targets = _v218ui_targets()
    except Exception:
        targets = []
    for target in targets:
        try:
            replacement = getattr(target, name, None)
            if not callable(replacement):
                continue
            candidates = [getattr(target, '_orig_v841m2_' + name, None),
                          getattr(target, '_orig_v839_' + name, None)]
            for old in candidates:
                old = getattr(old, '__func__', old)
                if old is not None and old is not replacement:
                    replacements[id(old)] = replacement
                    keepalive.append(old)
            keepalive.append(replacement)
        except Exception:
            continue
    patched = 0
    if replacements:
        existing_refs_done.add(name)
        for module in list(sys.modules.values()):
            try:
                module_name = str(getattr(module, '__name__', '')).lower()
                if any(part in module_name for part in _V218UI_EXCLUDED):
                    continue
                reference = getattr(module, name, None)
                base = getattr(reference, '__func__', reference)
                replacement = replacements.get(id(base))
                if replacement is not None and reference is not replacement:
                    setattr(module, name, replacement)
                    patched += 1
            except Exception:
                continue
    return patched


def _v218ui_install():
    try:
        real = install_name('GetRealGunSkinIcon',
                                    _v218ui_real_icon_factory)
        gun = install_name('GetGunIconBySkinGuiseItemId',
                                   gun_icon_factory)
        backpack = propagate_existing('GetBackpackGunSkinItemId')
        _install_log_key = ('install-status', tuple(real), tuple(gun), backpack)
        _install_log_count = _v218ui_log_seen.get(_install_log_key, 0)
        if _install_log_count < 2:
            _plog('[UIICON] local consumer hooks real=%s gun=%s backpack_refs=%d' %
                  (real, gun, backpack))
        _v218ui_log_seen[_install_log_key] = _install_log_count + 1
        return real[0] + gun[0] + backpack
    except Exception:
        return 0


_v218ui_previous_install = _v218li_install


def _v218ui_install_with_previous():
    # Preserve the established installer's return contract (its real-icon
    # target count); the additional consumers have their own bounded log.
    count = _v218ui_previous_install()
    _v218ui_install()
    return count


_v218li_install = _v218ui_install_with_previous
try:
    _v218li_install()
except Exception:
    pass
_plog('[UIICON] authentic local icon propagation ready')


# ---------------------------------------------------------------------------
# v2.18-ui4 is integrated in _v218ui_real_icon_factory above.  There is no
# additional outer helper reference to lose between installation and a native
# call.  The existing installer and its return contract remain unchanged.
# ---------------------------------------------------------------------------
_plog('[PAIRICON] in-wrapper catalog/native/Nearby icon pairs ready')


# ---------------------------------------------------------------------------
# v10.5-displaysync1: keep one authentic selected appearance coherent across
# the native consumers that do not call GetRealGunSkinIcon.  These are scoped,
# per-call display views, not server-backed item mutation and not a global
# CItem/property override.  Attachment containers, GUID ownership, gameplay
# state, magnification and the established WeaponCase/FX path pass through.
# ---------------------------------------------------------------------------
_v218display_log_seen = {}
_v218display_stack = []
drop_records = {}
_V218DISPLAY_PRIMITIVES = (str, bytes, int, float, bool, type(None))


def _v218display_log(key, message, limit=1):
    try:
        count = _v218display_log_seen.get(key, 0)
        if count >= limit:
            return
        if len(_v218display_log_seen) >= 100 and key not in _v218display_log_seen:
            return
        _plog('[DISPLAYSYNC] %s' % message)
        _v218display_log_seen[key] = count + 1
    except Exception:
        pass


def _v218display_field(value, name, default=None):
    """Read one native/mapping field without invoking an unbounded lookup."""
    if value is None or isinstance(value, _V218DISPLAY_PRIMITIVES):
        return default
    try:
        result = getattr(value, name, None)
        if result is not None:
            return result
    except Exception:
        pass
    try:
        getter = getattr(value, 'get', None)
        if callable(getter):
            result = getter(name, default)
            if result is not None:
                return result
    except Exception:
        pass
    try:
        return value[name]
    except Exception:
        return default


def _v218display_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def drop_snapshot(equip, guid, forced=0):
    """Capture only a proven local drop; later menu changes do not rewrite it."""
    try:
        guid = str(guid or '')
        equip = int(equip or 0)
        if not guid or not equip:
            return
        record = selected_equip(equip)
        if not record or (forced and int(record[1]) != int(forced)):
            drop_records.pop(guid, None)
            return
        if len(drop_records) >= 128:
            drop_records.pop(next(iter(
                drop_records)), None)
        drop_records[guid] = (equip, record, time.time())
        _v218display_log(('drop-snapshot', guid, record[1], record[2]),
                         'drop snapshot guid=%s equip=%d template=%d item=%d'
                         % (guid, equip, record[1], record[2]), 1)
    except Exception:
        pass


def _v218display_resolve(value, drop=False, depth=0, seen=None):
    """Return (selected_record, explicit_weapon_identity), fail-closed."""
    if value is None or isinstance(value, _V218DISPLAY_PRIMITIVES) or depth > 2:
        return None, False
    if seen is None:
        seen = set()
    marker = id(value)
    if marker in seen:
        return None, False
    seen.add(marker)

    guid = _v218display_field(value, 'guid', '') or \
        _v218display_field(value, 'weapon_guid', '') or \
        _v218display_field(value, 'item_guid', '')
    if drop:
        # A pickup/ground icon may use only the appearance captured for this
        # exact local GUID.  Never substitute the current menu selection for
        # another dropped item, Nearby item, ownerless world case or player.
        try:
            guid = str(guid or '')
            entry = drop_records.get(guid)
            if entry:
                equip, record, stamp = entry
                if time.time() - float(stamp) > 1800.0:
                    drop_records.pop(guid, None)
                    return None, True
                actual_equip = _v218display_int(
                    _v218display_field(value, 'equip_id', 0))
                if actual_equip and actual_equip != int(equip):
                    return None, True
                return record, True
        except Exception:
            pass
        return None, True

    equip = _v218display_int(_v218display_field(value, 'equip_id', 0))
    gun = _v218display_int(_v218display_field(value, 'gun_id', 0))
    if gun:
        # Authentic RefreshInfo fixtures and device objects use both actual
        # gun IDs and equip-slot IDs in this field.
        record = _v843l_selected_record(gun)
        if not record and gun in WEP_GUN_IDS:
            record = selected_equip(gun)
        if record:
            return record, True
    if not equip and gun in WEP_GUN_IDS:
        equip = gun
    if equip:
        record = selected_equip(equip)
        if record:
            return record, True
    try:
        gun_identity = bool(gun and (
            gun in WEP_GUN_IDS or gun in WEP_GUN_IDS.values()))
    except Exception:
        gun_identity = bool(gun and gun in WEP_GUN_IDS)
    if equip in WEP_GUN_IDS or gun_identity:
        return None, True

    # Native protos commonly expose only ``id`` rather than equip_id/gun_id.
    equip_proto = _v218display_field(value, 'equip_proto', None)
    if equip_proto is not None:
        proto_equip = _v218display_int(
            _v218display_field(equip_proto, 'equip_id', 0)
            or _v218display_field(equip_proto, 'id', 0))
        if proto_equip:
            record = selected_equip(proto_equip)
            if record:
                return record, True
            if proto_equip in WEP_GUN_IDS:
                return None, True
    gun_proto = _v218display_field(value, 'gun_proto', None)
    if gun_proto is not None:
        proto_gun = _v218display_int(
            _v218display_field(gun_proto, 'gun_id', 0)
            or _v218display_field(gun_proto, 'id', 0))
        if proto_gun:
            record = _v843l_selected_record(proto_gun)
            if record:
                return record, True
            return None, True

    for field_name in ('skin_template_id', 'guise_template_id'):
        template = _v218display_int(
            _v218display_field(value, field_name, 0))
        template_equip = int(SKIN_TO_EQUIP.get(template, 0) or 0)
        if template_equip:
            record = selected_equip(template_equip)
            if record and int(record[1]) == template:
                return record, True
            return None, True

    for field_name in ('item_id', 'skin_item_id', 'guise_item_id'):
        item_id = _v218display_int(_v218display_field(value, field_name, 0))
        if item_id in WEP_GUN_IDS:
            return selected_equip(item_id), True
        template = int(ITEM_TO_SKIN.get(item_id, 0) or 0)
        item_equip = int(SKIN_TO_EQUIP.get(template, 0) or 0)
        if item_equip:
            record = selected_equip(item_equip)
            if record and int(record[1]) == template and int(record[2]) == item_id:
                return record, True
            return None, True

    # Some panels receive a proto or wrapper instead of the CItem itself.
    # Recurse only through known weapon containers and only to depth two.
    for field_name in ('info', 'data', 'gun_info', '_gun_info', 'equipment',
                       'item', 'gun', 'cur_gun', 'current_gun', 'avatar_weapon',
                       'bind_item', 'combatitem', 'equip_proto', 'item_proto',
                       'gun_proto'):
        nested = _v218display_field(value, field_name, None)
        if nested is None or nested is value or isinstance(
                nested, _V218DISPLAY_PRIMITIVES):
            continue
        record, explicit = _v218display_resolve(
            nested, drop=False, depth=depth + 1, seen=seen)
        if record or explicit:
            return record, explicit
    return None, False


def refresh_record(panel, args, kwargs):
    """Explicit row identity first; never paint an unselected row from self."""
    if not sync_attrs.get('bSkinHack', False):
        return None
    for value in tuple(args) + tuple(kwargs.values()):
        record, explicit = _v218display_resolve(value)
        if record:
            return record
        if explicit:
            return None
    record, unused_explicit = _v218display_resolve(panel)
    return record


def visual_values(record, hud=False):
    """Only authentic visual fields are overridden in the temporary view."""
    try:
        equip, template, item_id = record
        kind = cosmetic_kind(record)
        if kind not in ('skin', 'guise'):
            return {}, ''
        if kind == 'guise':
            values = {
                'skin_item_id': 0,
                'guise_item_id': item_id,
                'display_skin_item_id': 0,
                'display_guise_item_id': item_id,
                'skin_template_id': 0,
                'guise_template_id': template,
                'display_skin_template_id': 0,
                'display_guise_template_id': template,
            }
            name = str(WEP_SKIN_INFO.get(template, {}).get('name', '') or '')
            if name:
                values['guise_name'] = name
        else:
            values = {
                'skin_item_id': item_id,
                'guise_item_id': 0,
                'display_skin_item_id': item_id,
                'display_guise_item_id': 0,
                'skin_template_id': template,
                'guise_template_id': 0,
                'display_skin_template_id': template,
                'display_guise_template_id': 0,
            }
            if hud:
                # hud_bottom_arms_base_comp.SetAvatarWeapon chooses its
                # selected/default HUD icon specifically from the guise
                # template row.  Supply the authentic selected skin template
                # only to this display consumer; raw cosmetic IDs remain in
                # their authentic skin/guise namespace.
                values['guise_template_id'] = template
                values['display_guise_template_id'] = template
        return values, kind
    except Exception:
        return {}, ''


def ultra_proto_values(record):
    """Authentic quality-5 lobby icon fallback for the bottom HUD only.

    EVO/Xtreme template rows normally provide icon_outline_replace and keep
    the v10.4 path byte-for-byte.  Ultra rows without that replacement fall
    back to item_proto.icon_outline in WeaponNodeBase.SetAvatarWeapon.  Supply
    only the selected lobby row's own icon fields; never borrow another skin.
    """
    try:
        equip, template, item_id = record
        info = (globals().get('WEP_SKIN_INFO') or {}).get(template) or {}
        proto = (globals().get('SKIN_LOBBY_PROTO') or {}).get(template)
        if proto is None:
            # Bounded O(1) reads of already-loaded authentic data; no import,
            # catalog scan, downloader, or native icon-helper recursion.
            for module_name in ('gclient.data.lobby_item_data',
                                'gclient.data.lobby_gun_skin_item_data'):
                module = sys.modules.get(module_name)
                data = getattr(module, 'data', None) if module is not None else None
                if data is None:
                    continue
                proto = _data_get(data, item_id, None)
                if proto is not None:
                    break
        quality = _safe_int(info.get('skin_quality'), 0)
        if not quality:
            quality = _safe_int(_proto_get(
                proto, 'quality', _proto_get(proto, 'rarity', 0)), 0)
        if quality != 5:  # existing special-optics tier map: 5 = Ultra
            return {}
        icon = _proto_get(proto, 'icon', None)
        outline = _proto_get(proto, 'icon_outline', None)
        outline_2 = _proto_get(proto, 'icon_outline_2', None)
        icon_id = _proto_get(proto, 'icon_id', None)
        small_icon = _proto_get(proto, 'small_icon_id', None)
        # Prefer the exact native field, then the same authentic lobby icon
        # used by GetRealGunSkinIcon.  Small icon is the final visual fallback.
        base_icon = outline or icon or icon_id or small_icon
        if not base_icon:
            return {}
        return {
            'icon_outline': base_icon,
            'icon_outline_2': outline_2 or base_icon,
        }
    except Exception:
        return {}


class _V218DisplayProxy(object):
    """Read-only visual overlay; all other state forwards to the real object."""
    __slots__ = ('_target', '_visual_values', '_record', '_kind')

    def __init__(self, target, values, record, kind):
        object.__setattr__(self, '_target', target)
        object.__setattr__(self, '_visual_values', values)
        object.__setattr__(self, '_record', record)
        object.__setattr__(self, '_kind', kind)

    @property
    def __class__(self):
        return object.__getattribute__(self, '_target').__class__

    def __getattr__(self, name):
        values = object.__getattribute__(self, '_visual_values')
        if name in values:
            return values[name]
        return getattr(object.__getattribute__(self, '_target'), name)

    def __setattr__(self, name, value):
        if name in _V218DisplayProxy.__slots__:
            object.__setattr__(self, name, value)
        else:
            setattr(object.__getattribute__(self, '_target'), name, value)

    def get(self, name, default=None):
        values = object.__getattribute__(self, '_visual_values')
        if name in values:
            return values[name]
        return _v218display_field(
            object.__getattribute__(self, '_target'), name, default)

    def __getitem__(self, name):
        values = object.__getattribute__(self, '_visual_values')
        if name in values:
            return values[name]
        return object.__getattribute__(self, '_target')[name]

    def __setitem__(self, name, value):
        object.__getattribute__(self, '_target')[name] = value

    def __contains__(self, name):
        values = object.__getattribute__(self, '_visual_values')
        if name in values:
            return True
        return name in object.__getattribute__(self, '_target')

    def __iter__(self):
        return iter(object.__getattribute__(self, '_target'))

    def __len__(self):
        return len(object.__getattribute__(self, '_target'))

    def __repr__(self):
        return '<V218DisplayProxy %r>' % (
            object.__getattribute__(self, '_target'),)


def _v218display_proxy(value, record, hud=False):
    if not record or value is None or isinstance(value, _V218DISPLAY_PRIMITIVES):
        return value
    if type(value) is _V218DisplayProxy:
        return value
    values, kind = visual_values(record, hud=hud)
    if not values:
        return value
    if hud:
        ultra_values = ultra_proto_values(record)
        if ultra_values:
            item_proto = _v218display_field(value, 'item_proto', None)
            if item_proto is not None:
                values = dict(values)
                values['item_proto'] = _V218DisplayProxy(
                    item_proto, ultra_values, record, kind)
                _v218display_log(
                    ('ultra-hud-icon', record,
                     ultra_values.get('icon_outline')),
                    '[DISPLAYSYNC] ultra-hud-icon equip=%s template=%s '
                    'item=%s icon=%s' % (
                        record[0], record[1], record[2],
                        ultra_values.get('icon_outline')), 1)
    return _V218DisplayProxy(value, values, record, kind)


def restore_panel(panel, proxies):
    """Do not let a native-stored temporary proxy outlive its refresh call."""
    if not proxies:
        return
    try:
        dictionary = getattr(panel, '__dict__', None)
        if isinstance(dictionary, dict):
            for name, current in list(dictionary.items()):
                if type(current) is _V218DisplayProxy:
                    setattr(panel, name, object.__getattribute__(
                        current, '_target'))
    except Exception:
        pass
    for name in ('avatar_weapon', 'combatitem', 'bind_item', 'weapon',
                 'item', 'info', 'data', 'gun_info', 'cur_gun', 'current_gun'):
        try:
            current = getattr(panel, name, None)
            if type(current) is _V218DisplayProxy:
                setattr(panel, name, object.__getattribute__(current, '_target'))
        except Exception:
            pass


def method_factory(surface, mode='held', hud=False):
    def factory(previous):
        def wrapper(self, *args, **kwargs):
            if not sync_attrs.get('bSkinHack', False):
                return previous(self, *args, **kwargs)
            record = None
            if mode == 'drop':
                for value in tuple(args) + tuple(kwargs.values()):
                    record, unused_explicit = _v218display_resolve(
                        value, drop=True)
                    if record:
                        break
            else:
                record = refresh_record(self, args, kwargs)
            if not record:
                return previous(self, *args, **kwargs)

            call_args = tuple(_v218display_proxy(value, record, hud=hud)
                              for value in args)
            call_kwargs = {key: _v218display_proxy(value, record, hud=hud)
                           for key, value in kwargs.items()}
            proxies = [value for value in
                       tuple(call_args) + tuple(call_kwargs.values())
                       if type(value) is _V218DisplayProxy]
            context = {'record': record, 'surface': surface, 'mode': mode}
            _v218display_stack.append(context)
            _v218display_log((surface, record[0], record[1], record[2]),
                             '%s equip=%d template=%d item=%d mode=%s'
                             % (surface, record[0], record[1], record[2], mode),
                             1)
            try:
                return previous(self, *call_args, **call_kwargs)
            finally:
                try:
                    if _v218display_stack and _v218display_stack[-1] is context:
                        _v218display_stack.pop()
                    else:
                        for index in range(len(_v218display_stack) - 1, -1, -1):
                            if _v218display_stack[index] is context:
                                _v218display_stack.pop(index)
                                break
                except Exception:
                    pass
                restore_panel(self, proxies)
        wrapper._v218display_method = surface
        return wrapper
    return factory


def current_record():
    if not sync_attrs.get('bSkinHack', False):
        return None
    if _v218display_stack:
        return _v218display_stack[-1].get('record')
    if refresh_stack:
        return refresh_stack[-1]
    return None


def realtime_factory(previous):
    """UIBakeTexture.LoadGunRealtimeIcon(self,equip,skin,guise,parts,...)."""
    def wrapper(self, *args, **kwargs):
        record = current_record()
        if not record:
            return previous(self, *args, **kwargs)
        values, kind = visual_values(record)
        if not values:
            return previous(self, *args, **kwargs)
        skin_template = values.get('skin_template_id', 0)
        guise_template = values.get('guise_template_id', 0)
        call_args = list(args)
        call_kwargs = dict(kwargs)
        # Preserve every authentic positional/keyword shape.  In particular,
        # do not pad positional args when equip_id/parts arrived by keyword:
        # doing so would duplicate equip_id and change the native contract.
        if len(call_args) > 1:
            call_args[1] = skin_template
            call_kwargs.pop('skin_id', None)
        else:
            call_kwargs['skin_id'] = skin_template
        if len(call_args) > 2:
            call_args[2] = guise_template
            call_kwargs.pop('guise_id', None)
        else:
            call_kwargs['guise_id'] = guise_template
        _v218display_log(('realtime', record[0], record[1], record[2], kind),
                         'realtime equip=%d skin=%d guise=%d parts=preserved'
                         % (record[0], skin_template, guise_template), 1)
        return previous(self, *call_args, **call_kwargs)
    wrapper._v218display_realtime = True
    return wrapper


def _v218display_install():
    count = 0
    # Runtime-dump qualified names are required here.  v10.3's shortened
    # module labels matched host fakes but not sys.modules on the device.
    specs = (
        ('gclient.gamesystem.uigunsmith.gunsmith_backpack_window',
         'BackpackGunNode', 'RefreshInfo', 'gunsmith-backpack', 'held', False),
        ('gclient.gamesystem.uigunsmith.gunsmith_backpack_window',
         'GunSmithBackpackGunNode', 'RefreshInfo', 'gunsmith-backpack',
         'held', False),
        ('gclient.gamesystem.uigunsmith.gunsmith_backpack_window',
         'GunSmithBackpackGunConfigNode', 'RefreshInfo', 'gunsmith-config',
         'held', False),
        ('gclient.gamesystem.uigunsmith.gun_armory_window',
         'GunArmoryWeaponListItemNode', 'RefreshData', 'armory-grid',
         'held', False),
        ('gclient.gamesystem.uigunsmith.gun_armory_window',
         'GunArmoryWeaponListItemNode', 'RefreshNode', 'armory-grid',
         'held', False),
        ('gclient.gameplay.logic_moba.ui.moba_hud_backpack_comp',
         'WeaponNode', 'UpdatePanel', 'backpack-weapon', 'held', False),
        ('gclient.gameplay.uicomponents.hud_backpack_select_comp',
         'BackpackSelectGunNode', 'RefreshInfo', 'backpack-select',
         'held', False),
        ('gclient.gameplay.logic_base.ui.hud_bottom_arms_base_comp',
         'WeaponNodeBase', 'SetAvatarWeapon', 'bottom-hud', 'held', True),
        # SmallWeaponNode overrides SetAvatarWeapon before calling super.
        # Cover the leaf as well as the base, plus the v2 HUD variant.
        ('gclient.gameplay.logic_base.ui.hud_bottom_arms_base_comp',
         'SmallWeaponNode', 'SetAvatarWeapon', 'bottom-hud-small',
         'held', True),
        ('gclient.gameplay.logic_base.ui.hud_bottom_arms_base_v2_comp',
         'SmallWeaponNode', 'SetAvatarWeapon', 'bottom-hud-small-v2',
         'held', True),
        ('gclient.gameplay.logic_moba.ui.moba_hud_pickup_comp',
         'PickupItem', 'LoadData', 'pickup-drop', 'drop', False),
        ('gclient.gameplay.logic_base.ui.hud_pickup_pc_comp',
         'PickupItem', 'LoadData', 'pickup-drop-pc', 'drop', False),
    )
    for module_name, class_name, method_name, surface, mode, hud in specs:
        try:
            module = sys.modules.get(module_name)
            owner = getattr(module, class_name, None) if module else None
            if owner is None:
                _v218display_log(
                    ('target-missing', module_name, class_name, method_name),
                    'target missing module=%s class=%s method=%s'
                    % (module_name, class_name, method_name), 1)
                continue
            wrapped = bool(_v839_wrap_method(
                owner, method_name,
                method_factory(surface, mode=mode, hud=hud)))
            count += int(wrapped)
            ready = wrapped or ('_orig_v839_' + method_name) in vars(owner)
            _v218display_log(
                ('target-ready' if ready else 'target-failed',
                 module_name, class_name, method_name),
                'target %s module=%s class=%s method=%s'
                % ('ready' if ready else 'FAILED', module_name,
                   class_name, method_name), 1)
        except Exception as exc:
            _v218display_log(
                ('target-error', module_name, class_name, method_name,
                 repr(exc)), 'target error %s.%s: %r'
                % (module_name, class_name, exc), 1)
            continue

    # Backward-compatible gun-refit grid module, also fully qualified.
    gun_select_module = (
        'gclient.gameplay.uicomponents.uigunrefit.'
        'hud_gunrefit_gun_select_comp')
    try:
        module = sys.modules.get(gun_select_module)
        for class_name, owner in list(vars(module).items()) if module else ():
            if not isinstance(owner, type) or getattr(
                    owner, '__module__', '') != module.__name__:
                continue
            count += int(bool(_v839_wrap_method(
                owner, 'RefreshInfo',
                method_factory('gun-select-grid'))))
    except Exception:
        pass

    try:
        module = sys.modules.get('gclient.framework.ui.widgets.ui_bake_texture')
        owner = getattr(module, 'UIBakeTexture', None) if module else None
        if owner is not None:
            count += int(bool(_v839_wrap_method(
                owner, 'LoadGunRealtimeIcon', realtime_factory)))
    except Exception:
        pass
    _v218display_log(('install', count), 'installed hooks=%d' % count, 2)
    return count


# Add exact-GUID snapshots without changing the established local drop factory
# or world WeaponCase behavior.  Both wrappers preserve exceptions/results.
previous_drop_note = note_local


def drop_note_with_snapshot(wid, args):
    result = previous_drop_note(wid, args)
    guid = call_guid(wid, args)
    if guid:
        drop_snapshot(wid, guid)
    return result


note_local = drop_note_with_snapshot
previous_drop_skin = _v218drop_forced_skin


def drop_skin_with_snapshot(wid, args, kwargs):
    forced = previous_drop_skin(wid, args, kwargs)
    guid = call_guid(wid, args)
    if guid and forced:
        drop_snapshot(wid, guid, forced=forced)
    return forced


_v218drop_forced_skin = drop_skin_with_snapshot

previous_install = _v218li_install


def install_with_previous():
    count = previous_install()
    _v218display_install()
    return count


_v218li_install = install_with_previous
try:
    _v218li_install()
except Exception:
    pass
_plog('[DISPLAYSYNC] scoped local/drop visual synchronization ready')


# ---------------------------------------------------------------------------
# v2.18-attach1: authentic max-progression attachments for menu-selected guns.
# Compatibility comes from the game's own GetWeaponPartIdListByType and
# gun_attachments_data.  No global unlock predicate, fabricated part, donor
# row, universal optic, account write, or other-player path is involved.
# ---------------------------------------------------------------------------
_v218att_log_seen = {}
catalog_cache = {}
_v218att_applied = {}
inventory_seen = set()


def _v218att_log(key, message, limit=1):
    try:
        count = _v218att_log_seen.get(key, 0)
        if count >= limit:
            return
        if len(_v218att_log_seen) >= 140 and key not in _v218att_log_seen:
            return
        _plog('[ATTACH] %s' % message)
        _v218att_log_seen[key] = count + 1
    except Exception:
        pass


def _v218att_modules():
    weapon_util = _import_module('gshare.weapon_util')
    consts = _import_module('gshare.consts')
    attachments = _import_module('gclient.data.gun_attachments_data')
    return weapon_util, consts, getattr(attachments, 'data', None)


def part_types(consts):
    excluded = ('recevier', 'receiver', 'invalid', 'unknown', 'none',
                'count', 'max', 'all', 'num')
    found = {}
    try:
        for name, value in sorted(vars(consts).items()):
            if not name.startswith('WeaponPartType_'):
                continue
            short = name[len('WeaponPartType_'):]
            if any(token in short.lower() for token in excluded):
                continue
            part_type = _safe_int(value, 0)
            if part_type > 0:
                found.setdefault(part_type, short)
    except Exception:
        pass
    return sorted(found.items())


def _v218att_row(data, part_id):
    row = _data_get(data, part_id, None)
    if row is None:
        row = _data_get(data, str(part_id), None)
    return row


def _v218att_rank(row, part_id):
    def first(keys):
        for key in keys:
            value = _safe_int(_proto_get(row, key, 0), 0)
            if value:
                return value
        return 0
    unlock = first(('unlock_weapon_level', 'weapon_unlock_level',
                    'unlock_gun_level', 'gun_unlock_level', 'unlock_level',
                    'need_weapon_level', 'need_gun_level', 'weapon_level',
                    'gun_level', 'need_level', 'level_require',
                    'level_required'))
    if not unlock:
        # Different table exports spell levels as *_level or *_lv.  Only
        # rank authentic fields that combine a progression/weapon token with
        # a level token; never invent an ID or a compatibility relationship.
        try:
            for key, raw in _data_items(row):
                name = str(key).lower()
                levelish = ('level' in name or name == 'lv' or
                            name.endswith('_lv') or name.startswith('lv_'))
                progression = any(token in name for token in (
                    'unlock', 'open', 'need', 'require', 'weapon', 'gun'))
                if levelish and progression:
                    unlock = max(unlock, _safe_int(raw, 0))
        except Exception:
            pass
    level = first(('part_level', 'attachment_level', 'level'))
    quality = first(('quality', 'rarity', 'grade'))
    return unlock, level, quality, part_id


def _v218att_compatible(row, part_type, gun_id, equip_id):
    try:
        row_type = _safe_int(_proto_get(row, 'part_type', 0), 0)
        if row_type and row_type != part_type:
            return False
        for key in ('gun_id', 'equip_id', 'weapon_id'):
            value = _safe_int(_proto_get(row, key, 0), 0)
            if value and value not in (gun_id, equip_id):
                return False
        return True
    except Exception:
        return False


def _v218att_catalog(equip_id):
    """Return {real part_type: highest-progression authentic part_id}."""
    equip_id = _safe_int(equip_id, 0)
    gun_id = _safe_int((globals().get('WEP_GUN_IDS') or {}).get(
        equip_id), 0)
    key = (equip_id, gun_id)
    now = time.time()
    cached = catalog_cache.get(key)
    if cached:
        ttl = 30.0 if cached.get('slots') else 1.0
        if now - cached.get('at', 0.0) < ttl:
            return dict(cached.get('slots') or {})
    slots = {}
    details = {}
    if not equip_id or not gun_id:
        return slots
    try:
        weapon_util, consts, data = _v218att_modules()
        list_fn = getattr(weapon_util, 'GetWeaponPartIdListByType', None)
        if not callable(list_fn) or data is None:
            _v218att_log(('module', equip_id),
                         'catalog unavailable equip=%d gun=%d list_fn=%s data=%s' %
                         (equip_id, gun_id, callable(list_fn), data is not None))
            return slots
        for part_type, part_name in part_types(consts):
            try:
                raw = list_fn(gun_id, part_type)
                if isinstance(raw, (int, str)):
                    candidates = [raw]
                else:
                    candidates = list(raw or ())[:96]
            except Exception as exc:
                _v218att_log(('list', gun_id, part_type, repr(exc)),
                             'list miss gun=%d type=%s(%d) error=%r' %
                             (gun_id, part_name, part_type, exc))
                continue
            best = None
            for candidate in candidates:
                part_id = _safe_int(candidate, 0)
                if not part_id:
                    continue
                row = _v218att_row(data, part_id)
                if row is None or not _v218att_compatible(
                        row, part_type, gun_id, equip_id):
                    continue
                rank = _v218att_rank(row, part_id)
                if best is None or rank > best[0]:
                    best = rank, part_id
            if best is not None:
                slots[part_type] = best[1]
                details[part_name] = (best[1],) + tuple(best[0][:3])
    except Exception as exc:
        _v218att_log(('catalog', equip_id, repr(exc)),
                     'catalog guarded error equip=%d gun=%d error=%r' %
                     (equip_id, gun_id, exc))
    if len(catalog_cache) >= 64:
        catalog_cache.clear()
    catalog_cache[key] = {'at': now, 'slots': dict(slots)}
    _v218att_log(('catalog', equip_id, tuple(sorted(slots.items()))),
                 'catalog equip=%d gun=%d slots=%r ranks=%r' %
                 (equip_id, gun_id, slots, details))
    return slots


def value_id(value):
    if value is None or isinstance(value, bool):
        return 0
    if isinstance(value, (int, str)):
        return _safe_int(value, 0)
    try:
        for key in ('part_id', 'id'):
            raw = _proto_get(value, key, None)
            if raw is not None:
                return _safe_int(raw, 0)
    except Exception:
        pass
    try:
        for name in ('part_id', 'id'):
            raw = getattr(value, name, None)
            if raw is not None:
                return _safe_int(raw, 0)
    except Exception:
        pass
    return 0


def _v218att_slot_key(keys, part_type):
    if part_type in keys:
        return part_type
    text = str(part_type)
    if text in keys:
        return text
    if keys and all(isinstance(key, str) for key in keys):
        return text
    return part_type


def _v218att_match(case, desired):
    """True=verified match, False=verified mismatch, None=no readable shape."""
    try:
        slots = getattr(case, 'part_slots', None)
    except Exception:
        slots = None
    if isinstance(slots, (list, tuple)):
        for part_type, part_id in desired.items():
            if part_type >= len(slots) or value_id(
                    slots[part_type]) != part_id:
                return False
        return True
    if slots is not None and _data_items(slots):
        keys = {key for key, _value in _data_items(slots)}
        for part_type, part_id in desired.items():
            key = _v218att_slot_key(keys, part_type)
            if value_id(_proto_get(slots, key, None)) != part_id:
                return False
        return True
    if isinstance(slots, dict) and not slots:
        return False if desired else True
    try:
        getter = getattr(case, 'GetWeaponPart', None)
        if callable(getter):
            for part_type, part_id in desired.items():
                if value_id(getter(part_type)) != part_id:
                    return False
            return True
    except Exception:
        pass
    return None


def write_slots(case, desired):
    """Shape-safe writes to the real part_slots member; return written types."""
    written = set()
    try:
        slots = getattr(case, 'part_slots', None)
    except Exception:
        return written
    if isinstance(slots, (list, tuple)):
        mutable = list(slots)
        changed = False
        for part_type, part_id in desired.items():
            if part_type >= len(mutable):
                continue
            old = mutable[part_type]
            if old is not None and (isinstance(old, bool) or
                                    not isinstance(old, (int, str))):
                continue
            value = str(part_id) if isinstance(old, str) else part_id
            if value_id(old) != part_id:
                mutable[part_type] = value
                written.add(part_type)
                changed = True
        if changed:
            try:
                setattr(case, 'part_slots',
                        tuple(mutable) if isinstance(slots, tuple) else mutable)
            except Exception:
                written.clear()
        return written
    if slots is None or not hasattr(slots, '__setitem__'):
        return written
    entries = _data_items(slots)
    keys = {key for key, _value in entries}
    object_map = any(value is not None and not isinstance(value, (int, str))
                     for _key, value in entries[:8])
    for part_type, part_id in desired.items():
        key = _v218att_slot_key(keys, part_type)
        old = _proto_get(slots, key, None)
        if old is None and part_type not in keys and str(part_type) not in keys:
            # An empty plain dict is the documented slot shape.  Do not add
            # scalar IDs to a map demonstrably populated by part objects.
            if object_map and not isinstance(slots, dict):
                continue
            if object_map and entries:
                continue
        elif old is not None and (isinstance(old, bool) or
                                 not isinstance(old, (int, str))):
            continue
        if value_id(old) == part_id:
            continue
        value = str(part_id) if isinstance(old, str) else part_id
        try:
            slots[key] = value
            written.add(part_type)
        except Exception as exc:
            _v218att_log(('write', type(case).__name__, part_type, repr(exc)),
                         'write miss case=%s type=%d error=%r' %
                         (type(case).__name__, part_type, exc))
    return written


def native_set(case, desired):
    """Use only explicitly named native (part_type, part_id) setters."""
    succeeded = set()
    for part_type, part_id in desired.items():
        for method_name in ('ChangeWeaponPart', 'SetWeaponPart',
                            'EquipWeaponPart'):
            try:
                fn = getattr(case, method_name, None)
                if not callable(fn):
                    continue
                params = inspect.signature(fn).parameters
                if 'part_type' not in params or 'part_id' not in params:
                    continue
                kwargs = {'part_type': part_type, 'part_id': part_id}
                unsupported = False
                for name, param in params.items():
                    if name == 'self':
                        continue
                    if (param.default is inspect.Parameter.empty and
                            param.kind in (param.POSITIONAL_ONLY,
                                           param.POSITIONAL_OR_KEYWORD,
                                           param.KEYWORD_ONLY) and
                            name not in kwargs):
                        unsupported = True
                        break
                if unsupported:
                    continue
                result = fn(**kwargs)
                if result is not False:
                    succeeded.add(part_type)
                    break
            except Exception as exc:
                _v218att_log(('native', method_name, repr(exc)),
                             'native setter miss %s type=%d error=%r' %
                             (method_name, part_type, exc))
    return succeeded


def _v218att_inventory(case):
    label = type(case).__name__
    if label in inventory_seen:
        return
    inventory_seen.add(label)
    try:
        methods = []
        for name in dir(type(case)):
            if 'part' not in name.lower() and 'attach' not in name.lower():
                continue
            try:
                fn = getattr(case, name, None)
                if callable(fn):
                    methods.append((name, str(inspect.signature(fn))))
            except Exception:
                continue
            if len(methods) >= 24:
                break
        _v218att_log(('inventory', label),
                     'api case=%s part_slots=%s methods=%r' %
                     (label, repr(getattr(case, 'part_slots', None))[:400],
                      methods))
    except Exception:
        pass


def _v218att_apply(case, equip_id, forced_skin, reason='apply'):
    """Apply only to a local case already gated by the menu skin selection."""
    if case is None or not sync_attrs.get('bSkinHack', False):
        return False
    equip_id = _safe_int(equip_id, 0)
    forced_skin = _safe_int(forced_skin, 0)
    if not equip_id or not forced_skin:
        return False
    try:
        if _safe_int(_get_forced_weapon_skin(equip_id), 0) != forced_skin:
            return False
    except Exception:
        return False
    desired = _v218att_catalog(equip_id)
    if not desired:
        return False
    gun_id = _safe_int((globals().get('WEP_GUN_IDS') or {}).get(
        equip_id), 0)
    signature = (equip_id, gun_id, tuple(sorted(desired.items())))
    match = _v218att_match(case, desired)
    if match is True:
        _v218att_applied[id(case)] = (signature, time.time())
        return False
    previous = _v218att_applied.get(id(case))
    if match is None and previous and previous[0] == signature:
        return False
    if previous and previous[0] == signature and time.time() - previous[1] < 2.0:
        return False
    _v218att_inventory(case)
    native = native_set(case, desired)
    written = write_slots(case, desired)
    changed = native | written
    if not changed:
        _v218att_log(('no-api', type(case).__name__, signature),
                     'no writable attachment surface case=%s equip=%d match=%r '
                     'part_slots=%s' %
                     (type(case).__name__, equip_id, match,
                      repr(getattr(case, 'part_slots', None))[:240]))
        return False
    for part_type in sorted(changed):
        try:
            fn = getattr(case, 'UpdateGuisePartSlots', None)
            if callable(fn):
                fn(part_type, desired[part_type])
        except Exception:
            pass
    if len(_v218att_applied) >= 64:
        _v218att_applied.clear()
    _v218att_applied[id(case)] = (signature, time.time())
    _v218att_log(('applied', id(case), signature),
                 'applied case=%s equip=%d gun=%d reason=%s native=%r '
                 'written=%r slots=%r' %
                 (type(case).__name__, equip_id, gun_id, reason,
                  sorted(native), sorted(written),
                  {key: desired[key] for key in sorted(changed)}))
    return True


_plog('[ATTACH] authentic selected-gun max-slot layer ready')


# ---------------------------------------------------------------------------
# attach2: dedicated Attachment Inject menu.  This is independent of bSkinHack
# and of the old automatic attach1 experiment.  Catalog and inject requests
# arrive through sync_attrs and run through the established game-thread pump.
# ---------------------------------------------------------------------------
_v218inj_log_seen = {}
detail_cache = {}
_v218inj_seen = {'catalog': -1, 'inject': None, 'max': None}


def _v218inj_log(key, message, limit=1):
    try:
        count = _v218inj_log_seen.get(key, 0)
        if count >= limit:
            return
        if len(_v218inj_log_seen) >= 140 and key not in _v218inj_log_seen:
            return
        _plog('[ATTACH2] %s' % message)
        _v218inj_log_seen[key] = count + 1
    except Exception:
        pass


def _v218inj_part_name(row, part_id):
    try:
        name = _english_display_text(_proto_get(row, 'name', None), '')
        if not name:
            for key in ('part_name', 'attachment_name', 'display_name',
                        'name_language', 'part_name_language'):
                name = _english_display_text(_proto_get(row, key, None), '')
                if name:
                    break
        return _clean_catalog_text(name)[:128] or ('Part %d' % part_id)
    except Exception:
        return 'Part %d' % part_id


def slot_name(part_name):
    lower = str(part_name).lower()
    if 'optic' in lower or 'sight' in lower:
        return 'Scope / Aimsight'
    labels = {
        'ammunition': 'Ammunition', 'magazine': 'Magazine',
        'underbarrel': 'Underbarrel', 'lowerrail': 'Lower Rail',
        'upperrail': 'Upper Rail', 'reargrip': 'Rear Grip',
        'foregrip': 'Foregrip', 'charger': 'Charger',
    }
    if lower in labels:
        return labels[lower]
    return _clean_catalog_text(str(part_name).replace('_', ' ').title()) or 'Attachment'


def _v218inj_catalog(equip_id, refresh=False):
    """Detailed authentic slots/parts for the menu and request validation."""
    equip_id = _safe_int(equip_id, 0)
    gun_id = _safe_int((globals().get('WEP_GUN_IDS') or {}).get(
        equip_id), 0)
    key = (equip_id, gun_id)
    now = time.time()
    cached = detail_cache.get(key)
    if cached and not refresh:
        ttl = 30.0 if cached.get('slots') else 1.0
        if now - cached.get('at', 0.0) < ttl:
            return cached.get('slots') or []
    slots = []
    if not equip_id or not gun_id:
        return slots
    try:
        weapon_util, consts, data = _v218att_modules()
        list_fn = getattr(weapon_util, 'GetWeaponPartIdListByType', None)
        if not callable(list_fn) or data is None:
            _v218inj_log(('modules', equip_id),
                         'detail catalog unavailable equip=%d gun=%d fn=%s data=%s' %
                         (equip_id, gun_id, callable(list_fn), data is not None))
            return slots
        row_sample_logged = False
        for part_type, part_name in part_types(consts):
            try:
                raw = list_fn(gun_id, part_type)
                candidates = [raw] if isinstance(raw, (int, str)) else list(raw or ())[:96]
            except Exception as exc:
                _v218inj_log(('list', gun_id, part_type, repr(exc)),
                             'detail list miss gun=%d type=%d error=%r' %
                             (gun_id, part_type, exc))
                continue
            parts = []
            seen = set()
            for candidate in candidates:
                part_id = _safe_int(candidate, 0)
                if not part_id or part_id in seen:
                    continue
                row = _v218att_row(data, part_id)
                if row is None or not _v218att_compatible(
                        row, part_type, gun_id, equip_id):
                    continue
                seen.add(part_id)
                rank = _v218att_rank(row, part_id)
                parts.append({'id': part_id, 'rank': rank,
                              'name': _v218inj_part_name(row, part_id)})
                if not row_sample_logged:
                    row_sample_logged = True
                    _v218inj_log(('row', gun_id),
                                 'authentic row gun=%d part=%d keys=%r' %
                                 (gun_id, part_id, _proto_keys(row, 60)))
            if parts:
                parts.sort(key=lambda item: item['rank'])
                slots.append({'type': part_type,
                              'name': slot_name(part_name),
                              'parts': parts})
    except Exception as exc:
        _v218inj_log(('catalog', equip_id, repr(exc)),
                     'detail catalog guarded error equip=%d error=%r' % (equip_id, exc))
    if len(detail_cache) >= 64:
        detail_cache.clear()
    detail_cache[key] = {'at': now, 'slots': slots}
    _v218inj_log(('detail', equip_id, tuple(
        (slot['type'], len(slot['parts'])) for slot in slots)),
        'detail catalog equip=%d gun=%d slots=%r' %
        (equip_id, gun_id,
         {slot['name']: len(slot['parts']) for slot in slots}))
    return slots


def _v218inj_status(equip_id, nonce, level, text):
    equip_id = _safe_int(equip_id, 0)
    nonce = _safe_int(nonce, 0)
    level = max(0, min(2, _safe_int(level, 0)))
    text = _clean_catalog_text(text)[:300]
    if not equip_id or not text:
        return
    try:
        _write_udp_skin('AT|%d|%d|%d|%s\n' % (equip_id, nonce, level, text))
    except Exception:
        pass
    _v218inj_log(('status', equip_id, nonce, level, text),
                 'status equip=%d nonce=%d level=%d text=%s' %
                 (equip_id, nonce, level, text))


def send_catalog(equip_id, nonce=0):
    equip_id = _safe_int(equip_id, 0)
    slots = _v218inj_catalog(equip_id, refresh=True)
    lines = ['ABEGIN|%d' % equip_id]
    for slot in slots[:32]:
        lines.append('AS|%d|%d|%s' % (
            equip_id, slot['type'], _clean_catalog_text(slot['name'])[:128]))
        for part in slot['parts'][:96]:
            lines.append('AP|%d|%d|%d|%d|%s' % (
                equip_id, slot['type'], part['id'],
                _safe_int(part['rank'][0], 0),
                _clean_catalog_text(part['name'])[:128]))
    lines.append('AEND|%d' % equip_id)
    _write_udp_chunked(_write_udp_skin, '\n'.join(lines) + '\n')
    if slots:
        _v218inj_status(equip_id, nonce, 0,
                        'Authentic catalog ready: %d slot(s)' % len(slots))
    else:
        _v218inj_status(equip_id, nonce, 2,
                        'No authentic attachment catalog; check [ATTACH2] log')
    return bool(slots)


def _v218inj_desired(equip_id, mode):
    slots = _v218inj_catalog(equip_id)
    desired = {}
    for slot in slots:
        part_type = slot['type']
        parts = slot['parts']
        if not parts:
            continue
        if mode == 'max':
            desired[part_type] = max(parts, key=lambda item: item['rank'])['id']
            continue
        key = 'iAttachmentPart_%d_%d' % (equip_id, part_type)
        part_id = _safe_int(sync_attrs.get(key, 0), 0)
        if not part_id:
            continue
        if any(part['id'] == part_id for part in parts):
            desired[part_type] = part_id
        else:
            _v218inj_log(('reject', equip_id, part_type, part_id),
                         'reject non-catalog manual part equip=%d type=%d part=%d' %
                         (equip_id, part_type, part_id))
    return desired, slots


def _v218inj_target_equip(target):
    if target is None:
        return 0
    try:
        resolver = globals().get('_weapon_case_wid')
        if callable(resolver):
            equip_id = _safe_int(resolver(target), 0)
            if equip_id in (globals().get('WEP') or {}):
                return equip_id
    except Exception:
        pass
    for name in ('equip_id', 'weapon_id'):
        try:
            equip_id = _safe_int(getattr(target, name, 0), 0)
            if equip_id in (globals().get('WEP') or {}):
                return equip_id
        except Exception:
            pass
    try:
        gun_id = _safe_int(getattr(target, 'gun_id', 0), 0)
        matches = [equip for equip, gun in (globals().get('WEP_GUN_IDS') or {}).items()
                   if gun == gun_id and gun_id]
        if len(matches) == 1:
            return matches[0]
    except Exception:
        pass
    return 0


def _v218inj_targets(equip_id):
    """Only the local current/remembered cases for this exact equip ID."""
    targets = []
    def add(target):
        if target is not None and not any(target is old for old in targets):
            targets.append(target)
    ca = None
    try:
        resolver = globals().get('_local_combat_avatar')
        ca = resolver() if callable(resolver) else None
    except Exception:
        ca = None
    if ca is None:
        try:
            sp = getattr(Space, '_instance', None)
            owner = getattr(sp, 'owner', None) if sp else None
            ca = getattr(owner, 'combat_avatar', None) if owner else None
        except Exception:
            ca = None
    if ca is not None:
        try:
            weapon = ca.GetCurWeapon()
            if _v218inj_target_equip(weapon) == equip_id:
                add(weapon)
        except Exception:
            pass
        try:
            for case in _current_weapon_cases(ca):
                if _v218inj_target_equip(case) == equip_id:
                    add(case)
        except Exception:
            pass
        try:
            for _key, case in _data_items(getattr(ca, 'weapon_cases', None)):
                if _v218inj_target_equip(case) == equip_id:
                    add(case)
        except Exception:
            pass
    try:
        for item in list(_weaponfx_cases):
            try:
                ref, stored_wid = item
                case = ref()
            except Exception:
                continue
            if case is not None and (stored_wid == equip_id or
                                     _v218inj_target_equip(case) == equip_id):
                add(case)
    except Exception:
        pass
    return targets[:8]


def _v218inj_rebuild(target):
    """Call an authentic refresh with named arguments only; never guess a signature."""
    try:
        fn = getattr(target, 'WeaponBodyIllusion', None)
        if callable(fn):
            params = inspect.signature(fn).parameters
            kwargs = {'need_callback': False} if 'need_callback' in params else {}
            supported = True
            for name, param in params.items():
                if name == 'self':
                    continue
                if param.kind == param.POSITIONAL_ONLY and name in kwargs:
                    supported = False
                    break
                if (param.default is inspect.Parameter.empty and
                        param.kind in (param.POSITIONAL_ONLY,
                                       param.POSITIONAL_OR_KEYWORD,
                                       param.KEYWORD_ONLY) and name not in kwargs):
                    supported = False
                    break
            if supported:
                result = fn(**kwargs)
                return 'WeaponBodyIllusion', result
    except Exception as exc:
        _v218inj_log(('illusion', type(target).__name__, repr(exc)),
                     'WeaponBodyIllusion miss case=%s error=%r' %
                     (type(target).__name__, exc))
    objects = [target]
    try:
        nested = getattr(target, 'weapon_case', None)
        if nested is not None and nested is not target:
            objects.append(nested)
    except Exception:
        pass
    for obj in objects:
        try:
            fn = getattr(obj, 'InitWeapon', None)
            if not callable(fn):
                continue
            slots = getattr(obj, 'part_slots', None)
            if slots is None:
                slots = getattr(target, 'part_slots', None)
            if slots is None:
                continue
            params = inspect.signature(fn).parameters
            if 'part_slots' not in params:
                continue
            kwargs = {'part_slots': slots}
            for name in ('part_loaded_callback', 'all_loaded_callback'):
                if name not in params:
                    continue
                value = getattr(obj, name, None)
                if value is None and obj is not target:
                    value = getattr(target, name, None)
                if value is not None:
                    kwargs[name] = value
            if 'is_fps_weapon' in params:
                value = getattr(obj, 'is_fps_weapon', None)
                if value is None and obj is not target:
                    value = getattr(target, 'is_fps_weapon', None)
                if callable(value):
                    value = value()
                if value is not None:
                    kwargs['is_fps_weapon'] = bool(value)
            supported = True
            for name, param in params.items():
                if name == 'self':
                    continue
                if param.kind == param.POSITIONAL_ONLY:
                    supported = False
                    break
                if (param.default is inspect.Parameter.empty and
                        param.kind in (param.POSITIONAL_OR_KEYWORD,
                                       param.KEYWORD_ONLY) and name not in kwargs):
                    supported = False
                    break
            if not supported:
                _v218inj_log(('init-signature', type(obj).__name__),
                             'InitWeapon unsupported required signature case=%s signature=%s' %
                             (type(obj).__name__, inspect.signature(fn)))
                continue
            result = fn(**kwargs)
            return 'InitWeapon', result
        except Exception as exc:
            _v218inj_log(('init', type(obj).__name__, repr(exc)),
                         'InitWeapon miss case=%s error=%r' %
                         (type(obj).__name__, exc))
    return None, None


def apply_target(target, desired):
    before = _v218att_match(target, desired)
    if before is True:
        return {'before': before, 'changed': set(), 'native': set(),
                'written': set(), 'rebuild': 'already', 'match': True}
    native = native_set(target, desired)
    written = write_slots(target, desired)
    changed = native | written
    if not changed:
        _v218att_inventory(target)
        return {'before': before, 'changed': set(), 'native': native,
                'written': written, 'rebuild': None, 'match': before}
    for part_type in sorted(changed):
        try:
            fn = getattr(target, 'UpdateGuisePartSlots', None)
            if callable(fn):
                fn(part_type, desired[part_type])
        except Exception:
            pass
    rebuild, rebuild_result = _v218inj_rebuild(target)
    match = _v218att_match(target, desired)
    return {'before': before, 'changed': changed, 'native': native,
            'written': written, 'rebuild': rebuild,
            'rebuild_result': rebuild_result, 'match': match}


def _v218inj_inject(equip_id, mode='manual', nonce=0):
    equip_id = _safe_int(equip_id, 0)
    if not sync_attrs.get('bAttachmentHack', False):
        _v218inj_status(equip_id, nonce, 2, 'Attachment master is OFF')
        return False
    desired, _slots = _v218inj_desired(equip_id, mode)
    if not desired:
        _v218inj_status(equip_id, nonce, 2,
                        'Choose at least one attachment or use Max all')
        return False
    targets = _v218inj_targets(equip_id)
    if not targets:
        _v218inj_status(equip_id, nonce, 2,
                        'No live case for this gun; equip/hold it and retry')
        _v218inj_log(('no-target', equip_id),
                     'no local target equip=%d mode=%s desired=%r' %
                     (equip_id, mode, desired))
        return False
    results = []
    for target in targets:
        try:
            result = apply_target(target, desired)
        except Exception as exc:
            result = {'changed': set(), 'match': False, 'error': repr(exc),
                      'rebuild': None}
        results.append((target, result))
        _v218inj_log(('target', id(target), tuple(sorted(desired.items())),
                      repr(result.get('rebuild')), repr(result.get('match'))),
                     'inject case=%s equip=%d mode=%s changed=%r native=%r '
                     'written=%r rebuild=%r match=%r error=%r' %
                     (type(target).__name__, equip_id, mode,
                      sorted(result.get('changed') or ()),
                      sorted(result.get('native') or ()),
                      sorted(result.get('written') or ()),
                      result.get('rebuild'), result.get('match'),
                      result.get('error')))
    changed = [result for _target, result in results if result.get('changed')]
    already = [result for _target, result in results
               if result.get('rebuild') == 'already' and result.get('match') is True]
    verified = [result for result in changed if result.get('match') is True]
    reverted = [result for result in changed if result.get('match') is False]
    refreshed = [result for result in changed if result.get('rebuild')]
    if not changed and already:
        _v218inj_status(equip_id, nonce, 1,
                        'Selected attachments already present; no rebuild needed')
        return True
    if not changed:
        _v218inj_status(equip_id, nonce, 2,
                        'No supported attachment write path; check [ATTACH2] log')
        return False
    if reverted and not verified:
        _v218inj_status(equip_id, nonce, 2,
                        'Game restored previous parts after refresh; check log')
        return False
    if verified:
        _v218inj_status(equip_id, nonce, 1,
                        'Part slots verified on %d target(s); check in game' % len(verified))
        return True
    if refreshed:
        _v218inj_status(equip_id, nonce, 0,
                        'Refresh called on %d target(s); device check required' % len(refreshed))
        return True
    _v218inj_status(equip_id, nonce, 2,
                    'State changed but no refresh API was available; check log')
    return False


def process_menu(reason='tick'):
    """Removed in optimized1; retained only as a no-op compatibility symbol."""
    return False
    processed = False
    equip_id = _safe_int(sync_attrs.get('iAttachmentWeapon', 0), 0)
    catalog_nonce = _safe_int(sync_attrs.get('iAttachmentCatalogNonce', 0), 0)
    if catalog_nonce != _v218inj_seen['catalog']:
        _v218inj_seen['catalog'] = catalog_nonce
        if equip_id:
            _game_run('attachment-catalog', send_catalog,
                      equip_id, catalog_nonce)
            processed = True
    for mode, state_key, config_key in (
            ('manual', 'inject', 'iAttachmentInjectNonce'),
            ('max', 'max', 'iAttachmentMaxNonce')):
        nonce = _safe_int(sync_attrs.get(config_key, 0), 0)
        previous = _v218inj_seen[state_key]
        if previous is None:
            _v218inj_seen[state_key] = nonce
            continue
        if nonce == previous:
            continue
        _v218inj_seen[state_key] = nonce
        if not sync_attrs.get('bAttachmentHack', False):
            _v218inj_status(equip_id, nonce, 2, 'Attachment master is OFF')
            continue
        if not equip_id:
            _v218inj_log(('no-equip', mode, nonce),
                         'request has no equip id mode=%s nonce=%d reason=%s' %
                         (mode, nonce, reason))
            continue
        _game_run('attachment-inject', _v218inj_inject,
                  equip_id, mode, nonce)
        processed = True
    return processed


_plog('[ATTACH2] dedicated per-slot/Max-all menu injector ready')

# ---------------------------------------------------------------------------
# special-optics-1: authentic cosmetic optic models + reticles + iron sights.
# This is deliberately separate from ordinary attachments and weapon skins.
# Catalog rows come from GetGunOpticSkinItemList for the selected real gun.
# A scope/iron-sight row is applicable only with an authentic model id; a
# reticle-only write is never reported as a special optic model application.
# ---------------------------------------------------------------------------
_SPECIAL_OPTICS_BUILD = 'NEXORA-SPECIAL-OPTICS-1'
_v218so_log_seen = {}
_v218so_catalog_cache = {}
_v218so_seen = {'catalog': -1, 'apply': None, 'restore': None}
enforce_at = [0.0]
_v218so_case_state = {}
_v218so_tiers = {5: 'Ultra', 6: 'Eternal', 7: 'EVO', 8: 'Xtreme'}


def _v218so_log(key, message, limit=2):
    try:
        count = _v218so_log_seen.get(key, 0)
        if count >= limit:
            return
        if len(_v218so_log_seen) >= 180 and key not in _v218so_log_seen:
            return
        _v218so_log_seen[key] = count + 1
        _plog('[SPOPTIC] %s' % message)
    except Exception:
        pass


def _v218so_status(equip_id, nonce, level, text):
    equip_id = _safe_int(equip_id, 0)
    nonce = _safe_int(nonce, 0)
    level = max(0, min(2, _safe_int(level, 0)))
    text = _clean_catalog_text(text)[:300]
    if not equip_id or not text:
        return
    try:
        _write_udp_skin('ST|%d|%d|%d|%s\n' % (
            equip_id, nonce, level, text))
    except Exception:
        pass
    _v218so_log(('status', equip_id, nonce, level, text),
                'status equip=%d nonce=%d level=%d text=%s' % (
                    equip_id, nonce, level, text), 1)


def _v218so_item_id(item):
    if isinstance(item, (int, str)) and not isinstance(item, bool):
        return _safe_int(item, 0)
    for key in ('item_id', 'id'):
        try:
            value = getattr(item, key, None)
            if callable(value):
                value = value()
            value = _safe_int(value, 0)
            if value:
                return value
        except Exception:
            pass
        value = _safe_int(_proto_get(item, key, None), 0)
        if value:
            return value
    return 0


def _v218so_item_proto(item):
    for name in ('item_proto', 'proto', 'guise_item_proto'):
        try:
            proto = getattr(item, name, None)
            if proto is not None and _data_items(proto):
                return proto
        except Exception:
            pass
    if isinstance(item, dict):
        return item
    item_id = _v218so_item_id(item)
    if item_id:
        for module_name in ('gclient.data.lobby_gun_skin_item_data',
                            'gclient.data.lobby_item_data'):
            try:
                module = sys.modules.get(module_name)
                if module is None:
                    module = _import_module(module_name)
                proto = _data_get(getattr(module, 'data', None), item_id, None)
                if proto is not None:
                    return proto
            except Exception:
                continue
    return None


def _v218so_field(item, proto, names, default=None):
    for name in names:
        try:
            value = getattr(item, name, None)
            if callable(value):
                value = value()
            if value is not None:
                return value
        except Exception:
            pass
        value = _proto_get(proto, name, None)
        if value is not None:
            return value
    return default


def optic_type():
    try:
        _weapon_util, consts, _data = _v218att_modules()
        for part_type, part_name in part_types(consts):
            if 'optic' in str(part_name).lower():
                return _safe_int(part_type, 0)
        value = getattr(consts, 'WeaponPartType_Optic', 0)
        return _safe_int(value, 0)
    except Exception:
        return 0


def is_iron(part_id):
    try:
        weapon_util = _import_module('gshare.weapon_util')
        fn = getattr(weapon_util, 'IsDefaultOpticPart', None)
        if callable(fn):
            return bool(fn(part_id))
    except Exception as exc:
        _v218so_log(('iron-helper', repr(exc)),
                    'IsDefaultOpticPart failed part=%r error=%r' % (part_id, exc))
    return None


def _v218so_entry(item, gun_id, part_hint=0, require_tier=True):
    item_id = _v218so_item_id(item)
    if not item_id:
        return None, 'item'
    proto = _v218so_item_proto(item)
    guise_id = _safe_int(_v218so_field(item, proto, (
        'guise_id', 'skin_id', 'guise_template_id', 'skin_template_id',
        'template_id', 'skin', 'guise'), 0), 0)
    part_id = _safe_int(_v218so_field(item, proto, (
        'skin_optic_part_id', 'optic_part_id', 'part_id'), 0), 0) or part_hint
    quality = _safe_int(_v218so_field(item, proto, (
        'quality', 'rarity', 'grade'), 0), 0)
    info = (globals().get('WEP_SKIN_INFO') or {}).get(guise_id) or {}
    if not quality:
        quality = _safe_int(info.get('skin_quality'), 0)
    if require_tier and quality not in _v218so_tiers:
        return None, 'tier'
    try:
        util = _import_module('gclient.util.gun_skin_util')
        model_fn = getattr(util, 'GetGunOpticGuiseModelIdByItem', None)
        optic_fn = getattr(util, 'GetGunOpticGuiseOpticIdByItem', None)
        model_id = _safe_int(model_fn(item_id) if callable(model_fn) else 0, 0)
        optic_id = _safe_int(optic_fn(item_id) if callable(optic_fn) else 0, 0)
    except Exception as exc:
        _v218so_log(('helpers', gun_id, repr(exc)),
                    'optic helper failed gun=%d item=%d error=%r' % (
                        gun_id, item_id, exc))
        return None, 'helper'
    if not model_id and guise_id:
        try:
            model_fn = getattr(util, 'GetGunOpticGuiseModelIdByGuise', None)
            model_id = _safe_int(model_fn(guise_id) if callable(model_fn) else 0, 0)
        except Exception:
            pass
    if not optic_id:
        optic_id = _safe_int(_v218so_field(item, proto, (
            'skin_optic_id', 'optic_id', 'reticle_id',
            'reticle_template_id'), 0), 0)
    if not part_id:
        return None, 'part'
    if not model_id:
        return None, 'model'
    iron = is_iron(part_id)
    kind = 1 if iron is True else (2 if iron is False else 0)
    # A known scope needs its reticle as well as its mesh. Unknown/default
    # optic classes remain model-required and are diagnosed on device.
    if kind == 2 and not optic_id:
        return None, 'reticle'
    name = _english_display_text(_v218so_field(item, proto, (
        'name', 'en_name', 'english_name', 'name_en', 'skin_name'), ''), '')
    if not name:
        base = _display_text(info.get('name'), '')
        name = ('%s %s' % (base, 'iron sight' if kind == 1 else 'scope')).strip()
    if not name:
        name = 'Optic item %d' % item_id
    return {
        'item_id': item_id, 'guise_id': guise_id, 'part_id': part_id,
        'model_id': model_id, 'optic_id': optic_id, 'quality': quality,
        'tier': _v218so_tiers.get(quality, 'Authentic'), 'kind': kind,
        'name': _clean_catalog_text(name)[:150],
    }, None


def part_from_optic_data(optic_id, info, item_id):
    """Resolve compatibility from authentic optic/template data, never optic_id itself."""
    for record in (info, info.get('raw_effect_fields') or {}):
        for key in ('skin_optic_part_id', 'optic_part_id', 'part_id'):
            part_id = _safe_int(_proto_get(record, key, None), 0)
            if part_id:
                return part_id
    try:
        module = _import_module('gclient.data.gun_skin_optic_data')
        record = _data_get(getattr(module, 'data', None), optic_id, None)
        for key in ('skin_optic_part_id', 'optic_part_id', 'part_id',
                    'skin_optic_base_attachment_id'):
            part_id = _safe_int(_proto_get(record, key, None), 0)
            if part_id:
                return part_id
    except Exception:
        pass
    try:
        proto = _v218so_item_proto(item_id)
        for key in ('skin_optic_part_id', 'optic_part_id', 'part_id'):
            part_id = _safe_int(_proto_get(proto, key, None), 0)
            if part_id:
                return part_id
    except Exception:
        pass
    return 0


def template_rows(equip_id, gun_id):
    """All authentic rows for this gun, including optics absent from warehouse.

    GetGunOpticSkinItemList is built from warehouse guise items on some
    clients. WEP/SKIN_TO_ITEM already contain the real full client catalog;
    use only exact per-gun mappings and require optic-data compatibility.
    """
    rows = []
    wep = globals().get('WEP') or {}
    infos = globals().get('WEP_SKIN_INFO') or {}
    item_map = globals().get('SKIN_TO_ITEM') or {}
    equip_map = globals().get('SKIN_TO_EQUIP') or {}
    for skin_id in list(wep.get(equip_id) or [])[1:257]:
        skin_id = _safe_int(skin_id, 0)
        if not skin_id or _safe_int(equip_map.get(skin_id, equip_id), 0) != equip_id:
            continue
        info = infos.get(skin_id) or {}
        item_id = _safe_int(item_map.get(skin_id) or info.get('lobby_item_id'), 0)
        if not item_id:
            continue
        proto = _v218so_item_proto(item_id)
        quality = _safe_int(info.get('skin_quality'), 0) or _safe_int(
            _proto_get(proto, 'quality', _proto_get(proto, 'rarity', 0)), 0)
        name = _display_text(info.get('name'), '') or _english_display_text(
            _proto_get(proto, 'name', _proto_get(proto, 'skin_name', '')), '')
        rows.append({'item_id': item_id, 'guise_id': skin_id,
                     'quality': quality, 'name': name,
                     'skin_optic_part_id': 0})
    return rows


def _v218so_catalog(equip_id, refresh=False):
    equip_id = _safe_int(equip_id, 0)
    gun_id = _safe_int((globals().get('WEP_GUN_IDS') or {}).get(equip_id), 0)
    key = (equip_id, gun_id)
    now = time.time()
    cached = _v218so_catalog_cache.get(key)
    if cached and not refresh:
        ttl = 30.0 if cached.get('entries') else 1.0
        if now - cached.get('at', 0.0) < ttl:
            return list(cached.get('entries') or [])
    entries = []
    rejected = {}
    if not equip_id or not gun_id:
        return entries
    try:
        util = _import_module('gclient.util.gun_skin_util')
        list_fn = getattr(util, 'GetGunOpticSkinItemList', None)
        parts_fn = getattr(util, 'GetGunOpticReticlePartList', None)
        if not callable(list_fn):
            _v218so_log(('no-list', equip_id),
                        'GetGunOpticSkinItemList unavailable equip=%d gun=%d; using authentic client rows' % (
                            equip_id, gun_id))
        groups = []
        if callable(list_fn):
            _v218so_log(('signature', gun_id),
                        'catalog gun=%d list%s parts%s' % (
                            gun_id, inspect.signature(list_fn),
                            inspect.signature(parts_fn) if callable(parts_fn) else '?'), 1)
            groups = [(0, list_fn(gun_id))]
            # The all-parts call is authoritative. Per-part calls are a fallback
            # for clients that omit skin_optic_part_id on returned IHallItems.
            raw_items = list(groups[0][1] or ())[:256]
            needs_parts = not raw_items
            if not needs_parts:
                for raw in raw_items[:32]:
                    proto = _v218so_item_proto(raw)
                    if not _safe_int(_v218so_field(raw, proto, (
                            'skin_optic_part_id', 'optic_part_id', 'part_id'), 0), 0):
                        needs_parts = True
                        break
            if needs_parts and callable(parts_fn):
                for part_id in list(parts_fn(gun_id) or ())[:32]:
                    part_id = _safe_int(part_id, 0)
                    if part_id:
                        groups.append((part_id, list_fn(gun_id, part_id)))
        seen = set()
        sample_logged = False
        for part_hint, raw_group in groups:
            for raw in list(raw_group or ())[:256]:
                if not sample_logged:
                    sample_logged = True
                    proto = _v218so_item_proto(raw)
                    _v218so_log(('row', gun_id),
                                'authentic row gun=%d class=%s item=%d keys=%r' % (
                                    gun_id, type(raw).__name__, _v218so_item_id(raw),
                                    _proto_keys(proto, 60)), 1)
                entry, reason = _v218so_entry(raw, gun_id, part_hint)
                if not entry:
                    rejected[reason or 'unknown'] = rejected.get(reason or 'unknown', 0) + 1
                    continue
                identity = (entry['item_id'], entry['part_id'], entry['model_id'],
                            entry['optic_id'])
                if identity in seen:
                    continue
                seen.add(identity)
                entry['source'] = 'warehouse'
                entries.append(entry)
        # Merge the full authentic client catalog as well. This is what keeps
        # unowned Ultra/Eternal/EVO/Xtreme optics visible when the warehouse
        # helper returns only the account's owned guise items.
        optic_fn = getattr(util, 'GetGunOpticGuiseOpticIdByItem', None)
        for raw in template_rows(equip_id, gun_id):
            item_id = raw['item_id']
            optic_id = _safe_int(optic_fn(item_id) if callable(optic_fn) else 0, 0)
            raw['skin_optic_part_id'] = part_from_optic_data(
                optic_id, (globals().get('WEP_SKIN_INFO') or {}).get(
                    raw.get('guise_id'), {}) or {}, item_id)
            entry, reason = _v218so_entry(raw, gun_id, raw['skin_optic_part_id'])
            if not entry:
                rejected[reason or 'unknown'] = rejected.get(reason or 'unknown', 0) + 1
                continue
            identity = (entry['item_id'], entry['part_id'], entry['model_id'],
                        entry['optic_id'])
            if identity in seen:
                continue
            seen.add(identity)
            entry['source'] = 'client-catalog'
            entries.append(entry)
    except Exception as exc:
        _v218so_log(('catalog', equip_id, repr(exc)),
                    'catalog guarded error equip=%d gun=%d error=%r' % (
                        equip_id, gun_id, exc), 1)
    entries.sort(key=lambda row: (-row['quality'], row['kind'],
                                  row['name'].lower(), row['item_id']))
    for index, entry in enumerate(entries, 1):
        entry['index'] = index
    if len(_v218so_catalog_cache) >= 64:
        _v218so_catalog_cache.clear()
    _v218so_catalog_cache[key] = {'at': now, 'entries': list(entries)}
    tier_counts = {tier: sum(1 for row in entries if row['tier'] == tier)
                   for tier in ('Ultra', 'Eternal', 'EVO', 'Xtreme')}
    _v218so_log(('detail', equip_id, len(entries), tuple(sorted(rejected.items()))),
                'catalog equip=%d gun=%d entries=%d tiers=%r rejected=%r sample=%r' % (
                    equip_id, gun_id, len(entries), tier_counts, rejected,
                    [(row['index'], row['name'], row['part_id'], row['model_id'])
                     for row in entries[:6]]), 1)
    return entries


def _v218so_send_catalog(equip_id, nonce=0):
    equip_id = _safe_int(equip_id, 0)
    entries = _v218so_catalog(equip_id, refresh=True)
    lines = ['SBEGIN|%d' % equip_id]
    for entry in entries[:256]:
        lines.append('SO|%d|%d|%d|%d|%d|%d|%d|%d|%s' % (
            equip_id, entry['index'], entry['item_id'], entry['part_id'],
            entry['model_id'], entry['quality'], entry['kind'],
            entry.get('optic_id', 0), _clean_catalog_text(entry['name'])[:150]))
    lines.append('SEND|%d' % equip_id)
    _write_udp_chunked(_write_udp_skin, '\n'.join(lines) + '\n')
    if entries:
        _v218so_status(equip_id, nonce, 0,
                       'Authentic model catalog ready: %d optic(s); visual check required' % len(entries))
    else:
        _v218so_status(equip_id, nonce, 2,
                       'No model-complete Ultra/Eternal/EVO/Xtreme optics for this gun; see [SPOPTIC]')
    return bool(entries)


def _v218so_selected(equip_id):
    entries = _v218so_catalog(equip_id)
    index = _safe_int(sync_attrs.get('iSpecialOptic_%d' % equip_id, 0), 0)
    item_id = _safe_int(sync_attrs.get('iSpecialOpticItem_%d' % equip_id, 0), 0)
    part_id = _safe_int(sync_attrs.get('iSpecialOpticPart_%d' % equip_id, 0), 0)
    if item_id and part_id:
        for entry in entries:
            if entry.get('item_id') == item_id and entry.get('part_id') == part_id:
                return entry
        _v218so_log(('reject-item', equip_id, item_id, part_id),
                    'reject non-catalog item equip=%d item=%d part=%d' % (
                        equip_id, item_id, part_id), 1)
        return None
    if index <= 0:
        return None
    for entry in entries:
        if entry.get('index') == index:
            return entry
    _v218so_log(('reject-index', equip_id, index),
                'reject non-catalog selection equip=%d index=%d' % (equip_id, index), 1)
    return None


def _v218so_bind(fn, values):
    """Bind only explicitly understood parameter names; never guess required args."""
    try:
        params = inspect.signature(fn).parameters
    except Exception:
        return None
    args, kwargs = [], {}
    for name, param in params.items():
        if name == 'self':
            continue
        if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            continue
        if name in values:
            value = values[name]
        elif param.default is not inspect.Parameter.empty:
            continue
        else:
            return None
        if param.kind == param.POSITIONAL_ONLY:
            args.append(value)
        else:
            kwargs[name] = value
    return args, kwargs


def _v218so_named_call(target, method_name, values):
    try:
        fn = getattr(target, method_name, None)
        if not callable(fn):
            return False, None, 'missing'
        bound = _v218so_bind(fn, values)
        if bound is None:
            _v218so_log(('signature', type(target).__name__, method_name),
                        'unsupported signature case=%s method=%s signature=%s' % (
                            type(target).__name__, method_name, inspect.signature(fn)), 1)
            return False, None, 'signature'
        args, kwargs = bound
        result = fn(*args, **kwargs)
        return result is not False, result, None
    except Exception as exc:
        _v218so_log(('call', type(target).__name__, method_name, repr(exc)),
                    'call failed case=%s method=%s error=%r' % (
                        type(target).__name__, method_name, exc), 1)
        return False, None, repr(exc)


def mapping_key(mapping, part_type):
    keys = [key for key, _value in _data_items(mapping)]
    if part_type in keys:
        return part_type
    if str(part_type) in keys:
        return str(part_type)
    if keys and all(isinstance(key, str) for key in keys):
        return str(part_type)
    return part_type


def attr_snapshot(target, attr, part_type):
    try:
        mapping = getattr(target, attr, None)
    except Exception:
        mapping = None
    if isinstance(mapping, (list, tuple)):
        if 0 <= part_type < len(mapping):
            return {'target': target, 'attr': attr, 'mapping': mapping,
                    'key': part_type, 'found': True,
                    'old': mapping[part_type], 'shape': 'sequence'}
        return {'target': target, 'attr': attr, 'mapping': mapping,
                'key': part_type, 'found': False, 'old': 0, 'shape': 'sequence'}
    if mapping is None:
        return {'target': target, 'attr': attr, 'mapping': None,
                'key': part_type, 'found': False, 'old': 0, 'shape': 'missing'}
    key = mapping_key(mapping, part_type)
    found = any(k == key for k, _v in _data_items(mapping))
    return {'target': target, 'attr': attr, 'mapping': mapping, 'key': key,
            'found': found, 'old': _proto_get(mapping, key, None),
            'shape': 'mapping'}


def attr_write(snapshot, value):
    mapping = snapshot.get('mapping')
    key = snapshot.get('key')
    if mapping is None:
        return False
    try:
        if snapshot.get('shape') == 'sequence':
            if not (0 <= key < len(mapping)):
                return False
            old = mapping[key]
            if old is not None and not isinstance(old, (int, str)):
                return False
            new_value = str(value) if isinstance(old, str) else value
            if isinstance(mapping, tuple):
                mutable = list(mapping)
                mutable[key] = new_value
                setattr(snapshot.get('target'), snapshot.get('attr'), tuple(mutable))
            else:
                mapping[key] = new_value
            return True
        old = _proto_get(mapping, key, None)
        entries = _data_items(mapping)
        object_map = any(v is not None and not isinstance(v, (int, str))
                         for _k, v in entries[:8])
        if object_map:
            return False
        if old is not None and not isinstance(old, (int, str)):
            return False
        mapping[key] = str(value) if isinstance(old, str) else value
        return True
    except Exception:
        return False


def attr_restore(snapshot):
    mapping = snapshot.get('mapping')
    key = snapshot.get('key')
    if mapping is None:
        return False
    if snapshot.get('found'):
        return attr_write(snapshot, snapshot.get('old') or 0)
    try:
        if snapshot.get('shape') == 'sequence':
            if 0 <= key < len(mapping):
                mapping[key] = 0
                return True
        elif hasattr(mapping, 'pop'):
            mapping.pop(key, None)
            return True
        elif hasattr(mapping, '__delitem__'):
            del mapping[key]
            return True
    except Exception:
        pass
    return False


def _v218so_guise_match(target, part_type, entry):
    try:
        mapping = getattr(target, 'part_guise_info', None)
        if mapping is None:
            return None
        key = mapping_key(mapping, part_type)
        if not any(k == key for k, _v in _data_items(mapping)):
            return None
        value = _proto_get(mapping, key, None)
        if isinstance(value, (int, str)):
            return _safe_int(value, 0) == entry['item_id']
        for name in ('item_id', 'guise_item_id', 'id'):
            item_id = _safe_int(getattr(value, name, 0), 0)
            if item_id:
                return item_id == entry['item_id']
    except Exception:
        pass
    return None


def _v218so_values(part_type, entry, guise_info=None):
    item_id = entry.get('item_id', 0)
    guise_id = entry.get('guise_id', 0)
    part_id = entry.get('part_id', 0)
    values = {
        'part_type': part_type, 'weapon_part_type': part_type,
        'part_id': part_id, 'optic_part_id': part_id, 'weapon_part_id': part_id,
        'item_id': item_id, 'guise_item_id': item_id,
        'optic_guise_item_id': item_id, 'optic_part_guise_item_id': item_id,
        'part_guise_item_id': item_id, 'guise_id': guise_id,
        'guise_template_id': guise_id, 'template_id': guise_id,
        'skin_optic_id': entry.get('optic_id', 0),
        'optic_id': entry.get('optic_id', 0),
        'reticle_id': entry.get('optic_id', 0),
        'data_changed': True, 'force_refresh': True, 'need_refresh': True,
        'refresh': True, 'need_callback': False, 'is_init': False,
    }
    if guise_info is not None:
        values['part_guise_info'] = guise_info
    return values


def _v218so_refresh(target, values):
    called = []
    for method in ('RefreshWeaponOpticReticle', 'RefreshLaserAndOptic',
                   'RefreshOpticMaterial', 'RefreshOpticScopeEnable'):
        ok, _result, error = _v218so_named_call(target, method, values)
        if ok:
            called.append(method)
    return called


def _v218so_apply_target(target, entry, manual=False):
    part_type = optic_type()
    if not part_type or not entry.get('model_id'):
        return {'ok': False, 'error': 'missing optic type or authentic model'}
    signature = (entry['index'], entry['item_id'], entry['part_id'],
                 entry['model_id'], entry.get('optic_id', 0))
    state = _v218so_case_state.get(id(target))
    now = time.time()
    if not manual and state and now - state.get('at', 0.0) < 5.0:
        return {'ok': False, 'error': 'retry window', 'signature': signature}
    slot = attr_snapshot(target, 'part_slots', part_type)
    guise = attr_snapshot(target, 'part_guise_info', part_type)
    if state is None:
        old_reticle = 0
        for attr in ('skin_optic_id', 'optic_id', 'reticle_id'):
            old_reticle = _safe_int(getattr(target, attr, 0), 0)
            if old_reticle:
                break
        state = {'backup': {'slot': slot, 'guise': guise, 'reticle': old_reticle}}
        _v218so_case_state[id(target)] = state
    if len(_v218so_case_state) > 40:
        for key in list(_v218so_case_state)[:-40]:
            _v218so_case_state.pop(key, None)
    state['at'] = now
    state['signature'] = signature
    part_match = _v218att_match(target, {part_type: entry['part_id']})
    guise_match = _v218so_guise_match(target, part_type, entry)
    if part_match is True and guise_match is True and state.get('applied') == signature:
        return {'ok': True, 'already': True, 'signature': signature}
    slot_changed = False if part_match is True else attr_write(slot, entry['part_id'])
    guise_changed = False if guise_match is True else attr_write(guise, entry['item_id'])
    if slot_changed:
        try:
            fn = getattr(target, 'UpdateGuisePartSlots', None)
            if callable(fn):
                fn(part_type, entry['part_id'])
        except Exception:
            pass
    values = _v218so_values(part_type, entry, getattr(target, 'part_guise_info', None))
    native_ok, _native_result, native_error = _v218so_named_call(
        target, 'ChangeWeaponPartGuise', values)
    model_path = native_ok or guise_changed or guise_match is True
    if not model_path:
        # Do not leave a base-part change or a reticle-only result behind when
        # the cosmetic model/guise path is unavailable.
        attr_restore(slot)
        attr_restore(guise)
        state['applied'] = None
        return {'ok': False, 'error': 'no authentic optic model write path',
                'native_error': native_error, 'signature': signature}
    try:
        try_dlc_download(entry['item_id'], [])
    except Exception:
        pass
    reticle_ok = False
    if entry.get('optic_id'):
        for method in ('ChangeWeaponOpticReticle', 'ChangeOpticReticle',
                       'SetOpticReticle'):
            reticle_ok, _result, _error = _v218so_named_call(target, method, values)
            if reticle_ok:
                break
    refreshed = _v218so_refresh(target, values)
    rebuild, _rebuild_result = _v218inj_rebuild(target)
    part_after = _v218att_match(target, {part_type: entry['part_id']})
    guise_after = _v218so_guise_match(target, part_type, entry)
    if part_after is False or guise_after is False:
        state['applied'] = None
        return {'ok': False, 'error': 'game restored previous optic state',
                'part_match': part_after, 'guise_match': guise_after,
                'native': native_ok, 'reticle': reticle_ok,
                'refresh': refreshed, 'rebuild': rebuild, 'signature': signature}
    state['applied'] = signature
    return {'ok': True, 'verified': part_after is True and guise_after is not False,
            'native': native_ok, 'guise_write': guise_changed,
            'reticle': reticle_ok or not entry.get('optic_id'),
            'refresh': refreshed, 'rebuild': rebuild, 'signature': signature}


def _v218so_apply(equip_id, nonce=0):
    equip_id = _safe_int(equip_id, 0)
    if not sync_attrs.get('bSpecialOpticHack', False):
        _v218so_status(equip_id, nonce, 2, 'Special Optics master is OFF')
        return False
    entry = _v218so_selected(equip_id)
    if not entry:
        _v218so_status(equip_id, nonce, 2, 'Choose an authentic special optic first')
        return False
    targets = _v218inj_targets(equip_id)
    if not targets:
        _v218so_status(equip_id, nonce, 2,
                       'No live case for this gun; equip/hold it and retry')
        return False
    results = []
    for target in targets:
        result = _v218so_apply_target(target, entry, manual=True)
        results.append(result)
        _v218so_log(('apply', id(target), repr(result.get('signature')),
                     result.get('ok'), result.get('error')),
                    'apply case=%s equip=%d entry=%r result=%r' % (
                        type(target).__name__, equip_id, entry, result), 1)
    good = [result for result in results if result.get('ok')]
    if not good:
        error = next((result.get('error') for result in results if result.get('error')),
                     'unsupported optic path')
        _v218so_status(equip_id, nonce, 2, '%s; reticle-only fallback refused' % error)
        return False
    verified = sum(1 for result in good if result.get('verified'))
    _v218so_status(equip_id, nonce, 0,
                   '%s: model path on %d target(s), state verified %d; visual scope/reticle check required' % (
                       entry['name'], len(good), verified))
    return True


def _v218so_restore(equip_id, nonce=0):
    equip_id = _safe_int(equip_id, 0)
    targets = _v218inj_targets(equip_id)
    if not targets:
        _v218so_status(equip_id, nonce, 2, 'No live case for this gun; restore unavailable')
        return False
    part_type = optic_type()
    restored = 0
    for target in targets:
        state = _v218so_case_state.get(id(target))
        backup = (state or {}).get('backup') or {}
        if not backup:
            continue
        slot_ok = attr_restore(backup.get('slot') or {})
        guise_ok = attr_restore(backup.get('guise') or {})
        old_part = _safe_int((backup.get('slot') or {}).get('old'), 0)
        old_item = _safe_int((backup.get('guise') or {}).get('old'), 0)
        entry = {'item_id': old_item, 'guise_id': 0, 'part_id': old_part,
                 'optic_id': _safe_int(backup.get('reticle'), 0)}
        values = _v218so_values(part_type, entry, getattr(target, 'part_guise_info', None))
        native_ok, _r, _e = _v218so_named_call(target, 'ChangeWeaponPartGuise', values)
        # Zero is the authentic default-reticle reset on the same existing
        # setter; do not leave the special reticle behind after Restore.
        _v218so_named_call(target, 'ChangeWeaponOpticReticle', values)
        _v218so_refresh(target, values)
        rebuild, _result = _v218inj_rebuild(target)
        if slot_ok or guise_ok or native_ok or rebuild:
            restored += 1
        _v218so_case_state.pop(id(target), None)
    if restored:
        _v218so_status(equip_id, nonce, 0,
                       'Pre-special optic state restored on %d target(s); visual check required' % restored)
        return True
    _v218so_status(equip_id, nonce, 2, 'No pre-special optic snapshot was available')
    return False


def enforce_now(reason='tick'):
    if not sync_attrs.get('bSpecialOpticHack', False):
        return False
    attempted = False
    for (equip_id, _gun_id), cached in list(_v218so_catalog_cache.items())[:64]:
        index = _safe_int(sync_attrs.get('iSpecialOptic_%d' % equip_id, 0), 0)
        item_id = _safe_int(sync_attrs.get('iSpecialOpticItem_%d' % equip_id, 0), 0)
        part_id = _safe_int(sync_attrs.get('iSpecialOpticPart_%d' % equip_id, 0), 0)
        if item_id and part_id:
            entry = next((row for row in (cached.get('entries') or [])
                          if row.get('item_id') == item_id and
                          row.get('part_id') == part_id), None)
        else:
            entry = next((row for row in (cached.get('entries') or [])
                          if index > 0 and row.get('index') == index), None)
        if not entry:
            continue
        for target in _v218inj_targets(equip_id):
            state = _v218so_case_state.get(id(target)) or {}
            signature = (entry['index'], entry['item_id'], entry['part_id'],
                         entry['model_id'], entry.get('optic_id', 0))
            part_type = optic_type()
            if (state.get('applied') == signature and
                    _v218so_guise_match(target, part_type, entry) is not False):
                continue
            result = _v218so_apply_target(target, entry, manual=False)
            attempted = attempted or result.get('ok', False)
            _v218so_log(('enforce', id(target), signature, result.get('ok'), result.get('error')),
                        'enforce reason=%s equip=%d result=%r' % (reason, equip_id, result), 1)
    return attempted


def _v218so_enforce(reason='tick'):
    # optimized1: no background special-optic enforcement, even from old config.
    return False
    if not sync_attrs.get('bSpecialOpticHack', False):
        return False
    now = time.time()
    if now - enforce_at[0] < 2.0:
        return False
    enforce_at[0] = now
    return _game_run('special-optic-enforce', enforce_now, reason)


def _v218so_process_menu(reason='tick'):
    # optimized1: no catalog/apply/restore requests from stale saved nonces.
    return False
    processed = False
    equip_id = _safe_int(sync_attrs.get('iSpecialOpticWeapon', 0), 0)
    catalog_nonce = _safe_int(sync_attrs.get('iSpecialOpticCatalogNonce', 0), 0)
    if catalog_nonce != _v218so_seen['catalog']:
        _v218so_seen['catalog'] = catalog_nonce
        if equip_id:
            _game_run('special-optic-catalog', _v218so_send_catalog,
                      equip_id, catalog_nonce)
            processed = True
    for mode, config_key in (('apply', 'iSpecialOpticApplyNonce'),
                             ('restore', 'iSpecialOpticRestoreNonce')):
        nonce = _safe_int(sync_attrs.get(config_key, 0), 0)
        previous = _v218so_seen[mode]
        if previous is None:
            _v218so_seen[mode] = nonce
            continue
        if nonce == previous:
            continue
        _v218so_seen[mode] = nonce
        if not equip_id:
            continue
        if mode == 'apply':
            _game_run('special-optic-apply', _v218so_apply, equip_id, nonce)
        else:
            _game_run('special-optic-restore', _v218so_restore, equip_id, nonce)
        processed = True
    return processed


_plog('[SPOPTIC] authentic model/reticle/iron-sight layer ready (%s)' % _SPECIAL_OPTICS_BUILD)


# ============================================================================
# scopesync-1: automatic authentic optic cosmetics for the equipped real part.
# The selected skin item, guise/template, optic model and reticle are distinct
# namespaces.  The real attachment ID is preserved and no donor optic is allowed.
# ============================================================================
_SCOPE_SYNC_BUILD = 'NEXORA-SCOPESYNC-2'
resolve_cache = {}
case_state = {}
_v218scope_log_seen = {}
tick_at = [0.0]
hook_at = [0.0]
_v218scope_hooked = [False]


def _v218scope_log(key, message, limit=2):
    try:
        count = _v218scope_log_seen.get(key, 0)
        if count >= limit:
            return
        if len(_v218scope_log_seen) >= 180 and key not in _v218scope_log_seen:
            return
        _v218scope_log_seen[key] = count + 1
        _plog('[SCOPESYNC] %s' % message)
    except Exception:
        pass


def selected_item(skin_id):
    """Return only the authentic lobby item mapping; never reuse template_id."""
    skin_id = _safe_int(skin_id, 0)
    info = (globals().get('WEP_SKIN_INFO') or {}).get(skin_id) or {}
    return _safe_int((globals().get('SKIN_TO_ITEM') or {}).get(skin_id)
                     or info.get('lobby_item_id'), 0)


def equipped_part(case, part_type):
    """Read (real_part_id, readable), using the existing shape-safe slot rules."""
    part_type = _safe_int(part_type, 0)
    if case is None or not part_type:
        return 0, False
    try:
        slots = getattr(case, 'part_slots', None)
    except Exception:
        slots = None
    if isinstance(slots, (list, tuple)):
        if 0 <= part_type < len(slots):
            return value_id(slots[part_type]), True
        return 0, True
    if slots is not None:
        try:
            entries = _data_items(slots)
            if entries:
                keys = {key for key, _value in entries}
                key = _v218att_slot_key(keys, part_type)
                if key not in keys:
                    return 0, True
                return value_id(_proto_get(slots, key, None)), True
            if isinstance(slots, dict) or hasattr(slots, 'items'):
                return 0, True
        except Exception:
            pass
    try:
        getter = getattr(case, 'GetWeaponPart', None)
        if callable(getter):
            return value_id(getter(part_type)), True
    except Exception:
        pass
    # These are secondary live-case fields, not the skin template's similarly
    # named skin_optic_part_id (which is not evidence of the equipped part).
    for name in ('cur_optic_part_id', 'optic_part_id'):
        try:
            value = getattr(case, name, None)
            if value is not None:
                return value_id(value), True
        except Exception:
            pass
    try:
        nested = getattr(case, 'weapon_case', None)
        if nested is not None and nested is not case:
            return equipped_part(nested, part_type)
    except Exception:
        pass
    return 0, False


def ads_state(case=None):
    """Return the real ADS bool, or None when an in-match state is unreadable."""
    objects = []
    try:
        getter = globals().get('_local_combat_avatar')
        local = getter() if callable(getter) else None
        if local is not None:
            objects.append(local)
    except Exception:
        pass
    if case is not None:
        objects.append(case)
        try:
            nested = getattr(case, 'weapon_case', None)
            if nested is not None and nested is not case:
                objects.append(nested)
        except Exception:
            pass
    for obj in objects:
        seen = False
        ads = False
        for name in ('is_ads', 'is_real_ads'):
            try:
                value = getattr(obj, name, None)
                if callable(value):
                    value = value()
                if value is not None:
                    seen = True
                    ads = ads or bool(value)
            except Exception:
                pass
        if seen:
            return ads
    try:
        in_match = globals().get('_hero_in_match')
        if callable(in_match) and not in_match():
            return False
    except Exception:
        pass
    return None


def exact_entry(raw, gun_id, skin_id, item_id, part_id, source):
    """Parse one authentic row, then enforce exact item + equipped-part identity."""
    entry, _reason = _v218so_entry(raw, gun_id, part_id, require_tier=False)
    if not entry:
        return None
    if entry.get('item_id') != item_id or entry.get('part_id') != part_id:
        return None
    guise_id = _safe_int(entry.get('guise_id'), 0)
    if guise_id and guise_id != skin_id:
        return None
    # An exact SKIN_TO_ITEM row is already bound to this template.  A missing
    # display-side guise field is filled for bookkeeping only, never for native
    # model lookup or as a substitute for item compatibility.
    entry['guise_id'] = skin_id
    entry['source'] = source
    return entry


def _v218scope_resolve(equip_id, skin_id, part_id, refresh=False):
    """Resolve only (this equip, this selected item, this real equipped part)."""
    equip_id = _safe_int(equip_id, 0)
    skin_id = _safe_int(skin_id, 0)
    part_id = _safe_int(part_id, 0)
    item_id = selected_item(skin_id)
    info = (globals().get('WEP_SKIN_INFO') or {}).get(skin_id) or {}
    gun_id = _safe_int((globals().get('WEP_GUN_IDS') or {}).get(equip_id), 0)
    if not gun_id:
        gun_id = _safe_int(_skin_raw_field(info, 'gun_id'), 0)
    key = (equip_id, gun_id, skin_id, item_id, part_id)
    now = time.time()
    cached = resolve_cache.get(key)
    if cached and not refresh:
        # v2.112: the 15s negative TTL re-ran the full catalog
        # search on the game frame every ~15s -> the 20-52s
        # loadout/pickup freezes (debug-12).  The variant tables
        # do not change mid-session: cache both outcomes 1h.
        ttl = 3600.0
        if now - cached.get('at', 0.0) < ttl:
            return cached.get('entry')
    result = None
    ambiguous = False
    if equip_id and gun_id and skin_id and item_id and part_id:
        try:
            util = _import_module('gclient.util.gun_skin_util')
            list_fn = getattr(util, 'GetGunOpticSkinItemList', None)
            matches = {}
            if callable(list_fn):
                try:
                    raw_items = list_fn(gun_id, part_id)
                except TypeError:
                    # Older helpers without the optional part argument get one
                    # bounded all-parts call; exact part filtering still applies.
                    raw_items = list_fn(gun_id)
                for raw in list(raw_items or ())[:256]:
                    entry = exact_entry(
                        raw, gun_id, skin_id, item_id, part_id,
                        'GetGunOpticSkinItemList(gun_id, part_id)')
                    if not entry:
                        continue
                    identity = (entry['item_id'], entry['guise_id'],
                                entry['part_id'], entry['model_id'],
                                entry.get('optic_id', 0))
                    matches[identity] = entry
            if len(matches) == 1:
                result = next(iter(matches.values()))
            elif len(matches) > 1:
                # Two different authentic models/reticles for the same exact
                # key are ambiguous.  Never pick one by list order.
                ambiguous = True
                _v218scope_log(('ambiguous', key),
                               'ambiguous authentic variants key=%r count=%d; optic unchanged'
                               % (key, len(matches)), 1)
            if result is None and not ambiguous:
                # Unowned/injected items can be absent from the warehouse list.
                # Fallback is allowed only when the selected item's own optic
                # data proves this exact part; feature names alone are insufficient.
                optic_fn = getattr(util, 'GetGunOpticGuiseOpticIdByItem', None)
                optic_id = _safe_int(optic_fn(item_id) if callable(optic_fn) else 0, 0)
                proven_part = part_from_optic_data(optic_id, info, item_id)
                if proven_part == part_id:
                    raw = {
                        'item_id': item_id, 'guise_id': skin_id,
                        'skin_optic_part_id': part_id,
                        'quality': _safe_int(info.get('skin_quality'), 0),
                        'name': info.get('name') or '',
                    }
                    result = exact_entry(
                        raw, gun_id, skin_id, item_id, part_id,
                        'selected-item exact optic-data')
        except Exception as exc:
            _v218scope_log(('resolve-error', key, repr(exc)),
                           'resolver guarded error key=%r error=%r' % (key, exc), 1)
    if len(resolve_cache) >= 64 and key not in resolve_cache:
        resolve_cache.clear()
    resolve_cache[key] = {'at': now, 'entry': result}
    return result


def named_call(target, method_name, values):
    """Bind logged native names only; unknown required arguments fail closed."""
    try:
        fn = getattr(target, method_name, None)
        if not callable(fn):
            return False, None, 'missing'
        bound = _v218so_bind(fn, values)
        if bound is None:
            _v218scope_log(('signature', type(target).__name__, method_name),
                           'unsupported signature case=%s method=%s signature=%s'
                           % (type(target).__name__, method_name, inspect.signature(fn)), 1)
            return False, None, 'signature'
        args, kwargs = bound
        result = fn(*args, **kwargs)
        return result is not False, result, None
    except Exception as exc:
        _v218scope_log(('call', type(target).__name__, method_name, repr(exc)),
                       'call failed case=%s method=%s error=%r'
                       % (type(target).__name__, method_name, exc), 1)
        return False, None, repr(exc)


def _v218scope_guise_info(case, part_type, item_id):
    """Copy cosmetic guise state and replace only its optic item, never parts."""
    try:
        current = getattr(case, 'part_guise_info', None)
    except Exception:
        current = None
    if current is None:
        return None
    if isinstance(current, (list, tuple)):
        if not (0 <= part_type < len(current)):
            return None
        old = current[part_type]
        if old is not None and not isinstance(old, (int, str)):
            return None
        mutable = list(current)
        mutable[part_type] = str(item_id) if isinstance(old, str) else item_id
        return tuple(mutable) if isinstance(current, tuple) else mutable
    try:
        entries = _data_items(current)
        if not entries and not (isinstance(current, dict) or hasattr(current, 'items')):
            return None
        keys = {key for key, _value in entries}
        key = mapping_key(current, part_type)
        old = _proto_get(current, key, None)
        if old is not None and not isinstance(old, (int, str)):
            return None
        try:
            updated = current.copy()
        except Exception:
            updated = dict(entries)
        updated[key] = str(item_id) if isinstance(old, str) else item_id
        return updated
    except Exception:
        return None


def _v218scope_values(case, part_type, entry, guise_info=None, ads=None):
    """Explicit native argument namespaces from the device-proven signatures."""
    values = {
        'part_type': part_type,
        'part_id': entry['part_id'],
        'item_id': entry['item_id'],
        'guise_item_id': entry['item_id'],
        'guise_id': entry.get('guise_id', 0),
        'model_id': entry['model_id'],
        'reticle_template_id': entry.get('optic_id', 0),
        'refresh_model': True,
        'data_changed': True,
        # This is the critical cosmetic-only contract.  True was the native
        # default and could replace the player's real attachment.
        'change_part': False,
        'part_loaded_callback': None,
    }
    if guise_info is not None:
        values['part_guise_info'] = guise_info
    if ads is not None:
        values['is_ads'] = bool(ads)
    return values


def _v218scope_refresh(case, part_type, entry, ads):
    """Refresh reticle/model/material with the actual ADS state, never a constant."""
    values = _v218scope_values(case, part_type, entry, ads=ads)
    called = []
    errors = {}
    for method in ('RefreshWeaponOpticReticle', 'RefreshLaserAndOptic'):
        ok, _result, error = named_call(case, method, values)
        if ok:
            called.append(method)
        elif error not in (None, 'missing'):
            errors[method] = error
    if ads is None:
        errors['is_ads'] = 'unreadable in-match ADS state'
        return called, errors
    for method in ('RefreshOpticMaterial', 'RefreshOpticScopeEnable',
                   'RefreshOpticModelForAds', 'RefreshOpticEffect'):
        ok, _result, error = named_call(case, method, values)
        if ok:
            called.append(method)
        elif error not in (None, 'missing'):
            errors[method] = error
    return called, errors


def _v218scope_reload(case, part_type, entry, ads):
    """Reload the optic mesh with the exact same real attachment part.

    ChangeWeaponPartGuise(change_part=False) updates cosmetic state without
    giving ScopeSync a mesh-load completion.  The runtime code index identifies
    AddWeaponPart as the authentic local model path used by the native UI.
    Passing the already-equipped part ID reloads its skinned mesh; it never
    selects a donor part or changes magnification.
    """
    values = _v218scope_values(case, part_type, entry, ads=ads)

    def loaded(*_args):
        # Model loading may complete after another Modify operation.  Never
        # let a stale callback restore an older optic cosmetic.
        try:
            current_part, readable = equipped_part(case, part_type)
            if (not readable or current_part != entry['part_id'] or
                    _v218so_guise_match(case, part_type, entry) is False):
                _v218scope_log(('stale-load', id(case), entry['item_id'],
                                current_part),
                               'post-load ignored equip part=%r expected=%d item=%d'
                               % (current_part, entry['part_id'], entry['item_id']), 1)
                return
            live_ads = ads_state(case)
            if live_ads is None:
                live_ads = ads
            post_values = _v218scope_values(
                case, part_type, entry, ads=live_ads)
            reticle_ok = True
            reticle_error = None
            if entry.get('optic_id'):
                reticle_ok, _result, reticle_error = named_call(
                    case, 'ChangeWeaponOpticReticle', post_values)
            refreshed, errors = _v218scope_refresh(
                case, part_type, entry, live_ads)
            _v218scope_log(('post-load', id(case), entry['item_id'],
                            entry['part_id']),
                           'post-load case=%s part=%d item=%d reticle_ok=%r '
                           'ads=%r refresh=%r errors=%r reticle_error=%r'
                           % (type(case).__name__, entry['part_id'],
                              entry['item_id'], reticle_ok, live_ads,
                              refreshed, errors, reticle_error), 1)
        except Exception as exc:
            _v218scope_log(('post-load-error', id(case), repr(exc)),
                           'post-load callback guarded error=%r' % (exc,), 1)

    values['part_loaded_callback'] = loaded
    return named_call(case, 'AddWeaponPart', values)


def apply_case(case, equip_id, skin_id, part_type, part_id,
                          entry, ads, reason='apply'):
    """Apply one resolved cosmetic; return honest native/state evidence only."""
    item_id = entry['item_id']
    signature = (equip_id, skin_id, item_id, part_id,
                 entry['model_id'], entry.get('optic_id', 0))
    # v2.90: a rebuilt case after a kill re-ran this apply and AddWeaponPart's
    # synchronous MESH RELOAD froze the game thread (24-93s stalls logged
    # right after 'Modify/loadout InitWeapon').  When the case already carries
    # this exact part + guise there is nothing to reload - skip it all.
    _same_part_299 = False
    try:
        _pa290 = equipped_part(case, part_type)
        if _pa290[1] and _pa290[0] == part_id:
            _same_part_299 = True
            if _v218so_guise_match(case, part_type, entry):
                return {'ok': True, 'state_verified': True,
                        'visual_verified': True, 'native': True, 'reload': True,
                        'reticle': not entry.get('optic_id'),
                        'skipped_v290': True, 'signature': signature,
                        'reason': reason}
    except Exception:
        pass
    try:
        native_fn = getattr(case, 'ChangeWeaponPartGuise', None)
        params = inspect.signature(native_fn).parameters if callable(native_fn) else {}
    except Exception:
        params = {}
    if 'change_part' not in params or 'part_guise_info' not in params:
        return {'ok': False, 'error': 'unverified ChangeWeaponPartGuise contract',
                'signature': signature, 'visual_verified': False}
    # Preflight the mesh reload before changing any cosmetic state.  v10.1
    # verified only the guise mapping, which could remain default visually.
    try:
        reload_fn = getattr(case, 'AddWeaponPart', None)
        reload_params = (inspect.signature(reload_fn).parameters
                         if callable(reload_fn) else {})
        reload_values = _v218scope_values(case, part_type, entry, ads=ads)
        reload_supported = bool(
            all(name in reload_params for name in
                ('part_id', 'part_type', 'refresh_model', 'part_loaded_callback'))
            and _v218so_bind(reload_fn, reload_values) is not None)
    except Exception:
        reload_supported = False
    if not reload_supported:
        return {'ok': False, 'error': 'unverified same-part AddWeaponPart contract',
                'signature': signature, 'visual_verified': False}
    guise_info = _v218scope_guise_info(case, part_type, item_id)
    if guise_info is None:
        return {'ok': False, 'error': 'unsupported part_guise_info shape',
                'signature': signature, 'visual_verified': False}
    try:
        try_dlc_download(item_id, [])
    except Exception:
        pass
    values = _v218scope_values(case, part_type, entry, guise_info, ads)
    native_ok, _native_result, native_error = named_call(
        case, 'ChangeWeaponPartGuise', values)
    # Reload before reticle/shader work: AddWeaponPart can create a new mesh,
    # and its loaded callback reapplies the exact reticle to that new mesh.
    reload_ok, _reload_result, reload_error = (False, None, 'not applied')
    if native_ok:
        if _same_part_299:
            # v2.99: the case already carries this exact part - the mesh
            # exists.  AddWeaponPart's synchronous re-load froze the game
            # thread 24-45s on a same-part cosmetic change (the debug-21
            # 45.62s block right after 'Modify/loadout InitWeapon').  The
            # ChangeWeaponPartGuise call above is all a same-part change
            # needs; a real part/model change still reloads below.
            reload_ok, reload_error = True, None
        else:
            reload_ok, _reload_result, reload_error = _v218scope_reload(
                case, part_type, entry, ads)
    part_after, part_readable = equipped_part(case, part_type)
    part_preserved = (part_after == part_id) if part_readable else None
    guise_match = _v218so_guise_match(case, part_type, entry)
    reticle_ok = not entry.get('optic_id')
    reticle_error = None
    if native_ok and reload_ok and entry.get('optic_id'):
        reticle_ok, _reticle_result, reticle_error = named_call(
            case, 'ChangeWeaponOpticReticle', values)
    refreshed, refresh_errors = ([], {'native': 'not applied'})
    if native_ok and reload_ok:
        refreshed, refresh_errors = _v218scope_refresh(case, part_type, entry, ads)
    ok = bool(native_ok and reload_ok and reticle_ok
              and part_preserved is not False and guise_match is not False)
    state_verified = bool(ok and part_preserved is True and guise_match is True
                          and (not entry.get('optic_id') or reticle_ok))
    result = {
        'ok': ok, 'state_verified': state_verified,
        'visual_verified': False, 'native': native_ok,
        'native_error': native_error, 'reload': reload_ok,
        'reload_error': reload_error, 'reticle': reticle_ok,
        'reticle_error': reticle_error, 'part_preserved': part_preserved,
        'guise_match': guise_match, 'ads': ads, 'refresh': refreshed,
        'refresh_errors': refresh_errors, 'signature': signature,
        'reason': reason,
    }
    if not ok:
        result['error'] = ('real optic part changed' if part_preserved is False else
                           'optic guise not retained' if guise_match is False else
                           'same-part mesh reload failed' if native_ok and not reload_ok else
                           'reticle native call failed' if native_ok and not reticle_ok else
                           'optic guise native call failed')
    return result


def after_skin(case, equip_id, forced_skin, reason='skin-apply'):
    """Cheap signature gate around resolution/apply; safe after every body apply."""
    if case is None or not sync_attrs.get('bSkinHack', False):
        return False
    equip_id = _safe_int(equip_id, 0)
    skin_id = _safe_int(forced_skin, 0)
    item_id = selected_item(skin_id)
    # v2.106: request the skin's resources before any model build.
    try:
        if item_id:
            _dl2106b = globals().get('try_dlc_download')
            if callable(_dl2106b):
                _dl2106b(item_id, [])
    except Exception:
        pass
    part_type = optic_type()
    part_id, readable = equipped_part(case, part_type)
    # v2.113: also prefetch the optic PART item - the last 35s
    # first-hit stall was the part bundle (debug-13).
    try:
        _dl2113 = globals().get('try_dlc_download')
        if callable(_dl2113) and part_id:
            _dl2113(part_id, [])
    except Exception:
        pass
    if not equip_id or not skin_id or not item_id or not part_type:
        return False
    key = (id(case), equip_id, skin_id, item_id, part_id)
    now = time.time()
    state = case_state.get(id(case)) or {}
    ads = ads_state(case)
    if not readable or not part_id:
        _th24 = globals().setdefault('scope_log_seen', {})
        _tk24 = ('no-part', equip_id, skin_id, item_id, part_id)
        _fresh24 = (not _th24.get(_tk24)) or (now - _th24[_tk24] >= 60.0)
        if _fresh24 and (state.get('key') != key
                         or now - state.get('at', 0.0) > 15.0):
            _th24[_tk24] = now
            _v218scope_log(('no-part', key),
                           'no readable equipped optic equip=%d skin=%d item=%d; optic unchanged'
                           % (equip_id, skin_id, item_id), 1)
        case_state[id(case)] = {
            'key': key, 'at': now, 'applied': False, 'entry': None,
            'status': 'no-readable-equipped-optic', 'ads': ads,
        }
        return False
    force_reload = (reason == 'Modify/loadout InitWeapon')
    if (not force_reload and state.get('key') == key and state.get('applied')
            and state.get('entry')):
        # No catalog work on this path.  ADS transitions reuse the exact entry.
        if _v218so_guise_match(case, part_type, state['entry']) is not False:
            if state.get('ads') != ads or state.get('pending_refresh'):
                called, errors = _v218scope_refresh(
                    case, part_type, state['entry'], ads)
                state['ads'] = ads
                state['pending_refresh'] = bool(errors)
                state['at'] = now
                _v218scope_log(('ads-refresh', key, ads),
                               'ADS refresh equip=%d part=%d ads=%r called=%r errors=%r'
                               % (equip_id, part_id, ads, called, errors), 1)
            return True
        if now - state.get('at', 0.0) < 2.0:
            return False
    if (not force_reload and state.get('key') == key
            and not state.get('applied')
            and now - state.get('at', 0.0) < 2.0):
        return False
    _bad25 = globals().setdefault('bad_cache', {})
    _bkey25 = (equip_id, skin_id, part_id)
    _bent25 = _bad25.get(_bkey25)
    if _bent25 is not None and now - _bent25 < 60.0:
        entry = None
    else:
        entry = _v218scope_resolve(equip_id, skin_id, part_id)
        if not entry:
            _bad25[_bkey25] = now
    if not entry:
        case_state[id(case)] = {
            'key': key, 'at': now, 'applied': False, 'entry': None,
            'status': 'no-exact-authentic-variant', 'ads': ads,
        }
        _th24b = globals().setdefault('scope_log_seen', {})
        _tk24b = ('unsupported', equip_id, skin_id, item_id, part_id)
        if (not _th24b.get(_tk24b)) or (now - _th24b[_tk24b] >= 60.0):
            _th24b[_tk24b] = now
            _v218scope_log(('unsupported', key),
                           'unsupported equip=%d skin=%d item=%d real_part=%d: '
                           'no exact authentic variant; real optic/magnification unchanged'
                           % (equip_id, skin_id, item_id, part_id), 1)
        return False
    result = apply_case(
        case, equip_id, skin_id, part_type, part_id, entry, ads, reason)
    new_state = {
        'key': key, 'at': now, 'applied': bool(result.get('ok')),
        'entry': entry if result.get('ok') else None,
        'status': 'native-applied' if result.get('ok') else result.get('error'),
        'ads': ads, 'pending_refresh': bool(result.get('refresh_errors')),
        'result': result,
    }
    if len(case_state) >= 48 and id(case) not in case_state:
        case_state.clear()
    case_state[id(case)] = new_state
    _v218scope_log(('apply', key, result.get('ok'), result.get('error')),
                   'apply reason=%s case=%s equip=%d skin=%d item=%d real_part=%d '
                   'model=%d reticle=%d native=%r reload=%r reticle_ok=%r '
                   'part_preserved=%r guise_match=%r state_verified=%r ads=%r '
                   'refresh=%r errors=%r reload_error=%r; '
                   'device visual verification pending'
                   % (reason, type(case).__name__, equip_id, skin_id, item_id,
                      part_id, entry['model_id'], entry.get('optic_id', 0),
                      result.get('native'), result.get('reload'),
                      result.get('reticle'), result.get('part_preserved'),
                      result.get('guise_match'), result.get('state_verified'),
                      ads, result.get('refresh'), result.get('refresh_errors'),
                      result.get('reload_error')), 1)
    return bool(result.get('ok'))


def _v218scope_tick(reason='pump'):
    """4 Hz cheap live-case check; catalog resolution occurs only on key changes."""
    if not sync_attrs.get('bSkinHack', False):
        return False
    now = time.time()
    if now - tick_at[0] < 0.25:
        return False
    tick_at[0] = now
    if not _v218scope_hooked[0] and now - hook_at[0] > 15.0:
        hook_at[0] = now
        install_case_hooks()
    try:
        local = _local_combat_avatar()
    except Exception:
        local = None
    if local is None:
        return False
    for name in ('is_reloading', 'is_reload', 'reloading', 'IsReloading'):
        try:
            if getattr(local, name, False):
                return False
        except Exception:
            pass
    try:
        weapon = local.GetCurWeapon()
        equip_id = _safe_int(getattr(weapon, 'equip_id', 0)
                             or getattr(weapon, 'weapon_id', 0), 0)
        forced = _get_forced_weapon_skin(equip_id)
        if not equip_id or not forced:
            return False
        applied = False
        for case in _current_weapon_cases(local):
            applied = after_skin(case, equip_id, forced, reason) or applied
        return applied
    except Exception as exc:
        _v218scope_log(('tick-error', repr(exc)), 'tick guarded error=%r' % (exc,), 1)
        return False


def install_case_hooks():
    """Observe the real native rebuild used by Modify/loadout; never replace parts."""
    found = []
    try:
        module = sys.modules.get('gclient.gameplay.logic_base.equips.weapon_case')
        if module is None:
            return found
        for cls_name in ('WeaponCase', 'WeaponCaseBase'):
            cls = getattr(module, cls_name, None)
            if not isinstance(cls, type):
                continue
            previous = cls.__dict__.get('InitWeapon')
            if not callable(previous):
                continue
            if getattr(previous, '_treacky_scopesync', False):
                found.append('%s.%s' % (cls_name, 'InitWeapon'))
                continue

            def _make(prev, label):
                def wrapper(self, *args, **kwargs):
                    result = prev(self, *args, **kwargs)
                    try:
                        if sync_attrs.get('bSkinHack', False):
                            equip_id = _weapon_case_wid(self)
                            forced = _get_forced_weapon_skin(equip_id)
                            if equip_id and forced:
                                _game_post('weapon-scopesync', after_skin,
                                           self, equip_id, forced, 'Modify/loadout InitWeapon')
                    except Exception as exc:
                        _v218scope_log(('native-hook', label, repr(exc)),
                                       'native rebuild observer error=%r' % (exc,), 1)
                    return result
                wrapper._treacky_scopesync = True
                return wrapper

            try:
                setattr(cls, 'InitWeapon', _make(previous, '%s.InitWeapon' % cls_name))
                found.append('%s.InitWeapon' % cls_name)
            except Exception:
                pass
    except Exception as exc:
        _v218scope_log(('hook-install', repr(exc)), 'hook install error=%r' % (exc,), 1)
    if found:
        _v218scope_hooked[0] = True
        _v218scope_log(('hooked', tuple(found)), 'Modify/loadout observers=%r' % (found,), 1)
    return found


# Keep the protected ordinary body/FX functions unchanged.  These late wrappers
# add optic work only after the established pipeline has completed.
_v218scope_previous_apply = _apply_weapon_case_skin


def _v218scope_apply_weapon_case_skin(case, equip_id, forced_skin,
                                      reason='apply', force=False):
    result = _v218scope_previous_apply(case, equip_id, forced_skin, reason, force)
    try:
        if result and sync_attrs.get('bSkinHack', False):
            after_skin(case, equip_id, forced_skin, reason)
    except Exception as exc:
        _v218scope_log(('post-apply', forced_skin, repr(exc)),
                       'post-skin optic stage error=%r' % (exc,), 1)
    return result


_apply_weapon_case_skin = _v218scope_apply_weapon_case_skin
previous_pump = _v31_weapon_fx_pump


def weapon_fx_pump():
    try:
        return previous_pump()
    finally:
        try:
            _v218scope_tick('game-pump')
        except Exception as exc:
            _v218scope_log(('pump', repr(exc)), 'pump guarded error=%r' % (exc,), 1)


_v31_weapon_fx_pump = weapon_fx_pump

try:
    install_case_hooks()
except Exception as _v218scope_boot_error:
    _v218scope_log(('boot', repr(_v218scope_boot_error)),
                   'boot observer error=%r' % (_v218scope_boot_error,), 1)
_plog('[SCOPESYNC] automatic equipped-part optic layer ready (%s)' % _SCOPE_SYNC_BUILD)

# ============================================================================
# v10.9: NATIVE COSMETIC VAULT UNLOCK
# ----------------------------------------------------------------------------
# Real lobby rows -> gshare.ihall_item.CreateHallItems -> local IHallItems.
# No always-true predicates, duck-typed items, RPC calls, or catalog scans on
# the game thread.  Native ownership/list/GUID/equip methods keep their exact
# arguments and return contracts; genuine native IHallItem objects are inserted
# into the local warehouse.  Queued rows keep the game's original answer until
# the native object exists, so HasItem/GetItem can never disagree.  Large lists
# are batched through the game's own Timer to avoid a long single-frame pass.
# ============================================================================
_COSMETIC_UNLOCK_BUILD = 'NEXORA-UNLOCK-ALL-NATIVE-12'
# Verbose bytecode tracing answered the v10.9.4 early-return question and is
# disabled for this repair candidate; bounded equip/result diagnostics remain.
EMOTE_VERBOSE_TRACE = False
# Keep the legacy isolation flag TRUE: it permanently suppresses the retired
# broad bUnlockAll/HasItem predicates below.  The controlled Unlock.cpp port
# instead exposes every native cosmetic category through real IHallItem rows.
EMOTE_ONLY = True
# #======================================================================
# //  COSMETICS.PY
# //
# //  This file is for: COSMETIC CATEGORIES + PERSISTENCE: the category resolution (_v109_category), the local-equip slot map, the pick persistence (config json), the saver + restore (restore_striker_picks), the melee equip pick.
# //
# //  Part of the split TREACKY BS payload (v2.112).  The runtime
# //  file payload/skins_payload.py is GENERATED: run
# //  tools/build_payload.py after editing these modules.
# #======================================================================
