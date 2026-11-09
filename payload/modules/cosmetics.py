# ============================================================
# COSMETICS.PY (payload feature module)
# PROVIDES: melee_log_key, _v109_log, _v109_int, _v109_signature, category_enabled, any_enabled, report_config, _v109_row, _v109_field, _v109_enum, subtype_name, main_supported, _v109_main_name, melee_equip, ... +49 more | NATIVE_CATEGORIES, ACTIVE_LOCAL_RPCS, MASTER_KEY, CATEGORY_KEYS, CATEGORY_KEY_MAP, SUBTYPE_CATEGORIES, BATCH_SIZE, STRIKER_RETRY_LIMIT, STRIKER_RETRY_DELAY, BATCH_SECONDS, ...
# REQUIRES: shared namespace (config/names/main/game_api/catalog);
#           game modules imported inline, verified against the dumps.
# Feature module - see REWRITE_PLAN.md S1.
# ============================================================
"""Cosmetic category resolution + pick persistence: category enable gates, remembered picks (ArmHeroSkin/ArmSkin...), equip-window apply helpers."""

# #======================================================================
# //  COSMETICS.PY
# //
# //  This file is for: COSMETIC CATEGORIES + PERSISTENCE: the category resolution (_v109_category), the local-equip slot map, the pick persistence (config json), the saver + restore (restore_striker_picks), the melee equip pick.
# //
# //  Part of the split TREACKY BS payload (v2.112).  The runtime
# //  file payload/skins_payload.py is GENERATED: run
# //  tools/build_payload.py after editing these modules.
# #======================================================================
NATIVE_CATEGORIES = frozenset((
    'weapon', 'melee', 'playpal', 'striker',
    'emote', 'vehicle', 'profile', 'other',
))
# Only RPCs with a scoped local equip/readback contract are active.  An
# injected GUID/item is never sent to a server equip RPC; unmapped shapes fail
# closed and genuine rows always retain the original server path.
ACTIVE_LOCAL_RPCS = frozenset((
    'ArmHeroEmo', 'ApplyMelee', 'ApplyPanpan', 'PanpanHallPlaying',
    'ArmGunSkin', 'ArmGunGuise',
    'ArmHeroSkin', 'ArmLowLevelSkin', 'ArmSkinExecuteItem',
    'ArmDisplayItem', 'ArmHeroTransform', 'SetHeroSkinEffectShow',
    'SetHeroSkinSlideEffectVisibility',
    # v10.12.1: these consumers already have scoped native field/readback
    # contracts below.  Keeping them in the broader dormant set only discarded
    # the user's click (notably aircraft/parachute/skydive and vehicles).
    'ArmVehicleSkin', 'ArmSkyBox', 'ArmBombSkin', 'ArmMedicineSkin',
    'ApplyDeathBoxSkin', 'SetAircraftSkin', 'SetParachuteSkin',
    'SetSkydiveSkin', 'ApplyTrailingSkin', 'SetAirDropItem',
    'SetVoicePackage', 'ArmBanner', 'ArmHallBackground', 'ArmHallMusic',
    'SetNameFrame', 'ChangeHeadFrame', 'ChangeCardBackground',
    'ChangeHomepageBackground', 'UseChatBubbles',
))
MASTER_KEY = 'bUnlockAllVault'
CATEGORY_KEYS = (
    ('weapon', 'bCosmeticUnlockWeapons'),
    ('melee', 'bUnlockMelee'),
    ('playpal', 'bCosmeticUnlockPlayPal'),
    ('striker', 'bUnlockHeroes'),
    ('emote', 'bEmoteHack'),
    ('vehicle', 'bCosmeticUnlockVehicles'),
    ('profile', 'bCosmeticUnlockProfile'),
    ('other', 'bCosmeticUnlockOther'),
)
CATEGORY_KEY_MAP = dict(CATEGORY_KEYS)
SUBTYPE_CATEGORIES = {
    # Weapon cosmetics. GunPart/OriginGun are gameplay/base items, not skins.
    'GunSkin': 'weapon',
    'GunOpticReticle': 'weapon',
    'GunDiyAnim': 'weapon',
    'Heirloom': 'weapon',             # melee rows are classified first
    # Striker skins, introductions, transformations and executions.
    'Execute': 'striker',
    'AppearanceAni': 'striker',
    'SkinTransformAni': 'striker',
    'Emote': 'emote',
    # v2.113: broadened Collection/consumable name coverage.
    'Skydiving': 'other', 'SkydivingTrail': 'other',
    'ParachuteSkin': 'other', 'Glider': 'other',
    'Throwable': 'other', 'ThrowingWeapon': 'other',
    'Grenade': 'other', 'GrenadeSkin': 'other',
    'MedicineSkin': 'other', 'Medkit': 'other',
    'DeathBoxSkin': 'other', 'AirDropSkin': 'other',
    'LoadoutDropSkin': 'other', 'Aircraft': 'other',
    'Trailing': 'other', 'SkyBox': 'other',
    'Avatar': 'profile', 'PlayerAvatar': 'profile',
    'HeadIcon': 'profile', 'PlayPal': 'playpal',
    'Playpal': 'playpal', 'Pet': 'playpal',
    'Vehicle': 'vehicle', 'Car': 'vehicle',
    # v2.112: Collection + Consumable vault families.
    'Banner': 'profile',
    'HolographicDome': 'other',
    'Holographic': 'other',
    'LootCrate': 'other',
    'LootCrateSkin': 'other',
    'Parachute': 'other',
    'SkydivTrail': 'other',
    'SkydiveTrail': 'other',
    'SkydivingTrail': 'other',
    'Glide': 'other',
    'LoadoutDrop': 'other',
    'AirDrop': 'other',
    'VoicePack': 'other',
    'VoicePackage': 'other',
    'Consumable': 'other',
    'Medicine': 'other',
    'Bandage': 'other',
    'DeathBox': 'other',
    'BombSkin': 'other',
    # Vehicles and sky cosmetics.
    'AircraftSkin': 'vehicle',
    'AllTerrainCar': 'vehicle',
    'Helicopter': 'vehicle',
    'LightTruck': 'vehicle',
    'Motorbike': 'vehicle',
    'NormalCar': 'vehicle',
    'OffRoadCar': 'vehicle',
    'ParachuteSkin': 'vehicle',
    'SkydiveSkin': 'vehicle',
    'AirDrop': 'vehicle',
    # Character, profile and hall cosmetics.
    'Banner': 'profile',
    'Body': 'profile',
    'CardBackground': 'profile',
    'ChatBubbles': 'profile',
    'Hair': 'profile',
    'HallBackground': 'profile',
    'Head': 'profile',
    'HeadFrame': 'profile',
    'HeroAchievementBg': 'profile',
    'HomepageBackground': 'profile',
    'Mask': 'profile',
    'Mustache': 'profile',
    'NameFrame': 'profile',
    'Ornament': 'profile',
    'ProfilePhoto': 'profile',
    'SkyBox': 'profile',
    'Sticker': 'profile',
    'Suit': 'profile',                # hero_skin_id/Striker rows win first
    'UP': 'profile',
    # Remaining cosmetic families.
    'BombSkin': 'other',
    'DeathBox': 'other',
    'MedicineSkin': 'other',
    'Music': 'other',
    'PanPan': 'playpal',
    'Trailing': 'other',
    'VoicePackage': 'other',
    'Watch': 'other',
}
BATCH_SIZE = 4
# Startup restore can run in the same native batch that creates the hero
# detail rows, so a striker equip may legitimately arrive before
# `hero_infos[hero_id]` exists.  Retry a bounded number of times on the native
# timer instead of discarding the saved pick; nothing is written until the
# normal readback gate passes.
STRIKER_RETRY_LIMIT = 8
STRIKER_RETRY_DELAY = 1.5
BATCH_SECONDS = 0.004
TIMER_DELAY = 0.025
MAX_JOBS = 128
MAX_TRACKED = 16384
RETRY_FAILED_SECONDS = 30.0
COSMETIC_RPC_CODES = {
    'ArmGunSkin': 1, 'ArmGunGuise': 2, 'ArmVehicleSkin': 3,
    'ArmSkyBox': 4, 'ArmBombSkin': 5, 'ArmMedicineSkin': 6,
    'ApplyDeathBoxSkin': 7, 'SetAircraftSkin': 8,
    'SetParachuteSkin': 9, 'SetSkydiveSkin': 10,
    'ApplyTrailingSkin': 11, 'SetAirDropItem': 12,
    'SetVoicePackage': 13, 'ArmBanner': 14,
    'ArmHallBackground': 15, 'ArmHallMusic': 16, 'SetNameFrame': 17,
    'ChangeHeadFrame': 18, 'ChangeCardBackground': 19,
    'ChangeHomepageBackground': 20, 'UseChatBubbles': 21,
    'ArmHeroSkin': 22, 'ArmLowLevelSkin': 23,
    'ArmSkinExecuteItem': 24, 'ArmDisplayItem': 25,
    'ArmHeroTransform': 26,
}
STRIKER_PERSIST_RPCS = frozenset((
    'ArmHeroSkin', 'ArmLowLevelSkin', 'ArmSkinExecuteItem',
    'ArmDisplayItem', 'ArmHeroTransform',
))
COSMETIC_CODE_RPCS = {
    code: rpc for rpc, code in COSMETIC_RPC_CODES.items()}
COSMETIC_SAVED = {}
LOCAL_RPCS = frozenset((
    'ApplyMelee', 'ArmVehicleSkin', 'ArmGunSkin', 'ArmGunGuise',
    'ArmHeroSkin', 'ArmLowLevelSkin', 'ArmSkinExecuteItem',
    'ArmDisplayItem', 'ArmHeroTransform', 'SetHeroSkinEffectShow',
    'SetHeroSkinSlideEffectVisibility',
    'ArmHeroEmo', 'ArmSkyBox', 'ApplyPanpan', 'ArmBombSkin',
    'ArmMedicineSkin', 'ApplyDeathBoxSkin', 'SetAircraftSkin',
    'SetParachuteSkin', 'SetSkydiveSkin', 'ApplyTrailingSkin',
    'SetAirDropItem', 'SetVoicePackage', 'ArmBanner', 'ArmHallBackground',
    'ArmHallMusic', 'SetNameFrame', 'ChangeHeadFrame',
    'ChangeCardBackground', 'ChangeHomepageBackground', 'UseChatBubbles',
))

