# ============================================================
# GAME_API.PY
# PROVIDES: verified game-module access layer. Every gclient/gshare
#           touchpoint in the payload goes through this file:
#           import cache, proto/data accessors, HOOK decorator,
#           wrap/install helpers, backup registry, signature probes.
# REQUIRES: config.sync_attrs (optional), main.log (guarded)
# ABI (never rename): _proto_get _data_items _data_get _proto_keys
#   _safe_int _import_module _exc_text HOOK _Missing
#   Space EquipCaseFactory Doll HallShowModel
# ============================================================
"""Verified game-API access layer.

Design rules (see REWRITE_PLAN.md):
* No game API is called from anywhere except through the helpers here or
  through class objects imported here. Every class/method referenced must
  exist in the runtime/SDK dumps (research/game_runtime_sdk_reference.md).
* Missing classes degrade to ``_Missing`` so hook installs log instead of
  raising; nothing is ever fabricated in their place.
* Hook backups live in one registry (HOOKS) as well as the historical
  ``_<Method>`` attribute the game-side code already looks for.
"""
import importlib as _importlib
import sys as _sys

# ---------------------------------------------------------------- logging
def _log(msg):
    """Forward to the boot logger when available (main.py owns it)."""
    fn = _sys.modules.get('__main__', _sys.modules.get('builtins'))
    fn = globals().get('log_line') or globals().get('_plog')
    if callable(fn):
        try:
            fn(msg)
        except Exception:
            pass


# ---------------------------------------------------------------- imports
_import_cache = {}


def _import_module(module_name):
    """Cached game-module import; returns None when unavailable."""
    try:
        return _importlib.import_module(module_name)
    except Exception:
        return None


class _Missing:
    """Sentinel for an unavailable game class; hook installs skip it."""
    pass


def import_game_class(module_name, class_name):
    """Import one game class, degrade to _Missing with a log line."""
    try:
        mod = _import_module(module_name)
        cls = getattr(mod, class_name, None) if mod is not None else None
        if isinstance(cls, type):
            return cls
    except Exception as exc:
        _log('[IMPORT] %s.%s failed: %r' % (module_name, class_name, exc))
        return _Missing
    _log('[IMPORT] %s.%s missing' % (module_name, class_name))
    return _Missing


# Frozen well-known targets (dump-verified, reference S2.1/S2.2):
Space = import_game_class('gclient.framework.entities.space', 'Space')
EquipCaseFactory = import_game_class(
    'gclient.gameplay.logic_base.equips.equip_case', 'EquipCaseFactory')
Doll = import_game_class('gclient.gamesystem.entities.hall_doll', 'Doll')
HallShowModel = import_game_class(
    'gclient.gamesystem.models.hall_show_model', 'HallShowModel')

# full doll family (dump S2.1 hall_doll: Doll, DollLike,
# CalculationDoll, BigHeadCalculationDoll)
DollLike = import_game_class(
    'gclient.gamesystem.entities.hall_doll', 'DollLike')
CalculationDoll = import_game_class(
    'gclient.gamesystem.entities.hall_doll',
    'CalculationDoll')
BigHeadCalculationDoll = import_game_class(
    'gclient.gamesystem.entities.hall_doll',
    'BigHeadCalculationDoll')


# ------------------------------------------------------- proto/data access
def _safe_int(value, default=0):
    try:
        if isinstance(value, bool):
            return int(value)
        return int(value)
    except Exception:
        return default


safe_int = _safe_int


def _proto_get(proto, key, default=None):
    """Read one field from a game proto (taggeddict/dict/attr)."""
    if proto is None:
        return default
    try:
        getter = getattr(proto, 'get', None)
        if callable(getter):
            value = getter(key, default)
            if value is not None:
                return value
    except Exception:
        pass
    try:
        return getattr(proto, key, default)
    except Exception:
        return default


proto_get = _proto_get


def _proto_keys(proto, limit=50):
    try:
        keys = getattr(proto, 'keys', None)
        if callable(keys):
            return list(keys())[:limit]
        if isinstance(proto, dict):
            return list(proto.keys())[:limit]
    except Exception:
        pass
    return []


