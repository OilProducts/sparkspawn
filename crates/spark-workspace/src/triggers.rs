use std::fs;

use serde_json::{Map, Value};
use spark_common::settings::SparkSettings;
use spark_storage::TriggerRepositories;
use spark_triggers::{
    SerializedTrigger, TriggerActivationOutcome, TriggerActivationRequest, TriggerActivationSink,
    TriggerActivationSinkOutcome, TriggerCreateRequest, TriggerDeleteResponse, TriggerService,
    TriggerSourceRuntime, TriggerUpdateRequest, WebhookDispatchOutcome, WebhookHandleRequest,
    WebhookHandleResponse, TERMINAL_PIPELINE_STATUSES,
};
use time::OffsetDateTime;

use crate::conversations::WorkspaceConversationService;
use crate::errors::{WorkspaceError, WorkspaceResult};
use crate::flows::WorkspaceFlowService;

#[derive(Debug, Clone)]
pub struct WorkspaceTriggerService {
    settings: SparkSettings,
}

impl WorkspaceTriggerService {
    pub fn new(settings: SparkSettings) -> Self {
        Self { settings }
    }

    pub fn list_triggers(&self) -> WorkspaceResult<Vec<SerializedTrigger>> {
        TriggerService::new(self.settings.clone())
            .list_triggers()
            .map_err(Into::into)
    }

    pub fn get_trigger(&self, trigger_id: &str) -> WorkspaceResult<SerializedTrigger> {
        TriggerService::new(self.settings.clone())
            .get_trigger(trigger_id)?
            .ok_or_else(|| WorkspaceError::NotFound("Unknown trigger.".to_string()))
    }

    pub fn create_trigger(
        &self,
        request: TriggerCreateRequest,
    ) -> WorkspaceResult<SerializedTrigger> {
        if action_mode(&request.action) != "workspace_draft" {
            let flow_name = required_flow_name(&request.action)?;
            self.ensure_flow_exists(flow_name)?;
        }
        TriggerService::new(self.settings.clone())
            .create_trigger(request)
            .map_err(Into::into)
    }

    pub fn update_trigger(
        &self,
        trigger_id: &str,
        request: TriggerUpdateRequest,
    ) -> WorkspaceResult<SerializedTrigger> {
        if request
            .action
            .as_ref()
            .is_none_or(|action| action_mode(action) != "workspace_draft")
        {
            if let Some(flow_name) = optional_flow_name(request.action.as_ref()) {
                self.ensure_flow_exists(flow_name)?;
            }
        }
        TriggerService::new(self.settings.clone())
            .update_trigger(trigger_id, request)
            .map_err(Into::into)
    }

    pub fn delete_trigger(&self, trigger_id: &str) -> WorkspaceResult<TriggerDeleteResponse> {
        TriggerService::new(self.settings.clone())
            .delete_trigger(trigger_id)
            .map_err(Into::into)
    }

    pub fn handle_webhook(
        &self,
        request: WebhookHandleRequest,
    ) -> WorkspaceResult<WebhookHandleResponse> {
        self.dispatch_webhook(request)
            .map(|outcome| outcome.response)
    }

    pub fn dispatch_webhook(
        &self,
        request: WebhookHandleRequest,
    ) -> WorkspaceResult<WebhookDispatchOutcome> {
        self.source_runtime()
            .process_webhook(request)
            .map_err(Into::into)
    }

    pub fn refresh_trigger_runtime_state(&self) -> WorkspaceResult<Vec<SerializedTrigger>> {
        self.source_runtime()
            .reload_refresh_state()
            .map_err(Into::into)
    }

    pub async fn process_due_trigger_sources(
        &self,
    ) -> WorkspaceResult<Vec<TriggerActivationOutcome>> {
        self.process_due_trigger_sources_at(OffsetDateTime::now_utc())
            .await
    }

    pub async fn process_due_trigger_sources_at(
        &self,
        now: OffsetDateTime,
    ) -> WorkspaceResult<Vec<TriggerActivationOutcome>> {
        self.source_runtime()
            .process_due_sources(now)
            .await
            .map_err(Into::into)
    }

