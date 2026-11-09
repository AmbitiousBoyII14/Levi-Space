# ============================================================
# CONFIG.PY
# PROVIDES: sync_attrs (ABI), SyncAttrsDict, DEFAULTS, KEY_GROUPS,
#           register_scene_gate, register_update_listener, apply_update
# REQUIRES: main.log_line is optional (boot-log guarded)
# ABI: sync_attrs is the UDP-50000 config surface read by every module.
# ============================================================
"""Configuration schema for the payload.

The menu (C++) owns persistence and sends flat JSON updates over UDP 50000;
this module owns the schema: every key the payload understands, its default,
and its group. Two policy behaviours are preserved from the proven engine:

* ``bStrikerRepaint`` is RETIRED (v8.03): a saved ON value from old testing
  re-armed the legacy force pile and looped the lobby model into a crash.
  The key is accepted but always reads False.
* ``bHeroSkinHack`` is the master striker switch AND is scene-gated: the
  stored value is the master; the per-scene answer comes from the registered
  scene gate (registered by striker_skin.py). Without a gate it reads the
  stored value.

Dynamic keys arrive from the menu and are schema'd by pattern:
  iSkin_<equip_id>       weapon-row selection index (1-based)
  iHeroSkin_<hero_id>    hero-row selection index (1-based)
"""
import json as _json
import threading as _threading

# ---- key groups (documentation + menu grouping) ---------------------
KEY_GROUPS = {
    'core': ('bSkinHack', 'bForceFX', 'bDebugLog', 'iDebugDump'),
    'esp': ('bESP', 'bESP_AI', 'bESP_Players', 'bESP_Box', 'bESP_Health',
            'bESP_Armor', 'bESP_Distance', 'bESP_Name', 'bESP_Weapon',
            'bESP_Skeleton', 'bESP_Lane', 'bESP_Radar', 'bESP_Count',
            'bVisCheck', 'bLootESP', 'fESP_MaxDistance', 'fESP_MaxDist',
            'fESPBoxThickness', 'fESP_TextScale', 'fESP_RadarSize',
            'fESP_RadarRange', 'fLootESP_MaxDist'),
    'aim': ('bAIM', 'bAIM_Lane', 'bAIM_Dot', 'bAIM_AutoFire',
            'bAIM_AutoTune', 'bAIM_CheckVisibility', 'bAIM_IgnoreBots',
            'bAIM_IgnoreKnocked', 'bAIM_Prediction', 'bAIM_SafeMode',
            'bAIM_Trigger', 'iAIM_TargetBone', 'fAIM_Fov', 'fAIM_MaxDist',
            'fAIM_SnapStrength'),
    'weapon': ('bAttachmentHack', 'iAttachmentWeapon',
               'iAttachmentCatalogNonce', 'iAttachmentInjectNonce',
               'iAttachmentMaxNonce', 'bSpecialOpticHack',
               'iSpecialOpticWeapon', 'iSpecialOpticCatalogNonce',
               'iSpecialOpticApplyNonce', 'iSpecialOpticRestoreNonce',
               'iNativeWeaponNonce', 'iNativeWeaponIndex',
               'iNativeWeaponEquip', 'iNativeWeaponAction', 'iRecentWeapon',
               'iSkinEquipNonce', 'iSkinMeleeSource'),
    'striker': ('bStrikerHack', 'bHeroSkinHack', 'bStrikerLobby',
                'bStrikerEmote', 'bStrikerMatch', 'bStrikerRepaint',
                'bHeroReassert', 'iHeroEquipNonce', 'iRecentStrikerHero'),
    'unlock': ('bUnlockAll', 'bUnlockAllVault', 'bUnlockMelee',
               'bUnlockHeroes', 'bUnlockEmote', 'bUnlockEmotes',
               'bUnlockExecution', 'bUnlockAvatar', 'bUnlockBanner',
               'bUnlockGlide', 'bUnlockGrenades', 'bUnlockLoadoutDrop',
               'bEmoteHack', 'bExecHack', 'iEmoteSel',
               'bCosmeticUnlockProfile', 'bCosmeticUnlockOther'),
    'ui': ('bCrosshair', 'bCrosshairOutline', 'bHideFovCircle',
           'fCrosshairSize', 'fCrosshairThickness', 'fFontSize',
           'fScrollbarSize', 'bDefaultsV56', 'bR19Migrated', 'bR5Migrated'),
    'diag': ('iEspRx', 'iEspRxInit', 'iEspRxFail', 'iEspRxEnts',
             'iEspRxDrawn', 'bIdsScan'),
}

