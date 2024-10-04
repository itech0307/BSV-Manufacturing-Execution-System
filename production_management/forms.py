from django import forms
from .models import Development, DevelopmentComment

class DevelopmentForm(forms.ModelForm):
    purpose = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}))
    category = forms.ChoiceField(choices=[('NewMaterial', 'New Material'), ('Improvement', 'Improvement'), ('Sample', 'Sample')], widget=forms.Select(attrs={'class': 'form-control'}))
    deadline = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}))
    content = forms.CharField(widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 10}))
    
    class Meta:
        model = Development
        fields = ['title', 'purpose', 'category', 'deadline', 'content']

class DevelopmentCommentForm(forms.ModelForm):
    class Meta:
        model = DevelopmentComment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
        }