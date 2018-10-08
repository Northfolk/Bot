from django.views import generic
from .models import BasicSettings
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.shortcuts import redirect


@method_decorator(login_required, name='dispatch')
class IndexView(generic.ListView):
    model = BasicSettings
    template_name = 'settings/detail.html'


@login_required
def runBot(request):
    # bot start on button press
    if request.method == 'POST':
        try:
            from . import Folkomatic
            Folkomatic.run()
        except Exception as e:
            print(e)
    return redirect('../settings/')



