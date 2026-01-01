import logging
from rest_framework import viewsets, status
from rest_framework.permissions import (
    IsAuthenticated,
    IsAuthenticatedOrReadOnly,
    BasePermission,
)
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.db.models import Prefetch, Q
from .models import Company, Job, Application, ApplicationHistory
from .serializers import (
    CompanySerializer,
    JobSerializer,
    JobDetailSerializer,
    ApplicationSerializer,
    ApplicationDetailSerializer,
    ApplicationHistorySerializer,
)
from . import tasks
from . import services

logger = logging.getLogger(__name__)

# ===========================
# PAGINATION
# ===========================
class StandardResultsSetPagination(PageNumberPagination):
    """Standard pagination for list endpoints."""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

# ===========================
# ROLE PERMISSIONS
# ===========================
class IsCandidate(BasePermission):
    """Permission check for candidate role."""
    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == "candidate"
        )

class IsRecruiter(BasePermission):
    """Permission check for recruiter role."""
    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == "recruiter"
        )

class IsHiringManager(BasePermission):
    """Permission check for hiring manager role."""
    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == "manager"
        )

# ===========================
# COMPANY VIEWSET
# ===========================
class CompanyViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing companies.
    
    List: GET /api/companies/
    Create: POST /api/companies/
    Retrieve: GET /api/companies/{id}/
    Update: PUT /api/companies/{id}/
    Partial Update: PATCH /api/companies/{id}/
    Delete: DELETE /api/companies/{id}/
    """
    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    pagination_class = StandardResultsSetPagination
    
    def perform_create(self, serializer):
        """Log company creation."""
        company = serializer.save()
        logger.info(f"Company created: {company.name} by user {self.request.user.username}")

# ===========================
# JOB VIEWSET
# ===========================
class JobViewSet(viewsets.ModelViewSet):
    """
    API endpoint for job listings.
    
    Recruiters can create and manage jobs.
    All authenticated users can view jobs.
    """
    queryset = Job.objects.select_related('company').all()
    pagination_class = StandardResultsSetPagination
    
    def get_permissions(self):
        """Set permissions based on request method."""
        if self.request.method in ["POST", "PUT", "PATCH", "DELETE"]:
            return [IsAuthenticated(), IsRecruiter()]
        return [IsAuthenticatedOrReadOnly()]
    
    def get_serializer_class(self):
        """Use detailed serializer for retrieve action."""
        if self.action == 'retrieve':
            return JobDetailSerializer
        return JobSerializer
    
    def get_queryset(self):
        """Optimize queries based on action."""
        queryset = Job.objects.select_related('company')
        
        if self.action == 'retrieve':
            # Prefetch applications for detail view
            queryset = queryset.prefetch_related('applications')
        
        # Filter by status if provided
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by company if provided
        company_filter = self.request.query_params.get('company_id')
        if company_filter:
            queryset = queryset.filter(company_id=company_filter)
        
        return queryset
    
    def perform_create(self, serializer):
        """Create job and log action."""
        # Recruiters can only create jobs for their company
        if self.request.user.role == "recruiter" and self.request.user.company:
            serializer.save(company=self.request.user.company)
            logger.info(f"Job created: {serializer.instance.title} by {self.request.user.username}")
        else:
            raise PermissionError("Only recruiters with a company can create jobs")

# ===========================
# APPLICATION VIEWSET
# ===========================
class ApplicationViewSet(viewsets.ModelViewSet):
    """
    API endpoint for job applications.
    
    Implements role-based access control and workflow state machine validation.
    Candidates: Apply to jobs, view their own applications
    Recruiters/Managers: View company applications, change stages
    """
    pagination_class = StandardResultsSetPagination
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        """Use detailed serializer for retrieve action."""
        if self.action == 'retrieve':
            return ApplicationDetailSerializer
        return ApplicationSerializer
    
    def get_queryset(self):
        """
        Filter applications based on user role.
        Candidates see only their own applications.
        Recruiters/Managers see applications for their company's jobs.
        Optimized with select_related and prefetch_related.
        """
        user = self.request.user
        
        base_queryset = Application.objects.select_related(
            'candidate', 'job', 'job__company'
        )
        
        if self.action == 'retrieve':
            base_queryset = base_queryset.prefetch_related(
                Prefetch(
                    'history',
                    ApplicationHistory.objects.select_related('changed_by')
                )
            )
        
        if user.role == "candidate":
            return base_queryset.filter(candidate=user)
        elif user.role in ["recruiter", "manager"]:
            return base_queryset.filter(job__company=user.company)
        
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
        """
        Candidate applies to a job.
        
        Request body:
        {
            "job": <job_id>
        }
        """
        job_id = request.data.get("job")
        if not job_id:
            logger.warning(f"Apply request without job ID from {request.user.username}")
            return Response(
                {"detail": "Job ID is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        try:
            job = get_object_or_404(Job, id=job_id)
            application = services.create_application(request.user, job)
            logger.info(f"Application created: {request.user.username} -> Job {job.id}")
            
            serializer = ApplicationSerializer(application)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except ValueError as e:
            logger.warning(f"Application creation failed: {str(e)}")
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
    
    # ---------------------------------------------------
    # CHANGE STAGE (RECRUITER OR HIRING MANAGER)
    # ---------------------------------------------------
    @action(
        detail=True,
        methods=["post"],
        permission_classes=[IsAuthenticated],
        url_path="change-stage",
    )
    def change_stage(self, request, pk=None):
        """
        Change application stage (workflow transition).
        
        Request body:
        {
            "stage": "Screening" | "Interview" | "Offer" | "Hired" | "Rejected"
        }
        
        Authorization:
        - Only recruiters/managers from the same company as the job
        """
        application = self.get_object()
        new_stage = request.data.get("stage")
        
        # Authorization check
        if request.user.role not in ["recruiter", "manager"]:
            logger.warning(f"Unauthorized stage change attempt by {request.user.username}")
            return Response(
                {"detail": "Only recruiters and managers can change stages"},
                status=status.HTTP_403_FORBIDDEN,
            )
        
        if request.user.company != application.job.company:
            logger.warning(
                f"Cross-company stage change attempt by {request.user.username}"
            )
            return Response(
                {"detail": "Not allowed - different company"},
                status=status.HTTP_403_FORBIDDEN,
            )
        
        # Validate stage input
        if not new_stage:
            return Response(
                {"detail": "Stage is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        valid_stages = [choice[0] for choice in Application.STAGE_CHOICES]
        if new_stage not in valid_stages:
            return Response(
                {"detail": f"Invalid stage. Must be one of {valid_stages}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Check if transition is valid
        if not application.can_transition_to(new_stage):
            logger.info(
                f"Invalid transition: {application.stage} -> {new_stage} by {request.user.username}"
            )
            return Response(
                {"detail": f"Invalid transition from {application.stage} to {new_stage}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Use service function to handle stage change with transaction
        try:
            services.change_application_stage(application, new_stage, request.user)
            logger.info(
                f"Application stage changed: {application.id} {application.stage} -> {new_stage}"
            )
            
            # Refresh from database
            application.refresh_from_db()
            serializer = ApplicationSerializer(application)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except ValueError as e:
            logger.error(f"Error changing stage: {str(e)}")
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

# ===========================
# APPLICATION HISTORY VIEWSET
# ===========================
class ApplicationHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only API endpoint for application history (audit trail).
    
    Shows all stage transitions for applications.
    Access controlled by application permissions.
    """
    serializer_class = ApplicationHistorySerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """
        Return history records based on user role and permissions.
        Optimized with select_related.
        """
        queryset = ApplicationHistory.objects.select_related(
            'application', 'application__candidate', 'application__job',
            'changed_by'
        ).order_by('-changed_at')
        
        # Filter based on user role
        user = self.request.user
        if user.is_authenticated:
            if user.role == "candidate":
                # Candidates see only their own application history
                queryset = queryset.filter(application__candidate=user)
            elif user.role in ["recruiter", "manager"]:
                # Recruiters/managers see history for their company
                queryset = queryset.filter(application__job__company=user.company)
        
        return queryset

# ===========================
# CURRENT USER PROFILE (ME)
# ===========================
from rest_framework.views import APIView

class MeView(APIView):
    """
    Get current authenticated user's profile information.
    
    GET /api/me/ - Returns current user details
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Return authenticated user's profile."""
        user = request.user
        company_info = None
        if user.company:
            company_info = {
                "id": user.company.id,
                "name": user.company.name,
            }
        
        return Response({
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "company": company_info,
            "created_at": user.created_at,
        })
