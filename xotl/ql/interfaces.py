# -*- encoding: utf-8 -*-
# ---------------------------------------------------------------------
# xotl.ql.interfaces
# ---------------------------------------------------------------------
# Copyright (c) 2012-2016 Merchise Autrement and Contributors
# All rights reserved.
#
# This is free software; you can redistribute it and/or modify it under the
# terms of the LICENCE attached (see LICENCE file) in the distribution
# package.
#
# Created on Aug 23, 2012

'''Interfaces that describe the major types used in the Query Language API,
and some internal interfaces as well.


'''

from __future__ import (division as _py3_division,
                        print_function as _py3_print,
                        absolute_import as _py3_abs_import)


try:
    from xoutil.eight.meta import metaclass
except ImportError:
    from xoutil.objects import metaclass


class InterfaceType(type):
    def __instancecheck__(self, instance):
        import types
        attrs = [attr for attr, val in self.__dict__.items()
                 if isinstance(val, (Attribute, types.FunctionType))]
        res = True
        while res and attrs:
            attr = attrs.pop()
            res = hasattr(instance, attr)
        return res
    __subclasscheck__ = __instancecheck__


class Interface(metaclass(InterfaceType)):
    '''Define an interface.

    Interfaces support a weak 'instance' test definition::

      >>> class IStartswith(Interface):
      ...    def startswith():
      ...        pass

      >>> isinstance('', IStartswith)
      True

    '''


class Attribute(object):
    def __init__(self, name, doc):
        self.name = name
        self.__doc__ = doc


class QueryObject(Interface):
    '''The required API-level interface for query objects.

    Query objects provide access to the QST for the query.

    '''
    qst = Attribute('qst', 'The Query Syntax Tree')
    partition = Attribute('partition', 'A slice indicating how much to fetch '
                          'from the data store.  The interpretation of this '
                          'slice value should be consistent with that of '
                          'Python own slice type.')

    locals = Attribute(
        'locals',
        'A MappingView for the locals in the query scope. '
        'See `get_name`:method:'
    )

    globals = Attribute(
        'globals',
        'A MappingView for the globals in the query scope.'
        'See `get_name`:method:'
    )

    def limit_by(self, limit):
        '''Return a new query object limited by limit.

        If this query object already has a limit it will be ignore.

        '''

    def offset(self, offset):
        '''Return a new query object with a new offset.'''

    def get_name(self, name, only_globals=False):
        '''Give the value for the `name`.

        Queries are defined in a scope where they could access any name
        (e.g. variables).  The translator may need to access the value of such
        names.

        Get name will prefer locals over globals unless `only_globals` is
        True.

        '''


class QueryExecutionPlan(Interface):
    '''Required API-level interface for a query execution plan.

    '''
    query = Attribute(
        'query',
        'The original query object this plan was built from.  Even if the '
        'translator was given a query expression directly, like in most of '
        'our examples, this must be a query object.'
    )

    def __call__(self, **kwargs):
        '''Execution plans are callable.

        Return an `iterator`:term:.  The returned iterator must produce the
        objects retrieved from the query.  Also it must not be confused with
        other iterators returned and once exhausted it won't produce more
        objects.

        Translators are required to properly document the optional keyword
        arguments.  Positional arguments are not allowed.  All arguments must
        be optional.

        .. note:: The restrictions on the returned iterator make it easy to
           reason about it.  However obtaining a simple Cartesian product
           would require a call to `itertools.tee`:func:::

               >>> from xotl.ql import this
               >>> from xotl.ql.translation.py import naive_translation
               >>> query = naive_translation(which for which in this)

               >>> from itertools import tee
               >>> from xoutil.eight import zip
               >>> product = zip(tee(query()))

           Doing a simple ``zip(query(), query())`` would work without error
           but between the first call to ``query()`` and the second the world
           might have changed the returned objects would not be the same.

        '''

    def __iter__(self):
        '''Execution plans are iterable.

        This is exactly the same as calling the plan without any arguments:
        ``plan()``.

        '''
        return self()


class QueryTranslator(Interface):
    '''A query translator.

    .. note:: Since Python classes are callable, you may implement a
       translator/execution plan in a single class::

         >>> class ExecutionPlan(object):
         ...     def __init__(self, query, **kwargs):
         ...         pass
         ...
         ...     def __call__(self, **options):
         ...         pass
         ...
         ...     def __iter__(self):
         ...         return self()


    '''
    def __call__(self, query, **kwargs):
        '''Return an execution plan for the given `query`.

        :param query: The query to be translated.  Translators must allow this
                       object to be either a `query expression` or a `query
                       object` that complies with the interface
                       `QueryObject`:class:.

        Translators are allowed to provide other keyword-only arguments.
        Translators' authors are encouraged to properly document those
        arguments.

        :return: The query execution plan.
        :rtype: `QueryExecutionPlan`:class:

        '''
        pass
