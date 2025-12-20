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
