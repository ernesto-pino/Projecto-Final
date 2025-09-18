from django.shortcuts import render

def home(request):
    return render(request, 'core/html/home.html')
