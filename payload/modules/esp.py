# ============================================================
# ESP.PY (payload feature module)
# PROVIDES: _install_esp_enter_hook, _utc_stamp, _esp_space, WorldToScreenPoint, IsVisible, _vis_cache_clear, _is_visible_cached, _get_item_id, _esp_float, EspUpdate, _aim_bone_for, _aim_sniper_snap, _cond_hash, AIM_AutoTune, ... +24 more | PAYLOAD_BUILD_TAG, PAYLOAD_BUILD, _ESP_BONES, _ESP_BOX_BONES, _VIS_CACHE_TTL, _AI_TUNE_INTERVAL, _AIM_MAX_LEAD_TIME, _AIM_MIN_DT, _AIM_MAX_DT, _AI_MODE_INT, ...
# REQUIRES: shared namespace (config/names/main/game_api/catalog);
#           game modules imported inline, verified against the dumps.
# ABI: 50001 JSON keys frozen (sync_entities.h).
# ============================================================
"""ESP + AIM feature: player info, distance, visibility, skeleton, box/radar, counters; publishes the 50001 JSON per the sync_entities schema; builds the aim frame."""

# #======================================================================
# //  ESP.PY
# //
# //  This file is for: ESP + AIMBOT: the entity feed (UDP 50001 to C++), the ESP hooks, the aim settings, the ESP diagnostics.
# //
# //  Part of the split TREACKY BS payload (v2.112).  The runtime
# //  file payload/skins_payload.py is GENERATED: run
# //  tools/build_payload.py after editing these modules.
# #======================================================================
def _install_esp_enter_hook():
    cls = globals().get('PlayerCombatAvatar', None)
    if cls is None or cls is _Missing:
        return False
    if getattr(cls, '_treacky_esp_enter', False):
        return True

    def _make(_cls):
        def on_enter_space(self, *a, **k):
            r = getattr(_cls, '_on_enter_space')(self, *a, **k)
            try:
                _ensure_space_tick_registered()
            except Exception:
                pass
            return r
        return on_enter_space

    fn = _make(cls)
    fn.__name__ = 'on_enter_space'
    try:
        HOOK(cls, 0)(fn)
        cls._treacky_esp_enter = True
        _plog('[ESP-TICK] PlayerCombatAvatar.on_enter_space hooked')
        return True
    except Exception as e:
        _plog('[ESP-TICK] enter hook failed: %r' % (e,))
        return False


try:
    _install_esp_enter_hook()
except Exception:
    pass
try:
    _ensure_space_tick_registered()
except Exception:
    pass

PAYLOAD_BUILD_TAG = "v2.121"
_plog("[PAYLOAD] LEVI by Treacky payload %s ready + ESP/Aimbot"
      % PAYLOAD_BUILD_TAG)


# ============================================================
# v2.8 SESSION STAMP - every log line carries it, so an old log line can
# never be mistaken for current evidence (the user's de-mixing rule).
# ============================================================
PAYLOAD_BUILD = "NEXORA-SRC-v10.12.2-split-r1"  # base: NEXORA-SRC-v8.52-pairicon6

def _utc_stamp():
    try:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    except Exception:
        return "?"

# ============================================================
# ESP + AIMBOT (v2.7.2: transplanted from the v2.7 full build onto the fixed
# skins payload. _game_genv / _local_combat_avatar / Distance / _esp_space /
# _space_tick_spaces / _ensure_space_tick_registered / on_space_tick are NOT
# redefined here - the skins section above already provides them, and its
# _ensure_space_tick_registered is the throttled, weakref-based v2.7.2 one.)
# Emotes and Executions are NOT part of this block and stay removed.
# Python runs on the game thread via Space.AddSpacePostTick.
# ESP entities are sent as JSON on UDP 50001 to sync_entities.h;
# Aimbot rotates the real FPS camera placer (client-side only).
# ============================================================

_ESPCombatAvatar = None
_ESPPlayerCombatAvatar = None
_ESPFpsPlacer = None
_ESPIsPlayerTeammate = None
_ESPDistance3D = None
_esp_lid = None
_esp_aim_installed = [False]
_esp_aim_attempts = [0]
_esp_frame_count = [0]
_esp_error_count = [0]
_aim_error_count = [0]
_aim_diag_count = [0]

_ESP_BONES = [
    ('head',      'biped Head'),
    ('neck',      'biped Neck'),
    ('spine',     'biped Spine'),
    ('spine1',    'biped Spine1'),
    ('pelvis',    'biped Pelvis'),
    ('lshoulder', 'biped L UpperArm'),
    ('rshoulder', 'biped R UpperArm'),
    ('lforearm',  'biped L Forearm'),
    ('rforearm',  'biped R Forearm'),
    ('lhand',     'biped L Hand'),
    ('rhand',     'biped R Hand'),
    ('lthigh',    'biped L Thigh'),
    ('rthigh',    'biped R Thigh'),
    ('lknee',     'biped L Calf'),
    ('rknee',     'biped R Calf'),
    ('lfoot',     'biped L Foot'),
    ('rfoot',     'biped R Foot'),
]
_ESP_BOX_BONES = ('head', 'spine', 'spine1', 'pelvis', 'lfoot', 'rfoot')

def _esp_space():
    # v2.7.2: same lookup as _game_space() (skins section); kept as its own
    # name because the ESP/Aimbot code below calls it directly.
    genv_obj = _game_genv()
    try:
        space = getattr(genv_obj, 'space', None)
        if space is not None:
            return space
    except Exception:
        pass
    try:
        return getattr(Space, '_instance', None)
    except Exception:
        return None


def WorldToScreenPoint(worldpos):
    space = _esp_space()
    return space.camera.engine_camera.GetScreenPointFromWorldPoint(worldpos)

def IsVisible(local, target, targetId, distance=100):
    space = _esp_space()
    raycast = space.RawRaycast(local, distance, 19, with_trigger=False, to_pos=target)
    ownerid = getattr(getattr(raycast, 'Body', None), 'ownerid', None)
    if getattr(raycast, 'Body', None) and ownerid:
        return ownerid == targetId
    return getattr(raycast, 'Flags', None) == 7


# v7.30R20: visibility raycasts were the per-frame cost that did not
# exist before R19 (bVisCheck default ON + aim check_vis + the aim bone
# pool each raycast per entity PER FRAME - the R19 device log shows the
# 0.4-0.5 s game-thread stalls right around EspUpdate/aim frames).
# One shared cache: per entity id, result held for 0.30 s. The [W]
# marker and the aim gate read the same cached answer.
_vis_cache = {}
_VIS_CACHE_TTL = 0.30


def _vis_cache_clear():
    try:
        _vis_cache.clear()
    except Exception:
        pass


def _is_visible_cached(local, target, targetId, distance=100):
    """IsVisible with a 0.30 s per-entity cache. Falls back to a raw
    raycast on any cache trouble - never to a wrong True."""
    try:
        key = (str(targetId),)
        now = time.time()
        hit = _vis_cache.get(key)
        if hit is not None and now < hit[1]:
            return hit[0]
        result = bool(IsVisible(local, target, targetId, distance))
        if len(_vis_cache) > 160:
            try:
                _vis_cache.clear()
            except Exception:
                pass
        _vis_cache[key] = (result, now + _VIS_CACHE_TTL)
        return result
    except Exception:
        try:
            return bool(IsVisible(local, target, targetId, distance))
        except Exception:
            return True

def _get_item_id(entity):
    for attr in ('item_id', 'gid', 'id', 'proto_id'):
        try:
            value = getattr(entity, attr, None)
            if value:
                return int(value)
        except Exception:
            continue
    return 0

def _esp_float(key, default):
    try:
        return float(sync_attrs.get(key, default))
    except Exception:
        return float(default)

_esp_scan_frame = [0]
_esp_found_last = [0]


_esp_gate100 = [0.0, 0.25]


