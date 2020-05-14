# -*- coding: utf-8 -*-
import re

from django.core.exceptions import FieldDoesNotExist
from django.db import models
from django.db.models import OneToOneField, OneToOneRel, ForeignKey, ManyToOneRel, ManyToManyField, ManyToManyRel

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

        Also sets initial to True, which states whether queryset should be optimized or not.
        """
        super(OptimizerQuerySet, self).__init__(*args, **kwargs)
        self.location = QuerySetLocation(self)
        self.initial = True

    def _populate_data(self):
        """
        Passes its data to every model instance for later usage in
        gathering column data and identifying relevant queryset.

        To be used only after _fetch_all(), it's taken for granted that
        full queryset is available on self._result_cache variable.
        """
        prefetch_lookup_names = [
            getattr(lookup, 'prefetch_through', str(lookup))
            for lookup in self._prefetch_related_lookups
        ]

        for instance in self._result_cache:
            try:
                instance.qs_location = self.location
                instance.prefetch_lookup_names = prefetch_lookup_names
            except AttributeError:
                instance['qs_location'] = self.location
                instance['prefetch_lookup_names'] = prefetch_lookup_names

    def _optimize(self):
        """
        Retrieves field sets from QuerySetFieldRegistry, then appends qs with only(), select_related()
        and prefetch_related() operations based on registry values and then updates self accordingly.

        Sets initial to False to skip optimization of any consequent querysets.
        """
        if self.location and self.initial:
            fields = field_registry.get(self.location)
            qs = self._prepare_qs(*fields)
            self.__dict__.update(qs.__dict__)
            self.initial = False

    def _fetch_all(self):
        """
        First optimizes queryset with usage of _optimize()

        Later proceeds to default _fetch_all() (which is responsible for retrieval of values from db).
        """
        self._optimize()
        super(OptimizerQuerySet, self)._fetch_all()
        self._populate_data()

    def values(self, *fields, **expressions):
        """
        Works similarly to _fetch_all, executes _optimize() and proceeds with values()
        """
        self._optimize()
        return super(OptimizerQuerySet, self).values(*fields, **expressions)

    def values_list(self, *fields, **kwargs):
        """
        Works similarly to _fetch_all, executes _optimize() and proceeds with values_list()
        """
        self._optimize()
        return super(OptimizerQuerySet, self).values_list(*fields, **kwargs)

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

        # select_related() cannot be called after values() or values_list()
        # this select_related() will be made after values(_list)() and then skipped
        if self._fields is not None:
            return qs

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

        # only() cannot be called after values() or values_list()
        # this only() will be made after values(_list)() and then skipped
        if self._fields is not None:
            return qs

        # only() without arguments acts like no-op, in this case no data should be retrieved
        # setting it to the list containing only 'id' seems to be a reasonable minimum
        fields |= {'id'}

        # if only doesn't have fields specified previously in select_related, then InvalidQuery error is raised
        # this needs to be taken care of here, fields have to contain contents of select_related field in query
        # that's why only() is executed last - this takes into account select fields added in _perform_select_related()
        select_fields = self.query.select_related
        if not isinstance(select_fields, bool):
            fields |= set(select_fields.keys())

        qs = qs.only(*fields)

        return qs


class OptimizerModel(models.Model):
    class Meta:
        abstract = True

    def __init__(self, *args, **kwargs):
        self.qs_location = ''
        self.prefetch_lookup_names = None
        super(OptimizerModel, self).__init__(*args, **kwargs)

    def __getattribute__(self, item):
        if item != '_meta' and item in [f.name for f in self._meta.get_fields()]:
            try:
                field = self._meta.get_field(item)
                self._add_select_field(field)
                self._add_prefetch_field(field)
            except FieldDoesNotExist:
                pass
        return super(OptimizerModel, self).__getattribute__(item)

    def _add_select_field(self, field):
        select_fields = [OneToOneField, OneToOneRel, ForeignKey]
        is_instance = any(isinstance(field, select) for select in select_fields)
        no_cache = not hasattr(self, field.get_cache_name())
        if is_instance and no_cache:
            field_registry.set_select(self.qs_location, [field.name])

    def _add_prefetch_field(self, field):
        prefetch_fields = [ManyToOneRel, ManyToManyField, ManyToManyRel]
        is_instance = any(isinstance(field, prefetch) for prefetch in prefetch_fields)
        no_name = self.prefetch_lookup_names is not None and field.name not in self.prefetch_lookup_names
        if is_instance and no_name:
            field_registry.set_prefetch(self.qs_location, [field.name])

    def refresh_from_db(self, using=None, fields=None):
        if fields:
            field_registry.set_only(self.qs_location, fields)
        super(OptimizerModel, self).refresh_from_db(using, fields)
