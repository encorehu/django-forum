"""
All forum logic is kept here - displaying lists of forums, threads
and posts, adding new threads, and adding replies.
"""

from datetime import datetime, timedelta
from django.shortcuts import get_object_or_404, render_to_response
from django.http import Http404, HttpResponse, HttpResponseRedirect, HttpResponseServerError, HttpResponseForbidden, HttpResponseNotAllowed
from django.template import RequestContext, Context, loader
from django import forms
from django.core.mail import EmailMessage
from django.conf import settings
from django.template.defaultfilters import striptags, wordwrap
from django.contrib.sites.models import Site
from django.contrib import comments
from django.contrib.contenttypes.models import ContentType
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext as _
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import permission_required
from django.utils import timezone

from django.views.generic import ListView
from django.views.generic import CreateView
from django.views.generic.edit import FormMixin
from django.core.urlresolvers import reverse_lazy



from forum.models import Forum,Thread,Post,Subscription
from forum.forms import CreateThreadForm, ReplyForm,ThreadForm
from forum.signals import thread_created

FORUM_PAGINATION = getattr(settings, 'FORUM_PAGINATION', 10)
LOGIN_URL = getattr(settings, 'LOGIN_URL', '/accounts/login/')

try:
    import json
except ImportError:
    try:
        import simplejson as json
    except:
        raise Exception('Need json module tobe installed.')

class JSONResponse(HttpResponse):
    def __init__(self, data, **kwargs):
        defaults = {
          'content_type': 'application/json',
        }
        defaults.update(kwargs)
        super(JSONResponse, self).__init__(json.dumps(data), **defaults)

class ForumIndexView(ListView):
    model = Forum

    def get_queryset(self):
        queryset = Forum.objects.for_user(self.request.user).filter(parent__isnull=True)
        return queryset

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super(ForumIndexView, self).get_context_data(**kwargs)

        return context


class ForumView(FormMixin, ListView):
    model       = Thread
    paginate_by = FORUM_PAGINATION
    template_object_name='thread'

    #@method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        #self.forum = get_object_or_404(Forum, slug=self.kwargs['forum'])
        try:
            self.forum = Forum.objects.for_user(request.user).select_related().get(slug=self.kwargs['forum'])
        except Forum.DoesNotExist:
            raise Http404

        self.child_forums = self.forum.child.for_user(request.user)
        self.recent_threads = self.forum.thread_set.filter(posts__gt=0).select_related().order_by('-id')[:10]
        self.active_threads = self.forum.thread_set.select_related().filter(
                                                latest_post_time__gt=timezone.now() - timedelta(hours=36)
                              ).order_by('-posts')[:10]

        return super(ForumView, self).dispatch(request, *args, **kwargs)

    def get_queryset(self):
        # get the url pattern <forum> from kwargs in func get_queryset or dispatch,
        # but it cant get in the func get_context_data, in which the url kwargs had been cleared
        #return super(ForumView, self).get_queryset().select_related('forum').filter(forum=self.forum).order_by('-latest_post_time')
        return self.forum.thread_set.select_related('forum').order_by('-latest_post_time')


    def get_context_data(self, **kwargs):
        context = super(ForumView, self).get_context_data(**kwargs)

        form = CreateThreadForm()

        extra_context = {
            'forum': self.forum,
            'child_forums':   self.child_forums,
            'active_threads': self.active_threads,
            'recent_threads': self.recent_threads,
            'form': form
        }
        context.update(extra_context)

        return context

    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated():
            return HttpResponseForbidden()
        self.object = self.get_object()
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def form_valid(self, form):
        # Here, we would record the user's interest using the message
        # passed in form.cleaned_data['message']
        return super(ForumView, self).form_valid(form)

class ThreadView(ListView):
    model = Post
    paginate_by = 10
    template_object_name='post'
    template_name = 'forum/thread.html'

    def get_queryset(self):
        # get the url pattern <forum> from kwargs in func get_queryset,
        # but it cant get in the func get_context_data, in which the url kwargs had been cleared
        #self.forum  = get_object_or_404(Forum, slug=self.kwargs['forum'])
        self.thread = get_object_or_404(Thread, pk=self.kwargs['thread'])
        self.forum = self.thread.forum

        self.thread.views +=1
        self.thread.save()
        return super(ThreadView, self).get_queryset().filter(thread=self.thread)


    def get_context_data(self, **kwargs):
        context = super(ThreadView, self).get_context_data(**kwargs)
        context['forum'] = self.forum
        context['thread'] = self.thread
        form = ReplyForm()
        context['form']=form
        print context
        return context

