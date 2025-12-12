from django.db import models
from django.contrib.auth.models import AbstractUser


# ===========================
# USER MODEL (RBAC)
# ===========================

class User(AbstractUser):

    ROLE_CHOICES = [
        ("candidate", "Candidate"),
        ("recruiter", "Recruiter"),
        ("manager", "Hiring Manager"),
    ]

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default="candidate",
    )

    # Recruiters / Hiring Managers belong to a company
    company = models.ForeignKey(
        "Company",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="users",
    )

    def __str__(self):
        return f"{self.username} ({self.role})"


# ===========================
# COMPANY
# ===========================

class Company(models.Model):

    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


# ===========================
# JOB
# ===========================

class Job(models.Model):

    STATUS_CHOICES = [
        ("open", "Open"),
        ("closed", "Closed"),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="open",
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="jobs",
    )

    def __str__(self):
        return f"{self.title} @ {self.company.name}"


# ===========================
# APPLICATION
# ===========================

class Application(models.Model):

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
    )

    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name="applications",
    )

    stage = models.CharField(
        max_length=20,
        choices=STAGE_CHOICES,
        default="Applied",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    # ✅ PREVENT DUPLICATE APPLICATIONS
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["candidate", "job"],
                name="unique_candidate_job",
            )
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
        return next_stage in self.VALID_TRANSITIONS.get(self.stage, [])

    def __str__(self):
        return f"{self.candidate.username} → {self.job.title} [{self.stage}]"


# ===========================
# APPLICATION HISTORY
# ===========================

class ApplicationHistory(models.Model):

    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name="history",
    )

    from_stage = models.CharField(max_length=20)
    to_stage = models.CharField(max_length=20)

    changed_by = models.ForeignKey(
        User,
        null=True,
        on_delete=models.SET_NULL,
        related_name="stage_changes",
    )

    changed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.application} ({self.from_stage} → {self.to_stage})"
