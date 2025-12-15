"""
Test suite for the Mergington High School Activities API
"""

import pytest
from fastapi.testclient import TestClient
import sys
from pathlib import Path

# Add the src directory to the path so we can import app
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app import app, activities


@pytest.fixture
def client():
    """Create a test client for the FastAPI app"""
    return TestClient(app)


@pytest.fixture
def reset_activities():
    """Reset activities to initial state before each test"""
    # Store original state
    original_activities = {
        key: {
            "description": value["description"],
            "schedule": value["schedule"],
            "max_participants": value["max_participants"],
            "participants": value["participants"].copy()
        }
        for key, value in activities.items()
    }
    
    # Clear participants for tests
    for activity in activities.values():
        activity["participants"].clear()
    
    yield
    
    # Restore original state after test
    for key, value in original_activities.items():
        activities[key]["participants"] = value["participants"]


class TestRootEndpoint:
    """Test the root endpoint"""
    
    def test_root_redirects_to_static(self, client):
        """Test that root endpoint redirects to static index.html"""
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 307
        assert response.headers["location"] == "/static/index.html"


class TestGetActivities:
    """Test the GET /activities endpoint"""
    
    def test_get_all_activities(self, client, reset_activities):
        """Test retrieving all activities"""
        response = client.get("/activities")
        assert response.status_code == 200
        data = response.json()
        
        # Verify all expected activities are present
        expected_activities = [
            "Basketball Team", "Soccer Club", "Art Club", "Drama Club",
            "Debate Team", "Math Club", "Chess Club", "Programming Class", "Gym Class"
        ]
        for activity in expected_activities:
            assert activity in data
    
    def test_activity_has_required_fields(self, client, reset_activities):
        """Test that activities have all required fields"""
        response = client.get("/activities")
        data = response.json()
        
        activity = data["Basketball Team"]
        assert "description" in activity
        assert "schedule" in activity
        assert "max_participants" in activity
        assert "participants" in activity
        assert isinstance(activity["participants"], list)


class TestSignupForActivity:
    """Test the POST /activities/{activity_name}/signup endpoint"""
    
    def test_successful_signup(self, client, reset_activities):
        """Test successful signup for an activity"""
        response = client.post(
            "/activities/Basketball Team/signup",
            params={"email": "student@mergington.edu"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "Signed up" in data["message"]
        assert "student@mergington.edu" in data["message"]
    
    def test_signup_adds_to_participants(self, client, reset_activities):
        """Test that signup actually adds the student to participants"""
        email = "john.doe@mergington.edu"
        client.post("/activities/Soccer Club/signup", params={"email": email})
        
        response = client.get("/activities")
        participants = response.json()["Soccer Club"]["participants"]
        assert email in participants
    
    def test_signup_nonexistent_activity(self, client, reset_activities):
        """Test signup fails for non-existent activity"""
        response = client.post(
            "/activities/Nonexistent Activity/signup",
            params={"email": "student@mergington.edu"}
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    def test_signup_duplicate_email(self, client, reset_activities):
        """Test that same email cannot sign up twice"""
        email = "student@mergington.edu"
        
        # First signup should succeed
        response1 = client.post(
            "/activities/Art Club/signup",
            params={"email": email}
        )
        assert response1.status_code == 200
        
        # Second signup should fail
        response2 = client.post(
            "/activities/Art Club/signup",
            params={"email": email}
        )
        assert response2.status_code == 400
        assert "already signed up" in response2.json()["detail"].lower()
    
    def test_signup_activity_full(self, client, reset_activities):
        """Test signup fails when activity is at max capacity"""
        activity_name = "Chess Club"
        
        # Get max participants
        response = client.get("/activities")
        max_participants = response.json()[activity_name]["max_participants"]
        
        # Sign up students until full
        for i in range(max_participants):
            client.post(
                f"/activities/{activity_name}/signup",
                params={"email": f"student{i}@mergington.edu"}
            )
        
        # Next signup should fail
        response = client.post(
            f"/activities/{activity_name}/signup",
            params={"email": "extra.student@mergington.edu"}
        )
        assert response.status_code == 400
        assert "full" in response.json()["detail"].lower()
    
    def test_multiple_activities_signup(self, client, reset_activities):
        """Test that same student can sign up for multiple activities"""
        email = "versatile.student@mergington.edu"
        
        # Sign up for multiple activities
        response1 = client.post(
            "/activities/Basketball Team/signup",
            params={"email": email}
        )
        response2 = client.post(
            "/activities/Drama Club/signup",
            params={"email": email}
        )
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        # Verify in both activities
        response = client.get("/activities")
        assert email in response.json()["Basketball Team"]["participants"]
        assert email in response.json()["Drama Club"]["participants"]


class TestParticipantLimits:
    """Test participant limit enforcement"""
    
    def test_max_participants_respected(self, client, reset_activities):
        """Test that max_participants limit is enforced"""
        activity_name = "Debate Team"
        response = client.get("/activities")
        max_participants = response.json()[activity_name]["max_participants"]
        
        # Sign up exactly max_participants
        for i in range(max_participants):
            response = client.post(
                f"/activities/{activity_name}/signup",
                params={"email": f"debater{i}@mergington.edu"}
            )
            assert response.status_code == 200
        
        # Verify we have max_participants
        response = client.get("/activities")
        assert len(response.json()[activity_name]["participants"]) == max_participants