def EspUpdate(*_, **__):
    try:
        # v2.128: ESP-off means ESP-off - no aim-ESP bleed-through.
        # If ESP is disabled, bail before touching the entity list.
        # Aim-ESP (aim_point overlay) now lives under the ESP toggle,
        # not the Aimbot toggle (user request).  Camera-rotation aimbot
        # lives in AIMUpdate and has its own bAIM gate.
        if not bool(sync_attrs.get('bESP', False)):
            return

        # v2.100: the 10-20 FPS fix - the scan walks every entity on
        # every game tick.  v2.103: scans measure 0.05-0.20s each
        # ('[STALL] EspUpdate took 0.20s' x23 in the round-120 log),
        # so the 100ms gate still ran back-to-back.  250ms (4Hz) gives
        # the game tick real breathing room.
        _now100 = time.time()
        if _now100 - _esp_gate100[0] < _esp_gate100[1]:
            return
        _esp_gate100[0] = _now100
        # v8.16: with 0 players found two scans in a row, scan
        # every 3rd tick only. The v8.15 device burned 50-80 ms PER
        # TICK walking every hall entity with nobody there - the
        # 'kinda laggy' home screen.
        _esp_scan_frame[0] += 1
        if _esp_found_last[0] <= 0 and (_esp_scan_frame[0] % 3):
            return
        if _ESPCombatAvatar is None or _ESPIsPlayerTeammate is None:
            return
        inst = _esp_space()
        genv_obj = _game_genv()
        if inst is None or not getattr(inst, 'entities', None) or not getattr(genv_obj, 'avatar', None):
            return
        localEntity = _local_combat_avatar()
        if not localEntity or not hasattr(localEntity, 'model'):
            return

        _cam = inst.camera
        _cp = _cam.position
        cam_pos = (_cp.x, _cp.y, _cp.z)
        _eng_cam = _cam.engine_camera
        _bVisCheck = bool(sync_attrs.get('bVisCheck', False))
        _bSkeleton = bool(sync_attrs.get('bESP_Skeleton', False))
        _bBox = bool(sync_attrs.get('bESP_Box', True))
        _MAX_DIST = _esp_float(
            'fESP_MaxDistance', _esp_float('fESP_MaxDist', 500.0))
        _bLootESP = bool(sync_attrs.get('bLootESP', False))
        _LOOT_MAX_DIST = _esp_float('fLootESP_MaxDist', 120.0)
        entities = []

        def get_bone_screen(model, bone_name):
            try:
                wp = model.GetBoneWorldPosition(bone_name)
                if not wp:
                    return None
                sp = _eng_cam.GetScreenPointFromWorldPoint(wp)
                return [sp.x, sp.y] if sp.z > 0.0 else None
            except Exception:
                return None

        for entity_id, entity in list(inst.entities.items()):
            try:
                if _bLootESP and getattr(entity, 'IsItem', False):
                    try:
                        pos = getattr(entity, 'position', None) or getattr(entity, 'pos', None)
                        if pos:
                            wpos = (pos.x, pos.y, pos.z)
                            dist_i = Distance(cam_pos, wpos)
                            if dist_i <= _LOOT_MAX_DIST:
                                screen = _eng_cam.GetScreenPointFromWorldPoint(pos)
                                is_on_screen_i = screen.z > 0.0
                                item_id = _get_item_id(entity)
                                item_proto = _data_get(
                                    getattr(_esp_lid, 'data', None), item_id, {}) if item_id else {}
                                item_label = _proto_english_name(
                                    item_proto,
                                    ('en_name', 'english_name', 'name_en', 'name'),
                                    'Item')
                                try:
                                    item_count = int(
                                        getattr(entity, 'count', 0) or
                                        getattr(entity, 'item_count', 0) or 1)
                                except Exception:
                                    item_count = 1
                                entities.append({
                                    'is_item': True,
                                    'item_id': item_id or _safe_int(entity_id, 0),
                                    'item_label': item_label,
                                    'item_count': item_count,
                                    'name': item_label,
                                    'worldpos': [wpos[0], wpos[1], wpos[2]],
                                    'distance': dist_i,
                                    'is_on_screen': is_on_screen_i,
                                    'is_alive': True,
                                    'bones': {'head': [screen.x, screen.y]} if is_on_screen_i else {},
                                })
                    except Exception:
                        pass
                    continue

                if not isinstance(entity, _ESPCombatAvatar):
                    continue
                if not getattr(entity, 'model', None) or not getattr(entity, 'is_alive', False):
                    continue
                try:
                    if _ESPIsPlayerTeammate(entity_id):
                        continue
                except Exception:
                    continue

                entityHeadPos = entity.model.GetBoneWorldPosition('biped Head')
                if not entityHeadPos:
                    continue
                head_world = (entityHeadPos.x, entityHeadPos.y, entityHeadPos.z)
                dist_e = Distance(cam_pos, head_world)
                if dist_e > _MAX_DIST:
                    continue

                model = entity.model
                head_screen = _eng_cam.GetScreenPointFromWorldPoint(entityHeadPos)
                is_on_screen = head_screen.z > 0.0
                bones = {}
                if is_on_screen:
                    bones['head'] = [head_screen.x, head_screen.y]
                    if _bSkeleton:
                        for key, bone_name in _ESP_BONES:
                            point = get_bone_screen(model, bone_name)
                            if point:
                                bones[key] = point
                    elif _bBox:
                        for key, bone_name in _ESP_BONES:
                            if key not in _ESP_BOX_BONES:
                                continue
                            point = get_bone_screen(model, bone_name)
                            if point:
                                bones[key] = point

                player_name = _display_text(getattr(entity, 'name', 'Unknown'), 'Unknown')
                is_bot = bool(getattr(entity, 'IsRobotCombatAvatar', False))
                is_zombie = bool(getattr(entity, 'IsRobotCombatAvatarZombie', False))
                hp = float(getattr(entity, 'hp', 0) or 0)
                maxhp = float(getattr(entity, 'cur_maxhp', 100) or 100)
                armor = float(getattr(entity, 'armor', 0.0) or 0.0)
                is_knocked = bool(getattr(entity, 'is_dying_state', False))
                weapon_name = 'Punk'
                try:
                    weapon = entity.GetCurWeapon()
                    if weapon:
                        weapon_name = _english_display_text(
                            WEP_NAMES.get(int(weapon.equip_id), 'Punk'), 'Punk')
                except Exception:
                    pass
                if _bVisCheck:
                    try:
                        is_visible = bool(_is_visible_cached(_cp, entityHeadPos, getattr(entity, 'id', entity_id), dist_e))
                    except Exception:
                        is_visible = True
                else:
                    is_visible = True

                # v2.125: AI/players are separate ESP toggles, fully
                # independent of the HP element (operator request).
                _show_ai25 = bool(sync_attrs.get('bESP_AI', True))
                _show_pl25 = bool(sync_attrs.get('bESP_Players', True))
                if (is_bot or is_zombie) and not _show_ai25:
                    continue
                if not (is_bot or is_zombie) and not _show_pl25:
                    continue
                entities.append({
                    'name': player_name,
                    'is_zombie': is_zombie,
                    'is_bot': is_bot,
                    'is_teammate': False,
                    'worldpos': [head_world[0], head_world[1], head_world[2]],
                    'distance': dist_e,
                    'is_on_screen': is_on_screen,
                    'bones': bones,
                    'is_visible': is_visible,
                    'is_alive': True,
                    'is_knocked': is_knocked,
                    'is_health': hp,
                    'cur_maxhp': maxhp,
                    'is_armor': armor,
                    'is_titan': maxhp >= 2000.0,
                    'weapon_name': weapon_name,
                })
            except Exception:
                continue

        aim_point = {'valid': False}
        try:
            _visual_point = globals().get('_aim_visual_point', [None])[0]
            _visual_time = globals().get('_aim_visual_time', [0.0])[0]
            if _visual_point is not None and (time.time() - _visual_time) <= 0.15:
                aim_point = {
                    'valid': True,
                    'x': float(_visual_point[0]),
                    'y': float(_visual_point[1]),
                    'target_id': str(globals().get('_aim_visual_target', [None])[0] or ''),
                    'bone': str(globals().get('_aim_visual_bone', [''])[0] or ''),
                }
        except Exception:
            pass
        _cam_euler = getattr(_cam, 'euler_angles', None)
        _cam_yaw = float(getattr(_cam_euler, 'y', 0.0) or 0.0) if _cam_euler else 0.0
        payload = json.dumps({
            'players': entities,
            'world_name': _display_text(getattr(inst, 'world_name', 'Unknown'), 'Unknown'),
            'real_world_name': _display_text(getattr(inst, 'real_world_name', ''), ''),
            'is_moba_map': bool(getattr(inst, 'is_moba_map', False)),
            'is_replaying': bool(getattr(inst, 'is_replaying', False)),
            'total_entities': len(inst.entities),
            'cam_yaw': _cam_yaw,
            'screen_w': _esp_float('fWidth', 1080.0),
            'screen_h': _esp_float('fHeight', 720.0),
            'aim_point': aim_point,
        }, separators=(',', ':')) + '\n'
        _write_udp_esp(payload)
        _esp_frame_count[0] += 1
        # v8.16: feeds the idle throttle (0 players found -> scan
        # every 3rd tick - see the top of EspUpdate).
        try:
            _esp_found_last[0] = len(entities)
        except Exception:
            pass
        if _esp_frame_count[0] == 1 or _esp_frame_count[0] % 600 == 0:
            _plog('[ESP] frame=%d sent entities=%d total=%d max_dist=%.0f'
                  % (_esp_frame_count[0], len(entities), len(inst.entities), _MAX_DIST))
    except Exception:
        _esp_error_count[0] += 1
        if _esp_error_count[0] <= 3:
            _plog('[ESP] EspUpdate error:\n%s' % (_exc_text(),))

FpsPlacerInstance = None
_ai_last_hash = 0
_ai_idle_frames = 0
_ai_tune_frame = 0
_AI_TUNE_INTERVAL = 30
_aim_pos_track = {}
_AIM_MAX_LEAD_TIME = 0.6
_AIM_MIN_DT = 0.02
_AIM_MAX_DT = 0.25

_AI_MODE_INT = {
    'idle': 0, 'close': 1, 'mid': 2, 'long': 3, 'sniper': 4,
    'smg': 5, 'cqc': 6, 'rush': 7, 'shotgun': 8, 'melee': 9,
    'sky': 10, 'vehicle': 11, 'dmr': 3,
}
_AIM_BONE_MAP = {
    0: 'biped Head', 1: 'biped Neck', 2: 'biped Spine1',
    3: 'biped Spine', 4: 'biped Pelvis',
}
_AIM_RANDOM_BONES = tuple(_AIM_BONE_MAP.values())
_aim_random_by_target = {}
_aim_visual_point = [None]
_aim_visual_bone = ['']
_aim_visual_target = [None]
_aim_visual_time = [0.0]

def _aim_bone_for(entity_id, selected_index, entity=None, camera_pos=None,
                  dist3d=None, sniper_mode=False):
    selected_index = _safe_int(selected_index, 5)
    # v7.30R19: SNIPERS -> head and neck ONLY. Any other selected bone is
    # overridden by the head/neck random pool while a sniper is out.
    if sniper_mode and selected_index not in (0, 1):
        selected_index = 5
    if selected_index != 5:
        return _AIM_BONE_MAP.get(selected_index, 'biped Neck')
    now = time.time()
    key = str(entity_id)
    entry = _aim_random_by_target.get(key)
    if entry is None or now >= entry[1]:
        # v7.21: "random" now means random among the parts that are
        # actually VISIBLE - a raycast per bone at re-roll cadence. If
        # nothing is confirmably visible, stay on the high pair. And with
        # a sniper scope the pool is the upper body only, held longer:
        # re-rolling the spot every 0.1 s at 8x zoom was the crosshair
        # "tweaking" (it chased the re-roll, not the enemy).
        pool = list(_AIM_RANDOM_BONES)
        hold = 0.25
        if sniper_mode:
            pool = ['biped Head', 'biped Neck']
            hold = 0.30
        try:
            if (entity is not None and camera_pos is not None
                    and dist3d is not None):
                _vis = []
                for _b in pool:
                    _bp = entity.model.GetBoneWorldPosition(_b)
                    if _bp and _is_visible_cached(camera_pos, _bp,
                                                  getattr(entity, 'id', entity_id),
                                                  dist3d):
                        _vis.append(_b)
                if _vis:
                    pool = _vis
                else:
                    pool = ['biped Head', 'biped Neck']
        except Exception:
            pass
        bone = random.choice(pool)
        # v7.16: each random spot is held for 0.1 s, then re-rolled.
        # v7.21: 0.45 s while scoped.
        _aim_random_by_target[key] = (bone, now + hold, now)
        if len(_aim_random_by_target) > 128:
            for old_key in [k for k, v in list(_aim_random_by_target.items()) if now - v[2] > 3.0]:
                _aim_random_by_target.pop(old_key, None)
        return bone
    _aim_random_by_target[key] = (entry[0], entry[1], now)
    return entry[0]
_AIM_SNIPER_IDS = frozenset({39, 47, 77, 103, 122, 45, 133})
_AIM_SHOTGUN_IDS = frozenset({34, 41, 79, 126})
_AIM_SMG_IDS = frozenset({2, 65, 67, 90, 110, 129})
_AIM_MELEE_IDS = frozenset({33, 84, 95, 96, 97, 106, 107, 112, 131, 134})
_aim_snap_stash = [None]     # v8.06: sniper auto-snap restore value


