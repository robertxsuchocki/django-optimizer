# -*- coding: utf-8 -*-
"""
Query module - SelectiveQuerySet and DeferredQuerySet definition
"""
from django.db import models
from django.db.models import Prefetch
from django.db.models.query import ModelIterable

from django_optimizer.conf import settings
from django_optimizer.iterables import LoggingModelIterable, LoggingValuesIterable, LoggingValuesListIterable
from django_optimizer.location import ObjectLocation
from django_optimizer.registry import field_registry, code_registry


class LoggingPrefetch(Prefetch):
    """
    Prefetch object, which was defined as a workaround: Django source code checks parameter _iterable_class for equality
    with class ModelIterable to determine whether .values() was used or not (raising an exception if needed).

    LoggingPrefetch replaces LoggingModelIterable with ModelIterable before __init__() (so no exceptions are raised)
    and reverts this change later
    """
    def __init__(self, lookup, queryset=None, to_attr=None):
        if queryset._iterable_class == LoggingModelIterable:
            queryset._iterable_class = ModelIterable
        super(LoggingPrefetch, self).__init__(lookup, queryset, to_attr)
        queryset._iterable_class = LoggingModelIterable


class SelectiveQuerySet(models.query.QuerySet):
    """
    QuerySet class that optimizes its queries based on maintained register holding sets of field names

    Based on these field names, object automatically performs only(), select_related() and prefetch_related()
    just before database query execution to optimize a query without programmer's work
    """

    def __init__(self, *args, **kwargs):
        """
        Remembers its location, which is set in __init__() function of ObjectLocation class
        """
        super(SelectiveQuerySet, self).__init__(*args, **kwargs)
        self._live_optimization = settings.DJANGO_OPTIMIZER_LIVE_OPTIMIZATION
        self._offsite_optimization = settings.DJANGO_OPTIMIZER_OFFSITE_OPTIMIZATION
        self._location = ObjectLocation(self.model.__name__, self._offsite_optimization)
        self._registry_fields = field_registry.get(self._location)
        self._without_only = not self._registry_fields[field_registry.ONLY]

    def _fetch_all(self):
        """
        First optimizes queryset with usage of _optimize() and refreshes db if objects are hanging

        Then proceeds to default _fetch_all() (which is responsible for retrieval of values from db)
        """
        self._optimize()
        super(SelectiveQuerySet, self)._fetch_all()

    def values(self, *fields, **expressions):
        """
        Calls _optimize() before super, later optimization (before _fetch_all()) will be a noop

        Also uses custom Iterable class, that populates necessary data from QuerySet to Model
        """
        self._optimize()
        clone = super(SelectiveQuerySet, self).values(*fields, **expressions)
        clone._iterable_class = LoggingValuesIterable
        return clone

    def values_list(self, *fields, **kwargs):
        """
        Calls _optimize() before super, later optimization (before _fetch_all()) will be a noop

        Also uses custom Iterable class, that populates necessary data from QuerySet to Model
        """
        self._optimize()
        flat = kwargs.get('flat', False)
        clone = super(SelectiveQuerySet, self).values_list(*fields, **kwargs)
        if not flat:
            clone._iterable_class = LoggingValuesListIterable
        return clone

    def _optimize(self):
        """
        Retrieves field sets from FieldRegistry, then appends qs with only(), select_related()
        and prefetch_related() operations based on registry values and then updates self accordingly
        """
        # should be a noop if object is outside of QuerySet
        # in case of _fetch_all() _optimize() is expected to be called once, before self._result_cache field creation
        # in case of values(_list), _optimize() will be manually called before them and skipped later
        if self._location and self._result_cache is None and self._fields is None:
            if self._live_optimization:
                qs = self._prepare_qs(*self._registry_fields)
                self.__dict__.update(qs.__dict__)
                if self._offsite_optimization:
                    self._log_qs()

            if self._iterable_class is ModelIterable:
                self._iterable_class = LoggingModelIterable

    def _log_qs(self):
        """
        Uses _prepare_qs to generate code, that can be used to make the same optimizations in source code

        :return: string containing generated code containing optimizations
        """
        def _get_listed_args(iterable):
            def _get_arg_repr(obj):
                if isinstance(obj, str):
                    return "'{}'".format(obj)
                elif isinstance(obj, Prefetch):
                    return _prefetch_string_repr(obj)
            return ', '.join(map(_get_arg_repr, iterable))

        def _queryset_string_repr(queryset):
            def _function_application(function_name, args):
                return '.{}({})'.format(function_name, _get_listed_args(args)) if args else ''

            select_code = _function_application('select_related', queryset.query.select_related or [])
            prefetch_code = _function_application('prefetch_related', queryset._prefetch_related_lookups)
            only_code = _function_application('only', queryset.query.deferred_loading[0])

            return select_code + prefetch_code + only_code

        def _prefetch_string_repr(prefetch):
            prefetch.queryset._optimize()
            return "Prefetch('{field}', queryset={model}.objects.all(){queryset})".format(
                field=prefetch.prefetch_through,
                model=prefetch.queryset.model.__name__,
                queryset=_queryset_string_repr(prefetch.queryset),
            )

        code_registry.add(self._location, _queryset_string_repr(self))

    def _prepare_qs(self, select, prefetch, only):
        """
        Runs only(), select_related() and prefetch_related() on self, based on parameters and returns the result

        Only needs to be last, because it needs to know full list of select_related() fields

        :param select: field names to use with select_related()
        :param prefetch: field names to use with prefetch_related()
        :param only: field names to use with only()
        :return: final queryset object
        """
        return self._perform_select_related(select)._perform_prefetch_related(prefetch)._perform_only(only)

    def _perform_select_related(self, fields):
        qs = self

        # if user deliberately wants to select all fields, then it shouldn't be optimized
        if self.query.select_related is True:
            return qs

        # if there are no fields, select_related() shouldn't be called at all
        # passing None clears the list (and selects added manually by a programmer)
        # passing empty list turns on select on all fields (opposite to this case)
        if fields:
            qs = qs.select_related(*fields)

        # select_for_update doesn't support select_related on nullable field at least for PostgreSQL
        # select fields are checked and removed if they're nullable to prevent errors
        if qs.select_for_update and not isinstance(qs.query.select_related, bool):
            def _filter_nullable_fields(model, field_dict):
                new_dict = dict()
                for key, value in field_dict.iteritems():
                    field = model._meta.get_field(key)
                    if not field.null:
                        new_dict[key] = _filter_nullable_fields(field.related_model, value)
                return new_dict

            qs.query.select_related = _filter_nullable_fields(qs.model, qs.query.select_related)

        return qs

    def _perform_prefetch_related(self, fields):
        from django_optimizer.wrappers import selective_query_set_wrapper

        qs = self

        # for all labels Prefetch object gets created with dynamically mixined queryset
        # used to enable optimization of these querysets in prefetch objects
        # without field queryset being declared as optimized in models
        for label in fields:
            prefetch_lookups = [
                getattr(lookup, 'prefetch_through', str(lookup)) for lookup in self._prefetch_related_lookups
            ]
            if label not in prefetch_lookups:
                field = self.model._meta.get_field(label)
                model = field.model if self.model != field.model else field.related_model
                queryset = selective_query_set_wrapper(model)
                prefetch_obj = LoggingPrefetch(field.name, queryset=queryset)
                qs = qs.prefetch_related(prefetch_obj)

        return qs

    def _perform_only(self, fields):
        qs = self

        # first evaluation of a queryset skips only for performance reasons (.only('id') was painfully slow)
        # instead on first evaluation most common fields are gathered even if they exist in an object
        # every evaluation after that will consider whether field exist or not prior to adding it to fields
        if not fields:
            return qs

        # if only doesn't have fields specified previously in select_related, then InvalidQuery error is raised
        # this needs to be taken care of here, fields have to contain contents of select_related field in query
        # that's why only() is executed last - this takes into account select fields added in _perform_select_related()
        select_fields = self.query.select_related
        if not isinstance(select_fields, bool):
            fields |= set(select_fields.keys())

        # here previous manual only() and defer() invocations are taken into consideration
        # it's essential to have refresh_from_db() work correctly as it uses only() with own fields and default_manager
        # lack of it resulted in refresh_from_db() being unable to refetch field deferred by _perform_only
        initial_fields, defer = self.query.deferred_loading
        if defer:
            fields -= initial_fields
        else:
            fields |= initial_fields

        qs = qs.only(*fields)

        return qs

    def _add_field(self, field, index):
        if field not in self._registry_fields[index]:
            self._registry_fields = field_registry.add(self._location, index, field)

    def _add_select(self, field):
        self._add_field(field, field_registry.SELECT)

    def _add_prefetch(self, field):
        self._add_field(field, field_registry.PREFETCH)

    def _add_only(self, field):
        self._add_field(field, field_registry.ONLY)


class DeferredQuerySet(models.query.QuerySet):
    """
    QuerySet class that delays database inserts in DeferredAtomic block

    DeferredAtomic block checks whether object is an instance of this class before deferring saves,
    also the class itself performs save on cached data early if queries are being done on deferred model
    """
    def _refresh_db(self):
        from django_optimizer.transaction import perform_deferred_db_queries

        perform_deferred_db_queries(self.model)

    def _fetch_all(self):
        """
        Saves deferred data to db before any queryset evaluation
        """
        self._refresh_db()
        super(DeferredQuerySet, self)._fetch_all()

    def count(self):
        """
        Refreshes db if objects' saves are deferred and _fetch_all wasn't used
        """
        if self._result_cache is None:
            self._refresh_db()
        return super(DeferredQuerySet, self).count()

    def exists(self):
        """
        Refreshes db if objects' saves are deferred and _fetch_all wasn't used
        """
        if self._result_cache is None:
            self._refresh_db()
        return super(DeferredQuerySet, self).exists()


class OptimizerQuerySet(SelectiveQuerySet, DeferredQuerySet):
    pass