    pub fn emit_flow_event(
        &self,
        payload: Map<String, Value>,
    ) -> WorkspaceResult<Vec<TriggerActivationOutcome>> {
        self.source_runtime()
            .emit_flow_event(payload)
            .map_err(Into::into)
    }

    pub fn emit_terminal_flow_event_for_run(
        &self,
        run_id: &str,
    ) -> WorkspaceResult<Vec<TriggerActivationOutcome>> {
        // Record-only read: runs on every publish cycle, and a full bundle
        // read reparses the entire event log.
        let store = attractor_runtime::RunStore::for_settings(&self.settings);
        let Some(paths) = store
            .find_run_root(run_id)
            .map_err(|error| WorkspaceError::Internal(error.to_string()))?
        else {
            return Ok(Vec::new());
        };
        let Some(record) = store
            .read_run_record(&paths)
            .map_err(|error| WorkspaceError::Internal(error.to_string()))?
        else {
            return Ok(Vec::new());
        };
        let status = record.status.trim().to_ascii_lowercase();
        if !TERMINAL_PIPELINE_STATUSES.contains(&status.as_str()) {
            return Ok(Vec::new());
        }
        let project_path = record
            .project_path
            .trim()
            .to_string()
            .if_empty_then(record.working_directory.trim().to_string());
        self.emit_flow_event(Map::from_iter([
            ("run_id".to_string(), Value::String(record.run_id)),
            ("flow_name".to_string(), Value::String(record.flow_name)),
            (
                "project_path".to_string(),
                if project_path.is_empty() {
                    Value::Null
                } else {
                    Value::String(project_path)
                },
            ),
            ("status".to_string(), Value::String(status)),
        ]))
    }

    fn ensure_flow_exists(&self, flow_name: &str) -> WorkspaceResult<()> {
        WorkspaceFlowService::new(self.settings.clone()).ensure_flow_exists(flow_name)
    }

    fn source_runtime(&self) -> TriggerSourceRuntime {
        TriggerSourceRuntime::with_sink(
            TriggerRepositories::from_settings(&self.settings),
            WorkspaceTriggerActivationSink {
                settings: self.settings.clone(),
            },
        )
    }
}

#[derive(Debug, Clone)]
struct WorkspaceTriggerActivationSink {
    settings: SparkSettings,
}

impl TriggerActivationSink for WorkspaceTriggerActivationSink {
    fn activate(
        &self,
        request: TriggerActivationRequest,
    ) -> spark_triggers::TriggerResult<TriggerActivationSinkOutcome> {
        if request.action.mode == "workspace_draft" {
            return self.launch_workspace_draft_trigger_flow(request);
        }
        let run_id = WorkspaceConversationService::new(self.settings.clone())
            .launch_trigger_flow(request)
            .map_err(|error| spark_triggers::TriggerError::Validation(error.detail()))?;
        Ok(TriggerActivationSinkOutcome {
            run_id: Some(run_id),
            message: Some("Trigger fired successfully.".to_string()),
            no_op: false,
        })
    }
}

