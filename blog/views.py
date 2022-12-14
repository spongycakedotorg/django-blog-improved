from django.shortcuts import get_object_or_404, render
from django.http import Http404
from django.core.exceptions import ObjectDoesNotExist
from django.views.generic import DetailView, ListView, TemplateView
from django.views.generic.detail import SingleObjectMixin
from django.urls import reverse
from .forms import CommentForm
from .models import Post, PostViaGit, PostRedirect, User, UserProfile
from taggit.models import Tag
from django.db.models.base import ModelBase
from django.db.models import Q, QuerySet

import operator

def filter_classes(queryset, model_list):
    filtered_list = []
    for obj in queryset:
        for model in model_list:
            if not isinstance(obj, model):
                filtered_list.append(obj)
    return filtered_list

def list_to_queryset(model, data):

    if not isinstance(model, ModelBase):
        raise ValueError(
            "%s must be Model" % model
        )
    if not isinstance(data, list):
        raise ValueError(
            "%s must be List Object" % data
        )

    pk_list = [obj.pk for obj in data]
    return model.objects.filter(pk__in=pk_list)

class HomePage(ListView):
    queryset = Post.objects.filter(status=1).select_subclasses()
    template_name = "index.html"

    class Meta:
        ordering = ["-created_on"]


class PostList(ListView):
    template_name = "post_list.html"
    paginate_by = 22
    
    def get_queryset(self):
        # show all posts for index pages
        if "/index/" in self.request.path:
            all_posts = Post.objects.filter(status=1).select_subclasses(PostRedirect)
            posts_cleaned = filter_classes(all_posts, (PostRedirect,))
            return list_to_queryset(Post, posts_cleaned)
        try:
            # categories in request string, seperated by comma
            cats = self.request.GET.get("cat").split(",")
            # remove whitespaces enteries
            cats = [cat for cat in cats if cat != ""]
            # only filter by category if string parameters are detected
            if len(cats) > 0:
                # get posts with a matching category
                all_posts = Post.objects.filter(status=1, category__name__in=cats).select_subclasses(PostRedirect)
                # here we are removing PostRedirect from posts list
                posts_cleaned = filter_classes(all_posts, (PostRedirect,))
                # build new queryset with list above
                return list_to_queryset(Post, posts_cleaned)
            raise Http404
            return Post.objects.none()
        except AttributeError:
            raise Http404
        return Post.objects.none()
        

    def get_context_data(self, object_list=None, **kwargs):
        context = super(PostList, self).get_context_data(**kwargs)
        context["tags"] = {post.category for post in context["object_list"]}
        context["total_post_count"] = self.get_queryset().count()
        context["search_title"] = "Posts"
        try: 
            query = self.request.GET.get("cat")# Query or None
            context["query"] = query
            context["filter_categories"] = query
        except KeyError:
            return context
        return context

def get_comments(request, post):
    comments = post.comments.filter(active=True).order_by("-created_on")
    new_comment = None
    # Comment posted
    if request.method == "POST":
        comment_form = CommentForm(data=request.POST)
        if comment_form.is_valid():
            # Create Comment object but don't save to database yet
            new_comment = comment_form.save(commit=False)
            # Assign the current post to the comment
            new_comment.post = post
            # Save the comment to the database
            new_comment.save()
    else:
        comment_form = CommentForm()
    return {"all_active": comments, "comment_form": comment_form, "new_comment": new_comment}

class PublicPostMixin(object):
    def get_queryset(self): 
        return Post.objects.filter(status=1)

class PostView(DetailView, PublicPostMixin, SingleObjectMixin):
    template_name = "post_detail.html"
    model = Post
    
    def get_context_data(self, **kwargs):
        context = super(PostView, self).get_context_data(**kwargs)
        post = self.get_object()
        # get comments
        comments = get_comments(self.request, post)
        context["comments"] = comments["all_active"]
        context["new_comment"] = comments["new_comment"]
        context["comment_form"] = comments["comment_form"]
        context["crumbs"] = [("Home", reverse("home"),),("Posts", reverse("post_list"),),(post.title, None,)]
        if operator.eq(post.collabaration_mode, Post.CollabrationMode.YES):
            post = get_object_or_404(PostViaGit, post_ptr_id=post.pk)
        try:
            author_profile = UserProfile.objects.get(pk=post.author.id)
            context["author_profile"] = author_profile
        except ObjectDoesNotExist:
            context["author_profile"] = {}
        context["post"] = post
        return context