log_seen = {}
# Melee lifecycle evidence has its own bounded budget.  The general 220-key
# cap otherwise fills during saved cosmetic restoration and hides the later
# lobby -> match native melee result, making a running retry look absent.
MELEE_LOG_SEEN = {}
MELEE_LOG_COUNT = [0]
MELEE_LOG_LIMIT = 768
MELEE_LOG_CAP_REPORTED = [False]
subtype_cache = {'enum': None, 'map': {}, 'retry': 0.0}
main_cache = {'enum': None, 'values': set()}
install_seen = set()
install_retry = [0.0]
_v109_state = {'wid': 0, 'token': 0}
menu_status = {'sig': None}
emote_probe_state = {'rpc': 0, 'ui': 0}
# Reference-derived readback fallback; only successful injected equips enter.
EMOTE_SAVED = {}
MELEE_SAVED = {}
PANPAN_SAVED = {}
# Transient hall-wheel playback only; never persisted as an equipment pick.
PANPAN_PLAYING = {}
# One latest click may wait for authentic PlayPal DLC.  Weak ownership,
# cancellation and a hard timeout prevent a delayed click becoming stale.
PANPAN_PLAY_PENDING = {}
PANPAN_PLAY_TICK = [0.0]
PANPAN_PLAY_PENDING_SECONDS = 120.0
# One official ArmLowLevelSkin -> ArmHeroSkin sequence, keyed by owner+owned
# item. Values hold only a weak owner reference and the selected appearance.
# Bounded post-download Home refresh. Entries hold only weak avatar references
# and the still-current injected selection; authentic DLC gates stay decisive.
STRIKER_MODEL_PENDING = {}
STRIKER_MODEL_TICK = [0.0]
STRIKER_MODEL_PENDING_SECONDS = 120.0
# Latest-wins native combat reconciliation after a real post-native hero/suit
# transition. Weak owner references and generations prevent stale completions.
STRIKER_COMBAT_PENDING = {}
STRIKER_COMBAT_GENERATION = [0]
# v10.10.2: official PlayerAvatarMember.ApplyMelee is an RPC-only forwarder.
# Preserve verified readback, but do not mistake its None/no-readback result
# for explicit rejection. PlayerAvatar.CallServer remains a separate object.
# Capture the real member through loaded ownership/receiver methods; never
# scan gc or invent a component attribute.
MELEE_RECEIVER = {'ref': None, 'warehouse': None}
MELEE_RECEIVER_DEPTH = [0]
restore_state = {'at': 0.0, 'key': None, 'done': False, 'attempts': 0}


def melee_log_key(key):
    """Route only high-signal native melee events to the separate budget."""
    try:
        head = key[0] if isinstance(key, tuple) and key else key
        if not isinstance(head, str):
            return False
        return head.startswith(('visual-', 'melee-', 'native-melee-')) or \
            head in ('kill-record-lobby-item', 'kill-avatar-native',
                     'kill-avatar-error')
    except Exception:
        return False


def _v109_log(key, message, limit=2):
    try:
        if melee_log_key(key):
            count = MELEE_LOG_SEEN.get(key, 0)
            if count >= limit:
                return
            if MELEE_LOG_COUNT[0] >= MELEE_LOG_LIMIT:
                if not MELEE_LOG_CAP_REPORTED[0]:
                    MELEE_LOG_CAP_REPORTED[0] = True
                    _plog('[CUNLOCK] native melee diagnostic budget exhausted; '
                          'further per-key outcomes suppressed')
                return
            MELEE_LOG_SEEN[key] = count + 1
            MELEE_LOG_COUNT[0] += 1
        else:
            count = log_seen.get(key, 0)
            if count >= limit:
                return
            if len(log_seen) >= 220 and key not in log_seen:
                return
            log_seen[key] = count + 1
        _plog('[CUNLOCK] %s' % message)
    except Exception:
        pass


def _v109_int(value, default=0):
    try:
        if isinstance(value, bool):
            return default
        return int(value)
    except Exception:
        try:
            return int(value.value)
        except Exception:
            return default


def _v109_signature():
    # Include every controlled category so each OFF edge performs its own
    # native cleanup.  This is independent of the retired broad bUnlockAll.
    return tuple([bool(sync_attrs.get(MASTER_KEY, False))] +
                 [bool(sync_attrs.get(key, False))
                  for _category, key in CATEGORY_KEYS])


def category_enabled(category):
    try:
        if category not in NATIVE_CATEGORIES:
            return False
        if sync_attrs.get(MASTER_KEY, False):
            return True
        key = CATEGORY_KEY_MAP.get(category)
        return bool(key and sync_attrs.get(key, False))
    except Exception:
        return False


def any_enabled():
    try:
        if sync_attrs.get(MASTER_KEY, False):
            return True
        return any(sync_attrs.get(key, False)
                   for _category, key in CATEGORY_KEYS)
    except Exception:
        return False


def report_config():
    """Bounded menu-to-payload edge diagnostic; no work on unchanged ticks."""
    try:
        signature = _v109_signature()
        if menu_status.get('sig') == signature:
            return False
        menu_status['sig'] = signature
        selected = [category for category, key in CATEGORY_KEYS
                    if sync_attrs.get(key, False)]
        message = 'menu config master=%s categories=%s' % (
            bool(signature[0]), ','.join(selected) or 'none')
        _v109_log(('menu-config', signature), message, 1)
        return True
    except Exception:
        return False


def _v109_row(item_id):
    """Only the authoritative lobby_item_data row is eligible."""
    item_id = _v109_int(item_id, 0)
    if not item_id:
        return None
    try:
        module = sys.modules.get('gclient.data.lobby_item_data')
        data = getattr(module, 'data', None) if module is not None else None
        if data is None:
            return None
        row = data.get(item_id)
        if row is None:
            row = data.get(str(item_id))
        return row
    except Exception:
        return None


def _v109_field(row, key, default=None):
    try:
        helper = globals().get('_v842_field')
        if callable(helper):
            return helper(row, key, default)
    except Exception:
        pass
    try:
        if isinstance(row, dict):
            return row.get(key, default)
        getter = getattr(row, 'get', None)
        if callable(getter):
            value = getter(key, default)
            if value is not None:
                return value
        value = getattr(row, key, default)
        return value() if callable(value) else value
    except Exception:
        return default


def _v109_enum():
    for module_name in ('gshare.consts', 'gshare.ihall_item'):
        try:
            module = sys.modules.get(module_name)
            consts = (getattr(module, 'consts', None)
                      if module_name.endswith('ihall_item') else module)
            enum = getattr(consts, 'ItemSubType', None)
            if enum is not None:
                return enum
        except Exception:
            continue
    return None


def subtype_name(sub_type):
    """Resolve the game's enum values once; never infer from display names."""
    sub_type = _v109_int(sub_type, 0)
    if not sub_type:
        return None
    now = time.time()
    enum = _v109_enum()
    cache = subtype_cache
    if enum is None:
        if now >= cache.get('retry', 0.0):
            cache['retry'] = now + 5.0
            cache['map'] = {}
        return None
    if cache.get('enum') is not enum:
        mapping = {}
        try:
            name_to_values = getattr(enum, 'name_to_values', {}) or {}
        except Exception:
            name_to_values = {}
        for name in SUBTYPE_CATEGORIES:
            value = None
            try:
                value = name_to_values.get(name)
            except Exception:
                pass
            if value is None:
                try:
                    value = getattr(enum, name, None)
                except Exception:
                    value = None
            number = _v109_int(value, 0)
            if number:
                mapping[number] = name
        cache['enum'] = enum
        cache['map'] = mapping
        cache['retry'] = 0.0
        _v109_log(('enum', len(mapping)),
                  'native ItemSubType map resolved=%d' % len(mapping), 1)
    return cache.get('map', {}).get(sub_type)


def main_supported(sub_type):
    """Exclude WarehouseItemType.Item/NoShow and other generic huge indexes."""
    sub_type = _v109_int(sub_type, 0)
    if not sub_type:
        return False
    consts = sys.modules.get('gshare.consts')
    enum = getattr(consts, 'WarehouseItemType', None) if consts else None
    if enum is None:
        try:
            module = sys.modules.get('gshare.ihall_item')
            consts = getattr(module, 'consts', None) if module else None
            enum = getattr(consts, 'WarehouseItemType', None) if consts else None
        except Exception:
            enum = None
    if enum is None:
        return False
    cache = main_cache
    if cache.get('enum') is not enum:
        allowed = set()
        names = ('GunSkin', 'GunGuise', 'MeleeWeapon', 'Vehicle',
                 'Clothes', 'Collection', 'Panpan', 'Heirloom')
        try:
            name_to_values = getattr(enum, 'name_to_values', {}) or {}
        except Exception:
            name_to_values = {}
        for name in names:
            value = name_to_values.get(name)
            if value is None:
                value = getattr(enum, name, None)
            number = _v109_int(value, 0)
            if number:
                allowed.add(number)
        cache['enum'] = enum
        cache['values'] = allowed
    return sub_type in cache.get('values', set())


