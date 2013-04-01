#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#----------------------------------------------------------------------
# xotl.ql.translate
#----------------------------------------------------------------------
# Copyright (c) 2012, 2013 Merchise Autrement and Contributors
# All rights reserved.
#
# This is free software; you can redistribute it and/or modify it under
# the terms of the LICENCE attached in the distribution package.
#
# Created on Jul 2, 2012

'''The main purposes of this module are two:

- To provide common query/expression translation framework from query
  objects to data store languages.

- To provide a testing bed for queries to retrieve real objects from
  somewhere (in this case the Python's).

'''

from __future__ import (division as _py3_division,
                        print_function as _py3_print,
                        unicode_literals as _py3_unicode,
                        absolute_import as _py3_abs_imports)

from xoutil.context import context
from xoutil.proxy import unboxed, UNPROXIFING_CONTEXT
from xoutil.modules import modulemethod

from zope.interface import Interface, implementer

from xotl.ql.expressions import ExpressionTree
from xotl.ql.interfaces import (ITerm,
                                IExpressionTree,
                                IQueryObject,
                                IQueryTranslator,
                                IQueryExecutionPlan)

__docstring_format__ = 'rst'
__author__ = 'manu'


def _iter_classes(accept=lambda x: True):
    '''Iterates over all the classes currently in Python's VM memory
    for which `accept(cls)` returns True.

    '''
    import gc
    return (ob for ob in gc.get_objects()
                if isinstance(ob, type) and accept(ob))


def _filter_by_pkg(pkg_name):
    '''Returns an `accept` filter for _iter_classes that only accepts classes
    of a given package name.

    '''
    def accept(cls):
        return cls.__module__.startswith(pkg_name)
    return accept


def _iter_objects(accept=lambda x: True):
    '''Iterates over all objects currently in Python's VM memory for which
    ``accept(ob)`` returns True.

    '''
    import gc
    return (ob for ob in gc.get_objects
                if not isinstance(ob, type) and accept(ob))


def _instance_of(which):
    '''Returns an `accept` filter for :func:`_iter_objects` or
    :func:`_iter_classes` that only accepts objects that are instances of
    `which`; `which` may be either a class or an Interface
    (:mod:`!zope.interface`).

    '''
    def accept(ob):
        return isinstance(ob, which) or (issubclass(which, Interface) and
                                         which.providedBy(ob))
    return accept


def cotraverse_expression(*expressions, **kwargs):
    '''Coroutine that traverses expression trees an yields every node that
    matched the `accept` predicate. If `accept` is None it defaults to accept
    only :class:`~xotl.ql.interface.ITerm` instances that have a non-None
    `name`.

    :param expressions: Several :term:`expression tree` objects (or
                        :term:`query objects <query object>`) to traverse.

    :param accept: A function that is passed every node found the trees that
                   must return True if the node should be yielded.

    Coroutine behavior:

    You may reintroduce both `expr` and `accept` arguments by sending messages
    to this coroutine. The message may be:

    - A single callable value, which will replace `accept`.

    - A single non callable value, which will be considered *another*
      expression to process. Notice this won't make `cotraverse_expression` to
      stop considering all the nodes from previous expressions. However, the
      expression might be explored before other later generated children of the
      previous expressions.

    - A tuple consisting in `(expr, accept)` that will be treated like the
      previous cases.

    - A dict that may have `expr` and `accept` keys.

    The default behavior helps to catch all named
    :class:`xotl.ql.interfaces.ITerm` instances in an expression. This is
    useful for finding every "name" in a query, which may not appear in the
    query selection. For instance we, may have a model that relates Person
    objects indirectly via a Relation object::

        >>> from xotl.ql.core import thesefy
        >>> @thesefy()
        ... class Person(object):
        ...     pass

        >>> @thesefy()
        ... class Relation(object):
        ...    pass

    Then, for the following query::

        >>> from xotl.ql.core import these
        >>> from xoutil.compat import izip
        >>> query = these((person, partner)
        ...               for person, partner in izip(Person, Person)
        ...               for rel in Relation
        ...               if (rel.subject == person) & (rel.obj == partner))

    if we need to find every single named term in the filters of the query, we
    would see that there are seven:

    - `person`, `partner` and `rel` (as given by the `is_instance(...)`
      filters ``@thesefy`` injects)

    - `rel.subject`, `person`, `rel.obj` and `partner` in the explicit
       filter::

        >>> len(list(cotraverse_expression(*query.filters)))
        7

    '''
    is_expression = IExpressionTree.providedBy
    accept = kwargs.get('accept', lambda x: _instance_of(ITerm)(x) and x.name)
    with context(UNPROXIFING_CONTEXT):
        queue = list(expressions)
        while queue:
            current = queue.pop(0)
            msg = None
            if accept(current):
                msg = yield current
            if is_expression(current):
                queue.extend(current.children)
                named_children = current.named_children
                queue.extend(named_children[key] for key in named_children)
            if msg:
                if callable(msg):
                    accept = msg
                elif isinstance(msg, tuple):
                    expr, accept = msg
                    queue.append(expr)
                elif isinstance(msg, dict):
                    expr = msg.get('expr', None)
                    if expr:
                        queue.append(expr)
                    accept = msg.get('accept', accept)
                else:
                    queue.append(msg)


