#!/usr/bin/env python
# -*- encoding: utf-8 -*-
# ---------------------------------------------------------------------
# xotl.ql.translation.py
# ---------------------------------------------------------------------
# Copyright (c) 2013-2016 Merchise Autrement and Contributors
# All rights reserved.
#
# This is free software; you can redistribute it and/or modify it under
# the terms of the LICENCE attached in the distribution package.
#
# Created on 2013-04-03

from __future__ import (division as _py3_division,
                        print_function as _py3_print,
                        absolute_import as _py3_abs_import)


class ExecPlan(object):
    # The map, join, zero, and unit are provided for tests.
    def __init__(self, query, map=None, join=None, zero=None, unit=None):
        from ._monads import _mc
        self.query = query
        self.map = '__x_map_%s' % id(self) if not map else map
        self.join = '__x_join_%s' % id(self) if not join else join
        self.zero = '__x_zero_%s' % id(self) if not zero else zero
        self.unit = '__x_unit_%s' % id(self) if not unit else unit
        self.plan = plan = _mc(query.qst, map=self.map, join=self.join,
                               zero=self.zero, unit=self.unit)
        self.compiled = compile(plan, '', 'eval')

    def explain(self):
        import dis
        print('\nOriginal query QST')
        print(str(self.query.qst))
        print('\nMonadic plan')
        print(str(self.plan))
        print('\nCompiled')
        dis.dis(self.compiled)

    def _plan_dict_(self, other, modules=None, use_ignores=True):
        from xotl.ql.core import this
        universe = lambda: PythonObjectsCollection(
            modules,
            use_ignores=use_ignores
        )
        return {
            name: (val if val is not this else universe())
            for name, val in other.items()
        }

    def __call__(self, modules=None, use_ignores=True):
        from xoutil.collections import ChainMap
        # In the following we use a 'mathematical' notation for variable
        # names: `f` stands for function, `l` stands for list (or collection),
        # `lls` stands for list of lists and `x` any item in a list.
        __do_plan = self._do_plan
        __l = {
            # These functions must return iterators since the _mc uses results
            # from
            self.map: lambda f: lambda l: iter(f(x) for x in __do_plan(l)),
            self.join: lambda lls: iter(x for l in lls for x in l),
            self.unit: lambda x: iter([x]),
            self.zero: lambda: iter([]),
        }
        return eval(
            self.compiled,
            # Don't split the globals and locals... Why?
            #
            # When we parse the byte-code, opcodes like LOAD_NAME, LOAD_FAST,
            # LOAD_DEREF, and LOAD_LOCAL are all cast to a the same QST
            # `qst.Name(..., qst.Load())` where the local/global/cell
            # distinction is lost.
            #
            # The 'core.py' treats the name '.0' specially since they're most
            # likely subqueries.  But then, those subqueries carry their own
            # local/global and the loss of context can lead to bad guesses.
            #
            # This is evident in the the implementation of `thesefy`, where
            # the 'self' is confused with a global.
            #
            dict(ChainMap(
                self._plan_dict_(self.query.locals, modules, use_ignores),
                self._plan_dict_(self.query.globals, modules, use_ignores),
                __l
            ))
        )

    def _do_plan(self, what):
        from xotl.ql.interfaces import QueryObject
        if isinstance(what, QueryObject):
            return ExecPlan(
                what,
                map=self.map,
                join=self.join,
                unit=self.unit,
                zero=self.zero
            )
        else:
            return what

    def __iter__(self):
        return self()


class _TestPlan(ExecPlan):
    def __init__(self, query):
        super(_TestPlan, self).__init__(
            query,
            map='Map',
            join='Join',
            zero='Empty',
            unit='Unit'
        )


class PythonObjectsCollection(object):
    '''Represent the entire collection of Python objects.'''

    def __init__(self, modules=None, use_ignores=True):
        self.modules = modules
        self.use_ignores = use_ignores

    @property
    def collection(self):
        modules = self.modules
        if modules:
            res = _iter_objects(accept=_filter_by_pkg(*modules),
                                use_ignores=self.use_ignores)
        else:
            res = _iter_objects(use_ignores=self.use_ignores)
        return res

    def __iter__(self):
        return self.collection


def _iter_objects(accept=None, use_ignores=False):
    '''Iterates over all objects currently in Python's VM memory for which
    ``accept(ob)`` returns True.

    '''
    import gc
    if use_ignores:
        filterby = lambda x: not defined(x, _avoid_modules) and (
            not accept or accept(x))
    else:
        filterby = accept
    return (ob for ob in gc.get_objects()
            if not isinstance(ob, type) and (not filterby or filterby(ob)))


def defined(who, modules):
    '''Checks if `who` (or its class) is defined in any of the given
    `modules`.

    The `modules` sequence may contains elements ending in ".*" to signify a
    package.

    '''
    if not isinstance(who, type):
        mod = type(who).__module__
    else:
        mod = who.__module__

    def check(target):
        if target.endswith('.*'):
            return mod.startswith(target[:-2])
        else:
            return mod == target
    return any(check(target) for target in modules)


def _iter_classes(accept=None, use_ignores=False):
    '''Iterates over all the classes currently in Python's VM memory
    for which `accept(cls)` returns True.

    If use_ignores is True classes and objects of types defined in xotl.ql's
    modules and builtins will be also ignored.

    '''
    import gc
    if use_ignores:
        filterby = lambda x: not defined(x, _avoid_modules) and (
            not accept or accept(x))
    else:
        filterby = accept
    return (ob for ob in gc.get_objects()
            if isinstance(ob, type) and (not filterby or filterby(ob)))


# Real signature is _filter_by_pkg(*pkg_names, negate=False)
def _filter_by_pkg(*pkg_names, **kwargs):
    '''Returns an `accept` filter for _iter_classes/_iter_objects that only
    accepts classes/objects defined in pkg_names.

    '''
    negate = kwargs.get('negate', False)

    def accept(cls):
        result = defined(cls, pkg_names)
        return result if not negate else not result
    return accept


# Modules whose objects are always "outside" this translator's view of the
# universe.
_avoid_modules = (
    'xotl.ql.*', 'xoutil.*', 'py.*', 'IPython.*',
    # The name of the builtins module is different in Pythons versions.
    type(1).__module__
)