def _aim_sniper_snap(localEntity):
    """v8.06: holding a sniper -> the aim snap auto-sets to 0.5. The
    previous value is restored when switching away; moving the slider
    manually while sniping hands control back to the user."""
    try:
        wid = 0
        try:
            w = localEntity.GetCurWeapon()
            wid = int(getattr(w, 'equip_id', 0) or 0) if w else 0
        except Exception:
            wid = 0
        cur = round(float(sync_attrs.get('fAIM_SnapStrength', 3.0)
                          or 3.0), 2)
        if wid in _AIM_SNIPER_IDS:
            if _aim_snap_stash[0] is None:
                _aim_snap_stash[0] = cur if abs(cur - 0.5) > 0.005 \
                    else None
                sync_attrs.update({'fAIM_SnapStrength': 0.5})
            elif abs(cur - 0.5) > 0.005:
                _aim_snap_stash[0] = None      # user took over
            else:
                sync_attrs.update({'fAIM_SnapStrength': 0.5})
        elif _aim_snap_stash[0] is not None:
            sync_attrs.update({'fAIM_SnapStrength': _aim_snap_stash[0]})
            _aim_snap_stash[0] = None
    except Exception:
        pass


_AIM_PRESETS = {
    'sniper': dict(snap=0.5, fov=45.0, pred=True, bone=0, bspd=900.0),
    'long': dict(snap=1.2, fov=80.0, pred=True, bone=0, bspd=700.0),
    'mid': dict(snap=2.0, fov=120.0, pred=True, bone=1, bspd=650.0),
    'smg': dict(snap=3.0, fov=150.0, pred=True, bone=2, bspd=500.0),
    'close': dict(snap=2.5, fov=140.0, pred=True, bone=1, bspd=600.0),
    'shotgun': dict(snap=3.5, fov=170.0, pred=False, bone=2, bspd=400.0),
    'cqc': dict(snap=4.5, fov=190.0, pred=False, bone=2, bspd=400.0),
    'rush': dict(snap=5.0, fov=200.0, pred=False, bone=2, bspd=500.0),
    'melee': dict(snap=6.0, fov=200.0, pred=False, bone=4, bspd=300.0),
    'sky': dict(snap=2.0, fov=160.0, pred=True, bone=1, bspd=600.0),
    'vehicle': dict(snap=3.5, fov=180.0, pred=True, bone=2, bspd=700.0),
}

def _cond_hash(mode, ec, ads, sprint, pose, hp_low, veh, sky):
    return hash((mode, min(ec, 6), ads, sprint, pose, hp_low, veh, sky))

def AIM_AutoTune(localEntity, enemy_data):
    global _ai_last_hash, _ai_idle_frames
    if not sync_attrs.get('bAIM_AutoTune', False):
        return
    try:
        if not enemy_data:
            _ai_idle_frames += 1
            if _ai_idle_frames > 10:
                sync_attrs.update({
                    'iAI_Mode': 0, 'iAI_EnemyCount': 0,
                    'bAI_Active': False, 'bAI_Changed': False,
                })
                _aim_pos_track.clear()
            return
        _ai_idle_frames = 0
        dists = [e['dist'] for e in enemy_data]
        avg_dist = sum(dists) / len(dists)
        min_dist = min(dists)
        enemy_count = len(enemy_data)
        try:
            weapon = localEntity.GetCurWeapon()
            wid = int(weapon.equip_id) if weapon else 0
        except Exception:
            wid = 0
        is_ads = bool(getattr(localEntity, 'is_ads', False))
        is_sprint = bool(getattr(localEntity, 'is_sprint', False))
        is_sky = bool(getattr(localEntity, 'is_on_sky', False))
        is_veh = bool(getattr(localEntity, 'is_vehicle_driver', False)) or bool(
            getattr(localEntity, 'is_vehicle_passenger', False))
        pose_type = _safe_int(getattr(localEntity, 'pose_type', 0), 0)
        my_hp = float(getattr(localEntity, 'hp', 100) or 100)
        my_maxhp = float(getattr(localEntity, 'cur_maxhp', 100) or 100)
        hp_low = (my_hp / max(my_maxhp, 1.0)) < 0.35
        try:
            optic = int(localEntity.GetCurWeaponPartOpticType() or 0)
        except Exception:
            optic = 0

        if wid in _AIM_MELEE_IDS:
            mode = 'melee'
        elif is_sky:
            mode = 'sky'
        elif is_veh:
            mode = 'vehicle'
        elif wid in _AIM_SNIPER_IDS and optic >= 4:
            mode = 'sniper'
        elif wid in _AIM_SHOTGUN_IDS:
            mode = 'shotgun'
        elif wid in _AIM_SMG_IDS and min_dist < 20:
            mode = 'cqc'
        elif wid in _AIM_SMG_IDS:
            mode = 'smg'
        elif min_dist < 10:
            mode = 'cqc'
        elif enemy_count >= 4 and avg_dist < 50:
            mode = 'rush'
        elif avg_dist > 120:
            mode = 'long'
        elif avg_dist > 60:
            mode = 'mid'
        else:
            mode = 'close'

        preset = dict(_AIM_PRESETS.get(mode, _AIM_PRESETS['mid']))
        mod_flags = 0
        if enemy_count >= 3:
            preset['fov'] = min(preset['fov'] + 30.0, 220.0)
            mod_flags |= (1 << 4)
        if is_sprint:
            preset['snap'] = min(preset['snap'] * 1.5, 12.0)
            mod_flags |= (1 << 0)
        if is_ads and mode not in ('sniper', 'long'):
            preset['snap'] = max(preset['snap'] * 0.8, 0.5)
            mod_flags |= (1 << 1)
        if pose_type == 2:
            preset['snap'] = max(preset['snap'] * 0.7, 0.4)
            preset['fov'] = max(preset['fov'] - 20.0, 30.0)
            mod_flags |= (1 << 2)
        if hp_low:
            preset['snap'] = min(preset['snap'] * 1.3, 12.0)
            mod_flags |= (1 << 3)

        keep_random_bone = (_safe_int(sync_attrs.get('iAIM_TargetBone', 5), 5) == 5)
        cur_hash = _cond_hash(mode, enemy_count, is_ads, is_sprint, pose_type, hp_low, is_veh, is_sky)
        changed = (cur_hash != _ai_last_hash)
        _ai_last_hash = cur_hash
        sync_attrs.update({
            'fAIM_SnapStrength': round(preset['snap'], 2),
            'fAIM_Fov': round(preset['fov'], 1),
            'bAIM_Prediction': preset['pred'],
            'iAIM_TargetBone': preset['bone'],
            'fAIM_BulletSpeed': preset['bspd'],
            'iAI_Mode': _AI_MODE_INT.get(mode, 0),
            'iAI_EnemyCount': enemy_count,
            'fAI_AvgDist': round(avg_dist, 1),
            'fAI_MinDist': round(min_dist, 1),
            'iAI_ModFlags': mod_flags,
            'bAI_Active': True,
            'bAI_Changed': changed,
            'fAI_SnapTuned': round(preset['snap'], 2),
            'fAI_FovTuned': round(preset['fov'], 1),
            'iAI_BoneTuned': preset['bone'],
        })
        if keep_random_bone:
            sync_attrs['iAIM_TargetBone'] = 5
    except Exception:
        pass

