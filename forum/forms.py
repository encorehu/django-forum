from django import forms
from django.utils.translation import ugettext as _
from forum.models import Thread

class CreateThreadForm(forms.Form):
    title = forms.CharField(label=_("Title"), max_length=100)
    body = forms.CharField(label=_("Body"), widget=forms.Textarea(attrs={'rows':8, 'cols':50}))
    subscribe = forms.BooleanField(label=_("Subscribe via email"), required=False)

class ThreadForm(forms.ModelForm):
    body = forms.CharField(label=_("Body"), widget=forms.Textarea(attrs={'rows':8, 'cols':50}))
    class Meta:
        model = Thread
        fields = ('title','body')
        
class ReplyForm(forms.Form):
    body = forms.CharField(label=_("Body"), widget=forms.Textarea(attrs={'rows':8, 'cols':50}))
    subscribe = forms.BooleanField(label=_("Subscribe via email"), required=False)