def _v109_main_name(sub_type):
    """Resolve WarehouseItemType names from the native enum, never guesses."""
    sub_type = _v109_int(sub_type, 0)
    if not sub_type:
        return None
    consts = sys.modules.get('gshare.consts')
    enum = getattr(consts, 'WarehouseItemType', None) if consts else None
    if enum is None:
        try:
            module = sys.modules.get('gshare.ihall_item')
            consts = getattr(module, 'consts', None) if module else None
            enum = getattr(consts, 'WarehouseItemType', None) if consts else None
        except Exception:
            enum = None
    if enum is None:
        return None
    cache = main_cache
    if cache.get('enum') is not enum or 'names' not in cache:
        names = {}
        values = set()
        try:
            name_to_values = getattr(enum, 'name_to_values', {}) or {}
        except Exception:
            name_to_values = {}
        for name, value in name_to_values.items():
            number = _v109_int(value, 0)
            if number:
                names[number] = name
        for name in ('GunSkin', 'GunGuise', 'MeleeWeapon', 'Vehicle',
                     'Clothes', 'Collection', 'Panpan', 'Heirloom'):
            value = name_to_values.get(name)
            if value is None:
                value = getattr(enum, name, None)
            number = _v109_int(value, 0)
            if number:
                names.setdefault(number, name)
                values.add(number)
        cache['enum'] = enum
        cache['names'] = names
        cache['values'] = values
    return cache.get('names', {}).get(sub_type)


def melee_equip(row):
    """Return an authenticated melee equip id, or zero for other rows.

    Prefer the official lobby/template/melee-data chain.  The established
    positive melee catalog then covers authentic base/merged rows whose UI
    subtype is not MeleeWeapon.  Catalog membership alone never admits a row:
    it must also resolve to a non-gun equip.  Spear/gun-only compatibility
    fields remain rejected.
    """
    try:
        item_id = _v109_int(
            _v109_field(row, 'id', 0) or _v109_field(row, 'item_id', 0), 0)
        sub_type = _v109_int(_v109_field(row, 'sub_type', 0), 0)
        main_name = _v109_main_name(sub_type)
        detail_name = subtype_name(sub_type)
        catalog = None
        cataloged = False
        catalog_fn = globals().get('_v841m2_catalog')
        if item_id and callable(catalog_fn):
            try:
                catalog = catalog_fn()
                cataloged = item_id in (catalog.get('items') or set())
            except Exception:
                catalog = None
                cataloged = False
        if (main_name != 'MeleeWeapon' and detail_name != 'Heirloom'
                and not cataloged):
            return 0
        gun_equips = globals().get('WEP_GUN_IDS') or {}
        templates = [_v109_int(_v109_field(row, 'guise', 0), 0)]
        if cataloged:
            templates.append(_v109_int(
                (catalog.get('item_to_template') or {}).get(item_id), 0))
        skin_module = sys.modules.get('gclient.data.gun_skin_template_data')
        skin_data = getattr(skin_module, 'data', None) if skin_module else None
        melee_module = sys.modules.get('gclient.data.melee_weapon_data')
        melee_data = getattr(melee_module, 'data', None) if melee_module else None
        for template_id in templates:
            if not template_id:
                continue
            template = _v109_field(skin_data, template_id, None)
            if template is None:
                continue
            melee_id = _v109_int(_v109_field(template, 'melee_weapon_id', 0), 0)
            if not melee_id:
                continue
            melee = _v109_field(melee_data, melee_id, None)
            if melee is None:
                continue
            equip_id = _v109_int(
                _v109_field(melee, 'replace_equip_id', 0), 0) or \
                _v109_int(_v109_field(melee, 'equip_id', 0), 0)
            if equip_id and equip_id not in gun_equips:
                return equip_id
        if cataloged:
            for equip_id, item_ids in (catalog.get('by_equip') or {}).items():
                equip_id = _v109_int(equip_id, 0)
                if (equip_id and equip_id not in gun_equips
                        and item_id in (item_ids or set())):
                    return equip_id
    except Exception:
        pass
    return 0


def melee_create_id(value):
    """Resolve only authentic melee picker inputs for EquipCaseFactory.Create.

    Adapted from the v8.70 reference's create normalization, but scoped by
    the real lobby/template/melee rows.  Guns, unknown objects and existing
    equip ids retain their original input; no ownership or catalog is changed.
    """
    try:
        melee_ids = globals().get('WEP_MELEE_IDS') or {}
        if isinstance(value, (int, float, str)) and not isinstance(value, bool):
            item_id = _v109_int(value, 0)
            if item_id and item_id not in melee_ids:
                equip_id = melee_equip(_v109_row(item_id))
                if equip_id:
                    return equip_id
            return value
        for field in ('equip_id', 'weapon_id', 'item_id', 'itemId',
                      'itemid', 'id', 'guid'):
            candidate = _v109_int(_v109_field(value, field, 0), 0)
            if not candidate:
                continue
            if candidate in melee_ids:
                return candidate
            equip_id = melee_equip(_v109_row(candidate))
            if equip_id:
                return equip_id
    except Exception:
        pass
    return value


def _v109_is_melee(item_id, row):
    """Only an authentic row with a resolvable native melee equip is melee."""
    if not _v109_int(item_id, 0) or row is None:
        return False
    return bool(melee_equip(row))


def _v109_category(item_id, row=None):
    item_id = _v109_int(item_id, 0)
    if not item_id:
        return None
    row = _v109_row(item_id) if row is None else row
    if row is None:
        return None
    try:
        sub_type = _v109_int(_v109_field(row, 'sub_type', 0), 0)
        main_name = _v109_main_name(sub_type)
        if main_name == 'MeleeWeapon':
            return 'melee' if _v109_is_melee(item_id, row) else None
        if _v109_is_melee(item_id, row):
            return 'melee'
        if main_name in ('GunSkin', 'GunGuise'):
            return 'weapon'
        if main_name == 'Vehicle':
            return 'vehicle'
        short_desc = _v109_field(row, 'short_desc', None)
        hero_skin_id = _v109_field(row, 'hero_skin_id', None)
        name = subtype_name(sub_type)
        # Explicit animation/emote types win even when a row also carries a
        # forced hero_skin_id for its preview/model contract.
        if name in ('Emote', 'Execute', 'AppearanceAni', 'SkinTransformAni'):
            return SUBTYPE_CATEGORIES.get(name)
        if sub_type == 300 or short_desc == 'Striker':
            return 'striker'
        if hero_skin_id is not None and name in (None, 'Suit', 'Body'):
            return 'striker'
        if name is not None:
            return SUBTYPE_CATEGORIES.get(name)
        # Existing authentic catalogs are a narrow fallback while the enum is
        # still loading.  Unknown gun/profile rows remain fail-closed.
        if item_id in (globals().get('EMOTE_INFO') or {}):
            return 'emote'
    except Exception:
        pass
    return None


def _v109_new_state(warehouse, token):
    try:
        reference = weakref.ref(warehouse)
    except Exception:
        reference = None
    return {
        'wid': id(warehouse), 'token': token, 'ref': reference,
        'warehouse': None, 'sig': None, 'injected': {}, 'by_item': {},
        'jobs': [], 'pending': set(), 'failed': {}, 'owned': set(),
        'owned_at': 0.0, 'completed': {}, 'equip_restore': {},
        'timer': False, 'busy': False, 'job_serial': 0,
    }


def get_state(warehouse):
    global _v109_state
    state = _v109_state
    same = state.get('wid') == id(warehouse)
    if same and state.get('ref') is not None:
        try:
            same = state['ref']() is warehouse
        except Exception:
            same = False
    if not same:
        state = _v109_new_state(warehouse, _v109_int(
            state.get('token'), 0) + 1)
        _v109_state = state
        STRIKER_PENDING.clear()
    return state


def state_warehouse(state):
    warehouse = state.get('warehouse')
    if warehouse is not None:
        return warehouse
    try:
        reference = state.get('ref')
        return reference() if reference is not None else None
    except Exception:
        return None


def native_item_ids(warehouse):
    try:
        mapping = getattr(warehouse, 'item_id_dict', None) or {}
        return set(_v109_int(key, 0) for key in mapping.keys())
    except Exception:
        return set()


def invalidate_item_index(warehouse):
    """Invalidate the official client's cached item_id -> GUID index.

    Client IHallItems uses a lazy ``item_id_dict`` property backed by
    ``_item_id_dict``.  Python-side insertion/removal must not leave ownership,
    Vault lists and GUID resolvers reading a pre-insertion cached index.
    """
    try:
        setattr(warehouse, '_item_id_dict', None)
        return True
    except Exception:
        return False


def item_index_has(warehouse, item_id, guid):
    invalidate_item_index(warehouse)
    try:
        mapping = getattr(warehouse, 'item_id_dict', None) or {}
        values = mapping.get(item_id)
        if values is None:
            values = mapping.get(str(item_id))
        return bool(values and guid in values)
    except Exception:
        return False


_V109_MISSING = object()
# Internal sentinel only: official ArmLowLevelSkin zero removes one mapping
# key. It is never sent to the game or confused with an item ID.
DELETE = object()


def path_get(owner, kind, key):
    try:
        if kind == 'attr':
            return True, getattr(owner, key)
        if kind == 'map':
            map_name, map_key = key
            mapping = getattr(owner, map_name)
            value = mapping.get(map_key, _V109_MISSING)
            return True, value
        if kind == 'hero_info':
            map_name, map_key, field = key
            info = getattr(owner, map_name).get(map_key)
            if info is None:
                return False, None
            try:
                value = info[field]
            except Exception:
                value = getattr(info, field)
            return True, value
        if kind == 'obj':
            map_name, map_key, field = key
            mapping = getattr(owner, map_name)
            obj = mapping.get(map_key)
            if obj is None:
                return False, None
            return True, getattr(obj, field)
        if kind == 'hero_map':
            heroes_name, hero_id, map_name, map_key = key
            info = getattr(owner, heroes_name).get(hero_id)
            if info is None:
                return False, None
            mapping = getattr(info, map_name)
            return True, mapping.get(map_key, _V109_MISSING)
        if kind == 'nested':
            map_name, map_key, slot = key
            nested = getattr(owner, map_name).get(map_key)
            if isinstance(nested, list):
                if not 0 <= slot < len(nested):
                    return False, None
                return True, nested[slot]
            value = nested.get(slot, _V109_MISSING)
            return True, value
    except Exception:
        return False, None
    return False, None


