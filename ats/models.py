from django.db import models
from django.contrib.auth.models import AbstractUser

# ===========================
# USER MODEL (RBAC)
# ===========================
class User(AbstractUser):
    """
    Custom user model extending Django's AbstractUser.
    Implements Role-Based Access Control (RBAC) for the ATS system.
    
    Roles:
    - candidate: Job applicants
    - recruiter: Company recruiters who manage jobs and applications
    - manager: Hiring managers who review candidates
    """
    ROLE_CHOICES = [
        ("candidate", "Candidate"),
        ("recruiter", "Recruiter"),
        ("manager", "Hiring Manager"),
    ]
    
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default="candidate",
        db_index=True,  # Index for filtering by role
    )
    
    # Recruiters / Hiring Managers belong to a company
    company = models.ForeignKey(
        "Company",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="users",
        db_index=True,  # Index for filtering by company
    )
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.username} ({self.role})"
    
    class Meta:
        indexes = [
            models.Index(fields=['role']),
            models.Index(fields=['company']),
            models.Index(fields=['created_at']),
        ]

# ===========================
# COMPANY
# ===========================
class Company(models.Model):
    """
    Represents a hiring company in the ATS system.
    """
    name = models.CharField(max_length=255, unique=True, db_index=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name_plural = "Companies"
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['created_at']),
        ]

# ===========================
# JOB
# ===========================
class Job(models.Model):
    """
    Represents a job posting from a company.
    """
    STATUS_CHOICES = [
        ("open", "Open"),
        ("closed", "Closed"),
    ]
    
    title = models.CharField(max_length=255, db_index=True)
    description = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="open",
        db_index=True,
    )
    
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="jobs",
        db_index=True,
    )
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.title} @ {self.company.name}"
    
    class Meta:
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['company']),
            models.Index(fields=['created_at']),
            models.Index(fields=['status', 'company']),
        ]

# ===========================
# APPLICATION
# ===========================
class Application(models.Model):
    """
    Represents a candidate's application to a job.
    Implements a strict workflow state machine for application stages.
    
    Valid transitions:
    Applied -> Screening -> Interview -> Offer -> Hired
                  |         |          |       |
                  +---> Rejected <-----+-------+
    
    From any stage except Hired and Rejected, candidates can be rejected.
    """
    # ✅ MUST MATCH TEST VALUES EXACTLY
    STAGE_CHOICES = [
        ("Applied", "Applied"),
        ("Screening", "Screening"),
        ("Interview", "Interview"),
        ("Offer", "Offer"),
        ("Hired", "Hired"),
        ("Rejected", "Rejected"),
    ]
    
    candidate = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="applications",
        db_index=True,
        limit_choices_to={"role": "candidate"},
    )
    
    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name="applications",
        db_index=True,
    )
    
    stage = models.CharField(
        max_length=20,
        choices=STAGE_CHOICES,
        default="Applied",
        db_index=True,
    )
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # ✅ PREVENT DUPLICATE APPLICATIONS
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["candidate", "job"],
                name="unique_candidate_job",
            )
        ]
        indexes = [
            models.Index(fields=['candidate']),
            models.Index(fields=['job']),
            models.Index(fields=['stage']),
            models.Index(fields=['created_at']),
            models.Index(fields=['candidate', 'stage']),
            models.Index(fields=['job', 'stage']),
        ]
    
    # ✅ WORKFLOW STATE MACHINE
    VALID_TRANSITIONS = {
        "Applied": ["Screening", "Rejected"],
        "Screening": ["Interview", "Rejected"],
        "Interview": ["Offer", "Rejected"],
        "Offer": ["Hired", "Rejected"],
        "Hired": [],
        "Rejected": [],
    }
    
    def can_transition_to(self, next_stage):
        """Check if transition from current stage to next_stage is valid."""
        if next_stage not in [choice[0] for choice in self.STAGE_CHOICES]:
            return False
        return next_stage in self.VALID_TRANSITIONS.get(self.stage, [])
    
    def __str__(self):
        return f"{self.candidate.username} → {self.job.title} [{self.stage}]"

# ===========================
# APPLICATION HISTORY
# ===========================
class ApplicationHistory(models.Model):
    """
    Audit log for application stage transitions.
    Tracks who changed the stage and when.
    """
    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name="history",
        db_index=True,
    )
    
    from_stage = models.CharField(max_length=20, db_index=True)
    to_stage = models.CharField(max_length=20, db_index=True)
    
    changed_by = models.ForeignKey(
        User,
        null=True,
        on_delete=models.SET_NULL,
        related_name="stage_changes",
        limit_choices_to={"role__in": ["recruiter", "manager"]},
    )
    
    changed_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    def __str__(self):
        return f"{self.application} ({self.from_stage} → {self.to_stage})"
    
    class Meta:
        verbose_name_plural = "Application Histories"
        ordering = ['-changed_at']
        indexes = [
            models.Index(fields=['application']),
            models.Index(fields=['changed_at']),
            models.Index(fields=['from_stage', 'to_stage']),
        ]
