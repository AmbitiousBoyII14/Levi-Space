#!/usr/bin/env python3
"""check_payload.py - static validation harness for the concatenated payload.

The payload is ONE exec'd namespace (srcpy.cpp -> PyRun). This harness:
  1. concatenates payload/modules/*.py in build_payload ORDER and runs
     py_compile (syntax),
  2. AST-walks every file for top-level defs/assignments and FAILS on
     duplicate top-level names across files (the class of bug where
     `_get_forced_skin` got shadowed by the hero helper),
  3. resolves every loaded name against: names bound anywhere in the same
     file, top-level names from ALL files, builtins -> FAIL otherwise
     (undefined-name detector for the shared namespace),
  4. verifies the frozen native/game ABI names exist,
  5. rejects sibling-module imports (import config / from catalog import x
     would fail at runtime - the files are sections of one script).

Static checks only. Runtime behaviour is proven by device logs, never by
this tool. Usage: python3 tools/check_payload.py <tree_root>
"""
import ast
import builtins
import py_compile
import sys
import tempfile
import os

FROZEN_ABI = [
    'sync_attrs', '_read_udp_thread', 'EspUpdate', 'AIMUpdate',
    'on_space_tick', 'WEP', 'WEP_NAMES',
]

SIBLING = set()  # filled from ORDER at runtime

# Wrap-chain rebinds: a later name rebind (`_x = newer_impl`) layered over an
# earlier def that stays alive as the captured previous link. Verified per-pair
# by capture analysis (see reconstruct_w2.py header) - these are by design.
CHAIN_OK = {
    ('scopesync.py', '_v841_skin_ids', 'kills.py'):
        'scopesync:632 captures kills def -> _v218m_skin_ids wraps',
    ('scopesync.py', '_v842g_feature_kinds', 'kills.py'):
        'scopesync:648+1656 capture kills def (two wrap layers)',
    ('scopesync.py', '_v842g_feature_number', 'kills.py'):
        'scopesync:669 captures kills def',
    ('scopesync.py', '_fx_mirror_case', 'equip.py'):
        'scopesync:1287 captures equip def -> _v218a_mirror_case wraps',
    ('scopesync.py', '_install_effect_util_hooks', 'weapon.py'):
        'scopesync:1530 captures weapon def -> _v218a_install wraps',
    ('scopesync.py', '_apply_weapon_case_skin', 'weapon.py'):
        'scopesync:1628+6337 capture chain (a -> scope wrap layers)',
    ('scopesync.py', '_v842g_record_supports', 'kills.py'):
        'scopesync:1686 captures kills def',
    ('scopesync.py', '_v842g_refresh_kill_feed', 'kills.py'):
        'scopesync kbc layer captures kills def (kbc -> bc2 wraps)',
    ('scopesync.py', '_v218drop_note_local', 'equip.py'):
        'scopesync:3868 captures equip def -> _v218display wraps',
    ('scopesync.py', '_v218drop_forced_skin', 'equip.py'):
        'scopesync:3880 captures equip def -> _v218display wraps',
    ('scopesync.py', '_v31_weapon_fx_pump', 'equip.py'):
        'scopesync:6353 captures equip def -> _v218scope_pump wraps',
    ('rpcs.py', '_v218m_panel_invoke', 'scopesync.py'):
        'rpcs:6985 captures scopesync chain -> _v218u_panel_invoke wraps',
    ('scopesync.py', 'note_local', 'equip.py'):
        'scopesync:3884 captures equip def -> drop_note_with_snapshot wraps',
}



def load_order(root):
    path = os.path.join(root, 'tools_order.txt')
    if os.path.exists(path):
        return [l.strip() for l in open(path) if l.strip()]
    # fall back to build_payload.py's ORDER
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'build_payload.py')).read()
    ns = {}
    start = src.index('ORDER = [')
    end = src.index(']', start) + 1
    exec(src[start:end], ns)
    return ns['ORDER']


