# -*- coding: utf-8 -*-
from django.db.models.query import ModelIterable, ValuesIterable, ValuesListIterable, FlatValuesListIterable

from django_optimizer.location import ObjectLocation


class OptimizerIterable(object):
    """
    Passes queryset data to every model instance for later usage in
    gathering column data and identifying relevant queryset.

    Needs to be added to every Iterable class to make sure every object has these attributes
    """
    def __iter__(self):
        qs = self.queryset
        location = ObjectLocation(qs.model.__name__)
        prefetch_lookup_names = [
            getattr(lookup, 'prefetch_through', str(lookup))
            for lookup in qs._prefetch_related_lookups
        ]

        for obj in super(OptimizerIterable, self).__iter__():
            try:
                obj._qs_location = location
                obj._prefetch_lookup_names = prefetch_lookup_names
            except AttributeError:
                obj['_qs_location'] = location
                obj['_prefetch_lookup_names'] = prefetch_lookup_names
            yield obj


class OptimizerModelIterable(OptimizerIterable, ModelIterable):
    pass


class OptimizerValuesIterable(OptimizerIterable, ValuesIterable):
    pass


class OptimizerValuesListIterable(OptimizerIterable, ValuesListIterable):
    pass


class OptimizerFlatValuesListIterable(OptimizerIterable, FlatValuesListIterable):
    pass
