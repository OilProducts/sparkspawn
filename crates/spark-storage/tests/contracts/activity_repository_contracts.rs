use serde_json::json;
use spark_storage::conversation::{TranscriptSegment, TranscriptTurn};
use spark_storage::{ActivityRepository, TranscriptRecord};
use std::io::Write;

#[test]
fn activity_repository_keeps_deltas_out_of_the_logical_transcript() {
    let temp = tempfile::tempdir().expect("tempdir");
    let repository = ActivityRepository::new(temp.path());
    for index in 0..50_000 {
        repository
            .append_event(json!({"type": "content_delta", "index": index}), "now")
            .expect("append delta");
    }
    let completion = repository
        .append_event(json!({"type": "content_completed", "text": "done"}), "now")
        .expect("append completion");
    repository
        .append_transcript(&TranscriptRecord::SegmentUpsert {
            revision: 1,
            committed_at: "now".to_string(),
            source_event_sequence: completion.sequence,
            segment: serde_json::from_value::<TranscriptSegment>(json!({
                "id": "answer", "turn_id": "turn", "kind": "assistant_message", "content": "done"
            }))
            .expect("segment"),
        })
        .expect("append semantic record");

    assert_eq!(repository.read_events().expect("events").len(), 50_001);
    assert_eq!(
        repository.read_transcript_records().expect("records").len(),
        1
    );
    assert_eq!(
        repository
            .hydrate_transcript()
            .expect("transcript")
            .segments
            .len(),
        1
    );
    assert!(repository
        .uncommitted_event_suffix()
        .expect("suffix")
        .is_empty());
}

#[test]
fn hydration_is_last_write_wins_by_stable_id() {
    let temp = tempfile::tempdir().expect("tempdir");
    let repository = ActivityRepository::new(temp.path());
    for (revision, content) in [(1, "working"), (2, "complete")] {
        let event = repository
            .append_event(json!({"type": "turn_completed"}), "now")
            .unwrap();
        repository
            .append_transcript(&TranscriptRecord::TurnUpsert {
                revision,
                committed_at: "now".to_string(),
                source_event_sequence: event.sequence,
                turn: TranscriptTurn {
                    id: "turn".to_string(),
                    content: content.to_string(),
                    ..Default::default()
                },
            })
            .unwrap();
    }
    let transcript = repository.hydrate_transcript().unwrap();
    assert_eq!(transcript.turns.len(), 1);
    assert_eq!(transcript.turns[0].content, "complete");
}

#[test]
fn append_discards_partial_crash_tails_without_corrupting_the_next_record() {
    let temp = tempfile::tempdir().expect("tempdir");
    let repository = ActivityRepository::new(temp.path());
    let first = repository
        .append_event(json!({"type": "first"}), "now")
        .expect("first event");
    let mut events = std::fs::OpenOptions::new()
        .append(true)
        .open(repository.events_path())
        .expect("events");
    write!(events, "{{\"sequence\":2").expect("partial event");
    drop(events);

    let second = repository
        .append_event(json!({"type": "second"}), "now")
        .expect("second event");
    assert_eq!(second.sequence, first.sequence + 1);
    assert_eq!(repository.read_events().expect("strict events").len(), 2);

    repository
        .append_transcript(&TranscriptRecord::TurnUpsert {
            revision: 1,
            committed_at: "now".to_string(),
            source_event_sequence: first.sequence,
            turn: TranscriptTurn {
                id: "first".to_string(),
                ..Default::default()
            },
        })
        .expect("first transcript");
    let mut transcript = std::fs::OpenOptions::new()
        .append(true)
        .open(repository.transcript_path())
        .expect("transcript");
    write!(transcript, "{{\"type\":\"turn_upsert\"").expect("partial transcript");
    drop(transcript);

    repository
        .append_transcript(&TranscriptRecord::TurnUpsert {
            revision: 2,
            committed_at: "now".to_string(),
            source_event_sequence: second.sequence,
            turn: TranscriptTurn {
                id: "second".to_string(),
                ..Default::default()
            },
        })
        .expect("second transcript");
    assert_eq!(
        repository
            .read_transcript_records()
            .expect("strict transcript")
            .len(),
        2
    );
}

