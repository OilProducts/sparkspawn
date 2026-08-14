use std::path::Path;
use std::sync::Arc;
use std::time::{Duration, Instant};

use attractor_api::AttractorApiService;
use attractor_core::CheckpointState;
use attractor_runtime::{
    human_gate_answered_event, prepare_fresh_run, NodeArtifacts, RunStore, RuntimeHandlerRunner,
};
use serde_json::json;
use spark_common::settings::SparkSettings;

fn settings(root: &Path) -> SparkSettings {
    SparkSettings {
        project_root: root.join("project"),
        data_dir: root.join("spark-home"),
        config_dir: root.join("spark-home/config"),
        runtime_dir: root.join("spark-home/runtime"),
        logs_dir: root.join("spark-home/logs"),
        workspace_dir: root.join("spark-home/workspace"),
        projects_dir: root.join("spark-home/workspace/projects"),
        attractor_dir: root.join("spark-home/attractor"),
        runs_dir: root.join("spark-home/attractor/runs"),
        flows_dir: root.join("spark-home/flows"),
        ui_dir: None,
        project_roots: Vec::new(),
    }
}

const GATE_FLOW: &str = r#"schema_version: "1"
id: recovery_gate
title: Recovery Gate
nodes:
  start:
    kind: start
  review:
    kind: human_gate
    config:
      kind: human_gate
      prompt: Ship the report?
  done:
    kind: exit
edges:
- from: start
  to: review
- from: review
  to: done
  label: Finish
"#;

const PAUSED_RECOVERY_FLOW: &str = r#"schema_version: "1"
id: paused_recovery
title: Paused Recovery
nodes:
  start: { kind: start }
  review:
    kind: human_gate
    runtime: { recovery_policy: pause }
    config: { kind: human_gate, prompt: Retry me? }
    contracts:
      writes_context: [context.accepted]
  done: { kind: exit }
edges:
- { from: start, to: review }
- { from: review, to: done, label: Finish }
"#;

const TREE_ROOT_FLOW: &str = r#"schema_version: "1"
id: tree_root
title: Tree Root
nodes:
  start: { kind: start }
  branch:
    kind: subflow
    runtime: { recovery_policy: pause }
    config: { kind: subflow, flow_ref: child.yaml }
    manager: { poll_interval: 0s, max_cycles: 1 }
  done: { kind: exit }
edges:
- { from: start, to: branch }
- { from: branch, to: done }
"#;

const TREE_CHILD_FLOW: &str = r#"schema_version: "1"
id: tree_child
title: Tree Child
nodes:
  start:
    kind: start
    runtime: { recovery_policy: pause }
  done: { kind: exit }
edges:
- { from: start, to: done }
"#;

/// Creates a run whose durable state says "parked at the review gate" with no
/// executor attached — exactly what a server restart leaves behind.
fn manufacture_orphaned_waiting_run(
    settings: &SparkSettings,
    workdir: &Path,
    run_id: &str,
) -> RunStore {
    let store = RunStore::for_settings(settings);
    let flow = attractor_dsl::parse_flow_definition(GATE_FLOW).expect("gate flow parses");
    let mut record = attractor_core::RunRecord::new(run_id, workdir.to_string_lossy());
    record.execution_profile_id = Some("native".to_string());
    record.flow_name = "recovery-gate".to_string();
    let launch_context = attractor_core::LaunchContext::empty();
    let runtime_context = attractor_core::ContextMap::from([(
        "internal.run_workdir".to_string(),
        json!(workdir.to_string_lossy().to_string()),
    )]);
    let paths = prepare_fresh_run(
        &store,
        &record,
        &flow,
        Some(GATE_FLOW.to_string()),
        None,
        &launch_context,
        &runtime_context,
    )
    .expect("prepare run");
    let checkpoint = CheckpointState {
        timestamp: "2026-07-14T12:00:00Z".to_string(),
        current_node: "review".to_string(),
        completed_nodes: vec!["start".to_string()],
        context: runtime_context,
        retry_counts: Default::default(),
        logs: Vec::new(),
    };
    store
        .save_checkpoint(&paths, &checkpoint, Default::default())
        .expect("save checkpoint");
    store
        .update_run_record(run_id, |record| {
            record.status = "waiting".to_string();
        })
        .expect("mark waiting");
    store
}