def cocreate_plan(query, **kwargs):
    '''**Not implemented yet**. The documentation provided is just an idea.

    Builds a :term:`query execution plan` for a given query that fetches
    objects from Python's VM memory.

    This function is meant to be general enough so that other may use
    it as a base for building their :term:`translators <query
    translator>`.

    It works like this:

    1. First it inspect the tokens and their relations (if a token is
       the parent of another). For instance in the query::

           query = these((parent, child)
                         for parent in this
                         if parent.children & (parent.age > 34)
                         for child in parent.children if child.age < 5)

       The `parent.children` generator tokens is *derived* from the
       token `this`, so there should be a relation between the two.

       .. todo::

          If we allow to have subqueries, it's not clear how to
          correlate tokens. A given token may be a whole query::

              p = these((parent, partner)
                        for parent in this('parent')
                        for partner, _ in subquery((partner, partner.depth())
                                            for partner in this
                                            if contains(partner.related_to,
                                                        parent)))

          Since all examples so far of sub-queries as generators
          tokens are not quite convincing, we won't consider that.

    '''
    pass

def _to_python_expression(expression):
    with context(UNPROXIFING_CONTEXT):
        if ITerm.providedBy(expression):
            parent = expression.parent
            if parent is None:
                return expression.name
            else:
                return _to_python_expression(expression.parent) + '.' + expression.name
        elif IExpressionTree.providedBy(expression):
            operation = expression.operation
            result = operation.arity.formatter(operation,
                                               expression.children,
                                               expression.named_children,
                                               _str=_to_python_expression)
            return result
        else:
            return repr(expression)


def evaluate(expression, table):
    expr = _to_python_expression(expression)
    return eval(expr, table, table)


def cmp_terms(t1, t2, strict=False):
    '''Compares two terms in a partial order.

    This is a *partial* compare operator. A term `t1 < t2` if and only if `t1` is
    in the parent-chain of `t2`.

    If `strict` is False the comparison between expressions will be made with
    the `eq` operation; otherwise `is` will be used.

    If either `t1` or `t2` are generator tokens it's
    :attr:`~xotl.ql.interfaces.IGeneratorToken.expression` is used instead.

    Examples::

        >>> from xotl.ql.core import this, these
        >>> t1 = this('a').b.c
        >>> t2 = this('b').b.c.d
        >>> t3 = this('a').b

        >>> cmp_terms(t1, t3)
        1

        # But if equivalence is False neither t1 < t3 nor t3 < t1 holds.
        >>> cmp_terms(t1, t3, True)
        0

        # Since t1 and t2 have no comon ancestor, they are not ordered.
        >>> cmp_terms(t1, t2)
        0

        >>> query = these((child, brother)
        ...               for parent in this
        ...               for child in parent.children
        ...               for brother in parent.children
        ...               if child is not brother)

        >>> t1, t2, t3 = query.tokens

        >>> cmp_terms(t1, t2)
        -1

        >>> cmp_terms(t2, t3)
        0

    '''
    import operator
    if not strict:
        test = operator.eq
    else:
        test = operator.is_
    with context(UNPROXIFING_CONTEXT):
        from ..interfaces import IGeneratorToken
        if IGeneratorToken.providedBy(t1):
            t1 = t1.expression
        if IGeneratorToken.providedBy(t2):
            t2 = t2.expression
        if test(t1, t2):
            return 0
        else:
            t = t1
            while t and not test(t, t2):
                t = t.parent
            if t:
                return 1
            t = t2
            while t and not test(t, t1):
                t = t.parent
            if t:
                return -1
            else:
                return 0


