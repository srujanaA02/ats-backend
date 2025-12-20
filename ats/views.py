from rest_framework import viewsets, status
from rest_framework.permissions import (
    IsAuthenticated,
    IsAuthenticatedOrReadOnly,
    BasePermission,
)
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import Company, Job, Application, ApplicationHistory
from .serializers import (
    CompanySerializer,
    JobSerializer,
    ApplicationSerializer,
    ApplicationHistorySerializer,
)
from . import tasks
from . import services

# ======================================================
# ROLE PERMISSIONS
# ======================================================
class IsCandidate(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == "candidate"
        )

class IsRecruiter(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == "recruiter"
        )

class IsHiringManager(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == "manager"
        )

# ======================================================
# COMPANY VIEWSET
# ======================================================
class CompanyViewSet(viewsets.ModelViewSet):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

# ======================================================
# JOB VIEWSET
# ======================================================
class JobViewSet(viewsets.ModelViewSet):
    queryset = Job.objects.all()
    serializer_class = JobSerializer
    
    def get_permissions(self):
        if self.request.method in ["POST", "PUT", "PATCH", "DELETE"]:
            return [IsAuthenticated(), IsRecruiter()]
        return [IsAuthenticatedOrReadOnly()]

# ======================================================
# APPLICATION VIEWSET
# ======================================================
70
class ApplicationViewSet(viewsets.ModelViewSet):
    queryset = Application.objects.all()
    serializer_class = ApplicationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Filter applications based on user role.
        Candidates see only their own applications.
        Recruiters/Managers see applications for their company's jobs.
        """
        user = self.request.user
        if user.role == "candidate":
            return Application.objects.filter(candidate=user)
        elif user.role in ["recruiter", "manager"]:
            return Application.objects.filter(job__company=user.company)
        return Application.objects.none()
    
    # ---------------------------------------------------
    # APPLY TO JOB (CANDIDATE ONLY)
    # ---------------------------------------------------
    @action(
        detail=False,
        methods=["post"],
        permission_classes=[IsAuthenticated, IsCandidate],
        url_path="apply",
    )
    def apply(self, request):
        job_id = request.data.get("job")
        if not job_id:
            return Response(
                {"detail": "Job ID is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        job = get_object_or_404(Job, id=job_id)
try:
            application = services.create_application(request.user, job)
        except ValueError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )71
            
        # Trigger Celery email tasks asynchronously
        tasks.send_candidate_email.delay(
            subject="Application Confirmation",
            body=f"Your application for {job.title} has been received.",
            to_email=request.user.email,
        )
        
        # Notify recruiters in the company
        recruiter_emails = job.company.users.filter(role="recruiter").values_list("email", flat=True)
        for recruiter_email in recruiter_emails:
            tasks.send_recruiter_email.delay(
                subject=f"New Application: {job.title}",
                body=f"{request.user.username} applied for {job.title}.",
                to_email=recruiter_email,
            )
        
        serializer = ApplicationSerializer(application)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    # ---------------------------------------------------
    # RECRUITER LISTS APPLICATIONS FOR SPECIFIC JOB
    # ---------------------------------------------------
    @action(
        detail=True,
        methods=["get"],
        permission_classes=[IsAuthenticated, IsRecruiter],
        url_path="applications",
    )
    def job_applications(self, request, pk=None):
        """Recruiter lists all applications for a specific job."""
        job = get_object_or_404(Job, id=pk)
        # Recruiter must belong to same company
        if request.user.company != job.company:
            return Response(
                {"detail": "Not allowed"},
                status=status.HTTP_403_FORBIDDEN
            )
        applications = Application.objects.filter(job=job)
        serializer = ApplicationSerializer(applications, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    # ---------------------------------------------------
    # CHANGE STAGE (RECRUITER OR HIRING MANAGER)
    # ---------------------------------------------------
    @action(
        detail=True,
        methods=["post"],
        permission_classes=[IsAuthenticated],
        url_path="change-stage",
    )
    175
199
(self, request, pk=None):
        application = self.get_object()
        new_stage = request.data.get("stage")
        
        # Authorization check: only recruiters or managers from the same company
        if request.user.role == "recruiter":
            if request.user.company != application.job.company:
                return Response(
                    {"detail": "Not allowed"},
                    status=status.HTTP_403_FORBIDDEN
                )
        elif request.user.role == "manager":
            if request.user.company != application.job.company:
                return Response(
                    {"detail": "Not allowed"},
                    status=status.HTTP_403_FORBIDDEN
                )
        else:
            return Response(
                {"detail": "Not allowed"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if not new_stage:
            return Response(
                {"detail": "Stage is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        valid_stages = [choice[0] for choice in Application.STAGE_CHOICES]
        if new_stage not in valid_stages:
            return Response(
                {"detail": "Invalid stage"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if transition is valid
            if not application.can_transition_to(new_stage):
                return Response(
                    {"detail": f"Invalid transition from {application.stage} to {new_stage}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        
        # Use service function to handle stage change with transaction
        try:
            services.change_application_stage(application, new_stage, request.user)
        except ValueError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        serializer = ApplicationSerializer(application)
        return Response(serializer.data, status=status.HTTP_200_OK)

# ======================================================
# APPLICATION HISTORY VIEWSET
# ======================================================
class ApplicationHistoryViewSet(viewsets.ModelViewSet):
    queryset = ApplicationHistory.objects.all()
    serializer_class = ApplicationHistorySerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

# ======================================================
# CURRENT USER PROFILE (ME)
# ======================================================
from rest_framework.views import APIView

class MeView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        return Response({
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
        })
