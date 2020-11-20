from django.db import models, router, transaction
from django.db.transaction import get_connection

from django_optimizer.registry import model_registry
from django_optimizer.transaction import get_db_instance, DeferredPK, DeferredAtomic


class DeferredModel(models.Model):
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        def _get_signal_params(obj, **obj_kwargs):
            return {
                'sender': obj.__class__,
                'instance': obj,
                'created': obj._state.adding,
                'update_fields': obj_kwargs.get('update_fields'),
                'raw': obj_kwargs.get('raw', False),
                'using': obj_kwargs.get('using', router.db_for_write(obj.__class__, instance=obj))
            }

        if getattr(get_connection(), DeferredAtomic.connection_attr_name, None) != DeferredAtomic.__name__:
            super(DeferredModel, self).save(*args, **kwargs)
        else:
            models.signals.pre_save.send(**_get_signal_params(self, **kwargs))
            model_registry.add(get_db_instance(self))
            setattr(self, self._meta.pk.attname, DeferredPK(self))
            models.signals.post_save.send(**_get_signal_params(self, **kwargs))