def path_set(owner, kind, key, value):
    try:
        if kind == 'attr':
            setattr(owner, key, value)
        elif kind == 'map':
            map_name, map_key = key
            getattr(owner, map_name)[map_key] = value
        elif kind == 'hero_info':
            map_name, map_key, field = key
            info = getattr(owner, map_name).get(map_key)
            if info is None:
                return False
            try:
                # Official CHeroInfo is an item container. This channel runs
                # its native on_setattr broadcast; a bare Python attribute
                # write can change a readback attr without notifying UI/model
                # subscribers (observed in the v10.11.3 device log).
                info[field] = value
            except Exception as exc:
                setattr(info, field, value)
                _v109_log(('striker-hero-info-attr-fallback', map_key, field, value),
                          'Striker CHeroInfo item write fallback hero=%d field=%s value=%s error=%r'
                          % (map_key, field, value, exc), 2)
            else:
                _v109_log(('striker-hero-info-item-write', map_key, field, value),
                          'Striker CHeroInfo official item write hero=%d field=%s value=%s'
                          % (map_key, field, value), 4)
        elif kind == 'obj':
            map_name, map_key, field = key
            obj = getattr(owner, map_name).get(map_key)
            if obj is None:
                return False
            setattr(obj, field, value)
        elif kind == 'hero_map':
            heroes_name, hero_id, map_name, map_key = key
            info = getattr(owner, heroes_name).get(hero_id)
            if info is None:
                return False
            getattr(info, map_name)[map_key] = value
        elif kind == 'nested':
            map_name, map_key, slot = key
            nested = getattr(owner, map_name).get(map_key)
            if isinstance(nested, list):
                if not 0 <= slot < len(nested):
                    return False
                nested[slot] = value
            else:
                nested[slot] = value
        else:
            return False
        return True
    except Exception:
        return False


def path_delete(owner, kind, key):
    try:
        if kind == 'map':
            map_name, map_key = key
            del getattr(owner, map_name)[map_key]
        elif kind == 'nested':
            map_name, map_key, slot = key
            nested = getattr(owner, map_name).get(map_key)
            if isinstance(nested, list):
                if not 0 <= slot < len(nested):
                    return False
                nested[slot] = 0
            else:
                del nested[slot]
        else:
            # Native scalar/info fields use zero for no selection.
            return path_set(owner, kind, key, 0)
        return True
    except Exception:
        return False


def restore_record(record):
    try:
        reference = record.get('ref')
        owner = reference() if callable(reference) else None
        if owner is None:
            return False
        kind, key = record['kind'], record['key']
        ok, current = path_get(owner, kind, key)
        if not ok or current != record.get('new'):
            return False               # a later native/genuine change wins
        if record.get('old') is _V109_MISSING:
            return path_delete(owner, kind, key)
        return path_set(owner, kind, key, record.get('old'))
    except Exception:
        return False


def restore_item(state, item_id):
    records = state.get('equip_restore', {}).pop(item_id, [])
    restored = 0
    for record in reversed(records):
        restored += int(bool(restore_record(record)))
    return restored


def remember_equip(state, item_id, owner, kind, key, old, new):
    # A native member and its PlayerAvatar can expose the same field name as
    # separate objects.  Keep one genuine baseline per object+slot so melee
    # OFF restores both without removing either object's restore record.
    token = (kind, key, id(owner))
    baseline = None
    # Reuse the original genuine baseline when moving between two injected
    # cosmetics in the same slot.  Do not restore the intermediate item later.
    for old_item, records in list(state.get('equip_restore', {}).items()):
        for record in list(records):
            if record.get('token') != token:
                continue
            baseline = record
            records.remove(record)
            if not records:
                state['equip_restore'].pop(old_item, None)
            break
        if baseline is not None:
            break
    try:
        reference = weakref.ref(owner)
    except Exception:
        reference = None
    record = {
        'token': token, 'ref': reference, 'kind': kind, 'key': key,
        'old': (baseline.get('old') if baseline is not None else old),
        'new': new,
    }
    state.setdefault('equip_restore', {}).setdefault(item_id, []).append(record)
    return record


def apply_equip(item_id, owner, operations):
    state = _v109_state
    applied = []
    for kind, key, value in operations:
        ok, old = path_get(owner, kind, key)
        if not ok:
            for record in reversed(applied):
                restore_record(record)
            return False
        record = remember_equip(
            state, item_id, owner, kind, key, old, value)
        if not path_set(owner, kind, key, value):
            restore_record(record)
            for old_record in reversed(applied):
                restore_record(old_record)
            return False
        applied.append(record)
        # v2.114: fire the game's _on_set_<name> observer so the in-match
        # visuals (trail / med / grenade / death-box / parachute / airdrop)
        # see the pick.  The debug-14 probe lists these exact callbacks on
        # PlayerAvatar; a raw field write alone never triggered them.
        try:
            if kind == 'attr':
                _cb = getattr(owner, '_on_set_' + str(key), None)
                if callable(_cb):
                    _cb()
        except Exception:
            pass
    return bool(applied)


def injected_record(value):
    state = _v109_state
    try:
        record = state.get('injected', {}).get(value)
    except Exception:
        record = None
    if record is None:
        item_id = _v109_int(value, 0)
        guid = state.get('by_item', {}).get(item_id) if item_id else None
        record = state.get('injected', {}).get(guid) if guid else None
    if not record:
        return None
    item_id, category, item = record
    if not category_enabled(category):
        return None
    return record


def persist_pick(kind, hero_id, slot, item_id):
    """Mirror one item pick into the existing config channel and local cache."""
    try:
        kind = str(kind).upper()
        hero_id = _v109_int(hero_id, 0)
        slot = _v109_int(slot, -1)
        item_id = _v109_int(item_id, 0)
        if not 0 <= item_id <= 9999999999:
            return False
        if kind == 'E':
            if not 1 <= hero_id <= 1000000 or not 0 <= slot < 64:
                return False
            key = 'iNativeEmote_%d_%d' % (hero_id, slot)
        elif kind == 'M':
            if hero_id != 0 or slot != 0:
                return False
            key = 'iNativeMelee'
        elif kind == 'P':
            if hero_id != 0 or slot != 0:
                return False
            key = 'iNativePlayPal'
        elif kind == 'C':
            # hero_id carries the stable RPC code; slot carries the official
            # vehicle/gun/equip/skybox key (zero for a scalar selection).
            if not 1 <= hero_id <= 63 or not 0 <= slot <= 1000000:
                return False
            if hero_id not in COSMETIC_CODE_RPCS:
                return False
            key = 'iNativeCosmetic_%d_%d' % (hero_id, slot)
        else:
            return False
        hi, lo = divmod(item_id, 1000000)
        sync_attrs[key + '_hi'] = hi
        sync_attrs[key + '_lo'] = lo
        writer = globals().get('_write_udp_skin')
        if callable(writer):
            writer('NP|%s|%d|%d|%d\n' % (kind, hero_id, slot, item_id))
        return True
    except Exception:
        return False


def config_pick(key):
    try:
        hi = _v109_int(sync_attrs.get(key + '_hi', 0), 0)
        lo = _v109_int(sync_attrs.get(key + '_lo', 0), 0)
        if hi <= 0 or not 0 <= lo < 1000000:
            return 0
        item_id = hi * 1000000 + lo
        return item_id if 0 < item_id <= 9999999999 else 0
    except Exception:
        return 0


def config_emote_picks():
    picks = []
    try:
        prefix = 'iNativeEmote_'
        for key, _value in list(sync_attrs.items()):
            if not key.startswith(prefix) or not key.endswith('_hi'):
                continue
            base = key[:-3]
            try:
                hero_text, slot_text = base[len(prefix):].rsplit('_', 1)
                hero_id = _v109_int(hero_text, 0)
                slot = _v109_int(slot_text, -1)
            except Exception:
                continue
            item_id = config_pick(base)
            if 1 <= hero_id <= 1000000 and 0 <= slot < 64 and item_id:
                picks.append((hero_id, slot, item_id))
            if len(picks) >= 64:
                break
    except Exception:
        pass
    return picks


# The three sky slots are mutually exclusive in the official client.  Every
# setter in `WarehouseItemWindow` clears the aircraft skin first:
#   _DoApplySkydiveSkin   -> CallServer('SetAircraftSkin', 0); CallServer('SetSkydiveSkin', id)
#   _DoApplyParachuteSkin -> CallServer('SetAircraftSkin', 0); CallServer('SetParachuteSkin', id)
#   _DoApplyTrailingSkin  -> CallServer('SetAircraftSkin', 0); CallServer('ApplyTrailingSkin', id)
#   OnUnequipAircraftSkin -> CallServer('SetAircraftSkin', 0)
# so choosing a skydive or parachute skin genuinely replaces the aircraft one
# rather than stacking three visuals on one entrance.  Mirror that locally and
# tell the UI, instead of leaving a stale aircraft model behind.
SKY_EXCLUSIVE_RPCS = ('SetSkydiveSkin', 'SetParachuteSkin',
                            'ApplyTrailingSkin')


def sky_clear_aircraft(owner, rpc):
    """Apply the official 'clear aircraft before this sky slot' step."""
    if rpc not in SKY_EXCLUSIVE_RPCS:
        return True
    try:
        ok, current = path_get(owner, 'attr', 'aircraft_skin')
    except Exception:
        return True
    if not ok or not _v109_int(current, 0):
        return True
    cleared = path_set(owner, 'attr', 'aircraft_skin', 0)
    _v109_log(('sky-exclusive', rpc, current, cleared),
              'sky slot exclusivity RPC=%s cleared aircraft_skin=%s (official '
              'client clears it before skydive/parachute/trailing) ok=%s'
              % (rpc, current, cleared), 2)
    return cleared


