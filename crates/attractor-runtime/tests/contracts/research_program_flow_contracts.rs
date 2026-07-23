use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Arc;

use attractor_core::{FlowDefinition, LaunchContext, Outcome, OutcomeStatus, RunRecord};
use attractor_runtime::{
    prepare_fresh_run, ExecuteRunRequest, ExecutionStart, PipelineExecutor, RunStore,
    RuntimeHandlerRunner, HANDLER_CODERGEN,
};

fn load_flow() -> FlowDefinition {
    let yaml = std::fs::read_to_string(concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/../spark-assets/assets/flows/math-research/research-program.yaml"
    ))
    .expect("read flow yaml");
    let flow = FlowDefinition::from_yaml_str(&yaml).expect("parse flow");
    flow.validate().expect("valid flow");
    flow
}

fn run_flow(
    workdir: &std::path::Path,
    runs_dir: &std::path::Path,
    run_id: &str,
    runner: RuntimeHandlerRunner,
) -> attractor_runtime::PipelineExecutionResult {
    let flow = load_flow();
    let store = RunStore::for_runs_dir(runs_dir.to_path_buf());
    let mut record = RunRecord::new(run_id, workdir.to_string_lossy());
    record.flow_name = flow.title.clone();
    let launch_context = LaunchContext::empty();
    let runtime_context = attractor_core::ContextMap::from([(
        "internal.run_workdir".to_string(),
        serde_json::json!(workdir.to_string_lossy().to_string()),
    )]);
    let paths = prepare_fresh_run(
        &store,
        &record,
        &flow,
        None,
        None,
        &launch_context,
        &runtime_context,
    )
    .expect("prepare run");
    let mut executor = PipelineExecutor::new(runner);
    executor
        .execute(ExecuteRunRequest {
            store,
            record,
            flow,
            flow_source: None,
            flow_definition_json: None,
            launch_context,
            runtime_context,
            max_steps: None,
            start: ExecutionStart::Prepared { paths },
        })
        .expect("execute run")
}

#[test]
fn research_program_cycles_explore_attack_and_park() {
    let temp = tempfile::tempdir().expect("tempdir");
    let workdir = temp.path().join("project");
    std::fs::create_dir_all(&workdir).expect("workdir");

    let orient_calls = Arc::new(AtomicUsize::new(0));
    let calls = Arc::clone(&orient_calls);
    let wd = workdir.clone();
    let mut runner = RuntimeHandlerRunner::new();
    runner.register_thread_safe_handler_fn(HANDLER_CODERGEN, move |runtime| {
        match runtime.node_id.as_str() {
            "orient" => {
                let _ = std::fs::create_dir_all(wd.join(".mathlab"));
                let _ = std::fs::write(wd.join(".mathlab/cycle.md"), "# probe cycle\n");
            }
            "experiment" => {
                let _ = std::fs::create_dir_all(wd.join("experiments"));
                let _ = std::fs::write(wd.join("experiments/verify.sh"), "exit 0\n");
            }
            "refute" => {
                let _ = std::fs::create_dir_all(wd.join("refuter"));
                let _ = std::fs::write(wd.join("refuter/verify.sh"), "exit 0\n");
            }
            _ => {}
        }
        let preferred = match runtime.node_id.as_str() {
            "orient" => match calls.fetch_add(1, Ordering::SeqCst) {
                0 => "Explore",
                1 => "Attack",
                _ => "Park",
            },
            "arbiter" => "Findings",
            _ => "",
        };
        Ok(Outcome {
            status: OutcomeStatus::Success,
            preferred_label: preferred.to_string(),
            ..Outcome::new(OutcomeStatus::Success)
        })
    });

    let result = run_flow(
        &workdir,
        &temp.path().join("runs"),
        "run-probe-cycles",
        runner,
    );
    assert_eq!(result.status, "completed", "route: {:?}", result.route_trace);
    assert_eq!(orient_calls.load(Ordering::SeqCst), 3);
    let commits = result
        .route_trace
        .iter()
        .filter(|node| node.as_str() == "commit_cycle")
        .count();
    assert_eq!(commits, 2, "route: {:?}", result.route_trace);
}

#[test]
fn research_program_guard_halts_stuck_repair_loop() {
    let temp = tempfile::tempdir().expect("tempdir");
    let workdir = temp.path().join("project");
    std::fs::create_dir_all(&workdir).expect("workdir");

    let wd = workdir.clone();
    let mut runner = RuntimeHandlerRunner::new();
    runner.register_thread_safe_handler_fn(HANDLER_CODERGEN, move |runtime| {
        match runtime.node_id.as_str() {
            "orient" => {
                let _ = std::fs::create_dir_all(wd.join(".mathlab"));
                let _ = std::fs::write(wd.join(".mathlab/cycle.md"), "# stuck cycle\n");
            }
            "experiment" => {
                // Evidence that never verifies: the repair loop must be
                // halted by guard_verify, failing the run.
                let _ = std::fs::create_dir_all(wd.join("experiments"));
                let _ = std::fs::write(wd.join("experiments/verify.sh"), "exit 1\n");
            }
            _ => {}
        }
        let preferred = if runtime.node_id == "orient" {
            "Explore"
        } else {
            ""
        };
        Ok(Outcome {
            status: OutcomeStatus::Success,
            preferred_label: preferred.to_string(),
            ..Outcome::new(OutcomeStatus::Success)
        })
    });

    let result = run_flow(
        &workdir,
        &temp.path().join("runs"),
        "run-probe-guard",
        runner,
    );
    assert_eq!(result.status, "failed", "route: {:?}", result.route_trace);
    let guard_hits = result
        .route_trace
        .iter()
        .filter(|node| node.as_str() == "guard_verify")
        .count();
    assert_eq!(guard_hits, 3, "route: {:?}", result.route_trace);
    assert!(
        result.route_trace.last().map(String::as_str) == Some("guard_verify"),
        "program must halt at the exhausted guard: {:?}",
        result.route_trace
    );
}