fn blocking_gate_service(settings: &SparkSettings) -> AttractorApiService {
    AttractorApiService::new_with_runtime_handler_runner_factory(
        settings.clone(),
        Arc::new(|| RuntimeHandlerRunner::new().with_blocking_human_gates()),
    )
}

fn wait_for_status(store: &RunStore, run_id: &str, expected: &str) {
    let deadline = Instant::now() + Duration::from_secs(10);
    loop {
        let status = store
            .read_run_bundle(run_id)
            .expect("read bundle")
            .and_then(|bundle| bundle.record)
            .map(|record| attractor_runtime::normalize_run_status(&record.status))
            .unwrap_or_default();
        if status == expected {
            return;
        }
        assert!(
            Instant::now() < deadline,
            "run never reached {expected}; last status {status}"
        );
        std::thread::sleep(Duration::from_millis(50));
    }
}

#[test]
fn startup_recovery_resumes_a_linked_orphaned_child_in_place() {
    let temp = tempfile::tempdir().expect("tempdir");
    let settings = settings(temp.path());
    std::fs::create_dir_all(&settings.config_dir).expect("config dir");
    let workdir = temp.path().join("project");
    std::fs::create_dir_all(&workdir).expect("workdir");
    let store = RunStore::for_settings(&settings);
    let root_flow = attractor_dsl::parse_flow_definition(TREE_ROOT_FLOW).expect("root flow");
    let child_flow = attractor_dsl::parse_flow_definition(TREE_CHILD_FLOW).expect("child flow");

    let mut root = attractor_core::RunRecord::new("tree-root", workdir.to_string_lossy());
    root.flow_name = "tree-root".to_string();
    root.root_run_id = Some("tree-root".to_string());
    root.execution_profile_id = Some("native".to_string());
    root.execution_profile_capabilities = Some(json!({"network": false}));
    root.execution_lock = Some(attractor_core::RunExecutionLock {
        scope: "project".to_string(),
        key: "tree".to_string(),
        conflict_policy: "queue".to_string(),
        identity: "tree-lock".to_string(),
        state: "acquired".to_string(),
        queue_position: None,
    });
    let root_context = attractor_core::ContextMap::from([
        ("internal.run_id".to_string(), json!("tree-root")),
        ("internal.root_run_id".to_string(), json!("tree-root")),
        (
            "internal.run_workdir".to_string(),
            json!(workdir.to_string_lossy().to_string()),
        ),
        (
            "context.stack.child.run_id".to_string(),
            json!("tree-child"),
        ),
        ("context.stack.child.status".to_string(), json!("running")),
    ]);
    let root_paths = prepare_fresh_run(
        &store,
        &root,
        &root_flow,
        Some(TREE_ROOT_FLOW.to_string()),
        None,
        &attractor_core::LaunchContext::empty(),
        &root_context,
    )
    .expect("prepare root");
    store
        .save_checkpoint(
            &root_paths,
            &CheckpointState {
                timestamp: "2026-08-14T00:00:00Z".to_string(),
                current_node: "branch".to_string(),
                completed_nodes: vec!["start".to_string()],
                context: root_context,
                retry_counts: Default::default(),
                logs: Vec::new(),
            },
            Default::default(),
        )
        .expect("checkpoint root");

    let mut child = attractor_core::RunRecord::new("tree-child", workdir.to_string_lossy());
    child.flow_name = "tree-child".to_string();
    child.parent_run_id = Some("tree-root".to_string());
    child.parent_node_id = Some("branch".to_string());
    child.root_run_id = Some("tree-root".to_string());
    child.child_invocation_index = Some(1);
    // Legacy children did not persist inherited placement metadata.
    child.execution_profile_id = None;
    let child_context = attractor_core::ContextMap::from([
        ("internal.run_id".to_string(), json!("tree-child")),
        ("internal.parent_run_id".to_string(), json!("tree-root")),
        ("internal.parent_node_id".to_string(), json!("branch")),
        ("internal.root_run_id".to_string(), json!("tree-root")),
        (
            "internal.run_workdir".to_string(),
            json!(workdir.to_string_lossy().to_string()),
        ),
    ]);
    let child_paths = prepare_fresh_run(
        &store,
        &child,
        &child_flow,
        Some(TREE_CHILD_FLOW.to_string()),
        None,
        &attractor_core::LaunchContext::empty(),
        &child_context,
    )
    .expect("prepare child");
    store
        .save_checkpoint(
            &child_paths,
            &CheckpointState {
                timestamp: "2026-08-14T00:00:01Z".to_string(),
                current_node: "start".to_string(),
                completed_nodes: Vec::new(),
                context: child_context,
                retry_counts: Default::default(),
                logs: Vec::new(),
            },
            Default::default(),
        )
        .expect("checkpoint child");

    store
        .write_node_artifacts(
            &child_paths,
            "start",
            0,
            0,
            &NodeArtifacts {
                response: Some("accepted before the crash\n".to_string()),
                status: Some(json!({
                    "outcome": "success",
                    "preferred_label": "",
                    "suggested_next_ids": [],
                    "context_updates": {},
                    "notes": ""
                })),
                under_logs: true,
                ..NodeArtifacts::default()
            },
        )
        .expect("durable child response");

    for run_id in ["tree-root", "tree-child"] {
        store
            .update_run_record(run_id, |record| {
                record.status = "failed".to_string();
                record.outcome = None;
                record.ended_at = None;
                record.last_error = "interrupted by restart".to_string();
            })
            .expect("mark restart interruption");
    }

    let recovery = blocking_gate_service(&settings).recover_interrupted_runs();
    assert_eq!(recovery["resumed"], json!(["tree-root"]), "{recovery:?}");
    let root_record = store
        .read_run_bundle("tree-root")
        .expect("root bundle")
        .and_then(|bundle| bundle.record)
        .expect("root record");
    assert_eq!(root_record.status, "waiting");
    assert_eq!(
        root_record.outcome_reason_code.as_deref(),
        Some("recovery_decision_required")
    );

    let retry = blocking_gate_service(&settings).retry_pipeline_route("tree-root");
    assert_eq!(retry.status_code, 200, "{:?}", retry.body);
    assert_eq!(retry.body["run_id"], json!("tree-root"));
    wait_for_status(&store, "tree-root", "completed");
    wait_for_status(&store, "tree-child", "completed");
    let children = store.list_child_run_bundles("tree-root").expect("children");
    assert_eq!(children.len(), 1, "recovery must not launch a sibling");
    assert_eq!(children[0].paths.run_id, "tree-child");
    let child = children[0].record.as_ref().expect("child record");
    assert_eq!(child.parent_run_id.as_deref(), Some("tree-root"));
    assert_eq!(child.parent_node_id.as_deref(), Some("branch"));
    assert_eq!(child.root_run_id.as_deref(), Some("tree-root"));
    assert_eq!(child.child_invocation_index, Some(1));
    assert_eq!(child.execution_profile_id.as_deref(), Some("native"));
    assert_eq!(
        child.execution_profile_capabilities,
        Some(json!({"network": false}))
    );
    assert_eq!(child.execution_lock, root.execution_lock);
    let child_checkpoint = children[0].checkpoint.as_ref().expect("child checkpoint");
    assert!(child_checkpoint
        .completed_nodes
        .contains(&"start".to_string()));
}