#[test]
fn chat_and_execution_repositories_persist_identical_transcript_records() {
    let temp = tempfile::tempdir().expect("tempdir");
    let chat = ActivityRepository::new(temp.path().join("chat"));
    let execution = ActivityRepository::new(temp.path().join("execution"));
    let record = TranscriptRecord::SegmentUpsert {
        revision: 1,
        committed_at: "2026-08-09T00:00:00Z".to_string(),
        source_event_sequence: 1,
        segment: serde_json::from_value(json!({
            "id": "answer", "turn_id": "turn", "kind": "assistant_message",
            "status": "complete", "content": "same logical unit"
        }))
        .expect("segment"),
    };
    for repository in [&chat, &execution] {
        repository
            .append_event(json!({"type": "content_completed"}), "2026-08-09T00:00:00Z")
            .expect("event");
        repository.append_transcript(&record).expect("transcript");
    }
    assert_eq!(
        std::fs::read(chat.transcript_path()).expect("chat transcript"),
        std::fs::read(execution.transcript_path()).expect("execution transcript")
    );
}

#[test]
fn missing_completion_is_recovered_exactly_once() {
    let temp = tempfile::tempdir().expect("tempdir");
    let repository = ActivityRepository::new(temp.path());
    repository
        .append_event(
            json!({"type": "content_completed", "content": "recovered"}),
            "now",
        )
        .expect("completion event");

    for _restart in 0..2 {
        for event in repository
            .uncommitted_event_suffix()
            .expect("uncommitted suffix")
        {
            repository
                .append_transcript(&TranscriptRecord::SegmentUpsert {
                    revision: repository.read_transcript_records().expect("records").len() as u64
                        + 1,
                    committed_at: event.committed_at,
                    source_event_sequence: event.sequence,
                    segment: serde_json::from_value(json!({
                        "id": "answer", "turn_id": "turn", "kind": "assistant_message",
                        "status": "complete", "content": event.event["content"]
                    }))
                    .expect("segment"),
                })
                .expect("recover completion");
        }
    }
    assert_eq!(
        repository.read_transcript_records().expect("records").len(),
        1
    );
}

#[test]
fn transcript_cursor_reads_only_the_new_suffix_in_a_large_execution() {
    let temp = tempfile::tempdir().expect("tempdir");
    let repository = ActivityRepository::new(temp.path());
    for revision in 1..=10_000 {
        let event = repository
            .append_event(json!({"type": "content_completed"}), "now")
            .expect("event");
        repository
            .append_transcript(&TranscriptRecord::SegmentUpsert {
                revision,
                committed_at: "now".to_string(),
                source_event_sequence: event.sequence,
                segment: serde_json::from_value(json!({
                    "id": format!("segment-{revision}"), "turn_id": "turn",
                    "kind": "assistant_message", "status": "complete"
                }))
                .expect("segment"),
            })
            .expect("transcript");
    }
    let (initial, cursor) = repository
        .read_transcript_records_from(0)
        .expect("initial publication");
    assert_eq!(initial.len(), 10_000);

    let event = repository
        .append_event(json!({"type": "content_completed"}), "now")
        .expect("event");
    repository
        .append_transcript(&TranscriptRecord::SegmentUpsert {
            revision: 10_001,
            committed_at: "now".to_string(),
            source_event_sequence: event.sequence,
            segment: serde_json::from_value(json!({
                "id": "latest", "turn_id": "turn", "kind": "assistant_message",
                "status": "complete"
            }))
            .expect("segment"),
        })
        .expect("transcript");

    let (suffix, next_cursor) = repository
        .read_transcript_records_from(cursor)
        .expect("incremental publication");
    assert_eq!(suffix.len(), 1);
    assert_eq!(suffix[0].revision(), 10_001);
    assert!(next_cursor > cursor);
}

#[test]
fn architecture_has_one_activity_writer_and_no_run_projection_sources() {
    let repository_root = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .and_then(std::path::Path::parent)
        .expect("repository root");
    for relative in [
        "crates/attractor-runtime/src/transcript.rs",
        "crates/attractor-runtime/src/segments.rs",
        "crates/attractor-runtime/src/journal_cache.rs",
        "crates/spark-storage/src/conversation/migrate.rs",
    ] {
        assert!(
            !repository_root.join(relative).exists(),
            "{relative} returned"
        );
    }
    let storage = std::fs::read_to_string(
        repository_root.join("crates/spark-storage/src/conversation/store.rs"),
    )
    .expect("conversation store");
    assert!(storage.contains("ActivityRepository"));
    assert!(!storage.contains("transcript.json\""));
    assert!(!storage.contains("journal.jsonl"));
}
