from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Company, Job, Application, ApplicationHistory

User = get_user_model()

# ===========================
# USER SERIALIZER
# ===========================
class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for User model with read-only sensitive fields.
    """
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'role', 'company', 'created_at')
        read_only_fields = ('id', 'created_at')

# ===========================
# COMPANY SERIALIZER
# ===========================
class CompanySerializer(serializers.ModelSerializer):
    """
    Serializer for Company model with comprehensive validation.
    """
    name = serializers.CharField(
        max_length=255,
        min_length=2,
        required=True,
        help_text="Company name (2-255 characters)"
    )
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=2000,
        help_text="Company description"
    )
    
    class Meta:
        model = Company
        fields = ('id', 'name', 'description', 'created_at')
        read_only_fields = ('id', 'created_at')
    
    def validate_name(self, value):
        """Ensure company name is unique and non-empty."""
        if Company.objects.filter(name__iexact=value).exists():
            raise serializers.ValidationError("Company with this name already exists.")
        return value.strip()

# ===========================
# JOB SERIALIZER
# ===========================
class JobSerializer(serializers.ModelSerializer):
    """
    Serializer for Job model with comprehensive validation and company details.
    """
    company_name = serializers.CharField(source='company.name', read_only=True)
    application_count = serializers.SerializerMethodField()
    
    title = serializers.CharField(
        max_length=255,
        min_length=5,
        required=True,
        help_text="Job title (5-255 characters)"
    )
    description = serializers.CharField(
        required=True,
        min_length=10,
        max_length=5000,
        help_text="Job description (10-5000 characters)"
    )
    status = serializers.ChoiceField(
        choices=['open', 'closed'],
        required=False,
        help_text="Job status"
    )
    
    class Meta:
        model = Job
        fields = ('id', 'title', 'description', 'status', 'company', 'company_name', 'application_count', 'created_at')
        read_only_fields = ('id', 'company_name', 'application_count', 'created_at')
    
    def validate_title(self, value):
        """Ensure job title is meaningful."""
        if not value.strip():
            raise serializers.ValidationError("Job title cannot be empty or whitespace.")
        return value.strip()
    
    def validate_description(self, value):
        """Ensure job description is meaningful."""
        if not value.strip():
            raise serializers.ValidationError("Job description cannot be empty.")
        return value.strip()
    
    def get_application_count(self, obj):
        """Get count of applications for this job."""
        return obj.applications.count()

# ===========================
# APPLICATION SERIALIZER
# ===========================
class ApplicationSerializer(serializers.ModelSerializer):
    """
    Serializer for Application model with comprehensive validation.
    Includes workflow state machine validation.
    """
    candidate_name = serializers.CharField(source='candidate.username', read_only=True)
    job_title = serializers.CharField(source='job.title', read_only=True)
    company_name = serializers.CharField(source='job.company.name', read_only=True)
    can_transition_to = serializers.SerializerMethodField()
    
    stage = serializers.ChoiceField(
        choices=['Applied', 'Screening', 'Interview', 'Offer', 'Hired', 'Rejected'],
        required=False,
        help_text="Application stage"
    )
    
    class Meta:
        model = Application
        fields = (
            'id', 'candidate', 'candidate_name', 'job', 'job_title',
            'company_name', 'stage', 'can_transition_to', 'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'candidate_name', 'job_title', 'company_name', 'can_transition_to', 'created_at', 'updated_at')
    
    def validate_stage(self, value):
        """Validate stage against workflow rules."""
        if not value:
            return value
        
        valid_stages = [choice[0] for choice in Application.STAGE_CHOICES]
        if value not in valid_stages:
            raise serializers.ValidationError(f"Invalid stage. Must be one of {valid_stages}")
        return value
    
    def get_can_transition_to(self, obj):
        """Return valid stages this application can transition to."""
        return obj.VALID_TRANSITIONS.get(obj.stage, [])

# ===========================
# APPLICATION HISTORY SERIALIZER
# ===========================
class ApplicationHistorySerializer(serializers.ModelSerializer):
    """
    Serializer for ApplicationHistory model (audit trail).
    Provides read-only history of application state changes.
    """
    application_id = serializers.IntegerField(source='application.id', read_only=True)
    candidate_name = serializers.CharField(source='application.candidate.username', read_only=True)
    job_title = serializers.CharField(source='application.job.title', read_only=True)
    changed_by_name = serializers.CharField(source='changed_by.username', read_only=True)
    
    class Meta:
        model = ApplicationHistory
        fields = (
            'id', 'application_id', 'candidate_name', 'job_title',
            'from_stage', 'to_stage', 'changed_by_name', 'changed_at'
        )
        read_only_fields = fields

# ===========================
# NESTED SERIALIZERS
# ===========================
class JobDetailSerializer(JobSerializer):
    """
    Extended Job serializer with nested applications.
    """
    applications = ApplicationSerializer(many=True, read_only=True)
    
    class Meta(JobSerializer.Meta):
        fields = JobSerializer.Meta.fields + ('applications',)

class ApplicationDetailSerializer(ApplicationSerializer):
    """
    Extended Application serializer with full history.
    """
    history = ApplicationHistorySerializer(many=True, read_only=True)
    
    class Meta(ApplicationSerializer.Meta):
        fields = ApplicationSerializer.Meta.fields + ('history',)