#[test]
fn recovery_pause_with_checkpoint_lag_consumes_the_durable_response() {
    let temp = tempfile::tempdir().expect("tempdir");
    let settings = settings(temp.path());
    std::fs::create_dir_all(&settings.config_dir).expect("config dir");
    let workdir = temp.path().join("project");
    std::fs::create_dir_all(&workdir).expect("workdir");
    let store = RunStore::for_settings(&settings);
    let flow = attractor_dsl::parse_flow_definition(PAUSED_RECOVERY_FLOW).expect("flow");
    let mut record = attractor_core::RunRecord::new("pause-answered", workdir.to_string_lossy());
    record.execution_profile_id = Some("native".to_string());
    let paths = prepare_fresh_run(
        &store,
        &record,
        &flow,
        Some(PAUSED_RECOVERY_FLOW.to_string()),
        None,
        &attractor_core::LaunchContext::empty(),
        &attractor_core::ContextMap::default(),
    )
    .expect("prepare");
    store
        .save_checkpoint(
            &paths,
            &CheckpointState {
                timestamp: "2026-08-14T00:00:00Z".to_string(),
                current_node: "review".to_string(),
                completed_nodes: vec!["start".to_string()],
                context: Default::default(),
                retry_counts: Default::default(),
                logs: Vec::new(),
            },
            Default::default(),
        )
        .expect("checkpoint");
    store
        .write_node_artifacts(
            &paths,
            "review",
            1,
            0,
            &NodeArtifacts {
                response: Some("accepted before checkpoint\n".to_string()),
                status: Some(json!({
                    "outcome": "success",
                    "preferred_label": "Finish",
                    "suggested_next_ids": [],
                    "context_updates": {},
                    "notes": ""
                })),
                under_logs: true,
                ..NodeArtifacts::default()
            },
        )
        .expect("durable response");

    let recovery = blocking_gate_service(&settings).recover_interrupted_runs();
    assert_eq!(recovery["resumed"], json!(["pause-answered"]));
    wait_for_status(&store, "pause-answered", "completed");
    let record = store
        .read_run_bundle("pause-answered")
        .expect("bundle")
        .and_then(|bundle| bundle.record)
        .expect("record");
    assert_ne!(
        record.outcome_reason_code.as_deref(),
        Some("recovery_decision_required")
    );
}