def AIMUpdate(*_, **__):
    global FpsPlacerInstance, _ai_tune_frame
    try:
        if not sync_attrs.get('bAIM', False):
            return
        if _ESPCombatAvatar is None or _ESPIsPlayerTeammate is None or _ESPDistance3D is None:
            return
        genv_obj = _game_genv()
        if not getattr(genv_obj, 'avatar', None):
            return
        localEntity = _local_combat_avatar()
        if not localEntity or not getattr(localEntity, 'is_alive', False):
            return

        # Shared with MENU.h v2.5: 0=Fire, 1=ADS, 2=Both, 3=Always.
        trigger = _safe_int(sync_attrs.get('iAIM_Trigger', 2), 2)
        is_shooting = bool(getattr(localEntity, 'is_shooting', False))
        is_ads = bool(getattr(localEntity, 'is_ads', False) or getattr(localEntity, 'is_real_ads', False))
        if trigger == 0 and not is_shooting:
            return
        if trigger == 1 and not is_ads:
            return
        if trigger == 2 and not (is_ads or is_shooting):
            return

        if not FpsPlacerInstance:
            try:
                cam = _esp_space().camera
                for attr in ('fps_placer', 'placer', 'aim_placer'):
                    candidate = getattr(cam, attr, None)
                    if candidate is not None and hasattr(candidate, 'Rotate'):
                        FpsPlacerInstance = candidate
                        break
            except Exception:
                return
        if not FpsPlacerInstance:
            return

        sw = _esp_float('fWidth', 1080.0)
        sh = _esp_float('fHeight', 720.0)
        if not (0 < sw <= 5000 and 0 < sh <= 5000):
            return
        cx = sw * 0.5
        cy = sh * 0.5
        max_fov = min(max(_esp_float('fAIM_Fov', 120.0), 1.0), 400.0)
        max_dist = min(max(_esp_float('fAIM_MaxDist', 400.0), 1.0), 600.0)
        check_vis = bool(sync_attrs.get('bAIM_CheckVisibility', False))
        ignore_bots = bool(sync_attrs.get('bAIM_IgnoreBots', False))
        ignore_knocked = bool(sync_attrs.get('bAIM_IgnoreKnocked', True))
        smoothing = 0.00021 * _esp_float('fAIM_SnapStrength', 3.0)
        selected_bone_idx = _safe_int(sync_attrs.get('iAIM_TargetBone', 5), 5)
        selected_bone = _AIM_BONE_MAP.get(selected_bone_idx, 'biped Neck')
        use_pred = bool(sync_attrs.get('bAIM_Prediction', True))
        bullet_speed = max(_esp_float('fAIM_BulletSpeed', 650.0), 50.0)

        space = _esp_space()
        camera_pos = space.camera.position
        entities_dict = space.entities
        if not camera_pos or not entities_dict:
            return

        # v7.21: sniper calm. At 8x the same pixel error is a far larger
        # angle, so fixed smoothing overstepped and oscillated. Scale the
        # step by the live camera FOV and never step past the remaining
        # error in angle space.
        cam_fov = 90.0
        try:
            _cf = getattr(space.camera, 'fov', None)
            if _cf is None:
                _cf = getattr(space.camera, 'field_of_view', None)
            if _cf is None:
                _cf = getattr(space.camera, 'fov_y', None)
            cam_fov = float(_cf or 90.0)
        except Exception:
            cam_fov = 90.0
        if not (15.0 <= cam_fov <= 160.0):
            cam_fov = 90.0
        # v7.30R19: snipers aim at head and neck ONLY - scoped OR simply
        # holding a sniper (user request).
        try:
            _sw = localEntity.GetCurWeapon()
            _swid = int(_sw.equip_id) if _sw else 0
        except Exception:
            _swid = 0
        sniper_mode = cam_fov < 45.0 or _swid in _AIM_SNIPER_IDS
        zoom_k = max(0.18, min(1.0, cam_fov / 90.0))
        smoothing_zoomed = smoothing * zoom_k
        px_to_ang = cam_fov / max(sw, 1.0)

        _ai_tune_frame += 1
        if sync_attrs.get('bAIM_AutoTune', False) and _ai_tune_frame >= _AI_TUNE_INTERVAL:
            _ai_tune_frame = 0
            temp_enemies = []
            for entityId, entity in list(entities_dict.items()):
                try:
                    if not isinstance(entity, _ESPCombatAvatar) or not entity.is_alive:
                        continue
                    if _ESPIsPlayerTeammate(entityId):
                        continue
                    if ignore_bots and getattr(entity, 'IsRobotCombatAvatar', False):
                        continue
                    dist3d = _ESPDistance3D(localEntity.position, entity.position)
                    if dist3d <= max_dist:
                        temp_enemies.append({'dist': dist3d})
                except Exception:
                    continue
            _aim_sniper_snap(localEntity)
            AIM_AutoTune(localEntity, temp_enemies)
            # Re-read values AutoTune may have just changed.
            max_fov = min(max(_esp_float('fAIM_Fov', max_fov), 1.0), 400.0)
            smoothing = 0.00021 * _esp_float('fAIM_SnapStrength', 3.0)
            selected_bone_idx = _safe_int(sync_attrs.get('iAIM_TargetBone', 5), 5)
            selected_bone = _AIM_BONE_MAP.get(selected_bone_idx, 'biped Neck')
            use_pred = bool(sync_attrs.get('bAIM_Prediction', True))
            bullet_speed = max(_esp_float('fAIM_BulletSpeed', bullet_speed), 50.0)

        candidates = []
        for entityId, entity in list(entities_dict.items()):
            try:
                if not isinstance(entity, _ESPCombatAvatar) or not getattr(entity, 'is_alive', False):
                    continue
                if _ESPIsPlayerTeammate(entityId):
                    continue
                if ignore_bots and getattr(entity, 'IsRobotCombatAvatar', False):
                    continue
                if ignore_knocked and getattr(entity, 'is_dying_state', False):
                    continue
                dist3d = _ESPDistance3D(localEntity.position, entity.position)
                if dist3d > max_dist:
                    continue
                bone_name = _aim_bone_for(entityId, selected_bone_idx,
                                          entity, camera_pos, dist3d,
                                          sniper_mode)
                bone_pos = entity.model.GetBoneWorldPosition(bone_name) or \
                    entity.model.GetBoneWorldPosition('biped Head')
                if not bone_pos:
                    continue
                if check_vis:
                    head_pos = entity.model.GetBoneWorldPosition('biped Head')
                    if not head_pos or not _is_visible_cached(camera_pos, head_pos, getattr(entity, 'id', entityId), dist3d):
                        continue
                sp = WorldToScreenPoint(bone_pos)
                if not hasattr(sp, 'z') or sp.z <= 0.01:
                    continue

                pred_x, pred_y = sp.x, sp.y
                now_t = time.time()
                prev = _aim_pos_track.get(entityId)
                if use_pred and prev:
                    ptype = type(bone_pos)
                    px, py, pz, pt = prev
                    dt = now_t - pt
                    if _AIM_MIN_DT < dt < _AIM_MAX_DT:
                        try:
                            prev_world = ptype(px, py, pz)
                            prev_screen = WorldToScreenPoint(prev_world)
                            if hasattr(prev_screen, 'z') and prev_screen.z > 0.01:
                                vx = (sp.x - prev_screen.x) / dt
                                vy = (sp.y - prev_screen.y) / dt
                                lead_time = min(dist3d / bullet_speed, _AIM_MAX_LEAD_TIME)
                                lx = vx * lead_time
                                ly = vy * lead_time
                                lead_cap = max_fov * 1.5
                                lmag = (lx * lx + ly * ly) ** 0.5
                                if lmag > lead_cap and lmag > 0.0001:
                                    scale = lead_cap / lmag
                                    lx *= scale
                                    ly *= scale
                                pred_x = sp.x + lx
                                pred_y = sp.y + ly
                        except Exception:
                            pass
                _aim_pos_track[entityId] = (bone_pos.x, bone_pos.y, bone_pos.z, now_t)
                dx = pred_x - cx
                dy = pred_y - cy
                fov_dist = (dx * dx + dy * dy) ** 0.5
                if fov_dist <= max_fov:
                    candidates.append((fov_dist, pred_x, pred_y, dist3d, entityId, bone_name))
            except Exception:
                continue

        if not candidates:
            if _aim_visual_point[0] is not None and (time.time() - _aim_visual_time[0]) > 0.15:
                _aim_visual_point[0] = None
            return
        # v7.30R20: focus the CLOSEST VISIBLE target (user request). The
        # FOV circle stays as the GATE - anything outside it is ignored -
        # but among the candidates that passed, distance to me decides,
        # not crosshair proximity.
        candidates.sort(key=lambda item: item[3])
        _fov, tx, ty, target_dist, target_id, target_bone_name = candidates[0]
        _aim_visual_point[0] = (tx, ty)
        _aim_visual_bone[0] = target_bone_name
        _aim_visual_target[0] = target_id
        _aim_visual_time[0] = time.time()
        dx = tx - cx
        dy = ty - cy
        if abs(dx) < 1.5 and abs(dy) < 1.5:
            return
        yaw = max(min(dx * smoothing_zoomed, 5.0), -5.0)
        pitch = max(min(-dy * smoothing_zoomed, 5.0), -5.0)
        try:
            # never step past the remaining error - kills the overshoot
            # bounce, especially at sniper zoom
            _my = abs(dx) * px_to_ang
            _mp = abs(dy) * px_to_ang
            yaw = max(min(yaw, _my), -_my)
            pitch = max(min(pitch, _mp), -_mp)
        except Exception:
            pass
        FpsPlacerInstance.Rotate(yaw, pitch)
        _aim_diag_count[0] += 1
        if _aim_diag_count[0] == 1 or _aim_diag_count[0] % 600 == 0:
            _plog('[AIM] rotate n=%d target=%r dist=%.1f fov=%.1f camfov=%.1f yaw=%.4f pitch=%.4f candidates=%d'
                  % (_aim_diag_count[0], target_id, target_dist, max_fov,
                     cam_fov, yaw, pitch, len(candidates)))
    except Exception:
        _aim_error_count[0] += 1
        if _aim_error_count[0] <= 3:
            _plog('[AIM] AIMUpdate error:\n%s' % (_exc_text(),))

def _install_esp_aim():
    global _ESPCombatAvatar, _ESPPlayerCombatAvatar, _ESPFpsPlacer
    global _ESPIsPlayerTeammate, _ESPDistance3D, _esp_lid, FpsPlacerInstance
    if _esp_aim_installed[0]:
        return True
    _esp_aim_attempts[0] += 1
    attempt = _esp_aim_attempts[0]
    try:
        from gclient.framework.util.replay_util import IsPlayerTeammate as _IsPlayerTeammate
        from gclient.framework.camera.fps_placer import FpsPlacer as _FpsPlacer
        from gclient.gameplay.logic_base.entities.combat_avatar import (
            CombatAvatar as _CombatAvatar,
            PlayerCombatAvatar as _PlayerCombatAvatar,
        )
        from gshare.formula import Distance3D as _Distance3D
    except Exception as e:
        if attempt == 1 or attempt % 10 == 0:
            _plog('[ESP] install deferred attempt=%d import error=%r' % (attempt, e))
        return False

    _ESPIsPlayerTeammate = _IsPlayerTeammate
    _ESPFpsPlacer = _FpsPlacer
    _ESPCombatAvatar = _CombatAvatar
    _ESPPlayerCombatAvatar = _PlayerCombatAvatar
    _ESPDistance3D = _Distance3D
    try:
        _esp_lid = _import_module('gclient.data.lobby_item_data')
    except Exception:
        _esp_lid = None

    @HOOK(_ESPFpsPlacer, 0)
    def OnStaticTick(self, *args, **kwargs):
        global FpsPlacerInstance
        if self:
            FpsPlacerInstance = self
        _ensure_space_tick_registered()
        return _ESPFpsPlacer._OnStaticTick(self, *args, **kwargs)

    # NOTE (v2.9): this ESP block does NOT install its own
    # on_enter_space hook. In this SRC, _install_esp_enter_hook() further
    # down is the single place that hooks PlayerCombatAvatar.on_enter_space
    # and calls _ensure_space_tick_registered(). Installing a second hook
    # here would double-wrap the same call and run the entry sequence twice.

    _esp_aim_installed[0] = True
    _plog('[ESP] ESP/Aimbot hooks installed attempt=%d' % (attempt,))
    _ensure_space_tick_registered()
    return True

def _esp_aim_install_loop():
    while not _esp_aim_installed[0]:
        if _install_esp_aim():
            return
        time.sleep(5)

if not _install_esp_aim() and not _ALREADY_LOADED:
    threading.Thread(target=_esp_aim_install_loop, daemon=True).start()


# ============================================================
# DIAGNOSTICS - one-shot evidence dump for anything SRC alone
# could not confirm. Read it after first run and adjust if a
# line says MISSING / args[4] does not look like a skin/guise.
# ============================================================
def _esp_sig(obj):
    try:
        return str(inspect.signature(obj))
    except Exception as e:
        return "<no signature: %r>" % (e,)

def _debug_log_on():
    """v7.23: Settings > Diagnostics > Debug logging. Off = no boot diag,
    no periodic/scene auto-dumps, no LANG-PROBE noise. The menu's Dump
    debug button and real error lines keep working either way."""
    return bool(sync_attrs.get('bDebugLog', True))


