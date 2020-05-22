# -*- coding: utf-8 -*-
from django.core.exceptions import FieldDoesNotExist
from django.db import models

from django_optimizer.iterables import OptimizerModelIterable, OptimizerValuesIterable, \
    OptimizerFlatValuesListIterable, OptimizerValuesListIterable
from django_optimizer.location import QuerySetLocation
from django_optimizer.registry import field_registry


class OptimizerQuerySet(models.query.QuerySet):
    """
    QuerySet objects that optimizes its queries based on maintained register holding sets of field names.

    Based on these field names, object automatically performs only(), select_related() and prefetch_related()
    just before database query execution to optimize a query without programmer's work.
    """
    def __init__(self, *args, **kwargs):
        """
        Remembers its location, which is set in __init__() function of QuerySetLocation class.
        """
        super(OptimizerQuerySet, self).__init__(*args, **kwargs)
        self._iterable_class = OptimizerModelIterable
        self.location = QuerySetLocation(self)

    def _fetch_all(self):
        """
        First optimizes queryset with usage of _optimize()

        Later proceeds to default _fetch_all() (which is responsible for retrieval of values from db).
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
        clone._iterable_class = OptimizerValuesIterable
        return clone

    def values_list(self, *fields, **kwargs):
        """
        Calls _optimize() before super, later optimization (before _fetch_all()) will be a noop

        Also uses custom Iterable class, that populates necessary data from QuerySet to Model
        """
        self._optimize()
        flat = kwargs.get('flat', False)
        clone = super(OptimizerQuerySet, self).values_list(*fields, **kwargs)
        clone._iterable_class = OptimizerFlatValuesListIterable if flat else OptimizerValuesListIterable
        return clone

    def _optimize(self):
        """
        Retrieves field sets from QuerySetFieldRegistry, then appends qs with only(), select_related()
        and prefetch_related() operations based on registry values and then updates self accordingly.
        """
        # all of those functions doesn't make sense if object is outside of QuerySet and values(_list) has been called
        # in case of values(_list), _optimize will be manually called before them and skipped later
        if self.location and self._fields is None:
            fields = field_registry.get(self.location)
            qs = self._prepare_qs(*fields)
            self.__dict__.update(qs.__dict__)

    def _prepare_qs(self, select, prefetch, only):
        """
        Runs only(), select_related() and prefetch_related() on self, based on parameters and returns the result.

        Only needs to be last, because it needs to know full list of select_related() fields.

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
        qs = self

        # passing empty list won't invalidate previous prefetch_related() calls
        # it's here only because prefetch_related() with empty fields might crash in old versions of django
        if fields:
            qs = qs.prefetch_related(*fields)

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


class OptimizerModel(models.Model):
    class Meta:
        abstract = True

    def __init__(self, *args, **kwargs):
        super(OptimizerModel, self).__init__(*args, **kwargs)

    def __getattribute__(self, item):
        if item != '_meta':
            try:
                field = self._meta.get_field(item)
                is_relation = field.is_relation
                is_field_colname = isinstance(field, models.Field) and item == field.get_attname()
                if is_relation and not is_field_colname:
                    self._add_select_field(field)
                    self._add_prefetch_field(field)
            except FieldDoesNotExist:
                pass
        return super(OptimizerModel, self).__getattribute__(item)

    def _add_select_field(self, field):
        has_qs = hasattr(self, '_qs_location')
        to_one = field.one_to_one or field.many_to_one
        no_cache = not hasattr(self, field.get_cache_name())
        if has_qs and to_one and no_cache:
            field_registry.set_select(self._qs_location, field.name)

    def _add_prefetch_field(self, field):
        has_qs = hasattr(self, '_qs_location')
        to_many = field.one_to_many or field.many_to_many
        no_name = hasattr(self, '_prefetch_lookup_names') and field.name not in self._prefetch_lookup_names
        if has_qs and to_many and no_name:
            field_registry.set_prefetch(self._qs_location, field.name)

    def refresh_from_db(self, using=None, fields=None):
        if fields:
            field_registry.set_only(self._qs_location, *fields)
        super(OptimizerModel, self).refresh_from_db(using, fields)
