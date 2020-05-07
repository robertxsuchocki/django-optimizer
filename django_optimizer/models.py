# -*- coding: utf-8 -*-
from django.db import models

from django_optimizer.location import QuerySetLocation
from django_optimizer.registry import field_registry


# TODO reconsider
# class LoggingQuerySet(models.query.QuerySet):
#     def __bool__(self):
#         if not self._result_cache:
#             print(type(self).__name__ + ' evaluated to check for truthiness')
#             return super(LoggingQuerySet, self).__bool__()
#
#     def __len__(self):
#         if not self._result_cache:
#             print(type(self).__name__ + ' evaluated to check for length')
#             return super(LoggingQuerySet, self).__len__()
#
#
# class LoggingModel(models.Model):
#     class Meta:
#         abstract = True
#
#     def __getattribute__(self, item):
#         if item != '_meta' and item in [f.name for f in self._meta.get_fields()]:
#             print(type(self).__name__ + '.' + item)
#         return super(LoggingModel, self).__getattribute__(item)


class OptimizerQuerySet(models.query.QuerySet):
    """
    QuerySet objects that optimizes its queries based on maintained register holding lists of field names.

    Based on these field names, object automatically performs only(), select_related() and prefetch_related()
    just before database query execution to optimize a query without programmer's work.
    """
    def __init__(self, *args, **kwargs):
        """
        Additionally remembers its location, which is set in __init__() function of QuerySetLocation class
        """
        super(OptimizerQuerySet, self).__init__(*args, **kwargs)
        self.location = QuerySetLocation(self)

    def _fetch_all(self):
        """
        Retrieves field lists from QuerySetFieldRegistry, then appends qs with only(), select_related()
        and prefetch_related() operations based on registry values and then updates self accordingly

        Finally proceeds to default _fetch_all() (which is responsible for retrieval of values from db).
        """
        fields = field_registry.get(self.location)
        qs = self._prepare_qs(*fields)
        self.__dict__.update(qs.__dict__)
        super(OptimizerQuerySet, self)._fetch_all()  # noqa

    def _prepare_qs(self, only, select, prefetch):
        """
        Runs only(), select_related() and pretech_related() on self, based on parameters and returns the result

        :param only: field names to use with only()
        :param select: field names to use with select_related()
        :param prefetch: field names to use with prefetch_related()
        :return: final queryset object
        """
        qs = self

        # only() without arguments acts like no-op, in this case no data should be retrieved
        # setting it to the list containing only 'id' seems to be a reasonable minimum
        only = only or ['id']
        qs = qs.only(*only)

        # if there are no fields, select_related() shouldn't be called at all
        # passing None clears the list (and selects added manually by a programmer)
        # passing empty list turns on select on all fields (opposite to this case)
        if select:
            qs = qs.select_related(*select)

        # passing empty list won't invalidate previous prefetch_related() calls
        # it's here only because prefetch_related() with empty fields might crash in old versions of django
        if prefetch:
            qs = qs.prefetch_related(*prefetch)

        return qs