def _run_esp_diag(tag):
    try:
        lines = []
        if not _debug_log_on():
            return
        lines.append("==== SKINS PAYLOAD DIAG %s build=%s utc=%s pid=%s py=%s ===="
                     % (tag, PAYLOAD_BUILD, _utc_stamp(),
                        getattr(os, 'getpid', lambda: '?')(),
                        sys.version.split()[0]))
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
                lines.append("%s.%s present=%s own=%s sig=%s" % (cname, m, fn is not None, own, _esp_sig(fn) if fn else "-"))
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
                lines.append('[WEAPONFX-PROBE] effect_util.%s present=%s treacky=%s sig=%s' % (_fname, _fn is not None, bool(getattr(_fn, '_treacky_weaponfx', False)), _esp_sig(_fn) if _fn else '-'))
        except Exception as _e:
            lines.append('[WEAPONFX-PROBE] effect_util error=%r' % (_e,))

        lines.append("sync_attrs keys=%d bSkinHack=%r" % (
            len(sync_attrs), sync_attrs.get('bSkinHack')))
        _plog("\n".join(lines))
    except Exception as e:
        _plog("[DIAG] error %r" % (e,))

_run_esp_diag("run1")

def _esp_diag_later():
    time.sleep(30)
    _run_esp_diag("run2-after-30s")

if not _ALREADY_LOADED:
    threading.Thread(target=_esp_diag_later, daemon=True).start()
    threading.Thread(target=name_worker, daemon=True).start()

_name_overrides_loaded[0] = _name_load_overrides()



UDP_HERO_PORT = 50003
_hero_sock = [None]


# v5.8: the hero catalog goes out in the SAME shape as the weapon catalog
# (8 KB complete-line chunks) instead of one ~28 KB datagram. The weapon
# catalog has always arrived and the hero catalog never did, on the same
# loopback, with the same C++ receiver - the only difference was the size of
# the datagram. The receiver is a line accumulator, so chunking is free.
# Every failure is logged now; the old version swallowed it (except: pass),
# which is why the Striker tab could sit on "scanning" with no evidence at all.
_hero_stats = {'sent': 0, 'bytes': 0, 'errors': 0, 'last_error': None}


def _hero_udp():
    if _hero_sock[0] is None:
        try:
            import socket as _s
            _hero_sock[0] = _s.socket(_s.AF_INET, _s.SOCK_DGRAM)
            _hero_sock[0].setsockopt(_s.SOL_SOCKET, _s.SO_REUSEADDR, 1)
            try:
                _hero_sock[0].setsockopt(_s.SOL_SOCKET, _s.SO_SNDBUF, 2 * 1024 * 1024)
            except Exception:
                pass
        except Exception as _he:
            _hero_sock[0] = False
            _plog("[HERO-UDP] socket failed: %r" % (_he,))
    return _hero_sock[0] or None


_hero_udp_last = [None]


def _write_udp_hero(data):
    # v7.30: the zip's sender loop calls this every 2 s with the FULL
    # hero catalog - match included (device log: hero_sent climbed
    # straight through matches, hundreds of KB of UDP each time). The
    # zip stays verbatim, so the transport drops it instead: nothing
    # mid-match, and identical payloads send once.
    dedup_data = data if isinstance(data, str) and data.strip() else None
    try:
        if _hero_scene_stable() == 'match':
            return
        if dedup_data is not None and data == _hero_udp_last[0]:
            return
    except Exception:
        pass
    sock = _hero_udp()
    if not sock:
        return
    try:
        if isinstance(data, str):
            data = data.encode('utf-8')
        # v6.1: the striker block sends H|/K|/END with no BEGIN, so the menu
        # only ever overwrote rows it happened to receive again - a row sent
        # before _hero_plain_protos() converted the protos stayed on screen as
        # a raw dict for the rest of the session. Every catalog send is now a
        # complete refresh, so nothing stale can survive.
        if data.startswith(b'H|') and not data.startswith(b'BEGIN'):
            data = b"BEGIN\n" + data
        if len(data) > 8192:
            # never split a line: the C++ side is a newline accumulator
            start = 0
            while start < len(data):
                end = min(len(data), start + 8192)
                if end < len(data):
                    nl = data.rfind(b'\n', start, end)
                    if nl > start:
                        end = nl + 1
                sock.sendto(data[start:end], ("127.0.0.1", UDP_HERO_PORT))
                _hero_stats['sent'] += 1
                _hero_stats['bytes'] += end - start
                start = end
            if dedup_data is not None:
                _hero_udp_last[0] = dedup_data
            return
        sock.sendto(data, ("127.0.0.1", UDP_HERO_PORT))
        _hero_stats['sent'] += 1
        _hero_stats['bytes'] += len(data)
        if dedup_data is not None:
            _hero_udp_last[0] = dedup_data
    except Exception as _he:
        _hero_udp_last[0] = None
        _hero_stats['errors'] += 1
        if _hero_stats['last_error'] != repr(_he):
            _hero_stats['last_error'] = repr(_he)
            _plog("[HERO-UDP] send error: %r" % (_he,))
        _hero_sock[0] = None   # rebuild the socket on the next attempt


UDP_EMOTE_PORT = 50005
_emote_sock = [None]
_emote_stats = {'sent': 0, 'bytes': 0, 'errors': 0, 'last_error': None}


def _write_udp_emote(data):
    """v6.1: every failure is logged now.

    The emote feed used to `except: pass`. On device the Emotes panel sat on
    "scanning..." with no evidence at all, because nothing in the chain - not
    the socket, not the send, not the count - was ever reported.
    """
    if _emote_sock[0] is None:
        try:
            import socket as _s
            _emote_sock[0] = _s.socket(_s.AF_INET, _s.SOCK_DGRAM)
            _emote_sock[0].setsockopt(_s.SOL_SOCKET, _s.SO_REUSEADDR, 1)
            try:
                _emote_sock[0].setsockopt(_s.SOL_SOCKET, _s.SO_SNDBUF, 2 * 1024 * 1024)
            except Exception:
                pass
        except Exception as _ee:
            _emote_sock[0] = False
            _plog("[EMOTE-UDP] socket failed: %r" % (_ee,))
    if not _emote_sock[0]:
        return
    try:
        if isinstance(data, str):
            data = data.encode('utf-8')
        _emote_sock[0].sendto(data, ("127.0.0.1", UDP_EMOTE_PORT))
        _emote_stats['sent'] += 1
        _emote_stats['bytes'] += len(data)
    except Exception as _ee:
        _emote_stats['errors'] += 1
        if _emote_stats['last_error'] != repr(_ee):
            _emote_stats['last_error'] = repr(_ee)
            _plog("[EMOTE-UDP] send error: %r" % (_ee,))
        _emote_sock[0] = None


def _write_udp_chunked_hero(text):
    _write_udp_chunked(_write_udp_hero, text)



# ============================================================
# NEXORA v8.0 - STRIKER CORE
# ------------------------------------------------------------
# Clean-room replacement for the old assembled hero section
# (the "BSB block"). All code in this file is ours; nothing is
# byte-copied from another project anymore. Semantics carried
# over where the device logs proved them useful, rewritten to
# one standard:
#   * every hook is SIGNATURE-TRANSPARENT - args are forwarded
#     exactly as the game passed them (the R26 crash was an
#     arg-padding TypeError inside the game's on_setattr);
#   * every forced value is VALIDATED - an id without a full
#     proto in the game's own lobby table is never injected
#     (the R27 log had NoneType crashes from feature checks on
#     missing protos);
#   * the pick functions answer None instead of raising, always.
# New in v8 (the actual skin strategy):
#   * AVATAR CAPTURE - PlayerAvatar.__init__ / _on_set_hero_id
#     wraps hand us the live local player (the game never calls
#     the read verbs we used to wait for);
#   * DATA-WRITE - our pick is written into the player's own
#     equip fields (names probed live from the game's code
#     objects), so every consumer reads it as real state, the
#     same way the weapon skin lives in the equip data;
#   * EQUIP BY GAME - the game's own ArmHeroSkin verb, called
#     on the captured avatar (lobby only, once per pick);
#   * NONE-SHIELDS on the game's feature-check utils so a
#     missing proto can never crash the game thread again.
# ============================================================

HERO = {}
HERO_SKIN_INFO = {}
_hero_lines_cache = [None]
dw_fields = [None]
dw_wrote = [None]

