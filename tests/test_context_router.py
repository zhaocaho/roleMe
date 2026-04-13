from tools.context_router import route_context_lookup
from tools.role_ops import initialize_role


def test_route_context_prefers_brain_for_domain_queries(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")

    result = route_context_lookup(role_path, query="帮我分析这个 AI 产品策略")

    assert result.primary_path == "brain/index.md"
    assert "memory/episodes/*" in result.fallback_paths


def test_route_context_prefers_projects_for_project_queries(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")

    result = route_context_lookup(role_path, query="这个仓库里的 roleMe 重构怎么推进")

    assert result.primary_path == "projects/index.md"
    assert "brain/index.md" in result.fallback_paths