class FileScan(ast.NodeVisitor):
    def __init__(self):
        self.bound = set()
        self.loads = set()
        self.toplevel = {}     # name -> (kind, lineno)
        self.sibling_imports = []

    def _bind(self, name):
        if name:
            self.bound.add(name)

    # -- bindings -----------------------------------------------------
    def visit_FunctionDef(self, node):
        self._bind(node.name)
        for a in (node.args.posonlyargs + node.args.args + node.args.kwonlyargs):
            self._bind(a.arg)
        if node.args.vararg:
            self._bind(node.args.vararg.arg)
        if node.args.kwarg:
            self._bind(node.args.kwarg.arg)
        for d in node.decorator_list:
            self.visit(d)
        for d in node.args.defaults + node.args.kw_defaults:
            if d:
                self.visit(d)
        for st in node.body:
            self.visit(st)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node):
        self._bind(node.name)
        for b in node.bases:
            self.visit(b)
        for st in node.body:
            self.visit(st)

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Store) or isinstance(node.ctx, ast.Del):
            self._bind(node.id)
        elif isinstance(node.ctx, ast.Load):
            self.loads.add(node.id)

    def visit_Import(self, node):
        for a in node.names:
            self._bind(a.asname or a.name.split('.')[0])
            if a.name.split('.')[0] in SIBLING:
                self.sibling_imports.append((node.lineno, a.name))

    def visit_ImportFrom(self, node):
        if node.module and node.module.split('.')[0] in SIBLING:
            self.sibling_imports.append((node.lineno, node.module))
        for a in node.names:
            self._bind(a.asname or a.name)

    def visit_ExceptHandler(self, node):
        self._bind(node.name)
        for st in node.body:
            self.visit(st)
        if node.type:
            self.visit(node.type)

    def visit_Global(self, node):
        for n in node.names:
            self._bind(n)

    visit_Nonlocal = visit_Global

    def visit_arg(self, node):
        self._bind(node.arg)

    def visit_comprehension(self, node):
        self.visit(node.target)
        for x in [node.iter] + list(node.ifs):
            self.visit(x)

    def visit_Lambda(self, node):
        for a in (node.args.posonlyargs + node.args.args + node.args.kwonlyargs):
            self._bind(a.arg)
        if node.args.vararg:
            self._bind(node.args.vararg.arg)
        if node.args.kwarg:
            self._bind(node.args.kwarg.arg)
        self.visit(node.body)

    def visit_With(self, node):
        for item in node.items:
            self.visit(item.context_expr)
            if item.optional_vars:
                self.visit(item.optional_vars)
        for st in node.body:
            self.visit(st)

    visit_AsyncWith = visit_With

    def visit_For(self, node):
        self.visit(node.target)
        self.visit(node.iter)
        for st in node.body + node.orelse:
            self.visit(st)

    visit_AsyncFor = visit_For


def toplevel_names(tree):
    out = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.setdefault(node.name, (type(node).__name__, node.lineno))
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                for n in ast.walk(t):
                    if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
                        # only direct targets count as definitions; a name
                        # inside Subscript (_x[0] = ...) is a mutation
                        parent_direct = True
                        stack = [t]
                        # crude parent check: Name must not sit under Subscript
                        for sub in ast.walk(t):
                            if isinstance(sub, ast.Subscript):
                                for n2 in ast.walk(sub):
                                    if n2 is n:
                                        parent_direct = False
                        if parent_direct:
                            out.setdefault(n.id, ('assign', node.lineno))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            out.setdefault(node.target.id, ('ann', node.lineno))
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for a in node.names:
                out.setdefault(a.asname or a.name.split('.')[0],
                               ('import', node.lineno))
        elif isinstance(node, ast.Try):
            for st in node.body + node.orelse + node.finalbody:
                if isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    out.setdefault(st.name, (type(st).__name__, node.lineno))
    return out