def token_before_filter(tk, expr, strict=False):
    '''Partial order (`<`) compare function between a token (or term) and an
    expression.

    A token or term *is before* an expression if it is before any of the terms
    in the expression.
    '''
    with context(UNPROXIFING_CONTEXT):
        signature = tuple(cmp_terms(tk, term, strict) for term in cotraverse_expression(expr))
        if any(mark == -1 for mark in signature):
            return True
        else:
            return False


def cmp(a, b):
    '''Partial compare function between tokens and expressions.

    Examples::

       >>> from xotl.ql import this, these
       >>> query = these((parent, child)
       ...               for parent in this
       ...               for child in parent.children
       ...               if parent.age > 34
       ...               if child.age < 6)

       >>> parent_token, children_token = query.tokens
       >>> expr1, expr2 = query.filters

       >>> cmp(parent_token, expr1)
       -1

       >>> cmp(children_token, parent_token)
       1

       >>> cmp(expr1, children_token)
       0

       >>> import functools
       >>> l = [expr1, expr2, parent_token, children_token]
       >>> l.sort(key=functools.cmp_to_key(cmp))
       >>> expected = [parent_token, expr1, children_token, expr2]
       >>> all(l[i] is expected[i] for i in (0, 1, 2, 3))
       True
    '''
    from ..interfaces import IGeneratorToken, IExpressionCapable
    if IGeneratorToken.providedBy(a) and IGeneratorToken.providedBy(b):
        return cmp_terms(a, b, True)
    elif IGeneratorToken.providedBy(a) and IExpressionCapable.providedBy(b):
        return -1 if token_before_filter(a, b) else 0
    elif IExpressionCapable.providedBy(a) and IGeneratorToken.providedBy(b):
        return 1 if token_before_filter(b, a) else 0
    else:
        return 0


def naive_translation(query, **kwargs):
    '''Does a naive translation to Python's VM memory.
    '''
    class _new(object): pass
    def new(cls, *args, **attrs):
        if cls == object:
            if args:
                raise TypeError("'object' expects no positional arguments; "
                                "{0} were provided".format(len(args)))
            from xoutil.compat import iteritems_
            result = _new()
            for k, v in iteritems_(attrs):
                setattr(result, k, v)
            return result
        else:
            return cls(*args, **attrs)

    def plan():
        table = {'is_instance': lambda x, y: isinstance(x, y),
                 'all': all,
                 'any': any,
                 'max': max,
                 'min': min,
                 'length': len,
                 'count': len,
                 'abs': abs,
                 'call': lambda t, *args, **kwargs: t(*args, **kwargs),
                 'new': new
        }
        # Since tokens are actually stored in the same order they are
        # found in the query expression, there's no risk in using the
        # given order to fetch the objects.
        #
        # The algorithm is simple; first we "intertwine" tokens and filters
        # using a (stable) partial order: a filter comes before a token if and
        # only if neither of it's terms is bound to the token.
        pass
    return plan


@modulemethod
def init(self, settings=None):
    '''Registers the implementation in this module as an
    IQueryTranslator for an object model we call "Python Object
    Model". Also we register this model as the default for the
    current :term:`registry`.

    .. warning::

       Don't call this method in your own code, since it will
       override all of your query-related configuration.

       This is only intended to allow testing of the translation
       common framework by configuring query translator that searches
       over Python's VM memory.

    '''
    from zope.component import getSiteManager
    from zope.interface import directlyProvides
    from ..interfaces import IQueryConfiguration
    directlyProvides(self, IQueryConfiguration, IQueryTranslator)
    manager = getSiteManager()
    configurator = manager.queryUtility(IQueryConfiguration)
    if configurator:
        pass
    else:
        manager.registerUtility(self, IQueryConfiguration)
    manager.registerUtility(self, IQueryTranslator)