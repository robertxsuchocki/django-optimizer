# -*- coding: utf-8 -*-
from django_optimizer.base import OptimizerModel
from django_optimizer.iterables import OptimizerModelIterable
from django_optimizer.location import ObjectLocation
from django_optimizer.query import OptimizerQuerySet


def optimizer_query_set_wrapper(model):
    queryset = model.objects.all()

    if not isinstance(queryset, OptimizerQuerySet):
        queryset.__class__ = type(
            'DjangoOptimizer' + type(queryset).__name__,
            (OptimizerQuerySet, type(queryset)),
            {
                '__module__': queryset.__module__
            }
        )
        queryset._location = ObjectLocation(queryset.model.__name__)
        queryset._iterable_class = OptimizerModelIterable

    return queryset


def optimizer_model_wrapper(model):
    if not isinstance(model, OptimizerModel) and not isinstance(model, dict):
        model.__class__ = type(
            'DjangoOptimizer' + type(model).__name__,
            (OptimizerModel, type(model)),
            {
                '__module__': model.__module__
            }
        )

    return model