class ThreadCreateView(CreateView):
    """Creates a Thread for a Forum."""
    model         = Thread
    form_class    = ThreadForm
    template_name = 'forum/newthread.html'
    #success_url   = reverse_lazy('forum_thread_list')

    def get_success_url(self):
        #return reverse_lazy('forum_thread_list',[self.forum])
        return reverse('forum_thread_list',args=[self.forum.slug])

    @method_decorator(permission_required('forum.add_thread'))
    def dispatch(self, *args, **kwargs):
        """ Decorate the view dispatcher with permission_required
            Ensure the forum exists before creating a new Thread."""
        self.forum = get_object_or_404(Forum, slug=kwargs['forum'])
        return super(ThreadCreateView, self).dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        """Add current shop to the context, so we can show it on the page."""
        context = super(ThreadCreateView, self).get_context_data(**kwargs)
        context['forum'] = self.forum
        return context

    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated():
            return HttpResponseForbidden()

        self.object = None

        form_class = self.get_form_class()
        form       = self.get_form(form_class)

        if form.is_valid():
            self.object = form.save(commit=False)
            self.object.forum = self.forum
            self.object.save()

            post = Post(thread = self.object,
                        author = request.user,
                        body = form.cleaned_data['body'],
                        time=timezone.now()
                        )
            post.save()

            return self.form_valid(form)
        else:
            return self.form_invalid(form)

        self.object = None
        return super(ThreadCreateView, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.forum = self.forum
        ###self.object = form.save(commit=False)
        ###self.object.owner = self.request.user
        ###self.object.save()
        print form.cleaned_data
        #post = Post()
        #post.save()
        return super(ThreadCreateView, self).form_valid(form)
        ###return HttpResponseRedirect(self.get_success_url())
#
#
#    ###def form_invalid(self, form, formset=None):
#    ###    return self.render_to_response(self.get_context_data(form=form, formset=formset))
#
#    def get_form_kwargs(self, **kwargs):
#        kwargs = super(ThreadCreateView, self).get_form_kwargs(**kwargs)
#        kwargs['initial']['forum'] = self.forum
#        print kwargs
#        return kwargs

class PostCreateView(CreateView):
    """Reply a Post to thread."""
    model         = Post
    form_class    = ReplyForm
    template_name = 'forum/reply.html'
    #success_url   = reverse_lazy('forum_thread_list')

    def get_success_url(self):
        return reverse('forum_view_thread',args=[self.thread.pk])

    @method_decorator(permission_required('forum.add_post'))
    def dispatch(self, *args, **kwargs):
        """ Decorate the view dispatcher with permission_required
            Ensure the forum exists before creating a new Thread."""
        self.thread = get_object_or_404(Thread, pk=kwargs['thread'])
        return super(PostCreateView, self).dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        """Add current shop to the context, so we can show it on the page."""
        context = super(PostCreateView, self).get_context_data(**kwargs)
        context['thread'] = self.thread
        return context

    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated():
            return HttpResponseForbidden()
        self.object = None
        form_class = self.get_form_class()
        form       = self.get_form(form_class)

        if form.is_valid():
            self.object = form.save(commit=False)
            self.object.thread = self.thread
            self.object.save()

            return self.form_valid(form)
        else:
            return self.form_invalid(form)

        self.object = None
        return super(ThreadCreateView, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.thread = self.thread
        return super(ThreadCreateView, self).form_valid(form)

class SearchUnavailable(Exception):
        pass

class SphinxObjectList(object):
    def __init__(self, sphinx, term):
        self.sphinx = sphinx
        self.term = term

    def _get_results(self):
        results = self.sphinx.Query(self.term)
        if results == {}:
            raise SearchUnavailable()
        if results is None:
            results = {'total_found': 0, 'matches': []}
        return results

    def count(self):
        if not hasattr(self, 'results'):
            return self._get_results()['total_found']
        return self.results['total_found']

    def __len__(self):
        return self.count()

    def __getitem__(self, k):
        if hasattr(self, 'result'):
            raise Exception('Search result already available')
        self.sphinx.SetLimits(k.start, (k.stop - k.start) or 1)
        self.results = self._get_results()
        ids = [m['id'] for m in self.results['matches']]
        return Topic.objects.filter(id__in=ids)

def search(request, slug):
    forum = get_object_or_404(Forum, slug=slug)
    try:
        try:
            from sphinxapi import SphinxClient, SPH_MATCH_EXTENDED, SPH_SORT_RELEVANCE
        except ImportError:
            raise SearchUnavailable()
        term = request.GET.get('term', '').encode('utf-8')
        if term:
            sphinx = SphinxClient()
            sphinx.SetServer(settings.CICERO_SPHINX_SERVER, settings.CICERO_SPHINX_PORT)
            sphinx.SetMatchMode(SPH_MATCH_EXTENDED)
            sphinx.SetSortMode(SPH_SORT_RELEVANCE)
            sphinx.SetFilter('gid', [forum.id])
            paginator = Paginator(SphinxObjectList(sphinx, term), settings.CICERO_PAGINATE_BY)
            try:
                page = paginator.page(request.GET.get('page', '1'))
            except InvalidPage:
                raise Http404
        else:
            paginator = Paginator([], 1)
            page = paginator.page(1)
        return response(request, 'cicero/search.html', {
            'page_id': 'search',
            'forum': forum,
            'term': term,
            'paginator': paginator,
            'page_obj': page,
            'query_dict': request.GET,
        })
    except SearchUnavailable:
        raise
        return response(request, 'cicero/search_unavailable.html', {})

def forum(request, slug):
    """
    Displays a list of threads within a forum.
    Threads are sorted by their sticky flag, followed by their
    most recent post.
    """
    try:
        f = Forum.objects.for_user(request.user).select_related().get(slug=slug)
    except Forum.DoesNotExist:
        raise Http404

    form = CreateThreadForm()
    child_forums = f.child.for_groups(request.user.groups.all())

    recent_threads = f.thread_set.filter(posts__gt=0).select_related().order_by('-id')[:10]
    active_threads = f.thread_set.select_related().filter(latest_post__submit_date__gt=\
            datetime.now() - timedelta(hours=36)).order_by('-posts')[:10]

    return object_list( request,
                        queryset=f.thread_set.select_related('forum').order_by('-latest_post__submit_date'),
                        paginate_by=FORUM_PAGINATION,
                        template_object_name='thread',
                        template_name='forum/thread_list.html',
                        extra_context = {
                            'forum': f,
                #'child_forums': child_forums,
                'active_threads': active_threads,
                'recent_threads': recent_threads,
                            'form': form,
                        })

def thread(request, thread):
    """
    Increments the viewed count on a thread then displays the
    posts for that thread, in chronological order.
    """
    try:
        t = Thread.objects.select_related().get(pk=thread)
        if not Forum.objects.has_access(t.forum, request.user):
            raise Http404
    except Thread.DoesNotExist:
        raise Http404

    Post = comments.get_model()
    p = Post.objects.exclude(pk=t.comment_id).filter(content_type=\
        ContentType.objects.get_for_model(Thread),object_pk=t.pk).order_by('submit_date')
    s = None
    """
    not sure
    if request.user.is_authenticated():
        s = t.subscription_set.select_related().filter(author=request.user)
    """

    #t.views += 1
    #t.save()

    if s:
        initial = {'subscribe': True}
    else:
        initial = {'subscribe': False}

    form = ReplyForm(initial=initial)

    return object_list( request,
                        queryset=p,
                        page=request.GET.get('p',None) or None,
                        paginate_by=FORUM_PAGINATION,
                        template_object_name='post',
                        template_name='forum/thread.html',
                        extra_context = {
                            'forum': t.forum,
                            'thread': t,
                            'object': t,
                            'subscription': s,
                            'form': form,
                        })

def reply(request, thread):
    """
    If a thread isn't closed, and the user is logged in, post a reply
    to a thread. Note we don't have "nested" replies at this stage.
    """
    if not request.user.is_authenticated():
        return HttpResponseRedirect('%s?next=%s' % (LOGIN_URL, request.path))
    t = get_object_or_404(Thread, pk=thread)
    if t.closed:
        return HttpResponseServerError()
    if not Forum.objects.has_access(t.forum, request.user.groups.all()):
        return HttpResponseForbidden()

    if request.method == "POST":
        form = ReplyForm(request.POST)
        if form.is_valid():
            body = form.cleaned_data['body']
            p = Post(
                thread=t,
                author=request.user,
                body=body,
                time=datetime.now(),
                )
            p.save()

            sub = Subscription.objects.filter(thread=t, author=request.user)
            if form.cleaned_data.get('subscribe',False):
                if not sub:
                    s = Subscription(
                        author=request.user,
                        thread=t
                        )
                    s.save()
            else:
                if sub:
                    sub.delete()

            if t.subscription_set.count() > 0:
                # Subscriptions are updated now send mail to all the authors subscribed in
                # this thread.
                mail_subject = ''
                try:
                    mail_subject = settings.FORUM_MAIL_PREFIX
                except AttributeError:
                    mail_subject = '[Forum]'

                mail_from = ''
                try:
                    mail_from = settings.FORUM_MAIL_FROM
                except AttributeError:
                    mail_from = settings.DEFAULT_FROM_EMAIL

                mail_tpl = loader.get_template('forum/notify.txt')
                c = Context({
                    'body': wordwrap(striptags(body), 72),
                    'site' : Site.objects.get_current(),
                    'thread': t,
                    })

                email = EmailMessage(
                        subject=mail_subject+' '+striptags(t.title),
                        body= mail_tpl.render(c),
                        from_email=mail_from,
                        bcc=[s.author.email for s in t.subscription_set.all()],)
                email.send(fail_silently=True)

            return HttpResponseRedirect(p.get_absolute_url())
    else:
        form = ReplyForm()

    return render_to_response('forum/reply.html',
        RequestContext(request, {
            'form': form,
            'forum': t.forum,
            'thread': t,
        }))

def newthread(request, forum):
    """
    Rudimentary post function - this should probably use
    newforms, although not sure how that goes when we're updating
    two models.

    Only allows a user to post if they're logged in.
    """
    if not request.user.is_authenticated():
        return HttpResponseRedirect('%s?next=%s' % (LOGIN_URL, request.path))

    f = get_object_or_404(Forum, slug=forum)

    if not Forum.objects.has_access(f, request.user):
        return HttpResponseForbidden()

    if request.method == 'POST':
        form = CreateThreadForm(request.POST)
        if form.is_valid():
            t = Thread(
                forum=f,
                title=form.cleaned_data['title'],
            )
            t.save()

            p = Post(
                thread=t,
                author=request.user,
                body=form.cleaned_data['body'],
                time=datetime.now(),
            )
            p.save()
            t.latest_post = p
            t.comment = p
            t.save()
            if form.cleaned_data.get('subscribe', False):
                s = Subscription(
                    author=request.user,
                    thread=t
                    )
                s.save()
            return HttpResponseRedirect(t.get_absolute_url())
    else:
        form = CreateThreadForm()

    return render_to_response('forum/newthread.html',
        RequestContext(request, {
            'form': form,
            'forum': f,
        }))

def updatesubs(request):
    """
    Allow users to update their subscriptions all in one shot.
    """
    if not request.user.is_authenticated():
        return HttpResponseRedirect('%s?next=%s' % (LOGIN_URL, request.path))

    subs = Subscription.objects.select_related().filter(author=request.user)

    if request.POST:
        # remove the subscriptions that haven't been checked.
        post_keys = [k for k in request.POST.keys()]
        for s in subs:
            if not str(s.thread.id) in post_keys:
                s.delete()
        return HttpResponseRedirect(reverse('forum_subscriptions'))

    return render_to_response('forum/updatesubs.html',
        RequestContext(request, {
            'subs': subs,
            'next': request.GET.get('next')
        }))

