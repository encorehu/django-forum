"""
URLConf for Django-Forum.

django-forum assumes that the forum application is living under
/forum/.

Usage in your base urls.py:
    (r'^forum/', include('forum.urls')),

"""

from django.conf.urls.defaults import *
from forum.models import Forum
from forum.feeds import RssForumFeed, AtomForumFeed
from forum.sitemap import ForumSitemap, ThreadSitemap, PostSitemap
from forum.views import ForumIndexView, \
                        ForumView, \
                        ThreadCreateView, \
                        ThreadView, \
                        PostCreateView, \
                        SubscriptionUpdateView

sitemap_dict = {
    'forums': ForumSitemap,
    'threads': ThreadSitemap,
    'posts': PostSitemap,
}

urlpatterns = patterns('',
    url(r'^$', ForumIndexView.as_view(), name='forum_index'),
    #(r'^(?P<url>(rss).*)/$', RssForumFeed()),
    (r'^(?P<url>(atom).*)/$', AtomForumFeed()),
    
    url(r'^thread/(?P<thread>[0-9]+)/$',           ThreadView.as_view(), name='forum_view_thread'),
    url(r'^thread/(?P<thread>[0-9]+)/reply/$', PostCreateView.as_view(), name='forum_reply_thread'),

    url(r'^subscriptions/$',   SubscriptionUpdateView.as_view(), name='forum_subscriptions'),
    url(r'^(?P<forum>[-\w]+)/$',            ForumView.as_view(), name='forum_thread_list'),
    url(r'^(?P<forum>[-\w]+)/new/$', ThreadCreateView.as_view(), name='forum_new_thread'),
    url(r'^(?P<forum>[-\w]+)/rss/$', RssForumFeed(), name='forum_rss'),
    
    url(r'^([-\w/]+/)(?P<forum>[-\w]+)/rss/$', RssForumFeed()), # must before forum_subforum_thread_list
    url(r'^([-\w/]+/)(?P<forum>[-\w]+)/new/$', ThreadCreateView.as_view()), # must before forum_subforum_thread_list
    url(r'^([-\w/]+/)(?P<forum>[-\w]+)/$', ForumView.as_view(), name='forum_subforum_thread_list'),

    (r'^sitemap.xml$', 'django.contrib.sitemaps.views.index', {'sitemaps': sitemap_dict}),
    (r'^sitemap-(?P<section>.+)\.xml$', 'django.contrib.sitemaps.views.sitemap', {'sitemaps': sitemap_dict}),
)