def _v109_cosmetic_slot(rpc, params):
    """Return the official persistence slot, or None for an ambiguous shape."""
    try:
        if rpc == 'ArmHeroTransform':
            if len(params) != 2:
                return None
            index = 0
        elif rpc in ('ArmGunSkin', 'ArmGunGuise', 'ArmVehicleSkin',
                     'ArmBombSkin', 'ArmMedicineSkin'):
            if len(params) < 2:
                return None
            index = 0 if rpc in ('ArmGunSkin', 'ArmGunGuise') else 1
        elif rpc == 'ArmSkyBox':
            if len(params) != 2:
                return None
            index = 1
        elif rpc in COSMETIC_RPC_CODES:
            if len(params) != 1:
                return None
            return 0
        else:
            return None
        slot = _v109_int(params[index], -1)
        return slot if 0 <= slot <= 1000000 else None
    except Exception:
        return None


def cosmetic_remember_pick(rpc, slot, item_id, persist=True):
    code = COSMETIC_RPC_CODES.get(rpc)
    slot = _v109_int(slot, -1)
    item_id = _v109_int(item_id, 0)
    if code is None or not 0 <= slot <= 1000000:
        return False
    # v2.105: download-cloud on selection - the model build's
    # synchronous resource load must never block the game thread
    # 39-75s waiting for bundles nobody requested (round-122).
    try:
        if item_id:
            _dl2105 = globals().get('try_dlc_download')
            if callable(_dl2105):
                try:
                    _dl2105(item_id, [], front=True)
                except TypeError:
                    _dl2105(item_id, [])
    except Exception:
        pass
    key = (rpc, slot)
    if item_id:
        COSMETIC_SAVED[key] = item_id
    else:
        COSMETIC_SAVED.pop(key, None)
    if persist:
        return persist_pick('C', code, slot, item_id)
    return True


def cosmetic_forget_baselines(owner, rpc, slot):
    """A later genuine RPC retires OFF restoration for only this native slot."""
    try:
        if rpc in ('ArmGunSkin', 'ArmGunGuise'):
            stem = 'skin' if rpc == 'ArmGunSkin' else 'guise'
            tokens = {
                ('obj', ('gun_infos', slot, stem + '_item_id'), id(owner)),
                ('obj', ('gun_infos', slot, stem + '_random'), id(owner)),
            }
        elif rpc in ('ArmVehicleSkin', 'ArmSkyBox',
                     'ArmBombSkin', 'ArmMedicineSkin'):
            name = {
                'ArmVehicleSkin': 'vehicle_skins', 'ArmSkyBox': 'skybox_info',
                'ArmBombSkin': 'bomb_skins', 'ArmMedicineSkin': 'medicine_skins',
            }[rpc]
            tokens = {('map', (name, slot), id(owner))}
        else:
            name = {
                'ApplyDeathBoxSkin': 'death_box_skin_id',
                'SetAircraftSkin': 'aircraft_skin',
                'SetParachuteSkin': 'parachute_skin',
                'SetSkydiveSkin': 'skydive_skin',
                'ApplyTrailingSkin': 'trailing_skin_item_id',
                'SetAirDropItem': 'airdrop_skin',
                'SetVoicePackage': 'voice_package',
                'ArmBanner': 'banner_item_id',
                'ArmHallBackground': 'hall_background_item_id',
                'ArmHallMusic': 'hall_music', 'SetNameFrame': 'name_frame',
                'ChangeHeadFrame': 'head_frame',
                'ChangeCardBackground': 'card_background',
                'ChangeHomepageBackground': 'homepage_background',
                'UseChatBubbles': 'chat_bubbles_item_id',
            }.get(rpc)
            tokens = {('attr', name, id(owner))} if name else set()
        if not tokens:
            return 0
        removed = 0
        restore = _v109_state.get('equip_restore', {})
        for item_id, records in list(restore.items()):
            before = len(records)
            records[:] = [record for record in records
                          if record.get('token') not in tokens]
            removed += before - len(records)
            if not records:
                restore.pop(item_id, None)
        return removed
    except Exception:
        return 0


def config_cosmetic_picks():
    picks = []
    try:
        prefix = 'iNativeCosmetic_'
        for key, _value in list(sync_attrs.items()):
            if not key.startswith(prefix) or not key.endswith('_hi'):
                continue
            base = key[:-3]
            try:
                code_text, slot_text = base[len(prefix):].split('_', 1)
                code = _v109_int(code_text, 0)
                slot = _v109_int(slot_text, -1)
            except Exception:
                continue
            rpc = COSMETIC_CODE_RPCS.get(code)
            item_id = config_pick(base)
            if rpc and 0 <= slot <= 1000000 and item_id:
                # v2.106: download-cloud for the config-restored pick
                # - no pick event fires at login, so request the
                # resources here (deduped; the staggered background
                # queue absorbs repeats).
                try:
                    if item_id:
                        _dl2106 = globals().get(
                            'try_dlc_download')
                        if callable(_dl2106):
                            _dl2106(item_id, [])
                except Exception:
                    pass
                picks.append((rpc, slot, item_id))
            if len(picks) >= 128:
                break
    except Exception:
        pass
    return picks


def cosmetic_restore_params(owner, rpc, slot, item_id, guid):
    """Rebuild the official argument order from a stable item/slot record."""
    if rpc == 'ArmHeroTransform':
        return (slot, item_id)
    if rpc in ('ArmGunSkin', 'ArmGunGuise'):
        try:
            info = getattr(owner, 'gun_infos').get(slot)
            if info is None or not guid:
                return None
            field = 'skin_random' if rpc == 'ArmGunSkin' else 'guise_random'
            return (slot, guid, False, bool(getattr(info, field, False)))
        except Exception:
            return None
    if rpc in ('ArmVehicleSkin', 'ArmSkyBox',
               'ArmBombSkin', 'ArmMedicineSkin'):
        return (item_id, slot)
    if rpc in COSMETIC_RPC_CODES:
        return (item_id,)
    return None


def restore_striker_picks(avatar, warehouse, picks):
    """Restore dependent Striker records with readback after every phase."""
    restored = 0
    pending = False
    suits = {slot: item_id for rpc, slot, item_id in picks
             if rpc == 'ArmHeroSkin'}
    appearances = {slot: item_id for rpc, slot, item_id in picks
                   if rpc == 'ArmLowLevelSkin'}
    for hero_id, equipped in sorted(suits.items()):
        appearance = appearances.get(hero_id, 0)
        needed = (equipped, appearance) if appearance else (equipped,)
        records = {}
        for item_id in needed:
            if _v109_category(item_id) != 'striker':
                pending = pending or _v109_category(item_id) is None
                continue
            ensure_item(warehouse, item_id, mode='single')
            record = injected_record(item_id)
            if record and record[1] == 'striker':
                records[item_id] = record
            else:
                native_state = get_state(warehouse)
                if item_id in native_state.get('owned', set()):
                    cosmetic_remember_pick(
                        'ArmHeroSkin', hero_id, 0)
                    cosmetic_remember_pick(
                        'ArmLowLevelSkin', hero_id, 0)
                else:
                    pending = True
        if any(item_id not in records for item_id in needed):
            continue
        if appearance:
            striker_low_level(
                avatar, (equipped, appearance), persist=False)
            ok, current = path_get(
                avatar, 'map', ('arm_low_level_skin', equipped))
            if not ok or current != appearance:
                pending = True
                continue
        striker_hero_skin(
            avatar, (hero_id, equipped), persist=False)
        current_equipped = striker_info_item(avatar, hero_id)
        current_appearance = striker_actual_skin(avatar, hero_id)
        if (current_equipped != equipped
                or current_appearance != (appearance or equipped)):
            pending = True
            continue
        cosmetic_remember_pick(
            'ArmHeroSkin', hero_id, equipped, persist=False)
        cosmetic_remember_pick(
            'ArmLowLevelSkin', hero_id, appearance, persist=False)
        restored += 1 + int(bool(appearance))

    for rpc, hero_id, item_id in sorted(
            picks, key=lambda entry: COSMETIC_RPC_CODES.get(entry[0], 0)):
        if rpc in ('ArmHeroSkin', 'ArmLowLevelSkin'):
            continue
        if _v109_category(item_id) is None:
            pending = True
            continue
        if _v109_category(item_id) != 'striker':
            continue
        ensure_item(warehouse, item_id, mode='single')
        record = injected_record(item_id)
        if not record or record[1] != 'striker':
            native_state = get_state(warehouse)
            if item_id in native_state.get('owned', set()):
                cosmetic_remember_pick(rpc, hero_id, 0)
            else:
                pending = True
            continue
        verified = False
        if rpc == 'ArmHeroTransform':
            verified = local_equip(
                avatar, rpc, (hero_id, item_id), persist=False)
        elif rpc in ('ArmSkinExecuteItem', 'ArmDisplayItem'):
            skin_id = striker_info_item(avatar, hero_id)
            _v109_log(
                ('striker-action-restore', rpc, hero_id, skin_id),
                'Striker action restore rpc=%s hero=%d skin=%d'
                % (rpc, hero_id, skin_id or 0), 1)
            if skin_id:
                striker_action_rpc(
                    avatar, rpc, ([[hero_id, skin_id, item_id]],),
                    persist=False)
                map_name = ('skin_execute_item_map'
                            if rpc == 'ArmSkinExecuteItem'
                            else 'skin_display_item_map')
                scalar_name = ('execute_item_id'
                               if rpc == 'ArmSkinExecuteItem'
                               else 'display_item_id')
                ok, mapped = path_get(
                    avatar, 'hero_map',
                    ('hero_infos', hero_id, map_name, skin_id))
                scalar = striker_info_item(
                    avatar, hero_id, scalar_name)
                verified = bool(ok and mapped == item_id and scalar == item_id)
        if verified:
            cosmetic_remember_pick(
                rpc, hero_id, item_id, persist=False)
            restored += 1
        else:
            pending = True
    return restored, pending


