# ============================================================
# CATALOG.PY
# PROVIDES: WEP, WEP_NAMES, WEP_SKIN_INFO, WEP_MERGED_DISPLAY,
#           WEP_GUN_IDS, WEP_MELEE_IDS, SKIN_TO_EQUIP, SKIN_TO_ITEM,
#           ITEM_TO_SKIN, SKIN_LOBBY_PROTO, OPTIC_LIST, _harvest_optics,
#           _optic_id_by_index, _resolve_effect, _skin_effect_id,
#           WEAPON_CATS, weapon_cat, build_auto_wep_dictionary
#           (+ name-localization passes, catalog sender loop)
# REQUIRES: names.py, main._plog, game_api.*, config.sync_attrs
# ============================================================
"""Weapon/skin catalog build and publication.

Harvests the game's own weapon/skin tables (equip_id rows from
GetEquipTemplateIdForSkin/GetAllGunIds family + lobby_item_data rows),
applies admission rules (entity_type==1, english_des==1, legal==1, model),
folds melee display rows (33/97/141 merged slots, WEP_MERGED_DISPLAY) and
publishes the catalog over UDP 50002/50003 for the menu UI.
"""

# kill-record helpers (module scope: called cross-module by
# kills.py / scopesync.py; were buried in the hud try and
# vanished whenever the hud import failed)
def _weapon_name_and_wids(weapon_id):
    try:
        weapon_id = int(weapon_id or 0)
        entry = WEP.get(weapon_id)
        if not entry:
            return None, []
        return entry[0], entry[1:]
    except Exception:
        return None, []

def _get_selected_skin_for_weapon(weapon_id):
    try:
        return _get_forced_weapon_skin(weapon_id) or 0
    except Exception:
        return 0

def _get_case_skin(wc):
    if not wc:
        return 0
    try:
        wid = getattr(wc, 'weapon_id', 0) or getattr(wc, 'equip_id', 0)
        if wid:
            sid = _get_selected_skin_for_weapon(wid)
            if sid:
                return sid
    except Exception:
        pass
    try:
        sid = getattr(wc, '_selected_skin_id', 0)
        if sid:
            return sid
    except Exception:
        pass
    try:
        sid = getattr(wc, '_treacky_skin_template_id', 0) or getattr(wc, 'guise_template_id', 0) or getattr(wc, 'guise_id', 0)
        if sid:
            return ITEM_TO_SKIN.get(sid, sid)
        item_sid = getattr(wc, 'guise_item_id', 0) or getattr(wc, 'skin_item_id', 0)
        if item_sid:
            return ITEM_TO_SKIN.get(item_sid, item_sid)
    except Exception:
        pass
    try:
        d = getattr(wc, '__dict__', {})
        sid = d.get('_selected_skin_id', 0) or d.get('guise_id', 0) or d.get('guise_item_id', 0) or d.get('guise_template_id', 0)
        if sid:
            return sid
    except Exception:
        pass
    return 0

def _get_kill_skin(info=None):
    try:
        ca = None
        _get_local = globals().get('_local_combat_avatar')
        if callable(_get_local):
            ca = _get_local()
        if ca is None:
            sp = getattr(Space, '_instance', None)
            owner = getattr(sp, 'owner', None) if sp else None
            ca = getattr(owner, 'combat_avatar', None) if owner else None
        if not ca:
            return 0, None
        wc = _get_weapon_case_from_info(ca, info)
        if wc:
            sid = _get_case_skin(wc)
            if sid:
                return sid, wc
        try:
            weapon = ca.GetCurWeapon()
            if weapon and hasattr(ca, 'GetWeaponCase'):
                guid = getattr(weapon, 'guid', None)
                if guid:
                    wc = ca.GetWeaponCase(guid)
                    if wc:
                        sid = _get_case_skin(wc)
                        if sid:
                            return sid, wc
        except Exception:
            pass
        try:
            weapon = ca.GetCurWeapon()
            if weapon:
                wid = getattr(weapon, 'weapon_id', 0) or getattr(weapon, 'equip_id', 0)
                sid = _get_selected_skin_for_weapon(wid)
                if sid:
                    return sid, None
        except Exception:
            pass
    except Exception:
        pass
    return 0, None


# catalog-ready flag box (module scope: read by unlocks/rpcs/equip
# watchdog; set by _try_build_weapon_catalog)
_weapon_catalog_ready = [False]
_weapon_catalog_attempts = [0]

# ============================================================
# Game class imports (skin targets only). Missing classes
# become dummies so HOOK v2 logs them instead of dying.
# ============================================================
WEP = {}
WEP_NAMES = {}
WEP_SKIN_INFO = {}
# v8.20: display-only rows for the merged melee slots (97/107/141).
# Skins apply through Dagger (33); the menu lists them under their
# own gun ids so every real gun is visible.
WEP_MERGED_DISPLAY = {}
# v7.21: weapon scopes. Harvested once from the game's own optic tables,
# fed to the Skins tab as "O|" catalog lines, applied via the same
# ChangeWeaponOpticReticle call the skin FX pass already uses.
OPTIC_LIST = []            # sorted [(optic_id, name)]
_optic_catalog_done = [False]
_optic_catalog_dirty = [False]  # v7.22: tells the weapon sender to resend
_fx_row_keys_done = set()  # v7.21: one-shot key dump per skin (tier fields)


def _harvest_optics():
    """v7.22: the REAL scope catalog.

    v7.21 scanned every module with 'optic' in its name and harvested 675
    entries - but those tables are keyed by SKIN id, so the menu was fed
    skin names as scopes. The only ids ChangeWeaponOpticReticle actually
    accepts are the optic PART ids the skin rows reference
    (skin_optic_id / skin_lobby_default_optic - e.g. 21402200, 2330202
    straight from the [SHOTS] dumps). Harvest exactly those, named after
    the skin that carries them.
    """
    found = {}
    try:
        for _sid, _info in (WEP_SKIN_INFO or {}).items():
            _nm = _display_text(_info.get('name') or str(_sid), '')
            for _k in ('skin_optic_id', 'optic_id'):
                _oid = _safe_int(_info.get(_k), 0)
                if _oid and _oid not in found:
                    found[_oid] = ('%s scope' % _nm) if _nm else ''
            try:
                _proto = SKIN_LOBBY_PROTO.get(_sid)
                _oid = _safe_int(_proto_get(_proto, 'skin_optic_id', None), 0)
                if _oid and _oid not in found:
                    found[_oid] = ('%s scope' % _nm) if _nm else ''
            except Exception:
                pass
    except Exception:
        pass
    out = []
    for _oid in sorted(found):
        _nm = found[_oid] or ('Optic %d' % _oid)
        if _contains_cjk(_nm):
            _tr = _lang_translate(_nm)
            if _tr and not _contains_cjk(_tr):
                _nm = _tr
        out.append((_oid, _nm))
    OPTIC_LIST[:] = out
    _optic_catalog_dirty[0] = len(out) > 0
    _plog('[OPTIC] catalog harvested=%d sample=%r'
          % (len(out), out[:8]))
    return len(out)


def _optic_id_by_index(idx):
    """1-based menu index -> optic id (0 / out of range -> None)."""
    idx = _safe_int(idx, 0)
    if 0 < idx <= len(OPTIC_LIST):
        return OPTIC_LIST[idx - 1][0]
    return None
SKIN_TO_EQUIP = {}
SKIN_TO_ITEM = {}
ITEM_TO_SKIN = {}
SKIN_LOBBY_PROTO = {}
WEP_GUN_IDS = {}
WEP_MELEE_IDS = {}
_late_lobby_name_scan = [None]

try:
    import gclient.data.effect_data as efd
except:
    efd = None

def _resolve_effect(effect_id):
    if not efd or not effect_id:
        return None
    try:
        info = _data_get(getattr(efd, 'data', None), effect_id)
        if not info:
            return None
        return _proto_get(info, 'path') or _proto_get(info, 'effect_string')
    except:
        return None

def _skin_effect_id(skin_info):
    fx = _proto_get(skin_info, 'optic_b_fx')
    if fx:
        return fx
    return None


# v8.17: the menu's STATIC weapon table is the source of truth
# again - the v8.16 map re-guessed 40 categories and got Spear
# (131) dumped into AR. Now the payload sends a category ONLY
# for weapons the static table does not have: G36 (150) and
# Scorpion (148) - plus any genuinely new gun that appears
# later (logged as v816_new_guns, defaults to AR).
WEAPON_CATS = {
    148: 'SMG',
    150: 'AR',
}
cat_unknown = {}


def weapon_cat(equip_id):
    """v8.16: the menu's weapon tabs. The old C++ list was a
    hardcoded 47-entry table - G36 (150) and Scorpion (148) were
    simply not in it (their v8.15 skins were in the catalog but
    unreachable), SKS sat in the wrong tab, and every future gun
    would repeat that. The payload now sends a C|id|cat line per
    weapon; melees come from the equip-table discovery."""
    try:
        if equip_id in (globals().get('WEP_MELEE_IDS') or {}):
            return 'MEL'
        cat = WEAPON_CATS.get(equip_id)
        if cat:
            return cat
        cat_unknown.setdefault(equip_id, True)
        return 'AR'
    except Exception:
        return 'AR'


