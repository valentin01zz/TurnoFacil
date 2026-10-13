from django.contrib.auth import login
from django.shortcuts import redirect, render

from .forms import SignupForm


def home(request):
    if request.user.is_authenticated:
        return redirect("panel")
    return render(request, "home.html")


def signup(request):
    if request.user.is_authenticated:
        return redirect("panel")
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect("panel")
    return render(request, "accounts/signup.html", {"form": form})