#[test]
fn recovery_rejects_incomplete_malformed_and_contract_invalid_durable_responses() {
    let temp = tempfile::tempdir().expect("tempdir");
    let settings = settings(temp.path());
    let workdir = temp.path().join("project");
    std::fs::create_dir_all(&workdir).expect("workdir");
    let store = RunStore::for_settings(&settings);
    let flow = attractor_dsl::parse_flow_definition(PAUSED_RECOVERY_FLOW).expect("flow");
    let node = flow.nodes.get("review").expect("review node");
    let record = attractor_core::RunRecord::new("invalid-durable", workdir.to_string_lossy());
    let paths = prepare_fresh_run(
        &store,
        &record,
        &flow,
        Some(PAUSED_RECOVERY_FLOW.to_string()),
        None,
        &attractor_core::LaunchContext::empty(),
        &attractor_core::ContextMap::default(),
    )
    .expect("prepare");

    let valid_status = json!({
        "outcome": "success",
        "preferred_label": "Finish",
        "suggested_next_ids": [],
        "context_updates": {},
        "notes": ""
    });
    store
        .write_node_artifacts(
            &paths,
            "review",
            1,
            0,
            &NodeArtifacts {
                status: Some(valid_status.clone()),
                under_logs: true,
                ..NodeArtifacts::default()
            },
        )
        .expect("status without response");
    assert!(attractor_runtime::durable_outcome(&store, &paths, "review", node, 1, 0).is_none());

    let mut contract_invalid_status = valid_status;
    contract_invalid_status["context_updates"] = json!({"context.forbidden": true});
    for (attempt, status) in [
        (1, json!({"outcome": "success"})),
        (2, contract_invalid_status),
    ] {
        store
            .write_node_artifacts(
                &paths,
                "review",
                1,
                attempt,
                &NodeArtifacts {
                    response: Some("unaccepted\n".to_string()),
                    status: Some(status),
                    under_logs: true,
                    ..NodeArtifacts::default()
                },
            )
            .expect("invalid durable artifacts");
        assert!(
            attractor_runtime::durable_outcome(&store, &paths, "review", node, 1, attempt)
                .is_none()
        );
    }
}

