import json

from tools.graph_index import (
    EdgeRecord,
    NodeRecord,
    deterministic_edge_id,
    deterministic_node_id,
    doctor_graph,
    load_graph,
    optimize_graph,
    rebuild_indexes,
    save_graph,
)


def test_path_backed_node_id_does_not_change_when_title_changes():
    first = deterministic_node_id(
        node_type="Workflow",
        scope="global",
        path="brain/workflows/review.md",
        title="Old title",
    )
    second = deterministic_node_id(
        node_type="Workflow",
        scope="global",
        path="./brain/workflows/review.md",
        title="New title",
    )

    assert first == second


def test_entry_backed_node_id_uses_entry_key():
    first = deterministic_node_id(
        node_type="Preference",
        scope="global",
        path="memory/USER.md",
        title="Use Chinese",
        metadata={"entry_key": "pref-001"},
    )
    second = deterministic_node_id(
        node_type="Preference",
        scope="global",
        path="memory/USER.md",
        title="使用中文",
        metadata={"entry_key": "pref-001"},
    )
    different = deterministic_node_id(
        node_type="Preference",
        scope="global",
        path="memory/USER.md",
        title="Use Chinese",
        metadata={"entry_key": "pref-002"},
    )

    assert first == second
    assert first != different


def test_concept_like_node_id_uses_title_even_when_path_matches():
    first = deterministic_node_id(
        node_type="Evidence",
        scope="project",
        project_slug="roleme",
        path="projects/roleme/memory.md",
        title="Evidence for first memory",
    )
    second = deterministic_node_id(
        node_type="Evidence",
        scope="project",
        project_slug="roleme",
        path="projects/roleme/memory.md",
        title="Evidence for second memory",
    )

    assert first != second


def test_save_and_load_graph_round_trips_jsonl(tmp_path):
    role_path = tmp_path / "role"
    workflow = NodeRecord(
        id="node-workflow",
        type="Workflow",
        scope="global",
        path="brain/workflows/review.md",
        title="Review workflow",
        aliases=("review", "审查"),
        keywords=("review",),
        metadata={"entry_key": "wf-review"},
    )
    evidence = NodeRecord(
        id="node-evidence",
        type="Evidence",
        scope="global",
        title="User statement",
    )
    edge = EdgeRecord(
        id=deterministic_edge_id("node-workflow", "evidenced_by", "node-evidence"),
        type="evidenced_by",
        from_node="node-workflow",
        to_node="node-evidence",
        weight=0.8,
        rationale="archived from user statement",
        metadata={"source": "test"},
    )

    save_graph(role_path, [workflow, evidence], [edge])
    loaded = load_graph(role_path)

    assert loaded.nodes == [workflow, evidence]
    assert loaded.edges == [edge]
    assert (role_path / "brain" / "graph" / "nodes.jsonl").exists()
    assert (role_path / "brain" / "graph" / "edges.jsonl").exists()


def test_rebuild_indexes_writes_type_path_alias_and_project_indexes(tmp_path):
    role_path = tmp_path / "role"
    nodes = [
        NodeRecord(
            id="project-roleme",
            type="Project",
            scope="project",
            project_slug="roleme",
            path="projects/roleme/context.md",
            title="roleMe",
            aliases=("role me",),
        ),
        NodeRecord(
            id="workflow-review",
            type="Workflow",
            scope="project",
            project_slug="roleme",
            path="projects/roleme/workflows/review.md",
            title="Review",
            aliases=("审查",),
        ),
    ]

    rebuild_indexes(role_path, nodes)

    indexes_dir = role_path / "brain" / "graph" / "indexes"
    assert json.loads((indexes_dir / "by-type.json").read_text(encoding="utf-8")) == {
        "Project": ["project-roleme"],
        "Workflow": ["workflow-review"],
    }
    assert json.loads((indexes_dir / "by-path.json").read_text(encoding="utf-8")) == {
        "projects/roleme/context.md": ["project-roleme"],
        "projects/roleme/workflows/review.md": ["workflow-review"],
    }
    assert json.loads((indexes_dir / "by-alias.json").read_text(encoding="utf-8")) == {
        "role me": ["project-roleme"],
        "roleme": ["project-roleme"],
        "review": ["workflow-review"],
        "审查": ["workflow-review"],
    }
    assert json.loads((indexes_dir / "by-project.json").read_text(encoding="utf-8")) == {
        "roleme": ["project-roleme", "workflow-review"],
    }


