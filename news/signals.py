from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ValidationError
from django.db.models.signals import m2m_changed, post_save
from django.dispatch import receiver

from .models import User


ROLE_PERMISSIONS = {
    User.Role.READER: ["view_article", "view_newsletter"],
    User.Role.PUBLISHER: ["view_article", "view_newsletter", "view_publisher"],
    User.Role.EDITOR: [
        "view_article",
        "change_article",
        "delete_article",
        "approve_article",
        "view_newsletter",
        "change_newsletter",
        "delete_newsletter",
    ],
    User.Role.JOURNALIST: [
        "add_article",
        "view_article",
        "change_article",
        "delete_article",
        "add_newsletter",
        "view_newsletter",
        "change_newsletter",
        "delete_newsletter"
    ],
}


@receiver(post_save, sender=User)
def assign_role_group(sender, instance, **kwargs):
    """Keep exactly one role group in sync with the user's role."""
    role_group_names = [label for _, label in User.Role.choices]
    group = {
        role: Group.objects.get_or_create(name=label)[0]
        for role, label in User.Role.choices
    }
    instance.groups.remove(*Group.objects.filter(name__in=role_group_names))
    group = group[instance.role]
    permissions = Permission.objects.filter(
        codename__in=ROLE_PERMISSIONS[instance.role]
    )
    group.permissions.set(permissions)
    instance.groups.add(group)
    if instance.role != User.Role.READER:
        instance.subscribed_publishers.clear()
        instance.subscribed_journalists.clear()


@receiver(m2m_changed, sender=User.subscribed_publishers.through)
def restrict_publisher_subscriptions(
    sender, instance, action, reverse, pk_set, **kwargs
):
    """Only reader accounts may be added as publisher subscribers."""
    if action != "pre_add":
        return
    if reverse:
        invalid = User.objects.filter(
            pk__in=pk_set
        ).exclude(role=User.Role.READER)
        if invalid.exists():
            raise ValidationError("Only readers may subscribe to publishers.")
    elif instance.role != User.Role.READER:
        raise ValidationError("Only readers may subscribe to publishers.")


@receiver(m2m_changed, sender=User.subscribed_journalists.through)
def restrict_journalist_subscriptions(
    sender, instance, action, reverse, pk_set, **kwargs
):
    """Subscriptions must connect readers to journalist accounts."""
    if action != "pre_add":
        return
    if reverse:
        if instance.role != User.Role.JOURNALIST:
            raise ValidationError("Readers may subscribe only to journalists.")
        invalid = User.objects.filter(pk__in=pk_set).exclude(
            role=User.Role.READER
        )
        if invalid.exists():
            raise ValidationError("Only readers may subscribe to journalists.")
    else:
        if instance.role != User.Role.READER:
            raise ValidationError("Only readers may have subscriptions.")
        invalid = User.objects.filter(pk__in=pk_set).exclude(
            role=User.Role.JOURNALIST
        )
        if invalid.exists():
            raise ValidationError("Readers may subscribe only to journalists.")