#[test]
fn startup_recovery_resumes_orphaned_waiting_run_and_consumes_journaled_answer() {
    let temp = tempfile::tempdir().expect("tempdir");
    let settings = settings(temp.path());
    std::fs::create_dir_all(&settings.config_dir).expect("config dir");
    let workdir = temp.path().join("project");
    std::fs::create_dir_all(&workdir).expect("workdir");
    let store = manufacture_orphaned_waiting_run(&settings, &workdir, "run-orphan-answered");

    // The user answered after the executor died: the answer is journaled,
    // nothing is consuming it.
    let bundle = store
        .read_run_bundle("run-orphan-answered")
        .expect("bundle")
        .expect("bundle exists");
    store
        .append_event(
            &bundle.paths,
            human_gate_answered_event(
                "run-orphan-answered",
                "review-1",
                Some("review".to_string()),
                Some("recovery-gate".to_string()),
                Some("Ship the report?".to_string()),
                "Finish",
                None,
            ),
        )
        .expect("journal answer");

    let recovery = blocking_gate_service(&settings).recover_interrupted_runs();
    assert_eq!(
        recovery["resumed"],
        json!(["run-orphan-answered"]),
        "{recovery:?}"
    );

    wait_for_status(&store, "run-orphan-answered", "completed");
}

#[test]
fn recovery_pause_survives_two_startups_without_retry_authorization() {
    let temp = tempfile::tempdir().expect("tempdir");
    let settings = settings(temp.path());
    std::fs::create_dir_all(&settings.config_dir).expect("config dir");
    let workdir = temp.path().join("project");
    std::fs::create_dir_all(&workdir).expect("workdir");
    let store = RunStore::for_settings(&settings);
    let flow = attractor_dsl::parse_flow_definition(PAUSED_RECOVERY_FLOW).expect("flow");
    let mut record = attractor_core::RunRecord::new("paused-twice", workdir.to_string_lossy());
    record.execution_profile_id = Some("native".to_string());
    let paths = prepare_fresh_run(
        &store,
        &record,
        &flow,
        Some(PAUSED_RECOVERY_FLOW.to_string()),
        None,
        &attractor_core::LaunchContext::empty(),
        &attractor_core::ContextMap::default(),
    )
    .expect("prepare");
    store
        .save_checkpoint(
            &paths,
            &CheckpointState {
                timestamp: "2026-08-14T00:00:00Z".to_string(),
                current_node: "review".to_string(),
                completed_nodes: vec!["start".to_string()],
                context: Default::default(),
                retry_counts: Default::default(),
                logs: Vec::new(),
            },
            Default::default(),
        )
        .expect("checkpoint");

    for _ in 0..2 {
        let result = blocking_gate_service(&settings).recover_interrupted_runs();
        assert_eq!(result["resumed"], json!(["paused-twice"]), "{result:?}");
        let record = store
            .read_run_bundle("paused-twice")
            .expect("bundle")
            .and_then(|bundle| bundle.record)
            .expect("record");
        assert_eq!(record.status, "waiting");
        assert_eq!(
            record.outcome_reason_code.as_deref(),
            Some("recovery_decision_required")
        );
    }
}

#[test]
fn parent_node_without_parent_run_is_stably_rejected() {
    let temp = tempfile::tempdir().expect("tempdir");
    let settings = settings(temp.path());
    std::fs::create_dir_all(&settings.config_dir).expect("config dir");
    let workdir = temp.path().join("project");
    std::fs::create_dir_all(&workdir).expect("workdir");
    let store = manufacture_orphaned_waiting_run(&settings, &workdir, "broken-lineage");
    store
        .update_run_record("broken-lineage", |record| {
            record.parent_node_id = Some("review".to_string());
        })
        .expect("corrupt lineage");

    for _ in 0..2 {
        let result = blocking_gate_service(&settings).recover_interrupted_runs();
        assert_eq!(result["resumed"], json!([]), "{result:?}");
        let record = store
            .read_run_bundle("broken-lineage")
            .expect("bundle")
            .and_then(|bundle| bundle.record)
            .expect("record");
        assert_eq!(record.status, "failed");
        assert_eq!(
            record.outcome_reason_code.as_deref(),
            Some("recovery_missing_lineage")
        );
    }
}

