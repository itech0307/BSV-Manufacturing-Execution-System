from django import forms
from .models import Worker, WorkerComment

class WorkerForm(forms.ModelForm):
    worker_code = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}))
    name = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}))
    join_date = forms.DateField(widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}))
    
    class Meta:
        model = Worker
        fields = ['worker_code','name', 'phone_number', 'department','position', 'join_date']

class WorkerCommentForm(forms.ModelForm):
    class Meta:
        model = WorkerComment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
        }