impl WorkspaceTriggerActivationSink {
    fn launch_workspace_draft_trigger_flow(
        &self,
        request: TriggerActivationRequest,
    ) -> spark_triggers::TriggerResult<TriggerActivationSinkOutcome> {
        let Some(project_path) = request.action.project_path.as_deref() else {
            return Ok(no_op(
                "Workspace draft trigger action is missing project_path.",
            ));
        };
        let draft_path = std::path::Path::new(project_path)
            .join(".mathlab")
            .join("next-session.json");
        let draft_text = match fs::read_to_string(&draft_path) {
            Ok(text) => text,
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => {
                return Ok(no_op("Workspace draft is missing."))
            }
            Err(error) => return Ok(no_op(format!("Workspace draft could not be read: {error}"))),
        };
        let draft = match serde_json::from_str::<Value>(&draft_text) {
            Ok(Value::Object(draft)) => draft,
            _ => return Ok(no_op("Workspace draft is not valid JSON object.")),
        };
        if draft.get("status").and_then(Value::as_str).map(str::trim) != Some("continue") {
            return Ok(no_op("Workspace draft did not request continuation."));
        }
        let flow_name = match draft.get("flow").and_then(Value::as_str).map(str::trim) {
            Some(flow_name) if !flow_name.is_empty() => flow_name.to_string(),
            _ => return Ok(no_op("Workspace draft is missing flow.")),
        };
        if !flow_allowed(&flow_name, &request.action.flow_allowlist) {
            return Ok(no_op(format!(
                "Workspace draft flow is not allowlisted: {flow_name}"
            )));
        }
        let launch_context = match draft.get("inputs").and_then(Value::as_object) {
            Some(inputs) => Value::Object(inputs.clone()),
            None => return Ok(no_op("Workspace draft inputs must be a JSON object.")),
        };
        WorkspaceFlowService::new(self.settings.clone())
            .ensure_flow_exists(&flow_name)
            .map_err(|error| spark_triggers::TriggerError::Validation(error.detail()))?;
        let mut artifact = Map::from_iter([
            ("flow_name".to_string(), Value::String(flow_name.clone())),
            (
                "summary".to_string(),
                Value::String(format!(
                    "Trigger {} launched workspace draft {flow_name}.",
                    request.trigger_id
                )),
            ),
            (
                "project_path".to_string(),
                Value::String(project_path.to_string()),
            ),
            ("launch_context".to_string(), launch_context),
        ]);
        if let Some(execution_profile_id) = request.action.execution_profile_id.clone() {
            artifact.insert(
                "execution_profile_id".to_string(),
                Value::String(execution_profile_id),
            );
        }
        let run_id = WorkspaceConversationService::new(self.settings.clone())
            .launch_workspace_flow(project_path, &flow_name, &Value::Object(artifact))
            .map_err(spark_triggers::TriggerError::Validation)?;
        let launched_path = draft_path.with_file_name("next-session.launched.json");
        fs::rename(&draft_path, &launched_path).map_err(|error| {
            spark_triggers::TriggerError::Validation(format!(
                "Launched run {run_id}, but failed to consume workspace draft: {error}"
            ))
        })?;
        Ok(TriggerActivationSinkOutcome {
            run_id: Some(run_id),
            message: Some("Trigger fired successfully.".to_string()),
            no_op: false,
        })
    }
}

fn required_flow_name(action: &Map<String, Value>) -> WorkspaceResult<&str> {
    action
        .get("flow_name")
        .and_then(|value| value.as_str())
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .ok_or_else(|| {
            WorkspaceError::Validation("Trigger action requires a flow_name.".to_string())
        })
}

fn action_mode(action: &Map<String, Value>) -> &str {
    action
        .get("mode")
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .unwrap_or("static")
}

fn optional_flow_name(action: Option<&Map<String, Value>>) -> Option<&str> {
    action?
        .get("flow_name")
        .and_then(|value| value.as_str())
        .map(str::trim)
        .filter(|value| !value.is_empty())
}

trait EmptyStringFallback {
    fn if_empty_then(self, fallback: String) -> String;
}

impl EmptyStringFallback for String {
    fn if_empty_then(self, fallback: String) -> String {
        if self.trim().is_empty() {
            fallback
        } else {
            self
        }
    }
}

fn no_op(message: impl Into<String>) -> TriggerActivationSinkOutcome {
    TriggerActivationSinkOutcome {
        run_id: None,
        message: Some(message.into()),
        no_op: true,
    }
}

fn flow_allowed(flow_name: &str, allowlist: &[String]) -> bool {
    allowlist.iter().any(|pattern| {
        let pattern = pattern.trim();
        if let Some(prefix) = pattern.strip_suffix('*') {
            flow_name.starts_with(prefix)
        } else {
            flow_name == pattern
        }
    })
}