#[test]
fn cancel_finalizes_an_orphaned_run_immediately() {
    let temp = tempfile::tempdir().expect("tempdir");
    let settings = settings(temp.path());
    std::fs::create_dir_all(&settings.config_dir).expect("config dir");
    let workdir = temp.path().join("project");
    std::fs::create_dir_all(&workdir).expect("workdir");
    let store = manufacture_orphaned_waiting_run(&settings, &workdir, "run-orphan-cancel");

    let response = blocking_gate_service(&settings).cancel_pipeline_route("run-orphan-cancel");
    assert_eq!(response.status_code, 200, "{:?}", response.body);
    assert_eq!(
        response.body["status"],
        json!("canceled"),
        "{:?}",
        response.body
    );

    let status = store
        .read_run_bundle("run-orphan-cancel")
        .expect("bundle")
        .and_then(|bundle| bundle.record)
        .map(|record| attractor_runtime::normalize_run_status(&record.status))
        .unwrap_or_default();
    assert_eq!(status, "canceled", "no executor needed to finalize");
}

#[test]
fn startup_recovery_resumes_unanswered_gate_back_into_waiting() {
    let temp = tempfile::tempdir().expect("tempdir");
    let settings = settings(temp.path());
    std::fs::create_dir_all(&settings.config_dir).expect("config dir");
    let workdir = temp.path().join("project");
    std::fs::create_dir_all(&workdir).expect("workdir");
    let store = manufacture_orphaned_waiting_run(&settings, &workdir, "run-orphan-pending");

    let recovery = blocking_gate_service(&settings).recover_interrupted_runs();
    assert_eq!(
        recovery["resumed"],
        json!(["run-orphan-pending"]),
        "{recovery:?}"
    );

    // The resumed run re-enters the gate wait and republishes its pending
    // question; answering it then completes the run.
    wait_for_status(&store, "run-orphan-pending", "waiting");
    let bundle = store
        .read_run_bundle("run-orphan-pending")
        .expect("bundle")
        .expect("bundle exists");
    store
        .append_event(
            &bundle.paths,
            human_gate_answered_event(
                "run-orphan-pending",
                "review-1",
                Some("review".to_string()),
                Some("recovery-gate".to_string()),
                Some("Ship the report?".to_string()),
                "Finish",
                None,
            ),
        )
        .expect("journal answer");
    wait_for_status(&store, "run-orphan-pending", "completed");
}

#[test]
fn startup_recovery_marks_orphaned_running_runs_failed() {
    let temp = tempfile::tempdir().expect("tempdir");
    let settings = settings(temp.path());
    std::fs::create_dir_all(&settings.config_dir).expect("config dir");
    let workdir = temp.path().join("project");
    std::fs::create_dir_all(&workdir).expect("workdir");
    let store = RunStore::for_settings(&settings);
    let flow = attractor_dsl::parse_flow_definition(GATE_FLOW).expect("gate flow parses");
    let launch_context = attractor_core::LaunchContext::empty();
    let runtime_context = attractor_core::ContextMap::default();

    // A root and its child, both left in `running` by a dead process.
    for (run_id, parent) in [
        ("run-orphan-running-root", None),
        ("run-orphan-running-child", Some("run-orphan-running-root")),
    ] {
        let mut record = attractor_core::RunRecord::new(run_id, workdir.to_string_lossy());
        record.flow_name = "recovery-gate".to_string();
        record.parent_run_id = parent.map(str::to_string);
        prepare_fresh_run(
            &store,
            &record,
            &flow,
            Some(GATE_FLOW.to_string()),
            None,
            &launch_context,
            &runtime_context,
        )
        .expect("prepare run");
        store
            .update_run_record(run_id, |record| {
                record.status = "running".to_string();
            })
            .expect("mark running");
    }

    let recovery = blocking_gate_service(&settings).recover_interrupted_runs();
    let mut interrupted: Vec<String> = recovery["interrupted"]
        .as_array()
        .expect("interrupted list")
        .iter()
        .map(|value| value.as_str().expect("run id").to_string())
        .collect();
    interrupted.sort();
    assert_eq!(
        interrupted,
        vec![
            "run-orphan-running-child".to_string(),
            "run-orphan-running-root".to_string(),
        ],
        "{recovery:?}"
    );

    for run_id in ["run-orphan-running-root", "run-orphan-running-child"] {
        let record = store
            .read_run_bundle(run_id)
            .expect("read bundle")
            .expect("bundle exists")
            .record
            .expect("record");
        assert_eq!(record.status, "failed");
        assert!(
            record
                .last_error
                .contains("interrupted by an earlier restart"),
            "unexpected last_error: {}",
            record.last_error
        );
    }
}