try:
    import gclient.data.hero_data as hd
    import gclient.data.lobby_item_data as lid
    from gclient.framework.entities.avatar import PlayerAvatar
    from gclient.gamesystem.entities.hall_doll import Doll, DollLike, \
        CalculationDoll, BigHeadCalculationDoll
    from gclient.gamesystem.models.hall_show_model import HallShowModel
    from gclient.gameplay.logic_base.entities.combat_avatar \
        import CombatAvatar
    import time, threading

    # ---- catalog (validated) --------------------------------------
    for hero_id, hero_proto in hd.data.items():
        try:
            HERO[hero_id] = [hero_proto.get('hero_name', str(hero_id))]
        except Exception:
            HERO[hero_id] = [str(hero_id)]
    for item_id, item_proto in lid.data.items():
        try:
            is_hero_skin = (
                item_proto.get('sub_type') == 300
                or item_proto.get('short_desc') == 'Striker'
                or (item_proto.get('hero_id')
                    and item_proto.get('hero_skin_id') is not None))
            if not is_hero_skin:
                continue
            hero_id = item_proto.get('hero_id')
            if not hero_id or hero_id not in HERO:
                continue
            if item_id == hd.data.get(hero_id, {}).get('hero_item_id'):
                continue
            # v8: a skin without a model_id is a stub - never force it
            if not item_proto.get('model_id'):
                continue
            HERO_SKIN_INFO[item_id] = item_proto
            if item_id not in HERO[hero_id]:
                HERO[hero_id].append(item_id)
        except Exception:
            continue

    def _build_hero_info_lines():
        lines = []
        for hero_id, entries in HERO.items():
            lines.append("H|%d|%s" % (hero_id, entries[0]))
            for idx, skin_id in enumerate(entries[1:], start=1):
                skin_proto = HERO_SKIN_INFO.get(skin_id, {})
                try:
                    skin_name = skin_proto.get('name', 'Skin_%d' % skin_id)
                except Exception:
                    skin_name = 'Skin_%d' % skin_id
                lines.append("K|%d|%d|%s" % (hero_id, idx, skin_name))
        lines.append("END")
        return lines



    try:
        with open("/storage/emulated/0/Nexora/nexora_herobuild_debug.txt",
                  "a") as f:
            f.write(
                "V8 HERO dict count=%d sample=%r\n"
                "HERO_SKIN_INFO count=%d sample=%r\n"
                "hd.data count=%d\nlid.data count=%d\n"
                % (
                    len(HERO), dict(list(HERO.items())[:3]),
                    len(HERO_SKIN_INFO),
                    dict(list(HERO_SKIN_INFO.items())[:2]),
                    len(hd.data), len(lid.data),
                ))
    except Exception as _hbe:
        try:
            with open("/storage/emulated/0/Nexora/nexora_herobuild_debug.txt",
                      "a") as f:
                f.write("V8 BUILD LOG ERROR: %r\n" % (_hbe,))
        except Exception:
            pass

    def _hero_sender_loop():
        # v8: the old loop rebuilt the whole catalog text every 2 s and
        # held the GIL 0.3 s each pass - pure lag. Now the text is
        # cached and only resent as a keepalive.
        while True:
            time.sleep(5)
            try:
                txt = _hero_lines_cache[0]
                if txt:
                    _write_udp_hero(txt)
            except Exception:
                pass

    threading.Thread(target=_hero_sender_loop, daemon=True).start()

    def _v8_settled():
        """v8.01: True once the equip-by-game landed for the CURRENT
        pick - from then on every force in this core stands down and
        lets the game build from the real equipped state."""
        try:
            sig = _hero_apply_sig[0]
            return bool(sig) and _avatar_equip_sig[0] == sig
        except Exception:
            return False

    load_log_n = [0]

    def honest_load_log(tag, data):
        """v8.02: with the forces off, log the game's OWN load values
        (first few) - the device log then proves the model is built
        from real equipped state, not by us."""
        try:
            if load_log_n[0] >= 6:
                return
            load_log_n[0] += 1
            hid = data.get('hero_id') if hasattr(data, 'get') else None
            mid = data.get('model_id') if hasattr(data, 'get') else None
            _plog('[V8] %s honest hero=%r model_id=%r' % (tag, hid, mid))
        except Exception:
            pass

    # ---- the pick functions (module level, None-safe) -------------

    def _get_forced_skin_proto(hero_id):
        try:
            skin_id = _get_forced_skin(hero_id)
            row = None
            if skin_id:
                try:
                    row = lid.data.get(skin_id)
                except Exception:
                    row = None
                # v2.90: hero skins carry fps_model_id/model_id/hero_skin_id
                # on the HERO_SKIN_INFO row, NOT in lobby_item_data.  Without
                # this fallback the FPS arms stay default and the proto reads
                # break (the lobby model resets after scene hops).
                if row is None:
                    row = (globals().get('HERO_SKIN_INFO') or {}).get(skin_id)
                elif not any(_safe_int(row.get(_f, 0), 0) for _f in
                             ('fps_model_id', 'model_id', 'hero_skin_id')):
                    _hs = (globals().get('HERO_SKIN_INFO') or {}).get(skin_id)
                    if _hs:
                        row = _hs
            return row
        except Exception:
            return None

    def _get_forced_model_id(hero_id):
        try:
            proto = _get_forced_skin_proto(hero_id)
            if proto is not None:
                return proto.get('model_id')
        except Exception:
            return None
        return None

    # ---- hero_skin_proto (plain property classes) ------------------
    def hook_hero_skin_proto(cls):
        try:
            orig_prop = cls.__dict__.get('hero_skin_proto')
            if orig_prop is None or not isinstance(orig_prop, property):
                return
            orig_get = orig_prop.fget
            if not callable(orig_get) \
                    or getattr(orig_get, '_treacky_v8hsp', False):
                return

            def _getter(self, _f=orig_get):
                result = _f(self)
                try:
                    if (_striker_native_combat_owned()
                            and _hero_scene_stable() == 'match'):
                        return result
                    if (_striker_native_combat_owned()
                            and not _striker_native_local_display(self)):
                        return result
                    if sync_attrs.get('bHeroSkinHack', False) \
                            and sync_attrs.get('bStrikerRepaint', False) \
                            and not _v8_settled():
                        hero_id = None
                        try:
                            hero_id = self.GetHeroId()
                        except Exception:
                            hero_id = None
                        if not hero_id:
                            hero_id = getattr(self, 'hero_id', None)
                        if hero_id:
                            resolver = globals().get(
                                '_get_forced_hero_skin_proto')
                            forced = resolver(hero_id) if callable(resolver) \
                                else None
                            if forced is not None:
                                return forced
                except Exception:
                    pass
                return result
            _getter._treacky_v8hsp = True
            setattr(cls, 'hero_skin_proto', property(_getter))
        except Exception:
            pass

    for _cls in (PlayerAvatar, CombatAvatar, Doll, DollLike,
                 CalculationDoll, BigHeadCalculationDoll):
        hook_hero_skin_proto(_cls)

    # ---- PlayerAvatar.GetHeroSkinProto: force + avatar capture -----
    @HOOK(PlayerAvatar, 0)
    def _on_set_hero_id(self, *a, **k):
        # v8.14: THE striker-swap verb (the v8.13 log: swapping Ethan
        # -> Nova never called ArmHeroSkin - the api dump shows the
        # game sets the hero through _on_set_hero_id observers).
        # v10.8: native first.  Repainting from inside the pre-native
        # observer re-showed the OLD operator while the switch was still
        # in flight (v10.7 device log, hero 115 -> 101 -> 103).
        # The current native signature is _on_set_hero_id(self, old).
        # Its integer is the PREVIOUS hero and the native body only broadcasts
        # ON_HERO_ID_CHANGE.  Read the actual post-native state instead of
        # treating that old value as the new operator.
        _result = PlayerAvatar.__on_set_hero_id(self, *a, **k)
        _hid = 0
        try:
            _hid = _safe_int(_hero_id_deep(self), 0)
        except Exception:
            _hid = 0
        if not _hid:
            try:
                _getter = getattr(self, 'GetHeroId', None)
                _hid = _safe_int(
                    _getter() if callable(_getter)
                    else getattr(self, 'hero_id', 0), 0)
            except Exception:
                _hid = 0
        if _hid:
            try:
                on_hero_change(_hid, '_on_set_hero_id')
            except Exception:
                pass
            try:
                _refresh = globals().get('striker_request_combat_refresh')
                if callable(_refresh):
                    _refresh(self, _hid)
            except Exception:
                pass
        return _result

    @HOOK(PlayerAvatar, 0)
    def GetHeroSkinProto(self, *a, **k):
        try:
            _avatar_note_seen(self)
        except Exception:
            pass
        try:
            if sync_attrs.get('bHeroSkinHack', False) \
                    and sync_attrs.get('bStrikerRepaint', False) \
                    and not _v8_settled():
                hero_id = k.get('hero_id', None)
                skin_item_id = k.get('skin_item_id', None)
                if len(a) > 0 and hero_id is None:
                    hero_id = a[0]
                if len(a) > 1 and skin_item_id is None:
                    skin_item_id = a[1]
                if not _safe_int(skin_item_id, 0):
                    if not hero_id:
                        try:
                            hero_id = self.GetHeroId()
                        except Exception:
                            hero_id = None
                    if not hero_id:
                        hero_id = getattr(self, 'hero_id', None)
                    if not hero_id:
                        _ow = getattr(self, 'owner', None)
                        if _ow is not None:
                            try:
                                hero_id = _ow.GetHeroId()
                            except Exception:
                                hero_id = getattr(_ow, 'hero_id', None)
                    if hero_id:
                        resolver = globals().get('_get_forced_hero_skin_proto')
                        fp = resolver(hero_id) if callable(resolver) else None
                        if fp is not None:
                            return fp
        except Exception:
            pass
        return PlayerAvatar._GetHeroSkinProto(self, *a, **k)

    # ---- HallShowModel Load / Reload: the model-id chain -----------
    @HOOK(HallShowModel, 0)
    def Load(self, data, done=None, **create_kwargs):
        # Native Load data is an atomic model/resource/component bundle.
        # Do not rewrite only model_id; ShowHeroSkinModel receives the full
        # selected lobby row later, after the native load has completed.
        try:
            honest_load_log('Load', data)
        except Exception:
            pass
        return HallShowModel._Load(self, data, done, **create_kwargs)

    @HOOK(HallShowModel, 0)
    def Reload(self, data, done=None, use_ready_to_appear=True):
        # Keep native model_id + resource/component paths atomic.
        try:
            honest_load_log('Reload', data)
        except Exception:
            pass
        return HallShowModel._Reload(self, data, done, use_ready_to_appear)

    # ---- Doll model ids --------------------------------------------
    @HOOK(Doll, 0)
    def GetModelUnitID(self, _download_info=None):
        try:
            if sync_attrs.get('bHeroSkinHack', False) \
                    and sync_attrs.get('bStrikerRepaint', False) \
                    and not _v8_settled():
                hero_id = None
                try:
                    hero_id = self.GetHeroId()
                except Exception:
                    hero_id = None
                if hero_id:
                    model_id = _get_forced_model_id(hero_id)
                    if model_id:
                        return model_id
        except Exception:
            pass
        return Doll._GetModelUnitID(self, _download_info)

    @HOOK(Doll, 0)
    def GetModelComponentList(self, _download_info=None):
        # The native getter combines GetModelUnitID with the authentic
        # hero_skin_proto/additional_models.  Do not inject a lone forced
        # model id into its download metadata.
        return Doll._GetModelComponentList(self, _download_info)

    # ---- the show channels: substitute our proto -------------------
    def subst_proto(self, item_proto):
        try:
            if item_proto is None:
                return item_proto
            hero_id = None
            if hasattr(item_proto, 'get'):
                hero_id = item_proto.get('hero_id')
            if not hero_id:
                try:
                    hero_id = self.GetHeroId()
                except Exception:
                    hero_id = None
            if hero_id:
                skin_proto = _get_forced_skin_proto(hero_id)
                if skin_proto is not None:
                    return skin_proto
        except Exception:
            pass
        return item_proto

    for cls in (Doll, DollLike, CalculationDoll, BigHeadCalculationDoll):
        @HOOK(cls, 0)
        def ShowHeroSkinModel(self, item_proto, *args, _c=cls, **kwargs):
            if sync_attrs.get('bHeroSkinHack', False) \
                    and sync_attrs.get('bStrikerRepaint', False) \
                    and not _v8_settled():
                item_proto = subst_proto(self, item_proto)
            return _c._ShowHeroSkinModel(self, item_proto, *args, **kwargs)

    @HOOK(Doll, 0)
    def ShowDisplayModel(self, item_proto, display_loop=False,
                         callback=None, *args, **kwargs):
        if sync_attrs.get('bHeroSkinHack', False) \
                and sync_attrs.get('bStrikerRepaint', False) \
                and not _v8_settled():
            item_proto = subst_proto(self, item_proto)
        return Doll._ShowDisplayModel(self, item_proto, display_loop,
                                      callback, *args, **kwargs)

    # v8.01: the ClearHeroSkinInfo / CueChangeHeroSkin re-show hooks are
    # GONE. The v8 device log showed the loop they cause once the equip
    # really lands: game clears -> we re-show -> game clears again ->
    # Load/Reload cycle x6 -> native segfault. With real equipped state
    # the game keeps its own skin alive; we stay out of its way.

    # ---- v8: AVATAR CAPTURE ----------------------------------------
    # The game never calls the PlayerAvatar read verbs we used to wait
    # for (27 rounds of logs). Capturing the instance at creation and
    # at hero change is the only reliable hold on the local player.
    def capture_avatar():
        try:
            prev_init = PlayerAvatar.__dict__.get('__init__')
            if callable(prev_init) \
                    and not getattr(prev_init, '_treacky_v8cap', False):
                def _v8_init(self, *a, **k):
                    rr = prev_init(self, *a, **k)
                    try:
                        _avatar_note_seen(self)
                    except Exception:
                        pass
                    return rr
                _v8_init._treacky_v8cap = True
                PlayerAvatar.__init__ = _v8_init
        except Exception:
            pass
        try:
            prev_sh = PlayerAvatar.__dict__.get('_on_set_hero_id')
            if callable(prev_sh) \
                    and not getattr(prev_sh, '_treacky_v8cap', False):
                def _v8_sh(self, *a, **k):
                    rr = prev_sh(self, *a, **k)
                    try:
                        _avatar_note_seen(self)
                        try:
                            _avatar_equip_sig[0] = None
                        except Exception:
                            pass
                    except Exception:
                        pass
                    return rr
                _v8_sh._treacky_v8cap = True
                PlayerAvatar._on_set_hero_id = _v8_sh
        except Exception:
            pass

    capture_avatar()

    # ---- v8: DATA-WRITE --------------------------------------------
    # The weapon skin shows everywhere because it lives in the equip
    # data. v8 writes our pick into the player's own skin fields the
    # same way: probe the real field names from the game's own code
    # objects, then overwrite only values that ARE a skin of the same
    # hero. Validated, idempotent, restorable by re-picking.
    def probe_skin_fields(avatar):
        fields = []
        try:
            for meth in ('_GetActualHeroSkinItemId', 'GetCurArmSkinItemId',
                         'GetActualArmSkinItemId', 'GetActualSkinItemId'):
                fn = getattr(type(avatar), meth, None)
                # v8: read through our own wraps to the real code
                # object. v8.07: the arm-skin getters can carry a
                # chain of wraps now - follow all of them.
                for _ in range(4):
                    nxt = getattr(fn, '_treacky_orig', None)
                    if not callable(nxt) or nxt is fn:
                        break
                    fn = nxt
                code = getattr(fn, '__code__', None)
                if code is None:
                    continue
                for cn in code.co_names:
                    low = str(cn).lower()
                    if ('skin' in low or 'item' in low) \
                            and not low.startswith('get') \
                            and hasattr(avatar, cn):
                        fields.append(cn)
        except Exception:
            pass
        fields = list(dict.fromkeys(fields))[:10]
        dw_fields[0] = fields
        _plog('[V8] skin fields probed: %r' % (fields,))
        return fields

    def data_write(avatar):
        """Write our pick into the avatar's own equip fields (lobby)."""
        try:
            if not sync_attrs.get('bHeroSkinHack', False):
                return
            try:
                if _hero_in_match():
                    return
            except Exception:
                return
            hero_id = None
            try:
                hero_id = _hero_id_deep(avatar)
            except Exception:
                hero_id = None
            if not hero_id:
                return
            forced = _get_forced_skin(hero_id)
            if not forced or forced not in lid.data:
                return
            fields = dw_fields[0]
            if fields is None:
                fields = probe_skin_fields(avatar)
            wrote = []
            for fname in (fields or []):
                try:
                    cur = getattr(avatar, fname, None)
                    if not isinstance(cur, int) or cur == forced:
                        continue
                    proto = lid.data.get(cur)
                    if proto is None:
                        continue
                    if proto.get('hero_id') != hero_id:
                        continue
                    setattr(avatar, fname, forced)
                    wrote.append('%s:%d->%d' % (fname, cur, forced))
                except Exception:
                    continue
            if wrote:
                dw_wrote[0] = forced
                _plog('[V8] data-write hero=%d %s'
                      % (hero_id, ', '.join(wrote[:6])))
        except Exception:
            pass

    # ---- v8: NONE-SHIELDS ------------------------------------------
    # The R27 device log had 19 uncaught NoneType crashes inside the
    # game's own feature checks (a proto lookup returned None and the
    # game did `proto.x // int`). These shields make the exact
    # None-input case safe and change NOTHING else.
    def install_none_shields():
        try:
            import gclient.util.cdata_util as _cu
            _fn = getattr(_cu, 'IsHeroSkinByLobbyItemProto', None)
            if callable(_fn) and not getattr(_fn, '_treacky_v8sh', False):
                def _sh_isproto(*a, _f=_fn, **k):
                    if not a or a[0] is None:
                        return False
                    try:
                        return _f(*a, **k)
                    except TypeError:
                        return False
                _sh_isproto._treacky_v8sh = True
                _cu.IsHeroSkinByLobbyItemProto = _sh_isproto
        except Exception:
            pass
        try:
            # v8.08: the v8.07 device log crashed 5x inside the game's
            # own kill-counter check - CheckSupportedKillCounter ->
            # HasFeatureByItemId -> ... -> IsVehicleSkinByLobbyItem-
            # Proto(None) -> None // int. Same none-shield family.
            import gclient.util.cdata_util as _cu2
            _fn = getattr(_cu2, 'IsVehicleSkinByLobbyItemProto', None)
            if callable(_fn) and not getattr(_fn, '_treacky_v8sh',
                                             False):
                def _sh_veh(*a, _f=_fn, **k):
                    if not a or a[0] is None:
                        return False
                    try:
                        return _f(*a, **k)
                    except TypeError:
                        return False
                _sh_veh._treacky_v8sh = True
                _cu2.IsVehicleSkinByLobbyItemProto = _sh_veh
        except Exception:
            pass
        try:
            import gclient.util.gun_upgrade_util as _gu
            for _m in ('GetItemFeatureType', 'GetItemNewFeatureList'):
                _fn = getattr(_gu, _m, None)
                if callable(_fn) \
                        and not getattr(_fn, '_treacky_v8sh', False):
                    def _sh_gu(*a, _f=_fn, **k):
                        if not a or a[0] is None:
                            return None
                        try:
                            return _f(*a, **k)
                        except TypeError:
                            return None
                    _sh_gu._treacky_v8sh = True
                    setattr(_gu, _m, _sh_gu)
        except Exception:
            pass

    install_none_shields()

    racer_shield_state = ['']
    racer_absorbed_seen = set()

    def racer_absorbed(where, err):
        """Log (once per site) an AttributeError the shield ate."""
        try:
            if where in racer_absorbed_seen:
                return
            racer_absorbed_seen.add(where)
            _plog('[SHIELD] racer %s absorbed %r' % (where, err))
        except Exception:
            pass

    def install_racer_shield():
        """v8.08: the game's own async component refresh crashes on
        REBUILT weapon cases (our pump re-apply rebuilds them):
        __refresh_racer_component__ -> UnLoadRacerEffect ->
        AttributeError 'WeaponCase' object has no attribute
        'play_other_effect_tick' - still 4x in the v8.09 device log.
        v8.10 root cause of the shield never firing: the BOOT-time
        install ran before the game ever loaded the module (the
        __import__ fallback failed silently -> nothing wrapped).
        Now: idempotent, sys.modules-only (no import), retried from
        EquipCaseFactory.Create and the weapon pump - the first
        moments the module is guaranteed loaded. Both levels are
        shielded: the module function AND the WeaponCase METHOD (the
        device crash is weapon_case_components.py L1141 inside
        WeaponCase.UnLoadRacerEffect)."""
        try:
            _st = racer_shield_state[0]
            # v8.11: the v8.10 lazy retry STILL never found it (0
            # 'racer installed' notes, 5 crashes in the v8.10 log):
            # WeaponCase is defined in weapon_case.py and the METHOD
            # is attached to it by weapon_case_components.py - a plain
            # getattr(module, 'WeaponCase') can miss the binding. Scan
            # BOTH modules' namespaces: the module-level function AND
            # every class that carries UnLoadRacerEffect.
            for _mn in ('gclient.gameplay.logic_base.equips.'
                        'weapon_case_components',
                        'gclient.gameplay.logic_base.equips.'
                        'weapon_case'):
                _m = sys.modules.get(_mn)
                if _m is None:
                    continue
                # v8.12: BOTH racer methods are shielded. The v8.11
                # device log moved the crash from UnLoadRacerEffect's
                # play_other_effect_tick to __refresh_racer_component__
                # 's is_in_combat - the case object itself is what is
                # broken, so ANY AttributeError in these racer paths is
                # absorbed (a no-op beats an uncaught crash + a 60 s
                # match-reload loop).
                for _rname in ('UnLoadRacerEffect',
                               '__refresh_racer_component__'):
                    _fn = getattr(_m, _rname, None)
                    if callable(_fn) and not getattr(_fn, '_treacky_v8sh',
                                                     False):
                        def _sh_racer(*a, _f=_fn, **k):
                            try:
                                return _f(*a, **k)
                            except (AttributeError, TypeError) as _ae:
                                racer_absorbed(
                                    'module.%s' % (_rname,), _ae)
                                return None
                        _sh_racer._treacky_v8sh = True
                        setattr(_m, _rname, _sh_racer)
                        _st += '+module:%s' % (_rname,)
                    for _v in list(vars(_m).values()):
                        if not isinstance(_v, type):
                            continue
                        _mfn = _v.__dict__.get(_rname)
                        if not callable(_mfn) or getattr(
                                _mfn, '_treacky_v8sh', False):
                            continue

                        def _sh_racer_m(self, *a, _f=_mfn,
                                        _rn=_rname, **k):
                            try:
                                return _f(self, *a, **k)
                            except (AttributeError, TypeError) as _ae:
                                racer_absorbed(
                                    '%s.%s' % (type(self).__name__, _rn),
                                    _ae)
                                return None
                        _sh_racer_m._treacky_v8sh = True
                        setattr(_v, _rname, _sh_racer_m)
                        _st += '+method:%s.%s' % (_v.__name__, _rname)
            if _st and _st != racer_shield_state[0]:
                racer_shield_state[0] = _st
                _plog('[SHIELD] racer installed%s' % (_st,))
        except Exception as _e:
            try:
                if 'racer-err' not in _emote_notes:
                    _emote_notes.add('racer-err')
                    _plog('[SHIELD] racer error=%r' % (_e,))
            except Exception:
                pass
        return racer_shield_state[0]

    install_racer_shield()