def test_doctor_graph_reports_duplicate_nodes_orphan_edges_and_missing_entry_key(tmp_path):
    role_path = tmp_path / "role"
    nodes_path = role_path / "brain" / "graph" / "nodes.jsonl"
    edges_path = role_path / "brain" / "graph" / "edges.jsonl"
    nodes_path.parent.mkdir(parents=True)
    nodes_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "id": "preference-1",
                        "type": "Preference",
                        "scope": "global",
                        "path": "memory/USER.md",
                    }
                ),
                json.dumps(
                    {
                        "id": "preference-1",
                        "type": "Preference",
                        "scope": "global",
                        "path": "memory/USER.md",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    edges_path.write_text(
        json.dumps(
            {
                "id": "edge-1",
                "type": "evidenced_by",
                "from": "preference-1",
                "to": "missing-evidence",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    report = doctor_graph(role_path)

    assert any("duplicate node id: preference-1" in warning for warning in report.warnings)
    assert any("orphan edge target: edge-1 -> missing-evidence" in warning for warning in report.warnings)
    assert any("entry-backed node missing metadata.entry_key: preference-1" in warning for warning in report.warnings)


def test_doctor_graph_reports_workflow_index_mismatch_low_confidence_and_unbacked_relations(tmp_path):
    role_path = tmp_path / "role"
    workflows_dir = role_path / "brain" / "workflows"
    workflows_dir.mkdir(parents=True)
    (workflows_dir / "index.md").write_text(
        "# 工作流索引\n\n"
        "## archive\n"
        "- title: Archive workflow\n"
        "- file: archive.md\n"
        "- applies_to: 归档时使用\n"
        "- keywords: archive\n"
        "- summary: 归档流程\n",
        encoding="utf-8",
    )
    orphan_evidence = NodeRecord(id="evidence-1", type="Evidence", scope="global")
    low_rule = NodeRecord(id="rule-1", type="Rule", scope="global", title="Important", confidence="low")
    old_decision = NodeRecord(id="decision-old", type="Decision", scope="global")
    new_decision = NodeRecord(id="decision-new", type="Decision", scope="global")
    edge = EdgeRecord(
        id=deterministic_edge_id("decision-new", "supersedes", "decision-old"),
        type="supersedes",
        from_node="decision-new",
        to_node="decision-old",
    )
    save_graph(role_path, [orphan_evidence, low_rule, old_decision, new_decision], [edge])

    report = doctor_graph(role_path)

    assert any("workflow index entry missing graph node: brain/workflows/archive.md" in warning for warning in report.warnings)
    assert any("low confidence strong node: rule-1" in warning for warning in report.warnings)
    assert any("orphan evidence node: evidence-1" in warning for warning in report.warnings)
    assert any("relationship missing evidence or episode source: edge-" in warning for warning in report.warnings)


def test_optimize_graph_removes_orphan_edges_rebuilds_indexes_and_backfills_workflows(tmp_path):
    role_path = tmp_path / "role"
    workflows_dir = role_path / "brain" / "workflows"
    workflows_dir.mkdir(parents=True)
    (workflows_dir / "index.md").write_text(
        "# 工作流索引\n\n"
        "## archive\n"
        "- title: Archive workflow\n"
        "- file: archive.md\n"
        "- applies_to: 归档时使用\n"
        "- keywords: archive\n"
        "- summary: 归档流程\n",
        encoding="utf-8",
    )
    project = NodeRecord(id="project-1", type="Project", scope="project", project_slug="roleme", path="projects/roleme/context.md")
    orphan_edge = EdgeRecord(id="edge-orphan", type="related_to", from_node="project-1", to_node="missing")
    save_graph(role_path, [project], [orphan_edge])

    result = optimize_graph(role_path)
    graph = load_graph(role_path)

    assert any("removed orphan edges: 1" in repair for repair in result.repairs)
    assert any("backfilled workflow node: brain/workflows/archive.md" in repair for repair in result.repairs)
    assert graph.edges == []
    assert any(node.type == "Workflow" and node.path == "brain/workflows/archive.md" for node in graph.nodes)
    assert (role_path / "brain" / "graph" / "indexes" / "by-type.json").exists()
