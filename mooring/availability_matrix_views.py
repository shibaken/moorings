from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView

from mooring.helpers import is_officer


class AvailabilityMatrixView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'admin/mooring/availability_matrix/index.html'

    def test_func(self):
        return is_officer(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Mooring Availability Matrix'
        return context