def _data_items(data):
    """[(key, value)] for a game data table (dict-like); [] otherwise."""
    if data is None:
        return []
    try:
        items = getattr(data, 'items', None)
        if callable(items):
            return list(items())
        if isinstance(data, dict):
            return list(data.items())
    except Exception:
        pass
    return []


def _data_get(data, key, default=None):
    if data is None:
        return default
    try:
        getter = getattr(data, 'get', None)
        if callable(getter):
            return getter(key, default)
        return data[key]
    except Exception:
        return default


# ---------------------------------------------------------------- strings
def _exc_text():
    try:
        import traceback
        return traceback.format_exc(limit=10)
    except Exception:
        try:
            return repr(_sys.exc_info()[1])
        except Exception:
            return '<unknown exception>'


# ----------------------------------------------------------------- hooks
HOOKS = {}   # (class_name, method) -> {'backup': name, 'original': fn}


def HOOK(clazz, bLog=True, _name=None):
    """Install ``func`` as ``Clazz.<func.__name__>``.

    Idempotent, reported, never swallows the wrapped call's behaviour: the
    installed callable IS the user's function. The original is preserved at
    ``Clazz._<Method>`` (the game-side convention) and in HOOKS.
    """
    def decorator(func):
        name = func.__name__
        backup = _name or ('_' + name)
        try:
            if clazz is None or clazz is _Missing:
                _log('[HOOK] SKIP %s.%s (class missing)'
                     % (getattr(clazz, '__name__', clazz), name))
                return func
            if backup in getattr(clazz, '__dict__', {}):
                if bLog:
                    _log('[HOOK] already installed %s.%s'
                         % (clazz.__name__, name))
                return func
            orig = getattr(clazz, name, None)
            if not callable(orig):
                _log('[HOOK] MISSING %s.%s left untouched'
                     % (clazz.__name__, name))
                return func
            setattr(clazz, backup, orig)
            setattr(clazz, name, func)
            HOOKS[(clazz.__name__, name)] = {'backup': backup,
                                             'original': orig}
            if bLog:
                _log('[HOOK] OK %s.%s' % (clazz.__name__, name))
        except Exception as exc:
            _log('[HOOK] ERROR %s.%s: %r'
                 % (getattr(clazz, '__name__', clazz), name, exc))
        return func
    return decorator


def wrap_method(clazz, method_name, factory):
    """Install ``factory(original)``-style wrapper; returns True on success.

    Used where the wrapper must call through (icon factories, refresh
    wrappers). Marker ``_treacky_wrap`` keeps installs idempotent.
    """
    try:
        if clazz is None or clazz is _Missing:
            return False
        prev = getattr(clazz, method_name, None)
        if not callable(prev) or getattr(prev, '_treacky_wrap', False):
            return False
        wrapped = factory(prev)
        if not callable(wrapped):
            return False
        wrapped._treacky_wrap = True
        setattr(clazz, method_name, wrapped)
        HOOKS[(getattr(clazz, '__name__', '?'), method_name)] = {
            'backup': '_' + method_name, 'original': prev, 'wrap': True}
        return True
    except Exception:
        return False


def install_module(target, name, factory):
    """Module-level wrap/install: factory(original) -> replacement."""
    try:
        if target is None or target is _Missing:
            return 0
        prev = getattr(target, name, None)
        if not callable(prev) or getattr(prev, '_treacky_wrap', False):
            return 0
        repl = factory(prev)
        if not callable(repl):
            return 0
        repl._treacky_wrap = True
        setattr(target, name, repl)
        return 1
    except Exception:
        return 0


def probe_signature(obj, name):
    """Best-effort (args, defaults, varargs) for a callable; None if absent.
    Diagnostic use only - never required for behaviour."""
    try:
        import inspect
        fn = getattr(obj, name, None)
        if not callable(fn):
            return None
        while isinstance(fn, (staticmethod, classmethod)):
            fn = fn.__func__
        sig = inspect.signature(fn)
        return str(sig)
    except Exception:
        return None


def class_flag(obj, name, default=False):
    """Read an entity Is* class flag (dump S2.2 flag family)."""
    try:
        return bool(getattr(obj, name, default))
    except Exception:
        return default
