from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings


DEFAULT_FROM_EMAIL = getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@ats.local")


@shared_task
def send_candidate_email(subject, body, to_email):
    """
    Sends email notifications to candidates.
    Called when:
    - Candidate applies for a job
    - Application stage changes
    """
    send_mail(
        subject,
        body,
        DEFAULT_FROM_EMAIL,
        [to_email],
        fail_silently=False,
    )
    return f"Email sent to candidate: {to_email}"


@shared_task
def send_recruiter_email(subject, body, to_email):
    """
    Sends email notifications to recruiters.
    Called when:
    - New application is submitted for their job
    """
    send_mail(
        subject,
        body,
        DEFAULT_FROM_EMAIL,
        [to_email],
        fail_silently=False,
    )
    return f"Email sent to recruiter: {to_email}"