except Exception as core_error:
    HERO = {1: ['Default']}

    def _v8_settled():
        return False

    try:
        _plog('[V8] CORE ERROR: %r' % (core_error,))
    except Exception:
        pass


    def _get_forced_skin_proto(hero_id):
        return None

    def _get_forced_model_id(hero_id):
        return None

    def data_write(avatar):
        pass

    try:
        with open("/storage/emulated/0/Nexora/nexora_herobuild_debug.txt",
                  "a") as f:
            f.write("V8 CORE SECTION ERROR: %r\n" % (core_error,))
    except Exception:
        pass

# ============================================================
# v7.30R18 SHARED PASSIVE HELPERS (emote / diag / FX only)
# ============================================================
# v8.0: the section above is OUR OWN striker core (clean-room). The
# helpers below (scene detection, proto readers, live-object scan)
# are shared infrastructure for the payload's systems.
# ====================================================================

_HERO_IN_DEEP = [0]


def _hero_id_deep(obj, _depth=0):
    if _depth > 3:
        return None
    _HERO_IN_DEEP[0] += 1
    try:
        return _hero_id_deep_inner(obj, _depth)
    finally:
        _HERO_IN_DEEP[0] -= 1


def _hero_id_deep_inner(obj, _depth=0):
    """Hero id from wherever this object actually keeps it (v7.30 impl
    verbatim: getters, owner chain, id attrs, then the proto's hero_id).
    v7.30R23: the hero hint our Load/Reload wrap stashes on hall models
    (the home lobby doll has no getter of its own)."""
    if obj is None:
        return None
    try:
        _hint = getattr(obj, '_treacky_hero_hint', None)
        if _hint:
            return _hint
    except Exception:
        pass
    for getter in ('GetHeroId', 'GetCurHeroId'):
        try:
            fn = getattr(obj, getter, None)
            if callable(fn):
                v = fn()
                if v:
                    return v
        except Exception:
            pass
    owner = getattr(obj, 'owner', None)
    if owner is not None and owner is not obj:
        v = _hero_id_deep_inner(owner, _depth + 1)
        if v:
            return v
    for attr in ('hero_id', 'real_hero_id', 'heroId', 'cur_hero_id',
                 'arm_hero_id'):
        try:
            v = getattr(obj, attr, None)
            if isinstance(v, int) and v > 0:
                return v
        except Exception:
            pass
    if _HERO_IN_DEEP[0] > 1 or _depth > 0:
        return None
    for meth in ('GetCurArmHeroSkinProto', 'GetActualArmHeroSkinProto',
                 'GetHeroSkinProto', 'GetCurArmHeroSkinItemId'):
        try:
            fn = getattr(obj, meth, None)
            if not callable(fn):
                continue
            v = fn()
            hid = _hero_proto_get(v, 'hero_id')
            if isinstance(hid, int) and hid > 0:
                return hid
        except Exception:
            continue
    # v7.30R24: LAST resort, HALL only - the home lobby doll has no id
    # of its own anywhere, but the hall space's owner is the local
    # player (the striker standing in the lobby IS the equipped hero).
    # Never in a match (every avatar there has its own id) and never
    # deeper in a chain (only the top-level object may inherit the
    # local hero).
    try:
        if _hero_scene_stable() == 'hall':
            sp = getattr(Space, '_instance', None)
            sp_owner = getattr(sp, 'owner', None)
            if sp_owner is not None and sp_owner is not obj:
                return _hero_id_deep_inner(sp_owner, _depth + 1)
    except Exception:
        pass
    return None