def native_avatar():
    """Return the already-loaded local avatar and warehouse, without imports."""
    try:
        helper = globals().get('_game_genv')
        root = helper() if callable(helper) else globals().get('genv')
    except Exception:
        root = globals().get('genv')
    avatar = getattr(root, 'avatar', None)
    warehouse = getattr(root, 'warehouse', None)
    if avatar is None and warehouse is not None:
        avatar = getattr(warehouse, 'avatar', None)
    if avatar is None:
        try:
            reference = globals().get('_avatar_seen_ref')
            avatar = reference() if callable(reference) else None
        except Exception:
            avatar = None
    if avatar is None:
        return None, None
    if warehouse is None:
        warehouse = getattr(avatar, 'warehouse', None)
    return avatar, warehouse


def clear_saved_picks(category=None):
    """Clear session and config picks on OFF; genuine native state is separate."""
    try:
        if category in (None, 'emote'):
            saved = list(EMOTE_SAVED.items())
            configured = config_emote_picks()
            for (hero_id, slot), _item in saved:
                persist_pick('E', hero_id, slot, 0)
            for hero_id, slot, _item in configured:
                if (hero_id, slot) not in EMOTE_SAVED:
                    persist_pick('E', hero_id, slot, 0)
            EMOTE_SAVED.clear()
        if category in (None, 'melee'):
            if MELEE_SAVED or config_pick('iNativeMelee'):
                persist_pick('M', 0, 0, 0)
            MELEE_SAVED.clear()
        if category in (None, 'playpal'):
            panpan_stop_playing()
            if PANPAN_SAVED or config_pick('iNativePlayPal'):
                persist_pick('P', 0, 0, 0)
            PANPAN_SAVED.clear()
        generic = dict(COSMETIC_SAVED)
        for rpc, slot, item_id in config_cosmetic_picks():
            generic.setdefault((rpc, slot), item_id)
        for (rpc, slot), item_id in list(generic.items()):
            item_category = _v109_category(item_id)
            if category is not None and item_category != category:
                continue
            cosmetic_remember_pick(rpc, slot, 0)
        if category is None:
            COSMETIC_SAVED.clear()
    except Exception:
        pass


def restore_native_picks():
    """Recreate saved native items once per avatar after a process restart."""
    avatar, warehouse = native_avatar()
    if avatar is None or warehouse is None:
        return 0
    state = restore_state
    key = (id(avatar), id(warehouse))
    if state.get('key') != key:
        state.update({'key': key, 'done': False, 'attempts': 0})
    if state.get('done'):
        return 0
    emote_enabled = category_enabled('emote')
    melee_enabled = category_enabled('melee')
    playpal_enabled = category_enabled('playpal')
    emote_picks = config_emote_picks() if emote_enabled else []
    melee_item = config_pick('iNativeMelee') if melee_enabled else 0
    playpal_item = config_pick(
        'iNativePlayPal') if playpal_enabled else 0
    cosmetic_picks = []
    striker_picks = []
    for rpc, slot, item_id in config_cosmetic_picks():
        item_category = _v109_category(item_id)
        if item_category is None or category_enabled(item_category):
            if rpc in STRIKER_PERSIST_RPCS:
                striker_picks.append((rpc, slot, item_id))
            else:
                cosmetic_picks.append((rpc, slot, item_id))
    # Native config sync may arrive after the avatar.  An empty snapshot is
    # not completion: keep waiting for the saved fields without equipping.
    if (not emote_picks and not melee_item and not playpal_item
            and not cosmetic_picks and not striker_picks):
        return 0
    attempts = state.get('attempts', 0) + 1
    state['attempts'] = attempts
    if attempts > 24:
        state['done'] = True
        return 0
    restored = 0
    pending = False
    for hero_id, slot, item_id in emote_picks:
        category = _v109_category(item_id)
        if category != 'emote':
            # Late native enum/data loads are transient; a known different
            # category is simply not an emote restore request.
            pending = pending or category is None
            continue
        ensure_item(warehouse, item_id, mode='single')
        record = injected_record(item_id)
        if not record:
            native_state = get_state(warehouse)
            if item_id in native_state.get('owned', set()):
                persist_pick('E', hero_id, slot, 0)
            else:
                pending = True
            continue
        _ok, current = path_get(
            avatar, 'nested', ('emote_info', hero_id, slot))
        current_id = _v109_int(current, 0)
        if current_id == item_id:
            EMOTE_SAVED[(hero_id, slot)] = item_id
            restored += 1
        else:
            # The first post-login value is the server's baseline, including a
            # normal genuine/default emote.  A saved injected selection must be
            # restored over that baseline once.  Later genuine native reads and
            # equips still clear this pick through the existing reader/RPC path.
            operations = emote_equip_plan(
                avatar, (item_id, slot), 0, item_id)
            if operations and apply_equip(
                    item_id, avatar, operations):
                emote_remember_pick(
                    item_id, operations, persist=False)
                restored += 1
            else:
                pending = True
    if melee_item:
        category = _v109_category(melee_item)
        if category != 'melee':
            pending = pending or category is None
        else:
            ensure_item(warehouse, melee_item, mode='single')
            record = injected_record(melee_item)
            if record:
                guid = getattr(record[2], 'guid', None)
                if melee_guid_present(avatar, guid):
                    melee_remember_pick(melee_item, persist=False)
                    restored += 1
                elif local_equip(
                        avatar, 'ApplyMelee', (guid, False), persist=False):
                    restored += 1
                else:
                    pending = True
            else:
                native_state = get_state(warehouse)
                if melee_item in native_state.get('owned', set()):
                    persist_pick('M', 0, 0, 0)
                else:
                    pending = True
    if playpal_item:
        category = _v109_category(playpal_item)
        if category != 'playpal':
            pending = pending or category is None
        else:
            ensure_item(warehouse, playpal_item, mode='single')
            record = injected_record(playpal_item)
            if record:
                guid = getattr(record[2], 'guid', None)
                current = getattr(avatar, 'arm_panpan', None)
                random = bool(getattr(avatar, 'arm_panpan_random', False))
                if current == guid and not random:
                    panpan_remember_pick(
                        playpal_item, persist=False)
                    restored += 1
                elif local_equip(
                        avatar, 'ApplyPanpan', (guid,), persist=False):
                    # Restore over the initial genuine/random server baseline.
                    # A later genuine ApplyPanpan clears the saved pick before
                    # its original server RPC, so this is not a sticky override.
                    restored += 1
                else:
                    pending = True
            else:
                native_state = get_state(warehouse)
                if playpal_item in native_state.get('owned', set()):
                    panpan_remember_pick(0)
                else:
                    pending = True
    for rpc, slot, item_id in cosmetic_picks:
        category = _v109_category(item_id)
        if category is None:
            pending = True
            continue
        if not category_enabled(category):
            continue
        ensure_item(warehouse, item_id, mode='single')
        record = injected_record(item_id)
        if not record or record[1] != category:
            native_state = get_state(warehouse)
            if item_id in native_state.get('owned', set()):
                cosmetic_remember_pick(rpc, slot, 0)
            else:
                pending = True
            continue
        guid = getattr(record[2], 'guid', None)
        params = cosmetic_restore_params(
            avatar, rpc, slot, item_id, guid)
        if params and local_equip(
                avatar, rpc, params, persist=False):
            cosmetic_remember_pick(
                rpc, slot, item_id, persist=False)
            restored += 1
        else:
            pending = True
    if striker_picks:
        striker_restored, striker_pending = restore_striker_picks(
            avatar, warehouse, striker_picks)
        restored += striker_restored
        pending = pending or striker_pending
    if not pending:
        state['done'] = True
    if restored:
        _v109_log(('native-picks-restored', key, restored),
                  'restored %d saved native cosmetic pick(s)' % restored, 1)
    return restored


def emote_compact(value):
    try:
        if value is None or isinstance(value, (bool, int)):
            return repr(value)
        if isinstance(value, str):
            return repr(value[:48])
        item_id = getattr(value, 'item_id', None)
        if isinstance(item_id, int) and not isinstance(item_id, bool):
            return '<%s item=%d>' % (type(value).__name__, item_id)
        guid = getattr(value, 'guid', None)
        if guid:
            return '<%s guid=%s>' % (type(value).__name__, str(guid)[:32])
        return '<%s>' % type(value).__name__
    except Exception:
        return '<?>'


def emote_code_contract(function, label):
    """One bounded, read-only bytecode capture for the exact native equip path."""
    try:
        if not EMOTE_VERBOSE_TRACE or not category_enabled('emote'):
            return False
        state = emote_probe_state
        seen = state.setdefault('code', set())
        if label in seen or len(seen) >= 4:
            return False
        seen.add(label)
        code = getattr(function, '__code__', None)
        if code is None:
            _plog('[CUNLOCK] EMOTE CODE source=%s unavailable=no-python-code'
                  % label)
            return False
        names = tuple(code.co_names)[:96]
        variables = tuple(code.co_varnames)[:48]
        strings = tuple(value[:100] for value in code.co_consts
                        if isinstance(value, str))[:40]
        _plog('[CUNLOCK] EMOTE CODE source=%s names=%r vars=%r strings=%r'
              % (label, names, variables, strings))
        import dis as _dis
        rendered = []
        count = 0
        truncated = False
        for instruction in _dis.get_instructions(function):
            count += 1
            if count > 600:
                truncated = True
                break
            rendered.append('%04d %-30s %s' % (
                instruction.offset, instruction.opname, instruction.argrepr))
        _plog('[CUNLOCK] EMOTE BYTECODE source=%s shown=%d truncated=%s\n%s'
              % (label, len(rendered), truncated, '\n'.join(rendered)))
        return True
    except Exception as exc:
        try:
            _plog('[CUNLOCK] EMOTE CODE source=%s error=%r' % (label, exc))
        except Exception:
            pass
        return False


def emote_window_state(owner):
    """Compact selected-item/slot fields only; no object or module scans."""
    try:
        values = vars(owner)
    except Exception:
        return 'fields=unavailable'
    fields = []
    try:
        for key in sorted(values):
            lower = str(key).lower()
            if not any(token in lower for token in (
                    'emote', 'item', 'slot', 'select', 'current')):
                continue
            fields.append('%s=%s' % (
                key, emote_compact(values[key])))
            if len(fields) >= 16:
                break
    except Exception:
        pass
    return 'fields={%s}' % ', '.join(fields)


