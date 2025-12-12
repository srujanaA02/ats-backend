from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model

from ats.models import Company, Job, Application

User = get_user_model()


# -----------------------
# Helper creators
# -----------------------

def create_user(username, role):
    return User.objects.create_user(
        username=username,
        password="testpass123",
        email=f"{username}@example.com",
        role=role
    )


# -----------------------
# BASE CLASS
# -----------------------

class ATSTestBase(APITestCase):

    def setUp(self):
        # Company
        self.company = Company.objects.create(name="Test Corp")

        # Users
        self.candidate = create_user("candidate1", "candidate")
        self.recruiter = create_user("recruiter1", "recruiter")
        self.manager = create_user("manager1", "hiring_manager")

        # Tie recruiter + manager to company
        self.recruiter.company = self.company
        self.recruiter.save()

        self.manager.company = self.company
        self.manager.save()

        # Job
        self.job = Job.objects.create(
            title="Backend Developer",
            description="Test job",
            company=self.company,
            status="open"
        )


    def authenticate(self, user):
        """
        Login user and attach JWT token to API client
        """
        url = reverse("token_obtain_pair")

        response = self.client.post(
            url,
            {
                "username": user.username,
                "password": "testpass123"
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        token = response.data["access"]

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token}"
        )



# -----------------------
# APPLICATION TESTS
# -----------------------

class ApplicationTests(ATSTestBase):

    def test_candidate_can_apply(self):
        """
        Candidate should be able to apply for a job
        """
        self.authenticate(self.candidate)

        url = reverse("apply-job")

        response = self.client.post(
            url,
            {"job": self.job.id},
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.assertEqual(Application.objects.count(), 1)

        application = Application.objects.first()
        self.assertEqual(application.stage, "Applied")
        self.assertEqual(application.candidate, self.candidate)
        self.assertEqual(application.job, self.job)


    def test_recruiter_cannot_apply(self):
        """
        Recruiter should NOT be able to apply to a job
        """
        self.authenticate(self.recruiter)

        url = reverse("apply-job")

        response = self.client.post(
            url,
            {"job": self.job.id},
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)



# -----------------------
# STAGE TRANSITION TESTS
# -----------------------

class StageTransitionTests(ATSTestBase):

    def setUp(self):
        super().setUp()

        self.application = Application.objects.create(
            job=self.job,
            candidate=self.candidate,
            stage="Applied"
        )


    def test_valid_stage_transition(self):
        """
        Recruiter can move stage:
        Applied -> Screening
        """
        self.authenticate(self.recruiter)

        url = reverse(
            "change-application-stage",
            args=[self.application.id]
        )

        response = self.client.post(
            url,
            {"stage": "Screening"},
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.application.refresh_from_db()

        self.assertEqual(self.application.stage, "Screening")


    def test_invalid_stage_transition(self):
        """
        Applied -> Offer should fail
        """
        self.authenticate(self.recruiter)

        url = reverse(
            "change-application-stage",
            args=[self.application.id]
        )

        response = self.client.post(
            url,
            {"stage": "Offer"},
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


    def test_any_stage_can_reject(self):
        """
        Rejection should be allowed from any stage
        """
        self.authenticate(self.recruiter)

        url = reverse(
            "change-application-stage",
            args=[self.application.id]
        )

        response = self.client.post(
            url,
            {"stage": "Rejected"},
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.application.refresh_from_db()

        self.assertEqual(self.application.stage, "Rejected")



# -----------------------
# RBAC TESTS
# -----------------------

class RBACPermissionTests(ATSTestBase):

    def test_candidate_cannot_change_stage(self):
        """
        Candidate must NOT be allowed
        to move application stages.
        """

        application = Application.objects.create(
            job=self.job,
            candidate=self.candidate,
            stage="Applied"
        )

        self.authenticate(self.candidate)

        url = reverse(
            "change-application-stage",
            args=[application.id]
        )

        response = self.client.post(
            url,
            {"stage": "Screening"},
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


    def test_recruiter_can_view_applications(self):
        """
        Recruiter should be able to list
        job applications
        """

        Application.objects.create(
            job=self.job,
            candidate=self.candidate,
            stage="Applied"
        )

        self.authenticate(self.recruiter)

        url = reverse(
            "job-applications",
            args=[self.job.id]
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(len(response.data), 1)