# ---- defaults -------------------------------------------------------
DEFAULTS = {
    # core
    'bSkinHack': False, 'bAttachmentHack': False, 'bForceFX': False,
    'bDebugLog': False, 'iDebugDump': 0,
    # weapon nonces (menu actions arrive as incrementing nonces)
    'iHeroEquipNonce': 0, 'iSkinEquipNonce': 0,
    'iAttachmentWeapon': 0, 'iAttachmentCatalogNonce': 0,
    'iAttachmentInjectNonce': 0, 'iAttachmentMaxNonce': 0,
    'bSpecialOpticHack': False, 'iSpecialOpticWeapon': 0,
    'iSpecialOpticCatalogNonce': 0, 'iSpecialOpticApplyNonce': 0,
    'iSpecialOpticRestoreNonce': 0,
    # striker (master switch default ON = the original single switch)
    'bStrikerHack': True, 'bHeroSkinHack': True,
    'bStrikerLobby': True, 'bStrikerEmote': True, 'bStrikerMatch': True,
    'bStrikerRepaint': False,          # retired - see module docstring
    # esp
    'bVisCheck': True, 'bLootESP': False, 'bIdsScan': False,
    # emotes / executions / unlocks
    'bEmoteHack': False, 'iEmoteSel': 0,
    'bUnlockMelee': True, 'bUnlockHeroes': True, 'bExecHack': False,
    # diag counters
    'iEspRx': 0, 'iEspRxInit': 0, 'iEspRxFail': 0, 'iEspRxEnts': 0,
    'iEspRxDrawn': 0,
}

_DYNAMIC_PREFIXES = ('iSkin_', 'iHeroSkin_')


class SyncAttrsDict(dict):
    """Config dict with the two preserved policy behaviours (see module
    docstring). Everything else is a plain dict."""

    def __init__(self, *a, **k):
        dict.__init__(self, *a, **k)
        self._scene_gate = None

    # -- policy slots (registered by feature modules) -----------------
    def set_scene_gate(self, gate):
        """gate() -> bool: may striker hooks force in the current scene?"""
        self._scene_gate = gate

    def get(self, key, default=None):
        if key == 'bStrikerRepaint':
            # RETIRED (v8.03): a saved ON re-armed the legacy force pile
            # and crashed the lobby model loop. Always reads False.
            return False
        if key == 'bHeroSkinHack':
            if not dict.get(self, 'bHeroSkinHack', False):
                return default if default is not None else False
            # registered gate (striker_skin.py W4) or the shared-namespace
            # legacy gate (display.py) - same globals dict at runtime
            gate = self._scene_gate or globals().get('_striker_scene_gate')
            if gate is not None:
                try:
                    return bool(gate())
                except Exception:
                    return True
            return True
        return dict.get(self, key, default)

    def __getitem__(self, key):
        if key == 'bHeroSkinHack':
            return self.get(key, False)
        return dict.__getitem__(self, key)


sync_attrs = SyncAttrsDict(DEFAULTS)

# ---- update pipeline (UDP thread -> listeners) ----------------------
_update_listeners = []
_update_lock = _threading.Lock()


def register_update_listener(fn):
    """fn(parsed_dict) runs after every batch update (e.g. re-apply picks)."""
    with _update_lock:
        if fn not in _update_listeners:
            _update_listeners.append(fn)


def apply_update(parsed):
    """Apply one decoded JSON config batch and notify listeners."""
    if not isinstance(parsed, dict):
        return
    sync_attrs.update(parsed)
    with _update_lock:
        listeners = list(_update_listeners)
    for fn in listeners:
        try:
            fn(parsed)
        except Exception:
            pass


def register_scene_gate(gate):
    sync_attrs.set_scene_gate(gate)


def validate_key(key):
    """True when the key is part of the schema (static or dynamic)."""
    if key in DEFAULTS:
        return True
    for group_keys in KEY_GROUPS.values():
        if key in group_keys:
            return True
    return any(key.startswith(p) and key[len(p):].isdigit()
               for p in _DYNAMIC_PREFIXES)


def snapshot():
    """Flat copy for diagnostics."""
    return dict(sync_attrs)