def _hero_proto_get(proto, key, dflt=None):
    """taggeddict-safe get: the game's protos are NOT dicts."""
    if proto is None:
        return dflt
    try:
        v = proto.get(key, dflt)
        if v is not None:
            return v
    except Exception:
        pass
    try:
        return getattr(proto, key, dflt)
    except Exception:
        return dflt


def _hero_skin_data_row(lobby_proto):
    """Resolve the authentic hero_skin_data row for a lobby skin item.

    lobby_item_data and hero_skin_data are different contracts: the former
    drives ShowHeroSkinModel/model resources, while the latter drives body
    attachments, effects and native animation state.  Never substitute one
    for the other.  This resolver deliberately fails closed with None.
    """
    try:
        if lobby_proto is None:
            return None
        hero_id = _safe_int(_hero_proto_get(lobby_proto, 'hero_id', None), 0)
        skin_raw = _hero_proto_get(lobby_proto, 'hero_skin_id', None)
        if not hero_id or skin_raw is None:
            return None
        skin_id = _safe_int(skin_raw, -1)
        if skin_id < 0:
            return None
        mod = sys.modules.get('gclient.data.hero_skin_data')
        data = getattr(mod, 'data', None) if mod is not None else None
        if not callable(getattr(data, 'get', None)):
            return None
        group = data.get(hero_id, None)
        if group is None:
            group = data.get(str(hero_id), None)
        if not callable(getattr(group, 'get', None)):
            return None
        row = group.get(skin_id, None)
        if row is None:
            row = group.get(str(skin_id), None)
        if row is None:
            return None
        # If both rows carry the item id, reject an accidental cross-skin
        # mapping instead of rendering a plausible but wrong hero row.
        lobby_item = _hero_proto_get(lobby_proto, 'skin_item_id', None)
        if lobby_item is None:
            lobby_item = _hero_proto_get(lobby_proto, 'id', None)
        row_item = _hero_proto_get(row, 'skin_item_id', None)
        if (lobby_item is not None and row_item is not None
                and _safe_int(lobby_item, 0) != _safe_int(row_item, -1)):
            return None
        return row
    except Exception:
        return None


def _get_forced_hero_skin_proto(hero_id):
    """Selected lobby item -> authentic hero_skin_data row (never lobby)."""
    try:
        lobby_get = globals().get('_get_forced_skin_proto')
        if not callable(lobby_get):
            return None
        return _hero_skin_data_row(lobby_get(hero_id))
    except Exception:
        return None


def _hero_proto_keys(proto, limit=12):
    try:
        return list(proto.keys())[:limit]
    except Exception:
        pass
    try:
        return [a for a in dir(proto) if not a.startswith('_')][:limit]
    except Exception:
        return []


def _hero_kind(obj):
    """'hall' or 'match' for one object - module first, then class name."""
    name = type(obj).__name__
    mod = type(obj).__module__ or ''
    if 'combat_avatar' in mod or 'ShootingRange' in name or 'shootingrange' in mod:
        return 'match'
    if 'avatar' in mod:
        return 'match'
    if 'Doll' in name or 'Hall' in name or 'Mall' in name or 'hall_' in mod:
        return 'hall'
    return None


_scene_space_logged = [None]
_scene_last = [None]
_scene_at = [0.0]
_unlock_try_at = [0.0]


_scene_cls_cache = {'at': 0.0, 'scene': None}


def _scene_from_space():
    """'hall' | 'match' | None, straight from the live Space (v7.30 impl).
    v7.30R19: CACHED - the scene-gated striker flag calls this per hook
    hit, so the imports/isinstance/string work now happen at most twice
    a second instead of on every call (that per-call cost was part of
    the R18 lag)."""
    now = time.time()
    if now - _scene_cls_cache['at'] < 0.5:
        return _scene_cls_cache['scene']
    _scene_cls_cache['at'] = now
    scene = _scene_from_space_uncached()
    _scene_cls_cache['scene'] = scene
    return scene


def _scene_from_space_uncached():
    """'hall' | 'match' | None, straight from the live Space (v7.30 impl)."""
    sp = None
    for name in ('_esp_space', '_game_space'):
        fn = globals().get(name)
        if not callable(fn):
            continue
        try:
            sp = fn()
        except Exception:
            sp = None
        if sp is not None:
            break
    if sp is None:
        return None
    cls = type(sp)
    n = (cls.__name__ or '').lower()
    m = (cls.__module__ or '').lower()
    label = '%s (%s) mro=%s' % (
        cls.__name__, cls.__module__,
        ','.join(c.__name__ for c in getattr(cls, '__mro__', ())[:4]))
    if label != _scene_space_logged[0]:
        _scene_space_logged[0] = label
        _plog('[HERO] space class=%s' % (label,))
    try:
        from gclient.framework.entities.hall_space import HallSpace as _HS
        if isinstance(sp, _HS):
            return 'hall'
    except Exception:
        _HS = None
    try:
        from gclient.framework.entities.space import Space as _SP
        if isinstance(sp, _SP):
            return 'match'
    except Exception:
        pass
    if 'hall' in n or 'mall' in n or 'lobby' in n or 'vault' in n:
        return 'hall'
    if ('range' in n or 'battle' in n or 'fight' in n or 'pve' in n
            or 'shooting' in n or 'game' in n):
        return 'match'
    if 'hall' in m or 'lobby' in m:
        return 'hall'
    if 'range' in m or 'battle' in m or 'gameplay' in m:
        return 'match'
    return None


def _hero_scene():
    """'hall' | 'match' | 'unknown' - the live Space decides (v6.7+)."""
    try:
        by_space = _scene_from_space()
        if by_space:
            return by_space
    except Exception:
        pass
    return 'unknown'


def _hero_scene_stable():
    """The scene we act on: a gap in detection never flips it.
    v7.30R17: simplified - the v7.30 block used this to re-push the
    striker on hall entry; with the ORIGINAL BSB block the hooks apply
    on the game's own show/load, so this only tracks + logs the scene."""
    scene = _hero_scene()
    if scene == 'unknown':
        return _scene_last[0] or 'hall'
    if scene != _scene_last[0]:
        _scene_last[0] = scene
        _scene_at[0] = time.time()
        # v7.30R20: a new space means new entities - cached visibility
        # answers from the old space are stale, drop them all.
        try:
            _vis_cache_clear()
        except Exception:
            pass
        _plog('[HERO] scene %s' % (scene,))
    return scene


def _hero_in_match():
    """True when a match / training ground is live."""
    try:
        return _hero_scene_stable() == 'match'
    except Exception:
        return False


def _hero_scene_ok(obj):
    """Only act on objects that belong to the scene we are in."""
    scene = _hero_scene_stable()
    kind = _hero_kind(obj)
    if kind is None or scene == 'unknown':
        return True
    return kind == scene


# #======================================================================
# //  DISPLAY.PY
# //
# //  This file is for: DISPLAY: the hero pick, the hand models / FPS arms (OnReloadHandModel, AddHandPrimitives), the ZLSKIN arm-clothes, the hall/combat dolls.
# //
# //  Part of the split TREACKY BS payload (v2.112).  The runtime
# //  file payload/skins_payload.py is GENERATED: run
# //  tools/build_payload.py after editing these modules.
# #======================================================================