def main(root):
    order = load_order(root)
    SIBLING.update(os.path.splitext(n)[0] for n in order)
    moddir = os.path.join(root, 'payload', 'modules')
    pieces, scans, tl_all = [], {}, {}
    failures = []

    for name in order:
        p = os.path.join(moddir, name)
        if not os.path.exists(p):
            failures.append('MISSING module: %s' % name)
            continue
        src = open(p, encoding='utf-8').read()
        pieces.append(src)
        tree = ast.parse(src, filename=name)
        scan = FileScan()
        scan.visit(tree)
        scans[name] = scan
        tl = toplevel_names(tree)
        tl_all.setdefault(name, {}).update(tl)
        print('%-18s defs=%3d loads=%4d bound=%4d lines=%5d' % (
            name,
            sum(1 for k, (kind, _) in tl.items() if kind.endswith('FunctionDef') or kind == 'ClassDef'),
            len(scan.loads), len(scan.bound), src.count('\n') + 1))

    # 1. syntax of the concatenation
    whole = '\n'.join(pieces)
    with tempfile.NamedTemporaryFile('w', suffix='.py', delete=False) as t:
        t.write(whole)
        tmp = t.name
    try:
        py_compile.compile(tmp, doraise=True)
        print('SYNTAX (concatenated): OK')
    except py_compile.PyCompileError as e:
        failures.append('SYNTAX: %s' % e)
    finally:
        os.unlink(tmp)

    # 2. duplicate top-level names across files
    seen = {}
    chains = []
    for fname, tl in tl_all.items():
        for n, (kind, lineno) in tl.items():
            if n.startswith('__'):
                continue
            # stdlib re-imports in several files are harmless (same module)
            benign = (kind == 'import' and n in ('re', 'json', 'sys', 'os', 'time',
                                          'threading', 'socket', 'struct',
                                          'math', 'random', 'collections',
                                          'itertools', 'functools', 'traceback',
                                          'importlib', 'inspect', 'copy',
                                          'binascii', 'array', 'base64',
                                          'hashlib', 'weakref'))
            if n in seen and seen[n][0] != fname and not benign:
                chain = (fname, n, seen[n][0])
                if chain in CHAIN_OK:
                    chains.append('%s: %s over %s - %s' % (
                        fname, n, seen[n][0], CHAIN_OK[chain]))
                else:
                    failures.append('DUP-TOPLEVEL %s: %s:%d and %s:%d' % (
                        n, fname, lineno, seen[n][0], seen[n][1]))
            seen.setdefault(n, (fname, lineno))

    # 3. name resolution across the shared namespace
    globals_all = set(seen) | set(builtins.__dict__)
    globals_all.update(['__name__', '__file__', '__builtins__', '__doc__',
                        'exec', 'getattr', 'setattr', 'globals', 'locals',
                        'vars', 'dir', 'next', 'iter', 'super', 'property',
                        'staticmethod', 'classmethod', 'enumerate', 'zip',
                        'range', 'print', 'open', 'hash', 'id', 'object',
                        'Exception', 'BaseException', 'type', 'TypeError',
                        'ValueError', 'KeyError', 'AttributeError',
                        'RuntimeError', 'StopIteration', 'NotImplementedError',
                        'isinstance', 'issubclass', 'callable', 'repr',
                        'sorted', 'reversed', 'any', 'all', 'min', 'max',
                        'sum', 'abs', 'round', 'map', 'filter', 'list',
                        'dict', 'set', 'tuple', 'str', 'int', 'float',
                        'bool', 'bytes', 'bytearray', 'frozenset', 'slice',
                        'staticmethod', 'None', 'True', 'False', 'Ellipsis',
                        'NotImplemented', 'memoryview', 'complex', 'divmod',
                        'pow', 'format', 'hash', 'ascii', 'bin', 'hex',
                        'oct', 'chr', 'ord', 'len', 'input', 'help'])
    for fname, scan in scans.items():
        missing = sorted(n for n in scan.loads
                         if n not in globals_all and n not in scan.bound)
        for n in missing[:20]:
            failures.append('UNDEFINED %s: %s' % (fname, n))
        if len(missing) > 20:
            failures.append('UNDEFINED %s: ... +%d more' % (fname, len(missing) - 20))
        for lineno, mod in scan.sibling_imports:
            failures.append('SIBLING-IMPORT %s:%d import %s' % (fname, lineno, mod))

    # 4. frozen ABI
    for abi in FROZEN_ABI:
        if abi not in globals_all:
            failures.append('ABI-MISSING: %s' % abi)

    for c in chains:
        print('CHAIN-REBIND (documented):', c)
    print()
    if failures:
        print('FAIL (%d)' % len(failures))
        for f in failures[:60]:
            print('  ', f)
        sys.exit(1)
    print('CHECK_PAYLOAD: ALL OK  (%d files, %d top-level names, '
          '%d documented chain rebinds)' % (len(scans), len(seen), len(chains)))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '.')
