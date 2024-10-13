from django import forms
from .models import Worker, WorkerComment

class WorkerForm(forms.ModelForm):
    worker_code = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}))
    name = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}))
    join_date = forms.DateField(widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}))
    profile_image = forms.ImageField(required=False, widget=forms.FileInput(attrs={'class': 'form-control'}))
    
    class Meta:
        model = Worker
        fields = ['worker_code','name', 'phone_number', 'department','position', 'join_date', 'profile_image']

class WorkerCommentForm(forms.ModelForm):
    class Meta:
        model = WorkerComment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
        }