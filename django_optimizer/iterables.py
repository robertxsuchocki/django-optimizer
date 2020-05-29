# -*- coding: utf-8 -*-
from django.db.models.query import ModelIterable, ValuesIterable, ValuesListIterable, FlatValuesListIterable

from django_optimizer.conf import settings
from django_optimizer.location import ObjectLocation


class LoggingIterable(object):
    """
    Passes queryset data to every model instance for later usage in
    gathering column data and identifying relevant queryset.

    Needs to be added to every Iterable class to make sure every object has these attributes
    """
    def __iter__(self):
        from django_optimizer.wrappers import logging_model_wrapper

        qs = self.queryset
        location = getattr(qs, '_location', ObjectLocation(qs.model.__name__))
        prefetch_lookup_names = [
            getattr(lookup, 'prefetch_through', str(lookup))
            for lookup in qs._prefetch_related_lookups
        ]

        for obj in super(LoggingIterable, self).__iter__():
            if settings.DJANGO_OPTIMIZER_DISABLE_LOGGING:
                yield obj
            else:
                try:
                    obj._qs_location = location
                    obj._prefetch_lookup_names = prefetch_lookup_names
                except AttributeError:
                    obj['_qs_location'] = location
                    obj['_prefetch_lookup_names'] = prefetch_lookup_names
                yield logging_model_wrapper(obj)


class LoggingModelIterable(LoggingIterable, ModelIterable):
    pass


class LoggingValuesIterable(LoggingIterable, ValuesIterable):
    pass


class LoggingValuesListIterable(LoggingIterable, ValuesListIterable):
    pass


class LoggingFlatValuesListIterable(LoggingIterable, FlatValuesListIterable):
    pass