def emote_shape(mapping):
    """Compact bounded container evidence; never walk a whole emote table."""
    if mapping is None:
        return 'None'
    try:
        output = [type(mapping).__name__]
        try:
            output.append('len=%d' % len(mapping))
        except Exception:
            pass
        try:
            iterator = iter(mapping)
        except Exception:
            keys = getattr(mapping, 'keys', None)
            iterator = iter(keys()) if callable(keys) else iter(())
        direct = []
        nested = []
        for key in iterator:
            if len(direct) >= 6:
                break
            direct.append(emote_compact(key))
            if len(nested) >= 2:
                continue
            try:
                getter = getattr(mapping, 'get', None)
                child = getter(key, _V109_MISSING) if callable(getter) \
                    else mapping[key]
                if isinstance(child, (dict, list, tuple)) or callable(
                        getattr(child, 'get', None)):
                    child_keys = []
                    try:
                        for child_key in child:
                            child_keys.append(emote_compact(child_key))
                            if len(child_keys) >= 6:
                                break
                    except Exception:
                        pass
                    nested.append('%s:%s%s' % (
                        emote_compact(key), type(child).__name__,
                        child_keys))
            except Exception:
                pass
        output.append('keys=%s' % direct)
        if nested:
            output.append('nested=%s' % nested)
        return ' '.join(output)
    except Exception as exc:
        return '%s(shape-error=%r)' % (type(mapping).__name__, exc)


def emote_probe(owner, params, source='CallServer', kind='rpc'):
    """Log a few real emote calls so slot support is evidence-led."""
    try:
        if not category_enabled('emote'):
            return False
        state = emote_probe_state
        count = state.get(kind, 0)
        if count >= 6:
            return False
        state[kind] = count + 1
        containers = []
        for name in ('emote_info', 'hero_emote_info', 'extra_emote_info'):
            try:
                value = getattr(owner, name)
            except Exception:
                continue
            containers.append('%s=%s' % (name, emote_shape(value)))
        callers = []
        try:
            frame = sys._getframe(2)
            for _depth in range(10):
                if frame is None:
                    break
                name = frame.f_code.co_name
                frame = frame.f_back
                if name.startswith('_v109_') or name == 'wrapper':
                    continue
                callers.append(name)
                if len(callers) >= 5:
                    break
        except Exception:
            pass
        compact = [emote_compact(value) for value in tuple(params)[:6]]
        # A dedicated 12-event budget keeps this evidence available even if
        # the general cosmetic log-key cap was reached earlier in the session.
        _plog('[CUNLOCK] EMOTE probe=%d source=%s owner=%s args=%s %s callers=%s'
              % (count + 1, source, type(owner).__name__, compact,
                 ' '.join(containers) or 'containers=missing', callers))
        return True
    except Exception:
        return False


def emote_nested_key(mapping, hero_id):
    """Return an existing hero key only when its child is a real container."""
    try:
        getter = getattr(mapping, 'get', None)
        if not callable(getter):
            return None
        for key in (hero_id, str(hero_id)):
            child = getter(key, _V109_MISSING)
            if child is _V109_MISSING:
                continue
            if isinstance(child, list) or callable(getattr(child, 'get', None)):
                return key
    except Exception:
        pass
    return None


def emote_slot_key(mapping, slot):
    if isinstance(mapping, list):
        return slot if 0 <= slot < len(mapping) else None
    try:
        getter = getattr(mapping, 'get', None)
        if callable(getter):
            for key in (slot, str(slot)):
                if getter(key, _V109_MISSING) is not _V109_MISSING:
                    return key
    except Exception:
        return None
    return slot


def emote_equip_plan(owner, params, item_index, item_id):
    """Mirror native ArmHeroEmo(item_id, slot) with native nested maps.

    The official item row supplies emote_id=(hero_id, animation_id).  The
    avatar stores CArmEmoteInfos[hero_id][slot], whose missing child is a
    CEmoteInfo created through VALUE_TYPE.  Unknown shapes fail closed.
    """
    if item_index != 0 or len(params) != 2:
        return []
    slot = _v109_int(params[1], -1)
    if not 0 <= slot < 12:
        return []
    try:
        info = getattr(owner, 'emote_info')
        if not callable(getattr(info, 'get', None)) or not hasattr(
                info, '__setitem__'):
            return []
        row = _v109_row(item_id)
        emote_id = _v109_field(row, 'emote_id')
        if emote_id is None or isinstance(emote_id, (str, bytes)) \
                or len(emote_id) != 2:
            return []
        hero_id = _v109_int(emote_id[0], 0)
        if not hero_id:
            return []
        hero_key = emote_nested_key(info, hero_id)
        if hero_key is not None:
            nested = info.get(hero_key)
            slot_key = emote_slot_key(nested, slot)
            if slot_key is None:
                return []
            return [('nested', ('emote_info', hero_key, slot_key), item_id)]
        # Do not replace a malformed existing child or invent a plain dict.
        for candidate in (hero_id, str(hero_id)):
            if info.get(candidate, _V109_MISSING) is not _V109_MISSING:
                return []
        value_type = getattr(info, 'VALUE_TYPE', None)
        if not callable(value_type):
            return []
        child = value_type()
        if not callable(getattr(child, 'get', None)) or not hasattr(
                child, '__setitem__'):
            return []
        return [('map', ('emote_info', hero_id), child),
                ('nested', ('emote_info', hero_id, slot), item_id)]
    except Exception:
        return []


def emote_remember_pick(item_id, operations, persist=True):
    """Remember one successful nested injected equip for native readback."""
    try:
        kind, key, _value = operations[-1]
        if kind != 'nested' or len(key) != 3 or key[0] != 'emote_info':
            return False
        pick = (key[1], key[2])
        if len(EMOTE_SAVED) >= 64 and pick not in EMOTE_SAVED:
            EMOTE_SAVED.pop(next(iter(EMOTE_SAVED)), None)
        EMOTE_SAVED[pick] = item_id
        if persist:
            persist_pick('E', pick[0], pick[1], item_id)
        return True
    except Exception:
        return False


def melee_remember_pick(item_id, random=False, persist=True):
    """Remember the item, never its session-specific native GUID."""
    try:
        item_id = _v109_int(item_id, 0)
        if item_id:
            MELEE_SAVED.update(
                {'item_id': item_id, 'random': bool(random)})
            # v2.102: download-cloud on SELECTION.  The melee mesh
            # bundle must land before the in-match visual applies (the
            # game match-skips downloads in-match).  The call dedupes
            # and queues onto the staggered worker.
            try:
                _dl = globals().get('try_dlc_download')
                if callable(_dl):
                    _dl(item_id, [])
            except Exception:
                pass
        else:
            MELEE_SAVED.clear()
        if persist:
            persist_pick('M', 0, 0, item_id)
        if not item_id:
            restore = globals().get('melee_visual_restore_all')
            if callable(restore):
                restore('pick-cleared')
        return True
    except Exception:
        return False


def panpan_stop_playing():
    """Stop only transient playback started by the injected wheel path."""
    PANPAN_PLAY_PENDING.clear()
    state = PANPAN_PLAYING
    if not state.get('active'):
        return False
    avatar, _warehouse = native_avatar()
    try:
        if avatar is not None and bool(
                getattr(avatar, 'panpan_playing', False)):
            # The official setter broadcasts ON_PANPAN_PLAYING_UPDATE, which
            # drives HallModelManager.ExitPanpanPlayingStatus.
            avatar.panpan_playing = False
    except Exception as exc:
        _v109_log(('playpal-wheel-stop-error', repr(exc)),
                  'native PlayPal wheel OFF stop guarded error=%r' % (exc,), 1)
    state.clear()
    return True


def panpan_model_playing(manager=None):
    """Read native PlayPal playback, never the wheel's boolean hint alone."""
    try:
        if manager is None:
            helper = globals().get('_game_genv')
            root = helper() if callable(helper) else globals().get('genv')
            manager = getattr(root, 'hall_model_mgr', None)
        if manager is None:
            return False
        checker = getattr(manager, 'IsPlayingPanpan', None)
        if callable(checker) and checker():
            return True
        npc = getattr(manager, 'main_npc', None)
        return bool(getattr(npc, 'is_play_panpan', False))
    except Exception:
        return False


def panpan_start_model(item_id):
    """Run the official DLC-gated model event after the native setter.

    EnterPanpanPlayingStatus resolves the current item, checks authentic lobby
    DLC, restores the official camera, and invokes PlayMainNpcPanpan with
    force_raise=True.  ClearMainNpcEmote is the same wheel prerequisite.
    """
    try:
        helper = globals().get('_game_genv')
        root = helper() if callable(helper) else globals().get('genv')
        manager = getattr(root, 'hall_model_mgr', None)
        if manager is None or panpan_model_playing(manager):
            return manager is not None
        clear = getattr(manager, 'ClearMainNpcEmote', None)
        if callable(clear):
            clear()
        enter = getattr(manager, 'EnterPanpanPlayingStatus', None)
        if not callable(enter):
            return False
        enter()                       # official PlayMainNpcPanpan(force_raise=True)
        playing = panpan_model_playing(manager)
        _v109_log(('playpal-model-start', item_id, playing),
                  'native PlayPal model event item=%d official_enter_complete playing=%s'
                  % (item_id, playing), 2)
        # The model can begin on a later native animation callback.  Completion
        # of the official event cancels retries; it is not a rendering claim.
        return True
    except Exception as exc:
        _v109_log(('playpal-model-start-error', item_id, repr(exc)),
                  'native PlayPal model event item=%d guarded error=%r'
                  % (item_id, exc), 1)
        return False


