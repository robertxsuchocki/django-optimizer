from django.db import models, router
from django.db.transaction import get_connection

from django_optimizer.registry import model_registry
from django_optimizer.transaction import get_db_instance, DeferredPK, DeferredAtomic


class DeferredModel(models.Model):
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        def _get_signal_params(**obj_kwargs):
            return {
                'sender': self.__class__,
                'instance': self,
                'created': self._state.adding,
                'update_fields': obj_kwargs.get('update_fields'),
                'raw': obj_kwargs.get('raw', False),
                'using': obj_kwargs.get('using', router.db_for_write(self.__class__, instance=self))
            }

        def _get_instance_with_duplicate_handling():
            model_registry.delete_by_ref(self._meta.model, id(self))
            current = get_db_instance(self, with_ref=True)
            return current

        if getattr(get_connection(), DeferredAtomic.connection_attr_name, None) != DeferredAtomic.__name__:
            super(DeferredModel, self).save(*args, **kwargs)
        else:
            models.signals.pre_save.send(**_get_signal_params(**kwargs))
            model_registry.add(_get_instance_with_duplicate_handling())
            setattr(self, self._meta.pk.attname, DeferredPK(self))
            models.signals.post_save.send(**_get_signal_params(**kwargs))

    def __del__(self):
        if not hasattr(self, '_deferred_obj'):
            model_registry.remove_refs(self._meta.model, id(self))
