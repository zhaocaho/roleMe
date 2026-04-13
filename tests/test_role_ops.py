from tools.role_ops import doctor_role, initialize_role, list_roles, load_role_bundle


def test_initialize_role_creates_required_files(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")

    assert (role_path / "AGENT.md").exists()
    assert (role_path / "role.json").exists()
    assert (role_path / "brain" / "topics").is_dir()
    assert (role_path / "memory" / "episodes").is_dir()


def test_load_role_bundle_returns_resident_and_on_demand_paths(tmp_role_home):
    initialize_role("self", skill_version="0.1.0")
    bundle = load_role_bundle("self")

    assert bundle.role_name == "self"
    assert "memory/MEMORY.md" in bundle.resident_files
    assert "memory/episodes" in bundle.on_demand_paths


def test_list_roles_returns_sorted_names(tmp_role_home):
    initialize_role("beta", skill_version="0.1.0")
    initialize_role("alpha", skill_version="0.1.0")

    assert list_roles() == ["alpha", "beta"]


def test_doctor_role_reports_missing_file(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")
    (role_path / "AGENT.md").unlink()

    report = doctor_role("self")
    assert "AGENT.md" in report.missing_files
