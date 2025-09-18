def test_privacy_policy_served_as_html(client):
    response = client.get("/privacy-policy")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Privacy Policy" in response.text