#[test]
fn ambiguous_child_invocations_leave_parent_terminal_and_never_resume_it() {
    let temp = tempfile::tempdir().expect("tempdir");
    let settings = settings(temp.path());
    std::fs::create_dir_all(&settings.config_dir).expect("config dir");
    let workdir = temp.path().join("project");
    std::fs::create_dir_all(&workdir).expect("workdir");
    let store = RunStore::for_settings(&settings);
    let flow = attractor_dsl::parse_flow_definition(GATE_FLOW).expect("flow parses");

    for (run_id, parent) in [
        ("ambiguous-parent", None),
        ("ambiguous-child-a", Some("ambiguous-parent")),
        ("ambiguous-child-b", Some("ambiguous-parent")),
    ] {
        let mut record = attractor_core::RunRecord::new(run_id, workdir.to_string_lossy());
        record.flow_name = "recovery-gate".to_string();
        record.execution_profile_id = Some("native".to_string());
        record.root_run_id = Some("ambiguous-parent".to_string());
        if let Some(parent) = parent {
            record.parent_run_id = Some(parent.to_string());
            record.parent_node_id = Some("review".to_string());
            record.child_invocation_index = Some(1);
        }
        prepare_fresh_run(
            &store,
            &record,
            &flow,
            Some(GATE_FLOW.to_string()),
            None,
            &attractor_core::LaunchContext::empty(),
            &attractor_core::ContextMap::default(),
        )
        .expect("prepare run");
    }

    let service = blocking_gate_service(&settings);
    let first = service.recover_interrupted_runs();
    assert_eq!(first["resumed"], json!([]), "{first:?}");
    let record = store
        .read_run_bundle("ambiguous-parent")
        .expect("bundle")
        .and_then(|bundle| bundle.record)
        .expect("record");
    assert_eq!(record.status, "failed");
    assert_eq!(
        record.outcome_reason_code.as_deref(),
        Some("recovery_ambiguous_child_invocation")
    );
    let second = service.recover_interrupted_runs();
    assert_eq!(second["resumed"], json!([]), "{second:?}");
    let record = store
        .read_run_bundle("ambiguous-parent")
        .expect("bundle")
        .and_then(|bundle| bundle.record)
        .expect("record");
    assert_eq!(record.status, "failed");
    assert_eq!(
        record.outcome_reason_code.as_deref(),
        Some("recovery_ambiguous_child_invocation"),
        "terminal failure code must be stable"
    );
    for child_id in ["ambiguous-child-a", "ambiguous-child-b"] {
        let child = store
            .read_run_bundle(child_id)
            .expect("child bundle")
            .and_then(|bundle| bundle.record)
            .expect("child record");
        assert_eq!(child.status, "failed", "ambiguous child must be terminal");
        assert_eq!(
            child.outcome_reason_code.as_deref(),
            Some("recovery_ambiguous_child_invocation"),
            "child failure code must be stable"
        );
    }
}
