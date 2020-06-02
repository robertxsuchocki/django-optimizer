# -*- coding: utf-8 -*-
"""
Iterables module containing iterables objects that are later used by
OptimizerQuerySet objects to enable logging from fetched objects
"""
from django.db.models.query import ModelIterable, ValuesIterable, ValuesListIterable, FlatValuesListIterable

from django_optimizer.conf import settings


class LoggingIterable(object):
    """
    Passes queryset data to every model instance for later usage in
    gathering column data and identifying relevant queryset

    Needs to be added to every Iterable class to make sure every object has these attributes
    """
    def __iter__(self):
        from django_optimizer.wrappers import logging_model_wrapper

        for obj in super(LoggingIterable, self).__iter__():
            if settings.DJANGO_OPTIMIZER_DISABLE_LOGGING:
                yield obj
            else:
                try:
                    obj._queryset = self.queryset
                except AttributeError:
                    obj['_queryset'] = self.queryset
                yield logging_model_wrapper(obj)


class LoggingModelIterable(LoggingIterable, ModelIterable):
    pass


class LoggingValuesIterable(LoggingIterable, ValuesIterable):
    pass


class LoggingValuesListIterable(LoggingIterable, ValuesListIterable):
    pass


class LoggingFlatValuesListIterable(LoggingIterable, FlatValuesListIterable):
    pass
