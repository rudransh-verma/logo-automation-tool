from django.shortcuts import render

def upload_view(request):
    return render(request, 'core/upload.html')
