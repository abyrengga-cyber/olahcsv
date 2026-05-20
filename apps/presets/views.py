from django.shortcuts import render
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from rest_framework import generics, permissions
from .models import Preset
from .serializers import PresetSerializer

# API Views
class PresetListCreateView(generics.ListCreateAPIView):
    serializer_class = PresetSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        return Preset.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
        
    def create(self, request, *args, **kwargs):
        print("PRESET CREATE PAYLOAD:", request.data)
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            print("PRESET SERIALIZER ERRORS:", serializer.errors)
        return super().create(request, *args, **kwargs)

class PresetDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PresetSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Preset.objects.filter(user=self.request.user)

# Page View
class PresetsPageView(LoginRequiredMixin, TemplateView):
    template_name = 'presets.html'
