from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CompanyViewSet,
    JobViewSet,
    ApplicationViewSet,
    ApplicationHistoryViewSet,
)

router = DefaultRouter()
router.register('companies', CompanyViewSet)
router.register('jobs', JobViewSet)
router.register('applications', ApplicationViewSet)
router.register('histories', ApplicationHistoryViewSet)

urlpatterns = [
    path('', include(router.urls)),

    # Candidate apply
    path(
        "applications/apply/",
        ApplicationViewSet.as_view({"post": "apply"}),
        name="apply-job",
    ),

    # Recruiter change stage
    path(
        "applications/<int:pk>/change-stage/",
        ApplicationViewSet.as_view({"post": "change_stage"}),
        name="change-application-stage",
    ),

    # Recruiter list applications for a job
    path(
        "jobs/<int:pk>/applications/",
        ApplicationViewSet.as_view({"get": "job_applications"}),
        name="job-applications",
    ),
]
