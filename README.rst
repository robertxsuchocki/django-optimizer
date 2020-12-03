================
Django Optimizer
================

Django Optimizer is a Django app to automatically optimize queries for querysets based on their usage within the project.

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

3. By default, optimizer uses file-based cache to store data needed in query optimization. To change location or type of this cache, define `DJANGO_OPTIMIZER_FIELD_REGISTRY` variable in your project's settings like this (variable fields are equivalent to django's `CACHES` variable) ::

    # These are default settings, using persistent version of file-based django cache and
    # storing this cache in `.django_optimizer_field_registry` subdirectory of your project
    DJANGO_OPTIMIZER_FIELD_REGISTRY = {
        'BACKEND': 'django_optimizer.cache.PersistentFileBasedCache',
        'LOCATION': os.path.join(django.conf.settings.BASE_DIR, '.django_optimizer_field_registry')
    }

4. For default cache settings, add this line to `.gitignore` file to disable tracking of cache files ::

    # django-optimizer's cache files
    .django_optimizer_field_registry/

5. To enable optimization of a queryset, add OptimizerQuerySet to its definition, like this::

    from django_optimizer.query import OptimizerQuerySet


    class CustomQuerySet(models.query.QuerySet, OptimizerQuerySet):
        (...)

5. In the end in order to take advantage of save deferring, DeferredModel has to be used in model definition::

    from django_optimizer.models import DeferredModel


    class CustomModel(DeferredModel):
        objects = CustomQuerySet.as_manager()
        (...)



