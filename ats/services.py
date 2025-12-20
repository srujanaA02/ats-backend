from django.db import transaction
from .models import Application, ApplicationHistory
from .workflow import validate_transition
from . import tasks

def change_application_stage(application, new_stage, actor):
    """
    Update application stage with transaction and history.
    Also triggers async email notifications.
    """
    if not validate_transition(application.stage, new_stage):
        raise ValueError("Invalid workflow stage transition")
    
    with transaction.atomic():
        old_stage = application.stage
        application.stage = new_stage
        application.save()
        
        ApplicationHistory.objects.create(
            application=application,
            from_stage=old_stage,
            to_stage=new_stage,
            changed_by=actor,
        )
    
    # Trigger async email after transaction commits
    tasks.send_candidate_email.delay(
        subject=f"Application Status Update: {new_stage}",
        body=f"Your application for {application.job.title} has been updated to {new_stage}.",
        to_email=application.candidate.email,
    )


def create_application(candidate, job):
    """
    Create application with transaction and trigger async notifications.
    """
    # Check if candidate already applied
    if Application.objects.filter(candidate=candidate, job=job).exists():
        raise ValueError("You have already applied for this job")
    
    with transaction.atomic():
        application = Application.objects.create(
            candidate=candidate,
            job=job,
            stage="Applied",
        )
    
    # Trigger async email notifications AFTER transaction commits
    tasks.send_candidate_email.delay(
        subject="Application Confirmation",
        body=f"Your application for {job.title} has been received.",
        to_email=candidate.email,
    )
    
    # Notify recruiters in the company
    recruiter_emails = job.company.users.filter(role="recruiter").values_list("email", flat=True)
    for recruiter_email in recruiter_emails:
        tasks.send_recruiter_email.delay(
            subject=f"New Application: {job.title}",
            body=f"{candidate.username} applied for {job.title}.",
            to_email=recruiter_email,
        )
    
    return application
