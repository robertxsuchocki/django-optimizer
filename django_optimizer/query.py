# -*- coding: utf-8 -*-
"""
Query module - OptimizerQuerySet definition
"""
from django.db import models
from django.db.models import Prefetch

from django_optimizer.conf import settings
from django_optimizer.iterables import LoggingModelIterable, LoggingValuesIterable, \
    LoggingFlatValuesListIterable, LoggingValuesListIterable
from django_optimizer.location import ObjectLocation
from django_optimizer.registry import field_registry


class OptimizerQuerySet(models.query.QuerySet):
    """
    QuerySet objects that optimizes its queries based on maintained register holding sets of field names

    Based on these field names, object automatically performs only(), select_related() and prefetch_related()
    just before database query execution to optimize a query without programmer's work
    """
    def __init__(self, *args, **kwargs):
        """
        Remembers its location, which is set in __init__() function of ObjectLocation class
        """
        super(OptimizerQuerySet, self).__init__(*args, **kwargs)
        self._enabled = not settings.DJANGO_OPTIMIZER_DISABLE_OPTIMIZATION
        self._location = ObjectLocation(self.model.__name__)
        self._iterable_class = LoggingModelIterable

    def _fetch_all(self):
        """
        First optimizes queryset with usage of _optimize()

        Later proceeds to default _fetch_all() (which is responsible for retrieval of values from db)
        """
        self._optimize()
        super(OptimizerQuerySet, self)._fetch_all()

    def values(self, *fields, **expressions):
        """
        Calls _optimize() before super, later optimization (before _fetch_all()) will be a noop

        Also uses custom Iterable class, that populates necessary data from QuerySet to Model
        """
        self._optimize()
        clone = super(OptimizerQuerySet, self).values(*fields, **expressions)
        clone._iterable_class = LoggingValuesIterable
        return clone

    def values_list(self, *fields, **kwargs):
        """
        Calls _optimize() before super, later optimization (before _fetch_all()) will be a noop

        Also uses custom Iterable class, that populates necessary data from QuerySet to Model
        """
        self._optimize()
        flat = kwargs.get('flat', False)
        clone = super(OptimizerQuerySet, self).values_list(*fields, **kwargs)
        clone._iterable_class = LoggingFlatValuesListIterable if flat else LoggingValuesListIterable
        return clone

    def _optimize(self):
        """
        Retrieves field sets from QuerySetFieldRegistry, then appends qs with only(), select_related()
        and prefetch_related() operations based on registry values and then updates self accordingly
        """
        # should be a noop if optimization is turned off or object is outside of QuerySet
        # in case of _fetch_all() _optimize() is expected to be called once, before self._result_cache field creation
        # in case of values(_list), _optimize() will be manually called before them and skipped later
        if self._enabled and self._location and self._result_cache is None and self._fields is None:
            fields = field_registry.get(self._location)
            qs = self._prepare_qs(*fields)
            self.__dict__.update(qs.__dict__)

    def _prepare_qs(self, select, prefetch, only):
        """
        Runs only(), select_related() and prefetch_related() on self, based on parameters and returns the result

        Only needs to be last, because it needs to know full list of select_related() fields

        :param only: field names to use with only()
        :param select: field names to use with select_related()
        :param prefetch: field names to use with prefetch_related()
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

        return qs

    def _perform_prefetch_related(self, fields):
        from django_optimizer.wrappers import optimizer_query_set_wrapper

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
                queryset = optimizer_query_set_wrapper(model)
                prefetch_obj = Prefetch(field.name, queryset=queryset)
                qs = qs.prefetch_related(prefetch_obj)

        return qs

    def _perform_only(self, fields):
        qs = self

        # only() without arguments acts like no-op, in this case no data should be retrieved
        # setting it to the list containing only 'id' seems to be a reasonable minimum
        fields |= {'id'}

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
