from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, UpdateView

from .forms import CommentForm, PostForm, UserEditForm
from .models import Category, Comment, Post

User = get_user_model()

POSTS_PER_PAGE = 10


def _published_posts_qs():
    now = timezone.now()
    return (
        Post.objects.select_related('author', 'category', 'location')
        .filter(
            is_published=True,
            pub_date__lte=now,
            category__is_published=True,
        )
        .annotate(comment_count=Count('comments'))
        .order_by('-pub_date')
    )


def _paginate(request, queryset, per_page=POSTS_PER_PAGE):
    paginator = Paginator(queryset, per_page)
    page_number = request.GET.get('page')
    return paginator.get_page(page_number)


def index(request):
    page_obj = _paginate(request, _published_posts_qs())
    return render(request, 'blog/index.html', {'page_obj': page_obj})


def category_posts(request, category_slug):
    category = get_object_or_404(
        Category, slug=category_slug, is_published=True
    )
    posts = _published_posts_qs().filter(category=category)
    page_obj = _paginate(request, posts)
    return render(
        request,
        'blog/category.html',
        {'category': category, 'page_obj': page_obj},
    )


def post_detail(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    if request.user != post.author:
        post = get_object_or_404(
            Post,
            pk=post_id,
            is_published=True,
            pub_date__lte=timezone.now(),
            category__is_published=True,
        )
    comments = post.comments.select_related('author')
    form = CommentForm()
    return render(
        request,
        'blog/detail.html',
        {'post': post, 'comments': comments, 'form': form},
    )


def profile(request, username):
    author = get_object_or_404(User, username=username)
    if request.user == author:
        posts = (
            Post.objects.filter(author=author)
            .annotate(comment_count=Count('comments'))
            .order_by('-pub_date')
        )
    else:
        posts = _published_posts_qs().filter(author=author)
    page_obj = _paginate(request, posts)
    return render(
        request,
        'blog/profile.html',
        {'profile': author, 'page_obj': page_obj},
    )


@login_required
def edit_profile(request):
    form = UserEditForm(request.POST or None, instance=request.user)
    if form.is_valid():
        form.save()
        return redirect('blog:profile', username=request.user.username)
    return render(request, 'blog/user.html', {'form': form})


class PostCreateView(LoginRequiredMixin, CreateView):
    model = Post
    form_class = PostForm
    template_name = 'blog/create.html'

    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse(
            'blog:profile', kwargs={'username': self.request.user.username}
        )


class PostUpdateView(LoginRequiredMixin, UpdateView):
    model = Post
    form_class = PostForm
    template_name = 'blog/create.html'
    pk_url_kwarg = 'post_id'

    def dispatch(self, request, *args, **kwargs):
        post = get_object_or_404(Post, pk=kwargs['post_id'])
        if post.author != request.user:
            return redirect('blog:post_detail', post_id=kwargs['post_id'])
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('blog:post_detail', kwargs={'post_id': self.object.pk})


class PostDeleteView(LoginRequiredMixin, DeleteView):
    model = Post
    template_name = 'blog/create.html'
    pk_url_kwarg = 'post_id'

    def dispatch(self, request, *args, **kwargs):
        post = get_object_or_404(Post, pk=kwargs['post_id'])
        if post.author != request.user:
            return redirect('blog:post_detail', post_id=kwargs['post_id'])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = PostForm(instance=self.object)
        return context

    def get_success_url(self):
        return reverse(
            'blog:profile', kwargs={'username': self.request.user.username}
        )


@login_required
def add_comment(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    form = CommentForm(request.POST or None)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.author = request.user
        comment.post = post
        comment.save()
    return redirect('blog:post_detail', post_id=post_id)


@login_required
def edit_comment(request, post_id, comment_id):
    comment = get_object_or_404(Comment, pk=comment_id, author=request.user)
    form = CommentForm(request.POST or None, instance=comment)
    if form.is_valid():
        form.save()
        return redirect('blog:post_detail', post_id=post_id)
    return render(
        request,
        'blog/comment.html',
        {'form': form, 'comment': comment},
    )


@login_required
def delete_comment(request, post_id, comment_id):
    comment = get_object_or_404(Comment, pk=comment_id, author=request.user)
    if request.method == 'POST':
        comment.delete()
        return redirect('blog:post_detail', post_id=post_id)
    return render(
        request,
        'blog/comment.html',
        {'comment': comment},
    )