def panpan_hall_playing(owner, params):
    """Complete only an injected wheel RPC through official native/model paths."""
    record = None
    try:
        if len(params) != 2:
            return False
        playing = _v109_int(params[0], -1)
        if playing not in (0, 1):
            return False
        guid = params[1]
        record = injected_record(guid)
        if (not record or record[1] != 'playpal'
                or not category_enabled('playpal')
                or getattr(owner, 'arm_panpan', None) != guid):
            return False
        item_id = record[0]
        desired = bool(playing)
        previous = bool(getattr(owner, 'panpan_playing', False))
        if not desired:
            PANPAN_PLAY_PENDING.clear()
        # Start/stop the native setter in this click/RPC frame.  DLC controls
        # model playback below; it must not postpone the wheel state itself.
        if previous != desired:
            owner.panpan_playing = desired
            if bool(getattr(owner, 'panpan_playing', False)) != desired:
                PANPAN_PLAY_PENDING.clear()
                _v109_log(('playpal-wheel-write', item_id),
                          'native PlayPal wheel item=%d setter readback mismatch'
                          % item_id, 1)
                return True
        if desired:
            if not PANPAN_PLAYING.get('active'):
                PANPAN_PLAYING['previous'] = previous
            PANPAN_PLAYING.update(
                {'active': True, 'item_id': item_id})
        else:
            PANPAN_PLAYING.clear()
            _v109_log(('playpal-wheel', item_id, 0),
                      'native PlayPal wheel item=%d playing=0 local setter complete; retry cancelled'
                      % item_id, 2)
            return True
        _v109_log(('playpal-wheel', item_id, 1),
                  'native PlayPal wheel item=%d playing=1 local setter complete'
                  % item_id, 2)
        if panpan_model_playing():
            PANPAN_PLAY_PENDING.clear()
            return True

        helper = globals().get('_game_genv')
        root = helper() if callable(helper) else globals().get('genv')
        manager = getattr(root, 'dlc_manager', None)
        check = getattr(manager, 'CheckDlcExists', None)
        missing = []
        unavailable = not callable(check)
        for name in ('InitPanPanDlcId', 'InitLobbyItemDlcId'):
            init = getattr(manager, name, None)
            if not callable(init):
                unavailable = True
                continue
            value = init(item_id)
            if name == 'InitLobbyItemDlcId':
                value = value[0] if isinstance(value, (tuple, list)) else value
            dlc_id = _v109_int(value, 0)
            if dlc_id and not check(dlc_id):
                missing.append(dlc_id)

        now = time.time()
        pending = PANPAN_PLAY_PENDING
        same = (pending.get('guid') == guid
                and pending.get('item_id') == item_id)
        request_at = pending.get('request_at', 0.0) if same else 0.0
        try:
            owner_ref = pending.get('ref') if same else weakref.ref(owner)
        except Exception:
            owner_ref = None
        created = pending.get('created', now) if same else now
        if unavailable or missing:
            if now - request_at >= 5.0:
                download = globals().get('try_dlc_download')
                if callable(download):
                    # Discover only the authentic IDs; never invent an asset.
                    download(item_id, missing[:2] if missing else [])
                request_at = now
            pending.update({
                'ref': owner_ref, 'guid': guid, 'item_id': item_id,
                'created': created, 'request_at': request_at,
            })
            _v109_log(('playpal-wheel-dlc', item_id,
                       tuple(missing[:2]), unavailable),
                      'native PlayPal wheel item=%d setter started; waiting for authentic DLC missing=%r unavailable=%s; bounded retry armed'
                      % (item_id, missing[:2], unavailable), 2)
            return True

        if panpan_start_model(item_id):
            pending.clear()
        else:
            # A not-yet-created lobby model/manager can become available on a
            # later scene callback.  Keep only this still-playing click pending.
            pending.update({
                'ref': owner_ref, 'guid': guid, 'item_id': item_id,
                'created': created, 'request_at': request_at,
            })
            _v109_log(('playpal-model-pending', item_id),
                      'native PlayPal item=%d official model event unavailable; bounded scene retry armed'
                      % item_id, 2)
        return True
    except Exception as exc:
        _v109_log(('playpal-wheel-error', repr(exc)),
                  'native PlayPal wheel guarded error=%r' % (exc,), 1)
        # Once an injected GUID is identified, never turn a local failure into
        # a server request for that injected item.
        return record is not None

def panpan_play_tick():
    """Advance one still-playing click; a stopped wheel is never restarted."""
    pending = PANPAN_PLAY_PENDING
    if not pending:
        return False
    if not category_enabled('playpal'):
        pending.clear()
        return False
    now = time.time()
    item_id = _v109_int(pending.get('item_id'), 0)
    guid = pending.get('guid')
    reference = pending.get('ref')
    owner = reference() if callable(reference) else None
    record = injected_record(guid) if guid else None
    if (owner is None or not record or record[0] != item_id
            or record[1] != 'playpal'
            or getattr(owner, 'arm_panpan', None) != guid):
        pending.clear()
        return False
    if not bool(getattr(owner, 'panpan_playing', False)):
        pending.clear()
        if PANPAN_PLAYING.get('item_id') == item_id:
            PANPAN_PLAYING.clear()
        _v109_log(('playpal-wheel-stopped', item_id),
                  'native PlayPal wheel item=%d stopped; pending refresh cancelled, no restart'
                  % item_id, 2)
        return False
    if now - pending.get('created', now) > PANPAN_PLAY_PENDING_SECONDS:
        _v109_log(('playpal-wheel-dlc-timeout', item_id),
                  'native PlayPal wheel item=%d authentic DLC/model wait expired; stopping this click without forcing playback'
                  % item_id, 1)
        panpan_stop_playing()
        return False
    if panpan_model_playing():
        pending.clear()
        return True
    panpan_hall_playing(owner, (1, guid))
    completed = not bool(pending)
    if completed:
        _v109_log(('playpal-wheel-dlc-ready', item_id),
                  'native PlayPal wheel item=%d official DLC/model event completed; retry cleared'
                  % item_id, 2)
    return completed

def panpan_readback(owner, item_id, guid):
    """Read the official armed/direct/resolved PlayPal state, never a UI hint."""
    armed = _V109_MISSING
    direct = None
    resolved = None
    random = None
    try:
        armed = getattr(owner, 'arm_panpan', _V109_MISSING)
        random = bool(getattr(owner, 'arm_panpan_random', False))
        direct_getter = getattr(owner, 'get_arm_panpan_item_id', None)
        resolved_getter = getattr(owner, 'get_arm_panpan_resolved_item_id', None)
        direct = direct_getter() if callable(direct_getter) else None
        resolved = (resolved_getter() if callable(resolved_getter)
                    else None)
        ok = (armed == guid and not random and callable(resolved_getter)
              and _v109_int(resolved, 0) == item_id)
    except Exception:
        ok = False
    return ok, (armed, direct, resolved, random)


def panpan_notify(owner, old_guid):
    """Run the official PlayPal update notification after a local field write.

    Property registration alone does not prove that a Python-level component
    write ran _on_set_arm_panpan.  The native callback is idempotent for an
    unchanged resolved item and refreshes Warehouse/model listeners.  Use the
    same messenger event directly only when the component callback is absent.
    """
    try:
        callback = getattr(owner, '_on_set_arm_panpan', None)
        if callable(callback):
            callback(old_guid)
            return 'official-callback'
    except Exception:
        pass
    try:
        helper = globals().get('_game_genv')
        root = helper() if callable(helper) else globals().get('genv')
        messenger = getattr(root, 'messenger', None)
        broadcast = getattr(messenger, 'Broadcast', None)
        events = sys.modules.get('gclient.framework.util.events')
        event = getattr(events, 'ON_ARM_PANPAN_UPDATE', None)
        if callable(broadcast) and event is not None:
            broadcast(event)
            return 'official-event'
    except Exception:
        pass
    return 'unavailable'


def panpan_remember_pick(item_id, persist=True):
    """Remember a direct injected PlayPal item, never its session GUID."""
    try:
        item_id = _v109_int(item_id, 0)
        previous = _v109_int(PANPAN_SAVED.get('item_id'), 0)
        if item_id:
            if previous and previous != item_id:
                panpan_stop_playing()
            PANPAN_SAVED.update(
                {'item_id': item_id, 'random': False})
        else:
            panpan_stop_playing()
            if previous:
                # A genuine later RPC/unequip owns the whole linked state;
                # do not later restore only its random-favorite baseline.
                _v109_state.get('equip_restore', {}).pop(previous, None)
            PANPAN_SAVED.clear()
        if persist:
            persist_pick('P', 0, 0, item_id)
        return True
    except Exception:
        return False


# Native injected melee -> authentic combat CItem/case refresh.
# The swap is local, transactional, and limited to genv.player's melee slot.
MELEE_VISUAL = {}
MELEE_VISUAL_TICK = [0.0]
MELEE_COMBAT_ID_CACHE = {}
# One bounded lazy load for the official equip table used by the target-class
# check; a failure is remembered so a missing module cannot cause a retry
# storm on every frame of the visual pump.
MELEE_EQUIP_DATA = {'retry': 0.0, 'failed': False}


def native_game_dispatch(name, fn, *args):
    """Execute native object work on the established game-thread pump.

    Worker callers never wait here: lobby hooks and the match post-tick drain
    the same bounded queue, and _game_post coalesces repeated visual requests.
    Host/main-thread tests retain direct execution through the established
    safe-thread helper.
    """
    try:
        safe = safe_game_thread()
    except Exception:
        safe = False
    if safe:
        # Do not catch a native transaction failure and execute it a second
        # time through the queue; its own rollback/recovery contract owns it.
        return fn(*args)
    _game_post(name, fn, *args)
    return None


# #======================================================================
# //  MELEE.PY
# //
# //  This file is for: MELEE VISUAL: the genuine-GUID melee visual chain (the clone, the case repair, the dual/replay case targets, the DLC readiness).
# //
# //  Part of the split TREACKY BS payload (v2.112).  The runtime
# //  file payload/skins_payload.py is GENERATED: run
# //  tools/build_payload.py after editing these modules.
# #======================================================================