try:
    try:
        import re
    except Exception:
        re = None

    def _base_skin_name_and_level(name):
        text = _display_text(name, '')
        if not text:
            return text, 0
        if re is not None:
            m = re.search(r'\s*-?\s*LV(\d+)\s*$', text)
            if not m:
                return text, 0
            return text[:m.start()].strip(), int(m.group(1))
        upper = text.upper()
        idx = upper.rfind('LV')
        if idx > 0 and text[idx - 1] in (' ', '-'):
            suffix = text[idx + 2:].strip()
            if suffix.isdigit():
                return text[:idx].rstrip(' -'), int(suffix)
        return text, 0

    def _v841all_unique_ids(values):
        out = []
        seen = set()
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            out.append(value)
        return out


    def build_auto_wep_dictionary():
        global WEP, WEP_NAMES, WEP_SKIN_INFO, SKIN_TO_EQUIP
        global SKIN_TO_ITEM, ITEM_TO_SKIN, SKIN_LOBBY_PROTO
        global WEP_GUN_IDS, WEP_MELEE_IDS

        # Lazy + retryable imports. On vc163 the payload runs on the 2nd
        # PyRun call, before every split gclient.data module is registered.
        # v2.3 proved hero/lobby data can be present while the gun data
        # import path is not ready yet, so do not import these at top level.
        ed = _import_module('gclient.data.equip_data')
        ed_data = getattr(ed, 'data', None)
        equip_items = _data_items(ed_data)
        if not equip_items:
            raise RuntimeError(
                'equip_data imported but data is empty/not ready (data type=%s)'
                % (type(ed_data).__name__,))

        equip_names = {}
        equip_by_id = {}
        gun_to_equip_map = {}
        for equip_id, equip_info in equip_items:
            equip_by_id[equip_id] = equip_info
            equip_names[equip_id] = _proto_english_name(
                equip_info,
                ('en_name', 'english_name', 'name_en', 'name', 'equip_name', 'gun_name'),
                str(equip_id))
            gun_id = _proto_get(equip_info, 'gun_id')
            if gun_id:
                gun_to_equip_map[gun_id] = equip_id

        gst_sources = []
        gst_attempts = []
        for module_name in (
            'gclient.data.gun_skin_template_data',
            'gclient.data.gun_skin_template_base_data',
        ):
            try:
                candidate = _import_module(module_name)
                candidate_items = _data_items(getattr(candidate, 'data', None))
                gst_attempts.append('%s=%d items' % (module_name, len(candidate_items)))
                if candidate_items:
                    gst_sources.append((module_name, candidate_items))
            except Exception as _gst_err:
                gst_attempts.append('%s error=%r' % (module_name, _gst_err))
        if not gst_sources:
            raise RuntimeError('gun skin template data not ready: ' + '; '.join(gst_attempts))

        # Merge both sources by skin ID. Combined stays primary for the
        # force/effect fields, while names/effect fields can fall back to
        # base. v2.5 used combined only and device logs proved its
        # skin_name values are predominantly Chinese.
        gst_source = '+'.join(name for name, _items in gst_sources)
        gst_items_by_id = {}
        gst_infos_by_id = {}
        gst_name_candidates = {}
        for _source_name, _source_items in gst_sources:
            for _sid, _info in _source_items:
                gst_infos_by_id.setdefault(_sid, []).append(_info)
                if _sid not in gst_items_by_id:
                    gst_items_by_id[_sid] = _info
                _candidate_name = _proto_display_name(
                    _info,
                    ('en_name', 'english_name', 'name_en', 'skin_name', 'name'),
                    '')
                if _candidate_name:
                    _names = gst_name_candidates.setdefault(_sid, [])
                    if _candidate_name not in _names:
                        _names.append(_candidate_name)
        gst_items = list(gst_items_by_id.items())

        melee_case_map = {'Melee': 33, 'DualMelee': 97, 'Heirloom': 141}
        melee_id_map = {2: 84, 3: 86, 4: 89, 5: 107}
        # v8.13: the hardcoded maps only know the four launch melees -
        # every melee added since was silently DROPPED from the catalog
        # ("new melees are missing"). Discover melee slots straight
        # from the game's own equip table: any equip carrying a
        # melee_weapon_id is a melee slot. Launch slots stay mapped
        # exactly as before; new ones are appended.
        _known_melee_slots = set(melee_case_map.values()) \
            | set(melee_id_map.values())
        for _eq_id, _eq_info in equip_by_id.items():
            try:
                if _proto_get(_eq_info, 'gun_id'):
                    continue   # a gun is NEVER a melee (this is the
                                # exact hole that put the spear in the
                                # melee tab)
                _mid2 = _safe_int(
                    _proto_get(_eq_info, 'melee_weapon_id'), 0)
                if not _mid2 or _eq_id in _known_melee_slots:
                    continue
                if _mid2 == 1:
                    _case2 = _display_text(
                        _proto_get(_eq_info, 'equip_case'), '')
                    if _case2 and _case2 not in melee_case_map:
                        melee_case_map[_case2] = _eq_id
                        _known_melee_slots.add(_eq_id)
                elif _mid2 not in melee_id_map:
                    melee_id_map[_mid2] = _eq_id
                    _known_melee_slots.add(_eq_id)
            except Exception:
                pass
        temp_skins = {}
        built_skin_info = {}
        candidate_count = 0
        skin_type_counts = {}
        _v815_admitted = {}
        admit_names = []
        _v816_rejects = []
        camo_dropped = 0
        melee_merged = 0
        _v841g_recovered = 0
        new_type_admitted = 0
        _v841g_same_level_kept = 0
        append_ids = set()
        recovery_samples = []
        # v8.41-gunmax: broaden GUN rows only. Melee admission/filtering and
        # saved iSkin_* selections remain untouched. Stats are aggregate only;
        # the larger camo/variant catalog must not create per-row log spam.
        gun_rows = 0
        _v841all_broadened = 0
        _v841all_exact_duplicates = 0
        name_levels = {}
        # v8.20: skin_id -> original merged slot (97/107/141) so the
        # menu can list those guns' skins under their own rows while
        # the apply keeps routing through the Dagger equip (33).
        merge_src = {}
        # v8.18: the AR-picker junk purge counters - base-default
        # bodies (type -1, skin_id == gun id) and non-displayable
        # variant names (placeholder / low-spec / advanced-body).
        base_dropped = 0
        junk_dropped = 0
        try:
            _eq1 = next(iter(equip_by_id.values()), None)
            if _eq1 is not None:
                _plog('[CATALOG] v816 equip-row probe keys=%r'
                      % (sorted(str(k) for k, _v
                                in _data_items(_eq1))[:48],))
        except Exception:
            pass

        def row_has_skin_signal(row):
            # v8.15: a real skin row carries display/effect fields a
            # parts/junk row does not - this keeps the type-0/-1
            # admission honest.
            try:
                for _f in ('skin_name', 'skin_quality', 'kill_mat',
                           'fps_tracer_bullet_id',
                           'tps_tracer_bullet_id',
                           'skin_optic_id', 'kill_tip_icon_replace',
                           'SkinAdsEmptyReloadAnimName',
                           'gun_skin_part_model_list'):
                    if _proto_get(row, _f, None) is not None:
                        return True
            except Exception:
                return False
            return False

        # v8.41-guncatalog: link template rows to REAL lobby gun items
        # BEFORE admission. The old late pass could rename/map only rows that
        # had already survived, so an unresolved/new-type skin was unrecoverable.
        # This is a selective gun-skin/subtype-index scan, never a 65k vault scan.
        def collect_ids(value, out=None, seen=None, depth=0):
            if out is None:
                out = []
            if seen is None:
                seen = set()
            if depth > 4 or len(out) >= 16384:
                return out
            if isinstance(value, (list, tuple)):
                for _entry in value:
                    collect_ids(_entry, out, seen, depth + 1)
                return out
            _ivalue = _safe_int(value, 0)
            if _ivalue and _ivalue not in seen:
                seen.add(_ivalue)
                out.append(_ivalue)
            return out

        _v841g_lobby_links = {}
        lobby_gun_hints = {}
        _v841g_lobby_scanned = [0]

        def template_candidates(proto, item_id=0):
            out = []
            def _add(value, depth=0):
                if depth > 3:
                    return
                if isinstance(value, (list, tuple)):
                    for nested in value[:8]:
                        _add(nested, depth + 1)
                    return
                ivalue = _safe_int(value, 0)
                if ivalue in gst_items_by_id and ivalue not in out:
                    out.append(ivalue)
            _add(item_id)
            try:
                for _key, _value in _data_items(proto):
                    if str(_key).lower() in (
                            'skin', 'skin_id', 'gun_skin_id', 'guise_id',
                            'guise_template_id', 'skin_template_id',
                            'template_id', 'skin_template', 'guise'):
                        _add(_value)
            except Exception:
                pass
            return out

        def add_lobby_item(item_id, proto):
            try:
                _item_int = _safe_int(item_id, 0)
                if not _item_int or proto is None or not _data_items(proto):
                    return
                _candidates = template_candidates(proto, _item_int)
            except Exception:
                return
            _v841g_lobby_scanned[0] += 1
            for _sid in _candidates:
                _new = (_item_int, proto)
                _old = _v841g_lobby_links.get(_sid)
                if _old is None:
                    _v841g_lobby_links[_sid] = _new
                else:
                    # Prefer the link that can independently resolve a gun.
                    _old_gun = (_proto_get(_old[1], 'gun_id', None)
                                or _proto_get(_old[1], 'equip_id', None))
                    _new_gun = (_proto_get(proto, 'gun_id', None)
                                or _proto_get(proto, 'equip_id', None))
                    if not _old_gun and _new_gun:
                        _v841g_lobby_links[_sid] = _new

        _v841g_gunskin_mod = None
        _v841g_lid_mod = None
        try:
            _v841g_gunskin_mod = _import_module(
                'gclient.data.lobby_gun_skin_item_data')
        except Exception:
            pass
        try:
            _v841g_lid_mod = _import_module('gclient.data.lobby_item_data')
        except Exception:
            pass
        gunskin_data = getattr(_v841g_gunskin_mod, 'data', None)
        _v841g_lid_data = getattr(_v841g_lid_mod, 'data', None)

        def lookup_lobby_item(item_id):
            for _data in (gunskin_data, _v841g_lid_data):
                try:
                    _row = _data_get(_data, item_id, None)
                    if _row is not None and _data_items(_row):
                        return _row
                except Exception:
                    continue
            return None

        try:
            for _item_id, _proto in _data_items(gunskin_data):
                add_lobby_item(_item_id, _proto)
        except Exception:
            pass
        try:
            for _attr in ('GUN_ID_TO_SKIN_ITEM_IDS',
                          'GUN_ID_TO_GUISE_ITEM_IDS'):
                _mapping = getattr(_v841g_gunskin_mod, _attr, None)
                for _gun_id, _item_ids in _data_items(_mapping):
                    for _item_id in collect_ids(_item_ids):
                        _proto = lookup_lobby_item(_item_id)
                        add_lobby_item(_item_id, _proto)
                        _gun_hint = _safe_int(_gun_id, 0)
                        if _gun_hint in gun_to_equip_map:
                            for _sid in template_candidates(
                                    _proto, _item_id):
                                if _sid in _v841g_lobby_links:
                                    lobby_gun_hints.setdefault(
                                        _sid, _gun_hint)
        except Exception:
            pass
        try:
            _subtype_mod = _import_module(
                'gclient.data.sub_type_to_item_ids_data')
            # Android gun_skin_util evidence names the exported table
            # SUB_TYPE_TO_ITEM_IDS. Older fixtures/builds may expose .data;
            # support both and deduplicate shared IDs across aliases.
            seen_subtype_items = set()
            for _attr in ('data', 'SUB_TYPE_TO_ITEM_IDS'):
                _subtype_data = getattr(_subtype_mod, _attr, None)
                for _sub_type in (100, 550, 210):
                    _ids = _data_get(_subtype_data, _sub_type, None)
                    for _item_id in collect_ids(_ids):
                        if _item_id in seen_subtype_items:
                            continue
                        seen_subtype_items.add(_item_id)
                        add_lobby_item(
                            _item_id, lookup_lobby_item(_item_id))
        except Exception:
            pass

        for skin_id, skin_info in gst_items:
            skin_type = _proto_get(skin_info, 'gun_skin_type')
            type_key = repr(skin_type)
            skin_type_counts[type_key] = skin_type_counts.get(type_key, 0) + 1

            target_equip_id = None
            resolved_gun_id = None
            gun_family_id = None
            replace_id = _proto_get(skin_info, 'replace_equip_id')
            if replace_id:
                orig_equip = equip_by_id.get(replace_id)
                if orig_equip is None:
                    orig_equip = _data_get(ed_data, replace_id, {})
                if _proto_get(orig_equip, 'gun_id'):
                    # v8.13: a skin whose replacement target is a GUN
                    # is a gun skin. The spear (a gun) ended up in the
                    # melee tab through this exact hole.
                    target_equip_id = gun_to_equip_map.get(
                        _proto_get(orig_equip, 'gun_id'))
                    gun_family_id = _proto_get(orig_equip, 'gun_id')
                else:
                    m_id = _proto_get(orig_equip, 'melee_weapon_id')
                    e_case = _display_text(
                        _proto_get(orig_equip, 'equip_case'), '')
                    if m_id == 1:
                        target_equip_id = melee_case_map.get(e_case)
                    else:
                        target_equip_id = melee_id_map.get(m_id)
            else:
                gun_id = _proto_get(skin_info, 'gun_id')
                if gun_id:
                    target_equip_id = gun_to_equip_map.get(gun_id)
                    resolved_gun_id = gun_id
                    gun_family_id = gun_id

            _v841g_link = _v841g_lobby_links.get(skin_id)
            recovery_used = False
            _st_v = _safe_int(skin_type, 0)
            template_signal = row_has_skin_signal(skin_info)
            if not target_equip_id and _v841g_link:
                _lobby_proto = _v841g_link[1]
                _lobby_gun = (_safe_int(
                    _proto_get(_lobby_proto, 'gun_id', None), 0)
                    or _safe_int(lobby_gun_hints.get(skin_id), 0))
                if _lobby_gun in gun_to_equip_map:
                    resolved_gun_id = _lobby_gun
                    gun_family_id = _lobby_gun
                    target_equip_id = gun_to_equip_map.get(_lobby_gun)
                else:
                    _lobby_equip = _safe_int(
                        _proto_get(_lobby_proto, 'replace_equip_id',
                                   _proto_get(_lobby_proto, 'equip_id', None)), 0)
                    _lobby_equip_row = equip_by_id.get(_lobby_equip)
                    _lobby_gun = _safe_int(
                        _proto_get(_lobby_equip_row, 'gun_id', None), 0)
                    if _lobby_gun in gun_to_equip_map:
                        resolved_gun_id = _lobby_gun
                        gun_family_id = _lobby_gun
                        target_equip_id = gun_to_equip_map.get(_lobby_gun)
                recovery_used = bool(target_equip_id)
            skin_signal = template_signal
            if (_v841g_link and gun_family_id
                    and not skin_signal
                    and (_st_v == -1 or _st_v > 9)):
                skin_signal = row_has_skin_signal(
                    _v841g_link[1])
                if skin_signal:
                    recovery_used = True
            if _v841g_link and (recovery_used or _st_v > 9):
                # Only recovered rows get lobby names before the stable sort;
                # existing rows keep their established naming/index path.
                _lobby_name = _proto_english_name(
                    _v841g_link[1],
                    ('en_name', 'english_name', 'name_en', 'name', 'skin_name'),
                    '')
                if _lobby_name:
                    _names = gst_name_candidates.setdefault(skin_id, [])
                    if _lobby_name not in _names:
                        _names.append(_lobby_name)

            # v8.17: the discovered slots 97 (Dual Blades), 107
            # (Scythe) and 141 (Artifact) are NOT separate
            # weapons - their skins are dagger-family model
            # swaps ("the chainblade ... belong to dagger").
            # Listing them under their own equip also BROKE the
            # apply: the loadout melee is 33, so forcing a case
            # for 97/107/141 never reached the game. Fold them
            # into the classic Dagger equip so they both list
            # and apply where the player's melee actually is.
            # v8.20: the apply still folds into 33, but the menu
            # now gives each of the three its own ROW again (the
            # v8.20 report: every real gun must be visible) -
            # remember the original slot so the display lines
            # can list the skins under their own gun too.
            if target_equip_id in (97, 107, 141):
                merge_src[skin_id] = target_equip_id
                target_equip_id = 33
                melee_merged += 1

            if not target_equip_id:
                # v2.124: operator "some weapons are missing" - fall back
                # before a row dies: (a0) the GAME'S OWN id resolvers
                # (authoritative, checked first), (a) the template row's own
                # gun_id through the equip map, (b) the documented id-prefix
                # family rule (skin_id startswith gun id + >=7 suffix,
                # longest match wins), (c) a t=-1 row whose id is itself
                # a gun id becomes a brand-new gun row so the weapon
                # still lists in the picker.
                if not target_equip_id:
                    # (a0) gclient.util.gun_skin_util.GetEquipIdBySkinOrGuiseItemId
                    # resolves item_id/skin rows through the game's own
                    # WarehouseItemType sub_type (100/550/210) + template
                    # tables - exactly the rows the heuristics below can
                    # miss (the 621000002x/41300001xx unresolved families).
                    try:
                        _gsu24 = _import_module('gclient.util.gun_skin_util')
                        _resolver24 = getattr(_gsu24,
                                              'GetEquipIdBySkinOrGuiseItemId',
                                              None)
                        if callable(_resolver24):
                            _rez24 = _safe_int(_resolver24(skin_id), 0)
                            if not _rez24 and _v841g_link:
                                _rez24 = _safe_int(
                                    _resolver24(_v841g_link[0]), 0)
                            if _rez24 and _rez24 in equip_by_id:
                                target_equip_id = _rez24
                                _orig24 = equip_by_id.get(_rez24)
                                _gun24 = _safe_int(
                                    _proto_get(_orig24, 'gun_id', 0), 0)
                                resolved_gun_id = _gun24 or resolved_gun_id
                                gun_family_id = _gun24 or gun_family_id
                                recovery_used = True
                    except Exception:
                        pass
                if not target_equip_id:
                    # (a0b) hall_ui_util.GetEquipTypeAndGunIdByItemId -
                    # the lobby's own item->(type, gun) resolver.
                    try:
                        _hui24 = _import_module('gclient.util.hall_ui_util')
                        _resolver24b = getattr(
                            _hui24, 'GetEquipTypeAndGunIdByItemId', None)
                        if callable(_resolver24b):
                            _tid24b = _safe_int(skin_id, 0)
                            if _v841g_link:
                                _tid24b = _safe_int(_v841g_link[0], 0) or _tid24b
                            _res24b = _resolver24b(_tid24b)
                            _gun24b = 0
                            if isinstance(_res24b, (tuple, list)) and _res24b:
                                for _part24b in _res24b:
                                    _gun24b = _safe_int(_part24b, 0) or _gun24b
                            else:
                                _gun24b = _safe_int(_res24b, 0)
                            if _gun24b and _gun24b in gun_to_equip_map:
                                resolved_gun_id = _gun24b
                                gun_family_id = _gun24b
                                target_equip_id = gun_to_equip_map.get(_gun24b)
                                recovery_used = True
                    except Exception:
                        pass
                if not resolved_gun_id:
                    _tid25 = _safe_int(
                        _proto_get(skin_info, 'gun_id', None), 0)
                    if not _tid25:
                        try:
                            _m25 = sys.modules.get(
                                'gclient.data.gun_skin_template_data')
                            _row25 = (_data_get(
                                getattr(_m25, 'data', None), skin_id, None)
                                if _m25 is not None else None)
                            if _row25 is not None:
                                _tid25 = _safe_int(_proto_get(
                                    _row25, 'gun_id', None), 0)
                        except Exception:
                            _tid25 = 0
                    if _tid25 and _tid25 in gun_to_equip_map:
                        resolved_gun_id = _tid25
                        gun_family_id = _tid25
                        target_equip_id = gun_to_equip_map.get(_tid25)
                if not target_equip_id:
                    _sid25 = str(skin_id)
                    _best25 = -1
                    for _g25 in list(gun_to_equip_map.keys()):
                        _gs25 = str(_g25)
                        if (_g25 and _sid25.startswith(_gs25)
                                and len(_sid25) >= len(_gs25) + 7
                                and len(_gs25) > _best25):
                            _best25 = len(_gs25)
                            resolved_gun_id = _g25
                            gun_family_id = _g25
                            target_equip_id = gun_to_equip_map.get(_g25)
                if (not target_equip_id and _safe_int(skin_type, 0) == -1
                        and _safe_int(skin_id, 0) > 0 and skin_signal):
                    _gid25 = _safe_int(skin_id, 0)
                    _nm25 = ''
                    for _c25 in (gst_name_candidates.get(skin_id) or []):
                        if _c25:
                            _nm25 = str(_c25)
                            break
                    if not _nm25:
                        _nm25 = str(_proto_get(
                            skin_info, 'skin_name',
                            _proto_get(skin_info, 'name', '')) or '')
                    if _nm25:
                        gun_to_equip_map[_gid25] = _gid25
                        equip_names.setdefault(
                            _gid25, _nm25.split(' - ')[0].strip() or _nm25)
                        resolved_gun_id = _gid25
                        gun_family_id = _gid25
                        target_equip_id = _gid25
                # v8.16: the new melees the user reports missing
                # die HERE if their rows do not resolve - log a
                # bounded sample of the -1/0 rejects so the next
                # device log pins exactly which rows and why.
                _st_probe = _safe_int(skin_type, 0)
                if _st_probe in (0, -1) and len(_v816_rejects) < 24:
                    _v816_rejects.append(
                        '%s/t=%s/gun=%r/rep=%r/sig=%s/unresolved'
                        % (skin_id, skin_type,
                           _proto_get(skin_info, 'gun_id', None),
                           replace_id,
                           row_has_skin_signal(skin_info)))
                continue
            # v8.13: the old `!= 1` filter dropped every skin whose
            # gun_skin_type was not exactly 1 - new guns ship with new
            # type values and vanished from the catalog. Accept the
            # full 1-9 range; 0/None (non-skin rows) stay excluded.
            # v8.15: the v8.14 device types histogram
            # [(0, 28220), (1, 1475), (-1, 23), (None, 3)] says the
            # NEW guns (G3 + the new SMG) and the new melees ship
            # with type -1 (exactly 23 rows - too few for junk, too
            # many for one item) and 0. A -1 row resolves to an equip
            # like any skin and is admitted when it carries skin
            # fields; a 0 row needs the full strict chain (own gun_id
            # that maps to an equip + id prefix == gun_id + skin
            # fields) so the 28k type-0 junk rows stay out. Real skin
            # ids use 7- AND 8-digit suffixes (a fixed-length rule
            # would drop half the catalog), so prefix + fields is the
            # discriminator.
            _st_v = _safe_int(skin_type, 0)
            is_camo = False
            new_type_row = False
            gun_row = bool(gun_family_id)
            broadened_row = False
            if gun_row and (_st_v < 1 or _st_v > 9):
                # Owner directive: every genuine resolved gun-skin row returns,
                # including camos/default bodies/new families. Signal-less and
                # unresolved rows remain out, so this is not a 28k-junk unlock.
                _admit15 = bool(skin_signal)
                if not _admit15:
                    if len(_v816_rejects) < 24:
                        _v816_rejects.append(
                            '%s/t=%s/gun=%r/rep=%r/sig=%s/no-real-skin-signal'
                            % (skin_id, skin_type, resolved_gun_id,
                               replace_id, skin_signal))
                    continue
                broadened_row = True
                new_type_row = (_st_v > 9)
                append_ids.add(skin_id)
                _v815_admitted[_st_v] = _v815_admitted.get(_st_v, 0) + 1
                if len(admit_names) < 24:
                    admit_names.append(
                        '%s/%s' % (skin_id,
                                   _proto_get(skin_info, 'skin_name', None)))
            else:
                _st_v = _safe_int(skin_type, 0)
                is_camo = False
                new_type_row = False
                if _st_v < 1 or _st_v > 9:
                    _admit15 = False
                    if _st_v > 9:
                        # New SDK skin families can use types above the old 1-9
                        # range. Admit only a resolved GUN with real skin fields.
                        _admit15 = bool(gun_family_id and skin_signal)
                        new_type_row = _admit15
                    elif _st_v == -1:
                        _admit15 = skin_signal
                        # v8.18: the 15 admitted -1 rows whose skin_id IS
                        # the gun id (1/M4A1, 4/Glock, 6/Origin-12, 8/
                        # Vector, 10/AK47, ...) are the gun's own DEFAULT
                        # body, not a skin - they listed in the picker
                        # named after the gun ("unnecessary things on
                        # AR"). A real -1 skin is a long id that differs
                        # from its gun (6011990015 vs 60).
                        if _admit15:
                            _gid18 = _safe_int(
                                _proto_get(skin_info, 'gun_id', None), 0)
                            if (skin_id == _gid18
                                    or (resolved_gun_id
                                        and skin_id == resolved_gun_id)):
                                _admit15 = False
                                base_dropped += 1
                    elif _st_v == 0 and resolved_gun_id:
                        _sid15 = str(skin_id)
                        _gid15 = str(resolved_gun_id)
                        if (_sid15.startswith(_gid15)
                                and len(_sid15) >= len(_gid15) + 7
                                and row_has_skin_signal(skin_info)):
                            # v8.17: the type-0 family IS the camo
                            # set - 28,137 rows, ~640 per weapon
                            # ('X - Abyss', 'X - Crimson', ...).
                            # The user wants every camo out of the
                            # picker; the ONE exception is the Pure
                            # Gold camo (CJK '纯金'). Real skins are
                            # type 1-9 and the new guns' skins are
                            # -1 - both untouched.
                            _nm17 = ''
                            _cands17 = gst_name_candidates.get(
                                skin_id, [])
                            if _cands17:
                                _nm17 = str(_cands17[0] or '')
                            if not _nm17:
                                _nm17 = str(_proto_get(
                                    skin_info, 'skin_name', '') or '')
                            _sfx17 = _nm17.split(' - ', 1)[1].strip() \
                                if ' - ' in _nm17 else _nm17.strip()
                            if (_sfx17 == '纯金'
                                    or _sfx17 == 'Pure Gold'):
                                _admit15 = True   # the gold camo stays
                            else:
                                camo_dropped += 1
                                is_camo = True
                    if not _admit15:
                        # v8.17: camos are an intentional drop, not a
                        # reject - the reject sample stays for real
                        # failures (unresolved rows, junk rows).
                        if (not is_camo
                                and len(_v816_rejects) < 24):
                            _v816_rejects.append(
                                '%s/t=%s/gun=%r/rep=%r/sig=%s/filtered'
                                % (skin_id, skin_type,
                                   resolved_gun_id,
                                   replace_id,
                                   row_has_skin_signal(skin_info)))
                        continue
                    _v815_admitted[_st_v] = _v815_admitted.get(_st_v, 0) + 1
                    if len(admit_names) < 24:
                        admit_names.append(
                            '%s/%s' % (skin_id,
                                       _proto_get(skin_info, 'skin_name',
                                                  None)))


            candidate_count += 1
            if target_equip_id not in temp_skins:
                temp_skins[target_equip_id] = {}
            _name_candidates = gst_name_candidates.get(skin_id, [])
            skin_name = ''
            for _candidate_name in _name_candidates:
                if not _contains_cjk(_candidate_name):
                    skin_name = _candidate_name
                    break
            if not skin_name:
                skin_name = _name_candidates[0] if _name_candidates else _proto_english_name(
                    skin_info,
                    ('en_name', 'english_name', 'name_en', 'skin_name', 'name'),
                    'Skin_%s' % (skin_id,))
            if _contains_cjk(skin_name):
                # v8.16: the embedded 644-paint table first - it
                # covers the whole 0100 family the v8.15 device
                # reported (27,684 CJK names).
                skin_name = translate_paint(skin_name)
            if _contains_cjk(skin_name):
                skin_name = _english_display_text(skin_name, skin_name)
            if _contains_cjk(skin_name):
                # v4.2: revert the v4.1 "Skin <id>" fallback. The user wants
                # real names with their level, not bare ids. Try the game's
                # own offline table one last time, then keep the original
                # name rather than degrading it to a number.
                _tr = _lang_translate(skin_name)
                if _tr and not _contains_cjk(_tr):
                    skin_name = _tr
            # v8.18: non-displayable variant rows - placeholder bodies
            # ('Yamato(Placeholder)'), low-spec / low-grade meshes
            # ('Low-Spec Appearance', 'Low Grade Inspect') and the
            # advanced-body upgrade meshes ('Heavenly Ink Armor LV5
            # Advanced Body'). Real displayable skins never carry
            # these tokens.
            if is_junk_skin_name(skin_name):
                if gun_row:
                    broadened_row = True
                    append_ids.add(skin_id)
                else:
                    junk_dropped += 1
                    continue
            if recovery_used or new_type_row:
                append_ids.add(skin_id)
            if recovery_used:
                _v841g_recovered += 1
                if len(recovery_samples) < 24:
                    recovery_samples.append(
                        '%s/%s' % (skin_id, skin_name))
            if new_type_row:
                new_type_admitted += 1
            base_name, level = _base_skin_name_and_level(skin_name)
            dedup_key = base_name if base_name else skin_id
            existing = (name_levels.get((target_equip_id, dedup_key))
                        if gun_row else
                        temp_skins[target_equip_id].get(dedup_key))
            if gun_row:
                if existing:
                    # A second name/level variant was historically collapsed.
                    broadened_row = True
                    append_ids.add(skin_id)
                    if existing[0] == level and existing[1] != skin_id:
                        _v841g_same_level_kept += 1
                exact_key = 'skin-id:%s' % (skin_id,)
                if exact_key in temp_skins[target_equip_id]:
                    _v841all_exact_duplicates += 1
                    continue
                if (target_equip_id, dedup_key) not in name_levels:
                    name_levels[(target_equip_id, dedup_key)] = (
                        level, skin_id)
                temp_skins[target_equip_id][exact_key] = (level, skin_id)
            else:
                base_name, level = _base_skin_name_and_level(skin_name)
                dedup_key = base_name if base_name else skin_id
                existing = temp_skins[target_equip_id].get(dedup_key)
                if existing and existing[0] > level:
                    continue
                if (existing and existing[0] == level
                        and existing[1] != skin_id):
                    # Same name + same max level can still be DISTINCT skins.
                    # Keep every such ID; only lower upgrade levels are collapsed.
                    _alt_key = '%s|skin:%s' % (dedup_key, skin_id)
                    temp_skins[target_equip_id][_alt_key] = (level, skin_id)
                    append_ids.add(skin_id)
                    _v841g_same_level_kept += 1
                else:
                    if existing and existing[0] < level and isinstance(dedup_key, str):
                        _prefix = dedup_key + '|skin:'
                        for _key, (_lv, _sid) in list(
                                temp_skins[target_equip_id].items()):
                            if ((_key == dedup_key or _key.startswith(_prefix))
                                    and _lv < level):
                                del temp_skins[target_equip_id][_key]
                    temp_skins[target_equip_id][dedup_key] = (level, skin_id)

            if gun_row:
                gun_rows += 1
                if broadened_row:
                    _v841all_broadened += 1

            eff_id = _skin_effect_id(skin_info)
            info = {
                'name': skin_name,
                'skin_level': level,
                'skin_quality': _safe_int(_proto_get(
                    skin_info, 'skin_quality',
                    _proto_get(skin_info, 'quality', None)), 0),
                'effect_id': eff_id,
                'effect_path': _resolve_effect(eff_id),
                'optic_b_fx': _proto_get(skin_info, 'optic_b_fx'),
                'optic_b_fx_path': _resolve_effect(_proto_get(skin_info, 'optic_b_fx')),
                'skin_optic_id': _proto_get(skin_info, 'skin_optic_id'),
                'kill_mat': _proto_get(skin_info, 'kill_mat'),
                'team_kill_mat': _proto_get(skin_info, 'Team_kill_mat'),
                'kill_mat_start_time': _proto_get(skin_info, 'kill_mat_start_time'),
                'team_kill_mat_start_time': _proto_get(skin_info, 'Team_kill_mat_start_time'),
                'kill_team_extra_model_id': _proto_get(skin_info, 'kill_team_extra_model_id'),
                'kill_team_extra_hexie_model_id': _proto_get(skin_info, 'kill_team_extra_hexie_model_id'),
                'kill_tip_icon_replace': _proto_get(skin_info, 'kill_tip_icon_replace'),
                'extra_model_kill_team_anim_name': _proto_get(skin_info, 'ExtraModelKillTeamAnimName'),
                'team_die_action_pose': _proto_get(skin_info, 'TeamDieActionPose'),
                'team_die_action_pose_time': _proto_get(skin_info, 'TeamDieActionPoseTime'),
                'special_die_action_pose': _proto_get(skin_info, 'SpecialDieActionPose'),
                'fps_tracer_bullet_id': _proto_get(skin_info, 'fps_tracer_bullet_id'),
                'fps_adstracer_bullet_id': _proto_get(skin_info, 'fps_adstracer_bullet_id'),
                'tps_tracer_bullet_id': _proto_get(skin_info, 'tps_tracer_bullet_id'),
                'fps_simple_tracer_bullet_id': _proto_get(skin_info, 'fps_simple_tracer_bullet_id'),
                'extra_ballistic_tracer_bullet_id': _proto_get(skin_info, 'extra_ballistic_tracer_bullet_id'),
            }
            # Fill missing known effect/optic fields from the secondary
            # template source, and retain every effect-like scalar field
            # for WeaponFX. Field names differ between skin families, so
            # guessing only the old fixed subset lost hit/tracer data.
            for _field in (
                'skin_optic_id', 'kill_mat', 'team_kill_mat',
                'kill_mat_start_time', 'team_kill_mat_start_time',
                'kill_team_extra_model_id', 'kill_team_extra_hexie_model_id',
                'kill_tip_icon_replace', 'fps_tracer_bullet_id',
                'fps_adstracer_bullet_id', 'tps_tracer_bullet_id',
                'fps_simple_tracer_bullet_id', 'extra_ballistic_tracer_bullet_id',
            ):
                if info.get(_field) is None:
                    for _src_info in gst_infos_by_id.get(skin_id, []):
                        _value = _proto_get(_src_info, _field, None)
                        if _value is not None:
                            info[_field] = _value
                            break
            if info.get('effect_id') is None:
                for _src_info in gst_infos_by_id.get(skin_id, []):
                    _value = _skin_effect_id(_src_info)
                    if _value is not None:
                        info['effect_id'] = _value
                        info['effect_path'] = _resolve_effect(_value)
                        break
            _raw_effect_fields = {}
            for _src_info in gst_infos_by_id.get(skin_id, []):
                for _key, _value in _data_items(_src_info):
                    if _value is None:
                        continue
                    _key_text = str(_key)
                    _lower = _key_text.lower()
                    if not any(token in _lower for token in (
                        'fx', 'effect', 'tracer', 'trace', 'hit', 'kill',
                        'optic', 'scope', 'reticle', 'sfx', 'bullet',
                    )):
                        continue
                    if isinstance(_value, (str, int, float, bool)):
                        _raw_effect_fields.setdefault(_key_text, _value)
                    elif isinstance(_value, (list, tuple)) and len(_value) <= 8:
                        _raw_effect_fields.setdefault(_key_text, _value)
            info['raw_effect_fields'] = _raw_effect_fields
            info['lobby_item_id'] = None
            if _v841g_link:
                _linked_item_id, _linked_proto = _v841g_link
                if _linked_item_id:
                    info['lobby_item_id'] = _linked_item_id
                    SKIN_TO_ITEM[skin_id] = _linked_item_id
                    ITEM_TO_SKIN[_linked_item_id] = skin_id
                    SKIN_LOBBY_PROTO[skin_id] = _linked_proto
            built_skin_info[skin_id] = info

        if candidate_count <= 0:
            samples = []
            for sample_id, sample_info in gst_items[:3]:
                samples.append((
                    sample_id,
                    _proto_keys(sample_info),
                    _proto_get(sample_info, 'gun_id'),
                    _proto_get(sample_info, 'replace_equip_id'),
                    _proto_get(sample_info, 'gun_skin_type'),
                ))
            raise RuntimeError(
                'gun template data present but no type-1 candidates '
                '(equip=%d templates=%d types=%r samples=%r)'
                % (len(equip_items), len(gst_items), skin_type_counts, samples))

        HARDCORE_SKINS = {33: [21000009,91000001,91000002,91000003,11000018,21000005,11000007,31000010,21000008,31000007,11000002,811990203,141199023]}
        for equip_id, hardcore_list in HARDCORE_SKINS.items():
            if equip_id not in temp_skins:
                temp_skins[equip_id] = {}
            existing_skin_ids = set(
                sid for _lvl, sid in temp_skins[equip_id].values())
            for skin_id in hardcore_list:
                if skin_id in existing_skin_ids:
                    continue
                existing_skin_ids.add(skin_id)
                temp_skins[equip_id]['hardcore_%s' % (skin_id,)] = (99, skin_id)
                if skin_id not in built_skin_info:
                    built_skin_info[skin_id] = {
                        'name': 'Skin_%s' % (skin_id,),
                        'effect_id': None, 'effect_path': None,
                        'optic_b_fx': None, 'optic_b_fx_path': None,
                        'skin_optic_id': None, 'kill_mat': None,
                        'team_kill_mat': None, 'kill_mat_start_time': None,
                        'team_kill_mat_start_time': None,
                        'kill_team_extra_model_id': None,
                        'kill_team_extra_hexie_model_id': None,
                        'kill_tip_icon_replace': None,
                        'extra_model_kill_team_anim_name': None,
                        'team_die_action_pose': None,
                        'team_die_action_pose_time': None,
                        'special_die_action_pose': None,
                        'fps_tracer_bullet_id': None,
                        'fps_adstracer_bullet_id': None,
                        'tps_tracer_bullet_id': None,
                        'fps_simple_tracer_bullet_id': None,
                        'extra_ballistic_tracer_bullet_id': None,
                        'raw_effect_fields': {}, 'lobby_item_id': None,
                    }


        # ---- English display names from lobby item protos (v2.5) ----
        # Gun template skin_name can be a Chinese source/design name.
        # The global client's display name lives on the matching lobby
        # item. Build template-id -> English lobby-name without changing
        # any force IDs or menu ordering yet (sorting happens below).
        def _candidate_ids_from_proto(proto):
            out = []
            def _add_candidate(value):
                if isinstance(value, (list, tuple)):
                    for item in value[:8]:
                        _add_candidate(item)
                    return
                ivalue = _safe_int(value, 0)
                if ivalue and ivalue not in out:
                    out.append(ivalue)
            for _key, _value in _data_items(proto):
                _key_text = str(_key)
                _lower = _key_text.lower()
                if any(token in _lower for token in ('skin', 'guise', 'template')):
                    _add_candidate(_value)
                elif _lower in ('id', 'item_id'):
                    _ivalue = _safe_int(_value, 0)
                    if _ivalue in built_skin_info:
                        _add_candidate(_ivalue)
            return out

        def _collect_int_values(value, out=None, _depth=0):
            if out is None:
                out = []
            if _depth > 4 or len(out) >= 64:
                return out
            if isinstance(value, (list, tuple)):
                for item in value[:32]:
                    _collect_int_values(item, out, _depth + 1)
                return out
            ivalue = _safe_int(value, 0)
            if ivalue and ivalue not in out:
                out.append(ivalue)
                return out
            for _key, _nested in _data_items(value)[:32]:
                _collect_int_values(_key, out, _depth + 1)
                _collect_int_values(_nested, out, _depth + 1)
            return out

        _lobby_scan_completed = [False]

        def _lobby_english_names():
            skin_names = {}
            equip_names2 = {}
            proto_by_item = {}
            item_by_skin = {}
            if _lobby_scan_completed[0]:
                return skin_names, equip_names2, proto_by_item, item_by_skin
            lid_mod = None
            gunskin_mod = None
            try:
                lid_mod = _import_module('gclient.data.lobby_item_data')
            except Exception:
                lid_mod = None
            try:
                gunskin_mod = _import_module('gclient.data.lobby_gun_skin_item_data')
            except Exception:
                gunskin_mod = None
            if lid_mod is None and gunskin_mod is None:
                return skin_names, equip_names2, proto_by_item, item_by_skin

            def _lookup_item(item_id):
                item_id = _safe_int(item_id, 0)
                if not item_id:
                    return None
                if item_id in proto_by_item:
                    return proto_by_item[item_id]
                for mod in (gunskin_mod, lid_mod):
                    if mod is None:
                        continue
                    record = _data_get(getattr(mod, 'data', None), item_id, None)
                    if record is not None and _data_items(record):
                        proto_by_item[item_id] = record
                        return record
                return None

            def _consider(item_id, proto):
                if proto is None:
                    return
                candidates = _candidate_ids_from_proto(proto)
                item_int = _safe_int(item_id, 0)
                if item_int and item_int in built_skin_info:
                    candidates.append(item_int)
                equip_candidate = _safe_int(_proto_get(proto, 'equip_id', None), 0)
                sub_type = _safe_int(_proto_get(proto, 'sub_type', None), 0)
                is_gun_skin_item = sub_type in (100, 550, 210)
                if not candidates and not equip_candidate and not is_gun_skin_item:
                    return
                for sid in candidates:
                    if sid in built_skin_info and item_int:
                        item_by_skin.setdefault(sid, item_int)
                display = _proto_english_name(
                    proto,
                    ('en_name', 'english_name', 'name_en', 'name', 'skin_name'),
                    '')
                if not display or _contains_cjk(display):
                    return
                for sid in candidates:
                    if sid in built_skin_info:
                        skin_names.setdefault(sid, display)
                if equip_candidate and equip_candidate in equip_names:
                    equip_names2.setdefault(equip_candidate, display)

            # Smaller generated gun-skin module first; its data/maps are
            # the authoritative template->item relationship.
            processed = 0
            try:
                for item_id, proto in _data_items(getattr(gunskin_mod, 'data', None)):
                    proto_by_item[item_id] = proto
                    _consider(item_id, proto)
                    processed += 1
            except Exception:
                pass
            try:
                for attr in ('GUN_ID_TO_SKIN_ITEM_IDS', 'GUN_ID_TO_GUISE_ITEM_IDS'):
                    mapping = getattr(gunskin_mod, attr, None)
                    for _gun_id, item_ids in _data_items(mapping):
                        for item_id in _collect_int_values(item_ids):
                            _consider(item_id, _lookup_item(item_id))
                            processed += 1
            except Exception:
                pass
            # Subtype index -> direct O(1) lobby lookups (no full scan).
            try:
                subtype_mod = _import_module('gclient.data.sub_type_to_item_ids_data')
                subtype_data = getattr(subtype_mod, 'data', None)
                for sub_type in (550, 100, 210):
                    for item_id in _collect_int_values(_data_get(subtype_data, sub_type, None)):
                        _consider(item_id, _lookup_item(item_id))
                        processed += 1
            except Exception:
                pass
            if processed:
                _lobby_scan_completed[0] = True
            return skin_names, equip_names2, proto_by_item, item_by_skin

        _english_skin_names, _english_equip_names, _lobby_proto_by_item, _item_by_skin = _lobby_english_names()
        _late_lobby_name_scan[0] = _lobby_english_names
        for _sid, _item_id in _item_by_skin.items():
            SKIN_TO_ITEM[_sid] = _item_id
            ITEM_TO_SKIN[_item_id] = _sid
            _info = built_skin_info.get(_sid)
            _proto = _lobby_proto_by_item.get(_item_id)
            if _info is not None:
                _info['lobby_item_id'] = _item_id
            if _proto is not None:
                SKIN_LOBBY_PROTO[_sid] = _proto
                if _info is not None:
                    if _info.get('skin_optic_id') is None:
                        _info['skin_optic_id'] = _proto_get(_proto, 'skin_optic_id', None)
                    _raw = _info.setdefault('raw_effect_fields', {})
                    for _key, _value in _data_items(_proto):
                        if _value is None:
                            continue
                        _key_text = str(_key)
                        _lower = _key_text.lower()
                        if any(token in _lower for token in (
                            'fx', 'effect', 'tracer', 'trace', 'hit', 'kill',
                            'optic', 'scope', 'reticle', 'sfx', 'bullet',
                        )) and isinstance(_value, (str, int, float, bool)):
                            _raw.setdefault(_key_text, _value)
        _localized_skins = 0
        for _sid, _english_name in _english_skin_names.items():
            _info = built_skin_info.get(_sid)
            if not _info:
                continue
            _old_name = _display_text(_info.get('name'), '')
            if _contains_cjk(_old_name) or _old_name.startswith('Skin_'):
                _info['name'] = _english_name
                _localized_skins += 1
        _localized_equips = 0
        for _equip_id, _english_name in _english_equip_names.items():
            if _contains_cjk(equip_names.get(_equip_id, '')):
                equip_names[_equip_id] = _english_name
                _localized_equips += 1

        # The game's own gun-name helper is localized for the selected
        # client language. Use it for any weapon names still in CJK.
        try:
            _gun_ui_util = _import_module('gclient.util.gun_ui_util')
            _get_gun_name = getattr(_gun_ui_util, 'GetGunNameByGunId', None)
            if callable(_get_gun_name):
                for _equip_id, _old_name in list(equip_names.items()):
                    if not _contains_cjk(_old_name):
                        continue
                    _gun_id = _proto_get(equip_by_id.get(_equip_id, {}), 'gun_id', None)
                    if not _gun_id:
                        continue
                    _new_name = _english_display_text(_get_gun_name(_gun_id), '')
                    if _new_name and not _contains_cjk(_new_name):
                        equip_names[_equip_id] = _new_name
                        _localized_equips += 1
        except Exception:
            pass

        # ---- v4.7 runtime translation ----------------------------------
        # Everything above (lobby proto, gclient.lang, GetGunNameByGunId) is
        # best-effort and comes back empty on vc163. This is the pass that
        # actually guarantees English: any name still carrying CJK goes
        # through the segment table, so the menu never shows it raw.
        _translated_skins = 0
        for _sid, _info in built_skin_info.items():
            if not _info:
                continue
            _old_name = _display_text(_info.get('name'), '')
            if not _old_name:
                continue
            # Run researched exact/alias matches even when an earlier paint or
            # language pass already produced English.  Ordinary English names
            # are returned unchanged by translate_name.
            _new_name = translate_name(_old_name)
            if _new_name and _new_name != _old_name:
                _info['name'] = _new_name
                _translated_skins += 1
        _translated_equips = 0
        for _equip_id, _old_name in list(equip_names.items()):
            if not _contains_cjk(_old_name):
                continue
            _new_name = translate_name(_old_name)
            if _new_name:
                equip_names[_equip_id] = _new_name
                _translated_equips += 1
        _plog('[NAME] translated skins=%d weapons=%d overrides=%d unresolved_chars=%d'
              % (_translated_skins, _translated_equips, _name_overrides_loaded[0],
                 len(_name_unresolved_chars)))

        _unresolved_names = []
        for _equip_id, _old_name in equip_names.items():
            if _contains_cjk(_old_name) and len(_unresolved_names) < 8:
                _unresolved_names.append('W%s=%s' % (_equip_id, _old_name))
        for _sid, _info in built_skin_info.items():
            _old_name = _display_text(_info.get('name'), '')
            if _contains_cjk(_old_name) and len(_unresolved_names) < 16:
                _unresolved_names.append('S%s=%s' % (_sid, _old_name))
        _plog('[CATALOG] English names: lobby skins localized=%d equips=%d '
              'unresolved_samples=%r'
              % (_localized_skins, _localized_equips, _unresolved_names))

        built_wep = {}
        built_names = dict(equip_names)
        built_skin_to_equip = {}
        for equip_id, entries in temp_skins.items():
            skin_ids = _v841all_unique_ids(
                [sid for _lvl, sid in entries.values()])
            if not skin_ids:
                continue
            # Stable, human-friendly order in the menu. The same order is
            # used by both the UDP lines and the Python force-by-index code.
            skin_ids = sorted(
                skin_ids,
                key=lambda sid: (
                    1 if sid in append_ids else 0,
                    _display_text(_proto_get(built_skin_info.get(sid, {}), 'name'), '').lower(),
                    _safe_int(sid, 0),
                ))
            name = equip_names.get(equip_id, str(equip_id))
            built_wep[equip_id] = [name] + skin_ids
            built_names[equip_id] = name
            for sid in skin_ids:
                built_skin_to_equip[sid] = equip_id

        # v2.124: "some guns are missing" fix - a gun whose skins were all
        # dropped (camo-only families / default bodies) must STILL show as a
        # gun row in the picker. Every resolved gun keeps a name-only row and
        # equips its default body through the normal default path.
        for _gid24, _eid24 in (gun_to_equip_map or {}).items():
            if _eid24 not in built_wep:
                _nm24 = equip_names.get(_eid24) or str(_eid24)
                built_wep[_eid24] = [_nm24]
                built_names[_eid24] = _nm24
        if not built_wep:
            raise RuntimeError('gun catalog build produced no weapons')

        # v8.20: display rows for the merged melee slots. Their skins
        # live under Dagger (33) for the APPLY, but the user's v8.20
        # report wants every real gun visible - 97 Dual Blades, 107
        # Scythe and 141 Artifact each get their own menu row with
        # their own skin list (same skin ids, same apply path).
        MERGED_FALLBACK_NAMES = {97: 'Dual Blades',
                                       107: 'Scythe',
                                       141: 'Artifact'}
        built_merged_display = {}
        for _src in (97, 107, 141):
            _src_skins = sorted(
                (sid for sid, ssrc in merge_src.items()
                 if ssrc == _src),
                key=lambda sid: (
                    1 if sid in append_ids else 0,
                    _display_text(_proto_get(built_skin_info.get(sid, {}), 'name'), '').lower(),
                    _safe_int(sid, 0), ))
            if not _src_skins:
                continue
            _src_name = _display_text(equip_names.get(_src, ''), '')
            if (not _src_name) or _contains_cjk(_src_name):
                _src_name = MERGED_FALLBACK_NAMES.get(_src, str(_src))
            built_merged_display[_src] = [_src_name] + _src_skins

        WEP_GUN_IDS = {}
        for _gun_id, _equip_id in gun_to_equip_map.items():
            WEP_GUN_IDS[_equip_id] = _gun_id
        WEP_MELEE_IDS = {}
        for _equip_id, _equip_info in equip_by_id.items():
            _melee_id = _proto_get(_equip_info, 'melee_weapon_id', None)
            # A row with a real gun mapping is never a melee slot, even if
            # the export also carries a melee_weapon_id compatibility field.
            if _melee_id and _equip_id not in WEP_GUN_IDS:
                WEP_MELEE_IDS[_equip_id] = _melee_id

        # Publish only after a complete build; a failed retry cannot leave
        # a half-populated catalog behind.
        WEP = built_wep
        WEP_NAMES = built_names
        WEP_SKIN_INFO = built_skin_info
        SKIN_TO_EQUIP = built_skin_to_equip
        _v841all_cache = globals().get('level_cache')
        if _v841all_cache is not None:
            _v841all_cache['sig'] = None
        global WEP_MERGED_DISPLAY
        WEP_MERGED_DISPLAY = built_merged_display
        return {
            'source': gst_source,
            'equip_raw': len(equip_items),
            'skin_raw': len(gst_items),
            'candidates': candidate_count,
            'types': sorted(skin_type_counts.items(),
                            key=lambda kv: -kv[1])[:8],
            'melee_slots': sorted(_known_melee_slots),
            'v815_admitted': dict(_v815_admitted),
            'v815_admit_names': list(admit_names),
            'v816_rejects': list(_v816_rejects),
            'v816_new_guns': sorted(cat_unknown),
            'v817_camo_dropped': camo_dropped,
            'v817_melee_merged': melee_merged,
            'v818_base_dropped': base_dropped,
            'v818_junk_dropped': junk_dropped,
            'v841g_lobby_scanned': _v841g_lobby_scanned[0],
            'v841g_lobby_links': len(_v841g_lobby_links),
            'v841g_recovered': _v841g_recovered,
            'v841g_new_type_admitted': new_type_admitted,
            'v841g_same_level_kept': _v841g_same_level_kept,
            'v841g_recovery_samples': list(recovery_samples),
            'v841all_gun_rows': gun_rows,
            'v841all_broadened': _v841all_broadened,
            'v841all_exact_duplicates': _v841all_exact_duplicates,
            'melee_skin_counts': {
                _eq: len(temp_skins.get(_eq, {}))
                for _eq in sorted(_known_melee_slots)
                if temp_skins.get(_eq)},
        }


    def _try_build_weapon_catalog(reason):
        if _weapon_catalog_ready[0]:
            return True
        _weapon_catalog_attempts[0] += 1
        attempt = _weapon_catalog_attempts[0]
        try:
            stats = build_auto_wep_dictionary()
            _weapon_catalog_ready[0] = True
            _plog(
                "[CATALOG] weapon build ok reason=%s attempt=%d source=%s "
                "equip_raw=%d skin_raw=%d candidates=%d weapons=%d names=%d skins=%d types=%r "
                "v815_admitted=%r v815_admit_names=%r "
                "v816_rejects=%r v816_new_guns=%r melee_skins=%r "
                "v817_camo_dropped=%r v817_melee_merged=%r "
                "v818_base_dropped=%r v818_junk_dropped=%r"
                % (
                    reason, attempt, stats.get('source'),
                    stats.get('equip_raw', 0), stats.get('skin_raw', 0),
                    stats.get('candidates', 0), len(WEP), len(WEP_NAMES),
                    len(WEP_SKIN_INFO),
                    stats.get('types'),
                    stats.get('v815_admitted', {}),
                    stats.get('v815_admit_names', [])[:24],
                    stats.get('v816_rejects', [])[:24],
                    stats.get('v816_new_guns', []),
                    stats.get('melee_skin_counts', {}),
                    stats.get('v817_camo_dropped', 0),
                    stats.get('v817_melee_merged', 0),
                    stats.get('v818_base_dropped', 0),
                    stats.get('v818_junk_dropped', 0),
                ))
            _plog('[CATALOG] gun completeness lobby_scanned=%d '
                  'lobby_links=%d recovered=%d new_types=%d '
                  'same_level_kept=%d samples=%r'
                  % (stats.get('v841g_lobby_scanned', 0),
                     stats.get('v841g_lobby_links', 0),
                     stats.get('v841g_recovered', 0),
                     stats.get('v841g_new_type_admitted', 0),
                     stats.get('v841g_same_level_kept', 0),
                     stats.get('v841g_recovery_samples', [])[:24]))
            _plog('[CATALOG] all-guns reset rows=%d broadened=%d exact_duplicates=%d; saved selections untouched'
                  % (stats.get('v841all_gun_rows', 0),
                     stats.get('v841all_broadened', 0),
                     stats.get('v841all_exact_duplicates', 0)))
            return True
        except Exception:
            if attempt == 1 or attempt % 10 == 0:
                _plog("[CATALOG] weapon build not ready reason=%s attempt=%d\n%s"
                      % (reason, attempt, _exc_text()))
            return False

    _try_build_weapon_catalog('initial')


    _gunskinutil_scanned_guns = set()
    _late_enrich_tick = [0]

    def _count_cjk_weapon_names():
        count = 0
        try:
            for _info in WEP_SKIN_INFO.values():
                if _contains_cjk(_display_text(_info.get('name'), '')):
                    count += 1
            for _equip_id, _name in WEP_NAMES.items():
                if _equip_id in WEP and _contains_cjk(_name):
                    count += 1
        except Exception:
            pass
        return count

    def _apply_late_weapon_name(skin_id, display):
        if not display or _contains_cjk(display):
            return False
        info = WEP_SKIN_INFO.get(skin_id)
        if not info:
            return False
        old = _display_text(info.get('name'), '')
        if _contains_cjk(old) or old.startswith('Skin_'):
            info['name'] = display
            return True
        return False

    def _apply_late_equip_name(equip_id, display):
        if not display or _contains_cjk(display):
            return False
        changed = False
        if _contains_cjk(WEP_NAMES.get(equip_id, '')):
            WEP_NAMES[equip_id] = display
            changed = True
        entries = WEP.get(equip_id)
        if entries and _contains_cjk(entries[0]):
            entries[0] = display
            changed = True
        return changed

    def _extract_gunskinutil_item(item):
        proto = None
        item_id = 0
        candidates = []
        def _add(value):
            if isinstance(value, (list, tuple)):
                for nested in value[:8]:
                    _add(nested)
                return
            ivalue = _safe_int(value, 0)
            if ivalue and ivalue not in candidates:
                candidates.append(ivalue)
        # GetAllGunSkinItemList may return ids, mappings, or IHallItems.
        if isinstance(item, (int, str)):
            item_id = _safe_int(item, 0)
            for modname in ('gclient.data.lobby_gun_skin_item_data', 'gclient.data.lobby_item_data'):
                try:
                    mod = _import_module(modname)
                    proto = _data_get(getattr(mod, 'data', None), item_id, None)
                    if proto is not None and _data_items(proto):
                        break
                except Exception:
                    proto = None
        else:
            try:
                proto = getattr(item, 'item_proto', None)
            except Exception:
                proto = None
            if proto is None:
                proto = item
            for attr in ('item_id', 'id'):
                try:
                    value = getattr(item, attr, None)
                    if value:
                        item_id = _safe_int(value, 0)
                        if item_id:
                            break
                except Exception:
                    pass
            if not item_id:
                item_id = _safe_int(_proto_get(proto, 'id', None), 0) or _safe_int(_proto_get(proto, 'item_id', None), 0)
            if not item_id:
                try:
                    packed = item.Pack()
                    if isinstance(packed, (list, tuple)) and len(packed) > 1:
                        item_id = _safe_int(packed[1], 0)
                    elif isinstance(packed, dict):
                        item_id = _safe_int(packed.get('item_id'), 0)
                except Exception:
                    pass
            for attr in ('skin_id', 'guise_id', 'guise_template_id', 'skin_template_id', 'template_id'):
                try:
                    _add(getattr(item, attr, None))
                except Exception:
                    pass
        for _key, _value in _data_items(proto):
            _lower = str(_key).lower()
            if any(token in _lower for token in ('skin', 'guise', 'template')):
                _add(_value)
        if item_id and item_id in WEP_SKIN_INFO:
            _add(item_id)
        display = _proto_english_name(
            proto, ('en_name', 'english_name', 'name_en', 'name', 'skin_name'), '')
        if not display:
            try:
                display = _english_display_text(getattr(item, 'name', ''), '')
            except Exception:
                display = ''
        if (not display or _contains_cjk(display)) and item_id:
            for _modname in ('gclient.data.lobby_item_data', 'gclient.data.lobby_gun_skin_item_data'):
                try:
                    _mod = _import_module(_modname)
                    _record = _data_get(getattr(_mod, 'data', None), item_id, None)
                    _alt = _proto_english_name(
                        _record, ('en_name', 'english_name', 'name_en', 'name', 'skin_name'), '')
                    if _alt and not _contains_cjk(_alt):
                        proto = _record
                        display = _alt
                        break
                except Exception:
                    pass
        return item_id, candidates, proto, display

    _late_gun_cursor = [0]
    _gunskinutil_sample_logged = [False]

    def _enrich_weapon_names_late(reason='late', allow_gunskinutil=False, max_guns=1):
        """Retry English names + template->item mapping after lobby/lang
        data is ready. This only edits display names/maps in place; it
        never re-sorts WEP lists, so saved menu indices stay stable."""
        if not _weapon_catalog_ready[0]:
            return 0
        changed = 0
        mapped = 0
        _reset_lang_caches_if_empty()

        scan = _late_lobby_name_scan[0]
        if callable(scan):
            try:
                skin_names, equip_names2, proto_by_item, item_by_skin = scan()
                for sid, item_id in item_by_skin.items():
                    if SKIN_TO_ITEM.get(sid) != item_id:
                        SKIN_TO_ITEM[sid] = item_id
                        ITEM_TO_SKIN[item_id] = sid
                        mapped += 1
                    info = WEP_SKIN_INFO.get(sid)
                    if info is not None:
                        info['lobby_item_id'] = item_id
                    proto = proto_by_item.get(item_id)
                    if proto is not None:
                        SKIN_LOBBY_PROTO[sid] = proto
                for sid, display in skin_names.items():
                    changed += 1 if _apply_late_weapon_name(sid, display) else 0
                for equip_id, display in equip_names2.items():
                    changed += 1 if _apply_late_equip_name(equip_id, display) else 0
            except Exception:
                pass

        # The game's own warehouse/list helper is authoritative for
        # template <-> lobby item mapping and localized item protos, but
        # it needs an avatar and should run on the game thread, so the
        # sender-thread pass leaves it to Space post-tick.
        try:
            if not allow_gunskinutil:
                raise RuntimeError('gunskinutil deferred to game thread')
            gun_skin_util = _import_module('gclient.util.gun_skin_util')
            get_all = getattr(gun_skin_util, 'GetAllGunSkinItemList', None)
            get_melee = getattr(gun_skin_util, 'GetAllMeleeSkinItemList', None)
            get_guise = getattr(gun_skin_util, 'GetWarehouseGunGuiseItemList', None)
            equip_entries = list(WEP.items())
            if equip_entries:
                processed_guns = 0
                checked_guns = 0
                while checked_guns < len(equip_entries) and processed_guns < max(1, max_guns):
                    equip_id, entries = equip_entries[_late_gun_cursor[0] % len(equip_entries)]
                    _late_gun_cursor[0] = (_late_gun_cursor[0] + 1) % len(equip_entries)
                    checked_guns += 1
                    skin_ids = entries[1:]
                    needs = any(
                        _contains_cjk(_display_text((WEP_SKIN_INFO.get(sid) or {}).get('name'), '')) or
                        sid not in SKIN_TO_ITEM
                        for sid in skin_ids)
                    if not needs:
                        continue
                    processed_guns += 1
                    gun_id = WEP_GUN_IDS.get(equip_id)
                    melee_id = WEP_MELEE_IDS.get(equip_id)
                    item_objects = []
                    try:
                        if gun_id and callable(get_all):
                            result = get_all(gun_id, include_mall=False, need_random=False, include_locked=True)
                            if result:
                                item_objects.extend(list(result))
                                _gunskinutil_scanned_guns.add(('gun', gun_id))
                        if gun_id and callable(get_guise):
                            try:
                                result = get_guise(gun_id, need_random=False)
                            except TypeError:
                                result = get_guise(gun_id)
                            if result:
                                item_objects.extend(list(result))
                                _gunskinutil_scanned_guns.add(('guise', gun_id))
                        if melee_id and callable(get_melee):
                            result = get_melee(melee_id, include_locked=True)
                            if result:
                                item_objects.extend(list(result))
                                _gunskinutil_scanned_guns.add(('melee', melee_id))
                    except Exception:
                        item_objects = []
                    if item_objects and not _gunskinutil_sample_logged[0]:
                        _gunskinutil_sample_logged[0] = True
                        _sample = item_objects[0]
                        _plog('[CATALOG] GunSkinUtil sample gun=%r melee=%r count=%d first_type=%s first=%r'
                              % (gun_id, melee_id, len(item_objects), type(_sample).__name__, _sample))
                    for item in item_objects:
                        try:
                            item_id, candidates, proto, display = _extract_gunskinutil_item(item)
                        except Exception:
                            continue
                        for sid in candidates:
                            if sid not in WEP_SKIN_INFO:
                                continue
                            if item_id and SKIN_TO_ITEM.get(sid) != item_id:
                                SKIN_TO_ITEM[sid] = item_id
                                ITEM_TO_SKIN[item_id] = sid
                                WEP_SKIN_INFO[sid]['lobby_item_id'] = item_id
                                mapped += 1
                            if proto is not None:
                                SKIN_LOBBY_PROTO[sid] = proto
                            changed += 1 if _apply_late_weapon_name(sid, display) else 0
        except Exception:
            pass

        # Retry direct lang translation now that the client language
        # package has had time to initialize.
        try:
            _v816_n = 0
            for info in WEP_SKIN_INFO.values():
                old = _display_text(info.get('name'), '')
                if _contains_cjk(old):
                    # v8.16: paint table first (covers everything
                    # the v8.15 device reported), then the segment
                    # translator.
                    _p = translate_paint(old)
                    if _p != old and not _contains_cjk(_p):
                        info['name'] = _p
                        changed += 1
                        old = _p
                    if _contains_cjk(old):
                        translated = _lang_translate(old)
                        if translated and not _contains_cjk(translated):
                            info['name'] = translated
                            changed += 1
                _v816_n += 1
                if (_v816_n % 200) == 0:
                    # v8.16: the v8.15 device stalled the game
                    # thread 0.4-1.0 s while this pass held the GIL
                    # across 29k names. Yield every 200 names.
                    time.sleep(0.02)
            for equip_id in list(WEP.keys()):
                old = WEP_NAMES.get(equip_id, '')
                if _contains_cjk(old):
                    translated = _lang_translate(old)
                    if translated:
                        changed += 1 if _apply_late_equip_name(equip_id, translated) else 0
        except Exception:
            pass

        if changed or mapped:
            _plog('[CATALOG] late English enrichment reason=%s changed=%d mapped=%d cjk_remaining=%d item_maps=%d'
                  % (reason, changed, mapped, _count_cjk_weapon_names(), len(SKIN_TO_ITEM)))
        return changed

    def _build_skin_info_lines():
        lines = ['BEGIN']
        # v8.16: category per weapon - the menu list is now DYNAMIC
        # (the hardcoded C++ table missed G36/Scorpion entirely).
        for equip_id in WEP.keys():
            lines.append('C|%d|%s' % (equip_id,
                                      weapon_cat(equip_id)))
        for equip_id, entries in WEP.items():
            weapon_name = _display_text(entries[0], str(equip_id))
            weapon_display = weapon_name
            lines.append("W|%d|%s" % (equip_id, weapon_display))
            for idx, skin_id in enumerate(entries[1:], start=1):
                _info = WEP_SKIN_INFO.get(skin_id) or {}
                # v2.86: tier filter - Ultra/Eternal/EVO/Xtreme or
                # leveled rows only; camo/basic never reaches the menu.
                if not menu_keep(skin_id, _info):
                    continue
                skin_name = _display_text(_info.get('name') or str(skin_id),
                                          str(skin_id))
                # v4.2: level back in the label, e.g. "Night Raid  Lv.3"
                _lvl = _safe_int(_info.get('skin_level'), 0)
                if _lvl > 0:
                    skin_name = '%s  Lv.%d' % (skin_name, _lvl)
                lines.append("S|%d|%d|%s" % (equip_id, idx, skin_name))
        # v8.19: the "every other named equip" W| loop is GONE. It
        # fed the menu one W| line per discovered equip (the whole
        # equip table - event items, grenades, utilities, merged
        # melee slots...), and the C++ W| handler ADDS every unknown
        # id to the weapon order with a default AR category - that
        # is exactly the "PayPal / melee / grenade rows in the AR
        # tab" report. The menu shows ONLY WEP weapons (the static
        # table + future real guns appended through C|).
        # v8.20 EXCEPTION: the merged melee slots 97/107/141 get
        # their own W|+S| rows - they are real guns in the static
        # table now, and the C++ only fills names/skins from these
        # lines (the rows themselves come from the static table,
        # so no AR-tab pollution is possible).
        for equip_id, entries in (globals().get('WEP_MERGED_DISPLAY') or {}).items():
            weapon_display = _display_text(entries[0], str(equip_id))
            lines.append("W|%d|%s" % (equip_id, weapon_display))
            for idx, skin_id in enumerate(entries[1:], start=1):
                _info = WEP_SKIN_INFO.get(skin_id) or {}
                skin_name = _display_text(_info.get('name') or str(skin_id),
                                          str(skin_id))
                _lvl = _safe_int(_info.get('skin_level'), 0)
                if _lvl > 0:
                    skin_name = '%s  Lv.%d' % (skin_name, _lvl)
                lines.append("S|%d|%d|%s" % (equip_id, idx, skin_name))
        lines.append("END")
        return ("\n".join(lines) + "\n")

    def _send_skin_info_loop():
        # v2.7.1 freeze fix. v2.7 still rebuilt the whole weapon catalog
        # on a 5 s retry (each retry scans the 64k-row lobby table) and
        # rebuilt the line payload every 2-15 s, holding the GIL on the
        # game thread. Now: rebuild only while the catalog is pending
        # (exponential backoff, capped at 60 s) or when late enrichment
        # reports a real change; otherwise resend the cached text as a
        # 30 s keepalive.
        n = 0
        next_try = 0.0
        _lobby_rebuild24 = [False]
        retry_gap = 5.0
        next_late_enrich = 0.0
        late_enrich_attempts = 0
        last_payload_hash = None
        last_sent = 0.0
        cached_payload = None
        dirty = True
        while True:
            try:
                now = time.time()
                if not _weapon_catalog_ready[0] and now >= next_try:
                    if _try_build_weapon_catalog('retry'):
                        dirty = True
                        retry_gap = 5.0
                    else:
                        retry_gap = min(retry_gap * 2.0, 60.0)
                    next_try = now + retry_gap
                if _weapon_catalog_ready[0] and now >= next_late_enrich and late_enrich_attempts < 3:
                    if _count_cjk_weapon_names() > 0 or len(SKIN_TO_ITEM) < max(1, len(WEP_SKIN_INFO) // 2):
                        if _enrich_weapon_names_late('sender', allow_gunskinutil=False):
                            dirty = True
                        late_enrich_attempts += 1
                    next_late_enrich = now + 30.0
                # v2.124: twin-dissolve evidence hooks (evo-after-inspect)
                try:
                    install_twin_hooks()
                except Exception:
                    pass
                # v2.124: the catalog's lobby-recovery pass can only link
                # lobby items when the split lobby tables are already
                # populated - on device they arrive AFTER the first build
                # (log: "lobby_scanned=0 lobby_links=0 recovered=0"). When
                # the tables show up later and the build has zero links,
                # rebuild ONCE so the recovery/resolver passes run against
                # real data (the "missing guns/skins" complaint).
                if (_weapon_catalog_ready[0] and not _lobby_rebuild24[0]
                        and not SKIN_TO_ITEM):
                    try:
                        _lid24 = sys.modules.get('gclient.data.lobby_item_data')
                        _lgs24 = sys.modules.get(
                            'gclient.data.lobby_gun_skin_item_data')
                        _ready24 = False
                        for _m24 in (_lid24, _lgs24):
                            _d24 = getattr(_m24, 'data', None) if _m24 else None
                            if _d24:
                                try:
                                    _ready24 = _ready24 or bool(
                                        next(iter(_d24.keys()), None))
                                except Exception:
                                    pass
                        if _ready24:
                            _lobby_rebuild24[0] = True
                            _weapon_catalog_ready[0] = False
                            retry_gap = 5.0
                            next_try = now
                            _plog('[CATALOG] lobby tables arrived with zero '
                                  'links - full rebuild for the recovery pass')
                    except Exception:
                        pass
                # v7.22: a late optic catalog must reach the menu
                if _optic_catalog_dirty[0]:
                    _optic_catalog_dirty[0] = False
                    dirty = True
                if _weapon_catalog_ready[0] and (dirty or cached_payload is None):
                    cached_payload = _build_skin_info_lines()
                    dirty = False
                if _weapon_catalog_ready[0] and cached_payload is not None:
                    payload_hash = hash(cached_payload)
                    # v7.30: no keepalive resends mid-match - change-
                    # triggered sends only.
                    if payload_hash != last_payload_hash or (
                            (now - last_sent) >= 30.0
                            and _hero_scene_stable() != 'match'):
                        _write_udp_chunked(_write_udp_skin, cached_payload)
                        last_payload_hash = payload_hash
                        last_sent = now
            except Exception:
                pass
            n += 1
            time.sleep(2 if not _weapon_catalog_ready[0] else 10)

    if not _ALREADY_LOADED:
        threading.Thread(target=_send_skin_info_loop, daemon=True).start()
        _plog('[BOOT] weapon sender started')

    try:
        from gclient.gameplay.uicomponents.hud_killrecord_comp import HudKillRecordComp, HudKillRecordCompPC, HudKillRecordCompV2




        def _get_weapon_case_from_info(ca, info):
            if not ca or info is None:
                return None
            try:
                wguid = _mapping_get(info, 'weapon_guid', None) or _mapping_get(info, 'weapon_id', None)
                if wguid and hasattr(ca, 'GetWeaponCase'):
                    for is_fps in (True, False):
                        try:
                            wc = ca.GetWeaponCase(wguid, is_fps_weapon=is_fps)
                        except TypeError:
                            try:
                                wc = ca.GetWeaponCase(wguid, is_fps)
                            except Exception:
                                wc = None
                        except Exception:
                            wc = None
                        if wc:
                            return wc
                    return ca.GetWeaponCase(wguid)
            except Exception:
                pass
            return None


        def _get_skin_data(skin_id):
            template = None
            feature = None
            item_id = SKIN_TO_ITEM.get(skin_id)
            try:
                from gclient.data import gun_skin_template_data
                data = getattr(gun_skin_template_data, 'data', None)
                template = _data_get(data, skin_id)
            except Exception:
                pass
            try:
                from gclient.data import item_feature_data
                data = getattr(item_feature_data, 'data', None)
                for _key in (item_id, skin_id):
                    if not _key:
                        continue
                    value = _data_get(data, _key)
                    if value is not None:
                        feature = value
                        break
            except Exception:
                pass
            return template, feature

        def _copy_skin_kill_broadcast_data(info, skin_id):
            if info is None or not skin_id:
                return
            template_id = ITEM_TO_SKIN.get(skin_id, skin_id)
            item_id = SKIN_TO_ITEM.get(template_id) or (WEP_SKIN_INFO.get(template_id) or {}).get('lobby_item_id') or template_id
            template, feature = _get_skin_data(template_id)
            # ---- v4.8: restored to the 14 MB original -----------------
            # The original assigned the SKIN id to all four keys:
            #     info['guise_id']          = skin_id
            #     info['guise_item_id']     = skin_id
            #     info['guise_template_id'] = skin_id
            #     info['hud_kill_ui']       = skin_id
            # v4.x remapped guise_item_id / skin_item_id / hud_kill_ui to the
            # LOBBY ITEM id. Those are two different namespaces (template vs
            # item) and the kill-HUD lookup walks the guise namespace, so the
            # remap pointed it at an id it has no kill animation for. That is
            # why the kill animation regressed after the original build.
            # ------------------------------------------------------------
            _mapping_set(info, 'guise_id', template_id)
            _mapping_set(info, 'guise_template_id', template_id)
            _mapping_set(info, 'guise_item_id', template_id)
            _mapping_set(info, 'hud_kill_ui', template_id)
            _mapping_set(info, 'skin_id', template_id)
            _mapping_set(info, 'skin_item_id', item_id)
            # Official KillPushAsidePanel.Push passes guise_item_id directly
            # to GetKillHudConfigForGameplay, whose item_feature_data and
            # lobby_item_data lookups require the authentic lobby item ID.
            # Keep the established template namespace for gun records, but
            # correct an active native melee record at this shared boundary.
            try:
                melee_record_fields = globals().get(
                    'melee_kill_record_fields')
                if callable(melee_record_fields):
                    melee_record_fields(info, template_id)
            except Exception:
                pass
            prefixes = ('kill', 'broadcast', 'racer')
            exact_keys = {
                'kill_tip_icon', 'kill_tip_icon_replace', 'kill_icon', 'kill_icon_replace',
                'kill_fx', 'kill_fx_id', 'kill_effect', 'kill_effect_id', 'kill_effect_type',
                'kill_avatar_effect', 'kill_avatar_effect_id', 'kill_avatar_effect_id_replace',
                'kill_racer_effect', 'kill_racer_effect_id', 'kill_racer_effect_id_replace',
                'kill_broadcast', 'kill_broadcast_id', 'kill_broadcast_id_replace',
                'broadcast_effect', 'broadcast_effect_id', 'broadcast_effect_id_replace',
                'racer_effect', 'racer_effect_id', 'kill_mat', 'Team_kill_mat',
            }
            sources = [template, feature, SKIN_LOBBY_PROTO.get(template_id)]
            skin_info = WEP_SKIN_INFO.get(template_id) or {}
            raw = skin_info.get('raw_effect_fields') or {}
            if raw:
                sources.append(raw)
            for source in sources:
                if source is None:
                    continue
                for key, value in _data_items(source):
                    if value is None:
                        continue
                    key_text = str(key)
                    lower = key_text.lower()
                    if key_text in exact_keys or lower.startswith(prefixes):
                        _mapping_set(info, key, value)
            for key in ('kill_mat', 'team_kill_mat', 'kill_mat_start_time', 'team_kill_mat_start_time', 'kill_tip_icon_replace'):
                if skin_info.get(key) is not None:
                    _mapping_set(info, key, skin_info.get(key))
            _has_kill_data = any(
                _mapping_get(info, _k, None) not in (None, False, 0, '')
                for _k in ('kill_mat', 'Team_kill_mat', 'team_kill_mat', 'kill_fx', 'kill_fx_id',
                           'kill_effect_id', 'kill_avatar_effect', 'kill_tip_icon_replace'))
            if _has_kill_data:
                _mapping_set(info, 'kill_effect', True)
            # v4.8: kill_effect is set UNCONDITIONALLY, as the 14 MB
            # original's PlaySkinDead* hooks did. v4.x gated it on
            # _has_kill_data (the skin's kill_mat / kill_fx / kill_effect_id
            # fields), which the device probe proved are all None for forced
            # skins - so the flag was never set and the death FX had nothing
            # to play. The richer keys collected above stay; they add detail
            # when the skin does carry them.
            _mapping_set(info, 'kill_effect', True)
            icon = _proto_get(template, 'kill_tip_icon_replace') or _proto_get(template, 'kill_tip_icon') or _proto_get(template, 'kill_icon_replace') or _proto_get(template, 'kill_icon') or skin_info.get('kill_tip_icon_replace')
            if icon:
                _mapping_set(info, 'weapon_icon', icon)
                _mapping_set(info, 'kill_tip_icon', icon)

        _force_kill_hud_skin = [None]

        def _install_kill_feed(cls):
            try:
                if cls is None:
                    return
                backup = '_actual_skin_original_push_kill_record'
                if hasattr(cls, backup):
                    return
                original_push = getattr(cls, 'PushKillRecord', None)
                if not callable(original_push):
                    return
                setattr(cls, backup, original_push)

                def PushKillRecordWithActualSkin(self, info, *args, **kwargs):
                    is_my_kill = False
                    forced_skin = 0
                    try:
                        if info is not None and sync_attrs.get('bSkinHack', False):
                            ca = None
                            _get_local = globals().get('_local_combat_avatar')
                            if callable(_get_local):
                                ca = _get_local()
                            if ca is None:
                                sp = getattr(Space, '_instance', None)
                                owner = getattr(sp, 'owner', None) if sp else None
                                ca = getattr(owner, 'combat_avatar', None) if owner else None
                            my_ids = set()
                            if ca is not None:
                                for attr in ('id', 'entity_id', 'guid', 'entityid'):
                                    value = getattr(ca, attr, None)
                                    if value is not None:
                                        my_ids.add(value)
                                        my_ids.add(str(value))
                            caster_value = None
                            for key in ('caster_id', 'killer_id', 'attacker_id', 'source_id', 'owner_id', 'caster', 'killer'):
                                caster_value = _mapping_get(info, key, None)
                                if caster_value is not None:
                                    break
                            weapon_guid = _mapping_get(info, 'weapon_guid', None)
                            current_guid = None
                            try:
                                current_weapon = ca.GetCurWeapon() if ca is not None else None
                                current_guid = getattr(current_weapon, 'guid', None)
                            except Exception:
                                pass
                            is_mine = (
                                (caster_value is not None and (caster_value in my_ids or str(caster_value) in my_ids)) or
                                (weapon_guid is not None and current_guid is not None and str(weapon_guid) == str(current_guid))
                            )
                            _weaponfx_log_once(
                                'pushkill-first',
                                '[WEAPONFX] PushKillRecord first keys=%r caster=%r my_ids=%r weapon_guid=%r current_guid=%r mine=%s'
                                % (_mapping_keys(info), caster_value, list(my_ids)[:6], weapon_guid, current_guid, is_mine))
                            if is_mine:
                                skin_id, _wc = _get_kill_skin(info)
                                if skin_id:
                                    template_id = ITEM_TO_SKIN.get(skin_id, skin_id)
                                    trace_v841 = globals().get('kill_record_trace')
                                    if callable(trace_v841):
                                        trace_v841(info, template_id, 'before-copy')
                                    _copy_skin_kill_broadcast_data(info, template_id)
                                    if callable(trace_v841):
                                        trace_v841(info, template_id, 'after-copy')
                                    _force_kill_hud_skin[0] = SKIN_TO_ITEM.get(template_id) or template_id
                                    # v8.41: seed real kill_hud_* fields from
                                    # the game's own config when available.
                                    try:
                                        enrich_v841 = globals().get('enrich_kill_config')
                                        if callable(enrich_v841):
                                            enrich_v841(info, template_id)
                                    except Exception:
                                        pass
                                    if callable(trace_v841):
                                        trace_v841(info, template_id, 'after-seed')
                                    forced_skin = template_id
                                    is_my_kill = True
                                    _weaponfx_log_once(
                                        ('pushkill-skin', template_id),
                                        '[WEAPONFX] kill notification enriched skin=%s item=%s keys=%r'
                                        % (template_id, _force_kill_hud_skin[0], _mapping_keys(info)))
                                    # v7.22: the kill broadcast's own
                                    # evidence line - what the HUD record
                                    # carries AFTER the skin enrichment.
                                    try:
                                        _kbc = {k: _mapping_get(info, k, None)
                                                for k in ('guise_id', 'guise_item_id',
                                                          'hud_kill_ui', 'kill_effect',
                                                          'kill_mat', 'kill_tip_icon_replace',
                                                          'kill_avatar_effect', 'kill_fx', 'kill_fx_id',
                                                          'kill_hud_id', 'kill_hud_csb_path',
                                                          'kill_hud_vx_node')}
                                        _kbc_n = _safe_int(
                                            globals().get('_kill_state', {}).get('events', 0)
                                            if isinstance(globals().get('_kill_state'), dict)
                                            else 0, 0) + 1
                                        if isinstance(globals().get('_kill_state'), dict):
                                            _kill_state['events'] = _kbc_n
                                        # v7.30R20: first 3 + every 25th - a
                                        # full hud_record %r per kill was pure
                                        # log weight in fights (R19 device log
                                        # printed one per kill).
                                        if _kbc_n <= 3 or _kbc_n % 25 == 0:
                                            _plog('[KILLBC] #%d skin=%s hud_record=%r'
                                                  % (_kbc_n, template_id, _kbc))
                                    except Exception:
                                        pass
                    except Exception as e:
                        _weaponfx_log_once(('pushkill-error', repr(e)), '[WEAPONFX] PushKillRecord hook error=%r' % (e,))
                    try:
                        return original_push(self, info, *args, **kwargs)
                    finally:
                        if is_my_kill:
                            _force_kill_hud_skin[0] = None

                setattr(cls, 'PushKillRecord', PushKillRecordWithActualSkin)
            except Exception:
                pass

        _install_kill_feed(HudKillRecordComp)
        _install_kill_feed(HudKillRecordCompPC)
        _install_kill_feed(HudKillRecordCompV2)

        try:
            import gclient.gameplay.uicomponents.hud_killrecord_comp as hkrc_mod
            if not hasattr(hkrc_mod, '_orig_GetKillHudConfigForGameplay'):
                hkrc_mod._orig_GetKillHudConfigForGameplay = hkrc_mod.GetKillHudConfigForGameplay

                def _hooked_GetKillHudConfigForGameplay(guise_item_id, *args, **kwargs):
                    use_id = guise_item_id
                    forced = _force_kill_hud_skin[0]
                    if forced:
                        use_id = forced
                    return hkrc_mod._orig_GetKillHudConfigForGameplay(use_id, *args, **kwargs)

                hkrc_mod.GetKillHudConfigForGameplay = _hooked_GetKillHudConfigForGameplay
        except Exception as e:
            pass

    except Exception as e:
        pass

    try:
        from gclient.gameplay.logic_base.models.avatar_model import AvatarModel
        _optional_skin_selection = {}

        def _get_active_guise_id(info):
            try:
                sp = getattr(Space, '_instance', None)
                if not sp:
                    return None
                lo = getattr(sp, 'owner', None)
                ca = getattr(lo, 'combat_avatar', None) if lo else None
                if not ca:
                    return None
                try:
                    cur_weapon = ca.GetCurWeapon() if hasattr(ca, 'GetCurWeapon') else None
                    if cur_weapon:
                        wid = getattr(cur_weapon, 'weapon_id', None) or getattr(cur_weapon, 'equip_id', None)
                        if wid:
                            skin = _optional_skin_selection.get(wid, 0)
                            if skin:
                                return skin
                            try:
                                selected = _get_forced_weapon_skin(wid)
                                if selected:
                                    return selected
                            except Exception:
                                pass
                except Exception:
                    pass
                try:
                    wguid = info.get('weapon_guid') if isinstance(info, dict) else None
                    if wguid and hasattr(ca, 'GetWeaponCase'):
                        wc = ca.GetWeaponCase(wguid)
                        if wc:
                            guise_id = getattr(wc, 'guise_id', None) or getattr(wc, 'guise_item_id', None) or wc.__dict__.get('guise_id') or wc.__dict__.get('guise_item_id')
                            if guise_id:
                                return guise_id
                            wid = getattr(wc, 'weapon_id', 0)
                            if wid:
                                skin = _optional_skin_selection.get(wid, 0)
                                if skin:
                                    return skin
                except Exception:
                    pass
                try:
                    if hasattr(ca, 'weapon_cases') and ca.weapon_cases:
                        for wc in ca.weapon_cases.values():
                            guise_id = getattr(wc, 'guise_id', None) or getattr(wc, 'guise_item_id', None) or wc.__dict__.get('guise_id') or wc.__dict__.get('guise_item_id')
                            if guise_id:
                                return guise_id
                            wid = getattr(wc, 'weapon_id', 0)
                            if wid:
                                skin = _optional_skin_selection.get(wid, 0)
                                if skin:
                                    return skin
                except Exception:
                    pass
            except Exception:
                pass
            return None

        def _ensure_kill_effect_data(guise_id):
            # ------------------------------------------------------------
            # v4.8: restored to the 14 MB original's behaviour.
            #
            # The original CREATED the feature/template records when the skin
            # had none, which is the normal case for the skins this hack
            # forces (they are not owned, so the client never materialised
            # their rows). v4.x only patched records that already existed
            # ("if record is not None"), so for exactly those skins this was
            # a no-op and the kill animation had nothing to read.
            #
            # Now: create-if-missing AND patch-if-present, under both ID
            # namespaces, with the original's exact seed dict.
            # ------------------------------------------------------------
            if not guise_id:
                return
            template_id = ITEM_TO_SKIN.get(guise_id, guise_id)
            item_id = SKIN_TO_ITEM.get(template_id) or (WEP_SKIN_INFO.get(template_id) or {}).get('lobby_item_id') or template_id
            keys = []
            for _k in (guise_id, template_id, item_id):
                if _k and _k not in keys:
                    keys.append(_k)
            try:
                from gclient.data import item_feature_data
                data = getattr(item_feature_data, 'data', None)
                if data is not None:
                    for key in keys:
                        record = _data_get(data, key, None)
                        if record is None:
                            # original: create an empty record then set the flag
                            try:
                                if hasattr(data, '__setitem__'):
                                    data[key] = {}
                                    record = _data_get(data, key, None)
                            except Exception:
                                record = None
                        if record is not None:
                            _mapping_set(record, 'kill_effect', True)
            except Exception:
                pass
            try:
                from gclient.data import gun_skin_template_data
                data = getattr(gun_skin_template_data, 'data', None)
                if data is not None:
                    for key in keys:
                        record = _data_get(data, key, None)
                        if record is None:
                            try:
                                if hasattr(data, '__setitem__'):
                                    data[key] = {
                                        'dlc_id': None,
                                        'kill_fx': True,
                                        'die_action_attach_model_id': None,
                                        'die_action_attach_model_time': 0.0,
                                        'die_action_disappear_time': 0.0,
                                        'SpecialDieActionPose': None,
                                    }
                                    record = _data_get(data, key, None)
                            except Exception:
                                record = None
                        if record is not None and _proto_get(record, 'kill_fx', None) is None:
                            _mapping_set(record, 'kill_fx', True)
            except Exception:
                pass

        @HOOK(AvatarModel, bLog=False)
        def PlaySkinDeadAnimAndEffect(self, info, *args, **kwargs):
            try:
                if sync_attrs.get('bSkinHack', False):
                    guise_id = _get_active_guise_id(info)
                    if guise_id:
                        _ensure_kill_effect_data(guise_id)
                        try:
                            owner = getattr(self, 'owner', None)
                            if owner and hasattr(owner, 'final_kill_info'):
                                import _pickle as cPickle
                                raw_fki = owner.final_kill_info
                                if raw_fki:
                                    fki = cPickle.loads(raw_fki)
                                    if isinstance(fki, dict):
                                        _copy_skin_kill_broadcast_data(fki, guise_id)
                                        owner.final_kill_info = cPickle.dumps(fki)
                        except Exception:
                            pass
                        _copy_skin_kill_broadcast_data(info, guise_id)
            except Exception:
                pass
            return self._PlaySkinDeadAnimAndEffect(info, *args, **kwargs)

        @HOOK(AvatarModel, bLog=False)
        def PlaySkinDeadEffect(self, sfx_info, material, time_offset, info, *args, **kwargs):
            try:
                if sync_attrs.get('bSkinHack', False):
                    guise_id = _get_active_guise_id(info)
                    if guise_id:
                        _ensure_kill_effect_data(guise_id)
                        _copy_skin_kill_broadcast_data(info, guise_id)
            except Exception:
                pass
            try:
                if sync_attrs.get('bSkinHack', False):
                    guise_id = _get_active_guise_id(info)
                    if guise_id:
                        _weaponfx_log_once(
                            ('dead-effect', guise_id),
                            '[WEAPONFX] PlaySkinDeadEffect skin=%s material=%r info_keys=%r args=%r kwargs=%r'
                            % (guise_id, material, _mapping_keys(info), args, list(kwargs.keys())))
            except Exception:
                pass
            return self._PlaySkinDeadEffect(sfx_info, material, time_offset, info, *args, **kwargs)

    except Exception:
        pass

except Exception:
    if not WEP:
        WEP = {1: ['M4A1', 11100002]}
        WEP_NAMES = {1: 'M4A1'}

# ============================================================
# WEAPONFX v2.6 - apply the selected skin's tracer / hit /
# scope-optic / kill data to live WeaponCase objects.
# v2.5 only post-processed EquipCaseFactory.Create results and
# called several refresh names that are not in the game stubs.
# ============================================================

_weaponfx_applied = {}
_weaponfx_logged = set()
_weaponfx_tick = [0]
_weaponfx_effect_hooks_installed = [False]
_weaponfx_effect_hook_attempts = [0]

def _weaponfx_log_once(key, message):
    try:
        if key in _weaponfx_logged:
            return
        _weaponfx_logged.add(key)
        _plog(message)
    except Exception:
        pass

def _mapping_get(mapping, key, default=None):
    return _proto_get(mapping, key, default)

def _mapping_set(mapping, key, value):
    if mapping is None:
        return False
    try:
        mapping[key] = value
        return True
    except Exception:
        pass
    try:
        setter = getattr(mapping, 'setdefault', None)
        if callable(setter):
            setter(key, value)
            return True
    except Exception:
        pass
    try:
        setattr(mapping, str(key), value)
        return True
    except Exception:
        return False

def _mapping_keys(mapping, limit=40):
    try:
        return [str(k) for k, _v in _data_items(mapping)[:limit]]
    except Exception:
        return []

def _set_case_attr(case, name, value):
    if case is None or value is None:
        return False
    try:
        setattr(case, name, value)
        return True
    except Exception:
        pass
    try:
        data = getattr(case, '__dict__', None)
        if data is not None and hasattr(data, '__setitem__'):
            data[name] = value
            return True
    except Exception:
        pass
    return False

def _call_case_method(case, method_name, args=(), kwargs=None, called=None, errors=None):
    if kwargs is None:
        kwargs = {}
    try:
        fn = getattr(case, method_name, None)
        if not callable(fn):
            return False
        fn(*args, **kwargs)
        if called is not None:
            called.append(method_name)
        return True
    except Exception as e:
        if errors is not None:
            errors.append('%s=%r' % (method_name, e))
        return False

def _skin_raw_field(skin_info, *keys):
    if not skin_info:
        return None
    raw = skin_info.get('raw_effect_fields') or {}
    for key in keys:
        value = skin_info.get(key)
        if value is not None:
            return value
        value = raw.get(key)
        if value is not None:
            return value
    lower_map = {}
    try:
        for key, value in raw.items():
            lower_map.setdefault(str(key).lower(), value)
    except Exception:
        pass
    for key in keys:
        value = lower_map.get(str(key).lower())
        if value is not None:
            return value
    return None

def _resolve_skin_optic_id(equip_id, template_id, item_id, case=None):
    skin_info = WEP_SKIN_INFO.get(template_id) or {}
    optic_id = _skin_raw_field(
        skin_info, 'skin_optic_id', 'optic_id', 'reticle_id',
        'reticle_template_id', 'skin_optic_part_id')
    if optic_id:
        return optic_id

    lobby_proto = SKIN_LOBBY_PROTO.get(template_id)
    for key in ('skin_optic_id', 'optic_id', 'reticle_id', 'reticle_template_id'):
        value = _proto_get(lobby_proto, key, None)
        if value:
            return value

    try:
        gun_skin_util = _import_module('gclient.util.gun_skin_util')
        for fn_name, arg in (
            ('GetGunOpticGuiseOpticIdByGuise', template_id),
            ('GetGunOpticGuiseOpticIdByItem', item_id),
        ):
            if not arg:
                continue
            fn = getattr(gun_skin_util, fn_name, None)
            if callable(fn):
                value = fn(arg)
                if value:
                    return value
    except Exception:
        pass

    # WeaponCase component resolver needs the currently equipped optic
    # guise item + part. Try only when the case exposes those values.
    try:
        fn = getattr(case, 'GetSkinOpticIdByOpticItemId', None)
        if callable(fn) and item_id:
            part_id = None
            for attr in ('cur_optic_part_id', 'optic_part_id', 'skin_optic_part_id'):
                part_id = getattr(case, attr, None)
                if part_id:
                    break
            if part_id:
                value = fn(item_id, part_id)
                if value:
                    return value
    except Exception:
        pass

    try:
        optic_mod = _import_module('gclient.data.gun_skin_optic_data')
        data = getattr(optic_mod, 'data', None)
        for key in (template_id, item_id):
            record = _data_get(data, key, None)
            if record is not None:
                value = _proto_get(record, 'skin_optic_id', None) or _proto_get(record, 'optic_id', None) or _proto_get(record, 'id', None)
                if value:
                    return value
        # Bounded reverse scan, cached by the caller's applied-map.
        for record_id, record in _data_items(data):
            for _key, _value in _data_items(record):
                if _safe_int(_value, 0) in (template_id, item_id):
                    value = _proto_get(record, 'skin_optic_id', None) or _proto_get(record, 'optic_id', None) or record_id
                    if value:
                        return value
    except Exception:
        pass
    return None

mat_healed = set()
dlc_tried = set()
dlc_probed = [False]


def heal_skin_row(skin_id):
    """v8.15: the game arrow/missile loader (arrow.py
    LoadModelSkin) indexes gun-skin template rows directly. The
    v8.14 device crashed 46x with KeyError(gun_skin_part_mat_list)
    on rows that ship gun_skin_part_model_list but no mat list.
    Fill the missing key on the forced skin row - donor = another
    row of the same gun that carries it, else zeros matching the
    model list - so the game read succeeds. Once per skin."""
    try:
        skin_id = _safe_int(skin_id, 0)
        if not skin_id or skin_id in mat_healed:
            return
        mat_healed.add(skin_id)
        _healed = []
        for _mod_name in ('gclient.data.gun_skin_template_data',
                          'gclient.data.gun_skin_template_base_data'):
            _mod = sys.modules.get(_mod_name)
            _data = getattr(_mod, 'data', None) \
                if _mod is not None else None
            if _data is None:
                continue
            _row = _data_get(_data, skin_id, None)
            if _row is None:
                continue
            try:
                if _row.get('gun_skin_part_mat_list') is not None:
                    continue
            except Exception:
                pass
            _donor = None
            try:
                _own_gun = _proto_get(_row, 'gun_id', None)
                if _own_gun:
                    _own_gun = _safe_int(_own_gun, 0)
                    for _sid2, _row2 in _data_items(_data):
                        if (_safe_int(
                                _proto_get(_row2, 'gun_id', 0), 0)
                                == _own_gun
                                and _proto_get(
                                    _row2, 'gun_skin_part_mat_list',
                                    None) is not None):
                            _donor = _proto_get(
                                _row2, 'gun_skin_part_mat_list', None)
                            break
            except Exception:
                _donor = None
            if _donor is None:
                try:
                    _ml = _proto_get(_row,
                                     'gun_skin_part_model_list', None)
                    _donor = (0,) * (len(_ml) if _ml else 0)
                except Exception:
                    _donor = ()
            try:
                _row['gun_skin_part_mat_list'] = _donor
                _healed.append('%s:%r' % (
                    _mod_name.rsplit('.', 1)[-1],
                    _donor if not isinstance(_donor, tuple) else (
                        'len%d' % (len(_donor),))))
            except Exception:
                pass
        if _healed:
            _plog('[V815] healed template row skin=%s %r'
                  % (skin_id, _healed))
    except Exception:
        pass


# #======================================================================
# //  WEAPON.PY
# //
# //  This file is for: WEAPON / DLC: the download queue + AutoDownloadItem fetches (melee-anywhere, others lobby-only), the weapon-case skin apply (ChangeWeaponSkin/ChangeWeaponGuise chain), the WEAPONFX rebuild pump, the ballistic/hit effect hooks.
# //
# //  Part of the split TREACKY BS payload (v2.112).  The runtime
# //  file payload/skins_payload.py is GENERATED: run
# //  tools/build_payload.py after editing these modules.
# #======================================================================
