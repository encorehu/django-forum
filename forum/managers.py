from django.db import models
from django.db.models import Q

class ForumManager(models.Manager):
    def for_user(self, user):
        if user and user.is_authenticated():
            public_query = Q(allowed_users__isnull=True)
            user_query   = Q(allowed_users=user)
            return self.filter(public_query|user_query).distinct()
        return self.filter(allowed_users__isnull=True)

    def for_groups(self, groups):
        if groups:
            public_query      = Q(groups__isnull=True)
            user_groups_query = Q(groups__in=groups)
            return self.filter(public_query|user_groups_query).distinct()
        return self.filter(groups__isnull=True)
    
    def has_access(self, forum, user):
        return forum in self.for_user(user)

    def has_access2(self, forum, groups):
        return forum in self.for_groups(groups)
