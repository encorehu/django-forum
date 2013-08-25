from django.contrib import admin
from django.db import models
from django.contrib.admin.widgets import FilteredSelectMultiple
from forum.models import Forum, Thread, Post, Subscription

class ForumAdmin(admin.ModelAdmin):
    list_display = ('title', '_parents_repr')
    list_filter = ('groups',)
    ordering = ['ordering', 'parent', 'title']
    prepopulated_fields = {"slug": ("title",)}
    raw_id_fields = ['allowed_users']
    formfield_overrides = {
        models.ManyToManyField: {'widget': FilteredSelectMultiple("allowed users",is_stacked=False) },
    }
    #raw_id_fields = ['allowed_users']

class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ['author','thread']

class ThreadAdmin(admin.ModelAdmin):
    list_display = ('title', 'forum', 'latest_post_time')
    list_filter = ('forum',)

admin.site.register(Forum, ForumAdmin)
admin.site.register(Thread, ThreadAdmin)
admin.site.register(Post)
admin.site.register(Subscription, SubscriptionAdmin)
