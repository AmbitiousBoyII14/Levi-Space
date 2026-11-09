#!/usr/bin/env python3
# build_payload.py - re-serialize payload/skins_payload.py from the split
# source modules (payload/modules/*.py, in MODULE ORDER).  Run this after
# editing any module, BEFORE regen_srcpy.py.  Validates with py_compile.
import io, os, py_compile, sys, tempfile

# MUST match tools/split_payload.py MODULE order = the file order.
GENERATED_BANNER = ('# GENERATED FILE - DO NOT EDIT.\n'
                    '# Source: payload/modules/*.py concatenated by tools/build_payload.py.\n'
                    '# Edit the modules, then re-run build_payload.py + regen_srcpy.py.\n'
                    '# ============================================================\n')

ORDER = ['config.py', 'names.py', 'main.py', 'game_api.py', 'catalog.py', 'weapon.py', 'equip.py', 'esp.py', 'display.py',
         'striker_skin.py', 'unlocks.py', 'kills.py', 'scopesync.py',
         'cosmetics.py', 'melee.py', 'rpcs.py']


def main(root):
    moddir = os.path.join(root, 'payload', 'modules')
    parts = []
    for name in ORDER:
        path = os.path.join(moddir, name)
        parts.append(io.open(path, encoding='utf-8').read())
    src = GENERATED_BANNER + ''.join(parts)
    out = os.path.join(root, 'payload', 'skins_payload.py')
    with io.open(out, 'w', encoding='utf-8') as f:
        f.write(src)
    # validate before declaring success
    with tempfile.NamedTemporaryFile('w', suffix='.py', delete=False) as t:
        t.write(src)
        tmp = t.name
    try:
        py_compile.compile(tmp, doraise=True)
    finally:
        os.unlink(tmp)
    print('build_payload: %d modules -> %s (%d lines) COMPILE_OK'
          % (len(ORDER), out, src.count('\n')))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '.')
