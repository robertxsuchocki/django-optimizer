=========
Optimizer
=========

Optimizer is a Django app to automatically optimize queries for querysets based on their usage within the project.

Detailed documentation is in the "docs" directory.

Quick start
-----------

1. Install from cloned repo::

    pip install . 

2. Add 'django-optimizer' to your INSTALLED_APPS setting like this::

    INSTALLED_APPS = [
        ...
        'django-optimizer',
    ]

3. To enable logging of a model or queryset, add LoggingModelMixin or LoggingQuerySetMixin to its definition, like this::

    class CustomModel(models.Model, LoggingModelMixin):


    class CustomQuerySet(models.query.QuerySet, LoggingQuerySetMixin):



